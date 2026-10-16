"""Uji identitas pengambil: jalur bawaan tidak boleh menyamar sebagai peramban.

Bug nyata yang pernah lolos: `stealthy_headers` bawaan Scrapling bernilai True dan
`impersonate` bawaan bernilai "chrome". Akibatnya radar mengirim User-Agent Chrome
buatan, header `sec-ch-ua`, dan referer Google — bertentangan dengan janji
dokumen bahwa jalur bawaan memakai identitas jujur.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar import config, fetch  # noqa: E402
from lokaradar.fetch import _scrapling_page  # noqa: E402


class ResponsePalsu:
    def __init__(self) -> None:
        self.status = 200
        self.html_content = "<html><body>halo</body></html>"
        self.body = self.html_content.encode()
        self.headers = {"content-type": "text/html"}
        self.url = "https://contoh.test/"
        self.reason = "OK"
        self.text = ""

    def get_all_text(self) -> str:
        return "halo"


class ScraplingPalsu:
    """Peniru Scrapling: mencatat argumen yang diberikan pemanggil."""

    panggilan: list[dict] = []

    def __init__(self) -> None:
        self.panggilan = []

    def get(self, url, **kwargs):
        self.panggilan.append(dict(kwargs, url=url))
        return ResponsePalsu()


class IdentityTest(unittest.TestCase):
    def setUp(self):
        self.asli = fetch._ScraplingFetcher
        self.palsu = ScraplingPalsu()
        fetch._ScraplingFetcher = self.palsu

    def tearDown(self):
        fetch._ScraplingFetcher = self.asli

    def test_jalur_bawaan_memakai_identitas_jujur(self):
        _scrapling_page("https://contoh.test/", 30.0)
        kwargs = self.palsu.panggilan[-1]
        self.assertEqual(kwargs["headers"]["User-Agent"], config.USER_AGENT)
        self.assertIn("LokaRadar", kwargs["headers"]["User-Agent"])
        self.assertIsNone(kwargs["impersonate"], "penyamaran peramban harus dimatikan")
        self.assertFalse(kwargs["stealthy_headers"], "stealthy_headers bawaan harus dimatikan")
        self.assertNotIn("Referer", kwargs["headers"])
        self.assertFalse([key for key in kwargs["headers"] if key.lower().startswith("sec-ch")])

    def test_identitas_tidak_mengaku_sebagai_google(self):
        _scrapling_page("https://contoh.test/", 30.0)
        kwargs = self.palsu.panggilan[-1]
        teks = " ".join(f"{k}: {v}" for k, v in kwargs["headers"].items()).lower()
        for jejak in ("chrome", "mozilla", "safari", "google.com"):
            self.assertNotIn(jejak, teks, f"jalur bawaan tidak boleh membawa jejak {jejak}")

    def test_penyamaran_hanya_bila_dinyalakan_sadar(self):
        _scrapling_page("https://contoh.test/", 30.0, stealthy=True)
        kwargs = self.palsu.panggilan[-1]
        self.assertTrue(kwargs["stealthy_headers"])
        self.assertNotIn("headers", kwargs, "mode menyamar memakai header bawaan Scrapling")

    def test_fetcher_meneruskan_pilihan_stealthy(self):
        fetcher = fetch.Fetcher(obey_robots=False, stealthy=True)
        fetcher.get("https://contoh.test/")
        self.assertTrue(self.palsu.panggilan[-1]["stealthy_headers"])
        fetcher2 = fetch.Fetcher(obey_robots=False)
        fetcher2.get("https://contoh.test/")
        self.assertFalse(self.palsu.panggilan[-1]["stealthy_headers"])

    def test_status_text_diambil_dari_respons(self):
        page = _scrapling_page("https://contoh.test/", 30.0)
        self.assertEqual(page.status_text, "OK")
        self.assertEqual(page.status, 200)


if __name__ == "__main__":
    unittest.main()
