#!/usr/bin/env bash
# Prints the upstream Docker builder directory for <component> <distro>; creates it first for
# distributions without an upstream builder (Ubuntu 24.04 is generated from Debian 13: base image
# and one package name differ). Upstream files are not changed.
#
#   packaging/linux/prepare-builder.sh client|agent Debian12|Debian13|Ubuntu2404
set -euo pipefail

component=${1:?client|agent}
distro=${2:?Debian12|Debian13|Ubuntu2404}
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
case "$component" in
  client) crate="$repo_root/upstream/uds-client" ;;
  agent)  crate="$repo_root/upstream/uds-actor" ;;
  *) echo "unknown component $component" >&2; exit 2 ;;
esac
builders="$crate/building/linux/builders"

if [[ "$distro" == "Ubuntu2404" && ! -d "$builders/Ubuntu2404" ]]; then
  echo "== generating Ubuntu 24.04 builder from Debian 13" >&2
  mkdir -p "$builders/Ubuntu2404"
  sed -e 's|^FROM debian:trixie|FROM ubuntu:24.04|' -e 's|libusb-1.0.0-dev|libusb-1.0-0-dev|' \
    "$builders/Debian13/Dockerfile" >"$builders/Ubuntu2404/Dockerfile"
fi
[[ -f "$builders/$distro/Dockerfile" ]] || { echo "no builder for $distro" >&2; exit 2; }
echo "$builders/$distro"
