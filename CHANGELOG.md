# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/de/1.1.0/). Versions follow
[Semantic Versioning](https://semver.org/lang/de/) once the first release is tagged.

## [Unreleased]

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
