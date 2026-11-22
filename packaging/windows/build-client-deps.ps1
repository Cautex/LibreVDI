# Builds the native dependencies of the OpenUDS 5.0 launcher (client) on a Windows build host:
#   * vcpkg packages: openssl zlib ffmpeg cjson libusb (dynamic, x64-windows)
#                     libvpx (static, x64-windows-static) for VP9 decoding
#   * FreeRDP (built from source) into $env:FREERDP_ROOT
#
# Mirrors upstream/uds-client/building/windows/Dockerfile, but runs natively (e.g. GitHub
# Actions windows runners, which already have Visual Studio, CMake, LLVM and vcpkg).
#
# Required environment: VCPKG_ROOT, FREERDP_ROOT. Optional: FREERDP_VERSION (default 3.26.0).
$ErrorActionPreference = "Stop"

$vcpkg = Join-Path $env:VCPKG_ROOT "vcpkg.exe"
$freerdpVersion = if ($env:FREERDP_VERSION) { $env:FREERDP_VERSION } else { "3.26.0" }
$installed = Join-Path $env:VCPKG_ROOT "installed"

function Invoke-Checked([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "$exe failed with exit code $LASTEXITCODE" }
}

Write-Host "== vcpkg packages"
Invoke-Checked $vcpkg @("install", "--triplet", "x64-windows", "openssl", "zlib", "ffmpeg", "cjson", "libusb")
Invoke-Checked $vcpkg @("install", "libvpx:x64-windows-static")

# freerdp-integration's build.rs expects z.dll; vcpkg's zlib installs libz.dll / zlib1.dll
$bin = Join-Path $installed "x64-windows\bin"
foreach ($candidate in @("libz.dll", "zlib1.dll")) {
    $src = Join-Path $bin $candidate
    if ((Test-Path $src) -and -not (Test-Path (Join-Path $bin "z.dll"))) {
        Copy-Item $src (Join-Path $bin "z.dll")
    }
}

if (Test-Path (Join-Path $env:FREERDP_ROOT "include\freerdp3")) {
    Write-Host "== FreeRDP already present in $env:FREERDP_ROOT (cache hit)"
    exit 0
}

Write-Host "== FreeRDP $freerdpVersion"
$src = Join-Path $env:RUNNER_TEMP "FreeRDP"
if (-not $env:RUNNER_TEMP) { $src = Join-Path $env:TEMP "FreeRDP" }
if (Test-Path $src) { Remove-Item -Recurse -Force $src }
Invoke-Checked git @("clone", "--branch", $freerdpVersion, "--depth", "1", "https://github.com/FreeRDP/FreeRDP.git", $src)

$vcpkgCmake = (Join-Path $env:VCPKG_ROOT "scripts\buildsystems\vcpkg.cmake") -replace '\\', '/'
$inst = ($installed -replace '\\', '/') + "/x64-windows"
$cmakeArgs = @(
    "-S", $src, "-B", "$src\build",
    "-DCMAKE_TOOLCHAIN_FILE=$vcpkgCmake",
    "-DVCPKG_TARGET_TRIPLET=x64-windows",
    "-DCMAKE_BUILD_TYPE=Release",
    "-DCMAKE_MODULE_PATH=$inst/share/ffmpeg",
    "-DWITH_CLIENT_COMMON=ON",
    "-DWITH_INTERNAL_MD4=ON", "-DWITH_INTERNAL_MD5=ON", "-DWITH_INTERNAL_RC4=ON",
    "-DWITH_SDL=OFF", "-DWITH_CLIENT_SDL=OFF", "-DWITH_CLIENT_WINDOWS=OFF",
    "-DWITH_SERVER=OFF", "-DWITH_SHADOW=OFF",
    "-DBUILD_TESTING=OFF", "-DWITH_MANPAGES=OFF",
    "-DWITH_CHANNELS=ON", "-DWITH_CLIENT_CHANNELS=ON",
    "-DWITH_RDPSND=ON", "-DWITH_AUDIN=ON", "-DWITH_WINMM=ON", "-DWITH_DSP_FFMPEG=ON",
    "-DWITH_LIBUSB=ON", "-DWITH_URBDRC=ON",
    "-DLIBUSB_1_INCLUDE_DIR=$inst/include/libusb-1.0",
    "-DLIBUSB_1_LIBRARY=$inst/lib/libusb-1.0.lib",
    "-DWITH_AAD=ON", "-DWITH_WINPR_JSON=ON",
    "-DWITH_VERBOSE_WINPR_ASSERT=OFF",
    "-DWITH_OPENH264=OFF", "-DWITH_GFX_H264=ON",
    "-DWITH_RDPGFX=ON", "-DWITH_DYNVC=ON",
    "-DWITH_VAAPI_H264_ENCODING=OFF",
    "-DWITH_DEBUG_ALL=OFF"
)
Invoke-Checked cmake $cmakeArgs
Invoke-Checked cmake @("--build", "$src\build", "--config", "Release", "--parallel")
Invoke-Checked cmake @("--install", "$src\build", "--config", "Release", "--prefix", $env:FREERDP_ROOT)
Write-Host "== FreeRDP installed to $env:FREERDP_ROOT"
