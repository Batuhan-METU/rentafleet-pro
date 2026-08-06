"""Denetim izi (audit trail) — Django admin'in zaten var olan `LogEntry`
altyapısını kullanır; kim/ne/ne zaman/hangi kayıt için yeni bir model/tablo
İCAT ETMEZ (bkz. üretim sertleştirme + kusursuzluk denetimi bulguları).

``python manage.py admin`` panelinden ya da ``LogEntry.objects.filter(...)``
ile sorgulanabilir; Django'nun kendi ``django_admin_log`` tablosunu kullanır.
"""

from __future__ import annotations

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.db.models import Model


def log_change(*, user, obj: Model, message: str, created: bool = False) -> None:
    """Kimliği doğrulanmış bir kullanıcının bir modeldeki değişikliğini kaydeder.

    Anonim/sistem kaynaklı değişiklikler (``user`` None ya da doğrulanmamışsa)
    sessizce atlanır — ``LogEntry.user_id`` NOT NULL'dır, sahte bir kullanıcı
    uydurmak yanıltıcı bir denetim izi yaratır.

    Django 6, tekil-nesne ``log_action`` metodunu kaldırıp toplu
    ``log_actions``'a taşıdı — ``single_object=True`` ile eski tekil
    davranışı korur.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return
    LogEntry.objects.log_actions(
        user.pk,
        [obj],
        ADDITION if created else CHANGE,
        message,
        single_object=True,
    )
