# ADR-0003: Betrieb als Docker-Compose-Stack mit PostgreSQL

- **Status:** angenommen (22.11.2026)
- **Kontext:** Der Auftrag verlangt den Broker als Docker-Container mit Postgres, Konfiguration
  über Umgebungsvariablen, Healthchecks, strukturierte Logs und keinen Zustand nur im Speicher.
  OpenUDS wird offiziell auf Ubuntu mit MySQL installiert und schreibt Log-Dateien.

## Entscheidung

- **Broker-Image** (`docker/broker/Dockerfile`) auf **Ubuntu 24.04 LTS** (Python 3.12), so nah
  wie möglich an der von Upstream dokumentierten Plattform; 5 Jahre Sicherheitsupdates.
- **Einstellungs-Overlay** (`docker/broker/settings.py`): lädt Upstreams `settings.py.sample`
  unverändert und überschreibt nur Container-relevante Werte. Upstream-Code wird nicht verändert.
- **Ein Image, drei Rollen:** `init` (Schlüssel, Migrationen, Konfiguration – idempotent),
  `web` (daphne/ASGI) und `tasks` (Task-Manager für Warm-Pool, Aufräumen, Timeouts).
- **PostgreSQL 17** als Datenbank. Der GPL-lizenzierte MySQL-Treiber wird nicht installiert.
- **memcached** als gemeinsamer Cache zwischen `web` und `tasks`.
- **Caddy** als Reverse Proxy mit TLS (lokale CA für Lab/LAN oder Let's Encrypt).
- **Schlüssel** (`SECRET_KEY`, RSA-Schlüssel für verschlüsselte DB-Felder) werden beim ersten
  Start erzeugt und auf dem Daten-Volume abgelegt oder per `*_FILE`/Umgebungsvariable gesetzt.
- **Logs** nach stdout (Text oder JSON), **Health** über `/healthz` und `/readyz`
  (eigene Middleware vor den Upstream-Middlewares; von außen über Caddy gesperrt).

## Konsequenzen

- Image ist groß (~1,4 GB), weil Upstream viele Bibliotheken für alle Hypervisoren und Berichte
  mitbringt. Optimierung später möglich.
- Der Tunnel-Server wird erst in Phase 2 eingebunden (braucht Registrierung beim Broker und
  vertrauenswürdiges TLS zwischen Tunnel und Broker).
- Mehrere `web`-Instanzen sind möglich (Zustand in Postgres/memcached); HA ist nicht Teil von V1.
