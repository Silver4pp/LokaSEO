"""Uji profil usaha: kunci utama yang berasal dari setelan awal LokaSEO."""

import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar import profil as profil_mod  # noqa: E402
from lokaradar import reputasi  # noqa: E402
from lokaradar.cli import main as cli_main  # noqa: E402
from lokaradar.report import build_pack, markdown  # noqa: E402
from lokaradar.run import run_once  # noqa: E402
from lokaradar.store import Store  # noqa: E402

CADANGAN = {
    "version": 1,
    "activeId": "kopi",
    "projects": [
        {
            "id": "kopi",
            "name": "Kebun Kopi Bogor",
            "domain": "kebunkopi.example",
            "city": "Bogor",
            "industry": "kafe-kedai",
            "keywords": "kopi bogor",
            "articles": [],
            "checks": [],
            "audit": None,
            "auditedAt": None,
        },
        {
            "id": "roti",
            "name": "Roti Jakarta",
            "domain": "roti.example",
            "city": "Jakarta",
            "industry": "toko-retail",
            "keywords": "",
            "articles": [],
            "checks": [],
            "audit": None,
            "auditedAt": None,
        },
    ],
}


class SaranSumberTest(unittest.TestCase):
    def test_setiap_jenis_punya_penanda_rating(self):
        for kunci, item in profil_mod.INDUSTRI.items():
            with self.subTest(jenis=kunci):
                self.assertIn("rating_penting", item, "setiap jenis usaha harus punya penanda rating")
                self.assertIsInstance(item["rating_penting"], bool)

    def test_klinik_dan_kafe_menganggap_rating_penting(self):
        for kunci in ("kafe-kedai", "restoran", "klinik-kesehatan", "penginapan", "jasa-kecantikan"):
            with self.subTest(jenis=kunci):
                self.assertTrue(profil_mod.INDUSTRI[kunci]["rating_penting"])

    def test_saran_menyebut_places_untuk_yang_penting(self):
        profil = profil_mod.Profil(jenis="klinik-kesehatan")
        self.assertIn("Places API", profil.saran_sumber_rating)
        lain = profil_mod.Profil(jenis="lainnya")
        self.assertIn("memadai", lain.saran_sumber_rating)


class KatalogTest(unittest.TestCase):
    def test_setiap_jenis_punya_bawaan_lengkap(self):
        for kunci, item in profil_mod.INDUSTRI.items():
            with self.subTest(jenis=kunci):
                self.assertTrue(item["label"])
                self.assertTrue(item["schema"])
                self.assertTrue(item["kata_kunci"])
                self.assertGreater(item["min_rating"], 0)

    def test_cadangan_lama_tanpa_kolom_jenis_tetap_terbaca(self):
        lama = json.loads(json.dumps(CADANGAN))
        for project in lama["projects"]:
            project.pop("industry")
        profil = profil_mod.from_lokaseo_backup(lama)
        self.assertEqual(profil.nama, "Kebun Kopi Bogor")
        self.assertEqual(profil.jenis, "")
        self.assertEqual(profil.ambang_rating, profil_mod.AMBANG_BAWAAN)

    def test_jenis_tidak_dikenal_jatuh_ke_lainnya(self):
        payload = json.loads(json.dumps(CADANGAN))
        payload["projects"][0]["industry"] = "kedai-antariksaa"
        self.assertEqual(profil_mod.from_lokaseo_backup(payload).jenis, "lainnya")

    def test_impor_memakai_proyek_aktif(self):
        profil = profil_mod.from_lokaseo_backup(CADANGAN)
        self.assertEqual(profil.nama, "Kebun Kopi Bogor")
        self.assertEqual(profil.kota, "Bogor")
        self.assertEqual(profil.jenis, "kafe-kedai")
        self.assertEqual(profil.jenis_label, "Kafe, kedai kopi, atau tempat makan kecil")
        self.assertEqual(profil.ambang_rating, 4.3)
        self.assertIn("CafeOrCoffeeShop", profil.schema_diharapkan)

    def test_cadangan_tanpa_proyek_ditolak(self):
        for rusak in ({}, {"projects": []}, {"projects": "bukan daftar"}, []):
            with self.subTest(rusak=rusak), self.assertRaises(ValueError):
                profil_mod.from_lokaseo_backup(rusak)

    def test_daftar_jenis_sama_dengan_lokaseo(self):
        """Daftar di LokaSEO (TypeScript) dan radar (Python) harus sama persis."""
        berkas = Path(__file__).resolve().parents[2] / "src/client/features/lokaseo/industries.ts"
        if not berkas.is_file():
            self.skipTest("berkas industries.ts tidak ada di salinan ini")
        isi = berkas.read_text(encoding="utf-8")
        di_lokaseo = re.findall(r'^\s{4}id: "([a-z0-9-]+)"', isi, flags=re.MULTILINE)
        self.assertTrue(di_lokaseo, "tidak ada id jenis usaha yang terbaca di industries.ts")
        self.assertEqual(
            di_lokaseo,
            list(profil_mod.INDUSTRI.keys()),
            "urutan dan nama jenis usaha harus sama di kedua sisi",
        )


class ProfilTest(unittest.TestCase):
    def test_milik_sendiri_mengenali_subdomain_dan_www(self):
        profil = profil_mod.Profil(nama="Kopi", jenis="kafe-kedai", situs="kopibogor.id")
        self.assertTrue(profil.is_milik_sendiri("https://kopibogor.id/harga"))
        self.assertTrue(profil.is_milik_sendiri("https://www.kopibogor.id/"))
        self.assertTrue(profil.is_milik_sendiri("https://menu.kopibogor.id/kopi"))
        self.assertFalse(profil.is_milik_sendiri("https://kopibogor.id.pesaing.com/"))
        self.assertFalse(profil.is_milik_sendiri("https://pesaing.id/"))

    def test_tanpa_situs_tidak_ada_yang_dianggap_milik_sendiri(self):
        profil = profil_mod.Profil(nama="Kopi", jenis="kafe-kedai")
        self.assertFalse(profil.is_milik_sendiri("https://apa-pun.test/"))

    def test_simpan_dan_muat_ulang(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "usaha.json"
            asli = profil_mod.Profil(nama="Kopi Bogor", jenis="kafe-kedai", kota="Bogor", situs="kopi.example")
            profil_mod.save(asli, path)
            lagi = profil_mod.load(path)
            self.assertIsNotNone(lagi)
            self.assertEqual(lagi.nama, "Kopi Bogor")
            self.assertEqual(lagi.jenis, "kafe-kedai")
            self.assertEqual(lagi.ambang_rating, 4.3)

    def test_berkas_rusak_tidak_menghentikan_radar(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "usaha.json"
            path.write_text("{bukan json", encoding="utf-8")
            self.assertIsNone(profil_mod.load(path))
            path.write_text("[]", encoding="utf-8")
            self.assertIsNone(profil_mod.load(path))
            self.assertIsNone(profil_mod.load(Path(tmp) / "tidak-ada.json"))

    def test_ringkas_untuk_kepala_laporan(self):
        profil = profil_mod.Profil(nama="Kopi Bogor", jenis="kafe-kedai", kota="Bogor", situs="kopi.example")
        teks = profil_mod.ringkas(profil)
        self.assertIn("Kopi Bogor", teks)
        self.assertIn("Bogor", teks)
        self.assertIn("kopi.example", teks)


class AmbangReputasiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "radar.sqlite3")
        for label, rating in (("Usaha Saya", 4.25), ("Pesaing", 4.45)):
            target = self.store.add_target(f"https://{label.lower().replace(' ', '-')}.test/", label, "reputasi")
            self.store.save_snapshot(
                int(target["id"]), 200, {"title": label, "rating": {"value": rating, "count": 50, "scale": 5}}
            )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_ambang_mengikuti_jenis_usaha(self):
        profil = profil_mod.Profil(nama="Kopi", jenis="kafe-kedai", situs="usaha-saya.test")
        papan = reputasi.board(self.store, days=30, profil=profil)
        self.assertEqual(papan["ambang_rating"], 4.3)
        self.assertEqual(papan["jenis_usaha"], "Kafe, kedai kopi, atau tempat makan kecil")
        perhatian = {row["label"]: row["tanda"] for row in papan["perhatian"]}
        self.assertIn("rating_rendah", perhatian["Usaha Saya"], "4,25 di bawah ambang jenis usaha 4,3")
        self.assertNotIn("rating_rendah", perhatian.get("Pesaing", []), "4,45 tidak di bawah ambang 4,3")

    def test_ambang_bawaan_bila_tanpa_profil(self):
        papan = reputasi.board(self.store, days=30)
        self.assertEqual(papan["ambang_rating"], reputasi.DEFAULT_MIN_RATING)

    def test_ambang_eksplisit_menang_atas_profil(self):
        profil = profil_mod.Profil(nama="Kopi", jenis="kafe-kedai")
        papan = reputasi.board(self.store, days=30, min_rating=4.95, profil=profil)
        self.assertEqual(papan["ambang_rating"], 4.95)
        self.assertEqual(len(papan["perhatian"]), 2)

    def test_baris_situs_sendiri_ditandai(self):
        profil = profil_mod.Profil(nama="Usaha Saya", jenis="kafe-kedai", situs="usaha-saya.test")
        papan = reputasi.board(self.store, days=30, profil=profil)
        sendiri = [row for row in papan["peringkat"] if row["milik_sendiri"]]
        self.assertEqual([row["label"] for row in sendiri], ["Usaha Saya"])
        teks = reputasi.board_markdown(papan)
        self.assertIn("(usaha Anda)", teks)
        self.assertIn("Usaha: Usaha Saya", teks)


class LaporanProfilTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "radar.sqlite3")
        self.profil = profil_mod.Profil(
            nama="Kebun Kopi Bogor", jenis="kafe-kedai", kota="Bogor", situs="kebunkopi.test"
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _rows(self, url: str, schema_types: list[str]) -> list[dict]:
        target = self.store.add_target(url, "Kebun Kopi", "halaman")
        facts = {"title": "Kebun Kopi", "schema_types": schema_types, "rating": None, "prices": []}
        self.store.save_snapshot(int(target["id"]), 200, facts)
        return [
            {
                "url": url,
                "label": "Kebun Kopi",
                "kind": "halaman",
                "fetched_at": "2026-10-14T00:00:00Z",
                "status": 200,
                "facts": facts,
                "changes": [],
            }
        ]

    def test_paket_memuat_profil_dan_menandai_peran(self):
        rows = self._rows("https://kebunkopi.test/", ["CafeOrCoffeeShop"])
        pack = build_pack(rows, store=self.store, profil=self.profil)
        self.assertEqual(pack["profil"]["jenis"], "kafe-kedai")
        teks = markdown(pack)
        self.assertIn("Usaha: Kebun Kopi Bogor", teks)
        self.assertIn("- Peran: Situs sendiri", teks)

    def test_data_terstruktur_yang_tidak_cocok_muncul_sebagai_ceklis(self):
        rows = self._rows("https://kebunkopi.test/", ["Organization"])
        pack = build_pack(rows, store=self.store, profil=self.profil)
        judul = " ".join(item["judul"].lower() for item in pack["lokaseo"]["cek_list"])
        self.assertIn("data terstruktur", judul)
        keterangan = " ".join(item["keterangan"] for item in pack["lokaseo"]["cek_list"])
        self.assertIn("CafeOrCoffeeShop", keterangan)

    def test_pesaing_tidak_diperiksa_data_terstrukturnya(self):
        rows = self._rows("https://pesaing.test/", ["Organization"])
        pack = build_pack(rows, store=self.store, profil=self.profil)
        keterangan = " ".join(item["keterangan"] for item in pack["lokaseo"]["cek_list"])
        self.assertNotIn("CafeOrCoffeeShop", keterangan)
        self.assertIn("- Peran: Pesaing / mitra", markdown(pack))

    def test_catatan_jenis_usaha_masuk_laporan(self):
        rows = self._rows("https://kebunkopi.test/", ["CafeOrCoffeeShop"])
        pack = build_pack(rows, store=self.store, profil=self.profil)
        catatan = " ".join(pack["lokaseo"]["catatan"])
        self.assertIn("jam buka", catatan.lower())

    def test_jenis_usaha_rating_penting_disarankan_pakai_places(self):
        """Lubang 1-dari-7 pada uji Bogor: usulan jalur rating resmi harus muncul."""
        rows = self._rows("https://kebunkopi.test/", ["CafeOrCoffeeShop"])
        pack = build_pack(rows, store=self.store, profil=self.profil)
        judul = " ".join(item["judul"] for item in pack["lokaseo"]["cek_list"])
        self.assertIn("Places API", judul)
        keterangan = " ".join(item["keterangan"] for item in pack["lokaseo"]["cek_list"])
        self.assertIn("lokaradar cari", keterangan)
        catatan = " ".join(pack["lokaseo"]["catatan"])
        self.assertIn("Rating penting", catatan)

    def test_tanpa_saran_places_bila_sudah_ada_sasaran_tempat(self):
        self.store.add_target("tempat:ChIJabcdefg", "Usaha Saya", "reputasi")
        rows = self._rows("https://kebunkopi.test/", ["CafeOrCoffeeShop"])
        pack = build_pack(rows, store=self.store, profil=self.profil)
        judul = " ".join(item["judul"] for item in pack["lokaseo"]["cek_list"])
        self.assertNotIn("Places API", judul)

    def test_jenis_lain_tidak_disarankan_places(self):
        profil = profil_mod.Profil(nama="Usaha Lain", jenis="lainnya", situs="kebunkopi.test")
        rows = self._rows("https://kebunkopi.test/", ["LocalBusiness"])
        pack = build_pack(rows, store=self.store, profil=profil)
        catatan = " ".join(pack["lokaseo"]["catatan"])
        self.assertNotIn("Rating penting", catatan)

    def test_kata_kunci_jenis_usaha_menjadi_cadangan(self):
        target = self.store.add_target("https://kebunkopi.test/", "Kebun Kopi", "halaman")
        facts = {"title": "", "schema_types": ["CafeOrCoffeeShop"], "rating": None, "prices": [], "h2": []}
        self.store.save_snapshot(int(target["id"]), 200, facts)
        self.store.save_changes(int(target["id"]), [{"type": "harga_turun", "severity": "tinggi", "message": "turun"}])
        rows = [
            {
                "url": "https://kebunkopi.test/",
                "label": "Kebun Kopi",
                "kind": "halaman",
                "fetched_at": "2026-10-14T00:00:00Z",
                "status": 200,
                "facts": facts,
                "changes": self.store.changes(target_id=int(target["id"])),
            }
        ]
        pack = build_pack(rows, store=self.store, profil=self.profil)
        semua = [kw for item in pack["lokaseo"]["ide_konten"] for kw in item["kata_kunci_usulan"]]
        self.assertTrue(any("kedai kopi" in kw for kw in semua), semua)


class RunProfilTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "radar.sqlite3")
        self.store.add_target("https://kebunkopi.test/", "Kebun Kopi", "halaman")
        self.profil = profil_mod.Profil(nama="Kebun Kopi", jenis="kafe-kedai", situs="kebunkopi.test")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _fetcher(self, html: str):
        class Robots:
            def check(self, url, refresh=False):
                return type("V", (), {"allowed": True, "crawl_delay": None, "reason": "uji", "sitemaps": []})()

        def loader(url, timeout):
            return type(
                "P",
                (),
                {"url": url, "status": 200, "html": html, "text": html, "elapsed_ms": 3, "final_url": url},
            )()

        from lokaradar.fetch import Fetcher, RateLimiter

        return Fetcher(robots=Robots(), limiter=RateLimiter(0.0), page_loader=loader)

    def test_catatan_muncul_untuk_situs_sendiri(self):
        html = '<html><head><script type="application/ld+json">{"@type":"Organization"}</script></head><body>x</body></html>'
        result = run_once(self.store, self._fetcher(html), profil=self.profil)
        row = result["sasaran"][0]
        self.assertTrue(row["milik_sendiri"])
        self.assertTrue(row["catatan_profil"])
        self.assertIn("CafeOrCoffeeShop", row["catatan_profil"][0])

    def test_tanpa_catatan_bila_data_terstruktur_sesuai(self):
        html = '<html><head><script type="application/ld+json">{"@type":"CafeOrCoffeeShop"}</script></head><body>x</body></html>'
        result = run_once(self.store, self._fetcher(html), profil=self.profil)
        self.assertEqual(result["sasaran"][0]["catatan_profil"], [])

    def test_pesaing_tidak_diberi_catatan_jenis_usaha(self):
        self.store.add_target("https://pesaing.test/", "Pesaing", "halaman")
        html = '<html><body>x</body></html>'
        result = run_once(self.store, self._fetcher(html), profil=self.profil)
        for row in result["sasaran"]:
            if row["url"] == "https://pesaing.test/":
                self.assertFalse(row["milik_sendiri"])
                self.assertEqual(row["catatan_profil"], [])


class CliProfilTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.environ.get("LOKARADAR_DATA")
        os.environ["LOKARADAR_DATA"] = self.tmp.name

    def tearDown(self):
        if self.env is None:
            os.environ.pop("LOKARADAR_DATA", None)
        else:
            os.environ["LOKARADAR_DATA"] = self.env
        self.tmp.cleanup()

    def jalankan(self, argv: list[str]) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli_main(argv)
        return code, buffer.getvalue()

    def test_tanpa_profil_menjelaskan_cara_mengisi(self):
        code, output = self.jalankan(["profil"])
        self.assertEqual(code, 1)
        self.assertIn("--dari", output)
        self.assertIn("kafe-kedai", output)

    def test_atur_profil_lalu_tampilkan(self):
        code, output = self.jalankan(
            ["profil", "--jenis", "kafe-kedai", "--nama", "Kebun Kopi", "--kota", "Bogor", "--situs", "kopi.example"]
        )
        self.assertEqual(code, 0)
        self.assertIn("Kebun Kopi", output)
        code, lagi = self.jalankan(["profil"])
        self.assertEqual(code, 0)
        self.assertIn("Kafe, kedai kopi", lagi)

    def test_jenis_tidak_dikenal_ditolak(self):
        code, output = self.jalankan(["profil", "--jenis", "kedai-antariksaa"])
        self.assertEqual(code, 4)
        self.assertIn("Pilihan yang tersedia", output)

    def test_impor_dari_cadangan_lokaseo(self):
        berkas = Path(self.tmp.name) / "lokaseo-cadangan.json"
        berkas.write_text(json.dumps(CADANGAN, ensure_ascii=False), encoding="utf-8")
        code, output = self.jalankan(["profil", "--dari", str(berkas)])
        self.assertEqual(code, 0)
        self.assertIn("cadangan LokaSEO", output)
        self.assertIn("Bogor", output)
        # Profil tersimpan dan terpakai perintah lain
        code, lagi = self.jalankan(["profil"])
        self.assertEqual(code, 0)
        self.assertIn("Kebun Kopi Bogor", lagi)

    def test_cadangan_rusak_dilaporkan(self):
        berkas = Path(self.tmp.name) / "rusak.json"
        berkas.write_text("bukan json", encoding="utf-8")
        code, output = self.jalankan(["profil", "--dari", str(berkas)])
        self.assertEqual(code, 4)
        self.assertIn("Gagal membaca cadangan", output)


if __name__ == "__main__":
    unittest.main()
