"""Sürücü API görünümleri (RentA-Fleet PRO)."""

from __future__ import annotations

from django.db import IntegrityError
from django.db.models import Prefetch, QuerySet
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.application.customer.profiles import apply_customer_profiles
from backend.application.customer.snapshots import ensure_customer_profiles
from backend.application.driver.evaluate_driver import DriverEvaluationService
from backend.application.driver.risk_payload import build_driver_risk_payload
from backend.application.rental.driver_eligibility import (
    driver_has_risk_approval,
    is_driver_eligible_for_vehicle,
)
from backend.apps.customer_profiles.serializers import DriverCreateRequestSerializer, DriverSerializer
from backend.apps.customer_profiles.models import Driver
from backend.apps.risk_checks.evaluation import RISK_LEVEL_LABELS
from backend.apps.risk_checks.models import CustomerRiskSnapshot
from backend.apps.reservations.models import Rental, RentalStatus
from backend.apps.vehicles.models import VehicleLiveState
from backend.common.permissions import IsFleetStaff
from backend.infrastructure.services.analytics.scoring_service import calculate_driver_score, driver_comment
from backend.infrastructure.services.sipp.sipp_service import format_marka_model_sinif
from backend.common.multitenancy_tools.scope import get_scoped_driver, get_scoped_vehicle, scoped_drivers


def _active_rental_payload(driver: Driver) -> dict | None:
    active_rentals = getattr(driver, "active_rentals", None)
    if active_rentals is not None:
        rental = active_rentals[0] if active_rentals else None
    else:
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


def _profile_summary(driver: Driver) -> dict:
    ensure_customer_profiles(driver)
    identity = getattr(driver, "identity_profile", None)
    license_p = getattr(driver, "license_profile", None)
    financial = getattr(driver, "financial_profile", None)

    return {
        "kimlik_dogrulandi": bool(identity and identity.identity_verified),
        "telefon_dogrulandi": bool(identity and identity.phone_verified),
        "belge_suphesi": bool(identity and identity.document_fraud_suspicion),
        "ehliyet_verilis": license_p.license_issue_date.isoformat() if license_p and license_p.license_issue_date else None,
        "ehliyet_puani": license_p.license_points if license_p else 0,
        "ehliyet_ceza_sayisi": license_p.license_penalty_count if license_p else 0,
        "findeks_skoru": financial.findeks_score if financial else None,
        "icra_kaydi": bool(financial and financial.has_enforcement_record),
        "banka_kara_liste": bool(financial and financial.bank_blacklist_flag),
        "odeme_gecikme": financial.payment_delay_count if financial else 0,
        "meslek": driver.occupation or "",
        "isveren": driver.employer or "",
        "aylik_gelir": str(driver.monthly_income) if driver.monthly_income is not None else None,
    }


def _driver_list_item(driver: Driver, *, vehicle=None) -> dict:
    data = DriverSerializer(driver).data
    level = driver.risk_level or None
    data["risk_skoru"] = driver.current_risk_score
    data["risk_seviye"] = level
    data["risk_seviye_label"] = RISK_LEVEL_LABELS.get(level or "", "—") if level else "—"
    data["risk_onaylandi"] = driver_has_risk_approval(driver)
    data["aktif_kiralama"] = _active_rental_payload(driver)
    if vehicle is not None:
        data["araca_uygun"] = is_driver_eligible_for_vehicle(driver, vehicle)
    return data


def _driver_detail_item(driver: Driver) -> dict:
    data = _driver_list_item(driver)
    evaluation = build_driver_risk_payload(driver)
    data["risk"] = evaluation
    data["profil_ozeti"] = _profile_summary(driver)
    return data


def _apply_driver_profiles(driver: Driver, data: dict) -> None:
    ensure_customer_profiles(driver)
    apply_customer_profiles(driver, data)


class DriverListView(ListAPIView):
    """GET /api/drivers/ — filodaki sürücüler.

    ``vehicle_id`` sorgu parametresi verilirse yalnızca seçilen araca
    risk skoru yeten sürücüler döner.
    """

    serializer_class = DriverSerializer
    permission_classes = (IsFleetStaff,)

    def get_queryset(self) -> QuerySet[Driver]:
        return (
            scoped_drivers(self.request)
            .select_related("company")
            .prefetch_related(
                Prefetch(
                    "rentals",
                    queryset=Rental.objects.filter(status=RentalStatus.ACTIVE).select_related(
                        "vehicle", "vehicle__live_state"
                    ),
                    to_attr="active_rentals",
                ),
                Prefetch(
                    "risk_snapshots",
                    queryset=CustomerRiskSnapshot.objects.order_by("-computed_at"),
                ),
            )
            .order_by("last_name", "first_name")
        )

    def list(self, request: Request, *args, **kwargs) -> Response:
        queryset = self.filter_queryset(self.get_queryset())
        vehicle = None
        vehicle_id = request.query_params.get("vehicle_id")
        if vehicle_id:
            vehicle = get_scoped_vehicle(request, vehicle_id)

        drivers = list(queryset)
        if vehicle is not None:
            drivers = [driver for driver in drivers if is_driver_eligible_for_vehicle(driver, vehicle)]

        items = [_driver_list_item(driver, vehicle=vehicle) for driver in drivers]
        return Response(
            {
                "surucu_sayisi": len(items),
                "surucular": items,
                "vehicle_id": vehicle.pk if vehicle else None,
            }
        )


class DriverCreateView(APIView):
    """POST /api/drivers/ — yeni sürücü + profiller + risk değerlendirmesi."""

    permission_classes = (IsFleetStaff,)

    def post(self, request: Request) -> Response:
        serializer = DriverCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user
        company_id = user.company_id
        if not company_id:
            return Response(
                {"error": "Kullanıcı bir şirkete bağlı değil."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            driver = Driver.objects.create(company_id=company_id, **data["driver"])
        except IntegrityError:
            return Response(
                {"error": "Bu TC kimlik numarası bu şirkette zaten kayıtlı."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _apply_driver_profiles(driver, data)
        evaluation = DriverEvaluationService().evaluate(driver)
        driver.refresh_from_db()

        payload = _driver_detail_item(driver)
        risk_payload = DriverEvaluationService().serialize(evaluation)
        risk_payload["uygun_araclar"] = list(evaluation.eligible_vehicles)
        payload["risk"] = risk_payload
        return Response(payload, status=status.HTTP_201_CREATED)


class DriverDetailView(RetrieveAPIView):
    """GET /api/drivers/<pk>/ — sürücü detayı."""

    serializer_class = DriverSerializer
    permission_classes = (IsFleetStaff,)

    def get_queryset(self) -> QuerySet[Driver]:
        return scoped_drivers(self.request).select_related("company")

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        driver = self.get_object()
        return Response(_driver_detail_item(driver))


class DriverScoreView(APIView):
    """GET /api/drivers/<pk>/driver-score/ — sürücü sürüş skoru."""

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request, pk: int) -> Response:
        driver = get_scoped_driver(request, pk)
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
    """GET /api/drivers/<pk>/rentals/ — sürücünün kiralama geçmişi."""

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request, pk: int) -> Response:
        driver = get_scoped_driver(request, pk)
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
