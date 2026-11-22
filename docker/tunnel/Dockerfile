# syntax=docker/dockerfile:1.7
#
# LibreVDI – Tunnel server image (OpenUDS 5.0 uds-tunnel-server, BSD-3-Clause, Rust)
#
# Build context: repository root
#   docker build -f docker/tunnel/Dockerfile -t librevdi-tunnel:local .
# Optional behind a TLS-intercepting proxy: see docker/broker/Dockerfile (HTTPS_PROXY + extra_ca)

ARG RUST_IMAGE=rust:1-slim-trixie
ARG BASE_IMAGE=debian:trixie-slim

FROM ${RUST_IMAGE} AS build
COPY docker/broker/scripts/with-extra-ca.sh /usr/local/bin/with-extra-ca
RUN --mount=type=secret,id=extra_ca,required=false \
    with-extra-ca sh -c 'apt-get update \
 && apt-get install -y --no-install-recommends pkg-config libssl-dev cmake build-essential ca-certificates \
 && rm -rf /var/lib/apt/lists/*'
WORKDIR /build
COPY upstream/uds-tunnel-server /build
RUN --mount=type=secret,id=extra_ca,required=false \
    with-extra-ca sh -c 'export CARGO_HTTP_CAINFO="${SSL_CERT_FILE:-}"; [ -n "$CARGO_HTTP_CAINFO" ] || unset CARGO_HTTP_CAINFO; \
    cargo build --release --locked --bin tunnel-server'

FROM ${BASE_IMAGE} AS runtime
LABEL org.opencontainers.image.title="LibreVDI Tunnel" \
      org.opencontainers.image.description="LibreVDI tunnel server (based on OpenUDS 5.0)" \
      org.opencontainers.image.source="https://github.com/Cautex/LibreVDI" \
      org.opencontainers.image.licenses="BSD-3-Clause"
COPY docker/broker/scripts/with-extra-ca.sh /usr/local/bin/with-extra-ca
RUN --mount=type=secret,id=extra_ca,required=false \
    with-extra-ca sh -c 'apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates libssl3t64 tini \
 && rm -rf /var/lib/apt/lists/*' \
 && rm /usr/local/bin/with-extra-ca \
 && useradd --system --uid 10002 --home-dir /var/lib/udstunnel --shell /usr/sbin/nologin udstunnel \
 && mkdir -p /var/lib/udstunnel && chown udstunnel /var/lib/udstunnel \
 && ln -s /var/lib/udstunnel/udstunnel.conf /etc/udstunnel.conf  # release builds read /etc/udstunnel.conf
COPY --from=build /build/target/release/tunnel-server /usr/local/bin/tunnel-server
COPY docker/tunnel/entrypoint.sh /usr/local/bin/librevdi-tunnel
RUN chmod 0755 /usr/local/bin/librevdi-tunnel
USER udstunnel
EXPOSE 4443/tcp 4443/udp
ENTRYPOINT ["/usr/bin/tini", "--", "librevdi-tunnel"]
