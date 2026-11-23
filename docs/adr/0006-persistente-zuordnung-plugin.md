# ADR-0006: Persistente Zuordnung über ein LibreVDI-Plugin

- **Status:** angenommen (22.11.2026)
- **Kontext:** Im Lab-Test zeigte sich: Der OpenUDS-Service „Proxmox Fixed Machines“ gibt die
  Zuordnung Benutzer ↔ VM bei jeder Abmeldung im Gast frei (`Service.is_removable_on_logout()`
  ist `True`, Pools mit festen Maschinen haben keinen OS-Manager, der das übersteuern könnte).
  Der Projektauftrag verlangt persistente Desktops mit fester VM pro Benutzer.

## Entscheidung

LibreVDI liefert einen eigenen Service-Typ **„Proxmox Persistent Desktops (LibreVDI)“**
(`LibreVDIProxmoxPersistentService`) als Broker-Plugin unter `uds/plugins/librevdi/`
(Quelle: `docker/broker/plugins/librevdi/`). Er erbt vollständig von `ProxmoxServiceFixed`
(gleiche Felder, gleicher Treiber) und überschreibt nur `is_removable_on_logout()` → `False`.
Das Plugin trägt den Typ zur Laufzeit in `ProxmoxProvider.offers` ein; Upstream-Dateien bleiben
unverändert.

## Konsequenzen

- Zuordnungen enden nur durch einen Administrator (Assigned services → Delete) – wie
  „dedicated assignment“ bei kommerziellen VDI-Lösungen.
- Der Typ-Name ist in der Datenbank gespeichert: Das Plugin muss in künftigen Images bleiben.
- Kandidat für einen Upstream-PR (Option „Zuordnung bei Abmeldung behalten“ im Fixed-Service);
  wird er übernommen, kann der Typ auf den Upstream-Mechanismus migriert werden.

## Nachtrag (23.11.2026, Lab-Test)

Die Zuordnung ging trotzdem nach ca. 10 Minuten auf „Entfernt“. Ursache: ein zweiter Upstream-Weg,
der Job „Unused services checker“. Er gibt bei Pools **ohne OS-Manager** zugewiesene, nicht benutzte
Maschinen nach `checkUnusedTime` (631 s) frei – unabhängig vom Service-Typ. Ergänzt:

- Pools mit diesem Service-Typ bekommen immer „Ignore unused“ (beim Speichern per Signal,
  bestehende Pools einmalig beim Start durch `librevdi_ext.bootstrap`).
- `UserServiceManager.release_from_logout` gibt Zuordnungen dieses Typs nicht frei
  (Sicherheitsnetz für beide Wege).
