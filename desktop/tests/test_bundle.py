"""Penjaga janji "tanpa layanan daring" untuk paket aplikasi.

Uji ini memeriksa berkas build yang benar-benar dikirim ke pengguna: tidak boleh ada
alamat luar selain penanda namespace, dan CSP harus menutup koneksi ke luar.
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaseo_desktop import config  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BUILD_DIR = REPO_ROOT / "loka-release"
# Penanda namespace di dalam berkas, bukan permintaan jaringan.
ALLOWED_HOSTS = {"www.w3.org", "json-schema.org", "react.dev"}
TEXT_SUFFIXES = {".js", ".mjs", ".css", ".html", ".svg", ".webmanifest", ".json", ".txt"}
HOST_PATTERN = re.compile(r"https?://([a-zA-Z0-9._-]+)")


class BundleTest(unittest.TestCase):
    def setUp(self):
        if not (BUILD_DIR / "index.html").is_file():
            self.skipTest("build loka-release belum ada; jalankan pnpm build:loka")

    def test_build_has_no_external_hosts(self):
        found = set()
        for path in BUILD_DIR.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            found.update(HOST_PATTERN.findall(text))
        unexpected = sorted(found - ALLOWED_HOSTS)
        self.assertEqual(unexpected, [], f"alamat luar tidak terduga di build: {unexpected}")

    def test_index_html_has_no_remote_assets(self):
        html = (BUILD_DIR / "index.html").read_text(encoding="utf-8")
        for reference in re.findall(r'(?:src|href)="([^"]+)"', html):
            self.assertFalse(
                reference.startswith(("http://", "https://", "//")),
                f"aset jarak jauh tidak boleh di paket: {reference}",
            )

    def test_default_binding_is_loopback(self):
        from lokaseo_desktop import app

        self.assertEqual(app.DEFAULT_HOST, "127.0.0.1")

    def test_egress_allowlist_is_only_the_four_providers(self):
        self.assertEqual(
            config.ALLOWED_EGRESS_HOSTS,
            {"api.openai.com", "openrouter.ai", "api.deepseek.com", "api.groq.com"},
        )

    def test_endpoints_are_https(self):
        for provider, endpoint in config.PROVIDER_ENDPOINTS.items():
            with self.subTest(provider=provider):
                self.assertTrue(endpoint.startswith("https://"), endpoint)


if __name__ == "__main__":
    unittest.main()
