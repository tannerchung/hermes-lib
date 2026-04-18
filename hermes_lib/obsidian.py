"""Obsidian markdown helpers: frontmatter, datetime parsing, vault path resolution."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_vault_path() -> Path:
    """Resolve Obsidian vault path from OBSIDIAN_VAULT env or platform default."""
    env = os.environ.get("OBSIDIAN_VAULT")
    if env:
        return Path(env).expanduser()
    return Path.home() / "Documents" / "Obsidian" / "Personal"


def parse_created_at(artifact: dict) -> datetime:
    """Extract and parse created_at from an artifact dict."""
    raw = artifact.get("created_at", "")
    if not raw:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def frontmatter(fields: dict[str, Any]) -> str:
    """Render YAML frontmatter block from a dict."""
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            safe = str(value).replace('"', '\\"')
            lines.append(f'{key}: "{safe}"')
    lines.append("---")
    return "\n".join(lines)
