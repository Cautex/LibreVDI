#!/bin/sh
# shellcheck disable=SC3045  # dash (Debian /bin/sh) supports ulimit -n/-H/-S
# LibreVDI tunnel entrypoint: waits for the broker registration token (written by the
# broker container "tunnel-init"), writes the tunnel configuration and starts the server.
set -eu

TOKEN_FILE="${LIBREVDI_TUNNEL_TOKEN_FILE:-/run/librevdi-tunnel/token}"
TICKET_URL="${LIBREVDI_TUNNEL_TICKET_URL:-http://proxy:8081/uds/rest/tunnel/ticket}"
CONF=/var/lib/udstunnel/udstunnel.conf
LOG_DIR=/var/lib/udstunnel/log

echo "librevdi-tunnel: waiting for registration token at $TOKEN_FILE"
i=0
while [ ! -s "$TOKEN_FILE" ]; do
  i=$((i + 1))
  [ "$i" -gt 120 ] && { echo "librevdi-tunnel: no token after 10 minutes" >&2; exit 1; }
  sleep 5
done

umask 077
cat > "$CONF" <<CONF
listen_addr = "0.0.0.0"
listen_port = 4443
ticket_api_url = "$TICKET_URL"
broker_auth_token = "$(cat "$TOKEN_FILE")"
log_level = "${LIBREVDI_TUNNEL_LOG_LEVEL:-info}"
CONF

mkdir -p "$LOG_DIR"
export UDSTUNNEL_TUNNEL_LOG_PATH="$LOG_DIR"
touch "$LOG_DIR/uds-tunnel.log"
tail -F "$LOG_DIR/uds-tunnel.log" &

# Many concurrent sessions need many file descriptors: use the host's hard limit
ulimit -n "$(ulimit -Hn)" 2>/dev/null || true
echo "librevdi-tunnel: open files limit $(ulimit -Sn)"

cd /var/lib/udstunnel
echo "librevdi-tunnel: starting on 4443 (broker: $TICKET_URL)"
exec tunnel-server "$@"
