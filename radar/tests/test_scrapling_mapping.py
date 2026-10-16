"""Regresi pemetaan respons Scrapling.

Bug nyata yang pernah terjadi: `response.text` pada Scrapling adalah `TextHandler`
dan sering kosong, sehingga robots.txt terbaca kosong (aturan Disallow diabaikan)
dan teks halaman selalu kosong (perubahan isi tidak pernah terdeteksi).
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar.fetch import Page, _response_html, _response_text  # noqa: E402
from lokaradar.robots import RobotsCache, _body_text  # noqa: E402


class TextHandler:
    """Meniru TextHandler Scrapling: objek yang tampak seperti teks tetapi kosong."""

    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        return ""


class ScraplingLike:
    """Meniru atribut respons Scrapling yang penting."""

    def __init__(self, html: str, visible: str = "", text_attr=None) -> None:
        self.html_content = html
        self.body = html.encode("utf-8")
        self.text = text_attr if text_attr is not None else TextHandler()
        self._visible = visible

    def get_all_text(self) -> str:
        return self._visible


class MappingTest(unittest.TestCase):
    def test_html_comes_from_html_content_not_text(self):
        response = ScraplingLike("<html><body>Halo</body></html>", visible="Halo")
        self.assertEqual(_response_html(response), "<html><body>Halo</body></html>")

    def test_visible_text_prefers_get_all_text(self):
        response = ScraplingLike("<html><body>Halo dunia</body></html>", visible="Halo dunia")
        self.assertEqual(_response_text(response), "Halo dunia")

    def test_falls_back_to_body_when_no_visible_text(self):
        response = ScraplingLike("Baris penting", visible="")
        self.assertEqual(_response_text(response), "Baris penting")

    def test_never_returns_non_string(self):
        response = ScraplingLike("", visible="")
        self.assertIsInstance(_response_text(response), str)
        self.assertIsInstance(_response_html(response), str)

    def test_robots_body_text_reads_page_html(self):
        """Objek Page menyimpan isi di `.html` dan `.text`; keduanya harus terbaca."""
        page = Page(
            url="http://contoh.test/robots.txt",
            status=200,
            html="User-agent: *\nDisallow: /rahasia\n",
            text="",
            elapsed_ms=1,
        )
        self.assertIn("Disallow: /rahasia", _body_text(page))

    def test_robots_body_text_reads_scrapling_like(self):
        self.assertIn("Disallow", _body_text(ScraplingLike("User-agent: *\nDisallow: /", visible="")))

    def test_robots_disallow_works_when_text_is_empty(self):
        """Inti bug: isi robots.txt harus dinilai dari html, bukan dari `.text`."""

        def loader(url: str, timeout: float = 30.0) -> Page:
            return Page(
                url=url,
                status=200,
                html="User-agent: *\nDisallow: /rahasia\n",
                text="",
                elapsed_ms=1,
            )

        cache = RobotsCache(loader)
        self.assertFalse(cache.check("http://contoh.test/rahasia/harga").allowed)
        self.assertTrue(cache.check("http://contoh.test/produk").allowed)

    def test_page_text_is_used_for_content_hash(self):
        from lokaradar.extract import page_facts

        first = page_facts("https://contoh.test/", "<p>a</p>", "Halo dunia")
        second = page_facts("https://contoh.test/", "<p>a</p>", "Halo dunia baru")
        self.assertNotEqual(first["content_hash"], second["content_hash"])
        self.assertGreater(first["word_count"], 0)


if __name__ == "__main__":
    unittest.main()
