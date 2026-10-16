"""Batas, nilai bawaan, dan lokasi data radar.

Semua nilai di sini sengaja konservatif: permintaan pelan, jumlah halaman terbatas,
dan menghormati robots.txt. Perilaku sopan adalah syarat pertama alat ini berguna.
"""

import os
import sys
from pathlib import Path

APP_NAME = "LokaRadar"
DATA_ENV = "LOKARADAR_DATA"
INSIGHT_SCHEMA = "lokaradar.insight.v1"

# Identitas alat. Jangan menyamar sebagai peramban biasa pada jalur bawaan.
USER_AGENT = (
    "LokaRadar/0.1 (+https://github.com/every-app/open-seo; pemantauan SEO lokal; "
    "hubungi pemilik situs bila keberatan)"
)

DEFAULT_DELAY_SECONDS = 2.5  # jeda minimum antar permintaan ke host yang sama
# Header identitas yang dipakai semua jalur pengambilan halaman — jalur biasa,
# jalur Scrapling, maupun jalur peramban lokal. Disimpan di sini supaya janji
# "identitas jujur" tidak bisa terlupa hanya karena ada jalur baru.
HEADER_JUJUR = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.5",
}

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_BYTES = 3_000_000
DEFAULT_MAX_PAGES_PER_RUN = 40
ROBOTS_CACHE_HOURS = 12
SNAPSHOT_RETENTION_DAYS = 180

# Rendering peramban: dipakai untuk situs yang isinya dibuat oleh JavaScript.
# "auto" = satu permintaan biasa dulu; bila hasilnya hampir kosong, halaman
# diambil ulang dengan peramban. "selalu" = langsung peramban. "tidak" = mati.
RENDER_MODES = ("auto", "selalu", "tidak")
DEFAULT_RENDER = "auto"
RENDER_MIN_WORDS = 40  # di bawah ini halaman dianggap "tipis" (dibuat JavaScript)

# Perubahan harga di bawah persentase ini diabaikan agar laporan tidak bising.
PRICE_CHANGE_THRESHOLD_PERCENT = 1.0

# Mata uang yang dikenali beserta polanya pada teks halaman.
CURRENCY_PATTERNS = (
    ("IDR", r"(?:rp\.?|idr)\s?([0-9][0-9.,]*)"),
    # Simbol dolar dengan awalan mata uang lain harus dicoba lebih dulu,
    # kalau tidak "S$12" akan terbaca sebagai USD.
    ("SGD", r"(?:sgd|(?<![A-Za-z])s\$)\s?([0-9][0-9.,]*)"),
    ("MYR", r"(?:myr|rm)\s?([0-9][0-9.,]*)"),
    ("USD", r"(?:usd|(?<![A-Za-z])\$)\s?([0-9][0-9.,]*)"),
    ("EUR", r"(?:eur|(?<![A-Za-z])\u20ac)\s?([0-9][0-9.,]*)"),
    ("GBP", r"(?:gbp|(?<![A-Za-z])\u00a3)\s?([0-9][0-9.,]*)"),
)

SEVERITY_ORDER = {"info": 0, "rendah": 1, "sedang": 2, "tinggi": 3}


def data_dir() -> Path:
    override = os.environ.get(DATA_ENV)
    if override:
        path = Path(override).expanduser()
    elif sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        path = Path(base) / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
        path = Path(base) / APP_NAME.lower()
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return data_dir() / "radar.sqlite3"


def report_dir() -> Path:
    path = data_dir() / "laporan"
    path.mkdir(parents=True, exist_ok=True)
    return path
