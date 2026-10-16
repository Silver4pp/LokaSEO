"""Uji penyimpanan SQLite: sasaran, potret, perubahan, dan pemangkasan riwayat."""

import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar.store import Store  # noqa: E402


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "radar.sqlite3"
        self.store = Store(self.path)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    # -- sasaran ------------------------------------------------------------
    def test_add_and_list_target(self):
        row = self.store.add_target("https://contoh.test/harga", "Kompetitor A", "harga")
        self.assertEqual(row["url"], "https://contoh.test/harga")
        self.assertEqual(row["label"], "Kompetitor A")
        self.assertEqual(row["kind"], "harga")
        self.assertEqual(len(self.store.targets()), 1)

    def test_duplicate_url_updates_label_instead_of_duplicating(self):
        first = self.store.add_target("https://contoh.test/harga", "A")
        second = self.store.add_target("https://contoh.test/harga", "B")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["label"], "B")
        self.assertEqual(len(self.store.targets()), 1)

    def test_invalid_scheme_is_rejected(self):
        for url in ("ftp://contoh.test", "contoh.test/harga", ""):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.store.add_target(url)

    def test_find_and_remove_by_url_and_id(self):
        row = self.store.add_target("https://contoh.test/a")
        self.assertIsNotNone(self.store.find_target("https://contoh.test/a"))
        self.assertEqual(self.store.remove_target("https://contoh.test/a"), row["id"])
        self.assertEqual(self.store.targets(), [])
        other = self.store.add_target("https://contoh.test/b")
        self.assertEqual(self.store.remove_target(str(other["id"])), other["id"])

    def test_remove_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.store.remove_target("https://tidak-ada.test/")

    def test_enable_flag_filters(self):
        row = self.store.add_target("https://contoh.test/a")
        self.store.set_enabled(row["id"], False)
        self.assertEqual(self.store.targets(), [dict(row, enabled=0)])
        self.assertEqual(self.store.targets(enabled_only=True), [])

    # -- potret -------------------------------------------------------------
    def test_snapshot_round_trip(self):
        row = self.store.add_target("https://contoh.test/a")
        self.store.save_snapshot(row["id"], 200, {"title": "Halo", "prices": []}, 123)
        latest = self.store.latest_snapshot(row["id"])
        self.assertEqual(latest["facts"]["title"], "Halo")
        self.assertEqual(latest["status"], 200)
        self.assertEqual(latest["elapsed_ms"], 123)
        self.assertEqual(self.store.snapshot_count(row["id"]), 1)

    def test_latest_snapshot_is_the_newest(self):
        row = self.store.add_target("https://contoh.test/a")
        self.store.save_snapshot(row["id"], 200, {"title": "Lama"})
        time.sleep(1.1)  # stempel waktu beresolusi detik
        self.store.save_snapshot(row["id"], 200, {"title": "Baru"})
        self.assertEqual(self.store.latest_snapshot(row["id"])["facts"]["title"], "Baru")

    def test_missing_snapshot_returns_none(self):
        row = self.store.add_target("https://contoh.test/a")
        self.assertIsNone(self.store.latest_snapshot(row["id"]))

    def test_removing_target_removes_history(self):
        row = self.store.add_target("https://contoh.test/a")
        self.store.save_snapshot(row["id"], 200, {"title": "x"})
        self.store.save_changes(row["id"], [{"type": "judul_berubah", "severity": "sedang", "message": "m"}])
        self.store.remove_target(str(row["id"]))
        self.assertEqual(self.store.change_count(), 0)
        self.assertEqual(self.store.stats()["potret"], 0)

    # -- perubahan ----------------------------------------------------------
    def test_changes_round_trip_with_filters(self):
        row = self.store.add_target("https://contoh.test/a", "A")
        self.store.save_changes(
            row["id"],
            [
                {"type": "harga_turun", "severity": "tinggi", "message": "turun", "before": "150", "after": "120"},
                {"type": "judul_berubah", "severity": "rendah", "message": "judul", "before": "a", "after": "b"},
            ],
        )
        self.assertEqual(self.store.change_count(), 2)
        high = self.store.changes(severities=("tinggi",))
        self.assertEqual(len(high), 1)
        self.assertEqual(high[0]["type"], "harga_turun")
        self.assertEqual(high[0]["before"], "150")
        self.assertEqual(high[0]["label"], "A")

    def test_changes_filter_by_time_and_target(self):
        first = self.store.add_target("https://contoh.test/a")
        second = self.store.add_target("https://contoh.test/b")
        self.store.save_changes(first["id"], [{"type": "x", "severity": "info", "message": "m"}])
        self.store.save_changes(second["id"], [{"type": "y", "severity": "info", "message": "m"}])
        self.assertEqual(len(self.store.changes(target_id=second["id"])), 1)
        self.assertEqual(len(self.store.changes(since="2000-01-01T00:00:00Z")), 2)
        self.assertEqual(len(self.store.changes(since="2999-01-01T00:00:00Z")), 0)

    def test_changes_limit_applies(self):
        row = self.store.add_target("https://contoh.test/a")
        self.store.save_changes(
            row["id"], [{"type": "x", "severity": "info", "message": f"m{i}"} for i in range(5)]
        )
        self.assertEqual(len(self.store.changes(limit=3)), 3)

    # -- keadaan dan pemangkasan -------------------------------------------
    def test_state_round_trip(self):
        self.assertIsNone(self.store.get_state("tidak-ada"))
        self.store.set_state("terakhir_jalan", "2026-10-12T00:00:00Z")
        self.assertEqual(self.store.get_state("terakhir_jalan"), "2026-10-12T00:00:00Z")
        self.store.set_state("terakhir_jalan", "2026-10-13T00:00:00Z")
        self.assertEqual(self.store.get_state("terakhir_jalan"), "2026-10-13T00:00:00Z")

    def test_prune_keeps_minimum_per_target(self):
        row = self.store.add_target("https://contoh.test/a")
        for index in range(8):
            self.store.save_snapshot(row["id"], 200, {"title": f"v{index}"})
        removed = self.store.prune_snapshots(days=0, keep_min=3)
        self.assertEqual(removed, 5)
        self.assertEqual(self.store.snapshot_count(row["id"]), 3)

    def test_stats_shape(self):
        row = self.store.add_target("https://contoh.test/a")
        self.store.save_snapshot(row["id"], 200, {"title": "x"})
        stats = self.store.stats()
        self.assertEqual(stats["sasaran"], 1)
        self.assertEqual(stats["potret"], 1)
        self.assertEqual(stats["perubahan"], 0)
        self.assertIn("radar.sqlite3", stats["database"])


if __name__ == "__main__":
    unittest.main()
