"""Pemeriksaan Host/Origin, header keamanan, dan pembacaan body dengan batas.

Padanan `studio/http-security.ts`. Pada aplikasi desktop server mengikat hanya ke
loopback, sehingga pemeriksaan ini melindungi dari halaman web lain di komputer yang
sama (DNS rebinding dan permintaan lintas situs), bukan dari pengguna sendiri.
"""

import os
import re
import select
import socket
from urllib.parse import urlsplit

from . import config

BAD_HOST_CHARS = re.compile(r"[\s/@?#\\]")
LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "[::1]"})


class BodyError(Exception):
    """Body permintaan ditolak; `status` menentukan kode balasan."""

    def __init__(self, status: int) -> None:
        super().__init__("Body permintaan tidak valid.")
        self.status = status


def allowed_host(host: str | None) -> bool:
    if not host or BAD_HOST_CHARS.search(host):
        return False
    lowered = host.lower()
    try:
        parts = urlsplit(f"http://{lowered}")
    except ValueError:
        return False
    if parts.netloc != lowered or not parts.hostname:
        return False
    hostname = parts.hostname
    if hostname in LOCAL_HOSTNAMES:
        return True
    public_origin = os.environ.get("LOKA_PUBLIC_ORIGIN")
    if public_origin:
        try:
            configured = urlsplit(public_origin)
            if configured.scheme == "https" and configured.netloc == lowered:
                return True
        except ValueError:
            return False
    sandbox = os.environ.get("E2B_SANDBOX_ID")
    return bool(sandbox and lowered == f"{os.environ.get('PORT', '3000')}-{sandbox}.e2b.app")


def allowed_origin(host: str | None, origin: str | None, fetch_site: str | None) -> bool:
    """Terima hanya permintaan dari halaman aplikasi yang sama."""
    if not allowed_host(host):
        return False
    if not origin:
        return False
    try:
        parts = urlsplit(origin)
    except ValueError:
        return False
    if f"{parts.scheme}://{parts.netloc}" != origin or parts.netloc != (host or "").lower():
        return False
    local = parts.hostname in LOCAL_HOSTNAMES
    scheme_ok = parts.scheme == "https" or (local and parts.scheme == "http")
    site_ok = fetch_site is None or fetch_site in ("same-origin", "none")
    return scheme_ok and site_ok


def security_headers() -> dict[str, str]:
    ancestors = os.environ.get("LOKA_FRAME_ANCESTORS")
    if ancestors is None:
        ancestors = "" if os.environ.get("E2B_SANDBOX_ID") else "'self'"
    policy = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; form-action 'self'; frame-src 'none'"
    )
    if ancestors:
        policy = f"{policy}; frame-ancestors {ancestors}"
    return {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Content-Security-Policy": policy,
        "Cross-Origin-Resource-Policy": "same-origin",
    }


def client_gone(sock: socket.socket) -> bool:
    """Perkirakan apakah klien sudah menutup koneksi, untuk membatalkan pekerjaan."""
    try:
        readable, _, _ = select.select([sock], [], [], 0)
        if not readable:
            return False
        return sock.recv(1, socket.MSG_PEEK) == b""
    except OSError:
        return True
    except (BlockingIOError, InterruptedError):
        return False


def read_body(
    rfile,
    sock: socket.socket,
    content_length: str | None,
    transfer_encoding: str | None,
    *,
    max_bytes: int = config.MAX_BODY_BYTES,
    timeout_ms: int = config.BODY_TIMEOUT_MS,
) -> bytes:
    """Baca body dengan batas ukuran dan tenggat absolut.

    Mengembalikan byte mentah; pemanggil yang mengurai JSON agar galat format
    dilaporkan terpisah dari galat ukuran.
    """
    try:
        length = int(content_length) if content_length else None
    except ValueError:
        raise BodyError(400) from None
    if length is not None and length < 0:
        raise BodyError(400)
    if length is not None and length > max_bytes:
        raise BodyError(413)
    chunked = bool(transfer_encoding and "chunked" in transfer_encoding.lower())
    if length is None and not chunked:
        return b""

    previous = sock.gettimeout()
    sock.settimeout(timeout_ms / 1000)
    received = bytearray()
    try:
        if length is not None:
            while len(received) < length:
                chunk = rfile.read(length - len(received))
                if not chunk:
                    raise BodyError(400)
                received += chunk
        else:  # chunked tanpa Content-Length: baca sampai akhir stream
            while True:
                line = rfile.readline(64)
                if not line:
                    break
                try:
                    size = int(line.strip().split(b";")[0], 16)
                except ValueError:
                    raise BodyError(400) from None
                if size == 0:
                    rfile.readline(64)
                    break
                received += rfile.read(size)
                rfile.read(2)
                if len(received) > max_bytes:
                    raise BodyError(413)
    except (TimeoutError, socket.timeout):
        raise BodyError(408) from None
    except OSError:
        raise BodyError(400) from None
    finally:
        try:
            sock.settimeout(previous)
        except OSError:
            pass
    if len(received) > max_bytes:
        raise BodyError(413)
    return bytes(received)
