# Third-party software / Software Dritter

LibreVDI's own code is licensed under the BSD-3-Clause license (see `LICENSE`).
LibreVDI builds on and distributes the following third-party software. Their copyright
notices and license texts are kept unchanged in the respective sources.

## Upstream components (git submodules under `upstream/`)

| Component | Path | License | Copyright | Used in |
|---|---|---|---|---|
| OpenUDS broker | `upstream/broker` | BSD-3-Clause | © Virtual Cable S.L. | broker image (unmodified) |
| OpenUDS actor (agent) | `upstream/uds-actor` | BSD-3-Clause | © Virtual Cable S.L.U. | LibreVDI Agent (Windows installer) |
| OpenUDS client/launcher | `upstream/uds-client` | BSD-3-Clause | © Virtual Cable S.L. | LibreVDI Client (Windows installer) |
| OpenUDS tunnel server | `upstream/uds-tunnel-server` | BSD-3-Clause | © Virtual Cable S.L. | tunnel image (optional compose profile) |

"OpenUDS" and "UDS" are names of Virtual Cable S.L. LibreVDI is an independent project; it is
**not** affiliated with or endorsed by Virtual Cable S.L. (BSD-3-Clause, clause 3).

The OpenUDS web UI ships pre-built JavaScript bundles; their own third-party notices are in
`upstream/broker/src/uds/static/*/3rdpartylicenses.txt`.

## Windows installers (LibreVDI Agent, LibreVDI Client)

Each installer contains `THIRD-PARTY-NOTICES.txt` with the complete list and license texts of the
bundled components; it is generated during the build by `packaging/windows/collect_licenses.py`
and also attached to every GitHub release (`THIRD-PARTY-NOTICES-Agent.txt`, `-Client.txt`).

| Component | License | Shipped as | Installer |
|---|---|---|---|
| Rust crates linked into the binaries (about 340 agent / 500 client) | predominantly MIT / Apache-2.0, also BSD, ISC, Zlib, Unicode-3.0, BSL-1.0, OFL-1.1 (fonts) | statically linked | both |
| FreeRDP 3.x | Apache-2.0 | DLLs | Client |
| FFmpeg (vcpkg default features, no GPL components) | LGPL-2.1-or-later | DLLs (replaceable) | Client |
| libusb | LGPL-2.1-or-later | DLL (replaceable) | Client |
| OpenSSL 3 | Apache-2.0 | DLLs | Client |
| zlib | Zlib | DLL | Client |
| cJSON | MIT | DLL | Client |
| libvpx | BSD-3-Clause | statically linked | Client |
| Microsoft Visual C++ Runtime | Microsoft Visual Studio Distributable Code | DLLs (app-local, unmodified) | Client |

Crates offered under a choice of licenses (e.g. `Apache-2.0 OR GPL-2.0-only`) are used under the
permissive option. **LGPL libraries:** they are dynamically linked and can be replaced by the user.
Their unmodified source code is the upstream release referenced by the vcpkg port version listed
in `THIRD-PARTY-NOTICES-Client.txt`; on request (GitHub issue in this repository) we provide the
exact source archives used for a release, for at least three years after that release.

## Container images used by `compose.yaml`

| Image | Software license |
|---|---|
| `ghcr.io/<owner>/librevdi-broker` (release image) | this file; also contains the Windows installers listed above |
| `ghcr.io/<owner>/librevdi-tunnel` (release image) | BSD-3-Clause (OpenUDS tunnel server) plus its Rust crates (`cargo metadata` of `upstream/uds-tunnel-server`) and Debian packages |
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
