# -*- mode: python ; coding: utf-8 -*-
"""Berkas PyInstaller untuk aplikasi desktop LokaSEO (fokus Windows).

Build di Windows:
    cd desktop
    python -m pip install pyinstaller pywebview
    python -m PyInstaller lokaseo.spec --noconfirm --distpath dist --workpath build

Hasil:
    dist/LokaSEO.exe           aplikasi berjendela (butuh pywebview saat build)
    dist/LokaSEO-console.exe   versi konsol untuk menelusuri masalah

Di sistem lain berkas ini tetap dapat dibangun dalam mode konsol saja, sehingga
pemeriksaan di server integrasi tetap berjalan.
"""

import sys
from pathlib import Path

# Berkas ini hidup di `desktop/alat/` bersama skrip pembangun lain, jadi akar
# repo dua tingkat di atasnya. Kalau ia dipindah lagi, yang perlu diubah hanya
# baris ini dan `DESKTOP_DIR` di bawah.
SPEC_DIR = Path(SPECPATH).resolve()  # type: ignore[name-defined]  # diisi PyInstaller
REPO_ROOT = SPEC_DIR.parents[1]
DESKTOP_DIR = REPO_ROOT / "desktop"
IS_WINDOWS = sys.platform.startswith("win")

ASSETS = DESKTOP_DIR / "assets"
ICON = ASSETS / "lokaseo.ico" if IS_WINDOWS else None
MANIFEST = ASSETS / "lokaseo.manifest" if IS_WINDOWS else None
VERSION_FILE = SPEC_DIR / "version_info.txt"

WINDOWED_HIDDEN = []  # type: list[str]
try:  # Jendela aplikasi asli; hanya ada bila pywebview terpasang saat build.
    import webview  # noqa: F401

    HAS_WEBVIEW = True
    WINDOWED_HIDDEN += ["webview", "clr", "clr_loader"]
except ImportError:
    HAS_WEBVIEW = False

try:  # Ikon tray; tanpa ini aplikasi tetap jalan tetapi hanya bisa dihentikan lewat konsol.
    import pystray  # noqa: F401
    from PIL import Image  # noqa: F401

    HAS_TRAY = True
    WINDOWED_HIDDEN += ["pystray", "PIL", "PIL.Image", "PIL._tkinter_finder"]
except ImportError:
    HAS_TRAY = False

a = Analysis(  # noqa: F821
    [str(DESKTOP_DIR / "run.py")],
    # `radar` ikut ke `pathex` supaya PyInstaller bisa menelusuri `lokaradar.*`
    # saat analisis. Tanpa itu, modul radar hanya tersalin sebagai berkas data
    # dan ketergantungan pustaka standarnya (mis. `html.parser` di `extract.py`)
    # tidak ikut terdeteksi — aplikasi hasil bundel lalu gagal saat dibuka.
    pathex=[str(DESKTOP_DIR), str(REPO_ROOT / "radar")],
    binaries=[],
    datas=[
        (str(REPO_ROOT / "loka-release"), "loka-release"),
        (str(ASSETS), "assets"),  # ikon tray dan ikon aplikasi
        # Modul radar ikut dibundel agar pemantauan situs bisa dijalankan dari
        # dalam aplikasi. Radar memakai pustaka standar Python saja di sini:
        # Scrapling dan peramban tidak dibundel, karena peramban perlu diunduh
        # terpisah (±150 MB) dan tidak muat di dalam satu berkas .exe.
        (str(REPO_ROOT / "radar" / "lokaradar"), "radar/lokaradar"),
        (str(REPO_ROOT / "radar" / "README.md"), "radar"),
    ],
    hiddenimports=[
        "lokaseo_desktop",
        "lokaseo_desktop.radar",
        "lokaseo_desktop.pages",
        # Modul radar diimpor saat dipakai, jadi PyInstaller perlu diberi tahu.
        "lokaradar",
        "lokaradar.cli",
        "lokaradar.config",
        "lokaradar.diff",
        "lokaradar.extract",
        "lokaradar.fetch",
        "lokaradar.peramban",
        "lokaradar.places",
        "lokaradar.profil",
        "lokaradar.report",
        "lokaradar.reputasi",
        "lokaradar.ringkasan",
        "lokaradar.robots",
        "lokaradar.run",
        "lokaradar.sasaran",
        "lokaradar.store",
    ],
    hookspath=[],
    runtime_hooks=[],
    # Modul besar yang tidak dipakai aplikasi ini dibuang agar paket tetap ringan.
    # `email`, `http`, dan `urllib` diperlukan http.server/urllib.request, jadi
    # tidak boleh dikecualikan.
    #
    # Berikut ini ketergantungan Scrapling dan Playwright. Keduanya membuat
    # berkas .exe membengkak dari sekitar 31 MB menjadi lebih dari 100 MB tanpa
    # memberi manfaat: merender halaman tetap butuh peramban Chromium yang harus
    # diunduh terpisah di komputer pengguna (±150 MB), dan itu tidak mungkin
    # dititipkan di dalam satu berkas .exe. Aplikasi hasil bundel karena itu
    # mengambil halaman dengan pustaka standar saja, dan radar memberi tahu
    # pengguna bila sebuah halaman ternyata perlu peramban.
    #
    # Bila Anda ingin mencoba rendering dari dalam bundel: hapus nama di bawah,
    # lalu jalankan `python -m playwright install chromium` di komputer tujuan.
    excludes=[
        "scrapling",
        "playwright",
        "patchright",
        "curl_cffi",
        "lxml",
        "bs4",
        "soupsieve",
        "w3lib",
        "browserforge",
        "protego",
        "tldextract",
        "html5lib",
        "msgspec",
        "tkinter",
        "numpy",
        "matplotlib",
        "scipy",
        "pandas",
        "IPython",
        "pytest",
        "setuptools",
        "pip",
        "distutils",
        "lib2to3",
        "pydoc",
        "doctest",
        "pdb",
        "xmlrpc",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

COMMON = {
    "debug": False,
    "bootloader_ignore_signals": False,
    "strip": False,
    "upx": False,
    "runtime_tmpdir": None,
    "icon": str(ICON) if ICON and ICON.is_file() else None,
    "version": str(VERSION_FILE) if IS_WINDOWS else None,
    "manifest": str(MANIFEST) if MANIFEST and MANIFEST.is_file() else None,
}

if IS_WINDOWS and HAS_WEBVIEW:
    exe_windowed = EXE(  # noqa: F821
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="LokaSEO",
        console=False,
        hiddenimports=WINDOWED_HIDDEN,
        **COMMON,
    )

exe_console = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="LokaSEO-console",
    console=True,
    upx_exclude=[],
    **COMMON,
)

if IS_WINDOWS and not HAS_TRAY:
    import warnings

    warnings.warn(
        "pystray tidak terpasang: LokaSEO.exe tidak akan punya ikon tray, sehingga "
        "aplikasi hanya dapat dihentikan lewat halaman /hentikan atau Task Manager. "
        "Jalankan `python -m pip install pystray pillow` lalu build ulang.",
        stacklevel=1,
    )

if IS_WINDOWS and not HAS_WEBVIEW:
    import warnings

    warnings.warn(
        "pywebview tidak terpasang: pilihan `--window native` tidak tersedia. "
        "Ini tidak masalah bila memakai antarmuka di peramban (bawaan).",
        stacklevel=1,
    )
