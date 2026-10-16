"""Uji biner hasil build (bila ada) agar kegagalan paket tertangkap otomatis.

Biner dibangun dengan `python -m PyInstaller desktop/alat/lokaseo.spec`. Uji ini melewati
dirinya sendiri bila paket belum dibangun, sehingga `unittest` tetap bisa dijalankan
tanpa langkah build.
"""

import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

DESKTOP = Path(__file__).resolve().parent.parent
# PyInstaller memberi akhiran .exe hanya di Windows. Kandidat dipilih sesuai sistem
# yang menjalankan uji, karena .exe hasil build lintas platform tidak bisa
# dieksekusi di Linux atau macOS.
CANDIDATES = [
    DESKTOP / "dist" / ("LokaSEO-console.exe" if sys.platform == "win32" else "LokaSEO-console"),
]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class BundleRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = next((path for path in CANDIDATES if path.is_file()), None)
        if binary is None:
            raise unittest.SkipTest("biner desktop belum dibangun; jalankan PyInstaller lebih dahulu")
        cls.binary = binary
        cls.port = free_port()
        cls.data_dir = tempfile.TemporaryDirectory()
        env = {
            **os.environ,
            "LOKA_DATA_DIR": cls.data_dir.name,
            "LOKA_OFFLINE": "1",
        }
        cls.process = subprocess.Popen(
            [str(binary), "--port", str(cls.port), "--no-open"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            if cls.process.poll() is not None:
                output = cls.process.stdout.read().decode("utf-8", "ignore")
                raise AssertionError(f"biner berhenti saat mulai:\n{output}")
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.3)
        raise AssertionError("biner tidak membuka port dalam 30 detik")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "process", None):
            cls.process.terminate()
            try:
                cls.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cls.process.kill()
        if getattr(cls, "data_dir", None):
            cls.data_dir.cleanup()

    def call(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        payload = json.dumps(body) if body is not None else None
        connection.request(method, path, body=payload, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        result = (response.status, dict(response.getheaders()), data)
        connection.close()
        return result

    def test_serves_interface_with_security_headers(self):
        status, headers, body = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"LokaSEO", body)
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])

    def test_bundle_carries_icons(self):
        self.assertEqual(self.call("GET", "/favicon.ico")[0], 200)

    def test_rejects_foreign_host(self):
        self.assertEqual(self.call("GET", "/", headers={"Host": "jahat.example:1"})[0], 421)

    def test_offline_mode_skips_provider(self):
        status, _, body = self.call(
            "POST",
            "/api/loka-ai/generate",
            body={
                "connections": [
                    {
                        "id": "c1",
                        "label": "Uji",
                        "provider": "openai",
                        "model": "gpt-4.1-mini",
                        "apiKey": "sk-uji-biner",
                        "enabled": True,
                    }
                ],
                "task": "ideas",
                "context": {"business": "Kopi", "city": "", "domain": "", "topic": "kopi", "notes": ""},
                "maxTokens": 256,
            },
            headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"},
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["attempts"], [], "mode luring tidak boleh memanggil penyedia")

    def test_log_file_created_and_has_no_api_key(self):
        log = Path(self.data_dir.name) / "lokaseo.log"
        self.assertTrue(log.is_file(), "catatan aplikasi tidak dibuat")
        content = log.read_text(encoding="utf-8", errors="ignore")
        self.assertNotIn("sk-uji-biner", content, "API key tidak boleh masuk catatan")


if __name__ == "__main__":
    unittest.main()
