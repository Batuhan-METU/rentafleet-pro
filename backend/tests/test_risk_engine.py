"""Risk kuralları + RiskEngine skor/seviye/blok davranışı."""

from __future__ import annotations

from decimal import Decimal

from backend.domain.risk.engine import RiskEngine
from backend.domain.risk.rules import build_default_risk_rules
from backend.domain.rule_engine.engine import RuleEngine
from backend.domain.rule_engine.thresholds import score_to_risk_level
from backend.domain.shared.enums import RiskLevel
from backend.tests.factories import make_snapshot


def _engine() -> RiskEngine:
    # DB'ye gitmeden (RuleSet sorgusu yapmadan) kod tabanlı varsayılan
    # kurallarla çalışan bir RiskEngine — domain katmanı DB'siz test edilebilir.
    return RiskEngine(RuleEngine("RISK", build_default_risk_rules()))


def test_clean_customer_is_very_low_risk_and_approved():
    result = _engine().evaluate(make_snapshot())

    assert result.score == 0
    assert result.level == RiskLevel.VERY_LOW.value
    assert result.approved is True


def test_blacklisted_customer_is_hard_blocked_regardless_of_score():
    result = _engine().evaluate(make_snapshot(is_blacklisted=True))

    assert result.approved is False
    assert "kara listesinde" in result.blockers[0]


def test_young_driver_and_new_license_stack_score():
    snapshot = make_snapshot(age=19, license_age_years=0.5)
    result = _engine().evaluate(snapshot)

    # YOUNG_DRIVER_MODERATE (15, 19<=yaş<21) + NEW_LICENSE_MODERATE (15, 0.5-2 yıl) = 30
    assert result.score == 30
    assert result.level == RiskLevel.LOW.value
    assert result.approved is True


def test_severe_young_driver_and_new_license_score_higher_than_moderate():
    """Kademeli puanlama: 18 yaş/3 ay ehliyet, 19 yaş/6 ay ehliyetten daha
    yüksek puan almalı (eskiden ikisi de aynı sabit puanı alıyordu)."""
    moderate = _engine().evaluate(make_snapshot(age=19, license_age_years=0.5))
    severe = _engine().evaluate(make_snapshot(age=18, license_age_years=0.25))

    assert severe.score > moderate.score


def test_very_high_score_triggers_hard_block_at_threshold():
    # Findeks düşük (22) + gelir düşük (8, WARN puana katkı yapmaz) + ödeme
    # gecikmesi (12) + hasar (10) + kaza (15) + geç teslim - tek sefer (6) +
    # trafik cezası (6) + genç sürücü orta kademe (15) + yeni ehliyet orta
    # kademe (15) = 101 -> clamp 100 -> VERY_HIGH
    snapshot = make_snapshot(
        age=19,
        license_age_years=0.5,
        findeks_score=400,
        monthly_income=Decimal("5000"),
        payment_delay_count=2,
        damaged_return_count=1,
        accident_count=1,
        late_return_count=1,
        traffic_fine_count=5,
    )
    result = _engine().evaluate(snapshot)

    assert result.score == 100
    assert result.level == RiskLevel.VERY_HIGH.value
    assert result.approved is False
    assert "çok yüksek" in result.blockers[-1]


def test_whitelist_and_loyalty_bonuses_reduce_score_but_never_below_zero():
    snapshot = make_snapshot(is_whitelisted=True, vip_tier="GOLD", loyalty_level=5)
    result = _engine().evaluate(snapshot)

    assert result.score == 0
    assert result.level == RiskLevel.VERY_LOW.value


def test_cancellation_rate_rule_fires_above_threshold_with_enough_history():
    # 3 iptal / (5 tamamlanan + 3 iptal) = %37.5 > %30 eşiği, toplam 8 girişim (>=3).
    snapshot = make_snapshot(total_rentals=5, cancelled_count=3)
    result = _engine().evaluate(snapshot)

    assert result.score == 12
    codes = [o.code for o in result.outcomes]
    assert "CANCELLATION_RATE" in codes


def test_cancellation_rate_rule_does_not_fire_below_threshold():
    # 1 iptal / 6 girişim = %16.7 < %30 eşiği.
    snapshot = make_snapshot(total_rentals=5, cancelled_count=1)
    result = _engine().evaluate(snapshot)

    assert result.score == 0


def test_cancellation_rate_rule_does_not_fire_with_too_little_history():
    # Tek bir iptal, hiç tamamlanmış kiralama yok — oran %100 ama örneklem
    # (1 girişim < 3) çok küçük, yeni bir sürücüyü haksız damgalamamalı.
    snapshot = make_snapshot(total_rentals=0, cancelled_count=1)
    result = _engine().evaluate(snapshot)

    codes = [o.code for o in result.outcomes]
    assert "CANCELLATION_RATE" not in codes


def test_score_to_risk_level_bands_are_contiguous_and_cover_0_to_100():
    for score in range(0, 101):
        level = score_to_risk_level(score)
        assert isinstance(level, RiskLevel)
    assert score_to_risk_level(0) == RiskLevel.VERY_LOW
    assert score_to_risk_level(20) == RiskLevel.VERY_LOW
    assert score_to_risk_level(21) == RiskLevel.LOW
    assert score_to_risk_level(81) == RiskLevel.VERY_HIGH
    assert score_to_risk_level(100) == RiskLevel.VERY_HIGH
    # Aralık dışı değerler clamp edilir, hata fırlatmaz.
    assert score_to_risk_level(-50) == RiskLevel.VERY_LOW
    assert score_to_risk_level(500) == RiskLevel.VERY_HIGH
