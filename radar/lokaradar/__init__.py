"""Radar pemantauan situs publik untuk LokaSEO.

Menjalankan pemeriksaan berkala atas halaman publik yang Anda tentukan, menyimpan
riwayat di komputer Anda sendiri, dan menghasilkan laporan yang bisa dipakai untuk
pekerjaan SEO di LokaSEO.
"""

from .config import APP_NAME, DATA_ENV, DEFAULT_DELAY_SECONDS, DEFAULT_TIMEOUT, USER_AGENT

__all__ = [
    "APP_NAME",
    "DATA_ENV",
    "DEFAULT_DELAY_SECONDS",
    "DEFAULT_TIMEOUT",
    "USER_AGENT",
    "__version__",
]

__version__ = "0.1.0"
