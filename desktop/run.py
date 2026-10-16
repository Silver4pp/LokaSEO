"""Titik masuk aplikasi desktop.

Jalankan dari source:
    python3 desktop/run.py

Dipakai juga sebagai entry point PyInstaller. Jalur `python -m lokaseo_desktop`
tetap tersedia bila paket ada di PYTHONPATH.
"""

import sys

from lokaseo_desktop.app import main

if __name__ == "__main__":
    raise SystemExit(main())
