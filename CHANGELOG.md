# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/de/1.1.0/). Versions follow
[Semantic Versioning](https://semver.org/lang/de/) once the first release is tagged.

## [Unreleased]

### Added (Phase 2b)
- Service type **"Proxmox Persistent Desktops (LibreVDI)"** (broker plugin): fixed user ↔ VM
  assignment that survives logoff (upstream "Fixed Machines" releases it), ADR-0006.
- **LibreVDI branding** everywhere: own logo, portal and admin texts, German UI (upstream ships no
  compiled translations), client and agent windows, Windows file properties, installers. Upstream
  copyright notices stay visible (BSD-3-Clause).
- **Tunnel** as optional compose profile (`--profile tunnel`), automatic registration; per pool via
  transports "RDP direct" / "RDP tunneled", optionally per network (`docs/tunnel.md`).
- **Signed RDP files**: signing certificate generated on first start or own certificate
  (`LIBREVDI_RDP_SIGN_CERT/KEY`), public certificate and SHA-1 thumbprint for GPO
  (`docs/rdp-signing.md`).
- **Releases** (`.github/workflows/release.yml`, ADR-0007): tag `v<semver>` builds the Windows
  installers and the broker/tunnel images, tests and pushes them to GHCR and creates a *draft*
  GitHub release with SHA256SUMS. Release images contain the matching Windows installers.
- Third-party license notices (`THIRD-PARTY-NOTICES.txt`) generated during the build and shipped
  in both installers; Windows file version set from the release version.
- Windows: agent service renamed to `LibreVDIAgent` (an older `UDSActorService` is removed on
  install), LibreVDI logo in "Installed apps" and the start menu, portal offers the client as
  `LibreVDI-Client-Setup-<version>.exe` instead of the upstream file name.
- Corresponding source of the LGPL libraries in the client (FFmpeg, libusb: upstream archives,
  vcpkg port files and patches) collected during the build and attached to every release.

### Added (Phase 2)
- Windows builds in GitHub Actions: LibreVDI Agent (OpenUDS actor, `unmanaged` and `managed`
  installers) and LibreVDI Client (OpenUDS launcher with FreeRDP, FFmpeg, OpenSSL runtime DLLs,
  installer registering `udssv2://`). Native client dependencies are cached.
- Guide for a persistent Windows 11 Pro desktop on Proxmox (`docs/test-phase2-windows.md`).
- Root CA download at `/ca.crt` (internal TLS) and operation behind an existing reverse proxy
  (`LIBREVDI_PROXY_CONFIG=Caddyfile.behind-proxy`, trusted client IPs).
- Windows installers offered by LibreVDI itself (portal "Launcher" for users, agent downloads for
  admins) from `downloads/`, fetched with `tools/fetch-windows-builds.sh`.

### Milestone
- **Phase 2 MVP reached in the lab (22.11.2026):** user logs in to the portal, selects the
  persistent Windows 11 Pro desktop, LibreVDI Client opens the RDP session (Proxmox VE 9.2).

### Added (Phase 2c)
- Power policy for "Proxmox Persistent Desktops (LibreVDI)": shut a machine down N minutes after
  its user logged off, or keep all machines powered on (job every two minutes). Stopped machines
  are started when their user connects (upstream behaviour).
- `docs/horizon-vergleich.md`: terms and pool types mapped to Horizon.
- Agent installer creates the start menu entry for all users (was only for the elevating admin
  account, so a normal user did not see "LibreVDI Agent konfigurieren").
- Pool group "Default" exists as a real, editable group (image, comment, priority); pools without
  a group are put into it on save, existing ones once on start (upstream: hidden virtual group).
- Default image of pools and pool groups is the LibreVDI logo (was the UDS logo).
- Agent configuration window shows the LibreVDI logo (crate-embedded image was still upstream).
- Power policy never shuts down machines whose agent has not reported for the assignment
  (actor version unknown), e.g. an agent still configured with another service's token.
- Agent installer: removes existing/older agent services first, retries creating the service
  (Windows deletes services delayed), starts it and shows the agent's output in the details.
- Downloads: the highest installer version wins (not the newest file date), admin downloads show
  the real file name incl. version, `fetch-windows-builds.sh` removes older installers.
- Installers move files that are still in use aside (renamed, deleted after reboot) instead of
  failing with "error overwriting launcher.exe"; CI compiles the installer scripts on Linux.
- Installers close a running client (with confirmation) or agent helpers before updating files;
  the power policy pauses while the provider is in maintenance mode.

### Added (Phase 2d)
- Persistent desktops: switch *Automatic assignment* (off = users only get the machine an
  administrator assigned via "Assign service", like dedicated pools without automatic assignment).
- Persistent service: machines optional (create the service first, add machines later); access
  errors never free a machine ("Keep on error" always on, field removed from the form).
- Step-by-step guide from an empty system to a connection with fixed user assignment
  (`docs/anleitung-persistente-desktops.md`); roadmap: UI/navigation (2e), desktop client app (2f).

### Fixed (from the Phase 2b lab test)
- Persistent desktops: assignments were still released after about 10 minutes by the upstream
  "Unused services checker" job (pools without OS manager). Pools of this service type now always
  ignore unused assignments, and the release path refuses to free them (ADR-0006 addendum).

### Fixed (from the Phase 2 lab test)
- Agent/client no longer need the Visual C++ runtime on fresh Windows (static CRT / app-local DLLs,
  CI checks DLL dependencies).
- Documented Proxmox privilege `VM.GuestAgent.Audit` (PVE 9), QEMU guest agent requirement and the
  firewall matrix (broker -> VM TCP 3389/43910).

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
