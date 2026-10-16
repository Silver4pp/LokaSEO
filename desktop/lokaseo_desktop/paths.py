"""Lokasi berkas milik pengguna.

Semua data tersimpan di dalam komputer pengguna. Tidak ada direktori daring, tidak
ada unggahan otomatis.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import config


def data_dir() -> Path:
    override = os.environ.get("LOKA_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    elif sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        path = Path(base) / config.APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / config.APP_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
        path = Path(base) / config.APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def asset_path(name: str) -> Path | None:
    """Cari berkas di folder `assets/` (source maupun di dalam paket)."""
    candidates = []
    if getattr(sys, "_MEIPASS", None):
        candidates.append(Path(sys._MEIPASS) / "assets" / name)
    module_root = Path(__file__).resolve().parent.parent
    candidates.append(module_root / "assets" / name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def log_file() -> Path:
    return data_dir() / "lokaseo.log"


def static_root(bundled: Path | None = None) -> Path:
    """Cari direktori build: dalam paket PyInstaller atau di samping source."""
    override = os.environ.get("LOKA_STATIC_ROOT")
    if override:
        return Path(override).expanduser()
    candidates = []
    if bundled:
        candidates.append(bundled)
    if getattr(sys, "_MEIPASS", None):
        candidates.append(Path(sys._MEIPASS) / config.STATIC_ROOT_NAME)
    module_root = Path(__file__).resolve().parent.parent.parent
    candidates.append(module_root / config.STATIC_ROOT_NAME)
    candidates.append(Path.cwd() / config.STATIC_ROOT_NAME)
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return candidates[0]


def configure_logging(verbose: bool = False) -> None:
    handlers: list[logging.Handler] = [
        RotatingFileHandler(log_file(), maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    ]
    if verbose:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )
