"""Uji laporan kesiapan: apa yang diperiksa, apa yang tidak boleh ikut tertulis."""

import http.client
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

DESKTOP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESKTOP))

from lokaseo_desktop import kesiapan, paths, radar  # noqa: E402
from lokaseo_desktop.server import create_server  # noqa: E402


class KesiapanButirTest(unittest.TestCase):
    """Butir-butir laporan, diuji satu per satu tanpa server."""

    def test_laporan_lengkap_dan_hitungannya_cocok(self):
        laporan = kesiapan.periksa(alamat="http://127.0.0.1:1234")
        nama = [butir["nama"] for butir in laporan["butir"]]
        for diharapkan in ("Versi aplikasi", "Sistem", "Folder data", "Peramban", "Penjadwal otomatis"):
            self.assertIn(diharapkan, nama)
        self.assertIn("Alamat antarmuka", nama)
        for butir in laporan["butir"]:
            self.assertIn(butir["keadaan"], (kesiapan.LULUS, kesiapan.PERHATIAN, kesiapan.GAGAL))
            self.assertTrue(butir["nilai"], f"{butir['nama']} harus punya nilai")
        ringkasan = laporan["ringkasan"]
        self.assertEqual(ringkasan[kesiapan.LULUS] + ringkasan[kesiapan.PERHATIAN] + ringkasan[kesiapan.GAGAL], len(laporan["butir"]))

    def test_teks_memuat_versi_hasil_dan_catatan(self):
        teks = kesiapan.periksa()["teks"]
        self.assertTrue(teks.startswith("LAPORAN KESIAPAN LOKASEO"))
        self.assertIn("Versi      : LokaSEO", teks)
        self.assertIn("lulus |", teks)
        self.assertIn("CATATAN", teks)
        self.assertIn("tidak memuat kunci API", teks)
        self.assertTrue(teks.endswith("\n"))

    def test_saran_muncul_hanya_untuk_butir_yang_perlu(self):
        laporan = {
            "butir": [
                {"nama": "A", "keadaan": kesiapan.LULUS, "nilai": "baik", "saran": "jangan tampil"},
                {"nama": "B", "keadaan": kesiapan.PERHATIAN, "nilai": "kosong", "saran": "isi dulu"},
                {"nama": "C", "keadaan": kesiapan.GAGAL, "nilai": "rusak", "saran": "perbaiki ini"},
            ],
            "ringkasan": {kesiapan.LULUS: 1, kesiapan.PERHATIAN: 1, kesiapan.GAGAL: 1},
        }
        teks = kesiapan.teks(laporan)
        self.assertIn("YANG PERLU DILAKUKAN", teks)
        self.assertIn("B: isi dulu", teks)
        self.assertIn("C: perbaiki ini", teks)
        self.assertNotIn("jangan tampil", teks)

    def test_teks_tanpa_butir_gagal_bilang_begitu(self):
        laporan = {
            "butir": [{"nama": "A", "keadaan": kesiapan.LULUS, "nilai": "baik", "saran": ""}],
            "ringkasan": {kesiapan.LULUS: 1, kesiapan.PERHATIAN: 0, kesiapan.GAGAL: 0},
        }
        teks = kesiapan.teks(laporan)
        self.assertIn("Tidak ada butir yang gagal.", teks)
        self.assertNotIn("YANG PERLU DILAKUKAN", teks)

    def test_kunci_places_tidak_pernah_ikut_tertulis(self):
        with mock.patch.dict(os.environ, {"LOKARADAR_PLACES_KEY": "AIza-rahasia-sekali"}):
            teks = kesiapan.periksa()["teks"]
        self.assertNotIn("AIza-rahasia-sekali", teks)

    def test_peramban_tidak_ada_diberi_petunjuk_edge(self):
        with mock.patch.object(radar, "peramban", lambda: {"tersedia": False, "pesan": "tidak ada"}):
            butir = next(b for b in kesiapan.periksa()["butir"] if b["nama"] == "Peramban")
        self.assertEqual(butir["keadaan"], kesiapan.PERHATIAN)
        self.assertIn("Edge", butir["saran"])

    def test_alasan_peramban_ikut_ke_laporan_kesiapan(self):
        """Laporan tidak boleh cuma berkata "tidak ada" — alasannya harus ikut."""
        alasan = (
            "Tidak ada berkas peramban di 34 lokasi yang diperiksa. Pasang Microsoft "
            "Edge atau Google Chrome, lalu klik \u201cPeriksa ulang\u201d."
        )
        with mock.patch.object(radar, "peramban", lambda: {"tersedia": False, "pesan": "x", "alasan": alasan}):
            butir = next(b for b in kesiapan.periksa()["butir"] if b["nama"] == "Peramban")
        self.assertEqual(butir["keadaan"], kesiapan.PERHATIAN)
        self.assertIn("34 lokasi", butir["saran"])
        self.assertIn("Periksa ulang", butir["saran"])
        # Konsol Windows (cp1252) merusak tanda kutip elok; laporan harus ASCII.
        for larangan in ("\u201c", "\u201d", "\u2014"):
            self.assertNotIn(larangan, butir["saran"])

    def test_peramban_ada_dilaporkan_dengan_versinya(self):
        data = {"tersedia": True, "nama": "Microsoft Edge", "versi": "141.0.1", "sumber": "terpasang di sistem"}
        with mock.patch.object(radar, "peramban", lambda: data):
            butir = next(b for b in kesiapan.periksa()["butir"] if b["nama"] == "Peramban")
        self.assertEqual(butir["keadaan"], kesiapan.LULUS)
        self.assertIn("Microsoft Edge (141.0.1)", butir["nilai"])

    def test_radar_tidak_bisa_dimuat_bukan_alasan_laporan_gagal(self):
        def meledak():
            raise radar.RadarError("Modul radar tidak ditemukan.")

        with mock.patch.object(radar, "tersedia", lambda: False), mock.patch.object(radar, "_modul", meledak):
            laporan = kesiapan.periksa()
        self.assertTrue(laporan["butir"], "laporan harus tetap punya butir")
        modul = next(b for b in laporan["butir"] if b["nama"] == "Modul radar")
        self.assertEqual(modul["keadaan"], kesiapan.PERHATIAN)
        self.assertIn("LOKARADAR_ROOT", modul["saran"])
        # Butir versi tetap lulus walau radar tidak ada.
        versi = next(b for b in laporan["butir"] if b["nama"] == "Versi aplikasi")
        self.assertEqual(versi["keadaan"], kesiapan.LULUS)
        self.assertNotIn("LokaRadar", versi["nilai"])

    def test_penjadwal_tidak_tersedia_menyarankan_cron(self):
        data = {
            "dukungan": {"bisa": False, "pesan": "hanya di Windows"},
            "terpasang": False,
            "aktif": False,
            "cron": "0 7 * * * /usr/bin/python3 /x/run.py --radar-periksa",
        }
        with mock.patch.object(kesiapan.jadwal, "status", lambda: data):
            butir = next(b for b in kesiapan.periksa()["butir"] if b["nama"] == "Penjadwal otomatis")
        self.assertEqual(butir["keadaan"], kesiapan.PERHATIAN)
        self.assertIn("cron", butir["saran"])

    def test_penjadwal_aktif_dilaporkan_jamnya(self):
        data = {
            "dukungan": {"bisa": True, "pesan": ""},
            "terpasang": True,
            "aktif": True,
            "waktu": "07:00",
            "frekuensi": "mingguan",
            "hari": "Rabu",
        }
        with mock.patch.object(kesiapan.jadwal, "status", lambda: data):
            butir = next(b for b in kesiapan.periksa()["butir"] if b["nama"] == "Penjadwal otomatis")
        self.assertEqual(butir["keadaan"], kesiapan.LULUS)
        self.assertIn("mingguan pukul 07:00 (Rabu)", butir["nilai"])

    def test_folder_data_yang_tidak_bisa_ditulis_ditandai_gagal(self):
        with tempfile.TemporaryDirectory() as nama:
            terkunci = Path(nama) / "terkunci"
            terkunci.mkdir()
            terkunci.chmod(stat.S_IRUSR | stat.S_IXUSR)  # hanya baca
            try:
                with mock.patch.object(paths, "data_dir", lambda: terkunci):
                    butir = kesiapan._butir_folder_data()  # noqa: SLF001 - butir diuji langsung
                self.assertEqual(butir["keadaan"], kesiapan.GAGAL)
                self.assertIn("tidak bisa menulis", butir["nilai"])
            finally:
                terkunci.chmod(stat.S_IRWXU)

    def test_laporan_bebas_karakter_yang_rusak_di_konsol_windows(self):
        """Konsol Windows memakai code page sendiri; laporan harus tetap utuh."""
        teks = kesiapan.periksa()["teks"]
        aneh = sorted({k for k in teks if ord(k) > 127})
        self.assertEqual(aneh, [], f"laporan harus ASCII, ditemukan: {aneh}")

    def test_waktu_memakai_nama_bulan_indonesia(self):
        waktu, zona = kesiapan._teks_waktu()  # noqa: SLF001
        bulan = waktu.split()[1]
        self.assertIn(bulan, kesiapan.BULAN)
        self.assertTrue(zona)


class KesiapanEndpointTest(unittest.TestCase):
    """Rute HTTP-nya: harus jalan bahkan saat radar sedang bermasalah."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / "build"
        root.mkdir()
        (root / "index.html").write_text("<!doctype html><html><body>LokaSEO</body></html>", encoding="utf-8")
        self._asli_data = os.environ.get("LOKA_DATA_DIR")
        os.environ["LOKA_DATA_DIR"] = str(Path(self.tmp.name) / "data")
        self.server = create_server(root, "127.0.0.1", 0, offline=False)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        if self._asli_data is None:
            os.environ.pop("LOKA_DATA_DIR", None)
        else:
            os.environ["LOKA_DATA_DIR"] = self._asli_data
        self.tmp.cleanup()

    def call(self, path: str):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        connection.request("GET", path)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, data

    def test_endpoint_mengembalikan_laporan(self):
        status, body = self.call("/api/kesiapan")
        self.assertEqual(status, 200)
        isi = json.loads(body)
        self.assertIn("teks", isi)
        self.assertIn("butir", isi)
        self.assertIn("ringkasan", isi)
        self.assertIn("LAPORAN KESIAPAN", isi["teks"])

    def test_endpoint_tetap_jalan_saat_radar_gagal(self):
        def meledak():
            raise radar.RadarError("Modul radar tidak ditemukan.")

        with mock.patch.object(radar, "tersedia", lambda: False), mock.patch.object(radar, "_modul", meledak):
            status, body = self.call("/api/kesiapan")
        self.assertEqual(status, 200, "laporan kesiapan tidak boleh ikut mati saat radar gagal")
        isi = json.loads(body)
        butir = next(b for b in isi["butir"] if b["nama"] == "Modul radar")
        self.assertEqual(butir["keadaan"], kesiapan.PERHATIAN)

    def test_halaman_dan_skrip_memuat_kartu_kesiapan(self):
        _, halaman = self.call("/radar")
        teks = halaman.decode("utf-8")
        self.assertIn("Kesiapan aplikasi di komputer ini", teks)
        self.assertIn('id="periksa-kesiapan"', teks)
        _, skrip = self.call("/radar.js")
        js = skrip.decode("utf-8")
        self.assertIn("/api/kesiapan", js)
        self.assertIn("Salin laporan", js)
        self.assertIn("gambarKesiapan", js)

    def test_galat_satu_butir_tidak_menjatuhkan_seluruh_laporan(self):
        with mock.patch.object(kesiapan, "_butir_peramban", side_effect=RuntimeError("peramban meledak")):
            status, body = self.call("/api/kesiapan")
        self.assertEqual(status, 200)
        isi = json.loads(body)
        butir = next(b for b in isi["butir"] if b["nama"] == "Peramban")
        self.assertEqual(butir["keadaan"], kesiapan.GAGAL)
        self.assertIn("peramban meledak", butir["nilai"])


class KesiapanBarisPerintahTest(unittest.TestCase):
    def test_mode_kesiapan_mencetak_dan_menyimpan_laporan(self):
        with tempfile.TemporaryDirectory() as nama:
            env = dict(os.environ)
            env["LOKA_DATA_DIR"] = nama
            env["LOKARADAR_ROOT"] = str(Path(DESKTOP).parent / "radar")
            hasil = subprocess.run(
                [sys.executable, str(DESKTOP / "run.py"), "--kesiapan"],
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
                check=False,
            )
            self.assertIn("LAPORAN KESIAPAN", hasil.stdout)
            self.assertIn(f"Laporan juga disimpan di: {Path(nama) / 'laporan-kesiapan.txt'}", hasil.stdout)
            self.assertEqual(hasil.returncode, 0, hasil.stdout + hasil.stderr)
            tersimpan = (Path(nama) / "laporan-kesiapan.txt").read_text(encoding="utf-8")
            self.assertEqual(tersimpan.strip(), hasil.stdout.split("Laporan juga disimpan")[0].strip())


if __name__ == "__main__":
    unittest.main()
