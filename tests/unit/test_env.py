import pytest
from librevdi_ext import env


def test_get_bool(monkeypatch):
    monkeypatch.setenv("X_BOOL", "yes")
    assert env.get_bool("X_BOOL", False) is True
    monkeypatch.setenv("X_BOOL", "0")
    assert env.get_bool("X_BOOL", True) is False
    monkeypatch.setenv("X_BOOL", "")
    assert env.get_bool("X_BOOL", True) is True
    monkeypatch.delenv("X_BOOL")
    assert env.get_bool("X_BOOL", False) is False


def test_get_list_and_int(monkeypatch):
    monkeypatch.setenv("X_LIST", " a, b ,,c ")
    assert env.get_list("X_LIST", []) == ["a", "b", "c"]
    assert env.get_list("X_MISSING", ["d"]) == ["d"]
    monkeypatch.setenv("X_INT", "42")
    assert env.get_int("X_INT", 1) == 42
    assert env.get_int("X_MISSING", 7) == 7


def test_secret_precedence(monkeypatch, tmp_path):
    f = tmp_path / "secret"
    f.write_text("from-file\n")
    default = tmp_path / "default"
    default.write_text("from-default")

    monkeypatch.delenv("X_SECRET", raising=False)
    monkeypatch.delenv("X_SECRET_FILE", raising=False)
    assert env.get_secret("X_SECRET", default_file=str(default)) == "from-default"

    monkeypatch.setenv("X_SECRET_FILE", str(f))
    assert env.get_secret("X_SECRET", default_file=str(default)) == "from-file"

    monkeypatch.setenv("X_SECRET", "from-env")
    assert env.get_secret("X_SECRET", default_file=str(default)) == "from-env"


def test_secret_required(monkeypatch, tmp_path):
    monkeypatch.delenv("X_SECRET", raising=False)
    monkeypatch.delenv("X_SECRET_FILE", raising=False)
    assert env.get_secret("X_SECRET") == ""
    with pytest.raises(env.ConfigError):
        env.get_secret("X_SECRET", default_file=str(tmp_path / "missing"), required=True)
