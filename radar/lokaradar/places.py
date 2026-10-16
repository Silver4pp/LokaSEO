"""Sumber resmi opsional: Google Places API (New).

Mengapa bukan pengambilan halaman Google Maps?

- `robots.txt` Google melarang banyak jalur yang dipakai untuk menampilkan hasil
  pencarian dan peta, sehingga radar versi sopan akan menolak sendiri.
- Ketentuan Layanan Google Maps Platform §3.2.3 melarang menyalin nama usaha,
  alamat, dan ulasan tanpa izin tertulis.

Karena itu jalur resmi ini disediakan sebagai pilihan: pengguna memakai **kunci
API miliknya sendiri**. Kunci hanya dibaca dari argumen atau variabel lingkungan
`LOKARADAR_PLACES_KEY`, tidak pernah disimpan ke basis data, laporan, atau catatan.
Yang disimpan hanyalah angka agregat (rating dan jumlah ulasan) beserta
`place_id` — bukan teks ulasan, bukan identitas penulis ulasan.
"""

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from . import config
from .extract import fingerprint

ENDPOINT = "https://places.googleapis.com/v1/places/"
SEARCH_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = "id,displayName,rating,userRatingCount,formattedAddress,websiteUri"
SEARCH_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.rating,places.userRatingCount,places.websiteUri"
)
MAX_SEARCH_RESULTS = 10
KEY_ENV = "LOKARADAR_PLACES_KEY"
SCHEME = "tempat:"
PLACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{5,200}$")


class PlacesError(RuntimeError):
    """Permintaan ke Places API gagal atau tidak dapat dijalankan."""


@dataclass
class PlacesRequest:
    """Satu permintaan ke Places API. Kunci ikut di sini dan tidak pernah dicatat."""

    url: str
    key: str
    method: str = "GET"
    field_mask: str = FIELD_MASK
    payload: dict | None = None
    headers: dict = field(default_factory=dict)


def key_from_env() -> str | None:
    """Kunci API dari lingkungan. Tidak pernah ditulis ke basis data atau log."""
    value = (os.environ.get(KEY_ENV) or "").strip()
    return value or None


def place_id_of(alamat: str) -> str:
    """Ambil `place_id` dari alamat sasaran berawalan `tempat:`."""
    if not alamat.startswith(SCHEME):
        raise ValueError("Bukan alamat tempat")
    return alamat[len(SCHEME) :].strip()


def target_url(place_id: str) -> str:
    if not PLACE_ID_PATTERN.match(place_id or ""):
        raise ValueError("place_id tidak wajar (hanya huruf, angka, - dan _)")
    return f"{SCHEME}{place_id}"


def _default_loader(spec: PlacesRequest, timeout: float) -> tuple[int, str]:
    data = None
    headers = {
        "X-Goog-Api-Key": spec.key,
        "X-Goog-FieldMask": spec.field_mask,
        "Accept": "application/json",
        "User-Agent": config.USER_AGENT,
    }
    headers.update(spec.headers or {})
    if spec.payload is not None:
        data = json.dumps(spec.payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(spec.url, data=data, headers=headers, method=spec.method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - titik akhir tetap
            return int(response.status), response.read(1_000_000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as error:
        body = error.read(2000).decode("utf-8", "ignore") if hasattr(error, "read") else ""
        return int(error.code), body
    except urllib.error.URLError as error:
        raise PlacesError(f"Tidak dapat menghubungi Places API: {error.reason}") from error


def lookup(
    place_id: str,
    key: str,
    *,
    loader=None,
    timeout: float = config.DEFAULT_TIMEOUT,
) -> dict:
    """Ambil angka agregat satu tempat resmi. Kunci tidak pernah disimpan."""
    if not key:
        raise PlacesError(
            f"Butuh kunci Places API. Setel variabel lingkungan {KEY_ENV} (kunci Anda sendiri)."
        )
    if not PLACE_ID_PATTERN.match(place_id or ""):
        raise ValueError("place_id tidak wajar (hanya huruf, angka, - dan _)")
    pengambil = loader or _default_loader
    status, body = pengambil(PlacesRequest(url=f"{ENDPOINT}{place_id}", key=key), timeout)
    _periksa_galat(status, body)
    try:
        payload = json.loads(body or "{}")
    except ValueError as error:
        raise PlacesError("Jawaban Places API tidak dapat dibaca sebagai JSON.") from error
    if not isinstance(payload, dict):
        raise PlacesError("Jawaban Places API tidak berbentuk objek.")
    display = payload.get("displayName") or {}
    name = display.get("text") if isinstance(display, dict) else None
    return {
        "place_id": str(payload.get("id") or place_id),
        "name": str(name or ""),
        "address": str(payload.get("formattedAddress") or ""),
        "website": str(payload.get("websiteUri") or ""),
        "rating": payload.get("rating"),
        "count": payload.get("userRatingCount"),
    }


def _periksa_galat(status: int, body: str) -> None:
    """Terjemahkan kode galat Places API menjadi pesan yang bisa ditindaklanjuti."""
    if status < 400:
        return
    if status == 400:
        raise PlacesError(
            "Places API menolak permintaan (HTTP 400). Biasanya kunci belum benar "
            "atau Places API (New) belum diaktifkan pada proyek Google Cloud Anda."
        )
    if status == 401:
        raise PlacesError("Places API menolak kunci ini (HTTP 401). Periksa apakah kuncinya salah salin.")
    if status == 403:
        raise PlacesError(
            "Kunci ditolak (HTTP 403). Periksa pembatasan kunci dan apakah Places API (New) "
            "sudah diaktifkan untuk proyek itu."
        )
    if status == 404:
        raise PlacesError("Tempat tidak ditemukan di Places API (place_id salah atau sudah tidak aktif).")
    if status == 429:
        raise PlacesError(
            "Kuota Places API habis atau permintaan terlalu sering (HTTP 429). "
            "Tunggu, atau periksa kuota dan tagihan pada proyek Google Cloud Anda."
        )
    raise PlacesError(f"Places API menjawab HTTP {status}.")


def search_text(
    query: str,
    key: str,
    *,
    kota: str = "",
    max_results: int = 5,
    loader=None,
    timeout: float = config.DEFAULT_TIMEOUT,
) -> list[dict]:
    """Cari tempat lewat Places API Text Search, untuk mendapatkan `place_id`.

    Pencarian ini memakai SKU Text Search pada kuota Google Cloud Anda sendiri.
    Yang dikembalikan hanya identitas usaha dan angka agregat rating — tidak ada
    ulasan, tidak ada nama penulis ulasan.
    """
    if not key:
        raise PlacesError(
            f"Butuh kunci Places API. Setel variabel lingkungan {KEY_ENV} (kunci Anda sendiri)."
        )
    teks = " ".join((query or "").split())
    if not teks:
        raise ValueError("Kata pencarian tidak boleh kosong")
    if kota and kota.strip().lower() not in teks.lower():
        teks = f"{teks} {kota.strip()}"
    jumlah = max(1, min(int(max_results or 5), MAX_SEARCH_RESULTS))
    spec = PlacesRequest(
        url=SEARCH_ENDPOINT,
        key=key,
        method="POST",
        field_mask=SEARCH_FIELD_MASK,
        payload={"textQuery": teks, "maxResultCount": jumlah, "languageCode": "id", "regionCode": "ID"},
    )
    pengambil = loader or _default_loader
    status, body = pengambil(spec, timeout)
    _periksa_galat(status, body)
    try:
        payload = json.loads(body or "{}")
    except ValueError as error:
        raise PlacesError("Jawaban Places API tidak dapat dibaca sebagai JSON.") from error
    if not isinstance(payload, dict):
        raise PlacesError("Jawaban Places API tidak berbentuk objek.")
    hasil: list[dict] = []
    for item in payload.get("places") or []:
        if not isinstance(item, dict):
            continue
        display = item.get("displayName") or {}
        hasil.append(
            {
                "place_id": str(item.get("id") or ""),
                "name": str(display.get("text") or "") if isinstance(display, dict) else "",
                "address": str(item.get("formattedAddress") or ""),
                "website": str(item.get("websiteUri") or ""),
                "rating": item.get("rating"),
                "count": item.get("userRatingCount"),
            }
        )
    return [row for row in hasil if row["place_id"]]


def place_facts(place: dict, *, scale: float = 5.0) -> dict:
    """Ubah hasil Places API menjadi fakta bergaya `page_facts` agar bisa dibandingkan."""
    rating = place.get("rating")
    count = place.get("count")
    facts = {
        "title": place.get("name") or "",
        "description": "",
        "lang": "",
        "canonical": "",
        "noindex": False,
        "viewport": "",
        "h1": [],
        "h2": [],
        "images": 0,
        "images_without_alt": 0,
        "links": [],
        "schema_types": ["Place"],
        "prices": [],
        "rating": None,
        "word_count": 0,
        "sumber": "places-api",
        "alamat": place.get("address") or "",
    }
    if rating is not None or count is not None:
        facts["rating"] = {
            "value": float(rating) if rating is not None else None,
            "count": int(count) if count is not None else None,
            "scale": float(scale),
        }
    rating_row = facts.get("rating") or {}
    facts["content_hash"] = fingerprint(facts["title"], rating_row.get("value"), rating_row.get("count"), "places-api")
    return facts
