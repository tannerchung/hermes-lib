# hermes-lib

Shared primitives for Hermes ecosystem bots. Provides the building blocks that [stockbot](https://github.com/tannerchung/stockbot), [datebot](https://github.com/tannerchung/datebot), and future bots share.

## Install

```bash
pip install hermes-lib          # from PyPI (once published)
pip install -e .                # local dev
```

## Modules

### `hermes_lib.cache` — ArtifactCache

Versioned JSON artifact storage with JSONL manifest and O(1) latest-by-kind lookups.

```python
from hermes_lib.cache import ArtifactCache

cache = ArtifactCache(root=Path("./my_cache"))
cache.write_artifact(kind="report", source="pipeline", name="daily", payload={...})
latest = cache.latest(kind="report")
```

Subclass to add domain-specific methods:

```python
class AdvisorCache(ArtifactCache):
    def store_truthifi_pull(self, *, tool, data, ...):
        ...
```

### `hermes_lib.feeds` — BaseFeed

HTTP data feed base class with SSL, rate limiting, caching, and graceful degradation.

```python
from hermes_lib.feeds import BaseFeed

class YelpFeed(BaseFeed):
    provider = "yelp"
    cache_kind = "restaurant_feed"
    default_ttl_hours = 4.0

    def fetch(self, city="NYC"):
        cached = self._check_cache(f"yelp-{city}")
        if cached:
            return cached
        data = self._fetch_json(f"https://api.yelp.com/v3/...")
        self._store_cache(f"yelp-{city}", data)
        return data
```

### `hermes_lib.runtime` — Credential & Path Helpers

```python
from hermes_lib.runtime import get_cred, hermes_home, parse_key_value_file

api_key = get_cred("OPENAI_API_KEY", Path(".creds"))
home = hermes_home()  # ~/.hermes or HERMES_HOME env
```

### `hermes_lib.obsidian` — Markdown Helpers

```python
from hermes_lib.obsidian import frontmatter, parse_created_at, default_vault_path

vault = default_vault_path()  # OBSIDIAN_VAULT env or ~/Documents/Obsidian/Personal
md = frontmatter({"title": "Report", "date": "2025-01-15", "tags": ["finance"]})
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HERMES_HOME` | `~/.hermes` | Hermes installation root |
| `OBSIDIAN_VAULT` | `~/Documents/Obsidian/Personal` | Obsidian vault for markdown sync |

## Testing

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
