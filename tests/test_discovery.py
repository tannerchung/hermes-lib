"""Tests for ecosystem discovery and credential resolution."""
import json
import tempfile
from pathlib import Path

import pytest

from hermes_lib.discovery import Ecosystem, resolve_cred, get_ecosystem


@pytest.fixture
def fake_hermes(tmp_path):
    """Build a minimal ~/.hermes tree for testing."""
    hermes = tmp_path / ".hermes"
    hermes.mkdir()
    (hermes / "hermes-agent").mkdir()
    env_file = hermes / ".env"
    env_file.write_text("SHARED_KEY=from_hermes_env\nHERMES_ONLY=hermes_val\n")

    ecosystem = {
        "project_roots": ["~/Documents/Projects/stockbot"],
    }
    (hermes / "ecosystem.json").write_text(json.dumps(ecosystem))
    return hermes


@pytest.fixture
def creds_file(tmp_path):
    f = tmp_path / ".creds"
    f.write_text("LOCAL_KEY=from_creds\nSHARED_KEY=from_creds_too\n")
    return f


class TestEcosystemDetection:
    def test_hermes_installed_true(self, fake_hermes):
        eco = Ecosystem(hermes_path=fake_hermes)
        assert eco.hermes_installed is True

    def test_hermes_installed_false(self, tmp_path):
        eco = Ecosystem(hermes_path=tmp_path / "nonexistent")
        assert eco.hermes_installed is False

    def test_hermes_installed_no_agent_dir(self, tmp_path):
        hermes = tmp_path / ".hermes"
        hermes.mkdir()
        eco = Ecosystem(hermes_path=hermes)
        assert eco.hermes_installed is False

    def test_obsidian_explicit_env(self, tmp_path, monkeypatch):
        vault = tmp_path / "vault"
        vault.mkdir()
        monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))
        eco = Ecosystem(hermes_path=tmp_path)
        assert eco.obsidian_available is True
        assert eco.obsidian_vault == vault

    def test_obsidian_explicit_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_VAULT", str(tmp_path / "nope"))
        eco = Ecosystem(hermes_path=tmp_path)
        assert eco.obsidian_available is False

    def test_obsidian_no_env_no_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
        eco = Ecosystem(hermes_path=tmp_path)
        # default path unlikely to exist in tmp
        # just verify it doesn't crash
        assert isinstance(eco.obsidian_available, bool)

    def test_ecosystem_json_loaded(self, fake_hermes):
        eco = Ecosystem(hermes_path=fake_hermes)
        assert eco.projects == ["~/Documents/Projects/stockbot"]

    def test_ecosystem_json_missing(self, tmp_path):
        eco = Ecosystem(hermes_path=tmp_path / "nope")
        assert eco.ecosystem_json == {}
        assert eco.projects == []

    def test_refresh_clears_cache(self, fake_hermes):
        eco = Ecosystem(hermes_path=fake_hermes)
        assert eco.hermes_installed is True
        eco.refresh()
        # cached_property cleared, next access re-probes
        assert eco.hermes_installed is True

    def test_summary_shape(self, fake_hermes):
        eco = Ecosystem(hermes_path=fake_hermes)
        s = eco.summary()
        assert "hermes" in s
        assert "gbrain" in s
        assert "obsidian" in s
        assert "onepassword_cli" in s
        assert "projects" in s


class TestResolveCredPriority:
    def test_creds_file_wins(self, fake_hermes, creds_file, monkeypatch):
        monkeypatch.setenv("SHARED_KEY", "from_env")
        eco = Ecosystem(hermes_path=fake_hermes)
        # .creds has SHARED_KEY=from_creds_too, env has from_env, hermes has from_hermes_env
        val = eco.resolve_cred("SHARED_KEY", creds_path=creds_file)
        assert val == "from_creds_too"

    def test_env_wins_over_hermes(self, fake_hermes, monkeypatch):
        monkeypatch.setenv("SHARED_KEY", "from_env")
        eco = Ecosystem(hermes_path=fake_hermes)
        val = eco.resolve_cred("SHARED_KEY")
        assert val == "from_env"

    def test_hermes_env_fallback(self, fake_hermes, monkeypatch):
        monkeypatch.delenv("HERMES_ONLY", raising=False)
        eco = Ecosystem(hermes_path=fake_hermes)
        val = eco.resolve_cred("HERMES_ONLY")
        assert val == "hermes_val"

    def test_default_when_missing(self, fake_hermes):
        eco = Ecosystem(hermes_path=fake_hermes)
        val = eco.resolve_cred("DOES_NOT_EXIST", default="fallback")
        assert val == "fallback"

    def test_none_when_truly_missing(self, fake_hermes):
        eco = Ecosystem(hermes_path=fake_hermes)
        val = eco.resolve_cred("DOES_NOT_EXIST")
        assert val is None

    def test_creds_only_key(self, fake_hermes, creds_file, monkeypatch):
        monkeypatch.delenv("LOCAL_KEY", raising=False)
        eco = Ecosystem(hermes_path=fake_hermes)
        val = eco.resolve_cred("LOCAL_KEY", creds_path=creds_file)
        assert val == "from_creds"

    def test_no_creds_path(self, fake_hermes, monkeypatch):
        monkeypatch.setenv("DIRECT_KEY", "direct_val")
        eco = Ecosystem(hermes_path=fake_hermes)
        val = eco.resolve_cred("DIRECT_KEY")
        assert val == "direct_val"


class TestModuleLevelHelpers:
    def test_get_ecosystem_singleton(self):
        eco1 = get_ecosystem()
        eco2 = get_ecosystem()
        assert eco1 is eco2

    def test_resolve_cred_convenience(self, monkeypatch):
        monkeypatch.setenv("CONV_KEY", "conv_val")
        val = resolve_cred("CONV_KEY")
        assert val == "conv_val"
