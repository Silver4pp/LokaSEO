#!/usr/bin/env python3
"""Bangun tiga berkas rilis LokaSEO dari satu sumber.

Jalankan dari mana saja:

    python3 desktop/alat/buat-paket-rilis.py [JALUR_EXE]

Nama berkasnya tetap, jadi rilis baru menimpa yang lama — pengguna tidak perlu
menebak berkas mana yang terbaru. Versinya terbaca di dalam BACA-INI-DULU.txt
dan di laporan kesiapan aplikasi.

Hasil (bertempat di folder induk repositori):
  - LokaSEO-Windows.zip        -> pengguna awam: exe siap klik dua kali.
                                  INI satu-satunya paket yang memuat .exe.
  - LokaSEO-untuk-Windows.zip  -> kode sumber + antarmuka yang sudah dibangun,
                                  TANPA .exe. Jalur kedua bila anti-virus
                                  memberi tanda pada .exe; dijalankan dengan
                                  Python, lihat MULAI-DI-WINDOWS.txt.
  - LokaSEO-source.zip         -> kode sumber saja, tanpa antarmuka yang sudah
                                  dibangun dan tanpa .exe.

Nama berkasnya sengaja tidak memuat nomor versi. Konsekuensinya: tiga berkas
ini tidak bisa dibedakan dari namanya saja, jadi jangan menebak isinya --
periksa keberadaan LokaSEO-console.exe di dalamnya sebelum menyuruh pengguna
mengkliknya.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # <repo>/desktop/alat/buat-paket-rilis.py
RUMAH = REPO.parent
AKAR_ZIP = "loka-seo"  # nama folder di dalam zip, harus tetap "loka-seo"
# Bawaan yang masuk akal: hasil build PyInstaller di mesin ini, bukan sisa sesi lama.
EXE_BAWAAN = REPO / "desktop" / "dist" / "LokaSEO-console.exe"

# Tidak pernah masuk paket: rahasia lokal, berkas besar sementara, dan sisa uji.
SELALU_BUANG = {
    ".git", ".env.local", "node_modules", "__pycache__", "test-results",
    ".cache", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}
DIREKTORI_BUANG = {
    "desktop/build", "desktop/dist",
}

BACA_INI = """LokaSEO untuk Windows -- versi {versi}
=====================================

Anda TIDAK perlu memasang apa pun. Tidak perlu Python, tidak perlu Node.js.

CARA MENJALANKAN
----------------
1. Ekstrak zip ini ke folder biasa, misalnya C:\\LokaSEO.
   (Jangan dijalankan dari dalam zip.)
2. Klik dua kali: LokaSEO-console.exe
3. Beberapa detik kemudian peramban Anda terbuka sendiri ke halaman LokaSEO.

Jendela hitam yang muncul itu bagian dari aplikasinya - biarkan terbuka selama
Anda memakai LokaSEO. Itu juga tempat pesan galat muncul bila ada yang tidak beres.

MENGhentikan aplikasi (ada tiga cara, pilih satu):
- Klik ikon LokaSEO di sudut kanan bawah layar (tray) -> Keluar, atau
- Tombol "Hentikan aplikasi" di halaman radar, atau
- Tutup jendela hitamnya.

Catatan: saat pertama dijalankan, Windows mungkin menampilkan peringatan
"Windows protected your PC" (SmartScreen). Itu muncul karena berkas ini tidak
ditandatangani secara digital. Klik "More info" -> "Run anyway" bila Anda
percaya berkas ini (berkasnya dibuat dari kode sumber yang Anda miliki).

BEBERAPA ANTI-VIRUS memberi tanda pada berkas .exe buatan PyInstaller. Bila itu
terjadi, Anda selalu punya jalur kedua: paket sumber LokaSEO-untuk-Windows.zip
(berkas terpisah, 17 MB) yang dijalankan dengan Python - lihat
MULAI-DI-WINDOWS.txt di folder ini.

UJI CEPAT 15 MENIT
------------------
- Buka docs\\lokaseo\\cara-uji-windows.txt (10 langkah, dengan hasil yang seharusnya).
- Di halaman radar, bagian bawah: "Kesiapan aplikasi di komputer ini" ->
  klik "Periksa kesiapan" -> "Salin laporan". Tempelkan laporannya bila ada
  yang tidak beres. Laporan itu tidak memuat kunci API, isi halaman, maupun
  daftar alamat Anda.

APA ISI PAKET INI
-----------------
  LokaSEO-console.exe           aplikasi ({ukuran} MB, satu berkas, tanpa pemasangan)
  docs\\lokaseo\\cara-pakai-desktop.txt  daftar kemampuan dan batasannya
  docs\\lokaseo\\cara-uji-windows.txt    panduan uji 10 langkah
  MULAI-DI-WINDOWS.txt          cara menjalankan dari sumber (Python), bila perlu

Semua data Anda (sasaran, riwayat, laporan) tersimpan di komputer Anda sendiri:
  C:\\Users\\<nama Anda>\\AppData\\Roaming\\LokaSEO
Tidak ada data yang dikirim ke mana pun. Aplikasi ini hanya membuka 127.0.0.1.
"""


def versi_aplikasi() -> str:
    teks = (REPO / "desktop/lokaseo_desktop/config.py").read_text(encoding="utf-8")
    cocok = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', teks)
    if not cocok:
        raise SystemExit("APP_VERSION tidak ditemukan di desktop/lokaseo_desktop/config.py")
    return cocok.group(1)


def layak(masuk: Path, *, ikut_loka_release: bool) -> bool:
    bagian = masuk.relative_to(REPO).parts
    if any(b in SELALU_BUANG for b in bagian):
        return False
    if masuk.suffix == ".pyc":
        return False
    jalur = "/".join(bagian)
    if any(jalur == d or jalur.startswith(d + "/") for d in DIREKTORI_BUANG):
        return False
    if not ikut_loka_release and (bagian[0] == "loka-release" or bagian[0] == ".env.local"):
        return False
    return True


def tulis_zip(tujuan: Path, berkas: list[Path]) -> None:
    with zipfile.ZipFile(tujuan, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in berkas:
            z.write(p, arcname=f"{AKAR_ZIP}/{p.relative_to(REPO).as_posix()}")


def periksa(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as z:
        rusak = z.testzip()
        jumlah = len(z.namelist())
    tanda = "integritas OK" if rusak is None else f"RUSAK: {rusak}"
    print(f"  {zip_path.name:34s} {zip_path.stat().st_size:>12,} B  {jumlah:5d} entri  {tanda}")


def tulis_baca_ini(versi: str, exe: Path, tujuan: Path) -> None:
    ukuran = f"{exe.stat().st_size / 1_000_000:.1f}"
    tujuan.write_text(BACA_INI.format(versi=versi, ukuran=ukuran), encoding="utf-8")


def tulis_paket_windows(versi: str, exe: Path, tujuan: Path) -> None:
    akar = f"LokaSEO-Windows/"
    baca = tujuan.parent / "BACA-INI-DULU.txt"
    tulis_baca_ini(versi, exe, baca)
    pasangan = [
        (exe, akar + "LokaSEO-console.exe"),
        (baca, akar + "BACA-INI-DULU.txt"),
        (REPO / "MULAI-DI-WINDOWS.txt", akar + "MULAI-DI-WINDOWS.txt"),
        (REPO / "docs/lokaseo/cara-pakai-desktop.txt", akar + "CARA-PAKAI.txt"),
        (REPO / "docs/lokaseo/cara-uji-windows.txt", akar + "CARA-UJI-WINDOWS.txt"),
    ]
    with zipfile.ZipFile(tujuan, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr(akar, "")
        for sumber, nama in pasangan:
            z.write(sumber, arcname=nama)
    baca.unlink()


def main() -> int:
    exe = Path(sys.argv[1]) if len(sys.argv) > 1 else EXE_BAWAAN
    if not exe.exists():
        raise SystemExit(f"berkas .exe tidak ada: {exe}")
    versi = versi_aplikasi()
    semua = sorted(p for p in REPO.rglob("*") if p.is_file() and layak(p, ikut_loka_release=True))
    sumber = [p for p in semua if layak(p, ikut_loka_release=False)]

    paket = {
        RUMAH / "LokaSEO-Windows.zip": None,
        RUMAH / "LokaSEO-untuk-Windows.zip": semua,
        RUMAH / "LokaSEO-source.zip": sumber,
    }
    print(f"versi {versi} | exe {exe} ({exe.stat().st_size:,} B)")
    for tujuan, daftar in paket.items():
        if daftar is None:
            tulis_paket_windows(versi, exe, tujuan)
        else:
            tulis_zip(tujuan, daftar)
    print("hasil:")
    for tujuan in paket:
        periksa(tujuan)
    loka = RUMAH / "LokaSEO-untuk-Windows.zip"
    with zipfile.ZipFile(loka) as z:
        jumlah = sum(1 for n in z.namelist() if n.startswith("loka-seo/loka-release/"))
    print(f"  antarmuka siap pakai di LokaSEO-untuk-Windows.zip: {jumlah} berkas loka-release/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
