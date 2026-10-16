"""Uji antarmuka baris perintah: alur harian tanpa jaringan."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar.cli import _parse_since, main  # noqa: E402
from lokaradar.store import Store  # noqa: E402


def run_cli(argv: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(argv)
    return code, buffer.getvalue()


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.environ.get("LOKARADAR_DATA")
        os.environ["LOKARADAR_DATA"] = self.tmp.name
        self.store = Store(Path(self.tmp.name) / "radar.sqlite3")
        self.store.add_target("https://contoh.test/kopi", "Kompetitor Kopi", "harga")
        self.store.save_snapshot(
            1,
            200,
            {
                "title": "Kopi Bogor",
                "prices": [{"amount": 150000.0, "currency": "IDR", "source": "json-ld", "name": "Arabika"}],
                "rating": {"value": 4.5, "count": 100, "scale": 5},
                "schema_types": ["LocalBusiness"],
                "h2": ["Layanan Katering"],
                "word_count": 500,
                "images_without_alt": 1,
            },
            42,
        )
        self.store.save_changes(
            1,
            [
                {"type": "harga_turun", "severity": "tinggi", "message": "Harga turun 20%.", "before": "IDR 150.000", "after": "IDR 120.000"},
                {"type": "jumlah_ulasan_berubah", "severity": "sedang", "message": "Ulasan bertambah 30.", "before": 100, "after": 130},
            ],
        )
        self.store.close()

    def tearDown(self):
        if self.env is None:
            os.environ.pop("LOKARADAR_DATA", None)
        else:
            os.environ["LOKARADAR_DATA"] = self.env
        self.tmp.cleanup()

    def test_status_reports_engine_and_counts(self):
        code, output = run_cli(["status"])
        self.assertEqual(code, 0)
        self.assertIn("LokaRadar", output)
        self.assertIn("Sasaran", output)
        self.assertIn("Potret tersimpan", output)
        self.assertIn("Perubahan", output)

    def test_add_and_list(self):
        code, output = run_cli(["add", "https://contoh.test/kedua", "--label", "Pesaing B", "--kind", "layanan"])
        self.assertEqual(code, 0)
        self.assertIn("kedua", output)
        code, listing = run_cli(["list"])
        self.assertEqual(code, 0)
        self.assertIn("Kompetitor Kopi", listing)
        self.assertIn("Pesaing B", listing)
        self.assertIn("IDR 150.000", listing)

    def test_add_rejects_non_http_url(self):
        with self.assertRaises(ValueError):
            run_cli(["add", "contoh.test"])

    def test_remove_existing_and_missing(self):
        code, output = run_cli(["remove", "https://contoh.test/kopi"])
        self.assertEqual(code, 0)
        self.assertIn("dihapus", output)
        code, _ = run_cli(["remove", "https://tidak-ada.test/"])
        self.assertEqual(code, 5)

    def test_changes_filters_and_output(self):
        code, output = run_cli(["changes"])
        self.assertEqual(code, 0)
        self.assertIn("harga", output.lower())
        code, tinggi = run_cli(["changes", "--severity", "tinggi"])
        self.assertIn("Harga turun 20%.", tinggi)
        self.assertNotIn("Ulasan bertambah 30.", tinggi)

    def test_report_writes_files_and_summarises(self):
        outdir = Path(self.tmp.name) / "keluaran"
        code, output = run_cli(["report", "--days", "30", "--out", str(outdir)])
        self.assertEqual(code, 0)
        self.assertIn("Laporan Markdown", output)
        files = sorted(path.name for path in outdir.glob("*"))
        self.assertTrue(any(name.startswith("wawasan-") for name in files))
        self.assertTrue(any(name.startswith("laporan-") for name in files))
        pack = json.loads(next(outdir.glob("wawasan-*.json")).read_text(encoding="utf-8"))
        self.assertEqual(pack["schema"], "lokaradar.insight.v1")
        self.assertTrue(pack["lokaseo"]["ide_konten"])

    def test_export_writes_json(self):
        target = Path(self.tmp.name) / "perubahan.json"
        code, output = run_cli(["export", str(target)])
        self.assertEqual(code, 0)
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["perubahan"]), 2)

    def test_export_sasaran_menulis_daftar_yang_bisa_diimpor_kembali(self):
        target = Path(self.tmp.name) / "sasaran.json"
        code, output = run_cli(["export", str(target), "--sasaran"])
        self.assertEqual(code, 0, output)
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["format"], "lokaradar.sasaran.v1")
        self.assertEqual([item["url"] for item in payload["sasaran"]], ["https://contoh.test/kopi"])

        # Impor ulang berkas yang sama: tidak ada yang berubah, tidak ada yang hilang.
        code, output = run_cli(["import", str(target)])
        self.assertEqual(code, 0, output)
        self.assertIn("1 sudah ada", output)
        self.assertIn("Belum ada halaman yang dihubungi", output)

    def test_import_dry_run_tidak_menyimpan(self):
        berkas = Path(self.tmp.name) / "baru.txt"
        berkas.write_text("https://pesaing-baru.test/\n", encoding="utf-8")
        code, output = run_cli(["import", str(berkas), "--dry-run"])
        self.assertEqual(code, 0, output)
        self.assertIn("Uji coba: tidak ada yang disimpan.", output)
        with Store(Path(self.tmp.name) / "radar.sqlite3") as store:
            self.assertIsNone(store.find_target("https://pesaing-baru.test/"))

    def test_import_berkas_tidak_ada_dan_bukan_utf8(self):
        code, output = run_cli(["import", str(Path(self.tmp.name) / "hilang.json")])
        self.assertEqual(code, 2)
        self.assertIn("tidak ditemukan", output)

        rusak = Path(self.tmp.name) / "biner.txt"
        rusak.write_bytes(b"\xff\xfe\x00\x01")
        code, output = run_cli(["import", str(rusak)])
        self.assertEqual(code, 2)
        self.assertIn("UTF-8", output)

    def test_import_berkas_bukan_daftar_sasaran(self):
        salah = Path(self.tmp.name) / "laporan.json"
        salah.write_text(json.dumps({"perubahan": []}), encoding="utf-8")
        code, output = run_cli(["import", str(salah)])
        self.assertEqual(code, 2)
        self.assertIn("sasaran", output)

    def test_report_without_snapshot_returns_error(self):
        empty = tempfile.TemporaryDirectory()
        os.environ["LOKARADAR_DATA"] = empty.name
        code, output = run_cli(["report"])
        self.assertEqual(code, 1)
        self.assertIn("Belum ada potret", output)
        empty.cleanup()

    def test_run_without_targets_returns_error(self):
        empty = tempfile.TemporaryDirectory()
        os.environ["LOKARADAR_DATA"] = empty.name
        code, output = run_cli(["run"])
        self.assertEqual(code, 1)
        self.assertIn("Belum ada sasaran", output)
        empty.cleanup()


class SinceParsingTest(unittest.TestCase):
    def test_relative_units(self):
        for value in ("7d", "24h", "30m"):
            with self.subTest(value=value):
                stamp = _parse_since(value)
                self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_iso_passthrough_and_empty(self):
        self.assertEqual(_parse_since("2026-01-01T00:00:00Z"), "2026-01-01T00:00:00Z")
        self.assertIsNone(_parse_since(None))


if __name__ == "__main__":
    unittest.main()
