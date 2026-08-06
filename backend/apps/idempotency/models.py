from __future__ import annotations

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class IdempotencyRecord(models.Model):
    """`Idempotency-Key` header'ıyla gönderilen bir POST isteğinin sonucu.

    (company, endpoint, key) birleşik benzersizliği aynı zamanda eşzamanlılık
    mutex'i olarak kullanılır (bkz. ``common/idempotency.py``): ilk isteği
    işleyen bir "beklemede" satır (response_status=None) YARATIR; aynı
    anahtarla gelen ikinci bir istek bu INSERT'te ``IntegrityError`` alır —
    bu, DB seviyesinde atomik bir "ilk gelen kazanır" garantisi verir.
    """

    key = models.CharField(max_length=255)
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="+",
    )
    endpoint = models.CharField(
        max_length=255,
        help_text="Anahtarın hangi uç noktaya ait olduğu (ör. 'rentals.create') — "
        "aynı anahtarın farklı uç noktalarda çakışmasını önler.",
    )
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "idempotency_record"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "endpoint", "key"],
                name="unique_idempotency_key_per_company_endpoint",
            ),
        ]
