#!/usr/bin/env bash
# Checks the optional tunnel (compose profile "tunnel") of a running stack:
# registration, tunnel group, assignment and the tunnel server listening.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
logs=$(docker compose --profile tunnel logs --no-color tunnel-init 2>&1 || true)
for msg in "registered" "ready" "assigned"; do
  if grep -q "$msg" <<<"$logs"; then echo "ok    tunnel-init: $msg"; else echo "FAIL  tunnel-init: '$msg' missing"; fail=1; fi
done

for _ in $(seq 1 20); do
  docker compose --profile tunnel logs --no-color tunnel 2>&1 | grep -q "Listening on 0.0.0.0:4443" && break
  sleep 3
done
if docker compose --profile tunnel logs --no-color tunnel 2>&1 | grep -q "Listening on 0.0.0.0:4443"; then
  echo "ok    tunnel listening on 4443"
else
  echo "FAIL  tunnel not listening"; fail=1
fi

[[ $fail -eq 0 ]] && echo "== tunnel test passed" || echo "== tunnel test FAILED"
exit $fail
