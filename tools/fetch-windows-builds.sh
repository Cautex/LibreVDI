#!/usr/bin/env bash
# Downloads the LibreVDI installers and packages (Windows .exe, Linux .deb/.rpm; agent + client) into
# ./downloads, so LibreVDI can offer them in the portal / admin UI. Release images already contain
# the installers of their release; this is for newer builds or self-built images.
#
#   RELEASE=v0.2.0 tools/fetch-windows-builds.sh      # assets of a published release, no token
#   GITHUB_TOKEN=<token> tools/fetch-windows-builds.sh # latest successful CI run
#
# GITHUB_TOKEN: GitHub token that may read Actions artifacts of the repository
#               (fine-grained token: repository access to this repo, permission "Actions: read").
#               Downloading artifacts always needs a token, even for public repositories.
# Optional:     REPO (default Cautex/LibreVDI), BRANCH (default: any branch),
#               WORKFLOWS (default "windows-builds.yml linux-builds.yml"), RUN_ID (one specific run)
set -euo pipefail

REPO="${REPO:-Cautex/LibreVDI}"
WORKFLOWS="${WORKFLOWS:-windows-builds.yml linux-builds.yml}"
DEST="$(cd "$(dirname "$0")/.." && pwd)/downloads"
API="https://api.github.com/repos/${REPO}"

if [[ -n "${RELEASE:-}" ]]; then
  mkdir -p "$DEST"
  find "$DEST" -maxdepth 1 \( -name 'LibreVDI-*-Setup-*.exe' -o -name 'librevdi-*.deb' -o -name 'librevdi-*.rpm' \) -delete
  echo "== release ${RELEASE}"
  curl -fsSL "${API}/releases/tags/${RELEASE}" |
    python3 -c 'import json,sys
for a in json.load(sys.stdin)["assets"]:
    n = a["name"]
    if n.startswith("LibreVDI-") and n.endswith(".exe") or n.startswith("librevdi-") and n.endswith((".deb", ".rpm")) \
            or n == "SHA256SUMS":
        print(a["name"], a["browser_download_url"])' |
    while read -r name url; do
      curl -fsSL -o "${DEST}/${name}" "$url"
      echo "   ${name}"
    done
  (cd "$DEST" && grep -E 'LibreVDI-.*\.exe$|librevdi-.*\.(deb|rpm)$' SHA256SUMS | sha256sum -c -) && rm -f "${DEST}/SHA256SUMS"
  echo "== saved to ${DEST}. Activate with: docker compose restart broker-web"
  exit 0
fi

TOKEN="${GITHUB_TOKEN:?set GITHUB_TOKEN (needs Actions: read), or RELEASE=<tag> for a published release}"

gh_api() {
  curl -fsSL -H "Authorization: Bearer ${TOKEN}" -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" "$@"
}

latest_run() {
  local query="status=success&per_page=1"
  [[ -n "${BRANCH:-}" ]] && query="${query}&branch=${BRANCH}"
  gh_api "${API}/actions/workflows/$1/runs?${query}" |
    python3 -c 'import json,sys; r=json.load(sys.stdin)["workflow_runs"]; print(r[0]["id"] if r else "")'
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

runs=()
if [[ -n "${RUN_ID:-}" ]]; then
  runs=("$RUN_ID")
else
  for wf in $WORKFLOWS; do
    run=$(latest_run "$wf")
    if [[ -z "$run" ]]; then echo "== no successful run of ${wf} (skipped)"; continue; fi
    runs+=("$run")
  done
fi
[[ ${#runs[@]} -gt 0 ]] || { echo "no successful runs found" >&2; exit 1; }

for run in "${runs[@]}"; do
  echo "== run ${run}"
  gh_api "${API}/actions/runs/${run}/artifacts" |
    python3 -c 'import json,sys
for a in json.load(sys.stdin)["artifacts"]:
    if not a["expired"]:
        print(a["name"], a["archive_download_url"])' |
    while read -r name url; do
      echo "== artifact ${name}"
      gh_api -o "${tmp}/${name}.zip" "$url"
      python3 -m zipfile -e "${tmp}/${name}.zip" "${tmp}/${name}"
    done
done

mkdir -p "$DEST"
found=0
for pattern in 'LibreVDI-*-Setup-*.exe' 'librevdi-*.deb' 'librevdi-*.rpm'; do
  # keep only the version being fetched (older installers would just pile up)
  find "$tmp" -name "$pattern" | grep -q . || continue
  find "$DEST" -maxdepth 1 -name "$pattern" -delete
  while IFS= read -r -d '' f; do
    cp -f "$f" "$DEST/"
    echo "   $(basename "$f")"
    found=1
  done < <(find "$tmp" -name "$pattern" -print0)
done

[[ $found -eq 1 ]] || { echo "no LibreVDI installers or packages in the artifacts" >&2; exit 1; }
echo "== saved to ${DEST}. Activate with: docker compose restart broker-web"
