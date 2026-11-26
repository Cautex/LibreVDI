#!/usr/bin/env bash
# Builds the LibreVDI Linux packages (client or agent) for one distribution with the upstream
# OpenUDS build (Docker builder images + rustbuilder.py) and packages them as LibreVDI:
#
#   Ubuntu 24.04 / 26.04: upstream dpkg-buildpackage, then rebrand_deb.py   -> .deb
#   Rocky Linux 9 / 10:   upstream "make install", then build_rpm.py        -> .rpm
#
#   packaging/linux/build-linux.sh client|agent Ubuntu2404|Ubuntu2604|Rocky9|Rocky10 <version> <outdir>
#
# Expects the upstream sources to be branded already (packaging/windows/brand_upstream.py).
# The builders are generated from the upstream Debian 13 builder (prepare-builder.sh). A builder
# image built beforehand (e.g. with a layer cache in CI) is reused when builders/<distro>/build.stamp
# is newer than its Dockerfile.
# NOTICES=<file>: third-party license notices, shipped as /usr/share/doc/<package>/THIRD-PARTY-NOTICES.txt
set -euo pipefail

component=${1:?client|agent}
distro=${2:?Ubuntu2404|Ubuntu2604|Rocky9|Rocky10}
version=${3:?version, e.g. 0.1.0-dev.21}
outdir=$(realpath -m "${4:?output directory}")

repo_root=$(cd "$(dirname "$0")/../.." && pwd)
case "$component" in
  client) crate="$repo_root/upstream/uds-client"; image_prefix=udslauncher ;;
  agent)  crate="$repo_root/upstream/uds-actor";  image_prefix=udsactor ;;
  *) echo "unknown component $component" >&2; exit 2 ;;
esac
case "$distro" in
  Ubuntu*) format=deb ;;
  Rocky*)  format=rpm ;;
  *) echo "unsupported distribution $distro" >&2; exit 2 ;;
esac
build_dir="$crate/building/linux"
pkg_version=${version//-/\~}   # 0.1.0-dev.21 -> 0.1.0~dev.21 (sorts before 0.1.0 in dpkg and rpm)
suffix=$(echo "$distro" | tr '[:upper:]' '[:lower:]')
icon="$repo_root/branding/logo-256.png"

"$repo_root/packaging/linux/prepare-builder.sh" "$component" "$distro" >/dev/null

echo "== building $component for $distro"
cd "$build_dir"
if [[ "$component" == "client" ]]; then
  # upstream main() ships the self-built FreeRDP libraries only for its own distro names; same step
  # for ours (copy /usr/local/lib/*.so next to the launcher, recreate the .so.N links)
  # shellcheck disable=SC2016  # the $ belong to the shell inside the builder container
  python3 -c '
import sys, rustbuilder
script = ("cp /usr/local/lib/*so [TARGET] && cd [TARGET] && "
          "for f in /usr/local/lib/*.so.*; do ln --force -s \"${f%%.*}.so\" \"$(basename $f)\"; done")
rustbuilder.build_for_distro(sys.argv[1], "../..", False, script)
' "$distro"
else
  python3 rustbuilder.py "$distro"
fi

mkdir -p "$outdir"
if [[ "$format" == "rpm" ]]; then
  notices=()
  [[ -n "${NOTICES:-}" ]] && notices=(--notices "$NOTICES")
  python3 "$repo_root/packaging/linux/build_rpm.py" "$component" "$distro" "$pkg_version" "$outdir" \
    --icon "$icon" "${notices[@]}"
  ls -l "$outdir"
  exit 0
fi

rm -f ../"${image_prefix}"*.deb
docker run --rm \
  -e IN_DOCKER=1 -e DISTRO="$distro" \
  -v "$crate:/crate" -w /crate/building/linux \
  "rust-builder-$image_prefix:$distro" \
  sh -c "dpkg-buildpackage -b -us -uc && chown -R $(id -u):$(id -g) /crate/building /crate/building/linux"

shopt -s nullglob
debs=(../"${image_prefix}"*.deb)
[[ ${#debs[@]} -gt 0 ]] || { echo "no packages produced" >&2; exit 1; }
for deb in "${debs[@]}"; do
  pkg=$(dpkg-deb -f "$deb" Package)
  case "$pkg" in
    udslauncher)        name=librevdi-client;           desc="LibreVDI Client - connects to LibreVDI virtual desktops" ;;
    udsactor)           name=librevdi-agent;            desc="LibreVDI Agent (managed) for cloned desktops" ;;
    udsactor-unmanaged) name=librevdi-agent-unmanaged;  desc="LibreVDI Agent (unmanaged) for persistent desktops" ;;
    *) echo "skipping unknown package $pkg"; continue ;;
  esac
  extra=()
  if [[ -n "${NOTICES:-}" ]]; then  # third-party license notices (collect_licenses.py)
    extra+=(--add-file "$NOTICES:/usr/share/doc/$name/THIRD-PARTY-NOTICES.txt:0644")
  fi
  if [[ "$pkg" == "udsactor-unmanaged" ]]; then
    extra+=(--add-file "$repo_root/packaging/linux/librevdi-agent-configure:/usr/sbin/librevdi-agent-configure")
  fi
  python3 "$repo_root/packaging/linux/rebrand_deb.py" "$deb" "$outdir" \
    --name "$name" --version "$pkg_version" --description "$desc" --suffix "$suffix" --icon "$icon" "${extra[@]}"
done
ls -l "$outdir"
