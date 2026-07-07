"""Filo analitik görünümleri."""
from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.permissions import IsFleetManager
from backend.infrastructure.services.analytics.analytics_service import get_fleet_analytics
from backend.tenant.scope import get_user_company


class FleetAnalyticsView(APIView):
    """GET /api/v1/fleet/analytics/ — dashboard için filo analitiği.

    Toplam/doluluk, aktif kritik anomali, ortalama sürücü skoru, en düşük
    skorlu 5 araç ve haftalık yakıt tasarruf trendini tek yanıtta döndürür.
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request) -> Response:
        company = get_user_company(request)
        company_id = company.pk if company else None
        data = get_fleet_analytics(company_id=company_id)
        return Response(
            {
                "toplam_arac": data.total,
                "kirada": data.rented,
                "musait": data.available,
                "bakimda": data.maintenance,
                "doluluk_orani": data.occupancy_rate,
                "aktif_kritik_anomali": data.critical_count,
                "ortalama_surus_skoru": data.avg_score,
                "en_dusuk_skorlu_suruculer": data.lowest_drivers,
                "haftalik_yakit_tasarrufu": data.weekly_fuel_savings,
            }
        )
