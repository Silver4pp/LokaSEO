"""Uji server lokal: pengikatan loopback, host, batas body, statis, dan mode luring."""

import http.client
import json
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaseo_desktop.server import create_server  # noqa: E402

VALID = {
    "connections": [
        {
            "id": "c1",
            "label": "Utama",
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "apiKey": "sk-test-key",
            "enabled": True,
        }
    ],
    "task": "ideas",
    "context": {"business": "Kebun Kopi", "city": "Bogor", "domain": "", "topic": "kopi", "notes": ""},
    "maxTokens": 256,
}


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        (root / "index.html").write_text("<!doctype html><title>LokaSEO</title>", encoding="utf-8")
        (root / "assets").mkdir()
        (root / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
        (root / ".rahasia.txt").write_text("jangan disajikan", encoding="utf-8")
        outside = Path(cls.tmp.name).parent / "lokaseo-outside.css"
        outside.write_text("HARMLESS_OUTSIDE_BUILD", encoding="utf-8")
        cls.outside = outside
        try:
            (root / "probe.css").symlink_to(outside)
        except OSError:
            pass
        cls.server = create_server(root, "127.0.0.1", 0, offline=False)
        cls.port = cls.server.server_address[1]
        cls.offline_server = create_server(root, "127.0.0.1", 0, offline=True)
        cls.offline_port = cls.offline_server.server_address[1]
        for server in (cls.server, cls.offline_server):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for server in (cls.server, cls.offline_server):
            server.shutdown()
            server.server_close()
        cls.tmp.cleanup()
        cls.outside.unlink(missing_ok=True)

    # -- util ---------------------------------------------------------------
    def call(self, method, path, port=None, body=None, headers=None, raw_body=None):
        port = port or self.port
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        payload = raw_body if raw_body is not None else (json.dumps(body) if body is not None else None)
        connection.request(method, path, body=payload, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        result = (response.status, dict(response.getheaders()), data)
        connection.close()
        return result

    def ai_headers(self, port=None, **extra):
        host = f"127.0.0.1:{port or self.port}"
        headers = {"Content-Type": "application/json", "Origin": f"http://{host}"}
        headers.update(extra)
        return headers

    # -- berkas statis ------------------------------------------------------
    def test_serves_index_and_assets(self):
        status, headers, body = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"LokaSEO", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, headers, _ = self.call("GET", "/assets/app.js")
        self.assertEqual(status, 200)
        self.assertIn("immutable", headers["Cache-Control"])

    def test_head_has_no_body(self):
        _, _, expected = self.call("GET", "/")
        status, headers, body = self.call("HEAD", "/")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(int(headers["Content-Length"]), len(expected))

    def test_security_headers_present(self):
        _, headers, _ = self.call("GET", "/")
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")

    def test_dotfile_extension_and_traversal_blocked(self):
        self.assertEqual(self.call("GET", "/.rahasia.txt")[0], 404)
        self.assertEqual(self.call("GET", "/berkas.tidakdikenal")[0], 404)
        self.assertEqual(self.call("GET", "/../../etc/passwd")[0], 404)
        self.assertEqual(self.call("GET", "/%2e%2e/%2e%2e/etc/passwd")[0], 404)

    def test_symlink_outside_build_is_not_served(self):
        status, _, body = self.call("GET", "/probe.css")
        self.assertEqual(status, 404)
        self.assertNotIn(b"HARMLESS_OUTSIDE_BUILD", body)

    def test_write_methods_rejected(self):
        self.assertEqual(self.call("PUT", "/")[0], 405)
        self.assertEqual(self.call("OPTIONS", "/")[0], 405)

    # -- host dan origin ----------------------------------------------------
    def test_unknown_host_is_rejected(self):
        status, _, _ = self.call("GET", "/", headers={"Host": "untrusted.example:3000"})
        self.assertEqual(status, 421)
        status, _, _ = self.call(
            "POST",
            "/api/loka-ai/generate",
            body=VALID,
            headers=self.ai_headers(**{"Host": "untrusted.example:3000", "Origin": "http://untrusted.example:3000"}),
        )
        self.assertEqual(status, 421)

    def test_cross_site_origin_is_rejected(self):
        status, _, _ = self.call(
            "POST",
            "/api/loka-ai/generate",
            body=VALID,
            headers={"Content-Type": "application/json", "Origin": "http://jahat.example"},
        )
        self.assertEqual(status, 403)

    def test_missing_origin_is_rejected(self):
        status, _, _ = self.call(
            "POST",
            "/api/loka-ai/generate",
            body=VALID,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 403)

    def test_cross_site_fetch_metadata_is_rejected(self):
        status, _, _ = self.call(
            "POST",
            "/api/loka-ai/generate",
            body=VALID,
            headers=self.ai_headers(**{"Sec-Fetch-Site": "cross-site"}),
        )
        self.assertEqual(status, 403)

    def test_wrong_content_type_is_rejected(self):
        status, _, _ = self.call(
            "POST",
            "/api/loka-ai/generate",
            body=VALID,
            headers=self.ai_headers(**{"Content-Type": "text/plain"}),
        )
        self.assertEqual(status, 415)

    # -- body --------------------------------------------------------------
    def test_invalid_json_and_schema(self):
        self.assertEqual(
            self.call("POST", "/api/loka-ai/generate", raw_body="{bukan json", headers=self.ai_headers())[0], 400
        )
        broken = json.loads(json.dumps(VALID))
        broken["connections"][0]["provider"] = "penyedia-palsu"
        self.assertEqual(self.call("POST", "/api/loka-ai/generate", body=broken, headers=self.ai_headers())[0], 400)
        no_enabled = json.loads(json.dumps(VALID))
        no_enabled["connections"][0]["enabled"] = False
        self.assertEqual(self.call("POST", "/api/loka-ai/generate", body=no_enabled, headers=self.ai_headers())[0], 400)

    def test_oversized_body_is_rejected(self):
        big = json.dumps(VALID).encode("utf-8").replace(b'"notes": ""', f'"notes": "{"x" * 70000}"'.encode())
        status, _, _ = self.call("POST", "/api/loka-ai/generate", raw_body=big, headers=self.ai_headers())
        self.assertEqual(status, 413)

    def test_slow_body_is_rejected_without_hanging(self):
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        host = f"127.0.0.1:{self.port}"
        sock.sendall(
            (
                "POST /api/loka-ai/generate HTTP/1.1\r\n"
                f"Host: {host}\r\nOrigin: http://{host}\r\n"
                "Content-Type: application/json\r\nContent-Length: 200\r\n\r\n{\"a\":1"
            ).encode()
        )
        status = int(sock.recv(64).split(b" ")[1])
        sock.close()
        self.assertEqual(status, 408)

    def test_incomplete_bodies_do_not_exhaust_slots(self):
        sockets = []
        try:
            for _ in range(8):
                sock = socket.create_connection(("127.0.0.1", self.port), timeout=10)
                host = f"127.0.0.1:{self.port}"
                sock.sendall(
                    (
                        "POST /api/loka-ai/generate HTTP/1.1\r\n"
                        f"Host: {host}\r\nOrigin: http://{host}\r\n"
                        "Content-Type: application/json\r\nContent-Length: 100\r\n\r\n{"
                    ).encode()
                )
                sockets.append(sock)
            status, _, _ = self.call(
                "POST", "/api/loka-ai/generate", raw_body="{bukan json", headers=self.ai_headers()
            )
            self.assertEqual(status, 400, "permintaan ke-9 harus dilayani, bukan 429")
        finally:
            for sock in sockets:
                sock.close()

    # -- mode luring --------------------------------------------------------
    def test_offline_mode_never_calls_provider(self):
        status, _, body = self.call(
            "POST",
            "/api/loka-ai/generate",
            port=self.offline_port,
            body=VALID,
            headers=self.ai_headers(port=self.offline_port),
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIsNone(payload["text"])
        self.assertEqual(payload["attempts"], [])
        self.assertFalse(payload["cancelled"])

    def test_unknown_api_path_is_404(self):
        status, _, _ = self.call("POST", "/api/lain", body={}, headers=self.ai_headers())
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
