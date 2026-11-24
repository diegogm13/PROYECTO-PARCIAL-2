"""Logs estructurados en JSON (stdout) con trace_id/span_id para correlacionar con las trazas."""
import json
import logging
import sys
from datetime import datetime, timezone

from opentelemetry import trace

# Atributos estándar de LogRecord: todo lo demás se considera un campo "extra"
_RESERVED = set(vars(logging.LogRecord("x", 0, "x", 0, "x", None, None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            entry["trace_id"] = format(ctx.trace_id, "032x")
            entry["span_id"] = format(ctx.span_id, "016x")
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("otel"):
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_logging(level=logging.INFO):
    root = logging.getLogger()
    root.setLevel(level)
    if not any(getattr(h, "_sa_json", False) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler._sa_json = True
        root.addHandler(handler)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
