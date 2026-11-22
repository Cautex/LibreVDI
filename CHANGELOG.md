# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/de/1.1.0/). Versions follow
[Semantic Versioning](https://semver.org/lang/de/) once the first release is tagged.

## [Unreleased]

### Added (Phase 2)
- Windows builds in GitHub Actions: LibreVDI Agent (OpenUDS actor, `unmanaged` and `managed`
  installers) and LibreVDI Client (OpenUDS launcher with FreeRDP, FFmpeg, OpenSSL runtime DLLs,
  installer registering `udssv2://`). Native client dependencies are cached.
- Guide for a persistent Windows 11 Pro desktop on Proxmox (`docs/test-phase2-windows.md`).

### Fixed
- Broker exhausted PostgreSQL connections ("too many clients", HTTP 500 in the admin UI)
  under load: persistent DB connections (`CONN_MAX_AGE=60`) leak under ASGI because every
  worker thread keeps its own connection. Now `0` (one connection per request, upstream
  default); PostgreSQL `max_connections` raised to 200. Found in the first lab test.
- Load test (`tests/load.sh`) added to CI to catch connection leaks.

### Added
- Phase 0: evaluation of existing open-source VDI projects and decision document
  (`docs/00-entscheidung.md`): LibreVDI is a distribution based on OpenUDS 5.0.
- OpenUDS 5.0 components (broker, actor, client, tunnel server) as pinned git submodules.
- Broker container image (Ubuntu 24.04) with LibreVDI settings overlay: configuration via
  `LIBREVDI_*` environment variables, PostgreSQL, keys generated on first start and kept on
  the data volume, logs to stdout (text or JSON), `/healthz` and `/readyz` endpoints.
- `compose.yaml`: PostgreSQL, memcached, broker (init/web/tasks), Caddy reverse proxy with TLS.
- First-start defaults: LibreVDI branding, reverse proxy awareness (trusted forwarders),
  login IP blocking.
- Smoke test (`tests/smoke.sh`), unit tests for the LibreVDI extensions, GitHub Actions CI.
- ADRs 0001–0005, installation guide, upstream notes, third-party license overview.
