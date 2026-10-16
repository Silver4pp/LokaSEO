"""Uji kepatuhan robots.txt: parsing, cache, dan sikap saat gagal mengambil."""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar import config  # noqa: E402
from lokaradar.robots import RobotsCache, _SimpleRules  # noqa: E402


class FakeResponse:
    def __init__(self, status: int, text: str = "") -> None:
        self.status = status
        self.text = text
        self.html_content = text


class SimpleRulesTest(unittest.TestCase):
    def test_disallow_all_blocks_everything(self):
        rules = _SimpleRules("User-agent: *\nDisallow: /\n")
        self.assertFalse(rules.can_fetch("https://contoh.test/halaman"))

    def test_allows_when_only_other_path_disallowed(self):
        rules = _SimpleRules("User-agent: *\nDisallow: /admin\n")
        self.assertTrue(rules.can_fetch("https://contoh.test/produk"))
        self.assertFalse(rules.can_fetch("https://contoh.test/admin/harga"))

    def test_allow_beats_disallow_for_specific_path(self):
        rules = _SimpleRules("User-agent: *\nDisallow: /katalog\nAllow: /katalog/umum\n")
        self.assertTrue(rules.can_fetch("https://contoh.test/katalog/umum"))
        self.assertFalse(rules.can_fetch("https://contoh.test/katalog/lain"))

    def test_crawl_delay_and_sitemap(self):
        rules = _SimpleRules("User-agent: *\nCrawl-delay: 8\nSitemap: https://contoh.test/sitemap.xml\n")
        self.assertEqual(rules.crawl_delay, 8.0)
        self.assertEqual(rules.sitemaps, ["https://contoh.test/sitemap.xml"])

    def test_other_agents_are_ignored(self):
        rules = _SimpleRules("User-agent: Googlebot\nDisallow: /\n")
        self.assertTrue(rules.can_fetch("https://contoh.test/apa-saja"))


class RobotsCacheTest(unittest.TestCase):
    def setUp(self):
        self.calls: list[str] = []

    def loader(self, response):
        def load(url):
            self.calls.append(url)
            return response
        return load

    def test_missing_robots_allows(self):
        cache = RobotsCache(self.loader(FakeResponse(404)))
        self.assertTrue(cache.check("https://contoh.test/halaman").allowed)

    def test_server_error_denies(self):
        cache = RobotsCache(self.loader(FakeResponse(503)))
        verdict = cache.check("https://contoh.test/halaman")
        self.assertFalse(verdict.allowed)
        self.assertIn("503", verdict.reason)

    def test_network_failure_denies(self):
        def boom(url):
            raise OSError("tidak terhubung")

        cache = RobotsCache(boom)
        self.assertFalse(cache.check("https://contoh.test/halaman").allowed)

    def test_disallow_directive_is_respected(self):
        cache = RobotsCache(self.loader(FakeResponse(200, "User-agent: *\nDisallow: /rahasia\n")))
        verdict = cache.check("https://contoh.test/rahasia/harga")
        self.assertFalse(verdict.allowed)

    def test_result_is_cached_per_host(self):
        cache = RobotsCache(self.loader(FakeResponse(404)))
        cache.check("https://contoh.test/a")
        cache.check("https://contoh.test/b")
        self.assertEqual(len(self.calls), 1, "robots.txt tidak boleh diambil berulang")

    def test_refresh_forces_new_fetch(self):
        cache = RobotsCache(self.loader(FakeResponse(404)))
        cache.check("https://contoh.test/a")
        cache.check("https://contoh.test/a", refresh=True)
        self.assertEqual(len(self.calls), 2)

    def test_robots_url_shape(self):
        cache = RobotsCache(self.loader(FakeResponse(404)))
        cache.check("https://contoh.test/halaman?x=1")
        self.assertEqual(self.calls[0], "https://contoh.test/robots.txt")
        self.assertIn("LokaRadar", config.USER_AGENT)


if __name__ == "__main__":
    unittest.main()
