"""Uji pengambil halaman: jeda sopan, penolakan robots, dan penanganan galat."""

import sys
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar.fetch import (  # noqa: E402
    BlockedError,
    Fetcher,
    FetchError,
    Page,
    RateLimiter,
    scrapling_available,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def fake_page(url: str, timeout: float = 30.0, status: int = 200, html: str = "<html><body>ok</body></html>") -> Page:
    """Peniru pengambil halaman. Tanda tangan harus sama dengan pengambil sungguhan."""
    return Page(url=url, status=status, html=html, text=html, elapsed_ms=12, final_url=url)


class RateLimiterTest(unittest.TestCase):
    def test_first_request_does_not_wait(self):
        clock = FakeClock()
        limiter = RateLimiter(2.5, clock=clock.monotonic, sleeper=clock.sleep)
        limiter.wait("https://contoh.test/a")
        self.assertEqual(clock.slept, [])

    def test_second_request_waits_remaining_delay(self):
        clock = FakeClock()
        limiter = RateLimiter(2.5, clock=clock.monotonic, sleeper=clock.sleep)
        limiter.wait("https://contoh.test/a")
        clock.now += 1.0
        limiter.wait("https://contoh.test/a")
        self.assertEqual(len(clock.slept), 1)
        self.assertAlmostEqual(clock.slept[0], 1.5, places=2)

    def test_different_hosts_are_independent(self):
        clock = FakeClock()
        limiter = RateLimiter(2.5, clock=clock.monotonic, sleeper=clock.sleep)
        limiter.wait("https://a.test/halaman")
        limiter.wait("https://b.test/halaman")
        self.assertEqual(clock.slept, [])

    def test_crawl_delay_override_is_maximum(self):
        clock = FakeClock()
        limiter = RateLimiter(2.5, clock=clock.monotonic, sleeper=clock.sleep)
        limiter.wait("https://contoh.test/a")
        clock.now += 3.0
        limiter.wait("https://contoh.test/a", override=8.0)
        self.assertEqual(len(clock.slept), 1)
        self.assertAlmostEqual(clock.slept[0], 5.0, places=2)

    def test_shorter_crawl_delay_does_not_shorten_default(self):
        clock = FakeClock()
        limiter = RateLimiter(2.5, clock=clock.monotonic, sleeper=clock.sleep)
        limiter.wait("https://contoh.test/a")
        clock.now += 1.0
        limiter.wait("https://contoh.test/a", override=0.5)
        self.assertAlmostEqual(clock.slept[0], 1.5, places=2)


class _Robots:
    def __init__(self, allowed: bool, delay: float | None = None) -> None:
        self.result = type("V", (), {"allowed": allowed, "crawl_delay": delay, "reason": "uji", "sitemaps": []})()
        self.checked: list[str] = []

    def check(self, url: str, refresh: bool = False):
        self.checked.append(url)
        return self.result


class FetcherTest(unittest.TestCase):
    def make(self, robots=None, loader=None, **kwargs) -> Fetcher:
        clock = FakeClock()
        limiter = kwargs.pop("limiter", None) or RateLimiter(0.0, clock=clock.monotonic, sleeper=clock.sleep)
        return Fetcher(robots=robots or _Robots(True), limiter=limiter, page_loader=loader or fake_page, **kwargs)

    def test_no_network_when_loader_is_injected(self):
        """Penjaga: uji tidak boleh menyentuh jaringan sungguhan."""
        original = urllib.request.urlopen

        def forbidden(*_args, **_kwargs):
            raise AssertionError("uji mencoba mengakses jaringan sungguhan")

        urllib.request.urlopen = forbidden  # type: ignore[assignment]
        try:
            fetcher = self.make()
            self.assertTrue(fetcher.get("https://contoh.test/halaman").ok)
        finally:
            urllib.request.urlopen = original  # type: ignore[assignment]

    def test_robots_denial_blocks_before_download(self):
        fetched: list[str] = []

        def loader(url, timeout):
            fetched.append(url)
            return fake_page(url)

        fetcher = self.make(robots=_Robots(False), loader=loader)
        with self.assertRaises(BlockedError):
            fetcher.get("https://contoh.test/rahasia")
        self.assertEqual(fetched, [], "halaman tidak boleh diambil bila robots menolak")

    def test_ignore_robots_skips_check(self):
        robots = _Robots(False)
        fetcher = self.make(robots=robots, obey_robots=False)
        self.assertTrue(fetcher.get("https://contoh.test/apapun").ok)
        self.assertEqual(robots.checked, [])

    def test_403_429_and_401_are_blocked(self):
        for status in (401, 403, 429):
            with self.subTest(status=status):
                fetcher = self.make(loader=lambda url, timeout, s=status: fake_page(url, status=s))
                with self.assertRaises(BlockedError) as context:
                    fetcher.get("https://contoh.test/halaman")
                self.assertEqual(context.exception.status, status)

    def test_error_pages_are_not_treated_as_blocked(self):
        """Halaman galat bukan penolakan robots: dicatat sebagai galat pengambilan."""
        for status in (404, 500, 503):
            with self.subTest(status=status):
                fetcher = self.make(loader=lambda url, timeout, s=status: fake_page(url, status=s, html="<p>galat</p>"))
                with self.assertRaises(FetchError) as context:
                    fetcher.get("https://contoh.test/halaman")
                self.assertNotIsInstance(context.exception, BlockedError)
                self.assertEqual(context.exception.status, status)
                self.assertIn(str(status), str(context.exception))

    def test_loader_exception_becomes_fetch_error(self):
        def boom(url, timeout):
            raise ValueError("pengurai gagal")

        fetcher = self.make(loader=boom)
        with self.assertRaises(FetchError):
            fetcher.get("https://contoh.test/halaman")

    def test_empty_html_is_fetch_error(self):
        fetcher = self.make(loader=lambda url, timeout: fake_page(url, status=200, html=""))
        with self.assertRaises(FetchError):
            fetcher.get("https://contoh.test/halaman")

    def test_calls_are_recorded(self):
        fetcher = self.make()
        fetcher.get("https://contoh.test/a")
        fetcher.get("https://contoh.test/b")
        self.assertEqual(fetcher.calls, ["https://contoh.test/a", "https://contoh.test/b"])

    def test_scrapling_detection_is_boolean(self):
        self.assertIsInstance(scrapling_available(), bool)


if __name__ == "__main__":
    unittest.main()
