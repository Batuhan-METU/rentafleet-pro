"""Celery uygulaması — arka plan işleri (bkz. `infrastructure/services/*/tasks.py`).

Worker başlatmak için (repo kökünden)::

    celery -A backend.celery_app worker --loglevel=info
    celery -A backend.celery_app beat --loglevel=info   # periyodik görevler

``REDIS_URL`` ayarlı değilse broker `settings.CELERY_TASK_ALWAYS_EAGER` sayesinde
senkron/doğrudan çalışır (ayrı bir worker süreci gerekmez) — yerel geliştirme/
test/CI'da hiçbir şey kırılmaz (bkz. settings.py CACHES ile aynı env-gated desen).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

from celery import Celery  # noqa: E402

app = Celery("rentafleet")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(
    [
        "backend.infrastructure.services.enuygun",
    ]
)
