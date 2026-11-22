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

Unicode true
!include "MUI2.nsh"
!include "x64.nsh"

!ifndef VERSION
  !define VERSION "0.0.0-dev"
!endif
!ifndef VARIANT
  !define VARIANT "unmanaged"
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

VIProductVersion "0.0.0.0"
VIAddVersionKey "ProductName" "${PRODUCT}"
VIAddVersionKey "FileDescription" "${PRODUCT} installer (${VARIANT})"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "LibreVDI contributors; based on OpenUDS (BSD-3-Clause)"

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
    MessageBox MB_ICONSTOP "LibreVDI Agent requires 64-bit Windows."
    Abort
  ${EndIf}
  SetRegView 64
FunctionEnd

Section "Agent"
  SetOutPath $INSTDIR
  File "${SRCDIR}\gui-helper.exe"
  File "${SRCDIR}\udsactor-client.exe"
  File "${SRCDIR}\udsactor-service.exe"
  !if "${VARIANT}" == "unmanaged"
    File /oname=udsactor-config.exe "${SRCDIR}\udsactor-unmanaged-config.exe"
  !else
    File "${SRCDIR}\udsactor-config.exe"
  !endif
  File /oname=LICENSE-OpenUDS.txt "..\..\upstream\uds-actor\LICENSE"

  ; Windows service (name defined by upstream binary)
  ExecWait '"$INSTDIR\udsactor-service.exe" --install'

  ; Broker -> agent communication (default listener port 43910)
  nsExec::Exec 'netsh advfirewall firewall delete rule name="LibreVDI Agent"'
  nsExec::Exec 'netsh advfirewall firewall add rule name="LibreVDI Agent" dir=in action=allow protocol=TCP localport=43910 program="$INSTDIR\udsactor-service.exe"'

  CreateDirectory "$SMPROGRAMS\LibreVDI"
  CreateShortCut "$SMPROGRAMS\LibreVDI\LibreVDI Agent konfigurieren.lnk" "$INSTDIR\udsactor-config.exe"

  WriteUninstaller "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${PRODUCT} (${VARIANT})"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "LibreVDI"
  WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetRegView 64
  ExecWait '"$INSTDIR\udsactor-service.exe" --uninstall'
  nsExec::Exec 'netsh advfirewall firewall delete rule name="LibreVDI Agent"'
  Delete "$SMPROGRAMS\LibreVDI\LibreVDI Agent konfigurieren.lnk"
  RMDir "$SMPROGRAMS\LibreVDI"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKLM "${UNINST_KEY}"
SectionEnd
