; LibreVDI Client installer (Windows x64)
; Packages the OpenUDS 5.0 launcher (BSD-3-Clause, (c) Virtual Cable S.L.) built from
; upstream/uds-client together with its runtime DLLs (FreeRDP, FFmpeg, OpenSSL, ...).
;
; Build (from repository root, after collecting launcher.exe + DLLs into .\out):
;   makensis /DVERSION=0.1.0 /DSRCDIR=..\..\out packaging\windows\client.nsi
;
; Registers the URL scheme "udssv2://" used by the portal to start a connection.

Unicode true
!include "MUI2.nsh"
!include "x64.nsh"

!ifndef VERSION
  !define VERSION "0.0.0-dev"
!endif
!ifndef SRCDIR
  !define SRCDIR "..\..\out"
!endif

!define PRODUCT "LibreVDI Client"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\LibreVDI-Client"
!define SCHEME "udssv2"

Name "${PRODUCT}"
OutFile "LibreVDI-Client-Setup-${VERSION}.exe"
InstallDir "$PROGRAMFILES64\LibreVDI\Client"
RequestExecutionLevel admin
SetCompressor /SOLID lzma

!ifndef VIVERSION
  !define VIVERSION "0.0.0.0"  ; numeric a.b.c.d for the Windows file properties
!endif
VIProductVersion "${VIVERSION}"
VIAddVersionKey "ProductName" "${PRODUCT}"
VIAddVersionKey "FileDescription" "${PRODUCT} installer"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "LibreVDI contributors; based on OpenUDS (BSD-3-Clause)"

!define MUI_ICON "..\..\branding\logo.ico"
!define MUI_UNICON "..\..\branding\logo.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\upstream\uds-client\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "German"
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "LibreVDI Client requires 64-bit Windows."
    Abort
  ${EndIf}
  SetRegView 64
FunctionEnd

Section "Client"
  ; a running client (open connection or window) locks launcher.exe and its DLLs
  nsExec::ExecToStack 'cmd.exe /c tasklist /FI "IMAGENAME eq launcher.exe" /NH | find /I "launcher.exe"'
  Pop $0
  Pop $1
  ${If} $0 == 0
    MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION "Der LibreVDI Client läuft noch und wird für das Update beendet. Offene Verbindungen werden getrennt.$\r$\n$\r$\nLibreVDI Client is still running and will be closed for the update. Open connections will be disconnected." IDOK close_client
    Abort
    close_client:
    nsExec::Exec 'taskkill.exe /F /IM launcher.exe'
    Sleep 1500
  ${EndIf}
  SetOutPath $INSTDIR
  File "${SRCDIR}\launcher.exe"
  File /oname=librevdi.ico "..\..\branding\logo.ico"
  File /nonfatal "${SRCDIR}\*.dll"
  File /oname=LICENSE-OpenUDS.txt "..\..\upstream\uds-client\LICENSE"
  !ifdef NOTICES
    ; licenses of bundled third-party components (packaging/windows/collect_licenses.py)
    File /oname=THIRD-PARTY-NOTICES.txt "${NOTICES}"
  !endif

  ; URL scheme handler: the portal hands connections to udssv2://host/ticket/scrambler
  WriteRegStr HKLM "Software\Classes\${SCHEME}" "" "URL:LibreVDI Protocol"
  WriteRegStr HKLM "Software\Classes\${SCHEME}" "URL Protocol" ""
  WriteRegStr HKLM "Software\Classes\${SCHEME}\DefaultIcon" "" '"$INSTDIR\librevdi.ico"'
  WriteRegStr HKLM "Software\Classes\${SCHEME}\shell\open\command" "" '"$INSTDIR\launcher.exe" "%1"'

  WriteUninstaller "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${PRODUCT}"
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
  DeleteRegKey HKLM "Software\Classes\${SCHEME}"
  DeleteRegKey HKLM "${UNINST_KEY}"
  RMDir /r "$INSTDIR"
  RMDir "$PROGRAMFILES64\LibreVDI"
SectionEnd
