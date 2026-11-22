# Sets LIBREVDI_VERSION (installer/file name) and LIBREVDI_VIVERSION (numeric a.b.c.d for the
# Windows file properties) for the following GitHub Actions steps.
#
#   set-version.ps1 <version or empty> <run number>
#     "0.2.0"         -> 0.2.0           / 0.2.0.0
#     "0.2.0-rc.1"    -> 0.2.0-rc.1      / 0.2.0.1
#     ""  (CI build)  -> 0.1.0-dev.<run> / 0.1.0.<run>
param([string]$Version = "", [int]$RunNumber = 0)
$ErrorActionPreference = "Stop"

if (-not $Version) { $Version = "0.1.0-dev.$RunNumber" }
if ($Version -notmatch '^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$') {
    throw "invalid version '$Version' (expected semantic version, e.g. 0.2.0 or 0.2.0-rc.1)"
}
$build = 0
if ($Matches[4]) {
    # last number of the pre-release part (rc.1 -> 1, dev.42 -> 42), capped to the 16-bit field
    $nums = [regex]::Matches($Matches[4], '\d+')
    if ($nums.Count -gt 0) { $build = [Math]::Min([int]$nums[$nums.Count - 1].Value, 65535) }
}
$vi = "$($Matches[1]).$($Matches[2]).$($Matches[3]).$build"
Write-Host "LibreVDI version $Version (file version $vi)"
if ($env:GITHUB_ENV) {
    "LIBREVDI_VERSION=$Version" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
    "LIBREVDI_VIVERSION=$vi" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
}
