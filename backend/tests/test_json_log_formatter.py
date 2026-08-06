"""`JsonFormatter` — DJANGO_LOG_FORMAT=json ile devreye giren yapılandırılmış
log biçimlendirici (bkz. settings.py LOGGING, common/json_log_formatter.py)."""

from __future__ import annotations

import json
import logging

from backend.common.json_log_formatter import JsonFormatter


def _make_record(msg: str, exc_info=None) -> logging.LogRecord:
    return logging.LogRecord(
        name="test.logger",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=exc_info,
    )


def test_formats_as_valid_single_line_json():
    formatter = JsonFormatter()
    output = formatter.format(_make_record("bir uyarı mesajı"))

    parsed = json.loads(output)
    assert parsed["level"] == "WARNING"
    assert parsed["logger"] == "test.logger"
    assert parsed["message"] == "bir uyarı mesajı"
    assert "timestamp" in parsed
    assert "exception" not in parsed


def test_includes_exception_traceback_when_present():
    formatter = JsonFormatter()
    try:
        raise ValueError("test hatası")
    except ValueError:
        import sys

        record = _make_record("hata oluştu", exc_info=sys.exc_info())

    parsed = json.loads(formatter.format(record))
    assert "ValueError: test hatası" in parsed["exception"]
