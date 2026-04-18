"""ArtifactCache — versioned JSON artifact storage with JSONL manifest and indexes.

Provides a directory-based cache for structured artifacts with:
- Date-partitioned storage: artifacts/<kind>/YYYY/MM/DD/<id>.json
- Append-only JSONL manifest with file locking
- Precomputed latest-by-kind index for O(1) lookups
- Mtime-based manifest caching to avoid re-parsing
"""
from __future__ import annotations

import fcntl
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _age_minutes(fetched_at: str | None) -> float | None:
    dt = _parse_datetime(fetched_at)
    if dt is None:
        return None
    return round((_utc_now() - dt).total_seconds() / 60.0, 2)


def _slug(value: str, max_len: int = 80) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value[:max_len] or "artifact"


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON atomically via tmp-file + rename to avoid partial reads."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class ArtifactCache:
    """Base artifact cache with manifest, latest-by-kind index, and status.

    Subclass to add domain-specific storage methods (e.g. store_truthifi_pull,
    for_user/for_shared namespacing).
    """

    def __init__(self, root: Path):
        self.root = root
        self.artifacts_dir = self.root / "artifacts"
        self.index_dir = self.root / "index"
        self.latest_dir = self.root / "latest"
        for d in (self.artifacts_dir, self.index_dir, self.latest_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.index_dir / "manifest.jsonl"
        self.latest_by_kind_path = self.latest_dir / "latest_by_kind.json"
        self._manifest_cache: list[dict[str, Any]] | None = None
        self._manifest_mtime: float = 0.0

    def artifact_path(self, kind: str, created_at: datetime, artifact_id: str) -> Path:
        return self.artifacts_dir / kind / created_at.strftime("%Y/%m/%d") / f"{artifact_id}.json"

    def write_artifact(
        self,
        *,
        kind: str,
        source: str,
        name: str,
        payload: dict[str, Any],
        as_of: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        created_at = _utc_now()
        artifact_id = f"{created_at.strftime('%Y%m%dT%H%M%SZ')}-{kind}-{_slug(name, 48)}"

        artifact = {
            "artifact_id": artifact_id,
            "kind": kind,
            "source": source,
            "name": name,
            "created_at": _iso(created_at),
            "as_of": as_of,
            "tags": tags or [],
            "metadata": metadata or {},
            "payload": payload,
        }

        path = self.artifact_path(kind, created_at, artifact_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact, indent=2, sort_keys=True, default=_json_default))

        manifest_record = {
            "artifact_id": artifact_id,
            "kind": kind,
            "source": source,
            "name": name,
            "created_at": artifact["created_at"],
            "as_of": as_of,
            "path": str(path),
            "tags": artifact["tags"],
        }
        line = json.dumps(manifest_record, sort_keys=True, default=_json_default) + "\n"
        with self.manifest_path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                handle.write(line)
                handle.flush()
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

        self._manifest_cache = None
        self._rebuild_indexes()
        return artifact | {"path": str(path)}

    def store_text(
        self,
        *,
        kind: str,
        source: str,
        name: str,
        text: str,
        format: str = "markdown",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.write_artifact(
            kind=kind, source=source, name=name,
            payload={"format": format, "text": text}, **kwargs,
        )

    def read_manifest(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        try:
            mtime = self.manifest_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        if self._manifest_cache is not None and mtime == self._manifest_mtime:
            return self._manifest_cache
        rows: list[dict[str, Any]] = []
        for line in self.manifest_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                print(f"[cache] skipping corrupt manifest line: {line[:80]}", file=sys.stderr)
                continue
            if not isinstance(row, dict) or "kind" not in row:
                continue
            rows.append(row)
        rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
        self._manifest_cache = rows
        self._manifest_mtime = mtime
        return rows

    def list_artifacts(
        self, kind: str | None = None, source: str | None = None, limit: int = 20,
    ) -> list[dict[str, Any]]:
        rows = self.read_manifest()
        if kind:
            rows = [r for r in rows if r.get("kind") == kind]
        if source:
            rows = [r for r in rows if r.get("source") == source]
        return rows[:limit]

    def latest(self, kind: str | None = None, source: str | None = None) -> dict[str, Any] | None:
        if kind and not source:
            try:
                if self.latest_by_kind_path.exists():
                    index = json.loads(self.latest_by_kind_path.read_text())
                    row = index.get(kind)
                    if row and isinstance(row, dict):
                        return row
            except Exception:
                pass
        rows = self.list_artifacts(kind=kind, source=source, limit=1)
        return rows[0] if rows else None

    def read_artifact(self, path: str) -> dict[str, Any] | None:
        try:
            return json.loads(Path(path).read_text())
        except Exception:
            return None

    def _rebuild_indexes(self) -> None:
        rows = self.read_manifest()
        latest_by_kind: dict[str, dict[str, Any]] = {}
        counts_by_kind: dict[str, int] = {}
        for row in rows:
            kind = row.get("kind")
            if not kind:
                continue
            counts_by_kind[kind] = counts_by_kind.get(kind, 0) + 1
            if kind not in latest_by_kind:
                latest_by_kind[kind] = row
        _atomic_write_json(self.latest_by_kind_path, latest_by_kind)

    def status(self) -> dict[str, Any]:
        rows = self.read_manifest()
        counts: dict[str, int] = {}
        for row in rows:
            k = row.get("kind", "unknown")
            counts[k] = counts.get(k, 0) + 1
        return {
            "root": str(self.root),
            "artifact_count": len(rows),
            "counts_by_kind": counts,
        }
