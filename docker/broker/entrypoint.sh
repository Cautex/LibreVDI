#!/bin/sh
# LibreVDI broker entrypoint
#
#   init     one-shot: wait for DB, create keys, migrate, apply LibreVDI configuration
#   web      run the web/API server (ASGI, daphne)
#   tasks    run the background task manager (warm pool, cleanup, ...)
#   tunnel-setup  one-shot: register the bundled tunnel server (compose profile "tunnel")
#   manage   run a Django management command, e.g. "manage showconfig"
#   *        exec anything else
set -eu
cd /app

DATA_DIR="${UDS_DATA_DIR:-/var/lib/uds}"

log() { echo "librevdi: $*"; }

wait_for_db() {
  python - <<'PY'
import sys, time
import django
django.setup()
from django.db import connections
deadline = time.time() + int(__import__("os").environ.get("LIBREVDI_DB_WAIT", "60"))
while True:
    try:
        connections["default"].ensure_connection()
        break
    except Exception as e:
        if time.time() > deadline:
            print(f"librevdi: database not reachable: {e}", file=sys.stderr)
            sys.exit(1)
        time.sleep(2)
print("librevdi: database reachable")
PY
}

cmd="${1:-web}"
[ $# -gt 0 ] && shift

case "$cmd" in
  init)
    mkdir -p "$DATA_DIR/keys"
    python -m librevdi_ext.keys "$DATA_DIR/keys"
    python -m librevdi_ext.rdp_signing init
    wait_for_db
    log "applying database migrations"
    python manage.py migrate --noinput
    python manage.py createcachetable
    python -m librevdi_ext.bootstrap
    python -m librevdi_ext.selfcheck --quiet   # OpenUDS contract + LibreVDI hooks (ADR-0008)
    log "init done"
    ;;
  web)
    echo "librevdi: LibreVDI ${LIBREVDI_VERSION:-dev} (broker OpenUDS 5.0)"
    python -m librevdi_ext.downloads
    python -m librevdi_ext.rdp_signing publish
    exec daphne -b 0.0.0.0 -p "${LIBREVDI_PORT:-8000}" --proxy-headers \
      --access-log - server.asgi:application "$@"
    ;;
  tasks)
    exec python manage.py task_manager --start --foreground "$@"
    ;;
  tunnel-setup)
    exec python -m librevdi_ext.tunnel_setup "$@"
    ;;
  manage)
    exec python manage.py "$@"
    ;;
  *)
    exec "$cmd" "$@"
    ;;
esac
