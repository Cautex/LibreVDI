# Installation (Docker Compose)

> Stand: Phase 1. Broker, Admin-Oberfläche und Benutzerportal laufen. Proxmox-Anbindung,
> Agent-Pakete und Tunnel folgen in Phase 2.

## Voraussetzungen

- Linux-Host mit Docker Engine ≥ 24 und dem Compose-Plugin (`docker compose`)
- mindestens 2 vCPU, 4 GB RAM, 20 GB Speicher
- ein DNS-Name für den Broker (z. B. `vdi.lab.example`), der auf den Host zeigt
- Ports 80 und 443 frei (oder andere Ports in `.env` setzen)

## 1. Repository holen

```bash
git clone --recurse-submodules https://github.com/Cautex/LibreVDI.git
cd LibreVDI
```

Bereits ohne Submodule geklont? `git submodule update --init`.

## 2. Konfiguration

```bash
cp .env.example .env
```

In `.env` **alle** Platzhalter ersetzen:

| Variable | Bedeutung |
|---|---|
| `LIBREVDI_DOMAIN` | DNS-Name des Brokers |
| `LIBREVDI_TLS` | `internal` (selbstsigniertes Zertifikat aus Caddys lokaler CA, für Lab/LAN) oder eine E-Mail-Adresse für Let's Encrypt (öffentlicher DNS-Name nötig) |
| `POSTGRES_PASSWORD` | langes Zufallspasswort, z. B. `openssl rand -base64 32` |
| `LIBREVDI_ROOT_PASSWORD` | Passwort des Super-Users `root` der Admin-Oberfläche |

Optionale Variablen stehen kommentiert in `.env.example` (Zeitzone, Sprache, Log-Format `json`,
Ports, internes Netz).

Die `.env` enthält Geheimnisse: Rechte auf `600` setzen und nie einchecken (steht in `.gitignore`).

## 3. Bauen und starten

```bash
docker compose build        # baut das Broker-Image (einige Minuten)
docker compose up -d
docker compose ps           # broker-web, broker-tasks und postgres sollten "healthy" sein
```

Beim ersten Start erledigt `broker-init`:

1. erzeugt `SECRET_KEY` und den RSA-Schlüssel unter `/var/lib/uds/keys` (Volume `broker-data`)
2. legt die Datenbank an bzw. migriert sie
3. setzt das Root-Passwort aus `.env` (bei jedem Start – `.env` ist führend)
4. setzt einmalig Standardwerte: Name „LibreVDI“, Proxy-Erkennung, IP-Sperre nach Fehlversuchen

Test: `tests/smoke.sh` prüft Seiten, Login und Container-Health.

## 4. Erste Anmeldung

`https://<LIBREVDI_DOMAIN>/` öffnen, mit `root` und dem Passwort aus `.env` anmelden.
Die Verwaltung erreicht man über das Benutzermenü oder direkt unter `/uds/adm/`.

Bei `LIBREVDI_TLS=internal` warnt der Browser vor dem Zertifikat. LibreVDI liefert die Root-CA
unter `https://<LIBREVDI_DOMAIN>/ca.crt` aus. Import auf Windows (als Administrator):

```powershell
curl.exe -k -o $env:TEMP\librevdi-ca.crt https://<LIBREVDI_DOMAIN>/ca.crt
certutil -addstore -f Root $env:TEMP\librevdi-ca.crt
```

Alternativ direkt vom Docker-Host kopieren:

```bash
docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt ./librevdi-root-ca.crt
```

Ohne jeden Import geht es mit einem öffentlich gültigen Zertifikat: `LIBREVDI_TLS` auf eine
E-Mail-Adresse setzen (Let's Encrypt, DNS-Name muss öffentlich auflösbar und Port 80/443 von
außen erreichbar sein) oder LibreVDI hinter einen vorhandenen Reverse Proxy mit gültigem
Zertifikat stellen.

## 5. Empfohlene Härtung nach der Einrichtung

Diese Punkte meldet auch der Sicherheitscheck im Dashboard:

- **Root-Zugang über Web/API abschalten**, sobald ein Authenticator (z. B. LDAP/AD) und
  Administratoren eingerichtet sind: Konfiguration → Security → *Allow root web access* = 0.
- **Trusted Sources** auf die eigenen Netze beschränken (Agent-VMs, Tunnel, Admin-Netz):
  Konfiguration → Security → *Trusted Hosts* / *Admin Trusted Sources*.
- **Unveränderliches Audit-Log** (*Enable immutable log*) nur einschalten, wenn der Broker einen
  RFC-3161-Zeitstempeldienst erreicht – sonst schlagen Logins fehl
  (siehe [upstream-notes.md](upstream-notes.md)).

## Datensicherung

Zu sichern sind **beide**:

```bash
# Datenbank
docker compose exec -T postgres pg_dump -U librevdi librevdi | gzip > librevdi-db.sql.gz
# Schlüssel (ohne sie sind verschlüsselte Felder, z. B. Hypervisor-Zugangsdaten, unlesbar)
docker compose cp broker-web:/var/lib/uds/keys ./librevdi-keys
```

Schlüssel-Backup sicher und getrennt aufbewahren.

## Aktualisieren

```bash
git pull --recurse-submodules
docker compose build
docker compose up -d        # broker-init migriert die Datenbank automatisch
```

Vorher eine Datensicherung machen.

## Fehlersuche

- `docker compose logs broker-init` – Schlüssel, Migrationen, Konfiguration
- `docker compose logs -f broker-web broker-tasks`
- Liveness/Readiness im Container: `docker compose exec broker-web python -m librevdi_ext.healthcheck`

## Hinweis Windows-Lizenzierung

Für Windows-Desktops in einer VDI sind passende Microsoft-Lizenzen nötig (z. B. Windows VDA bzw.
Microsoft 365 E3/E5 mit VDA-Rechten, für Windows Server zusätzlich RDS-CALs). Die Lizenzierung
liegt beim Betreiber und ist nicht Teil von LibreVDI.
