# Changelog

## 0.1.0 (2026-04-18)

Initial release.

- `hermes_lib.runtime` — path resolution, key-value file parsing, mtime-cached credential loading (`get_cred`)
- `hermes_lib.cache` — versioned JSON artifact storage (`ArtifactCache`) with JSONL manifest and `latest_by_kind` index
- `hermes_lib.feeds` — HTTP feed client base class (`BaseFeed`) with SSL context, throttling, credential resolution, and cache TTL
- `hermes_lib.obsidian` — Obsidian markdown helpers (frontmatter generation, date parsing, vault path resolution)
- `hermes_lib.discovery` — ecosystem detection (`Ecosystem` class) and unified credential resolution (`resolve_cred`) bridging project `.env`, `os.environ`, and `~/.hermes/.env`
- 41 unit tests across all modules
- Zero required dependencies (pure stdlib); optional `certifi` for SSL
