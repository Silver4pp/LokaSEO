"""Cek kesiapan: satu halaman yang menjawab "apakah aplikasi ini siap dipakai di komputer ini?".

Dibuat karena satu hal yang tidak bisa diuji dari jauh: apakah paket ini benar
berjalan di Windows milik pengguna. Setiap butir di sini **diperiksa sungguhan**
— menulis berkas uji di folder data, menanyakan versi peramban, membaca status
penjadwal — dan hasilnya disusun jadi teks polos yang bisa disalin pengguna.

Tiga janji:

1. **Yang tidak bisa diperiksa dinyatakan apa adanya**, bukan dianggap lulus.
2. **Tidak ada rahasia di dalam laporan.** Kunci API, isi halaman, dan daftar
   alamat yang dipantau tidak ikut tertulis; laporan ini aman ditempelkan ke
   percakapan dukungan.
3. **Tidak menghubungi situs mana pun.** Tidak ada permintaan keluar yang
   dilakukan demi pemeriksaan ini; jaringan hanya dicoba saat pemeriksaan radar.
"""

import platform
import shutil
import sys
import time
from pathlib import Path

from . import config, jadwal, paths, radar

LULUS = "lulus"
PERHATIAN = "perhatian"
GAGAL = "gagal"
URUTAN = {GAGAL: 0, PERHATIAN: 1, LULUS: 2}

NAMA_LAPORAN = "Laporan Kesiapan LokaSEO"
BATAS_DISK_MB = 500
# Nama bulan bahasa Indonesia: strftime selalu memakai nama Inggris di banyak
# sistem, dan laporan ini dibaca orang Indonesia.
BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


def _butir(nama: str, keadaan: str, nilai: str, saran: str = "") -> dict:
    return {"nama": nama, "keadaan": keadaan, "nilai": nilai, "saran": saran}


def _galat(nama: str, error: BaseException) -> dict:
    return _butir(nama, GAGAL, f"pemeriksaan gagal: {type(error).__name__}: {error}", "Laporkan butir ini.")


def _teks_waktu() -> tuple[str, str]:
    sekarang = time.localtime()
    teks_waktu = f"{sekarang.tm_mday} {BULAN[sekarang.tm_mon - 1]} {sekarang.tm_year} {sekarang.tm_hour:02d}:{sekarang.tm_min:02d}"
    offset = time.strftime("%z", sekarang)
    if offset:
        tanda = offset[0]
        jam = int(offset[1:3])
        menit = offset[3:]
        zona = f"UTC{tanda}{jam}" + (f":{menit}" if menit != "00" else "")
    else:
        zona = "zona waktu tidak diketahui"
    return teks_waktu, f"{time.tzname[0]}, {zona}"


# -- butir pemeriksaan -------------------------------------------------------
def _butir_versi() -> dict:
    versi_radar = None
    try:
        # `_modul()` menambahkan folder radar ke sys.path, jadi versinya baru
        # terbaca setelah modul radar dimuat. Kalau radar tidak ada, butir ini
        # tetap lulus: versi aplikasi tidak perlu menunggu radar.
        radar._modul()  # noqa: SLF001
        from lokaradar import __version__ as versi_radar  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - radar tidak ada bukan alasan laporan gagal
        versi_radar = versi_radar or None
    dari_paket = bool(getattr(sys, "frozen", False))
    nilai = f"LokaSEO {config.APP_VERSION}"
    if versi_radar:
        nilai += f" · LokaRadar {versi_radar}"
    nilai += " · dijalankan dari paket (.exe)" if dari_paket else " · dijalankan dari source"
    return _butir("Versi aplikasi", LULUS, nilai)


def _butir_sistem() -> dict:
    bit = platform.architecture()[0]
    nilai = f"{platform.system()} {platform.release()} ({platform.version()}) · {bit} · Python {platform.python_version()}"
    return _butir("Sistem", LULUS, nilai)


def _butir_folder_data() -> dict:
    folder = paths.data_dir()
    uji = folder / ".kesiapan-uji"
    try:
        uji.write_text("uji", encoding="utf-8")
        uji.unlink()
        tulis = "bisa ditulis"
    except OSError as error:
        return _butir(
            "Folder data",
            GAGAL,
            f"{folder} — tidak bisa menulis: {error}",
            "Pastikan folder ini bisa ditulis atau setel LOKA_DATA_DIR ke folder lain.",
        )
    try:
        bebas_mb = shutil.disk_usage(folder).free // (1024 * 1024)
    except OSError:
        bebas_mb = None
    nilai = f"{folder} ({tulis}"
    nilai += f", sisa ruang {bebas_mb / 1024:.1f} GB)" if bebas_mb is not None else ")"
    if bebas_mb is not None and bebas_mb < BATAS_DISK_MB:
        return _butir(
            "Folder data",
            PERHATIAN,
            nilai,
            f"Sisa ruang di bawah {BATAS_DISK_MB} MB; kosongkan sedikit agar riwayat radar aman.",
        )
    if not (folder / "lokaseo.log").exists():
        return _butir("Folder data", LULUS, nilai + " — berkas log belum dibuat (wajar saat baru dipasang)")
    return _butir("Folder data", LULUS, nilai)


def _butir_berkas_log() -> dict:
    berkas = paths.log_file()
    try:
        if berkas.parent.exists():
            uji = berkas.parent / ".log-uji"
            uji.write_text("uji", encoding="utf-8")
            uji.unlink()
        ukuran = berkas.stat().st_size if berkas.exists() else None
    except OSError as error:
        return _butir("Berkas log", PERHATIAN, f"{berkas} — {error}", "Catatan pemeriksaan terjadwal masuk ke sini.")
    nilai = str(berkas)
    nilai += f" ({ukuran / 1024:.0f} KB)" if ukuran else " (belum ada)"
    return _butir("Berkas log", LULUS, nilai)


def _butir_radar() -> dict:
    try:
        tersedia = bool(radar.tersedia())
    except Exception as error:  # noqa: BLE001
        return _galat("Modul radar", error)
    if not tersedia:
        return _butir(
            "Modul radar",
            PERHATIAN,
            "tidak bisa dimuat",
            "Tanpa modul radar, ruang kerja SEO tetap jalan tetapi pemantauan tidak. "
            "Jalankan aplikasi dari paket lengkap atau setel LOKARADAR_ROOT ke folder `radar/`.",
        )
    modul = radar._modul()  # noqa: SLF001 - modul yang sama dipakai seluruh aplikasi
    asal = "dari dalam paket" if modul.get("dari_bundel") else f"dari folder {modul.get('akar')}"
    return _butir("Modul radar", LULUS, f"tersedia {asal}")


def _butir_data_radar() -> dict:
    try:
        statistik = radar._modul()["Store"]  # noqa: SLF001
        with statistik() as store:
            angka = store.stats()
    except Exception as error:  # noqa: BLE001
        return _butir("Data radar", PERHATIAN, f"belum bisa dibaca ({type(error).__name__})", "")
    nilai = (
        f"{angka['sasaran']} sasaran ({angka['sasaran_aktif']} aktif) · "
        f"{angka['potret']} potret · {angka['perubahan']} perubahan"
    )
    return _butir("Data radar", LULUS, nilai)


def _butir_peramban() -> dict:
    try:
        info = radar.peramban()
    except Exception as error:  # noqa: BLE001
        return _galat("Peramban", error)
    if not info.get("tersedia"):
        return _butir(
            "Peramban",
            PERHATIAN,
            "tidak ada peramban yang ditemukan",
            _ascii(info.get("alasan") or "")
            or "Halaman ber-JavaScript belum bisa dirender. Pasang Microsoft Edge atau Google "
            "Chrome, lalu klik 'Periksa ulang' di halaman radar.",
        )
    nama = info.get("nama") or "peramban"
    versi = f" ({info['versi']})" if info.get("versi") else ""
    asal = info.get("sumber") or ""
    nilai = f"{nama}{versi}" + (f" · {asal}" if asal else "")
    return _butir("Peramban", LULUS, nilai)


def _butir_penjadwal() -> dict:
    try:
        info = jadwal.status()
    except jadwal.JadwalError as error:
        return _butir("Penjadwal otomatis", PERHATIAN, str(error), "")
    except Exception as error:  # noqa: BLE001
        return _galat("Penjadwal otomatis", error)
    dukungan = info.get("dukungan") or {}
    if not dukungan.get("bisa"):
        return _butir(
            "Penjadwal otomatis",
            PERHATIAN,
            dukungan.get("pesan") or "penjadwal tidak tersedia di sistem ini",
            f"Jalankan pemeriksaan manual, atau daftarkan cron: {info.get('cron') or 'lihat halaman radar'}",
        )
    if not info.get("terpasang"):
        return _butir(
            "Penjadwal otomatis",
            PERHATIAN,
            "belum diaktifkan (tugas belum terpasang)",
            "Buka bagian “Pemeriksaan otomatis” di halaman radar lalu aktifkan bila ingin diperiksa sendiri.",
        )
    jadwal_teks = f"{info.get('frekuensi', 'harian')} pukul {info.get('waktu', '')}"
    if info.get("frekuensi") == "mingguan" and info.get("hari"):
        jadwal_teks += f" ({info['hari']})"
    keadaan = "aktif" if info.get("aktif") else "terpasang tetapi tidak aktif"
    return _butir("Penjadwal otomatis", LULUS, f"{keadaan} · {jadwal_teks}")


def _butir_pemeriksaan_terakhir() -> dict:
    try:
        with radar._modul()["Store"]() as store:  # noqa: SLF001
            terakhir = store.get_state("terakhir_jalan")
    except Exception as error:  # noqa: BLE001
        return _butir("Pemeriksaan terakhir", PERHATIAN, f"belum bisa dibaca ({type(error).__name__})", "")
    if not terakhir:
        return _butir(
            "Pemeriksaan terakhir",
            PERHATIAN,
            "belum pernah dijalankan",
            "Klik “Periksa sekarang” sekali agar ada potret pertama; perubahan hanya terlihat setelah dua kali.",
        )
    return _butir("Pemeriksaan terakhir", LULUS, terakhir)


def _butir_kunci_places() -> dict:
    try:
        terpasang = bool(radar._modul()["places"].key_from_env())  # noqa: SLF001
    except Exception:  # noqa: BLE001
        return _butir("Kunci Places API", PERHATIAN, "belum bisa diperiksa (radar tidak termuat)", "")
    if terpasang:
        return _butir("Kunci Places API", LULUS, "terpasang lewat variabel lingkungan (kuncinya tidak ikut ditulis di laporan)")
    return _butir(
        "Kunci Places API",
        LULUS,
        "belum diatur (tidak wajib)",
        "",
    )


def _butir_alamat(alamat: str, luring: bool) -> dict:
    nilai = f"{alamat} · hanya 127.0.0.1 · pemeriksaan host aktif"
    if luring:
        nilai += " · mode luring aktif"
    return _butir("Alamat antarmuka", LULUS, nilai)


def _butir_waktu() -> dict:
    waktu, zona = _teks_waktu()
    return _butir("Jam komputer", LULUS, f"{waktu} ({zona})")


# Nama fungsi disimpan sebagai teks, bukan dipegang langsung: dengan begitu
# tiap butir tetap bisa diganti saat pengujian (dan satu butir yang meledak
# tetap bisa ditangkap tanpa menjatuhkan laporan).
BUTIR = (
    ("Versi aplikasi", "_butir_versi"),
    ("Sistem", "_butir_sistem"),
    ("Jam komputer", "_butir_waktu"),
    ("Folder data", "_butir_folder_data"),
    ("Berkas log", "_butir_berkas_log"),
    ("Modul radar", "_butir_radar"),
    ("Data radar", "_butir_data_radar"),
    ("Peramban", "_butir_peramban"),
    ("Penjadwal otomatis", "_butir_penjadwal"),
    ("Pemeriksaan terakhir", "_butir_pemeriksaan_terakhir"),
    ("Kunci Places API", "_butir_kunci_places"),
)


def periksa(*, alamat: str = "", luring: bool = False) -> dict:
    """Jalankan semua pemeriksaan; tidak pernah melempar galat ke pemanggil."""
    butir = []
    for nama, nama_fungsi in BUTIR:
        try:
            butir.append(globals()[nama_fungsi]())
        except Exception as error:  # noqa: BLE001 - satu butir gagal bukan alasan seluruh laporan gagal
            butir.append(_galat(nama, error))
    if alamat:
        butir.append(_butir_alamat(alamat, luring))
    ringkasan = {
        LULUS: sum(1 for satu in butir if satu["keadaan"] == LULUS),
        PERHATIAN: sum(1 for satu in butir if satu["keadaan"] == PERHATIAN),
        GAGAL: sum(1 for satu in butir if satu["keadaan"] == GAGAL),
    }
    laporan = {
        "dibuat_pada": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "luring": bool(luring),
        "ringkasan": ringkasan,
        "butir": butir,
    }
    laporan["teks"] = teks(laporan)
    return laporan


def _ascii(teks: str) -> str:
    """Ganti tanda baca „elok” dengan padanan ASCII agar terbaca di konsol Windows."""
    ganti = {
        "\u00b7": "|", "\u2014": "-", "\u2013": "-", "\u2026": "...",
        "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
    }
    for asal, tujuan in ganti.items():
        teks = teks.replace(asal, tujuan)
    return teks


def teks(laporan: dict) -> str:
    """Susun laporan teks polos yang bisa disalin pengguna."""
    waktu, zona = _teks_waktu()
    ringkasan = laporan["ringkasan"]
    baris = [
        NAMA_LAPORAN.upper(),
        "=" * len(NAMA_LAPORAN),
        f"Dibuat     : {waktu} ({zona})",
    ]
    versi = next((butir["nilai"] for butir in laporan["butir"] if butir["nama"] == "Versi aplikasi"), "")
    if versi:
        baris.append(f"Versi      : {versi}")
    baris.append(
        f"Hasil      : {ringkasan[LULUS]} lulus | {ringkasan[PERHATIAN]} perhatian | {ringkasan[GAGAL]} gagal"
    )
    baris.append("")
    baris.append("BUTIR PEMERIKSAAN")
    tanda = {LULUS: "[LULUS]    ", PERHATIAN: "[PERHATIAN]", GAGAL: "[GAGAL]    "}
    lebar = max(len(butir["nama"]) for butir in laporan["butir"])
    for butir in laporan["butir"]:
        baris.append(f"{tanda[butir['keadaan']]} {butir['nama'].ljust(lebar)} : {butir['nilai']}")
    perlu = [butir for butir in laporan["butir"] if butir["keadaan"] in (GAGAL, PERHATIAN) and butir["saran"]]
    if perlu:
        baris.append("")
        baris.append("YANG PERLU DILAKUKAN")
        for nomor, butir in enumerate(perlu, 1):
            baris.append(f"{nomor}. {butir['nama']}: {butir['saran']}")
    gagal = [butir for butir in laporan["butir"] if butir["keadaan"] == GAGAL]
    if not gagal:
        perhatian = [butir for butir in laporan["butir"] if butir["keadaan"] == PERHATIAN]
        baris.append("")
        baris.append(
            "Tidak ada butir yang gagal."
            + (" Butir bertanda perhatian bukan kerusakan: hanya belum diatur atau belum ada." if perhatian else "")
        )
    baris.append("")
    baris.append("CATATAN")
    baris.append("- Laporan ini tidak memuat kunci API, isi halaman, maupun daftar alamat yang Anda pantau.")
    baris.append("- Tidak ada data yang dikirim ke mana pun: laporan ini dibuat dan berhenti di komputer Anda.")
    baris.append("- Salin seluruh laporan ini bila Anda melaporkan masalah, supaya penyebabnya bisa ditelusuri.")
    # Laporan ini dibaca di konsol Windows yang code page-nya bisa apa saja; karena
    # itu semua penanda dirapikan dulu agar tidak muncul sebagai tanda tanya.
    return _ascii("\n".join(baris) + "\n")
