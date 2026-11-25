#!/usr/bin/env bash
# Builds the LibreVDI Linux packages (client or agent) for one distribution with the upstream
# OpenUDS build (Docker builder images + dpkg-buildpackage) and repackages them as LibreVDI.
#
#   packaging/linux/build-linux.sh client|agent Debian12|Debian13|Ubuntu2404 <version> <outdir>
#
# Expects the upstream sources to be branded already (packaging/windows/brand_upstream.py).
# NOTICES=<file>: third-party license notices, shipped as /usr/share/doc/<package>/THIRD-PARTY-NOTICES.txt
# Ubuntu 24.04 has no upstream builder: prepare-builder.sh generates it from the Debian 13 one.
# A builder image built beforehand (e.g. with a layer cache in CI) is reused when
# builders/<distro>/build.stamp is newer than its Dockerfile.
set -euo pipefail

component=${1:?client|agent}
distro=${2:?Debian12|Debian13|Ubuntu2404}
version=${3:?version, e.g. 0.1.0-dev.21}
outdir=$(realpath -m "${4:?output directory}")

repo_root=$(cd "$(dirname "$0")/../.." && pwd)
case "$component" in
  client) crate="$repo_root/upstream/uds-client"; image_prefix=udslauncher ;;
  agent)  crate="$repo_root/upstream/uds-actor";  image_prefix=udsactor ;;
  *) echo "unknown component $component" >&2; exit 2 ;;
esac
build_dir="$crate/building/linux"
deb_version=${version//-/\~}   # 0.1.0-dev.21 -> 0.1.0~dev.21 (sorts before 0.1.0)
suffix=$(echo "$distro" | tr '[:upper:]' '[:lower:]')

"$repo_root/packaging/linux/prepare-builder.sh" "$component" "$distro" >/dev/null

echo "== building $component for $distro"
cd "$build_dir"
rm -f ../"${image_prefix}"*.deb
if [[ "$component" == "client" && "$distro" == "Ubuntu2404" ]]; then
  # upstream main() only ships the FreeRDP libraries for its own distro names; same step as for
  # Debian 12/13 (copy /usr/local/lib/*.so next to the launcher, recreate the .so.N links)
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
docker run --rm \
  -e IN_DOCKER=1 -e DISTRO="$distro" \
  -v "$crate:/crate" -w /crate/building/linux \
  "rust-builder-$image_prefix:$distro" \
  sh -c "dpkg-buildpackage -b -us -uc && chown -R $(id -u):$(id -g) /crate/building /crate/building/linux"

mkdir -p "$outdir"
icon="$repo_root/branding/logo-256.png"
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
    --name "$name" --version "$deb_version" --description "$desc" --suffix "$suffix" --icon "$icon" "${extra[@]}"
done
ls -l "$outdir"
