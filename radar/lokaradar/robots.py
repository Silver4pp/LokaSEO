"""Pemeriksaan robots.txt, di-cache per host.

Aturan yang dipakai:

- robots.txt tidak ada (4xx selain 401/403) -> boleh menjelajah.
- robots.txt menjawab 401/403/5xx atau gagal diambil -> ditolak (aman secara bawaan).
- `Disallow` yang berlaku untuk agen kita -> ditolak.
- `Crawl-delay` -> dipakai sebagai jeda minimum bila lebih besar dari bawaan.

Catatan penting: aturan diambil per host, tetapi **dinilai per alamat**. Halaman yang
berbeda dapat punya izin berbeda, jadi penilaian tidak boleh memakai alamat root.
"""

import logging
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from . import config

LOG = logging.getLogger("lokaradar")

try:  # protego dipasang bersama Scrapling; radar tetap jalan tanpa itu
    from protego import Protego
except ImportError:  # pragma: no cover
    Protego = None


@dataclass
class RobotsResult:
    allowed: bool
    crawl_delay: float | None = None
    sitemaps: list[str] = field(default_factory=list)
    reason: str = ""


class _SimpleRules:
    """Parser robots.txt sederhana untuk lingkungan tanpa protego."""

    def __init__(self, text: str) -> None:
        self.disallow: list[str] = []
        self.allow: list[str] = []
        self.crawl_delay: float | None = None
        self.sitemaps: list[str] = []
        active = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                active = value == "*" or value.lower().startswith("lokaradar")
            elif key == "disallow" and active:
                self.disallow.append(value)
            elif key == "allow" and active:
                self.allow.append(value)
            elif key == "crawl-delay" and active:
                try:
                    self.crawl_delay = float(value)
                except ValueError:
                    pass
            elif key == "sitemap":
                self.sitemaps.append(value)

    def can_fetch(self, url: str, user_agent: str = "") -> bool:  # noqa: ARG002 - tanda tangan seragam
        path = urlsplit(url).path or "/"
        for rule in sorted(self.allow, key=len, reverse=True):
            if rule and path.startswith(rule):
                return True
        for rule in sorted(self.disallow, key=len, reverse=True):
            if rule == "/" or (rule and path.startswith(rule)):
                return False
        return True


@dataclass
class _HostRules:
    """Aturan satu host, sudah diurai dan siap dinilai untuk alamat apa pun."""

    reason: str
    parser: object | None = None
    allow_all: bool = False
    crawl_delay: float | None = None
    sitemaps: list[str] = field(default_factory=list)

    def can_fetch(self, url: str) -> bool:
        if self.allow_all:
            return True
        if self.parser is None:
            return False
        if Protego is not None and isinstance(self.parser, Protego):
            # Protego memakai urutan (url, user-agent).
            return bool(self.parser.can_fetch(url, config.USER_AGENT))
        return bool(self.parser.can_fetch(url, config.USER_AGENT))


class RobotsCache:
    """Simpan aturan per host agar robots.txt tidak diambil berulang kali."""

    def __init__(self, fetcher, ttl_hours: float = config.ROBOTS_CACHE_HOURS) -> None:
        self.fetcher = fetcher
        self.ttl = ttl_hours * 3600
        self._entries: dict[str, tuple[float, _HostRules]] = {}

    @staticmethod
    def host_of(url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.netloc}"

    def rules_for(self, url: str, *, refresh: bool = False) -> _HostRules:
        host = self.host_of(url)
        now = time.time()
        cached = self._entries.get(host)
        if cached and not refresh and now - cached[0] < self.ttl:
            return cached[1]
        rules = self._load(host)
        self._entries[host] = (now, rules)
        return rules

    def check(self, url: str, *, refresh: bool = False) -> RobotsResult:
        rules = self.rules_for(url, refresh=refresh)
        allowed = rules.can_fetch(url)
        reason = rules.reason if allowed else (rules.reason or "robots.txt melarang alamat ini")
        if not allowed and rules.parser is not None:
            reason = "robots.txt melarang alamat ini"
        return RobotsResult(
            allowed=allowed,
            crawl_delay=rules.crawl_delay,
            sitemaps=list(rules.sitemaps),
            reason=reason,
        )

    def _load(self, host: str) -> _HostRules:
        target = f"{host}/robots.txt"
        try:
            response = self.fetcher(target)
        except Exception as error:  # noqa: BLE001 - gagal ambil dianggap tolak
            LOG.warning("robots.txt %s tidak dapat diambil (%s); penjelajahan ditolak.", host, error)
            return _HostRules("robots.txt tidak dapat diambil")
        status = int(getattr(response, "status", 0) or 0)
        if status in (401, 403):
            return _HostRules("robots.txt menolak akses")
        if status >= 500:
            return _HostRules(f"robots.txt menjawab {status}")
        if status >= 400:
            return _HostRules("robots.txt tidak ada", allow_all=True)
        text = _body_text(response)
        delay: float | None = None
        if Protego is not None:
            parser = Protego.parse(text)
            try:
                value = parser.crawl_delay(config.USER_AGENT)
                delay = float(value) if value is not None else None
            except Exception:  # noqa: BLE001 - sebagian versi tidak mendukung argumen
                delay = None
            return _HostRules("protego", parser, crawl_delay=delay, sitemaps=list(parser.sitemaps))
        rules = _SimpleRules(text)
        return _HostRules(
            "parser sederhana",
            rules,
            crawl_delay=rules.crawl_delay,
            sitemaps=list(rules.sitemaps),
        )


def _body_text(response) -> str:
    """Isi robots.txt dari objek Page maupun respons pengambil.

    Objek `Page` menaruh isi di `.html`; respons Scrapling di `.html_content`.
    Jangan mengandalkan `.text` saja: pada Scrapling atribut itu bukan teks berkas.
    """
    for attribute in ("text", "body", "content", "html_content", "html"):
        value = getattr(response, attribute, None)
        if isinstance(value, bytes):
            value = value.decode("utf-8", "ignore")
        if isinstance(value, str) and value.strip():
            return value
    return ""
