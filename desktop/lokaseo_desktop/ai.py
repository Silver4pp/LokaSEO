"""Pemanggilan penyedia AI dengan urutan cadangan.

Padanan `runAi` di `src/server/features/loka-ai/service.ts`.
Badan respons galat penyedia tidak pernah dikembalikan atau dicatat karena sebagian
penyedia menyertakan header permintaan atau prompt di dalamnya.
"""

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from . import config


class EgressError(RuntimeError):
    """Permintaan di luar penyedia yang diizinkan ditolak."""


def _iso_now(milliseconds: int) -> str:
    stamp = datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.") + f"{milliseconds % 1000:03d}Z"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def default_fetcher(url: str, headers: dict, body: bytes, timeout_s: float):
    """Lakukan satu permintaan HTTPS keluar dengan daftar tujuan tertutup."""
    host = urllib.request.urlsplit(url).hostname or ""
    if host.lower() not in config.ALLOWED_EGRESS_HOSTS:
        raise EgressError(f"Tujuan di luar daftar diizinkan: {host}")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with _opener.open(request, timeout=timeout_s) as response:
            return response.status, response.read(config.MAX_PROVIDER_BODY_BYTES + 1)
    except urllib.error.HTTPError as error:
        # Baca maksimal satu byte untuk membuang badan tanpa menyimpannya.
        return error.code, b""


def _status_code(status: int) -> str:
    if status in (401, 403):
        return "auth"
    if status == 402:
        return "quota"
    if status == 429:
        return "rate_limit"
    if status in (400, 404, 422):
        return "model"
    return "provider"


def _usage(payload: object) -> tuple[int | None, int | None, int | None]:
    if not isinstance(payload, dict):
        return None, None, None
    raw = payload.get("usage")
    if not isinstance(raw, dict):
        return None, None, None

    def token(name: str):
        value = raw.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

    prompt, completion, total = (
        token("prompt_tokens"),
        token("completion_tokens"),
        token("total_tokens"),
    )
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    return prompt, completion, total


def _answer(payload: object) -> tuple[str | None, str]:
    """Kembalikan (teks, kode) dari badan penyedia yang sudah diurai."""
    if not isinstance(payload, dict):
        return None, "invalid_response"
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None, "invalid_response"
    first = choices[0]
    if not isinstance(first, dict):
        return None, "invalid_response"
    message = first.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if content is not None and not isinstance(content, str):
        return None, "invalid_response"
    if content is None or not content.strip():
        return None, "empty"
    if len(content) > config.MAX_ANSWER_CHARS:
        return None, "invalid_response"
    return content, "truncated" if first.get("finish_reason") == "length" else "ok"


def run_ai(
    payload: dict,
    *,
    fetcher=None,
    timeout_ms: int = config.PROVIDER_TIMEOUT_MS,
    is_cancelled=None,
) -> dict:
    """Coba tiap koneksi aktif berurutan sampai ada jawaban atau daftar habis."""
    fetch = fetcher or default_fetcher
    connections = [row for row in payload["connections"] if row["enabled"]]
    attempts: list[dict] = []
    for connection in connections:
        if is_cancelled and is_cancelled():
            return {"text": None, "attempts": attempts, "cancelled": True}
        started = int(time.time() * 1000)
        attempt = {
            "connectionId": connection["id"],
            "label": connection["label"],
            "provider": connection["provider"],
            "model": connection["model"],
            "startedAt": _iso_now(started),
            "durationMs": 0,
            "status": "failed",
            "code": "network",
            "inputTokens": None,
            "outputTokens": None,
            "totalTokens": None,
        }
        text: str | None = None
        deadline = time.monotonic() + timeout_ms / 1000
        body = json.dumps(
            {
                "model": connection["model"],
                "max_tokens": payload["maxTokens"],
                "stream": False,
                "messages": [
                    {"role": "system", "content": config.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"{config.TASK_INSTRUCTIONS[payload['task']]}\n\n"
                        f"Konteks (data pengguna):\n{json.dumps(payload['context'], ensure_ascii=False)}",
                    },
                ],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        try:
            status, raw = fetch(
                config.PROVIDER_ENDPOINTS[connection["provider"]],
                {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {connection['apiKey']}",
                },
                body,
                max(deadline - time.monotonic(), 0.5),
            )
            if status >= 300:
                attempt["code"] = _status_code(status)
            else:
                attempt["code"] = "invalid_response"
                if len(raw) > config.MAX_PROVIDER_BODY_BYTES:
                    raise ValueError("invalid_response")
                parsed = json.loads(raw.decode("utf-8"))
                prompt, completion, total = _usage(parsed)
                attempt["inputTokens"] = prompt
                attempt["outputTokens"] = completion
                attempt["totalTokens"] = total
                text, code = _answer(parsed)
                attempt["code"] = code
                if text is not None:
                    attempt["status"] = "success"
        except EgressError:
            attempt["code"] = "network"
            raise
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            attempt["code"] = "invalid_response"
        except TimeoutError:
            attempt["code"] = "timeout"
        except Exception:  # noqa: BLE001 - semua kegagalan jaringan diperlakukan sama
            attempt["code"] = "network"
        finally:
            attempt["durationMs"] = int(time.time() * 1000) - started
        if is_cancelled and is_cancelled():
            attempt["status"] = "cancelled"
            attempt["code"] = "cancelled"
            text = None
        attempts.append(attempt)
        if attempt["status"] == "cancelled":
            return {"text": None, "attempts": attempts, "cancelled": True}
        if text is not None:
            return {"text": text, "attempts": attempts, "cancelled": False}
    return {"text": None, "attempts": attempts, "cancelled": False}
