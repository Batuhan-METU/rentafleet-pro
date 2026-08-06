"""``serializer_to_json_schema`` — DRF serializer'dan OpenAI function-calling
şeması üretimi. Bu, her AI tool'unun parametre şemasının gerçek sunucu
taraflı doğrulamadan asla sapmamasının tek garantisi."""

from __future__ import annotations

from backend.apps.customer_profiles.serializers import DriverCreateRequestSerializer
from backend.apps.rentals.serializers import RentalCreateSerializer
from backend.apps.vehicle_finance.serializers import VehicleExpenseSerializer
from backend.infrastructure.services.ai.tools.schema import serializer_to_json_schema


def test_simple_fields_map_to_correct_json_types():
    schema = serializer_to_json_schema(RentalCreateSerializer)
    props = schema["properties"]

    assert props["driver_id"]["type"] == "integer"
    assert props["vehicle_id"]["type"] == "integer"
    assert props["pickup_date"]["type"] == "string"
    assert props["pickup_date"]["format"] == "date"
    assert props["daily_rate"]["type"] == "number"


def test_required_fields_reflect_serializer_required_flags():
    schema = serializer_to_json_schema(RentalCreateSerializer)
    # driver_id/vehicle_id/pickup_date/dropoff_date zorunlu; pickup_time
    # (default'lu) ve daily_rate (required=False) zorunlu DEĞİL.
    assert set(schema["required"]) == {"driver_id", "vehicle_id", "pickup_date", "dropoff_date"}
    assert "pickup_time" not in schema["required"]
    assert "daily_rate" not in schema["required"]


def test_choice_field_becomes_string_enum():
    schema = serializer_to_json_schema(VehicleExpenseSerializer)
    category = schema["properties"]["category"]
    assert category["type"] == "string"
    assert isinstance(category["enum"], list)
    assert len(category["enum"]) > 0


def test_read_only_fields_are_excluded():
    schema = serializer_to_json_schema(VehicleExpenseSerializer)
    # `id`/`category_display`/`label` vb. read-only alanlar AI'nin
    # DOLDURMASI gereken parametreler değildir.
    assert "id" not in schema["properties"]
    assert "category_display" not in schema["properties"]
    assert "label" not in schema["properties"]


def test_nested_serializer_becomes_nested_object_schema():
    schema = serializer_to_json_schema(DriverCreateRequestSerializer)
    driver_schema = schema["properties"]["driver"]

    assert driver_schema["type"] == "object"
    assert "first_name" in driver_schema["properties"]
    assert "national_id" in driver_schema["properties"]
    assert "first_name" in driver_schema["required"]
    assert schema["required"] == ["driver"]
    # identity/license/financial hepsi opsiyonel (required=False).
    assert "identity" not in schema["required"]
