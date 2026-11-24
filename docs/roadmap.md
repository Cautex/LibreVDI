# Roadmap

Stand: 23.11.2026. Reihenfolge der Phasen = vereinbarte Reihenfolge: erst persistente Desktops
vollständig und übersichtlich, dann automatisierte Pools (Phase 3). Innerhalb einer Phase =
vorgeschlagene Priorität.

## Phase 2b – MVP abrunden

| # | Thema | Inhalt | Umsetzung |
|---|---|---|---|
| 1 | **Echte persistente Zuordnung** | „Proxmox Fixed Machines“ gibt die VM bei Windows-Abmeldung frei (Status *Removed*), der Benutzer bekommt beim nächsten Mal irgendeine freie VM. Ziel: feste Zuordnung Benutzer ↔ VM, die bestehen bleibt | LibreVDI-Plugin: Service-Typ „Proxmox Persistent Desktops“ (erbt von Fixed Machines, gibt bei Abmeldung nicht frei); Anleitung für manuelle Zuweisung |
| 2 | **Branding** | „LibreVDI“ statt „UDS“ überall: Portal, Admin, Download-Texte, Launcher-Fenster (About, Server-Freigabe, Fortschritt), Installer, Dienstname des Agents; eigenes Logo | Logo + Überschreiben statischer Dateien und Übersetzungen im Image; Client/Agent: Patch-Dateien auf Upstream (bis Upstream Branding konfigurierbar macht) |
| 3 | **Tunnel als Option pro Pool** | wie Horizon „Tunnel ja/nein“: Clients verbinden über LibreVDI statt direkt zur VM | Tunnel-Server als Compose-Dienst (Profil), automatische Registrierung; pro Pool Transport „RDP direkt“ und/oder „RDP getunnelt“, optional per Netzwerk (intern direkt, extern Tunnel) |
| 4 | **Signierte RDP-Dateien** | keine Warnung „Unbekannter Herausgeber“ | Option *Sign RDP file* im Transport + Zertifikat aus eigener CA oder öffentlich; GPO-Vorlage „vertrauenswürdige RDP-Herausgeber“ |
| 5 | **Releases** | fertige Downloads statt Selbstbau: Docker-Image (GHCR) + Windows-Installer als GitHub-Release, Lizenzhinweise für mitgelieferte Bibliotheken (FreeRDP, FFmpeg, OpenSSL …) | ✅ umgesetzt: `release.yml` (Tag → Draft-Release + GHCR), Installer im Image gebündelt, Lizenzhinweise automatisch ([release.md](release.md)); offen: Code-Signing der Installer |

## Phase 2c – näher an die Horizon-Logik

| # | Thema | Stand |
|---|---|---|
| 1 | **Energie-Richtlinie** für persistente Pools: nach Abmeldung herunterfahren (Verzögerung in Minuten) oder immer eingeschaltet; ausgeschaltete VMs starten beim Verbinden | ✅ umgesetzt |
| 2 | **Begriffe und Pooltypen** wie bei Horizon erklärt ([horizon-vergleich.md](horizon-vergleich.md)) | ✅ umgesetzt |

## Phase 2d – Persistente Desktops fertigstellen (aktuell)

| # | Thema | Stand |
|---|---|---|
| 1 | **Feste Zuweisung durch den Admin** (Horizon „Assign User“): VM vorbereiten, einem Benutzer zuweisen; Schalter *Automatic assignment* am Dienst (aus = nur zugewiesene VMs) | ✅ umgesetzt, Lab-Test nach [anleitung-persistente-desktops.md](anleitung-persistente-desktops.md) |
| 2 | **Durchgehende Testanleitung** von leerem System bis Verbindung | ✅ [anleitung-persistente-desktops.md](anleitung-persistente-desktops.md) |
| 3 | Agent-Update über ältere Versionen (Dienst-Umbenennung) im Lab bestätigen | offen |
| 4 | Dienst ohne Maschinen anlegbar, Maschinen später ergänzen; Fehler heben Zuweisungen nie auf („Keep on error“ fest an) | ✅ umgesetzt |
| 5 | **Silent-Installation des Agents** mit Parametern (z. B. `/S /BROKER=… /TOKEN=…`), damit nicht jede VM von Hand konfiguriert werden muss (Konfiguration liegt in `HKLM\SOFTWARE\UDSActor`, Base64-JSON) | offen |

## Phase 2e – Bedienung wie bei Horizon: Oberfläche, Navigation, Begriffe

Die Upstream-Verwaltung ist verschachtelt (Services → Anbieter → Services → Pools → Service-Pools
→ Zugewiesene Services). Ziel ist eine Struktur, die Horizon-Administratoren sofort verstehen:

- **Konzept zuerst** (mit Skizzen, vor jeder Umsetzung abstimmen): Navigation etwa
  *Inventar* (Desktop-Pools, Maschinen, Benutzer-Zuweisungen), *Überwachung* (Sitzungen,
  Ereignisse, Problem-Maschinen), *Benutzer und Gruppen*, *Einstellungen* (Hypervisoren,
  Protokolle/Transporte, Tunnel, Zertifikate)
- **Begriffe** vereinheitlichen (z. B. „Desktop-Pool“ statt „Service-Pool“, „Maschinen“ statt
  „Zugewiesene Services“, „Hypervisor“ statt „Anbieter“), verständliche Spalten und Status
- **Pool anlegen in einem Ablauf**: Typ (manuell/automatisiert, dedicated/floating) →
  VMs → Protokoll → Berechtigung, statt vier getrennter Bereiche
- Umsetzung: eigene Oberfläche über die vorhandene REST-API (Upstream-Verwaltung bleibt für
  Spezialfälle erreichbar) oder Anpassung der Upstream-Oberfläche – Entscheidung als ADR

### Notizen aus dem UI-Rundgang (24.11.2026)

| Bereich heute | Beobachtung | Idee |
|---|---|---|
| Hauptmenü „Services“ | Oberbegriff passt nicht; darunter „Anbieter“, darin wieder „Services“ | Horizon-Struktur: *Settings → Servers → Hypervisors*; Pools unter *Inventory → Desktops* |
| Anbieter-Typen „Hypervisors“ / „Cloud providers“ | Trennung für Admins unklar | zu einer Liste „Virtualization platforms“ zusammenführen; Proxmox hervorgehoben, nicht getestete Plattformen als „experimentell“ markieren oder ausblenden |
| fehlende Plattform | Apache **CloudStack** nicht angebunden | eigener Anbieter-Plugin (später, eigene Phase) |
| „Existing machines“: OpenGnsys, Static IP Machines | OpenGnsys (spanisches Klon-System für Schul-PCs) für LibreVDI irrelevant; „Static IP Machines“ unverständlich benannt | OpenGnsys ausblenden; umbenennen in „Physical / existing machines (by IP)“ |
| Servers → „Unmanaged IP Server“ | Zweck nicht erkennbar | erklären bzw. nur zeigen, wenn „Static IP“-Pools genutzt werden |
| Authentifikatoren | „IP“ unklar; welcher ist „Active Directory“? | Vorlage **„Active Directory“** (LDAP mit AD-Voreinstellungen), „IP“ als „Network-based (kiosk)“ beschriften, Entwickler-Beispiel „Sample“ ausblenden |
| Sprache | Deutsche Upstream-Übersetzung teils holprig („Instandhaltung“ für Maintenance) | **Englisch als Standardsprache**, Deutsch umschaltbar |
| Anbieter → Dienst → Service-Pool | Zwischenschritt „Dienst“ ungewohnt (Horizon: vCenter → Pool) | Upstream-Grund: ein Dienst (VMs/Template) kann mehrere Pools speisen (andere Gruppen/Protokolle). Ziel: Assistent „Desktop-Pool anlegen“ erzeugt Dienst und Pool in einem Ablauf; Maschinen direkt am Pool hinzufügen |
| Formulare | Feld „Tags“ steht über „Name“ | Pflichtfeld Name immer zuerst |
| Transporte | sehr viele Einzeloptionen, „direct/tunneled“ und „Connectivity → Tunnels“ getrennt | Protokoll-Profile mit Voreinstellungen (z. B. „LAN – beste Qualität“, „WAN – sparsam“), Tunnel als Option „über Gateway verbinden“ direkt am Protokoll; Geräte-Filter mit verständlichen Namen (ChromeOS, Dell Wyse) |
| Authentifikator | Felder wie „Access“, „Priority“, „Different user for each host“ nicht selbsterklärend | Erklärtexte direkt im Formular, Sonderoptionen einklappen |
| Rollen | nur Admin / Staff Member / User, keine eigenen Rollen | Rollenmodell wie Horizon (z. B. Helpdesk: nur Sitzungen und Zuweisungen) prüfen |
| Pools / Zugewiesene Services | Maschinen liegen unter dem Pool versteckt | eigene Übersicht *Inventory → Machines* (alle VMs, Benutzer, Status, Agent) |

## Phase 2f – LibreVDI Client als Desktop-App (Windows, später Linux)

Wie der Horizon Client: Server eintragen, anmelden, Desktops als Liste, Doppelklick verbindet –
ohne Browser. Vorher Spike: welche Broker-API die Desktop-Liste und Tickets liefert (das Portal
nutzt dafür bereits eine REST-Schnittstelle); dann eigene App auf Basis der Upstream-Rust-Bausteine
(Verbindungsaufbau, FreeRDP), Windows zuerst, Linux in Phase 4.

## Phase 3 – Automatisierte Pools (Klone), floating und dedicated

Ziel: die Horizon-Pooltypen „automatisiert, floating“ und „automatisiert, dedicated“.

- Unbeaufsichtigte Template-Erstellung: `autounattend.xml` (lokales Konto, RDP, VirtIO, Guest
  Agent, LibreVDI-Agent „managed“), dokumentiert und skriptbar
- Linked-Clone-Pool mit Windows-OS-Manager (Rename, optional AD-Join), Warm-Pool, Löschen bei
  Abmeldung, Disconnect-/Maximal-Timeouts
- Dedicated-Variante: Klon bleibt beim Benutzer (OS-Manager „behalten“), Energie-Richtlinie
  auch für Klone
- Image-Update per Publikation (neue Template-Version, Klone werden schrittweise ersetzt)
- Domain-Join-Variante (AD im Lab), Profile (FSLogix/Roaming) dokumentieren

## Phase 4 – Linux

- **Linux-Client** (Desktop-App aus Phase 2f bzw. Launcher als Paket für Debian/Ubuntu/Fedora)
- **Linux-Agent** und Linux-Desktops (persistente und geklonte Pools, xrdp)

## Phase 5 – GPU

- **GPU-Unterstützung**: Durchreichen ganzer GPUs (PCI-Passthrough) für persistente Desktops,
  später geteilte GPUs (vGPU/SR-IOV, abhängig von Hardware und Lizenzen); passende
  Protokolleinstellungen (H.264/AVC444)

## Später / eigene Bausteine

- Härtung, MFA/OIDC
- Upstream-Beiträge aus `docs/upstream-notes.md`
