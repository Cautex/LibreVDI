#!/usr/bin/env bash
# Installs LibreVDI packages (.deb or .rpm) into a clean container of the target distribution and
# checks that every installed program finds all its shared libraries, that the license notices are
# in the package and that the agent configuration tool works.
#
#   packaging/linux/test-install.sh Ubuntu2404|Ubuntu2604|Rocky9|Rocky10 <dir with packages>
set -euo pipefail

distro=${1:?distro}
dir=$(realpath "${2:?package directory}")
case "$distro" in
  Ubuntu2404) image=ubuntu:24.04 ;;
  Ubuntu2604) image=ubuntu:26.04 ;;
  Rocky9)     image=rockylinux/rockylinux:9 ;;
  Rocky10)    image=rockylinux/rockylinux:10 ;;
  *) echo "unknown distro $distro" >&2; exit 2 ;;
esac

# shellcheck disable=SC2016  # evaluated by the shell inside the container
common='
missing=0
for f in $(files); do
  [ -f "$f" ] || continue
  case "$f" in /usr/lib/.build-id/*) continue ;; esac   # RPM build-id links ($ORIGIN differs)
  if head -c 4 "$f" | grep -q ELF; then
    # programs must resolve everything (rpath $ORIGIN); bundled libraries find each other only
    # once the launcher has loaded them, so they are checked with their own directory
    case "$f" in *.so|*.so.*) lp=$(dirname "$f") ;; *) lp= ;; esac
    if LD_LIBRARY_PATH="$lp" ldd "$f" 2>/dev/null | grep "not found"; then
      echo "missing libraries for $f"; missing=1
    else
      echo "ok    $f"
    fi
  fi
done
[ $missing -eq 0 ]
# checked in the package: minimised images (ubuntu:*) do not install /usr/share/doc
contents | grep -q "/usr/share/doc/$pkg/THIRD-PARTY-NOTICES.txt"
echo "ok    third-party license notices"
if [ "$pkg" = librevdi-agent-unmanaged ]; then
  echo ci-test-token-0123456789 | librevdi-agent-configure --broker vdi.example.test --no-restart
  grep -q "master_token = \"ci-test-token-0123456789\"" /etc/udsactor/udsactor.cfg
  [ "$(stat -c %a /etc/udsactor/udsactor.cfg)" = 600 ]
  echo "ok    librevdi-agent-configure"
fi
grep -l LibreVDI $(files | grep -E "\.desktop$") >/dev/null 2>&1 && echo "ok    desktop entries branded" || true
'

shopt -s nullglob
packages=("$dir"/*.deb "$dir"/*.rpm)
[[ ${#packages[@]} -gt 0 ]] || { echo "no packages in $dir" >&2; exit 1; }
for package in "${packages[@]}"; do
  name=$(basename "$package")
  echo "== install test: $name on $image"
  if [[ "$name" == *.deb ]]; then
    # shellcheck disable=SC2016
    setup='
      apt-get update -qq
      apt-get install -y -qq "/pkgs/$file" >/tmp/install.log 2>&1 || { tail -30 /tmp/install.log; exit 1; }
      pkg=$(dpkg-deb -f "/pkgs/$file" Package)
      echo "installed $pkg $(dpkg-query -W -f="\${Version}" "$pkg")"
      files() { dpkg -L "$pkg"; }
      contents() { dpkg-deb -c "/pkgs/$file"; }'
  else
    # EPEL provides the FFmpeg libraries of the client (documented in the Rocky guide)
    # shellcheck disable=SC2016
    setup='
      dnf install -y -q epel-release >/dev/null
      dnf install -y -q "/pkgs/$file" >/tmp/install.log 2>&1 || { tail -30 /tmp/install.log; exit 1; }
      pkg=$(rpm -qp --qf "%{NAME}" "/pkgs/$file")
      echo "installed $pkg $(rpm -q --qf "%{VERSION}-%{RELEASE}" "$pkg")"
      files() { rpm -ql "$pkg"; }
      contents() { rpm -qlp "/pkgs/$file"; }'
  fi
  docker run --rm -e DEBIAN_FRONTEND=noninteractive -e file="$name" -v "$dir:/pkgs:ro" "$image" \
    sh -ec "$setup
$common"
done
echo "== install test passed for $distro"
