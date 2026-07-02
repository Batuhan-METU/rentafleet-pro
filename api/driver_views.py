"""Sürücü API görünümleri (RentA-Fleet PRO)."""

from __future__ import annotations

from django.db.models import Prefetch, QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.driver_serializers import DriverSerializer
from api.models import Driver, Rental, RentalStatus, VehicleLiveState
from api.permissions import IsFleetManager, IsFleetStaff
from api.services.scoring_service import calculate_driver_score, driver_comment
from api.services.sipp_service import format_marka_model_sinif


def _active_rental_payload(driver: Driver) -> dict | None:
    """Sürücünün aktif kiralamasını Türkçe JSON olarak döndürür."""
    rental = (
        driver.rentals.filter(status=RentalStatus.ACTIVE)
        .select_related("vehicle", "vehicle__live_state")
        .first()
    )
    if rental is None:
        return None

    vehicle = rental.vehicle
    state: VehicleLiveState | None = getattr(vehicle, "live_state", None)
    return {
        "kiralama_id": rental.pk,
        "plaka": vehicle.plate_number,
        "marka_model": f"{vehicle.brand} {vehicle.model}",
        "marka_model_sinif": format_marka_model_sinif(
            vehicle.brand, vehicle.model, vehicle.sipp_code
        ),
        "guncel_km": vehicle.current_km,
        "enlem": round(state.latitude, 6) if state else None,
        "boylam": round(state.longitude, 6) if state else None,
        "baslangic_km": rental.start_km,
        "baslangic_tarihi": rental.started_at.isoformat(),
    }


def _driver_list_item(driver: Driver) -> dict:
    """Liste yanıtı için tek sürücü sözlüğü."""
    score = calculate_driver_score(driver.pk)
    data = DriverSerializer(driver).data
    data["surus_skoru"] = score.score
    data["surus_yorumu"] = driver_comment(score.score)
    data["aktif_kiralama"] = _active_rental_payload(driver)
    data["skor_ozeti"] = {
        "toplam_hiz_ihlali": score.total_violations,
        "toplam_ani_fren": score.total_brakes,
        "toplam_ani_hizlanma": score.total_accelerations,
        "kiralama_sayisi": score.rental_count,
    }
    return data


class DriverListView(ListAPIView):
    """GET /api/v1/drivers/ — filodaki tüm sürücüler."""

    serializer_class = DriverSerializer
    permission_classes = (IsFleetStaff,)

    def get_queryset(self) -> QuerySet[Driver]:
        return (
            Driver.objects.select_related("company")
            .prefetch_related(
                Prefetch(
                    "rentals",
                    queryset=Rental.objects.filter(status=RentalStatus.ACTIVE).select_related(
                        "vehicle", "vehicle__live_state"
                    ),
                )
            )
            .order_by("last_name", "first_name")
        )

    def list(self, request: Request, *args, **kwargs) -> Response:
        queryset = self.filter_queryset(self.get_queryset())
        drivers = list(queryset)
        return Response(
            {
                "surucu_sayisi": len(drivers),
                "surucular": [_driver_list_item(driver) for driver in drivers],
            }
        )


class DriverDetailView(RetrieveAPIView):
    """GET /api/v1/drivers/<pk>/ — sürücü detayı."""

    serializer_class = DriverSerializer
    permission_classes = (IsFleetStaff,)
    queryset = Driver.objects.select_related("company")

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        driver = self.get_object()
        return Response(_driver_list_item(driver))


class DriverScoreView(APIView):
    """GET /api/v1/drivers/<pk>/driver-score/ — sürücü sürüş skoru."""

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request, pk: int) -> Response:
        driver = get_object_or_404(Driver, pk=pk)
        result = calculate_driver_score(driver.pk)
        return Response(
            {
                "driver_id": result.driver_id,
                "ad_soyad": driver.full_name,
                "driver_score": result.score,
                "summary": {
                    "toplam_hiz_ihlali": result.total_violations,
                    "toplam_ani_fren": result.total_brakes,
                    "toplam_ani_hizlanma": result.total_accelerations,
                    "kiralama_sayisi": result.rental_count,
                    "surus_yorumu": driver_comment(result.score),
                },
            }
        )


class DriverRentalHistoryView(APIView):
    """GET /api/v1/drivers/<pk>/rentals/ — sürücünün kiralama geçmişi."""

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request, pk: int) -> Response:
        driver = get_object_or_404(Driver, pk=pk)
        rentals = (
            Rental.objects.filter(driver=driver)
            .exclude(status=RentalStatus.CANCELLED)
            .select_related("vehicle")
            .order_by("-started_at")
        )
        return Response(
            {
                "driver_id": driver.pk,
                "ad_soyad": driver.full_name,
                "kiralamalar": [
                    {
                        "id": rental.pk,
                        "plaka": rental.vehicle.plate_number,
                        "marka_model": format_marka_model_sinif(
                            rental.vehicle.brand,
                            rental.vehicle.model,
                            rental.vehicle.sipp_code,
                        ),
                        "durum": rental.get_status_display(),
                        "durum_kodu": rental.status,
                        "baslangic": rental.started_at.isoformat(),
                        "bitis": rental.ended_at.isoformat() if rental.ended_at else None,
                        "baslangic_km": rental.start_km,
                        "bitis_km": rental.end_km,
                    }
                    for rental in rentals
                ],
            }
        )
