"""Uji pembacaan halaman: harga, rating agregat, dan audit dasar."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar import extract  # noqa: E402
from lokaradar.extract import page_facts  # noqa: E402


def ld(payload: str) -> str:
    return f'<script type="application/ld+json">{payload}</script>'


class MultiCurrencyTest(unittest.TestCase):
    """Satu halaman bisa memuat beberapa mata uang; tiap simbol harus terbaca benar."""

    def test_symbols_and_prefixes(self):
        html = "<p>Harga S$12.50</p><p>&pound;51.77</p><p>&euro;9,95</p><p>RM 45</p><p>$1,299.00</p>"
        found = {(row["currency"], row["amount"]) for row in page_facts("https://x.test/", html, "")["prices"]}
        self.assertEqual(
            found,
            {("SGD", 12.5), ("GBP", 51.77), ("EUR", 9.95), ("MYR", 45.0), ("USD", 1299.0)},
        )

    def test_dollar_prefix_is_not_double_counted(self):
        facts = page_facts("https://x.test/", "<p>S$12.50</p>", "")
        currencies = [row["currency"] for row in facts["prices"]]
        self.assertEqual(currencies, ["SGD"], "S$ tidak boleh juga terbaca sebagai USD")

    def test_rupiah_thousands_are_not_decimals(self):
        facts = page_facts("https://x.test/", "<p>Rp 1.250.000</p>", "")
        self.assertEqual(facts["prices"][0]["amount"], 1250000.0)


class PriceTest(unittest.TestCase):
    def test_indonesian_formats(self):
        cases = {
            "Rp 150.000": 150000.0,
            "Rp150.000": 150000.0,
            "IDR 1.250.000": 1250000.0,
            "Rp 1.250.000,50": 1250000.5,
            "Rp 99.900": 99900.0,
        }
        for raw, expected in cases.items():
            with self.subTest(harga=raw):
                facts = extract.page_facts("https://contoh.test/", f"<p>{raw}</p>", raw)
                amounts = [row["amount"] for row in facts["prices"]]
                self.assertIn(expected, amounts)

    def test_harga_dari_teks_membawa_nama_layanannya(self):
        """Halaman harga nyata menaruh nama layanan persis sebelum angkanya."""
        html = (
            "<ul>"
            "<li>Bleaching gigi <span>IDR 649.000</span></li>"
            "<li>Tambal gigi Rp 215.000</li>"
            "</ul>"
            "<table>"
            "<tr><td>Cuci Karpet</td><td>Rp 199.000</td></tr>"
            "<tr><td>Laundry Kiloan</td><td>Rp 12.000/kg</td></tr>"
            "</table>"
        )
        harga = {row["amount"]: row["name"] for row in extract.page_facts("https://x.test/", html)["prices"]}
        self.assertEqual(harga[649000.0], "Bleaching gigi")
        self.assertEqual(harga[215000.0], "Tambal gigi")
        self.assertEqual(harga[199000.0], "Cuci Karpet")
        self.assertEqual(harga[12000.0], "Laundry Kiloan")

    def test_judul_bagian_menjadi_nama_bila_tidak_ada_teks_lain(self):
        html = "<h3>Paket Bulanan</h3><p>Rp 499.000</p>"
        harga = extract.page_facts("https://x.test/", html)["prices"]
        self.assertEqual(harga[0]["name"], "Paket Bulanan")

    def test_keterangan_tidak_menyeberang_antar_baris(self):
        """Harga di baris baru tidak boleh memakai nama dari baris sebelumnya."""
        html = (
            "<table><tr><td>Cuci Karpet</td><td>Rp 199.000</td></tr>"
            "<tr><td>Layanan lain menyusul</td><td></td></tr></table>"
            "<div>Rp 12.000</div>"
        )
        harga = {row["amount"]: row["name"] for row in extract.page_facts("https://x.test/", html)["prices"]}
        self.assertEqual(harga[199000.0], "Cuci Karpet")
        self.assertEqual(harga[12000.0], "", "tanpa keterangan di dekatnya, nama harus kosong — bukan menebak")

    def test_keterangan_tanpa_huruf_tidak_dipakai(self):
        html = "<p>12 34 <span>Rp 99.000</span></p>"
        harga = extract.page_facts("https://x.test/", html)["prices"]
        self.assertEqual(harga[0]["name"], "")

    def test_json_ld_offer_is_preferred_and_named(self):
        html = ld(
            '{"@type":"Product","name":"Arabika 250g","offers":{"@type":"Offer",'
            '"price":"150000","priceCurrency":"IDR"}}'
        )
        facts = extract.page_facts("https://contoh.test/", html, "Rp 150.000")
        self.assertEqual(len(facts["prices"]), 1)
        self.assertEqual(facts["prices"][0]["name"], "Arabika 250g")
        self.assertEqual(facts["prices"][0]["source"], "json-ld")

    def test_offer_list_and_low_price(self):
        html = ld(
            '{"@type":"Product","name":"Paket","offers":[{"price":"200000","priceCurrency":"IDR"},'
            '{"price":"175000","priceCurrency":"IDR"}]}'
        )
        facts = extract.page_facts("https://contoh.test/", html)
        self.assertEqual(len(facts["prices"]), 2)
        self.assertEqual(extract.lowest_price(facts)["amount"], 175000.0)

    def test_offers_are_not_double_counted(self):
        html = ld('{"@type":"Product","name":"A","offers":{"price":"100000","priceCurrency":"IDR"}}')
        facts = extract.page_facts("https://contoh.test/", html)
        self.assertEqual(len(facts["prices"]), 1)

    def test_usd_prices_are_detected_with_currency(self):
        facts = extract.page_facts("https://contoh.test/", "<p>$49.90</p>", "$49.90")
        self.assertEqual(facts["prices"][0]["currency"], "USD")
        self.assertEqual(facts["prices"][0]["amount"], 49.9)

    def test_no_price_returns_none(self):
        facts = extract.page_facts("https://contoh.test/", "<p>Hubungi kami</p>", "Hubungi kami")
        self.assertIsNone(extract.lowest_price(facts))
        self.assertEqual(extract.readable_prices(facts), "tidak ada harga terbaca")

    def test_readingable_prices_is_indonesian(self):
        facts = extract.page_facts("https://contoh.test/", "<p>Rp 1.500.000</p>", "Rp 1.500.000")
        self.assertIn("IDR 1.500.000", extract.readable_prices(facts))


class RatingTest(unittest.TestCase):
    def test_aggregate_rating_from_json_ld(self):
        html = ld('{"@type":"LocalBusiness","name":"Kopi","aggregateRating":'
                  '{"ratingValue":"4.7","reviewCount":"213","bestRating":"5"}}')
        facts = extract.page_facts("https://contoh.test/", html)
        self.assertEqual(facts["rating"], {"value": 4.7, "count": 213, "scale": 5.0})
        self.assertTrue(facts["has_local_business"])

    def test_rating_count_alias_is_supported(self):
        html = ld('{"@type":"Product","aggregateRating":{"ratingValue":"4.9","ratingCount":"1.204"}}')
        facts = extract.page_facts("https://contoh.test/", html)
        self.assertEqual(facts["rating"]["count"], 1204)
        self.assertEqual(facts["rating"]["scale"], 5.0)

    def test_bigger_count_wins_when_repeated(self):
        html = ld('{"@type":"Product","aggregateRating":{"ratingValue":"4.1","reviewCount":"10"}}') + ld(
            '{"@type":"Store","aggregateRating":{"ratingValue":"4.6","reviewCount":"980"}}'
        )
        facts = extract.page_facts("https://contoh.test/", html)
        self.assertEqual(facts["rating"]["count"], 980)

    def test_no_rating_returns_none(self):
        facts = extract.page_facts("https://contoh.test/", "<p>tanpa rating</p>")
        self.assertIsNone(facts["rating"])

    def test_reviewer_identity_is_never_stored(self):
        html = ld(
            '{"@type":"Product","aggregateRating":{"ratingValue":"4.5","reviewCount":"12"},'
            '"review":{"author":{"name":"Budi Santoso"},"reviewBody":"Sangat bagus"}}'
        )
        facts = extract.page_facts("https://contoh.test/", html)
        dumped = repr(facts)
        self.assertNotIn("Budi", dumped)
        self.assertNotIn("Sangat bagus", dumped)


class PageAuditTest(unittest.TestCase):
    def test_basic_fields(self):
        html = (
            '<html lang="id"><head><title>Kopi Bogor</title>'
            '<meta name="description" content="Kopi segar Bogor">'
            '<meta name="robots" content="noindex, follow">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<link rel="canonical" href="https://contoh.test/kopi"></head>'
            "<body><h1>Kopi</h1><h2>Layanan</h2><img src='a.png'><img src='b.png' alt='biji kopi'>"
            "<a href='/kontak'>Kontak</a><a href='https://lain.test/'>Lain</a></body></html>"
        )
        facts = extract.page_facts("https://contoh.test/", html, "Kopi segar Bogor Layanan")
        self.assertEqual(facts["title"], "Kopi Bogor")
        self.assertEqual(facts["description"], "Kopi segar Bogor")
        self.assertEqual(facts["lang"], "id")
        self.assertTrue(facts["noindex"])
        self.assertTrue(facts["has_viewport"])
        self.assertEqual(facts["canonical"], "https://contoh.test/kopi")
        self.assertEqual(facts["h1_count"], 1)
        self.assertEqual(facts["h2"], ["Layanan"])
        self.assertEqual(facts["images"], 2)
        self.assertEqual(facts["images_without_alt"], 1)
        self.assertEqual(facts["links_internal"], 1)
        self.assertEqual(facts["links_external"], 1)
        self.assertEqual(facts["word_count"], len("Kopi segar Bogor Layanan".split()))

    def test_content_hash_is_stable_and_sensitive_to_whitespace_only(self):
        first = extract.page_facts("https://contoh.test/", "<p>Halo</p>", "Halo   Dunia")
        second = extract.page_facts("https://contoh.test/", "<p>Halo</p>", "halo dunia")
        third = extract.page_facts("https://contoh.test/", "<p>Halo</p>", "Halo Dunia baru")
        self.assertEqual(first["content_hash"], second["content_hash"])
        self.assertNotEqual(second["content_hash"], third["content_hash"])

    def test_broken_html_does_not_crash(self):
        facts = extract.page_facts("https://contoh.test/", "<html><title>Rusak<div><p>", "")
        self.assertEqual(facts["title"], "Rusak")

    def test_dangerous_json_ld_is_ignored(self):
        html = ld("{bukan json}") + ld('{"@type":"Product","name":"Valid","offers":{"price":"5","priceCurrency":"IDR"}}')
        facts = extract.page_facts("https://contoh.test/", html)
        self.assertEqual(facts["schema_types"], ["Product"])
        self.assertEqual(facts["prices"][0]["amount"], 5.0)

    def test_script_content_is_not_read_as_price(self):
        html = '<script>var harga = "Rp 999.999";</script><p>Hubungi kami</p>'
        facts = extract.page_facts("https://contoh.test/", html, "Hubungi kami")
        self.assertEqual(facts["prices"], [])


if __name__ == "__main__":
    unittest.main()
