"""Pemeriksaan radar otomatis: satu tugas harian di Windows Task Scheduler.

Radar berguna justru karena dijalankan rutin: perubahan harga dan rating baru
terlihat artinya setelah ada pembanding dari hari sebelumnya. Menuntut pengguna
membuka aplikasi tiap hari bukan rencana yang bertahan lama, jadi bagian ini
memasang satu tugas Windows yang memanggil aplikasi pada jam yang dipilih
pengguna.

Prinsip yang dipegang:

- **Tidak ada yang dipasang diam-diam.** Tugas hanya dibuat setelah pengguna
  menekannya, dan perintah yang akan didaftarkan ditampilkan apa adanya lebih
  dulu. Satu tombol menghapusnya kembali.
- **Tanpa hak administrator.** Tugas dibuat untuk pengguna yang sedang masuk
  (schtasks bawaan), bukan tugas sistem.
- **Tidak lebih sering dari sekali sehari.** Radar memeriksa situs orang lain;
  jadwal per jam akan menjadi beban yang tidak diminta. Pilihan yang tersedia
  hanya harian atau mingguan.
- **Jujur soal batasnya.** Bila komputer mati atau sedang tidur pada jam itu,
  pemeriksaan itu terlewat dan tidak menyusul sendiri.
- **Bisa diuji tanpa Windows.** Seluruh pemanggilan `schtasks` lewat satu pintu
  (`runner`) yang dapat diganti pada pengujian, dan naskah XML tugas dibaca
  memakai nama unsur bahasa Inggris sehingga tidak bergantung bahasa Windows.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from . import paths

LOG = logging.getLogger("lokaseo")

# Nama tugas. Dipakai apa adanya saat membuat, membaca, dan menghapus.
NAMA_TUGAS = "LokaSEO - Radar harian"

# Pilihan yang diizinkan. Sengaja tidak ada pilihan per jam.
FREKUENSI = {"harian": "HARIAN", "mingguan": "MINGGUAN"}
HARI = {
    "senin": "MON",
    "selasa": "TUE",
    "rabu": "WED",
    "kamis": "THU",
    "jumat": "FRI",
    "sabtu": "SAT",
    "minggu": "SUN",
}
HARI_URUT = list(HARI)
WAKTU_BAWAAN = "07:00"

# Batas waktu satu panggilan schtasks. Cepat; kalau lebih dari ini ada masalah.
BATAS_DETIK = 30


class JadwalError(RuntimeError):
    """Penjadwalan tidak bisa dijalankan atau gagal."""


class MasukanJadwalTidakSah(JadwalError):
    """Jam, frekuensi, atau hari yang dikirim antarmuka tidak masuk akal."""


# -- pintu ke sistem ---------------------------------------------------------
def _jalankan(perintah: list[str]) -> tuple[int, str]:
    """Pintu tunggal ke `schtasks`. Diganti pada pengujian."""
    creationflags = 0x08000000 if sys.platform.startswith("win") else 0  # CREATE_NO_WINDOW
    try:
        hasil = subprocess.run(  # noqa: S603 - daftar argumen, bukan shell
            perintah,
            capture_output=True,
            text=True,
            timeout=BATAS_DETIK,
            check=False,
            creationflags=creationflags,
        )
    except FileNotFoundError as error:
        raise JadwalError("Perintah `schtasks` tidak ditemukan di komputer ini.") from error
    except subprocess.TimeoutExpired as error:
        raise JadwalError("Penjadwal Windows tidak menjawab dalam 30 detik.") from error
    keluaran = (hasil.stdout or "") + (hasil.stderr or "")
    return hasil.returncode, keluaran.strip()


def dukungan(*, windows: bool | None = None) -> dict:
    """Apakah penjadwalan bisa dipakai di komputer ini.

    Bila `windows` diberikan, pemeriksaan keberadaan `schtasks` dilewati: nilai
    itu berarti pemanggil sudah menentukan sendiri bahwa mesinnya Windows (dipakai
    pengujian). Tanpa argumen, keduanya diperiksa sungguhan.
    """
    otomatis = windows is None
    if otomatis:
        windows = sys.platform.startswith("win")
    if not windows:
        return {
            "bisa": False,
            "platform": sys.platform,
            "nama_tugas": NAMA_TUGAS,
            "pesan": (
                "Penjadwalan lewat Windows Task Scheduler hanya tersedia di Windows. "
                "Di Linux atau macOS, pakai cron dengan perintah yang tampil di bawah."
            ),
        }
    if otomatis and shutil.which("schtasks") is None:
        return {
            "bisa": False,
            "platform": sys.platform,
            "nama_tugas": NAMA_TUGAS,
            "pesan": "`schtasks` tidak ditemukan, jadi jadwal otomatis tidak bisa dipasang.",
        }
    return {
        "bisa": True,
        "platform": sys.platform,
        "nama_tugas": NAMA_TUGAS,
        "pesan": "Windows Task Scheduler siap dipakai.",
    }


# -- perintah yang dijalankan penjadwal --------------------------------------
def program_terbaik(program: str | None = None) -> str:
    """Program yang dipanggil penjadwal.

    Bila ada `LokaSEO.exe` (tanpa jendela konsol) di folder yang sama, itu yang
    dipakai supaya jendela hitam tidak berkedip setiap pagi. Kalau tidak ada,
    `LokaSEO-console.exe` tetap bekerja — hasilnya masuk ke berkas catatan.
    """
    if program:
        return str(program)
    if not getattr(sys, "frozen", False):
        return sys.executable
    kini = Path(sys.executable).resolve()
    jendela = kini.with_name("LokaSEO.exe")
    if jendela.is_file():
        return str(jendela)
    return str(kini)


def perintah_periksa(program: str | None = None) -> list[str]:
    """Susunan perintah yang dijalankan setiap kali tugas menyala."""
    exe = program_terbaik(program)
    if getattr(sys, "frozen", False) or program:
        return [exe, "--radar-periksa"]
    # Dijalankan dari source: panggil run.py di folder desktop.
    peluncur = Path(__file__).resolve().parent.parent / "run.py"
    return [exe, str(peluncur), "--radar-periksa"]


def _teks_perintah(keping: list[str]) -> str:
    """Satu baris perintah yang bisa dibaca manusia (dan disalin ke cron)."""
    hasil = []
    for bagian in keping:
        hasil.append(f'"{bagian}"' if " " in bagian else bagian)
    return " ".join(hasil)


def perintah_tugas(
    *,
    waktu: str = WAKTU_BAWAAN,
    frekuensi: str = "harian",
    hari: str = "",
    program: str | None = None,
) -> list[str]:
    """Argumen `schtasks /Create` yang dipasang untuk pengguna ini."""
    waktu, frekuensi, hari = _periksa_masukan(waktu, frekuensi, hari)
    # Nilai /TR adalah satu baris perintah apa adanya. Kutip hanya dibutuhkan di
    # sekitar jalur program yang mengandung spasi; mengurung seluruh baris malah
    # membuat schtasks mencari berkas bernama seluruh baris itu.
    aksi = _teks_perintah(perintah_periksa(program))
    perintah = [
        "schtasks",
        "/Create",
        "/TN",
        NAMA_TUGAS,
        "/TR",
        aksi,
        "/F",
    ]
    if frekuensi == "mingguan":
        perintah += ["/SC", "WEEKLY", "/D", HARI[hari], "/ST", waktu]
    else:
        perintah += ["/SC", "DAILY", "/ST", waktu]
    return perintah


def jadwal_cron(waktu: str = WAKTU_BAWAAN, *, frekuensi: str = "harian", hari: str = "") -> str:
    """Baris crontab untuk pengguna Linux/macOS yang menjalankan dari source."""
    waktu, frekuensi, hari = _periksa_masukan(waktu, frekuensi, hari)
    jam, menit = waktu.split(":")
    aksi = _teks_perintah(perintah_periksa())
    if frekuensi == "mingguan":
        nomor = (HARI_URUT.index(hari) + 1) % 7
        return f"{int(menit)} {int(jam)} * * {nomor} {aksi}"
    return f"{int(menit)} {int(jam)} * * * {aksi}"


# -- pemeriksaan masukan -----------------------------------------------------
def _periksa_waktu(waktu: str) -> str:
    mentah = str(waktu or "").strip()
    if not mentah:
        raise MasukanJadwalTidakSah("Jam pemeriksaan belum diisi (contoh: 07:00).")
    bagian = mentah.split(":")
    if len(bagian) != 2 or not all(p.isdigit() for p in bagian):
        raise MasukanJadwalTidakSah("Jam harus berbentuk HH:MM, contoh 07:00 atau 19:30.")
    jam, menit = int(bagian[0]), int(bagian[1])
    if jam > 23 or menit > 59:
        raise MasukanJadwalTidakSah("Jam harus antara 00:00 dan 23:59.")
    return f"{jam:02d}:{menit:02d}"


def _periksa_masukan(waktu: str, frekuensi: str, hari: str) -> tuple[str, str, str]:
    jam = _periksa_waktu(waktu)
    rekan = str(frekuensi or "harian").strip().lower()
    if rekan not in FREKUENSI:
        raise MasukanJadwalTidakSah(
            "Frekuensi hanya boleh harian atau mingguan. Radar tidak memeriksa lebih "
            "sering dari sekali sehari supaya tidak membebani situs orang."
        )
    if rekan == "mingguan":
        harinya = str(hari or "").strip().lower()
        if harinya not in HARI:
            raise MasukanJadwalTidakSah(
                "Pilih hari untuk jadwal mingguan (senin sampai minggu)."
            )
        return jam, rekan, harinya
    return jam, rekan, ""


# -- bacaan keadaan ----------------------------------------------------------
def _baca_xml(xml: str) -> dict:
    """Baca naskah XML tugas. Nama unsur XML selalu bahasa Inggris."""
    try:
        akar = ET.fromstring(xml)
    except ET.ParseError as error:
        raise JadwalError("Jawaban penjadwal Windows tidak bisa dibaca.") from error

    def cari(nama: str) -> str:
        simpul = akar.find(f".//{{*}}{nama}")
        return (simpul.text or "").strip() if simpul is not None and simpul.text else ""

    simpul_aktif = akar.find(".//{*}Settings/{*}Enabled")
    teks_aktif = (simpul_aktif.text or "").strip() if simpul_aktif is not None and simpul_aktif.text else cari("Enabled")
    aktif = teks_aktif.lower() != "false"
    mulai = cari("StartBoundary")
    waktu = ""
    if "T" in mulai:
        waktu = mulai.split("T", 1)[1][:5]
    if akar.find(".//{*}ScheduleByWeek") is not None:
        frekuensi = "mingguan"
        hari = ""
        simpul_hari = akar.find(".//{*}DaysOfWeek")
        if simpul_hari is not None:
            kode = (simpul_hari.text or "").strip()
            if not kode:  # bentuk <DaysOfWeek><Friday /></DaysOfWeek>
                kode = simpul_hari[0].tag.split("}")[-1] if len(simpul_hari) else ""
            kode = kode[:3].upper()
            hari = next((n for n, k in HARI.items() if k == kode), "")
    else:
        frekuensi = "harian"
        hari = ""
    return {
        "terpasang": True,
        "aktif": aktif,
        "waktu": waktu,
        "frekuensi": frekuensi,
        "hari": hari,
        "perintah": (cari("Command") + " " + cari("Arguments")).strip(),
        "nama_tugas": NAMA_TUGAS,
    }


def _berikutnya(waktu: str, frekuensi: str, hari: str, *, sekarang: datetime | None = None) -> str:
    """Perkiraan jadwal berikutnya, dihitung lokal — XML tidak memuatnya."""
    if not waktu:
        return ""
    jam, menit = (int(bagian) for bagian in waktu.split(":"))
    kini = sekarang or datetime.now()
    calon = kini.replace(hour=jam, minute=menit, second=0, microsecond=0)
    if frekuensi == "mingguan" and hari:
        target = HARI_URUT.index(hari) + 1  # senin=1 … minggu=7, sama dengan isoweekday()
        maju = (target - kini.isoweekday()) % 7
        calon += timedelta(days=maju)
    if calon <= kini:
        calon += timedelta(days=7 if frekuensi == "mingguan" else 1)
    return calon.strftime("%Y-%m-%d %H:%M")


def _kerangka(windows: bool | None = None) -> dict:
    """Bentuk dasar keadaan tugas: belum terpasang, memakai jadwal bawaan.

    Dipakai `status()` dan `tak_terbaca()` supaya keduanya tidak pernah
    menyusun kamus ini sendiri-sendiri — kalau bentuknya berubah satu tempat,
    yang lain ikut.
    """
    return {
        "nama_tugas": NAMA_TUGAS,
        "perintah": _teks_perintah(perintah_periksa()),
        "cron": jadwal_cron(),
        "dukungan": dukungan(windows=windows),
        "terpasang": False,
        "aktif": False,
        "waktu": WAKTU_BAWAAN,
        "frekuensi": "harian",
        "hari": "",
        "berikutnya": "",
        "catatan": "",
    }


def tak_terbaca(alasan: str, *, windows: bool | None = None) -> dict:
    """Keadaan tugas bila penjadwal menolak dibaca.

    Ini bukan kegagalan aplikasi: kebijakan perusahaan, Windows berbahasa lain,
    atau penjadwal yang tidak tersedia bisa membuat `schtasks` menjawab sesuatu
    yang bukan XML. Keadaannya dikembalikan sebagai "belum terpasang" beserta
    alasannya, supaya antarmuka bisa menampilkannya apa adanya.
    """
    hasil = _kerangka(windows=windows)
    hasil["catatan"] = alasan
    return hasil


def status(*, runner=None, windows: bool | None = None, sekarang: datetime | None = None) -> dict:
    """Keadaan tugas: terpasang atau tidak, dan bagaimana jadwalnya."""
    hasil = _kerangka(windows=windows)
    if not hasil["dukungan"]["bisa"]:
        return hasil
    jalan = runner or _jalankan
    kode, keluaran = jalan(["schtasks", "/Query", "/TN", NAMA_TUGAS, "/XML"])
    if kode != 0:
        # Tugas belum ada. Pesannya bahasa apa saja; kode keluarnya yang menentu.
        LOG.info("Tugas penjadwalan belum terpasang.")
        return hasil
    hasil.update(_baca_xml(keluaran))
    hasil["berikutnya"] = _berikutnya(hasil["waktu"], hasil["frekuensi"], hasil["hari"], sekarang=sekarang)
    return hasil


# -- ubah keadaan ------------------------------------------------------------
def aktifkan(
    *,
    waktu: str = WAKTU_BAWAAN,
    frekuensi: str = "harian",
    hari: str = "",
    runner=None,
    windows: bool | None = None,
    program: str | None = None,
) -> dict:
    """Pasang atau perbarui tugas pemeriksaan otomatis.

    Masukan diperiksa lebih dahulu, baru keadaan sistem: jam yang salah adalah
    kesalahan pengguna (400), sedangkan Windows yang tidak ada adalah keadaan
    mesin (409). Urutan ini membuat pesannya tepat di kedua keadaan.
    """
    perintah = perintah_tugas(waktu=waktu, frekuensi=frekuensi, hari=hari, program=program)
    info = dukungan(windows=windows)
    if not info["bisa"]:
        raise JadwalError(info["pesan"])
    jalan = runner or _jalankan
    kode, keluaran = jalan(perintah)
    if kode != 0:
        raise JadwalError(_pesan_schtasks(keluaran))
    LOG.info("Tugas penjadwalan dipasang: %s %s", frekuensi, waktu)
    hasil = status(runner=runner, windows=windows)
    hasil["perintah_tugas"] = _teks_perintah(perintah)
    return hasil


def matikan(*, runner=None, windows: bool | None = None) -> dict:
    """Hapus tugas pemeriksaan otomatis."""
    info = dukungan(windows=windows)
    if not info["bisa"]:
        raise JadwalError(info["pesan"])
    jalan = runner or _jalankan
    kode, keluaran = jalan(["schtasks", "/Delete", "/TN", NAMA_TUGAS, "/F"])
    if kode != 0:
        raise JadwalError(_pesan_schtasks(keluaran))
    LOG.info("Tugas penjadwalan dihapus.")
    return status(runner=runner, windows=windows)


def jalankan_sekarang(*, runner=None, windows: bool | None = None) -> dict:
    """Minta penjadwal Windows menjalankan tugas itu sekarang.

    Bedanya dengan tombol “Periksa sekarang”: yang ini membuktikan rangkaian
    penjadwalnya bekerja, dari tugas tersimpan sampai aplikasi benar-benar
    dipanggil. Hasilnya muncul di daftar perubahan beberapa saat kemudian.
    """
    info = dukungan(windows=windows)
    if not info["bisa"]:
        raise JadwalError(info["pesan"])
    jalan = runner or _jalankan
    kode, keluaran = jalan(["schtasks", "/Run", "/TN", NAMA_TUGAS])
    if kode != 0:
        raise JadwalError(_pesan_schtasks(keluaran))
    LOG.info("Tugas penjadwalan dijalankan atas permintaan pengguna.")
    return status(runner=runner, windows=windows)


def _pesan_schtasks(keluaran: str) -> str:
    """Terjemahkan kegagalan schtasks menjadi satu kalimat yang bisa ditindaklanjuti."""
    baris = [b.strip() for b in keluaran.splitlines() if b.strip()]
    ringkas = baris[-1] if baris else "tanpa keterangan"
    if "Access is denied" in keluaran or "Access denied" in keluaran:
        return (
            "Windows menolak membuat tugas ini (akses ditolak). Coba jalankan aplikasi "
            f"sebagai pengguna biasa yang merupakan pemilik komputer ini. Pesan sistem: {ringkas}"
        )
    return f"Penjadwal Windows menolak permintaan. Pesan sistem: {ringkas}"


def ringkas(jadwal: dict) -> str:
    """Satu baris untuk ditampilkan di antarmuka dan catatan."""
    if not jadwal.get("terpasang"):
        return "Jadwal otomatis belum dipasang."
    if not jadwal.get("aktif"):
        return f"Tugas {jadwal['nama_tugas']} ada tetapi sedang dinonaktifkan."
    if jadwal.get("frekuensi") == "mingguan":
        pola = f"setiap {jadwal.get('hari') or '?'} pukul {jadwal['waktu']}"
    else:
        pola = f"setiap hari pukul {jadwal['waktu']}"
    tambahan = f" Berikutnya sekitar {jadwal['berikutnya']}." if jadwal.get("berikutnya") else ""
    return f"Pemeriksaan otomatis aktif: {pola}.{tambahan}"


def catat_jadwal(jadwal: dict) -> None:
    """Simpan salinan ringkas ke berkas catatan aplikasi (tanpa data pribadi)."""
    try:
        berkas = paths.data_dir() / "jadwal-radar.txt"
        berkas.write_text(
            f"{ringkas(jadwal)}\nPerintah: {jadwal.get('perintah', '')}\n",
            encoding="utf-8",
        )
    except OSError:  # pragma: no cover - catatan gagal bukan alasan menghentikan kerja
        LOG.warning("Catatan jadwal tidak bisa ditulis.")
