"""Uji penjadwalan pemeriksaan otomatis.

Yang dijaga berkas ini:

- perintah yang didaftarkan ke Windows Task Scheduler benar, termasuk jalur
  program yang mengandung spasi dan pilihan `LokaSEO.exe` tanpa konsol;
- masukan dari antarmuka divalidasi: jam, frekuensi, dan hari;
- hasil `schtasks` dibaca lewat XML sehingga tidak bergantung bahasa Windows;
- kegagalan penjadwal menjadi pesan yang bisa ditindaklanjuti, bukan galat mentah;
- di luar Windows, radar menjawab terus terang dan memberi baris cron.

Tidak ada `schtasks` sungguhan yang dipanggil di sini: seluruhnya lewat
`PenjadwalPalsu`, jadi pengujian berjalan di komputer mana pun dan tanpa jaringan.
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaseo_desktop import jadwal  # noqa: E402

XML_HARIAN = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Author>Pengguna</Author></RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-10-14T07:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Settings><Enabled>true</Enabled></Settings>
  <Actions Context="Author">
    <Exec>
      <Command>C:\\Program Files\\LokaSEO\\LokaSEO.exe</Command>
      <Arguments>--radar-periksa</Arguments>
    </Exec>
  </Actions>
</Task>
"""

XML_MINGGUAN = XML_HARIAN.replace(
    "<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>",
    "<ScheduleByWeek><WeeksInterval>1</WeeksInterval><DaysOfWeek>Friday</DaysOfWeek></ScheduleByWeek>",
).replace("2026-10-14T07:00:00", "2026-10-16T19:30:00")

XML_NONAKTIF = XML_HARIAN.replace(
    "<Settings><Enabled>true</Enabled></Settings>",
    "<Settings><Enabled>false</Enabled></Settings>",
)

BALASAN_ADA = (0, XML_HARIAN)
BALASAN_TIDAK_ADA = (1, "ERROR: The system cannot find the file specified.")


class PenjadwalPalsu:
    """Pengganti `schtasks`: mencatat perintah dan menjawab dari naskah."""

    def __init__(self, **balasan):
        self.balasan = balasan
        self.perintah: list[list[str]] = []

    def __call__(self, perintah: list[str]) -> tuple[int, str]:
        self.perintah.append(list(perintah))
        for penanda, jawab in self.balasan.items():
            if penanda in perintah:
                return jawab
        return (0, "")

    @property
    def terakhir(self) -> list[str]:
        return self.perintah[-1] if self.perintah else []


class PerintahTest(unittest.TestCase):
    """Perintah yang didaftarkan harus tepat sampai tanda kutipnya."""

    def test_perintah_periksa_dari_source(self):
        keping = jadwal.perintah_periksa()
        self.assertEqual(keping[-1], "--radar-periksa")
        self.assertTrue(any(bagian.endswith("run.py") for bagian in keping), keping)

    def test_lebih_memilih_lokaexe_tanpa_konsol(self):
        with tempfile.TemporaryDirectory() as folder:
            konsol = Path(folder) / "LokaSEO-console.exe"
            konsol.write_bytes(b"")
            (Path(folder) / "LokaSEO.exe").write_bytes(b"")
            with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(
                sys, "executable", str(konsol)
            ):
                self.assertEqual(jadwal.program_terbaik(), str(Path(folder) / "LokaSEO.exe"))

    def test_kembali_ke_versi_konsol_bila_tanpa_jendela_tidak_ada(self):
        with tempfile.TemporaryDirectory() as folder:
            konsol = Path(folder) / "LokaSEO-console.exe"
            konsol.write_bytes(b"")
            with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(
                sys, "executable", str(konsol)
            ):
                self.assertEqual(jadwal.program_terbaik(), str(konsol))

    def test_perintah_tugas_harian(self):
        perintah = jadwal.perintah_tugas(waktu="07:00", frekuensi="harian", program="C:\\X\\LokaSEO.exe")
        self.assertEqual(perintah[0:2], ["schtasks", "/Create"])
        self.assertIn("/F", perintah)
        self.assertIn(jadwal.NAMA_TUGAS, perintah)
        self.assertEqual(perintah[perintah.index("/SC") + 1], "DAILY")
        self.assertEqual(perintah[perintah.index("/ST") + 1], "07:00")
        self.assertNotIn("/D", perintah)

    def test_perintah_tugas_mingguan(self):
        perintah = jadwal.perintah_tugas(
            waktu="19:30", frekuensi="mingguan", hari="jumat", program="C:\\X\\LokaSEO.exe"
        )
        self.assertEqual(perintah[perintah.index("/SC") + 1], "WEEKLY")
        self.assertEqual(perintah[perintah.index("/D") + 1], "FRI")
        self.assertEqual(perintah[perintah.index("/ST") + 1], "19:30")

    def test_aksi_dikutip_hanya_di_sekitar_jalur_berpasi(self):
        # Salah satu bug yang pernah lolos sampai uji peramban: seluruh baris
        # dikurung tanda kutip, sehingga penjadwal mencari berkas bernama
        # `"C:\Program Files\...\LokaSEO.exe" --radar-periksa`.
        perintah = jadwal.perintah_tugas(program="C:\\Program Files\\LokaSEO\\LokaSEO.exe")
        aksi = perintah[perintah.index("/TR") + 1]
        self.assertEqual(aksi, '"C:\\Program Files\\LokaSEO\\LokaSEO.exe" --radar-periksa')

    def test_aksi_tanpa_spasi_tidak_dikutip(self):
        perintah = jadwal.perintah_tugas(program="C:\\X\\LokaSEO.exe")
        self.assertEqual(perintah[perintah.index("/TR") + 1], "C:\\X\\LokaSEO.exe --radar-periksa")

    def test_waktu_dinormalkan_dua_digit(self):
        perintah = jadwal.perintah_tugas(waktu="7:05", program="x.exe")
        self.assertEqual(perintah[perintah.index("/ST") + 1], "07:05")


class MasukanTest(unittest.TestCase):
    """Batas yang menjaga sopan santun dan mencegah masukan aneh."""

    def test_jam_aneh_ditolak(self):
        for buruk in ("25:00", "07:60", "pagi", "", "07.00", "07:00:00", "7"):
            with self.subTest(buruk=buruk):
                with self.assertRaises(jadwal.MasukanJadwalTidakSah):
                    jadwal.perintah_tugas(waktu=buruk, program="x.exe")

    def test_frekuensi_lebih_sering_dari_harian_ditolak(self):
        with self.assertRaises(jadwal.MasukanJadwalTidakSah) as tangkap:
            jadwal.perintah_tugas(waktu="07:00", frekuensi="per-jam", program="x.exe")
        self.assertIn("sekali sehari", str(tangkap.exception))

    def test_mingguan_wajib_menyebut_hari(self):
        with self.assertRaises(jadwal.MasukanJadwalTidakSah) as tangkap:
            jadwal.perintah_tugas(waktu="07:00", frekuensi="mingguan", hari="", program="x.exe")
        self.assertIn("hari", str(tangkap.exception).lower())

    def test_hari_asing_ditolak(self):
        with self.assertRaises(jadwal.MasukanJadwalTidakSah):
            jadwal.perintah_tugas(waktu="07:00", frekuensi="mingguan", hari="kemarin", program="x.exe")

    def test_cron_harian_dan_mingguan(self):
        harian = jadwal.jadwal_cron("07:30")
        self.assertTrue(harian.startswith("30 7 * * * "), harian)
        self.assertIn("--radar-periksa", harian)
        mingguan = jadwal.jadwal_cron("07:30", frekuensi="mingguan", hari="minggu")
        self.assertTrue(mingguan.startswith("30 7 * * 0 "), mingguan)


class StatusTest(unittest.TestCase):
    """Bacaan keadaan tugas, apa pun bahasa Windows-nya."""

    def test_belum_terpasang(self):
        palsu = PenjadwalPalsu(**{"/Query": BALASAN_TIDAK_ADA})
        hasil = jadwal.status(runner=palsu, windows=True)
        self.assertFalse(hasil["terpasang"])
        self.assertFalse(hasil["aktif"])
        self.assertEqual(hasil["waktu"], jadwal.WAKTU_BAWAAN)
        self.assertEqual(palsu.terakhir[:3], ["schtasks", "/Query", "/TN"])
        self.assertIn("/XML", palsu.terakhir)

    def test_terpasang_dibaca_dari_xml(self):
        palsu = PenjadwalPalsu(**{"/Query": BALASAN_ADA})
        hasil = jadwal.status(runner=palsu, windows=True, sekarang=datetime(2026, 10, 14, 6, 0))
        self.assertTrue(hasil["terpasang"])
        self.assertTrue(hasil["aktif"])
        self.assertEqual(hasil["waktu"], "07:00")
        self.assertEqual(hasil["frekuensi"], "harian")
        self.assertEqual(hasil["berikutnya"], "2026-10-14 07:00")
        self.assertIn("--radar-periksa", hasil["perintah"])

    def test_mingguan_membaca_nama_hari(self):
        palsu = PenjadwalPalsu(**{"/Query": (0, XML_MINGGUAN)})
        hasil = jadwal.status(runner=palsu, windows=True, sekarang=datetime(2026, 10, 14, 6, 0))
        self.assertEqual(hasil["frekuensi"], "mingguan")
        self.assertEqual(hasil["hari"], "jumat")
        self.assertEqual(hasil["waktu"], "19:30")
        self.assertEqual(hasil["berikutnya"], "2026-10-16 19:30")

    def test_tugas_tetapi_dinonaktifkan(self):
        palsu = PenjadwalPalsu(**{"/Query": (0, XML_NONAKTIF)})
        hasil = jadwal.status(runner=palsu, windows=True)
        self.assertTrue(hasil["terpasang"])
        self.assertFalse(hasil["aktif"])

    def test_xml_rusak_menghasilkan_pesan_jelas(self):
        palsu = PenjadwalPalsu(**{"/Query": (0, "bukan xml")})
        with self.assertRaises(jadwal.JadwalError):
            jadwal.status(runner=palsu, windows=True)

    def test_status_selalu_membawa_perintah_dan_cron(self):
        palsu = PenjadwalPalsu(**{"/Query": BALASAN_TIDAK_ADA})
        hasil = jadwal.status(runner=palsu, windows=True)
        self.assertIn("--radar-periksa", hasil["perintah"])
        self.assertIn("--radar-periksa", hasil["cron"])

    def test_deteksi_sungguhan_sesuai_mesin_ini(self):
        """Tanpa argumen, jawabannya harus benar untuk mesin yang menjalankan uji."""
        import shutil

        hasil = jadwal.dukungan()
        seharusnya = sys.platform.startswith("win") and shutil.which("schtasks") is not None
        self.assertEqual(hasil["bisa"], seharusnya)
        if not seharusnya:
            self.assertTrue(hasil["pesan"])

    def test_di_luar_windows_tidak_memanggil_schtasks(self):
        palsu = PenjadwalPalsu()
        hasil = jadwal.status(runner=palsu, windows=False)
        self.assertFalse(hasil["dukungan"]["bisa"])
        self.assertEqual(palsu.perintah, [], "schtasks tidak boleh dipanggil di luar Windows")
        self.assertIn("cron", hasil["dukungan"]["pesan"].lower())
        self.assertIn("--radar-periksa", hasil["cron"])


class BerikutnyaTest(unittest.TestCase):
    """Perkiraan waktu berikutnya dihitung sendiri, karena XML tidak memuatnya."""

    def test_harian_belum_lewat_dan_sudah_lewat(self):
        rabu_pagi = datetime(2026, 10, 14, 6, 0)
        rabu_siang = datetime(2026, 10, 14, 9, 0)
        self.assertEqual(jadwal._berikutnya("07:00", "harian", "", sekarang=rabu_pagi), "2026-10-14 07:00")
        self.assertEqual(jadwal._berikutnya("07:00", "harian", "", sekarang=rabu_siang), "2026-10-15 07:00")

    def test_mingguan_maju_ke_hari_yang_benar(self):
        rabu = datetime(2026, 10, 14, 6, 0)  # 14 Okt 2026 jatuh pada hari Rabu
        self.assertEqual(jadwal._berikutnya("07:00", "mingguan", "jumat", sekarang=rabu), "2026-10-16 07:00")
        self.assertEqual(jadwal._berikutnya("07:00", "mingguan", "rabu", sekarang=rabu), "2026-10-14 07:00")
        self.assertEqual(jadwal._berikutnya("07:00", "mingguan", "selasa", sekarang=rabu), "2026-10-20 07:00")

    def test_senin_ke_minggu_tidak_tertukar(self):
        sabtu = datetime(2026, 10, 17, 6, 0)
        self.assertEqual(jadwal._berikutnya("07:00", "mingguan", "minggu", sekarang=sabtu), "2026-10-18 07:00")
        self.assertEqual(jadwal._berikutnya("07:00", "mingguan", "senin", sekarang=sabtu), "2026-10-19 07:00")


class UbahTest(unittest.TestCase):
    """Memasang, mematikan, dan menjalankan tugas — semuanya atas perintah pengguna."""

    def test_aktifkan_mengirim_create_lalu_membaca_bukti(self):
        palsu = PenjadwalPalsu(**{"/Create": (0, "SUCCESS"), "/Query": BALASAN_ADA})
        hasil = jadwal.aktifkan(
            waktu="07:00", frekuensi="harian", runner=palsu, windows=True, program="C:\\X\\LokaSEO.exe"
        )
        self.assertTrue(hasil["terpasang"])
        self.assertEqual(palsu.perintah[0][1], "/Create")
        self.assertEqual(palsu.perintah[1][1], "/Query")
        self.assertIn("/Create", hasil["perintah_tugas"])
        self.assertIn("--radar-periksa", hasil["perintah_tugas"])

    def test_aktifkan_menolak_di_luar_windows(self):
        with self.assertRaises(jadwal.JadwalError) as tangkap:
            jadwal.aktifkan(waktu="07:00", runner=PenjadwalPalsu(), windows=False)
        self.assertIn("Windows", str(tangkap.exception))

    def test_aktifkan_tidak_memanggil_create_bila_masukan_salah(self):
        palsu = PenjadwalPalsu()
        with self.assertRaises(jadwal.MasukanJadwalTidakSah):
            jadwal.aktifkan(waktu="jam tujuh", runner=palsu, windows=True)
        self.assertEqual(palsu.perintah, [], "perintah tidak boleh dikirim sebelum masukan sah")

    def test_akses_ditolak_diterjemahkan(self):
        palsu = PenjadwalPalsu(**{"/Create": (1, "ERROR: Access is denied.")})
        with self.assertRaises(jadwal.JadwalError) as tangkap:
            jadwal.aktifkan(waktu="07:00", runner=palsu, windows=True)
        pesan = str(tangkap.exception)
        self.assertIn("akses ditolak", pesan.lower())
        self.assertIn("Access is denied", pesan)

    def test_matikan_mengirim_delete(self):
        palsu = PenjadwalPalsu(**{"/Delete": (0, "SUCCESS"), "/Query": BALASAN_TIDAK_ADA})
        hasil = jadwal.matikan(runner=palsu, windows=True)
        self.assertFalse(hasil["terpasang"])
        self.assertEqual(palsu.perintah[0][1], "/Delete")
        self.assertIn("/F", palsu.perintah[0])

    def test_matikan_melaporkan_kegagalan(self):
        palsu = PenjadwalPalsu(**{"/Delete": (1, "ERROR: Akses ditolak.")})
        with self.assertRaises(jadwal.JadwalError):
            jadwal.matikan(runner=palsu, windows=True)

    def test_jalankan_sekarang_mengirim_run(self):
        palsu = PenjadwalPalsu(**{"/Run": (0, "SUCCESS"), "/Query": BALASAN_ADA})
        hasil = jadwal.jalankan_sekarang(runner=palsu, windows=True)
        self.assertEqual(palsu.perintah[0][1], "/Run")
        self.assertTrue(hasil["terpasang"])

    def test_jalankan_sekarang_tanpa_tugas_memberi_pesan(self):
        palsu = PenjadwalPalsu(**{"/Run": (1, "ERROR: The system cannot find the file specified.")})
        with self.assertRaises(jadwal.JadwalError) as tangkap:
            jadwal.jalankan_sekarang(runner=palsu, windows=True)
        self.assertIn("menolak permintaan", str(tangkap.exception))


class RingkasTest(unittest.TestCase):
    """Kalimat status yang dibaca pengguna."""

    def test_belum_dipasang(self):
        teks = jadwal.ringkas({"terpasang": False})
        self.assertIn("belum dipasang", teks.lower())

    def test_harian(self):
        teks = jadwal.ringkas(
            {"terpasang": True, "aktif": True, "waktu": "07:00", "frekuensi": "harian", "berikutnya": "2026-10-15 07:00"}
        )
        self.assertIn("setiap hari pukul 07:00", teks)
        self.assertIn("2026-10-15 07:00", teks)

    def test_mingguan(self):
        teks = jadwal.ringkas(
            {"terpasang": True, "aktif": True, "waktu": "19:30", "frekuensi": "mingguan", "hari": "jumat"}
        )
        self.assertIn("setiap jumat pukul 19:30", teks)

    def test_dinonaktifkan(self):
        teks = jadwal.ringkas({"terpasang": True, "aktif": False, "nama_tugas": jadwal.NAMA_TUGAS})
        self.assertIn("dinonaktifkan", teks.lower())

    def test_catat_jadwal_menulis_berkas(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.dict(os.environ, {"LOKA_DATA_DIR": folder}):
                jadwal.catat_jadwal(
                    {
                        "terpasang": True,
                        "aktif": True,
                        "waktu": "07:00",
                        "frekuensi": "harian",
                        "perintah": "x --radar-periksa",
                    }
                )
            isi = (Path(folder) / "jadwal-radar.txt").read_text(encoding="utf-8")
        self.assertIn("setiap hari pukul 07:00", isi)
        self.assertIn("--radar-periksa", isi)


if __name__ == "__main__":
    unittest.main()
