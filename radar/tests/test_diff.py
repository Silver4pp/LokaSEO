"""Uji pembanding potret: jenis perubahan, tingkat kepentingan, dan ambang bising."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar.diff import compare, highest_severity  # noqa: E402


def facts(**changes) -> dict:
    base = {
        "url": "https://contoh.test/",
        "title": "Kopi Bogor",
        "description": "Kopi segar",
        "canonical": "https://contoh.test/",
        "noindex": False,
        "has_viewport": True,
        "images_without_alt": 1,
        "has_local_business": False,
        "prices": [{"amount": 150000.0, "currency": "IDR", "source": "json-ld", "name": "Arabika"}],
        "rating": {"value": 4.5, "count": 100, "scale": 5},
        "content_hash": "aaa",
        "word_count": 500,
        "schema_types": ["Product"],
        "h2": ["Layanan Katering"],
    }
    base.update(changes)
    return base


def types(changes: list[dict]) -> list[str]:
    return [row["type"] for row in changes]


class FirstSnapshotTest(unittest.TestCase):
    def test_first_snapshot_is_informational(self):
        changes = compare(None, facts())
        self.assertEqual(types(changes), ["pemantauan_dimulai"])
        self.assertEqual(highest_severity(changes), "info")


class PriceTest(unittest.TestCase):
    def test_large_drop_is_high_severity(self):
        changes = compare(facts(), facts(prices=[{"amount": 120000.0, "currency": "IDR", "name": "Arabika"}]))
        row = next(row for row in changes if row["type"] == "harga_turun")
        self.assertEqual(row["severity"], "tinggi")
        self.assertIn("20.0%", row["message"])
        self.assertEqual(row["before"], "IDR 150.000")
        self.assertEqual(row["after"], "IDR 120.000")

    def test_small_drop_is_medium_and_raise_is_low(self):
        drop = compare(facts(), facts(prices=[{"amount": 147000.0, "currency": "IDR", "name": "Arabika"}]))
        self.assertEqual(next(r for r in drop if r["type"] == "harga_turun")["severity"], "sedang")
        raise_ = compare(facts(), facts(prices=[{"amount": 153000.0, "currency": "IDR", "name": "Arabika"}]))
        self.assertEqual(next(r for r in raise_ if r["type"] == "harga_naik")["severity"], "rendah")

    def test_noise_below_threshold_is_ignored(self):
        changes = compare(facts(), facts(prices=[{"amount": 149900.0, "currency": "IDR", "name": "Arabika"}]))
        self.assertEqual(changes, [], "pergeseran di bawah 1% tidak boleh dilaporkan")

    def test_new_and_removed_prices(self):
        added = compare(facts(), facts(prices=[]))
        self.assertIn("harga_hilang", types(added))
        removed = compare(facts(prices=[]), facts())
        self.assertIn("harga_baru", types(removed))

    def test_currency_change_is_treated_as_new_price(self):
        changes = compare(facts(), facts(prices=[{"amount": 150000.0, "currency": "USD", "name": "Arabika"}]))
        self.assertIn("harga_baru", types(changes))
        self.assertIn("harga_hilang", types(changes))


class ReputationTest(unittest.TestCase):
    def test_rating_value_shift(self):
        changes = compare(facts(), facts(rating={"value": 4.1, "count": 100, "scale": 5}))
        self.assertIn("rating_berubah", types(changes))

    def test_small_rating_shift_is_ignored(self):
        changes = compare(facts(), facts(rating={"value": 4.45, "count": 100, "scale": 5}))
        self.assertNotIn("rating_berubah", types(changes))

    def test_review_count_growth_gets_severity_by_size(self):
        big = compare(facts(), facts(rating={"value": 4.5, "count": 130, "scale": 5}))
        small = compare(facts(), facts(rating={"value": 4.5, "count": 102, "scale": 5}))
        self.assertEqual(next(r for r in big if r["type"] == "jumlah_ulasan_berubah")["severity"], "sedang")
        self.assertEqual(next(r for r in small if r["type"] == "jumlah_ulasan_berubah")["severity"], "rendah")
        self.assertIn("bertambah 30", next(r for r in big if r["type"] == "jumlah_ulasan_berubah")["message"])

    def test_rating_missing_now_is_reported_as_change(self):
        changes = compare(facts(), facts(rating=None))
        self.assertNotIn("rating_berubah", types(changes))

    def test_scale_change_when_rating_moves_to_ten(self):
        changes = compare(facts(), facts(rating={"value": 9.1, "count": 100, "scale": 10}))
        self.assertIn("skala_rating_berubah", types(changes))
        self.assertIn("rating_berubah", types(changes))


class SectionTest(unittest.TestCase):
    def test_new_section_is_reported_with_heading(self):
        changes = compare(facts(h2=["Layanan Katering"]), facts(h2=["Layanan Katering", "Layanan Pernikahan"]))
        row = next(row for row in changes if row["type"] == "bagian_baru")
        self.assertEqual(row["after"], "Layanan Pernikahan")
        self.assertEqual(row["severity"], "sedang")
        self.assertIn("Layanan Pernikahan", row["message"])

    def test_removed_section_is_reported(self):
        changes = compare(facts(h2=["A", "B"]), facts(h2=["A"]))
        self.assertIn("bagian_hilang", types(changes))

    def test_unchanged_sections_produce_nothing(self):
        self.assertEqual(compare(facts(h2=["A", "B"]), facts(h2=["A", "B"])), [])


class SeoElementTest(unittest.TestCase):
    def test_noindex_appearing_is_high_severity(self):
        changes = compare(facts(), facts(noindex=True))
        row = next(row for row in changes if row["type"] == "noindex_aktif")
        self.assertEqual(row["severity"], "tinggi")

    def test_noindex_removed_is_informational(self):
        changes = compare(facts(noindex=True), facts(noindex=False))
        self.assertIn("noindex_dihapus", types(changes))

    def test_title_and_description_changes(self):
        changes = compare(facts(), facts(title="Kopi Baru", description="Baru"))
        self.assertIn("judul_berubah", types(changes))
        self.assertIn("deskripsi_berubah", types(changes))

    def test_canonical_change(self):
        changes = compare(facts(), facts(canonical="https://contoh.test/baru"))
        self.assertIn("canonical_berubah", types(changes))

    def test_content_change_with_word_delta(self):
        changes = compare(facts(), facts(content_hash="bbb", word_count=650))
        row = next(row for row in changes if row["type"] == "isi_berubah")
        self.assertIn("bertambah 150 kata", row["message"])

    def test_content_change_without_word_delta(self):
        """Perubahan teks yang tidak mengubah apa pun dilaporkan tenang, bukan seperti temuan."""
        changes = compare(facts(), facts(content_hash="bbb", word_count=505))
        row = next(row for row in changes if row["type"] == "isi_berubah")
        self.assertEqual(row["severity"], "info")
        self.assertIn("berbeda sedikit", row["message"])
        self.assertIn("tidak berubah", row["message"])

    def test_catatan_isi_dihapus_bila_ada_temuan_yang_lebih_penting(self):
        perubahan = compare(
            facts(),
            facts(content_hash="bbb", word_count=505, prices=[{"amount": 90000.0, "currency": "IDR", "name": "Cabut"}]),
        )
        jenis = [row["type"] for row in perubahan]
        self.assertNotIn("isi_berubah", jenis, "catatan kecil tidak perlu menemani temuan harga")

    def test_missing_alt_growth(self):
        changes = compare(facts(), facts(images_without_alt=4))
        self.assertIn("alt_gambar_berkurang", types(changes))

    def test_viewport_removal(self):
        changes = compare(facts(), facts(has_viewport=False))
        self.assertIn("viewport_hilang", types(changes))

    def test_schema_local_business_appears(self):
        changes = compare(facts(), facts(has_local_business=True))
        self.assertIn("schema_lokal_baru", types(changes))

    def test_no_change_returns_empty(self):
        self.assertEqual(compare(facts(), facts()), [])


class OrderingTest(unittest.TestCase):
    def test_most_important_change_comes_first(self):
        changes = compare(
            facts(),
            facts(noindex=True, prices=[{"amount": 100000.0, "currency": "IDR", "name": "Arabika"}]),
        )
        self.assertEqual(changes[0]["severity"], "tinggi")
        self.assertEqual(highest_severity(changes), "tinggi")

    def test_highest_severity_of_empty_list_is_info(self):
        self.assertEqual(highest_severity([]), "info")


if __name__ == "__main__":
    unittest.main()

class HargaLapisDuaTest(unittest.TestCase):
    """Uji lapangan 14 Okt 2026: keterangan harga berubah tidak boleh jadi alarm palsu."""

    def _potret(self, prices):
        return {"title": "Klinik", "prices": prices, "rating": None, "word_count": 500, "h2": []}

    def test_keterangan_muncul_bukan_harga_baru(self):
        lama = self._potret([{"amount": 649000.0, "currency": "IDR", "source": "teks", "name": ""}])
        baru = self._potret([{"amount": 649000.0, "currency": "IDR", "source": "teks", "name": "Bleaching gigi"}])
        jenis = [c["type"] for c in compare(lama, baru)]
        self.assertNotIn("harga_baru", jenis)
        self.assertNotIn("harga_hilang", jenis)

    def test_keterangan_hilang_bukan_harga_hilang(self):
        lama = self._potret([{"amount": 199000.0, "currency": "IDR", "source": "teks", "name": "Cuci Karpet"}])
        baru = self._potret([{"amount": 199000.0, "currency": "IDR", "source": "teks", "name": ""}])
        jenis = [c["type"] for c in compare(lama, baru)]
        self.assertNotIn("harga_hilang", jenis)
        self.assertNotIn("harga_baru", jenis)

    def test_angka_yang_benar_benar_hilang_tetap_dilaporkan(self):
        lama = self._potret(
            [
                {"amount": 199000.0, "currency": "IDR", "source": "teks", "name": ""},
                {"amount": 499000.0, "currency": "IDR", "source": "teks", "name": ""},
            ]
        )
        baru = self._potret([{"amount": 199000.0, "currency": "IDR", "source": "teks", "name": ""}])
        jenis = [c["type"] for c in compare(lama, baru)]
        self.assertEqual(jenis.count("harga_hilang"), 1)
        self.assertTrue(any("499" in str(c.get("before", "")) for c in compare(lama, baru) if c["type"] == "harga_hilang"))

    def test_harga_barang_bernama_tetap_terdeteksi_naik(self):
        lama = self._potret([{"amount": 140000.0, "currency": "IDR", "source": "teks", "name": "Les Privat SD"}])
        baru = self._potret([{"amount": 175000.0, "currency": "IDR", "source": "teks", "name": "Les Privat SD"}])
        perubahan = [c for c in compare(lama, baru) if c["type"] == "harga_naik"]
        self.assertEqual(len(perubahan), 1)
        self.assertIn("Les Privat SD", perubahan[0]["message"])
        self.assertIn("25.0%", perubahan[0]["message"])

    def test_dua_barang_dengan_harga_sama_tidak_tertukar(self):
        """Dua layanan berharga sama: yang berubah hanya satu, dan itu yang dilaporkan."""
        lama = self._potret(
            [
                {"amount": 150000.0, "currency": "IDR", "source": "teks", "name": "Cabut gigi"},
                {"amount": 150000.0, "currency": "IDR", "source": "teks", "name": "Tambal gigi"},
            ]
        )
        baru = self._potret(
            [
                {"amount": 150000.0, "currency": "IDR", "source": "teks", "name": "Cabut gigi"},
                {"amount": 165000.0, "currency": "IDR", "source": "teks", "name": "Tambal gigi"},
            ]
        )
        perubahan = compare(lama, baru)
        naik = [c for c in perubahan if c["type"] == "harga_naik"]
        self.assertEqual(len(naik), 1)
        self.assertIn("Tambal gigi", naik[0]["message"])
        self.assertNotIn("harga_hilang", [c["type"] for c in perubahan])

    def test_mata_uang_berbeda_tidak_dicampur(self):
        lama = self._potret([{"amount": 100.0, "currency": "USD", "source": "teks", "name": ""}])
        baru = self._potret([{"amount": 100.0, "currency": "SGD", "source": "teks", "name": ""}])
        jenis = [c["type"] for c in compare(lama, baru)]
        self.assertIn("harga_hilang", jenis)
        self.assertIn("harga_baru", jenis)


if __name__ == "__main__":
    unittest.main()
