"""Sürücü API görünümleri (RentA-Fleet PRO)."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q, QuerySet
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
from backend.apps.customer_profiles.models import Driver
from backend.apps.customer_profiles.serializers import (
    DriverCreateRequestSerializer,
    DriverSerializer,
)
from backend.apps.rentals.models import Rental, RentalStatus
from backend.apps.risk_checks.evaluation import RISK_LEVEL_LABELS
from backend.apps.risk_checks.models import CustomerRiskSnapshot
from backend.apps.vehicles.models import VehicleLiveState
from backend.common.multitenancy_tools.scope import (
    get_scoped_driver,
    get_scoped_vehicle,
    scoped_drivers,
)
from backend.common.permissions import IsFleetStaff
from backend.infrastructure.services.analytics.scoring_service import (
    calculate_driver_score,
    driver_comment,
)
from backend.infrastructure.services.sipp.sipp_service import format_brand_model_segment


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
        "rental_id": rental.pk,
        "plate_number": vehicle.plate_number,
        "brand_model": f"{vehicle.brand} {vehicle.model}",
        "brand_model_segment": format_brand_model_segment(
            vehicle.brand, vehicle.model, vehicle.sipp_code
        ),
        "current_km": vehicle.current_km,
        "latitude": round(state.latitude, 6) if state else None,
        "longitude": round(state.longitude, 6) if state else None,
        "start_km": rental.start_km,
        "started_at": rental.started_at.isoformat(),
    }


def _profile_summary(driver: Driver) -> dict:
    ensure_customer_profiles(driver)
    identity = getattr(driver, "identity_profile", None)
    license_p = getattr(driver, "license_profile", None)
    financial = getattr(driver, "financial_profile", None)

    return {
        "identity_verified": bool(identity and identity.identity_verified),
        "phone_verified": bool(identity and identity.phone_verified),
        "document_fraud_suspicion": bool(identity and identity.document_fraud_suspicion),
        "license_issue_date": license_p.license_issue_date.isoformat() if license_p and license_p.license_issue_date else None,
        "license_points": license_p.license_points if license_p else 0,
        "license_penalty_count": license_p.license_penalty_count if license_p else 0,
        "findeks_score": financial.findeks_score if financial else None,
        "enforcement_record": bool(financial and financial.has_enforcement_record),
        "bank_blacklist": bool(financial and financial.bank_blacklist_flag),
        "payment_delay_count": financial.payment_delay_count if financial else 0,
        "occupation": driver.occupation or "",
        "employer": driver.employer or "",
        "monthly_income": str(driver.monthly_income) if driver.monthly_income is not None else None,
    }


def _driver_list_item(driver: Driver, *, vehicle=None) -> dict:
    data = DriverSerializer(driver).data
    level = driver.risk_level or None
    data["risk_score"] = driver.current_risk_score
    data["risk_level"] = level
    data["risk_level_label"] = RISK_LEVEL_LABELS.get(level or "", "—") if level else "—"
    data["risk_approved"] = driver_has_risk_approval(driver)
    data["active_rental"] = _active_rental_payload(driver)
    if vehicle is not None:
        data["vehicle_eligible"] = is_driver_eligible_for_vehicle(driver, vehicle)
    return data


def _driver_detail_item(driver: Driver) -> dict:
    data = _driver_list_item(driver)
    evaluation = build_driver_risk_payload(driver)
    data["risk"] = evaluation
    data["profile_summary"] = _profile_summary(driver)
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
            # DriverSerializer.get_total_rentals() eskiden HER sürücü için
            # ayrı bir COUNT sorgusu çalıştırıyordu (N+1 — 500 sürücülük bir
            # filoda 500 ekstra sorgu). Tek bir JOIN+GROUP BY ile önceden
            # hesaplanır; serializer artık bunu okur, sorgu atmaz.
            .annotate(total_rentals_count=Count("rentals", filter=~Q(rentals__status=RentalStatus.CANCELLED)))
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

        total_count = len(drivers)

        # Sayfalama İSTEĞE BAĞLIDIR (geriye dönük uyumluluk için) — `?page=`
        # gönderilmezse davranış birebir eskisi gibi TAM listedir (mevcut
        # frontend bu parametreyi hiç göndermez, bu yüzden mevcut davranış
        # değişmez). Gönderilirse, en pahalı kısım (`_driver_list_item` —
        # her sürücü için risk/uygunluk hesabı) yalnızca o sayfanın
        # sürücüleri için çalışır; büyük filolarda tam listeyi serileştirme
        # CPU/yanıt-boyutu maliyetini önler (bkz. performans denetimi).
        page_param = request.query_params.get("page")
        if page_param is not None:
            try:
                page_size = max(1, min(200, int(request.query_params.get("page_size", 25))))
                page_number = max(1, int(page_param))
            except ValueError:
                page_number, page_size = 1, 25
            start = (page_number - 1) * page_size
            drivers = drivers[start : start + page_size]

        items = [_driver_list_item(driver, vehicle=vehicle) for driver in drivers]
        return Response(
            {
                "driver_count": total_count,
                "drivers": items,
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

        # `Driver.objects.create(...)` tetiklediği `post_save` sinyali
        # (apps/customer_profiles/signals.py) risk değerlendirmesini
        # `transaction.on_commit` ile erteler. Bu blok bilerek TEK bir
        # `transaction.atomic()` içine alınıyor — aksi halde sinyalin
        # ertelenmiş çağrısı, aşağıdaki `_apply_driver_profiles` ve
        # `evaluate()` çağrılarından ÖNCE (bu view'da başka bir atomic blok
        # olmadığı için) tetiklenir ve sürücü henüz boş/varsayılan profille
        # değerlendirilir; ardından buradaki gerçek `evaluate()` ikinci kez
        # (gereksiz bir kural motoru geçişi + fazladan bir
        # CustomerRiskSnapshot ile) çalışır. Tek atomic blok içinde sinyalin
        # `on_commit` çağrısı bu view'ın KENDİ `evaluate()` çağrısından SONRA
        # tetiklenir; sinyaldeki `current_risk_score is not None` koruması
        # da bu noktada zaten dolu olduğu için ikinci değerlendirmeyi
        # atlar — sinyal başka bir oluşturma yolunda (ör. doğrudan ORM/admin)
        # hâlâ tek başına çalışmaya devam eder, kaldırılmıyor.
        try:
            with transaction.atomic():
                driver = Driver.objects.create(company_id=company_id, **data["driver"])
                _apply_driver_profiles(driver, data)
                evaluation = DriverEvaluationService().evaluate(driver)
        except IntegrityError:
            return Response(
                {"error": "Bu TC kimlik numarası bu şirkette zaten kayıtlı."},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
                "full_name": driver.full_name,
                "driver_score": result.score,
                "summary": {
                    "total_speed_violations": result.total_violations,
                    "total_hard_brakes": result.total_brakes,
                    "total_hard_accelerations": result.total_accelerations,
                    "rental_count": result.rental_count,
                    "driving_comment": driver_comment(result.score),
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
                "full_name": driver.full_name,
                "rentals": [
                    {
                        "id": rental.pk,
                        "plate_number": rental.vehicle.plate_number,
                        "brand_model": format_brand_model_segment(
                            rental.vehicle.brand,
                            rental.vehicle.model,
                            rental.vehicle.sipp_code,
                        ),
                        "status_label": rental.get_status_display(),
                        "status_code": rental.status,
                        "started_at": rental.started_at.isoformat(),
                        "ended_at": rental.ended_at.isoformat() if rental.ended_at else None,
                        "start_km": rental.start_km,
                        "end_km": rental.end_km,
                    }
                    for rental in rentals
                ],
            }
        )
