# syntax=docker/dockerfile:1.7
#
# LibreVDI – Broker image (based on the openUDS 5.0 broker, BSD-3-Clause)
#
# Build context: repository root
#   docker build -f docker/broker/Dockerfile -t librevdi/broker .
#
# Optional, only for build environments behind a TLS-intercepting HTTPS proxy:
#   --network host --build-arg HTTPS_PROXY=http://proxy:port \
#   --secret id=extra_ca,src=/path/to/ca.crt
# Proxy and CA are used during the build only and are NOT part of the image.

ARG BASE_IMAGE=ubuntu:24.04

############################
# Stage 1: build virtualenv
############################
FROM ${BASE_IMAGE} AS build

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

COPY docker/broker/scripts/with-extra-ca.sh /usr/local/bin/with-extra-ca

RUN --mount=type=secret,id=extra_ca,required=false \
    with-extra-ca sh -c 'apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-dev \
      build-essential pkg-config git \
      libsasl2-dev libldap2-dev libssl-dev \
      libxml2-dev libxslt1-dev libxmlsec1-dev \
      libmemcached-dev zlib1g-dev libcurl4-openssl-dev \
      libffi-dev libjpeg-dev \
 && rm -rf /var/lib/apt/lists/*'

# Upstream requirements minus mysqlclient (GPL-2.0; LibreVDI uses PostgreSQL, see ADR-0003)
COPY upstream/broker/requirements.txt /tmp/requirements.txt
COPY docker/broker/requirements-librevdi.txt /tmp/requirements-librevdi.txt

RUN --mount=type=secret,id=extra_ca,required=false \
    python3 -m venv "$VIRTUAL_ENV" \
 && with-extra-ca sh -c 'pip install --upgrade pip wheel setuptools \
 && pip install --no-binary lxml --no-binary xmlsec lxml xmlsec \
 && grep -viE "^(mysqlclient)([<>=! ;]|$)" /tmp/requirements.txt > /tmp/requirements-filtered.txt \
 && pip install -r /tmp/requirements-filtered.txt -r /tmp/requirements-librevdi.txt'

############################
# Stage 2: runtime
############################
FROM ${BASE_IMAGE} AS runtime

# Set by the release workflow; local builds report "dev"
ARG LIBREVDI_VERSION=dev
ARG LIBREVDI_SOURCE=https://github.com/Cautex/LibreVDI

LABEL org.opencontainers.image.title="LibreVDI Broker" \
      org.opencontainers.image.description="LibreVDI connection broker (based on OpenUDS 5.0)" \
      org.opencontainers.image.source="${LIBREVDI_SOURCE}" \
      org.opencontainers.image.version="${LIBREVDI_VERSION}" \
      org.opencontainers.image.licenses="BSD-3-Clause"

ENV DEBIAN_FRONTEND=noninteractive

COPY docker/broker/scripts/with-extra-ca.sh /usr/local/bin/with-extra-ca

# Runtime libraries only (no compilers)
RUN --mount=type=secret,id=extra_ca,required=false \
    with-extra-ca sh -c 'apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates python3 tini \
      libsasl2-2 libldap2 libxml2 libxslt1.1 libxmlsec1t64 libxmlsec1t64-openssl \
      libmemcached11t64 libcurl4t64 libjpeg-turbo8 \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 libcairo2 fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*' \
 && rm /usr/local/bin/with-extra-ca

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=server.settings \
    UDS_DATA_DIR=/var/lib/uds \
    LIBREVDI_VERSION=${LIBREVDI_VERSION}

COPY --from=build /opt/venv /opt/venv

# Upstream broker code (unchanged)
COPY upstream/broker/src /app
# LibreVDI additions: settings overlay and helpers (later also plugins)
COPY docker/broker/settings.py /app/server/settings.py
COPY docker/broker/librevdi_ext /app/librevdi_ext
# LibreVDI broker plugins (auto-imported by upstream from uds/plugins/)
COPY docker/broker/plugins/librevdi /app/uds/plugins/librevdi
# Branding (logo, texts, translations), applied once below
COPY branding/logo-*.png branding/logo.ico /opt/librevdi/branding/
COPY docker/broker/branding/apply_branding.py /opt/librevdi/apply_branding.py
COPY docker/broker/entrypoint.sh /usr/local/bin/librevdi-entrypoint
# Windows installers bundled into release images (CI puts them into downloads/ before the build;
# local builds bundle whatever was fetched there). ./downloads mounted on the host takes precedence.
COPY downloads/ /opt/librevdi/bundled-downloads/

RUN useradd --system --uid 10001 --home-dir /var/lib/uds --shell /usr/sbin/nologin uds \
 && mkdir -p /var/lib/uds /app/log \
 && chmod 0755 /usr/local/bin/librevdi-entrypoint \
 && cd /app \
 && cp /app/uds/services/Proxmox/service.png /app/uds/plugins/librevdi/service.png \
 && LIBREVDI_BUILD=1 python manage.py collectstatic --noinput >/dev/null \
 && python /opt/librevdi/apply_branding.py \
 && chmod -R a+rX /app \
 && mkdir -p /app/static/clients /app/static/librevdi /app/uds/osmanagers/WindowsOsManager/files \
    /run/librevdi-tunnel \
 && chown -R uds:uds /var/lib/uds /app/log /app/static/clients /app/static/librevdi \
    /app/uds/osmanagers/WindowsOsManager/files /run/librevdi-tunnel

WORKDIR /app
USER uds
VOLUME ["/var/lib/uds"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD ["python", "-m", "librevdi_ext.healthcheck"]

ENTRYPOINT ["/usr/bin/tini", "--", "librevdi-entrypoint"]
CMD ["web"]
