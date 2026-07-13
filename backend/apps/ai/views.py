"""AI danışman SSE görünümleri."""
from __future__ import annotations

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.common.permissions import IsFleetManager
from backend.infrastructure.services.ai.ai_consultant_service import stream_ai_fleet_advice_sse
from backend.common.multitenancy_tools.scope import require_user_company


class EventStreamRenderer(BaseRenderer):
    """DRF içerik müzakeresi için SSE medya tipi (stream yanıtı doğrudan geçer)."""

    media_type = "text/event-stream"
    format = "event-stream"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class AIConsultantView(APIView):
    """POST /api/ai/consult/ — AI Filo Danışmanı (SSE stream)."""

    permission_classes = (IsFleetManager,)
    renderer_classes = (EventStreamRenderer, JSONRenderer)

    def post(self, request: Request) -> StreamingHttpResponse | Response:
        query = request.data.get("query", "")
        if not isinstance(query, str) or not query.strip():
            return Response(
                {"error": "Lütfen bir soru girin ('query' alanı boş olamaz)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company = require_user_company(request)

        response = StreamingHttpResponse(
            stream_ai_fleet_advice_sse(query.strip(), company_id=company.pk),
            content_type="text/event-stream; charset=utf-8",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response