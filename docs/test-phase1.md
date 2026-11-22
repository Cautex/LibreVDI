# Testanleitung Stand Phase 1

## Was testbar ist und was noch nicht

| Bereich | Stand | Testbar? |
|---|---|---|
| Broker-Stack (Docker, Postgres, TLS) | fertig | ✅ |
| Admin-Oberfläche, Benutzerportal, REST-API | fertig (openUDS) | ✅ |
| Anmeldung: interne Benutzer, LDAP/AD | in openUDS vorhanden | ✅ |
| Proxmox-Anbindung (Provider, Klonen, Publikation, Warm-Pool) | in openUDS vorhanden, von uns noch nicht gegen echtes Proxmox geprüft | ✅ (Ziel dieses Tests) |
| Agent in der VM (Windows/Linux) | Quellcode da, **noch keine Pakete** – Upstream veröffentlicht für 5.0 keine Binärdateien | ❌ Phase 2 |
| Client/Launcher (Windows) | Quellcode da, **noch kein Build** | ❌ Phase 2 |
| Desktop wirklich öffnen (RDP) | braucht Agent + Launcher | ❌ Phase 2 |
| Tunnel, Web-Client (HTML5) | noch nicht eingebunden | ❌ Phase 2+ |

Ohne Agent melden geklonte VMs nie „bereit“. Der Test prüft deshalb die Proxmox-Seite
(Verbindung, Rechte, Template-Erstellung, Klonen, Starten, Löschen), nicht die Benutzersitzung.

## Teil A – Stack im Lab starten

Auf einem Docker-Host im Lab (nicht aus dem Internet erreichbar):

```bash
git clone --recurse-submodules -b claude/happy-allen-xenekt https://github.com/Cautex/LibreVDI.git
cd LibreVDI
cp .env.example .env && chmod 600 .env
nano .env        # LIBREVDI_DOMAIN, POSTGRES_PASSWORD, LIBREVDI_ROOT_PASSWORD setzen
docker compose build          # ca. 5–10 Minuten
docker compose up -d
docker compose ps             # broker-web, broker-tasks, postgres: "healthy"
tests/smoke.sh                # erwartet: "== smoke test passed" (braucht curl und python3)
```

DNS: `LIBREVDI_DOMAIN` muss auf den Docker-Host zeigen (lokaler DNS oder `hosts`-Datei auf dem
Test-PC). Mit `LIBREVDI_TLS=internal` erscheint eine Zertifikatswarnung (siehe
[installation.md](installation.md), Abschnitt 4).

**Prüfen:**
- [ ] `https://<LIBREVDI_DOMAIN>/` zeigt die Login-Seite „LibreVDI“
- [ ] Login mit `root` + Passwort aus `.env` → Benutzerportal; Admin unter `/uds/adm/`
- [ ] Dashboard zeigt keine kritischen Sicherheitswarnungen (2 mittlere sind erwartet:
      Root-Zugang und „Trusted Sources“, siehe installation.md Abschnitt 5)

## Teil B – Proxmox vorbereiten (eigener Benutzer + API-Token)

Auf einem Proxmox-Knoten in der Shell. Die Rechte sind aus den API-Aufrufen des
openUDS-Proxmox-Treibers abgeleitet und **noch nicht in der Praxis geprüft** – genau das ist
Teil des Tests.

```bash
# Rolle mit den Rechten, die der Treiber nutzt
# Proxmox VE 9: VM.GuestAgent.Audit (IP-Adresse der VM über den QEMU Guest Agent lesen)
# Proxmox VE 8: statt VM.GuestAgent.Audit das Recht VM.Monitor verwenden
pveum role add LibreVDI -privs "VM.Audit VM.Allocate VM.Clone VM.Config.CPU VM.Config.Memory VM.Config.Network VM.Config.Options VM.Config.Disk VM.Config.HWType VM.PowerMgmt VM.Snapshot VM.Snapshot.Rollback VM.Console VM.GuestAgent.Audit Datastore.Audit Datastore.AllocateSpace Pool.Audit Sys.Audit SDN.Use"

# Benutzer, Pool und Token
pveum user add librevdi@pve --comment "LibreVDI broker"
pveum pool add librevdi --comment "LibreVDI desktops"
pveum acl modify / -user librevdi@pve -role LibreVDI     # für den Test: Rechte auf alles
pveum user token add librevdi@pve broker --privsep 0      # zeigt das Token-Secret EINMAL an
```

Das Secret sicher notieren (nicht in Chat, Git oder Tickets).

Für den Test reicht eine **kleine Linux-VM** als Basis-Maschine (z. B. Debian mit 1 vCPU,
1 GB RAM, ausgeschaltet). Ein Windows-Template ist erst mit dem Agent sinnvoll. Storage mit
Linked-Clone-Unterstützung (LVM-thin, ZFS, Ceph RBD oder qcow2 auf Directory/NFS) verwenden.

## Teil C – Proxmox im Broker einrichten

In der Admin-Oberfläche (`/uds/adm/`):

1. **Services → Service Providers → Neu → Proxmox**
   - Host: IP/Name eines Proxmox-Knotens, Port `8006`
   - *Use API Token*: an
   - Username: `librevdi@pve!broker`
   - Password: das Token-Secret
   - Speichern, dann **Test** ausführen
   - [ ] Test erfolgreich
2. Im Provider: **Services → Neu → Proxmox Clone** („Linked Clone“)
   - **HA: Disabled** – wichtig: Voreinstellung ist „Enabled“, das Feld ist später nicht mehr
     änderbar, und HA braucht das weitreichende Recht `Sys.Console` auf `/`
   - Pool: `librevdi`, Base Machine: die Test-VM, *Use full clone*: aus
   - **Storage:** ein VM-Storage mit Linked-Clone-Unterstützung – **nicht** den
     Proxmox-Backup-Server-Storage (wird mit angeboten und steht oft oben)
   - Network: eure Bridge
3. **Os Managers → Neu → Linux OS Manager** (Standardwerte)
4. **Pools → Service Pools → Neu**
   - Service: der Proxmox-Clone-Service, OS Manager: der eben angelegte
   - Cache: **Initial 1, Cache L1 1, Max 1** (damit nicht viele VMs entstehen)
5. Im Service Pool: **Publications → Neu** (erzeugt das Master-Template)

**In Proxmox beobachten:**
- [ ] Die Publikation erstellt aus der Basis-VM ein Template (VMID ab 10000) im Pool `librevdi`
- [ ] Danach entsteht ein **Linked Clone** und wird gestartet (Warm-Pool / Cache L1)
- [ ] Erwartet: Der Klon bleibt im Broker im Zustand „vorbereiten“, weil kein Agent meldet.
      Nach dem Timeout wird er als Fehler markiert und wieder **gelöscht** – auch das prüft
      den Treiber (Stop/Destroy).

**Aufräumen:** Service Pool löschen (Broker entfernt Klone und Template), danach in Proxmox
kontrollieren, dass nichts übrig bleibt.

## Bekannte Stolpersteine (aus dem ersten Lab-Test)

| Meldung | Ursache | Lösung |
|---|---|---|
| `storage '…' does not support vm images` | PBS-Storage im Service gewählt | Service mit VM-Storage neu anlegen |
| `Permission check failed (/, Sys.Console)` | HA im Service aktiviert (Standard) | Service mit **HA: Disabled** neu anlegen |
| `Item has associated deployed services` beim Löschen | Service hängt noch an einem Service Pool | zuerst den Pool löschen |
| `Permission check failed (/vms/…, VM.GuestAgent.Audit…)`, Verbindung hängt bei 50 % | Rolle ohne Guest-Agent-Recht (PVE 9) | `pveum role modify LibreVDI --append 1 --privs VM.GuestAgent.Audit` (PVE 8: `VM.Monitor`) |
| Proxmox zeigt bei der VM „No Guest Agent configured“, Verbindung hängt bei 50 % | QEMU Guest Agent in den VM-Optionen aus oder nicht installiert | *Options → QEMU Guest Agent* an, VM **Shutdown → Start**, Dienst „QEMU Guest Agent“ in Windows prüfen |
| `Item changed by another administrator` beim Speichern | noch ungeklärt (siehe upstream-notes.md) | Seite neu laden; sonst Service neu anlegen |

## Was ich als Rückmeldung brauche

- Haken bzw. Fehler pro Punkt oben
- bei Fehlern die passenden Logs, **ohne Secrets**:
  ```bash
  docker compose logs --no-color broker-tasks broker-web | grep -iE "proxmox|error|denied|403" | tail -100
  ```
- Proxmox-Version (`pveversion`) und Storage-Typ der Basis-VM
- fehlende Rechte erkennt man an `403 Forbidden ... Permission check failed (... , <Recht>)`
  in den Logs oder im Proxmox-Task-Log

## Aufräumen nach dem Test

```bash
docker compose down -v        # löscht Container UND Daten (Datenbank, Schlüssel)
```

In Proxmox bei Bedarf: `pveum user token remove librevdi@pve broker`,
`pveum user delete librevdi@pve`, `pveum role delete LibreVDI`, `pveum pool delete librevdi`.
