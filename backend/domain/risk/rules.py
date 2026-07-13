"""Varsayılan risk kuralları."""

from __future__ import annotations

from decimal import Decimal

from backend.domain.rule_engine.engine import RuleDefinitionData
from backend.domain.shared.enums import RuleEffect

MIN_DRIVER_AGE = 21
MAX_DRIVER_AGE = 70
MIN_LICENSE_YEARS = 2
MIN_FINDEX_SCORE = 600
LOW_INCOME_THRESHOLD = Decimal("15000")


def build_default_risk_rules() -> list[RuleDefinitionData]:
  return [
      RuleDefinitionData(
          code="BLACKLIST",
          priority=1,
          effect=RuleEffect.BLOCK,
          points=0,
          message="Müşteri şirket kara listesinde.",
          predicate=lambda c: c.is_blacklisted,
      ),
      RuleDefinitionData(
          code="BANK_BLACKLIST",
          priority=2,
          effect=RuleEffect.BLOCK,
          points=0,
          message="Banka kara listesi kaydı mevcut.",
          predicate=lambda c: c.bank_blacklist_flag,
      ),
      RuleDefinitionData(
          code="FRAUD_SUSPICION",
          priority=3,
          effect=RuleEffect.BLOCK,
          points=0,
          message="Dolandırıcılık şüphesi — manuel inceleme gerekli.",
          predicate=lambda c: c.fraud_suspicion,
      ),
      RuleDefinitionData(
          code="DOCUMENT_FRAUD",
          priority=4,
          effect=RuleEffect.BLOCK,
          points=0,
          message="Sahte belge şüphesi.",
          predicate=lambda c: c.document_fraud_suspicion,
      ),
      RuleDefinitionData(
          code="ENFORCEMENT_RECORD",
          priority=5,
          effect=RuleEffect.BLOCK,
          points=0,
          message="İcra kaydı nedeniyle kiralama onaylanamaz.",
          predicate=lambda c: c.has_enforcement_record,
      ),
      RuleDefinitionData(
          code="YOUNG_DRIVER",
          priority=10,
          effect=RuleEffect.ADD_SCORE,
          points=20,
          message="Sürücü yaşı minimum eşiğin altında.",
          predicate=lambda c: c.age < MIN_DRIVER_AGE,
      ),
      RuleDefinitionData(
          code="SENIOR_DRIVER",
          priority=11,
          effect=RuleEffect.ADD_SCORE,
          points=15,
          message="Sürücü yaşı üst risk eşiğinde.",
          predicate=lambda c: c.age > MAX_DRIVER_AGE,
      ),
      RuleDefinitionData(
          code="NEW_LICENSE",
          priority=20,
          effect=RuleEffect.ADD_SCORE,
          points=18,
          message="Ehliyet süresi 2 yıldan kısa.",
          predicate=lambda c: c.license_age_years < MIN_LICENSE_YEARS,
      ),
      RuleDefinitionData(
          code="LOW_FINDEX",
          priority=30,
          effect=RuleEffect.ADD_SCORE,
          points=22,
          message="Findeks skoru düşük.",
          predicate=lambda c: c.findeks_score is not None and c.findeks_score < MIN_FINDEX_SCORE,
      ),
      RuleDefinitionData(
          code="LOW_INCOME",
          priority=31,
          effect=RuleEffect.WARN,
          points=8,
          message="Aylık gelir düşük görünüyor.",
          predicate=lambda c: c.monthly_income is not None and c.monthly_income < LOW_INCOME_THRESHOLD,
      ),
      RuleDefinitionData(
          code="PAYMENT_DELAYS",
          priority=32,
          effect=RuleEffect.ADD_SCORE,
          points=12,
          message="Geçmiş ödeme gecikmeleri var.",
          predicate=lambda c: c.payment_delay_count > 0,
      ),
      RuleDefinitionData(
          code="DAMAGE_HISTORY",
          priority=40,
          effect=RuleEffect.ADD_SCORE,
          points=10,
          message="Hasarlı teslim geçmişi.",
          predicate=lambda c: c.damaged_return_count > 0,
      ),
      RuleDefinitionData(
          code="ACCIDENT_HISTORY",
          priority=41,
          effect=RuleEffect.ADD_SCORE,
          points=15,
          message="Kaza geçmişi kayıtlı.",
          predicate=lambda c: c.accident_count > 0,
      ),
      RuleDefinitionData(
          code="LATE_RETURNS",
          priority=42,
          effect=RuleEffect.ADD_SCORE,
          points=8,
          message="Geç teslim geçmişi.",
          predicate=lambda c: c.late_return_count > 0,
      ),
      RuleDefinitionData(
          code="TRAFFIC_FINES",
          priority=43,
          effect=RuleEffect.ADD_SCORE,
          points=6,
          message="Yoğun trafik cezası geçmişi.",
          predicate=lambda c: c.traffic_fine_count >= 3,
      ),
      RuleDefinitionData(
          code="FIRST_RENTAL",
          priority=50,
          effect=RuleEffect.ADD_SCORE,
          points=5,
          message="İlk kiralama — sınırlı geçmiş.",
          predicate=lambda c: c.is_first_rental,
      ),
      RuleDefinitionData(
          code="UNVERIFIED_IDENTITY",
          priority=60,
          effect=RuleEffect.WARN,
          points=5,
          message="Kimlik doğrulaması tamamlanmadı.",
          predicate=lambda c: not c.identity_verified,
      ),
      RuleDefinitionData(
          code="WHITELIST_BONUS",
          priority=90,
          effect=RuleEffect.ADD_SCORE,
          points=-15,
          message="Beyaz liste müşterisi.",
          predicate=lambda c: c.is_whitelisted,
      ),
      RuleDefinitionData(
          code="VIP_BONUS",
          priority=91,
          effect=RuleEffect.ADD_SCORE,
          points=-10,
          message="VIP müşteri indirimi.",
          predicate=lambda c: c.vip_tier in {"SILVER", "GOLD", "PLATINUM"},
      ),
      RuleDefinitionData(
          code="LOYALTY_BONUS",
          priority=92,
          effect=RuleEffect.ADD_SCORE,
          points=-5,
          message="Sadakat seviyesi avantajı.",
          predicate=lambda c: c.loyalty_level >= 3,
      ),
  ]