"""Uji ekspor dan impor daftar sasaran: berkasnya bisa dipindah, tidak merusak data."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar import sasaran  # noqa: E402
from lokaradar.store import Store  # noqa: E402


class SasaranTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "radar.sqlite3")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _isi_bawaan(self):
        self.store.add_target("https://pesaing-a.example/menu", "Pesaing A", "harga")
        self.store.add_target("https://pesaing-b.example/", "Pesaing B", "halaman")

    # -- ekspor -------------------------------------------------------------
    def test_ekspor_memuat_semua_sasaran(self):
        self._isi_bawaan()
        berkas = sasaran.ekspor(self.store)
        self.assertEqual(berkas["format"], sasaran.FORMAT)
        self.assertEqual(berkas["jumlah"], 2)
        self.assertEqual([item["url"] for item in berkas["sasaran"]],
                         ["https://pesaing-a.example/menu", "https://pesaing-b.example/"])
        self.assertEqual(berkas["sasaran"][0]["jenis"], "harga")
        self.assertTrue(berkas["sasaran"][0]["aktif"])

    def test_ekspor_menyertakan_profil_sebagai_keterangan(self):
        self._isi_bawaan()
        berkas = sasaran.ekspor(self.store, profil={"jenis_usaha": "kafe-kedai", "kota": "Bogor"})
        self.assertEqual(berkas["profil"]["jenis_usaha"], "kafe-kedai")
        self.assertEqual(berkas["profil"]["kota"], "Bogor")

    def test_ekspor_kosong_bukan_galat(self):
        berkas = sasaran.ekspor(self.store)
        self.assertEqual(berkas["jumlah"], 0)
        self.assertEqual(berkas["sasaran"], [])

    def test_tulis_menghasilkan_berkas_json_yang_bisa_dibaca_ulang(self):
        self._isi_bawaan()
        jalur = Path(self.tmp.name) / "keluaran" / "sasaran.json"
        ringkas = sasaran.tulis(self.store, jalur)
        self.assertEqual(ringkas["jumlah"], 2)
        isi = json.loads(jalur.read_text(encoding="utf-8"))
        self.assertEqual(isi["format"], sasaran.FORMAT)
        self.assertTrue(ringkas["berkas"].endswith("sasaran.json"))

    def test_nama_berkas_bertanggal(self):
        nama = sasaran.nama_berkas()
        self.assertTrue(nama.startswith("sasaran-radar-"))
        self.assertTrue(nama.endswith(".json"))

    # -- membaca berkas -----------------------------------------------------
    def test_membaca_berkas_buatan_sendiri(self):
        entri, catatan, format_terbaca = sasaran.baca(
            json.dumps(
                {
                    "format": sasaran.FORMAT,
                    "sasaran": [{"url": "https://x.example/", "label": "X", "jenis": "layanan"}],
                }
            )
        )
        self.assertEqual(format_terbaca, sasaran.FORMAT)
        self.assertEqual(entri, [{"url": "https://x.example/", "label": "X", "jenis": "layanan"}])
        self.assertEqual(catatan, [])

    def test_membaca_daftar_json_sederhana(self):
        entri, _catatan, format_terbaca = sasaran.baca('["https://a.example/", "https://b.example/"]')
        self.assertEqual(format_terbaca, "json-daftar")
        self.assertEqual([item["url"] for item in entri], ["https://a.example/", "https://b.example/"])

    def test_membaca_teks_biasa_dengan_komentar(self):
        entri, catatan, format_terbaca = sasaran.baca(
            "# daftar dari teman\n\nhttps://a.example/\n   \nhttps://b.example/harga\n"
        )
        self.assertEqual(format_terbaca, "teks")
        self.assertEqual([item["url"] for item in entri], ["https://a.example/", "https://b.example/harga"])
        # Satu baris komentar dan dua baris kosong memang dilewati, dan jumlahnya
        # disebut supaya pembaca tahu tidak ada alamat yang hilang diam-diam.
        self.assertIn("3 baris kosong atau komentar diabaikan.", catatan)

    def test_format_lain_dibaca_dengan_catatan(self):
        _entri, catatan, format_terbaca = sasaran.baca(
            json.dumps({"format": "lokaradar.sasaran.v2", "sasaran": [{"url": "https://a.example/"}]})
        )
        self.assertEqual(format_terbaca, "lokaradar.sasaran.v2")
        self.assertTrue(any("v2" in satu for satu in catatan))

    def test_berkas_kosong_ditolak_dengan_alasan(self):
        with self.assertRaises(sasaran.BerkasTidakSah) as ctx:
            sasaran.baca("   \n  ")
        self.assertIn("kosong", str(ctx.exception))

    def test_berkas_bukan_daftar_sasaran_ditolak(self):
        laporan = json.dumps({"dibuat_pada": "2026-10-14T00:00:00Z", "perubahan": [{"jenis": "harga"}]})
        with self.assertRaises(sasaran.BerkasTidakSah) as ctx:
            sasaran.baca(laporan)
        self.assertIn("sasaran", str(ctx.exception))

    def test_json_rusak_ditolak_dengan_barisnya(self):
        with self.assertRaises(sasaran.BerkasTidakSah) as ctx:
            sasaran.baca('{"sasaran": [{"url": "https://a.example/"},]}')
        self.assertIn("baris", str(ctx.exception))

    def test_berkas_terlalu_besar_ditolak(self):
        with self.assertRaises(sasaran.BerkasTidakSah) as ctx:
            sasaran.baca("https://a.example/\n" * 100_000)
        self.assertIn("KB", str(ctx.exception))

    def test_batas_entri_dipotong_dengan_catatan(self):
        teks = "\n".join(f"https://pesaing-{i}.example/" for i in range(sasaran.MAKS_ENTRI + 5))
        entri, catatan, _ = sasaran.baca(teks)
        self.assertEqual(len(entri), sasaran.MAKS_ENTRI)
        self.assertTrue(any("500 entri pertama" in satu for satu in catatan))

    # -- impor --------------------------------------------------------------
    def test_impor_menambah_dan_menggabung(self):
        self._isi_bawaan()
        teks = json.dumps({
            "format": sasaran.FORMAT,
            "sasaran": [
                {"url": "https://pesaing-b.example/", "label": "Pesaing B", "jenis": "halaman"},
                {"url": "https://pesaing-c.example/", "label": "Pesaing C", "jenis": "reputasi"},
            ],
        })
        hasil = sasaran.impor(self.store, teks)
        self.assertEqual(hasil["ditambahkan"], 1)
        self.assertEqual(hasil["sudah_ada"], 1)
        self.assertEqual(hasil["sasaran_sekarang"], 3)
        self.assertIsNotNone(self.store.find_target("https://pesaing-c.example/"))

    def test_impor_menghitung_yang_diperbarui(self):
        self._isi_bawaan()
        teks = json.dumps({"sasaran": [{"url": "https://pesaing-a.example/menu", "label": "Pesaing A (baru)", "jenis": "harga"}]})
        hasil = sasaran.impor(self.store, teks)
        self.assertEqual(hasil["diperbarui"], 1)
        self.assertEqual(self.store.find_target("https://pesaing-a.example/menu")["label"], "Pesaing A (baru)")

    def test_alamat_saja_tidak_mengubah_label_dan_jenis(self):
        """Berkas yang hanya berisi alamat tidak boleh mengubah apa pun pada sasaran lama."""
        self._isi_bawaan()
        hasil = sasaran.impor(self.store, "https://pesaing-a.example/menu\n")
        self.assertEqual(hasil["sudah_ada"], 1)
        self.assertEqual(hasil["diperbarui"], 0)
        baris = self.store.find_target("https://pesaing-a.example/menu")
        self.assertEqual(baris["label"], "Pesaing A")
        self.assertEqual(baris["kind"], "harga")

    def test_jenis_yang_disebut_berkas_tetap_dipakai(self):
        self._isi_bawaan()
        hasil = sasaran.impor(
            self.store, json.dumps({"sasaran": [{"url": "https://pesaing-a.example/menu", "jenis": "reputasi"}]})
        )
        self.assertEqual(hasil["diperbarui"], 1)
        self.assertEqual(self.store.find_target("https://pesaing-a.example/menu")["kind"], "reputasi")

    def test_impor_tidak_pernah_menghapus(self):
        self._isi_bawaan()
        sasaran.impor(self.store, "https://baru.example/\n")
        url = [row["url"] for row in self.store.targets()]
        self.assertIn("https://pesaing-a.example/menu", url)
        self.assertIn("https://pesaing-b.example/", url)
        self.assertIn("https://baru.example/", url)

    def test_impor_uji_coba_tidak_menyimpan(self):
        hasil = sasaran.impor(self.store, "https://baru.example/\n", uji_coba=True)
        self.assertEqual(hasil["ditambahkan"], 1)
        self.assertEqual(self.store.targets(), [])
        self.assertTrue(hasil["uji_coba"])

    def test_entri_ditolak_disebut_satu_per_satu(self):
        hasil = sasaran.impor(self.store, "https://baik.example/\nbukan-url\nftp://salah.example/\n")
        self.assertEqual(hasil["ditambahkan"], 1)
        self.assertEqual([item["entri"] for item in hasil["ditolak"]], ["bukan-url", "ftp://salah.example/"])

    def test_jenis_asing_diganti_dan_dicatat(self):
        hasil = sasaran.impor(self.store, json.dumps({"sasaran": [{"url": "https://a.example/", "jenis": "promo"}]}))
        self.assertEqual(self.store.find_target("https://a.example/")["kind"], "halaman")
        self.assertTrue(any("promo" in satu for satu in hasil["catatan"]))

    def test_ganda_di_dalam_berkas_dihitung_sekali(self):
        hasil = sasaran.impor(self.store, "https://a.example/\nhttps://a.example/\n")
        self.assertEqual(hasil["ditambahkan"], 1)
        self.assertEqual(hasil["ganda"], 1)

    def test_batas_jumlah_sasaran_menunda_sisanya(self):
        sasaran.impor(self.store, "https://a.example/\n")
        teks = "https://b.example/\nhttps://c.example/\n"
        hasil = sasaran.impor(self.store, teks, maksimum=2)
        self.assertEqual(hasil["ditambahkan"], 1)
        self.assertEqual(hasil["tertunda"], 1)
        self.assertTrue(any("batas" in satu or "sasaran" in satu for satu in hasil["catatan"]))
        self.assertIsNone(self.store.find_target("https://c.example/"))

    def test_label_panjang_dipotong(self):
        hasil = sasaran.impor(
            self.store, json.dumps({"sasaran": [{"url": "https://a.example/", "label": "x" * 200}]})
        )
        self.assertEqual(hasil["ditambahkan"], 1)
        self.assertEqual(len(self.store.find_target("https://a.example/")["label"]), sasaran.LABEL_MAKS)

    def test_profil_dari_berkas_diabaikan_dengan_catatan(self):
        teks = json.dumps({
            "format": sasaran.FORMAT,
            "profil": {"jenis_usaha": "klinik-gigi"},
            "sasaran": [{"url": "https://a.example/"}],
        })
        hasil = sasaran.impor(self.store, teks)
        self.assertTrue(any("profil" in satu for satu in hasil["catatan"]))

    def test_tempat_places_diterima(self):
        hasil = sasaran.impor(self.store, "tempat:ChIJ1234567890\n")
        self.assertEqual(hasil["ditambahkan"], 1)
        self.assertIsNotNone(self.store.find_target("tempat:ChIJ1234567890"))

    # -- ringkasan ----------------------------------------------------------
    def test_ringkasan_menyebut_semua_angka(self):
        hasil = sasaran.impor(self.store, "https://a.example/\nhttps://a.example/\nbukan-url\n")
        baris = sasaran.ringkas(hasil)
        teks = "\n".join(baris)
        self.assertIn("1 ditambahkan", teks)
        self.assertIn("1 ganda", teks)
        self.assertIn("ditolak", teks)
        self.assertIn("Belum ada halaman yang dihubungi", teks)

    def test_ringkasan_uji_coba_menyebut_tidak_menyimpan(self):
        hasil = sasaran.impor(self.store, "https://a.example/\n", uji_coba=True)
        self.assertIn("Uji coba: tidak ada yang disimpan.", sasaran.ringkas(hasil))

    def test_ringkasan_tanpa_sasaran_baru_tetap_jelas(self):
        hasil = sasaran.impor(self.store, "bukan-url\n")
        self.assertIn("Tidak ada sasaran baru di berkas itu.", sasaran.ringkas(hasil))


if __name__ == "__main__":
    unittest.main()
