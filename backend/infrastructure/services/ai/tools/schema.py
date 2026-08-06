"""DRF serializer'lardan OpenAI function-calling JSON şeması üretimi.

Her AI tool'unun parametre şeması, ilgili endpoint'in ZATEN kullandığı DRF
serializer'ından üretilir — elle yazılmış iki paralel doğrulama kümesi
(serializer + ayrı bir tool şeması) zamanla birbirinden sapabilirdi; bu
modül TEK bir gerçek kaynaktan (serializer) türeterek bu riski ortadan
kaldırır.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

# Sıra önemli: EmailField, CharField'ın alt sınıfıdır — isinstance taraması
# yukarıdan aşağı yapıldığı için daha özel tip önce gelmeli.
_FIELD_TYPE_MAP: list[tuple[type[serializers.Field], dict[str, Any]]] = [
    (serializers.EmailField, {"type": "string", "format": "email"}),
    (serializers.DateTimeField, {"type": "string", "format": "date-time"}),
    (serializers.DateField, {"type": "string", "format": "date"}),
    (serializers.TimeField, {"type": "string", "format": "time"}),
    (serializers.BooleanField, {"type": "boolean"}),
    (serializers.IntegerField, {"type": "integer"}),
    (serializers.FloatField, {"type": "number"}),
    (serializers.DecimalField, {"type": "number"}),
    (serializers.CharField, {"type": "string"}),
]


def _field_schema(field: serializers.Field) -> dict[str, Any]:
    if isinstance(field, serializers.ChoiceField):
        schema: dict[str, Any] = {"type": "string", "enum": list(field.choices.keys())}
    elif isinstance(field, serializers.ListField):
        schema = {"type": "array", "items": _field_schema(field.child)}
    elif isinstance(field, serializers.Serializer):
        schema = serializer_instance_to_json_schema(field)
    else:
        schema = next(
            (dict(mapped) for cls, mapped in _FIELD_TYPE_MAP if isinstance(field, cls)),
            {"type": "string"},  # bilinmeyen alan tipleri için güvenli varsayılan
        )

    if field.help_text:
        schema["description"] = str(field.help_text)
    return schema


def serializer_instance_to_json_schema(serializer: serializers.Serializer) -> dict[str, Any]:
    """Bir serializer ÖRNEĞİNİN (bound olması gerekmez) OpenAI ``parameters``
    şemasını üretir. Nested serializer alanları için özyinelemeli çağrılır."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, field in serializer.fields.items():
        if field.read_only:
            continue
        properties[name] = _field_schema(field)
        if field.required:
            required.append(name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def serializer_to_json_schema(serializer_class: type[serializers.Serializer]) -> dict[str, Any]:
    """Verilen (unbound) serializer SINIFININ OpenAI ``parameters`` şemasını üretir."""
    return serializer_instance_to_json_schema(serializer_class())
