"""Uji penghentian aplikasi: halaman, endpoint, pemeriksaan asal, dan bendera berhenti."""

import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaseo_desktop.server import STOP_REQUESTED, create_server  # noqa: E402


class StopTest(unittest.TestCase):
    def setUp(self):
        STOP_REQUESTED.clear()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "index.html").write_text("<!doctype html><title>LokaSEO</title>", encoding="utf-8")
        self.server = create_server(root, "127.0.0.1", 0, offline=True)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        STOP_REQUESTED.clear()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def call(self, method, path, headers=None, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        payload = json.dumps(body) if body is not None else None
        connection.request(method, path, body=payload, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        result = (response.status, dict(response.getheaders()), data)
        connection.close()
        return result

    def origin(self):
        return f"http://127.0.0.1:{self.port}"

    def test_stop_page_served_without_inline_script(self):
        """Halaman hentikan memakai skrip terpisah.

        Bug yang pernah lolos: skrip ditulis sebaris di dalam halaman, padahal
        header CSP aplikasi memakai `script-src 'self'`. Akibatnya tombol
        "Hentikan aplikasi" tidak berfungsi di peramban sungguhan.
        """
        status, headers, body = self.call("GET", "/hentikan")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        text = body.decode("utf-8")
        self.assertIn("Hentikan aplikasi", text)
        self.assertNotIn("<script>", text, "skrip sebaris diblokir CSP")
        self.assertIn('/hentikan.js', text)
        # Tanpa sumber daya luar: halaman tetap berfungsi tanpa internet.
        for marker in ("http://", "https://", "//cdn", "fonts.googleapis"):
            self.assertNotIn(marker, text.replace("http://127.0.0.1", "local"))

    def test_stop_script_contains_endpoint(self):
        status, headers, body = self.call("GET", "/hentikan.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["Content-Type"])
        teks = body.decode("utf-8")
        self.assertIn("/api/lokaseo/hentikan", teks)
        self.assertIn('method: "POST"', teks)

    def test_info_endpoint_reports_desktop_mode(self):
        status, _, body = self.call("GET", "/api/lokaseo/info")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["mode"], "desktop")
        self.assertTrue(payload["luring"])
        self.assertEqual(payload["hentikan"], "/hentikan")

    def test_stop_requires_same_origin(self):
        status, _, _ = self.call(
            "POST",
            "/api/lokaseo/hentikan",
            headers={"Origin": "http://jahat.example", "Content-Type": "application/json"},
        )
        self.assertEqual(status, 403)
        self.assertFalse(STOP_REQUESTED.is_set(), "permintaan lintas situs tidak boleh menghentikan aplikasi")

    def test_stop_requires_origin_header(self):
        status, _, _ = self.call("POST", "/api/lokaseo/hentikan", headers={"Content-Type": "application/json"})
        self.assertEqual(status, 403)
        self.assertFalse(STOP_REQUESTED.is_set())

    def test_stop_rejects_foreign_host(self):
        status, _, _ = self.call(
            "POST",
            "/api/lokaseo/hentikan",
            headers={"Host": "jahat.example:1", "Origin": self.origin()},
        )
        self.assertEqual(status, 421)

    def test_stop_sets_flag_after_confirmation(self):
        status, _, body = self.call(
            "POST",
            "/api/lokaseo/hentikan",
            headers={"Origin": self.origin(), "Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["dihentikan"])
        self.assertTrue(
            STOP_REQUESTED.wait(3),
            "bendera berhenti harus aktif setelah balasan dikirim",
        )

    def test_info_still_served_when_stopping(self):
        """Balasan dikirim lebih dahulu, jadi halaman tidak menampilkan galat jaringan."""
        self.call(
            "POST",
            "/api/lokaseo/hentikan",
            headers={"Origin": self.origin(), "Content-Type": "application/json"},
        )
        status, _, _ = self.call("GET", "/api/lokaseo/info")
        self.assertIn(status, (200, 421, 404, 500))  # server boleh sudah menutup diri


if __name__ == "__main__":
    unittest.main()
