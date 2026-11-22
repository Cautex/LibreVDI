"""Small helpers to read configuration from environment variables and secret files."""

import os


class ConfigError(RuntimeError):
    """Raised when a required configuration value is missing."""


def get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def get_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def get_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def get_list(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def get_secret(name: str, default_file: str = "", required: bool = False) -> str:
    """Return a secret from ``NAME``, from the file named in ``NAME_FILE`` or from ``default_file``."""
    value = os.environ.get(name)
    if value:
        return value
    path = os.environ.get(f"{name}_FILE") or default_file
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    if required:
        raise ConfigError(f"Missing required secret {name} (set {name}, {name}_FILE or run 'librevdi-entrypoint init')")
    return ""
