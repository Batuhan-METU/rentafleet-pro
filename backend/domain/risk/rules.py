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
      # YOUNG_DRIVER/SENIOR_DRIVER/NEW_LICENSE — eskiden tek bir sert eşik,
      # ikili (0 ya da tam puan) puanlıyordu: 20 yaş 11 aylık biri ile 21
      # yaşındaki biri arasında hiç fark yoktu ama tam +20/0 sıçraması
      # vardı. Aynı kod, TEK ANLAMLI kavramı iki kademeye bölerek (mevcut
      # RuleEngine mimarisi DEĞİŞMEDEN, sadece iki ayrı basit kural olarak)
      # daha kademeli bir risk eğrisi üretir.
      RuleDefinitionData(
          code="YOUNG_DRIVER_SEVERE",
          priority=10,
          effect=RuleEffect.ADD_SCORE,
          points=25,
          message="Sürücü yaşı asgari eşiğin belirgin altında (<19).",
          predicate=lambda c: c.age < 19,
      ),
      RuleDefinitionData(
          code="YOUNG_DRIVER_MODERATE",
          priority=10,
          effect=RuleEffect.ADD_SCORE,
          points=15,
          message="Sürücü yaşı minimum eşiğin biraz altında.",
          predicate=lambda c: 19 <= c.age < MIN_DRIVER_AGE,
      ),
      RuleDefinitionData(
          code="SENIOR_DRIVER_MODERATE",
          priority=11,
          effect=RuleEffect.ADD_SCORE,
          points=10,
          message="Sürücü yaşı üst risk eşiğinin biraz üzerinde.",
          predicate=lambda c: MAX_DRIVER_AGE < c.age <= 75,
      ),
      RuleDefinitionData(
          code="SENIOR_DRIVER_SEVERE",
          priority=11,
          effect=RuleEffect.ADD_SCORE,
          points=18,
          message="Sürücü yaşı üst risk eşiğinin belirgin üzerinde (>75).",
          predicate=lambda c: c.age > 75,
      ),
      RuleDefinitionData(
          code="NEW_LICENSE_SEVERE",
          priority=20,
          effect=RuleEffect.ADD_SCORE,
          points=25,
          message="Ehliyet süresi 6 aydan kısa.",
          predicate=lambda c: c.license_age_years < 0.5,
      ),
      RuleDefinitionData(
          code="NEW_LICENSE_MODERATE",
          priority=20,
          effect=RuleEffect.ADD_SCORE,
          points=15,
          message="Ehliyet süresi 2 yıldan kısa.",
          predicate=lambda c: 0.5 <= c.license_age_years < MIN_LICENSE_YEARS,
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
      # LATE_RETURNS — tek bir geç teslim (belki yıllar önce, tek seferlik)
      # ile tekrarlayan bir alışkanlık artık aynı puanı almıyor; ikisi de
      # gerçek verilerden (late_fee > 0 olan RentalIncome kayıtları,
      # sync_rental_history_stats) geliyor.
      RuleDefinitionData(
          code="LATE_RETURNS_LOW",
          priority=42,
          effect=RuleEffect.ADD_SCORE,
          points=6,
          message="Bir kez geç teslim geçmişi.",
          predicate=lambda c: c.late_return_count == 1,
      ),
      RuleDefinitionData(
          code="LATE_RETURNS_HIGH",
          priority=42,
          effect=RuleEffect.ADD_SCORE,
          points=14,
          message="Tekrarlayan geç teslim geçmişi.",
          predicate=lambda c: c.late_return_count >= 2,
      ),
      RuleDefinitionData(
          code="TRAFFIC_FINES",
          priority=43,
          effect=RuleEffect.ADD_SCORE,
          points=6,
          message="Yoğun trafik cezası geçmişi.",
          predicate=lambda c: c.traffic_fine_count >= 3,
      ),
      # CANCELLATION_RATE — cancelled_count zaten gerçek veriden (Rental
      # kayıtları) geliyordu ama hiçbir kural onu kullanmıyordu; sürekli
      # rezervasyon yapıp iptal eden bir sürücü eskiden risksiz görünüyordu.
      # En az 3 toplam girişim (kiralama+iptal) şartı, tek bir iptalin yeni
      # bir sürücüyü haksız yere damgalamasını önler.
      RuleDefinitionData(
          code="CANCELLATION_RATE",
          priority=44,
          effect=RuleEffect.ADD_SCORE,
          points=12,
          message="Yüksek rezervasyon iptal oranı.",
          predicate=lambda c: (c.total_rentals + c.cancelled_count) >= 3
          and c.cancelled_count / (c.total_rentals + c.cancelled_count) > 0.3,
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
      # LOYALTY_BONUS — loyalty_level (0-10, total_rentals // 5'ten gerçek
      # veriyle geliyor) artık TEK eşikte sabit indirim değil, kademeli:
      # sadakat arttıkça indirim de büyür.
      RuleDefinitionData(
          code="LOYALTY_BONUS_TIER1",
          priority=92,
          effect=RuleEffect.ADD_SCORE,
          points=-5,
          message="Sadakat seviyesi avantajı.",
          predicate=lambda c: 3 <= c.loyalty_level < 6,
      ),
      RuleDefinitionData(
          code="LOYALTY_BONUS_TIER2",
          priority=92,
          effect=RuleEffect.ADD_SCORE,
          points=-10,
          message="Yüksek sadakat seviyesi avantajı.",
          predicate=lambda c: 6 <= c.loyalty_level < 9,
      ),
      RuleDefinitionData(
          code="LOYALTY_BONUS_TIER3",
          priority=92,
          effect=RuleEffect.ADD_SCORE,
          points=-15,
          message="En üst sadakat seviyesi avantajı.",
          predicate=lambda c: c.loyalty_level >= 9,
      ),
  ]