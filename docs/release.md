# Releases

Ablauf und Hintergründe: [ADR-0007](adr/0007-releases.md).

## Für Betreiber: Release installieren

In `.env` die Images des Releases eintragen (statt selbst zu bauen):

```bash
LIBREVDI_BROKER_IMAGE=ghcr.io/<owner>/librevdi-broker:0.2.0
LIBREVDI_TUNNEL_IMAGE=ghcr.io/<owner>/librevdi-tunnel:0.2.0   # nur mit --profile tunnel
```

```bash
git checkout v0.2.0              # compose.yaml, Caddyfiles und Doku zur Version
docker compose pull
docker compose up -d --no-build  # ggf. --profile tunnel
```

Die Windows-Installer (Client, Agent managed/unmanaged) sind im Broker-Image enthalten und
erscheinen ohne weiteren Schritt im Portal („Launcher“) und in der Admin-Oberfläche. Einzeln
gibt es sie als Assets am GitHub-Release, mit `SHA256SUMS`:

```bash
sha256sum -c SHA256SUMS --ignore-missing
```

Ein eigenes `./downloads` auf dem Host (z. B. neuere CI-Builds, `tools/fetch-windows-builds.sh`)
hat Vorrang vor den mitgelieferten Installern.

**Hinweis:** Die Installer sind noch nicht code-signiert. Windows SmartScreen zeigt beim ersten
Start „Der Computer wurde durch Windows geschützt“ → *Weitere Informationen* → *Trotzdem
ausführen*. In Firmen per Softwareverteilung installieren oder den Hash freigeben.

## Für Maintainer: Release erstellen

1. `CHANGELOG.md`: Abschnitt `## [Unreleased]` in `## [0.2.0] – JJJJ-MM-TT` umbenennen
   (wird zu den Release-Notes), neuen leeren `[Unreleased]`-Abschnitt anlegen, committen.
2. Tag setzen und pushen:
   ```bash
   git tag -a v0.2.0 -m "LibreVDI 0.2.0"
   git push origin v0.2.0
   ```
3. Workflow **Release** abwarten (Windows-Builds bei leerem Cache ca. 1–2 h, sonst ca. 30 min):
   baut Installer und Images, testet die Images, pusht sie nach GHCR und legt einen
   **Release-Entwurf** an.
4. Prüfen: Entwurf unter *Releases*, Assets und Notes; optional Installer im Lab testen.
5. **Veröffentlichen:** Entwurf → *Publish release*.
6. Nur beim ersten Release: unter *Packages* → `librevdi-broker` bzw. `librevdi-tunnel` →
   *Package settings* → *Change visibility* → **Public**, und das Paket mit dem Repository
   verknüpfen (geschieht über das Image-Label `org.opencontainers.image.source` automatisch).

Vorabversionen (`v0.2.0-rc.1`) werden als *Pre-release* markiert und setzen kein `latest`-Tag.

**Probelauf ohne Veröffentlichung:** *Actions → Release → Run workflow* (auf dem
Standard-Branch) oder jede Änderung an `release.yml` auf einem Entwicklungs-Branch. Ergebnis:
Artefakt `release-dryrun-<version>` mit allen Assets; nichts wird gepusht oder veröffentlicht.

Ein fehlgeschlagener Release lässt sich wiederholen: Entwurf (falls angelegt) löschen,
*Re-run failed jobs* oder Tag neu setzen (`git push --delete origin v0.2.0`, dann erneut).
