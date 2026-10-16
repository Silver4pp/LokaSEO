"""Mengubah halaman menjadi fakta ringkas yang bisa dibandingkan antarwaktu.

Sumber utama:

1. Data terstruktur JSON-LD (`schema.org`) untuk harga dan rating agregat — jauh
   lebih tahan perubahan tata letak daripada pemilih CSS.
2. Atribut halaman untuk pemeriksaan SEO dasar, sejalan dengan audit HTML LokaSEO.
3. Pola teks sebagai cadangan bila halaman tidak menyertakan data terstruktur.

Identitas pribadi tidak diambil sama sekali: hanya angka agregat seperti nilai
rating dan jumlah ulasan.
"""

import hashlib
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from . import config

MAX_HEADINGS = 25
MAX_PRICES = 20
MAX_LINKS = 200


def _to_number(raw: str) -> float | None:
    """Ubah teks angka gaya Indonesia atau Inggris menjadi angka."""
    cleaned = re.sub(r"[^\d.,]", "", raw or "")
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        head, _, tail = cleaned.rpartition(",")
        cleaned = f"{head}.{tail}" if len(tail) == 2 else cleaned.replace(",", "")
    elif "." in cleaned:
        head, _, tail = cleaned.rpartition(".")
        if len(tail) != 3:
            cleaned = f"{head}.{tail}" if head else cleaned
        else:
            cleaned = cleaned.replace(".", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value >= 0 else None


# Panjang maksimum keterangan harga yang diambil dari teks di sekitarnya.
KONTEKS_HARGA_MAKS = 45
KONTEKS_HARGA_KATA_MAKS = 6
# Sejauh mana teks sebelum harga masih diingat sebagai calon keterangan.
TEKS_SEBELUM_MAKS = 200
# Jarak maksimum (dalam karakter teks) antara judul bagian dan harga agar judul
# itu masih dianggap keterangannya. Tanpa batas ini, tagline di kepala halaman
# ("The First Playground in Dental Clinic") menempel ke semua harga di bawahnya.
JUDUL_DEKAT_MAKS = 120

# Tag judul yang teksnya disimpan (dipakai sebagai keterangan cadangan) dan tag
# pemisah blok: teks tidak boleh menyeberang dari satu baris tabel ke baris lain.
_TAG_JUDUL = ("title", "h1", "h2", "h3", "h4")
_TAG_PEMISAH = ("p", "li", "tr", "div", "section", "article", "h1", "h2", "h3", "h4", "br")

# Pemotong di ujung keterangan: tanda baca dan kata sambung yang tidak menambah arti.
_PEMOTONG_KONTEKS = ("|", ">", "•", "·", "-", "–", "—", ":", ";", ",", "=", "…", "...")


def _judul_layak_dipakai(judul: str) -> bool:
    """Apakah judul bagian layak jadi keterangan harga.

    Judul seperti "Ready To Serve You!" adalah kalimat pemasaran, bukan nama
    layanan — lebih baik tidak dipakai sama sekali daripada menyesatkan.
    """
    bersih = " ".join(judul.split())
    if not bersih or bersih.endswith(("!", "?")):
        return False
    return len(bersih.split()) <= KONTEKS_HARGA_KATA_MAKS and len(bersih) <= KONTEKS_HARGA_MAKS


def _konteks_harga(teks_sebelum: str) -> str:
    """Ambil keterangan singkat dari teks tepat sebelum angka harga.

    Halaman harga jarang menaruh nama layanan jauh dari angkanya; yang paling
    dekat biasanya justru namanya ("Bleaching gigi Rp 649.000"). Fungsi ini
    mengambil potongan terdekat itu dan membuang tanda baca di ujungnya.
    """
    bersih = " ".join(teks_sebelum.split())
    if not bersih:
        return ""
    # Hanya kalimat terakhir: keterangan harga tidak pernah sepanjang paragraf.
    # Ini yang membuang tagline ("Ready To Serve You!") dari daftar harga.
    for pemisah in (". ", "!", "?", ";", "|", "•", "·", "—", "–"):
        potong = bersih.rfind(pemisah)
        if potong != -1:
            bersih = bersih[potong + len(pemisah) :].strip()
    if not bersih:
        return ""
    # Nama layanan itu pendek. Kalau yang tertangkap lebih panjang dari ini, itu
    # kalimat pemasaran — lebih baik kembali ke judul bagian daripada menampilkan
    # keterangan yang menyesatkan.
    if len(bersih.split()) > KONTEKS_HARGA_KATA_MAKS or len(bersih) > KONTEKS_HARGA_MAKS:
        return ""
    # Ambil bagian terdekat dengan angkanya, bukan sejak awal paragraf.
    if len(bersih) > KONTEKS_HARGA_MAKS:
        bersih = bersih[-KONTEKS_HARGA_MAKS:]
        potong = bersih.find(" ")
        if potong > 0:
            bersih = bersih[potong + 1 :]
    while bersih and bersih[-1] in _PEMOTONG_KONTEKS:
        bersih = bersih[:-1].strip()
    while bersih and bersih[0] in _PEMOTONG_KONTEKS:
        bersih = bersih[1:].strip()
    # Keterangan tanpa huruf (mis. "12") tidak membantu siapa pun.
    if not any(karakter.isalpha() for karakter in bersih):
        return ""
    if len(bersih) < 3:
        return ""
    return bersih


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.lang = ""
        self.canonical = ""
        self.robots_meta = ""
        self.viewport = ""
        self.h1: list[str] = []
        self.h2: list[str] = []
        self.images = 0
        self.images_without_alt = 0
        self.links: list[str] = []
        self.json_ld: list[str] = []
        # Tiap harga dari teks disertai konteksnya: potongan teks tepat sebelum
        # angkanya, atau judul bagian terakhir. Tanpa ini laporan hanya berbunyi
        # "IDR 649.000" tanpa keterangan itu harga apa — tidak berguna untuk
        # membandingkan harga pesaing.
        self.prices_text: list[tuple[str, str, str]] = []
        self._stack: list[str] = []
        self._buffer: list[str] = []
        self._script_type = ""
        self._script_buffer: list[str] = []
        self._skip_text = 0
        self._judul_bagian = ""
        self._sejak_judul = 0
        # Teks yang sudah lewat dan belum dipakai harga mana pun: calon nama
        # layanan bagi harga berikutnya.
        self._teks_terakhir: list[str] = []

    # -- util ---------------------------------------------------------------
    def _flush(self, tag: str) -> None:
        text = " ".join("".join(self._buffer).split())
        self._buffer = []
        if not text:
            return
        if tag == "title":
            self.title = text
        elif tag == "h1" and len(self.h1) < MAX_HEADINGS:
            self.h1.append(text)
        elif tag == "h2" and len(self.h2) < MAX_HEADINGS:
            self.h2.append(text)
        if tag in ("h1", "h2", "h3", "h4") and _judul_layak_dipakai(text):
            self._judul_bagian = text[:KONTEKS_HARGA_MAKS]
            self._sejak_judul = 0

    def _teks_sebelumnya(self) -> str:
        gabung = " ".join(self._teks_terakhir)
        return gabung[-TEKS_SEBELUM_MAKS:]

    def finish(self) -> None:
        """Simpan sisa teks yang belum ditutup, misalnya `<title>` tanpa `</title>`."""
        if self._stack and self._stack[-1] in _TAG_JUDUL:
            if self._stack[-1] == "title" and self._buffer:
                # Mode CDATA mengembalikan sisa dokumen; ambil teksnya saja.
                buffered = "".join(self._buffer)
                marker = buffered.find("<")
                if marker != -1:
                    self._buffer = [buffered[:marker]]
            self._flush(self._stack[-1])

    # -- parser -------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        # Judul atau heading yang tidak ditutup tetap disimpan sebelum tag berikutnya.
        if self._stack and self._stack[-1] in _TAG_JUDUL and tag != self._stack[-1]:
            self._flush(self._stack[-1])
        if tag in _TAG_PEMISAH:
            # Baris/blok baru: keterangan harga tidak boleh menyeberang dari sini.
            self._teks_terakhir = []
        attributes = {name.lower(): (value or "") for name, value in attrs}
        if tag in ("script", "style", "noscript"):
            self._skip_text += 1
            if tag == "script":
                self._script_type = attributes.get("type", "").lower()
                self._script_buffer = []
        if tag == "html" and not self.lang:
            self.lang = attributes.get("lang", "").strip()
        elif tag == "meta":
            name = attributes.get("name", "").lower() or attributes.get("property", "").lower()
            content = attributes.get("content", "")
            if name == "description" and not self.description:
                self.description = content.strip()
            elif name == "robots":
                self.robots_meta = f"{self.robots_meta} {content}".strip()
            elif name == "viewport":
                self.viewport = content.strip()
        elif tag == "link":
            rel = attributes.get("rel", "").lower()
            if rel == "canonical" and not self.canonical:
                self.canonical = attributes.get("href", "").strip()
        elif tag == "img":
            self.images += 1
            if not attributes.get("alt", "").strip():
                self.images_without_alt += 1
        elif tag == "a" and len(self.links) < MAX_LINKS:
            href = attributes.get("href", "").strip()
            if href:
                self.links.append(href)
        self._stack.append(tag)

    def handle_endtag(self, tag):
        if tag in _TAG_JUDUL:
            self._flush(tag)
        if tag in _TAG_PEMISAH:
            self._teks_terakhir = []
        if tag in ("script", "style", "noscript") and self._skip_text:
            self._skip_text -= 1
            if tag == "script":
                payload = "".join(self._script_buffer).strip()
                if payload and ("ld+json" in self._script_type or payload.startswith("{")):
                    self.json_ld.append(payload)
                self._script_type = ""
                self._script_buffer = []
        if self._stack and tag in self._stack:
            while self._stack:
                if self._stack.pop() == tag:
                    break

    def handle_data(self, data):
        if self._script_type and "ld+json" in self._script_type:
            self._script_buffer.append(data)
            return
        if self._skip_text:
            return
        if self._stack and self._stack[-1] in _TAG_JUDUL:
            self._buffer.append(data)
        elif not self._stack or self._stack[-1] not in ("script", "style"):
            # Kumpulkan kandidat harga dari teks yang terlihat saja.
            temuan: list[tuple[int, int, str, str]] = []
            for currency, pattern in config.CURRENCY_PATTERNS:
                for cocok in re.finditer(pattern, data, flags=re.IGNORECASE):
                    temuan.append((cocok.start(), cocok.end(), currency, cocok.group(0)))
            temuan.sort()
            if not temuan:
                self._teks_terakhir.append(data)
                self._sejak_judul += len(data)
                return
            posisi = 0
            for start, end, currency, raw in temuan:
                if len(self.prices_text) >= 400:
                    break
                sebelumnya = f"{self._teks_sebelumnya()} {data[posisi:start]}".strip()
                konteks = _konteks_harga(sebelumnya)
                if not konteks and self._judul_bagian and self._sejak_judul <= JUDUL_DEKAT_MAKS:
                    konteks = self._judul_bagian
                self.prices_text.append((currency, raw, konteks))
                posisi = end
            sisa = data[posisi:]
            self._teks_terakhir = [sisa] if sisa.strip() else []


def _walk_json_ld(payloads: list[str]) -> tuple[list[dict], list[str]]:
    nodes: list[dict] = []
    types: list[str] = []

    def visit(value) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            node_type = value.get("@type")
            if isinstance(node_type, list):
                types.extend(str(entry) for entry in node_type)
            elif node_type:
                types.append(str(node_type))
            nodes.append(value)
            # Hanya wadah yang ditelusuri. `offers`, `aggregateRating`, dan `review`
            # dibaca langsung dari simpulnya agar tidak terhitung dua kali, dan
            # ulasan tidak pernah disimpan sebagai data pribadi.
            for key in ("@graph", "itemListElement", "mainEntity"):
                if key in value:
                    visit(value[key])

    for payload in payloads:
        try:
            visit(json.loads(payload))
        except (json.JSONDecodeError, TypeError):
            continue
    return nodes, types


def _prices_from_ld(nodes: list[dict]) -> list[dict]:
    prices: list[dict] = []
    for node in nodes:
        offers = node.get("offers")
        for offer in offers if isinstance(offers, list) else [offers] if isinstance(offers, dict) else []:
            if not isinstance(offer, dict):
                continue
            raw = offer.get("price", offer.get("lowPrice"))
            amount = _to_number(str(raw)) if raw is not None else None
            if amount is None:
                continue
            prices.append(
                {
                    "amount": amount,
                    "currency": str(offer.get("priceCurrency") or "IDR").upper()[:3],
                    "source": "json-ld",
                    "name": str(node.get("name") or offer.get("name") or "")[:120],
                }
            )
        if isinstance(node.get("price"), (int, float, str)) and "offers" not in node:
            amount = _to_number(str(node["price"]))
            if amount is not None:
                prices.append(
                    {
                        "amount": amount,
                        "currency": str(node.get("priceCurrency") or "IDR").upper()[:3],
                        "source": "json-ld",
                        "name": str(node.get("name") or "")[:120],
                    }
                )
    return prices


def _prices_from_text(parser: _PageParser) -> list[dict]:
    prices: list[dict] = []
    for currency, raw, konteks in parser.prices_text:
        amount = _to_number(raw)
        if amount is None or amount <= 0:
            continue
        prices.append({"amount": amount, "currency": currency, "source": "teks", "name": konteks[:120]})
    return prices


def _price_priority(price: dict) -> tuple:
    """Utamakan harga dari data terstruktur, lalu yang punya nama barang."""
    return (
        0 if price["source"] == "json-ld" else 1,
        0 if price.get("name") else 1,
        price["amount"],
    )


def _dedupe_prices(prices: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    result: list[dict] = []
    for price in sorted(prices, key=_price_priority):
        key = (round(price["amount"], 2), price["currency"])
        if key in seen:
            continue
        seen.add(key)
        result.append(_round_price(price))
        if len(result) >= MAX_PRICES:
            break
    return result


def _round_price(price: dict) -> dict:
    rounded = dict(price)
    rounded["amount"] = round(float(price["amount"]), 2)
    return rounded


def _ratings(nodes: list[dict]) -> dict | None:
    best: dict | None = None
    for node in nodes:
        rating = node.get("aggregateRating")
        if not isinstance(rating, dict):
            continue
        value = _to_number(str(rating.get("ratingValue") or ""))
        count_raw = rating.get("reviewCount", rating.get("ratingCount"))
        count = _to_number(str(count_raw)) if count_raw is not None else None
        candidate = {
            "value": round(value, 2) if value is not None else None,
            "count": int(count) if count is not None else None,
            "scale": _to_number(str(rating.get("bestRating") or "5")) or 5,
        }
        if candidate["value"] is None and candidate["count"] is None:
            continue
        if best is None or (candidate["count"] or 0) > (best["count"] or 0):
            best = candidate
    return best


def _normalized_text(text: str) -> str:
    return " ".join(text.split()).lower()


def page_facts(url: str, html: str, text: str = "") -> dict:
    """Hasilkan fakta halaman: audit dasar, harga, rating, dan sidik isi."""
    parser = _PageParser()
    try:
        parser.feed(html)
        parser.close()  # HTML rusak sering tidak menutup <title>; close() mengeluarkan sisa teks
    except Exception:  # noqa: BLE001 - HTML rusak tidak boleh menggagalkan pemantauan
        pass
    parser.finish()
    plain = _normalized_text(text or "")
    nodes, types = _walk_json_ld(parser.json_ld)
    # Bila halaman menyertakan harga pada data terstruktur, pola teks diabaikan:
    # teks sering memuat harga lama, harga coret, atau harga produk lain.
    structured = _dedupe_prices(_prices_from_ld(nodes))
    prices = structured if structured else _dedupe_prices(_prices_from_text(parser))
    base = urlsplit(url)
    internal = external = 0
    for href in parser.links:
        absolute = urljoin(url, href)
        if urlsplit(absolute).netloc.lower() in ("", base.netloc.lower()):
            internal += 1
        else:
            external += 1
    return {
        "url": url,
        "title": parser.title.strip()[:300],
        "description": parser.description.strip()[:500],
        "lang": parser.lang.strip()[:20],
        "canonical": parser.canonical[:500],
        "noindex": "noindex" in parser.robots_meta.lower(),
        "robots_meta": parser.robots_meta.strip()[:200],
        "has_viewport": bool(parser.viewport),
        "h1": parser.h1[:5],
        "h1_count": len(parser.h1),
        "h2": parser.h2[:MAX_HEADINGS],
        "images": parser.images,
        "images_without_alt": parser.images_without_alt,
        "links_internal": internal,
        "links_external": external,
        "schema_types": sorted(set(types))[:40],
        "has_local_business": any(
            t in types for t in ("LocalBusiness", "Store", "Restaurant", "HealthAndBeautyBusiness", "ProfessionalService")
        ),
        "has_organization": any(t in types for t in ("Organization", "Corporation", "OnlineStore")),
        "prices": prices,
        "rating": _ratings(nodes),
        "word_count": len(plain.split()),
        "content_hash": fingerprint(plain),
    }


def fingerprint(*parts: object) -> str:
    """Sidik ringkas untuk mendeteksi perubahan tanpa menyimpan isi mentah."""
    text = "\u241f".join(str(part) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def format_amount(amount: float, currency: str) -> str:
    """Format angka gaya Indonesia: titik untuk ribuan, koma untuk desimal."""
    whole, _, fraction = f"{float(amount):,.2f}".partition(".")
    whole = whole.replace(",", ".")
    fraction = fraction.rstrip("0")
    return f"{currency} {whole},{fraction}" if fraction else f"{currency} {whole}"


def lowest_price(facts: dict) -> dict | None:
    prices = facts.get("prices") or []
    if not prices:
        return None
    return min(prices, key=lambda row: row["amount"])


def readable_prices(facts: dict) -> str:
    rows = facts.get("prices") or []
    if not rows:
        return "tidak ada harga terbaca"
    return ", ".join(format_amount(row["amount"], row["currency"]) for row in rows[:4])
