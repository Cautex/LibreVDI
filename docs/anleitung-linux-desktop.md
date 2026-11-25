# Anleitung: Persistenter Linux-Desktop (Ubuntu 24.04 + xrdp) und Linux-Client

Ziel: wie bei Windows ([anleitung-persistente-desktops.md](anleitung-persistente-desktops.md)),
nur mit einer **Ubuntu-24.04-VM** als Desktop. Ein Benutzer bekommt fest „seine“ Linux-VM und
verbindet sich per RDP (xrdp in der VM). Dazu der **LibreVDI Client für Linux** auf dem eigenen
Rechner.

> **Stand:** Pakete und Konfiguration sind in der CI gebaut und in sauberen Containern installiert
> (Debian 12, Debian 13, Ubuntu 24.04). Eine echte Sitzung (VM + xrdp + Broker) ist **noch nicht
> im Lab getestet** – Rückmeldung bitte über [testauftrag-2026-11-26.md](testauftrag-2026-11-26.md).

Voraussetzung: Die Windows-Anleitung bis Teil 3 ist erledigt (Anbieter `Proxmox Lab`,
Authentifikator `Lokal`, Benutzer `max`, Gruppe `VDI-Benutzer`). Die Linux-VM bekommt einen
**eigenen Dienst** und einen **eigenen Pool** (eigener Token, eigene Kachel).

**Zeitbedarf:** ca. 45 min.

---

## Teil 1 – Ubuntu-VM anlegen (Proxmox)

1. VM `vdi-ubuntu-01` aus dem ISO **Ubuntu Server 24.04 LTS** (Desktop-ISO geht auch, siehe
   Hinweis unten), 2 vCPU, 4 GB RAM, 32 GB Disk, Netz im VDI-VLAN, **QEMU Guest Agent: an**
   (VM → Optionen). In den Proxmox-Ressourcenpool `librevdi` aufnehmen.
2. Bei der Installation: Benutzer `vdiadmin` (Verwaltung), OpenSSH-Server an.
3. Nach dem ersten Start (per SSH oder Konsole):
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   sudo apt install -y qemu-guest-agent xrdp xfce4 xfce4-goodies dbus-x11
   sudo systemctl enable --now qemu-guest-agent xrdp
   sudo adduser xrdp ssl-cert                      # xrdp darf das TLS-Zertifikat lesen
   echo "xfce4-session" | sudo tee /etc/skel/.xsession >/dev/null
   ```
   **Warum XFCE:** GNOME (Ubuntu-Standard) läuft unter xrdp nur eingeschränkt (eine Sitzung pro
   Benutzer, lokale Anmeldung blockiert die RDP-Anmeldung). XFCE ist leicht und xrdp-erprobt.
4. Desktop-Benutzer anlegen (Konto in der VM = Portal-Benutzer, gleiches Passwort, dann klappt
   auch die Anmeldung ohne Nachfrage):
   ```bash
   sudo adduser max          # legt ~/.xsession aus /etc/skel an
   ```
   Für schon vorhandene Konten: `echo xfce4-session > ~/.xsession` als dieser Benutzer.
5. Firewall: Ubuntu hat `ufw` standardmäßig **aus**. Ist sie an:
   `sudo ufw allow 3389/tcp && sudo ufw allow 43910/tcp` (RDP und Agent).
6. Test ohne LibreVDI: vom eigenen PC per RDP auf die IP der VM, als `max` – es muss ein
   XFCE-Desktop erscheinen. Danach abmelden (Menü → Abmelden), nicht nur Fenster schließen.

**Ubuntu Desktop statt Server:** zusätzlich *Einstellungen → System → Remotedesktop* **aus**
lassen (sonst belegt GNOME den Port 3389) und vor dem RDP-Test lokal abmelden.

## Teil 2 – Dienst und Pool in LibreVDI

Wie Windows-Anleitung Teil 4–6, mit diesen Werten:

| Wo | Feld | Wert |
|---|---|---|
| Dienst (Neu → „Proxmox Persistent Desktops (LibreVDI)“) | Name | `Persistent Ubuntu` |
| | Service-Token | neuer Zufallswert (`openssl rand -hex 24`) – **notieren** |
| | Machines | `vdi-ubuntu-01` |
| | Automatic assignment | aus |
| Transport | | den vorhandenen `RDP direkt` wiederverwenden (xrdp spricht RDP) |
| Service-Pool | Short name / Name | `Ubuntu` / `Ubuntu persistent`, Base service `Persistent Ubuntu`, OS Manager keiner |
| | Gruppen / Transporte | `VDI-Benutzer` / `RDP direkt` |

## Teil 3 – Agent in der VM

1. Paket holen: als `root` in der LibreVDI-Verwaltung → Benutzermenü → **Downloads** →
   **LibreVDI Agent (unmanaged) for persistent Linux desktops – Ubuntu 24.04**
   (`librevdi-agent-unmanaged_<version>_amd64-ubuntu2404.deb`), z. B. mit `scp` in die VM.
   Für Debian 12/13-VMs das passende Paket nehmen.
2. Installieren:
   ```bash
   sudo apt install ./librevdi-agent-unmanaged_<version>_amd64-ubuntu2404.deb
   ```
3. Konfigurieren – der Token wird **abgefragt** (nicht in der Befehlszeile, nicht im Verlauf):
   ```bash
   sudo librevdi-agent-configure --broker <domain>
   # Service token: <Token aus Teil 2>
   ```
   Ausgabe: `LibreVDI Agent configured for broker <domain> …` und `agent service
   (udsactor-unmanaged.service) restarted`. Optionen: `--no-verify-ssl` (selbstsigniertes
   Zertifikat ohne importierte CA), `--log-level debug`. Für Provisionierung (Ansible, cloud-init):
   Token per stdin, z. B. `sudo librevdi-agent-configure --broker <domain> < token.txt`.

   Alternativ grafisch im XFCE-Menü: **LibreVDI Agent Configuration** (fragt das root-Passwort).
4. Prüfen:
   ```bash
   systemctl status udsactor-unmanaged.service     # active (running)
   sudo journalctl -u udsactor-unmanaged.service -n 30
   ```
   Die Konfiguration liegt in `/etc/udsactor/udsactor.cfg` (nur root lesbar, enthält den Token).
5. Snapshot `02-agent-bereit`.

Technische Namen (`udsactor-…`, `/etc/udsactor`) stammen aus der Upstream-Software und bleiben,
damit Updates und Upstream-Doku passen; Paketname, Beschreibung und Menüeinträge heißen LibreVDI.

## Teil 4 – VM zuweisen und verbinden

1. Pool `Ubuntu persistent` → **Zugewiesene Services → Service zuweisen**: `max@Lokal`,
   Maschine `vdi-ubuntu-01`.
2. **Linux-Client** auf dem eigenen Rechner (Debian 12, Debian 13 oder Ubuntu 24.04): im Portal
   oben **LibreVDI Client** → Abschnitt **Linux** → passendes Paket, dann
   ```bash
   sudo apt install ./librevdi-client_<version>_amd64-<distribution>.deb
   ```
   Der Client registriert sich für Links aus dem Portal (Startmenü-Eintrag „LibreVDI Client“).
   Windows-PCs nehmen weiter den Windows-Client.
3. Im Portal als `max` → Kachel **Ubuntu** → Browser fragt „LibreVDI Client öffnen?“ → Öffnen.
4. xrdp-Anmeldemaske: Session `Xorg`, Benutzer `max` + Passwort (bei *Empty creds* aus im
   Transport werden die Portal-Daten übergeben).

## Teil 5 – Prüfen

| # | Test | Erwartung |
|---|---|---|
| L1 | Client-Paket installieren (Debian 12/13 oder Ubuntu 24.04) | Installation ohne Fehler; Menüeintrag „LibreVDI Client“ mit LibreVDI-Logo |
| L2 | Agent installieren + `librevdi-agent-configure` | Dienst `udsactor-unmanaged` läuft; in der Verwaltung beim Dienst keine Fehler im Log |
| L3 | Verbinden wie Teil 4 | XFCE-Desktop; *Zugewiesene Services*: In Benutzung **Ja**, Angemeldeter Benutzer `max`, Actor-Version gefüllt |
| L4 | In XFCE **abmelden** | In Benutzung **Nein**, Zuweisung bleibt (Status Gültig) |
| L5 | Fenster schließen **ohne** Abmelden, neu verbinden | dieselbe Sitzung (xrdp verbindet wieder), In Benutzung bleibt **Ja** |
| L6 | Energie-Richtlinie und Leerlauf-Abmeldung wie Windows-Tests 5, 6 und 8 | gleiches Verhalten |

## Fehlerbilder

| Symptom | Ursache / Lösung |
|---|---|
| Schwarzer Bildschirm nach der Anmeldung, Verbindung bricht ab | `~/.xsession` fehlt oder Benutzer lokal angemeldet (Ubuntu Desktop): Teil 1, Schritt 3/4 |
| Verbindung bleibt bei **75 %** | Port 3389 nicht erreichbar: `systemctl status xrdp`, `ufw status` |
| In Benutzung bleibt „Nein“ | Agent meldet sich nicht: `journalctl -u udsactor-unmanaged`; Token = Token **dieses** Dienstes? Broker per HTTPS erreichbar (`curl -I https://<domain>/`)? Bei eigener CA `--no-verify-ssl` oder CA importieren (`/usr/local/share/ca-certificates/` + `update-ca-certificates`) |
| Browser öffnet den Client nicht | Paket installiert? `xdg-mime query default x-scheme-handler/udssv2` muss `udslauncher.desktop` zeigen |
| `apt` meldet fehlende Abhängigkeiten | Paket der falschen Distribution: Debian 12, Debian 13 und Ubuntu 24.04 haben je ein eigenes Paket |
