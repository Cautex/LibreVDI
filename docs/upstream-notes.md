# Hinweise zu Upstream (OpenUDS)

Beobachtungen beim Paketieren von OpenUDS 5.0 (Broker-Commit `4e4347bcf`, 22.11.2026).
Kandidaten für Issues oder Pull Requests bei Upstream.

## 1. Zirkulärer Import hängt von der Logging-Konfiguration ab

`uds.core.consts` → `consts.os` → `uds.core.types` → `types.tickets` → `uds.core.util.model`
nutzt beim Klassenaufbau `consts.NEVER`, bevor `uds.core.consts` fertig geladen ist.
Das funktioniert nur, weil Djangos Logging-Setup über die Upstream-Datei-Handler zuerst
`uds.core.util.log` importiert. Mit einer anderen Logging-Konfiguration (z. B. nur stdout)
bricht `django.setup()` mit `AttributeError: partially initialized module 'uds.core.consts'`.

- **Workaround in LibreVDI:** `librevdi_ext/console.py` importiert `uds.core.util.log`.
- **Vorschlag Upstream:** in `TimeTrack` die Klassenattribute ohne `consts.NEVER`
  initialisieren (z. B. lokaler Default) oder den Import in `types/tickets.py` verzögern.

## 2. Unveränderliches Audit-Log blockiert Logins ohne Internet

Mit `Security.Enable immutable log = 1` wird jeder Eintrag bei einem externen
RFC-3161-Zeitstempeldienst gestempelt. Ist dieser nicht erreichbar (Lab ohne Internet,
DNS-Fehler), endet **jeder Login** mit einem internen Serverfehler (Fehlerseite 17).

- **LibreVDI:** schaltet das Audit-Log nicht automatisch ein; Doku weist darauf hin.
- **Vorschlag Upstream:** bei nicht erreichbarem Zeitstempeldienst den Eintrag ohne Stempel
  schreiben und später nachstempeln, statt den Login abzubrechen.

## 3. Kleinere Punkte

- Der Quickstart (`doc/source/quickstart`) beschreibt noch den Python-Tunnel und MySQL;
  in 5.0 ist der Tunnel in Rust.
- `settings.py.sample` enthält einen alten Beispiel-RSA-Schlüssel, den aktuelle
  `cryptography`-Versionen ablehnen (`Invalid private key`).
