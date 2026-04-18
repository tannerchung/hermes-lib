# hermes-lib

Shared Python library for the [Hermes](https://github.com/tannerchung) ecosystem. Provides common primitives — credential resolution, artifact caching, HTTP feed clients, Obsidian markdown helpers, and ecosystem discovery — so bots like [stockbot](https://github.com/tannerchung/stockbot), [datebot](https://github.com/tannerchung/datebot), and future bots (mealbot, runningbot, etc.) don't re-implement the same patterns.

Zero required dependencies. Pure stdlib Python. Optional `certifi` for SSL certificate handling.

## Why this exists

Every bot in the ecosystem ends up needing the same things: load credentials from `.env` files, cache JSON artifacts to disk, fetch data from HTTP APIs, sync results to Obsidian. Before hermes-lib, each bot had its own copy of this boilerplate.

hermes-lib pulls those shared patterns into a single installable package. Bots still work without it — they carry local fallback implementations — but installing hermes-lib adds the **discovery layer** that bridges credentials and configuration across the entire ecosystem.

## Installation

```bash
pip install -e /path/to/hermes-lib

# typical ecosystem layout
pip install -e ~/Documents/Projects/hermes-lib
```

## Modules

### `hermes_lib.runtime` — Path resolution and credential loading

Core primitives for finding Hermes paths and resolving credentials from multiple sources.

| Function | Description |
|---|---|
| `hermes_home()` | Resolve the Hermes root directory (`HERMES_HOME` env var or `~/.hermes`) |
| `parse_key_value_file(path)` | Parse a `KEY=value` file into a dict |
| `load_creds(path)` | Load credentials from a file with mtime-based caching (re-reads only when the file changes) |
| `get_cred(key, creds_file)` | Look up a credential through the resolution chain: `.env` file → `os.environ` → `~/.hermes/.env` |

```python
from hermes_lib.runtime import get_cred, hermes_home

home = hermes_home()                          # ~/.hermes or $HERMES_HOME
api_key = get_cred("OPENAI_API_KEY", ".creds")  # checks .creds → env → ~/.hermes/.env
```

### `hermes_lib.discovery` — Ecosystem detection and unified credentials

Lazy detection of ecosystem components. Discovers what's installed (Hermes, GBrain, Obsidian, 1Password) and provides a single credential resolution interface across all of them.

| Symbol | Description |
|---|---|
| `Ecosystem` | Lazy-initialized class that detects available ecosystem components |
| `resolve_cred(key)` | Unified credential resolution across all discovered sources |
| `get_ecosystem()` | Module-level singleton accessor |

```python
from hermes_lib.discovery import get_ecosystem

eco = get_ecosystem()
cred = eco.resolve_cred("YELP_API_KEY")  # searches all discovered credential sources
```

### `hermes_lib.cache` — Versioned JSON artifact storage

Persistent artifact cache with a JSONL manifest and per-kind indexes for O(1) latest-artifact lookups.

```python
from pathlib import Path
from hermes_lib.cache import ArtifactCache

cache = ArtifactCache(root=Path("./my_cache"))
cache.write_artifact(kind="report", source="pipeline", name="daily", payload={"revenue": 42})
latest = cache.latest(kind="report")
```

Subclass to add domain-specific storage methods:

```python
class AdvisorCache(ArtifactCache):
    def store_pull(self, *, tool, data, **meta):
        self.write_artifact(kind="pull", source=tool, name=tool, payload=data, **meta)
```

### `hermes_lib.feeds` — HTTP feed client base class

Base class for building data-feed clients with built-in SSL context management, request throttling, credential resolution, and transparent caching.

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
        data = self._fetch_json(f"https://api.yelp.com/v3/businesses/search?location={city}")
        self._store_cache(f"yelp-{city}", data)
        return data
```

### `hermes_lib.obsidian` — Obsidian markdown helpers

Utilities for generating Obsidian-compatible markdown: YAML frontmatter, date parsing, and vault path resolution.

```python
from hermes_lib.obsidian import frontmatter, parse_created_at, default_vault_path

vault = default_vault_path()  # $OBSIDIAN_VAULT or ~/Documents/Obsidian/Personal
md = frontmatter({"title": "Daily Report", "date": "2025-01-15", "tags": ["finance"]})
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HERMES_HOME` | `~/.hermes` | Hermes installation root |
| `OBSIDIAN_VAULT` | `~/Documents/Obsidian/Personal` | Obsidian vault path for markdown sync |

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Architecture

```
┌──────────────────────────────────────────────────┐
│                 Hermes Orchestrator               │
│           (scheduling, coordination)              │
└──────────┬──────────┬──────────┬─────────────────┘
           │          │          │
     ┌─────▼──┐ ┌────▼───┐ ┌───▼────┐
     │stockbot│ │datebot │ │mealbot │  ...
     └────┬───┘ └───┬────┘ └───┬────┘
          │         │          │
          └─────────┼──────────┘
                    │
          ┌─────────▼─────────┐
          │    hermes-lib      │
          │  runtime · cache   │
          │  feeds · obsidian  │
          │  discovery         │
          └────────────────────┘
```

hermes-lib is the shared layer between standalone bots and the orchestrator. Each bot can be run independently — hermes-lib is an optional enhancement that provides ecosystem-wide credential resolution and consistent caching. Bots that import it get the full discovery chain; bots that don't fall back to their own local implementations.

## Contributing

- **New module**: add the source file in `hermes_lib/`, add corresponding tests in `tests/`.
- **Zero-dependency rule**: the library must remain pure stdlib. No third-party runtime dependencies. `certifi` is the only optional extra.
- **Testing**: all new code should have test coverage. Run `pytest tests/ -v` before submitting.

## License

[MIT](LICENSE)
