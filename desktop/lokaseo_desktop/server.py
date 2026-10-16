"""Server lokal aplikasi desktop LokaSEO.

Hanya mengikat ke alamat yang diminta (bawaan loopback), menyajikan berkas build
yang sudah ada, dan menyediakan satu titik masuk AI. Tidak ada telemetri, tidak ada
permintaan keluar selain ke penyedia AI yang dipilih pengguna.
"""

import json
import logging
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from . import config, jadwal, kesiapan, pages, radar
from .ai import EgressError, run_ai
from .security import (
    BodyError,
    allowed_origin,
    allowed_host,
    client_gone,
    read_body,
    security_headers,
)
from .validation import ValidationError, validate_request

LOG = logging.getLogger("lokaseo")
DOT_SEGMENT = re.compile(r"(^|/)\.")
STOP_REQUESTED = threading.Event()
# Halaman HTML (termasuk skrip terpisah) ada di `pages.py`.
STOP_PAGE = pages.HENTIKAN_PAGE

TOKEN_BUSY = {
    "readers": 0,
    "running": 0,
    "rate": {},
    "lock": threading.Lock(),
}


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _batas(nilai: str, bawaan: int, maksimum: int) -> int:
    """Ubah nilai dari antarmuka menjadi angka yang aman."""
    try:
        angka = int(nilai)
    except (TypeError, ValueError):
        return bawaan
    return max(1, min(angka, maksimum))


def _url_radar_sah(url: str) -> bool:
    """Hanya alamat http(s) yang wajar; sisanya ditolak sebelum disimpan."""
    if not url or len(url) > 500 or any(karakter.isspace() for karakter in url):
        return False
    bagian = urlsplit(url)
    return bagian.scheme in ("http", "https") and bool(bagian.netloc)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = f"{config.APP_NAME}/{config.APP_VERSION}"
    sys_version = ""

    # -- util ---------------------------------------------------------------
    def version_string(self) -> str:  # noqa: D102 - jangan bocorkan versi Python
        return f"{config.APP_NAME}/{config.APP_VERSION}"

    def _send(
        self,
        status: int,
        body: bytes = b"",
        content_type: str = "text/plain; charset=utf-8",
        extra: dict | None = None,
    ) -> None:
        if self.wfile.closed:
            return
        try:
            self.send_response(status)
            for key, value in security_headers().items():
                self.send_header(key, value)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if body and self.command != "HEAD":
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            LOG.info("Klien menutup koneksi sebelum balasan selesai.")
            self.close_connection = True

    def _json(self, status: int, value: object) -> None:
        self._send(
            status,
            _json_bytes(value),
            "application/json; charset=utf-8",
            {"Cache-Control": "no-store"},
        )

    def _reject_host(self) -> bool:
        if allowed_host(self.headers.get("Host")):
            return False
        self._send(421, "Host tidak diizinkan.".encode("utf-8"))
        return True

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003 - API induk
        LOG.info("%s %s", self.address_string(), fmt % args)

    # -- rute ---------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 - API induk
        if self._reject_host():
            return
        path = urlsplit(self.path).path
        if path in ("/hentikan", "/hentikan/"):
            self._send(200, STOP_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/lokaseo/info":
            self._json(
                200,
                {
                    "mode": "desktop",
                    "versi": config.APP_VERSION,
                    "luring": bool(self.server.offline),  # type: ignore[attr-defined]
                    "hentikan": "/hentikan",
                    "radar": radar.tersedia(),
                },
            )
            return
        if path == "/api/kesiapan":
            # Sengaja **tidak** lewat pemeriksaan ketersediaan radar: justru saat
            # radar gagal dimuat, laporan ini yang paling dibutuhkan.
            alamat = f"http://{self.headers.get('Host') or '127.0.0.1'}"
            self._json(200, kesiapan.periksa(alamat=alamat, luring=bool(self.server.offline)))  # type: ignore[attr-defined]
            return
        if path in ("/radar", "/radar/"):
            self._send(200, pages.RADAR_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/radar.js":
            self._send(200, pages.RADAR_JS.encode("utf-8"), config.MIME_TYPES[".js"])
            return
        if path == "/radar-tautan.js":
            self._send(200, pages.RADAR_LINK_JS.encode("utf-8"), config.MIME_TYPES[".js"])
            return
        if path == "/hentikan.js":
            self._send(200, pages.HENTIKAN_JS.encode("utf-8"), config.MIME_TYPES[".js"])
            return
        if path.startswith("/api/radar/"):
            self._radar_get(path)
            return
        self._serve_static()

    def do_HEAD(self) -> None:  # noqa: N802
        if self._reject_host():
            return
        self._serve_static(head_only=True)

    def do_OPTIONS(self) -> None:  # noqa: N802
        # Tanpa header CORS: browser lain tidak boleh membaca balasan.
        if self._reject_host():
            return
        self._send(405, b"")

    def do_POST(self) -> None:  # noqa: N802
        if self._reject_host():
            return
        path = urlsplit(self.path).path
        if path == "/api/lokaseo/hentikan":
            self._stop_app()
            return
        if path.startswith("/api/radar/"):
            self._radar_post(path)
            return
        if path != "/api/loka-ai/generate":
            self._send(404, "Tidak ditemukan.".encode("utf-8"))
            return
        self._generate()

    def do_PUT(self) -> None:  # noqa: N802
        if self._reject_host():
            return
        self._send(405, b"")

    do_DELETE = do_PUT
    do_PATCH = do_PUT

    # -- berkas statis ------------------------------------------------------
    def _serve_static(self, head_only: bool = False) -> None:
        root: Path = self.server.static_root  # type: ignore[attr-defined]
        pathname = unquote(urlsplit(self.path).path)
        if DOT_SEGMENT.search(pathname):  # segmen tersembunyi dan ".." ditolak
            self._send(404, "Tidak ditemukan.".encode("utf-8"))
            return
        relative = "index.html" if pathname in ("", "/") else pathname.lstrip("/")
        extension = os.path.splitext(relative)[1].lower()
        content_type = config.MIME_TYPES.get(extension)
        if not content_type:
            self._send(404, "Tidak ditemukan.".encode("utf-8"))
            return
        candidate = root / relative
        try:
            if not candidate.resolve().is_relative_to(root):
                raise ValueError("keluar dari direktori build")
            info = candidate.stat()
            if not candidate.is_file() or info.st_size > config.STATIC_MAX_BYTES:
                raise ValueError("bukan berkas biasa")
            body = candidate.read_bytes()
        except (OSError, ValueError):
            self._send(
                404,
                "Tidak ditemukan. Jalankan build:loka terlebih dahulu.".encode("utf-8"),
            )
            return
        if relative == "index.html":
            body = self._sisipkan_tautan_radar(body)
        cache = (
            "public, max-age=31536000, immutable"
            if pathname.startswith("/assets/")
            else "no-store"
        )
        self._send(200, body, content_type, {"Cache-Control": cache})

    # -- radar --------------------------------------------------------------
    @staticmethod
    def _sisipkan_tautan_radar(body: bytes) -> bytes:
        """Tambahkan tombol menuju /radar pada halaman aplikasi.

        Dipasang dari sisi server supaya antarmuka tidak perlu dibangun ulang
        hanya untuk menambah satu tautan. Hanya ditambahkan bila halaman belum
        memuatnya, agar tidak pernah dobel.
        """
        if not radar.tersedia() or pages.RADAR_LINK_TAG.encode("utf-8") in body:
            return body
        penanda = b"</body>"
        if penanda not in body:
            return body
        return body.replace(penanda, pages.RADAR_LINK_TAG.encode("utf-8") + penanda, 1)

    def _radar_siap(self) -> bool:
        if radar.tersedia():
            return True
        self._json(
            503,
            {
                "error": (
                    "Modul radar tidak ditemukan di dalam paket aplikasi. "
                    "Fitur pemantauan tidak tersedia, fitur lain tetap berjalan."
                )
            },
        )
        return False

    def _radar_get(self, path: str) -> None:
        if self._reject_host():
            return
        if not self._radar_siap():
            return
        try:
            if path == "/api/radar/sasaran/ekspor":
                # Berkasnya dikirim sebagai unduhan supaya pengguna bisa menyimpannya
                # atau mengirimkannya ke komputer lain. Isinya sama dengan yang
                # ditampilkan di halaman; tidak ada data yang dikirim ke mana pun.
                berkas = radar.ekspor_sasaran()
                nama = berkas.get("nama_berkas") or "sasaran-radar.json"
                self._send(
                    200,
                    _json_bytes(berkas),
                    "application/json; charset=utf-8",
                    {
                        "Cache-Control": "no-store",
                        "Content-Disposition": f'attachment; filename="{nama}"',
                    },
                )
                return
            if path == "/api/radar/info":
                nilai = radar.status()
                nilai["luring"] = bool(self.server.offline)  # type: ignore[attr-defined]
                self._json(200, nilai)
                return
            if path == "/api/radar/sasaran":
                self._json(200, radar.sasaran())
                return
            if path == "/api/radar/perubahan":
                query = parse_qs(urlsplit(self.path).query)
                batas = _batas(query.get("limit", ["50"])[0], bawaan=50, maksimum=200)
                self._json(200, radar.perubahan(since=query.get("since", [None])[0], limit=batas))
                return
            if path == "/api/radar/jenis":
                self._json(200, radar.daftar_jenis())
                return
            if path == "/api/radar/profil":
                self._json(200, radar.profil_usaha() or {})
                return
            if path == "/api/radar/jadwal":
                self._json(200, radar.jadwal())
                return
            if path == "/api/radar/peramban":
                # ?ulang=1 dipakai tombol "Periksa ulang": paksa pencarian
                # peramban dijalankan dari awal (berguna setelah memasang Edge
                # atau Chrome saat aplikasi sedang terbuka).
                query = parse_qs(urlsplit(self.path).query)
                ulang = str(query.get("ulang", [""])[0]).strip().lower() in ("1", "true", "ya")
                self._json(200, radar.peramban(refresh=ulang))
                return
            if path == "/api/radar/ringkasan":
                query = parse_qs(urlsplit(self.path).query)
                hari = _batas(query.get("hari", ["7"])[0], bawaan=7, maksimum=90)
                self._json(200, radar.ringkasan(hari=hari))
                return
            if path == "/api/radar/papan":
                query = parse_qs(urlsplit(self.path).query)
                hari = _batas(query.get("days", ["30"])[0], bawaan=30, maksimum=365)
                self._json(200, radar.papan(days=hari) or {})
                return
            if path == "/api/radar/laporan":
                laporan = radar.laporan_terbaru()
                if laporan is None:
                    self._json(404, {"error": "Belum ada laporan. Jalankan pemeriksaan lalu buat laporan."})
                    return
                self._json(200, laporan)
                return
        except radar.RadarError as error:
            self._json(503, {"error": str(error)})
            return
        except Exception:  # noqa: BLE001 - kesalahan radar tidak boleh mematikan server
            LOG.exception("Permintaan radar gagal")
            self._json(500, {"error": "Permintaan radar tidak dapat diselesaikan."})
            return
        self._json(404, {"error": "Tidak ditemukan."})

    def _radar_post(self, path: str) -> None:
        if not allowed_origin(
            self.headers.get("Host"),
            self.headers.get("Origin"),
            self.headers.get("Sec-Fetch-Site"),
        ):
            self._json(403, {"error": "Origin atau host tidak diizinkan."})
            return
        if not self._radar_siap():
            return
        if path == "/api/radar/periksa" and self.server.offline:  # type: ignore[attr-defined]
            self._json(
                409,
                {"error": "Mode luring aktif. Pemeriksaan butuh jaringan, jadi tidak dijalankan."},
            )
            return
        try:
            besar = path == "/api/radar/sasaran/impor"
            isi = self._baca_json(max_bytes=config.RADAR_MAX_IMPORT_BYTES if besar else None)
        except ValueError as error:
            self._json(400, {"error": str(error)})
            return
        try:
            if path == "/api/radar/periksa":
                if radar.sedang_berjalan():
                    self._json(409, {"error": "Pemeriksaan lain masih berjalan. Tunggu sampai selesai."})
                    return
                maksimum = _batas(str(isi.get("max_pages", config.RADAR_MAX_PAGES)), config.RADAR_MAX_PAGES, 200)
                pekerjaan = radar.mulai_periksa(max_pages=maksimum, hanya=isi.get("target"))
                LOG.info("Pemeriksaan radar dimulai dari antarmuka (pekerjaan #%s).", pekerjaan["id"])
                self._json(202, pekerjaan)
                return
            if path == "/api/radar/tambah":
                url = str(isi.get("url", "")).strip()
                if not _url_radar_sah(url):
                    self._json(400, {"error": "Alamat harus dimulai dengan http:// atau https://"})
                    return
                label = str(isi.get("label", "")).strip()[:60]
                jenis = str(isi.get("jenis", "halaman")).strip().lower()
                if jenis not in ("halaman", "harga", "layanan", "reputasi"):
                    self._json(400, {"error": "Jenis pantauan tidak dikenal."})
                    return
                if len(radar.sasaran()) >= config.RADAR_MAX_TARGETS:
                    self._json(
                        409,
                        {"error": f"Sasaran sudah mencapai batas {config.RADAR_MAX_TARGETS}. Hapus yang tidak dipakai."},
                    )
                    return
                self._json(200, radar.tambah(url, label, jenis))
                return
            if path == "/api/radar/profil":
                # Jalur utama: pengaturan proyek aktif LokaSEO (jenis usaha, nama,
                # kota, domain) dibaca halaman radar dari penyimpanan peramban,
                # lalu dikirim ke sini supaya radar memakai kunci yang sama.
                self._json(200, radar.simpan_profil(isi))
                return
            if path == "/api/radar/peramban":
                # Menguji peramban berarti benar-benar membuka satu peramban.
                # Jawabannya ditunggu sampai selesai supaya hasilnya langsung
                # terlihat; lamanya sekitar satu sampai tiga detik.
                # Bila `jalur` dikirim, pengguna menunjuk sendiri berkas
                # perambannya: berkas itu diuji dulu, baru dipakai.
                jalur = str(isi.get("jalur", "") or "").strip()
                self._json(200, radar.uji_peramban(jalur or None))
                return
            if path == "/api/radar/jadwal":
                if self.server.offline:  # type: ignore[attr-defined]
                    self._json(
                        409,
                        {
                            "error": "Mode luring aktif. Jadwal otomatis tidak dipasang karena "
                            "pemeriksaan butuh jaringan."
                        },
                    )
                    return
                aksi = str(isi.get("aksi", "aktifkan")).strip().lower()
                if aksi == "aktifkan":
                    self._json(200, radar.jadwal_aktifkan(
                        waktu=str(isi.get("waktu", "")),
                        frekuensi=str(isi.get("frekuensi", "harian")),
                        hari=str(isi.get("hari", "")),
                    ))
                    return
                if aksi == "matikan":
                    self._json(200, radar.jadwal_matikan())
                    return
                if aksi == "jalankan":
                    self._json(200, radar.jadwal_jalankan())
                    return
                self._json(400, {"error": "Aksi jadwal hanya aktifkan, matikan, atau jalankan."})
                return
            if path == "/api/radar/sasaran/impor":
                # Berkas daftar sasaran bisa jauh lebih besar dari body biasa,
                # jadi batasnya dinaikkan khusus untuk rute ini — dan tetap ada
                # batasnya, supaya permintaan raksasa tidak menghabiskan memori.
                nama = str(isi.get("nama", ""))[:120]
                teks = isi.get("teks")
                if not isinstance(teks, str):
                    self._json(400, {"error": "Sertakan isi berkas pada kolom “teks”."})
                    return
                self._json(200, radar.impor_sasaran(teks, nama))
                return
            if path == "/api/radar/hapus":
                identifier = isi.get("id")
                if identifier in (None, ""):
                    self._json(400, {"error": "Sertakan id sasaran yang akan dihapus."})
                    return
                self._json(200, radar.hapus(str(identifier)))
                return
        except radar.TidakDitemukan as error:
            self._json(404, {"error": str(error)})
            return
        except radar.MasukanTidakSah as error:
            self._json(400, {"error": str(error)})
            return
        except jadwal.MasukanJadwalTidakSah as error:
            self._json(400, {"error": str(error)})
            return
        except jadwal.JadwalError as error:
            self._json(409, {"error": str(error)})
            return
        except radar.RadarError as error:
            self._json(409, {"error": str(error)})
            return
        except ValueError as error:  # masukan pengguna yang tidak sah
            self._json(400, {"error": str(error)})
            return
        except Exception:  # noqa: BLE001
            LOG.exception("Permintaan radar gagal")
            self._json(500, {"error": "Permintaan radar tidak dapat diselesaikan."})
            return
        self._json(404, {"error": "Tidak ditemukan."})

    def _baca_json(self, *, max_bytes: int | None = None) -> dict:
        """Baca body JSON kecil; body kosong dianggap objek kosong.

        `max_bytes` dipakai rute yang memang menerima berkas besar, mis. impor
        daftar sasaran. Bawaannya tetap batas ketat untuk permintaan biasa.
        """
        if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() not in (
            "application/json",
            "",
        ):
            raise ValueError("Gunakan application/json.")
        try:
            mentah = read_body(
                self.rfile,
                self.connection,
                self.headers.get("Content-Length"),
                self.headers.get("Transfer-Encoding"),
                max_bytes=max_bytes or config.RADAR_MAX_BODY_BYTES,
            )
        except BodyError as error:
            raise ValueError(
                "Permintaan terlalu besar." if error.status == 413 else "Permintaan tidak valid."
            ) from error
        if not mentah:
            return {}
        try:
            isi = json.loads(mentah.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Format permintaan tidak valid.") from error
        if not isinstance(isi, dict):
            raise ValueError("Format permintaan tidak valid.")
        return isi

    # -- penghentian --------------------------------------------------------
    def _stop_app(self) -> None:
        if not allowed_origin(
            self.headers.get("Host"),
            self.headers.get("Origin"),
            self.headers.get("Sec-Fetch-Site"),
        ):
            self._json(403, {"error": "Origin atau host tidak diizinkan."})
            return
        self._json(200, {"dihentikan": True})
        LOG.info("Permintaan penghentian diterima; aplikasi berhenti.")
        threading.Timer(0.4, STOP_REQUESTED.set).start()

    # -- AI -----------------------------------------------------------------
    def _generate(self) -> None:
        if not allowed_origin(
            self.headers.get("Host"),
            self.headers.get("Origin"),
            self.headers.get("Sec-Fetch-Site"),
        ):
            self._json(403, {"error": "Origin atau host tidak diizinkan."})
            return
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type != "application/json":
            self._json(415, {"error": "Gunakan application/json."})
            return
        with TOKEN_BUSY["lock"]:
            now = time.time()
            for key in [k for k, v in TOKEN_BUSY["rate"].items() if v[1] <= now]:
                TOKEN_BUSY["rate"].pop(key, None)
            client = self.client_address[0] if self.client_address else "unknown"
            count, until = TOKEN_BUSY["rate"].get(client, (0, now + 60))
            too_many = (
                count >= config.REQUESTS_PER_MINUTE
                or (client not in TOKEN_BUSY["rate"] and len(TOKEN_BUSY["rate"]) >= config.RATE_BUCKET_CAP)
                or TOKEN_BUSY["readers"] >= config.MAX_READERS
            )
            if too_many:
                self._json(429, {"error": "Terlalu banyak permintaan. Coba lagi dalam satu menit."})
                return
            TOKEN_BUSY["rate"][client] = (count + 1, until)
            TOKEN_BUSY["readers"] += 1
        try:
            raw_body = read_body(
                self.rfile,
                self.connection,
                self.headers.get("Content-Length"),
                self.headers.get("Transfer-Encoding"),
            )
        except BodyError as error:
            self._send(
                error.status,
                _json_bytes(
                    {
                        "error": (
                            "Unggahan terlalu lambat. Coba lagi."
                            if error.status == 408
                            else "Permintaan terlalu besar."
                            if error.status == 413
                            else "Format permintaan tidak valid."
                        )
                    }
                ),
                "application/json; charset=utf-8",
                {"Connection": "close", "Cache-Control": "no-store"},
            )
            self.close_connection = True
            return
        finally:
            with TOKEN_BUSY["lock"]:
                TOKEN_BUSY["readers"] -= 1
        try:
            payload = validate_request(json.loads(raw_body.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"error": "Format permintaan tidak valid."})
            return
        except ValidationError as error:
            self._json(400, {"error": str(error)})
            return
        if self.server.offline:  # type: ignore[attr-defined]
            LOG.info("Mode luring: permintaan AI dijawab tanpa memanggil penyedia.")
            self._json(200, {"text": None, "attempts": [], "cancelled": False})
            return
        with TOKEN_BUSY["lock"]:
            busy = TOKEN_BUSY["running"] >= config.MAX_PROVIDER_RUNS
            if not busy:
                TOKEN_BUSY["running"] += 1
        if busy:
            self._json(429, {"error": "Server sedang sibuk. Coba lagi sebentar."})
            return
        try:
            result = run_ai(
                payload,
                is_cancelled=lambda: client_gone(self.connection),
            )
            self._json(200, result)
        except EgressError as error:  # bug pemrograman, bukan kesalahan pengguna
            LOG.error("Tujuan keluar ditolak: %s", error)
            self._json(500, {"error": "Konfigurasi server tidak valid."})
        except Exception:  # noqa: BLE001
            LOG.exception("Permintaan AI gagal")
            self._json(
                500,
                {
                    "error": (
                        "Permintaan AI tidak dapat diselesaikan. Penggunaan token "
                        "mungkin tidak diketahui."
                    )
                },
            )
        finally:
            with TOKEN_BUSY["lock"]:
                TOKEN_BUSY["running"] -= 1


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    static_root: Path
    offline: bool

    def handle_error(self, request, client_address) -> None:  # noqa: D102
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionResetError)):
            LOG.info("Koneksi %s ditutup klien.", client_address[1] if client_address else "?")
            return
        LOG.exception("Galat saat menangani permintaan", exc_info=error)


def create_server(root: Path, host: str, port: int, offline: bool = False) -> Server:
    server = Server((host, port), Handler)
    server.static_root = root.resolve()
    server.offline = offline
    server.request_timeout = 15  # type: ignore[attr-defined]
    return server
