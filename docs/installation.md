# Installation (Docker Compose)

> Stand: Phase 2b. Broker, Admin-Oberfläche, Portal, Proxmox-Pools, Windows-Client/-Agent,
> optionaler Tunnel und signierte RDP-Dateien.

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

**Variante A – fertiges Release-Image** (empfohlen, sobald ein Release veröffentlicht ist; enthält
auch die Windows-Installer, siehe [release.md](release.md)):

```bash
git checkout v0.2.0                                   # Version wählen
echo "LIBREVDI_BROKER_IMAGE=ghcr.io/<owner>/librevdi-broker:0.2.0" >> .env
docker compose pull
docker compose up -d --no-build
```

**Variante B – selbst bauen** (Entwicklungsstand):

```bash
docker compose build        # baut das Broker-Image (einige Minuten)
docker compose up -d
```

`docker compose ps`: broker-web, broker-tasks und postgres sollten "healthy" sein.

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

## 4a. Variante: hinter einem vorhandenen Reverse Proxy (z. B. Nginx Proxy Manager)

Hat das Netz bereits einen Reverse Proxy mit **gültigem Zertifikat** (z. B. Wildcard für
`*.int.example.de`), übernimmt dieser TLS. Clients und VMs müssen dann **kein** Zertifikat
importieren.

**1. `.env` auf dem Docker-Host**

```bash
LIBREVDI_DOMAIN=vdi.int.example.de
LIBREVDI_PROXY_CONFIG=Caddyfile.behind-proxy
LIBREVDI_TRUSTED_PROXIES=192.168.1.10/32   # genaue IP des Reverse Proxy
LIBREVDI_HTTP_PORT=8080                    # Port, den der Reverse Proxy anspricht
```

`LIBREVDI_TRUSTED_PROXIES` muss die IP sein, von der der Reverse Proxy den Docker-Host anspricht.
Nur dann sieht LibreVDI die echten Client-IPs (wichtig für Logs und die IP-Sperre nach
Fehlversuchen). **Nicht** `private_ranges` verwenden: Dann könnte jeder LAN-Client eine
beliebige IP vortäuschen. Danach `docker compose up -d --force-recreate proxy broker-web`.

**2. Proxy Host im Nginx Proxy Manager**

| Feld | Wert |
|---|---|
| Domain Names | `vdi.int.example.de` |
| Scheme / Forward Hostname / Port | `http` / IP des Docker-Hosts / `8080` |
| Websockets Support | **an** |
| Block Common Exploits | aus (kann REST-Aufrufe stören) |
| SSL | gültiges Zertifikat (z. B. Wildcard), **Force SSL**, HTTP/2 |

**3. Firewall:** Den HTTP-Port (`8080`) auf dem Docker-Host nur für den Reverse Proxy freigeben.
In diesem Modus behandelt LibreVDI alle Anfragen als HTTPS.

**Prüfen:** `https://vdi.int.example.de/` öffnet ohne Zertifikatswarnung;
`SMOKE_PORT=443 SMOKE_HOST_IP=192.168.1.10 tests/smoke.sh` auf dem Docker-Host
(IP des Reverse Proxy).

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
# Signaturzertifikat für RDP-Dateien (siehe rdp-signing.md)
docker compose cp broker-web:/var/lib/uds/rdp-signing ./librevdi-rdp-signing
```

Schlüssel-Backup sicher und getrennt aufbewahren.

## Aktualisieren

```bash
# Release-Image: Version in .env (LIBREVDI_BROKER_IMAGE) anpassen, dann
git fetch --tags && git checkout v<neue Version>
docker compose pull && docker compose up -d --no-build

# selbst gebaut:
git pull --recurse-submodules
docker compose build
docker compose up -d        # broker-init migriert die Datenbank automatisch
```

Vorher eine Datensicherung machen.

## Fehlersuche

- `docker compose logs broker-init` – Schlüssel, Migrationen, Konfiguration, Selbsttest
  (`librevdi: selfcheck …/… ok`; bei `FAIL` hat ein OpenUDS-Update eine LibreVDI-Erweiterung
  gebrochen, siehe ADR-0008 – vorübergehend `LIBREVDI_SELFCHECK=warn` in `.env`)
- Selbsttest von Hand: `docker compose exec broker-web python -m librevdi_ext.selfcheck`
- `docker compose logs -f broker-web broker-tasks`
- Liveness/Readiness im Container: `docker compose exec broker-web python -m librevdi_ext.healthcheck`

## Hinweis Windows-Lizenzierung

Für Windows-Desktops in einer VDI sind passende Microsoft-Lizenzen nötig (z. B. Windows VDA bzw.
Microsoft 365 E3/E5 mit VDA-Rechten, für Windows Server zusätzlich RDS-CALs). Die Lizenzierung
liegt beim Betreiber und ist nicht Teil von LibreVDI.
