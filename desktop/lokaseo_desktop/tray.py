"""Ikon system tray supaya aplikasi dapat dihentikan tanpa jendela konsol.

Bergantung pada `pystray` dan `Pillow`. Keduanya opsional: bila tidak terpasang,
aplikasi memakai cara lain (konsol atau halaman Hentikan LokaSEO).
"""

import logging
from pathlib import Path

from . import config

LOG = logging.getLogger("lokaseo")


def tray_available() -> bool:
    try:
        import PIL.Image  # noqa: F401
        import pystray  # noqa: F401
    except ImportError:
        return False
    return True


def _image(asset: Path | None):
    from PIL import Image

    if asset and asset.is_file():
        return Image.open(asset).convert("RGBA")
    # Cadangan: kotak hijau tua dengan huruf L, agar tray tetap terbaca.
    image = Image.new("RGBA", (64, 64), (26, 74, 53, 255))
    for x in range(20, 26):
        for y in range(14, 50):
            image.putpixel((x, y), (240, 248, 240, 255))
    for x in range(20, 44):
        for y in range(46, 50):
            image.putpixel((x, y), (240, 248, 240, 255))
    return image


def start(url: str, asset: Path | None, on_open, on_quit) -> object | None:
    """Tampilkan ikon tray. Kembalikan objek ikon, atau None bila tidak tersedia."""
    if not tray_available():
        return None
    import pystray

    def open_app(icon, item) -> None:  # noqa: ARG001 - tanda tangan pystray
        on_open()

    def quit_app(icon, item) -> None:  # noqa: ARG001
        icon.visible = False
        icon.stop()
        on_quit()

    icon = pystray.Icon(
        config.APP_ID,
        _image(asset),
        f"{config.APP_NAME} — klik untuk membuka, klik kanan untuk keluar",
        menu=pystray.Menu(
            pystray.MenuItem("Buka LokaSEO", open_app, default=True),
            pystray.MenuItem("Hentikan LokaSEO", quit_app),
        ),
    )
    try:
        icon.run_detached()
    except Exception:  # noqa: BLE001 - tray gagal tidak boleh menggagalkan aplikasi
        LOG.exception("Ikon tray tidak dapat ditampilkan")
        return None
    LOG.info("Ikon tray aktif. Klik kanan untuk menghentikan aplikasi.")
    return icon
