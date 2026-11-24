# Anleitung: Persistente Windows-Desktops mit fester Benutzerzuweisung

Ziel (entspricht bei Horizon einem **manuellen Desktop-Pool, dedicated, ohne automatische
Zuweisung**): Der Administrator bereitet eine Windows-VM vor, weist sie **einem bestimmten
Benutzer** zu, und nur dieser Benutzer bekommt genau diese VM – dauerhaft.

Begriffe im Vergleich zu Horizon: [horizon-vergleich.md](horizon-vergleich.md).

```
Anbieter (Proxmox)                       ≈ vCenter
 └─ Dienst „Proxmox Persistent Desktops“ ≈ Pool-Definition: welche VMs
     └─ Service-Pool                      ≈ Desktop-Pool: + Transport (RDP) + Berechtigung (Gruppe)
         └─ Zugewiesene Services          ≈ Machines: VM ↔ Benutzer
Authentifikator „Lokal“ (Benutzer, Gruppen) ≈ AD-Benutzer/-Gruppen
Transport „RDP direkt“                      ≈ Protokoll
```

**Zeitbedarf:** ca. 1,5 h inkl. Windows-Installation.
Menünamen sind so angegeben, wie die deutsche Oberfläche sie zeigt.

---

## Teil 0 – Ausgangslage herstellen

1. **LibreVDI aktualisieren** (Docker-Host):
   ```bash
   cd /opt/LibreVDI
   git pull --recurse-submodules
   docker compose build
   docker compose up -d
   GITHUB_TOKEN=<token> tools/fetch-windows-builds.sh   # neueste Windows-Installer
   docker compose restart broker-web
   ```
2. **Alte Testobjekte entfernen** (Verwaltung, `https://<domain>/uds/adm/`), in dieser Reihenfolge:
   1. **Pools → Service-Pools**: alte Pools markieren → **Löschen**
      (zuvor ggf. unter *Zugewiesene Services* die Einträge löschen)
   2. **Services → Anbieter** → deinen Proxmox-Anbieter öffnen → Reiter **Services**:
      alte Dienste löschen
   3. **Konnektivität → Transporte**: alte Transporte löschen (oder wiederverwenden)
   Den **Anbieter** und den **Authentifikator „Lokal“** kannst du behalten, wenn sie
   funktionieren – Teil 2 und 3 beschreiben trotzdem das Neuanlegen.

## Teil 1 – Windows-VM neu aufsetzen

Ausführlich mit Screenshots-Hinweisen: [test-phase2-windows.md](test-phase2-windows.md) Teil 1–3.
Kurzfassung:

1. **VM in Proxmox anlegen** – Name z. B. `vdi-win11-01`, in den Proxmox-**Ressourcenpool**
   `librevdi` (Rechenzentrum → Berechtigungen → Pools, Pool anlegen, VM zuordnen):
   - OS: Windows 11, Maschine **q35**, BIOS **OVMF (UEFI)** mit EFI-Disk und **TPM 2.0**
   - **QEMU Guest Agent: an**
   - Disk: VirtIO SCSI, ≥ 64 GB, Discard an; CPU 4 Kerne (Typ `host`), RAM 8 GB
   - Netzwerk: VirtIO, im VDI-VLAN
   - zweites CD-Laufwerk: VirtIO-Treiber-ISO
2. **Windows 11 Pro installieren** – lokales Konto (z. B. `vdiadmin`), keine Microsoft-Anmeldung
   (bei der Kontoabfrage: *Anmeldeoptionen → Offlinekonto* bzw. `start ms-cxh:localonly`).
3. In Windows (als Administrator):
   - **VirtIO Guest Tools** von der Treiber-CD installieren (`virtio-win-guest-tools.exe`,
   enthält den QEMU Guest Agent) → in Proxmox unter *Übersicht* erscheint die **IP**
   - **Remotedesktop aktivieren**: Einstellungen → System → Remotedesktop → Ein
   - Netzwerkprofil **Privat**; Firewall-Regeln für RDP sind damit aktiv
   - Windows-Updates einspielen, neu starten
4. **Benutzer für den Desktop anlegen** (der Mensch, dem die VM gehören soll), z. B. `max`:
   ```powershell
   net user max <Passwort> /add
   net localgroup "Remotedesktopbenutzer" max /add
   ```
   (Später mit AD entfällt das – dann meldet sich der Domänenbenutzer an.)
5. **Snapshot** in Proxmox: VM → Snapshots → *Snapshot erstellen*, Name `01-windows-basis`
   (ohne RAM). Ab hier kann jederzeit neu begonnen werden.

## Teil 2 – Anbieter (Proxmox) anlegen

**Services → Anbieter → Neu → Proxmox**

| Feld | Wert |
|---|---|
| Name | `Proxmox Lab` |
| Host | IP oder Name eines Proxmox-Knotens |
| Port | `8006` |
| Use API Token | **an** |
| Username | Token-ID, z. B. `librevdi@pve!broker` |
| Password | Token-Secret |
| Starting VmId | z. B. `20000` (nur für spätere Klone relevant) |

Rechte des Tokens: Rolle aus [test-phase1.md](test-phase1.md) (u. a. `VM.PowerMgmt`,
`VM.GuestAgent.Audit`), auf `/` vergeben, **Privilege Separation** wie dort beschrieben.
→ **Testen** → erfolgreich → **Speichern**.

## Teil 3 – Benutzer und Gruppe (Authentifikator)

**Authentifikatoren → Neu → Interne Datenbank** (falls „Lokal“ noch nicht existiert):
Name `Lokal`, Etikett `lokal`.

Den Authentifikator öffnen:
1. Reiter **Gruppen → Neu**: `VDI-Benutzer`
2. Reiter **Benutzer → Neu**: Benutzername `max`, Passwort setzen, Status *aktiviert*,
   Gruppe `VDI-Benutzer`

Das ist die **Anmeldung am LibreVDI-Portal**. Die Anmeldung *in Windows* ist davon getrennt
(lokales Windows-Konto aus Teil 1, Schritt 4).

## Teil 4 – Dienst „Proxmox Persistent Desktops“

**Services → Anbieter → `Proxmox Lab`** öffnen → Reiter **Services → Neu →
„Proxmox Persistent Desktops (LibreVDI)“**

| Reiter | Feld | Wert |
|---|---|---|
| Main | Name | `Persistent Win11` |
| Main | Service-Token | Zufallswert, z. B. Ausgabe von `openssl rand -hex 24` – **notieren** |
| Maschine | Resource Pool | `librevdi` – der **Proxmox-Ressourcenpool** aus Teil 1 (Rechenzentrum → Berechtigungen → Pools); er begrenzt, welche VMs zur Auswahl stehen |
| Maschine | Machines | `vdi-win11-01` – darf auch leer bleiben und später ergänzt werden (Dienst bearbeiten) |
| Erweitert | Use snapshots | **aus** – an würde die VM nach jeder Nutzung auf einen Snapshot zurücksetzen (nicht persistent) |
| Erweitert | **Automatic assignment** | **aus** (nur vom Admin zugewiesene VMs) |
| Erweitert | After logoff | `Do nothing` (für den ersten Test) |

„Keep on error“ gibt es bei diesem Dienst-Typ nicht: Fehler an einer VM heben die Zuweisung nie
auf (beim Upstream-Typ „Fixed Machines“ würde die VM sonst freigegeben).

→ **Speichern**.

Der **Service-Token** verbindet den Agent in der VM mit *diesem* Dienst. Kommt die VM später in
einen anderen Dienst, muss der Agent den neuen Token bekommen.

## Teil 5 – Transport (Protokoll)

**Konnektivität → Transporte → Neu → RDP** (direkte Verbindung)

| Feld | Wert |
|---|---|
| Name | `RDP direkt` |
| Empty creds | **an** (Windows fragt nach Benutzer/Passwort) |
| Enable clipboard | an |
| Multiple monitors | nach Wunsch |
| Sign RDP file | optional, siehe [rdp-signing.md](rdp-signing.md) |

→ **Speichern**. (Tunnel für den Zugriff von außen: [tunnel.md](tunnel.md), später.)

## Teil 6 – Service-Pool (Desktop-Pool)

**Pools → Service-Pools → Neu**

| Feld | Wert |
|---|---|
| Name | `Windows 11 persistent` (so sieht der Benutzer die Kachel) |
| Service | `Proxmox Lab` → `Persistent Win11` |
| OS Manager | **keiner** |
| Sichtbar | an |

→ **Speichern**, dann den Pool öffnen:
1. Reiter **Gruppen → Neu**: Authentifikator `Lokal`, Gruppe `VDI-Benutzer`
2. Reiter **Transporte → Neu**: `RDP direkt`

## Teil 7 – Agent in der VM

1. In der VM: Edge → `https://<domain>/` → als `root` anmelden → Benutzermenü → **Downloads** →
   **LibreVDI Agent for Unmanaged windows machines**
   (`LibreVDI-Agent-unmanaged-Setup-<version>.exe`) → als Administrator installieren.
2. Startmenü → **LibreVDI → LibreVDI Agent konfigurieren**:
   - SSL Validation: *Verify certificate*
   - LibreVDI Broker: `<domain>`
   - Service Token: der Token aus Teil 4
   - **Test** → erfolgreich → **Save Configuration**
3. Prüfen (PowerShell als Administrator – **`sc.exe`**, nicht `sc`):
   ```powershell
   sc.exe query LibreVDIAgent      # STATE: 4 RUNNING
   ```
4. Aus Windows **abmelden**.
5. **Snapshot** `02-agent-bereit`.

## Teil 8 – VM dem Benutzer zuweisen

**Pools → Service-Pools → `Windows 11 persistent`** → Reiter **Zugewiesene Services** →
**Service zuweisen**:
- Authentifikator `Lokal`, Benutzer `max`
- Maschine `vdi-win11-01`
→ **OK**.

Der Eintrag erscheint mit Inhaber `max@Lokal`; LibreVDI prüft die VM (startet sie bei Bedarf)
und setzt den Status auf **Gültig**.

## Teil 9 – Client und Verbindung

1. Auf dem eigenen PC `https://<domain>/` öffnen → oben **LibreVDI Client** →
   `LibreVDI-Client-Setup-<version>.exe` installieren.
2. Im Portal als **`max`** (Authentifikator `Lokal`) anmelden → Kachel
   **Windows 11 persistent** → Verbinden.
3. Browser fragt „LibreVDI Client öffnen?“ → **Öffnen** (ggf. „immer erlauben“).
4. RDP startet → Windows-Anmeldung als `max` (lokales Windows-Konto).

## Teil 10 – Prüfen

| # | Test | Erwartung |
|---|---|---|
| 1 | Verbunden: *Zugewiesene Services* ansehen | Inhaber `max@Lokal`, **In Benutzung: Ja**, **Actor-Version** gefüllt, Src Host = dein PC |
| 2 | In Windows **abmelden**, 15 min warten | Eintrag bleibt, Status **Gültig**, In Benutzung **Nein** |
| 3 | Erneut als `max` verbinden | dieselbe VM `vdi-win11-01` |
| 4 | Zweiten Portal-Benutzer `erika` (Gruppe `VDI-Benutzer`) anlegen, als `erika` verbinden | Meldung, dass kein Dienst verfügbar ist – es wird **keine** VM vergeben |
| 5 | Energie-Richtlinie: im Dienst *After logoff* = `Shut down machine after delay`, 5 min; abmelden | nach ca. 5–7 min ist die VM in Proxmox aus |
| 6 | Bei ausgeschalteter VM als `max` verbinden | VM startet von selbst, nach 1–2 min verbunden |
| 7 | Wartung: **Services → Anbieter → Proxmox Lab → Instandhaltung** an | Energie-Richtlinie pausiert, Portal-Verbindungen gesperrt; danach wieder aus |

Ergebnis bitte als Tabelle (OK / Fehler + Screenshot) zurückmelden.

## Fehlerbilder

| Symptom | Ursache / Lösung |
|---|---|
| Verbindung bleibt bei **50 %** | VM meldet keine IP: QEMU Guest Agent in der VM installiert? In Proxmox „QEMU Guest Agent“ an? Recht `VM.GuestAgent.Audit` (PVE 9)? |
| Verbindung bleibt bei **75 %** | Broker erreicht Port 3389 der VM nicht: Remotedesktop an? Netzwerkprofil Privat? Firewall zwischen Docker-Host und VDI-VLAN (TCP 3389, 43910)? |
| **In Benutzung bleibt „Nein“**, Actor-Version „unbekannt“ | Agent meldet sich nicht für diese Zuweisung: Dienst `LibreVDIAgent` läuft? Token im Agent = Token des Dienstes aus Teil 4? Broker-Log: `docker compose logs --since 15m broker-web \| grep actor/v3` |
| Portal-Kachel fehlt | Benutzer nicht in der Gruppe des Pools, oder Pool ohne Transport |
| „Kein Dienst verfügbar“ für den zugewiesenen Benutzer | Zuweisung in Teil 8 fehlt oder steht auf Fehler; VM im richtigen Dienst? |
| Klick auf „Verbinden“ öffnet nichts | Client nicht installiert oder Browser blockiert `udssv2://` (Symbol in der Adressleiste) |
| Client-Update „Fehler beim Überschreiben“ | Client läuft noch – neuer Installer beendet ihn bzw. benennt Dateien um; sonst alle LibreVDI-Fenster schließen |
