# Phase 2 – Persistenter Windows-11-Desktop per RDP

Ziel: Ein Benutzer meldet sich im LibreVDI-Portal an, klickt auf „Mein Windows-Desktop“ und
landet per RDP in **seiner festen** Windows-11-VM.

```
Benutzer-PC                    Docker-Host (LibreVDI)          Proxmox
┌──────────────┐  HTTPS 443   ┌────────────────────┐  API 8006  ┌───────────────────┐
│ Browser      │─────────────►│ Portal / Broker    │───────────►│ Windows-11-VM     │
│ LibreVDI-    │              └────────────────────┘◄───────────│  LibreVDI-Agent   │
│ Client →     │                 ▲  Agent meldet sich (443)    │  (unmanaged)      │
│ mstsc.exe ───┼─────────────────┼──── RDP 3389 direkt ───────►│                   │
└──────────────┘                 └── Broker → Agent (43910) ──►└───────────────────┘
```

**Netzwerk-Voraussetzungen**
- Benutzer-PC und VM lösen `LIBREVDI_DOMAIN` auf und erreichen den Docker-Host auf Port 443.
- Docker-Host erreicht die VM auf TCP **43910** (Agent).
- Benutzer-PC erreicht die VM auf TCP **3389** (RDP direkt, ohne Tunnel; Tunnel folgt später).

---

## Teil 1 – Windows-11-Pro-VM in Proxmox anlegen

Vorher in Proxmox das **virtio-win-ISO** bereitstellen: ISO-Speicher (z. B. `local`) →
*ISO Images* → *Download from URL* →
`https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.iso`

| Reiter | Einstellung |
|---|---|
| General | Name z. B. `win11-desktop01`; Resource Pool: **`librevdi-persistent`** (eigener Pool für feste Desktops, vorher unter *Datacenter → Permissions → Pools* anlegen) |
| OS | Windows-11-ISO; Type *Microsoft Windows*, Version *11/2022/2025*; **„Add additional drive for VirtIO drivers“** mit dem virtio-win-ISO |
| System | Machine **q35**, BIOS **OVMF (UEFI)**, EFI Storage + **TPM 2.0** (v2.0) auf dem VM-Storage, **Qemu Agent: an** |
| Disks | Bus **SCSI** (Controller *VirtIO SCSI single*), 64 GB+, **Discard** an, **IO thread** an, VM-Storage (nicht PBS) |
| CPU | Type **host**, 4 Cores |
| Memory | 8192 MB |
| Network | Model **VirtIO**, deine Bridge |

## Teil 2 – Windows installieren

1. VM starten, von der Windows-ISO booten, Edition **Windows 11 Pro** wählen.
2. Bei „Wo möchten Sie Windows installieren?“ → **Treiber laden** → virtio-win-Laufwerk →
   `vioscsi\w11\amd64` → Festplatte erscheint.
3. Einrichtung (OOBE): Für den Test ein **lokales Konto** anlegen. Microsoft ändert den Weg
   dafür häufig; bei Windows 11 Pro funktionieren je nach Build z. B. *„Für Arbeit oder Schule
   einrichten → Anmeldeoptionen → Stattdessen der Domäne beitreten“* oder die Einrichtung ohne
   Netzwerk. Später kann die VM auch einer AD-Domäne beitreten.
4. Nach dem ersten Login: **`virtio-win-guest-tools.exe`** vom virtio-win-Laufwerk (oder deinen
   heruntergeladenen) installieren → Netzwerk-, Balloon-Treiber und **QEMU Guest Agent**.
   In Proxmox unter *Summary* sollte jetzt bei **IPs** die IP-Adresse der VM erscheinen.
   Steht dort „No Guest Agent configured“: VM → *Options* → **QEMU Guest Agent** einschalten
   und die VM in Proxmox **Shutdown → Start** (ein Neustart aus Windows reicht nicht). In
   Windows muss der Dienst **„QEMU Guest Agent“** laufen. **Ohne IP kann der Broker keine
   RDP-Verbindung aufbauen** (Client hängt bei 50 %).
5. Windows-Updates installieren, neu starten.

## Teil 3 – Windows für VDI vorbereiten

Als Administrator in PowerShell:

```powershell
# Remotedesktop einschalten (mit Network Level Authentication) und Firewall freigeben
Set-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -Value 0
Set-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name UserAuthentication -Value 1
Enable-NetFirewallRule -Group '@FirewallAPI.dll,-28752'   # Regelgruppe "Remotedesktop" (sprachunabhängig)

# Kein Ruhezustand / Standby (sonst ist die VM für Broker und RDP nicht erreichbar)
powercfg /hibernate off
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
```

- **Testbenutzer:** einen lokalen Benutzer anlegen (z. B. `vdi-test`) und zur Gruppe
  **Remotedesktopbenutzer** hinzufügen (Administratoren dürfen ohnehin).
- **Zertifikat:** entfällt, wenn LibreVDI hinter einem Reverse Proxy mit gültigem Zertifikat
  läuft ([installation.md, Abschnitt 4a](installation.md)) – empfohlen.
  Nur bei `LIBREVDI_TLS=internal`: LibreVDI liefert seine Root-CA selbst aus.
  In der VM als Administrator (PowerShell oder Eingabeaufforderung):
  ```powershell
  curl.exe -k -o $env:TEMP\librevdi-ca.crt https://<LIBREVDI_DOMAIN>/ca.crt
  certutil -addstore -f Root $env:TEMP\librevdi-ca.crt
  ```
  `-k` ist hier nötig, weil der Rechner der CA ja noch nicht vertraut. Wer sichergehen will,
  vergleicht den Fingerabdruck (`certutil -dump $env:TEMP\librevdi-ca.crt`, Zeile
  „Zertifikathash(sha256)“) mit dem auf dem Docker-Host:
  `docker compose exec proxy cat /data/caddy/pki/authorities/local/root.crt | openssl x509 -noout -fingerprint -sha256`.
  Danach muss `https://<LIBREVDI_DOMAIN>/` im Edge der VM **ohne** Zertifikatswarnung öffnen.
  Mit einem öffentlich gültigen Zertifikat (Let's Encrypt, siehe installation.md) entfällt
  dieser Schritt ganz.

## Teil 4 – Persistenten Pool im Broker anlegen

In der Admin-Oberfläche (`/uds/adm/`):

1. **Services → Providers → pve → Services → New → „Proxmox Fixed Machines“**
   - Name: `Windows 11 persistent`
   - Resource Pool: `librevdi-persistent` – die Liste *Machines* zeigt nur VMs aus diesem
     Proxmox-Pool. Fehlt die VM: in Proxmox unter *Pools → librevdi-persistent → Members → Add*
     hinzufügen und den Dialog neu öffnen. **Nicht** die Klone/Templates aus dem Pool `librevdi`
     wählen, die gehören dem Floating-Pool.
   - **Service Token:** ein langes Zufallswort (z. B. `openssl rand -hex 24`), notieren –
     der Agent braucht es gleich
   - Machines: die Windows-VM `win11-desktop01` auswählen
   - *Use snapshots*: aus
2. **Authentication → Authenticators → New → „Internal Database“**, Name `Lokal`
   - darin **Groups → New** `vdi-users`, **Users → New** z. B. `anna` (Passwort setzen,
     Gruppe `vdi-users`)
3. **Connectivity → Transports → New → „RDP“** (direkt)
   - Name: `RDP direkt`
   - **Empty creds: an** (für den ersten Test gibt man im RDP-Fenster die Windows-Anmeldung ein)
   - Rest auf Standard
4. **Pools → Service Pools → New**
   - Name: `Mein Windows-Desktop`, Service: `Windows 11 persistent`
   - OS Manager: keiner (wird für feste Maschinen nicht benötigt)
   - danach im Pool: Reiter **Groups → Add** `vdi-users`, Reiter **Transports → Add** `RDP direkt`

## Teil 5 – Agent in der VM installieren und registrieren

**Installer bereitstellen (einmalig, auf dem Docker-Host):** LibreVDI bietet die Windows-
Installer selbst zum Download an. Dazu die Dateien in den Ordner `downloads/` legen:

```bash
cd /opt/LibreVDI && git pull
GITHUB_TOKEN=<token> tools/fetch-windows-builds.sh   # holt die neuesten CI-Builds
docker compose up -d broker-web                       # bzw. restart, veröffentlicht die Dateien
```

Der Token braucht nur Leserechte auf Actions dieses Repos (GitHub → Settings → Developer
settings → *Fine-grained tokens* → Repository *LibreVDI* → Permission **Actions: Read-only**).
Alternativ die `.exe`-Dateien aus den Artefakten von Hand nach `downloads/` kopieren (z. B. per
`scp`/WinSCP).

1. In der VM in Edge `https://<LIBREVDI_DOMAIN>/` öffnen, als **root** anmelden.
2. Im Portal oben rechts das Benutzermenü → **Downloads** (nur für Admins sichtbar, direkt:
   `https://<LIBREVDI_DOMAIN>/uds/page/downloads`) → „UDS Actor for Unmanaged windows machines“.
   Die Beschriftung stammt noch von openUDS; die Datei ist der **LibreVDI-Agent (unmanaged)**.
3. Die heruntergeladene Datei als Administrator ausführen und installieren.
4. Startmenü → **LibreVDI → „LibreVDI Agent konfigurieren“**:
   - SSL Validation: **Verify certificate**
   - UDS Broker Host: `<LIBREVDI_DOMAIN>`
   - Service Token: der Token aus Teil 4, Schritt 1
   - **Test** → erfolgreich → **Save Configuration**
5. VM neu starten (oder Dienst neu starten).
6. Im Broker: Pool „Mein Windows-Desktop“ → die VM sollte als **verfügbar** mit IP erscheinen
   (Reiter *Assigned services* bzw. nach der ersten Anmeldung zugewiesen).

## Teil 6 – Client auf dem Benutzer-PC und Test

1. Auf dem Benutzer-PC `https://<LIBREVDI_DOMAIN>/` öffnen → oben **Launcher** →
   **Windows** → `LibreVDI-Client-Setup` herunterladen (liegt bereit, sobald Teil 5 –
   „Installer bereitstellen“ erledigt ist).
2. Bei `LIBREVDI_TLS=internal`: Root-CA wie in Teil 3 auch auf dem **Benutzer-PC** importieren
   (die zwei Befehle mit `curl.exe` und `certutil`, als Administrator).
3. Den heruntergeladenen Client-Installer als Administrator ausführen. Er landet unter
   `C:\Program Files\LibreVDI\Client` und registriert Links vom Typ `udssv2://`.
4. Im Browser `https://<LIBREVDI_DOMAIN>/` öffnen → Authenticator **„Lokal“** wählen →
   Benutzer `anna` anmelden.
5. Kachel **„Mein Windows-Desktop“** anklicken → der Browser fragt, ob „LibreVDI Protocol“ bzw.
   der Client geöffnet werden soll → **Öffnen** (ggf. „immer erlauben“ anhaken).
6. Der Client startet `mstsc.exe` → Windows-Anmeldedaten der VM eingeben (`vdi-test`) →
   **Desktop erscheint**.

Wenn Schritt 5/6 nicht klappt, hilft das Client-Log im `%TEMP%`-Ordner des Benutzers
(Dateien mit `launcher` bzw. `uds` im Namen).

## Rückmeldung

Pro Teil: ✅ / ❌ und bei Fehlern Screenshot oder Log:
```bash
docker compose logs --no-color --since 30m broker-web broker-tasks | grep -iE "error|actor|unmanaged|ready" | tail -80
```
Agent-Logs in der VM: Dienst und Konfiguration schreiben nach `C:\Windows\Temp\`
(Dateien `udsactor*.log`), der Teil in der Benutzersitzung nach `%TEMP%` des Benutzers.
