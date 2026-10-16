# Catatan uji nyata: usaha Bogor, 14 Oktober 2026

Uji dilakukan sekali, sopan: satu halaman per usaha, `robots.txt` dihormati,
jeda 2,5 detik per host, User-Agent jujur (`LokaRadar/0.1 …`). Total 7 permintaan
halaman + 7 permintaan `robots.txt`. Data tersimpan lokal di `radar/uji-bogor/`
(folder ini tidak ikut masuk Git).

## Hasil per usaha

| Usaha | Jenis | Status | Data terstruktur terbaca | Rating | Harga | Kata | Gambar tanpa alt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Damessa Klinik Gigi (Bogor) | Kesehatan | 200 | `BreadcrumbList`, `ListItem` | — | — | 2.687 | 1 dari 32 |
| OMDC Dental (Bogor) | Kesehatan | 200 | tidak ada | — | IDR 100.000, IDR 149.000+ | 4.781 | 83 dari 83 |
| FDC Dental Clinic (Bogor) | Kesehatan | 200 | tidak ada | — | — | **3** | 0 dari 0 |
| Lapis Bogor Sangkuriang | Toko | **405** | — | — | — | — | — |
| Bogor Coklat | Toko | 200 | `BreadcrumbList`, `ListItem`, `Organization` | — | — | 474 | 12 dari 31 |
| Bogor Raincake | Toko | 200 | `BreadcrumbList`, `CollectionPage`, `ListItem` | — | — | 1.466 | 0 dari 104 |
| Luma Senja Villa (Bogor) | Penginapan | 200 | `Hotel`, `ItemList`, `WebPage` | 9,9 dari 10 (784 ulasan) | — | 1.171 | 3 dari 15 |

## Yang berhasil

1. **Pengambilan dasar bekerja** pada 6 dari 7 situs: judul, deskripsi, struktur heading, jumlah kata, dan hitungan gambar tanpa teks alternatif semuanya terbaca.
2. **Data terstruktur terbaca** bila ada. Luma Senja villa memuat `Hotel` + `aggregateRating` lengkap, dan skalanya (9,9 dari **10**) ikut terbaca benar.
3. **Harga terbaca** di OMDC Dental (IDR 100.000, IDR 149.000) karena harganya ditulis sebagai teks biasa di halaman.
4. **Radar menolak dengan jujur** saat situs memblokir: Lapis Bogor menjawab HTTP 405 dan dicatat sebagai kegagalan sasaran — tidak diambil paksa, tidak diulang-ulang, dan tidak menyamar sebagai peramban untuk menembusnya.

## Yang kurang (temuan sungguhan dari lapangan)

1. **Hampir tidak ada usaha lokal yang memuat rating di situsnya.** Dari 7 usaha, hanya 1 yang memuat `aggregateRating`. Jadi memantau reputasi lewat situs sendiri **tidak cukup**: jalur yang masuk akal adalah Google Places API (kunci pengguna sendiri) atau halaman direktori yang memuat rating.
2. **Konten hasil JavaScript tidak terbaca.** FDC Dental hanya terbaca **3 kata** — halaman depannya dirender JavaScript, jadi `Fetcher` biasa hanya menerima kerangka kosong. Perlu `DynamicFetcher`/`StealthyFetcher` Scrapling (belum dipakai) atau pilihan sumber lain.
3. **Toko daring menyembunyikan harga di keranjang/JS.** Tiga toko oleh-oleh tidak memuat harga yang bisa dibaca (tidak ada JSON-LD `Product`/`offers`), sehingga pemantauan harga produk belum berguna untuk mereka.
4. **Sebagian situs menolak pengambil sederhana** (405). Itu hak mereka. Radar melaporkannya apa adanya; memaksa masuk berarti harus menyamar, dan itu bertentangan dengan janji identitas jujur.
5. **Kafe kecil di Bogor hampir semuanya hanya punya Instagram.** Pencarian kafe Bogor hanya menemukan daftar yang menautkan akun Instagram: tidak ada situs untuk dipantau. Pemantauan halaman untuk jenis ini praktis tidak ada gunanya; yang relevan adalah papan reputasi.
6. **Skala rating berbeda-beda.** 9,9 dari 10 tidak boleh dibandingkan langsung dengan 4,5 dari 5. Papan sekarang memakai **rasio terhadap skala** dan menampilkan kolom "Setara (dari 5)".

## Yang diperbaiki karena uji ini

| Temuan | Perbaikan |
| --- | --- |
| Jalur bawaan ternyata menyamar sebagai Chrome/macOS (header `sec-ch-ua`, referer Google) | `impersonate=None` + `stealthy_headers=False` + User-Agent jujur. Ada 5 uji penjaga di `tests/test_fetch_identity.py`. Mode menyamar hanya lewat `--stealthy`, diberi peringatan saat dipakai. |
| Papan mencampur skala rating | Peringkat memakai rasio; ditambah kolom "Setara / 5", rata-rata setara, dan catatan bila skala berbeda. |

## Tindak lanjut (14 Oktober 2026, sore)

Dua temuan di atas sudah dikerjakan:

- **Temuan 1 → Places API.** Ada perintah `cari` (`lokaradar cari "Klinik Gigi" --kota Bogor`)
  yang mencari `place_id` memakai kunci Places API pengguna sendiri, plus butir ceklis
  otomatis untuk jenis usaha yang ratingnya penting.
- **Temuan 2 → rendering peramban.** Perintah `run`/`scrape` kini punya `--render auto`
  (bawaan): halaman yang hanya terbaca sedikit kata diambil **ulang** dengan peramban
  headless. Diuji ulang ke situs yang sama:

  | | Sebelum (permintaan biasa) | Sesudah (`--render auto`) |
  | --- | --- | --- |
  | `fdcdentalclinic.co.id` | 3 kata, tanpa judul | **537 kata**, judul "FDC Dental Clinic", deskripsi terbaca, 244 gambar (1 tanpa alt) |

  Permintaan kedua tetap menghormati jeda per host, dan identitas tetap jujur: User-Agent
  `LokaRadar/0.1`, tanpa referer Google (bawaan `google_search=True` milik Scrapling
  dimatikan). Perlu dicatat apa adanya: peramban tetap mengirim sebagian header khas
  peramban (`sec-ch-ua`, `Sec-Fetch-*`) yang tidak bisa dihapus.

## Langkah berikutnya yang masuk akal

1. **Pakai Places API** untuk jenis usaha yang ratingnya penting (klinik, kafe, penginapan): sasaran `tempat:<place_id>` + kunci sendiri, tanpa menyentuh halaman Google.
2. **Tambah pembacaan JavaScript** lewat `DynamicFetcher` untuk situs seperti FDC, dengan jeda tetap sopan.
3. **Prioritaskan papan reputasi** untuk jenis usaha yang situsnya tidak ada (kafe), dan pemantauan halaman untuk jenis usaha yang situsnya aktif (klinik, penginapan, toko besar).
