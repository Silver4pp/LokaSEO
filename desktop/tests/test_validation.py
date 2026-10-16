"""Uji skema permintaan AI, disamakan dengan `aiRequestSchema` sisi klien."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaseo_desktop.validation import ValidationError, validate_request  # noqa: E402


def payload(**changes):
    base = {
        "connections": [
            {
                "id": "c1",
                "label": "Utama",
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "apiKey": "sk-abcdef",
                "enabled": True,
            }
        ],
        "task": "ideas",
        "context": {"business": "Kebun Kopi", "city": "Bogor", "domain": "", "topic": "kopi", "notes": ""},
        "maxTokens": 512,
    }
    base.update(changes)
    return base


class ValidationTest(unittest.TestCase):
    def test_valid_payload_is_trimmed(self):
        result = validate_request(
            payload(context={"business": "  Kebun Kopi  ", "city": "", "domain": "", "topic": " kopi ", "notes": ""})
        )
        self.assertEqual(result["context"]["business"], "Kebun Kopi")
        self.assertEqual(result["context"]["topic"], "kopi")

    def test_rejects_each_boundary(self):
        cases = {
            "tanpa koneksi": payload(connections=[]),
            "terlalu banyak koneksi": payload(
                connections=[
                    {"id": f"c{i}", "label": "x", "provider": "openai", "model": "m", "apiKey": "sk-aa", "enabled": True}
                    for i in range(6)
                ]
            ),
            "id duplikat": payload(
                connections=[
                    {"id": "sama", "label": "a", "provider": "openai", "model": "m", "apiKey": "sk-aa", "enabled": True},
                    {"id": "sama", "label": "b", "provider": "groq", "model": "m", "apiKey": "sk-bb", "enabled": True},
                ]
            ),
            "tidak ada yang aktif": payload(connections=[{**payload()["connections"][0], "enabled": False}]),
            "provider asing": payload(connections=[{**payload()["connections"][0], "provider": "lain"}]),
            "model berkarakter aneh": payload(connections=[{**payload()["connections"][0], "model": "model aneh!"}]),
            "key berisi spasi": payload(connections=[{**payload()["connections"][0], "apiKey": "sk ada spasi"}]),
            "key terlalu pendek": payload(connections=[{**payload()["connections"][0], "apiKey": "abc"}]),
            "task asing": payload(task="lain"),
            "topik kosong": payload(context={"business": "a", "city": "", "domain": "", "topic": "   ", "notes": ""}),
            "catatan terlalu panjang": payload(
                context={"business": "a", "city": "", "domain": "", "topic": "b", "notes": "x" * 12_001}
            ),
            "maxTokens kecil": payload(maxTokens=127),
            "maxTokens besar": payload(maxTokens=4001),
            "maxTokens bukan angka": payload(maxTokens="512"),
            "bukan objek": "bukan objek",
        }
        for name, value in cases.items():
            with self.subTest(kasus=name), self.assertRaises(ValidationError):
                validate_request(value)

    def test_api_key_is_required_not_optional(self):
        with self.assertRaises(ValidationError):
            validate_request(payload(connections=[{**payload()["connections"][0], "apiKey": ""}]))


if __name__ == "__main__":
    unittest.main()
