"""Tests for ArtifactCache."""
import json
import tempfile
from pathlib import Path

from hermes_lib.cache import ArtifactCache, _slug, _iso, _utc_now


def test_slug_basic():
    assert _slug("Hello World!") == "hello-world"
    assert _slug("   ") == "artifact"
    assert _slug("a" * 100, max_len=10) == "a" * 10


def test_iso_none():
    assert _iso(None) is None


def test_iso_naive_datetime():
    from datetime import datetime
    dt = datetime(2025, 1, 1, 12, 0, 0)
    result = _iso(dt)
    assert "+00:00" in result


def test_write_and_read_artifact():
    with tempfile.TemporaryDirectory() as tmp:
        cache = ArtifactCache(root=Path(tmp))
        result = cache.write_artifact(
            kind="test",
            source="unit",
            name="sample artifact",
            payload={"value": 42},
        )
        assert result["kind"] == "test"
        assert result["source"] == "unit"
        assert "path" in result
        assert Path(result["path"]).exists()

        rows = cache.read_manifest()
        assert len(rows) == 1
        assert rows[0]["kind"] == "test"


def test_latest_by_kind():
    with tempfile.TemporaryDirectory() as tmp:
        cache = ArtifactCache(root=Path(tmp))
        cache.write_artifact(kind="a", source="s", name="first", payload={})
        cache.write_artifact(kind="b", source="s", name="second", payload={})
        cache.write_artifact(kind="a", source="s", name="third", payload={})

        latest_a = cache.latest(kind="a")
        assert latest_a is not None
        assert latest_a["name"] == "third"

        latest_b = cache.latest(kind="b")
        assert latest_b is not None
        assert latest_b["name"] == "second"


def test_store_text():
    with tempfile.TemporaryDirectory() as tmp:
        cache = ArtifactCache(root=Path(tmp))
        result = cache.store_text(kind="note", source="test", name="hello", text="# Hello")
        artifact = json.loads(Path(result["path"]).read_text())
        assert artifact["payload"]["format"] == "markdown"
        assert artifact["payload"]["text"] == "# Hello"


def test_status():
    with tempfile.TemporaryDirectory() as tmp:
        cache = ArtifactCache(root=Path(tmp))
        cache.write_artifact(kind="x", source="s", name="one", payload={})
        cache.write_artifact(kind="x", source="s", name="two", payload={})
        cache.write_artifact(kind="y", source="s", name="three", payload={})

        st = cache.status()
        assert st["artifact_count"] == 3
        assert st["counts_by_kind"]["x"] == 2
        assert st["counts_by_kind"]["y"] == 1


def test_list_artifacts_filter():
    with tempfile.TemporaryDirectory() as tmp:
        cache = ArtifactCache(root=Path(tmp))
        cache.write_artifact(kind="a", source="s1", name="one", payload={})
        cache.write_artifact(kind="b", source="s2", name="two", payload={})

        assert len(cache.list_artifacts(kind="a")) == 1
        assert len(cache.list_artifacts(source="s2")) == 1
        assert len(cache.list_artifacts(kind="c")) == 0
