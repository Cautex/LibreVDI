#!/usr/bin/env bash
# Installs LibreVDI .deb packages into a clean container of the target distribution and checks
# that every installed program finds all its shared libraries.
#
#   packaging/linux/test-install.sh Debian12|Debian13|Ubuntu2404 <dir with .deb files>
set -euo pipefail

distro=${1:?distro}
dir=$(realpath "${2:?package directory}")
case "$distro" in
  Debian12)   image=debian:bookworm ;;
  Debian13)   image=debian:trixie ;;
  Ubuntu2404) image=ubuntu:24.04 ;;
  *) echo "unknown distro $distro" >&2; exit 2 ;;
esac

for deb in "$dir"/*.deb; do
  name=$(basename "$deb")
  echo "== install test: $name on $image"
  docker run --rm -e DEBIAN_FRONTEND=noninteractive -v "$dir:/pkgs:ro" "$image" sh -ec "
    apt-get update -qq
    apt-get install -y -qq /pkgs/$name >/tmp/apt.log 2>&1 || { tail -30 /tmp/apt.log; exit 1; }
    pkg=\$(dpkg-deb -f /pkgs/$name Package)
    echo \"installed \$pkg \$(dpkg-query -W -f='\${Version}' \$pkg)\"
    missing=0
    for f in \$(dpkg -L \$pkg); do
      [ -f \"\$f\" ] || continue
      if head -c 4 \"\$f\" | grep -q ELF; then
        dir=\$(dirname \"\$f\")
        if LD_LIBRARY_PATH=\"\$dir\" ldd \"\$f\" 2>/dev/null | grep 'not found'; then
          echo \"missing libraries for \$f\"; missing=1
        else
          echo \"ok    \$f\"
        fi
      fi
    done
    [ \$missing -eq 0 ]
    # checked in the package: minimised images (ubuntu:24.04) do not install /usr/share/doc
    dpkg-deb -c /pkgs/$name | grep -q \"./usr/share/doc/\$pkg/THIRD-PARTY-NOTICES.txt\"
    echo 'ok    third-party license notices'
    if [ \"\$pkg\" = librevdi-agent-unmanaged ]; then
      echo ci-test-token-0123456789 | librevdi-agent-configure --broker vdi.example.test --no-restart
      grep -q 'master_token = \"ci-test-token-0123456789\"' /etc/udsactor/udsactor.cfg
      [ \"\$(stat -c %a /etc/udsactor/udsactor.cfg)\" = 600 ]
      echo 'ok    librevdi-agent-configure'
    fi
    grep -l 'LibreVDI' \$(dpkg -L \$pkg | grep -E '\\.desktop\$') >/dev/null 2>&1 && echo 'ok    desktop entries branded' || true
  "
done
echo "== install test passed for $distro"
