# ADR-0007: Releases als Entwurf mit GHCR-Images und gebündelten Installern

- **Status:** angenommen (22.11.2026)
- **Kontext:** Bisher mussten Betreiber das Broker-Image selbst bauen und die Windows-Installer
  mit einem GitHub-Token aus CI-Artefakten holen. Ziel aus Phase 2b: fertige Downloads.
  Der Projektauftrag verlangt, dass nichts ohne Freigabe öffentlich erscheint und Lizenzen
  dokumentiert sind.

## Entscheidung

- **Auslöser:** Git-Tag `v<semver>` (z. B. `v0.2.0`, `v0.2.0-rc.1`). Workflow
  `.github/workflows/release.yml`; ohne Tag (manuell oder Änderung am Workflow) läuft er als
  **Probelauf** ohne Veröffentlichung.
- **Windows:** derselbe Build wie in der CI (`windows-builds.yml` als wiederverwendbarer
  Workflow), mit Release-Version im Dateinamen und in den Windows-Dateieigenschaften.
- **Images:** `ghcr.io/<owner>/librevdi-broker:<version>` und `librevdi-tunnel:<version>`
  (amd64), vor dem Push mit Smoke- und Tunnel-Test geprüft; `latest` nur für finale Versionen.
- **Installer im Broker-Image:** Das Release-Image enthält die Installer seiner Version
  (`/opt/librevdi/bundled-downloads`). Ein auf dem Host befülltes `./downloads` hat Vorrang.
  Damit passen Broker, Client und Agent ohne zusätzlichen Schritt zusammen.
- **GitHub-Release als Entwurf** (Draft) mit Installern, `THIRD-PARTY-NOTICES-*.txt`,
  `THIRD_PARTY.md` und `SHA256SUMS`. Veröffentlichen ist ein bewusster manueller Schritt.
- **Lizenzhinweise** werden beim Build erzeugt (`packaging/windows/collect_licenses.py`): alle zur
  Laufzeit gelinkten Rust-Crates, vcpkg-Bibliotheken, FreeRDP, VC-Laufzeit – mit Lizenztexten,
  im Installer als `THIRD-PARTY-NOTICES.txt`.

## Konsequenzen

- Ein Release = ein Tag; Versionen folgen SemVer, Abschnitt `## [<version>]` im CHANGELOG wird
  zu den Release-Notes.
- GHCR-Pakete sind nach dem ersten Push privat und müssen einmalig auf „public“ gestellt werden.
- Die Windows-Installer sind (noch) nicht code-signiert: Windows SmartScreen warnt beim ersten
  Start. Code-Signing (z. B. über ein OSS-Signierprogramm) ist ein späterer Schritt.
- Nach dem Umzug des Repositorys in eine Organisation ändert sich der Image-Pfad
  (`ghcr.io/<org>/…`); der Workflow leitet ihn aus dem Repository ab.
