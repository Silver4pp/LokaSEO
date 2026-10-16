"""Uji perilaku pemanggilan AI: urutan cadangan, kode galat, dan pencatatan token."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaseo_desktop import ai  # noqa: E402


def connection(conn_id="c1", provider="openai", enabled=True):
    return {
        "id": conn_id,
        "label": f"Koneksi {conn_id}",
        "provider": provider,
        "model": "gpt-4.1-mini",
        "apiKey": "sk-test-key",
        "enabled": enabled,
    }


def payload(connections):
    return {
        "connections": connections,
        "task": "ideas",
        "context": {
            "business": "Kebun Kopi",
            "city": "Bogor",
            "domain": "",
            "topic": "kopi arabika",
            "notes": "",
        },
        "maxTokens": 512,
    }


def reply(status=200, content="Jawaban", finish=None, usage=None, body=None):
    if body is not None:
        return lambda *_: (status, body)
    data = {
        "choices": [{"message": {"content": content}, "finish_reason": finish}],
    }
    if usage is not None:
        data["usage"] = usage
    return lambda *_: (status, json.dumps(data).encode("utf-8"))


class RunAiTest(unittest.TestCase):
    def test_success_records_usage(self):
        result = ai.run_ai(
            payload([connection()]),
            fetcher=reply(usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}),
        )
        self.assertEqual(result["text"], "Jawaban")
        self.assertFalse(result["cancelled"])
        attempt = result["attempts"][0]
        self.assertEqual(attempt["status"], "success")
        self.assertEqual(attempt["code"], "ok")
        self.assertEqual(attempt["totalTokens"], 120)

    def test_missing_usage_stays_unknown(self):
        result = ai.run_ai(payload([connection()]), fetcher=reply())
        attempt = result["attempts"][0]
        self.assertIsNone(attempt["inputTokens"])
        self.assertIsNone(attempt["totalTokens"])

    def test_partial_usage_sums_only_when_both_known(self):
        result = ai.run_ai(
            payload([connection()]),
            fetcher=reply(usage={"prompt_tokens": 40}),
        )
        attempt = result["attempts"][0]
        self.assertEqual(attempt["inputTokens"], 40)
        self.assertIsNone(attempt["totalTokens"])

    def test_fallback_stops_at_first_success(self):
        calls = []

        def fetcher(url, headers, body, timeout):
            calls.append(url)
            if len(calls) == 1:
                return 401, b""
            return reply(usage={"total_tokens": 7})(url, headers, body, timeout)

        result = ai.run_ai(
            payload([connection("c1"), connection("c2", "groq"), connection("c3", "deepseek", False)]),
            fetcher=fetcher,
        )
        self.assertEqual(len(result["attempts"]), 2)
        self.assertEqual(result["attempts"][0]["code"], "auth")
        self.assertEqual(result["attempts"][1]["status"], "success")
        self.assertEqual(len(calls), 2, "koneksi yang gagal tidak boleh diulang")

    def test_all_failed_returns_no_text(self):
        result = ai.run_ai(
            payload([connection("c1"), connection("c2", "groq")]),
            fetcher=reply(500),
        )
        self.assertIsNone(result["text"])
        self.assertFalse(result["cancelled"])
        self.assertEqual([row["status"] for row in result["attempts"]], ["failed", "failed"])

    def test_status_codes(self):
        for status, expected in ((401, "auth"), (403, "auth"), (402, "quota"), (429, "rate_limit"), (400, "model"), (503, "provider")):
            with self.subTest(status=status):
                result = ai.run_ai(payload([connection()]), fetcher=reply(status))
                self.assertEqual(result["attempts"][0]["code"], expected)

    def test_truncated_answer_is_a_success(self):
        result = ai.run_ai(payload([connection()]), fetcher=reply(finish="length"))
        attempt = result["attempts"][0]
        self.assertEqual(attempt["status"], "success")
        self.assertEqual(attempt["code"], "truncated")

    def test_empty_and_malformed_answers(self):
        empty = ai.run_ai(payload([connection()]), fetcher=reply(content="   "))
        self.assertEqual(empty["attempts"][0]["code"], "empty")
        broken = ai.run_ai(payload([connection()]), fetcher=reply(body=b"{bukan json"))
        self.assertEqual(broken["attempts"][0]["code"], "invalid_response")

    def test_oversized_provider_body_rejected(self):
        huge = ai.run_ai(
            payload([connection()]),
            fetcher=reply(body=b"x" * (ai.config.MAX_PROVIDER_BODY_BYTES + 1)),
        )
        self.assertEqual(huge["attempts"][0]["code"], "invalid_response")

    def test_network_error_maps_to_network(self):
        def boom(*_):
            raise OSError("tidak terhubung")

        result = ai.run_ai(payload([connection()]), fetcher=boom)
        self.assertEqual(result["attempts"][0]["code"], "network")

    def test_timeout_is_reported(self):
        def slow(*_):
            raise TimeoutError("lewat batas")

        result = ai.run_ai(payload([connection()]), fetcher=slow)
        self.assertEqual(result["attempts"][0]["code"], "timeout")

    def test_cancelled_before_start(self):
        result = ai.run_ai(payload([connection()]), fetcher=reply(), is_cancelled=lambda: True)
        self.assertTrue(result["cancelled"])
        self.assertEqual(result["attempts"], [])

    def test_cancelled_during_attempt(self):
        state = {"count": 0}

        def cancel():
            state["count"] += 1
            return state["count"] > 1

        result = ai.run_ai(payload([connection()]), fetcher=reply(), is_cancelled=cancel)
        self.assertTrue(result["cancelled"])
        self.assertIsNone(result["text"])

    def test_egress_allowlist_blocks_unknown_host(self):
        with self.assertRaises(ai.EgressError):
            ai.default_fetcher("https://contoh.example/v1/chat", {}, b"{}", 1.0)

    def test_known_endpoints_allowed_by_allowlist(self):
        self.assertEqual(
            ai.config.ALLOWED_EGRESS_HOSTS,
            {"api.openai.com", "openrouter.ai", "api.deepseek.com", "api.groq.com"},
        )


if __name__ == "__main__":
    unittest.main()
