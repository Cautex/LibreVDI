# ADR-0002: Projektlizenz BSD-3-Clause

- **Status:** angenommen (22.11.2026)
- **Kontext:** Die Lizenz sollte zur Basis passen (Auftrag Abschnitt 2). OpenUDS steht unter
  BSD-3-Clause.

## Entscheidung

LibreVDI-eigener Code steht unter **BSD-3-Clause** (`LICENSE`). Abhängigkeiten werden in
`THIRD_PARTY.md` und `docs/licenses/` dokumentiert. Pakete mit starkem Copyleft (GPL) werden
nur aufgenommen, wenn sie unverzichtbar sind; `mysqlclient` (GPL-2.0) wird deshalb nicht
installiert (siehe ADR-0003).

## Konsequenzen

- Gleiche Lizenz wie Upstream: Beiträge können ohne Lizenzfragen in beide Richtungen fließen.
- Copyright-Vermerke von Virtual Cable bleiben erhalten; mit deren Namen wird nicht geworben.
