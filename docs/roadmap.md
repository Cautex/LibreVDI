# Roadmap

Stand: 22.11.2026, nach dem ersten erfolgreichen Lab-Test (Phase-2-MVP: Portal → persistenter
Windows-11-Desktop per RDP). Reihenfolge innerhalb einer Phase = vorgeschlagene Priorität.

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

- **Linux-Client** (Launcher für Debian/Ubuntu/Fedora als Paket; Upstream liefert die Bausteine)
- **Linux-Agent** und Linux-Desktops (persistente und geklonte Pools, xrdp)

## Phase 5 – GPU

- **GPU-Unterstützung**: Durchreichen ganzer GPUs (PCI-Passthrough) für persistente Desktops,
  später geteilte GPUs (vGPU/SR-IOV, abhängig von Hardware und Lizenzen); passende
  Protokolleinstellungen (H.264/AVC444)

## Später / eigene Bausteine

- **LibreVDI Desktop-App für Windows** (wie der native Horizon Client): Server eintragen,
  anmelden, Desktops als Liste, Doppelklick verbindet – ohne Browser. Vorher prüfen, welche
  Broker-API dafür nutzbar ist (Spike), dann eigene App auf Basis der Upstream-Rust-Bausteine.
- Navigation, Übersichten und Wording der Admin-Oberfläche überarbeiten (z. B. „Zugewiesene
  Dienste“: verständliche Spalten und Status, Actor-Version) – eigenes Thema, später
- Härtung, MFA/OIDC
- Upstream-Beiträge aus `docs/upstream-notes.md`
