# ADR-0004: Mandantenfähigkeit – eine Instanz pro Mandant, später

- **Status:** angenommen (22.11.2026)
- **Kontext:** OpenUDS kennt keine Mandanten im Datenmodell. Ein Umbau des fremden Datenmodells
  würde einen dauerhaften Fork bedeuten. Mandantenfähigkeit hat aktuell keine hohe Priorität.

## Entscheidung

- V1 ist **eine Instanz** (ein Compose-Stack).
- Mandantenfähigkeit später über **Instanz-Isolierung**: pro Mandant ein eigener Stack (eigene
  DB, eigenes Netz, eigener Proxmox-Pool und API-Token). Anlage/Verwaltung soll dann per GUI/API
  erfolgen (Verwaltungsschicht über die REST-APIs der Instanzen), nicht manuell.
- Bis dahin wird nichts Mandanten-Spezifisches gebaut; Compose-Projektnamen und Variablen
  sind aber so gewählt, dass mehrere Stacks parallel laufen können (`docker compose -p`).

## Konsequenzen

- Starke Isolation, keine Änderung am Upstream-Datenmodell.
- Mehr Ressourcen pro Mandant (eigene DB/Prozesse); zentrale Auswertung braucht die
  Verwaltungsschicht.
