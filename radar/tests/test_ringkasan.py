"""Ringkasan pemantauan: yang penting di atas, pola bising dinyatakan.

Daftar perubahan kronologis tidak bisa dipakai untuk mengambil keputusan: lima
sasaran yang diperiksa harian menghasilkan puluhan baris dalam seminggu, dan
yang penting tenggelam. Yang dijaga berkas ini:

- perubahan dikelompokkan (sasaran + jenis + pesan) dan dihitung, sehingga pola
  yang muncul belasan kali tampil sebagai satu baris "14x", bukan 14 baris;
- tingkat tinggi dan sedang selalu di atas;
- sasaran yang tidak aktif tidak ikut dihitung;
- tidak ada kebohongan: jumlah pemeriksaan dan perubahan diambil dari data
  yang sama dengan yang ditampilkan.
"""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaradar import ringkasan  # noqa: E402
from lokaradar.store import Store  # noqa: E402

FAKTA = {
    "title": "contoh",
    "text": "isi",
    "word_count": 120,
    "prices": [],
    "services": [],
    "structured": [],
    "rating": None,
    "content_hash": "abc",
}


class RingkasanTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = Store(Path(self._tmp.name) / "radar.sqlite3")
        self.addCleanup(self.store.close)
        self.a = self.store.add_target("https://satu.example/harga", "Klinik Sehat", "harga")
        self.b = self.store.add_target("https://dua.example/menu", "Toko Roti", "harga")

    def _potret(self, target, jumlah):
        for _ in range(jumlah):
            self.store.save_snapshot(target["id"], 200, FAKTA, sumber="permintaan-biasa")

    def _ubah(self, target, jenis, tingkat, pesan, jumlah=1):
        for _ in range(jumlah):
            self.store.save_changes(
                target["id"], [{"type": jenis, "severity": tingkat, "message": pesan,
                                "before": "lama", "after": "baru"}]
            )

    def test_kosong_tetap_jujur(self):
        data = ringkasan.bikin(self.store, hari=7)
        self.assertEqual(data["sasaran"], 2)
        self.assertEqual(data["diperiksa"], 0)
        self.assertEqual(data["perubahan"], 0)
        self.assertEqual(data["penting"], [])
        # Belum pernah diperiksa sama sekali: tidak boleh diklaim "tidak berubah".
        self.assertEqual(data["diam"], [])
        self.assertEqual([d["sasaran"] for d in data["belum_diperiksa"]], ["Klinik Sehat", "Toko Roti"])
        self.assertIn("Belum ada perubahan", ringkasan.markdown(data))
        self.assertIn("Belum diperiksa", ringkasan.markdown(data))

    def test_sasaran_nonaktif_tidak_dihitung(self):
        self.store.set_enabled(self.b["id"], False)
        data = ringkasan.bikin(self.store, hari=7)
        self.assertEqual(data["sasaran"], 1)
        self.assertEqual([d["sasaran"] for d in data["belum_diperiksa"]], ["Klinik Sehat"])

    def test_penting_diatas_dan_pola_dihitung(self):
        self._potret(self.a, 5)
        self._potret(self.b, 2)
        self._ubah(self.a, "harga", "tinggi", "Harga turun menjadi Rp 300.000.")
        self._ubah(self.a, "layanan", "sedang", "Muncul layanan baru: pesan antar.")
        self._ubah(self.b, "isi", "info", "Isi halaman berubah.", jumlah=6)
        data = ringkasan.bikin(self.store, hari=7)

        self.assertEqual(data["diperiksa"], 7)
        self.assertEqual(data["perubahan"], 8)
        self.assertEqual(data["per_tingkat"]["tinggi"], 1)
        self.assertEqual(data["per_tingkat"]["info"], 6)
        # Tingkat tinggi lebih dulu; pola berulang jadi satu baris dengan hitungan.
        self.assertEqual([p["tingkat"] for p in data["penting"]], ["tinggi", "sedang"])
        self.assertEqual(len(data["berulang"]), 1)
        self.assertEqual(data["berulang"][0]["jumlah"], 6)
        # Delapan perubahan hanya menghasilkan tiga baris.
        self.assertEqual(len(data["penting"]) + len(data["berulang"]), 3)

    def test_diam_hanya_untuk_yang_benar_diperiksa(self):
        """Sasaran yang belum pernah diambil tidak boleh dibilang tidak berubah.

        "Tidak berubah" adalah klaim: radar sudah melihat isinya dua kali dan
        tidak menemukan beda. Sasaran yang belum pernah diambil tidak punya
        dasar untuk klaim itu.
        """
        self._potret(self.a, 3)          # diperiksa, tidak ada perubahan
        # self.b sengaja tidak punya potret sama sekali
        data = ringkasan.bikin(self.store, hari=7)
        self.assertEqual([d["sasaran"] for d in data["diam"]], ["Klinik Sehat"])
        self.assertEqual([d["sasaran"] for d in data["belum_diperiksa"]], ["Toko Roti"])

    def _ubah_pada(self, target, jenis, tingkat, pesan, stempel):
        """Simpan satu perubahan dengan stempel tertentu (butuh SQL langsung)."""
        self.store.connection.execute(
            "INSERT INTO changes (target_id, detected_at, type, severity, message, before_value, after_value)"
            " VALUES (?,?,?,?,?,?,?)",
            (target["id"], stempel, jenis, tingkat, pesan, json.dumps("lama"), json.dumps("baru")),
        )
        self.store.connection.commit()

    def test_tingkat_sama_yang_terbaru_di_atas(self):
        """Dua perubahan sama-sama tinggi: yang lebih baru harus lebih dulu.

        Pernah rusak karena pengurutan dilakukan dua kali dan yang kedua
        menimpa kunci waktu yang sudah dipasang yang pertama.
        """
        self._ubah_pada(self.a, "harga", "tinggi", "Harga naik.", "2026-09-25T07:00:00Z")
        self._ubah_pada(self.a, "harga", "tinggi", "Harga turun.", "2026-10-14T07:00:00Z")
        data = ringkasan.bikin(self.store, hari=30)
        self.assertEqual([p["terakhir"][:10] for p in data["penting"]],
                         ["2026-10-14", "2026-09-25"])

    def test_pola_yang_sama_tidak_ditulis_berulang(self):
        self._ubah(self.b, "isi", "info", "Isi halaman berubah.", jumlah=4)
        data = ringkasan.bikin(self.store, hari=7)
        teks = ringkasan.markdown(data)
        self.assertEqual(teks.count("Isi halaman berubah."), 1, "pola sama harus jadi satu baris")
        self.assertIn("4x", teks)

    def test_tidak_ada_yang_perlu_dilihat_dinyatakan(self):
        self._ubah(self.b, "isi", "info", "Isi halaman berubah.")
        data = ringkasan.bikin(self.store, hari=7)
        self.assertEqual(data["penting"], [])
        self.assertIn("Tidak ada perubahan bertingkat tinggi atau sedang", ringkasan.markdown(data))

    def test_tanggal_dibaca_manusia(self):
        self.assertEqual(ringkasan._tanggal("2026-10-14T02:31:00Z"), "14 Okt")
        self.assertEqual(ringkasan._tanggal(""), "")
        self.assertEqual(ringkasan._tanggal(None), "")

    def test_nama_sasaran_jatuh_ke_alamat(self):
        self.assertEqual(ringkasan._nama_sasaran({"label": "", "url": "https://x.example"}), "https://x.example")
        self.assertEqual(ringkasan._nama_sasaran({"label": "Nama", "url": "https://x.example"}), "Nama")


if __name__ == "__main__":
    unittest.main()
