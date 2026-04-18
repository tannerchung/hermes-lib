"""Tests for Obsidian helpers."""
from datetime import datetime, timezone
from pathlib import Path

from hermes_lib.obsidian import frontmatter, parse_created_at, date_str, default_vault_path


def test_frontmatter_basic():
    result = frontmatter({"title": "Hello", "draft": True, "count": 5})
    assert result.startswith("---")
    assert result.endswith("---")
    assert 'title: "Hello"' in result
    assert "draft: true" in result
    assert "count: 5" in result


def test_frontmatter_list():
    result = frontmatter({"tags": ["a", "b", "c"]})
    assert "tags: [a, b, c]" in result


def test_frontmatter_none():
    result = frontmatter({"value": None})
    assert "value: null" in result


def test_parse_created_at_valid():
    artifact = {"created_at": "2025-06-15T10:30:00+00:00"}
    dt = parse_created_at(artifact)
    assert dt.year == 2025
    assert dt.month == 6
    assert dt.tzinfo is not None


def test_parse_created_at_missing():
    dt = parse_created_at({})
    assert dt.tzinfo is not None


def test_date_str():
    dt = datetime(2025, 1, 15, tzinfo=timezone.utc)
    assert date_str(dt) == "2025-01-15"


def test_default_vault_path_env(monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT", "/tmp/my-vault")
    assert default_vault_path() == Path("/tmp/my-vault")


def test_default_vault_path_default(monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
    result = default_vault_path()
    assert result == Path.home() / "Documents" / "Obsidian" / "Personal"
