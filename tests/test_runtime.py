"""Tests for runtime helpers."""
import tempfile
from pathlib import Path

from hermes_lib.runtime import parse_key_value_file, load_creds, get_cred, hermes_home


def test_parse_key_value_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".creds", delete=False) as f:
        f.write("# comment\n")
        f.write("KEY1=value1\n")
        f.write("KEY2='quoted value'\n")
        f.write('KEY3="double quoted"\n')
        f.write("\n")
        f.write("EMPTY=\n")
        path = Path(f.name)

    result = parse_key_value_file(path)
    assert result["KEY1"] == "value1"
    assert result["KEY2"] == "quoted value"
    assert result["KEY3"] == "double quoted"
    assert result["EMPTY"] == ""
    path.unlink()


def test_parse_missing_file():
    result = parse_key_value_file(Path("/nonexistent"))
    assert result == {}


def test_get_cred_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".creds", delete=False) as f:
        f.write("API_KEY=secret123\n")
        path = Path(f.name)

    assert get_cred("API_KEY", path) == "secret123"
    assert get_cred("MISSING", path) is None
    assert get_cred("MISSING", path, "fallback") == "fallback"
    path.unlink()


def test_get_cred_env_fallback(monkeypatch):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".creds", delete=False) as f:
        f.write("")
        path = Path(f.name)

    monkeypatch.setenv("MY_SECRET", "from_env")
    assert get_cred("MY_SECRET", path) == "from_env"
    path.unlink()


def test_hermes_home_default(monkeypatch):
    monkeypatch.delenv("HERMES_HOME", raising=False)
    assert hermes_home() == Path.home() / ".hermes"


def test_hermes_home_env(monkeypatch):
    monkeypatch.setenv("HERMES_HOME", "/tmp/test-hermes")
    assert hermes_home() == Path("/tmp/test-hermes")
