import json
import logging

from librevdi_ext.logging import QUIET_LOGGERS, JsonFormatter, build_logging_config

UPSTREAM = {
    "version": 1,
    "formatters": {"simple": {"format": "%(message)s"}},
    "handlers": {
        "null": {"class": "logging.NullHandler"},
        "file": {"class": "uds.core.util.log.UDSLogHandler", "formatter": "simple", "filename": "/x"},
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "loggers": {
        "": {"handlers": ["file"], "level": "DEBUG"},
        "django.db.backends": {"handlers": ["file"], "level": "DEBUG"},
        "authLog": {"handlers": ["file"], "level": "INFO"},
    },
}


def test_all_handlers_go_to_stdout():
    cfg = build_logging_config(UPSTREAM, level="INFO", fmt="text")
    assert cfg["handlers"]["null"]["class"] == "logging.NullHandler"
    for name in ("file", "console"):
        assert cfg["handlers"][name]["class"] == "librevdi_ext.console.ConsoleHandler"
        assert cfg["handlers"][name]["stream"] == "ext://sys.stdout"
        assert "filename" not in cfg["handlers"][name]
    # upstream dict untouched
    assert UPSTREAM["handlers"]["file"]["class"] == "uds.core.util.log.UDSLogHandler"


def test_levels_and_quiet_loggers():
    cfg = build_logging_config(UPSTREAM, level="INFO", fmt="json")
    assert cfg["loggers"][""]["level"] == "INFO"
    assert cfg["loggers"]["django.db.backends"]["level"] == "WARNING"
    assert cfg["loggers"]["authLog"]["level"] == "INFO"
    assert cfg["handlers"]["file"]["formatter"] == "json"
    for name in QUIET_LOGGERS:
        assert cfg["loggers"][name]["level"] == "WARNING"


def test_json_formatter():
    record = logging.LogRecord("uds.test", logging.WARNING, __file__, 10, "hello %s", ("world",), None)
    data = json.loads(JsonFormatter().format(record))
    assert data["msg"] == "hello world"
    assert data["level"] == "WARNING"
    assert data["logger"] == "uds.test"
