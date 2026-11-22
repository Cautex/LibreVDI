"""Logging configuration: everything to stdout, optionally as JSON lines."""

import copy
import json
import logging
import typing


class JsonFormatter(logging.Formatter):
    """Minimal JSON-lines formatter (no external dependency)."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, typing.Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "pid": record.process,
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


# Very chatty at INFO level (plugin registration on every start, PDF rendering)
QUIET_LOGGERS: tuple[str, ...] = (
    "uds.core.util.modfinder",
    "uds.REST.dispatcher",
    "weasyprint",
    "fontTools",
)


def build_logging_config(upstream: dict, level: str, fmt: str) -> dict:
    """Keep upstream logger names (auth, use, trace ...) but route all handlers to stdout."""
    cfg = copy.deepcopy(upstream)
    cfg["formatters"]["json"] = {"()": "librevdi_ext.logging.JsonFormatter"}
    for name, handler in list(cfg["handlers"].items()):
        if handler.get("class") == "logging.NullHandler":
            continue
        formatter = "json" if fmt == "json" else handler.get("formatter", "simple")
        cfg["handlers"][name] = {
            "level": "DEBUG",
            "class": "librevdi_ext.console.ConsoleHandler",
            "stream": "ext://sys.stdout",
            "formatter": formatter,
        }
    for name, logger in cfg["loggers"].items():
        if name.startswith("django.db.backends"):
            logger["level"] = "WARNING"  # SQL debug logging is far too verbose for containers
        elif logger.get("level") == "DEBUG":  # upstream sample computes these from DEBUG_LOG
            logger["level"] = level
    for name in QUIET_LOGGERS:
        if level in ("DEBUG",):
            continue
        cfg["loggers"][name] = {"handlers": ["console"], "level": "WARNING", "propagate": False}
    return cfg
