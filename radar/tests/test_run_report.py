"""Uji alur pemeriksaan dan penyusunan laporan, tanpa jaringan."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar import config, report  # noqa: E402
from lokaradar.fetch import BlockedError, FetchError, Fetcher, RateLimiter  # noqa: E402
from lokaradar.run import run_once  # noqa: E402
from lokaradar.store import Store  # noqa: E402

PAGE_V1 = """<!doctype html><html lang="id"><head><title>Kopi Bogor</title>
<meta name="description" content="Kopi segar Bogor">
<script type="application/ld+json">{"@type":"LocalBusiness","name":"Kopi Bogor",
"aggregateRating":{"ratingValue":"4.5","reviewCount":"100"},
"review":{"author":{"name":"Siti Rahayu"},"reviewBody":"Pelayanan ramah sekali"},
"offers":{"price":"150000","priceCurrency":"IDR"}}</script></head>
<body><h1>Kopi</h1><h2>Layanan Katering</h2><p>Rp 150.000</p></body></html>"""

PAGE_V2 = PAGE_V1.replace('"price":"150000"', '"price":"120000"').replace(
    '"reviewCount":"100"', '"reviewCount":"130"'
).replace("Kopi Bogor</title>", "Kopi Bogor Terbaru</title>")


class FakeRobots:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    def check(self, url: str, refresh: bool = False):
        return type(
            "V", (), {"allowed": self.allowed, "crawl_delay": None, "reason": "uji", "sitemaps": []}
        )()


class Pages:
    """Peniru pengambil halaman: mengembalikan isi berbeda pada putaran berbeda."""

    def __init__(self, pages: list[str], robots=None, errors: dict | None = None) -> None:
        self.pages = pages
        self.robots = robots or FakeRobots()
        self.errors = errors or {}
        self.round = 0
        self.loaded: list[str] = []

    def fetcher(self) -> Fetcher:
        def loader(url: str, timeout: float):
            self.loaded.append(url)
            if url in self.errors:
                raise self.errors[url]
            html = self.pages[min(self.round, len(self.pages) - 1)]
            return type(
                "P",
                (),
                {
                    "url": url,
                    "status": 200,
                    "html": html,
                    "text": html,
                    "elapsed_ms": 5,
                    "final_url": url,
                    "ok": True,
                },
            )()

        def robots_loader(url: str):
            return type("R", (), {"status": 404, "text": ""})()

        return Fetcher(
            robots=self.robots if isinstance(self.robots, FakeRobots) else None,
            limiter=RateLimiter(0.0),
            page_loader=loader,
        )


class RunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "radar.sqlite3")
        self.store.add_target("https://contoh.test/kopi", "Kompetitor Kopi", "harga")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_first_run_records_baseline(self):
        pages = Pages([PAGE_V1])
        result = run_once(self.store, pages.fetcher())
        self.assertEqual(result["diperiksa"], 1)
        self.assertEqual(result["gagal"], 0)
        self.assertEqual(result["sasaran"][0]["changes"][0]["type"], "pemantauan_dimulai")
        self.assertEqual(self.store.snapshot_count(1), 1)

    def test_second_run_detects_price_and_review_change(self):
        run_once(self.store, Pages([PAGE_V1]).fetcher())
        pages = Pages([PAGE_V2])
        pages.round = 0
        result = run_once(self.store, pages.fetcher())
        kinds = [row["type"] for row in result["sasaran"][0]["changes"]]
        self.assertIn("harga_turun", kinds)
        self.assertIn("jumlah_ulasan_berubah", kinds)
        self.assertIn("judul_berubah", kinds)
        # Perubahan isi tidak perlu dilaporkan karena judul dan harga sudah menjelaskannya.
        self.assertNotIn("isi_berubah", kinds)
        self.assertEqual(self.store.snapshot_count(1), 2)
        self.assertGreaterEqual(self.store.change_count(), 3)

    def test_no_change_on_identical_page(self):
        run_once(self.store, Pages([PAGE_V1]).fetcher())
        result = run_once(self.store, Pages([PAGE_V1]).fetcher())
        self.assertEqual(result["sasaran"][0]["changes"], [])

    def test_blocked_target_is_reported_without_crashing(self):
        fetcher = Pages([PAGE_V1], robots=FakeRobots(False)).fetcher()
        result = run_once(self.store, fetcher)
        self.assertEqual(result["dilewati"], 1)
        self.assertEqual(result["diperiksa"], 0)
        self.assertTrue(result["sasaran"][0]["blocked"])
        self.assertEqual(self.store.snapshot_count(1), 0, "potret tidak boleh disimpan saat ditolak")

    def test_fetch_error_is_reported_without_crashing(self):
        fetcher = Pages([PAGE_V1], errors={"https://contoh.test/kopi": OSError("mati")}).fetcher()
        result = run_once(self.store, fetcher)
        self.assertEqual(result["gagal"], 1)
        self.assertIn("mati", result["sasaran"][0]["error"])

    def test_max_pages_limits_work(self):
        self.store.add_target("https://contoh.test/kedua", "Kedua")
        pages = Pages([PAGE_V1])
        result = run_once(self.store, pages.fetcher(), max_pages=1)
        self.assertEqual(result["diperiksa"], 1)
        self.assertEqual(self.store.snapshot_count(1) + self.store.snapshot_count(2), 1)

    def test_only_one_target_when_requested(self):
        self.store.add_target("https://contoh.test/kedua", "Kedua")
        result = run_once(self.store, Pages([PAGE_V1]).fetcher(), only_id=2)
        self.assertEqual([row["url"] for row in result["sasaran"]], ["https://contoh.test/kedua"])


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "radar.sqlite3")
        self.store.add_target("https://contoh.test/kopi", "Kompetitor Kopi", "harga")
        run_once(self.store, Pages([PAGE_V1]).fetcher())
        run_once(self.store, Pages([PAGE_V2]).fetcher())

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def rows(self) -> list[dict]:
        target = self.store.targets()[0]
        snapshot = self.store.latest_snapshot(int(target["id"]))
        return [
            {
                "url": target["url"],
                "label": target["label"],
                "kind": target["kind"],
                "fetched_at": snapshot["fetched_at"],
                "status": snapshot["status"],
                "facts": snapshot["facts"],
                "changes": self.store.changes(target_id=int(target["id"])),
            }
        ]

    def test_pack_has_expected_schema_and_summary(self):
        pack = report.build_pack(self.rows())
        self.assertEqual(pack["schema"], config.INSIGHT_SCHEMA)
        self.assertEqual(pack["ringkasan"]["sasaran"], 1)
        self.assertGreater(pack["ringkasan"]["perubahan"], 0)
        self.assertIn("per_tingkat", pack["ringkasan"])

    def test_pack_carries_facts_and_prices(self):
        pack = report.build_pack(self.rows())
        target = pack["sasaran"][0]
        self.assertEqual(target["judul"], "Kopi Bogor Terbaru")
        self.assertEqual(target["rating"]["count"], 130)
        self.assertEqual([row["amount"] for row in target["harga"]], [120000.0])
        self.assertIn("LocalBusiness", target["data_terstruktur"])

    def test_new_section_becomes_content_idea(self):
        """Bagian baru di halaman pesaing harus muncul sebagai usulan ide konten."""
        store = self.store
        target = store.targets()[0]
        store.save_changes(
            int(target["id"]),
            [
                {
                    "type": "bagian_baru",
                    "severity": "sedang",
                    "message": "Bagian baru di halaman: \u201cLayanan Pernikahan\u201d.",
                    "before": None,
                    "after": "Layanan Pernikahan",
                }
            ],
        )
        rows = self.rows()
        pack = report.build_pack(rows)
        titles = " ".join(item["judul"] for item in pack["lokaseo"]["ide_konten"])
        self.assertIn("Layanan Pernikahan", titles)

    def test_suggestions_are_generated_from_changes(self):
        pack = report.build_pack(self.rows())
        lokaseo = pack["lokaseo"]
        self.assertTrue(lokaseo["ide_konten"], "perubahan harga dan ulasan harus menghasilkan ide konten")
        self.assertTrue(lokaseo["cek_list"])
        titles = " ".join(item["judul"].lower() for item in lokaseo["ide_konten"])
        self.assertTrue("ulasan" in titles or "harga" in titles)
        for item in lokaseo["ide_konten"]:
            self.assertEqual(item["sumber"], "LokaRadar")
            self.assertTrue(item["alasan"])

    def test_pack_never_carries_reviewer_identity(self):
        """Halaman uji memuat nama dan isi ulasan; keduanya tidak boleh ikut tersimpan."""
        pack = report.build_pack(self.rows())
        dumped = json.dumps(pack, ensure_ascii=False)
        self.assertNotIn("Siti Rahayu", dumped)
        self.assertNotIn("Pelayanan ramah", dumped)
        self.assertNotIn("author", dumped.lower())
        self.assertNotIn("reviewBody", dumped)

    def test_markdown_contains_key_sections(self):
        text = report.markdown(report.build_pack(self.rows()))
        self.assertIn("# Laporan LokaRadar", text)
        self.assertIn("Kompetitor Kopi", text)
        self.assertIn("Usulan ide konten", text)
        self.assertIn("Butir ceklis", text)
        self.assertIn("harga_turun" if "harga_turun" in text else "turun", text.lower())

    def test_write_reports_creates_both_files(self):
        pack = report.build_pack(self.rows())
        paths = report.write_reports(pack, Path(self.tmp.name), stamp="uji")
        self.assertTrue(paths["json"].is_file())
        self.assertTrue(paths["markdown"].is_file())
        reloaded = json.loads(paths["json"].read_text(encoding="utf-8"))
        self.assertEqual(reloaded["schema"], config.INSIGHT_SCHEMA)
        self.assertIn("Laporan LokaRadar", paths["markdown"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
