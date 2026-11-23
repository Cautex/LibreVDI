#!/usr/bin/env bash
# Compiles the Windows installer scripts with dummy payloads (syntax/logic check on Linux).
# Needs makensis (apt-get install nsis). The real installers are built on Windows in CI.
set -euo pipefail
cd "$(dirname "$0")/../packaging/windows"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"; rm -f LibreVDI-*-Setup-0.0.0-check.exe' EXIT
mkdir -p "$tmp/client" "$tmp/agent"
for f in launcher.exe dummy.dll; do echo x > "$tmp/client/$f"; done
for f in gui-helper.exe udsactor-client.exe udsactor-service.exe udsactor-config.exe udsactor-unmanaged-config.exe; do
  echo x > "$tmp/agent/$f"
done
echo notices > "$tmp/notices.txt"
common=(-V2 -INPUTCHARSET UTF8 -DVERSION=0.0.0-check -DVIVERSION=0.0.0.0 "-DNOTICES=$tmp/notices.txt")
makensis "${common[@]}" "-DSRCDIR=$tmp/client" client.nsi
for variant in unmanaged managed; do
  makensis "${common[@]}" "-DSRCDIR=$tmp/agent" "-DVARIANT=$variant" agent.nsi
done
echo "nsis: client and agent installers compile"
