# ADR-0001: LibreVDI als Distribution auf Basis von OpenUDS 5.0

- **Status:** angenommen (22.11.2026)
- **Kontext:** Phase 0 (`docs/00-entscheidung.md`) hat bestehende Open-Source-VDI-Projekte
  verglichen. OpenUDS deckt den größten Teil des Auftrags ab (Proxmox Linked Clones, Warm-Pool,
  persistente Desktops, Agent für Windows/Linux, LDAP/SAML/MFA) und steht unter BSD-3. Ein
  vollständiger Neubau wäre als Ein-Personen-Projekt sehr aufwendig, ein harter Fork würde
  vom schnell entwickelten Upstream abdriften.

## Entscheidung

- LibreVDI ist eine **Distribution** („Option A2“): Der OpenUDS-Code wird **unverändert** als
  Git-Submodul (`upstream/`) eingebunden und auf einen geprüften Commit gepinnt.
- Basis ist der Zweig **v5.0** (Rust-Agent und -Client), nicht das stabile v4.0.
- LibreVDI ergänzt: Container-Betrieb, Konfiguration, Proxmox-Einrichtung, Templates, Doku
  (DE/EN) und Erweiterungen als **Plugins** (`uds/plugins/` wird von OpenUDS automatisch geladen).
- Änderungen am Kern gehen als Pull Request an Upstream („upstream first“); bis zur Übernahme
  ggf. als Patch-Datei in diesem Repo.
- Eigene Komponenten können später schrittweise Upstream-Teile ersetzen (Annäherung an
  „Option C“), ohne das Gesamtsystem neu zu bauen.

## Konsequenzen

- + Schnell nutzbar, Kernwartung liegt beim Hersteller.
- − Abhängigkeit von Virtual Cable (Open-Core-Modell). Bereits veröffentlichter BSD-Code bleibt
  nutzbar; ein Fork ist jederzeit möglich.
- − v5.0 ist Entwicklungsstand ohne Release-Tags: Upstream-Updates werden bewusst und mit
  Smoke-Test übernommen (Submodul-Commit erhöhen).
- Keine Marken Dritter in der Oberfläche: Name/Copyright werden beim ersten Start auf LibreVDI
  gesetzt; Logo und weitere Grafiken folgen (Phase 2).
