# ADR-0005: Programmiersprachen

- **Status:** angenommen (22.11.2026)

## Entscheidung

| Bereich | Sprache | Grund |
|---|---|---|
| Broker-Erweiterungen, Plugins, Werkzeuge | Python | OpenUDS-Plugins müssen Python sein; eine Sprache weniger |
| Agent, Client, Tunnel | Rust (Upstream) | werden von Upstream übernommen |
| Betrieb | Shell, Dockerfile, Compose | |
| Eigene neue Komponenten (falls später nötig) | Entscheidung im jeweiligen ADR | z. B. Go oder Rust |

## Konsequenzen

- Python-Code wird mit `ruff` geprüft, Shell-Skripte mit `shellcheck` (CI).
