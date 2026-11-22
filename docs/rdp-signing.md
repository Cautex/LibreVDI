# Signierte RDP-Dateien

Windows warnt beim Öffnen unsignierter `.rdp`-Dateien („Unbekannter Herausgeber“). LibreVDI kann
die Dateien signieren, die der Client an `mstsc.exe` übergibt.

## 1. Signaturzertifikat

Beim ersten Start erzeugt LibreVDI ein **eigenes Signaturzertifikat** (RSA 3072, 5 Jahre gültig)
unter `/var/lib/uds/rdp-signing/` im Volume `broker-data`. Das Log zeigt den Fingerabdruck:

```bash
docker compose logs broker-web | grep rdp-signing
# librevdi: rdp-signing: public certificate at /uds/res/librevdi/rdp-signing.crt, SHA-1 B18131AB...
```

**Eigenes Zertifikat** (z. B. aus der Firmen-CA) statt des selbst erzeugten: Dateien in den Container
einbinden und in `.env` setzen (PEM-Zertifikat + Schlüssel oder PFX ohne Passwort):

```bash
LIBREVDI_RDP_SIGN_CERT=/run/secrets/rdp-sign.pem
LIBREVDI_RDP_SIGN_KEY=/run/secrets/rdp-sign.key
```

Ein Let's-Encrypt-Zertifikat ist möglich, wechselt aber alle 90 Tage – der Fingerabdruck in der
Gruppenrichtlinie (Schritt 3) müsste dann jedes Mal angepasst werden.

## 2. Signieren einschalten (pro Transport)

**Konnektivität → Transporte → RDP-Transport bearbeiten → „Sign RDP file“** aktivieren.
Gilt für direkte und getunnelte RDP-Transporte gleichermaßen.

## 3. Clients vertrauen lassen

**a) Zertifikat importieren** (selbst erzeugtes oder eigenes CA-Zertifikat), auf jedem Client als
Administrator:

```powershell
curl.exe -o $env:TEMP\librevdi-rdp.crt https://<LIBREVDI_DOMAIN>/uds/res/librevdi/rdp-signing.crt
certutil -addstore -f Root $env:TEMP\librevdi-rdp.crt
```

Danach zeigt `mstsc` den Herausgeber („LibreVDI RDP signing (…)“) statt „Unbekannter Herausgeber“.

**b) Warnung ganz abschalten** (optional, empfohlen in Firmen): Gruppenrichtlinie
*Computerkonfiguration → Administrative Vorlagen → Windows-Komponenten → Remotedesktopdienste →
Remotedesktopverbindungs-Client → „SHA1-Fingerabdrücke von Zertifikaten angeben, die vertrauenswürdige
RDP-Herausgeber darstellen“* → aktivieren, Fingerabdruck aus dem Log eintragen (ohne Doppelpunkte).

In Domänen verteilt man Zertifikat (Schritt a) und Richtlinie (Schritt b) per GPO.
Ob neuere Windows-Versionen zusätzlich den allgemeinen Hinweis „Öffnen einer
Remotedesktopverbindung“ zeigen, hängt vom Patchstand ab; mit vertrauenswürdigem Herausgeber und
Richtlinie entfällt in unseren bisherigen Erfahrungen die Herausgeber-Warnung, im Lab noch zu
bestätigen.

## Datensicherung

Das Signaturzertifikat gehört zur Sicherung (siehe installation.md):

```bash
docker compose cp broker-web:/var/lib/uds/rdp-signing ./librevdi-rdp-signing
```
