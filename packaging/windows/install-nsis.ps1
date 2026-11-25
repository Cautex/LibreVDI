# Makes makensis available on a Windows CI runner and adds it to PATH for the following steps.
# Order: already on PATH -> default install dir (also restored from the actions cache) ->
# Chocolatey with retries (the community feed is sometimes unavailable, HTTP 503).
$ErrorActionPreference = "Stop"
$dir = Join-Path ${env:ProgramFiles(x86)} "NSIS"

function Publish-Path {
    if ($env:GITHUB_PATH) { $dir | Out-File -FilePath $env:GITHUB_PATH -Append -Encoding utf8 }
    $env:PATH += ";$dir"
}

if (Get-Command makensis -ErrorAction SilentlyContinue) { Write-Host "makensis already on PATH"; exit 0 }
if (Test-Path (Join-Path $dir "makensis.exe")) { Write-Host "makensis found in $dir"; Publish-Path; exit 0 }

for ($attempt = 1; $attempt -le 5; $attempt++) {
    Write-Host "== installing NSIS via Chocolatey (attempt $attempt/5)"
    choco install nsis -y --no-progress
    if ($LASTEXITCODE -eq 0 -and (Test-Path (Join-Path $dir "makensis.exe"))) { Publish-Path; exit 0 }
    Start-Sleep -Seconds (20 * $attempt)
}
throw "NSIS could not be installed (Chocolatey unavailable?)"
