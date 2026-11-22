# Third-party software / Software Dritter

LibreVDI's own code is licensed under the BSD-3-Clause license (see `LICENSE`).
LibreVDI builds on and distributes the following third-party software. Their copyright
notices and license texts are kept unchanged in the respective sources.

## Upstream components (git submodules under `upstream/`)

| Component | Path | License | Copyright | Used in |
|---|---|---|---|---|
| OpenUDS broker | `upstream/broker` | BSD-3-Clause | © Virtual Cable S.L. | broker image (unmodified) |
| OpenUDS actor (agent) | `upstream/uds-actor` | BSD-3-Clause | © Virtual Cable S.L.U. | not yet packaged (Phase 2) |
| OpenUDS client/launcher | `upstream/uds-client` | BSD-3-Clause | © Virtual Cable S.L. | not yet packaged (Phase 2) |
| OpenUDS tunnel server | `upstream/uds-tunnel-server` | BSD-3-Clause | © Virtual Cable S.L. | not yet packaged (Phase 2) |

"OpenUDS" and "UDS" are names of Virtual Cable S.L. LibreVDI is an independent project; it is
**not** affiliated with or endorsed by Virtual Cable S.L. (BSD-3-Clause, clause 3).

The OpenUDS web UI ships pre-built JavaScript bundles; their own third-party notices are in
`upstream/broker/src/uds/static/*/3rdpartylicenses.txt`.

## Container images used by `compose.yaml`

| Image | Software license |
|---|---|
| `ubuntu:24.04` (base of the broker image) | various (Debian/Ubuntu package licenses, see `/usr/share/doc/*/copyright` in the image) |
| `postgres:17-alpine` | PostgreSQL License |
| `memcached:1.6-alpine` | BSD-3-Clause |
| `caddy:2-alpine` | Apache-2.0 |

## Python packages in the broker image

See [`docs/licenses/broker-python-packages.md`](docs/licenses/broker-python-packages.md)
(generated from package metadata). Summary of the review (22.11.2026):

* predominantly permissive licenses (MIT, BSD, Apache-2.0, PSF, ISC, MPL-2.0)
* LGPL packages (e.g. `psycopg`, `paramiko`, `CairoSVG`, `pycurl` dual LGPL/MIT): used as
  unmodified, dynamically imported libraries – compatible with distributing LibreVDI under BSD-3
* `mysqlclient` (GPL-2.0-or-later) from the upstream requirements is **intentionally not
  installed**; LibreVDI uses PostgreSQL (ADR-0003)

## Build-time only

`tini` (MIT) is installed in the image as init process.
