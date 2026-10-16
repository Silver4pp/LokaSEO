"""Validasi permintaan AI tanpa dependency eksternal.

Aturan ini adalah padanan `aiRequestSchema` di `src/shared/loka-ai.ts`.
Bila aturan di sisi klien berubah, ubah keduanya bersamaan.
"""

import re

from . import config

PROVIDERS = frozenset(config.PROVIDER_ENDPOINTS)
TASKS = frozenset(config.TASK_INSTRUCTIONS)
MODEL_PATTERN = re.compile(r"^[a-zA-Z0-9_./:@+-]+$")
KEY_PATTERN = re.compile(r"^[\x21-\x7e]+$")

INVALID_MESSAGE = (
    "Periksa koneksi AI, model, dan topik. Jangan masukkan API key ke kolom selain "
    "API key."
)


class ValidationError(ValueError):
    """Permintaan tidak memenuhi skema."""

    def __init__(self, message: str = INVALID_MESSAGE) -> None:
        super().__init__(message)


def _fail() -> None:
    raise ValidationError()


def _text(value: object, minimum: int, maximum: int, *, trim: bool = True) -> str:
    if not isinstance(value, str):
        _fail()
    if len(value) > maximum * 4:  # hindari pemangkasan string raksasa
        _fail()
    result = value.strip() if trim else value
    if len(result) < minimum or len(result) > maximum:
        _fail()
    return result


def _connection(raw: object) -> dict:
    if not isinstance(raw, dict):
        _fail()
    provider = raw.get("provider")
    if provider not in PROVIDERS:
        _fail()
    model = _text(raw.get("model"), 1, 150)
    if not MODEL_PATTERN.match(model):
        _fail()
    api_key = _text(raw.get("apiKey"), 4, 512)
    if not KEY_PATTERN.match(api_key):
        _fail()
    enabled = raw.get("enabled")
    if not isinstance(enabled, bool):
        _fail()
    return {
        "id": _text(raw.get("id"), 1, 80),
        "label": _text(raw.get("label"), 1, 50),
        "provider": provider,
        "model": model,
        "apiKey": api_key,
        "enabled": enabled,
    }


def validate_request(raw: object) -> dict:
    """Kembalikan permintaan yang sudah dinormalkan atau naikkan `ValidationError`."""
    if not isinstance(raw, dict):
        _fail()
    connections = raw.get("connections")
    if not isinstance(connections, list) or not 1 <= len(connections) <= 5:
        _fail()
    parsed = [_connection(row) for row in connections]
    if len({row["id"] for row in parsed}) != len(parsed):
        _fail()
    if not any(row["enabled"] for row in parsed):
        _fail()
    task = raw.get("task")
    if task not in TASKS:
        _fail()
    context = raw.get("context")
    if not isinstance(context, dict):
        _fail()
    max_tokens = raw.get("maxTokens")
    if not isinstance(max_tokens, int) or isinstance(max_tokens, bool):
        _fail()
    if not 128 <= max_tokens <= 4000:
        _fail()
    return {
        "connections": parsed,
        "task": task,
        "context": {
            "business": _text(context.get("business"), 1, 80),
            "city": _text(context.get("city", ""), 0, 80, trim=False),
            "domain": _text(context.get("domain", ""), 0, 250, trim=False),
            "topic": _text(context.get("topic"), 1, 500),
            "notes": _text(context.get("notes", ""), 0, 12_000, trim=False),
        },
        "maxTokens": max_tokens,
    }
