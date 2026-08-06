"""AI asistanı için mutasyon (değişiklik yapan) tool'ları.

İki katman:

* **Özel (bespoke) eylemler** — gerçek iş mantığı (kilitleme, risk kapısı,
  önizleme) içerenler; ilgili view'ın ZATEN çağırdığı application-layer
  fonksiyonlarını doğrudan çağırır (``create_rental``, ``cancel_rental``,
  ``extend_active_rental``, ``process_vehicle_return``) — mantık asla
  kopyalanmaz.
* **Generic CRUD eylemleri** — kredi/sigorta/masraf/gelir/genel gider/kredi
  tahsisi gibi "serializer'ı doğrula, ilgili kapsam FK'sini ekle, kaydet"
  şeklindeki tekrar eden deseni TEK bir yürütücü (``_register_generic_create``)
  işler; her biri için ayrı bir fonksiyon YAZILMAZ.

Tüm mutasyon tool'ları AI asistanı tarafından DOĞRUDAN çalıştırılmaz — önce
bir ``AIPendingAction`` olarak saklanır, yalnızca kullanıcı sohbetteki onay
kartında "Onayla"ya bastığında bu modüldeki ``handler`` gerçekten çağrılır
(bkz. ``agent_service.py`` ve ``apps/ai/views.py:AIActionConfirmView``).
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.serializers import Serializer

from backend.application.customer.profiles import apply_customer_profiles
from backend.application.customer.snapshots import ensure_customer_profiles
from backend.application.driver.evaluate_driver import DriverEvaluationService
from backend.application.rental.cancel_rental import cancel_rental as _cancel_rental_app
from backend.application.rental.create_rental import RentalCreateInput
from backend.application.rental.create_rental import create_rental as _create_rental_app
from backend.application.rental.return_processing import (
    extend_active_rental,
    process_vehicle_return,
)
from backend.apps.customer_profiles.models import Driver
from backend.apps.customer_profiles.serializers import DriverCreateRequestSerializer
from backend.apps.rentals.serializers import RentalCreateSerializer, RentalSerializer
from backend.apps.vehicle_finance.serializers import (
    CompanyOverheadExpenseSerializer,
    InsurancePolicySerializer,
    LoanSerializer,
    LoanVehicleAllocationSerializer,
    RentalIncomeSerializer,
    VehicleExpenseSerializer,
)
from backend.common.audit import log_change
from backend.common.multitenancy_tools.scope import (
    get_scoped_driver,
    get_scoped_loan,
    get_scoped_rental,
    get_scoped_vehicle,
    require_user_company,
)
from backend.infrastructure.services.ai.tools.registry import ToolSpec, register
from backend.infrastructure.services.ai.tools.schema import serializer_to_json_schema
from backend.infrastructure.services.cost_calculation.credit_interest_service import (
    generate_amortization_schedule,
)


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_time(value: Any, *, default: time = time(10, 0)) -> time:
    if value in (None, ""):
        return default
    return time.fromisoformat(str(value))


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    dt = datetime.fromisoformat(str(value))
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValidationError({"error": f"Geçersiz sayı: {value!r}"}) from exc


# --- Özel (bespoke) eylemler --------------------------------------------


def _create_rental_summary(request: Request, args: dict[str, Any]) -> str:
    driver = get_scoped_driver(request, args["driver_id"])
    vehicle = get_scoped_vehicle(request, args["vehicle_id"])
    return (
        f"**{driver.full_name}** sürücüsü için **{vehicle.plate_number}** "
        f"({vehicle.brand} {vehicle.model}) aracını **{args['pickup_date']} → "
        f"{args['dropoff_date']}** tarihleri arasında kiralayacağım."
    )


def _create_rental_handler(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    company = require_user_company(request)
    driver = get_scoped_driver(request, args["driver_id"])
    vehicle = get_scoped_vehicle(request, args["vehicle_id"])
    rental = _create_rental_app(
        company=company,
        data=RentalCreateInput(
            driver=driver,
            vehicle=vehicle,
            pickup_date=_parse_date(args["pickup_date"]),
            dropoff_date=_parse_date(args["dropoff_date"]),
            pickup_time=_parse_time(args.get("pickup_time")),
            dropoff_time=_parse_time(args.get("dropoff_time")),
            daily_rate=_parse_decimal(args.get("daily_rate")),
            deposit_amount=_parse_decimal(args.get("deposit_amount")),
        ),
        created_by=request.user,
    )
    return dict(RentalSerializer(rental).data)


register(
    ToolSpec(
        name="create_rental",
        description="Bir sürücü ile bir aracı belirli tarihler arasında eşleştirerek YENİ bir kiralama oluşturur. Risk/uygunluk kontrolünden geçmeyen veya tarih çakışması olan istekler reddedilir.",
        parameters=serializer_to_json_schema(RentalCreateSerializer),
        kind="mutation",
        handler=_create_rental_handler,
        summary=_create_rental_summary,
    )
)


def _cancel_rental_summary(request: Request, args: dict[str, Any]) -> str:
    rental = get_scoped_rental(request, args["rental_id"])
    return (
        f"**#{rental.pk}** numaralı kiralamayı (**{rental.driver.full_name}** → "
        f"**{rental.vehicle.plate_number}**) iptal edeceğim."
    )


def _cancel_rental_handler(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    rental = get_scoped_rental(request, args["rental_id"])
    result = _cancel_rental_app(rental, cancelled_by=request.user)
    payload: dict[str, Any] = {"rental": RentalSerializer(result.rental).data, "early_return": result.early_return}
    if result.settlement is not None:
        payload["settlement"] = {
            "status": result.settlement.return_status,
            "price_difference": str(result.settlement.price_difference),
            "message": result.settlement.message,
        }
    return payload


register(
    ToolSpec(
        name="cancel_rental",
        description="Bir kiralamayı iptal eder. Kiralama henüz başlamadıysa doğrudan iptal edilir; zaten başladıysa fiilen erken teslim olarak işlenir ve fiyat farkı hesaplanır.",
        parameters={
            "type": "object",
            "properties": {"rental_id": {"type": "integer"}},
            "required": ["rental_id"],
        },
        kind="mutation",
        handler=_cancel_rental_handler,
        summary=_cancel_rental_summary,
    )
)


def _preview_vehicle_return_handler(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    rental = get_scoped_rental(request, args["rental_id"])
    settlement = process_vehicle_return(
        rental, _parse_datetime(args["actual_return_at"]), args.get("notes", ""), preview=True
    )
    return {
        "status": settlement.return_status,
        "unused_days": settlement.unused_days,
        "overage_hours": settlement.overage_hours,
        "daily_rate": str(settlement.daily_rate),
        "price_difference": str(settlement.price_difference),
        "message": settlement.message,
    }


register(
    ToolSpec(
        name="preview_vehicle_return",
        description="Bir aracı teslim almanın (henüz hiçbir şeyi DEĞİŞTİRMEDEN) ne sonuç vereceğini önizler: erken/geç teslim farkı, tutar.",
        parameters={
            "type": "object",
            "properties": {
                "rental_id": {"type": "integer"},
                "actual_return_at": {"type": "string", "format": "date-time"},
                "notes": {"type": "string"},
            },
            "required": ["rental_id", "actual_return_at"],
        },
        kind="read",
        handler=_preview_vehicle_return_handler,
    )
)


def _return_vehicle_summary(request: Request, args: dict[str, Any]) -> str:
    rental = get_scoped_rental(request, args["rental_id"])
    return (
        f"**{rental.vehicle.plate_number}** aracını **#{rental.pk}** numaralı kiralamadan "
        f"**{args['actual_return_at']}** tarihinde teslim alacağım."
    )


def _return_vehicle_handler(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    rental = get_scoped_rental(request, args["rental_id"])
    settlement = process_vehicle_return(
        rental, _parse_datetime(args["actual_return_at"]), args.get("notes", ""), preview=False
    )
    rental.refresh_from_db()
    log_change(
        user=request.user,
        obj=rental,
        message=f"Araç teslim alındı (AI asistanı aracılığıyla): {settlement.message}",
    )
    return {
        "status": settlement.return_status,
        "price_difference": str(settlement.price_difference),
        "message": settlement.message,
        "rental": RentalSerializer(rental).data,
    }


register(
    ToolSpec(
        name="return_vehicle",
        description="Bir aracı GERÇEKTEN teslim alır (kiralamayı tamamlar). Önce preview_vehicle_return ile önizleme yapılması önerilir.",
        parameters={
            "type": "object",
            "properties": {
                "rental_id": {"type": "integer"},
                "actual_return_at": {"type": "string", "format": "date-time"},
                "notes": {"type": "string"},
            },
            "required": ["rental_id", "actual_return_at"],
        },
        kind="mutation",
        handler=_return_vehicle_handler,
        summary=_return_vehicle_summary,
    )
)


def _extend_rental_summary(request: Request, args: dict[str, Any]) -> str:
    rental = get_scoped_rental(request, args["rental_id"])
    return (
        f"**#{rental.pk}** numaralı kiralamanın (**{rental.vehicle.plate_number}**) bitiş "
        f"tarihini **{args['new_ended_at']}** olarak uzatacağım."
    )


def _extend_rental_handler(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    rental = get_scoped_rental(request, args["rental_id"])
    extend_active_rental(rental, _parse_datetime(args["new_ended_at"]))
    log_change(
        user=request.user,
        obj=rental,
        message=f"Kiralama süresi uzatıldı (AI asistanı aracılığıyla): yeni bitiş {args['new_ended_at']}.",
    )
    return dict(RentalSerializer(rental).data)


register(
    ToolSpec(
        name="extend_rental",
        description="Aktif bir kiralamanın bitiş tarihini ileri öteler. Aracın yeni tarih aralığında başka bir aktif kiralaması varsa reddedilir.",
        parameters={
            "type": "object",
            "properties": {
                "rental_id": {"type": "integer"},
                "new_ended_at": {"type": "string", "format": "date-time"},
            },
            "required": ["rental_id", "new_ended_at"],
        },
        kind="mutation",
        handler=_extend_rental_handler,
        summary=_extend_rental_summary,
    )
)


def _create_driver_summary(request: Request, args: dict[str, Any]) -> str:
    d = args.get("driver", {})
    name = f"{d.get('first_name', '')} {d.get('last_name', '')}".strip() or "yeni sürücü"
    return f"**{name}** adında yeni bir sürücü kaydı oluşturup risk değerlendirmesi yapacağım."


def _create_driver_handler(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    from backend.apps.customer_profiles.views import _driver_detail_item

    serializer = DriverCreateRequestSerializer(data=args, context={"request": request})
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    company_id = request.user.company_id

    # DriverCreateView.post() ile AYNI tek-atomic-blok deseni — sinyalin
    # ertelenen risk değerlendirmesi bu bloğun kendi evaluate() çağrısından
    # SONRA tetiklenir ve ikinci bir gereksiz değerlendirmeyi atlar.
    from django.db import IntegrityError, transaction

    try:
        with transaction.atomic():
            driver = Driver.objects.create(company_id=company_id, **data["driver"])
            ensure_customer_profiles(driver)
            apply_customer_profiles(driver, data)
            evaluation = DriverEvaluationService().evaluate(driver)
    except IntegrityError as exc:
        raise ValidationError({"error": "Bu TC kimlik numarası bu şirkette zaten kayıtlı."}) from exc

    driver.refresh_from_db()
    log_change(
        user=request.user,
        obj=driver,
        message="Sürücü AI asistanı aracılığıyla oluşturuldu.",
        created=True,
    )
    payload = _driver_detail_item(driver)
    payload["risk"] = DriverEvaluationService().serialize(evaluation)
    return payload


register(
    ToolSpec(
        name="create_driver",
        description="Yeni bir sürücü kaydı oluşturur ve otomatik risk değerlendirmesi yapar.",
        parameters=serializer_to_json_schema(DriverCreateRequestSerializer),
        kind="mutation",
        handler=_create_driver_handler,
        summary=_create_driver_summary,
    )
)


# --- Generic CRUD eylemleri (kredi/sigorta/masraf/gelir/genel gider) ----

ScopeKind = Literal["vehicle", "loan", "company"]


def _register_generic_create(
    *,
    name: str,
    description: str,
    serializer_class: type[Serializer],
    scope: ScopeKind,
    summary_label: str,
    post_save: Any = None,
) -> None:
    base_schema = serializer_to_json_schema(serializer_class)
    properties = dict(base_schema["properties"])
    required = list(base_schema.get("required", []))
    if scope == "vehicle":
        properties["vehicle_id"] = {"type": "integer", "description": "Bu kaydın ait olduğu araç."}
        required.append("vehicle_id")
    elif scope == "loan":
        properties["loan_id"] = {"type": "integer", "description": "Bu kaydın ait olduğu kredi."}
        required.append("loan_id")
    parameters: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required

    def handler(request: Request, args: dict[str, Any]) -> dict[str, Any]:
        data = {k: v for k, v in args.items() if k not in ("vehicle_id", "loan_id")}
        serializer = serializer_class(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        save_kwargs: dict[str, Any] = {}
        if scope == "vehicle":
            save_kwargs["vehicle"] = get_scoped_vehicle(request, args["vehicle_id"])
        elif scope == "loan":
            save_kwargs["loan"] = get_scoped_loan(request, args["loan_id"])
        else:
            save_kwargs["company"] = require_user_company(request)
        instance = serializer.save(**save_kwargs)
        if post_save is not None:
            post_save(instance)
        log_change(
            user=request.user,
            obj=instance,
            message=f"{summary_label.capitalize()} AI asistanı aracılığıyla oluşturuldu.",
            created=True,
        )
        return dict(serializer_class(instance).data)

    def summary(request: Request, args: dict[str, Any]) -> str:
        amount = args.get("amount") or args.get("principal_amount") or args.get("base_amount")
        amount_text = f" ({amount} TL)" if amount else ""
        return f"Yeni bir **{summary_label}**{amount_text} kaydı oluşturacağım."

    register(
        ToolSpec(
            name=name,
            description=description,
            parameters=parameters,
            kind="mutation",
            handler=handler,
            summary=summary,
        )
    )


_register_generic_create(
    name="create_loan",
    description="Şirket için yeni bir kredi tanımı oluşturur ve taksit planını üretir.",
    serializer_class=LoanSerializer,
    scope="company",
    summary_label="kredi",
    post_save=generate_amortization_schedule,
)

_register_generic_create(
    name="create_vehicle_expense",
    description="Bir araç için yeni bir gider kaydı (bakım, hasar, yıkama vb.) oluşturur.",
    serializer_class=VehicleExpenseSerializer,
    scope="vehicle",
    summary_label="araç gideri",
)

_register_generic_create(
    name="create_vehicle_income",
    description="Bir araç için yeni bir kiralama geliri kaydı oluşturur.",
    serializer_class=RentalIncomeSerializer,
    scope="vehicle",
    summary_label="araç geliri",
)

_register_generic_create(
    name="create_insurance_policy",
    description="Bir araç için yeni bir sigorta/kasko poliçesi kaydı oluşturur.",
    serializer_class=InsurancePolicySerializer,
    scope="vehicle",
    summary_label="sigorta poliçesi",
)

_register_generic_create(
    name="create_overhead_expense",
    description="Şirket geneli (araca bağlı olmayan) yeni bir genel gider kaydı oluşturur.",
    serializer_class=CompanyOverheadExpenseSerializer,
    scope="company",
    summary_label="genel gider",
)

_register_generic_create(
    name="create_loan_allocation",
    description="Bir krediyi bir araca tahsis eder (aracın kredi ile finanse edilen payını belirler).",
    serializer_class=LoanVehicleAllocationSerializer,
    scope="loan",
    summary_label="kredi tahsisi",
)
