"""AI asistanı görünümleri: SSE sohbet akışı + mutasyon eylemi onayı."""
from __future__ import annotations

from django.db import transaction
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.ai.models import AIPendingAction
from backend.common.multitenancy_tools.scope import require_user_company
from backend.common.permissions import IsFleetManager
from backend.infrastructure.services.ai.agent_service import (
    execute_confirmed_action,
    stream_ai_agent_sse,
)


class EventStreamRenderer(BaseRenderer):
    """DRF içerik müzakeresi için SSE medya tipi (stream yanıtı doğrudan geçer)."""

    media_type = "text/event-stream"
    format = "event-stream"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class AIConsultantView(APIView):
    """POST /api/ai/consult/ — AI Filo Operasyon Asistanı (SSE stream).

    Gövde: ``{"query": "...", "history": [{"role": "user"|"ai", "text": "..."}]}``
    ``history`` opsiyoneldir — gönderilmezse davranış tek turlu bir soru gibi çalışır.
    """

    permission_classes = (IsFleetManager,)
    renderer_classes = (EventStreamRenderer, JSONRenderer)

    def post(self, request: Request) -> StreamingHttpResponse | Response:
        query = request.data.get("query", "")
        if not isinstance(query, str) or not query.strip():
            return Response(
                {"error": "Lütfen bir soru girin ('query' alanı boş olamaz)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        history = request.data.get("history", [])
        if not isinstance(history, list):
            history = []

        company = require_user_company(request)

        response = StreamingHttpResponse(
            stream_ai_agent_sse(request, query.strip(), history, company_id=company.pk),
            content_type="text/event-stream; charset=utf-8",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class AIActionConfirmView(APIView):
    """POST /api/ai/actions/<uuid:pk>/confirm/ — AI'nin önerdiği bir mutasyon
    eylemini GERÇEKTEN çalıştırır.

    Güvenlik: eylem satırı ``select_for_update()`` ile kilitlenip
    ``consumed_at`` yalnızca BAŞARILI çalıştırma sonrası işaretlenir — çift
    tıklamada ikinci istek birincinin bitmesini bekler (kilit), birinci
    başarısız olursa (rollback) ikinci istek anahtarı temiz bulur ve normal
    şekilde tekrar dener (bkz. ``common/idempotency.py``'deki aynı ilke:
    reddedilen bir deneme anahtarı kilitlememeli).
    """

    permission_classes = (IsFleetManager,)

    def post(self, request: Request, pk: str) -> Response:
        company = require_user_company(request)

        with transaction.atomic():
            try:
                pending = AIPendingAction.objects.select_for_update().get(pk=pk)
            except (AIPendingAction.DoesNotExist, ValueError, TypeError) as exc:
                raise NotFound("Onay isteği bulunamadı veya süresi dolmuş.") from exc

            if pending.company_id != company.pk:
                raise NotFound("Onay isteği bulunamadı veya süresi dolmuş.")
            if pending.is_consumed:
                raise ValidationError({"error": "Bu eylem zaten çalıştırıldı."})
            if pending.is_expired:
                raise ValidationError(
                    {"error": "Onay süresi doldu, lütfen isteği asistana tekrar iletin."}
                )

            result = execute_confirmed_action(request, pending)
            pending.consumed_at = timezone.now()
            pending.save(update_fields=["consumed_at"])

        return Response(result, status=status.HTTP_200_OK)
