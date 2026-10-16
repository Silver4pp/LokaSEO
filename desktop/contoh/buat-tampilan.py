"""Membuat contoh tampilan halaman radar yang bisa dibuka tanpa menjalankan aplikasi.

Berkas hasilnya (`contoh/tampilan-radar.html`) memuat halaman radar apa adanya —
HTML dan JavaScript diambil langsung dari `lokaseo_desktop.pages` — lalu diisi data
contoh lewat `window.__RADAR_DATA__`, cabang yang memang sudah dipakai halaman itu
untuk keadaan tanpa server.

Gunanya: meninjau tampilan di mana saja (termasuk pratinjau ruang kerja) tanpa
harus menjalankan aplikasi Windows, dan memastikan tampilan tidak pernah
bergantung pada berkas luar — semua gaya dan skrip ditulis di dalam berkas.

Jalankan dari folder `desktop/`:

    python3 contoh/buat-tampilan.py

Data di dalamnya hanya contoh. Angka rating, harga, dan tanggal dipakai untuk
memperlihatkan bentuk tampilan, bukan hasil pantauan sungguhan.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
if str(AKAR) not in sys.path:
    sys.path.insert(0, str(AKAR))

from lokaseo_desktop import pages  # noqa: E402

KELUARAN = Path(__file__).resolve().parent / "tampilan-radar.html"

PROFIL = {
    "nama": "Kopi Ranah",
    "jenis": "kafe-kedai",
    "jenis_label": "Kafe, kedai kopi, atau tempat makan kecil",
    "kota": "Bogor",
    "situs": "kotaranah.example",
    "sumber": "pengaturan LokaSEO di aplikasi desktop",
    "ambang_rating": 4.3,
    "rating_penting": True,
    "schema": ["CafeOrCoffeeShop", "Restaurant", "LocalBusiness"],
    "kata_kunci": ["kedai kopi", "menu", "pesan antar"],
    "catatan": [
        "Cantumkan jam buka terbaru, menu, dan pilihan pesan antar di halaman.",
    ],
    "ringkas": "Kopi Ranah · jenis: Kafe, kedai kopi, atau tempat makan kecil · kota: Bogor",
}

INFO = {
    "tersedia": True,
    "versi": "0.1.0",
    "data": "C:\\Users\\Anda\\AppData\\Local\\LokaSEO\\radar",
    "sasaran": 6,
    "sasaran_aktif": 6,
    "potret": 11,
    "perubahan": 7,
    "terakhir_jalan": "2026-10-14 16:20",
    "sasaran_tempat": 1,
    "peramban": "siap",
    "kunci_places": True,
    "luring": False,
    "profil": PROFIL,
    "pekerjaan": {
        "id": 3,
        "keadaan": "selesai",
        "mulai": "2026-10-14T09:20:11Z",
        "selesai": "2026-10-14T09:20:26Z",
        "ringkasan": {"diperiksa": 4, "gagal": 0, "dilewati": 0, "perubahan": 2},
        "galat": None,
    },
}

SASARAN = [
    {
        "id": 1,
        "url": "https://kotaranah.example/",
        "label": "Situs sendiri",
        "jenis": "halaman",
        "aktif": True,
        "diperiksa_pada": "2026-10-14T09:20:12Z",
        "sumber": "permintaan-biasa",
        "catatan": "",
        "judul": "Kopi Ranah — Kedai Kopi Bogor",
        "kata": 412,
        "rating": 4.6,
        "jumlah_ulasan": 239,
        "harga_terendah": {"currency": "IDR", "amount": 18000, "name": "Kopi susu"},
        "jumlah_perubahan": 2,
    },
    {
        "id": 2,
        "url": "https://kopiutara.example/menu",
        "label": "Pesaing Kopi Utara",
        "jenis": "harga",
        "aktif": True,
        "diperiksa_pada": "2026-10-14T09:20:17Z",
        "sumber": "permintaan-biasa",
        "catatan": "",
        "judul": "Menu — Kopi Utara",
        "kata": 268,
        "rating": None,
        "jumlah_ulasan": None,
        "harga_terendah": {"currency": "IDR", "amount": 17000, "name": "Es kopi susu"},
        "jumlah_perubahan": 3,
    },
    {
        "id": 3,
        "url": "https://roasteryselatan.example/harga",
        "label": "Pesaing Roastery Selatan",
        "jenis": "harga",
        "aktif": True,
        "diperiksa_pada": "2026-10-14T09:20:21Z",
        "sumber": "peramban",
        "catatan": "",
        "judul": "Daftar harga — Roastery Selatan",
        "kata": 537,
        "rating": None,
        "jumlah_ulasan": None,
        "harga_terendah": {"currency": "IDR", "amount": 25000, "name": "Kopi tubruk"},
        "jumlah_perubahan": 1,
    },
    {
        "id": 6,
        "url": "https://kateringtimur.example/harga",
        "label": "Katering Timur",
        "jenis": "harga",
        "aktif": True,
        "diperiksa_pada": None,
        "sumber": "",
        "catatan": "",
        "judul": "",
        "kata": 0,
        "rating": None,
        "jumlah_ulasan": None,
        "harga_terendah": None,
        "jumlah_perubahan": 0,
    },
    {
        "id": 5,
        "url": "https://kafebarat.example/menu",
        "label": "Pesaing Kafe Barat",
        "jenis": "harga",
        "aktif": True,
        "diperiksa_pada": "2026-10-14T09:20:27Z",
        "sumber": "permintaan-biasa",
        "catatan": "",
        "judul": "Menu dan harga — Kafe Barat",
        "kata": 301,
        "rating": None,
        "jumlah_ulasan": None,
        "harga_terendah": {"currency": "IDR", "amount": 21000, "name": "Americano"},
        "jumlah_perubahan": 0,
    },
    {
        "id": 4,
        "url": "tempat:ChIJcontohplaceidBogor",
        "label": "Rating Google Kopi Ranah",
        "jenis": "reputasi",
        "aktif": True,
        "diperiksa_pada": "2026-10-14T09:20:24Z",
        "sumber": "places-api",
        "catatan": "",
        "judul": "Kopi Ranah",
        "kata": 0,
        "rating": 4.6,
        "jumlah_ulasan": 239,
        "harga_terendah": None,
        "jumlah_perubahan": 1,
    },
]

PERAMBAN = {
    "tersedia": True,
    "jalur": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "nama": "Microsoft Edge",
    "versi": "Microsoft Edge 141.0.3537.57",
    "sumber": "terpasang di sistem",
    "pesan": "Peramban siap dipakai untuk merender halaman ber-JavaScript.",
    "mode_render": "auto",
    "instalator": False,
}

JADWAL = {
    "nama_tugas": "LokaSEO - Radar harian",
    "perintah": '"C:\\Program Files\\LokaSEO\\LokaSEO.exe" --radar-periksa',
    "cron": "0 7 * * * LokaSEO.exe --radar-periksa",
    "dukungan": {
        "bisa": True,
        "platform": "win32",
        "nama_tugas": "LokaSEO - Radar harian",
        "pesan": "Windows Task Scheduler siap dipakai.",
    },
    "terpasang": True,
    "aktif": True,
    "waktu": "07:00",
    "frekuensi": "harian",
    "hari": "",
    "berikutnya": "2026-10-15 07:00",
}

PERUBAHAN = [
    {
        "id": 7,
        "target_id": 1,
        "pada": "2026-10-14T09:20:12Z",
        "jenis": "harga",
        "tingkat": "sedang",
        "pesan": "Harga terendah naik dari IDR 16.000 menjadi IDR 18.000.",
    },
    {
        "id": 6,
        "target_id": 4,
        "pada": "2026-10-14T09:20:24Z",
        "jenis": "rating",
        "tingkat": "tinggi",
        "pesan": "Rating turun dari 4,5 menjadi 4,4 pada skala 5; jumlah ulasan 214 menjadi 239.",
    },
    {
        "id": 5,
        "target_id": 3,
        "pada": "2026-10-14T09:20:21Z",
        "jenis": "cara-pengambilan",
        "tingkat": "info",
        "pesan": "Cara pengambilan berubah dari permintaan biasa menjadi peramban.",
    },
    {
        "id": 4,
        "target_id": 2,
        "pada": "2026-10-14T09:20:17Z",
        "jenis": "layanan",
        "tingkat": "sedang",
        "pesan": "Muncul layanan baru: “Pesan antar sendiri, tanpa biaya”.",
    },
    {
        "id": 3,
        "target_id": 2,
        "pada": "2026-10-13T09:05:00Z",
        "jenis": "isi",
        "tingkat": "info",
        "pesan": "Isi halaman bertambah 118 kata (dari 150 menjadi 268).",
    },
    {
        "id": 2,
        "target_id": 4,
        "pada": "2026-10-12T09:04:00Z",
        "jenis": "reputasi",
        "tingkat": "info",
        "pesan": "Pemantauan pertama: potret awal disimpan sebagai dasar pembanding.",
    },
]

RINGKASAN = {
    "hari": 7,
    "sejak": "2026-10-07T09:20:00Z",
    "sasaran": 6,
    "diperiksa": 11,
    "perubahan": 20,
    "per_tingkat": {"tinggi": 1, "sedang": 2, "rendah": 0, "info": 17},
    "penting": [
        {
            "target_id": 4,
            "sasaran": "Rating Google Kopi Ranah",
            "url": "tempat:ChIJcontohplaceidBogor",
            "jenis": "rating",
            "tingkat": "tinggi",
            "pesan": "Rating turun dari 4,5 menjadi 4,4 pada skala 5; jumlah ulasan 214 menjadi 239.",
            "jumlah": 1,
            "pertama": "2026-10-14T09:20:24Z",
            "terakhir": "2026-10-14T09:20:24Z",
        },
        {
            "target_id": 1,
            "sasaran": "Situs sendiri",
            "url": "https://kotaranah.example/",
            "jenis": "harga",
            "tingkat": "sedang",
            "pesan": "Harga terendah naik dari IDR 16.000 menjadi IDR 18.000.",
            "jumlah": 2,
            "pertama": "2026-10-11T09:04:00Z",
            "terakhir": "2026-10-14T09:20:12Z",
        },
        {
            "target_id": 2,
            "sasaran": "Pesaing Kopi Utara",
            "url": "https://kopiutara.example/menu",
            "jenis": "layanan",
            "tingkat": "sedang",
            "pesan": "Muncul layanan baru: \u201cPesan antar sendiri, tanpa biaya\u201d.",
            "jumlah": 1,
            "pertama": "2026-10-14T09:20:17Z",
            "terakhir": "2026-10-14T09:20:17Z",
        },
    ],
    "berulang": [
        {
            "target_id": 2,
            "sasaran": "Pesaing Kopi Utara",
            "url": "https://kopiutara.example/menu",
            "jenis": "isi",
            "tingkat": "info",
            "pesan": "Isi halaman berubah, tetapi tidak ada harga atau layanan yang berubah.",
            "jumlah": 14,
            "pertama": "2026-10-08T09:02:00Z",
            "terakhir": "2026-10-14T09:20:17Z",
        }
    ],
    "diam": [
        {
            "sasaran": "Pesaing Kafe Barat",
            "url": "https://kafebarat.example/menu",
        }
    ],
    "belum_diperiksa": [
        {
            "sasaran": "Katering Timur",
            "url": "https://kateringtimur.example/harga",
        }
    ],
    "terakhir_diperiksa": "2026-10-14T09:20:27Z",
    "ambang_berulang": 3,
}

DATA = {
    "info": INFO,
    "sasaran": SASARAN,
    "perubahan": PERUBAHAN,
    "jadwal": JADWAL,
    "peramban": PERAMBAN,
    "ringkasan": RINGKASAN,
}


def main() -> int:
    halaman = pages.RADAR_PAGE
    skrip = f"<script>window.__RADAR_DATA__ = {json.dumps(DATA, ensure_ascii=False)};</script>\n"
    skrip += "<script>\n" + pages.RADAR_JS + "\n</script>\n"
    if '<script src="/radar.js"></script>' not in halaman:
        raise SystemExit("Bentuk halaman radar berubah: tambalan skrip perlu diperbarui.")
    isi = halaman.replace('<script src="/radar.js"></script>', skrip.strip())
    if "<script>window.__RADAR_DATA__" not in isi:
        raise SystemExit("Data contoh gagal disisipkan ke halaman.")
    # Halaman harus bisa dibuka tanpa jaringan. Alamat `https://` pada teks
    # contoh (mis. petunjuk di kolom isian) tidak dihitung — yang dihitung hanya
    # rujukan berkas luar, sama seperti pemeriksaan di uji desktop.
    kepala = isi.split("<script>window.__RADAR_DATA__")[0]
    luar = [
        penanda
        for penanda in ('src="http', "src='http", 'href="http', "href='http", "@import")
        if penanda in kepala
    ]
    if luar:
        raise SystemExit(f"Halaman masih memuat sumber luar: {luar}")
    KELUARAN.write_text(isi, encoding="utf-8")
    print(f"Contoh tampilan ditulis: {KELUARAN} ({len(isi):,} bita)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
