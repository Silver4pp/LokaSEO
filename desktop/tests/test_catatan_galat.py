"""Uji pesan galat latar: pengguna melihat kalimat, bukan traceback."""

import sys
import tempfile
import threading
import unittest
from pathlib import Path

DESKTOP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESKTOP))

from lokaseo_desktop import app  # noqa: E402


class CatatanGalatLatarTest(unittest.TestCase):
    def setUp(self):
        self.asli = threading.excepthook
        self.tercetak: list[str] = []
        asli_cetak = app.cetak
        app.cetak = lambda teks="": self.tercetak.append(str(teks))  # type: ignore[assignment]
        self._pulih = asli_cetak
        app.pasang_catatan_galat_latar()

    def tearDown(self):
        threading.excepthook = self.asli
        app.cetak = self._pulih  # type: ignore[assignment]

    def _picu(self, galat: BaseException) -> None:
        def peledak():
            raise galat

        thread = threading.Thread(target=peledak, name="Thread-2")
        thread.start()
        thread.join()

    def _picu_dari_pystray(self, pesan: str) -> None:
        """Galat yang jejaknya memang berasal dari berkas pystray (seperti di Windows)."""
        kode = compile(f"raise OSError({pesan!r})", "pystray/_win32.py", "exec")

        def peledak():
            exec(kode, {"__name__": "pystray._win32"})  # noqa: S102 - meniru jejak galat

        thread = threading.Thread(target=peledak, name="Thread-2")
        thread.start()
        thread.join()

    def test_galat_tray_diganti_satu_kalimat(self):
        self._picu_dari_pystray("Invalid window handle.")
        teks = " ".join(self.tercetak)
        self.assertIn("ikon tray tidak bisa ditampilkan", teks)
        self.assertIn("Hentikan aplikasi", teks)
        self.assertNotIn("Traceback", teks)

    def test_galat_lain_tetap_diumumkan_singkat(self):
        self._picu(RuntimeError("sesuatu rusak"))
        teks = " ".join(self.tercetak)
        self.assertIn("galat di latar belakang", teks)
        self.assertIn("sesuatu rusak", teks)
        self.assertNotIn("Traceback", teks)

    def test_satu_baris_saja_per_galat(self):
        self._picu_dari_pystray("Invalid window handle.")
        self.assertEqual(len(self.tercetak), 1)


if __name__ == "__main__":
    unittest.main()
