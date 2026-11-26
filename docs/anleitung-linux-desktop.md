# Anleitung: Persistente Linux-Desktops (Ubuntu, Rocky Linux) und Linux-Client

Ziel: wie bei Windows ([anleitung-persistente-desktops.md](anleitung-persistente-desktops.md)),
nur mit einer **Linux-Desktop-VM**. Ein Benutzer bekommt fest „seine“ VM und verbindet sich per
RDP – vom Windows- oder vom Linux-Client aus.

| Verbindung | Client | Desktop |
|---|---|---|
| Windows → Linux | LibreVDI Client für Windows | Ubuntu / Rocky (diese Anleitung) |
| Linux → Windows | LibreVDI Client für Linux (Teil 5) | Windows (Windows-Anleitung) |
| Linux → Linux | LibreVDI Client für Linux | Ubuntu / Rocky |

Server ohne grafische Oberfläche gehören nicht in LibreVDI – dafür bleibt SSH.

> **Stand:** Pakete in der CI gebaut und in sauberen Containern installiert. Eine echte Sitzung
> (VM + RDP-Server + Broker) ist **noch nicht im Lab getestet**. Rückmeldung über den Testauftrag.

## Welcher RDP-Server?

Der Desktop braucht einen RDP-Server, der *mehrere Benutzer* über den Anmeldebildschirm
anmeldet. Das hängt von der GNOME-Version ab (geprüft an den Paketen der Distributionen):

| Distribution | GNOME | X11-Sitzung | RDP-Server | Leerlauf-Abmeldung |
|---|---|---|---|---|
| **Ubuntu 24.04 Desktop** | 46 | ja („Ubuntu on Xorg“) | **GNOME Remote Desktop – Remote Login** (eingebaut) | GNOME-Einstellung (Teil 4) |
| **Ubuntu 26.04 Desktop** | 50 | nein (nur Wayland) | **GNOME Remote Desktop – Remote Login** (eingebaut) | GNOME-Einstellung (Teil 4) |
| **Rocky Linux 10** | 47 | nein (Xorg entfernt) | **GNOME Remote Desktop – Remote Login** | GNOME-Einstellung (Teil 4) |
| **Rocky Linux 9** | 40 | ja | **xrdp** (EPEL); GNOME 40 hat noch kein Remote Login | LibreVDI-Dienst (*Log off inactive sessions*) |

**Warum zweierlei Leerlauf-Abmeldung:** Der LibreVDI-Agent misst die Leerlaufzeit über X11. In
Wayland-Sitzungen (alle mit GNOME Remote Desktop) sähe er nur Eingaben in X11-Fenstern und könnte
einen aktiven Benutzer abmelden. LibreVDI schickt ihm deshalb für Wayland-Sitzungen keine
Leerlaufzeit; dort übernimmt GNOME selbst die Abmeldung (Teil 4). In xrdp-Sitzungen (X11) misst
der Agent korrekt.

**Anmeldung bei GNOME Remote Desktop:** Remote Login hat *ein* gemeinsames RDP-Konto für die
Verbindung (nur zum Verbinden, kein Linux-Konto). Danach erscheint der GNOME-Anmeldebildschirm,
an dem sich der Benutzer mit **seinem eigenen Linux-Konto** anmeldet. Bei xrdp gibt es nur eine
Anmeldung (Linux-Konto direkt).

---

## Teil 1 – VM anlegen (Proxmox)

1. VM `vdi-ubuntu-01` (bzw. `vdi-rocky-01`) aus dem **Desktop**-ISO (Ubuntu 24.04/26.04
   Desktop; Rocky: DVD-ISO mit „Server with GUI“ oder „Workstation“), 2–4 vCPU, 4–8 GB RAM,
   40 GB Disk, VDI-VLAN, **QEMU Guest Agent: an**, in den Proxmox-Ressourcenpool `librevdi`.
2. Bei der Installation: Admin-Konto `vdiadmin`. Danach aktualisieren und Guest Agent:
   ```bash
   # Ubuntu
   sudo apt update && sudo apt full-upgrade -y
   sudo apt install -y qemu-guest-agent openssh-server
   # Rocky
   sudo dnf upgrade -y
   sudo dnf install -y qemu-guest-agent epel-release
   sudo systemctl enable --now qemu-guest-agent
   ```
3. **Keine automatische Anmeldung** (Einstellungen → Benutzer → Automatische Anmeldung **aus**).
   Ein lokal angemeldeter Benutzer blockiert sonst die RDP-Anmeldung desselben Kontos.
4. Desktop-Benutzer anlegen, z. B. `max` (gleicher Name wie im Portal ist übersichtlich):
   `sudo adduser max` (Ubuntu) bzw. `sudo useradd -m max && sudo passwd max` (Rocky).
5. Firewall – RDP (3389) und Agent (43910):
   ```bash
   # Ubuntu (ufw ist standardmäßig aus; nur falls aktiv)
   sudo ufw allow 3389/tcp && sudo ufw allow 43910/tcp
   # Rocky
   sudo firewall-cmd --permanent --add-port=3389/tcp --add-port=43910/tcp && sudo firewall-cmd --reload
   ```

## Teil 2a – GNOME Remote Desktop (Ubuntu 24.04, Ubuntu 26.04, Rocky 10)

**Grafisch (Ubuntu):** *Einstellungen → System → Remotedesktop → Reiter „Remote-Anmeldung“* →
einschalten, Benutzername und Passwort für das **RDP-Konto** festlegen (z. B. `rdp-vdi` und ein
langes Passwort – notieren, kommt in Teil 3 in den Transport). Fertig.

**Kommandozeile (alle drei; Rocky 10 nur so):**
```bash
# Rocky 10: Paket installieren (Ubuntu hat es schon)
sudo dnf install -y gnome-remote-desktop

# TLS-Zertifikat für den Systemdienst (als dessen Benutzer erzeugen)
d=~gnome-remote-desktop/.local/share/gnome-remote-desktop
sudo -u gnome-remote-desktop mkdir -p "$d"
sudo -u gnome-remote-desktop openssl req -new -newkey rsa:4096 -days 3650 -nodes -x509 \
  -subj "/CN=$(hostname -f)" -keyout "$d/tls.key" -out "$d/tls.crt"
sudo grdctl --system rdp set-tls-key "$d/tls.key"
sudo grdctl --system rdp set-tls-cert "$d/tls.crt"

# RDP-Konto (nur zum Verbinden) und Dienst einschalten
sudo grdctl --system rdp set-credentials rdp-vdi '<langes Passwort>'   # 26.04: ohne Passwort aufrufen, fragt danach
sudo grdctl --system rdp enable
sudo systemctl enable --now gnome-remote-desktop.service
sudo grdctl --system status
```
Die genaue Syntax von `grdctl` unterscheidet sich zwischen GNOME 46 und 50 leicht – im Zweifel
`grdctl --help`. Test ohne LibreVDI: vom PC per RDP auf die VM, mit dem RDP-Konto verbinden →
GNOME-Anmeldebildschirm → als `max` anmelden → Desktop.

## Teil 2b – xrdp (Rocky 9)

```bash
sudo dnf install -y xrdp xorgxrdp            # aus EPEL
sudo systemctl enable --now xrdp
# GNOME auf Xorg für xrdp-Sitzungen
echo "gnome-session" | sudo tee /etc/skel/.Xclients >/dev/null && sudo chmod +x /etc/skel/.Xclients
sudo -u max sh -c 'echo gnome-session > ~/.Xclients && chmod +x ~/.Xclients'
```
SELinux bleibt an (xrdp aus EPEL bringt die nötige Richtlinie mit). Test: per RDP auf die VM, als
`max` anmelden → GNOME-Desktop. Abmelden über das Menü (nicht nur Fenster schließen).

## Teil 3 – Dienst, Transport und Pool in LibreVDI

Wie Windows-Anleitung Teil 4–6, mit diesen Werten:

| Wo | Feld | Wert |
|---|---|---|
| Dienst (Neu → „Proxmox Persistent Desktops (LibreVDI)“) | Name | `Persistent Linux` |
| | Service-Token | neuer Zufallswert (`openssl rand -hex 24`) – **notieren** |
| | Machines | `vdi-ubuntu-01` (bzw. Rocky-VM) |
| | Automatic assignment | aus |
| | Log off inactive sessions after | GNOME Remote Desktop: **0** (Teil 4 regelt das); xrdp/Rocky 9: nach Wunsch |
| Transport **für GNOME Remote Desktop** (Neu → RDP) | Name | `RDP Linux (GNOME)` |
| | Username / Password | das **RDP-Konto** aus Teil 2a (`rdp-vdi` + Passwort) |
| | Empty creds | aus |
| Transport **für xrdp** | | den vorhandenen `RDP direkt` wiederverwenden (Linux-Konto direkt) |
| Service-Pool | Short name / Name | `Linux` / `Linux persistent`, Base service `Persistent Linux`, OS Manager keiner |
| | Gruppen / Transporte | `VDI-Benutzer` / der passende Transport |

## Teil 4 – Agent in der VM

1. Paket holen: als `root` in der Verwaltung → Benutzermenü → **Downloads** →
   **LibreVDI Agent (unmanaged) for persistent Linux desktops – <Distribution>**, z. B. mit `scp`
   in die VM kopieren.
2. Installieren:
   ```bash
   sudo apt install ./librevdi-agent-unmanaged_<version>_amd64-ubuntu2404.deb   # Ubuntu
   sudo dnf install ./librevdi-agent-unmanaged-<version>.x86_64-rocky9.rpm        # Rocky
   ```
3. Konfigurieren – der Token wird **abgefragt** (nicht in Befehlszeile oder Verlauf):
   ```bash
   sudo librevdi-agent-configure --broker <domain>
   # Service token: <Token aus Teil 3>
   ```
   Optionen: `--no-verify-ssl` (selbstsigniertes Zertifikat ohne importierte CA),
   `--log-level debug`. Für Provisionierung: Token per stdin (`… < token.txt`).
   Alternativ grafisch: Anwendung **LibreVDI Agent Configuration** (fragt das Admin-Passwort).
4. Prüfen:
   ```bash
   systemctl status udsactor-unmanaged.service || systemctl status udsactor.service   # deb / rpm
   sudo journalctl -u 'udsactor*' -n 30
   ```
   Konfiguration: `/etc/udsactor/udsactor.cfg` (nur root lesbar, enthält den Token).
5. **Leerlauf-Abmeldung durch GNOME** (nur Teil 2a; Beispiel 30 Minuten):
   ```bash
   sudo mkdir -p /etc/dconf/profile /etc/dconf/db/local.d
   [ -f /etc/dconf/profile/user ] || printf 'user-db:user\nsystem-db:local\n' | sudo tee /etc/dconf/profile/user
   sudo tee /etc/dconf/db/local.d/50-librevdi-idle >/dev/null <<'EOF'
   [org/gnome/settings-daemon/plugins/power]
   sleep-inactive-ac-type='logout'
   sleep-inactive-ac-timeout=1800
   EOF
   sudo dconf update
   ```
   GNOME meldet dann nach 30 Minuten ohne Eingabe ab (`logout` ist bei GNOME 46 und 50 ein
   gültiger Wert, an den Paketen geprüft). Ob das in Remote-Login-Sitzungen greift, ist Teil des
   Tests.
6. Snapshot `02-agent-bereit`.

Technische Namen (`udsactor-…`, `/etc/udsactor`) stammen aus der Upstream-Software und bleiben;
Paketname, Beschreibung und Menüeinträge heißen LibreVDI.

## Teil 5 – Zuweisen, Linux-Client, verbinden

1. Pool `Linux persistent` → **Zugewiesene Services → Service zuweisen**: `max@Lokal`, Maschine
   `vdi-ubuntu-01`.
2. **Linux-Client** auf dem eigenen Rechner (Ubuntu 24.04/26.04 Desktop, Rocky 9/10): im Portal
   oben **LibreVDI Client** → Abschnitt **Linux** → passendes Paket:
   ```bash
   sudo apt install ./librevdi-client_<version>_amd64-ubuntu2604.deb                 # Ubuntu
   sudo dnf install -y epel-release && sudo dnf install ./librevdi-client-<version>.x86_64-rocky10.rpm   # Rocky
   ```
   Rocky braucht **EPEL** (FFmpeg-Bibliotheken). Auf Rocky ist H.264 aus (für Enterprise Linux
   nicht frei verfügbar); RDP nutzt dann die anderen Codecs – etwas mehr Bandbreite.
3. Im Portal als `max` → Kachel **Linux** (oder **Windows 11**) → „LibreVDI Client öffnen?“ →
   Öffnen.
4. GNOME Remote Desktop: GNOME-Anmeldebildschirm → `max` + Passwort. xrdp: direkt angemeldet
   bzw. xrdp-Anmeldemaske.

## Teil 6 – Prüfen

| # | Test | Erwartung |
|---|---|---|
| L1 | Client-Paket installieren | ohne Fehler; Menüeintrag **LibreVDI Client** mit LibreVDI-Logo |
| L2 | Agent installieren + `librevdi-agent-configure` | Dienst läuft; im Log des Dienstes (Verwaltung) keine Fehler |
| L3 | Verbinden | Desktop; *Zugewiesene Services*: In Benutzung **Ja**, Angemeldeter Benutzer `max`, Actor-Version gefüllt |
| L4 | Abmelden (Menü) | In Benutzung **Nein**, Zuweisung bleibt |
| L5 | Fenster schließen **ohne** Abmelden, neu verbinden | gleiche Sitzung wieder da (bei GNOME Remote Desktop: zu prüfen), In Benutzung bleibt **Ja** |
| L6 | Leerlauf-Abmeldung (GNOME: Teil 4.5 mit kurzer Zeit, z. B. 300; xrdp: Dienst-Einstellung 5) | nach der Zeit ohne Eingabe abgemeldet, In Benutzung **Nein** |
| L7 | Energie-Richtlinie (*Shut down machine after delay*) | wie bei Windows: VM fährt nach Abmeldung + Verzögerung herunter, startet beim Verbinden |

## Fehlerbilder

| Symptom | Ursache / Lösung |
|---|---|
| RDP-Verbindung wird sofort abgelehnt (GNOME) | RDP-Konto im Transport ≠ `grdctl`-Zugangsdaten; `sudo grdctl --system status`; Zertifikat gesetzt? |
| Anmeldebildschirm, danach schwarz / zurück | Benutzer ist lokal (Proxmox-Konsole) angemeldet → dort abmelden; keine automatische Anmeldung |
| Verbindung bleibt bei **75 %** | Port 3389 nicht erreichbar: Firewall (Teil 1.5), Dienst läuft? |
| In Benutzung bleibt „Nein“ | Agent meldet sich nicht: `journalctl -u 'udsactor*'`; Token = Token **dieses** Dienstes? Broker per HTTPS erreichbar (`curl -I https://<domain>/`)? Eigene CA: `--no-verify-ssl` oder CA importieren |
| Browser öffnet den Client nicht | Paket installiert? `xdg-mime query default x-scheme-handler/udssv2` → `udslauncher.desktop` |
| `dnf` findet `libavcodec…` nicht (Rocky) | EPEL fehlt: `sudo dnf install -y epel-release` |
| Paket passt nicht zur Distribution | Ubuntu 24.04, 26.04, Rocky 9, 10 haben je ein eigenes Paket |
