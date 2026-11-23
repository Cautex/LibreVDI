# LibreVDI für Horizon-Kenner

LibreVDI (auf Basis von OpenUDS) nutzt andere Begriffe als kommerzielle VDI-Lösungen wie
Omnissa Horizon, die Logik ist aber sehr ähnlich. Diese Seite übersetzt Begriffe und Pooltypen.

## Begriffe

| Horizon | LibreVDI | Wo in der Verwaltung |
|---|---|---|
| vCenter / Hypervisor | **Anbieter** (Provider), z. B. Proxmox VE | Dienste → Anbieter |
| Pool-Definition (VMs, Golden Image, Klon-Art) | **Dienst** (Service) unter dem Anbieter | Dienste → Anbieter → Dienste |
| Desktop-Pool | **Service-Pool** (Dienst + Transporte + Gruppen) | Pools → Service-Pools |
| Entitlement (Berechtigung) | **Gruppen** am Service-Pool | Service-Pool → Gruppen |
| Anpassung der Klone (QuickPrep/Sysprep) | **OS-Manager** (Umbenennen, Domäne, Verhalten bei Abmeldung) | Dienste → OS-Manager |
| Protokoll (Blast, PCoIP, RDP) | **Transport** (RDP direkt, RDP getunnelt, …) | Konnektivität → Transporte |
| Unified Access Gateway | **Tunnel** (optional) bzw. Reverse Proxy | [tunnel.md](tunnel.md) |
| Connection Server | **Broker** (Docker-Stack) | – |
| Horizon Client | **LibreVDI Client** | Portal → „LibreVDI Client“ |
| Horizon Agent | **LibreVDI Agent** (managed / unmanaged) | Downloads (Admin) |
| Golden Image / Snapshot, „Push Image“ | Template + **Publikation** (neue Version ausrollen) | Service-Pool → Publikationen |
| Spare (bereitgehaltene) Maschinen | **Cache** (L1) | Service-Pool → Cache |
| Benutzer zuweisen (dedicated) | **Zugewiesene Dienste**, auch manuell | Service-Pool → Zugewiesene Dienste |
| Remote Machine Power Policy | **Energie-Richtlinie** des Dienstes (LibreVDI) | Dienst → Reiter „Erweitert“ |
| Cloud Pod / globale Berechtigung | Meta-Pool (mehrere Pools hinter einer Kachel) | Pools → Meta-Pools |

## Pooltypen

| Horizon-Pool | Zuweisung | LibreVDI-Dienst | OS-Manager | Stand |
|---|---|---|---|---|
| Manuell (vorhandene VMs) | **dedicated** | Proxmox Persistent Desktops (LibreVDI) | keiner | ✅ |
| Manuell (vorhandene VMs) | **floating** | Proxmox Fixed Machines | keiner | ✅ |
| Automatisiert (Klone) | **floating** | Proxmox Linked Clone | Windows, „bei Abmeldung entfernen“ | Phase 3 |
| Automatisiert (Klone) | **dedicated** | Proxmox Linked Clone | Windows, „behalten“ | Phase 3 |

Agent: Bei **manuellen** Pools den Agent **unmanaged** installieren (Token des Dienstes), bei
**automatisierten** Pools den Agent **managed** ins Template (er meldet sich in jedem Klon selbst
an und führt die Anweisungen des OS-Managers aus).

**Instant Clones:** Horizon klont eine laufende VM samt Arbeitsspeicher in Sekunden. Proxmox kann
das nicht; LibreVDI nutzt Linked Clones (Sekunden bis Minuten) und gleicht die Wartezeit mit dem
Cache aus – es liegen immer einige fertige VMs bereit.

## Energie-Richtlinie (persistente Desktops)

Dienst „Proxmox Persistent Desktops (LibreVDI)“ → Reiter **Erweitert**:

| Einstellung „After logoff“ | Wirkung |
|---|---|
| Do nothing (Standard) | VMs bleiben, wie sie sind |
| Shut down machine after delay | VM wird heruntergefahren, wenn ihr Benutzer seit *Shutdown delay* Minuten abgemeldet ist (Gast-Shutdown über ACPI/QEMU-Agent) |
| Keep all machines powered on | alle VMs des Dienstes werden eingeschaltet gehalten |

In allen Fällen gilt: Ist die VM aus, wenn sich ihr Benutzer verbindet, **startet LibreVDI sie**
und wartet, bis der Agent bereit ist (etwa 1–2 Minuten). Nur *getrennte* Sitzungen (Fenster
geschlossen ohne Abmelden) gelten weiter als „in Benutzung“ und werden nicht heruntergefahren.
Die Prüfung läuft alle zwei Minuten; die Aktionen stehen im Log des Dienstes bzw. der Zuweisung.

**Wartung an den VMs** (z. B. Agent aktualisieren über die Proxmox-Konsole): den **Anbieter in den
Wartungsmodus** setzen (Dienste → Anbieter → Wartung). Solange greift die Energie-Richtlinie nicht
und Benutzer können sich nicht verbinden – wie der Wartungsmodus bei Horizon.

Benötigt das Proxmox-Recht `VM.PowerMgmt` (in der Rolle aus [test-phase1.md](test-phase1.md) enthalten).

## Was (noch) fehlt

| Thema | Stand |
|---|---|
| Protokoll für schwache Leitungen (wie Blast) | RDP mit H.264; gut im LAN, schwächer über WAN |
| Desktop-App mit Desktop-Liste | Roadmap |
| Automatisierte Pools (Klone) | Phase 3 |
| GPU / vGPU | Roadmap |
| Linux-Client, Linux-Desktops (Agent) | Roadmap |
| Profile / Apps (DEM, App Volumes) | FSLogix oder servergespeicherte Profile, zu dokumentieren |
| Hochverfügbarkeit mehrerer Broker | technisch möglich (gemeinsame Datenbank), nicht eingerichtet |
