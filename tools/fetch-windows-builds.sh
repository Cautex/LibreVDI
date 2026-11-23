#!/usr/bin/env bash
# Downloads the Windows installers (agent + client) into ./downloads, so LibreVDI can offer them
# in the portal / admin UI. Release images already contain the installers of their release;
# this is for newer builds or self-built images.
#
#   RELEASE=v0.2.0 tools/fetch-windows-builds.sh      # assets of a published release, no token
#   GITHUB_TOKEN=<token> tools/fetch-windows-builds.sh # latest successful CI run
#
# GITHUB_TOKEN: GitHub token that may read Actions artifacts of the repository
#               (fine-grained token: repository access to this repo, permission "Actions: read").
#               Downloading artifacts always needs a token, even for public repositories.
# Optional:     REPO (default Cautex/LibreVDI), BRANCH (default: any branch), RUN_ID (specific run)
set -euo pipefail

REPO="${REPO:-Cautex/LibreVDI}"
WORKFLOW="windows-builds.yml"
DEST="$(cd "$(dirname "$0")/.." && pwd)/downloads"
API="https://api.github.com/repos/${REPO}"

if [[ -n "${RELEASE:-}" ]]; then
  mkdir -p "$DEST"
  find "$DEST" -maxdepth 1 -name 'LibreVDI-*-Setup-*.exe' -delete
  echo "== release ${RELEASE}"
  curl -fsSL "${API}/releases/tags/${RELEASE}" |
    python3 -c 'import json,sys
for a in json.load(sys.stdin)["assets"]:
    if a["name"].startswith("LibreVDI-") and a["name"].endswith(".exe") or a["name"] == "SHA256SUMS":
        print(a["name"], a["browser_download_url"])' |
    while read -r name url; do
      curl -fsSL -o "${DEST}/${name}" "$url"
      echo "   ${name}"
    done
  (cd "$DEST" && grep 'LibreVDI-.*\.exe$' SHA256SUMS | sha256sum -c -) && rm -f "${DEST}/SHA256SUMS"
  echo "== saved to ${DEST}. Activate with: docker compose restart broker-web"
  exit 0
fi

TOKEN="${GITHUB_TOKEN:?set GITHUB_TOKEN (needs Actions: read), or RELEASE=<tag> for a published release}"

gh_api() {
  curl -fsSL -H "Authorization: Bearer ${TOKEN}" -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" "$@"
}

if [[ -z "${RUN_ID:-}" ]]; then
  query="status=success&per_page=1"
  [[ -n "${BRANCH:-}" ]] && query="${query}&branch=${BRANCH}"
  RUN_ID=$(gh_api "${API}/actions/workflows/${WORKFLOW}/runs?${query}" |
    python3 -c 'import json,sys; r=json.load(sys.stdin)["workflow_runs"]; print(r[0]["id"] if r else "")')
  [[ -n "$RUN_ID" ]] || { echo "no successful run of ${WORKFLOW} found" >&2; exit 1; }
fi
echo "== run ${RUN_ID}"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

gh_api "${API}/actions/runs/${RUN_ID}/artifacts" |
  python3 -c 'import json,sys
for a in json.load(sys.stdin)["artifacts"]:
    if not a["expired"]:
        print(a["name"], a["archive_download_url"])' |
  while read -r name url; do
    echo "== artifact ${name}"
    gh_api -o "${tmp}/${name}.zip" "$url"
    python3 -m zipfile -e "${tmp}/${name}.zip" "${tmp}/${name}"
  done

mkdir -p "$DEST"
if find "$tmp" -name 'LibreVDI-*-Setup-*.exe' | grep -q .; then
  # keep only the version being fetched (older installers would just pile up)
  find "$DEST" -maxdepth 1 -name 'LibreVDI-*-Setup-*.exe' -delete
fi
found=0
while IFS= read -r -d '' f; do
  cp -f "$f" "$DEST/"
  echo "   $(basename "$f")"
  found=1
done < <(find "$tmp" -name 'LibreVDI-*-Setup-*.exe' -print0)

[[ $found -eq 1 ]] || { echo "no LibreVDI installers in the artifacts" >&2; exit 1; }
echo "== saved to ${DEST}. Activate with: docker compose restart broker-web"
