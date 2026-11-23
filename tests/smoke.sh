#!/usr/bin/env bash
# LibreVDI smoke test against a running compose stack.
#
#   tests/smoke.sh            # reads .env from the repository root
#
# Checks (through the reverse proxy, TLS):
#   - login page and static files are served, admin UI redirects to login
#   - health endpoints are NOT reachable from outside
#   - REST login with the super user works, a wrong password is rejected
#   - the task manager container is healthy
#   - with SMOKE_EXPECT_DOWNLOADS=1: client and agent installers are published (release images)
set -euo pipefail

cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
. ./.env
set +a

DOMAIN="${LIBREVDI_DOMAIN:?}"
# SMOKE_PORT: HTTPS port to test (e.g. the outer reverse proxy in "behind-proxy" mode)
PORT="${SMOKE_PORT:-${LIBREVDI_HTTPS_PORT:-443}}"
BASE="https://${DOMAIN}:${PORT}"
ZERO_AUTH="00000000-0000-0000-0000-000000000000"  # built-in super user "authenticator"

fail=0
# SMOKE_HOST_IP: where DOMAIN is reached (default: this host; in "behind-proxy" mode the outer proxy)
HOST_IP="${SMOKE_HOST_IP:-127.0.0.1}"
c() { curl --noproxy '*' -sk --max-time 20 --resolve "${DOMAIN}:${PORT}:${HOST_IP}" "$@"; }

expect_status() {  # path expected_code
  local code
  code=$(c -o /dev/null -w '%{http_code}' "${BASE}$1")
  if [[ "$code" == "$2" ]]; then
    echo "ok    GET $1 -> $code"
  else
    echo "FAIL  GET $1 -> $code (expected $2)"
    fail=1
  fi
}

expect_redirect() {  # path expected_location
  local loc
  loc=$(c -o /dev/null -w '%{http_code} %{redirect_url}' "${BASE}$1")
  if [[ "$loc" == "302 ${BASE}$2" ]]; then
    echo "ok    GET $1 -> 302 $2"
  else
    echo "FAIL  GET $1 -> $loc (expected 302 to $2)"
    fail=1
  fi
}

login() {  # password -> prints HTTP code and body
  c -w '\n%{http_code}' -X POST -H 'Content-Type: application/json' \
    -d "{\"auth_id\":\"${ZERO_AUTH}\",\"username\":\"${LIBREVDI_ROOT_USER:-root}\",\"password\":\"$1\"}" \
    "${BASE}/uds/rest/auth/login"
}

echo "== LibreVDI smoke test against ${BASE}"

# Wait for the proxy to answer (first start: certificate issuance)
for _ in $(seq 1 30); do
  [[ "$(c -o /dev/null -w '%{http_code}' "${BASE}/uds/page/login")" == "200" ]] && break
  sleep 2
done

expect_status /uds/page/login 200
expect_redirect /uds/adm/ /uds/page/login  # admin UI requires login
expect_status /uds/res/admin/main.js 200
if [[ "${LIBREVDI_PROXY_CONFIG:-Caddyfile}" == "Caddyfile" && "${LIBREVDI_TLS:-internal}" == "internal" ]]; then
  expect_status /ca.crt 200  # root CA download for clients/VMs
fi
expect_status /uds/res/librevdi/rdp-signing.crt 200  # RDP signing certificate for clients
if [[ "${SMOKE_EXPECT_DOWNLOADS:-0}" == "1" ]]; then
  client=$(docker compose exec -T broker-web sh -c 'ls /app/static/clients/ | grep "^LibreVDI-Client-Setup-" | head -1')
  expect_status "/uds/res/clients/${client:-missing}" 200  # portal "LibreVDI Client" download
  for f in UDSActorSetup-5.0.0.exe UDSActorUnmanagedSetup-5.0.0.exe; do  # admin UI agent downloads
    if docker compose exec -T broker-web test -s "/app/uds/osmanagers/WindowsOsManager/files/$f"; then
      echo "ok    agent installer $f published"
    else
      echo "FAIL  agent installer $f missing"
      fail=1
    fi
  done
fi
expect_status /healthz 404
expect_status /readyz 404

# REST login as super user
resp=$(login "${LIBREVDI_ROOT_PASSWORD:?}")
code=${resp##*$'\n'}
body=${resp%$'\n'*}
if [[ "$code" == "200" ]] && python3 -c 'import json,sys; d=json.loads(sys.argv[1]); sys.exit(0 if d.get("result")=="ok" and d.get("token") else 1)' "$body"; then
  echo "ok    REST login super user"
else
  echo "FAIL  REST login super user -> $code ${body:0:200}"
  fail=1
fi

# Wrong password must not yield a token
resp=$(login "definitely-wrong-password")
body=${resp%$'\n'*}
if python3 -c 'import json,sys; d=json.loads(sys.argv[1]); sys.exit(1 if d.get("token") else 0)' "$body" 2>/dev/null; then
  echo "ok    REST login with wrong password rejected"
else
  echo "FAIL  REST login with wrong password returned a token"
  fail=1
fi

# LibreVDI broker plugins are loaded
if docker compose exec -T broker-web python -c '
import django; django.setup()
from uds.services.Proxmox.provider import ProxmoxProvider
assert any(t.type_type == "LibreVDIProxmoxPersistentService" for t in ProxmoxProvider.offers)
' >/dev/null 2>&1; then
  echo "ok    plugin 'Proxmox Persistent Desktops' registered"
else
  echo "FAIL  plugin 'Proxmox Persistent Desktops' not registered"
  fail=1
fi

# Container health (healthchecks may still be in their start period)
for svc in broker-web broker-tasks postgres; do
  state=""
  for _ in $(seq 1 30); do
    state=$(docker compose ps --format '{{.Health}}' "$svc" 2>/dev/null || true)
    [[ "$state" == "starting" ]] || break
    sleep 3
  done
  if [[ "$state" == "healthy" ]]; then
    echo "ok    $svc healthy"
  else
    echo "FAIL  $svc health: ${state:-unknown}"
    fail=1
  fi
done

if [[ $fail -eq 0 ]]; then echo "== smoke test passed"; else echo "== smoke test FAILED"; fi
exit $fail
