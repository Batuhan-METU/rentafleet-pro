"""``AIPendingAction`` modeli — AI onay kartının güvenlik temeli.

Süre dolumu, tek kullanımlık tüketim ve varsayılan TTL davranışını doğrular.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from backend.apps.ai.models import PENDING_ACTION_TTL, AIPendingAction
from backend.apps.companies.choices import UserRole
from backend.apps.companies.models import CustomUser

pytestmark = pytest.mark.django_db


def _pending(company, user, **overrides) -> AIPendingAction:
    defaults = dict(
        company=company,
        requested_by=user,
        tool_name="create_rental",
        arguments={"driver_id": 1, "vehicle_id": 2},
        summary="Test özeti.",
    )
    defaults.update(overrides)
    return AIPendingAction.objects.create(**defaults)


def test_save_auto_fills_expires_at_with_default_ttl(company, manager):
    before = timezone.now()
    pending = _pending(company, manager)
    assert pending.expires_at >= before + PENDING_ACTION_TTL - timedelta(seconds=5)
    assert pending.expires_at <= before + PENDING_ACTION_TTL + timedelta(seconds=5)


def test_explicit_expires_at_is_not_overwritten(company, manager):
    custom_expiry = timezone.now() + timedelta(hours=2)
    pending = _pending(company, manager, expires_at=custom_expiry)
    assert pending.expires_at == custom_expiry


def test_is_expired_reflects_expires_at(company, manager):
    future = _pending(company, manager, expires_at=timezone.now() + timedelta(minutes=5))
    past = _pending(company, manager, expires_at=timezone.now() - timedelta(minutes=1))
    assert future.is_expired is False
    assert past.is_expired is True


def test_is_consumed_reflects_consumed_at(company, manager):
    pending = _pending(company, manager)
    assert pending.is_consumed is False
    pending.consumed_at = timezone.now()
    pending.save(update_fields=["consumed_at"])
    assert pending.is_consumed is True


def test_different_companies_get_independent_pending_actions(company, manager):
    other_company = company.__class__.objects.create(name="other-tenant", tax_number="0000000002")
    other_user = CustomUser.objects.create_user(
        username="other_manager",
        password="test-pass-123",
        company=other_company,
        role=UserRole.FLEET_MANAGER,
    )
    mine = _pending(company, manager)
    theirs = _pending(other_company, other_user)
    assert mine.company_id != theirs.company_id
    assert AIPendingAction.objects.filter(company=company).count() == 1
    assert AIPendingAction.objects.filter(company=other_company).count() == 1
