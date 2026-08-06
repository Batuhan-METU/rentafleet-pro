"""``agent_service.stream_ai_agent_sse`` — streaming + function-calling ajan
döngüsü. OpenAI client MOCK'lanır (CI'da gerçek API'ye bağlanılmaz);
gerçek API ile canlı doğrulama ayrıca tarayıcıda elle yapıldı.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from backend.apps.ai.models import AIPendingAction
from backend.apps.companies.models import CustomUser
from backend.infrastructure.services.ai import agent_service
from backend.infrastructure.services.ai import ai_consultant_service as base

pytestmark = pytest.mark.django_db


def _request(user: CustomUser) -> Request:
    django_request = APIRequestFactory().post("/api/ai/consult/")
    request = Request(django_request)
    request._user = user  # type: ignore[attr-defined]
    return request


def _content_chunk(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text, tool_calls=None))])


def _tool_call_chunk(index: int, *, id: str | None = None, name: str | None = None, arguments: str | None = None):  # noqa: A002
    tc = SimpleNamespace(index=index, id=id, function=SimpleNamespace(name=name, arguments=arguments))
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None, tool_calls=[tc]))])


def _parse_sse(lines: list[str]) -> list[dict]:
    events = []
    for line in lines:
        line = line.strip()
        if line.startswith("data:"):
            events.append(json.loads(line[len("data:"):].strip()))
    return events


def _patch_client(monkeypatch, fake_client) -> None:
    monkeypatch.setattr(base, "_openai_client", lambda: fake_client)


def test_no_api_key_falls_back_to_rule_based_response(monkeypatch, company, manager):
    monkeypatch.setattr(base, "_openai_client", lambda: None)

    lines = list(agent_service.stream_ai_agent_sse(_request(manager), "Filo özeti ver", [], company_id=company.pk))
    events = _parse_sse(lines)

    assert any("content" in e for e in events)
    assert events[-1] == {"done": True}


def test_read_tool_call_executes_and_loop_continues_with_result(monkeypatch, company, manager):
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        [_tool_call_chunk(0, id="call_1", name="get_fleet_overview", arguments="{}")],
        [_content_chunk("Filonuzda "), _content_chunk("araç yok.")],
    ]
    _patch_client(monkeypatch, fake_client)

    lines = list(
        agent_service.stream_ai_agent_sse(_request(manager), "Filoda kaç araç var?", [], company_id=company.pk)
    )
    events = _parse_sse(lines)

    assert fake_client.chat.completions.create.call_count == 2
    joined_content = "".join(e["content"] for e in events if "content" in e)
    assert joined_content == "Filonuzda araç yok."
    assert events[-1] == {"done": True}

    # İkinci çağrıya giden mesajlarda bir "tool" rolü sonucu olmalı.
    second_call_messages = fake_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert any(m["role"] == "tool" for m in second_call_messages)


def test_mutation_tool_call_creates_pending_action_instead_of_executing(monkeypatch, company, manager):
    from datetime import date, timedelta

    from backend.apps.customer_profiles.models import Driver
    from backend.apps.rentals.models import Rental
    from backend.apps.vehicles.models import Vehicle, VehicleStatus

    driver = Driver.objects.create(
        company=company,
        first_name="Ajan",
        last_name="Testi",
        national_id="11111111119",
        birth_date=date.today() - timedelta(days=365 * 30),
        phone="5551239876",
        license_number="X000999",
        city="Bursa",
    )
    vehicle = Vehicle.objects.create(
        company=company,
        plate_number="34AJT001",
        brand="Fiat",
        model="Egea",
        production_year=2023,
        current_km=100,
        status=VehicleStatus.AVAILABLE,
    )
    args = {
        "driver_id": driver.pk,
        "vehicle_id": vehicle.pk,
        "pickup_date": (date.today() + timedelta(days=1)).isoformat(),
        "dropoff_date": (date.today() + timedelta(days=3)).isoformat(),
    }

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        [_tool_call_chunk(0, id="call_1", name="create_rental", arguments=json.dumps(args))],
    ]
    _patch_client(monkeypatch, fake_client)

    lines = list(
        agent_service.stream_ai_agent_sse(_request(manager), "Bu aracı kirala", [], company_id=company.pk)
    )
    events = _parse_sse(lines)

    # Mutasyon GERÇEKTEN çalıştırılmadı — sadece önerildi.
    assert not Rental.objects.filter(driver=driver, vehicle=vehicle).exists()
    assert fake_client.chat.completions.create.call_count == 1

    confirmation_events = [e["confirmation"] for e in events if "confirmation" in e]
    assert len(confirmation_events) == 1
    pending = AIPendingAction.objects.get(id=confirmation_events[0]["action_id"])
    assert pending.tool_name == "create_rental"
    assert pending.company_id == company.pk
    assert pending.consumed_at is None


def test_roundtrip_limit_prevents_infinite_tool_loop(monkeypatch, company, manager):
    fake_client = MagicMock()
    # Model HER seferinde tekrar bir read-tool çağırıyor, asla düz metinle bitirmiyor.
    fake_client.chat.completions.create.side_effect = [
        [_tool_call_chunk(0, id=f"call_{i}", name="get_fleet_overview", arguments="{}")]
        for i in range(agent_service.MAX_TOOL_ROUNDTRIPS)
    ]
    _patch_client(monkeypatch, fake_client)

    lines = list(agent_service.stream_ai_agent_sse(_request(manager), "Sürekli sorgula", [], company_id=company.pk))
    events = _parse_sse(lines)

    assert fake_client.chat.completions.create.call_count == agent_service.MAX_TOOL_ROUNDTRIPS
    assert events[-1] == {"done": True}
    assert any("çok fazla adım" in e.get("content", "") for e in events)
