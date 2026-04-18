"""BaseFeed — HTTP data feed with caching, rate limiting, and graceful degradation.

Subclass and set provider/cache_kind/default_ttl_hours, then implement fetch().
Uses ArtifactCache for transparent caching with TTL-based expiry.
"""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

try:
    import certifi
except Exception:
    certifi = None

from hermes_lib.cache import ArtifactCache


def _ssl_ctx() -> ssl.SSLContext | None:
    return ssl.create_default_context(cafile=certifi.where()) if certifi else None


_provider_timestamps: dict[str, list[float]] = {}


class BaseFeed:
    """Common infrastructure for all data feeds.

    Subclass attributes:
        provider: identifier for this feed (used in user-agent, logging)
        cache_kind: artifact kind used for cache storage
        default_ttl_hours: how long cached data is considered fresh
        rate_limit_per_minute: max requests per minute per provider
    """

    provider: str = "unknown"
    cache_kind: str = "data_feed"
    default_ttl_hours: float = 6.0
    rate_limit_per_minute: int = 30

    def __init__(self, cache: ArtifactCache):
        self.cache = cache

    def _cred(self, names: list[str], *, creds_path: Any = None) -> str | None:
        """Look up first available credential from .creds file or env."""
        for n in names:
            if creds_path:
                from hermes_lib.runtime import get_cred
                v = get_cred(n, creds_path)
            else:
                v = os.environ.get(n)
            if v:
                return v
        return None

    def _throttle(self) -> None:
        now = time.time()
        ts = _provider_timestamps.setdefault(self.provider, [])
        ts[:] = [t for t in ts if now - t < 60]
        if len(ts) >= self.rate_limit_per_minute:
            sleep_time = 60 - (now - ts[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        ts.append(time.time())

    def _user_agent(self) -> str:
        return f"hermes-bot/1.0 ({self.provider})"

    def _fetch_json(self, url: str, headers: dict | None = None, timeout: int = 20) -> Any:
        self._throttle()
        req = urllib.request.Request(url, headers=headers or {"User-Agent": self._user_agent()})
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            return json.loads(resp.read().decode())

    def _post_json(self, url: str, payload: dict, headers: dict | None = None, timeout: int = 30) -> Any:
        self._throttle()
        data = json.dumps(payload).encode()
        hdrs = headers or {}
        hdrs.setdefault("Content-Type", "application/json")
        hdrs.setdefault("User-Agent", self._user_agent())
        req = urllib.request.Request(url, data=data, headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            return json.loads(resp.read().decode())

    def _fetch_text(self, url: str, headers: dict | None = None, timeout: int = 20) -> str:
        self._throttle()
        req = urllib.request.Request(url, headers=headers or {"User-Agent": self._user_agent()})
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            return resp.read().decode()

    def _fetch_with_retry(
        self, url: str, headers: dict | None = None, timeout: int = 20,
        max_retries: int = 2, parse_json: bool = True,
    ) -> Any:
        """Fetch with exponential backoff on server errors."""
        last_exc: Exception | None = None
        for attempt in range(1 + max_retries):
            if attempt > 0:
                time.sleep(min(2 ** attempt, 8))
            try:
                if parse_json:
                    return self._fetch_json(url, headers=headers, timeout=timeout)
                else:
                    return self._fetch_text(url, headers=headers, timeout=timeout)
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    raise
                last_exc = exc
            except (urllib.error.URLError, OSError) as exc:
                last_exc = exc
        raise last_exc  # type: ignore[misc]

    def _check_cache(self, source_key: str, ttl_hours: float | None = None) -> dict | None:
        ttl = ttl_hours or self.default_ttl_hours
        row = self.cache.latest(kind=self.cache_kind, source=source_key)
        if not row:
            return None
        try:
            ts = datetime.fromisoformat(row.get("as_of") or row["created_at"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age_hours > ttl:
                return None
        except Exception:
            pass
        artifact = self.cache.read_artifact(row["path"])
        if artifact:
            return artifact.get("payload", {}).get("data", {})
        return None

    def _store_cache(self, source_key: str, data: dict) -> None:
        try:
            self.cache.write_artifact(
                kind=self.cache_kind,
                source=source_key,
                name=f"{self.provider}-{source_key}",
                payload={"data": data},
            )
        except Exception:
            pass

    def fetch(self, **kwargs: Any) -> dict[str, Any]:
        """Override in subclass. Returns data dict; should not raise."""
        raise NotImplementedError

    def safe_fetch(self, **kwargs: Any) -> dict[str, Any]:
        """Wrapper that catches all exceptions and returns an error dict."""
        try:
            return self.fetch(**kwargs)
        except Exception as exc:
            return {"provider": self.provider, "error": str(exc), "source": "unavailable"}
