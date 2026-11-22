#!/bin/sh
# Build helper: runs a command (usually apt-get/pip) and, only if configured,
#  * routes apt through the HTTPS proxy given as build arg HTTPS_PROXY
#    (apt sources are switched to https:// for the duration of the command,
#    because CONNECT-only proxies cannot forward plain http), and
#  * trusts an extra CA certificate passed as BuildKit secret "extra_ca".
# Without proxy/secret it simply runs the command. Nothing of this is persisted.
set -e
conf=/etc/apt/apt.conf.d/99-librevdi-build
bundle=""
restore=""

cleanup() {
  rm -f "$conf"
  [ -n "$bundle" ] && rm -f "$bundle"
  for f in $restore; do mv -f "$f.librevdi-orig" "$f"; done
}
trap cleanup EXIT

proxy="${HTTPS_PROXY:-${https_proxy:-}}"
if [ -n "$proxy" ]; then
  echo "Acquire::https::Proxy \"$proxy\";" >> "$conf"
  for f in /etc/apt/sources.list.d/*.sources /etc/apt/sources.list; do
    [ -f "$f" ] || continue
    cp -p "$f" "$f.librevdi-orig"
    sed -i 's|http://|https://|g' "$f"
    restore="$restore $f"
  done
fi

if [ -s /run/secrets/extra_ca ]; then
  bundle=$(mktemp)
  chmod 0644 "$bundle"  # apt downloads as user _apt
  [ -f /etc/ssl/certs/ca-certificates.crt ] && cat /etc/ssl/certs/ca-certificates.crt > "$bundle"
  cat /run/secrets/extra_ca >> "$bundle"
  export SSL_CERT_FILE="$bundle" PIP_CERT="$bundle" REQUESTS_CA_BUNDLE="$bundle" CURL_CA_BUNDLE="$bundle"
  echo "Acquire::https::CAInfo \"$bundle\";" >> "$conf"
fi

"$@"
