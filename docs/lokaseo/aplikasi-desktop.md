# Aplikasi Windows LokaSEO (antarmuka di peramban)

LokaSEO dapat dibungkus menjadi **satu berkas `.exe`**: dijalankan sekali, lalu
antarmukanya terbuka sebagai tab di peramban bawaan Anda. Tidak ada jendela aplikasi,
tidak ada akun, tidak ada server bersama, dan tidak ada pengiriman data ke layanan
kami. Tidak ada layanan daring milik proyek ini.

Alasannya sederhana: peramban sudah ada di setiap komputer Windows, tampilannya sudah
dikenal pengguna, dan Anda bisa memakai fitur peramban yang biasa — tab, bookmark,
zoom, pencarian di halaman — tanpa aplikasi tambahan.

Sasaran paket untuk saat ini **hanya Windows**. Kode servernya sendiri lintas sistem,
jadi pengguna Linux atau macOS tetap dapat menjalankannya dari source seperti dijelaskan
di bagian akhir dokumen ini.

## Janji "tanpa layanan daring"

| Aspek               | Cara LokaSEO memenuhinya                                                                                                                |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Pengikatan jaringan | Server hanya mendengarkan `127.0.0.1`. Perangkat lain di jaringan yang sama tidak dapat membukanya.                                     |
| Konten ke luar      | Antarmuka tidak memuat font eksternal, analytics, CDN, maupun gambar jarak jauh. Penjagaannya otomatis: `desktop/tests/test_bundle.py`. |
| Kebijakan konten    | `connect-src 'self'` — halaman hanya boleh menghubungi server lokal itu sendiri.                                                        |
| Telemetri           | Tidak ada. Tidak ada pelaporan pemakaian, pembaruan otomatis, atau pemeriksaan versi.                                                   |
| Data pengguna       | Tersimpan di komputer Anda. Tidak ada unggahan ke mana pun.                                                                             |
| AI                  | Nonaktif sampai Anda menekan tombol dan memberi API key sendiri. Key hanya berada di memori sesi dan hilang saat dimuat ulang.          |

### Yang perlu diketahui jujur

- **AI tetap memanggil penyedianya.** Bila Anda memakai fitur AI, prompt dan key
  dikirim langsung dari komputer Anda ke penyedia yang Anda pilih (OpenAI, OpenRouter,
  DeepSeek, atau Groq). Tidak ada server perantara dari proyek ini.
- **Mode luring penuh.** Jalankan dengan `--offline` untuk mematikan seluruh panggilan
  AI; endpoint AI menjawab dengan hasil kosong agar Anda dapat bekerja manual.
- **Bukan sandbox keamanan.** Program lokal lain milik Anda tetap dapat memanggil API
  di port loopback. Yang terlindungi: halaman web lain ditolak lewat Origin dan
  `Sec-Fetch-Site`, dan tanpa header CORS mereka tidak bisa membaca balasan.
- **Tanpa hak administrator.** Manifest aplikasi memakai `asInvoker`, jadi tidak ada
  permintaan elevasi saat dijalankan.

## Radar pemantauan situs di dalam aplikasi

Radar (folder `radar/`, lihat [`radar/README.md`](../../radar/README.md)) dibundel ke dalam
`.exe`. Pengguna tidak perlu membuka terminal: cukup satu halaman di peramban.

| Hal                | Keterangan                                                                                                                                                     |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Halaman            | `http://127.0.0.1:<port>/radar`, ditautkan dari beranda aplikasi. Tombol: periksa sekarang, muat ulang, lihat laporan, tambah dan hapus sasaran.              |
| Pengaturan usaha   | Dibaca dari proyek aktif LokaSEO di penyimpanan peramban (`lokaseo.workspace.v1`) lewat `POST /api/radar/profil`, sehingga jenis usaha yang dipilih di awal proyek otomatis memakai ambang rating, data terstruktur, dan kata kunci yang sama. Ada isian manual sebagai cadangan. |
| Data               | `%APPDATA%\LokaSEO\radar` (Windows). Dapat dipindah lewat `LOKARADAR_DATA`. Isinya: `radar.sqlite3`, potret, perubahan, dan laporan Markdown.               |
| Batas              | Badan permintaan 8 KiB, 40 sasaran diperiksa per putaran, 200 sasaran tersimpan. Pemeriksaan berjalan satu per satu di latar belakang.                        |
| Jalur baca         | `GET /api/radar/info`, `/sasaran`, `/perubahan`, `/papan`, `/laporan`, `/jenis`, `/profil`                                                                     |
| Jalur ubah         | `POST /api/radar/periksa`, `/tambah`, `/hapus`, `/profil` — semuanya melewati pemeriksaan Origin seperti endpoint lain.                                        |
| Mode luring        | `--offline` menolak pemeriksaan (`409`). Radar mengatakannya, bukan gagal diam-diam.                                                                           |
| Peramban           | `GET /api/radar/peramban` (keadaan, `?ulang=1` untuk mencari ulang) dan `POST /api/radar/peramban` (uji; kirim `jalur` untuk menunjuk sendiri berkasnya).       |

### Bila peramban tidak ditemukan

Kartu **“Peramban untuk halaman ber-JavaScript”** tidak pernah membiarkan tombol
“Uji rendering” pudar tanpa keterangan. Bila tidak ada peramban yang bisa dipakai,
kartu menulis alasannya (berapa lokasi yang sudah diperiksa, atau peramban
ditemukan tetapi tidak dikenali), menyediakan tombol “Periksa ulang”, daftar
“Yang sudah dicari” berisi jalur yang diperiksa berikut alasannya, dan satu kolom
untuk menunjuk sendiri berkas peramban — diuji dulu, baru disimpan. Alasan yang
sama masuk ke laporan kesiapan, jadi satu tempelan cukup untuk menelusuri masalah.
Peramban dicari di jalur pemasangan lazim, registry Windows (`App Paths`), `PATH`,
lalu variabel `LOKARADAR_PERAMBAN` atau pilihan yang disimpan di folder data radar.
**Di Windows nomor versinya dibaca dari berkasnya** (sumber daya versi PE, lalu
folder samping bernama nomor versi), bukan dengan menjalankan `chrome.exe --version`:
Chrome dan Edge di Windows adalah aplikasi GUI yang tidak menulis ke pipa (crbug
158372) dan malah bisa membuka jendela peramban. Pencarian peramban karena itu
tidak pernah menjalankan apa pun; bukti sesungguhnya ada di tombol “Uji rendering”,
yang benar-benar membuka peramban headless dan merender satu halaman.

### Pemeriksaan otomatis harian

Radar berguna kalau berjalan rutin, jadi aplikasi bisa memasang sendiri satu tugas Windows:

| Hal              | Keterangan                                                                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Perintah         | `LokaSEO.exe --radar-periksa` — periksa sekali lalu keluar. Tidak membuka peramban, tidak menyalakan server, tidak memasang ikon tray.                   |
| Di mana          | Tugas Windows bernama **LokaSEO - Radar harian**, dibuat lewat `schtasks` untuk pengguna yang sedang masuk. Tanpa hak administrator.                     |
| Pilihan          | Setiap hari atau setiap minggu, pada jam pilihan pengguna. **Tidak ada pilihan per jam**: radar memeriksa situs orang lain, dan beban itu tidak diminta. |
| Bukti            | Tombol “Jalankan tugasnya sekarang” memeriksa rangkaiannya lewat `schtasks /Run`, bukan hanya mempercayai pendaftarannya.                                |
| Jalur API        | `GET /api/radar/jadwal` (keadaan), `POST /api/radar/jadwal` dengan `aksi`: `aktifkan`, `matikan`, atau `jalankan`.                                     |
| Mode luring      | `--offline` menolak memasang jadwal (409) karena pemeriksaan butuh jaringan.                                                                            |
| Di luar Windows  | Halaman radar menjawab terus terang dan menampilkan baris cron yang bisa disalin.                                                                        |
| Batas jujur      | Bila komputer mati atau tidur pada jam itu, pemeriksaan terlewat dan tidak menyusul sendiri.                                                            |

Catatan operasional: bila Anda memindahkan folder data radar lewat `LOKARADAR_DATA`, setel variabel itu
sebagai variabel lingkungan pengguna juga — kalau tidak, tugas terjadwal akan memakai folder bawaan
`%APPDATA%\LokaSEO\radar`. Pemeriksaan terjadwal dan pemeriksaan manual bisa bentrok pada jam yang sama;
yang kalah akan melaporkan galat basis data apa adanya, bukan gagal diam-diam.

### Paket rilis Windows

Ada dua bentuk yang dibagikan:

| Paket | Isi | Untuk siapa |
| --- | --- | --- |
| `LokaSEO-Windows.zip` | `LokaSEO-console.exe` (16,7 MB) + panduan teks | Pengguna akhir: ekstrak, klik dua kali, peramban terbuka. Tanpa pemasangan apa pun. |
| `LokaSEO-source.zip` / `LokaSEO-untuk-Windows.zip` | Seluruh kode sumber, antarmuka yang sudah dibangun, skrip build | Mereka yang ingin menjalankan dari sumber, memeriksa kode, atau membangun ulang `.exe`. |

`LokaSEO-console.exe` dibangun dengan Python 3.12.8 dan PyInstaller 6.22.3 untuk Windows x86-64, dengan ikon tray di dalamnya. Karena berkasnya tidak ditandatangani secara digital, Windows SmartScreen bisa menampilkan peringatan saat pertama dibuka ("More info" lalu "Run anyway"); sebagian antivirus juga bisa menandai berkas `.exe` buatan PyInstaller — jalur sumber selalu tersedia sebagai alternatif.

### Memeriksa kesiapan aplikasi di komputer pengguna

Satu hal tidak bisa diuji dari jauh: apakah paket ini berjalan benar di Windows milik pengguna. Karena
itu ada tombol **Periksa kesiapan** di halaman radar dan mode `--kesiapan` di baris perintah.

| Hal            | Keterangan                                                                                                                                                     |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Butir          | 11 pemeriksaan sungguhan: versi aplikasi (dan apakah jalan dari paket `.exe`), sistem, jam, folder data (uji tulis + sisa ruang), berkas log, modul radar, jumlah sasaran/potret/perubahan, peramban + versinya, keadaan penjadwal, pemeriksaan terakhir, dan kunci Places (tanpa isi kuncinya). |
| Keluaran       | Laporan teks polos di kotak yang bisa disalin (tombol **Salin laporan**), plus `/api/kesiapan` untuk mesin.                                                       |
| Aman dikirim   | Tidak memuat kunci API, isi halaman, maupun daftar alamat yang dipantau — hanya angka dan keadaan. Tidak ada data yang dikirim ke mana pun secara otomatis.      |
| Saat radar mati | Rute `/api/kesiapan` sengaja tetap hidup: justru ketika modul radar gagal dimuat, laporan inilah yang dibutuhkan. Satu butir yang meledak menjadi bertanda [GAGAL], bukan menggagalkan seluruh laporan. |
| Tanpa antarmuka | `LokaSEO-console.exe --kesiapan` mencetak laporan dan menyimpannya sebagai `laporan-kesiapan.txt` di folder data.                                                |
| Sekalian panduan | `docs/lokaseo/cara-uji-windows.txt` — 10 langkah uji 15 menit di Windows, dengan hasil yang seharusnya terlihat di setiap langkah.                                    |

### Memindahkan, mencadangkan, dan berbagi daftar sasaran

| Hal                | Keterangan                                                                                                                                                                                              |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unduh              | Tombol **Unduh daftar sasaran** di kartu “Sasaran yang dipantau”. Berkasnya JSON (`lokaradar.sasaran.v1`, nama `sasaran-radar-TANGGAL.json`) berisi alamat, nama singkat, jenis pantauan, dan keadaan aktifnya. |
| Impor              | Tombol **Impor daftar sasaran** menerima berkas JSON itu, atau berkas teks biasa berisi satu alamat per baris (`#` sebagai catatan). Rute: `POST /api/radar/sasaran/impor`.                                |
| Sifat impor        | **Menggabung**: tidak menghapus sasaran mana pun, memperbarui yang bertabrakan, menambah yang baru. Tidak ada tombol “ganti seluruh daftar” — penghapusan harus disengaja lewat tombol Hapus.            |
| Tanpa jaringan     | Impor tidak menghubungi situs mana pun; hanya menyimpan alamat. Ringkasan impor mengatakannya sendiri supaya tidak disalahpahami sebagai “sudah diperiksa”.                                             |
| Batas              | 1 MB per berkas, 500 entri per berkas, dan tetap tunduk pada batas `RADAR_MAX_TARGETS` (200 sasaran) milik aplikasi — kelebihannya dilaporkan sebagai “tertunda”, bukan dibuang diam-diam.                 |
| Isi yang ditolak   | Dijawab dengan alasan: berkas bukan daftar sasaran, JSON rusak, berkas kosong, alamat bukan http(s), entri ganda, dan jenis pantauan tak dikenal (dipakai “halaman” sambil dicatat).                       |
| Profil usaha       | Tertulis di berkas ekspor sebagai keterangan (agar penerima tahu daftar itu disusun untuk usaha apa), tetapi tidak diimpor. Jenis usaha selalu diatur pengguna sendiri.                                   |

### Halaman ber-JavaScript: memakai peramban yang sudah ada

Situs yang isinya disusun JavaScript terbaca kosong bila diambil dengan permintaan biasa. Aplikasi
ini mengatasinya **tanpa mengunduh apa pun**: ia memakai peramban yang sudah terpasang di
komputer pengguna — Microsoft Edge di Windows 10/11, Chrome, atau Chromium — dan berbicara
langsung dengan protokol perambannya (Chrome DevTools Protocol) memakai pustaka standar Python
(`radar/lokaradar/peramban.py`).

| Hal               | Keterangan                                                                                                                                        |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Yang dibutuhkan   | Peramban yang sudah terpasang. Di Windows, Edge sudah ada sejak awal. Bila peramban ditaruh di tempat lain, setel `LOKARADAR_PERAMBAN` ke berkasnya. |
| Mode render       | Otomatis `auto` bila peramban ditemukan: halaman yang tipis dan tampak disusun JavaScript diambil ulang dengan peramban. Bila tidak ada peramban, `tidak`. |
| Uji di antarmuka  | Tombol **Uji rendering** membuka satu peramban untuk halaman uji milik radar sendiri (`data:` bawaan) dan melaporkan hasilnya. Tidak menghubungi situs siapa pun. Jalur ini dijaga uji peramban `tests/lokaseo/browser/peramban-ui.mjs` (`pnpm test:loka:peramban`), yang menjalankan aplikasi lalu menekan tombolnya sungguhan. |
| Sopan santun      | `robots.txt` tetap diperiksa **sebelum** peramban dibuka, jeda per host tetap dihitung, dan gambar/media/font diblokir supaya situs orang tidak dibebani. |
| Identitas         | User-Agent `LokaRadar/0.1`, `Accept-Language` bahasa Indonesia, tanpa Referer Google. Peramban tetap menambah header khasnya (`sec-ch-ua`, `Sec-Fetch-*`) — disebut apa adanya. |
| Jejak di komputer | Peramban dijalankan dengan profil sementara sendiri: tanpa akun, riwayat, ekstensi, atau sinkronisasi milik pengguna, dan foldernya dihapus setelah selesai. |
| Batas             | Situs yang menolak peramban (mis. memblokir Chromium headless) tetap gagal — kegagalannya dicatat apa adanya, bukan disamarkan dengan mode menyamar. |

Berkas yang tidak bisa dijalankan tidak dianggap siap: Chromium yang kehilangan pustaka sistem pernah
membuat aplikasi mengaku "peramban siap" lalu gagal di setiap rendering, jadi setiap kandidat diuji
`--version` lebih dahulu dan hasilnya harus benar-benar terbaca sebagai nomor versi.

### Yang tidak dibundel, dan alasannya

Peramban Chromium (±150 MB) tidak ikut ke dalam `.exe`; mengunduhnya untuk setiap pengguna
tidak masuk akal untuk satu berkas yang harus bisa dikirim lewat surel. Akibatnya, di dalam
aplikasi paket radar mengambil halaman dengan pustaka standar saja:

- `GET /api/radar/info` melaporkan `"peramban": "belum terunduh"`, sehingga halaman radar dan
  laporan berkata terus terang alih-alih menjanjikan rendering yang tidak ada.
- Halaman yang isinya disusun JavaScript akan terbaca pendek; radar menandainya sebagai catatan
  (“Halaman ini pendek …”), bukan menganggapnya situs kosong.
- Untuk rendering sungguhan, jalankan `radar/` dari source dengan Scrapling dan Chromium
  terpasang (`scrapling install`), lalu pakai `--render auto` atau `selalu`.

Dua jebakan PyInstaller yang sudah ditutup dan perlu diingat bila `lokaseo.spec` diubah lagi:

1. `radar/` **wajib** ada di `pathex` saat analisis. Tanpa itu PyInstaller tidak menelusuri modul
   `lokaradar`, `html.parser` tidak ikut terbundel, dan aplikasi hasil bundel gagal saat dibuka
   dengan `ModuleNotFoundError`.
2. Ketergantungan Scrapling/Playwright ada di daftar `excludes`. Bila dikeluarkan dari daftar itu,
   berkas membengkak dari 32 MB menjadi 100 MB lebih tanpa membuat rendering bisa dipakai.

## Pakai versi siap pakai

1. Unduh `LokaSEO-Windows.zip` dari artefak GitHub Actions (tab **Actions** → alur
   **LokaSEO desktop (Windows)** → unduh artefak), lalu ekstrak.
2. Klik dua kali `LokaSEO.exe`.
3. Tutup jendela untuk keluar; tidak ada proses yang tertinggal.

Bila jendela tidak terbuka, jalankan `LokaSEO-console.exe`. Versi ini menampilkan
informasi di jendela konsol, termasuk pesan galat. Aplikasi memakai mesin web
Microsoft Edge WebView2 — sudah tersedia di Windows 10 versi 21H2 ke atas dan
Windows 11; bila belum ada, pasang _Microsoft Edge WebView2 Runtime_ (gratis, dari
Microsoft). Tanpa WebView2, jalankan:

```bat
LokaSEO-console.exe --window browser
```

**Catatan SmartScreen.** Berkas ini belum ditandatangani secara digital, sehingga
Windows dapat menampilkan peringatan saat pertama dijalankan (pilih _More info_ →
_Run anyway_). Untuk menghilangkannya diperlukan sertifikat penandatanganan kode
berbayar — hal ini wajar untuk proyek gratis tanpa penerbitan resmi.

## Menjalankan dari source

Di Windows, cara tercepat:

```bat
desktop\dist\LokaSEO-console.exe
```

Skrip itu memeriksa Python, membangun antarmuka bila belum ada, lalu menjalankan
aplikasi. Atau secara manual:

```bat
pnpm install --frozen-lockfile
pnpm build:loka
python desktop\run.py
```

Pilihan lain:

| Perintah                                 | Kegunaan                                 |
| ---------------------------------------- | ---------------------------------------- |
| `python desktop\run.py --offline`        | Matikan seluruh panggilan AI             |
| `python desktop\run.py --port 3000`      | Pakai port tetap                         |
| `python desktop\run.py --window browser` | Buka di peramban, bukan jendela aplikasi |
| `python desktop\run.py --no-open`        | Hanya jalankan server lokal              |
| `python desktop\run.py --verbose`        | Tampilkan catatan rinci                  |

## Membangun `.exe`

Sekali perintah di Windows:

```powershell
powershell -ExecutionPolicy Bypass -File desktop\alat\build-windows.ps1
```

Pilihan: `-SkipFrontend` (pakai `loka-release` yang ada), `-NoWebview` (hanya versi
konsol), `-SkipTests`.

Hasil:

| Berkas                                | Keterangan                                                              |
| ------------------------------------- | ----------------------------------------------------------------------- |
| `desktop\dist\LokaSEO.exe`            | Aplikasi berjendela (butuh `pywebview` saat build)                      |
| `desktop\dist\LokaSEO-console.exe`    | Versi konsol untuk menelusuri masalah                                   |
| `desktop\release\LokaSEO-Windows.zip` | Paket siap dibagikan berisi `.exe`, `LICENSE.txt`, dan `CARA-PAKAI.txt` |

Biner harus dibangun di sistem tujuannya; PyInstaller tidak menautkan silang. Untuk
mendapatkan `.exe` tanpa komputer Windows, jalankan alur
`.github/workflows/loka-desktop.yml` di GitHub Actions (runner `windows-latest`).
Alur itu juga menguji `.exe` hasil build: menjalankannya dalam mode luring, memeriksa
halaman utama, header keamanan, penolakan Host asing, dan memastikan mode luring tidak
memanggil penyedia.

## Lokasi data di Windows

| Isi              | Lokasi                                                            |
| ---------------- | ----------------------------------------------------------------- |
| Catatan aplikasi | `%APPDATA%\LokaSEO\lokaseo.log`                                   |
| Data proyek SEO  | Penyimpanan antarmuka LokaSEO (ikuti menu Laporan untuk cadangan) |

Catatan aplikasi tidak memuat isi prompt maupun API key — hal ini diperiksa otomatis
oleh `desktop/tests/test_bundle_run.py`. Ganti lokasi data dengan `LOKA_DATA_DIR`, atau
arahkan berkas antarmuka dengan `LOKA_STATIC_ROOT`.

## Pengujian

```sh
python3 -m unittest discover -s desktop/tests -t desktop -v
```

61 uji mencakup: validasi permintaan, urutan cadangan penyedia, kode galat, pencatatan
token, penolakan Host/Origin, batas ukuran dan tenggat body, penolakan berkas
tersembunyi dan tautan simbolik, mode luring, penjagaan "tanpa layanan daring" atas
build, berkas paket Windows (manifest, versi, ikon), **halaman dan endpoint penghentian**
(termasuk penolakan permintaan lintas situs), dan **pengujian biner hasil build** yang
menjalankan `.exe`/biner konsol sungguhan lalu memeriksa halaman utama, ikon, penolakan
Host asing, mode luring, dan kebersihan catatan dari API key.

Seluruh tes browser LokaSEO yang sudah ada juga dijalankan terhadap server Python ini
tanpa perubahan, karena pengujiannya lewat HTTP:

```sh
pnpm build:loka
node tests/lokaseo/browser/smoke.mjs          # juga: polish, responsive, beginner, ai
node tests/lokaseo/security/regression-browser.mjs
```

## Linux dan macOS (dari source)

Kode servernya lintas sistem. Dari source, langkahnya sama seperti Windows:

```sh
pnpm install --frozen-lockfile && pnpm build:loka && python3 desktop/run.py
```

Jendela asli memerlukan `pywebview` dan GTK/Qt di Linux; tanpa itu aplikasi memakai
peramban bawaan. Paket untuk kedua sistem ini belum dibuat dan belum disiapkan di
alur otomasi.

## Batas yang belum diuji

- `.exe` Windows belum dibangun di lingkungan kerja ini (mesin pengembangan Linux).
  Yang sudah diuji di sini: seluruh unit test, dan biner Linux hasil PyInstaller.
- Jendela asli melalui `pywebview` belum diuji karena paketnya hanya dipasang di
  Windows pada alur otomasi. Bawaan LokaSEO memakai peramban, jadi hal ini tidak
  memengaruhi pemakaian normal.
- Panggilan ke penyedia AI nyata dengan API key sungguhan belum diuji; pengujian
  memakai penyedia tiruan.
- Pemeriksaan keamanan mengikuti hasil audit `docs/lokaseo/security-audit.md`;
  jalur backend Cloudflare penuh tetap belum diverifikasi.
