# Testauftrag: Linux-Client, Linux-Agent, Leerlauf-Abmeldung

Stand: 26.11.2026 (Branch `claude/happy-allen-xenekt`). Was neu ist und hier getestet werden soll:

| # | Neu | Status vor dem Lab-Test |
|---|---|---|
| N1 | **LibreVDI Client für Linux** (`.deb` für Debian 12, Debian 13, Ubuntu 24.04), im Portal unter *Linux* | in der CI gebaut, in sauberen Containern installiert (alle Programme finden ihre Bibliotheken) |
| N2 | **LibreVDI Agent für Linux** (`.deb`, unmanaged + managed) mit `librevdi-agent-configure`, Anleitung Ubuntu + xrdp | in der CI gebaut und installiert; Konfigurationsdatei gegen den echten Agent-Parser geprüft |
| N3 | Dienst-Einstellung **„Log off inactive sessions after (minutes)“** | gegen die Actor-API geprüft (Broker sendet `max_idle`); Abmeldung selbst macht der Agent – noch nicht in einer echten Sitzung gesehen |

Nicht enthalten (bewusst): `.rpm` (Fedora/openSUSE), AppImage, geklonte Linux-Pools.

---

## 0 – Vorbereitung (Docker-Host)

```bash
cd /opt/LibreVDI
git pull --recurse-submodules
docker compose build
docker compose up -d
GITHUB_TOKEN=<token> tools/fetch-windows-builds.sh   # holt jetzt Windows- UND Linux-Builds
docker compose restart broker-web
docker compose exec broker-web python -m librevdi_ext.selfcheck --quiet   # "selfcheck 71/71 ok"
```

`fetch-windows-builds.sh` legt neben den `.exe` jetzt auch `librevdi-*.deb` in `downloads/` ab.

| # | Prüfung | Erwartung |
|---|---|---|
| 0.1 | Selbsttest (letzte Zeile oben) | `71/71 ok` |
| 0.2 | Portal → **LibreVDI Client** | Abschnitt Windows *und* Linux; Linux: „LibreVDI Client (Debian 12)“, „(Debian 13)“, „(Ubuntu 24.04)“ |
| 0.3 | Verwaltung → Benutzermenü → **Downloads** | zusätzlich 6 Linux-Einträge „LibreVDI Agent (unmanaged/managed) for … Linux desktops – <Distribution>“; keine „UDS“-Einträge |

## A – Linux-Client (N1)

Auf einem Linux-Rechner (Notebook oder Test-VM mit Desktop) mit Debian 12, Debian 13 oder
Ubuntu 24.04. Ziel ist der **bestehende Windows-Desktop** aus der Windows-Anleitung – so wird
nur der Client getestet.

| # | Schritt | Erwartung |
|---|---|---|
| A1 | Im Portal das passende Paket laden, `sudo apt install ./librevdi-client_<version>_amd64-<distribution>.deb` | ohne Fehler; Menüeintrag **LibreVDI Client** mit LibreVDI-Logo |
| A2 | Im Portal als `max` → Kachel **Windows 11** | Browser fragt „LibreVDI Client öffnen?“ → Öffnen → RDP-Fenster, Windows-Anmeldung |
| A3 | Arbeiten: Tastatur (Umlaute, `@`), Maus, Zwischenablage hin und zurück, Fenstergröße | funktioniert wie mit dem Windows-Client |
| A4 | Ton (z. B. Video in der VM), falls Lautsprecher vorhanden | Ton kommt an (FreeRDP mit PulseAudio) |
| A5 | Fenster schließen, erneut verbinden | Sitzung wird fortgesetzt |
| A6 | `apt remove librevdi-client` | sauber entfernt |

## B – Linux-Desktop mit Agent (N2)

Nach [anleitung-linux-desktop.md](anleitung-linux-desktop.md) (Teil 1–4), dann deren Prüftabelle
**L1–L6**. Wichtigste Punkte:

| # | Schritt | Erwartung |
|---|---|---|
| B1 | `sudo librevdi-agent-configure --broker <domain>` (Token wird abgefragt) | „LibreVDI Agent configured …“, „agent service (udsactor-unmanaged.service) restarted“ |
| B2 | `systemctl status udsactor-unmanaged` | `active (running)` |
| B3 | Verbinden (Windows- oder Linux-Client) | XFCE-Desktop; *Zugewiesene Services*: In Benutzung **Ja**, Angemeldeter Benutzer `max`, Actor-Version gefüllt |
| B4 | In XFCE abmelden | In Benutzung **Nein**, Zuweisung bleibt |

## C – Leerlauf-Abmeldung (N3)

Windows-VM (und, wenn B klappt, auch die Linux-VM). Dienst → Reiter **Erweitert** →
*Log off inactive sessions after (minutes)* = `5` → Speichern.

| # | Schritt | Erwartung |
|---|---|---|
| C1 | Neu anmelden (die Einstellung gilt ab der **nächsten Anmeldung**), dann Fenster schließen ohne Abmelden | nach ca. 5 min: In Benutzung **Nein**; im Log der Zuweisung (Pool → Zugewiesene Services → Eintrag → Logs) „Session closed due to inactivity …“ |
| C2 | Verbunden bleiben, 3–4 min nichts tun | Hinweis in der Sitzung („You have been idle for a while …“), Mausbewegung → Hinweis verschwindet, keine Abmeldung |
| C3 | Einstellung wieder `0`, neu anmelden, 6 min warten | keine Abmeldung |
| C4 | Zusammen mit Energie-Richtlinie (*Shut down machine after delay*, 5 min) | nach Leerlauf-Abmeldung + Verzögerung fährt die VM herunter |

Bekannte Abweichung zu Horizon: Abgemeldet wird nach **Leerlauf** (keine Eingabe), nicht nach der
Trennungszeit – auch eine verbundene, aber unbenutzte Sitzung (mit Warnung). Wer exakt „nach
Trennung“ braucht, nutzt die Windows-Richtlinie „Zeitlimit für getrennte Sitzungen“
([horizon-vergleich.md](horizon-vergleich.md)).

## D – Gegenprobe Bestehendes

| # | Prüfung | Erwartung |
|---|---|---|
| D1 | Windows-Anleitung Teil 10, Tests 1–3 mit dem neuen Build | unverändert OK |
| D2 | Windows-Client/-Agent aus dem neuen Build installieren (drüber) | unverändert OK |

## Rückmeldung

Bitte als Tabelle zurück (Nummer, OK / Fehler, ggf. Screenshot oder Log-Auszug):

- Broker: `docker compose logs --since 30m broker-web | grep -i -e actor/v3 -e librevdi`
- Linux-Agent: `sudo journalctl -u udsactor-unmanaged -n 100` (enthält keinen Token)
- Linux-Client: Start im Terminal, `/usr/share/udslauncher/launcher` mit dem Link aus dem Portal
  zeigt Fehlermeldungen direkt an

Bekannte offene Punkte: Hinweistexte des Agenten in der Sitzung sind englisch (Upstream);
Broker-seitiges „Jetzt abmelden“ für unmanaged Agenten gibt es noch nicht (Roadmap 2d, Punkt 8).
