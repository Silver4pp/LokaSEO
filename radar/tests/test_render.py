"""Uji rendering peramban untuk situs yang isinya dibuat JavaScript.

Temuan uji Bogor: halaman fdcdentalclinic.co.id hanya terbaca 3 kata lewat
permintaan biasa, karena seluruh isinya disusun JavaScript. Berkas ini mengunci
perilaku rendernya, termasuk janji-janji yang mudah bocor:

- mode `auto` hanya merender halaman yang memang tipis;
- identitas tetap jujur (User-Agent LokaRadar, tanpa referer Google);
- jeda sopan tetap dihitung untuk permintaan kedua;
- kegagalan peramban tidak pernah menggagalkan pemeriksaan, hanya dicatat;
- pengambil halaman yang diganti (pengujian) tidak pernah membuka peramban.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar import config, fetch, run as run_mod  # noqa: E402
from lokaradar.fetch import BlockedError, Fetcher, FetchError, Page  # noqa: E402

PANJANG = (
    "<html><body><h1>Kedai kopi</h1>"
    + " ".join(f"kalimat{index}" for index in range(120))
    + "</body></html>"
)
TIPIS = "<html><body><div id='app'>Memuat</div></body></html>"


class RobotsSelalu:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.dicek: list[str] = []

    def check(self, url, refresh=False):
        self.dicek.append(url)
        return type(
            "V", (), {"allowed": self.allowed, "crawl_delay": None, "reason": "uji", "sitemaps": []}
        )()


class LimiterPenghitung:
    """Penghitung jeda tanpa menunggu: uji tidak perlu tidur 2,5 detik."""

    def __init__(self) -> None:
        self.jeda: list[str] = []

    def wait(self, url, override=None):  # noqa: ARG002 - tanda tangan disamakan
        self.jeda.append(url)


def halaman(teks: str, url: str = "https://contoh.test/") -> Page:
    return Page(url=url, status=200, html=teks, text=teks, elapsed_ms=5, final_url=url)


class RenderModeTest(unittest.TestCase):
    """Kapan peramban dipakai dan kapan tidak."""

    def setUp(self):
        self.render_dipanggil: list[str] = []

    def _fetcher(self, *, render: str, statis_teks: str = TIPIS, render_teks: str | None = PANJANG):
        def statis(url, timeout):  # noqa: ARG001
            return halaman(statis_teks, url)

        def peramban(url, timeout):  # noqa: ARG001
            self.render_dipanggil.append(url)
            if render_teks is None:
                raise RuntimeError("Executable doesn't exist at /x/y/chrome")
            return halaman(render_teks, url)

        return Fetcher(
            robots=RobotsSelalu(),
            limiter=LimiterPenghitung(),
            page_loader=statis,
            render_loader=peramban,
            render=render,
        )

    def test_auto_merender_halaman_tipis(self):
        page = self._fetcher(render="auto").get("https://contoh.test/")
        self.assertTrue(page.rendered)
        self.assertEqual(self.render_dipanggil, ["https://contoh.test/"])
        self.assertGreater(page.jumlah_kata, config.RENDER_MIN_WORDS)

    def test_auto_tidak_merender_halaman_penuh(self):
        page = self._fetcher(render="auto", statis_teks=PANJANG).get("https://contoh.test/")
        self.assertFalse(page.rendered)
        self.assertEqual(self.render_dipanggil, [], "halaman berisi tidak perlu peramban")

    def test_mode_selalu_langsung_peramban(self):
        def statis(url, timeout):  # noqa: ARG001 - tidak boleh dipanggil
            raise AssertionError("mode selalu tidak boleh memakai permintaan biasa")

        def peramban(url, timeout):  # noqa: ARG001
            self.render_dipanggil.append(url)
            return halaman(PANJANG, url)

        fetcher = Fetcher(
            robots=RobotsSelalu(),
            limiter=LimiterPenghitung(),
            page_loader=statis,
            render_loader=peramban,
            render="selalu",
        )
        page = fetcher.get("https://contoh.test/")
        self.assertTrue(page.rendered)
        self.assertEqual(fetcher.calls, ["https://contoh.test/ (render)"])

    def test_mode_tidak_tidak_pernah_merender(self):
        page = self._fetcher(render="tidak").get("https://contoh.test/")
        self.assertFalse(page.rendered)
        self.assertEqual(self.render_dipanggil, [])

    def test_mode_selalu_jatuh_ke_permintaan_biasa_bila_peramban_gagal(self):
        fetcher = self._fetcher(render="selalu", render_teks=None)
        page = fetcher.get("https://contoh.test/")
        self.assertFalse(page.rendered)
        self.assertEqual(page.text, TIPIS, "isi yang dipakai harus dari permintaan biasa")

    def test_robots_ditolak_tidak_merender(self):
        fetcher = Fetcher(
            robots=RobotsSelalu(allowed=False),
            limiter=LimiterPenghitung(),
            page_loader=lambda url, timeout: halaman(TIPIS, url),
            render_loader=lambda url, timeout: halaman(PANJANG, url),
            render="auto",
        )
        with self.assertRaises(BlockedError):
            fetcher.get("https://contoh.test/")
        self.assertEqual(self.render_dipanggil, [], "penolakan robots berlaku untuk semua jalur")


class KesopananRenderTest(unittest.TestCase):
    """Permintaan kedua tetap patuh jeda per host."""

    def test_jeda_dihitung_dua_kali(self):
        limiter = LimiterPenghitung()
        fetcher = Fetcher(
            robots=RobotsSelalu(),
            limiter=limiter,
            page_loader=lambda url, timeout: halaman(TIPIS, url),
            render_loader=lambda url, timeout: halaman(PANJANG, url),
            render="auto",
        )
        fetcher.get("https://contoh.test/")
        self.assertEqual(limiter.jeda, ["https://contoh.test/"] * 2)

    def test_permintaan_biasa_hanya_sekali_dihitung_jika_tidak_merender(self):
        limiter = LimiterPenghitung()
        fetcher = Fetcher(
            robots=RobotsSelalu(),
            limiter=limiter,
            page_loader=lambda url, timeout: halaman(PANJANG, url),
            render_loader=lambda url, timeout: halaman(PANJANG, url),
            render="auto",
        )
        fetcher.get("https://contoh.test/")
        self.assertEqual(limiter.jeda, ["https://contoh.test/"])


class CatatanRenderTest(unittest.TestCase):
    """Kegagalan rendering dicatat, tidak disembunyikan atau dibesar-besarkan."""

    def test_pesan_peramban_belum_terunduh_diterjemahkan(self):
        fetcher = Fetcher(
            robots=RobotsSelalu(),
            limiter=LimiterPenghitung(),
            page_loader=lambda url, timeout: halaman(TIPIS, url),
            render_loader=lambda url, timeout: (_ for _ in ()).throw(
                RuntimeError("Executable doesn't exist at /x/y/chrome")
            ),
            render="auto",
        )
        page = fetcher.get("https://contoh.test/")
        # Pesannya harus bisa ditindaklanjuti lewat dua jalan: peramban yang
        # sudah terpasang di komputer, atau Scrapling yang diunduh sendiri.
        self.assertIn("Edge", page.render_gagal)
        self.assertIn("scrapling install", page.render_gagal)

    def test_halaman_masih_tipis_setelah_dirender(self):
        fetcher = Fetcher(
            robots=RobotsSelalu(),
            limiter=LimiterPenghitung(),
            page_loader=lambda url, timeout: halaman(TIPIS, url),
            render_loader=lambda url, timeout: halaman("<html><body>masih kosong</body></html>", url),
            render="auto",
        )
        page = fetcher.get("https://contoh.test/")
        self.assertTrue(page.rendered)
        self.assertIn("Rendering berhasil, tetapi halaman tetap tipis", page.render_gagal)

    def test_status_galat_dari_render_dilaporkan(self):
        fetcher = Fetcher(
            robots=RobotsSelalu(),
            limiter=LimiterPenghitung(),
            page_loader=lambda url, timeout: halaman(TIPIS, url),
            render_loader=lambda url, timeout: Page(
                url=url, status=403, html="", text="", elapsed_ms=1, final_url=url
            ),
            render="auto",
        )
        page = fetcher.get("https://contoh.test/")
        self.assertEqual(page.text, TIPIS, "isi biasa tetap dipakai bila render ditolak")
        self.assertIn("403", page.render_gagal)

    def test_pengambil_palsu_tidak_pernah_membuka_peramban(self):
        """Pengujian harus tetap luring: penggantian pengambil mematikan peramban."""
        fetcher = Fetcher(
            robots=RobotsSelalu(),
            limiter=LimiterPenghitung(),
            page_loader=lambda url, timeout: halaman(TIPIS, url),
            render="auto",
        )
        self.assertIsNone(fetcher.render_loader)


class PenandaJavaScriptTest(unittest.TestCase):
    """Halaman pendek yang statis tidak boleh memaksa unduhan peramban."""

    def _page(self, html: str) -> Page:
        return Page(url="https://contoh.test/", status=200, html=html, text=html, elapsed_ms=1)

    def test_kerangka_nextjs_perlu_render(self):
        html = '<html><body><div id="root"></div><script src="/_next/static/chunk.js"></script></body></html>'
        self.assertTrue(fetch.page_perlu_render(self._page(html)))

    def test_halaman_kontak_pendek_tidak_perlu_render(self):
        html = "<html><body><h1>Kontak</h1><p>Jl. Pajajaran 12, Bogor. Buka 08.00-17.00.</p></body></html>"
        self.assertFalse(fetch.page_perlu_render(self._page(html)))
        self.assertTrue(fetch.page_tipis(self._page(html)), "halaman itu memang pendek")

    def test_halaman_panjang_tidak_perlu_render(self):
        html = '<html><body><div id="app"></div>' + " ".join(f"kata{i}" for i in range(200)) + "</body></html>"
        self.assertFalse(fetch.page_perlu_render(self._page(html)))

    def test_kerangka_besar_tanpa_penanda_terkenal_tetap_dirender(self):
        html = '<html><body><div></div>' + "<script>let a=1;</script>" * 6 + "x" * 16000 + "</body></html>"
        self.assertTrue(fetch.page_perlu_render(self._page(html)))


class SesiPerambanTest(unittest.TestCase):
    """Satu peramban untuk seluruh putaran, dan tetap jujur soal identitas."""

    class SesiPalsu:
        """Peniru DynamicSession Scrapling: mencatat pembukaan dan permintaan."""

        dibuka = 0
        permintaan: list[dict] = []

        def __init__(self, **kwargs):
            SesiPerambanTest.SesiPalsu.dibuka += 1
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def fetch(self, url, **kwargs):
            SesiPerambanTest.SesiPalsu.permintaan.append(dict(kwargs, url=url))
            return Page(url=url, status=200, html=PANJANG, text=PANJANG, elapsed_ms=7, final_url=url)

    def setUp(self):
        self.asli_fetch = fetch._ScraplingDynamicFetcher
        self.asli_sesi = fetch._ScraplingDynamicSession
        fetch._ScraplingDynamicFetcher = type("D", (), {"fetch": staticmethod(lambda *a, **k: None)})()
        fetch._ScraplingDynamicSession = self.SesiPalsu
        self.SesiPalsu.dibuka = 0
        self.SesiPalsu.permintaan = []

    def tearDown(self):
        fetch._ScraplingDynamicFetcher = self.asli_fetch
        fetch._ScraplingDynamicSession = self.asli_sesi

    def _fetcher(self, *, render: str = "auto"):
        # Pengambil peramban diganti agar pengujian tetap luring; sesi palsu di
        # bawah akan menggantikannya selama blok `render_session`.
        return Fetcher(
            robots=RobotsSelalu(),
            limiter=LimiterPenghitung(),
            page_loader=lambda url, timeout: halaman(TIPIS, url),
            render_loader=lambda url, timeout: halaman(PANJANG, url),
            render=render,
        )

    def test_satu_peramban_untuk_banyak_halaman(self):
        fetcher = self._fetcher()
        with fetcher.render_session() as aktif:
            for alamat in ("https://a.test/", "https://b.test/", "https://c.test/"):
                fetcher.get(alamat)
            self.assertIs(aktif, fetcher)
        self.assertEqual(self.SesiPalsu.dibuka, 1)
        self.assertEqual(len(self.SesiPalsu.permintaan), 3)
        self.assertTrue(fetcher.sesi_terpakai)

    def test_sesi_ditutup_dan_loader_dikembalikan(self):
        fetcher = self._fetcher()
        semula = fetcher.render_loader
        with fetcher.render_session():
            self.assertIsNot(fetcher.render_loader, semula)
        self.assertIs(fetcher.render_loader, semula)

    def test_tidak_ada_sesi_saat_rendering_mati(self):
        fetcher = self._fetcher(render="tidak")
        with fetcher.render_session():
            fetcher.get("https://a.test/")
        self.assertEqual(self.SesiPalsu.dibuka, 0)
        self.assertFalse(fetcher.sesi_terpakai)

    def test_selektor_tunggu_dikirim_pada_tiap_permintaan(self):
        fetcher = Fetcher(
            robots=RobotsSelalu(),
            limiter=LimiterPenghitung(),
            page_loader=lambda url, timeout: halaman(TIPIS, url),
            render_loader=lambda url, timeout: halaman(PANJANG, url),
            render="auto",
            render_wait="#harga",
        )
        with fetcher.render_session():
            fetcher.get("https://a.test/")
        self.assertEqual(self.SesiPalsu.permintaan[-1].get("wait_selector"), "#harga")


class SelektorTungguTest(unittest.TestCase):
    """Selektor yang salah harus diberitahukan, bukan menunggu diam-diam."""

    def test_selektor_ditemukan(self):
        self.assertTrue(fetch.selektor_ditemukan('<div id="harga">Rp 10</div>', "#harga"))
        self.assertFalse(fetch.selektor_ditemukan("<div>Rp 10</div>", "#harga"))
        self.assertIsNone(fetch.selektor_ditemukan("<div></div>", ""))

    def test_catatan_ditulis_bila_selektor_tidak_ada(self):
        page = halaman(PANJANG)
        fetch._catat_selektor(page, "#tabel-harga")
        self.assertIn("tidak ditemukan", page.render_gagal)
        self.assertIn("#tabel-harga", page.render_gagal)

    def test_catatan_selektor_tidak_tertimpa_oleh_catatan_lain(self):
        def peramban(url, timeout):  # noqa: ARG001
            return fetch._catat_selektor(halaman(PANJANG, url), "#tabel-harga")

        fetcher = Fetcher(
            robots=RobotsSelalu(),
            limiter=LimiterPenghitung(),
            page_loader=lambda url, timeout: halaman(TIPIS, url),
            render_loader=peramban,
            render="auto",
        )
        page = fetcher.get("https://contoh.test/")
        self.assertTrue(page.rendered)
        self.assertIn("tidak ditemukan", page.render_gagal)


class IdentitasPerambanTest(unittest.TestCase):
    """Peramban pun tidak boleh menyamar sebagai orang lain."""

    class DynamicPalsu:
        panggilan: list[dict] = []

        def fetch(self, url, **kwargs):
            IdentitasPerambanTest.DynamicPalsu.panggilan.append(dict(kwargs, url=url))
            return Page(url=url, status=200, html=PANJANG, text=PANJANG, elapsed_ms=9, final_url=url)

    def setUp(self):
        self.asli = fetch._ScraplingDynamicFetcher
        fetch._ScraplingDynamicFetcher = self.DynamicPalsu()
        self.DynamicPalsu.panggilan = []

    def tearDown(self):
        fetch._ScraplingDynamicFetcher = self.asli

    def test_identitas_jujur_dan_tanpa_referer_google(self):
        fetch._dynamic_page("https://contoh.test/", 30.0)
        kwargs = self.DynamicPalsu.panggilan[-1]
        self.assertEqual(kwargs["useragent"], config.USER_AGENT)
        self.assertIn("LokaRadar", kwargs["useragent"])
        self.assertFalse(kwargs["google_search"], "referer Google bawaan Scrapling harus dimatikan")
        self.assertTrue(kwargs["headless"])
        self.assertEqual(kwargs["timeout"], 30000, "waktu tunggu Playwright memakai milidetik")
        for kunci, nilai in kwargs["extra_headers"].items():
            self.assertNotIn("google.com", str(nilai).lower())
            self.assertFalse(kunci.lower().startswith("sec-ch"), f"{kunci} adalah jejak peramban")

    def test_galat_jelas_bila_scrapling_peramban_tidak_ada(self):
        fetch._ScraplingDynamicFetcher = None
        with self.assertRaises(FetchError) as ctx:
            fetch._dynamic_page("https://contoh.test/", 10.0)
        self.assertIn("scrapling", str(ctx.exception))


class KesiapanPerambanTest(unittest.TestCase):
    def tearDown(self):
        fetch._BROWSER_READY = None
        fetch.BROWSER_CHECK_ERROR = None

    def test_ketersediaan_sesi_dilaporkan(self):
        asli = fetch._ScraplingDynamicSession
        fetch._ScraplingDynamicSession = None
        try:
            self.assertFalse(fetch.session_available())
        finally:
            fetch._ScraplingDynamicSession = asli
        # Sejak ada jalur peramban lokal, jawabannya mengikuti modul yang benar-
        # benar ada; kalau Scrapling tidak terpasang, sesi Scrapling memang tidak ada.
        self.assertEqual(fetch.session_available(), asli is not None)

    def test_belum_terpasang(self):
        """Tanpa Scrapling **dan** tanpa peramban terpasang, rendering mati."""
        asli = fetch._ScraplingDynamicFetcher
        fetch._ScraplingDynamicFetcher = None
        try:
            fetch._BROWSER_READY = None
            with mock.patch.object(fetch.peramban, "cari", lambda *a, **k: None):
                fetch.peramban._KETERSEDIAAN = None
                self.assertFalse(fetch.browser_ready(refresh=True))
            self.assertFalse(fetch.dynamic_available())
        finally:
            fetch._ScraplingDynamicFetcher = asli
            fetch.peramban._KETERSEDIAAN = None
            fetch._BROWSER_READY = None

    def test_peramban_terpasang_sudah_cukup_untuk_merender(self):
        """Tanpa Scrapling, peramban bawaan komputer tetap membuat rendering siap."""
        if not fetch.peramban.tersedia():
            self.skipTest("Tidak ada peramban di komputer ini.")
        asli = fetch._ScraplingDynamicFetcher
        fetch._ScraplingDynamicFetcher = None
        try:
            fetch._BROWSER_READY = None
            self.assertTrue(fetch.browser_ready(refresh=True))
        finally:
            fetch._ScraplingDynamicFetcher = asli
            fetch._BROWSER_READY = None

    def test_galat_peramban_dijelaskan_bukan_disembunyikan(self):
        pesan = fetch._pesan_ramah(RuntimeError("Executable doesn't exist at /x/y/chrome"))
        self.assertIn("scrapling install", pesan)
        self.assertIn("Edge", pesan, "petunjuk harus menyebut peramban yang sudah terpasang")
        pesan_timeout = fetch._pesan_ramah(RuntimeError("Timeout 30000ms exceeded"))
        self.assertIn("waktu", pesan_timeout)


class RunRenderTest(unittest.TestCase):
    """Alur radar mencatat bahwa halaman diambil dengan peramban."""

    def setUp(self):
        import tempfile

        from lokaradar.store import Store

        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "radar.sqlite3")
        self.store.add_target("https://js.test/", "Situs JS", "halaman")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_baris_mencatat_render_dan_menyarankan_langkah(self):
        fetcher = Fetcher(
            robots=RobotsSelalu(),
            limiter=LimiterPenghitung(),
            page_loader=lambda url, timeout: halaman(TIPIS, url),
            render_loader=lambda url, timeout: halaman(
                "<html><head><title>Kedai</title></head><body>"
                + " ".join(f"kata{index}" for index in range(90))
                + "</body></html>",
                url,
            ),
            render="auto",
        )
        hasil = run_mod.run_once(self.store, fetcher)
        baris = hasil["sasaran"][0]
        self.assertTrue(baris["dirender"])
        self.assertTrue(any("peramban" in catatan for catatan in baris["catatan_render"]))
        self.assertEqual(hasil["diperiksa"], 1)


class LaporanRenderTest(unittest.TestCase):
    """Laporan menyebut halaman ber-JavaScript, bukan diam saja."""

    def _pack(self, row: dict) -> dict:
        from lokaradar.report import build_pack

        baris = {
            "url": "https://js.test/",
            "label": "Situs JS",
            "kind": "halaman",
            "fetched_at": "2026-10-14T00:00:00Z",
            "status": 200,
            "facts": {"title": "JS", "word_count": 3, "prices": []},
            "changes": [],
        }
        baris.update(row)
        return build_pack([baris])

    def test_sasaran_dirender_ditulis_di_markdown(self):
        from lokaradar.report import markdown

        teks = markdown(self._pack({"dirender": True, "jumlah_kata": 120}))
        self.assertIn("dengan peramban", teks)

    def test_halaman_tipis_tanpa_render_menjadi_butir_ceklis(self):
        pack = self._pack({"dirender": False, "jumlah_kata": 3, "perlu_render": True})
        judul = [item["judul"] for item in pack["lokaseo"]["cek_list"]]
        self.assertTrue(any("peramban" in item.lower() for item in judul), judul)

    def test_catatan_render_disertakan_bila_gagal(self):
        pack = self._pack({"dirender": False, "render_gagal": "Peramban belum terunduh."})
        self.assertTrue(any("Peramban belum terunduh" in item for item in pack["lokaseo"]["catatan"]))


class PerubahanSumberTest(unittest.TestCase):
    """Ganti cara pengambilan bukan berarti situsnya berubah."""

    def test_cara_sama_tidak_menghasilkan_perubahan(self):
        self.assertIsNone(run_mod._perubahan_sumber("peramban", "peramban"))
        self.assertIsNone(run_mod._perubahan_sumber("", "peramban"))
        self.assertIsNone(run_mod._perubahan_sumber(None, "peramban"))

    def test_cara_berbeda_menghasilkan_satu_catatan_info(self):
        perubahan = run_mod._perubahan_sumber("permintaan-biasa", "peramban")
        self.assertEqual(perubahan["type"], "cara_pengambilan_berubah")
        self.assertEqual(perubahan["severity"], "info")
        self.assertIn("permintaan biasa", perubahan["message"])
        self.assertIn("peramban", perubahan["message"])


class RunSumberTest(unittest.TestCase):
    """Pemeriksaan sungguhan: alarm palsu dicegah, perubahan nyata tetap terbaca."""

    def setUp(self):
        import tempfile

        from lokaradar.store import Store

        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "radar.sqlite3")
        self.store.add_target("https://js.test/", "Situs JS", "halaman")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _fetcher(self, *, rendered: bool, harga: str = "Rp 10.000"):
        html = (
            "<html><body><div id='root'>"
            + f"<p>Harga {harga}</p>"
            + " ".join(f"kata{index}" for index in range(80))
            + "</div></body></html>"
        )

        def statis(url, timeout):  # noqa: ARG001
            return halaman(TIPIS, url)

        def peramban(url, timeout):  # noqa: ARG001
            return halaman(html, url)

        return Fetcher(
            robots=RobotsSelalu(),
            limiter=LimiterPenghitung(),
            page_loader=statis,
            render_loader=peramban,
            render="auto" if rendered else "tidak",
        )

    def test_perpindahan_ke_peramban_tidak_menghasilkan_alarm_isi(self):
        run_mod.run_once(self.store, self._fetcher(rendered=False))
        hasil = run_mod.run_once(self.store, self._fetcher(rendered=True))
        perubahan = hasil["sasaran"][0]["changes"]
        self.assertEqual([item["type"] for item in perubahan], ["cara_pengambilan_berubah"])
        self.assertTrue(hasil["sasaran"][0]["dirender"])
        self.assertEqual(self.store.latest_snapshot(1)["sumber"], "peramban")
        # Keterangan perpindahan cukup sekali: lewat baris perubahan, bukan catatan kembar.
        catatan = " ".join(hasil["sasaran"][0]["catatan_render"])
        self.assertNotIn("pembandingan isi dimulai ulang", catatan)
        self.assertIn("diambil ulang dengan peramban", catatan)

    def test_perubahan_harga_tetap_terbaca_saat_cara_pengambilan_sama(self):
        run_mod.run_once(self.store, self._fetcher(rendered=True, harga="Rp 10.000"))
        hasil = run_mod.run_once(self.store, self._fetcher(rendered=True, harga="Rp 25.000"))
        jenis = [item["type"] for item in hasil["sasaran"][0]["changes"]]
        self.assertTrue(any("harga" in item for item in jenis), jenis)


class CatatanTanpaKembarTest(unittest.TestCase):
    """Catatan yang sama tidak ditulis berulang di laporan."""

    def _pack(self, rows: list[dict]) -> dict:
        from lokaradar.report import build_pack

        siap = []
        for index, tambahan in enumerate(rows):
            baris = {
                "url": f"https://js{index}.test/",
                "label": f"Situs JS {index}",
                "kind": "halaman",
                "fetched_at": "2026-10-14T00:00:00Z",
                "status": 200,
                "facts": {"title": "JS", "word_count": 3, "prices": []},
                "changes": [],
            }
            baris.update(tambahan)
            siap.append(baris)
        return build_pack(siap)

    def test_catatan_kembar_ditulis_sekali(self):
        pack = self._pack([{"render_gagal": "Peramban belum terunduh."}] * 3)
        catatan = [item for item in pack["lokaseo"]["catatan"] if item.startswith("Rendering —")]
        self.assertEqual(len(catatan), 1, catatan)

    def test_catatan_berbeda_tetap_utuh(self):
        pack = self._pack(
            [
                {"render_gagal": "Peramban belum terunduh."},
                {"render_gagal": "Selektor tunggu tidak ditemukan."},
            ]
        )
        catatan = [item for item in pack["lokaseo"]["catatan"] if item.startswith("Rendering —")]
        self.assertEqual(len(catatan), 2, catatan)


class CliRenderTest(unittest.TestCase):
    def test_tunggu_diterima_sebelum_dan_sesudah_subperintah(self):
        from lokaradar.cli import build_parser

        parser = build_parser()
        self.assertEqual(parser.parse_args(["--tunggu", "#harga", "scrape", "https://a.test/"]).tunggu, "#harga")
        self.assertEqual(parser.parse_args(["scrape", "https://a.test/", "--tunggu", ".menu"]).tunggu, ".menu")
        self.assertIsNone(parser.parse_args(["run"]).tunggu)

    def test_render_diterima_sebelum_dan_sesudah_subperintah(self):
        from lokaradar.cli import build_parser

        parser = build_parser()
        self.assertEqual(parser.parse_args(["--render", "selalu", "run"]).render, "selalu")
        self.assertEqual(parser.parse_args(["run", "--render", "tidak"]).render, "tidak")
        self.assertEqual(parser.parse_args(["run"]).render, config.DEFAULT_RENDER)
        with self.assertRaises(SystemExit):
            parser.parse_args(["--render", "kadang-kadang", "run"])


if __name__ == "__main__":
    unittest.main()
