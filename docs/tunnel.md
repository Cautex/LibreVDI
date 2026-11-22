# Tunnel (optional)

Ohne Tunnel verbindet sich der RDP-Client des Benutzers **direkt** mit der VM (TCP/UDP 3389).
Mit Tunnel geht die Sitzung **über LibreVDI**: Der Client spricht nur mit dem Tunnel auf dem
Docker-Host, der Tunnel mit der VM. Das ist sinnvoll, wenn

- Benutzer von außen (Homeoffice, Internet) arbeiten und die VMs nicht erreichbar sein sollen,
- zwischen Client-Netz und VDI-Netz keine RDP-Freigaben gewünscht sind.

Vergleichbar mit „Tunnel ja/nein“ bzw. einem Gateway bei kommerziellen VDI-Lösungen.
Die Entscheidung trifft der Administrator **pro Pool** (über die Transporte des Pools) und
optional **pro Netzwerk** (intern direkt, extern über Tunnel).

## 1. Tunnel aktivieren

`.env` auf dem Docker-Host:

```bash
# Adresse und Port, unter denen Clients den Tunnel erreichen (Standard: LIBREVDI_DOMAIN:4443)
LIBREVDI_TUNNEL_HOST=vdi.example.de
LIBREVDI_TUNNEL_PORT=4443
```

Starten (der Tunnel ist ein Compose-**Profil**, ohne `--profile tunnel` läuft er nicht):

```bash
docker compose --profile tunnel build
docker compose --profile tunnel up -d
docker compose logs tunnel-init      # "registered", "created", "assigned"
```

`tunnel-init` meldet den Tunnel automatisch beim Broker an und legt unter
**Konnektivität → Tunnel** die Gruppe „LibreVDI Tunnel“ mit Host/Port an. Ein erneuter Start
ändert nichts (idempotent).

## 2. Netzwerk

| Von | Nach | Port |
|---|---|---|
| Benutzer-PCs (intern/extern) | Docker-Host | **TCP und UDP 4443** (bzw. `LIBREVDI_TUNNEL_PORT`) |
| Docker-Host | VDI-VMs | TCP 3389 (wie ohne Tunnel) |

Der Tunnel spricht kein HTTP – ein HTTP-Reverse-Proxy (z. B. Proxy Host im Nginx Proxy Manager)
kann ihn **nicht** weiterleiten. Entweder den Port direkt freigeben/weiterleiten oder im
Nginx Proxy Manager einen **Stream** (TCP + UDP, Port 4443 → Docker-Host:4443) anlegen.

## 3. Pro Pool festlegen: direkt oder Tunnel

1. **Konnektivität → Transporte → Neu → (Gruppe „Getunnelt“/„Tunneled“) → RDP**
   - Name: `RDP über Tunnel`
   - Tunnel: `LibreVDI Tunnel`
   - übrige Einstellungen wie beim direkten RDP-Transport (z. B. *Empty creds*)
2. Im Service Pool unter **Transporte** den gewünschten Transport hinzufügen:
   - nur `RDP direkt` → immer direkt
   - nur `RDP über Tunnel` → immer über den Tunnel
   - beide → der Benutzer kann wählen; mit Netzwerkregeln automatisch (siehe 4.)

## 4. Optional: intern direkt, extern über Tunnel

1. **Konnektivität → Netzwerke → Neu**: z. B. `LAN` = `172.16.0.0/12` (eure internen Netze)
2. Transport `RDP direkt` → Reiter Netzwerke: **Erlauben** für `LAN`
3. Transport `RDP über Tunnel` → Reiter Netzwerke: **Verbieten** für `LAN`

Dann sehen interne Clients nur die direkte Verbindung, externe nur den Tunnel. Die Client-IP
kommt dabei aus dem Reverse Proxy – im Betrieb hinter Nginx Proxy Manager muss
`LIBREVDI_TRUSTED_PROXIES` gesetzt sein (siehe installation.md, Abschnitt 4a).
