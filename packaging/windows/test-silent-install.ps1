# End-to-end test of the silent agent installation on a Windows CI runner (needs admin rights).
#   test-silent-install.ps1 <dir with LibreVDI-Agent-unmanaged-Setup-*.exe>
# Installs silently with /BROKER /TOKEN, checks configuration (format, permissions), autostart,
# service and start menu entry, then uninstalls silently and checks the cleanup.
param([Parameter(Mandatory = $true)][string]$Dir)
$ErrorActionPreference = "Stop"
$failures = 0
function Check([bool]$ok, [string]$what) {
    if ($ok) { Write-Host "ok    $what" } else { Write-Host "FAIL  $what"; $script:failures++ }
}

$setup = Get-ChildItem (Join-Path $Dir "LibreVDI-Agent-unmanaged-Setup-*.exe") | Select-Object -First 1
if (-not $setup) { throw "no unmanaged agent installer in $Dir" }
Write-Host "== silent install: $($setup.Name)"
$p = Start-Process -FilePath $setup.FullName -Wait -PassThru `
    -ArgumentList "/S", "/BROKER=vdi.example.test", "/TOKEN=ci-test-token-0123456789", "/LOGLEVEL=debug"
Check ($p.ExitCode -eq 0) "installer exit code 0 (got $($p.ExitCode))"

$installDir = Join-Path $env:ProgramFiles "LibreVDI\Agent"
Check (Test-Path (Join-Path $installDir "udsactor-service.exe")) "files installed in $installDir"
$log = Join-Path $installDir "install.log"
Check (Test-Path $log) "install.log written"
if (Test-Path $log) {
    Get-Content $log | ForEach-Object { Write-Host "      log: $_" }
    Check (-not (Select-String -Path $log -SimpleMatch "ci-test-token" -Quiet)) "install.log contains no token"
}

# Configuration as the agent stores it: Base64(JSON) in the default value, REG_BINARY
$base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
    [Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryView]::Registry64)
$key = $base.OpenSubKey("SOFTWARE\UDSActor")
Check ($null -ne $key) "registry key HKLM\SOFTWARE\UDSActor exists"
if ($key) {
    Check ($key.GetValueKind("") -eq [Microsoft.Win32.RegistryValueKind]::Binary) "default value is REG_BINARY"
    $raw = [Text.Encoding]::ASCII.GetString([byte[]]$key.GetValue(""))
    $cfg = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($raw)) | ConvertFrom-Json
    Check ($cfg.broker_url -eq "https://vdi.example.test/uds/rest/") "broker_url = $($cfg.broker_url)"
    Check ($cfg.master_token -eq "ci-test-token-0123456789") "master_token stored"
    Check ($cfg.actor_type -eq "unmanaged") "actor_type = unmanaged"
    Check ($cfg.verify_ssl -eq $true) "verify_ssl = true"
    Check ($cfg.log_level -eq 20000) "log_level = 20000 (debug)"

    $acl = $key.GetAccessControl()
    $users = [Security.Principal.SecurityIdentifier]::new("S-1-5-32-545")
    $userRules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]) |
        Where-Object { $_.IdentityReference -eq $users })
    Check ($acl.AreAccessRulesProtected) "key permissions: inheritance disabled"
    Check ($userRules.Count -eq 0) "key permissions: no access for BUILTIN\Users"
    $key.Close()
}

$run = Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -ErrorAction SilentlyContinue
Check ($run."LibreVDI Agent" -like "*udsactor-client.exe*") "autostart of the session helper"
Check ($null -ne (Get-Service LibreVDIAgent -ErrorAction SilentlyContinue)) "service LibreVDIAgent registered"
Check ($null -eq (Get-Service UDSActorService -ErrorAction SilentlyContinue)) "no old service UDSActorService"
$lnk = Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs\LibreVDI\LibreVDI Agent konfigurieren.lnk"
Check (Test-Path $lnk) "start menu entry for all users"
$uninstKey = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LibreVDI-Agent"
Check ((Get-ItemProperty $uninstKey -ErrorAction SilentlyContinue).DisplayIcon -like "*librevdi.ico") "Installed apps: icon"

Write-Host "== silent uninstall"
# _?= runs the uninstaller in place (otherwise it copies itself and returns immediately)
$u = Start-Process -FilePath (Join-Path $installDir "uninstall.exe") -Wait -PassThru `
    -ArgumentList "/S", "_?=$installDir"
Check ($u.ExitCode -eq 0) "uninstaller exit code 0 (got $($u.ExitCode))"
Start-Sleep -Seconds 3
Check ($null -eq (Get-Service LibreVDIAgent -ErrorAction SilentlyContinue)) "service removed"
$run = Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -ErrorAction SilentlyContinue
Check ($null -eq $run."LibreVDI Agent") "autostart removed"
Check (-not (Test-Path $lnk)) "start menu entry removed"

if ($failures) { throw "$failures check(s) failed" }
Write-Host "== silent installation test passed"
