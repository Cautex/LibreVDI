#!/usr/bin/env bash
# Prepares a Linux desktop VM for LibreVDI in one run (docs/anleitung-linux-desktop.md, parts 1-4):
#
#   * RDP server: GNOME Remote Desktop "Remote Login" (Ubuntu 24.04/26.04, Rocky 10) or xrdp (Rocky 9)
#   * no automatic login, QEMU guest agent, firewall ports 3389 (RDP) and 43910 (agent)
#   * LibreVDI agent (unmanaged) installed from a local package and configured
#   * GNOME idle logout (GNOME Remote Desktop only; the agent cannot measure idle time under Wayland)
#
# Run as root inside the VM; copy the agent package (admin UI -> Downloads) next to it first:
#
#   sudo tools/setup-linux-desktop.sh --broker vdi.example.com [--agent-package FILE]
#        [--rdp-user rdp-vdi] [--idle-logout MINUTES] [--no-verify-ssl] [--dry-run]
#
# Asked interactively (never on the command line): the service token of the LibreVDI service and,
# for GNOME Remote Desktop, the password of the RDP account (enter it in the LibreVDI transport).
# Non-interactive: LIBREVDI_TOKEN_FILE=<file> and LIBREVDI_RDP_PASSWORD_FILE=<file>.
# --dry-run prints what would be done without changing anything.
set -euo pipefail

broker=""
agent_package=""
rdp_user="rdp-vdi"
idle_minutes=30
verify_flag=()
dry_run=0

usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --broker) broker=${2:-}; shift 2 ;;
    --agent-package) agent_package=${2:-}; shift 2 ;;
    --rdp-user) rdp_user=${2:-}; shift 2 ;;
    --idle-logout) idle_minutes=${2:-}; shift 2 ;;
    --no-verify-ssl) verify_flag=(--no-verify-ssl); shift ;;
    --dry-run) dry_run=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "unknown option: $1" >&2; usage 2 ;;
  esac
done

say() { printf '\n== %s\n' "$*"; }
run() {  # prints and runs a command (only prints with --dry-run)
  printf '   $ %s\n' "$*"
  [[ $dry_run -eq 1 ]] || "$@"
}
die() { echo "ERROR: $*" >&2; exit 1; }
write_file() {  # write_file <path> <mode> <content> (only prints with --dry-run)
  printf '   write %s (mode %s)\n' "$1" "$2"
  [[ $dry_run -eq 1 ]] && return 0
  printf '%s' "$3" >"$1"
  chmod "$2" "$1"
}

[[ -n "$broker" ]] || die "--broker <domain> is required"
[[ "$idle_minutes" =~ ^[0-9]+$ ]] || die "--idle-logout needs minutes (0 = off)"
[[ "$rdp_user" =~ ^[A-Za-z0-9._-]+$ ]] || die "--rdp-user: letters, digits, . _ - only"
[[ $dry_run -eq 1 || $(id -u) -eq 0 ]] || die "run as root (sudo)"

# --- distribution --------------------------------------------------------------------------------
[[ -r /etc/os-release ]] || die "/etc/os-release missing"
# shellcheck disable=SC1091
. /etc/os-release
major=${VERSION_ID%%.*}
case "${ID:-}:${major}" in
  ubuntu:24|ubuntu:26)              family=ubuntu; rdp=grd;  distro="Ubuntu ${VERSION_ID}" ;;
  rocky:10|almalinux:10|rhel:10)    family=el;     rdp=grd;  distro="${NAME} ${VERSION_ID}" ;;
  rocky:9|almalinux:9|rhel:9)       family=el;     rdp=xrdp; distro="${NAME} ${VERSION_ID}" ;;
  *) die "unsupported distribution ${PRETTY_NAME:-unknown} (supported: Ubuntu 24.04/26.04, Rocky Linux 9/10)" ;;
esac
say "$distro - RDP server: $([[ $rdp == grd ]] && echo 'GNOME Remote Desktop (Remote Login)' || echo xrdp)"

if [[ -z "$agent_package" ]]; then
  if [[ $family == ubuntu ]]; then
    pattern="librevdi-agent-unmanaged_*_amd64-ubuntu${VERSION_ID//./}.deb"
  else
    pattern="librevdi-agent-unmanaged-*.x86_64-rocky${major}.rpm"
  fi
  agent_package=$(find . -maxdepth 1 -name "$pattern" | sort -V | tail -n 1)
fi
[[ -n "$agent_package" && -f "$agent_package" ]] \
  || die "agent package not found - copy it from the admin UI (Downloads) or pass --agent-package FILE"
agent_package=$(realpath "$agent_package")
expected=$([[ $family == ubuntu ]] && echo "ubuntu${VERSION_ID//./}" || echo "rocky${major}")
[[ "$(basename "$agent_package")" == *"-$expected".* ]] \
  || die "$(basename "$agent_package") is not the package for $distro (expected *-$expected.*)"

# --- secrets (read once, never echoed or put on a command line we print) -------------------------
read_secret() {  # read_secret <prompt> <file variable>
  local file=${!2:-} value
  if [[ -n "$file" ]]; then
    IFS= read -r value <"$file"
  elif [[ -t 0 ]]; then
    read -r -s -p "$1: " value; echo >&2
  else
    IFS= read -r value
  fi
  printf '%s' "$value" | tr -d '\r\n'
}
token=$(read_secret "Service token of the LibreVDI service" LIBREVDI_TOKEN_FILE)
[[ "$token" =~ ^[A-Za-z0-9_-]+$ ]] || die "service token empty or unexpected characters"
rdp_password=""
if [[ $rdp == grd ]]; then
  rdp_password=$(read_secret "New password for the RDP account '$rdp_user' (min. 12 characters)" LIBREVDI_RDP_PASSWORD_FILE)
  [[ ${#rdp_password} -ge 12 ]] || die "RDP password too short (min. 12 characters)"
fi

# --- packages ------------------------------------------------------------------------------------
say "Packages"
if [[ $family == ubuntu ]]; then
  export DEBIAN_FRONTEND=noninteractive
  run apt-get update -qq
  run apt-get install -y -qq qemu-guest-agent openssl gnome-remote-desktop
else
  run dnf install -y -q epel-release
  if [[ $rdp == grd ]]; then
    run dnf install -y -q qemu-guest-agent openssl gnome-remote-desktop
  else
    run dnf install -y -q qemu-guest-agent xrdp xorgxrdp
  fi
fi
run systemctl enable --now qemu-guest-agent

# --- no automatic login (a session logged in locally blocks the RDP login of the same account) ---
say "Disable automatic login"
for conf in /etc/gdm3/custom.conf /etc/gdm/custom.conf; do
  [[ -f "$conf" ]] || continue
  run sed -i -E 's/^\s*AutomaticLoginEnable\s*=.*/AutomaticLoginEnable=false/; s/^\s*TimedLoginEnable\s*=.*/TimedLoginEnable=false/' "$conf"
done

# --- RDP server ----------------------------------------------------------------------------------
if [[ $rdp == grd ]]; then
  say "GNOME Remote Desktop - Remote Login"
  grd_home=$(getent passwd gnome-remote-desktop | cut -d: -f6 || true)
  [[ -n "$grd_home" || $dry_run -eq 1 ]] || die "user gnome-remote-desktop missing (package gnome-remote-desktop installed?)"
  grd_dir="${grd_home:-/var/lib/gnome-remote-desktop}/.local/share/gnome-remote-desktop"
  run install -d -o gnome-remote-desktop -g gnome-remote-desktop -m 0700 "$grd_dir"
  if [[ ! -s "$grd_dir/tls.crt" ]]; then
    run runuser -u gnome-remote-desktop -- openssl req -new -newkey rsa:4096 -days 3650 -nodes -x509 \
      -subj "/CN=$(hostname -f 2>/dev/null || hostname)" -keyout "$grd_dir/tls.key" -out "$grd_dir/tls.crt"
  fi
  run grdctl --system rdp set-tls-key "$grd_dir/tls.key"
  run grdctl --system rdp set-tls-cert "$grd_dir/tls.crt"
  printf '   $ grdctl --system rdp set-credentials %s ********\n' "$rdp_user"
  if [[ $dry_run -eq 0 ]]; then
    if grdctl --help 2>&1 | grep -q 'set-credentials \[<username> \[<password>\]\]'; then
      printf '%s\n' "$rdp_password" | grdctl --system rdp set-credentials "$rdp_user"   # GNOME 47+: stdin
    else
      grdctl --system rdp set-credentials "$rdp_user" "$rdp_password"                  # GNOME 46
    fi
  fi
  run grdctl --system rdp enable
  run systemctl enable --now gnome-remote-desktop.service
  run systemctl set-default graphical.target
else
  say "xrdp (GNOME on Xorg)"
  run systemctl enable --now xrdp
  # GNOME for xrdp sessions of new and existing users
  write_file /etc/skel/.Xclients 0755 $'gnome-session\n'
  for home in /home/*; do
    [[ -d "$home" && ! -e "$home/.Xclients" ]] || continue
    owner=$(stat -c %U "$home")
    write_file "$home/.Xclients" 0755 $'gnome-session\n'
    run chown "$owner": "$home/.Xclients"
  done
fi

# --- firewall ------------------------------------------------------------------------------------
say "Firewall (3389 RDP, 43910 agent)"
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q '^Status: active'; then
  run ufw allow 3389/tcp
  run ufw allow 43910/tcp
elif command -v firewall-cmd >/dev/null && firewall-cmd --state >/dev/null 2>&1; then
  run firewall-cmd --permanent --add-port=3389/tcp --add-port=43910/tcp
  run firewall-cmd --reload
else
  echo "   no active firewall (ufw/firewalld) - nothing to do"
fi

# --- LibreVDI agent ------------------------------------------------------------------------------
say "LibreVDI agent ($(basename "$agent_package"))"
if [[ $family == ubuntu ]]; then
  run apt-get install -y -qq "$agent_package"
else
  run dnf install -y -q "$agent_package"
fi
printf '   $ librevdi-agent-configure --broker %s %s < (token)\n' "$broker" "${verify_flag[*]:-}"
if [[ $dry_run -eq 0 ]]; then
  printf '%s\n' "$token" | librevdi-agent-configure --broker "$broker" "${verify_flag[@]}"
fi

# --- GNOME idle logout -----------------------------------------------------------------------------
if [[ $rdp == grd ]]; then
  say "GNOME idle logout: $([[ $idle_minutes -gt 0 ]] && echo "after $idle_minutes minutes" || echo off)"
  if [[ $idle_minutes -gt 0 ]]; then
    run install -d /etc/dconf/profile /etc/dconf/db/local.d
    [[ -f /etc/dconf/profile/user ]] || write_file /etc/dconf/profile/user 0644 $'user-db:user\nsystem-db:local\n'
    write_file /etc/dconf/db/local.d/50-librevdi-idle 0644 "[org/gnome/settings-daemon/plugins/power]
sleep-inactive-ac-type='logout'
sleep-inactive-ac-timeout=$((idle_minutes * 60))
"
  else
    run rm -f /etc/dconf/db/local.d/50-librevdi-idle
  fi
  run dconf update
fi

# --- summary -------------------------------------------------------------------------------------
say "Done$([[ $dry_run -eq 1 ]] && echo ' (dry run - nothing changed)')"
cat <<EOF
   Next steps in the LibreVDI admin UI (docs/anleitung-linux-desktop.md, part 3 and 5):
   - assign this VM to its user (pool -> Assigned services -> Assign service)
EOF
if [[ $rdp == grd ]]; then
  cat <<EOF
   - transport for this pool: RDP with Username '$rdp_user' and the password you just entered
     (the user then logs in with their own Linux account on the GNOME login screen)
   - reboot once so GDM starts with Remote Login: sudo reboot
EOF
else
  cat <<EOF
   - transport for this pool: RDP direct (users log in with their Linux account)
EOF
fi
