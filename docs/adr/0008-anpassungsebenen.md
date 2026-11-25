# ADR-0008: Anpassungsebenen rund um den OpenUDS-Kern

- **Status:** angenommen (25.11.2026)
- **Kontext:** LibreVDI ist eine Distribution auf Basis von OpenUDS (ADR-0001). Die OpenUDS-Teile
  liegen als Git-Submodule unter `upstream/` und sind auf feste Commits gepinnt; neue
  OpenUDS-Stände kommen nur durch bewusstes Anheben des Pins. Damit Updates beherrschbar bleiben,
  braucht es Regeln, *wie* LibreVDI den Kern anpasst.

## Entscheidung

Anpassungen werden auf der **niedrigsten möglichen Ebene** gemacht:

| Ebene | Mittel | Update-Risiko | Regel |
|---|---|---|---|
| 1 Konfiguration | OpenUDS-Einstellwerte (`GlobalConfig`), gesetzt über die Oberfläche oder `librevdi_ext.bootstrap` | keins | immer zuerst prüfen |
| 2 Plugins | offizielle Erweiterungspunkte: eigene Service-Typen, Jobs, Django-Signale (`docker/broker/plugins/librevdi`) | gering | bevorzugt |
| 3 Laufzeit-Hooks | interne Methoden umhüllen/ersetzen (z. B. `UserServiceManager.release_from_logout`) | mittel | nur wenn 1–2 nicht reichen; Original aufbewahren und aufrufen; **jeder Hook bekommt Prüfungen im Selbsttest** |
| 4 Build-Ersetzungen | Texte, Bilder, Übersetzungen beim Image-/Windows-Build (`apply_branding.py`, `brand_upstream.py`) | mittel, laut | jede erwartete Stelle muss gefunden werden, sonst bricht der Build ab |
| 5 Kern-Dateien ändern | Patch/Fork von OpenUDS | hoch | **nicht** ohne neuen ADR |

**Selbsttest** (`uds.plugins.librevdi.selfcheck`, Aufruf `python -m librevdi_ext.selfcheck`):

- prüft den **Upstream-Vertrag** (Klassen, Methoden mit Parametern, Modellfelder, Einstellungen,
  auf die LibreVDI angewiesen ist) und ob **alle LibreVDI-Erweiterungen aktiv** sind;
- läuft bei jedem Start in `broker-init` (bricht standardmäßig ab, `LIBREVDI_SELFCHECK=warn`
  macht daraus eine Warnung) und im CI-Smoke-Test.

**OpenUDS-Updates:** Pin anheben → Image bauen → CI (Selbsttest, Smoke-, Tunnel-, Branding-
Prüfungen) → Lab-Test → Release. Rhythmus: regelmäßig (etwa monatlich) und bei Sicherheitsmeldungen.

**Upstream-Beiträge:** Allgemein nützliche Änderungen (z. B. Option „Zuweisung bei Abmeldung
behalten“, Autostart im Installer-Beispiel) werden als Pull Request an OpenUDS angeboten; jede
angenommene Änderung ersetzt einen Hook.

## Konsequenzen

- Ein OpenUDS-Update, das LibreVDI bricht, fällt beim Start bzw. in der CI auf statt im Betrieb.
- Neue Hooks kosten zusätzlich Prüfungen im Selbsttest – das ist gewollt.
- **Fork-Kriterien** (neuer ADR nötig): die Hook-Schicht wird groß und bricht häufig, tiefe
  Änderungen am Datenmodell oder an Kernabläufen sind nötig, oder OpenUDS entwickelt sich in eine
  andere Richtung bzw. wird kaum noch gepflegt. Zwischenstufe: eigene OpenUDS-Branch mit wenigen,
  dokumentierten Patches, die bei jedem Update neu aufgesetzt werden.
- Die neue Verwaltungsoberfläche (Phase 2e) nutzt die REST-API (offizielle Schnittstelle) statt
  weiterer Hooks in der Upstream-Oberfläche.
