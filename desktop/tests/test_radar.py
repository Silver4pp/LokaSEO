"""Uji jembatan radar di aplikasi desktop: halaman, endpoint, dan keamanannya.

Yang dijaga berkas ini:

- radar dijalankan dari dalam aplikasi, memakai folder data milik pengguna;
- satu pemeriksaan pada satu waktu, berjalan di latar belakang supaya antarmuka
  tidak menggantung;
- endpoint radar hanya menerima permintaan dari halaman aplikasi sendiri;
- mode luring tidak diam-diam mengirim permintaan keluar;
- halaman radar dan halaman hentikan tidak memakai skrip sebaris, karena CSP
  aplikasi memakai `script-src 'self'`.
"""

import http.client
import json
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest import mock  # noqa: E402

from lokaseo_desktop import config, jadwal, pages, radar  # noqa: E402
from lokaseo_desktop.server import create_server  # noqa: E402


class RadarBridgeTest(unittest.TestCase):
    """Jembatan ke modul radar tanpa server HTTP."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        radar._MODUL.clear()
        self._asli_data = radar.os.environ.get("LOKARADAR_DATA")
        radar.os.environ["LOKARADAR_DATA"] = str(Path(self.tmp.name) / "radar")
        self._asli_pekerjaan = dict(radar._PEKERJAAN)
        radar._PEKERJAAN.update(
            {"id": 0, "keadaan": "belum pernah", "mulai": None, "selesai": None,
             "ringkasan": None, "hasil": None, "galat": None}
        )

    def tearDown(self):
        radar._PEKERJAAN.update(self._asli_pekerjaan)
        radar._MODUL.clear()
        if self._asli_data is None:
            radar.os.environ.pop("LOKARADAR_DATA", None)
        else:
            radar.os.environ["LOKARADAR_DATA"] = self._asli_data
        self.tmp.cleanup()

    def test_modul_radar_ditemukan(self):
        self.assertTrue(radar.tersedia())
        self.assertTrue((radar.radar_root() / "lokaradar" / "__init__.py").is_file())

    def test_folder_data_di_dalam_data_pengguna(self):
        arah = radar.data_dir()
        self.assertTrue(arah.is_dir())
        self.assertEqual(str(arah), radar.os.environ["LOKARADAR_DATA"])

    def test_status_awal_kosong_tapi_tersedia(self):
        status = radar.status()
        self.assertTrue(status["tersedia"])
        self.assertEqual(status["sasaran"], 0)
        self.assertEqual(status["perubahan"], 0)
        self.assertIn("pekerjaan", status)

    def test_tambah_dan_hapus_sasaran(self):
        hasil = radar.tambah("https://pesaing.example/harga", "Pesaing Kopi", "harga")
        daftar = radar.sasaran()
        self.assertEqual(len(daftar), 1)
        self.assertEqual(daftar[0]["label"], "Pesaing Kopi")
        self.assertEqual(daftar[0]["jenis"], "harga")
        radar.hapus(str(hasil["id"]))
        self.assertEqual(radar.sasaran(), [])

    def test_pemeriksaan_berjalan_di_latar_dan_selesai(self):
        dipanggil: list[dict] = []

        def palsu(**kwargs):
            dipanggil.append(kwargs)
            time.sleep(0.05)
            return {"diperiksa": 2, "gagal": 0, "dilewati": 0, "durasi_detik": 1.2,
                    "perubahan": 1, "sasaran": [{"label": "A", "url": "https://a.test/", "perubahan": []}]}

        asli = radar._lakukan_pemeriksaan
        radar._lakukan_pemeriksaan = palsu
        try:
            hasil = radar.mulai_periksa(max_pages=5)
            self.assertEqual(hasil["keadaan"], "berjalan")
            for _ in range(60):
                if radar.pekerjaan()["keadaan"] != "berjalan":
                    break
                time.sleep(0.05)
            selesai = radar.pekerjaan()
        finally:
            radar._lakukan_pemeriksaan = asli
        self.assertEqual(selesai["keadaan"], "selesai")
        self.assertEqual(selesai["ringkasan"]["diperiksa"], 2)
        self.assertEqual(dipanggil[0]["max_pages"], 5)
        self.assertFalse(radar.sedang_berjalan())

    def test_pemeriksaan_kedua_ditolak_saat_masih_berjalan(self):
        lepas = threading.Event()
        asli = radar._lakukan_pemeriksaan

        def lambat(**kwargs):  # noqa: ARG001
            lepas.wait(2)
            return {"diperiksa": 0, "gagal": 0, "dilewati": 0, "durasi_detik": 0, "perubahan": 0, "sasaran": []}

        radar._lakukan_pemeriksaan = lambat
        try:
            radar.mulai_periksa()
            with self.assertRaises(radar.RadarError):
                radar.mulai_periksa()
        finally:
            lepas.set()
            for _ in range(40):
                if not radar.sedang_berjalan():
                    break
                time.sleep(0.05)
            radar._lakukan_pemeriksaan = asli

    def test_kegagalan_dilaporkan_bukan_disembunyikan(self):
        asli = radar._lakukan_pemeriksaan

        def rusak(**kwargs):  # noqa: ARG001
            raise RuntimeError("jaringan mati")

        radar._lakukan_pemeriksaan = rusak
        try:
            radar.mulai_periksa()
            for _ in range(60):
                if radar.pekerjaan()["keadaan"] != "berjalan":
                    break
                time.sleep(0.05)
            hasil = radar.pekerjaan()
        finally:
            radar._lakukan_pemeriksaan = asli
        self.assertEqual(hasil["keadaan"], "gagal")
        self.assertIn("jaringan mati", hasil["galat"])

    def test_mulai_periksa_ditolak_bila_modul_tidak_ada(self):
        asli = radar.tersedia
        radar.tersedia = lambda: False
        try:
            with self.assertRaises(radar.RadarError):
                radar.mulai_periksa()
        finally:
            radar.tersedia = asli

    def test_laporan_belum_ada_mengembalikan_none(self):
        self.assertIsNone(radar.laporan_terbaru())

    def test_ringkasan_kosong_tetap_jujur(self):
        data = radar.ringkasan(hari=7)
        self.assertEqual(data["hari"], 7)
        self.assertEqual(data["sasaran"], 0)
        self.assertEqual(data["diperiksa"], 0)
        self.assertEqual(data["perubahan"], 0)
        self.assertEqual(data["penting"], [])
        self.assertEqual(data["berulang"], [])
        self.assertEqual(data["diam"], [])
        # Kunci yang dibaca antarmuka harus lengkap, atau kartunya kosong.
        for kunci in ("per_tingkat", "diam", "belum_diperiksa", "terakhir_diperiksa", "ambang_berulang"):
            self.assertIn(kunci, data)


class RadarTampilanTest(unittest.TestCase):
    """Kesalahan yang hanya muncul saat halaman benar-benar dibuka peramban."""

    def test_nama_data_contoh_ditulis_benar(self):
        # Pernah salah tulis: `window.__RADAR_DATA.info` (kurang satu garis
        # bawah) membuat cabang contoh melempar "Cannot read properties of
        # undefined" sehingga kartu pengaturan dan sasaran tidak pernah tampil.
        salah = re.findall(r"__RADAR_DATA(?!__)", pages.RADAR_JS)
        self.assertEqual(salah, [], "nama window.__RADAR_DATA__ harus lengkap")

    def test_tidak_ada_rantai_setelah_append(self):
        # `element.append(...)` mengembalikan undefined, bukan elemennya.
        # Rantai seperti `.append(x).value = ""` selalu meledak di peramban.
        rantai = [baris for baris in pages.RADAR_JS.splitlines() if re.search(r"\.append\([^)]*\)\s*\.", baris)]
        self.assertEqual(rantai, [], f"append() tidak bisa dirantai: {rantai}")

    def test_contoh_tampilan_bisa_dibuka_tanpa_jaringan(self):
        berkas = Path(__file__).resolve().parent.parent / "contoh" / "tampilan-radar.html"
        self.assertTrue(berkas.is_file(), "contoh tampilan belum dibuat")
        isi = berkas.read_text(encoding="utf-8")
        self.assertIn("window.__RADAR_DATA__ = {", isi)
        for penanda in ('src="http', "src='http", 'href="http', "href='http", "@import", "fonts.googleapis"):
            self.assertNotIn(penanda, isi, f"contoh tampilan memuat sumber luar: {penanda}")

    def test_kartu_ringkasan_ada_di_halaman(self):
        # Ringkasan ditaruh di atas "Pengaturan usaha": bila kartunya tidak
        # ada, `gambarRingkasan` melempar dan seluruh halaman gagal dimuat.
        self.assertIn('id="ringkasan"', pages.RADAR_PAGE)
        self.assertIn("Ringkasan pemantauan", pages.RADAR_PAGE)
        self.assertLess(pages.RADAR_PAGE.index('id="ringkasan"'),
                        pages.RADAR_PAGE.index("Pengaturan usaha"))

    def test_ringkasan_digambar_di_tiga_cabang(self):
        # Tiga jalur berbeda mengisi kartu yang sama: muat awal, contoh statis,
        # dan penyegaran seusai pemeriksaan. Yang terakhir mudah terlupa.
        # Dihitung dari penyebutan namanya, bukan dari tanda kurung: pemanggilan
        # lewat `muatKartu(...)` tidak memakai `gambarRingkasan(`.
        self.assertGreaterEqual(pages.RADAR_JS.count("gambarRingkasan"), 4,
                                "gambarRingkasan harus dipakai di muat awal, contoh, dan seusai periksa")
        lewat_kartu = pages.RADAR_JS.count('"/api/radar/ringkasan?hari=7", "ringkasan", gambarRingkasan')
        self.assertGreaterEqual(lewat_kartu, 2,
                                "ringkasan harus dimuat di muat awal dan seusai pemeriksaan")

    def test_kartu_dimuat_sendiri_sendiri(self):
        # Pernah: enam permintaan dirantai dalam satu `try`, sehingga penjadwal
        # Windows yang menolak dibaca mengosongkan daftar sasaran dan ringkasan.
        self.assertIn("async function muatKartu(", pages.RADAR_JS)
        self.assertIn("Promise.all([", pages.RADAR_JS)
        # Kegagalan satu kartu harus mengisi kartunya sendiri, bukan berhenti.
        self.assertIn('Gagal dimuat: " + error.message', pages.RADAR_JS)

    def test_tombol_periode_ringkasan_ada(self):
        self.assertIn("HARI_RINGKASAN", pages.RADAR_JS)
        self.assertIn("/api/radar/ringkasan?hari=", pages.RADAR_JS)

    def test_contoh_tampilan_punya_pembuat(self):
        pembuat = Path(__file__).resolve().parent.parent / "contoh" / "buat-tampilan.py"
        self.assertTrue(pembuat.is_file(), "pembuat contoh tampilan hilang")


class RadarProfilTest(unittest.TestCase):
    """Pengaturan awal LokaSEO menjadi kunci utama kerja radar."""

    PENGATURAN = {
        "version": 1,
        "activeId": "p-1",
        "projects": [
            {"id": "p-0", "name": "Proyek lain", "city": "Depok", "domain": "lain.example", "industry": "laundry"},
            {"id": "p-1", "name": "Kopi Ranah", "city": "Bogor", "domain": "kotaranah.example", "industry": "kafe-kedai"},
        ],
    }

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        radar._MODUL.clear()
        self._asli = radar.os.environ.get("LOKARADAR_DATA")
        radar.os.environ["LOKARADAR_DATA"] = str(Path(self.tmp.name) / "radar")

    def tearDown(self):
        radar._MODUL.clear()
        if self._asli is None:
            radar.os.environ.pop("LOKARADAR_DATA", None)
        else:
            radar.os.environ["LOKARADAR_DATA"] = self._asli
        self.tmp.cleanup()

    def test_daftar_jenis_usaha_lengkap(self):
        daftar = radar.daftar_jenis()
        self.assertGreaterEqual(len(daftar), 13)
        kafe = next(item for item in daftar if item["id"] == "kafe-kedai")
        self.assertEqual(kafe["min_rating"], 4.3)
        self.assertTrue(kafe["rating_penting"])
        for item in daftar:
            self.assertTrue(item["label"], item)

    def test_profil_diambil_dari_proyek_aktif(self):
        hasil = radar.simpan_profil(self.PENGATURAN)
        self.assertEqual(hasil["nama"], "Kopi Ranah")
        self.assertEqual(hasil["kota"], "Bogor")
        self.assertEqual(hasil["jenis"], "kafe-kedai")
        self.assertEqual(hasil["ambang_rating"], 4.3)
        self.assertIn("CafeOrCoffeeShop", hasil["schema"])
        self.assertIn("kedai kopi", hasil["kata_kunci"])
        self.assertIn("LokaSEO", hasil["sumber"])

    def test_profil_tersimpan_dan_dibaca_ulang(self):
        radar.simpan_profil(self.PENGATURAN)
        profil = radar.profil_usaha()
        self.assertIsNotNone(profil)
        self.assertEqual(profil["jenis"], "kafe-kedai")
        status = radar.status()
        self.assertEqual(status["profil"]["jenis_label"], "Kafe, kedai kopi, atau tempat makan kecil")

    def test_profil_manual(self):
        hasil = radar.simpan_profil(
            {"nama": "Bengkel Jaya", "jenis": "bengkel-otomotif", "kota": "Bogor", "situs": "bengkeljaya.example"}
        )
        self.assertEqual(hasil["jenis"], "bengkel-otomotif")
        self.assertEqual(hasil["nama"], "Bengkel Jaya")

    def test_jenis_asing_ditolak(self):
        with self.assertRaises(radar.MasukanTidakSah):
            radar.simpan_profil({"nama": "X", "jenis": "jual-beli-apa-saja"})

    def test_pengaturan_tanpa_proyek_ditolak(self):
        with self.assertRaises(radar.MasukanTidakSah):
            radar.simpan_profil({"version": 1, "projects": [], "activeId": ""})

    def test_jenis_kosong_diterima_karena_pengguna_baru(self):
        hasil = radar.simpan_profil({"version": 1, "activeId": "p", "projects": [{"id": "p", "name": "Baru"}]})
        self.assertEqual(hasil["jenis"], "")
        self.assertEqual(hasil["ambang_rating"], 4.0)


class RadarServerTest(unittest.TestCase):
    """Endpoint radar melalui server lokal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / "build"
        root.mkdir()
        (root / "index.html").write_text(
            "<!doctype html><html><body><h1>LokaSEO</h1></body></html>", encoding="utf-8"
        )
        radar._MODUL.clear()
        self._asli_data = radar.os.environ.get("LOKARADAR_DATA")
        radar.os.environ["LOKARADAR_DATA"] = str(Path(self.tmp.name) / "radar")
        self._asli_pekerjaan = dict(radar._PEKERJAAN)
        radar._PEKERJAAN.update(
            {"id": 0, "keadaan": "belum pernah", "mulai": None, "selesai": None,
             "ringkasan": None, "hasil": None, "galat": None}
        )
        self.server = create_server(root, "127.0.0.1", 0, offline=False)
        self.offline_server = create_server(root, "127.0.0.1", 0, offline=True)
        self.port = self.server.server_address[1]
        self.offline_port = self.offline_server.server_address[1]
        for server in (self.server, self.offline_server):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    def tearDown(self):
        for server in (self.server, self.offline_server):
            server.shutdown()
            server.server_close()
        radar._PEKERJAAN.update(self._asli_pekerjaan)
        radar._MODUL.clear()
        if self._asli_data is None:
            radar.os.environ.pop("LOKARADAR_DATA", None)
        else:
            radar.os.environ["LOKARADAR_DATA"] = self._asli_data
        self.tmp.cleanup()

    def call(self, method, path, port=None, body=None, headers=None):
        port = port or self.port
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
        payload = json.dumps(body) if body is not None else None
        connection.request(method, path, body=payload, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        hasil = (response.status, dict(response.getheaders()), data)
        connection.close()
        return hasil

    def json_headers(self, port=None, **extra):
        host = f"127.0.0.1:{port or self.port}"
        headers = {"Content-Type": "application/json", "Origin": f"http://{host}"}
        headers.update(extra)
        return headers

    # -- pembacaan -----------------------------------------------------------
    def test_info_radar(self):
        status, _, body = self.call("GET", "/api/radar/info")
        self.assertEqual(status, 200)
        isi = json.loads(body)
        self.assertTrue(isi["tersedia"])
        self.assertEqual(isi["sasaran"], 0)
        self.assertFalse(isi["luring"])

    def test_sasaran_dan_perubahan_awal_kosong(self):
        status, _, body = self.call("GET", "/api/radar/sasaran")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), [])
        status, _, body = self.call("GET", "/api/radar/perubahan?limit=5")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), [])

    def test_laporan_belum_ada_menjawab_404(self):
        status, _, body = self.call("GET", "/api/radar/laporan")
        self.assertEqual(status, 404)
        self.assertIn("Belum ada laporan", json.loads(body)["error"])

    def test_ringkasan_dilayani(self):
        status, _, body = self.call("GET", "/api/radar/ringkasan?hari=7")
        self.assertEqual(status, 200)
        isi = json.loads(body)
        self.assertEqual(isi["hari"], 7)
        for kunci in ("sasaran", "diperiksa", "perubahan", "per_tingkat", "penting", "berulang", "diam"):
            self.assertIn(kunci, isi)

    def test_ringkasan_hari_dijaga(self):
        # Angka di luar batas dikembalikan ke batas, bukan dipakai apa adanya:
        # `hari` dipakai untuk menghitung tanggal, jadi 9999 hari akan membuat
        # rentang yang tidak masuk akal.
        for kirim, harap in (("9999", 90), ("0", 1), ("-5", 1), ("abc", 7), ("", 7)):
            status, _, body = self.call("GET", f"/api/radar/ringkasan?hari={kirim}")
            self.assertEqual(status, 200, kirim)
            self.assertEqual(json.loads(body)["hari"], harap, f"hari={kirim} harus jadi {harap}")

    def test_jadwal_yang_menolak_dibaca_bukan_galat_500(self):
        # Penjadwal Windows bisa menolak dibaca (kebijakan perusahaan, Windows
        # berbahasa lain). Dulu ini menjawab 500, dan karena antarmuka merantai
        # semua permintaan dalam satu blok, seluruh halaman radar ikut kosong.
        with mock.patch.object(jadwal, "status", side_effect=jadwal.JadwalError("contoh gagal")):
            status, _, body = self.call("GET", "/api/radar/jadwal")
        self.assertEqual(status, 200)
        isi = json.loads(body)
        self.assertFalse(isi["terpasang"])
        self.assertIn("contoh gagal", isi["catatan"])

    def test_endpoint_radar_asing_ditolak_host(self):
        status, _, _ = self.call("GET", "/api/radar/info", headers={"Host": "jahat.example"})
        self.assertEqual(status, 421)

    # -- penambahan sasaran --------------------------------------------------
    def test_tambah_dari_antarmuka(self):
        status, _, body = self.call(
            "POST",
            "/api/radar/tambah",
            body={"url": "https://pesaing.example/", "label": "Pesaing", "jenis": "harga"},
            headers=self.json_headers(),
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["url"], "https://pesaing.example/")
        _, _, daftar = self.call("GET", "/api/radar/sasaran")
        self.assertEqual(len(json.loads(daftar)), 1)

    def test_tambah_lintas_asal_ditolak(self):
        status, _, body = self.call(
            "POST",
            "/api/radar/tambah",
            body={"url": "https://jahat.example/"},
            headers={"Content-Type": "application/json", "Origin": "http://jahat.example"},
        )
        self.assertEqual(status, 403)
        self.assertIn("tidak diizinkan", json.loads(body)["error"])

    def test_tambah_tanpa_origin_ditolak(self):
        status, _, _ = self.call(
            "POST", "/api/radar/tambah", body={"url": "https://a.test/"}, headers={"Content-Type": "application/json"}
        )
        self.assertEqual(status, 403)

    def test_tambah_alamat_tidak_sah_ditolak(self):
        for alamat in ("ftp://a.test/", "contoh.test/harga", "javascript:alert(1)"):
            status, _, body = self.call(
                "POST",
                "/api/radar/tambah",
                body={"url": alamat},
                headers=self.json_headers(),
            )
            self.assertEqual(status, 400, alamat)
            self.assertIn("http", json.loads(body)["error"])

    def test_tambah_jenis_tidak_dikenal_ditolak(self):
        status, _, _ = self.call(
            "POST",
            "/api/radar/tambah",
            body={"url": "https://a.test/", "jenis": "apa-saja"},
            headers=self.json_headers(),
        )
        self.assertEqual(status, 400)

    def test_hapus_sasaran(self):
        _, _, body = self.call(
            "POST",
            "/api/radar/tambah",
            body={"url": "https://a.test/", "jenis": "halaman"},
            headers=self.json_headers(),
        )
        target_id = json.loads(body)["id"]
        status, _, _ = self.call(
            "POST", "/api/radar/hapus", body={"id": target_id}, headers=self.json_headers()
        )
        self.assertEqual(status, 200)
        _, _, daftar = self.call("GET", "/api/radar/sasaran")
        self.assertEqual(json.loads(daftar), [])

    def test_hapus_tanpa_id_ditolak(self):
        status, _, _ = self.call("POST", "/api/radar/hapus", body={}, headers=self.json_headers())
        self.assertEqual(status, 400)

    # -- pemeriksaan ---------------------------------------------------------
    def test_periksa_di_latar_dan_selesai(self):
        asli = radar._lakukan_pemeriksaan
        def lambat_sebentar(**kwargs):  # noqa: ARG001
            time.sleep(0.3)
            return {
                "diperiksa": 1, "gagal": 0, "dilewati": 0, "durasi_detik": 0.4,
                "perubahan": 0, "sasaran": [],
            }

        radar._lakukan_pemeriksaan = lambat_sebentar
        try:
            status, _, body = self.call(
                "POST", "/api/radar/periksa", body={}, headers=self.json_headers()
            )
            self.assertEqual(status, 202)
            self.assertEqual(json.loads(body)["keadaan"], "berjalan")
            for _ in range(60):
                _, _, info = self.call("GET", "/api/radar/info")
                if json.loads(info)["pekerjaan"]["keadaan"] == "selesai":
                    break
                time.sleep(0.05)
            self.assertEqual(json.loads(info)["pekerjaan"]["keadaan"], "selesai")
        finally:
            radar._lakukan_pemeriksaan = asli

    def test_periksa_saat_luring_ditolak_jelas(self):
        status, _, body = self.call(
            "POST", "/api/radar/periksa", body={}, headers=self.json_headers(port=self.offline_port),
            port=self.offline_port,
        )
        self.assertEqual(status, 409)
        self.assertIn("luring", json.loads(body)["error"])

    def test_periksa_kedua_saat_sibuk_ditolak(self):
        lepas = threading.Event()
        asli = radar._lakukan_pemeriksaan

        def lambat(**kwargs):  # noqa: ARG001
            lepas.wait(2)
            return {"diperiksa": 0, "gagal": 0, "dilewati": 0, "durasi_detik": 0, "perubahan": 0, "sasaran": []}

        radar._lakukan_pemeriksaan = lambat
        try:
            self.call("POST", "/api/radar/periksa", body={}, headers=self.json_headers())
            status, _, body = self.call(
                "POST", "/api/radar/periksa", body={}, headers=self.json_headers()
            )
            self.assertEqual(status, 409)
            self.assertIn("masih berjalan", json.loads(body)["error"])
        finally:
            lepas.set()
            for _ in range(40):
                if not radar.sedang_berjalan():
                    break
                time.sleep(0.05)
            radar._lakukan_pemeriksaan = asli

    def test_periksa_lintas_asal_ditolak(self):
        status, _, _ = self.call(
            "POST", "/api/radar/periksa", body={},
            headers={"Content-Type": "application/json", "Origin": "http://jahat.example"},
        )
        self.assertEqual(status, 403)

    def test_jenis_usaha_dilayani_untuk_antarmuka(self):
        status, _, body = self.call("GET", "/api/radar/jenis")
        self.assertEqual(status, 200)
        daftar = json.loads(body)
        self.assertGreaterEqual(len(daftar), 13)
        self.assertIn("kafe-kedai", [item["id"] for item in daftar])

    def test_profil_awal_kosong(self):
        status, _, body = self.call("GET", "/api/radar/profil")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {})

    def test_simpan_pengaturan_lokaseo(self):
        pengaturan = {
            "version": 1,
            "activeId": "p-1",
            "projects": [
                {"id": "p-1", "name": "Kopi Ranah", "city": "Bogor", "domain": "kopiranah.example", "industry": "kafe-kedai"}
            ],
        }
        status, _, body = self.call(
            "POST", "/api/radar/profil", body=pengaturan, headers=self.json_headers()
        )
        self.assertEqual(status, 200)
        isi = json.loads(body)
        self.assertEqual(isi["jenis"], "kafe-kedai")
        self.assertEqual(isi["ambang_rating"], 4.3)
        _, _, info = self.call("GET", "/api/radar/info")
        self.assertEqual(json.loads(info)["profil"]["kota"], "Bogor")

    def test_simpan_pengaturan_lintas_asal_ditolak(self):
        status, _, _ = self.call(
            "POST",
            "/api/radar/profil",
            body={"nama": "X", "jenis": "kafe-kedai"},
            headers={"Content-Type": "application/json", "Origin": "http://jahat.example"},
        )
        self.assertEqual(status, 403)

    def test_jenis_asing_ditolak_400(self):
        status, _, body = self.call(
            "POST",
            "/api/radar/profil",
            body={"nama": "X", "jenis": "apa-saja"},
            headers=self.json_headers(),
        )
        self.assertEqual(status, 400)
        self.assertIn("tidak dikenal", json.loads(body)["error"])

    def test_body_bukan_objek_ditolak(self):
        status, _, _ = self.call(
            "POST", "/api/radar/profil", body=[1, 2, 3], headers=self.json_headers()
        )
        self.assertEqual(status, 400)

    def test_endpoint_radar_tidak_dikenal_404(self):
        status, _, _ = self.call("GET", "/api/radar/apa-pun")
        self.assertEqual(status, 404)
        status, _, _ = self.call("POST", "/api/radar/apa-pun", body={}, headers=self.json_headers())
        self.assertEqual(status, 404)


class RadarPeriksaTerjadwalTest(unittest.TestCase):
    """Mode `--radar-periksa` yang dipanggil Windows Task Scheduler."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        radar._MODUL.clear()
        self._asli = radar.os.environ.get("LOKARADAR_DATA")
        radar.os.environ["LOKARADAR_DATA"] = str(Path(self.tmp.name) / "radar")

    def tearDown(self):
        radar._MODUL.clear()
        if self._asli is None:
            radar.os.environ.pop("LOKARADAR_DATA", None)
        else:
            radar.os.environ["LOKARADAR_DATA"] = self._asli
        self.tmp.cleanup()

    def test_tanpa_sasaran_selesai_dengan_pesan_jujur(self):
        from lokaseo_desktop import app

        tertangkap: list[str] = []
        with mock.patch.object(app, "cetak", tertangkap.append):
            kode = app.periksa_radar()
        self.assertEqual(kode, 0)
        self.assertIn("Belum ada sasaran", tertangkap[0])

    def test_ringkasan_berisi_angka_pemeriksaan(self):
        with mock.patch.object(
            radar,
            "periksa_langsung",
            lambda **_: {"diperiksa": 3, "gagal": 0, "dilewati": 1, "perubahan": 2, "durasi_detik": 4.2},
        ):
            kode, pesan = radar.periksa_dari_baris_perintah()
        self.assertEqual(kode, 0)
        self.assertIn("3 halaman diperiksa", pesan)
        self.assertIn("2 perubahan tercatat", pesan)
        self.assertIn("4.20 detik", pesan)

    def test_gagal_sebagian_memberi_kode_keluar_1(self):
        with mock.patch.object(
            radar,
            "periksa_langsung",
            lambda **_: {"diperiksa": 1, "gagal": 1, "dilewati": 0, "perubahan": 0, "durasi_detik": 1.0},
        ):
            kode, pesan = radar.periksa_dari_baris_perintah()
        self.assertEqual(kode, 1)
        self.assertIn("Buka halaman radar", pesan)

    def test_radar_tidak_tersedia_tidak_menjatuhkan_penjadwal(self):
        with mock.patch.object(radar, "periksa_langsung", side_effect=radar.RadarError("tidak ada")):
            kode, pesan = radar.periksa_dari_baris_perintah()
        self.assertEqual(kode, 1)
        self.assertIn("tidak bisa dijalankan", pesan)

    def test_galat_tak_terduga_pun_jadi_kode_keluar(self):
        with mock.patch.object(radar, "periksa_langsung", side_effect=RuntimeError("bom")):
            kode, pesan = radar.periksa_dari_baris_perintah()
        self.assertEqual(kode, 1)
        self.assertIn("bom", pesan)

    def test_mode_ini_keluar_sebelum_server_menyala(self):
        from lokaseo_desktop import app

        with mock.patch.object(radar, "periksa_dari_baris_perintah", lambda **_: (0, "selesai")), mock.patch.object(
            app, "cetak"
        ), mock.patch.object(app, "run") as jalan_server:
            kode = app.main(["--radar-periksa"])
        self.assertEqual(kode, 0)
        jalan_server.assert_not_called()


class RadarPerambanTest(unittest.TestCase):
    """Peramban untuk halaman ber-JavaScript: keadaan, dan uji yang dibuktikan."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / "build"
        root.mkdir()
        (root / "index.html").write_text(
            "<!doctype html><html><body><h1>LokaSEO</h1></body></html>", encoding="utf-8"
        )
        radar._MODUL.clear()
        self._asli_data = radar.os.environ.get("LOKARADAR_DATA")
        radar.os.environ["LOKARADAR_DATA"] = str(Path(self.tmp.name) / "radar")
        self._asli_pekerjaan = dict(radar._PEKERJAAN)
        radar._PEKERJAAN.update(
            {"id": 0, "keadaan": "belum pernah", "mulai": None, "selesai": None,
             "ringkasan": None, "hasil": None, "galat": None}
        )
        self.server = create_server(root, "127.0.0.1", 0, offline=False)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        radar._PEKERJAAN.update(self._asli_pekerjaan)
        radar._MODUL.clear()
        if self._asli_data is None:
            radar.os.environ.pop("LOKARADAR_DATA", None)
        else:
            radar.os.environ["LOKARADAR_DATA"] = self._asli_data
        self.tmp.cleanup()

    def call(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        connection.request(method, path, json.dumps(body) if body is not None else None, headers or {})
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, data

    def headers(self, **extra):
        hasil = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"}
        hasil.update(extra)
        return hasil

    def test_keadaan_peramban_dilaporkan(self):
        status, body = self.call("GET", "/api/radar/peramban")
        self.assertEqual(status, 200)
        isi = json.loads(body)
        self.assertIn("tersedia", isi)
        self.assertIn("mode_render", isi)
        self.assertIn(isi["mode_render"], ("auto", "tidak"))
        # Bawaannya "auto" hanya bila peramban memang ada.
        self.assertEqual(isi["mode_render"] == "auto", bool(isi["tersedia"]))

    def test_chip_rendering_tidak_bertentangan_dengan_kartu(self):
        """Bila kartu berkata peramban siap, chip tidak boleh berkata "permintaan biasa"."""
        _, body = self.call("GET", "/api/radar/info")
        isi = json.loads(body)
        if isi["peramban_info"]["tersedia"]:
            self.assertEqual(isi["peramban"], "siap", "kartu menyatakan siap, chip harus sejalan")
        else:
            self.assertNotEqual(isi["peramban"], "siap")

    def test_info_radar_ikut_membawa_peramban(self):
        _, body = self.call("GET", "/api/radar/info")
        isi = json.loads(body)
        self.assertIn("peramban_info", isi)
        self.assertIn("tersedia", isi["peramban_info"])

    def test_tanpa_peramban_uji_dijawab_jelas(self):
        asli = radar._modul()["peramban"].ketersediaan
        radar._modul()["peramban"].ketersediaan = lambda refresh=False: {
            "tersedia": False, "pesan": radar._modul()["peramban"].PETUNJUK_TANPA_PERAMBAN
        }
        try:
            status, body = self.call("POST", "/api/radar/peramban", body={}, headers=self.headers())
        finally:
            radar._modul()["peramban"].ketersediaan = asli
        self.assertEqual(status, 400)
        self.assertIn("Edge", json.loads(body)["error"])

    def test_uji_ditolak_saat_pemeriksaan_sedang_berjalan(self):
        radar._PEKERJAAN.update({"keadaan": "berjalan"})
        status, body = self.call("POST", "/api/radar/peramban", body={}, headers=self.headers())
        self.assertEqual(status, 409)
        self.assertIn("sedang berjalan", json.loads(body)["error"])

    def test_lintas_asal_ditolak(self):
        status, _ = self.call(
            "POST",
            "/api/radar/peramban",
            body={},
            headers={"Content-Type": "application/json", "Origin": "http://jahat.example"},
        )
        self.assertEqual(status, 403)

    def test_uji_render_sungguhan_lewat_endpoint(self):
        """Bukti penuh: server membuka satu peramban dan mengembalikan hasilnya."""
        if not radar._modul()["peramban"].tersedia():
            self.skipTest("Tidak ada peramban di komputer ini.")
        status, body = self.call("POST", "/api/radar/peramban", body={}, headers=self.headers())
        self.assertEqual(status, 200, body)
        hasil = json.loads(body)
        self.assertTrue(hasil["berhasil"], hasil["pesan"])
        self.assertIn("Rendering berjalan", hasil["pesan"])
        self.assertIn("peramban", hasil)

    def test_ulang_paksa_pencarian_peramban(self):
        """Tombol "Periksa ulang" harus benar-benar mencari dari awal."""
        tangkap = {}

        def peramban_palsu(*, refresh=False):
            tangkap["refresh"] = refresh
            return {"tersedia": False, "refresh": refresh}

        with mock.patch.object(radar, "peramban", peramban_palsu):
            status, body = self.call("GET", "/api/radar/peramban")
            self.assertEqual(status, 200)
            self.assertFalse(json.loads(body)["refresh"], "permintaan biasa tidak perlu mencari ulang")
            status, body = self.call("GET", "/api/radar/peramban?ulang=1")
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)["refresh"], "?ulang=1 harus memaksa pencarian ulang")
        self.assertEqual(tangkap["refresh"], True)

    def test_jalur_peramban_yang_ditunjuk_diteruskan(self):
        """Kolom "Pakai berkas ini" harus sampai ke radar, bukan terbuang di server."""
        tangkap = {}

        def uji_palsu(jalur=None):
            tangkap["jalur"] = jalur
            return {"berhasil": False, "pesan": "cuma uji"}

        with mock.patch.object(radar, "uji_peramban", uji_palsu):
            status, _ = self.call("GET", "/api/radar/peramban")
            self.assertEqual(status, 200)
            status, _ = self.call(
                "POST",
                "/api/radar/peramban",
                body={"jalur": "C:\\Edge\\msedge.exe"},
                headers=self.headers(),
            )
            self.assertEqual(status, 200)
            self.assertEqual(tangkap["jalur"], "C:\\Edge\\msedge.exe")
            status, _ = self.call("POST", "/api/radar/peramban", body={}, headers=self.headers())
            self.assertEqual(status, 200)
            self.assertIsNone(tangkap["jalur"], "tanpa jalur, radar memakai hasil pencariannya sendiri")

    def test_kartu_peramban_tidak_membiarkan_tombol_mati_tanpa_keterangan(self):
        """Tombol yang pudar harus disertai alasan dan jalan keluar."""
        for bagian in ("Periksa ulang", "Pakai berkas ini", "Yang sudah dicari", "data.alasan ||"):
            self.assertIn(bagian, pages.RADAR_JS, f"bagian antarmuka hilang: {bagian}")
        self.assertIn("/api/radar/peramban?ulang=1", pages.RADAR_JS)

    def test_mode_render_bawaan_auto_bila_ada_peramban(self):
        modul = radar._modul()
        if modul["peramban"].tersedia():
            self.assertEqual(radar._mode_render_bawaan(modul), "auto")
        with mock.patch.object(modul["peramban"], "tersedia", lambda: False), mock.patch.object(
            modul["fetch"], "dynamic_available", lambda: False
        ):
            self.assertEqual(radar._mode_render_bawaan(modul), "tidak")


class RadarSasaranBerkasTest(unittest.TestCase):
    """Ekspor dan impor daftar sasaran: bisa dipindah, tidak menghapus apa pun."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / "build"
        root.mkdir()
        (root / "index.html").write_text(
            "<!doctype html><html><body><h1>LokaSEO</h1></body></html>", encoding="utf-8"
        )
        radar._MODUL.clear()
        self._asli_data = radar.os.environ.get("LOKARADAR_DATA")
        radar.os.environ["LOKARADAR_DATA"] = str(Path(self.tmp.name) / "radar")
        self._asli_pekerjaan = dict(radar._PEKERJAAN)
        radar._PEKERJAAN.update(
            {"id": 0, "keadaan": "belum pernah", "mulai": None, "selesai": None,
             "ringkasan": None, "hasil": None, "galat": None}
        )
        self.server = create_server(root, "127.0.0.1", 0, offline=False)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        radar._PEKERJAAN.update(self._asli_pekerjaan)
        radar._MODUL.clear()
        if self._asli_data is None:
            radar.os.environ.pop("LOKARADAR_DATA", None)
        else:
            radar.os.environ["LOKARADAR_DATA"] = self._asli_data
        self.tmp.cleanup()

    def call(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        connection.request(method, path, json.dumps(body) if body is not None else None, headers or {})
        response = connection.getresponse()
        data = response.read()
        hasil = (response.status, dict(response.getheaders()), data)
        connection.close()
        return hasil

    def headers(self, **extra):
        hasil = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"}
        hasil.update(extra)
        return hasil

    def tambah(self, url, label="", jenis="halaman"):
        status, _, body = self.call("POST", "/api/radar/tambah", {"url": url, "label": label, "jenis": jenis}, self.headers())
        self.assertEqual(status, 200, body)
        return json.loads(body)

    # -- ekspor -------------------------------------------------------------
    def test_unduh_daftar_sasaran_berupa_berkas(self):
        self.tambah("https://pesaing-a.example/menu", "Pesaing A", "harga")
        self.tambah("https://pesaing-b.example/", "Pesaing B")
        status, kepala, body = self.call("GET", "/api/radar/sasaran/ekspor")
        self.assertEqual(status, 200)
        self.assertIn("attachment", kepala.get("Content-Disposition", ""))
        self.assertIn("sasaran-radar-", kepala.get("Content-Disposition", ""))
        self.assertTrue(kepala["Content-Disposition"].endswith('.json"'))
        isi = json.loads(body)
        self.assertEqual(isi["format"], "lokaradar.sasaran.v1")
        self.assertEqual(isi["jumlah"], 2)
        self.assertTrue(isi["nama_berkas"].endswith(".json"))

    def test_unduh_daftar_kosong_tetap_berkas_sah(self):
        status, _, body = self.call("GET", "/api/radar/sasaran/ekspor")
        self.assertEqual(status, 200)
        isi = json.loads(body)
        self.assertEqual(isi["jumlah"], 0)
        self.assertEqual(isi["sasaran"], [])

    # -- impor --------------------------------------------------------------
    def test_impor_menambah_dan_melaporkan_hasilnya(self):
        self.tambah("https://pesaing-a.example/", "Pesaing A")
        teks = "https://pesaing-a.example/\nhttps://pesaing-baru.example/\nbukan-url\n"
        status, _, body = self.call(
            "POST", "/api/radar/sasaran/impor", {"teks": teks, "nama": "daftar.txt"}, self.headers()
        )
        self.assertEqual(status, 200, body)
        hasil = json.loads(body)
        self.assertEqual(hasil["ditambahkan"], 1)
        self.assertEqual(hasil["sudah_ada"], 1)
        self.assertEqual(len(hasil["ditolak"]), 1)
        self.assertEqual(hasil["nama_berkas"], "daftar.txt")
        self.assertTrue(any("Belum ada halaman yang dihubungi" in b for b in hasil["ringkasan"]))
        # Daftar lama tetap ada: impor menggabung, bukan mengganti.
        _, _, sesudah = self.call("GET", "/api/radar/sasaran")
        url = [item["url"] for item in json.loads(sesudah)]
        self.assertIn("https://pesaing-a.example/", url)
        self.assertIn("https://pesaing-baru.example/", url)

    def test_impor_berkas_bukan_daftar_dijawab_400(self):
        laporan = json.dumps({"perubahan": []})
        status, _, body = self.call(
            "POST", "/api/radar/sasaran/impor", {"teks": laporan}, self.headers()
        )
        self.assertEqual(status, 400)
        self.assertIn("sasaran", json.loads(body)["error"])

    def test_impor_tanpa_isi_berkas_dijawab_400(self):
        status, _, body = self.call("POST", "/api/radar/sasaran/impor", {}, self.headers())
        self.assertEqual(status, 400)
        self.assertIn("teks", json.loads(body)["error"])

    def test_impor_lintas_asal_ditolak(self):
        status, _, _ = self.call(
            "POST",
            "/api/radar/sasaran/impor",
            {"teks": "https://x.example/"},
            {"Content-Type": "application/json", "Origin": "http://jahat.example"},
        )
        self.assertEqual(status, 403)

    def test_impor_menghormati_batas_jumlah_sasaran(self):
        self.tambah("https://pesaing-a.example/", "Pesaing A")
        self.tambah("https://pesaing-b.example/", "Pesaing B")
        with mock.patch.object(config, "RADAR_MAX_TARGETS", 2):
            status, _, body = self.call(
                "POST", "/api/radar/sasaran/impor", {"teks": "https://kelebihan.example/\n"}, self.headers()
            )
        self.assertEqual(status, 200, body)
        hasil = json.loads(body)
        self.assertEqual(hasil["ditambahkan"], 0)
        self.assertEqual(hasil["tertunda"], 1)
        self.assertTrue(any("tertunda" in b or "batas" in b for b in hasil["ringkasan"]))

    def test_impor_berkas_besar_diterima_badan_lebih_longgar(self):
        """Daftar 400 sasaran jauh melewati batas body biasa, dan tetap harus masuk."""
        baris = "\n".join(f"https://pesaing-{i:03d}.example/halaman" for i in range(400))
        self.assertGreater(len(baris), config.RADAR_MAX_BODY_BYTES)
        with mock.patch.object(config, "RADAR_MAX_TARGETS", 500):
            status, _, body = self.call(
                "POST", "/api/radar/sasaran/impor", {"teks": baris, "nama": "besar.txt"}, self.headers()
            )
        self.assertEqual(status, 200, body[:200])
        self.assertEqual(json.loads(body)["ditambahkan"], 400)

    def test_halaman_memuat_kartu_berkas_sasaran(self):
        _, _, halaman = self.call("GET", "/radar")
        teks = halaman.decode("utf-8")
        self.assertIn("Unduh daftar sasaran", teks)
        self.assertIn("Impor daftar sasaran", teks)
        self.assertIn('id="berkas-sasaran"', teks)

    def test_skrip_berkas_sasaran_memakai_endpoint_yang_benar(self):
        _, _, skrip = self.call("GET", "/radar.js")
        teks = skrip.decode("utf-8")
        self.assertIn("/api/radar/sasaran/ekspor", teks)
        self.assertIn("/api/radar/sasaran/impor", teks)
        self.assertIn("folder Unduhan", teks)
        self.assertIn("tulisPesanSasaran", teks)

    def test_kartu_menjelaskan_janji_impor(self):
        _, _, halaman = self.call("GET", "/radar")
        teks = halaman.decode("utf-8")
        self.assertIn("menggabung", teks)
        self.assertIn("tidak pernah menghapus", teks)
        self.assertIn("tidak menghubungi\n      situs mana pun", teks)


class RadarJadwalTest(unittest.TestCase):
    """Pemeriksaan otomatis: tampil di antarmuka, dipasang hanya bila diminta."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / "build"
        root.mkdir()
        (root / "index.html").write_text(
            "<!doctype html><html><body><h1>LokaSEO</h1></body></html>", encoding="utf-8"
        )
        radar._MODUL.clear()
        self._asli_data = radar.os.environ.get("LOKARADAR_DATA")
        radar.os.environ["LOKARADAR_DATA"] = str(Path(self.tmp.name) / "radar")
        self.server = create_server(root, "127.0.0.1", 0, offline=False)
        self.offline_server = create_server(root, "127.0.0.1", 0, offline=True)
        self.port = self.server.server_address[1]
        self.offline_port = self.offline_server.server_address[1]
        for server in (self.server, self.offline_server):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    def tearDown(self):
        for server in (self.server, self.offline_server):
            server.shutdown()
            server.server_close()
        radar._MODUL.clear()
        if self._asli_data is None:
            radar.os.environ.pop("LOKARADAR_DATA", None)
        else:
            radar.os.environ["LOKARADAR_DATA"] = self._asli_data
        self.tmp.cleanup()

    def call(self, method, path, port=None, body=None, headers=None):
        port = port or self.port
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
        payload = json.dumps(body) if body is not None else None
        connection.request(method, path, payload, headers or {})
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, data

    def headers(self, port=None, **extra):
        host = f"127.0.0.1:{port or self.port}"
        hasil = {"Content-Type": "application/json", "Origin": f"http://{host}"}
        hasil.update(extra)
        return hasil

    # -- keadaan ------------------------------------------------------------
    def test_status_jadwal_membawa_dukungan_perintah_dan_cron(self):
        status, body = self.call("GET", "/api/radar/jadwal", 0 and None or self.port)
        self.assertEqual(status, 200)
        isi = json.loads(body)
        self.assertIn("dukungan", isi)
        self.assertIn("--radar-periksa", isi["perintah"])
        self.assertIn("--radar-periksa", isi["cron"])
        self.assertEqual(isi["nama_tugas"], jadwal.NAMA_TUGAS)

    def test_belum_terpasang_saat_belum_dipasang(self):
        _, body = self.call("GET", "/api/radar/jadwal")
        self.assertFalse(json.loads(body)["terpasang"])

    # -- penolakan ----------------------------------------------------------
    def test_jam_salah_ditolak_400(self):
        status, body = self.call(
            "POST", "/api/radar/jadwal", body={"aksi": "aktifkan", "waktu": "25:00"}, headers=self.headers()
        )
        self.assertEqual(status, 400)
        self.assertIn("23:59", json.loads(body)["error"])

    def test_frekuensi_per_jam_ditolak_400(self):
        status, body = self.call(
            "POST",
            "/api/radar/jadwal",
            body={"aksi": "aktifkan", "waktu": "07:00", "frekuensi": "per-jam"},
            headers=self.headers(),
        )
        self.assertEqual(status, 400)
        self.assertIn("sekali sehari", json.loads(body)["error"])

    def test_aksi_asing_ditolak_400(self):
        status, body = self.call(
            "POST", "/api/radar/jadwal", body={"aksi": "pasang-diam-diam"}, headers=self.headers()
        )
        self.assertEqual(status, 400)
        self.assertIn("aktifkan", json.loads(body)["error"])

    def test_lintas_asal_ditolak_403(self):
        status, _ = self.call(
            "POST",
            "/api/radar/jadwal",
            body={"aksi": "matikan"},
            headers={"Content-Type": "application/json", "Origin": "http://jahat.example"},
        )
        self.assertEqual(status, 403)

    def test_mode_luring_menolak_jadwal(self):
        status, body = self.call(
            "POST",
            "/api/radar/jadwal",
            port=self.offline_port,
            body={"aksi": "aktifkan", "waktu": "07:00"},
            headers=self.headers(port=self.offline_port),
        )
        self.assertEqual(status, 409)
        self.assertIn("luring", json.loads(body)["error"])

    def test_di_luar_windows_memberi_pesan_jujur_bukan_gagal_senyap(self):
        if radar.os.sys.platform.startswith("win"):  # pragma: no cover - hanya di Windows
            self.skipTest("Uji ini untuk mesin non-Windows.")
        status, body = self.call(
            "POST", "/api/radar/jadwal", body={"aksi": "aktifkan", "waktu": "07:00"}, headers=self.headers()
        )
        self.assertEqual(status, 409)
        self.assertIn("Windows", json.loads(body)["error"])

    # -- jalur berhasil (Windows ditiru) ------------------------------------
    def test_aktifkan_mendaftarkan_tugas_lalu_membacanya(self):
        perintah: list[list[str]] = []
        xml = """<?xml version="1.0"?>
        <Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
          <Triggers><CalendarTrigger><StartBoundary>2026-10-14T07:00:00</StartBoundary>
          <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger></Triggers>
          <Settings><Enabled>true</Enabled></Settings>
          <Actions><Exec><Command>C:\\LokaSEO.exe</Command><Arguments>--radar-periksa</Arguments></Exec></Actions>
        </Task>"""

        def palsu(keping):
            perintah.append(list(keping))
            return (0, xml) if "/Query" in keping else (0, "SUCCESS")

        with mock.patch.object(jadwal, "_jalankan", palsu), mock.patch.object(
            jadwal, "dukungan", lambda **_: {"bisa": True, "platform": "win32", "pesan": "siap"}
        ):
            status, body = self.call(
                "POST",
                "/api/radar/jadwal",
                body={"aksi": "aktifkan", "waktu": "07:00", "frekuensi": "harian"},
                headers=self.headers(),
            )
            self.assertEqual(status, 200, body)
            isi = json.loads(body)
            self.assertTrue(isi["terpasang"])
            self.assertTrue(isi["aktif"])
            self.assertEqual(isi["waktu"], "07:00")
            self.assertIn("--radar-periksa", isi["perintah"])
            _, kedua = self.call("GET", "/api/radar/jadwal")
            self.assertTrue(json.loads(kedua)["terpasang"])

        self.assertEqual(perintah[0][1], "/Create")
        self.assertEqual(perintah[1][1], "/Query")
        self.assertIn("/ST", perintah[0])

    def test_matikan_menghapus_tugas(self):
        perintah: list[list[str]] = []

        def palsu(keping):
            perintah.append(list(keping))
            return (0, "SUCCESS") if "/Delete" in keping else (1, "tidak ada")

        with mock.patch.object(jadwal, "_jalankan", palsu), mock.patch.object(
            jadwal, "dukungan", lambda **_: {"bisa": True, "platform": "win32", "pesan": "siap"}
        ):
            status, body = self.call(
                "POST", "/api/radar/jadwal", body={"aksi": "matikan"}, headers=self.headers()
            )
        self.assertEqual(status, 200, body)
        self.assertFalse(json.loads(body)["terpasang"])
        self.assertEqual(perintah[0][1], "/Delete")

    def test_jalankan_meminta_penjadwal_menjalankan_tugas(self):
        perintah: list[list[str]] = []

        def palsu(keping):
            perintah.append(list(keping))
            return (0, "SUCCESS") if "/Run" in keping else (1, "tidak ada")

        with mock.patch.object(jadwal, "_jalankan", palsu), mock.patch.object(
            jadwal, "dukungan", lambda **_: {"bisa": True, "platform": "win32", "pesan": "siap"}
        ):
            status, _ = self.call(
                "POST", "/api/radar/jadwal", body={"aksi": "jalankan"}, headers=self.headers()
            )
        self.assertEqual(status, 200)
        self.assertEqual(perintah[0][1], "/Run")


class RadarPageTest(unittest.TestCase):
    """Halaman radar dan penyisipan tautannya."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "index.html").write_text(
            "<!doctype html><html><body><h1>LokaSEO</h1></body></html>", encoding="utf-8"
        )
        self.root = root
        radar._MODUL.clear()
        self._asli_data = radar.os.environ.get("LOKARADAR_DATA")
        radar.os.environ["LOKARADAR_DATA"] = str(Path(self.tmp.name) / "data-radar")
        self.server = create_server(root, "127.0.0.1", 0, offline=False)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        radar._MODUL.clear()
        if self._asli_data is None:
            radar.os.environ.pop("LOKARADAR_DATA", None)
        else:
            radar.os.environ["LOKARADAR_DATA"] = self._asli_data
        self.tmp.cleanup()

    def call(self, path, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request("GET", path, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        hasil = (response.status, dict(response.getheaders()), data)
        connection.close()
        return hasil

    def test_halaman_radar_tanpa_skrip_sebaris(self):
        status, headers, body = self.call("/radar")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        teks = body.decode("utf-8")
        self.assertNotIn("<script>", teks, "skrip sebaris diblokir CSP")
        self.assertIn('/radar.js', teks)
        self.assertIn("Radar pemantauan", teks)
        # Tanpa sumber daya luar: tidak ada skrip/gaya/gambar dari alamat lain.
        # (Contoh alamat di dalam placeholder formulir bukan sumber daya.)
        for penanda in ('src="http', "src='http", 'href="http', "href='http", "@import", "fonts.googleapis"):
            self.assertNotIn(penanda, teks)

    def test_skrip_radar_dilayani_dari_asal_yang_sama(self):
        status, headers, body = self.call("/radar.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["Content-Type"])
        teks = body.decode("utf-8")
        self.assertIn("/api/radar/info", teks)
        self.assertIn("Periksa sekarang", self.call("/radar")[2].decode("utf-8"))

    def test_skrip_radar_tidak_menulis_html_tanpa_escape(self):
        """Data dari laporan harus di-escape sebelum diformat jadi markdown."""
        teks = self.call("/radar.js")[2].decode("utf-8")
        self.assertIn("function aman", teks)
        self.assertIn(".replace(/&/g", teks)
        self.assertIn(".replace(/</g", teks)

    def test_index_mendapat_tautan_radar(self):
        status, _, body = self.call("/")
        self.assertEqual(status, 200)
        teks = body.decode("utf-8")
        self.assertIn('/radar-tautan.js', teks)
        self.assertEqual(teks.count("/radar-tautan.js"), 1, "tautan tidak boleh dobel")

    def test_tautan_tidak_disuntik_bila_radar_tidak_ada(self):
        asli = radar.tersedia
        radar.tersedia = lambda: False
        try:
            teks = self.call("/")[2].decode("utf-8")
        finally:
            radar.tersedia = asli
        self.assertNotIn("/radar-tautan.js", teks)

    def test_halaman_memuat_kartu_pengaturan_usaha(self):
        teks = self.call("/radar")[2].decode("utf-8")
        self.assertIn("Pengaturan usaha", teks)
        self.assertIn('id="profil"', teks)

    def test_skrip_membaca_pengaturan_lokaseo(self):
        teks = self.call("/radar.js")[2].decode("utf-8")
        self.assertIn("lokaseo.workspace.v1", teks)
        self.assertIn("/api/radar/profil", teks)
        self.assertIn("Ambil pengaturan dari proyek LokaSEO", teks)

    def test_halaman_memuat_kartu_jadwal(self):
        teks = self.call("/radar")[2].decode("utf-8")
        self.assertIn("Pemeriksaan otomatis", teks)
        self.assertIn('id="jadwal"', teks)

    def test_skrip_jadwal_memakai_endpoint_yang_benar(self):
        teks = self.call("/radar.js")[2].decode("utf-8")
        self.assertIn("/api/radar/jadwal", teks)
        for aksi in ("aktifkan", "matikan", "jalankan"):
            self.assertIn(f'aksi: "{aksi}"', teks)
        self.assertIn("sekali sehari", teks)
        self.assertIn("Perintah yang didaftarkan", teks)

    def test_halaman_memuat_kartu_peramban(self):
        teks = self.call("/radar")[2].decode("utf-8")
        self.assertIn("Peramban untuk halaman ber-JavaScript", teks)
        self.assertIn('id="peramban"', teks)

    def test_skrip_peramban_memakai_endpoint_yang_benar(self):
        teks = self.call("/radar.js")[2].decode("utf-8")
        self.assertIn("/api/radar/peramban", teks)
        self.assertIn("Uji rendering", teks)
        self.assertIn("Tidak ada yang ", teks)
        self.assertIn("mode “auto”", teks)

    def test_skrip_tautan_tidak_menyentuh_iframe(self):
        teks = self.call("/radar-tautan.js")[2].decode("utf-8")
        self.assertIn("window.top !== window.self", teks)


if __name__ == "__main__":
    unittest.main()
