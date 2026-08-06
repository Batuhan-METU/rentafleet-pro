"""Excel dışa aktarma view'ları için ortak indirme yanıtı."""

from __future__ import annotations

from django.http import HttpResponse
from django.utils import timezone

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def xlsx_attachment_response(content: bytes, filename_prefix: str) -> HttpResponse:
    """``<prefix>_<YYYY-AA-GG>.xlsx`` adıyla indirilen bir ek yanıtı üretir."""
    filename = f"{filename_prefix}_{timezone.localdate():%Y-%m-%d}.xlsx"
    response = HttpResponse(content, content_type=XLSX_CONTENT_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
