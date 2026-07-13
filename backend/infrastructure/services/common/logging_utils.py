"""Servis katmanı log susturma yardımcıları."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def quiet_loggers(*logger_names: str, level: int = logging.ERROR) -> Iterator[None]:
    """Belirtilen logger'ların seviyesini geçici olarak yükseltir."""
    loggers = [logging.getLogger(name) for name in logger_names]
    previous = [lg.level for lg in loggers]
    for lg in loggers:
        lg.setLevel(level)
    try:
        yield
    finally:
        for lg, prev in zip(loggers, previous):
            lg.setLevel(prev)