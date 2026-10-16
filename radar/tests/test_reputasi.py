"""Uji papan reputasi lokal: riwayat, laju ulasan, tanda perhatian, dan usulan."""

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar import reputasi  # noqa: E402
from lokaradar.report import build_pack, markdown  # noqa: E402
from lokaradar.store import Store  # noqa: E402


def stamp(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


class BoardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "radar.sqlite3")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def riwayat(self, url: str, label: str, poin: list[tuple[int, float, int]], kind: str = "reputasi") -> int:
        """poin: daftar (hari_lalu, rating, jumlah_ulasan) dari yang paling lama."""
        target = self.store.add_target(url, label, kind)
        for days_ago, rating, ulasan in poin:
            snapshot_id = self.store.save_snapshot(
                int(target["id"]), 200, {"title": label, "rating": {"value": rating, "count": ulasan, "scale": 5}}
            )
            self.store.connection.execute(
                "UPDATE snapshots SET fetched_at = ? WHERE id = ?", (stamp(days_ago), snapshot_id)
            )
        self.store.connection.commit()
        return int(target["id"])

    # -- profil -------------------------------------------------------------
    def test_profile_computes_growth_and_velocity(self):
        self.riwayat("https://a.test/", "Usaha A", [(28, 4.4, 100), (14, 4.5, 114), (0, 4.6, 128)])
        row = reputasi.profile(self.store, self.store.targets()[0], days=30)
        self.assertEqual(row["rating"], 4.6)
        self.assertEqual(row["rating_awal"], 4.4)
        self.assertEqual(row["perubahan_rating"], 0.2)
        self.assertEqual(row["ulasan_baru"], 28)
        self.assertEqual(row["laju_mingguan"], 7.0)
        self.assertEqual(row["hari_terukur"], 28.0)
        self.assertEqual(len(row["titik"]), 3)

    def test_profile_without_rating_is_honest(self):
        self.riwayat("https://b.test/", "Tanpa rating", [(2, 4.0, 10)])
        target = self.store.targets()[0]
        self.store.save_snapshot(int(target["id"]), 200, {"title": "Tanpa rating"})
        self.store.connection.execute("UPDATE snapshots SET fetched_at = ? WHERE id = 2", (stamp(0),))
        self.store.connection.commit()
        row = reputasi.profile(self.store, target, days=30)
        self.assertEqual(row["jumlah_potret"], 2)

    def test_profile_with_single_point_has_no_velocity(self):
        self.riwayat("https://c.test/", "Satu titik", [(1, 4.9, 40)])
        row = reputasi.profile(self.store, self.store.targets()[0], days=30)
        self.assertIsNone(row["laju_mingguan"])
        self.assertIsNone(row["ulasan_baru"])

    def test_profile_ignores_old_history_outside_period(self):
        self.riwayat("https://d.test/", "Lama", [(120, 3.0, 5), (2, 4.8, 90)])
        row = reputasi.profile(self.store, self.store.targets()[0], days=30)
        self.assertEqual(row["rating_awal"], 4.8, "potret di luar periode tidak boleh dipakai")

    # -- tanda --------------------------------------------------------------
    def test_flags_for_low_and_falling_rating(self):
        self.riwayat("https://e.test/", "Turun", [(20, 4.5, 100), (0, 3.8, 96)])
        row = reputasi.profile(self.store, self.store.targets()[0], days=30)
        kode = set(reputasi.tanda(row))
        self.assertIn("rating_rendah", kode)
        self.assertIn("rating_turun", kode)
        self.assertIn("ulasan_menurun", kode)

    def test_flag_for_slow_reviews(self):
        self.riwayat("https://f.test/", "Lambat", [(28, 4.6, 100), (0, 4.6, 101)])
        row = reputasi.profile(self.store, self.store.targets()[0], days=30)
        self.assertIn("ulasan_lambat", reputasi.tanda(row))

    def test_places_source_is_marked_without_becoming_a_warning(self):
        """Sumber resmi bukan masalah: cukup ditandai di kolom Sumber."""
        self.riwayat("tempat:ChIJabcdefg", "Tempat resmi", [(0, 4.7, 210)])
        row = reputasi.profile(self.store, self.store.targets()[0], days=30)
        self.assertEqual(row["sumber"], "places-api")
        self.assertNotIn("tempat_resmi", reputasi.tanda(row))
        self.assertIn("Places API", reputasi.board_markdown(reputasi.board(self.store, days=30)))

    def test_healthy_profile_has_no_warning_flags(self):
        self.riwayat("https://g.test/", "Sehat", [(28, 4.7, 200), (0, 4.8, 240)])
        row = reputasi.profile(self.store, self.store.targets()[0], days=30)
        self.assertEqual(reputasi.tanda(row), [])

    # -- papan --------------------------------------------------------------
    def test_board_ranks_by_rating_then_reviews(self):
        self.riwayat("https://p1.test/", "Pesaing A", [(20, 4.3, 90), (0, 4.4, 120)])
        self.riwayat("https://p2.test/", "Pesaing B", [(20, 4.4, 500), (0, 4.4, 520)])
        self.riwayat("https://mine.test/", "Usaha Saya", [(20, 4.6, 60), (0, 4.7, 75)])
        papan = reputasi.board(self.store, days=30)
        urutan = [row["label"] for row in papan["peringkat"]]
        self.assertEqual(urutan, ["Usaha Saya", "Pesaing B", "Pesaing A"])
        self.assertEqual(papan["peringkat"][0]["peringkat"], 1)
        self.assertEqual(papan["ringkasan"]["usaha"], 3)
        self.assertEqual(papan["ringkasan"]["total_ulasan_baru"], 65)
        self.assertAlmostEqual(papan["ringkasan"]["rata_rata_rating"], 4.5, places=2)

    def test_ranking_uses_ratio_when_scales_differ(self):
        """Rating 9,9 dari 10 (setara 4,95) harus mengalahkan 4,8 dari 5."""
        self.riwayat("https://skala10.test/", "Setara 4,95", [(1, 9.9, 100)])
        target = self.store.find_target("https://skala10.test/")
        self.store.connection.execute(
            "UPDATE snapshots SET facts = ? WHERE target_id = ?",
            (
                '{"title": "Setara 4,95", "rating": {"value": 9.9, "count": 100, "scale": 10.0}}',
                int(target["id"]),
            ),
        )
        self.store.connection.commit()
        self.riwayat("https://skala5.test/", "Setara 4,8", [(1, 4.8, 100)])
        papan = reputasi.board(self.store, days=30)
        self.assertEqual([row["label"] for row in papan["peringkat"]], ["Setara 4,95", "Setara 4,8"])
        self.assertEqual(papan["peringkat"][0]["rasio"], 0.99)
        self.assertTrue(any("Skala rating berbeda" in note for note in papan["catatan"]))
        teks = reputasi.board_markdown(papan)
        self.assertIn("Setara", teks)
        self.assertIn("4.95 / 5", teks)

    def test_board_shares_are_relative_to_total(self):
        self.riwayat("https://p1.test/", "A", [(1, 4.5, 100)])
        self.riwayat("https://p2.test/", "B", [(1, 4.5, 300)])
        papan = reputasi.board(self.store, days=30)
        pangsa = {row["label"]: row["pangsa_ulasan"] for row in papan["peringkat"]}
        self.assertEqual(pangsa, {"B": 75.0, "A": 25.0})

    def test_board_separates_targets_without_rating(self):
        self.riwayat("https://p1.test/", "Ada rating", [(1, 4.5, 100)])
        target = self.store.add_target("https://nol.test/", "Belum ada rating")
        self.store.save_snapshot(int(target["id"]), 200, {"title": "Belum ada rating"})
        papan = reputasi.board(self.store, days=30)
        self.assertEqual(len(papan["peringkat"]), 1)
        self.assertEqual(papan["ringkasan"]["tanpa_rating"], 1)
        labels = [row["label"] for row in papan["perhatian"]]
        self.assertIn("Belum ada rating", labels)

    def test_target_without_snapshot_is_not_put_on_the_board(self):
        """Sasaran yang belum pernah berhasil diperiksa tidak memenuhi papan."""
        self.riwayat("https://p1.test/", "Ada rating", [(1, 4.5, 100)])
        self.store.add_target("https://terlarang.test/", "Halaman terlarang", "reputasi")
        papan = reputasi.board(self.store, days=30)
        self.assertEqual([row["label"] for row in papan["peringkat"]], ["Ada rating"])
        self.assertEqual(papan["ringkasan"]["usaha"], 1)
        labels = [row["label"] for row in papan["perhatian"]]
        self.assertNotIn("Halaman terlarang", labels, "sasaran tanpa potret tidak perlu masuk daftar perhatian")
        self.assertEqual(papan["belum_terperiksa"], ["Halaman terlarang"])

    def test_scale_is_shown_without_trailing_zero(self):
        self.riwayat("https://skala.test/", "Skala", [(1, 4.5, 100)])
        teks = reputasi.board_markdown(reputasi.board(self.store, days=30))
        self.assertIn("4.5 / 5", teks)
        self.assertNotIn("5.0", teks)

    def test_disabled_target_is_left_out(self):
        target = self.riwayat("https://mati.test/", "Nonaktif", [(1, 4.5, 10)])
        self.store.set_enabled(target, False)
        papan = reputasi.board(self.store, days=30)
        self.assertEqual(papan["peringkat"], [])
        self.assertEqual(papan["ringkasan"]["usaha"], 0)

    # -- Markdown dan usulan ------------------------------------------------
    def test_markdown_table_lists_businesses(self):
        self.riwayat("https://p1.test/", "Pesaing A", [(20, 4.3, 90), (0, 4.4, 120)])
        potongan = reputasi.board_markdown(reputasi.board(self.store, days=30))
        self.assertIn("## Papan reputasi lokal", potongan)
        self.assertIn("Pesaing A", potongan)
        self.assertIn("Laju/minggu", potongan)
        self.assertIn("Hanya angka agregat", potongan)

    def test_suggestions_from_flags(self):
        self.riwayat("https://tur.test/", "Rating Turun", [(20, 4.5, 100), (0, 3.9, 99)])
        papan = reputasi.board(self.store, days=30)
        ide, ceklis, catatan = reputasi.suggestions(papan)
        judul_ide = " ".join(item["judul"].lower() for item in ide)
        self.assertIn("membalas ulasan", judul_ide)
        judul_ceklis = " ".join(item["judul"].lower() for item in ceklis)
        self.assertIn("ulasan", judul_ceklis)
        self.assertTrue(any("berkurang" in note for note in catatan))

    def test_suggestions_for_missing_rating(self):
        target = self.store.add_target("https://kosong.test/", "Kosong")
        self.store.save_snapshot(int(target["id"]), 200, {"title": "Kosong"})
        papan = reputasi.board(self.store, days=30)
        _, _, catatan = reputasi.suggestions(papan)
        self.assertTrue(any("belum ada rating" in note.lower() for note in catatan))

    # -- laporan ------------------------------------------------------------
    def test_pack_and_markdown_include_reputation(self):
        self.riwayat("https://p1.test/", "Pesaing A", [(20, 4.3, 90), (0, 4.4, 120)])
        target = self.store.targets()[0]
        snapshot = self.store.latest_snapshot(int(target["id"]))
        rows = [
            {
                "url": target["url"],
                "label": target["label"],
                "kind": target["kind"],
                "fetched_at": snapshot["fetched_at"],
                "status": snapshot["status"],
                "facts": snapshot["facts"],
                "changes": [],
            }
        ]
        pack = build_pack(rows, store=self.store, days=30)
        self.assertIsNotNone(pack["reputasi"])
        self.assertEqual(pack["reputasi"]["peringkat"][0]["label"], "Pesaing A")
        teks = markdown(pack)
        self.assertIn("## Papan reputasi lokal", teks)
        self.assertIn("ide konten" if "ide konten" in teks.lower() else "Papan reputasi", teks)

    def test_pack_without_store_has_no_board(self):
        pack = build_pack([])
        self.assertIsNone(pack["reputasi"])


if __name__ == "__main__":
    unittest.main()
