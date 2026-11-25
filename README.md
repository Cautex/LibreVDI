# LibreVDI

**Deutsch** · [English](#english)

Open-Source-VDI für **Proxmox VE**: persistente Desktops und Instant-Clone-/Floating-Pools,
Broker als Docker-Compose-Stack. LibreVDI ist eine Distribution auf Basis von
[OpenUDS](https://github.com/VirtualCable/openuds) 5.0 (BSD-3-Clause) und ergänzt
Container-Betrieb, Proxmox-Einrichtung, Templates und Dokumentation.

> **Status: Phase 1 (Entwicklungsstand).** Der Broker-Stack (Portal, Admin-Oberfläche,
> REST-API, Hintergrunddienste) läuft in Docker mit PostgreSQL. Proxmox-Pools, Agent-Pakete,
> Tunnel und Windows-Client folgen in Phase 2. Nicht für den Produktivbetrieb.

## Schnellstart

```bash
git clone --recurse-submodules https://github.com/Cautex/LibreVDI.git && cd LibreVDI
cp .env.example .env      # Platzhalter ersetzen
docker compose build && docker compose up -d
tests/smoke.sh            # optional: Funktionstest
```

Details: [docs/installation.md](docs/installation.md)

## Aufbau

```
compose.yaml            Stack: postgres, memcached, broker-init/-web/-tasks, Caddy
docker/broker/          Broker-Image: Dockerfile, Einstellungs-Overlay, Entrypoint, librevdi_ext
docker/proxy/           Caddyfile (TLS, Reverse Proxy)
upstream/               OpenUDS-Komponenten als Git-Submodule (unverändert)
tests/                  Smoke-Test (Stack) und Unit-Tests (LibreVDI-Erweiterungen)
docs/                   Entscheidung, ADRs, Installation, Upstream-Hinweise, Lizenzen
```

## Dokumentation

- [Entscheidung Phase 0](docs/00-entscheidung.md) – Vergleich bestehender Projekte
- [Architekturentscheidungen (ADR)](docs/adr/README.md)
- [Installation](docs/installation.md)
- [Hinweise zu Upstream](docs/upstream-notes.md)
- [Testanleitung Stand Phase 1](docs/test-phase1.md)
- [Anleitung: persistente Desktops mit fester Benutzerzuweisung](docs/anleitung-persistente-desktops.md)
- [Anleitung: persistenter Linux-Desktop (Ubuntu + xrdp) und Linux-Client](docs/anleitung-linux-desktop.md)
- [Testauftrag 26.11.2026: Linux-Client, Linux-Agent, Leerlauf-Abmeldung](docs/testauftrag-2026-11-26.md)
- [Phase 2: persistenter Windows-Desktop (Details zur Windows-VM)](docs/test-phase2-windows.md)
- [Tunnel (optional, pro Pool)](docs/tunnel.md)
- [Signierte RDP-Dateien](docs/rdp-signing.md)
- [Releases](docs/release.md)
- [LibreVDI für Horizon-Kenner](docs/horizon-vergleich.md)
- [Roadmap](docs/roadmap.md)
- [Software Dritter / Lizenzen](THIRD_PARTY.md)

## Lizenz

BSD-3-Clause, siehe [LICENSE](LICENSE). LibreVDI ist ein unabhängiges Projekt und steht in keiner
Verbindung zu Virtual Cable S.L.

---

## English

Open-source VDI for **Proxmox VE** with persistent desktops and instant-clone/floating pools; the
broker runs as a Docker Compose stack. LibreVDI is a distribution based on
[OpenUDS](https://github.com/VirtualCable/openuds) 5.0 (BSD-3-Clause), adding container
operation, Proxmox setup, templates and documentation.

> **Status: phase 1 (work in progress).** The broker stack (portal, admin UI, REST API,
> background services) runs in Docker with PostgreSQL. Proxmox pools, agent packages, tunnel and
> Windows client follow in phase 2. Not for production use.

Quick start: see the commands above and [docs/installation.md](docs/installation.md)
(German; an English translation will follow with the first release).

License: BSD-3-Clause. LibreVDI is an independent project, not affiliated with Virtual Cable S.L.
