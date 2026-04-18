"""Project runtime helpers: credential loading, path resolution, environment."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_kv_cache: dict[str, tuple[float, dict[str, str]]] = {}


def hermes_home() -> Path:
    """Resolve HERMES_HOME from env, falling back to ~/.hermes."""
    raw = os.environ.get("HERMES_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hermes"


def parse_key_value_file(path: Path) -> dict[str, str]:
    """Parse a KEY=value file (shell-style, # comments, optional quotes)."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def load_creds(creds_path: Path) -> dict[str, str]:
    """Load credentials from a .creds file with mtime caching."""
    key = str(creds_path)
    try:
        mtime = creds_path.stat().st_mtime
    except OSError:
        _kv_cache.pop(key, None)
        return {}
    entry = _kv_cache.get(key)
    if entry and entry[0] == mtime:
        return entry[1]
    data = parse_key_value_file(creds_path)
    _kv_cache[key] = (mtime, data)
    return data


def get_cred(
    name: str,
    creds_path: Path,
    default: str | None = None,
    *,
    check_env: bool = True,
) -> str | None:
    """Look up a credential by name: .creds file first, then env."""
    value = load_creds(creds_path).get(name)
    if value:
        return value
    if check_env:
        return os.environ.get(name, default)
    return default
