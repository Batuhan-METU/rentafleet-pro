"""AI Filo Operasyon Asistanı — streaming + function-calling ajan döngüsü.

Eski salt-okunur "AI Filo Danışmanı" (``ai_consultant_service.py``) burada
GERÇEK EYLEMLER yapabilen bir ajana genişletilir:

* Model, okuma (read) tool'larını (bkz. ``tools/read_tools.py``) DOĞRUDAN
  çalıştırabilir — sonuç modele geri beslenir, döngü devam eder.
* Mutasyon (write) tool'larını (bkz. ``tools/write_tools.py``) ise asla
  doğrudan ÇALIŞTIRMAZ; bunun yerine bir ``AIPendingAction`` oluşturur ve
  sohbette bir onay kartı önerir. Gerçek çalıştırma yalnızca kullanıcı
  "Onayla"ya bastığında ``AIActionConfirmView`` üzerinden olur.

OpenAI API'si yapılandırılmamışsa (``OPENAI_API_KEY`` boş), tool-calling
YAPILMAZ — eski davranışla birebir aynı, kural-tabanlı Türkçe fallback yanıtı
kelime kelime akıtılır (bkz. ``_fallback_response``/``_simulate_stream``).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from typing import Any

from django.conf import settings
from django.utils import timezone
from rest_framework.request import Request

from backend.apps.ai.models import AIPendingAction
from backend.common.multitenancy_tools.scope import require_user_company
from backend.infrastructure.services.ai import ai_consultant_service as base
from backend.infrastructure.services.ai.tools import (  # noqa: F401 (tool kaydı için)
    read_tools,
    write_tools,
)
from backend.infrastructure.services.ai.tools.registry import TOOLS, openai_tool_schemas

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDTRIPS = 4
MAX_HISTORY_MESSAGES = 12

_WEEKDAYS_TR = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")

AGENT_SYSTEM_PROMPT_TR = (
    "Sen RentA-Fleet PRO sisteminin AI Filo Operasyon Asistanısın. Karşındaki "
    "kişi bir Araç Kiralama Şirketi Müdürü veya Operasyon Personelidir. "
    "Cevapların her zaman profesyonel, Türkçe, kısa ve net olmalıdır. "
    "Sana verilen tool'ları kullanarak GERÇEK bilgi sorgulayabilir ve GERÇEK "
    "işlemler önerebilirsin — yalnızca tool sonuçlarındaki gerçek verilere "
    "dayan, uydurma bilgi/istatistik üretme. Kullanıcı isim/plaka gibi "
    "belirsiz bir bilgi verdiğinde önce ilgili sorgu tool'unu (list_vehicles, "
    "list_drivers vb.) kullanarak doğru ID'yi bul, sonra asıl işlemi yap. "
    "ÇOK ÖNEMLİ: bir mutasyon tool'u (ör. create_driver, create_loan) "
    "kullanıcının SANA SÖYLEMEDİĞİ zorunlu bir bilgi istiyorsa (T.C. kimlik "
    "no, telefon, ehliyet no, doğum tarihi, adres, tutar vb. gerçek dünya "
    "verileri) ASLA uydurma/varsayılan/boş bir değer ÜRETİP tool'u ÇAĞIRMA — "
    "bunun yerine kullanıcıya hangi bilgilerin eksik olduğunu sorup bekle, "
    "yalnızca kullanıcı bu bilgileri gerçekten verdikten SONRA tool'u çağır. "
    "Bir mutasyon tool'u çağırdığında bu İSTEK OLARAK sohbete bir onay kartı "
    "döner, sen bunu zaten biliyorsun — kullanıcıya ayrıca 'onaylıyor musunuz' "
    "diye SORMA, doğrudan tool'u çağır."
)


def _tool_error(exc: Exception) -> str:
    return json.dumps({"error": str(exc)}, ensure_ascii=False)


def _run_read_tool(request: Request, tool_name: str, args: dict[str, Any]) -> str:
    try:
        result = TOOLS[tool_name].handler(request, args)
    except Exception as exc:  # noqa: BLE001 - sonuç modele "hata" olarak geri beslenir, tur çökmez
        return _tool_error(exc)
    return json.dumps(result, ensure_ascii=False, default=str)


def _prepare_confirmation(request: Request, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    spec = TOOLS[tool_name]
    assert spec.summary is not None  # ToolSpec.__post_init__ mutasyon tool'larında garanti eder
    try:
        summary_text = spec.summary(request, args)
    except Exception as exc:  # noqa: BLE001 - model hatayı görüp düzeltilmiş bir çağrı deneyebilsin
        return {"error": str(exc)}

    company = require_user_company(request)
    pending = AIPendingAction.objects.create(
        company=company,
        requested_by=request.user,
        tool_name=tool_name,
        arguments=args,
        summary=summary_text,
    )
    return {"action_id": str(pending.id), "tool": tool_name, "summary": summary_text}


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _fallback_sse(query: str, context: base.FleetContext) -> Iterator[str]:
    for chunk in base._simulate_stream(base._fallback_response(query, context)):
        yield _sse({"content": chunk})
    yield _sse({"done": True})


def stream_ai_agent_sse(
    request: Request,
    user_query: str,
    history: list[dict[str, Any]],
    *,
    company_id: int,
) -> Iterator[str]:
    """SSE formatında satırlar üretir: ``content``, ``confirmation`` veya ``error`` + son olarak ``done``."""
    try:
        yield from _stream_agent(request, user_query, history, company_id=company_id)
    except Exception as exc:
        logger.exception("AI ajan stream hatası")
        yield _sse({"error": str(exc)})


def _history_messages(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for turn in history[-MAX_HISTORY_MESSAGES:]:
        role = turn.get("role")
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        if role == "user":
            messages.append({"role": "user", "content": text})
        elif role == "ai":
            messages.append({"role": "assistant", "content": text})
    return messages


def _stream_agent(
    request: Request,
    user_query: str,
    history: list[dict[str, Any]],
    *,
    company_id: int,
) -> Iterator[str]:
    query = (user_query or "").strip()
    context = base._build_fleet_context(company_id=company_id)
    context_text = base._context_summary_text(context)

    client = base._openai_client()
    if client is None:
        yield from _fallback_sse(query, context)
        return

    today_line = f"BUGÜNÜN TARİHİ: {timezone.localdate().isoformat()} ({_WEEKDAYS_TR[timezone.localdate().weekday()]})"
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": f"{AGENT_SYSTEM_PROMPT_TR}\n\n{today_line}\n\n{context_text}"},
        *_history_messages(history),
        {"role": "user", "content": query},
    ]
    model = os.getenv("OPENAI_MODEL", getattr(settings, "OPENAI_MODEL", "gpt-4o"))

    for _round in range(MAX_TOOL_ROUNDTRIPS):
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=openai_tool_schemas(),
                tool_choice="auto",
                temperature=0.2,
                stream=True,
            )
        except Exception as exc:
            logger.warning("OpenAI stream başlatılamadı, fallback'e geçiliyor: %s", exc)
            yield from _fallback_sse(query, context)
            return

        collected_text = ""
        tool_calls: dict[int, dict[str, Any]] = {}

        for event in stream:
            delta = event.choices[0].delta
            if delta.content:
                collected_text += delta.content
                yield _sse({"content": delta.content})
            for tc in delta.tool_calls or []:
                entry = tool_calls.setdefault(tc.index, {"id": None, "name": "", "arguments": ""})
                if tc.id:
                    entry["id"] = tc.id
                if tc.function and tc.function.name:
                    entry["name"] += tc.function.name
                if tc.function and tc.function.arguments:
                    entry["arguments"] += tc.function.arguments

        if not tool_calls:
            yield _sse({"done": True})
            return

        messages.append(
            {
                "role": "assistant",
                "content": collected_text or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in tool_calls.values()
                ],
            }
        )

        pending_confirmation: dict[str, Any] | None = None
        for tc in tool_calls.values():
            tool_name = tc["name"]
            try:
                args = json.loads(tc["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}

            if tool_name not in TOOLS:
                tool_output = json.dumps({"error": f"Bilinmeyen tool: {tool_name}"}, ensure_ascii=False)
            elif TOOLS[tool_name].kind == "mutation":
                if pending_confirmation is not None:
                    tool_output = json.dumps(
                        {"error": "Aynı anda yalnızca bir eylem için onay istenebilir; önce diğerini tamamlayın."},
                        ensure_ascii=False,
                    )
                else:
                    confirmation = _prepare_confirmation(request, tool_name, args)
                    if "error" in confirmation:
                        tool_output = json.dumps(confirmation, ensure_ascii=False)
                    else:
                        pending_confirmation = confirmation
                        tool_output = json.dumps({"status": "confirmation_pending"}, ensure_ascii=False)
            else:
                tool_output = _run_read_tool(request, tool_name, args)

            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_output})

        if pending_confirmation is not None:
            yield _sse({"confirmation": pending_confirmation})
            yield _sse({"done": True})
            return

        # Yalnızca read tool'lar çalıştıysa döngü devam eder — model sonucu yorumlayıp
        # ya doğal dil yanıtı üretir ya da başka bir tool daha çağırır.

    yield _sse({"content": "Bu istek için çok fazla adım gerekti, lütfen daha spesifik bir şekilde tekrar sorar mısınız?"})
    yield _sse({"done": True})


def execute_confirmed_action(request: Request, pending: AIPendingAction) -> dict[str, Any]:
    """Onaylanmış bir ``AIPendingAction``'ı GERÇEKTEN çalıştırır."""
    spec = TOOLS[pending.tool_name]
    return spec.handler(request, pending.arguments)
