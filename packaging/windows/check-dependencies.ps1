# Fails if an .exe/.dll in the given directory imports a DLL that is neither shipped in that
# directory nor part of a standard Windows installation (e.g. VCRUNTIME140.dll, MSVCP140.dll).
# Uses dumpbin from the Visual Studio installation of the build host.
param([Parameter(Mandatory = $true)][string]$Dir)
$ErrorActionPreference = "Stop"

$vs = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -property installationPath
$dumpbin = Get-ChildItem "$vs\VC\Tools\MSVC\*\bin\Hostx64\x64\dumpbin.exe" | Select-Object -Last 1
if (-not $dumpbin) { throw "dumpbin.exe not found" }

$shipped = @{}
Get-ChildItem $Dir -Filter *.dll | ForEach-Object { $shipped[$_.Name.ToLowerInvariant()] = $true }

# DLLs that are part of every Windows 10/11 installation (System32), incl. API sets and the UCRT
function Test-SystemDll([string]$name) {
    $n = $name.ToLowerInvariant()
    if ($n.StartsWith("api-ms-win-") -or $n.StartsWith("ext-ms-")) { return $true }
    if ($n -eq "ucrtbase.dll") { return $true }
    if ($n -like "vcruntime*" -or $n -like "msvcp*" -or $n -like "concrt*" -or $n -like "vccorlib*") { return $false }
    return Test-Path (Join-Path $env:WINDIR "System32\$n")
}

$missing = @()
Get-ChildItem $Dir -Include *.exe, *.dll -Recurse | ForEach-Object {
    $file = $_
    $deps = & $dumpbin.FullName /nologo /dependents $file.FullName |
        Where-Object { $_ -match '^\s+(\S+\.dll)\s*$' } | ForEach-Object { $Matches[1] }
    foreach ($d in $deps) {
        if (-not $shipped.ContainsKey($d.ToLowerInvariant()) -and -not (Test-SystemDll $d)) {
            $missing += "$($file.Name) -> $d"
        }
    }
}

if ($missing.Count -gt 0) {
    Write-Host "Missing runtime dependencies:"
    $missing | Sort-Object -Unique | ForEach-Object { Write-Host "  $_" }
    exit 1
}
Write-Host "All DLL dependencies are shipped or part of Windows."
