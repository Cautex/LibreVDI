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

## 3. Proxmox-Service bietet ungeeignete Storages an

Die Storage-Auswahl im Service „Proxmox Clone“ (`services/Proxmox/helpers.py`, `get_storage`)
listet alle Storages des Knotens, ohne nach dem Inhaltstyp `images` zu filtern; geteilte
Storages stehen zuerst. Dadurch werden z. B. Proxmox-Backup-Server-Storages (Typ `pbs`)
angeboten und sogar vorausgewählt. Die Publikation scheitert dann mit
`storage '…' does not support vm images` (im Lab-Test am 22.11.2026 beobachtet).

- **Vorschlag Upstream:** `list_storages(node=…, content="images")` verwenden; zusätzlich in
  `StorageInfo.supports_linked_clone()` Typen ohne VM-Images (z. B. `pbs`) ausschließen.

## 4. Proxmox-Service: HA standardmäßig an und später nicht änderbar

Im Service „Proxmox Clone“ ist das Feld *HA* mit „Enabled“ (`""`) vorbelegt und `readonly`.
Mit HA ruft der Treiber `POST cluster/ha/resources` auf, was in Proxmox `Sys.Console` auf `/`
erfordert. Ein Token mit minimalen VM-Rechten scheitert dann bei der Publikation mit
`Permission check failed (/, Sys.Console)` (Lab-Test 22.11.2026); korrigieren lässt sich das nur
durch Löschen und Neuanlegen von Pool und Service.

- **Vorschlag Upstream:** „Disabled“ (`__`) als Vorgabe; Fehlermeldung mit Hinweis auf HA.

## 5. Speichern meldet „Item changed by another administrator“ (offen)

Im Lab-Test kam beim Bearbeiten eines Proxmox-Clone-Service (mit Pool und fehlgeschlagener
Publikation) HTTP 412 („changed by another administrator“), obwohl niemand sonst daran
gearbeitet hat. Mit einem einfachen Service („Static Single IP“) ließ sich das lokal **nicht**
nachstellen: GET-ETag und PUT mit `If-Match` funktionieren dort. Ursache noch unklar; die ETag
wird über die GUI-Felder des Elements gebildet (`REST/model/detail`, `inmutables()`).

## 6. Kleinere Punkte

- Interne Fehler beim Anlegen von Detail-Elementen (z. B. falscher Schlüssel `type` statt
  `data_type` im REST-Body) werden als `Invalid method put/post` gemeldet
  (`REST/model/master/__init__.py`, `process_detail` fängt `KeyError`/`AttributeError`).
- Der Quickstart (`doc/source/quickstart`) beschreibt noch den Python-Tunnel und MySQL;
  in 5.0 ist der Tunnel in Rust.
- `settings.py.sample` enthält einen alten Beispiel-RSA-Schlüssel, den aktuelle
  `cryptography`-Versionen ablehnen (`Invalid private key`).
