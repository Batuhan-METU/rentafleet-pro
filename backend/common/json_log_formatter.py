"""Tek satırlık JSON log formatlayıcı — üretimde log toplama araçları
(ELK, Datadog, CloudWatch vb.) yapılandırılmış (structured) logu ayrıştırmayı
serbest metinden çok daha güvenilir bulur. `DJANGO_LOG_FORMAT=json` ile
devreye girer (bkz. settings.py LOGGING) — varsayılan `text`, yerel
geliştirmede okunur kalır.
"""

from __future__ import annotations

import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
