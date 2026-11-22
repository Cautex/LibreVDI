# 00 – Entscheidung: Fork, Neubau oder Hybrid

| | |
|---|---|
| **Status** | **Entschieden (22.11.2026): Option A2 – Distribution auf Basis von OpenUDS 5.0.** Siehe [ADR-0001](adr/0001-basis-openuds-distribution.md) bis [ADR-0005](adr/0005-sprachen.md). |
| **Stand der Recherche** | 21.11.2026 |
| **Methode** | Repos geklont und gelesen (Lizenzdatei, Git-Historie der letzten 12 Monate, Struktur, Stichproben im Code), ergänzend GitHub-Suche. Nur offener Quellcode, keine proprietären Binaries. |

> **Ergebnis der Rückfragen (22.11.2026):** Option **A2** (LibreVDI als Distribution auf
> OpenUDS **v5.0**), Lizenz **BSD-3-Clause**, Mandantenfähigkeit später per Instanz pro Mandant,
> MVP-Client: Portal + `.rdp`/Launcher, Name **LibreVDI**. Die Empfehlung „Option C“ in den
> Abschnitten 1–6 ist damit überholt und bleibt nur zur Nachvollziehbarkeit stehen.

## 1. Kurzfassung (ursprünglicher Vorschlag)

**Empfehlung: Option C (Hybrid).** Wir bauen einen eigenen, schlanken Broker und einen eigenen Agent, die genau auf Proxmox und unsere Anforderungen zugeschnitten sind. Für alles, was es schon gut und offen lizenziert gibt, bauen wir nichts selbst: RDP-Gateway, HTML5-Gateway, RDP-Clients, Proxmox-API-Bibliothek, Gast-Personalisierung. openUDS dient als Referenz für bewährte Konzepte (Warm-Pool-Cache, Publikationen, OS-Manager). Wegen der BSD-3-Lizenz dürfen wir dort einzelne Teile mit Namensnennung übernehmen.

Damit das ehrlich bleibt: **openUDS 5.0 erfüllt heute schon rund 80 % des Auftrags** (Proxmox Linked Clones, Warm-Pool, persistente Desktops, Abmelden → Löschen, Windows- und Linux-Agent in Rust, LDAP/SAML/OAuth2/MFA, BSD-3). Wenn das Hauptziel ist, im Lab oder in der Firma *schnell* eine funktionierende VDI zu haben, ist **openUDS direkt einsetzen (ohne Fork)** der günstigste Weg. Ein eigenes Projekt lohnt sich, wenn du eine eigene, Docker-native und schlanke Plattform willst, die du vollständig verstehst und steuerst. Das gilt auch als Studien- oder Abschlussarbeitsprojekt oder als spätere Produktbasis.

## 2. Bewertung der Kandidaten

Legende: ✅ gut · ⚠️ eingeschränkt · ❌ nicht vorhanden/ungeeignet

| Kandidat | Lizenz | Aktivität (12 Mon.) | Proxmox | Persistent / Floating | Win / Linux | Eignung |
|---|---|---|---|---|---|---|
| **openUDS** (Broker, Actor, Client, Tunnel, GUI) | BSD-3-Clause ✅ | sehr aktiv: Broker ~1.420 Commits, 9 Autoren (fast alle vom Hersteller Virtual Cable) | ✅ Linked/Full Clone, Fixed-Services | ✅ / ✅ (Cache L1/L2 = Warm-Pool) | ✅ / ✅ | **Referenz und Ideenquelle**, Fork möglich (siehe 4.1) |
| **IsardVDI** | AGPL-3.0 | sehr aktiv: ~4.900 Commits, 23 Autoren | ❌ eigener KVM/libvirt-Stack | ✅ / ⚠️ | ✅ / ✅ | ❌ als Basis (kein Proxmox), Ideen für GPU und Admin-UI |
| **Kasm Workspaces CE** | Workspaces selbst **proprietär** (kostenlose Lizenz, kein Quellcode). Offen sind nur KasmVNC (GPL-2.0) und Images (MIT) | aktiv | ⚠️ (nicht geprüft, closed source) | Container-Fokus | ⚠️ / ✅ | ❌ als Basis. KasmVNC optional als Linux-Protokoll |
| **Apache Guacamole** | Apache-2.0 ✅ | aktiv: ~230 Commits, 26–28 Autoren, Release 1.6.0 | – (Gateway) | – | RDP/VNC/SSH | ✅ **Baustein**: HTML5-Gateway |
| **osvdi** (Uni Freiburg) | Apache-2.0 | gering (4 Commits) | ❌ (OpenStack) | – | – | Kein Code, nur Doku, Ansible und Paper. **Ideenquelle für V2/GPU** (mdev, SPICE mit HW-Encoding) |
| **OpenDesk VDI** | AGPL-3.0 (Haupt-Repo). **Backend-Repo ohne Lizenzdatei** ⚠️ | 1 Autor, 12 Commits/Repo, seit 06/2026 | ✅ (Clone über PVE-API) | ✅ / ❓ | ✅ / ⚠️ (Kylin/UOS) | ❌ als Basis: Node.js, ~10k LOC, keine Tests, kein Agent, keine Instant Clones. Lizenz des Backends unklar |
| **openVDI** (PAzter1101) | **keine Lizenz** ❌ | inaktiv seit 05/2025, 10 Commits | ✅ (Python, Guacamole) | ⚠️ „Buffers“ ≈ Warm-Pool | – | ❌ ohne Lizenz rechtlich nicht nutzbar, nur Idee |
| **PVE-VDIClient** | Apache-2.0 | gering, 1 Autor | ✅ direkt (SPICE) | ❌ kein Broker | Client: Win/Linux | Ideenquelle Client (Python, ~1.100 LOC) |
| **Ravada** (UPC, gefunden) | AGPL-3.0 | aktiv: 95 Commits, 7 Autoren | ❌ KVM/libvirt | ✅ / ✅ | ✅ / ✅ | ❌ als Basis (Perl, kein Proxmox) |
| **Multitap** (gefunden) | AGPL-3.0 | 10 Tage alt, 1 Autor | ✅ (nur Zuweisung) | ⚠️ nur persistent, keine Pools | Win / ❌ | ❌ (zu jung, eigenes Streaming-Protokoll) |
| **pxvdi** (gefunden) | **keine Lizenz** | 2 Autoren | ✅ | ? | ? | ❌ Repo enthält nur Doku |
| **Deskpool** | proprietär (Marktvergleich) | – | ✅ laut Hersteller | ✅ | ✅ | ❌ nur Marktvergleich, nicht weiter geprüft |

### 2.1 openUDS im Detail (stärkster Kandidat)

- **Aufbau (Version 5.0, master):** Meta-Repo mit Submodulen `broker` (Python 3.11+/Django 6.1, ~147k LOC, ~520 Testdateien), `uds-actor` (Rust, Windows/Linux/macOS), `uds-client` (Rust-Launcher), `uds-tunnel-server` (Rust), `openuds-gui` (Angular). Alles BSD-3.
- **Proxmox-Treiber:** eigener REST-Client (`services/Proxmox/proxmox/client.py`), Linked Clone nur von Templates, sonst Full Clone im Format qcow2. Dazu „Fixed“-Services für persistente VMs.
- **Pool-Logik:** Cache-Level L1 (laufende VMs) und L2 (z. B. suspendierte VMs), „Publications“ (Master-Version des Templates), OS-Manager mit „bei Abmeldung entfernen/behalten“. Das entspricht genau unseren Instant-Clone-/Warm-Pool-Anforderungen.
- **Auth:** InternalDB, SimpleLDAP, RegexLdap, SAML, OAuth2, Radius, IP, X.509, dazu MFA-Module.
- **Transports:** RDP, HTML5-RDP (über Guacamole), SPICE, X2Go und das neue eigene „UDS Remote Protocol“.
- **Schwächen für unseren Zweck:** Django-Monolith mit 9 Hypervisor-Treibern und sehr vielen Features, die wir nicht brauchen. Standard-DB ist MySQL (Konfiguration über `settings.py.sample`), Docker ist nicht der vorgesehene Betriebsweg. Die Entwicklung wird fast nur vom Hersteller getragen (UDS Enterprise ist die kommerzielle Version) und ändert sich sehr schnell. Ein Fork würde schnell abdriften, und Upstream-Merges wären teuer. Außerdem müssten die Marke „UDS“ und die Logos überall entfernt werden.

## 3. Wiederverwendbare Bausteine (alle geprüft: Lizenz und Aktivität)

| Baustein | Zweck bei uns | Lizenz | Stand |
|---|---|---|---|
| **rdpgw** (bolkedebruin) | RDP-Gateway (MS-TSGU über HTTPS) in Go. Unterstützt Gateway-Access-Tokens (PAA) in `.rdp`-Dateien. Damit reicht **mstsc.exe** als Client, ohne eigene Installation | Apache-2.0 | aktiv, 9 Autoren |
| **Apache Guacamole** | HTML5-Client (Web-Client) als Protokoll-Plugin | Apache-2.0 | aktiv, 1.6.0 |
| **FreeRDP** / **IronRDP** | RDP-Client unter Linux/macOS bzw. Rust-RDP für einen späteren eigenen Client | Apache-2.0 / Apache-2.0 (+MIT) | sehr aktiv |
| **xrdp** | RDP-Server für Linux-Desktops, damit überall dasselbe Protokoll läuft | Apache-2.0 | sehr aktiv |
| **go-proxmox** / **proxmox-api-go** | Proxmox-REST-Client in Go | Apache-2.0 / MIT | aktiv |
| **cloudbase-init** / cloud-init | Personalisierung von Klonen (Hostname, Netzwerk, Skripte) | Apache-2.0 | aktiv |
| **Sunshine/Moonlight**, **Selkies** | V2: GPU-Streaming | GPL-3.0 bzw. MPL-2.0 (als getrennter Prozess bzw. Plugin nutzbar) | aktiv |
| openUDS (Teile) | z. B. Proxmox-Sonderfälle, Ideen für den Credential Provider (`win-credentials-provider`, BSD-3) | BSD-3 | aktiv |

## 4. Optionen

### 4.1 Option A – openUDS forken

- **Pro:** sofort sehr großer Funktionsumfang, ausgereifte Pool-/Cache-Logik, Rust-Agent und Rust-Client vorhanden, permissive Lizenz.
- **Contra:** ~150k LOC fremde Python/Django-Codebasis plus Rust und Angular, also drei Technologien und viel Wartung für ein kleines Team. Ein schnell laufender, herstellergetriebener Upstream bedeutet einen dauerhaften Merge-Aufwand oder ein hartes Abdriften. Komplettes Rebranding nötig. Docker und Postgres müssten nachgerüstet werden. Die Architektur liegt fest (Monolith, eigenes Protokoll). Echter eigener Mehrwert ist schwer darzustellen („noch ein UDS“).
- **Variante A′:** openUDS unverändert einsetzen und nur Docker-Packaging bzw. Doku beitragen. Das ist der schnellste Weg zu einer nutzbaren VDI, aber kein eigenes Projekt.

### 4.2 Option B – kompletter Neubau

- **Pro:** volle Kontrolle, saubere Architektur nach Auftrag (Docker, Postgres, OpenAPI, Treiber- und Protokoll-Plugins).
- **Contra:** Wir würden auch Dinge neu bauen, die es offen schon gibt (Gateway, HTML5, Clients). Das ist unnötiger Aufwand und mehr Sicherheitsrisiko.

### 4.3 Option C – Hybrid (**empfohlen**)

Eigener Code nur dort, wo der Mehrwert liegt:

| Eigenentwicklung | Übernommen bzw. integriert |
|---|---|
| Broker (Auth, Pools, Zuweisung, Lifecycle/Reconciler, REST-API, Audit) | rdpgw als RDP-Gateway (Sidecar-Container, Tokens vom Broker) |
| Hypervisor-Treiber-Interface + Proxmox-Treiber + Mock | go-proxmox bzw. proxmox-api-go als API-Client |
| Agent (Windows/Linux): Heartbeat, Session-Events, Befehle | cloudbase-init/cloud-init für die Erstpersonalisierung |
| Admin-UI (Svelte) über die Broker-API | Guacamole als HTML5-Protokoll-Plugin (später) |
| Später: dünner Windows-Client (Login, Desktop-Liste, Start) | mstsc.exe / FreeRDP als eigentlicher RDP-Viewer |

**Wesentlicher Vorteil für das MVP (Phase 2):** Mit rdpgw braucht es zunächst **keinen eigenen Client**. Der Benutzer meldet sich im Web-Portal an, wählt einen Desktop und bekommt eine `.rdp`-Datei mit Einmal-Gateway-Token, die das eingebaute `mstsc.exe` öffnet. Den nativen Client bauen wir danach als Komfortschicht (URI-Handler `librevdi://`, Desktop-Liste, Auto-Reconnect).

## 5. Vorschläge zu den offenen Punkten (endgültig erst nach deiner Freigabe bzw. als ADR in Phase 1)

1. **Sprache Broker: Go.** Gründe: rdpgw ist selbst in Go (gemeinsame Token-Logik, ggf. später einbettbar). Es gibt reife, permissiv lizenzierte Bibliotheken für Proxmox, LDAP (go-ldap), OIDC (go-oidc), Postgres (pgx) und Prometheus. Ein statisches Binary ergibt ein kleines Docker-Image, Goroutines passen gut zu Reconcile-Loops (Warm-Pool nachfüllen, Timeouts). Go ist leicht lesbar und gut wartbar für ein kleines Team. Rust wäre technisch genauso möglich, kostet bei einem API- und CRUD-lastigen Broker aber deutlich mehr Entwicklungszeit. Python/Django würde nur bei einem openUDS-Fork Sinn ergeben.
2. **Sprache Agent: ebenfalls Go**, *ein* Workspace mit gemeinsamem Core und plattformspezifischen Dateien (`_windows.go` / `_linux.go`). Windows-Dienst über `x/sys/windows/svc`, Session-Events über WTS-APIs. Vorteil: eine Sprache im ganzen Stack, gemeinsame API-Typen aus OpenAPI generiert. Binary ca. 8–10 MB statt ca. 2 MB bei Rust, was für eine VM unkritisch ist. **Rust nur dort, wo eine native Windows-DLL nötig ist** (Credential Provider für SSO, spätere Phase).
3. **Display-Protokoll V1:** RDP für alles (Windows nativ, Linux über xrdp) über rdpgw. HTML5 über Guacamole als zweites Plugin. Die Protokoll-Schnittstelle wird von Anfang an so geschnitten, dass in V2 Sunshine/Moonlight, Selkies oder SPICE dazukommen können.
4. **Lizenz des Projekts:** Vorschlag **Apache-2.0**. Sie ist permissiv, enthält einen Patent-Grant und ist identisch mit rdpgw, Guacamole, FreeRDP, IronRDP und xrdp. BSD-3-Code aus openUDS darf mit Hinweis übernommen werden. Alternative: **AGPL-3.0**, falls du verhindern willst, dass jemand das Projekt als geschlossenen SaaS-Dienst weiterverkauft. Damit dürften wir aber AGPL-Code (IsardVDI, OpenDesk) übernehmen, nicht aber umgekehrt. → **Deine Entscheidung.**
5. **Projektname:** „LibreVDI“. Auf GitHub gibt es keine Kollision (nur dieses Repo). Eine Marken- bzw. Domainprüfung habe ich nicht gemacht. Falls der Name öffentlich werden soll, bitte kurz beim DPMA/EUIPO prüfen.
6. **Mandantenfähigkeit:** Vorschlag: im Datenmodell ab Phase 1 eine `organization_id` an allen Kernobjekten (mit genau einer Standard-Organisation). Funktion und UI kommen erst später (Phase 6/7). Das kostet jetzt fast nichts, nachträglich einzubauen wäre teuer. → **Deine Entscheidung** (schwer rückgängig zu machen).
7. **Web-Client:** ja, über Guacamole. Technisch frühestens ab Phase 4 sinnvoll, Vorschlag Phase 6/7.
8. **Instant Clones auf Proxmox:** Linked Clones brauchen ein Template auf Storage mit Snapshot- bzw. Clone-Support (LVM-thin, ZFS, Ceph RBD, qcow2 auf Directory/NFS), sonst gibt es einen Full Clone. Personalisierung: Hostname und Netz über cloudbase-init bzw. cloud-init (Proxmox-Cloud-Init-Laufwerk). Domain-Join bevorzugt als **Offline Domain Join** (`djoin`-Blob, vom Broker erzeugt und vom Agent angewendet), weil das schneller und robuster ist als ein Join beim Boot. Profile über FSLogix/Roaming/Netzlaufwerk (wird dokumentiert). Details folgen als ADR in Phase 3.
9. **Windows-Lizenzierung** (VDA bzw. RDS-CALs/Windows Server) wird in der Doku als Betreiberpflicht erwähnt. Das ist nicht Teil der Software.

## 6. Grobe Zielarchitektur bei Option C

```
           ┌────────────── Docker-Host (compose) ──────────────┐
 Browser ──┤ Reverse Proxy (TLS) ─┬─ Broker (Go, REST/OpenAPI)  │
 Client  ──┤                      ├─ Admin-/User-UI (Svelte)    │
 mstsc   ──┤                      ├─ rdpgw (RDP-Gateway)        │
           │                      └─ (später) guacd + Web-Client│
           │  Postgres                                         │
           └─────────────┬─────────────────────────────────────┘
                         │ Proxmox-REST-API (API-Token)
                ┌────────┴────────┐
                │  Proxmox VE     │  VMs mit Agent (Go) ──HTTPS+Token/mTLS──► Broker
                └─────────────────┘  RDP 3389 nur vom Gateway erreichbar
```

## 6a. openUDS gegen den Auftrag (Nachtrag nach Rückfrage, 21.11.2026)

Am Code geprüft (Branch master/v5.0). ✅ vorhanden · ⚠️ teilweise/unklar · ❌ fehlt

| Anforderung | openUDS | Beleg / Anmerkung |
|---|---|---|
| Persistente Desktops auf Proxmox | ✅ | `ProxmoxServiceFixed` („Proxmox Fixed Machines“) |
| Instant Clones / Floating | ✅ | `ProxmoxService` mit Linked Clone und Publications (Master-Version) |
| Warm-Pool + automatisches Nachfüllen | ✅ | Cache L1 (laufend) / L2 (z. B. suspendiert), Mindest- und Maximalanzahl |
| Löschen bei Abmeldung, Idle-/Unused-Timeout | ✅ | OS-Manager `on_logout`, `Max.Idle time`, `handle_unused` |
| Maximaldauer einer Session | ⚠️ | über Kalender-/Zugriffsregeln möglich, Detail nicht verifiziert |
| Proxmox per API-Token | ✅ | Option „Use API Token“ im Provider |
| Personalisierung: Rename, AD-Join (Windows/Linux), Zufallspasswort | ✅ | `WinDomainManager`, `LinuxADManager`, `*RandomPasswordManager` |
| Agent Windows + Linux | ✅ | `uds-actor` in Rust, Builds für Windows/Linux/macOS |
| Client Windows (+Linux/macOS) | ✅ | `uds-client` (Rust-Launcher) |
| Web-Client (HTML5) | ✅ | Transport HTML5-RDP/SSH über Guacamole |
| Tunnel/Gateway | ✅ | `uds-tunnel-server` (Rust, mit Dockerfile) |
| LDAP/AD, SAML, OAuth2, Radius, X.509 | ✅ | `auths/` |
| MFA (TOTP, E-Mail, SMS, Radius) | ✅ | `mfas/` |
| Admin-UI | ✅ | `openuds-gui` (Angular, BSD-3) |
| REST-API mit OpenAPI | ✅ | `doc/api/rest.yaml`, Generator `genapi` |
| Audit-Log | ⚠️ | Logs + `immutable_log`-Modell vorhanden, Umfang nicht bewertet |
| Deutsche Oberfläche | ✅ | Locale `de` vorhanden |
| CI/Tests | ✅ | GitHub Actions (Tests, CodeQL), ~520 Testdateien |
| GPU (vGPU auf Proxmox) | ⚠️ | Proxmox-Service prüft vGPU-/mdev-Verfügbarkeit. GPU-taugliches Streaming (Sunshine/Selkies) fehlt |
| **Broker als Docker-Container** | ❌ | offizieller Weg: Ubuntu + venv + MySQL (Quickstart „für Lab/PoC“). Docker nur für den Tunnel |
| **Postgres** | ⚠️ | Django-seitig unterstützt, Code kennt `postgresql`. Doku und Standard sind MySQL → testen |
| **Mandantenfähigkeit** | ❌ | kein Organisations-/Mandanten-Modell |
| **Prometheus-Metriken** | ❌ | nur eigene Statistik-Zähler |
| Einfacher Liveness-/Health-Endpoint | ⚠️ | `/system/checks` (Admin-Selbsttest), kein schlanker Healthcheck gefunden |
| Saubere Releases | ⚠️ | stabil ist v4.0. v5.0 (Rust-Agent/-Client) ist Entwicklungsstand ohne Release-Tags |

**Nur in der kommerziellen Enterprise-Version** (abgeleitet aus der mitgelieferten API-Doku, nicht im offenen Code): eigener AD-Authenticator, Azure AD/Entra ID, eDirectory, RDS/RemoteApp-Anwendungsbereitstellung, VMware/Hyper-V/Nutanix/AWS/Azure/GCP, NICE DCV, PCoIP, NoMachine. Für Proxmox-VDI ist davon nur Entra ID ggf. relevant. AD funktioniert auch über die offenen LDAP-Module.

**Community:** 105 Issues insgesamt, nur 4 neue in den letzten 12 Monaten. PRs kommen fast nur vom Hersteller. Das Projekt wird also professionell, aber praktisch von einer Firma entwickelt (Open-Core-Modell).

### 6b. Optionen neu bewertet

| | **A1 – harter Fork** | **A2 – Distribution auf openUDS (upstream-first)** | **C – Hybrid/Neubau** |
|---|---|---|---|
| Idee | openUDS kopieren, umbenennen, eigenständig weiterentwickeln | openUDS fast unverändert nutzen. LibreVDI liefert Docker-Packaging, Proxmox-Automatisierung, Doku (DE/EN) und Zusatzmodule. Änderungen am Kern gehen als PR an Upstream | eigener Broker und Agent, offene Bausteine |
| Weg zum MVP | sofort | sehr kurz (Packaging + Doku) | lang (alles von Grund auf) |
| Wartung | ❌ ~150k LOC allein, Upstream läuft sehr schnell → hartes Abdriften | ✅ Kernwartung macht der Hersteller | ⚠️ alles selbst, aber kleiner Code |
| Eigener Mehrwert | gering | mittel (Betrieb, Proxmox-Fokus, Zusatzfunktionen) | hoch |
| Mandantenfähigkeit | tiefer Umbau im fremden Datenmodell | **Instanz pro Mandant** (eigener Broker-Stack + DB, eigener Proxmox-Pool und API-Token) + später eine Verwaltungsschicht über die REST-APIs | sauber im eigenen Datenmodell |
| Risiko | Abdriften, Rebranding | Abhängigkeit vom Hersteller (Open Core). BSD-Code bleibt aber nutzbar, Fallback zu A1 jederzeit möglich | Aufwand, ein Ein-Personen-Projekt |
| Sprachen | Python, Rust, Angular | Python (Kern-PRs), Rust (Agent/Client), eigene Tools in Python | Go (+ Svelte) |
| Lizenz | BSD-3 (vorgegeben) | BSD-3 (passend zu Upstream) | frei (Apache-2.0) |

**Empfehlung nach Rückfrage: A2.** Sie nutzt die Reife von openUDS und hält den eigenen Wartungsaufwand klein. A1 bleibt trotzdem als Ausweg offen. C lohnt sich nur, wenn das eigene Produkt bzw. das Lernziel im Vordergrund steht.

## 7. Was ich nicht geprüft habe (ehrlich)

- Ich habe keine der Lösungen tatsächlich installiert und betrieben. Die Bewertung beruht auf Code, Struktur und Git-Historie.
- Bei Kasm Workspaces CE und Deskpool habe ich keinen Quellcode gesehen (proprietär). Die Angaben stammen aus meinem Wissensstand bzw. öffentlichen Herstellerangaben.
- Die Codequalität von openUDS und IsardVDI habe ich nur stichprobenartig angesehen, nicht vollständig bewertet.

## 8. Rückfragen (Stopp vor Phase 1)

1. **Option C (Hybrid) freigeben?** Oder doch A (openUDS-Fork) bzw. A′ (openUDS direkt nutzen)?
2. **Lizenz:** Apache-2.0 (Vorschlag) oder AGPL-3.0?
3. **Sprache:** Go für Broker und Agent (Vorschlag) oder Rust für den Agent bzw. für beide?
4. **Mandantenfähigkeit:** `organization_id` im Datenmodell ab Phase 1 vorbereiten (Vorschlag) – ja/nein?
5. **MVP-Client:** In Phase 2 Web-Portal + `.rdp`-Datei für mstsc über rdpgw, den eigenen Windows-Client danach – einverstanden?
6. **Name:** „LibreVDI“ beibehalten?
