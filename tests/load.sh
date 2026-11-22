#!/usr/bin/env bash
# Short parallel load test against a running compose stack.
#
#   tests/load.sh [seconds]     (default 30)
#
# Sends parallel portal and authenticated REST requests and fails if
#   - any request does not answer 200, or
#   - the broker logs "too many clients" (PostgreSQL connection exhaustion), or
#   - more than MAX_DB_CONNECTIONS (default 50) database connections are open at once.
set -euo pipefail

cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
. ./.env
set +a

DURATION="${1:-30}"
MAX_ALLOWED="${MAX_DB_CONNECTIONS:-50}"
DOMAIN="${LIBREVDI_DOMAIN:?}"
PORT="${LIBREVDI_HTTPS_PORT:-443}"
BASE="https://${DOMAIN}:${PORT}"
c() { curl --noproxy '*' -sk --max-time 20 --resolve "${DOMAIN}:${PORT}:127.0.0.1" "$@"; }
db_connections() {
  docker compose exec -T postgres psql -U "${POSTGRES_USER:-librevdi}" -d "${POSTGRES_DB:-librevdi}" -tAc \
    "select count(*) from pg_stat_activity where datname=current_database()" 2>/dev/null || echo 9999
}

token=$(c -X POST -H 'Content-Type: application/json' \
  -d "{\"auth_id\":\"00000000-0000-0000-0000-000000000000\",\"username\":\"${LIBREVDI_ROOT_USER:-root}\",\"password\":\"${LIBREVDI_ROOT_PASSWORD:?}\"}" \
  "${BASE}/uds/rest/auth/login" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')

codes=$(mktemp)
trap 'rm -f "$codes"' EXIT
max=0
errors=0
end=$((SECONDS + DURATION))
echo "== load test: ${DURATION}s against ${BASE}"
while ((SECONDS < end)); do
  for _ in $(seq 1 20); do
    c -o /dev/null -w '%{http_code}\n' "${BASE}/uds/page/login" &
    c -o /dev/null -w '%{http_code}\n' -H "X-Auth-Token: ${token}" "${BASE}/uds/rest/providers" &
    c -o /dev/null -w '%{http_code}\n' -H "X-Auth-Token: ${token}" "${BASE}/uds/rest/servicespools" &
  done >"$codes"
  wait
  errors=$((errors + $(grep -vc '^200$' "$codes" || true)))
  n=$(db_connections)
  ((n > max)) && max=$n
done

exhausted=$(docker compose logs --no-color broker-web broker-tasks 2>&1 | grep -c "too many clients" || true)
echo "max DB connections: ${max} (limit ${MAX_ALLOWED}), non-200 responses: ${errors}, 'too many clients': ${exhausted}"

if ((errors > 0 || exhausted > 0 || max > MAX_ALLOWED)); then
  echo "== load test FAILED"
  exit 1
fi
echo "== load test passed"
