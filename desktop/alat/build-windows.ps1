# Membangun aplikasi Windows LokaSEO dari source.
#
# Pemakaian (PowerShell, dari folder mana pun):
#   powershell -ExecutionPolicy Bypass -File desktop\alat\build-windows.ps1
#
# Pilihan:
#   -SkipFrontend   jangan jalankan pnpm build:loka (pakai loka-release yang ada)
#   -NoWebview      tanpa jendela aplikasi; hanya LokaSEO-console.exe
#   -SkipTests      jangan jalankan unit test

param(
    [switch]$SkipFrontend,
    [switch]$NoWebview,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Assert-Command($name, $hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "$name tidak ditemukan. $hint"
    }
}

Assert-Command python "Pasang Python 3.10+ dari https://www.python.org/downloads/windows/ (centang 'Add python.exe to PATH')."

if (-not $SkipFrontend) {
    Assert-Command pnpm "Pasang Node.js 22+ lalu jalankan: npm install -g pnpm"
    Write-Host "== Memasang dependency dan membangun antarmuka ==" -ForegroundColor Cyan
    pnpm install --frozen-lockfile
    pnpm build:loka
}

if (-not (Test-Path "loka-release\index.html")) {
    throw "loka-release\index.html tidak ditemukan. Jalankan tanpa -SkipFrontend, atau `pnpm build:loka` lebih dahulu."
}

Write-Host "== Memasang PyInstaller ==" -ForegroundColor Cyan
python -m pip install --upgrade --disable-pip-version-check pyinstaller

# Ikon tray: cara utama menghentikan aplikasi karena antarmuka tampil di peramban.
Write-Host "== Memasang pystray dan Pillow untuk ikon tray ==" -ForegroundColor Cyan
python -m pip install --upgrade --disable-pip-version-check pystray pillow

if (-not $NoWebview) {
    Write-Host "== Memasang pywebview (opsional, untuk --window native) ==" -ForegroundColor Cyan
    python -m pip install --upgrade --disable-pip-version-check pywebview
}

if (-not $SkipTests) {
    Write-Host "== Menjalankan unit test server lokal ==" -ForegroundColor Cyan
    python -m unittest discover -s desktop/tests -t desktop
}

Write-Host "== Membangun aplikasi ==" -ForegroundColor Cyan
python -m PyInstaller desktop/alat/lokaseo.spec --noconfirm --distpath desktop/dist --workpath desktop/build

Write-Host "== Menyiapkan paket siap dibagikan ==" -ForegroundColor Cyan
$Release = "desktop\release"
if (Test-Path $Release) { Remove-Item $Release -Recurse -Force }
New-Item -ItemType Directory -Path $Release | Out-Null
Copy-Item "desktop\dist\LokaSEO.exe" $Release -ErrorAction SilentlyContinue
Copy-Item "desktop\dist\LokaSEO-console.exe" $Release
Copy-Item "LICENSE" "$Release\LICENSE.txt"
Copy-Item "docs\lokaseo\cara-pakai-desktop.txt" "$Release\CARA-PAKAI.txt"
Compress-Archive -Path "$Release\*" -DestinationPath "desktop\release\LokaSEO-Windows.zip" -Force

$Size = [math]::Round((Get-Item "desktop\release\LokaSEO-Windows.zip").Length / 1MB, 1)
Write-Host ""
Write-Host "Selesai." -ForegroundColor Green
Write-Host "  Aplikasi : desktop\dist\LokaSEO.exe"
Write-Host "  Konsol   : desktop\dist\LokaSEO-console.exe"
Write-Host "  Paket    : desktop\release\LokaSEO-Windows.zip ($Size MB)"
Write-Host ""
Write-Host "Uji cepat: jalankan desktop\dist\LokaSEO-console.exe --offline --no-open --port 3000"
