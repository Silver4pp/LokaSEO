# LokaRadar — radar pemantauan situs publik

## Merender halaman ber-JavaScript tanpa memasang apa pun

Sebagian situs menyusun isinya dengan JavaScript; halaman seperti itu terbaca hampir kosong lewat
permintaan biasa. Radar menanganinya dengan **peramban yang sudah ada di komputer** — Microsoft Edge
di Windows 10/11, Google Chrome, atau Chromium — melalui `lokaradar/peramban.py` yang hanya memakai
pustaka standar. Tidak ada unduhan, tidak ada `pip`, tidak ada perintah yang perlu dihafal:

```sh
python3 -m lokaradar scrape https://situs-klinik.example/ --render selalu
```

Kalau peramban ditaruh di tempat tidak biasa, tunjuk berkasnya:

```sh
LOKARADAR_PERAMBAN="/path/ke/msedge.exe" python3 -m lokaradar run --render auto
```

Yang dijaga modul ini:

- **`robots.txt` diperiksa sebelum peramban dibuka.** Alamat yang dilarang tidak pernah sampai ke
  peramban, bukan sekadar tidak dipakai hasilnya.
- **Gambar, video, dan font diblokir** supaya situs orang tidak diunduh lebih dari perlu; CSS dan
  skrip tetap diambil agar teks dan harga terbaca benar.
- **Identitas jujur**: User-Agent `LokaRadar/0.1`, `Accept-Language: id-ID`, tanpa Referer Google.
  Peramban sungguhan tetap mengirim `sec-ch-ua` dan `Sec-Fetch-*` yang tidak bisa dihapus dari sisi
  ini — sama seperti jalur Scrapling.
- **Tanpa menyentuh peramban pribadi Anda**: profil sementara sendiri (tanpa akun, riwayat, ekstensi,
  atau sinkronisasi), ditutup dan dihapus setelah selesai.
- **Satu peramban per putaran**, bukan satu per halaman: biaya membuka peramban (±1 detik) dibayar
  sekali.

Kalau Scrapling beserta Chromium-nya juga terpasang, jalur Scrapling yang dipakai lebih dahulu;
peramban lokal menjadi cadangan yang membuat radar tetap bisa merender tanpanya.

## Menjalankan dari aplikasi desktop

Radar ini juga dipakai dari dalam aplikasi LokaSEO untuk Windows (`desktop/`), tanpa terminal:
buka halaman **/radar**, tekan “Periksa sekarang”, dan hasilnya muncul di peramban. Jembatannya
ada di `desktop/lokaseo_desktop/radar.py` dengan aturan berikut.

- **Pengaturan usaha mengikuti proyek LokaSEO.** Jenis usaha yang Anda pilih saat membuat proyek
  (dari 13 pilihan yang sama dengan `profil.py`) menjadi ambang rating, data terstruktur yang
  diharapkan, dan kata kunci awal. Radar di aplikasi membaca proyek aktif dari penyimpanan
  peramban, jadi Anda tidak perlu mengatur dua kali.
- **Satu pemeriksaan pada satu waktu**, dijalankan di latar belakang supaya halaman tidak
  menggantung. Menekan “Periksa” saat pemeriksaan lain berjalan dijawab `409`.
- **Batas aman**: badan permintaan 8 KiB, 40 sasaran per putaran, 200 sasaran tersimpan. `/radar`
  tidak memuat skrip sebaris (CSP aplikasi `script-src 'self'`), dan semua POST diperiksa Origin.
- **Tanpa peramban.** Chromium tidak ikut ke dalam `.exe`, sehingga halaman disusun JavaScript
  akan terbaca pendek di aplikasi paket. Rendering penuh tetap perlu menjalankan folder ini dari
  source (`scrapling install`).

Uji jembatan itu ada di `desktop/tests/test_radar.py`, dan contoh tampilan tanpa server di
`desktop/contoh/tampilan-radar.html`.

### Menjalankan rutin dari baris perintah

Radar baru berguna kalau dijalankan rutin. Dua pilihan, tergantung cara Anda memakainya:

- **Dari aplikasi Windows**: halaman `/radar` punya bagian “Pemeriksaan otomatis” yang memasang
  tugas Windows Task Scheduler sendiri (perintah `LokaSEO.exe --radar-periksa`, harian atau
  mingguan, tanpa hak administrator).
- **Dari source**: panggil perintah yang sama seperti biasa, lalu daftarkan ke cron. Jam 07:00
  setiap hari, misalnya:

```sh
0 7 * * * cd /path/ke/loka-seo/radar && LOKARADAR_DATA=~/.local/share/lokaradar \
  python3 -m lokaradar run --report >> ~/.local/share/lokaradar/cron.log 2>&1
```

Sopan santunnya tetap berlaku di jalur otomatis ini: `robots.txt`, jeda per host, dan identitas
jujur. Karena itu **jangan** menjadwalkan lebih sering dari sekali sehari — perubahan harga dan
rating tidak berubah setiap jam, sedangkan beban ke situs orang bertambah setiap kali.


**Radar ini mengamati halaman publik milik pesaing atau mitra Anda, mencatat perubahannya di komputer sendiri, lalu menyusun bahan kerja untuk ruang kerja LokaSEO.** Ada juga **papan reputasi lokal** untuk memantau rating dan jumlah ulasan usaha di sekitar Anda — hanya angka agregatnya, tanpa pernah mengambil isi ulasan atau identitas penulisnya.

Dibangun di atas **[Scrapling](https://github.com/d4vinci/Scrapling)** (BSD), berjalan **lokal**, tanpa akun, tanpa server, dan tanpa mengirim data ke layanan daring. Tidak ada langganan; sesuai keputusan proyek, radar ini gratis.

---

## Untuk apa?

Anda memasukkan alamat halaman publik. Setiap kali radar dijalankan, ia:

1. Mengambil halaman tersebut dengan jeda sopan dan menghormati `robots.txt`.
2. Membaca hal-hal yang biasanya penting bagi pemilik usaha: judul, deskripsi, struktur heading, harga, rating agregat, jumlah ulasan, data terstruktur (`LocalBusiness`, `Product`, …), `noindex`, dan `canonical`.
3. Membandingkannya dengan potret sebelumnya dan menuliskan perubahan yang berarti — misalnya *“Kopi Bogor turun 20% menjadi IDR 120.000”* atau *“Bagian baru di halaman: Layanan Pernikahan”*.
4. Menyusun **laporan Markdown** dan **paket wawasan JSON** berisi usulan ide konten serta butir ceklis yang bisa langsung dipakai di LokaSEO.

Contoh keluaran nyata ada di folder [`contoh/`](contoh/): `laporan-demo.md` dan `wawasan-demo.json`.

## Pemasangan

Butuh Python 3.10 atau lebih baru.

```sh
pip install "scrapling[fetchers]"
```

Uji cepat bahwa mesin pengambil bekerja:

```sh
cd radar
python3 -m lokaradar scrape https://quotes.toscrape.com/
```

Jika Scrapling tidak tersedia, radar tetap berjalan memakai pustaka standar Python (`urllib`), hanya tanpa penyempurnaan header dari Scrapling.

## Mulai cepat

```sh
cd radar

# 1. Tambahkan halaman yang ingin dipantau
python3 -m lokaradar add https://situs-pesaing.example/harga --label "Pesaing Kopi" --kind harga

# 2. Jalankan pemeriksaan
python3 -m lokaradar run

# 3. Lihat apa yang berubah
python3 -m lokaradar changes --since 7d

# 4. Susun laporan + paket wawasan untuk LokaSEO
python3 -m lokaradar report --days 30
```

## Situs yang isinya dibuat JavaScript

Banyak situs zaman sekarang mengirim HTML kosong lalu mengisi isinya lewat
JavaScript. Permintaan HTTP biasa hanya melihat kerangkanya — pada uji Bogor,
`fdcdentalclinic.co.id` hanya terbaca **3 kata**. Radar menangani ini dengan
tiga mode:

| Mode | Perilaku |
| --- | --- |
| `auto` (**bawaan**) | Satu permintaan biasa dulu. Bila hasilnya di bawah 40 kata **dan** terlihat seperti kerangka JavaScript (penanda Next/Nuxt/React/Angular/Svelte, `id="root"`, `window.__`, atau banyak skrip pada halaman besar), halaman diambil **ulang** dengan peramban headless. |
| `selalu` | Langsung peramban, tanpa permintaan biasa. Untuk situs yang Anda tahu serba JavaScript. |
| `tidak` | Tidak pernah membuka peramban. Paling ringan dan paling sopan. |

```sh
python3 -m lokaradar scrape https://contoh.example/ --render auto   # periksa satu halaman
python3 -m lokaradar run --render selalu                            # seluruh putaran berperamban
python3 -m lokaradar --render tidak run                             # putaran paling ringan
python3 -m lokaradar run --tunggu "#daftar-harga"                   # tunggu bagian tertentu muncul
```

**Satu peramban untuk seluruh putaran.** Membuka peramban butuh sekitar satu detik,
jadi `run` memakai satu sesi peramban untuk semua halaman dalam putaran itu
(Scrapling `DynamicSession`), bukan membuka-tutup per halaman. Perintah `status`
menyebut `sesi dipakai ulang` bila ini tersedia.

**`--tunggu SELEKTOR`.** Untuk situs yang memuat harga atau daftar layanan
belakangan, radar bisa menunggu elemen tertentu muncul sebelum halaman diserahkan:

```sh
python3 -m lokaradar scrape https://toko.example/ --tunggu "#tabel-harga"
```

Perlu diketahui: selektor yang salah **tidak** menggagalkan permintaan — peramban
hanya menunggu sampai batas `--timeout` lalu menyerahkan halaman seadanya. Karena
itu radar memeriksa hasilnya sendiri dan memberi tahu:

```text
Catatan       : Selektor tunggu '#tabel-harga' tidak ditemukan setelah halaman
                dirender; peramban menunggu sampai batas waktu dan isi halaman
                bisa belum lengkap.
```

Sekali saja, unduh perambannya (±150 MB, tidak ikut di dalam paket Scrapling):

```sh
scrapling install          # atau: playwright install chromium
python3 -m lokaradar status   # baris "Rendering" menyebut siap / belum terunduh
```

Hasil uji nyata pada situs yang sama di Bogor:

| | Permintaan biasa | `--render auto` |
| --- | --- | --- |
| Kata terbaca | 3 | **537** |
| Judul halaman | — | FDC Dental Clinic |
| Gambar (tanpa alt) | 0 | 244 (1) |

Aturan yang tetap dipegang saat merender:

- **robots.txt dilihat lebih dulu.** Bila alamatnya dilarang, permintaan peramban tidak pernah dikirim — sama seperti permintaan biasa.
- **Jeda per host dihitung dua kali**, sekali untuk tiap permintaan. Merender bukan alasan untuk memborbardir server.
- **Identitas tetap jujur**: User-Agent `LokaRadar/0.1 (+…)`, tanpa referer Google. Bawaan Scrapling yang menyisipkan `Referer: https://www.google.com/` (`google_search=True`) dimatikan.
- **Apa adanya soal sisa jejak**: peramban tetap mengirim header khas peramban (`sec-ch-ua`, `Sec-Fetch-*`, `Accept-Encoding`). Itu tidak bisa dihapus dari sisi kami, dan disebut di sini supaya tidak ada janji yang berlebihan.
- **Halaman pendek yang statis tidak memicu peramban.** Halaman kontak 20 kata tanpa penanda JavaScript tidak perlu dirender; memaksanya hanya membuang waktu dan menambah permintaan ke situs orang.
- **Ganti cara pengambilan tidak dianggap perubahan situs.** Bila cara pengambilan berubah (mis. peramban baru dipasang, atau justru dihapus), isi halaman yang terbaca ikut berubah banyak. Radar tidak melaporkannya sebagai puluhan perubahan palsu: ia menulis satu baris info `Cara pengambilan berubah …` dan memulai pembandingan isi dari potret itu.
- **Kegagalan rendering tidak menggagalkan pemeriksaan.** Halaman hasil permintaan biasa tetap dipakai, dan laporan menuliskan sebabnya (misalnya peramban belum terunduh).
- Rendering **tidak** memakai `StealthyFetcher` dan **tidak** menembus Cloudflare/CAPTCHA. Kalau situs menolak, radar menolak juga.

Bukti lengkap bisa dijalankan sendiri tanpa internet:

```sh
bash contoh/demo-render.sh          # situs lokal ber-JavaScript, 3 mode render
```

Contoh nyata dari uji Bogor — putaran pertama tanpa peramban, putaran kedua dengan
peramban, pada situs yang sama:

```text
$ python3 -m lokaradar --render tidak run
  · FDC Dental: Halaman hampir tanpa teks (3 kata) dan terlihat seperti kerangka JavaScript;
    jalankan dengan `--render selalu` bila peramban sudah terpasang.

$ python3 -m lokaradar --render auto run
Peramban dipakai ulang untuk seluruh putaran ini (satu peluncuran).
  [info] FDC Dental: Cara pengambilan berubah dari permintaan biasa menjadi peramban.
         Isi halaman bisa terbaca berbeda karena itu, bukan karena situsnya berubah —
         pembandingan isi dimulai ulang dari potret ini.
```

### Contoh keluaran

```text
$ python3 -m lokaradar run
Selesai dalam 2.5 detik: 1 diperiksa, 0 gagal, 1 dilewati.
3 perubahan terdeteksi:
  [tinggi] Kopi Bogor (pesaing): Kopi Bogor turun 20.0% menjadi IDR 120.000.
  [sedang] Kopi Bogor (pesaing): Bagian baru di halaman: “Layanan Pernikahan”. Bisa menandakan layanan atau penawaran baru.
  [sedang] Kopi Bogor (pesaing): Jumlah ulasan bertambah 30 (dari 100 menjadi 130).
  ! https://situs-pesaing.example/rahasia: Ditolak robots.txt: robots.txt melarang alamat ini
```

## Kunci utama: jenis usaha dari LokaSEO

Radar mengambil **jenis usaha** dari proyek LokaSEO yang Anda buat di awal. Satu
pilihan itu menentukan banyak hal:

| Yang ditentukan | Contoh untuk jenis “Kafe, kedai kopi, atau tempat makan kecil” |
| --- | --- |
| Data terstruktur yang diperiksa | `CafeOrCoffeeShop`, `Restaurant`, `LocalBusiness` |
| Ambang rating papan reputasi | 4,3 (bisa ditimpa `--min-rating`) |
| Kata kunci awal untuk usulan konten | `kedai kopi`, `menu`, `pesan antar` |
| Catatan jenis usaha di laporan | “Cantumkan jam buka terbaru, menu, dan pilihan pesan antar.” |
| Peran pada laporan | Mana “Situs sendiri”, mana “Pesaing / mitra” |

Dua cara mengisinya:

```sh
# 1. Dari cadangan LokaSEO (paling pas: memakai setelan proyek Anda)
#    Unduh dulu lewat tombol "Unduh cadangan" di LokaSEO, lalu:
python3 -m lokaradar profil --dari ~/Unduhan/lokaseo-cadangan.json

# 2. Diatur langsung di radar
python3 -m lokaradar profil --jenis kafe-kedai --nama "Kebun Kopi Bogor" \
  --kota Bogor --situs kebunkopi.id
```

Perintah `profil` tanpa argumen menampilkan isi profil sekarang, dan tanpa profil
ia menunjukkan daftar jenis usaha yang tersedia. Hasilnya disimpan di
`usaha.json` di folder data radar; lokasinya bisa dipindah dengan `--profil` atau
variabel `LOKARADAR_PROFIL`.

Kalau jenis usaha belum diisi, radar tetap berjalan memakai ambang netral 4,0 dan
tanpa pemeriksaan data terstruktur — tidak menghentikan apa pun.

## Papan reputasi lokal (fase 2)

Selain memantau halaman, radar menyusun **papan reputasi**: peringkat rating dan
jumlah ulasan beberapa usaha lokal sekaligus — usaha Anda sendiri dan pesaing di
sekitar Anda.

```sh
# Usaha sendiri dan dua pesaing, semua lewat halaman publik
python3 -m lokaradar add https://usaha-saya.example/ --label "Usaha Saya" --kind reputasi
python3 -m lokaradar add https://pesaing-a.example/ --label "Pesaing A" --kind reputasi
python3 -m lokaradar add https://pesaing-b.example/ --label "Pesaing B" --kind reputasi

python3 -m lokaradar run
python3 -m lokaradar reputasi --days 30 --min-rating 4.6 --out laporan/
```

Contoh keluaran:

```text
Papan reputasi 30 hari · ambang rating 4.6 · 3 usaha (3 punya rating terbaca)
Rata-rata rating: 4.55 · total ulasan: 690 · ulasan baru: 96

#  Usaha                    Rating  Ulasan  Baru  Laju/minggu  Sumber
1  Kedai Pajajaran          4.65/5  470     60    15.56        halaman
2  Kopi Bogor (usaha saya)  4.61/5  121     25    6.48         halaman
3  Warung Sempurna          4.38/5  99      11    2.85         halaman

Perlu perhatian:
  - Warung Sempurna: rating di bawah ambang, rating menurun
```

Yang dihitung papan:

| Angka | Sumbernya |
| --- | --- |
| Rating dan jumlah ulasan | Angka agregat pada halaman (data terstruktur `aggregateRating`) atau angka resmi Places API. |
| Ulasan baru | Selisih jumlah ulasan antara potret terlama dan terbaru dalam periode. |
| Laju per minggu | Ulasan baru dibagi jumlah hari terukur, dikali tujuh. Butuh minimal dua potret dengan angka. |
| Pangsa ulasan | Bagian ulasan satu usaha terhadap total ulasan semua usaha di papan. |

Tanda perhatian yang muncul: `rating_rendah` (di bawah `--min-rating`), `rating_turun` (turun ≥ 0,1), `ulasan_menurun` (jumlah ulasan berkurang, bisa berarti ulasan dihapus platform), `ulasan_lambat` (laju di bawah 1 ulasan per minggu), `belum_ada_rating`, dan `data_kurang`. Tanda `tempat_resmi` hanya menandai bahwa angkanya berasal dari Places API.

Angka reputasi juga masuk ke laporan dan paket wawasan (`reputasi` + usulan kerja di `lokaseo`), jadi hasilnya bisa langsung dipakai di ruang kerja LokaSEO. Contohnya ada di [`contoh/laporan-reputasi-demo.md`](contoh/laporan-reputasi-demo.md), [`contoh/papan-reputasi-demo.md`](contoh/papan-reputasi-demo.md), dan [`contoh/wawasan-reputasi-demo.json`](contoh/wawasan-reputasi-demo.json).

### Sumber rating: mana yang dipakai?

| Sumber | Cara pakai | Catatan |
| --- | --- | --- |
| Halaman publik (mis. situs usaha, direktori, halaman profil yang memuat `aggregateRating`) | `add <url> --kind reputasi` | Jalur bawaan. Tetap menghormati robots.txt dan jeda sopan. |
| **Google Places API (New)** resmi | `add tempat:<place_id> --kind reputasi`, kunci di `LOKARADAR_PLACES_KEY` | Sesuai ketentuan Google, memakai **kunci dan kuota Anda sendiri**. Yang disimpan hanya `place_id` dan angka agregat. |
| Halaman Google Maps / hasil pencarian Google | **tidak dipakai sebagai jalur bawaan** | `robots.txt` Google melarang jalur peta dan pencarian, dan Ketentuan Layanan Google Maps Platform §3.2.3 melarang menyalin nama usaha, alamat, serta ulasan. Radar yang sopan akan menolak sendiri. |

### Alur memakai Places API

Temuan uji Bogor: **hampir tidak ada usaha lokal yang menulis rating di situsnya
sendiri** (1 dari 7). Jadi untuk jenis usaha yang ratingnya menentukan pembeli —
kafe, restoran, klinik, penginapan, salon — jalur resmi inilah yang masuk akal.

```sh
# 1. Siapkan kunci Places API (New) milik sendiri, lalu setel di sesi terminal
export LOKARADAR_PLACES_KEY="kunci-anda"     # Windows: set LOKARADAR_PLACES_KEY=...

# 2. Cari place_id usaha dan pesaing sekitar
python3 -m lokaradar cari "Klinik Gigi" --kota Bogor

# 3. Tambahkan yang relevan (atau pakai --tambah N pada langkah 2)
python3 -m lokaradar add tempat:ChIJ... --label "Klinik Pesaing" --kind reputasi

# 4. Jalankan pemantauan seperti biasa, lalu lihat papan
python3 -m lokaradar run
python3 -m lokaradar reputasi --days 30
```

Contoh keluaran ada di [`contoh/papan-places-demo.md`](contoh/papan-places-demo.md)
(dijalankan dengan jawaban **tiruan** lewat `contoh/demo-places.sh`, sehingga tidak
memakai kuota siapa pun).

Biaya dan kuota, disebut apa adanya:

- Pencarian (`cari`) memakai SKU **Text Search**; pembacaan detail tempat memakai SKU **Place Details**. Keduanya masuk kuota dan tagihan **proyek Google Cloud milik Anda**, bukan milik proyek ini.
- Satu `cari` = satu permintaan. Satu sasaran `tempat:` yang diperiksa = satu permintaan. Jalankan seperlunya saja; jangan dijadwalkan tiap beberapa menit.
- Yang disimpan hanya `place_id`, nama, alamat, dan angka agregat (rating + jumlah ulasan). Isi ulasan dan identitas penulisnya tidak pernah diambil, sesuai batas penyimpanan Google.
- Radar tidak mengirim kunci ke mana pun selain `places.googleapis.com`, dan tidak menuliskannya ke basis data, laporan, atau catatan. Perintah `status` hanya menyebut "terpasang" atau "belum diatur".

Kunci Places API dibaca dari variabel lingkungan atau argumen `--places-key`, **tidak pernah ditulis** ke basis data, laporan, atau catatan. Kalau sasaran `tempat:` dijalankan tanpa kunci, radar melaporkannya sebagai kegagalan yang jelas, bukan diam-diam melewatinya.

## Daftar perintah

| Perintah | Kegunaan |
| --- | --- |
| `status` | Ringkasan basis data, mesin pengambil, ketersediaan Scrapling, dan kesiapan peramban. |
| `add <url> [--label NAMA] [--kind halaman\|harga\|layanan\|reputasi]` | Menambah sasaran pemantauan. Alamat `tempat:<place_id>` memakai Google Places API. |
| `list` | Daftar sasaran, harga terendah yang terbaca, dan waktu pemeriksaan terakhir. |
| `remove <id-atau-url>` | Menghapus sasaran beserta riwayatnya. |
| `run [--max-pages N] [--target ID] [--report] [--days N] [--out FOLDER]` | Memeriksa sasaran aktif, menyimpan potret, dan menghitung perubahan. |
| `changes [--since 7d\|24h\|30m\|ISO] [--severity …] [--limit N]` | Menampilkan perubahan yang terdeteksi. |
| `profil [--dari CADANGAN.json] [--jenis ID] [--nama …] [--kota …] [--situs …]` | Menampilkan, mengatur, atau mengimpor profil usaha dari cadangan LokaSEO. |
| `reputasi [--days N] [--min-rating X] [--out FOLDER]` | Papan reputasi lokal: peringkat rating, jumlah ulasan, laju ulasan per minggu, dan tanda perhatian. |
| `cari "<kata kunci>" [--kota NAMA] [--max N] [--tambah N]` | Mencari `place_id` di Google Places memakai kunci Anda sendiri. Hasil `--tambah N` langsung dijadikan sasaran. |
| `tempat <place_id>` | Membaca rating agregat satu tempat lewat Google Places API memakai kunci Anda sendiri. |
| `report [--days N] [--out FOLDER]` | Menulis `laporan-<stempel>.md` dan `wawasan-<stempel>.json`. |
| `export <berkas.json>` | Mengekspor perubahan ke JSON untuk diolah sendiri. |
| `export <berkas.json> --sasaran` | Mengekspor **daftar sasaran** agar bisa dipindah ke komputer lain atau dibagikan. |
| `import <berkas> [--dry-run]` | Mengimpor daftar sasaran dari berkas JSON atau teks. Menggabung, tidak pernah menghapus, dan tidak menghubungi situs mana pun. |
| `scrape <url>` | Mengambil satu halaman sekali untuk menguji pembacaan (termasuk hasil rendering). |

Opsi global: `--verbose`, `--timeout DETIK`, `--delay DETIK`, `--render auto\|selalu\|tidak`, `--tunggu SELEKTOR`, `--profil BERKAS`, `--places-key KUNCI`, `--ignore-robots` (tidak disarankan), `--stealthy` (menyamar sebagai peramban; tidak disarankan dan diberi peringatan).

Catatan penulisan argumen: opsi global ditulis **sebelum** subperintah (`python3 -m lokaradar --verbose run`). Pengecualian: `--render` dan `--profil` juga diterima setelah subperintah `run` dan `scrape`, karena keduanya paling sering dipakai di sana.

## Berbagi atau memindahkan daftar sasaran

Daftar sasaran bisa diekspor jadi satu berkas JSON, lalu dibawa ke komputer lain — misalnya dari
laptop kantor ke PC rumah, atau dikirim ke rekan kerja yang juga memakai LokaRadar:

```sh
python3 -m lokaradar export sasaran-radar.json --sasaran   # di komputer asal
python3 -m lokaradar import sasaran-radar.json --dry-run   # periksa dulu, belum menyimpan
python3 -m lokaradar import sasaran-radar.json             # gabungkan ke daftar yang ada
```

Bentuk berkasnya sengaja sederhana dan bisa dibaca mata:

```json
{
  "format": "lokaradar.sasaran.v1",
  "dibuat_pada": "2026-10-14T06:30:00Z",
  "jumlah": 2,
  "sasaran": [
    { "url": "https://pesaing.example/menu", "label": "Pesaing Kopi", "jenis": "harga", "aktif": true }
  ]
}
```

Empat janji yang dijaga uji:

- **Menggabung, bukan mengganti.** Sasaran yang sudah ada tetap ada; yang bertabrakan diperbarui,
  yang baru ditambahkan. Tidak ada penghapusan lewat impor.
- **Tidak menghubungi situs mana pun.** Yang disimpan hanya alamatnya; potret pertama terjadi saat
  pemeriksaan berikutnya. Ini disampaikan di ringkasan impor supaya tidak ada salah paham.
- **Jenis yang tidak dikenal tidak mengganti jenis lama.** Berkas yang hanya memuat alamat
  (mis. daftar teks satu alamat per baris) tidak mengubah label maupun jenis pantauan sasaran lama.
- **Yang ditolak disebut alasannya.** Entri yang bukan alamat http(s), di luar batas 500 entri,
  atau berkas yang bukan daftar sasaran dijawab dengan kalimat yang menjelaskan, bukan diam.

Berkas yang hanya berisi alamat juga diterima — satu alamat per baris, baris `#` dianggap catatan:

```
# daftar pesaing dari rekan kerja
https://pesaing-a.example/
https://pesaing-b.example/harga
```

Batasnya: satu berkas maksimum 1 MB dan 500 entri. Profil usaha ikut tertulis di berkas ekspor
sebagai keterangan, tetapi **tidak** diimpor — jenis usaha selalu diatur pengguna sendiri.

## Hasil kerja dan cara memakainya di LokaSEO

Paket wawasan memakai skema `lokaradar.insight.v1`:

```json
{
  "schema": "lokaradar.insight.v1",
  "ringkasan": { "sasaran": 1, "perubahan": 4, "per_tingkat": { "tinggi": 1 } },
  "sasaran": [
    {
      "label": "Kopi Bogor (pesaing)",
      "judul": "Kopi Bogor — Pesan Online",
      "harga": [{ "amount": 120000.0, "currency": "IDR", "source": "json-ld" }],
      "rating": { "value": 4.5, "count": 130, "scale": 5 },
      "perubahan": [{ "type": "harga_turun", "severity": "tinggi", "message": "…" }]
    }
  ],
  "lokaseo": {
    "ide_konten": [{ "judul": "…", "alasan": "…", "kata_kunci_usulan": ["…"], "sumber": "LokaRadar" }],
    "cek_list": [{ "judul": "…", "keterangan": "…", "prioritas": "tinggi" }],
    "catatan": ["…"]
  }
}
```

Buka berkas `wawasan-*.json` di ruang kerja LokaSEO untuk memindahkan usulan ide konten dan butir ceklisnya. Laporan Markdown bisa dilampirkan ke laporan bulanan.

Jenis perubahan yang dikenali: `harga_turun`, `harga_naik`, `harga_baru`, `harga_hilang`, `rating_berubah`, `jumlah_ulasan_berubah`, `judul_berubah`, `deskripsi_berubah`, `bagian_baru`, `bagian_hilang`, `noindex_aktif`, `canonical_berubah`, `isi_berubah`, `alt_gambar_berkurang`, `viewport_hilang`, `schema_lokal_baru`, dan `pemantauan_dimulai`.

## Hasil uji nyata di Bogor

Uji sekali jalan terhadap tujuh situs usaha Bogor (empat jenis usaha) menghasilkan
temuan yang mengubah radar — catatan lengkapnya di
[`uji-bogor/CATATAN-UJI-BOGOR.md`](uji-bogor/CATATAN-UJI-BOGOR.md):

- Enam dari tujuh situs terbaca; satu menolak dengan HTTP 405 dan dilaporkan apa adanya.
- **Hanya 1 dari 7 yang memuat rating di situsnya.** Jadi memantau reputasi lewat situs sendiri tidak cukup — jalur yang masuk akal adalah Places API resmi atau halaman direktori.
- Satu situs klinik hanya terbaca **3 kata** karena halaman depannya dirender JavaScript. Sejak mode `--render auto` (bawaan), halaman itu dibaca ulang dengan peramban: **537 kata**, judul dan deskripsi terbaca.
- Toko oleh-oleh menyembunyikan harga di keranjang, sehingga harga tidak terbaca.
- Kafe kecil Bogor hampir semuanya hanya punya Instagram: tidak ada situs untuk dipantau.
- Skala rating berbeda (9,9 dari 10 vs 4,5 dari 5), sehingga papan memakai rasio dan menampilkan kolom "Setara / 5".
- Uji ini juga menangkap **bug kejujuran pada radar sendiri**: jalur bawaan ternyata menyamar sebagai Chrome/macOS. Sudah diperbaiki dan dikunci oleh uji.

## Sopan santun, batasan, dan legalitas

- **`robots.txt` dihormati.** Aturan `Disallow` dinilai per alamat yang diminta, bukan per domain. Bila `robots.txt` tidak dapat diambil atau bermasalah, radar **menolak** menjelajah (aman secara bawaan), kecuali Anda memakai `--ignore-robots`.
- **Jeda 2,5 detik per host** secara bawaan, dan `Crawl-delay` dipakai sebagai batas minimum. Maksimal 40 halaman per putaran.
- **Identitas pengambil jujur.** User-Agent menyebut nama LokaRadar beserta alamat proyek. Penyamaran peramban dimatikan dua kali: `impersonate=None` dan `stealthy_headers=False`, sehingga tidak ada header `sec-ch-ua` maupun referer Google. Uji di `tests/test_fetch_identity.py` memastikan itu tidak kembali bocor. Mode menyamar hanya tersedia lewat `--stealthy` dan diberi peringatan saat dipakai.
- **Tanpa login, tanpa cookie, tanpa biaya.** Hanya halaman publik yang boleh dipantau.
- **Hanya angka agregat.** Rating dan jumlah ulasan memang dicatat, tetapi nama, isi, atau identitas penulis ulasan tidak pernah disimpan.
- **Peraturan situs tetap berlaku.** Beberapa situs (antara lain layanan marketplace besar) melarang pengambilan otomatis dalam ketentuan layanan mereka. Memantau halaman publik umumnya dipandang sebagai pelanggaran kontrak, bukan tindak pidana, dan putusan seperti *hiQ v. LinkedIn* serta *Meta v. Bright Data* menguatkan posisi data publik tanpa login. Tetaplah menilai secara wajar: pantau halaman yang memang Anda butuhkan, jangan membebani server orang lain, dan jangan menyimpan data pribadi.
- **Angka bisa berubah kapan saja.** Jadikan laporan sebagai petunjuk, bukan bukti. Verifikasi sebelum mengambil keputusan penting.

## Di mana data disimpan?

Semua ada di komputer Anda:

| Sistem | Lokasi bawaan |
| --- | --- |
| Windows | `%LOCALAPPDATA%\LokaRadar` |
| macOS | `~/Library/Application Support/LokaRadar` |
| Linux | `~/.local/share/LokaRadar` |

Isinya: `radar.sqlite3` (riwayat potret dan perubahan) dan folder `laporan/`. Ubah lokasi dengan `LOKARADAR_DATA`. Potret lama dipangkas otomatis (retensi 180 hari, minimal 3 potret terakhir per sasaran).

Tidak ada proses yang berjalan di latar belakang: radar hanya bekerja saat Anda menjalankannya. Untuk pemeriksaan berkala, jadwalkan sendiri:

**Windows (Task Scheduler)**

```powershell
schtasks /create /tn "LokaRadar harian" /sc daily /st 08:00 ^
  /tr "python -m lokaradar run --report" /rl LIMITED
```

**Linux/macOS (cron)**

```cron
0 8 * * * cd /path/ke/loka-seo/radar && LOKARADAR_DATA=/home/nama/radar python3 -m lokaradar run --report >> radar.log 2>&1
```

## Uji

```sh
cd radar
python3 -m unittest discover -s tests -t .
```

337 uji tanpa jaringan (pengambil, jam, `robots.txt`, Places API, peramban palsu, dan berkas daftar sasaran): aturan `robots.txt`, batas permintaan dan jeda, pembacaan harga/rating/data terstruktur, aturan deteksi perubahan, penyimpanan SQLite, penyusunan laporan, dan antarmuka baris perintah. Satu berkas khusus menjaga agar pemetaan respons Scrapling tidak kembali rusak.

## Uji lapangan

`uji-lapangan/CATATAN-UJI-LAPANGAN.md` memuat hasil menjalankan radar pada **13 halaman usaha
di Bogor** (14 Oktober 2026), lengkap dengan angka apa adanya dan data mentahnya
(`hasil-20261014.json`). Empat temuan dari uji itu langsung mengubah radar: alarm harga palsu
akibat pencocokan berdasarkan keterangan dihilangkan, catatan “isi berubah” diturunkan ke tingkat
info untuk situs yang teksnya berganti sendiri, keterangan harga yang menyesatkan dibatasi hanya
bila benar-benar dekat dengan angkanya, dan harapan terhadap rating/JSON-LD diturunkan.

## Batasan yang jujur

- Rendering peramban memerlukan unduhan peramban sekali (`scrapling install`, ±150 MB). Bila belum ada, radar tetap mengambil halaman dengan permintaan biasa dan mengatakannya apa adanya di laporan — bukan gagal diam-diam.
- Tanpa tembus CAPTCHA, tanpa proxy, tanpa akun. Kalau situs menolak, radar mencatat penolakan itu dan berhenti untuk sasaran tersebut.
- Pencocokan harga memakai pola angka dan data terstruktur; mata uang yang dikenali baru IDR, USD, SGD, MYR, EUR, dan GBP. Situs dengan format harga tidak lazim (misalnya harga tanpa simbol di dalam gambar) bisa terlewat. Periksa `contoh/` untuk melihat bentuk keluarannya.
- Belum ada antarmuka grafis: seluruh alur berjalan lewat baris perintah. Rencana berikutnya menggabungkannya ke aplikasi LokaSEO.
- Sumber Places API sudah diuji dengan pemanggil tiruan, **belum** dengan kunci sungguhan atau kuota nyata. Pesan galat untuk kunci salah, kuota habis (HTTP 429), dan pembatasan kunci sudah disiapkan dan diuji dengan jawaban tiruan.
- Jenis usaha menentukan apakah rating dianggap penting; bila ya dan belum ada sasaran `tempat:`, laporan menambahkan butir ceklis untuk memakai jalur resmi.
- Pengenalan “situs sendiri” memakai nama host: satu host dianggap milik sendiri, termasuk seluruh subdomainnya. Bila Anda memantau halaman pesaing di host yang sama (misalnya direktori pihak ketiga), tandai sendiri di laporan.
- Papan reputasi membaca angka yang dipublikasikan halaman. Kalau halaman menampilkan rating yang sudah dibulatkan atau tertunda, angka radar juga begitu. Angka resmi hanya dari sumber resmi.

## Uji lokal tanpa menyentuh internet

Lima skrip contoh menjalankan radar tanpa menyentuh internet:

- [`contoh/demo-lokal.sh`](contoh/demo-lokal.sh) — menyalakan server contoh di komputer sendiri, mengubah halaman di tengah jalan, lalu memperlihatkan perubahan yang terdeteksi.
- [`contoh/demo-reputasi.sh`](contoh/demo-reputasi.sh) — membangun riwayat 30 hari untuk tiga usaha (simulasi, supaya hasilnya langsung terlihat) lalu menampilkan papan reputasi.
- [`contoh/demo-places.sh`](contoh/demo-places.sh) — memperlihatkan alur Places API lengkap (cari → tambah → pantau → papan) memakai jawaban tiruan, tanpa kunci dan tanpa kuota.
- [`contoh/demo-jenis-usaha.sh`](contoh/demo-jenis-usaha.sh) — mengimpor cadangan LokaSEO, lalu memperlihatkan bagaimana jenis usaha menentukan ambang rating, pemeriksaan data terstruktur, dan pemisahan situs sendiri dari pesaing.
- [`contoh/demo-render.sh`](contoh/demo-render.sh) — menyiapkan situs lokal yang isinya dibuat JavaScript, lalu memperlihatkan tiga mode render dan apa yang berubah pada laporan.

Contoh keluaran lengkap ada di [`contoh/`](contoh/): `laporan-jenis-usaha-demo.md`, `laporan-reputasi-demo.md`, `papan-reputasi-demo.md`, `laporan-render-demo.md` (halaman ber-JavaScript), `laporan-places-demo.md`, `papan-places-demo.md`, beserta berkas `wawasan-*.json` pasangannya.

---

LokaRadar bagian dari [LokaSEO](../README.md). Kode dasar proyek berasal dari [OpenSEO](../ASAL-PROYEK.md) (MIT); mesin pengambil halaman memakai [Scrapling](https://github.com/d4vinci/Scrapling) (BSD-3-Clause). Mesin pengambil pihak ketiga tidak ikut dibundel di repositori ini; pemasangan dilakukan lewat `pip`.
