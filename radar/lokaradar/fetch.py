"""Pengambilan halaman: sopan, berbatas, dan dapat diuji tanpa jaringan.

Scrapling dipakai bila tersedia (TLS fingerprint peramban, header wajar, cookie
sesi). Bila tidak terpasang, radar tetap berjalan dengan `urllib` dalam mode
sederhana, sehingga alat ini tidak mati hanya karena satu dependency hilang.
"""

import logging
import time
from contextlib import contextmanager
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from . import config, peramban

LOG = logging.getLogger("lokaradar")

SCRAPLING_ERROR: str | None = None
try:
    from scrapling.fetchers import Fetcher as _ScraplingFetcher
except Exception as error:  # noqa: BLE001 - Scrapling opsional
    _ScraplingFetcher = None
    SCRAPLING_ERROR = str(error)

DYNAMIC_ERROR: str | None = None
try:
    from scrapling.fetchers import DynamicFetcher as _ScraplingDynamicFetcher
except Exception as error:  # noqa: BLE001 - Scrapling opsional
    _ScraplingDynamicFetcher = None
    DYNAMIC_ERROR = str(error)

SESSION_ERROR: str | None = None
try:
    from scrapling.fetchers import DynamicSession as _ScraplingDynamicSession
except Exception as error:  # noqa: BLE001 - versi Scrapling lama tidak punya sesi
    _ScraplingDynamicSession = None
    SESSION_ERROR = str(error)


def scrapling_available() -> bool:
    return _ScraplingFetcher is not None


def dynamic_available() -> bool:
    """Apakah pengambil berbasis peramban (untuk situs ber-JavaScript) tersedia."""
    return _ScraplingDynamicFetcher is not None


def session_available() -> bool:
    """Apakah peramban bisa dipakai ulang untuk seluruh putaran (DynamicSession)."""
    return _ScraplingDynamicSession is not None


_BROWSER_READY: bool | None = None
BROWSER_CHECK_ERROR: str | None = None


def browser_ready(refresh: bool = False) -> bool:
    """Apakah berkas peramban benar-benar ada di mesin ini.

    Paket Scrapling bisa terpasang tanpa perambannya (`scrapling install`). Tanpa
    pemeriksaan ini, `status` akan mengaku "siap" padahal setiap rendering akan
    gagal — persis jenis kebohongan yang tidak boleh ada di alat ini.
    """
    global _BROWSER_READY
    if _BROWSER_READY is not None and not refresh:
        return _BROWSER_READY
    if _ScraplingDynamicFetcher is None:
        # Scrapling tidak ada, tetapi peramban yang sudah terpasang di komputer
        # (Microsoft Edge, Chrome) tetap bisa dipakai lewat peramban.py.
        _BROWSER_READY = peramban.tersedia()
        return _BROWSER_READY
    global BROWSER_CHECK_ERROR
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            executable = playwright.chromium.executable_path
        _BROWSER_READY = bool(executable) and Path(executable).exists()
        BROWSER_CHECK_ERROR = None if _BROWSER_READY else f"Berkas peramban tidak ada: {executable}"
    except Exception as error:  # noqa: BLE001 - Playwright tidak terpasang atau rusak
        _BROWSER_READY = False
        BROWSER_CHECK_ERROR = f"{type(error).__name__}: {error}"
    return _BROWSER_READY


PETUNJUK_PERAMBAN = (
    "Peramban tidak ditemukan. LokaRadar memakai Microsoft Edge atau Google "
    "Chrome yang sudah terpasang di komputer ini; bila keduanya tidak ada, pasang "
    "salah satunya — atau jalankan `scrapling install` sekali "
    "(atau `playwright install chromium`) lalu coba lagi."
)


def _pesan_ramah(error: Exception) -> str:
    """Terjemahkan galat peramban yang membingungkan menjadi satu kalimat jelas."""
    pesan = str(error)
    if "Executable doesn't exist" in pesan or "playwright install" in pesan:
        return PETUNJUK_PERAMBAN
    if "Timeout" in pesan or "timeout" in pesan:
        return "Peramban kehabisan waktu memuat halaman (bisa dicoba ulang dengan --timeout lebih besar)."
    baris = [line.strip() for line in pesan.splitlines() if line.strip()]
    return f"Rendering gagal: {baris[0][:200] if baris else 'sebab tidak diketahui'}"


def page_ok(page) -> bool:
    """Status halaman menandakan keberhasilan (tanpa bergantung pada kelasnya)."""
    return 200 <= int(getattr(page, "status", 0) or 0) < 300


# Penanda halaman yang isinya disusun JavaScript. Dipakai bersama ambang jumlah
# kata: halaman pendek yang statis (mis. halaman kontak) tidak perlu peramban,
# sedangkan kerangka Next/Nuxt/React perlu.
PENANDA_JAVASCRIPT = (
    "/_next/",  # Next.js
    "/_nuxt/",  # Nuxt
    "__NEXT_DATA__",
    "__NUXT__",
    "data-reactroot",  # React
    "ng-version",  # Angular
    "data-sveltekit",  # SvelteKit
    'id="root"',
    "id='root'",
    'id="app"',
    "id='app'",
    # Kerangka Next.js dan Vue memasang wadah bernama ini; tanpa penanda ini,
    # halaman yang isinya dimuat JavaScript lewat bundel luar tidak dikenali
    # sebagai kerangka (jumlah skripnya sedikit) dan rendering tidak dijalankan.
    'id="__next"',
    "id='__next'",
    'id="__nuxt"',
    "id='__nuxt'",
    'id="vue-app"',
    "'v-app'",
    "window.__",
)


def page_tipis(page) -> bool:
    """Halaman hampir tanpa teks (bisa statis pendek, bisa juga kerangka JS)."""
    return len(str(getattr(page, "text", "") or "").split()) < config.RENDER_MIN_WORDS


def page_perlu_render(page) -> bool:
    """Perlu diambil ulang dengan peramban?

    Halaman harus **tipis** sekaligus membawa tanda kerangka JavaScript. Tanpa
    syarat kedua, setiap halaman pendek (mis. halaman "Terima kasih") akan
    memaksa unduhan peramban — pemborosan yang juga tidak sopan bagi situs
    yang dipantau.
    """
    if not page_tipis(page):
        return False
    html = str(getattr(page, "html", "") or "")
    if any(penanda in html for penanda in PENANDA_JAVASCRIPT):
        return True
    # Cadangan: banyak skrip pada halaman besar tapi hampir tanpa teks.
    return html.count("<script") >= 5 and len(html) >= 15_000


@dataclass
class Page:
    """Hasil satu pengambilan halaman."""

    url: str
    status: int
    html: str
    text: str
    elapsed_ms: int
    final_url: str = ""
    from_cache: bool = False
    status_text: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    # True bila halaman diambil ulang dengan peramban karena isinya dibuat
    # JavaScript. `render_gagal` diisi alasan bila percobaan itu tidak berhasil.
    rendered: bool = False
    render_gagal: str = ""
    # Jumlah kata pada permintaan biasa sebelum dirender, dan lama rendering.
    # Dipakai perintah `scrape` untuk memperlihatkan apa yang berubah.
    kata_statis: int | None = None
    render_ms: int | None = None

    @property
    def jumlah_kata(self) -> int:
        return len(self.text.split())

    @property
    def tipis(self) -> bool:
        return page_tipis(self)

    @property
    def ok(self) -> bool:
        return page_ok(self)


class FetchError(RuntimeError):
    """Pengambilan gagal: jaringan bermasalah atau halaman menjawab galat."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class BlockedError(RuntimeError):
    """Pengambilan ditolak: robots.txt atau batas kesopanan."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class RateLimiter:
    """Jeda minimum per host, memakai jam yang bisa diganti pada pengujian."""

    def __init__(self, delay: float = config.DEFAULT_DELAY_SECONDS, clock=time.monotonic, sleeper=time.sleep):
        self.delay = delay
        self.clock = clock
        self.sleeper = sleeper
        self._last: dict[str, float] = {}
        self.waited = 0.0

    def wait(self, url: str, override: float | None = None) -> None:
        host = urlsplit(url).netloc.lower()
        delay = max(self.delay, override or 0.0)
        last = self._last.get(host)
        now = self.clock()
        if last is not None:
            remaining = delay - (now - last)
            if remaining > 0:
                self.sleeper(remaining)
                self.waited += remaining
                now = self.clock()
        self._last[host] = now


def _response_text(response) -> str:
    """Ambil teks yang terlihat dari respons Scrapling.

    Catatan penting: `response.text` pada Scrapling **bukan** teks halaman
    (tipenya `TextHandler` dan sering kosong pada berkas non-HTML). Urutan yang
    dipakai: teks terbaca, lalu isi mentah, terakhir `.text` bila berupa teks biasa.
    """
    candidates: list[str] = []
    getter = getattr(response, "get_all_text", None)
    if callable(getter):
        try:
            visible = getter()
        except Exception:  # noqa: BLE001 - sebagian versi tidak menyediakannya
            visible = None
        if isinstance(visible, str):
            candidates.append(visible)
    for attribute in ("body", "html_content"):
        value = getattr(response, attribute, None)
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8", "ignore")
        if isinstance(value, str):
            candidates.append(value)
    fallback = getattr(response, "text", "")
    if isinstance(fallback, str):
        candidates.append(fallback)
    for candidate in candidates:
        if candidate.strip():
            return candidate
    return ""


def _response_html(response) -> str:
    for attribute in ("html_content", "body"):
        value = getattr(response, attribute, None)
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8", "ignore")
        if isinstance(value, str) and value:
            return value
    fallback = getattr(response, "text", "")
    return fallback if isinstance(fallback, str) else ""


# Identitas diri sendiri, bukan tiruan peramban. Isinya ada di config supaya
# jalur peramban lokal (peramban.py) memakai janji yang sama.
HEADER_JUJUR = config.HEADER_JUJUR


def _scrapling_page(url: str, timeout: float, *, stealthy: bool = False) -> Page:
    """Ambil halaman dengan Scrapling.

    Bawaan: tanpa penyamaran. `impersonate=None` mematikan penyamaran peramban
    curl_cffi, dan header membawa User-Agent jujur dari config. Bila `stealthy`
    dinyalakan secara sadar, penyamaran peramban dipakai (tidak disarankan).
    """
    started = time.monotonic()
    headers = dict(HEADER_JUJUR, **{"User-Agent": config.USER_AGENT})
    if stealthy:
        response = _ScraplingFetcher.get(url, stealthy_headers=True, timeout=timeout)
    else:
        # stealthy_headers bawaan Scrapling bernilai True (menambah referer Google
        # dan header peramban). Jalur jujur harus mematikannya.
        response = _ScraplingFetcher.get(
            url, headers=headers, impersonate=None, stealthy_headers=False, timeout=timeout
        )
    elapsed = int((time.monotonic() - started) * 1000)
    html = _response_html(response)
    text = _response_text(response)
    headers = {str(k).lower(): str(v) for k, v in (getattr(response, "headers", {}) or {}).items()}
    return Page(
        url=url,
        status=int(getattr(response, "status", 0) or 0),
        html=html[: config.DEFAULT_MAX_BYTES],
        text=text,
        elapsed_ms=elapsed,
        final_url=str(getattr(response, "url", url) or url),
        status_text=str(getattr(response, "reason", "") or ""),
        headers=headers,
    )


class _PencariSelektor(HTMLParser):
    """Cari elemen sederhana di HTML: `#id`, `.kelas`, `tag`, `[atribut]`, dan gabungannya.

    Dipakai sebagai jalur cadangan saat Scrapling tidak terpasang — misalnya di
    dalam aplikasi `.exe`. Tanpa ini, catatan "selektor tunggu tidak ditemukan"
    hilang begitu saja di sana, dan pengguna mengira penantiannya berhasil.
    """

    def __init__(self, tag: str, elemen_id: str, kelas: tuple[str, ...], atribut: tuple[tuple[str, str | None], ...]) -> None:
        super().__init__(convert_charrefs=True)
        self.tag = tag
        self.elemen_id = elemen_id
        self.kelas = kelas
        self.atribut = atribut
        self.ditemukan = False

    def handle_starttag(self, tag, attrs):  # noqa: ANN001 - tanda tangan bawaan
        self._periksa(tag, attrs)
        # Beberapa penanda kerangka JavaScript menyisipkan isi lewat tag ini,
        # jadi tidak perlu; pemeriksaan hanya pada elemen biasa.

    def handle_startendtag(self, tag, attrs):  # noqa: ANN001
        self._periksa(tag, attrs)

    def _periksa(self, tag: str, attrs) -> None:  # noqa: ANN001
        if self.ditemukan:
            return
        if self.tag and tag.lower() != self.tag:
            return
        peta = {nama.lower(): (nilai or "") for nama, nilai in attrs}
        if self.elemen_id and peta.get("id", "") != self.elemen_id:
            return
        kelas_elemen = set(peta.get("class", "").split())
        if any(k not in kelas_elemen for k in self.kelas):
            return
        for nama, nilai in self.atribut:
            if nama not in peta:
                return
            if nilai is not None and peta[nama] != nilai:
                return
        self.ditemukan = True


def _pisah_selektor(selector: str) -> tuple[str, str, tuple[str, ...], tuple[tuple[str, str | None], ...]] | None:
    """Ubah selektor sederhana menjadi bagian-bagiannya; None bila terlalu rumit."""
    sisa = selector.strip()
    if not sisa or any(penanda in sisa for penanda in (" ", ">", "+", "~", ",", ":", "*")):
        return None
    tag = ""
    if not sisa.startswith(("#", ".", "[")):
        potong = min((sisa.index(k) for k in ("#", ".", "[") if k in sisa), default=len(sisa))
        tag, sisa = sisa[:potong].lower(), sisa[potong:]
    elemen_id = ""
    kelas: list[str] = []
    atribut: list[tuple[str, str | None]] = []
    while sisa:
        penanda, sisa = sisa[0], sisa[1:]
        if penanda == "[":
            akhir = sisa.find("]")
            if akhir < 0:
                return None
            isi = sisa[:akhir]
            sisa = sisa[akhir + 1 :]
            if "=" in isi:
                nama, nilai = isi.split("=", 1)
                atribut.append((nama.strip().lower(), nilai.strip().strip("\"'").lower()))
            else:
                atribut.append((isi.strip().lower(), None))
            continue
        batas = min((sisa.index(k) for k in ("#", ".", "[") if k in sisa), default=len(sisa))
        nilai, sisa = sisa[:batas], sisa[batas:]
        if not nilai:
            return None
        if penanda == "#":
            if elemen_id:
                return None  # dua id: bukan selektor sederhana lagi
            elemen_id = nilai
        else:
            kelas.append(nilai)
    return tag, elemen_id, tuple(kelas), tuple(atribut)


def selektor_ditemukan(html: str, selector: str) -> bool | None:
    """Apakah selektor tunggu benar-benar ada di halaman hasil.

    Mengembalikan None bila pengecekan tidak bisa dilakukan. Berguna karena
    selektor yang salah tidak menggagalkan permintaan — peramban hanya menunggu
    sampai batas waktu lalu menyerahkan halaman seadanya. Pengguna perlu tahu
    bahwa penantiannya sia-sia, bukan mengira hasilnya lengkap.
    """
    if not selector:
        return None
    try:  # jalur utama: parser Scrapling, bila terpasang
        from scrapling.parser import Selector

        return bool(Selector(html or "").css(selector))
    except Exception:  # noqa: BLE001 - Scrapling (atau parse-nya) tidak tersedia
        pass
    bagian = _pisah_selektor(selector)
    if bagian is None:
        return None  # selektor rumit: lebih baik mengaku tidak tahu
    pencari = _PencariSelektor(*bagian)
    try:
        pencari.feed(html or "")
    except Exception:  # noqa: BLE001 - HTML rusak bukan alasan menggagalkan pemeriksaan
        return None
    return pencari.ditemukan


def _catat_selektor(page: Page, selector: str | None) -> Page:
    if not selector:
        return page
    ditemukan = selektor_ditemukan(page.html, selector)
    if ditemukan is False:
        page.render_gagal = (
            f"Selektor tunggu '{selector}' tidak ditemukan setelah halaman dirender; "
            "peramban menunggu sampai batas waktu dan isi halaman bisa belum lengkap."
        )
    return page


def opsi_peramban(timeout: float = config.DEFAULT_TIMEOUT) -> dict:
    """Opsi peramban yang dipakai di semua jalur rendering.

    Dikumpulkan di satu tempat supaya janji identitas jujur tidak bisa terlupa
    hanya karena ada jalur baru yang lupa menyalin opsinya.
    """
    return {
        "headless": True,
        # Waktu tunggu Playwright memakai milidetik.
        "timeout": int(timeout * 1000),
        "network_idle": True,
        "load_dom": True,
        "useragent": config.USER_AGENT,
        "extra_headers": dict(HEADER_JUJUR),
        # `google_search` bawaan Scrapling bernilai True dan menyisipkan
        # `Referer: https://www.google.com/` — yaitu berpura-pura datang dari
        # pencarian Google. Jalur jujur harus mematikannya.
        "google_search": False,
    }


def _page_dari_respons(response, url: str, started: float, *, rendered: bool = True) -> Page:
    """Ubah respons peramban Scrapling menjadi `Page` milik radar."""
    elapsed = int((time.monotonic() - started) * 1000)
    html = _response_html(response)
    text = _response_text(response)
    headers = {str(k).lower(): str(v) for k, v in (getattr(response, "headers", {}) or {}).items()}
    return Page(
        url=url,
        status=int(getattr(response, "status", 0) or 0),
        html=html[: config.DEFAULT_MAX_BYTES],
        text=text,
        elapsed_ms=elapsed,
        final_url=str(getattr(response, "url", url) or url),
        status_text=str(getattr(response, "reason", "") or ""),
        headers=headers,
        rendered=rendered,
        render_ms=elapsed if rendered else None,
    )


def _dynamic_page(url: str, timeout: float, *, wait_selector: str | None = None) -> Page:
    """Ambil halaman dengan peramban sungguhan (Chromium) supaya JavaScript jalan.

    Identitas tetap jujur: User-Agent diberi nilai config.USER_AGENT dan header
    tambahan dari HEADER_JUJUR. Perlu diketahui apa adanya: peramban tetap
    mengirim sebagian header khas peramban (mis. `sec-ch-ua`, `Accept-Encoding`)
    yang tidak bisa dihapus dari sisi ini. Karena itu rendering hanya dipakai
    sebagai upaya terakhir, bukan sebagai perilaku bawaan tiap permintaan.
    """
    if _ScraplingDynamicFetcher is None:
        raise FetchError(
            "Pengambil peramban tidak tersedia. Pasang Scrapling beserta perambannya "
            "(`pip install scrapling` lalu `scrapling install`)."
        )
    started = time.monotonic()
    opsi = opsi_peramban(timeout)
    if wait_selector:
        opsi["wait_selector"] = wait_selector
    response = _ScraplingDynamicFetcher.fetch(url, **opsi)
    return _catat_selektor(_page_dari_respons(response, url, started), wait_selector)


def _page_dari_peramban(hasil, url: str, wait_selector: str | None = None) -> Page:
    """Ubah hasil peramban lokal (peramban.py) menjadi `Page` milik radar."""
    headers = {k.lower(): v for k, v in (hasil.headers or {}).items() if k != "x-lokaradar-catatan"}
    page = Page(
        url=url,
        status=int(hasil.status or 0),
        html=(hasil.html or "")[: config.DEFAULT_MAX_BYTES],
        text=hasil.text or "",
        elapsed_ms=int(hasil.ms or 0),
        final_url=hasil.final_url or url,
        headers=headers,
        rendered=True,
        render_ms=int(hasil.ms or 0),
    )
    if hasil.catatan:
        page.render_gagal = hasil.catatan
    return _catat_selektor(page, wait_selector)


def _peramban_page(url: str, timeout: float, *, wait_selector: str | None = None) -> Page:
    """Ambil satu halaman dengan peramban yang sudah terpasang di komputer."""
    hasil = peramban.ambil(url, timeout=timeout, wait_selector=wait_selector)
    return _page_dari_peramban(hasil, url, wait_selector)


class RenderSession:
    """Satu peramban untuk seluruh putaran, bukan satu peramban per halaman.

    Membuka peramban butuh sekitar satu detik. Untuk putaran yang memeriksa
    beberapa situs ber-JavaScript, biaya itu terasa. Sesi ini memakai peramban
    yang sama berulang kali, dengan identitas jujur yang sama.

    Bila sesi tidak tersedia (Scrapling lama atau peramban belum terunduh),
    `load` jatuh kembali ke satu-peramban-per-halaman, lalu ke jalur biasa.
    """

    def __init__(self, *, timeout: float = config.DEFAULT_TIMEOUT, wait_selector: str | None = None) -> None:
        self.timeout = timeout
        self.wait_selector = wait_selector
        self._cm = None
        self._session = None

    def __enter__(self) -> "RenderSession":
        if _ScraplingDynamicSession is None:
            return self
        try:
            self._cm = _ScraplingDynamicSession(**opsi_peramban(self.timeout))
            self._session = self._cm.__enter__()
        except Exception as error:  # noqa: BLE001 - peramban bisa gagal dibuka
            LOG.warning("Sesi peramban tidak bisa dibuka: %s", _pesan_ramah(error))
            self._cm = None
            self._session = None
        return self

    def __exit__(self, *exc_info) -> None:
        cm, self._cm, self._session = self._cm, None, None
        if cm is not None:
            try:
                cm.__exit__(*exc_info)
            except Exception as error:  # noqa: BLE001 - penutupan gagal bukan urusan pemanggil
                LOG.debug("Penutupan sesi peramban bermasalah: %s", error)

    @property
    def aktif(self) -> bool:
        return self._session is not None

    def load(self, url: str, timeout: float | None = None) -> Page:
        """Ambil satu halaman dengan peramban sesi ini."""
        lama = timeout or self.timeout
        if self._session is None:
            return _dynamic_page(url, lama, wait_selector=self.wait_selector)
        started = time.monotonic()
        opsi = {"timeout": int(lama * 1000), "network_idle": True, "load_dom": True}
        if self.wait_selector:
            opsi["wait_selector"] = self.wait_selector
        response = self._session.fetch(url, **opsi)
        return _catat_selektor(_page_dari_respons(response, url, started), self.wait_selector)


def _urllib_page(url: str, timeout: float, *, stealthy: bool = False) -> Page:  # noqa: ARG001 - tanda tangan disamakan
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL dari pengguna
            raw = response.read(config.DEFAULT_MAX_BYTES)
            status = response.status
            status_text = str(getattr(response, "reason", "") or "")
            headers = {k.lower(): v for k, v in response.headers.items()}
            final = response.url
    except urllib.error.HTTPError as error:
        raw = error.read(config.DEFAULT_MAX_BYTES) if hasattr(error, "read") else b""
        status = error.code
        status_text = str(getattr(error, "reason", "") or "")
        headers = {}
        final = url
    except urllib.error.URLError as error:
        raise FetchError(str(error.reason)) from error
    elapsed = int((time.monotonic() - started) * 1000)
    charset = "utf-8"
    probe = raw[:2048].decode("ascii", "ignore")
    if "charset=" in probe.lower():
        charset = probe.lower().split("charset=", 1)[1].split(";")[0].split('"')[0].strip() or "utf-8"
    html = raw.decode(charset, "ignore")
    return Page(
        url=url,
        status=status,
        html=html,
        text=html,
        elapsed_ms=elapsed,
        final_url=final,
        status_text=status_text,
        headers=headers,
    )


class SesiPerambanLokal:
    """Satu peramban lokal untuk seluruh putaran, seperti RenderSession.

    Membuka peramban butuh sekitar satu detik; memakainya berulang membuat biaya
    itu terbayar saat beberapa sasaran perlu dirender. Bila peramban tidak ada
    atau gagal dibuka, sesi ini tidak aktif dan `load` jatuh ke jalur sekali pakai.
    """

    def __init__(self, *, timeout: float = config.DEFAULT_TIMEOUT, wait_selector: str | None = None) -> None:
        self.timeout = timeout
        self.wait_selector = wait_selector
        self._sesi = None

    def __enter__(self) -> "SesiPerambanLokal":
        if not peramban.tersedia():
            return self
        try:
            self._sesi = peramban.Sesi(timeout=self.timeout, wait_selector=self.wait_selector)
            self._sesi.__enter__()
        except Exception as error:  # noqa: BLE001 - peramban bisa gagal karena banyak hal
            LOG.warning("Peramban lokal tidak bisa dibuka: %s", _pesan_ramah(error))
            self._sesi = None
        return self

    def __exit__(self, *exc_info) -> None:
        sesi, self._sesi = self._sesi, None
        if sesi is not None:
            try:
                sesi.__exit__(*exc_info)
            except Exception as error:  # noqa: BLE001 - penutupan gagal bukan urusan pemanggil
                LOG.debug("Penutupan peramban lokal bermasalah: %s", error)

    @property
    def aktif(self) -> bool:
        return self._sesi is not None and self._sesi.aktif

    def load(self, url: str, timeout: float | None = None) -> Page:
        lama = timeout or self.timeout
        if self._sesi is None:
            return _peramban_page(url, lama, wait_selector=self.wait_selector)
        hasil = self._sesi.buka(url, timeout=lama)
        return _page_dari_peramban(hasil, url, self.wait_selector)


def _sesi_render(timeout: float, wait_selector: str | None):
    """Pilih sesi rendering yang tersedia: Scrapling dulu, lalu peramban lokal."""
    if session_available():
        return RenderSession(timeout=timeout, wait_selector=wait_selector)
    return SesiPerambanLokal(timeout=timeout, wait_selector=wait_selector)


class Fetcher:
    """Pengambil halaman dengan pemeriksaan robots.txt dan batas kesopanan."""

    def __init__(
        self,
        *,
        timeout: float = config.DEFAULT_TIMEOUT,
        delay: float = config.DEFAULT_DELAY_SECONDS,
        robots=None,
        limiter: RateLimiter | None = None,
        page_loader=None,
        obey_robots: bool = True,
        stealthy: bool = False,
        # Bawaan pustaka: rendering **mati**. Pemanggil pustaka tidak boleh
        # tanpa sadar membuka peramban; perintah `run`/`scrape` milik CLI yang
        # menyalakan mode "auto" bagi pengguna (lihat config.DEFAULT_RENDER).
        render: str = "tidak",
        render_loader=None,
        render_wait: str | None = None,
    ) -> None:
        self.timeout = timeout
        self.obey_robots = obey_robots
        self.stealthy = stealthy
        self.render = render if render in config.RENDER_MODES else "tidak"
        # Selektor CSS yang ditunggu sebelum peramban menyerahkan halaman; berguna
        # untuk situs yang memuat daftar harga belakangan.
        self.render_wait = render_wait or None
        self.limiter = limiter or RateLimiter(delay)
        if page_loader is not None:
            self.page_loader = page_loader
        elif scrapling_available():
            self.page_loader = lambda url, timeout: _scrapling_page(url, timeout, stealthy=self.stealthy)
        else:
            self.page_loader = lambda url, timeout: _urllib_page(url, timeout)
        # Pengambil peramban hanya dipakai bila mode render mengizinkannya. Bila
        # peramban belum terpasang, jalur biasa tetap berjalan (tanpa gagal).
        #
        # Bila pengambil halaman diganti sendiri (page_loader), peramban **tidak**
        # dipakai otomatis: penggantian pengambil berarti pemanggil ingin menguasai
        # seluruh lalu lintas, dan pengujian harus tetap luring. Berikan
        # `render_loader` sendiri bila memang ingin rendering.
        if render_loader is not None:
            self.render_loader = render_loader
        # `browser_ready()` sengaja **tidak** dipakai di sini: bila peramban belum
        # diunduh, percobaan tetap dilakukan sekali supaya pengguna menerima
        # pesan galat yang sebenarnya (dan menerjemahkannya jadi petunjuk jelas),
        # bukan gagal diam-diam.
        elif page_loader is not None or self.render == "tidak":
            self.render_loader = None
        elif dynamic_available():
            self.render_loader = lambda url, timeout: _dynamic_page(
                url, timeout, wait_selector=self.render_wait
            )
        elif peramban.tersedia():
            # Tanpa Scrapling: pakai peramban yang sudah ada di komputer ini.
            self.render_loader = lambda url, timeout: _peramban_page(
                url, timeout, wait_selector=self.render_wait
            )
        else:
            self.render_loader = None
        self.render_dipakai = 0
        self.render_gagal_terakhir = ""
        self.sesi_terpakai = False
        self.calls: list[str] = []
        if robots is None:
            from .robots import RobotsCache

            robots = RobotsCache(self._robots_loader)
        self.robots = robots

    # -- sesi peramban ------------------------------------------------------
    @contextmanager
    def render_session(self):
        """Pakai satu peramban untuk seluruh putaran pemeriksaan.

        Selama blok ini, `render_loader` diganti oleh sesi. Bila rendering mati
        atau peramban tidak ada, tidak ada yang dibuka dan semuanya berjalan
        seperti biasa.
        """
        if self.render == "tidak" or self.render_loader is None:
            yield self
            return
        sesi = _sesi_render(self.timeout, self.render_wait)
        with sesi:
            semula = self.render_loader
            self.render_loader = sesi.load
            self.sesi_terpakai = sesi.aktif
            try:
                yield self
            finally:
                self.render_loader = semula

    # -- robots -------------------------------------------------------------
    def _robots_loader(self, url: str):
        return self.page_loader(url, self.timeout)

    def robots_verdict(self, url: str):
        if not self.obey_robots:
            return None
        return self.robots.check(url)

    # -- pengambilan --------------------------------------------------------
    def _render(self, url: str, delay: float | None) -> Page | None:
        """Ambil halaman dengan peramban. Jeda kesopanan tetap dihitung lagi.

        Mengembalikan None bila gagal; kegagalan rendering tidak boleh
        menggagalkan pemeriksaan karena jalur biasa sudah punya hasilnya.
        """
        if self.render_loader is None:
            return None
        self.limiter.wait(url, delay)  # permintaan kedua ke host yang sama
        self.render_dipakai += 1
        try:
            page = self.render_loader(url, self.timeout)
        except Exception as error:  # noqa: BLE001 - peramban bisa gagal karena banyak hal
            self.render_gagal_terakhir = _pesan_ramah(error)
            LOG.warning("Rendering gagal untuk %s: %s", url, self.render_gagal_terakhir)
            return None
        self.calls.append(f"{url} (render)")
        # Fetcher yang menentukan penandanya, bukan pengambil: halaman ini jelas
        # datang dari peramban apa pun jenis pengambil yang dipakai.
        page.rendered = True
        return page

    def get(self, url: str, *, expect_html: bool = True) -> Page:
        """Ambil satu halaman. Naikkan `BlockedError` bila tidak diizinkan."""
        verdict = self.robots_verdict(url)
        if verdict is not None and not verdict.allowed:
            raise BlockedError(f"Ditolak robots.txt untuk {url}: {verdict.reason}")
        delay = verdict.crawl_delay if verdict is not None else None
        if self.render == "selalu" and self.render_loader is not None:
            diambil = self._render(url, delay)
            if diambil is not None:
                return self._periksa(diambil, url, expect_html)
            LOG.info("Rendering tidak berhasil untuk %s; memakai permintaan biasa.", url)
        self.limiter.wait(url, delay)
        try:
            page = self.page_loader(url, self.timeout)
        except FetchError:
            raise
        except Exception as error:  # noqa: BLE001 - normalkan galat pustaka pengambil
            raise FetchError(str(error)) from error
        self.calls.append(url)
        page.kata_statis = len(str(getattr(page, "text", "") or "").split())
        if self.render == "selalu":
            # Mode "selalu": permintaan biasa hanya dipakai bila rendering gagal.
            page.render_gagal = page.render_gagal or self.render_gagal_terakhir
        if self.render == "auto" and self.render_loader is not None and page_ok(page) and page_perlu_render(page):
            LOG.info(
                "Halaman %s hanya %s kata; dicoba diambil ulang dengan peramban.",
                url,
                len(str(getattr(page, "text", "") or "").split()),
            )
            diambil = self._render(url, delay)
            if diambil is not None and page_ok(diambil):
                kata = len(str(getattr(diambil, "text", "") or "").split())
                # Jangan menimpa catatan yang sudah ada (mis. selektor tunggu tidak
                # ditemukan) hanya karena halamannya cukup panjang.
                if page_tipis(diambil) and not getattr(diambil, "render_gagal", ""):
                    # Rendering **berhasil**; catatan ini hanya mengatakan halamannya
                    # tetap pendek, supaya tidak terbaca seolah peramban gagal.
                    diambil.render_gagal = (
                        f"Rendering berhasil, tetapi halaman tetap tipis ({kata} kata) — "
                        "bisa jadi isinya memang singkat."
                    )
                page = diambil
            elif diambil is not None:
                page.render_gagal = f"Rendering menjawab status {diambil.status}."
            elif self.render_gagal_terakhir:
                page.render_gagal = self.render_gagal_terakhir
        return self._periksa(page, url, expect_html)

    def _periksa(self, page: Page, url: str, expect_html: bool) -> Page:
        """Periksa status halaman hasil; naikkan galat bila tidak layak disimpan."""
        if page.status in (401, 403, 429):
            raise BlockedError(f"Situs menolak permintaan ({page.status}) untuk {url}", status=page.status)
        if page.status >= 400:
            # Jangan simpan potret halaman galat: riwayat pemantauan harus berisi
            # halaman sungguhan. Kegagalan cukup dicatat sebagai galat sasaran.
            keterangan = f" ({page.status_text})" if getattr(page, "status_text", "") else ""
            raise FetchError(f"Halaman menjawab {page.status}{keterangan} untuk {url}", status=page.status)
        if expect_html and not page.html:
            raise FetchError(f"Tidak ada isi HTML dari {url}")
        return page
