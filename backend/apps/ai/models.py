from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone

PENDING_ACTION_TTL = timedelta(minutes=5)


class AIPendingAction(models.Model):
    """AI asistanının önerdiği ama henüz ÇALIŞTIRMADIĞI bir mutasyon eylemi.

    Sohbette gösterilen onay kartının güvenlik temeli: opak UUID PK + şirket/
    kullanıcı eşleşme kontrolü + tek kullanımlık ``consumed_at`` —
    ``IdempotencyRecord``'daki "DB satırı = mutex" deseniyle tutarlı, HMAC
    token imzalamaya göre daha basit. Kullanıcı "Onayla"ya basmadıkça
    (``AIActionConfirmView``) ilgili tool handler'ı ASLA çağrılmaz.
    """

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="+")
    requested_by = models.ForeignKey("companies.CustomUser", on_delete=models.CASCADE, related_name="+")
    tool_name = models.CharField(max_length=64)
    arguments = models.JSONField(encoder=DjangoJSONEncoder)
    summary = models.TextField(help_text="Kullanıcıya onay kartında gösterilen Türkçe özet.")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ai_pending_action"

    def save(self, *args, **kwargs) -> None:
        if self.expires_at is None:
            self.expires_at = timezone.now() + PENDING_ACTION_TTL
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None
