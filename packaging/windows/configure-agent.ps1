# Writes the LibreVDI Agent (unmanaged) configuration exactly like the configuration program does
# (upstream/uds-actor: crates/config-unmanaged/src/callbacks.rs + crates/shared/src/windows/config.rs):
#
#   HKLM\SOFTWARE\UDSActor, default value, REG_BINARY = ASCII bytes of Base64(JSON ActorConfiguration)
#   key permissions: inheritance disabled, BUILTIN\Users removed (normal users cannot read the token)
#
# Called by the installer for silent installs:
#   LibreVDI-Agent-unmanaged-Setup-<ver>.exe /S /BROKER=vdi.example.com /TOKEN=<service token>
# Can also be run on its own (as administrator):
#   powershell -ExecutionPolicy Bypass -File configure-agent.ps1 -Broker vdi.example.com -Token <token>
param(
    [Parameter(Mandatory = $true)][string]$Broker,
    [Parameter(Mandatory = $true)][string]$Token,
    [string]$VerifySsl = "1",
    [ValidateSet("debug", "info", "warn", "warning", "error", "fatal")][string]$LogLevel = "warn",
    [string]$Net = ""
)
$ErrorActionPreference = "Stop"

$levels = @{ debug = 20000; info = 30000; warn = 40000; warning = 40000; error = 50000; fatal = 60000 }
$hostName = $Broker.Trim() -replace '^https?://', '' -replace '/.*$', ''
if (-not $hostName) { throw "Broker host is empty" }
if (-not $Token.Trim()) { throw "Service token is empty" }

$cfg = [ordered]@{
    broker_url      = "https://$hostName/uds/rest/"
    verify_ssl      = ($VerifySsl -notin @("0", "false", "no"))
    actor_type      = "unmanaged"
    master_token    = $Token.Trim()
    own_token       = $null
    restrict_net    = $(if ($Net.Trim()) { $Net.Trim() } else { $null })
    pre_command     = $null
    runonce_command = $null
    post_command    = $null
    log_level       = $levels[$LogLevel.ToLower()]
    config          = [ordered]@{ unique_id = $null; os = $null; ssl_ciphers = $null }
    data            = $null
}
$json = $cfg | ConvertTo-Json -Compress -Depth 5
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))

# Always the 64-bit registry view (the installer itself is a 32-bit process)
$base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
    [Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryView]::Registry64)
$base.CreateSubKey("SOFTWARE\UDSActor").Close()
# reopen with full control: changing the permissions needs WRITE_DAC
$key = $base.OpenSubKey("SOFTWARE\UDSActor",
    [Microsoft.Win32.RegistryKeyPermissionCheck]::ReadWriteSubTree,
    [System.Security.AccessControl.RegistryRights]::FullControl)

# Same protection as the agent: no inheritance, no access for BUILTIN\Users
$acl = $key.GetAccessControl()
$acl.SetAccessRuleProtection($true, $true)
$key.SetAccessControl($acl)
$acl = $key.GetAccessControl()
$acl.PurgeAccessRules([Security.Principal.SecurityIdentifier]::new("S-1-5-32-545"))
$key.SetAccessControl($acl)

$key.SetValue("", [Text.Encoding]::ASCII.GetBytes($encoded), [Microsoft.Win32.RegistryValueKind]::Binary)
$key.Close()
Write-Output "LibreVDI Agent configured for broker $hostName (unmanaged, verify_ssl=$($cfg.verify_ssl), log level $LogLevel)"
