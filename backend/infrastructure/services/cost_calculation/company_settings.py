"""Şirket bazlı maliyet hesabı parametreleri — MALIYET_HESAPLAMA_METODOLOJISI §3.1/§3.2/§6.

BSMV oranı, yıllık mevduat faiz oranı ve hedef kâr marjı kod seviyesinde
sabit DEĞİLDİR; ``CostCalculationSettings`` üzerinden şirket başına
okunur/değiştirilir (bkz. plan kararı: multi-tenant SaaS, doküman da bu
oranların "güncel piyasa oranıyla değiştirilmesi gerekir" dediği için).
"""

from __future__ import annotations

from backend.apps.companies.models import Company
from backend.apps.vehicle_finance.models import CostCalculationSettings


def get_cost_settings(company: Company) -> CostCalculationSettings:
    """Şirketin maliyet ayarlarını döner; yoksa doküman varsayılanlarıyla oluşturur."""
    settings_row, _ = CostCalculationSettings.objects.get_or_create(company=company)
    return settings_row
