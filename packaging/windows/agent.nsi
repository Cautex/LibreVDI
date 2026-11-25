; LibreVDI Agent installer (Windows x64)
; Packages the OpenUDS 5.0 actor (BSD-3-Clause, (c) Virtual Cable S.L.) built from upstream/uds-actor.
;
; Build (from repository root, after `cargo build --release` in upstream/uds-actor):
;   makensis /DVERSION=0.1.0 /DVARIANT=unmanaged packaging\windows\agent.nsi
;   makensis /DVERSION=0.1.0 /DVARIANT=managed   packaging\windows\agent.nsi
;
; VARIANT
;   unmanaged  persistent machines ("Proxmox Fixed Machines", static machines):
;              registers with a service token
;   managed    floating pools / linked clones with an OS manager:
;              registers with broker administrator credentials
;
; Silent installation (unmanaged): configures the agent and starts the service, no reboot needed
;   LibreVDI-Agent-unmanaged-Setup-<ver>.exe /S /BROKER=vdi.example.com /TOKEN=<service token>
;   optional: /VERIFYSSL=0 (self-signed certificate)  /LOGLEVEL=debug|info|warn|error

Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"

!ifndef VERSION
  !define VERSION "0.0.0-dev"
!endif
!ifndef VARIANT
  !define VARIANT "unmanaged"
!endif
!ifndef POWERSHELL
  !define POWERSHELL "powershell.exe"  ; overridable for tests
!endif
!ifndef SRCDIR
  !define SRCDIR "..\..\upstream\uds-actor\target\release"
!endif

!define PRODUCT "LibreVDI Agent"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\LibreVDI-Agent"

Name "${PRODUCT} (${VARIANT})"
OutFile "LibreVDI-Agent-${VARIANT}-Setup-${VERSION}.exe"
InstallDir "$PROGRAMFILES64\LibreVDI\Agent"
RequestExecutionLevel admin
SetCompressor /SOLID lzma

!ifndef VIVERSION
  !define VIVERSION "0.0.0.0"  ; numeric a.b.c.d for the Windows file properties
!endif
VIProductVersion "${VIVERSION}"
VIAddVersionKey "ProductName" "${PRODUCT}"
VIAddVersionKey "FileDescription" "${PRODUCT} installer (${VARIANT})"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "LibreVDI contributors; based on OpenUDS (BSD-3-Clause)"

!define MUI_ICON "..\..\branding\logo.ico"
!define MUI_UNICON "..\..\branding\logo.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\upstream\uds-actor\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "German"
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "LibreVDI Agent requires 64-bit Windows." /SD IDOK
    Abort
  ${EndIf}
  SetRegView 64
FunctionEnd

!macro MoveAside NAME
  IfFileExists "$INSTDIR\${NAME}" 0 +2
    Rename "$INSTDIR\${NAME}" "$INSTDIR\${NAME}.old"
!macroend

Section "Agent"
  ; stop a running agent (this or an older version) so its files can be replaced
  nsExec::Exec 'sc.exe stop LibreVDIAgent'
  nsExec::Exec 'sc.exe stop UDSActorService'
  ; helpers running in user sessions lock their files as well (restarted at the next login)
  nsExec::Exec 'taskkill.exe /F /IM udsactor-client.exe'
  nsExec::Exec 'taskkill.exe /F /IM gui-helper.exe'
  nsExec::Exec 'taskkill.exe /F /IM udsactor-config.exe'
  Sleep 3000
  ; files still in use cannot be overwritten but can be renamed (removed now or after a reboot)
  Delete "$INSTDIR\*.old"
  !insertmacro MoveAside "gui-helper.exe"
  !insertmacro MoveAside "udsactor-client.exe"
  !insertmacro MoveAside "udsactor-service.exe"
  !insertmacro MoveAside "udsactor-config.exe"
  SetOutPath $INSTDIR
  File /oname=librevdi.ico "..\..\branding\logo.ico"
  File "${SRCDIR}\gui-helper.exe"
  File "${SRCDIR}\udsactor-client.exe"
  File "${SRCDIR}\udsactor-service.exe"
  !if "${VARIANT}" == "unmanaged"
    File /oname=udsactor-config.exe "${SRCDIR}\udsactor-unmanaged-config.exe"
  !else
    File "${SRCDIR}\udsactor-config.exe"
  !endif
  File /oname=LICENSE-OpenUDS.txt "..\..\upstream\uds-actor\LICENSE"
  !if "${VARIANT}" == "unmanaged"
    File "configure-agent.ps1"
    ; Optional configuration from the command line (/BROKER= /TOKEN= [/VERIFYSSL=] [/LOGLEVEL=])
    ${GetParameters} $R0
    ClearErrors
    ${GetOptions} $R0 "/BROKER=" $R1
    IfErrors config_done
    ${GetOptions} $R0 "/TOKEN=" $R2
    IfErrors 0 +3
      DetailPrint "/BROKER ohne /TOKEN angegeben - Agent bitte manuell konfigurieren"
      Goto config_done
    ${GetOptions} $R0 "/VERIFYSSL=" $R3
    IfErrors 0 +2
      StrCpy $R3 "1"
    ClearErrors
    ${GetOptions} $R0 "/LOGLEVEL=" $R4
    IfErrors 0 +2
      StrCpy $R4 "warn"
    ClearErrors
    DetailPrint "Konfiguriere LibreVDI Agent für $R1 ..."
    nsExec::ExecToLog '${POWERSHELL} -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$INSTDIR\configure-agent.ps1" -Broker "$R1" -Token "$R2" -VerifySsl "$R3" -LogLevel "$R4"'
    Pop $0
    StrCmp $0 "0" config_done
      MessageBox MB_ICONEXCLAMATION "Die Agent-Konfiguration ist fehlgeschlagen (Code $0), siehe 'Details anzeigen'.$\r$\nAgent configuration failed (code $0)." /SD IDOK
      SetErrorLevel 2
    config_done:
  !endif
  !ifdef NOTICES
    ; licenses of bundled third-party components (packaging/windows/collect_licenses.py)
    File /oname=THIRD-PARTY-NOTICES.txt "${NOTICES}"
  !endif

  ; Windows service "LibreVDIAgent". "--uninstall" first removes an existing LibreVDIAgent and the
  ; older "UDSActorService" (same display name). Windows finishes deleting a service only when no
  ; handle is open anymore (e.g. the Services console), so creating the new one is retried.
  nsExec::ExecToLog '"$INSTDIR\udsactor-service.exe" --uninstall'
  Pop $0
  StrCpy $1 0
  install_service:
    IntOp $1 $1 + 1
    nsExec::ExecToLog '"$INSTDIR\udsactor-service.exe" --install'
    Pop $0
    StrCmp $0 "0" service_installed
    IntCmp $1 10 service_failed
    DetailPrint "Dienst noch nicht bereit, neuer Versuch ($1/10) ..."
    Sleep 3000
    Goto install_service
  service_failed:
    SetErrorLevel 3
    MessageBox MB_ICONEXCLAMATION "Der LibreVDI-Agent-Dienst konnte nicht eingerichtet werden (Code $0). Bitte die Dienste-Konsole schließen oder Windows neu starten und den Installer erneut ausführen. Details: 'Details anzeigen'.$\r$\n$\r$\nThe LibreVDI Agent service could not be installed (code $0). Close the Services console or restart Windows and run the installer again." /SD IDOK
    Goto service_done
  service_installed:
    nsExec::ExecToLog 'sc.exe start LibreVDIAgent'
    Pop $0
  service_done:

  ; Broker -> agent communication (default listener port 43910)
  nsExec::Exec 'netsh advfirewall firewall delete rule name="LibreVDI Agent"'
  nsExec::Exec 'netsh advfirewall firewall add rule name="LibreVDI Agent" dir=in action=allow protocol=TCP localport=43910 program="$INSTDIR\udsactor-service.exe"'

  ; Session helper: reports logins/logoffs of every user session to the agent service.
  ; Must start at each logon (upstream's Linux packages use an autostart entry for the same).
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "LibreVDI Agent" '"$INSTDIR\udsactor-client.exe"'

  ; Start menu for all users: the installer usually runs elevated under another (admin) account
  SetShellVarContext all
  CreateDirectory "$SMPROGRAMS\LibreVDI"
  CreateShortCut "$SMPROGRAMS\LibreVDI\LibreVDI Agent konfigurieren.lnk" "$INSTDIR\udsactor-config.exe" "" "$INSTDIR\librevdi.ico"

  Delete /REBOOTOK "$INSTDIR\*.old"
  WriteUninstaller "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${PRODUCT} (${VARIANT})"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "LibreVDI"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\librevdi.ico"
  WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetRegView 64
  ExecWait '"$INSTDIR\udsactor-service.exe" --uninstall'
  nsExec::Exec 'netsh advfirewall firewall delete rule name="LibreVDI Agent"'
  DeleteRegValue HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "LibreVDI Agent"
  SetShellVarContext all
  Delete "$SMPROGRAMS\LibreVDI\LibreVDI Agent konfigurieren.lnk"
  RMDir "$SMPROGRAMS\LibreVDI"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKLM "${UNINST_KEY}"
SectionEnd
