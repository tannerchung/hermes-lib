"""Ecosystem discovery: detect installed components and resolve credentials."""
from __future__ import annotations

import os
import shutil
from functools import cached_property
from pathlib import Path
from typing import Any

from .runtime import hermes_home, parse_key_value_file


class Ecosystem:
    """Lazy detector for Hermes ecosystem components.

    All properties are cached after first access. Call ``refresh()`` to
    re-probe the filesystem (useful in long-running processes after the
    user finishes setup mid-session).
    """

    def __init__(self, hermes_path: Path | None = None):
        self._hermes_path = hermes_path

    def _hermes_root(self) -> Path:
        return self._hermes_path or hermes_home()

    # ── component detection ──────────────────────────────────────

    @cached_property
    def hermes_installed(self) -> bool:
        root = self._hermes_root()
        return root.is_dir() and (root / "hermes-agent").is_dir()

    @cached_property
    def gbrain_installed(self) -> bool:
        return shutil.which("gbrain") is not None

    @cached_property
    def op_available(self) -> bool:
        return shutil.which("op") is not None

    @cached_property
    def obsidian_vault(self) -> Path | None:
        """Return the Obsidian vault path if explicitly configured or the
        default path already exists on disk.  Never creates directories."""
        explicit = os.environ.get("OBSIDIAN_VAULT")
        if explicit:
            p = Path(explicit).expanduser()
            return p if p.is_dir() else None

        default = Path.home() / "Documents" / "Obsidian" / "Personal"
        return default if default.is_dir() else None

    @cached_property
    def obsidian_available(self) -> bool:
        return self.obsidian_vault is not None

    # ── ecosystem manifest ───────────────────────────────────────

    @cached_property
    def ecosystem_json(self) -> dict[str, Any]:
        path = self._hermes_root() / "ecosystem.json"
        if not path.exists():
            return {}
        try:
            import json
            return json.loads(path.read_text())
        except Exception:
            return {}

    @cached_property
    def projects(self) -> list[str]:
        return self.ecosystem_json.get("project_roots", [])

    # ── hermes env file ──────────────────────────────────────────

    @cached_property
    def _hermes_env(self) -> dict[str, str]:
        """Parse ~/.hermes/.env once (mtime-cached by runtime module)."""
        env_path = self._hermes_root() / ".env"
        if not env_path.exists():
            return {}
        return parse_key_value_file(env_path)

    # ── credential resolution ────────────────────────────────────

    def resolve_cred(
        self,
        name: str,
        creds_path: Path | None = None,
        default: str | None = None,
    ) -> str | None:
        """Unified credential lookup.

        Priority:
        1. Project ``.creds`` file (if *creds_path* given)
        2. ``os.environ``
        3. ``~/.hermes/.env`` (if Hermes installed)
        4. *default*
        """
        if creds_path is not None:
            from .runtime import load_creds
            val = load_creds(creds_path).get(name)
            if val:
                return val

        val = os.environ.get(name)
        if val:
            return val

        val = self._hermes_env.get(name)
        if val:
            return val

        return default

    # ── lifecycle ────────────────────────────────────────────────

    def refresh(self) -> None:
        """Clear all cached properties so the next access re-probes."""
        for attr in list(vars(self)):
            if not attr.startswith("_hermes_path"):
                try:
                    delattr(self, attr)
                except AttributeError:
                    pass

    def summary(self) -> dict[str, Any]:
        """Human-readable snapshot for diagnostics / bin/setup output."""
        return {
            "hermes": self.hermes_installed,
            "gbrain": self.gbrain_installed,
            "obsidian": self.obsidian_available,
            "obsidian_vault": str(self.obsidian_vault) if self.obsidian_vault else None,
            "onepassword_cli": self.op_available,
            "projects": self.projects,
        }


_default_ecosystem: Ecosystem | None = None


def get_ecosystem() -> Ecosystem:
    """Module-level singleton for convenience."""
    global _default_ecosystem
    if _default_ecosystem is None:
        _default_ecosystem = Ecosystem()
    return _default_ecosystem


def resolve_cred(
    name: str,
    creds_path: Path | None = None,
    default: str | None = None,
) -> str | None:
    """Convenience wrapper around the singleton's resolve_cred."""
    return get_ecosystem().resolve_cred(name, creds_path, default)
