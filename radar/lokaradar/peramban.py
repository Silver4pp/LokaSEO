"""Peramban yang sudah ada di komputer, dipakai untuk merender halaman ber-JavaScript.

Radar mengambil halaman dengan pustaka standar Python. Situs yang isinya disusun
JavaScript terbaca pendek karena itu, dan pemeriksaan jadi tidak adil. Sampai di
sini ada dua jalan: memasang Scrapling beserta peramban Chromium (±150 MB), atau
memakai peramban yang **sudah ada** di komputer pengguna.

Modul ini menempuh jalan kedua. Di Windows 10 dan 11, Microsoft Edge sudah
terpasang — begitu juga Google Chrome di banyak komputer. Keduanya berbicara
protokol yang sama (Chrome DevTools Protocol) melalui soket lokal, dan itu bisa
dipakai dengan pustaka standar saja: tanpa pip, tanpa unduhan, tanpa terminal.

Prinsip yang dipegang:

- **Tidak ada unduhan di belakang layar.** Modul ini tidak pernah mengunduh
  apa pun. Ia hanya memakai peramban yang sudah ada, dan mengatakannya terus
  terang bila tidak ada.
- **Identitas tetap jujur.** User-Agent tetap `LokaRadar/0.1` (bukan tiruan
  Chrome), `Accept-Language` tetap bahasa Indonesia, dan Referer tidak dipalsukan
  menjadi pencarian Google. Peramban sungguhan tetap mengirim sebagian header
  khasnya (`sec-ch-ua`, `Accept-Encoding`) yang tidak bisa dihapus dari sisi ini;
  itu disebut apa adanya di README.
- **Sopan ke situs orang.** Gambar, media, dan font diblokir supaya unduhan yang
  tidak perlu tidak membebani pemilik situs. Halaman tetap dirender penuh
  termasuk CSS, sehingga teks dan harga yang dibaca tetap benar.
- **Berumur pendek.** Peramban dijalankan dengan folder data sementara sendiri,
  tanpa profil pengguna, tanpa ekstensi, tanpa sinkronisasi; ditutup dan folder
  itu dihapus setelah selesai. Tidak ada riwayat yang tertinggal di peramban
  pribadi pengguna.
- **Tidak mengganggu pemakaian peramban biasa.** Proses dijalankan headless
  dengan `--remote-debugging-port=0` (port dipilih sistem) di dalam folder data
  milik radar sendiri, jadi peramban pengguna yang sedang terbuka tidak
  tersentuh.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import logging
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from . import config

LOG = logging.getLogger("lokaradar")

# Variabel lingkungan untuk menunjuk peramban sendiri (mis. versi portabel).
BROWSER_ENV = "LOKARADAR_PERAMBAN"
# Nama berkas tempat Chromium menuliskan port debug yang dipakai.
PORT_FILE = "DevToolsActivePort"

# Batas waktu menunggu peramban siap menerima perintah.
START_TIMEOUT = 25.0
# Batas waktu satu permintaan-perintah ke peramban.
CMD_TIMEOUT = 20.0

# Berkas yang tidak perlu diunduh saat merender. Tujuannya mengurangi beban ke
# situs orang, bukan menyembunyikan apa pun: teks, harga, dan data terstruktur
# tetap dibaca utuh. Isi HTML dan CSS tidak diblokir.
MEDIA_POLA = (
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.svg",
    "*.ico",
    "*.avif",
    "*.bmp",
    "*.mp4",
    "*.webm",
    "*.ogg",
    "*.mp3",
    "*.wav",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.otf",
    "*.eot",
)

PETUNJUK_TANPA_PERAMBAN = (
    "Peramban tidak ditemukan. LokaRadar bisa memakai Microsoft Edge atau Google "
    "Chrome yang sudah terpasang di komputer ini; bila keduanya tidak ada, pasang "
    "salah satunya lalu klik “Periksa ulang”, atau tunjuk sendiri berkas "
    "perambannya lewat kolom di bawah."
)


class PerambanError(RuntimeError):
    """Peramban tidak bisa dipakai atau gagal dijalankan."""


@dataclass
class Hasil:
    """Hasil satu halaman yang dirender peramban."""

    url: str
    final_url: str
    status: int
    html: str
    text: str
    title: str = ""
    ms: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    # None = tidak diminta; True/False = hasil penantian selektor tunggu.
    selektor_ditemukan: bool | None = None
    catatan: str = ""


# ---------------------------------------------------------------------------
# Mencari peramban yang sudah ada
# ---------------------------------------------------------------------------
def _kandidat_windows() -> list[Path]:
    program = [os.environ.get("ProgramFiles", r"C:\Program Files")]
    program86 = [os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
    lokal = os.environ.get("LOCALAPPDATA")
    akar: list[Path] = []
    for dasar in program + program86:
        if dasar:
            akar.append(Path(dasar))
    if lokal:
        akar.append(Path(lokal))
    # Urutan = prioritas: Edge dan Chrome stabil dulu, lalu saluran lain,
    # lalu peramban berbasis Chromium yang lain. Semuanya bicara protokol yang
    # sama, jadi tidak ada alasan untuk menolak yang sudah terpasang.
    pola = [
        ("Microsoft", "Edge", "Application", "msedge.exe"),
        ("Google", "Chrome", "Application", "chrome.exe"),
        ("Microsoft", "Edge Beta", "Application", "msedge.exe"),
        ("Google", "Chrome Beta", "Application", "chrome.exe"),
        ("Microsoft", "Edge Dev", "Application", "msedge.exe"),
        ("Google", "Chrome Dev", "Application", "chrome.exe"),
        ("Microsoft", "Edge SxS", "Application", "msedge.exe"),  # Edge Canary
        ("Google", "Chrome SxS", "Application", "chrome.exe"),  # Chrome Canary
        ("Chromium", "Application", "chrome.exe"),
        ("BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        ("Vivaldi", "Application", "vivaldi.exe"),
        ("Programs", "Opera", "launcher.exe"),
    ]
    hasil = [dasar.joinpath(*bagian) for dasar in akar for bagian in pola]
    if lokal:  # Chromium yang diunduh Playwright/Scrapling
        kache = Path(lokal) / "ms-playwright"
        hasil += sorted(kache.glob("chromium-*/chrome-win*/chrome.exe"))
        hasil += sorted(kache.glob("chromium_headless_shell-*/chrome-win*/*headless-shell.exe"))
    return hasil


def _kandidat_registry() -> list[Path]:
    """Jalur peramban dari registry Windows.

    Daftar jalur berkas saja tidak cukup: Edge dan Chrome bisa terpasang di
    folder lain (komputer kantor yang dikelola, Edge yang dipasang ulang, atau
    Windows yang dipindah ke drive lain). Registry selalu menyimpan jalur yang
    dipakai sistem untuk menjalankan peramban itu, di `App Paths`.
    """
    if not sys.platform.startswith("win"):
        return []
    try:
        import winreg
    except Exception:  # noqa: BLE001 - registry bisa tidak tersedia
        return []
    kunci = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe",
    )
    hasil: list[Path] = []
    for akar, bendera in (
        (winreg.HKEY_CURRENT_USER, 0),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY),
    ):
        for nama in kunci:
            try:
                with winreg.OpenKey(akar, nama, 0, winreg.KEY_READ | bendera) as buka:
                    nilai, _ = winreg.QueryValueEx(buka, "")
            except OSError:
                continue
            except Exception:  # noqa: BLE001 - registry bisa berisi apa saja
                continue
            bersih = str(nilai or "").strip().strip('"')
            if bersih and bersih.lower().endswith(".exe"):
                hasil.append(Path(bersih))
    return hasil


def _kandidat_path() -> list[Path]:
    """Peramban yang bisa dipanggil langsung dari PATH (mis. versi portabel)."""
    if sys.platform.startswith("win"):
        nama = ("msedge.exe", "chrome.exe", "msedge", "chrome")
    else:
        nama = ("microsoft-edge", "microsoft-edge-stable", "google-chrome", "chromium", "chromium-browser")
    hasil: list[Path] = []
    for n in nama:
        ketemu = shutil.which(n)
        if ketemu:
            hasil.append(Path(ketemu))
    return hasil


def _kandidat_linux() -> list[Path]:
    hasil = [
        Path("/usr/bin/microsoft-edge"),
        Path("/usr/bin/microsoft-edge-stable"),
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/google-chrome-stable"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
        Path("/snap/bin/chromium"),
        Path("/usr/lib/chromium/chromium"),
    ]
    cache = Path.home() / ".cache" / "ms-playwright"
    if cache.is_dir():
        # Beberapa versi Playwright memakai folder chrome-linux, yang lain chrome-linux64.
        hasil += [
            *cache.glob("chromium-*/chrome-linux*/chrome"),
            *cache.glob("chromium-*/chrome-linux*/headless_shell"),
            *cache.glob("chromium_headless_shell-*/chrome-*/chrome-headless-shell"),
            *cache.glob("chromium_headless_shell-*/chrome-*/headless_shell"),
        ]
    return hasil


def _kandidat_macos() -> list[Path]:
    hasil = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    return hasil


def kandidat() -> list[Path]:
    """Daftar tempat peramban biasanya berada di sistem ini, menurut urutan prioritas.

    Tiga sumber digabung: jalur pemasangan yang lazim, registry Windows (yang
    mencatat jalur sebenarnya bila pemasangannya tidak lazim), dan PATH.
    """
    if sys.platform.startswith("win"):
        dasar = _kandidat_windows()
        tambahan = _kandidat_registry() + _kandidat_path()
    elif sys.platform == "darwin":
        dasar = _kandidat_macos()
        tambahan = _kandidat_path()
    else:
        dasar = _kandidat_linux()
        tambahan = _kandidat_path()
    return _rapi(dasar + tambahan)


def _rapi(daftar: list[Path]) -> list[Path]:
    """Buang jalur kembar tanpa mengubah urutan prioritas."""
    hasil: list[Path] = []
    sudah: set[str] = set()
    for jalur in daftar:
        kunci = str(jalur).lower()
        if kunci in sudah:
            continue
        sudah.add(kunci)
        hasil.append(jalur)
    return hasil


# Berkas tempat pilihan peramban pengguna disimpan, di folder data radar.
BERKAS_PILIHAN = "peramban.json"


def _berkas_pilihan() -> Path:
    return config.data_dir() / BERKAS_PILIHAN


def pilihan_tersimpan() -> Path | None:
    """Peramban yang pernah ditunjuk pengguna sendiri, bila masih ada."""
    try:
        isi = json.loads(_berkas_pilihan().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    jalur = str((isi or {}).get("jalur") or "").strip()
    return Path(jalur) if jalur else None


def tetapkan(jalur: str | Path | None) -> None:
    """Simpan atau hapus pilihan peramban pengguna.

    Disimpan di folder data radar, jadi pilihan ini bertahan walau aplikasi
    ditutup dan dibuka lagi — dan tetap tidak pernah dikirim ke mana pun.
    """
    global _KETERSEDIAAN
    berkas = _berkas_pilihan()
    if not jalur:
        try:
            berkas.unlink(missing_ok=True)
        except OSError as error:  # noqa: BLE001
            LOG.warning("Pilihan peramban tidak bisa dihapus: %s", error)
        _KETERSEDIAAN = None
        return
    berkas.write_text(
        json.dumps({"jalur": str(Path(jalur).expanduser())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _KETERSEDIAAN = None


def _urutan_pilihan(explicit: str | Path | None) -> list[Path]:
    """Siapa yang berhak menentukan peramban, dari yang paling berhak."""
    hasil: list[Path] = []
    for nilai in (explicit, os.environ.get(BROWSER_ENV) or "", pilihan_tersimpan()):
        if not nilai:
            continue
        jalur = Path(str(nilai)).expanduser()
        if not jalur.is_file():
            LOG.warning("Peramban yang ditunjuk tidak ada: %s", jalur)
            continue
        hasil.append(jalur)
    return hasil


def cari(explicit: str | Path | None = None, *, uji_jalan: bool = True) -> Path | None:
    """Peramban yang akan dipakai: pilihan pengguna dulu, lalu yang terpasang.

    Berkas yang tidak bisa dijalankan dilewati, bukan dianggap siap: Chromium
    yang kehilangan pustaka sistem tetap ada di cakram dan akan gagal di setiap
    rendering.
    """
    for jalur in _urutan_pilihan(explicit) + kandidat():
        if not jalur.is_file():
            continue
        if not uji_jalan or layak(jalur):
            return jalur
        LOG.warning("Peramban ada tetapi tidak dikenali sebagai peramban: %s", jalur)
    return None


def lacak() -> list[dict]:
    """Jejak pencarian: di mana saja radar mencari, dan kenapa tiap calon dilewati.

    "Tidak ada peramban" saja tidak bisa ditindaklanjuti. Daftar ini menjawab
    pertanyaan yang sesungguhnya: berkasnya tidak ada di mana-mana, atau ada
    tetapi menolak dijalankan? Daftarnya tidak dipotong: jumlahnya dipakai
    sendiri oleh kalimat alasan, jadi memotongnya akan membuat angkanya bohong.
    """
    ditemukan: list[dict] = []
    tidak_ada: list[dict] = []
    for jalur in kandidat():
        if not jalur.is_file():
            tidak_ada.append({"jalur": str(jalur), "ada": False, "alasan": "berkas tidak ada"})
            continue
        if layak(jalur):
            ditemukan.append({"jalur": str(jalur), "ada": True, "alasan": "dipakai", "versi": versi(jalur)})
            continue
        ditemukan.append({"jalur": str(jalur), "ada": True, "alasan": "ada, tetapi tidak dikenali sebagai peramban"})
    # Berkas yang ditemukan lebih bermakna daripada yang tidak ada, jadi
    # ditaruh di atas supaya langsung terlihat.
    return ditemukan + tidak_ada


VERSI_TERTINGGAL: dict[str, tuple[str, str]] = {}

# Nomor versi peramban, mis. 120.0.2210.91 atau 141.0.2903.86.
_POLA_VERSI = re.compile(r"\b\d+(?:\.\d+){2,3}\b")

# Penanda yang berarti "berkasnya ada, tetapi tidak bisa dipakai".
_PENANDA_GALAT = (
    "error while loading shared libraries",
    "cannot open shared object",
    "permission denied",
    "access is denied",
    "is not recognized",
    "command not found",
    "not found",
    "no such file or directory",
    "cannot execute",
    "exec format error",
)


def _keluaran_versi_mentah(jalur: Path) -> tuple[str, str]:
    """Jalankan `--version`, lalu kembalikan (keluaran baku, keluaran galat)."""
    kunci = str(jalur)
    if kunci in VERSI_TERTINGGAL:
        return VERSI_TERTINGGAL[kunci]
    pasangan = ("", "")
    try:  # noqa: SIM105 - blok panjang, sengaja eksplisit
        hasil = subprocess.run(  # noqa: S603 - jalur yang sudah diperiksa
            [str(jalur), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            creationflags=_bendera_tanpa_jendela(),
        )
        pasangan = ((hasil.stdout or "").strip(), (hasil.stderr or "").strip())
    except (OSError, subprocess.SubprocessError) as error:
        LOG.debug("Versi peramban tidak terbaca: %s", error)
    VERSI_TERTINGGAL[kunci] = pasangan
    if pasangan[1]:
        LOG.debug("Peramban %s menulis ke keluaran galat: %s", jalur, pasangan[1][:200])
    return pasangan


def _keluaran_versi(jalur: Path) -> str:
    """Teks pembaca versi: keluaran baku dulu, keluaran galat hanya bila baku kosong.

    Chromium suka menulis peringatan ke keluaran galat, mis.
    `[1015/084855.123:WARNING:policy.cc(123)] …`. Dulu dua keluaran itu
    digabung, sehingga satu baris peringatan sudah cukup untuk membuat
    peramban yang sehat terbaca "rusak" — dan tombol uji rendering mati
    tanpa sebab yang jelas.
    """
    baku, galat = _keluaran_versi_mentah(jalur)
    return baku or galat


# Nama berkas peramban yang dikenal — dipakai bila versi tidak terbaca.
_NAMA_PERAMBAN = ("msedge", "chrome", "chromium", "brave", "vivaldi", "opera", "headless_shell")


def _nama_peramban_dikenal(jalur: Path) -> bool:
    nama = jalur.name.lower()
    return any(tanda in nama for tanda in _NAMA_PERAMBAN)


def _versi_dari_berkas(jalur: Path) -> str:
    """Nomor versi dari sumber daya versi berkas .exe Windows, tanpa menjalankannya.

    Edge dan Chrome di Windows adalah aplikasi **GUI** (`/SUBSYSTEM:WINDOWS`):
    mereka terlepas dari konsol, sehingga `chrome.exe --version` tidak menulis
    apa pun ke pipa — dan lebih buruk lagi, pada banyak versi ia malah
    **membuka jendela peramban sungguhan**. Memakainya sebagai penapis membuat
    peramban yang sehat terbaca "rusak". Keluhan ini sudah dilaporkan ke
    Chromium sejak 2012 (crbug 158372 / 40953357) dan belum juga diperbaiki.

    Karena itu di Windows nomor versi dibaca dari berkasnya saja:
    sumber daya versi PE (`VS_FIXEDFILEINFO`), lalu folder samping bernama
    nomor versi (tata letak pemasangan Chromium: `Application\\141.0.7390.54\\`).
    Bukti bahwa perambannya benar-benar bisa dipakai tetap ada di `uji()`, yang
    nyata-nyata merender satu halaman.
    """
    if not sys.platform.startswith("win"):
        return ""
    return _versi_dari_sumber_daya(jalur) or _versi_dari_folder_samping(jalur)


class _InfoTetapBerkas(ctypes.Structure):
    """`VS_FIXEDFILEINFO` — bagian dari sumber daya versi PE."""

    _fields_ = [
        ("dwSignature", ctypes.c_uint32),
        ("dwStrucVersion", ctypes.c_uint32),
        ("dwFileVersionMS", ctypes.c_uint32),
        ("dwFileVersionLS", ctypes.c_uint32),
        ("dwProductVersionMS", ctypes.c_uint32),
        ("dwProductVersionLS", ctypes.c_uint32),
        ("dwFileFlagsMask", ctypes.c_uint32),
        ("dwFileFlags", ctypes.c_uint32),
        ("dwOS", ctypes.c_uint32),
        ("dwFileType", ctypes.c_uint32),
        ("dwFileSubtype", ctypes.c_uint32),
        ("dwFileDateMS", ctypes.c_uint32),
        ("dwFileDateLS", ctypes.c_uint32),
    ]


_SUMBER_DAYA_TERTINGGAL: dict[str, tuple[str, str]] = {}


def _baca_sumber_daya(jalur: Path) -> tuple[str, str]:
    """Baca sumber daya versi PE: (nomor versi, nama produk).

    Dipakai untuk mengenali peramban **tanpa menjalankannya**. Nama produk
    diambil dari seluruh teks sumber daya (bukan hanya `ProductName`) supaya
    peramban turunan Chromium dengan nama berkas apa pun — Thorium, Ungoogled,
    Supermium — tetap dikenali dari identitas yang mereka tulis sendiri.
    """
    kunci = str(jalur)
    if kunci in _SUMBER_DAYA_TERTINGGAL:
        return _SUMBER_DAYA_TERTINGGAL[kunci]
    pasangan = ("", "")
    try:
        pasangan = _baca_sumber_daya_mentah(jalur)
    except (OSError, ValueError, AttributeError) as error:
        LOG.debug("Sumber daya versi tidak terbaca untuk %s: %s", jalur, error)
    _SUMBER_DAYA_TERTINGGAL[kunci] = pasangan
    return pasangan


def _baca_sumber_daya_mentah(jalur: Path) -> tuple[str, str]:
    try:
        pustaka = ctypes.WinDLL("version.dll")
    except (OSError, ValueError):
        return "", ""
    pustaka.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)]
    pustaka.GetFileVersionInfoSizeW.restype = ctypes.c_uint32
    pustaka.GetFileVersionInfoW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p
    ]
    pustaka.GetFileVersionInfoW.restype = ctypes.c_int
    pustaka.VerQueryValueW.argtypes = [
        ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    pustaka.VerQueryValueW.restype = ctypes.c_int

    nama = str(jalur)
    abaikan = ctypes.c_uint32(0)
    ukuran = pustaka.GetFileVersionInfoSizeW(nama, ctypes.byref(abaikan))
    if not ukuran:
        return "", ""
    penyangga = ctypes.create_string_buffer(ukuran)
    if not pustaka.GetFileVersionInfoW(nama, 0, ukuran, penyangga):
        return "", ""
    versi = ""
    penunjuk = ctypes.c_void_p()
    panjang = ctypes.c_uint32(0)
    if pustaka.VerQueryValueW(penyangga, "\\", ctypes.byref(penunjuk), ctypes.byref(panjang)):
        if penunjuk.value and panjang.value >= ctypes.sizeof(_InfoTetapBerkas):
            info = ctypes.cast(penunjuk, ctypes.POINTER(_InfoTetapBerkas)).contents
            bagian = (
                (info.dwFileVersionMS >> 16) & 0xFFFF,
                info.dwFileVersionMS & 0xFFFF,
                (info.dwFileVersionLS >> 16) & 0xFFFF,
                info.dwFileVersionLS & 0xFFFF,
            )
            # "0.0.0.0" berarti sumber dayanya ada tetapi tidak terisi.
            if any(bagian):
                versi = ".".join(str(b) for b in bagian)
    # Teks sumber daya: seluruh penyangga didekode UTF-16 untuk mencari nama
    # produk. Ini hanya pembacaan berkas, bukan eksekusi.
    teks = bytes(penyangga).decode("utf-16-le", errors="ignore").lower()
    produk = ""
    for tanda in _NAMA_PERAMBAN:
        if tanda.replace("_", " ") in teks or tanda in teks:
            produk = tanda
            break
    return versi, produk


def _versi_dari_sumber_daya(jalur: Path) -> str:
    """Nomor versi dari `VS_FIXEDFILEINFO`, tanpa menjalankan berkasnya."""
    return _baca_sumber_daya(jalur)[0]


def _versi_dari_folder_samping(jalur: Path) -> str:
    """Tata letak Chromium menaruh berkasnya di folder bernama nomor versi."""
    try:
        anak = [b for b in jalur.parent.iterdir() if b.is_dir()]
    except OSError:
        return ""
    terbaik: tuple[int, ...] = ()
    for folder in anak:
        if not _POLA_VERSI.fullmatch(folder.name):
            continue
        kunci = tuple(int(b) for b in folder.name.split("."))
        if kunci > terbaik:
            terbaik = kunci
    return ".".join(str(b) for b in terbaik)


def _keluaran_seperti_versi(keluaran: str) -> bool:
    """Apakah keluaran `--version` memuat nomor versi, bukan pesan galat.

    Peramban bisa ada sebagai berkas tetapi tidak bisa dijalankan — misalnya
    Chromium yang kehilangan pustaka sistem. Tanpa pemeriksaan ini, radar akan
    mengaku "peramban siap" lalu gagal di setiap rendering. Baris peringatan
    yang menyertai nomor versinya tidak dipedulikan.
    """
    teks = (keluaran or "").strip()
    if not teks:
        return False
    rendah = teks.lower()
    if any(penanda in rendah for penanda in _PENANDA_GALAT):
        return False
    return bool(_POLA_VERSI.search(teks))


def versi(jalur: Path) -> str:
    """Nomor versi peramban, atau teks kosong bila tidak terbaca."""
    if sys.platform.startswith("win"):
        return _versi_dari_berkas(jalur)
    keluaran = _keluaran_versi(jalur)
    if not _keluaran_seperti_versi(keluaran):
        return ""
    cocok = _POLA_VERSI.search(keluaran)
    return cocok.group(0) if cocok else keluaran.strip().splitlines()[0]


def layak(jalur: Path) -> bool:
    """Patutkah berkas ini dicoba sebagai peramban — tanpa membuka jendelanya.

    Di Windows peramban tidak dijalankan untuk diperiksa (lihat
    `_versi_dari_berkas`): cukup dilihat bahwa berkasnya ada, berujung `.exe`,
    dan namanya (atau sumber daya versinya) dikenali sebagai peramban.
    """
    if not jalur.is_file():
        return False
    if sys.platform.startswith("win"):
        if not jalur.name.lower().endswith(".exe"):
            return False
        if sys.platform.startswith("win") and _nama_peramban_dikenal(jalur):
            return True
        # Berkas yang namanya tidak dikenal tetap diterima bila sumber daya
        # versinya memperkenalkan diri sebagai peramban Chromium. Tanpa itu,
        # menempelkan jalur berkas apa pun akan membuatnya dijalankan.
        return bool(_baca_sumber_daya(jalur)[1])
    return _keluaran_seperti_versi(_keluaran_versi(jalur))


def nama_peramban(jalur: Path) -> str:
    """Nama yang bisa dibaca manusia, mis. “Microsoft Edge”."""
    nama = jalur.name.lower()
    if "msedge" in nama:
        return "Microsoft Edge"
    if "chrome" in nama and "chromium" not in nama:
        return "Google Chrome"
    if "chromium" in nama or "headless_shell" in nama:
        return "Chromium"
    return jalur.name


def ketersediaan(refresh: bool = False) -> dict:
    """Keadaan peramban: ada atau tidak, di mana, versi berapa."""
    global _KETERSEDIAAN
    if _KETERSEDIAAN is not None and not refresh:
        return dict(_KETERSEDIAAN)
    jalur = cari()
    if jalur is None:
        # `lacak()` menjalankan `--version` untuk setiap berkas yang ada, jadi
        # hasilnya dipakai dua kali (alasan + daftar) dan tidak dihitung ulang.
        jejak = lacak()
        _KETERSEDIAAN = {
            "tersedia": False,
            "jalur": "",
            "nama": "",
            "versi": "",
            "sumber": "",
            "pesan": PETUNJUK_TANPA_PERAMBAN,
            "alasan": _alasan_tanpa_peramban(jejak),
            "dicari": jejak,
        }
        return dict(_KETERSEDIAAN)
    _KETERSEDIAAN = {
        "tersedia": True,
        "jalur": str(jalur),
        "nama": nama_peramban(jalur),
        "versi": versi(jalur),
        "sumber": _sumber(jalur),
        "pesan": "Peramban siap dipakai untuk merender halaman ber-JavaScript.",
        "alasan": "",
        "dicari": [],
    }
    return dict(_KETERSEDIAAN)


def _sumber(jalur: Path) -> str:
    """Dari mana jalur peramban ini berasal: pilihan Anda, variabel, atau sistem."""
    if jalur == pilihan_tersimpan():
        return "pilihan Anda"
    if str(jalur) == str(os.environ.get(BROWSER_ENV) or ""):
        return f"variabel {BROWSER_ENV}"
    return "terpasang di sistem"


def _alasan_tanpa_peramban(jejak: list[dict] | None = None) -> str:
    """Satu kalimat yang menjelaskan kenapa tidak ada peramban yang dipakai.

    Dua kegagalan yang berbeda harus dibedakan, karena penanganannya juga
    berbeda: berkasnya tidak ada di mana pun (pasang peramban), atau berkasnya
    ada tetapi menolak dijalankan (izin, kebijakan perusahaan, Chromium yang
    kehilangan pustaka).
    """
    if jejak is None:
        jejak = lacak()
    ada = [b for b in jejak if b["ada"]]
    if ada:
        return (
            f"Peramban ditemukan di {len(ada)} lokasi, tetapi tidak satupun yang dikenali "
            "sebagai peramban yang bisa dipakai. Bila komputer ini dikelola kantor, minta "
            "izin menjalankan peramban itu; atau tunjuk sendiri berkasnya di bawah."
        )
    return (
        f"Tidak ada berkas peramban di {len(jejak)} lokasi yang diperiksa. "
        "Pasang Microsoft Edge atau Google Chrome, lalu klik “Periksa ulang”."
    )


_KETERSEDIAAN: dict | None = None


def tersedia() -> bool:
    return bool(ketersediaan()["tersedia"])


def _bahasa_untuk_peramban(nilai: str) -> str:
    """Ubah `id-ID,id;q=0.9,en;q=0.5` menjadi `id-ID,id,en`.

    Chromium ingin daftar bahasa, bukan nilai berkualitas: bila diberi nilai
    berkualitas ia menyusun ulang sendiri dan hasilnya rusak
    (`id-ID,id;q=0.9;q=0.9,en;q=0.5;q=0.8`) — pernah kejadian, dan itu terlihat
    seperti permintaan yang cacat di sisi pemilik situs.
    """
    bagian = [b.strip().split(";")[0] for b in str(nilai or "").split(",")]
    bersih = [b for b in bagian if b]
    return ",".join(bersih) if bersih else "id-ID,id,en"


def _bendera_tanpa_jendela() -> int:
    return 0x08000000 if sys.platform.startswith("win") else 0  # CREATE_NO_WINDOW


# ---------------------------------------------------------------------------
# WebSocket kecil: hanya yang perlu untuk berbicara dengan peramban
# ---------------------------------------------------------------------------
def _bingkai(pesan: str, opcode: int = 0x1) -> bytes:
    """Bangun satu bingkai WebSocket dari klien (wajib bermasker)."""
    data = pesan.encode("utf-8")
    kepala = bytearray([0x80 | opcode])
    panjang = len(data)
    if panjang < 126:
        kepala.append(0x80 | panjang)
    elif panjang < 65_536:
        kepala.append(0x80 | 126)
        kepala += struct.pack(">H", panjang)
    else:
        kepala.append(0x80 | 127)
        kepala += struct.pack(">Q", panjang)
    mask = os.urandom(4)
    kepala += mask
    berkas = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return bytes(kepala) + berkas


def _bingkai_mentah(soket: socket.socket, *, batas: int = 64 * 1024 * 1024) -> tuple[int, bytes, bool]:
    """Baca satu bingkai apa adanya. Mengembalikan (opcode, isi, bingkai terakhir)."""
    def ambil(jumlah: int) -> bytes:
        keping = b""
        while len(keping) < jumlah:
            bagian = soket.recv(jumlah - len(keping))
            if not bagian:
                raise PerambanError("Koneksi ke peramban ditutup sebelum jawaban lengkap.")
            keping += bagian
        return keping

    kepala = ambil(2)
    akhir = bool(kepala[0] & 0x80)
    opcode = kepala[0] & 0x0F
    bermasker = bool(kepala[1] & 0x80)
    panjang = kepala[1] & 0x7F
    if panjang == 126:
        panjang = struct.unpack(">H", ambil(2))[0]
    elif panjang == 127:
        panjang = struct.unpack(">Q", ambil(8))[0]
    if panjang > batas:
        raise PerambanError(f"Jawaban peramban terlalu besar ({panjang} bita).")
    mask = ambil(4) if bermasker else b""
    data = ambil(panjang) if panjang else b""
    if bermasker:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, data, akhir


def _baca_bingkai(soket: socket.socket, *, batas: int = 64 * 1024 * 1024) -> tuple[int, bytes]:
    """Baca satu **pesan** utuh, menyatukan bingkai lanjutan bila pesannya dipecah.

    Satu pesan bisa datang sebagai beberapa bingkai; isi halaman dari peramban
    mudah melewati ukuran satu bingkai. Perlu diingat: bingkai lanjutan terakhir
    membawa tanda akhir (FIN), dan itulah yang mengakhiri pembacaan — bukan
    opcode-nya. Pernah salah di sini, dan akibatnya pembacaan menggantung
    selamanya sambil menunggu bita yang tidak akan datang.
    """
    opcode, data, akhir = _bingkai_mentah(soket, batas=batas)
    if akhir:
        return opcode, data
    awal = opcode
    while True:
        lanjut_op, lanjut_data, lanjut_akhir = _bingkai_mentah(soket, batas=batas)
        data += lanjut_data
        if len(data) > batas:
            raise PerambanError("Jawaban peramban terlalu besar.")
        if lanjut_op != 0x0:  # seharusnya hanya bingkai lanjutan
            raise PerambanError("Peramban mengirim bingkai yang tidak diharapkan.")
        if lanjut_akhir:
            return awal, data


class WebSocket:
    """Klien WebSocket seadanya: cukup untuk protokol peramban, tanpa pustaka luar."""

    def __init__(self, url: str, *, timeout: float = CMD_TIMEOUT) -> None:
        bagian = urlsplit(url)
        if bagian.scheme not in ("ws", "http", "https"):
            raise PerambanError(f"Alamat soket peramban tidak dikenal: {url}")
        host = bagian.hostname or "127.0.0.1"
        port = bagian.port or (443 if bagian.scheme == "https" else 80)
        jalur = bagian.path or "/"
        if bagian.query:
            jalur += "?" + bagian.query
        self.timeout = timeout
        self.soket = socket.create_connection((host, port), timeout=timeout)
        self.soket.settimeout(timeout)
        kunci = base64.b64encode(os.urandom(16)).decode()
        permintaan = (
            f"GET {jalur} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {kunci}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.soket.sendall(permintaan.encode())
        jawaban = b""
        while b"\r\n\r\n" not in jawaban:
            bagian_jawaban = self.soket.recv(4096)
            if not bagian_jawaban:
                raise PerambanError("Peramban menutup koneksi saat jabat tangan.")
            jawaban += bagian_jawaban
        baris_pertama = jawaban.split(b"\r\n", 1)[0].decode("latin-1")
        if "101" not in baris_pertama:
            raise PerambanError(f"Peramban menolak jabat tangan WebSocket: {baris_pertama.strip()}")
        diharapkan = base64.b64encode(
            hashlib.sha1((kunci + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()
        if diharapkan.lower() not in jawaban.decode("latin-1").lower():
            raise PerambanError("Jawaban jabat tangan peramban tidak sah.")

    def kirim(self, pesan: str | bytes) -> None:
        if isinstance(pesan, bytes):
            self.soket.sendall(_bingkai(pesan.decode("utf-8", "ignore"), 0x2))
        else:
            self.soket.sendall(_bingkai(pesan))

    def terima(self) -> str | None:
        """Baca satu pesan teks. Mengembalikan None bila peramban menutup koneksi."""
        while True:
            opcode, data = _baca_bingkai(self.soket)
            if opcode == 0x1:
                return data.decode("utf-8", "replace")
            if opcode == 0x2:
                return data.decode("utf-8", "replace")
            if opcode == 0x8:
                return None
            if opcode == 0x9:  # ping: wajib dijawab pong
                self.soket.sendall(_bingkai(data.decode("utf-8", "ignore"), 0xA))
                continue
            # pong atau opcode lain: abaikan, tunggu pesan berikutnya.

    def tutup(self) -> None:
        try:
            self.soket.sendall(_bingkai("", 0x8))
        except OSError:
            pass
        try:
            self.soket.close()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Sesi peramban
# ---------------------------------------------------------------------------
class Sesi:
    """Satu peramban headless yang dipakai berulang untuk banyak halaman.

    Dipakai sebagai pengelola konteks:

        with Sesi() as sesi:
            hasil = sesi.buka("https://contoh.example/")
    """

    def __init__(
        self,
        *,
        timeout: float = config.DEFAULT_TIMEOUT,
        wait_selector: str | None = None,
        blokir_media: bool = True,
        executable: str | Path | None = None,
        user_agent: str = config.USER_AGENT,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        # Bawaan: header jujur yang sama dengan jalur permintaan biasa, sehingga
        # pemilik situs melihat identitas dan bahasa yang sama di semua jalur.
        self.timeout = timeout
        self.wait_selector = wait_selector
        self.blokir_media = blokir_media
        self.user_agent = user_agent
        self.extra_headers = dict(config.HEADER_JUJUR if extra_headers is None else extra_headers)
        self.executable = Path(executable) if executable else cari()
        self.proses: subprocess.Popen | None = None
        self.soket: WebSocket | None = None
        self.session_id = ""
        self.target_id = ""
        self._folder: tempfile.TemporaryDirectory | None = None
        self._berikut = 0

    # -- hidup dan mati -----------------------------------------------------
    def __enter__(self) -> "Sesi":
        if self.executable is None:
            raise PerambanError(PETUNJUK_TANPA_PERAMBAN)
        if not Path(self.executable).is_file():
            raise PerambanError(f"Peramban tidak ditemukan di {self.executable}")
        self._folder = tempfile.TemporaryDirectory(prefix="lokaradar-peramban-")
        profil = Path(self._folder.name) / "data"
        profil.mkdir(parents=True, exist_ok=True)
        # Chrome Headless Shell sudah headless; memberi --headless=new justru ditolaknya.
        tanpa_jendela = "headless_shell" not in Path(self.executable).name.lower()
        perintah = [str(self.executable)]
        if tanpa_jendela:
            perintah.append("--headless=new")
        perintah += [
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-service-autorun",
            "--disable-extensions",
            "--disable-sync",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-client-side-phishing-detection",
            "--disable-domain-reliability",
            "--metrics-recording-only",
            "--mute-audio",
            "--hide-scrollbars",
            f"--user-data-dir={profil}",
            "--remote-debugging-port=0",
            "--lang=id-ID",
            f"--user-agent={self.user_agent}",
            "about:blank",
        ]
        LOG.info("Menjalankan peramban %s untuk rendering.", nama_peramban(Path(self.executable)))
        self.proses = subprocess.Popen(  # noqa: S603 - daftar argumen, bukan shell
            perintah,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_bendera_tanpa_jendela(),
        )
        try:
            port = self._tunggu_port(profil)
            self._sambung(port)
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc_info) -> None:
        if self.soket is not None:
            try:
                self._perintah("Browser.close", None, session=self.session_id or None, harapkan_jawaban=False)
            except (PerambanError, OSError):
                pass
            self.soket.tutup()
            self.soket = None
        if self.proses is not None:
            proses, self.proses = self.proses, None
            try:
                proses.terminate()
                proses.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proses.kill()
            except OSError:
                pass
        if self._folder is not None:
            # Chromium kadang masih menulis sebentar setelah keluar; kegagalan
            # pembersihan folder sementara bukan alasan menggagalkan pekerjaan.
            folder, self._folder = self._folder, None
            try:
                folder.cleanup()
            except OSError as error:
                LOG.debug("Folder data peramban tidak terhapus: %s", error)

    @property
    def aktif(self) -> bool:
        return self.soket is not None and bool(self.session_id)

    # -- penyambungan -------------------------------------------------------
    def _tunggu_port(self, profil: Path) -> int:
        berkas = profil / PORT_FILE
        batas = time.monotonic() + START_TIMEOUT
        while time.monotonic() < batas:
            if berkas.is_file():
                isi = berkas.read_text(encoding="utf-8", errors="replace").splitlines()
                if isi and isi[0].strip().isdigit():
                    return int(isi[0].strip())
            if self.proses is not None and self.proses.poll() is not None:
                raise PerambanError(
                    "Peramban langsung berhenti saat dijalankan. Coba jalankan "
                    "peramban itu sekali secara manual untuk memastikan bisa dipakai."
                )
            time.sleep(0.05)
        raise PerambanError(
            "Peramban tidak siap dalam 25 detik. Bila peramban sedang dipakai banyak "
            "tab, tutup sebagian lalu coba lagi."
        )

    def _sambung(self, port: int) -> None:
        alamat_ws = ""
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as jawaban:
                    alamat_ws = str(json.loads(jawaban.read().decode("utf-8")).get("webSocketDebuggerUrl") or "")
            except Exception as error:  # noqa: BLE001 - peramban butuh waktu menyala
                LOG.debug("Peramban belum menjawab: %s", error)
            if alamat_ws:
                break
            time.sleep(0.1)
        if not alamat_ws:
            raise PerambanError("Peramban tidak memberikan alamat kendali.")
        self.soket = WebSocket(alamat_ws, timeout=CMD_TIMEOUT)
        hasil = self._perintah("Target.createTarget", {"url": "about:blank"})
        self.target_id = str(hasil.get("targetId") or "")
        sesi = self._perintah(
            "Target.attachToTarget", {"targetId": self.target_id, "flatten": True}
        )
        self.session_id = str(sesi.get("sessionId") or "")
        if not self.session_id:
            raise PerambanError("Peramban tidak memberi sesi untuk halaman baru.")
        self._perintah("Page.enable", {})
        self._perintah("Network.enable", {})
        header = dict(self.extra_headers)
        # `Accept-Language` **tidak** dikirim lewat header tambahan: Chromium
        # menggabungkannya dengan pengaturan bahasanya sendiri dan hasilnya
        # menyesatkan (`id-ID,id;q=0.9;q=0.9,en;q=0.5;q=0.8`). Nilainya diatur
        # sekali di `Network.setUserAgentOverride` di bawah.
        bahasa = header.pop("Accept-Language", "") or config.HEADER_JUJUR["Accept-Language"]
        bahasa = _bahasa_untuk_peramban(bahasa)
        if header:
            self._perintah("Network.setExtraHTTPHeaders", {"headers": header})
        if self.blokir_media:
            self._perintah("Network.setBlockedURLs", {"urls": list(MEDIA_POLA)})
        # Bahasa juga diatur di sini: tanda `--lang` hanya mengubah bahasa
        # antarmuka peramban, bukan header `Accept-Language` permintaan.
        self._perintah(
            "Network.setUserAgentOverride",
            {"userAgent": self.user_agent, "acceptLanguage": bahasa},
        )

    # -- bicara dengan peramban --------------------------------------------
    def _perintah(
        self,
        method: str,
        params: dict | None,
        *,
        session: str | None = None,
        harapkan_jawaban: bool = True,
    ) -> dict:
        if self.soket is None:
            raise PerambanError("Peramban belum tersambung.")
        self._berikut += 1
        nomor = self._berikut
        pesan: dict = {"id": nomor, "method": method, "params": params or {}}
        sesi = session if session is not None else (self.session_id or None)
        if sesi:
            pesan["sessionId"] = sesi
        self.soket.kirim(json.dumps(pesan))
        if not harapkan_jawaban:
            return {}
        while True:
            mentah = self.soket.terima()
            if mentah is None:
                raise PerambanError("Peramban menutup koneksi sebelum menjawab.")
            try:
                balasan = json.loads(mentah)
            except ValueError:
                continue
            if balasan.get("id") != nomor:
                self._catat_kejadian(balasan)
                continue
            if "error" in balasan:
                galat = balasan["error"]
                pesan_galat = galat.get("message") if isinstance(galat, dict) else str(galat)
                raise PerambanError(f"Peramban menolak {method}: {pesan_galat}")
            return balasan.get("result") or {}

    def _catat_kejadian(self, balasan: dict) -> None:
        """Simpan kejadian yang berguna sambil menunggu jawaban."""
        if balasan.get("method") == "Network.responseReceived":
            parameter = balasan.get("params") or {}
            if (parameter.get("type") or "") == "Document":
                respons = parameter.get("response") or {}
                if not self._status and isinstance(respons.get("status"), int):
                    self._status = int(respons["status"])

    _status = 0

    def buka(self, url: str, *, wait_selector: str | None = None, timeout: float | None = None) -> Hasil:
        """Muat satu halaman dan kembalikan isinya setelah JavaScript berjalan."""
        if not self.aktif:
            raise PerambanError("Sesi peramban tidak aktif.")
        lama = timeout or self.timeout
        self._status = 0
        mulai = time.monotonic()
        jawaban = self._perintah(
            "Page.navigate", {"url": url}, session=self.session_id
        )
        galat_navigasi = str(jawaban.get("errorText") or "")
        dimuat = self._tunggu_kejadian("Page.loadEventFired", lama, session=self.session_id)
        if not dimuat and not galat_navigasi:
            galat_navigasi = "Halaman tidak selesai dimuat sampai batas waktu."
        selektor = wait_selector or self.wait_selector
        ditemukan: bool | None = None
        if selektor and not galat_navigasi:
            ditemukan = self._tunggu_selektor(selektor, lama)
            if not ditemukan:
                LOG.info("Selektor tunggu '%s' tidak ditemukan setelah halaman dirender.", selektor)
        hasil = self._ambil_isi(url, mulai)
        if galat_navigasi and not hasil.text:
            raise PerambanError(galat_navigasi)
        hasil.selektor_ditemukan = ditemukan
        if ditemukan is False:
            hasil.catatan = (
                f"Selektor tunggu '{selektor}' tidak ditemukan setelah halaman dirender; "
                "peramban menunggu sampai batas waktu dan isi halaman bisa belum lengkap."
            )
        elif galat_navigasi:
            hasil.catatan = galat_navigasi
        return hasil

    def _tunggu_kejadian(self, nama: str, timeout: float, *, session: str | None = None) -> bool:
        if self.soket is None:
            raise PerambanError("Peramban belum tersambung.")
        batas = time.monotonic() + timeout
        while time.monotonic() < batas:
            self.soket.soket.settimeout(max(0.5, min(2.0, batas - time.monotonic())))
            try:
                mentah = self.soket.terima()
            except (socket.timeout, TimeoutError):
                continue
            if mentah is None:
                raise PerambanError("Peramban menutup koneksi saat memuat halaman.")
            try:
                balasan = json.loads(mentah)
            except ValueError:
                continue
            if balasan.get("method") == nama:
                if session is None or balasan.get("sessionId") == session:
                    return True
            self._catat_kejadian(balasan)
        return False

    def _tunggu_selektor(self, selektor: str, timeout: float) -> bool:
        ekspresi = (
            "(() => { try { return Boolean(document.querySelector("
            + json.dumps(selektor)
            + ")); } catch (error) { return true; } })()"
        )
        batas = min(timeout, 15.0)
        akhir = time.monotonic() + batas
        while time.monotonic() < akhir:
            hasil = self._perintah(
                "Runtime.evaluate",
                {"expression": ekspresi, "returnByValue": True},
                session=self.session_id,
            )
            if (hasil.get("result") or {}).get("value") is True:
                return True
            time.sleep(0.25)
        return False

    def _ambil_isi(self, url: str, mulai: float) -> Hasil:
        ekspresi = (
            "JSON.stringify({"
            "url: document.documentURI,"
            "title: document.title || '',"
            "html: document.documentElement ? document.documentElement.outerHTML : '',"
            "text: document.body ? (document.body.innerText || document.body.textContent || '') : ''"
            "})"
        )
        hasil = self._perintah(
            "Runtime.evaluate",
            {"expression": ekspresi, "returnByValue": True, "awaitPromise": False},
            session=self.session_id,
        )
        mentah = (hasil.get("result") or {}).get("value")
        if not isinstance(mentah, str):
            raise PerambanError("Isi halaman tidak bisa dibaca dari peramban.")
        data = json.loads(mentah)
        html = str(data.get("html") or "")
        return Hasil(
            url=url,
            final_url=str(data.get("url") or url),
            status=int(self._status or 200),
            html=html[: config.DEFAULT_MAX_BYTES],
            text=_rapikan(str(data.get("text") or "")),
            title=str(data.get("title") or ""),
            ms=int((time.monotonic() - mulai) * 1000),
        )


def _rapikan(teks: str) -> str:
    """Rapikan teks hasil peramban: buang baris kosong beruntun."""
    baris = [b.rstrip() for b in teks.replace("\r\n", "\n").split("\n")]
    hasil: list[str] = []
    for b in baris:
        if b or (hasil and hasil[-1]):
            hasil.append(b)
    return "\n".join(hasil).strip()


def ambil(url: str, *, timeout: float = config.DEFAULT_TIMEOUT, wait_selector: str | None = None) -> Hasil:
    """Buka satu halaman dengan peramban sekali pakai (untuk pemeriksaan tunggal)."""
    with Sesi(timeout=timeout, wait_selector=wait_selector) as sesi:
        return sesi.buka(url)


def uji(jalur: str | Path | None = None) -> dict:
    """Periksa peramban secara jujur: benar-benar dipakai membuka satu halaman.

    Halaman yang diuji adalah halaman data milik radar sendiri, jadi pengujian ini
    tidak menghubungi situs siapa pun. Hasilnya menjelaskan apa yang berhasil dan
    apa yang tidak, bukan sekadar “siap” bila berkasnya ada.
    """
    if jalur:
        calon = Path(str(jalur)).expanduser()
        if not calon.is_file():
            return {
                "berhasil": False,
                "pesan": f"Berkas tidak ditemukan: {calon}",
                "peramban": ketersediaan(),
            }
        if not layak(calon):
            return {
                "berhasil": False,
                "pesan": f"Berkas ini tidak bisa dipakai sebagai peramban: {calon}",
                "peramban": ketersediaan(),
            }
        hasil = {
            "tersedia": True,
            "jalur": str(calon),
            "nama": nama_peramban(calon),
            "versi": versi(calon),
            "sumber": "pilihan Anda",
            "pesan": "Peramban siap dipakai untuk merender halaman ber-JavaScript.",
            "alasan": "",
            "dicari": [],
        }
    else:
        hasil = ketersediaan(refresh=True)
        if not hasil["tersedia"]:
            return {"berhasil": False, "pesan": hasil["pesan"], "peramban": hasil}
    halaman = (
        "data:text/html;charset=utf-8,"
        + urllib.parse.quote(
            "<!doctype html><html><head><title>Uji LokaRadar</title></head>"
            "<body><div id='isi'></div><script>"
            "document.getElementById('isi').textContent = 'Rendering berjalan: ' + (6*7);"
            "</script></body></html>",
            safe="",
        )
    )
    mulai = time.monotonic()
    try:
        with Sesi(timeout=15.0, executable=jalur) as sesi:
            keluaran = sesi.buka(halaman)
    except (PerambanError, OSError) as error:
        return {"berhasil": False, "pesan": f"Peramban ada, tetapi gagal dipakai: {error}", "peramban": hasil}
    lolos = "Rendering berjalan: 42" in keluaran.text
    if lolos and jalur:
        # Baru disimpan setelah benar-benar terbukti bisa merender: pilihan yang
        # disimpan sebelum itu akan terus dipakai walau tidak pernah bekerja.
        tetapkan(calon)
        hasil = ketersediaan(refresh=True)
    return {
        "berhasil": lolos,
        "pesan": (
            f"Rendering berjalan lewat {hasil['nama']} dalam {keluaran.ms} ms."
            if lolos
            else "Peramban terbuka tetapi isi hasil JavaScript tidak terbaca."
        ),
        "peramban": hasil,
        "ms": keluaran.ms,
        "uji_ms": int((time.monotonic() - mulai) * 1000),
    }


def ringkas() -> str:
    """Satu baris keadaan peramban untuk ditampilkan di antarmuka dan laporan."""
    info = ketersediaan()
    if not info["tersedia"]:
        return "Peramban: tidak ditemukan (halaman ber-JavaScript dibaca apa adanya)."
    versi_teks = f", {info['versi']}" if info["versi"] else ""
    return f"Peramban: {info['nama']}{versi_teks} ({info['sumber']})."
