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
Enable-NetFirewallRule -Group '@FirewallAPI.dll,-28752'   # Regelgruppe "Remotedesktop" (sprachunabhängig)

# Kein Ruhezustand / Standby (sonst ist die VM für Broker und RDP nicht erreichbar)
powercfg /hibernate off
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
```

- **Testbenutzer:** einen lokalen Benutzer anlegen (z. B. `vdi-test`) und zur Gruppe
  **Remotedesktopbenutzer** hinzufügen (Administratoren dürfen ohnehin).
- **Zertifikat** (nur bei `LIBREVDI_TLS=internal`): LibreVDI liefert seine Root-CA selbst aus.
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

1. Aus dem neuesten Lauf „Windows builds (agent + client)“ das Artefakt
   **`librevdi-client-windows-x64`** herunterladen und entpacken.
2. Bei `LIBREVDI_TLS=internal`: Root-CA wie in Teil 3 auch auf dem **Benutzer-PC** importieren
   (die zwei Befehle mit `curl.exe` und `certutil`, als Administrator).
3. **`LibreVDI-Client-Setup-….exe`** als Administrator installieren. Er landet unter
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
