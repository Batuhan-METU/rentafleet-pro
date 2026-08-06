"""`Idempotency-Key` header desteği — aynı anahtarla tekrarlanan bir POST,
kaynağı ikinci kez oluşturmak yerine ilk seferki yanıtı aynen döner.

Kullanım: ``@idempotent(endpoint="rentals.create")`` ile bir DRF view'ının
``post`` metodunu sar. ``Idempotency-Key`` header'ı gönderilmezse davranış
DEĞİŞMEZ (dekoratör şeffaf biçimde devre dışı kalır) — mevcut istemciler
(frontend) hiçbir değişiklik yapmadan çalışmaya devam eder; anahtar YALNIZCA
gönderen taraf (ör. yeniden deneme mantığı olan bir istemci) isterse
devreye girer.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from backend.apps.idempotency.models import IdempotencyRecord


def idempotent(*, endpoint: str) -> Callable:
    """(company, endpoint, key) üzerindeki DB UniqueConstraint'i eşzamanlılık
    mutex'i olarak kullanır: ilk istek bir "beklemede" satır (response
    alanları None) yaratmayı DENER. Başarılıysa view çalışır, sonuç satıra
    yazılır. Aynı anahtarla eşzamanlı gelen bir istek bu INSERT'te
    ``IntegrityError`` alır — mevcut satır tamamlanmışsa kayıtlı yanıtı
    aynen döner, hâlâ işleniyorsa (nadir yarış penceresi) 409 döner.
    """

    def decorator(view_method: Callable) -> Callable:
        @functools.wraps(view_method)
        def wrapper(self, request: Request, *args, **kwargs):
            key = request.headers.get("Idempotency-Key", "").strip()
            if not key:
                return view_method(self, request, *args, **kwargs)

            company = getattr(request.user, "company", None)
            if company is None:
                return view_method(self, request, *args, **kwargs)

            try:
                with transaction.atomic():
                    record = IdempotencyRecord.objects.create(
                        company=company, endpoint=endpoint, key=key
                    )
            except IntegrityError:
                existing = IdempotencyRecord.objects.filter(
                    company=company, endpoint=endpoint, key=key
                ).first()
                if existing is not None and existing.response_status is not None:
                    return Response(existing.response_body, status=existing.response_status)
                return Response(
                    {"error": "Aynı istek şu anda işleniyor, lütfen kısa bir süre sonra tekrar deneyin."},
                    status=status.HTTP_409_CONFLICT,
                )

            try:
                response = view_method(self, request, *args, **kwargs)
            except Exception:
                # GERÇEK HATA (doğrulama/izin hatası dahil — DRF bunları
                # normal akışta İSTİSNA olarak fırlatır, Response DÖNDÜRMEZ;
                # ör. enforce_risk_and_eligibility reddedilince ValidationError
                # fırlatır). Bu durumda "beklemede" kaydı SİLİNMEZSE, anahtar
                # response_status=None'da SONSUZA DEK takılı kalır — aynı
                # anahtarla yapılan HER sonraki deneme (isteğin düzeltilmiş
                # bir tekrarı olsa bile) 409 "işleniyor" almaya devam eder.
                # Kaydı silmek, istemcinin aynı anahtarla güvenle tekrar
                # deneyebilmesini sağlar.
                record.delete()
                raise

            record.response_status = response.status_code
            record.response_body = response.data
            record.save(update_fields=["response_status", "response_body"])
            return response

        return wrapper

    return decorator
