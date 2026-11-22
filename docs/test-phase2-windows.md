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
| General | Name z. B. `win11-desktop01`; Resource Pool: `librevdi` |
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
   In Proxmox unter *Summary* sollte jetzt die **IP-Adresse** der VM erscheinen.
5. Windows-Updates installieren, neu starten.

## Teil 3 – Windows für VDI vorbereiten

Als Administrator in PowerShell:

```powershell
# Remotedesktop einschalten (mit Network Level Authentication) und Firewall freigeben
Set-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -Value 0
Set-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name UserAuthentication -Value 1
Enable-NetFirewallRule -DisplayGroup '@FirewallAPI.dll,-28752'   # Gruppe "Remotedesktop"

# Kein Ruhezustand / Standby (sonst ist die VM für Broker und RDP nicht erreichbar)
powercfg /hibernate off
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
```

- **Testbenutzer:** einen lokalen Benutzer anlegen (z. B. `vdi-test`) und zur Gruppe
  **Remotedesktopbenutzer** hinzufügen (Administratoren dürfen ohnehin).
- **Zertifikat** (nur bei `LIBREVDI_TLS=internal`): Die Caddy-Root-CA auf dem Docker-Host
  exportieren (siehe [installation.md](installation.md), Abschnitt 4), in die VM kopieren und
  als Administrator importieren:
  ```powershell
  certutil -addstore -f Root C:\Temp\librevdi-root-ca.crt
  ```
  Danach muss `https://<LIBREVDI_DOMAIN>/` im Edge der VM **ohne** Zertifikatswarnung öffnen.

## Teil 4 – Persistenten Pool im Broker anlegen

In der Admin-Oberfläche (`/uds/adm/`):

1. **Services → Providers → pve → Services → New → „Proxmox Fixed Machines“**
   - Name: `Windows 11 persistent`
   - Resource Pool: `librevdi`
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

1. Aus dem GitHub-Actions-Lauf „Windows builds (agent + client)“ das Artefakt
   **`librevdi-agent-windows-x64`** herunterladen (GitHub → Actions → Lauf → *Artifacts*),
   in die VM kopieren, entpacken.
2. **`LibreVDI-Agent-unmanaged-Setup-….exe`** als Administrator ausführen.
3. Startmenü → **LibreVDI → „LibreVDI Agent konfigurieren“**:
   - SSL Validation: **Verify certificate**
   - UDS Broker Host: `<LIBREVDI_DOMAIN>`
   - Service Token: der Token aus Teil 4, Schritt 1
   - **Test** → erfolgreich → **Save Configuration**
4. VM neu starten (oder Dienst neu starten).
5. Im Broker: Pool „Mein Windows-Desktop“ → die VM sollte als **verfügbar** mit IP erscheinen
   (Reiter *Assigned services* bzw. nach der ersten Anmeldung zugewiesen).

## Teil 6 – Client auf dem Benutzer-PC und Test

> Der **LibreVDI-Client-Installer** wird gerade gebaut (FreeRDP + Abhängigkeiten, erster Build
> dauert lange). Dieser Abschnitt wird ergänzt, sobald er verfügbar ist.

Geplanter Ablauf:
1. Root-CA wie in Teil 3 auch auf dem Benutzer-PC importieren (bei `LIBREVDI_TLS=internal`).
2. `LibreVDI-Client-Setup.exe` installieren (registriert Links `udssv2://`).
3. Im Browser `https://<LIBREVDI_DOMAIN>/` → Anmeldung mit **Authenticator „Lokal“**, Benutzer
   `anna` → Kachel „Mein Windows-Desktop“ → Browser fragt, ob der LibreVDI-Client geöffnet
   werden soll → **Öffnen** → `mstsc.exe` startet → Windows-Anmeldung (`vdi-test`) → Desktop.

## Rückmeldung

Pro Teil: ✅ / ❌ und bei Fehlern Screenshot oder Log:
```bash
docker compose logs --no-color --since 30m broker-web broker-tasks | grep -iE "error|actor|unmanaged|ready" | tail -80
```
Agent-Logs in der VM: Dienst und Konfiguration schreiben nach `C:\Windows\Temp\`
(Dateien `udsactor*.log`), der Teil in der Benutzersitzung nach `%TEMP%` des Benutzers.
