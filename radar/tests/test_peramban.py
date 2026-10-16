"""Uji peramban lokal: memakai Edge/Chrome yang sudah ada tanpa unduhan.

Yang dijaga berkas ini:

- peramban yang tidak bisa dijalankan **tidak** dianggap siap (Chromium tanpa
  pustaka sistem tetap ada di cakram, dan pernah membuat radar mengaku siap);
- protokol soket ke peramban (WebSocket) dibaca benar, termasuk pesan besar dan
  bingkai terpotong — isi halaman bisa ratusan kilobita;
- identitas tetap jujur: User-Agent `LokaRadar`, bahasa Indonesia, tanpa Referer
  palsu, dan gambar/font tidak diunduh supaya situs orang tidak dibebani;
- hasil render masuk ke radar sebagai potret biasa, dan halaman yang gagal
  dilaporkan apa adanya, bukan disimpan sebagai halaman kosong yang "berhasil".

Pengujian yang perlu peramban sungguhan dilewati sendiri bila peramban tidak ada
di komputer ini (mis. di mesin pengembangan tanpa Chrome).
"""

import json
import os
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar import config, fetch, peramban  # noqa: E402

ADA_PERAMBAN = peramban.tersedia()
alasan_tanpa_peramban = "Peramban (Edge/Chrome/Chromium) tidak ada di komputer ini."


# ---------------------------------------------------------------------------
# Situs tiruan untuk pengujian yang butuh render sungguhan
# ---------------------------------------------------------------------------
HALAMAN_SPA = b"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<title>Klinik Gigi Sehat</title>
<meta name="description" content="Klinik gigi di Bogor.">
<link rel="stylesheet" href="/gaya.css"></head>
<body><div id="__next"></div><img src="/hero.png" alt=""><script src="/app.js"></script></body></html>"""

APLIKASI_JS = b"""document.getElementById('__next').innerHTML =
 '<h1>Klinik Gigi Sehat</h1><p>Layanan: perawatan saluran akar, pembersihan karang gigi.</p>' +
 '<div id="tabel-harga">Harga mulai Rp 350.000</div>';"""


class SitusTiruan:
    """Server HTTP kecil yang mencatat setiap permintaan yang masuk."""

    def __init__(self) -> None:
        import http.server
        import socketserver

        self.catatan: list[dict] = []
        luar = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - nama bawaan http.server
                luar.catatan.append(
                    {
                        "jalur": self.path,
                        "ua": self.headers.get("User-Agent", ""),
                        "bahasa": self.headers.get("Accept-Language", ""),
                        "referer": self.headers.get("Referer", ""),
                    }
                )
                isi = {"/": HALAMAN_SPA, "/gaya.css": b"body{}", "/app.js": APLIKASI_JS}
                if self.path == "/robots.txt":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"User-agent: *\nDisallow: /rahasia\n")
                    return
                if self.path not in isi:
                    self.send_response(404)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"<html><body><h1>Tidak ada</h1></body></html>")
                    return
                tipe = "text/html; charset=utf-8"
                if self.path.endswith(".css"):
                    tipe = "text/css"
                elif self.path.endswith(".js"):
                    tipe = "application/javascript"
                self.send_response(200)
                self.send_header("Content-Type", tipe)
                self.end_headers()
                self.wfile.write(isi[self.path])

            def log_message(self, *args):  # senyap
                return

        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.utas = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.utas.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def jalur(self) -> list[str]:
        return [baris["jalur"] for baris in self.catatan]

    def tutup(self) -> None:
        self.server.shutdown()
        self.server.server_close()


# ---------------------------------------------------------------------------
# Bagian yang bisa diuji tanpa peramban
# ---------------------------------------------------------------------------
class PencarianPerambanTest(unittest.TestCase):
    """Menemukan peramban: lewat variabel lingkungan, lalu yang terpasang."""

    def test_variabel_lingkungan_dipakai_lebih_dulu(self):
        with tempfile.TemporaryDirectory() as folder:
            palsu = Path(folder) / "msedge"
            palsu.write_text("#!/bin/sh\necho 'Microsoft Edge 999.0.0'\n", encoding="utf-8")
            palsu.chmod(0o755)
            with mock.patch.dict(os.environ, {peramban.BROWSER_ENV: str(palsu)}), mock.patch.object(
                peramban, "kandidat", lambda: [Path("/usr/bin/google-chrome")]
            ):
                self.assertEqual(peramban.cari(), palsu)

    def test_berkas_yang_tidak_bisa_dijalankan_dilewati(self):
        """Chromium tanpa pustaka sistem tetap ada di cakram — jangan dianggap siap."""
        with tempfile.TemporaryDirectory() as folder:
            rusak = Path(folder) / "chrome"
            rusak.write_text("#!/bin/sh\necho 'error while loading shared libraries: libnspr4.so'\n", encoding="utf-8")
            rusak.chmod(0o755)
            # Kandidat sistem dikosongkan supaya hasilnya tidak bergantung pada
            # peramban yang kebetulan ada di mesin yang menjalankan uji.
            with mock.patch.dict(os.environ, {peramban.BROWSER_ENV: str(rusak)}), mock.patch.object(
                peramban, "kandidat", lambda: []
            ):
                self.assertIsNone(peramban.cari())
                # Tanpa penyaringan, berkas itu akan dipakai dan gagal di setiap render.
                self.assertEqual(peramban.cari(uji_jalan=False), rusak)

    def test_penunjuk_yang_tidak_ada_diabaikan(self):
        with mock.patch.dict(os.environ, {peramban.BROWSER_ENV: "/tidak/ada/peramban"}), mock.patch.object(
            peramban, "kandidat", lambda: []
        ):
            self.assertIsNone(peramban.cari())
        # Tanpa pengosongan kandidat, penunjuk yang salah tidak boleh menghalangi
        # peramban yang benar-benar terpasang di komputer ini.
        with mock.patch.dict(os.environ, {peramban.BROWSER_ENV: "/tidak/ada/peramban"}):
            self.assertNotEqual(str(peramban.cari() or ""), "/tidak/ada/peramban")

    def test_kandidat_windows_memuat_edge_dan_chrome(self):
        with mock.patch.dict(
            os.environ,
            {
                "LOCALAPPDATA": r"C:\Users\Anda\AppData\Local",
                "ProgramFiles": r"C:\Program Files",
                "ProgramFiles(x86)": r"C:\Program Files (x86)",
            },
            clear=False,
        ):
            daftar = [str(p).replace("\\", "/") for p in peramban._kandidat_windows()]
        self.assertTrue(any(p.endswith("Microsoft/Edge/Application/msedge.exe") for p in daftar), daftar)
        self.assertTrue(any(p.endswith("Google/Chrome/Application/chrome.exe") for p in daftar), daftar)
        self.assertTrue(any("LOCALAPPDATA" in p or "AppData" in p for p in daftar))

    def test_nama_peramban_dibaca_manusia(self):
        self.assertEqual(peramban.nama_peramban(Path("/x/msedge.exe")), "Microsoft Edge")
        self.assertEqual(peramban.nama_peramban(Path("/x/chrome.exe")), "Google Chrome")
        self.assertEqual(peramban.nama_peramban(Path("/x/chromium")), "Chromium")

    def test_keluaran_versi_harus_seperti_nomor_versi(self):
        self.assertTrue(peramban._keluaran_seperti_versi("Microsoft Edge 120.0.2210.91"))
        self.assertTrue(peramban._keluaran_seperti_versi("Google Chrome 156.0.8078.4"))
        self.assertFalse(peramban._keluaran_seperti_versi(""))
        self.assertFalse(
            peramban._keluaran_seperti_versi(
                "chrome: error while loading shared libraries: libnspr4.so: cannot open shared object file"
            )
        )
        self.assertFalse(peramban._keluaran_seperti_versi("bash: chrome: command not found"))
        self.assertFalse(peramban._keluaran_seperti_versi("/bin/sh: 1: chrome: Permission denied"))

    def test_bahasa_dikirim_sebagai_daftar_bukan_nilai_berkualitas(self):
        # Bila nilai berkualitas dikirim apa adanya, Chromium menyusun ulang dan
        # hasilnya rusak: id-ID,id;q=0.9;q=0.9,en;q=0.5;q=0.8
        self.assertEqual(peramban._bahasa_untuk_peramban("id-ID,id;q=0.9,en;q=0.5"), "id-ID,id,en")
        self.assertEqual(peramban._bahasa_untuk_peramban(""), "id-ID,id,en")
        self.assertEqual(peramban._bahasa_untuk_peramban("en-US,en;q=0.9"), "en-US,en")

    def test_ketersediaan_jujur_saat_tidak_ada_peramban(self):
        with mock.patch.object(peramban, "cari", lambda *a, **k: None):
            peramban._KETERSEDIAAN = None
            info = peramban.ketersediaan()
        self.assertFalse(info["tersedia"])
        self.assertIn("Edge", info["pesan"])
        self.assertIn("Chrome", info["pesan"])
        self.assertIn("tidak ditemukan", peramban.ringkas().lower())
        peramban._KETERSEDIAAN = None


class JejakPencarianTest(unittest.TestCase):
    """Tidak ada peramban harus bisa dijelaskan, bukan cuma diumumkan.

    Di Windows 11 yang memakai Edge bawaan, tombol "Uji rendering" pernah mati
    tanpa keterangan. Yang lebih menyulitkan lagi: keluaran galat Chromium
    (`[1015/084855:WARNING:…]`) ikut dibaca sebagai bagian dari nomor versi,
    sehingga peramban yang sehat bisa terbaca "rusak". Dua hal itu dijaga di
    sini: jejak pencarian yang bisa dilaporkan, dan pembacaan versi yang tidak
    genting.
    """

    def setUp(self):
        self._kandidat_asli = peramban.kandidat
        peramban.VERSI_TERTINGGAL.clear()
        peramban._KETERSEDIAAN = None
        self.addCleanup(self._pulihkan)

    def _pulihkan(self):
        peramban.kandidat = self._kandidat_asli
        peramban.VERSI_TERTINGGAL.clear()
        peramban._KETERSEDIAAN = None

    @staticmethod
    def _stub(folder, nama, keluar):
        jalur = Path(folder) / nama
        jalur.write_text("#!/bin/sh\necho " + repr(keluar) + "\n", encoding="utf-8")
        jalur.chmod(0o755)
        return jalur

    def test_jejak_menyebut_berkas_tidak_ada(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(peramban, "kandidat", lambda: [Path(folder) / "msedge.exe"]):
                jejak = peramban.lacak()
        self.assertEqual(len(jejak), 1)
        self.assertFalse(jejak[0]["ada"])
        self.assertIn("tidak ada", jejak[0]["alasan"])
        self.assertIn("msedge.exe", jejak[0]["jalur"])

    def test_jejak_menyebut_berkas_ditemukan_tetapi_gagal(self):
        with tempfile.TemporaryDirectory() as folder:
            rusak = self._stub(folder, "chrome", "error while loading shared libraries: libnspr4.so")
            with mock.patch.object(peramban, "kandidat", lambda: [rusak]):
                jejak = peramban.lacak()
        self.assertTrue(jejak[0]["ada"])
        self.assertIn("tidak dikenali", jejak[0]["alasan"])

    def test_alasan_membedakan_tidak_ada_dan_tidak_bisa_dijalankan(self):
        with mock.patch.object(
            peramban, "lacak", lambda *a, **k: [{"jalur": "/x", "ada": False, "alasan": "berkas tidak ada"}]
        ):
            self.assertIn("Tidak ada berkas peramban", peramban._alasan_tanpa_peramban())
        with mock.patch.object(
            peramban, "lacak",
            lambda *a, **k: [{"jalur": "/x", "ada": True, "alasan": "ada, tetapi tidak dikenali"}],
        ):
            self.assertIn("tidak satupun yang dikenali", peramban._alasan_tanpa_peramban())

    def test_ketersediaan_membawa_alasan_dan_daftar_yang_dicari(self):
        with mock.patch.object(peramban, "cari", lambda *a, **k: None):
            with mock.patch.object(
                peramban, "lacak", lambda *a, **k: [{"jalur": "C:/x/msedge.exe", "ada": False, "alasan": "berkas tidak ada"}]
            ):
                info = peramban.ketersediaan(refresh=True)
        self.assertFalse(info["tersedia"])
        self.assertTrue(info["alasan"])
        self.assertEqual(len(info["dicari"]), 1)

    def test_peringatan_chromium_tidak_membuat_peramban_terbaca_rusak(self):
        self.assertTrue(
            peramban._keluaran_seperti_versi(
                "[1015/084855.123:WARNING:policy.cc(123)] Microsoft Edge 141.0.2903.86"
            )
        )
        self.assertTrue(peramban._keluaran_seperti_versi("Google Chrome 156.0.8078.4"))
        self.assertFalse(peramban._keluaran_seperti_versi("[1015/084855.123:FATAL:tidak bisa mulai]"))

    def test_keluaran_galat_tidak_mengalahkan_keluaran_baku(self):
        jalur = Path("/x/msedge.exe")
        with mock.patch.object(
            peramban,
            "_keluaran_versi_mentah",
            lambda p: ("Microsoft Edge 141.0.2903.86", "[1015/084855:WARNING:bising]"),
        ):
            self.assertEqual(peramban._keluaran_versi(jalur), "Microsoft Edge 141.0.2903.86")
            self.assertEqual(peramban.versi(jalur), "141.0.2903.86")

    def test_kandidat_registry_dan_path_tidak_duplikat(self):
        with mock.patch.object(peramban, "_kandidat_windows", lambda: [Path("C:/Edge/msedge.exe")]):
            with mock.patch.object(peramban, "_kandidat_registry", lambda: [Path("C:/Edge/msedge.exe")]):
                with mock.patch.object(peramban, "_kandidat_path", lambda: [Path("D:/chrome.exe")]):
                    if not sys.platform.startswith("win"):
                        # Di Linux rutenya berbeda; cukup pastikan penyaring kembar bekerja.
                        self.assertEqual(len(peramban._rapi([Path("/a"), Path("/a"), Path("/b")])), 2)
                    else:
                        self.assertEqual([str(p) for p in peramban.kandidat()], ["C:/Edge/msedge.exe", "D:/chrome.exe"])


class VersiDariBerkasTest(unittest.TestCase):
    """Versi peramban dibaca dari berkasnya, bukan dengan menjalankannya.

    Chrome dan Edge di Windows adalah aplikasi GUI yang tidak menulis `--version`
    ke pipa (crbug 158372), dan pada banyak versi malah membuka jendela peramban.
    Karena itu di Windows berkasnya tidak pernah dijalankan untuk diperiksa.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name)

    def test_folder_samping_bernama_nomor_versi(self):
        for nama in ("139.0.1.1", "141.0.7390.54", "bukan-versi", "141.0"):
            (self.folder / nama).mkdir()
        (self.folder / "chrome.exe").write_text("x", encoding="utf-8")
        self.assertEqual(peramban._versi_dari_folder_samping(self.folder / "chrome.exe"), "141.0.7390.54")

    def test_folder_samping_kosong_bila_tidak_ada(self):
        (self.folder / "chrome.exe").write_text("x", encoding="utf-8")
        self.assertEqual(peramban._versi_dari_folder_samping(self.folder / "chrome.exe"), "")

    def test_nama_peramban_dikenal(self):
        self.assertTrue(peramban._nama_peramban_dikenal(Path("C:/Edge/msedge.exe")))
        self.assertTrue(peramban._nama_peramban_dikenal(Path("C:/x/headless_shell.exe")))
        self.assertFalse(peramban._nama_peramban_dikenal(Path("C:/windows/regedit.exe")))

    def test_uji_tidak_pernah_menjalankan_berkas_sembarangan(self):
        """Menunjuk berkas yang bukan peramban harus ditolak sebelum diluncurkan."""
        sembarang = self.folder / "catatan.exe"
        sembarang.write_text("x", encoding="utf-8")
        hasil = peramban.uji(str(sembarang))
        self.assertFalse(hasil["berhasil"])
        self.assertIn("tidak bisa dipakai sebagai peramban", hasil["pesan"])
        self.assertIsNone(peramban.pilihan_tersimpan(), "pilihan yang ditolak tidak boleh disimpan")


class PilihanPerambanTest(unittest.TestCase):
    """Pengguna boleh menunjuk sendiri berkas perambannya, dan pilihan itu diingat."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self._data = mock.patch.object(peramban.config, "data_dir", lambda: self.folder)
        self._data.start()
        self.addCleanup(self._data.stop)
        peramban.VERSI_TERTINGGAL.clear()
        peramban._KETERSEDIAAN = None
        self.addCleanup(peramban.VERSI_TERTINGGAL.clear)
        self.addCleanup(self._bersihkan)

    def _bersihkan(self):
        peramban._KETERSEDIAAN = None

    def test_pilihan_disimpan_lalu_dibaca_lagi(self):
        self.assertIsNone(peramban.pilihan_tersimpan())
        peramban.tetapkan("/tmp/msedge")
        self.assertEqual(peramban.pilihan_tersimpan(), Path("/tmp/msedge"))
        peramban.tetapkan(None)
        self.assertIsNone(peramban.pilihan_tersimpan())

    def test_pilihan_dipakai_walaupun_kandidat_kosong(self):
        with tempfile.TemporaryDirectory() as folder:
            bagus = JejakPencarianTest._stub(folder, "msedge", "Microsoft Edge 141.0.2903.86")
            peramban.tetapkan(bagus)
            with mock.patch.object(peramban, "kandidat", lambda: []):
                info = peramban.ketersediaan(refresh=True)
        self.assertTrue(info["tersedia"])
        self.assertEqual(info["sumber"], "pilihan Anda")
        self.assertEqual(info["versi"], "141.0.2903.86")

    def test_uji_dengan_jalur_yang_ditunjuk_dijawab_bukan_diam(self):
        with tempfile.TemporaryDirectory() as folder:
            hasil = peramban.uji(str(Path(folder) / "tidak-ada.exe"))
        self.assertFalse(hasil["berhasil"])
        self.assertIn("tidak ditemukan", hasil["pesan"])

    def test_pilihan_yang_ditunjuk_tetap_harus_bisa_dijalankan(self):
        with tempfile.TemporaryDirectory() as folder:
            rusak = JejakPencarianTest._stub(folder, "chrome", "error while loading shared libraries")
            hasil = peramban.uji(str(rusak))
        self.assertFalse(hasil["berhasil"])
        self.assertIn("tidak bisa dipakai sebagai peramban", hasil["pesan"])
        self.assertIsNone(peramban.pilihan_tersimpan(), "pilihan yang gagal tidak boleh disimpan")


class BingkaiWebSocketTest(unittest.TestCase):
    """Pembacaan bingkai WebSocket: pesan besar dan terpotong harus utuh."""

    def setUp(self):
        self.a, self.b = socket.socketpair()
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)

    def kirim_dan_baca(self, data: bytes) -> tuple[int, bytes]:
        self.a.sendall(data)
        return peramban._baca_bingkai(self.b)

    def test_pesan_kecil(self):
        opcode, isi = self.kirim_dan_baca(peramban._bingkai("halo"))
        self.assertEqual(opcode, 0x1)
        self.assertEqual(isi, b"halo")

    def test_bingkai_klien_selalu_bermasker(self):
        bingkai = peramban._bingkai("rahasia")
        self.assertTrue(bingkai[1] & 0x80, "bingkai dari klien wajib bermasker")
        self.assertNotIn(b"rahasia", bingkai, "isi tidak boleh terlihat apa adanya")

    def test_panjang_16_bit(self):
        # 200 bita: header 2 bita tidak cukup, harus memakai panjang 16 bit.
        teks = "x" * 200
        opcode, isi = self.kirim_dan_baca(peramban._bingkai(teks))
        self.assertEqual((opcode, isi), (0x1, teks.encode()))

    def test_panjang_64_bit(self):
        # 70.000 bita: melebihi batas 16 bit, wajib memakai panjang 64 bit.
        teks = "y" * 70_000
        opcode, isi = self.kirim_dan_baca(peramban._bingkai(teks))
        self.assertEqual(opcode, 0x1)
        self.assertEqual(isi.decode(), teks)

    def test_bingkai_terpotong_disatukan(self):
        # Peramban boleh memecah satu pesan menjadi beberapa bingkai.
        kepala = bytes([0x01, 0x80 | 5]) + b"\x00\x00\x00\x00" + b"bagia"
        lanjutan = bytes([0x80, 0x80 | 5]) + b"\x00\x00\x00\x00" + b"n dua"
        self.a.sendall(kepala + lanjutan)
        opcode, isi = peramban._baca_bingkai(self.b)
        self.assertEqual(opcode, 0x1)
        self.assertEqual(isi, b"bagian dua")

    def test_bingkai_besar_ditolak_bukan_menghabiskan_memori(self):
        kepala = bytes([0x81, 0x7F]) + struct.pack(">Q", 10**12)
        self.a.sendall(kepala)
        with self.assertRaises(peramban.PerambanError):
            peramban._baca_bingkai(self.b, batas=1024)

    def test_koneksi_ditutup_di_tengah_dilaporkan(self):
        self.a.sendall(bytes([0x81, 0x80 | 10]) + b"\x00\x00\x00\x00" + b"abc")
        self.a.close()
        with self.assertRaises(peramban.PerambanError):
            peramban._baca_bingkai(self.b)


class RapikanTeksTest(unittest.TestCase):
    def test_baris_kosong_beruntun_diringkas_jadi_satu(self):
        # Satu baris kosong antar paragraf dipertahankan — itu yang membuat teks
        # halaman tetap terbaca sebagai halaman; yang dibuang hanya tumpukannya.
        self.assertEqual(peramban._rapikan("a\n\n\n\nb\n"), "a\n\nb")
        self.assertEqual(peramban._rapikan("a\nb"), "a\nb")

    def test_teks_kosong(self):
        self.assertEqual(peramban._rapikan("\n\n  \n"), "")


# ---------------------------------------------------------------------------
# Bagian yang butuh peramban sungguhan
# ---------------------------------------------------------------------------
@unittest.skipUnless(ADA_PERAMBAN, alasan_tanpa_peramban)
class RenderTest(unittest.TestCase):
    """Rendering sungguhan: JavaScript dijalankan, sopan santun dijaga."""

    @classmethod
    def setUpClass(cls):
        cls.situs = SitusTiruan()

    @classmethod
    def tearDownClass(cls):
        cls.situs.tutup()

    def test_isi_javascript_terbaca(self):
        with peramban.Sesi(timeout=20) as sesi:
            hasil = sesi.buka(self.situs.url + "/")
        self.assertEqual(hasil.status, 200)
        self.assertEqual(hasil.title, "Klinik Gigi Sehat")
        self.assertIn("Rp 350.000", hasil.text)
        self.assertIn("tabel-harga", hasil.html)
        self.assertGreater(hasil.ms, 0)

    def test_identitas_jujur_sampai_ke_situs(self):
        awal = len(self.situs.catatan)
        with peramban.Sesi(timeout=20) as sesi:
            sesi.buka(self.situs.url + "/")
        masuk = self.situs.catatan[awal:]
        self.assertTrue(masuk, "situs tiruan harus menerima permintaan")
        for baris in masuk:
            self.assertTrue(baris["ua"].startswith("LokaRadar/"), baris["ua"])
            self.assertIn("id-ID", baris["bahasa"])
            self.assertNotIn("google", baris["referer"].lower())

    def test_gambar_tidak_diunduh_font_dan_css_tetap(self):
        awal = len(self.situs.catatan)
        with peramban.Sesi(timeout=20) as sesi:
            sesi.buka(self.situs.url + "/")
        jalur = [baris["jalur"] for baris in self.situs.catatan[awal:]]
        self.assertNotIn("/hero.png", jalur, "gambar seharusnya diblokir")
        self.assertIn("/gaya.css", jalur, "CSS tetap diunduh supaya tata letak benar")
        self.assertIn("/app.js", jalur, "skrip tetap diunduh supaya isi terbaca")

    def test_media_bisa_dinyalakan_bila_diminta(self):
        awal = len(self.situs.catatan)
        with peramban.Sesi(timeout=20, blokir_media=False) as sesi:
            sesi.buka(self.situs.url + "/")
        jalur = [baris["jalur"] for baris in self.situs.catatan[awal:]]
        self.assertIn("/hero.png", jalur)

    def test_halaman_404_dilaporkan_bukan_dianggap_berhasil(self):
        with peramban.Sesi(timeout=20) as sesi:
            hasil = sesi.buka(self.situs.url + "/tidak-ada.html")
        self.assertEqual(hasil.status, 404)

    def test_selektor_tunggu_dilaporkan_apa_adanya(self):
        with peramban.Sesi(timeout=15, wait_selector="#tabel-harga") as sesi:
            ada = sesi.buka(self.situs.url + "/")
        self.assertIs(ada.selektor_ditemukan, True)
        self.assertEqual(ada.catatan, "")
        with peramban.Sesi(timeout=15, wait_selector="#tidak-ada-sama-sekali") as sesi:
            mulai = time.monotonic()
            tidak = sesi.buka(self.situs.url + "/")
        self.assertIs(tidak.selektor_ditemukan, False)
        self.assertIn("tidak ditemukan", tidak.catatan)
        self.assertLess(time.monotonic() - mulai, 40, "penantian harus berhenti sendiri")

    def test_satu_peramban_untuk_banyak_halaman(self):
        with peramban.Sesi(timeout=20) as sesi:
            pertama = sesi.buka(self.situs.url + "/")
            kedua = sesi.buka(self.situs.url + "/")
        self.assertEqual(pertama.title, kedua.title)
        self.assertIn("Rp 350.000", kedua.text)

    def test_peramban_ditutup_dan_folder_sementara_dibersihkan(self):
        import glob

        sebelum = set(glob.glob("/tmp/lokaradar-peramban-*"))
        with peramban.Sesi(timeout=20) as sesi:
            sesi.buka(self.situs.url + "/")
        time.sleep(0.4)
        sesudah = set(glob.glob("/tmp/lokaradar-peramban-*"))
        self.assertEqual(sesudah - sebelum, set(), "folder data peramban harus dibersihkan")

    def test_peramban_tidak_bisa_dijalankan_memberi_pesan_jelas(self):
        with tempfile.TemporaryDirectory() as folder:
            palsu = Path(folder) / "chrome"
            palsu.write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
            palsu.chmod(0o755)
            with self.assertRaises(peramban.PerambanError) as tangkap:
                with peramban.Sesi(timeout=5, executable=palsu) as sesi:
                    sesi.buka(self.situs.url + "/")
        self.assertIn("berhenti", str(tangkap.exception).lower())

    def test_uji_mandiri_tidak_menghubungi_situs_luar(self):
        hasil = peramban.uji()
        self.assertTrue(hasil["berhasil"], hasil["pesan"])
        self.assertIn("Rendering berjalan", hasil["pesan"])


@unittest.skipUnless(ADA_PERAMBAN, alasan_tanpa_peramban)
class SambunganKeRadarTest(unittest.TestCase):
    """Hasil peramban harus masuk ke radar sebagai potret biasa."""

    @classmethod
    def setUpClass(cls):
        cls.situs = SitusTiruan()

    @classmethod
    def tearDownClass(cls):
        cls.situs.tutup()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self._asli = os.environ.get("LOKARADAR_DATA")
        os.environ["LOKARADAR_DATA"] = str(Path(self.folder.name) / "radar")
        fetch._BROWSER_READY = None

    def tearDown(self):
        if self._asli is None:
            os.environ.pop("LOKARADAR_DATA", None)
        else:
            os.environ["LOKARADAR_DATA"] = self._asli
        fetch._BROWSER_READY = None
        self.folder.cleanup()

    def test_browser_ready_benar_tanpa_scrapling(self):
        with mock.patch.object(fetch, "_ScraplingDynamicFetcher", None):
            self.assertTrue(fetch.browser_ready(refresh=True))

    def test_fetcher_merender_lewat_peramban_lokal(self):
        with mock.patch.object(fetch, "_ScraplingDynamicFetcher", None), mock.patch.object(
            fetch, "_ScraplingDynamicSession", None
        ):
            fetcher = fetch.Fetcher(obey_robots=False, render="selalu", timeout=20)
            halaman = fetcher.get(self.situs.url + "/")
        self.assertTrue(halaman.rendered)
        self.assertIn("Rp 350.000", halaman.text)
        self.assertEqual(halaman.sumber if hasattr(halaman, "sumber") else "peramban", "peramban")

    def test_potret_tersimpan_bertanda_peramban(self):
        from lokaradar import run as radar_run
        from lokaradar.store import Store

        with mock.patch.object(fetch, "_ScraplingDynamicFetcher", None), mock.patch.object(
            fetch, "_ScraplingDynamicSession", None
        ):
            with Store() as store:
                store.add_target(self.situs.url + "/", "Klinik", "halaman")
                fetcher = fetch.Fetcher(obey_robots=False, render="selalu", timeout=20)
                with fetcher.render_session():
                    hasil = radar_run.run_once(store, fetcher, max_pages=5)
        self.assertEqual(hasil["diperiksa"], 1)
        baris = sqlite3.connect(str(Path(self.folder.name) / "radar" / "radar.sqlite3"))
        sumber = baris.execute("SELECT sumber, facts FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(sumber[0], "peramban")
        fakta = json.loads(sumber[1])
        self.assertGreaterEqual(fakta["word_count"], 10)
        self.assertEqual([h.get("amount") for h in fakta.get("prices") or []], [350000.0])

    def test_robots_tetap_dihormati_di_jalur_peramban(self):
        """Alamat yang dilarang tidak boleh sampai ke peramban — bahkan tidak dicoba."""
        awal = len(self.situs.catatan)
        with mock.patch.object(fetch, "_ScraplingDynamicFetcher", None), mock.patch.object(
            fetch, "_ScraplingDynamicSession", None
        ):
            fetcher = fetch.Fetcher(obey_robots=True, render="selalu", timeout=20)
            with self.assertRaises(fetch.BlockedError):
                fetcher.get(self.situs.url + "/rahasia.html")
        jalur = [baris["jalur"] for baris in self.situs.catatan[awal:]]
        self.assertNotIn("/rahasia.html", jalur, "alamat terlarang tidak boleh diminta ke situs")


class TanpaPerambanTest(unittest.TestCase):
    """Saat peramban tidak ada, radar berjalan seperti biasa dan berkata jujur."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self._asli = os.environ.get("LOKARADAR_DATA")
        os.environ["LOKARADAR_DATA"] = str(Path(self.folder.name) / "radar")
        peramban._KETERSEDIAAN = None
        fetch._BROWSER_READY = None

    def tearDown(self):
        if self._asli is None:
            os.environ.pop("LOKARADAR_DATA", None)
        else:
            os.environ["LOKARADAR_DATA"] = self._asli
        peramban._KETERSEDIAAN = None
        fetch._BROWSER_READY = None
        self.folder.cleanup()

    def test_browser_ready_salah_dan_petunjuknya_menyebut_edge(self):
        with mock.patch.object(fetch, "_ScraplingDynamicFetcher", None), mock.patch.object(
            peramban, "cari", lambda *a, **k: None
        ):
            peramban._KETERSEDIAAN = None
            self.assertFalse(fetch.browser_ready(refresh=True))
        self.assertIn("Edge", fetch.PETUNJUK_PERAMBAN)
        self.assertIn("scrapling install", fetch.PETUNJUK_PERAMBAN)

    def test_fetcher_tanpa_render_loader_tidak_gagal(self):
        with mock.patch.object(fetch, "_ScraplingDynamicFetcher", None), mock.patch.object(
            peramban, "cari", lambda *a, **k: None
        ):
            peramban._KETERSEDIAAN = None
            fetcher = fetch.Fetcher(obey_robots=False, render="selalu")
        self.assertIsNone(fetcher.render_loader, "tanpa peramban, rendering dimatikan dengan tenang")


class PenandaKerangkaTest(unittest.TestCase):
    """Halaman ber-JavaScript harus dikenali supaya `auto` benar-benar merender."""

    def test_id_next_dikenali(self):
        tipis = fetch.Page(
            url="http://x/", status=200, html='<div id="__next"></div>', text="kata " * 5, elapsed_ms=1
        )
        self.assertTrue(fetch.page_perlu_render(tipis))

    def test_halaman_statis_tipis_tidak_memicu_peramban(self):
        statis = fetch.Page(
            url="http://x/",
            status=200,
            html="<html><body><h1>Kontak</h1><p>Hubungi kami.</p></body></html>",
            text="Kontak Hubungi kami",
            elapsed_ms=1,
        )
        self.assertFalse(fetch.page_perlu_render(statis))

    def test_halaman_panjang_tidak_memicu_peramban(self):
        panjang = fetch.Page(
            url="http://x/", status=200, html='<div id="__next"></div>', text="kata " * 200, elapsed_ms=1
        )
        self.assertFalse(fetch.page_perlu_render(panjang))


if __name__ == "__main__":
    unittest.main()
