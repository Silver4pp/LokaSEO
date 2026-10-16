"""Uji sumber resmi Google Places API dan integrasinya ke putaran pemantauan."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar import places  # noqa: E402
from lokaradar.cli import main as cli_main  # noqa: E402
from lokaradar.run import run_once  # noqa: E402
from lokaradar.store import Store  # noqa: E402

PLACE_OK = {
    "id": "ChIJabcdefg",
    "displayName": {"text": "Kopi Bogor"},
    "formattedAddress": "Jl. Pajajaran 1, Bogor",
    "websiteUri": "https://kopi.test/",
    "rating": 4.6,
    "userRatingCount": 132,
    "reviews": [{"authorAttribution": {"displayName": "Budi"}, "text": {"text": "Enak"}}],
}


SEARCH_OK = {
    "places": [
        {
            "id": "ChIJklinik1",
            "displayName": {"text": "Klinik Gigi Sehat Bogor"},
            "formattedAddress": "Jl. Pajajaran 1, Bogor",
            "rating": 4.8,
            "userRatingCount": 210,
            "websiteUri": "https://kliniksehat.test/",
        },
        {
            "id": "ChIJklinik2",
            "displayName": {"text": "Klinik Gigi Bogor Utara"},
            "formattedAddress": "Jl. Pandu Raya 5, Bogor",
            "rating": 4.4,
            "userRatingCount": 88,
        },
    ]
}


class FakePlaces:
    """Peniru pemanggil HTTP: mencatat permintaan, mengembalikan jawaban tetap."""

    def __init__(self, payload=PLACE_OK, status: int = 200) -> None:
        self.payload = payload
        self.status = status
        self.calls: list[places.PlacesRequest] = []

    def __call__(self, spec: places.PlacesRequest, timeout: float) -> tuple[int, str]:
        self.calls.append(spec)
        body = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return self.status, body

    @property
    def terakhir(self) -> places.PlacesRequest:
        return self.calls[-1]


class LookupTest(unittest.TestCase):
    def test_successful_lookup_maps_aggregates_only(self):
        loader = FakePlaces()
        place = places.lookup("ChIJabcdefg", "kunci-rahasia", loader=loader)
        self.assertEqual(place["place_id"], "ChIJabcdefg")
        self.assertEqual(place["name"], "Kopi Bogor")
        self.assertEqual(place["rating"], 4.6)
        self.assertEqual(place["count"], 132)
        self.assertNotIn("reviews", place, "ulasan tidak boleh ikut diambil")
        self.assertEqual(loader.calls[0].url, f"{places.ENDPOINT}ChIJabcdefg")
        self.assertEqual(loader.calls[0].key, "kunci-rahasia")
        self.assertEqual(loader.calls[0].method, "GET")

    def test_missing_key_is_reported_clearly(self):
        with self.assertRaises(places.PlacesError) as context:
            places.lookup("ChIJabcdefg", "", loader=FakePlaces())
        self.assertIn(places.KEY_ENV, str(context.exception))

    def test_rejected_key_and_missing_place(self):
        for status in (401, 403):
            with self.subTest(status=status), self.assertRaises(places.PlacesError) as context:
                places.lookup("ChIJabcdefg", "kunci", loader=FakePlaces(status=status))
            self.assertIn(str(status), str(context.exception))
        with self.assertRaises(places.PlacesError) as context:
            places.lookup("ChIJabcdefg", "kunci", loader=FakePlaces(status=404))
        self.assertIn("tidak ditemukan", str(context.exception))

    def test_broken_json_and_server_error(self):
        with self.assertRaises(places.PlacesError):
            places.lookup("ChIJabcdefg", "kunci", loader=FakePlaces(payload="{bukan json"))
        with self.assertRaises(places.PlacesError) as context:
            places.lookup("ChIJabcdefg", "kunci", loader=FakePlaces(status=503))
        self.assertIn("503", str(context.exception))

    def test_place_id_is_validated(self):
        for bad in ("", "ruang kosong", "pelanggaran/../id"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                places.lookup(bad, "kunci", loader=FakePlaces())

    def test_target_helpers(self):
        self.assertEqual(places.place_id_of("tempat:ChIJabcdefg"), "ChIJabcdefg")
        self.assertEqual(places.target_url("ChIJabcdefg"), "tempat:ChIJabcdefg")
        with self.assertRaises(ValueError):
            places.place_id_of("https://contoh.test/")
        with self.assertRaises(ValueError):
            places.target_url("x")

    def test_key_is_never_stored_in_facts(self):
        facts = places.place_facts(places.lookup("ChIJabcdefg", "kunci-rahasia", loader=FakePlaces()))
        dumped = json.dumps(facts, ensure_ascii=False)
        self.assertNotIn("kunci-rahasia", dumped)
        self.assertNotIn("Budi", dumped, "nama penulis ulasan tidak boleh ikut")
        self.assertNotIn("Enak", dumped, "isi ulasan tidak boleh ikut")


class SearchTest(unittest.TestCase):
    def test_search_returns_candidates_without_reviews(self):
        loader = FakePlaces(payload=SEARCH_OK)
        hasil = places.search_text("Klinik Gigi", "kunci", kota="Bogor", loader=loader)
        self.assertEqual(len(hasil), 2)
        self.assertEqual(hasil[0]["place_id"], "ChIJklinik1")
        self.assertEqual(hasil[0]["name"], "Klinik Gigi Sehat Bogor")
        self.assertEqual(hasil[0]["rating"], 4.8)
        self.assertNotIn("reviews", json.dumps(hasil))

    def test_search_uses_post_with_city_and_language(self):
        loader = FakePlaces(payload=SEARCH_OK)
        places.search_text("Klinik Gigi", "kunci", kota="Bogor", max_results=3, loader=loader)
        spec = loader.terakhir
        self.assertEqual(spec.url, places.SEARCH_ENDPOINT)
        self.assertEqual(spec.method, "POST")
        self.assertEqual(spec.payload["textQuery"], "Klinik Gigi Bogor")
        self.assertEqual(spec.payload["maxResultCount"], 3)
        self.assertEqual(spec.payload["languageCode"], "id")
        self.assertIn("places.rating", spec.field_mask)

    def test_city_is_not_added_twice(self):
        loader = FakePlaces(payload=SEARCH_OK)
        places.search_text("Klinik Gigi Bogor", "kunci", kota="Bogor", loader=loader)
        self.assertEqual(loader.terakhir.payload["textQuery"], "Klinik Gigi Bogor")

    def test_empty_query_is_rejected(self):
        with self.assertRaises(ValueError):
            places.search_text("   ", "kunci", loader=FakePlaces(payload=SEARCH_OK))

    def test_quota_error_mentions_kuota(self):
        with self.assertRaises(places.PlacesError) as context:
            places.search_text("Klinik", "kunci", loader=FakePlaces(payload="{}", status=429))
        self.assertIn("Kuota", str(context.exception))

    def test_bad_key_message_is_actionable(self):
        for status, harapan in ((400, "diaktifkan"), (401, "salah salin"), (403, "pembatasan kunci")):
            with self.subTest(status=status), self.assertRaises(places.PlacesError) as context:
                places.search_text("Klinik", "kunci", loader=FakePlaces(payload="{}", status=status))
            self.assertIn(harapan, str(context.exception))

    def test_results_without_id_are_dropped(self):
        payload = {"places": [{"displayName": {"text": "Tanpa id"}}, {"id": "", "displayName": {"text": "Kosong"}}]}
        self.assertEqual(places.search_text("x", "kunci", loader=FakePlaces(payload=payload)), [])

    def test_missing_key_is_reported(self):
        with self.assertRaises(places.PlacesError) as context:
            places.search_text("Klinik", "")
        self.assertIn(places.KEY_ENV, str(context.exception))


class FactsTest(unittest.TestCase):
    def test_facts_shape_matches_page_facts(self):
        facts = places.place_facts(
            {"place_id": "ChIJabcdefg", "name": "Kopi Bogor", "address": "Jl. A", "rating": 4.6, "count": 132}
        )
        self.assertEqual(facts["title"], "Kopi Bogor")
        self.assertEqual(facts["rating"], {"value": 4.6, "count": 132, "scale": 5.0})
        self.assertEqual(facts["sumber"], "places-api")
        self.assertEqual(facts["prices"], [])
        self.assertTrue(facts["content_hash"])

    def test_content_hash_changes_with_rating(self):
        dasar = places.place_facts({"name": "A", "rating": 4.5, "count": 100})
        lain = places.place_facts({"name": "A", "rating": 4.6, "count": 100})
        self.assertNotEqual(dasar["content_hash"], lain["content_hash"])

    def test_missing_rating_is_honest(self):
        facts = places.place_facts({"name": "Baru", "rating": None, "count": None})
        self.assertIsNone(facts["rating"])


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.environ.get("LOKARADAR_DATA")
        self.key = os.environ.get(places.KEY_ENV)
        os.environ["LOKARADAR_DATA"] = self.tmp.name
        os.environ.pop(places.KEY_ENV, None)

    def tearDown(self):
        if self.env is None:
            os.environ.pop("LOKARADAR_DATA", None)
        else:
            os.environ["LOKARADAR_DATA"] = self.env
        if self.key is None:
            os.environ.pop(places.KEY_ENV, None)
        else:
            os.environ[places.KEY_ENV] = self.key
        self.tmp.cleanup()

    def jalankan(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli_main(argv)
        return code, buffer.getvalue()

    def test_status_shows_places_readiness_without_the_key(self):
        os.environ[places.KEY_ENV] = "kunci-rahasia-jangan-tampil"
        store = Store()
        store.add_target("tempat:ChIJabcdefg", "Klinik", "reputasi")
        store.close()
        code, output = self.jalankan(["status"])
        self.assertEqual(code, 0)
        self.assertIn("Kunci Places API: terpasang", output)
        self.assertIn("Sasaran tempat  : 1", output)
        self.assertNotIn("kunci-rahasia-jangan-tampil", output, "kunci tidak boleh tercetak")

    def test_status_says_key_missing(self):
        code, output = self.jalankan(["status"])
        self.assertEqual(code, 0)
        self.assertIn("belum diatur", output)


class StoreTargetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "radar.sqlite3")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_place_target_is_accepted(self):
        row = self.store.add_target("tempat:ChIJabcdefg", "Usaha Saya", "reputasi")
        self.assertEqual(row["url"], "tempat:ChIJabcdefg")

    def test_short_place_id_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.add_target("tempat:abc")

    def test_snapshots_listing_is_chronological(self):
        target = self.store.add_target("https://contoh.test/")
        for rating in (4.4, 4.5, 4.6):
            self.store.save_snapshot(int(target["id"]), 200, {"rating": {"value": rating, "count": 10}})
        rows = self.store.snapshots(int(target["id"]))
        self.assertEqual([row["facts"]["rating"]["value"] for row in rows], [4.4, 4.5, 4.6])


class RunIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "radar.sqlite3")
        self.store.add_target("tempat:ChIJabcdefg", "Kopi Bogor", "reputasi")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_first_run_saves_baseline_from_places(self):
        loader = FakePlaces()
        result = run_once(
            self.store,
            fetcher=None,
            places_key="kunci",
            places_loader=loader,
        )
        self.assertEqual(result["diperiksa"], 1)
        self.assertEqual(result["gagal"], 0)
        snapshot = self.store.latest_snapshot(1)
        self.assertEqual(snapshot["facts"]["rating"]["count"], 132)
        self.assertEqual(result["sasaran"][0]["changes"][0]["type"], "pemantauan_dimulai")

    def test_second_run_detects_rating_and_review_change(self):
        run_once(self.store, fetcher=None, places_key="kunci", places_loader=FakePlaces())
        berubah = dict(PLACE_OK, rating=4.4, userRatingCount=140)
        result = run_once(self.store, fetcher=None, places_key="kunci", places_loader=FakePlaces(payload=berubah))
        kinds = {row["type"] for row in result["sasaran"][0]["changes"]}
        self.assertIn("rating_berubah", kinds)
        self.assertIn("jumlah_ulasan_berubah", kinds)

    def test_missing_key_records_failure_not_silence(self):
        result = run_once(self.store, fetcher=None, places_key="")
        self.assertEqual(result["gagal"], 1)
        self.assertIn(places.KEY_ENV, result["sasaran"][0]["error"])
        self.assertIsNone(self.store.latest_snapshot(1))

    def test_places_error_is_recorded(self):
        result = run_once(self.store, fetcher=None, places_key="kunci", places_loader=FakePlaces(status=403))
        self.assertEqual(result["gagal"], 1)
        self.assertIn("403", result["sasaran"][0]["error"])


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.environ.get("LOKARADAR_DATA")
        self.key = os.environ.get(places.KEY_ENV)
        os.environ["LOKARADAR_DATA"] = self.tmp.name
        os.environ.pop(places.KEY_ENV, None)

    def tearDown(self):
        if self.env is None:
            os.environ.pop("LOKARADAR_DATA", None)
        else:
            os.environ["LOKARADAR_DATA"] = self.env
        if self.key is None:
            os.environ.pop(places.KEY_ENV, None)
        else:
            os.environ[places.KEY_ENV] = self.key
        self.tmp.cleanup()

    def jalankan(self, argv: list[str]) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli_main(argv)
        return code, buffer.getvalue()

    def test_cari_without_key_explains_quota(self):
        code, output = self.jalankan(["cari", "Klinik Gigi", "--kota", "Bogor"])
        self.assertEqual(code, 3)
        self.assertIn(places.KEY_ENV, output)
        self.assertIn("Text Search", output)

    def test_cari_lists_candidates_and_can_add_one(self):
        asli = places._default_loader

        def palsu(spec, timeout):
            return 200, json.dumps(SEARCH_OK)

        places._default_loader = palsu
        os.environ[places.KEY_ENV] = "kunci-uji"
        try:
            code, output = self.jalankan(["cari", "Klinik Gigi", "--kota", "Bogor"])
            self.assertEqual(code, 0)
            self.assertIn("Klinik Gigi Sehat Bogor", output)
            self.assertIn("tempat:ChIJklinik1", output)

            code, output = self.jalankan(["cari", "Klinik Gigi", "--tambah", "2"])
            self.assertEqual(code, 0)
            self.assertIn("Sasaran ditambahkan", output)
            store = Store()
            self.assertIsNotNone(store.find_target("tempat:ChIJklinik2"))
            store.close()
        finally:
            places._default_loader = asli
            os.environ.pop(places.KEY_ENV, None)

    def test_cari_rejects_unknown_choice(self):
        asli = places._default_loader
        places._default_loader = lambda spec, timeout: (200, json.dumps(SEARCH_OK))
        os.environ[places.KEY_ENV] = "kunci-uji"
        try:
            code, output = self.jalankan(["cari", "Klinik", "--tambah", "9"])
            self.assertEqual(code, 4)
            self.assertIn("tidak ada pada daftar", output)
        finally:
            places._default_loader = asli
            os.environ.pop(places.KEY_ENV, None)

    def test_tempat_without_key_explains_how_to_set_it(self):
        code, output = self.jalankan(["tempat", "ChIJabcdefg"])
        self.assertEqual(code, 3)
        self.assertIn(places.KEY_ENV, output)

    def test_reputasi_without_targets(self):
        code, output = self.jalankan(["reputasi"])
        self.assertEqual(code, 1)
        self.assertIn("Belum ada sasaran", output)

    def test_reputasi_without_snapshots(self):
        store = Store()
        store.add_target("tempat:ChIJabcdefg", "Kopi", "reputasi")
        store.close()
        code, output = self.jalankan(["reputasi"])
        self.assertEqual(code, 1)
        self.assertIn("Belum ada potret rating", output)

    def test_reputasi_prints_board(self):
        store = Store()
        target = store.add_target("https://kopi.test/", "Kopi Bogor", "reputasi")
        store.save_snapshot(
            int(target["id"]), 200, {"title": "Kopi", "rating": {"value": 4.6, "count": 120, "scale": 5}}
        )
        store.close()
        code, output = self.jalankan(["reputasi", "--min-rating", "4.8"])
        self.assertEqual(code, 0)
        self.assertIn("Papan reputasi", output)
        self.assertIn("Kopi Bogor", output)
        self.assertIn("rating di bawah ambang", output)

    def test_reputasi_writes_markdown_copy(self):
        store = Store()
        target = store.add_target("https://kopi.test/", "Kopi Bogor", "reputasi")
        store.save_snapshot(
            int(target["id"]), 200, {"title": "Kopi", "rating": {"value": 4.2, "count": 20, "scale": 5}}
        )
        store.close()
        outdir = Path(self.tmp.name) / "keluaran"
        code, output = self.jalankan(["reputasi", "--out", str(outdir)])
        self.assertEqual(code, 0)
        berkas = list(outdir.glob("reputasi-*.md"))
        self.assertEqual(len(berkas), 1)
        self.assertIn("# Papan reputasi lokal", berkas[0].read_text(encoding="utf-8"))
        self.assertIn("Salinan Markdown", output)


if __name__ == "__main__":
    unittest.main()
