#!/usr/bin/env bash
# Prints the Docker builder directory for <component> <distro>, after creating it from the upstream
# Debian 13 builder (packaging/linux/make_builder.py). Upstream files are not changed; the
# generated directory lives in the (untracked) build area of the submodule.
#
#   packaging/linux/prepare-builder.sh client|agent Ubuntu2404|Ubuntu2604|Rocky9|Rocky10
set -euo pipefail

component=${1:?client|agent}
distro=${2:?Ubuntu2404|Ubuntu2604|Rocky9|Rocky10}
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
case "$component" in
  client) crate="$repo_root/upstream/uds-client" ;;
  agent)  crate="$repo_root/upstream/uds-actor" ;;
  *) echo "unknown component $component" >&2; exit 2 ;;
esac
builders="$crate/building/linux/builders"
case "$distro" in
  Ubuntu2404|Ubuntu2604|Rocky9|Rocky10) ;;
  *) echo "unsupported distribution $distro" >&2; exit 2 ;;
esac

mkdir -p "$builders/$distro"
new="$builders/$distro/Dockerfile.new"
python3 "$repo_root/packaging/linux/make_builder.py" "$component" "$distro" "$builders/Debian13/Dockerfile" "$new"
if cmp -s "$new" "$builders/$distro/Dockerfile"; then
  rm -f "$new"   # unchanged: keep the timestamp, so a cached builder image stays valid
else
  mv -f "$new" "$builders/$distro/Dockerfile"
  echo "== generated $distro builder for $component" >&2
fi
echo "$builders/$distro"
