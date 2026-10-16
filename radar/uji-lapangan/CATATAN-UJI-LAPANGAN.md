# Uji lapangan LokaRadar — 13 situs usaha Bogor (14 Oktober 2026)

Bukan uji laboratorium: ini radar yang dijalankan sungguhan pada halaman-halaman usaha
yang benar-benar ada di Bogor, dengan identitas jujur `LokaRadar/0.1`, `robots.txt`
dihormati, satu halaman per situs, dan jeda 2,5 detik per host. Tujuannya bukan memamerkan
angka bagus, melainkan **menemukan apa yang rusak sebelum dipakai orang lain**.

## Apa yang dijalankan

| Hal | Keterangan |
| --- | --- |
| Sasaran | 13 alamat dari 6 jenis usaha: klinik gigi (2), toko oleh-oleh/kue (4), hotel (1), katering (1), laundry (2), bimbel (2) |
| Putaran | 3 kali pada hari yang sama (14 Okt 2026), semua sasaran diperiksa setiap putaran |
| Mode | `render=auto` — halaman yang tipis dan tampak disusun JavaScript diambil ulang dengan peramban |
| Identitas | `LokaRadar/0.1 (+…open-seo; pemantauan SEO lokal; hubungi pemilik situs bila keberatan)` |
| Data mentah | `hasil-20261014.json` di folder ini (potret terakhir setiap sasaran) |

## Angka apa adanya

- **12 dari 13 sasaran berhasil dipotret.** Satu ditolak situsnya sendiri.
- **1 kegagalan tetap: `lapisbogor.co.id` menjawab HTTP 405 (Not Allowed)** di ketiga
  putaran. Radar melaporkannya sebagai kegagalan, tidak mengarang hasil.
- **1 pelewatan lalu lolos: `fastlaundry.co.id`.** Di dua putaran pertama `robots.txt`-nya
  tidak bisa diambil dalam batas waktu, jadi radar **menolak menjelajah** — persis yang
  seharusnya dilakukan. Di putaran ketiga berhasil.
- **2 alamat tidak pernah diuji** karena domainnya tidak ditemukan (DNS):
  `sariroselaundry.com` dan `bimbelkiddoszone.com`. Keduanya dibuang sebelum pengujian.
- **Panjang halaman: 199 sampai 17.736 kata.** Tidak ada satu pun halaman yang cukup tipis
  untuk memicu jalur peramban, jadi **rendering tidak terbukti di lapangan hari ini** —
  yang terbukti adalah ia tidak dipakai saat tidak perlu.
- **Harga terbaca di 3 dari 12 situs** (33 angka seluruhnya). Sisanya memang tidak
  memasang harga di halaman.
- **Rating agregat hanya di 1 dari 12 situs** (Hotel Lumasenja 9,9 dari 784 ulasan).
- **Data terstruktur ada di 8 dari 12 situs**, dan sebagian besar hanya `BreadcrumbList`
  atau `ListItem` — bukan harga, bukan rating.

## Tabel hasil (potret terakhir)

| Usaha | Jenis | Status | Kata | Harga | Rating | Data terstruktur |
| --- | --- | --- | ---: | ---: | --- | --- |
| Klinik gigi FDC | harga | 200 | 1.395 | – | – | – |
| Klinik OMDC | harga | 200 | 13.340 | 20 | – | – |
| Bogor Coklat | harga | 200 | 6.467 | – | – | BreadcrumbList, ListItem, Organization |
| Bogor Rain Cake | harga | 200 | 9.053 | – | – | BreadcrumbList, CollectionPage |
| Venus Bakery | harga | 200 | 9.213 | – | – | – |
| Majesty Bakery | harga | 200 | 199 | – | – | – |
| Hotel Lumasenja | reputasi | 200 | 4.715 | – | **9,9 / 784** | Hotel, ItemList, ListItem, WebSite |
| Damessa | layanan | 200 | 17.736 | – | – | BreadcrumbList, ListItem |
| Lapis Bogor | harga | **405** | – | – | – | – |
| Fast Laundry | harga | 200 | 7.832 | – | – | Organization (putaran 3) |
| Okey Wash | harga | 200 | 8.627 | 2 | – | Organization, WebSite |
| Akademi Prestasi | harga | 200 | 15.033 | 3 | – | BreadcrumbList, FAQPage, ImageObject |
| Tutor Indonesia | layanan | 200 | 6.936 | – | – | Article, BreadcrumbList, ImageObject |

Kecepatan: putaran pertama **62 detik** untuk 13 sasaran, putaran berikutnya **32 detik**
untuk 12 (sisa waktu itu jeda sopan per host, bukan kelambatan program).

## Empat temuan yang mengubah produk

Uji ini bukan sekadar laporan — ada empat hal yang langsung diperbaiki karena angka di atas.

### 1. Pencocokan harga berdasarkan nama melahirkan alarm palsu

Putaran kedua melaporkan hal seperti ini:

```
[sedang] Klinik OMDC: Harga Ready To Serve You! tidak lagi tampak di halaman.
[rendah] Klinik OMDC: Harga baru muncul: item baru IDR 1.099.000.
```

Padahal **tidak ada harga yang berubah**. Penyebabnya: harga dicocokkan berdasarkan
keterangannya, sehingga begitu teks keterangan berubah (atau mulai terbaca), barang yang
sama terlihat seperti hilang lalu muncul kembali. Untuk alat pemantau harga, alarm palsu
seperti ini lebih buruk daripada tidak ada laporan sama sekali.

**Perbaikan:** pencocokan berlapis di `diff.py` — (1) nama sama → bandingkan angkanya,
(2) angka sama persis → tidak ada perubahan yang dilaporkan, (3) sisanya baru disebut
hilang atau baru. Putaran ketiga: **nol alarm harga palsu.** Enam uji baru menjaga aturan
ini, termasuk kasus dua layanan berharga sama (Rp 150.000) di mana hanya satu yang berubah.

### 2. Sebagian situs mengganti teksnya di setiap permintaan

Pada dua putaran berurutan, `omdc.co.id` dan `okeywashlaundry.com` punya sidik isi yang
berbeda padahal judul, harga, jumlah kata, tautan, dan judul bagian **semuanya sama**.
Artinya ada teks di halaman itu yang berganti sendiri (penghitung, testimoni bergilir,
atau stempel waktu). Laporan lama menulisnya sebagai temuan bertingkat **rendah** — terbaca
seperti ada sesuatu yang perlu diperiksa, tiap kali, padahal tidak.

**Perbaikan:** catatan itu kini bertingkat **info** dengan kalimat yang menyebut kenyataan:
"Teks halaman berbeda sedikit dari pemeriksaan sebelumnya; harga, judul, dan data
terstruktur tidak berubah." Dan bila ada temuan yang lebih penting, catatan ini dibuang
sama sekali.

### 3. Keterangan harga harus dekat, atau tidak usah sama sekali

Angka pertama dari lapangan memprihatinkan: harga dibaca benar, tetapi keterangannya kosong
(`IDR 649.000` — harga apa?). Perbaikan pertama menambahkan pengambilan teks di sekitar
angka; hasilnya di halaman nyata justru **menyesatkan**: semua harga klinik gigi mendapat
keterangan "Ready To Serve You!" dan "The First Playground in Dental Clinic" — tagline
kepala halaman, bukan nama layanan.

**Perbaikan:** keterangan hanya dipakai bila benar-benar dekat dan berbentuk label —
dipotong pada akhir kalimat (membuang tagline ber-`!`), dibatasi 6 kata/45 aksara, dan
judul bagian hanya dipakai bila muncul tak lebih dari 120 aksara sebelum harganya. Setelah
perbaikan, di halaman nyata: `Harga mulai` (Akademi Prestasi) terbaca benar, sedangkan
halaman yang tidak menaruh label di dekat angkanya menghasilkan **keterangan kosong** —
jujur, tidak menebak.

### 4. Harapan terhadap data terstruktur dan rating perlu diturunkan

Hanya 1 dari 12 situs memasang rating agregat, dan harga dari JSON-LD tidak muncul di
satu pun dari 12 situs ini. Ini menegaskan temuan uji sebelumnya (7 situs, 1 rating):
**pemantauan reputasi lewat situs saja tidak cukup** — jalur resmi Google Places API tetap
jalan utama, dan laporan memang sudah menyiapkan butir ceklisnya.

## Batas pengujian ini (jangan dibaca lebih dari seharusnya)

- **13 situs bukan sampel acak.** Dipilih dari pencarian, bukan diundi; usaha yang tidak
  punya situs (hanya Instagram) tidak bisa diuji sama sekali.
- **Tiga putaran dalam satu hari.** Perubahan harga/rating yang sesungguhnya terjadi
  berminggu-minggu belum pernah ditangkap; yang terbukti hari ini adalah tidak adanya alarm
  palsu dan laporan yang jujur soal penolakan situs.
- **Rendering peramban tidak terpicu** di lapangan. Yang membuktikannya masih uji tersendiri
  (halaman uji ber-JavaScript dan situs tiruan di `radar/tests`).
- **Windows belum diuji.** Seluruh pengujian ini berjalan di Linux; lihat
  `docs/lokaseo/cara-uji-windows.txt` untuk pengujian di komputer pengguna.

## Berkas

- `hasil-20261014.json` — potret terakhir setiap sasaran: status, jumlah kata, harga beserta
  keterangannya, rating, dan data terstruktur. Bisa dibaca dengan editor teks biasa.

Uji ini dijalankan dengan perintah biasa, bukan skrip khusus:

```sh
python3 -m lokaradar add <alamat> --label "Nama" --kind harga
python3 -m lokaradar run --max-pages 14
```
