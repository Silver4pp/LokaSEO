# 16 Oktober 2026 — Penataan skrip: satu folder untuk alat pembangun, tanpa berkas .bat

Empat alat pembangun sebelumnya tersebar: dua di `desktop/`, satu di `scripts/`, dan satu lagi berupa pintasan `.bat`. Sekarang mereka berada di satu folder bernama `desktop/alat/`, dan pintasannya dihapus — yang dibagikan ke pengguna adalah `.exe`, bukan skrip.

- **`desktop/alat/` berisi empat alat pembangun**: `lokaseo.spec` (PyInstaller), `version_info.txt` (sumber daya versi Windows), `build-windows.ps1` (satu perintah: bangun antarmuka, uji, bikin `.exe`, kemas zip), dan `buat-paket-rilis.py` (tiga zip bernama tetap) yang sebelumnya terasing di `scripts/`. Dengan ini `desktop/lokaseo_desktop/` hanya berisi kode aplikasi, bukan alat yang membangunnya.
- **`desktop/run-windows.bat` dihapus.** Ia menjalankan aplikasi dari source lewat Python — jalan yang kalah cepat oleh `.exe`, dan menambah satu berkas lagi yang harus dijelaskan kepada pengguna awam. Tidak ada lagi berkas `.bat` di repositori.
- **Dua panduan pengguna akhir pindah ke `docs/lokaseo/`**: `cara-pakai-desktop.txt` dan `cara-uji-windows.txt`, sejajar dengan dokumen produk lain di folder itu. `build-windows.ps1` tetap menyalinnya ke dalam paket dengan nama yang sudah dikenal pengguna (`CARA-PAKAI.txt`).
- **`radar/uji-bogor/radar.sqlite3` dihapus** — basis data hasil uji, bukan bagian aplikasi. Catatan dan laporan uji lapangannya tetap ada karena dirujuk dokumentasi.
- **Kerusakan yang saya buat sendiri dan tidak langsung terlihat**: penyuntingan jalur massal mengubah langkah 3 di `MULAI-DI-WINDOWS.txt` menjadi "klik dua kali `LokaSEO-console.exe`", padahal berkas itu adalah panduan jalur sumber, yang justru tidak berisi `.exe`. Dikembalikan ke `desktop\run.py`. Jalur `build-windows.ps1` di `README.md` dan `aplikasi-desktop.md` meleset pada sapuan yang sama.
- **`.github/workflows/loka-desktop.yml` ikut diperbarui.** Ia memanggil `desktop/lokaseo.spec` dan menyalin `desktop/CARA-PAKAI.txt` — dua jalur yang baru saja dipindah. Tanpa perubahan ini CI akan gagal pada komit pertama setelah penataan.
- **Uji biner hasil build memilih kandidat sesuai sistem.** `setUpClass` dulu mencoba dua nama (`LokaSEO-console` dan `LokaSEO-console.exe`); setelah build lintas platform, `.exe` Windows ada di `desktop/dist/` dan Linux mencoba menjalankannya — lalu gagal. Nama kandidat kini dipilih dari `sys.platform`.

`.exe` dibangun ulang dari struktur yang baru dan diuji di dalam Wine: laporan kesiapan lulus (8 lulus, 3 perhatian, 0 gagal), halaman radar menampilkan perubahan nyata dari dua sasaran, tanpa galat JavaScript. Tiga zip rilis dibuat ulang dengan nama yang sama.

# 16 Oktober 2026 — Kode dirapikan: tidak ada lagi bentuk data yang disusun dua kali

Fitur ringkasan kemarin menyisakan beberapa kebiasaan buruk yang membuat kode tampak lebih rumit dari yang seharusnya. Tidak ada perilaku yang berubah — semua uji lama tetap lulus tanpa disentuh.

- **`radar.jadwal()` tidak lagi menyusun kamus milik modul lain.** Bila penjadwal menolak dibaca, ia dulu membangun ulang seluruh bentuk data `status()` dan memanggil fungsi privat `_jadwal._teks_perintah()` untuk mengisinya. Sekarang ada `jadwal.tak_terbaca(alasan)` di sebelah `status()`, dan keduanya memakai satu kerangka bersama (`_kerangka()`). Kalau bentuknya berubah, cukup di satu tempat. Fungsinya turun dari 25 baris menjadi 16, dan yang memanggilnya tinggal lima baris.
- **`bikin()` dipecah menjadi empat langkah bernama** (`_rekap_potret`, `_kelompokkan`, `_urutkan`, `_tanpa_perubahan`); dari 90 baris menjadi 36. Yang paling terasa: perhitungan "kapan pertama dan terakhir kali" dulu diulang di dua cabang, sekarang cukup mengurutkan kumpulan stempelnya.
- **Konsep yang ditulis dua kali dihapus.** Ada `PANGKAT_TINGKAT` dan `_pangkat()` untuk urutan tingkat yang sama — yang pertama tidak dipakai siapa pun. Ada kunci `"informasi"` di `LABEL_TINGKAT` padahal tingkatnya bernama `"info"`. Keduanya dibuang.
- **`kelompok` dikeluarkan dari balasan API.** Sama seperti `terbaru` kemarin: tidak ada yang membacanya, dan contoh statis mengirim `[]` padahal `penting` berisi tiga butir — kombinasi yang membingungkan siapa pun yang membaca contohnya.
- **Dua fungsi kembar di antarmuka jadi satu.** `butirPerubahan` dan `butirRingkas` nyaris identik; kini satu fungsi dengan hitungan opsional. Rantai `tingkat === "tinggi" ? ... : tingkat === "sedang" ? ...` yang ditulis ulang di dua tempat jadi `kelasTingkat()`. Dua blok "sebut nama sasaran" jadi satu `sebutSasaran()`, dan dua blok `<ul>` jadi `daftarSorot()`.
- **Pembatasan `hari` yang diulang tiga kali dikurangi.** Endpoint memanggil `max(1, _batas(...))` padahal `_batas()` sudah menjamin minimal 1, dan `bikin()` membatasinya lagi.
- **Satu aturan CSS mati dibuang** (`.sorot .kapan`, kelasnya tidak pernah dipakai).

Satu kesalahan saya sendiri ikut tercatat: waktu merapikan, `kepala` dihapus tetapi dua baris pemakainya tertinggal. `node --check` lolos dan 217 uji Python lolos — yang menemukannya justru uji peramban, karena galat itu hanya muncul ketika halamannya benar-benar dibuka.

Uji radar **361**, uji desktop **217**, sembilan uji peramban: semuanya lolos.

---

# 15 Oktober 2026 — Dua kerusakan yang hanya muncul pada `.exe` sungguhan, dan `.exe` 0.1.19 dibangun ulang

Ringkasan pemantauan selesai, lalu diuji dari dalam berkas `.exe` yang dibangun di Wine — bukan hanya dari kode sumber. Dua kerusakan muncul hanya di situ, dan keduanya juga bisa menimpa pemakaian nyata.

- **Penjadwal Windows yang menolak dibaca menjawab 500.** Bila `schtasks /Query /XML` mengembalikan sesuatu yang bukan XML — kebijakan perusahaan, Windows berbahasa lain, penjadwal yang tidak tersedia — `jadwal.status()` melempar `JadwalError`, dan galat itu tidak ditangani endpointnya. Laporan kesiapan menangani keadaan ini dengan rapi, tetapi endpointnya tidak: satu permintaan berubah menjadi `500 Internal Server Error`.
- **Satu permintaan yang gagal mengosongkan seluruh halaman radar.** Antarmuka merantai enam permintaan di dalam satu blok `try`. Karena penjadwal gagal lebih dulu, daftar sasaran, ringkasan, dan perubahan tidak pernah digambar — halaman tampak kosong dengan satu pesan galat, padahal hanya satu kartu yang bermasalah. Sekarang **setiap kartu dimuat sendiri-sendiri**: kegagalan satu endpoint mengisi kartunya sendiri dengan pesannya, tidak menghentikan kartu lain. Ringkasan dan daftar sasaran tidak lagi bergantung pada penjadwal.
- **Keadaan penjadwal yang tak terbaca kini dikembalikan sebagai keadaan, bukan galat.** `GET /api/radar/jadwal` menjawab 200 dengan `terpasang: false` dan alasannya di `catatan`, persis seperti yang dilakukan laporan kesiapan.
- **Fungsi ganda di modul peramban dibersihkan.** `_keluaran_seperti_versi` tertulis dua kali; rintisan yang pertama hanya separuh dan tidak pernah dipakai — sisa penyuntingan yang tidak rampung.
- **Dokumen pembuat paket dikoreksi.** `LokaSEO-untuk-Windows.zip` disebut "berkas `.exe` + kode sumber", padahal isinya tidak memuat `.exe` sama sekali — ia jalur kedua untuk dijalankan dengan Python. Kekeliruan itu layak dicatat karena menimbulkan pertanyaan "di mana file `.exe`-nya?". Kini tertulis bahwa `LokaSEO-Windows.zip` **satu-satunya** paket yang memuat `.exe`.
- **`.exe` 0.1.19 dibangun ulang (16,8 MB)** dan diuji sebagai aplikasi Windows: laporan kesiapan lulus tanpa butir gagal, modul radar terbaca dari dalam paket, dan halaman radar menampilkan ringkasan, daftar sasaran, dan tombol periode 7/30 hari dengan benar. Tiga berkas zip ditimpa dengan nama yang sama.
- Uji desktop 215 → **217** (jadwal yang menolak dibaca tidak lagi 500; kartu dimuat sendiri-sendiri; ringkasan digambar di tiga cabang).

---

# 15 Oktober 2026 — Ringkasan pemantauan: yang penting di atas, pola bising dinyatakan

Tiga hari pemantauan menghasilkan puluhan baris perubahan, hampir semuanya "isi halaman berubah" yang sama — dan satu perubahan harga yang benar-benar penting tenggelam di bawahnya. Halaman radar kini membuka dengan **Ringkasan pemantauan** sebelum apa pun.

- **Perubahan dikelompokkan, bukan diulang.** Perubahan pada sasaran yang sama, jenis yang sama, dan pesan yang sama digabung jadi satu baris dengan hitungannya (`14x`). Dua puluh perubahan yang isinya satu pola bising kini tampil sebagai satu baris, bukan dua puluh.
- **Yang perlu dilihat di atas.** Perubahan bertingkat **tinggi** dan **sedang** ditaruh paling atas sendiri. Bila tidak ada, kartunya menulis itu terus terang dan menunjuk ke rincian di bawah, bukan diam-diam kosong.
- **Pola yang berulang dinyatakan sebagai kemungkinan bising.** Pola yang muncul tiga kali atau lebih dikumpulkan di bagian sendiri, disertai penjelasan bahwa situs semacam ini biasanya memang menukar teks kecilnya sendiri setiap kali diminta — jadi pembacanya tidak mengira ada yang perlu ditanggapi.
- **Sasaran yang tidak berubah disebut sekali** sebagai satu baris nama, bukan dibiarkan hilang tanpa keterangan.
- **Periode bisa dipilih: 7 atau 30 hari.** Angka pemeriksaan, perubahan, dan rincian menurut tingkat ikut berubah; batasnya dijaga di server (1–90 hari), jadi angka yang aneh dari antarmuka dikembalikan ke batasnya, bukan dipakai apa adanya.
- **Dua urutan yang keliru diperbaiki.** Pengurutan dilakukan dua kali dan yang kedua menimpa yang pertama, sehingga perubahan lama bisa muncul di atas yang baru walau tingkatnya sama; dan lencana hitungan jatuh ke baris sendiri di bawah tanggal karena ditambahkan sesudahnya.
- **Contoh statis ikut diperbarui** menjadi lima sasaran supaya memperlihatkan ketiga bagian sekaligus: satu perubahan penting, dua yang perlu dilihat, satu pola bising 14x, dan satu sasaran yang tidak berubah. Contoh itu bisa dibuka tanpa server, jadi calon pengguna melihat wujudnya sebelum memantau apa pun.
- Uji radar 352 → **360** (modul baru `radar/lokaradar/ringkasan.py` dengan 8 uji: pengelompokan, ambang berulang, urutan tingkat, urutan waktu, sasaran nonaktif, dan keadaan kosong), uji desktop 209 → **215** (endpoint, pembatasan `hari`, dan keberadaan kartu di tiga cabang antarmuka). Uji peramban `radar-smoke` kini mengawal urutan tingkat dan bahwa lencana hitungan sebaris dengan pesannya.

---

# 15 Oktober 2026 — Peramban Windows tidak lagi “dijalankan” untuk diperiksa

Petunjuk dari komputer Windows sungguhan: `C:\Program Files\Google\Chrome\Application\chrome.exe — ada, tetapi gagal dijalankan`. Berkasnya ada, perambannya sehat — **pemeriksaannya yang keliru**.

- **Penyebabnya sudah diketahui sejak 2012 dan belum diperbaiki Chromium.** Chrome dan Edge di Windows dibangun sebagai aplikasi GUI (`/SUBSYSTEM:WINDOWS`), terlepas dari konsol. Karena itu `chrome.exe --version` **tidak menulis apa pun ke pipa** — pada banyak versi ia malah membuka jendela peramban sungguhan dan baru berhenti setelah batas waktu. Radar mengandalkannya sebagai penapis, jadi peramban yang sehat selalu terbaca “rusak” (crbug 158372 / 40953357).
- **Di Windows nomor versi kini dibaca dari berkasnya**, tanpa menjalankan peramban sama sekali: sumber daya versi PE (`VS_FIXEDFILEINFO` lewat `version.dll`, pustaka standar Windows), lalu folder samping bernama nomor versi yang dipakai tata letak Chromium (`Application\141.0.7390.54\`). Di luar Windows (`--version` memang bekerja di Linux/macOS) pemeriksaan lama tetap dipakai.
- **Efek samping yang hilang:** pemeriksaan lama bisa membuka jendela Chrome di layar pengguna dan menahan aplikasi 15 detik per calon. Sekarang pencarian peramban tidak pernah menjalankan apa pun.
- **Bukti yang sesungguhnya tetap ada.** Karena deteksi tidak lagi menjalankan peramban, tombol “Uji rendering” menjadi satu-satunya hakim: ia benar-benar membuka peramban headless dan merender satu halaman. Bila itu gagal, pesannya menyebut penyebabnya (`Peramban ada, tetapi gagal dipakai: …`), bukan menyalahkan berkasnya.
- Alasan pada kartu dan laporan kesiapan diperjelas: “tidak satupun yang **dikenali** sebagai peramban”, bukan “tidak bisa dijalankan”.
- Uji radar 348 → **352** (uji baru untuk pembacaan versi dari berkas dan penolakan berkas sembarangan), uji desktop 209.

---

# 15 Oktober 2026 — Tombol “Uji rendering” yang mati diberi keterangan, dan pencarian peramban diperluas

Laporan dari Windows 11 (build 26200): tombol **“Uji rendering”** berwarna pudar dan tidak bisa diklik, sementara laporan kesiapan hanya menulis “tidak ada peramban yang ditemukan” tanpa sebab. Dua hal diperbaiki.

- **Tombol yang pudar tidak pernah berdiri sendiri lagi.** Bila tidak ada peramban, kartu kini menulis alasannya dalam satu kalimat — dibedakan antara *“Tidak ada berkas peramban di 34 lokasi yang diperiksa”* dan *“Peramban ditemukan di 1 lokasi, tetapi tidak satupun yang bisa dijalankan”* — karena penanganan keduanya berbeda. Di bawahnya ada tombol **“Periksa ulang”** (untuk peramban yang baru dipasang), daftar **“Yang sudah dicari”** berisi jalur yang diperiksa berikut alasan tiap jalur dilewati, dan satu kolom untuk **menunjuk sendiri berkas perambannya**. Alasan yang sama kini ikut masuk laporan kesiapan, jadi satu tempelan cukup untuk menelusuri masalah.
- **Menunjuk sendiri berkas peramban.** Jalurnya bisa disalin dari peramban itu sendiri (`edge://version` → baris “Executable Path”). Berkas itu **diuji dulu** — benar-benar dipakai merender satu halaman — dan baru disimpan di folder data radar setelah terbukti bekerja. Pilihan yang gagal tidak disimpan.
- **Pencarian peramban diperluas.** Selain jalur pemasangan lazim, kini dibaca juga **registry Windows** (`App Paths`), `PATH`, dan saluran lain (Edge Beta/Dev/Canary, Chrome Beta/Dev/Canary, Chromium, Brave, Vivaldi, Opera). Registry penting karena komputer yang dikelola kantor atau Windows yang dipindah ke drive lain sering memasang Edge di luar jalur lazim.
- **Pembacaan versi tidak genting lagi.** Dulu keluaran galat peramban digabung dengan keluaran bakunya, sehingga satu baris peringatan Chromium (`[1015/084855:WARNING:…]`) sudah cukup untuk membuat peramban yang sehat terbaca “rusak”. Sekarang nomor versi dicari di keluaran baku saja, dan baris peringatan diabaikan (tetap dicatat di log). Ini kandidat kuat penyebab tombol mati di Windows 11.
- Nomor versi kini dilaporkan bersih (`141.0.2903.86`), bukan seluruh keluaran peramban.
- Uji desktop 210 → **214**; uji radar 337 → **348**. Uji peramban di peramban sungguhan kini memeriksa dua skenario: peramban ada (tombol hidup, render terbukti) dan peramban tidak ada (alasan, jejak pencarian, dan jalan keluar tersedia).

---

# 14 Oktober 2026 — Galat ikon tray jadi satu kalimat, dan `.exe` 0.1.17

- **Galat di latar belakang tidak lagi muncul sebagai traceback Python.** Ikon tray dijalankan `pystray` di thread sendiri; di komputer yang menolak pembuatannya (kebijakan perusahaan, sesi jarak jauh, desktop tidak tersedia) pengguna dulu melihat tumpukan galat yang mengkhawatirkan padahal aplikasinya sehat. Sekarang `threading.excepthook` diganti: **traceback penuh tetap masuk berkas log** untuk ditelusuri, dan di layar hanya muncul satu kalimat — "ikon tray tidak bisa ditampilkan di komputer ini; aplikasi tetap berjalan seperti biasa", lengkap dengan tiga cara menghentikan aplikasi. Kalimat itu ikut dicatat ke log supaya tetap terbaca ketika aplikasi dijalankan tanpa jendela konsol (mis. dari Penjadwal Tugas).
- **Sumber galat dikenali dengan benar.** Penentuan "ini galat tray atau bukan" dilihat dari nama berkas pada jejak galat (mengandung `pystray`), bukan dari nama thread — nama thread tidak memberi tahu apa pun, dan menebak dari isi pesan galat bisa salah kategori. Galat latar lain tetap dilaporkan sebagai satu kalimat tanpa mengklaim penyebabnya.
- **`.exe` dibangun ulang (0.1.17, 16,7 MB)** di dalam Wine, lalu diuji sebagai aplikasi Windows: `--kesiapan` melaporkan `Windows 10 (10.0.19043)`, `/` dan `/radar` menjawab 200, dan pada percobaan yang membuat tray gagal, server tetap 200 sementara log memuat kalimat ramah di atas.
- Uji desktop 207 → **210** (tiga uji baru di `desktop/tests/test_catatan_galat.py`).

---

# 14 Oktober 2026 — Berkas `.exe` Windows siap pakai, dan konsol yang tahan code page

- **`LokaSEO-console.exe` (16,7 MB) kini disertakan dalam paket rilis Windows.** Dibangun dengan Python 3.12.8 + PyInstaller 6.22.3 untuk Windows x86-64, ikon tray ikut di dalamnya. Pengguna tidak perlu memasang Python, Node.js, atau apa pun: ekstrak, klik dua kali, peramban terbuka sendiri ke `127.0.0.1`. Cara membangunnya dari sumber tetap tersedia (`build-windows.ps1`).
- **Keluaran konsol kini aman di Windows.** Konsol Windows memakai code page sendiri, dan uji nyata di dalam Wine menunjukkan karakter pemisah `·` muncul sebagai `�`. Laporan kesiapan sekarang **memakai ASCII sepenuhnya** (pemisah `|`, tanda kutip lurus), dan `sys.stdout`/`sys.stderr` diatur `encoding="utf-8", errors="replace"` sehingga cetakan tidak pernah meledak di konsol mana pun.
- **Dibuktikan berjalan sebagai aplikasi Windows.** Diuji di dalam Wine: laporan kesiapan melaporkan `Windows 10 (10.0.19043)`, folder data `C:\users\user\AppData\Roaming\LokaSEO`, modul radar terbaca dari dalam paket `_MEI…`, SQLite dan TLS hidup; sasaran ditambah, pemeriksaan dijalankan, dan potret tersimpan lengkap dengan harga bernama (`Tambal gigi`, `Bleaching gigi`) serta rating 4,7/128 dari data terstruktur.
- Uji desktop 206 → **207**.

---

# 14 Oktober 2026 — Cek kesiapan, dan apa yang ditemukan uji lapangan

- **Tombol “Periksa kesiapan” di halaman radar.** Satu klik memeriksa 11 butir sungguhan — versi aplikasi (dan apakah jalan dari paket `.exe`), sistem, jam, folder data (termasuk uji tulis dan sisa ruang), berkas log, modul radar, jumlah sasaran/potret, peramban beserta versinya, keadaan penjadwal, pemeriksaan terakhir, dan kunci Places — lalu menyusun **laporan teks polos yang bisa disalin** dengan tombol “Salin laporan”. Laporan itu sengaja tidak memuat kunci API, isi halaman, maupun daftar alamat, sehingga aman dikirim untuk menelusuri masalah.
- **Rute `/api/kesiapan` sengaja hidup walaupun radar bermasalah.** Justru saat modul radar gagal dimuat, laporan inilah yang paling dibutuhkan — jadi rutenya tidak lewat pemeriksaan ketersediaan radar, dan setiap butir dibungkus try/except supaya satu kegagalan tidak menjatuhkan seluruh laporan.
- **Mode baru `LokaSEO-console.exe --kesiapan`.** Untuk keadaan ketika antarmuka tidak mau terbuka: laporan dicetak ke layar sekaligus disimpan sebagai `laporan-kesiapan.txt` di folder data (bisa dibuka dengan Notepad).
- **Panduan uji Windows 15 menit**: `desktop/CARA-UJI-WINDOWS.txt` — 10 langkah, hasil yang seharusnya terlihat di tiap langkah, dan apa yang harus dilakukan bila gagal. Ini menutup lubang jujur yang selama ini selalu muncul di laporan: aplikasi belum pernah dijalankan di Windows sungguhan.
- **Uji lapangan 13 situs usaha Bogor** (`radar/uji-lapangan/CATATAN-UJI-LAPANGAN.md` + `hasil-20261014.json`): 12 dari 13 berhasil dipotret, satu ditolak situsnya sendiri (HTTP 405), satu pernah dilewati karena `robots.txt`-nya tidak menjawab lalu berhasil di putaran berikutnya. Empat temuan langsung diperbaiki:
  - **Alarm harga palsu.** Harga dulu dicocokkan berdasarkan keterangannya, sehingga perubahan teks keterangan terbaca sebagai “harga hilang” + “harga baru” padahal angkanya sama. Kini pencocokan berlapis: nama sama → bandingkan angka; angka sama persis → tidak dilaporkan; sisanya baru benar-benar hilang/baru. Putaran ketiga: nol alarm palsu.
  - **Halaman yang teksnya berganti sendiri.** Dua situs nyata memakai teks yang berubah di setiap permintaan (sidik isi berbeda, judul/harga/kata sama). Catatan “isi berubah” diturunkan ke tingkat **info** dengan kalimat yang menyebut kenyataan, dan dibuang bila ada temuan yang lebih penting.
  - **Keterangan harga yang menyesatkan.** Pengambilan teks di sekitar angka pernah membuat semua harga klinik diberi keterangan “Ready To Serve You!” — tagline kepala halaman. Kini keterangan dipotong pada akhir kalimat, dibatasi 6 kata/45 aksara, dan judul bagian hanya dipakai bila muncul tak lebih dari 120 aksara sebelum harganya. Hasil di halaman nyata: “Harga mulai” benar, sisanya **kosong** — jujur daripada menebak.
  - **Harapan data terstruktur diturunkan.** Dari 12 situs, hanya 1 memasang rating agregat dan tidak satu pun menyediakan harga lewat JSON-LD; jalur resmi Places API tetap yang utama.
- Uji radar 326 → **337**; uji desktop 189 → **206**; ditambah uji peramban `tests/lokaseo/browser/kesiapan-ui.mjs` (`pnpm test:loka:kesiapan`) yang menekan tombolnya sungguhan dan memeriksa isi papan klip.

---

# 14 Oktober 2026 — Daftar sasaran radar bisa dipindah dan dibagikan

- **Ekspor daftar sasaran.** Modul baru `radar/lokaradar/sasaran.py` menulis satu berkas JSON sederhana (`lokaradar.sasaran.v1`) berisi alamat, nama singkat, jenis pantauan, dan keadaannya. Di halaman radar ada tombol **Unduh daftar sasaran**; berkasnya mendarat di folder Unduhan dengan nama `sasaran-radar-TANGGAL.json`. Dari baris perintah: `lokaradar export sasaran.json --sasaran`.
- **Impor yang menggabung, bukan mengganti.** Tombol **Impor daftar sasaran** menerima berkas JSON maupun teks biasa (satu alamat per baris, baris `#` dianggap catatan). Sasaran lama tetap ada, yang bertabrakan diperbarui, yang baru ditambahkan. Impor **tidak menghubungi situs mana pun** — pemeriksaan pertama tetap terjadi saat pemeriksaan berikutnya, dan itu dikatakan di ringkasan supaya tidak ada salah paham. `lokaradar import BERKAS --dry-run` memperlihatkan hasilnya tanpa menyimpan.
- **Jawaban yang jujur untuk berkas yang salah.** Bukan daftar sasaran (mis. berkas laporan), JSON rusak, berkas kosong, atau berkas lebih besar dari 1 MB dijawab kalimat yang menjelaskan — bukan gagal diam-diam. Entri yang bukan alamat http(s), ganda di dalam berkas, di atas batas 500 entri, atau di atas batas sasaran aplikasi dilaporkan satu per satu: *"3 ditambahkan, 1 diperbarui, 2 sudah ada, 1 ditolak"*.
- **Tidak merusak data lama.** Berkas yang hanya memuat alamat tidak mengubah label maupun jenis pantauan sasaran yang sudah ada; jenis yang tidak dikenal menjadi “halaman” dan dicatat; profil usaha yang ikut tertulis di berkas ekspor sebagai keterangan **tidak** diimpor, karena jenis usaha diatur pengguna sendiri.
- **Badan permintaan impor punya batasnya sendiri.** Daftar 400 alamat jauh melewati batas body 8 KB yang dipakai rute lain, jadi rute impor memakai batas 2,5 MB — tetap terbatas, tetapi cukup untuk ratusan alamat.
- Uji radar 292 → **326** (`tests/test_sasaran.py`, 30 uji) dan uji desktop 178 → **189**; ditambah uji peramban `tests/lokaseo/browser/sasaran-ui.mjs` (`pnpm test:loka:sasaran`) yang mengunduh berkasnya sungguhan lalu mengimpornya kembali.

---

# 14 Oktober 2026 — Halaman ber-JavaScript dirender tanpa unduhan

- **Rendering memakai peramban yang sudah ada di komputer.** Modul baru `radar/lokaradar/peramban.py` berbicara dengan Microsoft Edge, Google Chrome, atau Chromium lewat Chrome DevTools Protocol — hanya dengan pustaka standar Python. Tidak ada pip, tidak ada unduhan ±150 MB, tidak ada terminal: di Windows 10/11 Edge sudah terpasang sejak awal. Halaman klinik yang tadinya terbaca 19 kata kini terbaca lengkap dengan harga `Rp 350.000` dan `#tabel-harga` di dalamnya.
- **Aplikasi `.exe` ikut bisa merender.** Mode render bawaan aplikasi berubah dari `tidak` menjadi `auto` begitu peramban ditemukan, jadi tombol “Periksa sekarang” di peramban sungguhan kini mengambil ulang halaman yang isinya disusun JavaScript. Terbukti di biner hasil bundel: `POST /api/radar/peramban` menjawab “Rendering berjalan lewat Google Chrome dalam 136 ms”, lalu pemeriksaan menyimpan potret dengan `sumber=peramban` berisi 25 kata dan satu harga — halaman statisnya hanya terbaca 5 kata.
- **Tombol “Uji rendering” membuktikan, bukan mengklaim.** Radar membuka satu peramban untuk halaman uji miliknya sendiri (`data:` bawaan) dan melaporkan lama render; pengujian ini tidak menghubungi situs siapa pun. Kartu baru di halaman `/radar` juga menyebut peramban mana yang dipakai, versinya, dan berkasnya.
- **Sopan santun tetap utuh.** Gambar, video, dan font diblokir (`Network.setBlockedURLs`) sehingga situs orang tidak diunduh lebih dari perlu; CSS dan skrip tetap diambil supaya teks dan harga terbaca benar. `robots.txt` tetap diperiksa **sebelum** peramban dibuka — alamat terlarang tidak sampai ke peramban sama sekali, ada uji yang mengunci itu. Peramban dijalankan dengan profil sementara sendiri: tanpa akun, riwayat, ekstensi, atau sinkronisasi pengguna, dan folder datanya dihapus setelah selesai.
- **Identitas tetap jujur dan diuji sampai ke sisi situs.** User-Agent `LokaRadar/0.1`, `Accept-Language` bahasa Indonesia, tanpa Referer Google; uji memeriksa header yang benar-benar diterima situs tiruan.
- **Peramban yang tidak bisa dijalankan tidak lagi dianggap siap.** Chromium yang kehilangan pustaka sistem tetap ada di cakram dan pernah membuat `versi()` mengembalikan pesan galat seolah-olah nomor versi. Kini setiap kandidat diuji `--version` lebih dahulu, dan biner yang gagal dilewati — termasuk bentuk Chrome Headless Shell yang tidak menerima `--headless=new`.
- **Penanda kerangka JavaScript ditambah** (`id="__next"`, `id="__nuxt"`, `id="vue-app"`). Sebelum ini, halaman Next.js yang hanya memuat satu skrip bundel luaran tidak dikenali sebagai kerangka, sehingga mode `auto` melewatinya.
- **Pemeriksaan selektor tunggu tidak lagi bergantung pada Scrapling.** `selektor_ditemukan()` kini punya pemeriksa pustaka-standar untuk `#id`, `.kelas`, `tag`, dan `[atribut]`, dan mengembalikan “tidak tahu” untuk selektor rumit. Sebelumnya, di dalam `.exe` catatan “selektor tunggu tidak ditemukan” hilang diam-diam.
- Tiga bug yang ketangkap saat mengerjakan ini: penyusun bingkai WebSocket **menggantung selamanya** pada pesan yang dipecah peramban (bingkai lanjutan terakhir tidak pernah mengakhiri pembacaan); `Accept-Language` dikirim dua kali sehingga situs menerima nilai rusak `id-ID,id;q=0.9;q=0.9,en;q=0.5;q=0.8`; dan `versi()` melaporkan pesan galat pustaka sebagai versi peramban.
- **Chip “Rendering” tidak lagi bertentangan dengan kartu.** Ringkasan di atas halaman radar menulis “permintaan biasa” padahal kartu di bawahnya baru menyatakan peramban siap — kesiapan peramban dulu hanya dinilai dari Scrapling, bukan dari peramban yang benar-benar ada di komputer. Kini keduanya membaca keadaan yang sama, dan ada uji yang mengunci kesepakatan itu (uji Python **dan** uji peramban).
- **Pesan hasil render lebih tepat.** Catatan “Setelah dirender halaman masih hanya 25 kata” terbaca seperti kegagalan padahal renderingnya berhasil; sekarang berbunyi “Rendering berhasil, tetapi halaman tetap tipis (25 kata) — bisa jadi isinya memang singkat.”
- **Uji peramban baru `tests/lokaseo/browser/peramban-ui.mjs`** (`pnpm test:loka:peramban`) menjalankan aplikasi desktop sendiri, membuka halaman `/radar`, dan menekan tombol “Uji rendering” di peramban sungguhan; tanpa peramban, uji itu menuntut jawaban yang jelas, bukan diam.
- Uji radar 255 → **292** (berkas baru `tests/test_peramban.py`, 36 uji; termasuk uji yang benar-benar membuka peramban). Uji desktop 168 → **178**.

---

# 14 Oktober 2026 — Pemeriksaan radar otomatis harian

- **Satu tombol memasang jadwal harian.** Halaman `/radar` punya bagian “Pemeriksaan otomatis”: pilih jam dan ulangan (harian atau mingguan), tekan “Aktifkan jadwal”, dan Windows memanggil aplikasi sendiri setiap pagi lewat tugas **LokaSEO - Radar harian**. Tidak perlu peramban maupun aplikasi yang tetap terbuka.
- **Mode baru `--radar-periksa`.** Aplikasi memeriksa sekali lalu keluar: tanpa peramban, tanpa server, tanpa tray. Inilah yang dipanggil penjadwal. Kode keluarnya bisa dibaca mesin (0 selesai, 1 ada yang perlu dilihat), dan catatannya masuk ke berkas log aplikasi.
- **Tanpa hak administrator, dan bisa dilepas lagi.** Tugas dibuat untuk pengguna yang sedang masuk; tombol “Matikan jadwal” menghapusnya. Perintah yang akan didaftarkan ditampilkan apa adanya di antarmuka sebelum pengguna menekan apa pun.
- **Tidak ada pilihan per jam.** Radar memeriksa situs orang lain, jadi ulangan dibatasi harian atau mingguan — jadwal per jam akan menjadi beban yang tidak diminta. Bila komputer mati atau tidur pada jam itu, pemeriksaan terlewat dan tidak menyusul sendiri; itu ditulis di antarmuka.
- **Bukti, bukan kepercayaan.** Tombol “Jalankan tugasnya sekarang” meminta penjadwal Windows menjalankannya (`schtasks /Run`), sehingga yang diuji adalah rangkaian penuh: tugas tersimpan → aplikasi dipanggil → potret tersimpan.
- **Naskah tugas dibaca sebagai XML**, bukan teks yang sudah diterjemahkan. Windows berbahasa Indonesia pun tetap terbaca benar: jam, ulangan, hari, dan keadaan aktif/nonaktif diambil dari unsur XML yang bahasanya tetap Inggris.
- **Di luar Windows, jawabannya jujur**: halaman radar tidak menampilkan tombol palsu, melainkan penjelasan singkat plus baris cron yang bisa disalin ke `crontab`.
- Dua bug yang ketangkap uji saat mengerjakan ini: nilai `/TR` sempat dikurung tanda kutip dua kali sehingga penjadwal akan mencari berkas bernama `"C:\Program Files\...\LokaSEO.exe" --radar-periksa`, dan perhitungan hari berikutnya memakai konvensi hari yang salah (Senin tertukar dengan Minggu) — keduanya kini dikunci uji, termasuk uji bahwa kutip hanya muncul di sekitar jalur yang mengandung spasi.
- Mode `--offline` menolak memasang jadwal (409) dengan alasan yang jelas: pemeriksaan butuh jaringan.
- Berkas baru `desktop/lokaseo_desktop/jadwal.py`; seluruh panggilan `schtasks` lewat satu pintu yang bisa diganti, sehingga pengujian berjalan di komputer mana pun tanpa menyentuh penjadwal sungguhan.
- Uji desktop 112 → **168** (berkas baru `desktop/tests/test_jadwal.py`, 37 uji). Uji radar tetap **255**. Contoh tampilan tanpa server ikut menampilkan kartu jadwal.

---

# 14 Oktober 2026 — Radar masuk ke dalam aplikasi `.exe`

- **Satu klik dari ruang kerja, tanpa terminal.** Halaman `/radar` di aplikasi desktop: tambah sasaran, jalankan pemeriksaan di latar belakang, lihat perubahan terakhir, lalu baca laporan terbaru. Tautan “Radar pemantauan situs” disuntikkan ke beranda aplikasi.
- **Pengaturan LokaSEO menjadi kunci utama kerja radar.** Halaman radar membaca proyek aktif dari penyimpanan LokaSEO di peramban (`lokaseo.workspace.v1`) dan mengirimkannya ke server lokal sebagai profil radar: nama usaha, kota, domain, dan **jenis usaha**. Dari situ radar menetapkan ambang rating, data terstruktur yang diharapkan, dan kata kunci awal. Tersedia pula isian manual bila proyek belum punya jenis usaha, dan tombol “Ambil ulang pengaturan dari LokaSEO”.
- **Data radar tinggal di folder aplikasi**: `%APPDATA%\LokaSEO\radar` di Windows (dapat dipindah lewat `LOKARADAR_DATA`). Tidak ada unggahan ke mana pun.
- **Sopan santun tetap utuh di jalur aplikasi**: `robots.txt` dihormati, jeda per host dihitung, identitas `LokaRadar` disebut apa adanya, pemeriksaan berjalan satu per satu, dan permintaan dari halaman lain ditolak (403) seperti endpoint aplikasi lainnya. Batas baru: `RADAR_MAX_BODY_BYTES` 8 KiB, `RADAR_MAX_PAGES` 40 sasaran per putaran, `RADAR_MAX_TARGETS` 200.
- **Dua bug bundel yang hanya muncul saat `.exe` sungguhan dibangun.** PyInstaller tidak dapat menelusuri `lokaradar` karena folder `radar/` belum ada di `pathex`, sehingga modul itu ikut sebagai berkas data dan `html.parser` (dipakai `extract.py`) tidak masuk paket — aplikasi hasil bundel menjawab `ModuleNotFoundError: No module named 'html.parser'`. Setelah `pathex` diperbaiki, seluruh ketergantungan Scrapling/Playwright ikut tertarik dan berkas membengkak 31 MB → **104 MB**; keduanya kini dikecualikan dengan alasan tertulis. Hasil akhir **32,8 MB**.
- **Dua bug tampilan yang hanya muncul saat halaman benar-benar dibuka peramban**: nama `window.__RADAR_DATA__` pernah salah tulis satu garis bawah (cabang contoh selalu melempar galat sehingga tidak ada kartu yang tampil), dan `.append(...).value = ""` (dalam JavaScript, `append` mengembalikan `undefined`, bukan elemennya). Keduanya kini dikunci uji.
- **Contoh tampilan yang bisa dibuka tanpa server dan tanpa jaringan**: `desktop/contoh/tampilan-radar.html`, dibuat oleh `python3 desktop/contoh/buat-tampilan.py`, dijaga uji peramban `tests/lokaseo/browser/radar-smoke.mjs` (`pnpm test:loka:radar`).
- Waktu di halaman radar ditampilkan dalam format setempat (“14 Okt 2026, 16.20”), bukan bentuk ISO mentah.
- **Bukti uji**: biner hasil bundel dijalankan dari folder kosong di luar repository, lalu — lewat API-nya sendiri — profil “Kopi Ranah” (kafe-kedai, ambang 4,3) disimpan, dua sasaran ditambahkan pada situs contoh lokal, dan pemeriksaan dijalankan: satu halaman tersimpan sebagai potret dasar, satu halaman 404 dilaporkan apa adanya sebagai galat, dan catatan “Halaman ini pendek (39 kata)” muncul untuk halaman yang mungkin perlu peramban.
- **Batas jujur yang tetap berlaku**: merender halaman ber-JavaScript hanya bisa dari folder `radar/` (butuh Scrapling + Chromium ±150 MB); peramban tidak dibundel ke dalam `.exe`. Aplikasi menyebutkannya apa adanya (`peramban: belum terunduh`) alih-alih diam-diam gagal.
- Uji desktop 93 → **112**; uji radar tetap **255**.

---

# 14 Oktober 2026 — Polesan rendering: hemat peramban, tanpa alarm palsu

- **Satu peramban per putaran.** `run` memakai satu `DynamicSession` Scrapling untuk semua halaman (bukan membuka-tutup peramban per halaman); hemat sekitar satu detik per halaman ber-JavaScript. Sesinya ditutup otomatis, dan bila sesi tidak tersedia jalur satu-peramban tetap dipakai.
- **`--tunggu SELEKTOR`.** Menunggu elemen tertentu muncul sebelum halaman diserahkan — berguna untuk situs yang memuat daftar harga belakangan. Selektor yang salah tidak menggagalkan permintaan, jadi radar memeriksa hasilnya sendiri dan menuliskan peringatan bahwa penantiannya sia-sia.
- **Alarm palsu dicegah.** Perubahan cara pengambilan (mis. peramban baru dipasang) tidak lagi terbaca sebagai puluhan perubahan isi: potret dibandingkan ulang dari nol dengan satu catatan info `Cara pengambilan berubah …`. Bukti: putaran pertama `--render tidak` (3 kata) lalu `--render auto` (537 kata) pada fdcdentalclinic.co.id menghasilkan satu baris info, bukan puluhan perubahan palsu.
- **Heuristik "perlu dirender" diperbaiki.** Penanda kerangka JavaScript (Next/Nuxt/React/Angular/Svelte, `id="root"`, `window.__`, atau banyak skrip pada halaman besar) harus ikut terlihat, supaya halaman pendek yang statis seperti halaman kontak tidak memicu unduhan peramban.
- **Catatan kembar dibuang.** Satu masalah yang muncul untuk banyak sasaran (mis. peramban belum terunduh) kini ditulis sekali saja di laporan.
- Perintah `scrape` memperlihatkan apa yang berubah karena rendering: `Jumlah kata : 95 (permintaan biasa hanya terbaca 7)` dan lama renderingnya.
- Perintah `status` menyebut `sesi dipakai ulang` bila peramban bisa dipakai berulang.
- Dua bug yang ketangkap saat mengerjakan ini: catatan "selektor tunggu tidak ditemukan" tertimpa catatan lain pada mode `auto`, dan `run` bisa mengulang keterangan perpindahan cara pengambilan dua kali di terminal.
- Uji radar bertambah 240 → **255** (berkas `tests/test_render.py` kini 40 uji).

---

# 14 Oktober 2026 — Pembacaan situs ber-JavaScript (rendering peramban)

- Mode render baru: `--render auto` (**bawaan**), `selalu`, atau `tidak`. Pada mode `auto`, halaman yang terbaca di bawah 40 kata **dan** terlihat seperti kerangka JavaScript (penanda Next/Nuxt/React/Angular/Svelte, `id="root"`, `window.__`, atau banyak skrip pada halaman besar) diambil **ulang** dengan peramban headless lewat `DynamicFetcher` Scrapling. Halaman pendek yang statis — misalnya halaman kontak — tidak memicu peramban, supaya tidak ada permintaan yang terbuang ke situs orang. Situs klinik yang pada uji Bogor hanya terbaca 3 kata kini terbaca **537 kata**, lengkap dengan judul dan deskripsi.
- Janji kesopanan tetap utuh saat merender: `robots.txt` diperiksa lebih dulu (alamat yang dilarang tidak pernah dikirim ke peramban), jeda per host dihitung untuk tiap permintaan, dan permintaan kedua memakai jeda yang sama.
- Identitas jujur juga berlaku di peramban: User-Agent `LokaRadar/0.1`, `google_search=False` (bawaan Scrapling menyisipkan `Referer: https://www.google.com/` — sudah dimatikan), dan sisa jejak peramban (`sec-ch-ua`, `Sec-Fetch-*`) disebut apa adanya di README.
- Kegagalan rendering tidak lagi gagal diam-diam: sebabnya diterjemahkan menjadi satu kalimat ("Peramban belum terunduh. Jalankan `scrapling install` …") dan ditulis di laporan.
- Perintah `status` menambah baris `Rendering` (mode + kesiapan peramban). Perintah `scrape` menyebut apakah halaman diambil dengan peramban.
- Potret menyimpan cara pengambilannya (`sumber`: `permintaan-biasa`, `peramban`, atau `places-api`) beserta catatan; basis data lama dimigrasikan otomatis tanpa menghapus data.
- Laporan menuliskan "Pengambilan: dengan peramban (isi dibuat JavaScript)" per sasaran, dan menambah butir ceklis "Buka halaman dengan peramban" untuk halaman yang masih tipis.
- Bug yang ditemukan dan diperbaiki saat mengerjakan ini: `browser_ready()` gagal karena `pathlib.Path` belum diimpor di `fetch.py` (tertutup oleh `except` lebar — sekarang pesan galatnya disimpan dan ditampilkan), dan pengambil halaman yang diganti kini tidak pernah membuka peramban sehingga pengujian tetap luring.
- Demo baru `contoh/demo-render.sh`: situs lokal ber-JavaScript, tiga mode render, plus laporan hasilnya. Contoh keluaran: `contoh/laporan-render-demo.md`.
- Uji radar bertambah 215 → **240** (berkas baru `tests/test_render.py`, 25 uji).
- Rendering peramban perlu unduhan sekali (`scrapling install`, ±150 MB). Tanpa itu radar tetap berjalan dengan permintaan biasa, dan laporan menyebutkannya.

---

# 14 Oktober 2026 — Places API: menutup lubang rating usaha lokal

- Perintah baru **`cari "<kata kunci>" [--kota NAMA] [--max N] [--tambah N]`**: mencari `place_id` lewat Google Places API Text Search memakai kunci pengguna sendiri, menampilkan kandidat beserta rating dan alamat, dan bisa langsung menambahkan satu kandidat sebagai sasaran `tempat:<place_id>`.
- Jenis usaha kini punya penanda **`rating_penting`**. Untuk kafe, restoran, klinik, salon, penginapan, bengkel, laundry, kursus, kontraktor, jasa profesional, dan logistik, laporan menambahkan butir ceklis "Tambahkan sasaran rating resmi" bila belum ada sasaran `tempat:` — inilah tindak lanjut temuan uji Bogor bahwa hanya 1 dari 7 usaha lokal memuat rating di situsnya.
- Perintah `status` kini menampilkan kesiapan kunci Places (`terpasang`/`belum diatur`) **tanpa pernah mencetak kuncinya**, serta jumlah sasaran `tempat:`.
- Pesan galat Places API dibuat bisa ditindaklanjuti: kunci belum diaktifkan (400), kunci salah (401), pembatasan kunci (403), tempat tidak ditemukan (404), dan kuota habis (429).
- Pemanggil API kini menerima spesifikasi permintaan (`PlacesRequest`) sehingga mendukung GET dan POST; bawaan loader dapat diganti saat pengujian.
- Demo baru `radar/contoh/demo-places.sh` memakai jawaban tiruan: menampilkan alur lengkap (status → profil → cari → tambah → pantau → papan) tanpa kunci dan tanpa memakai kuota siapa pun. Contoh keluaran: `radar/contoh/laporan-places-demo.md`.
- Uji radar bertambah 196 → **215**.
- Belum diuji dengan kunci Places API sungguhan; seluruh pengujian memakai pemanggil tiruan.

---

# 14 Oktober 2026 — uji nyata usaha Bogor: dua perbaikan penting

- Uji lapangan sekali jalan terhadap **tujuh situs usaha Bogor** (klinik gigi, toko oleh-oleh, villa) dengan satu halaman per usaha, `robots.txt` dihormati, jeda 2,5 detik, dan User-Agent jujur. Catatan lengkap: `radar/uji-bogor/CATATAN-UJI-BOGOR.md`.
- **Bug kejujuran ditemukan dan diperbaiki.** `stealthy_headers` bawaan Scrapling bernilai True dan `impersonate` bawaan bernilai `chrome`, sehingga radar mengirim User-Agent Chrome buatan, header `sec-ch-ua`, dan referer Google — bertentangan dengan janji dokumen. Kini jalur bawaan memakai `impersonate=None` + `stealthy_headers=False` dan hanya mengirim `User-Agent: LokaRadar/0.1 …`, `Accept`, dan `Accept-Language`. Lima uji penjaga baru di `radar/tests/test_fetch_identity.py`.
- Mode menyamar tetap tersedia tetapi harus dinyalakan sadar lewat `--stealthy`, dan pemakaiannya mencetak peringatan.
- **Skala rating kini dinormalkan pada papan reputasi.** Rating 9,9 dari 10 tidak lagi dibandingkan langsung dengan 4,5 dari 5: peringkat memakai rasio, ditambah kolom "Setara / 5", rata-rata setara, dan catatan bila skala berbeda.
- Temuan lapangan lain: hanya 1 dari 7 situs memuat rating di halamannya; satu situs klinik hanya terbaca 3 kata karena dirender JavaScript; toko oleh-oleh menyembunyikan harga di keranjang; satu situs menolak dengan HTTP 405 (dilaporkan apa adanya, tidak ditembus); kafe kecil Bogor hampir semuanya hanya punya Instagram.
- Uji radar bertambah 190 → **196**.

---

# 14 Oktober 2026 — jenis usaha menjadi kunci utama kerja

- **LokaSEO:** proyek kini punya kolom **jenis usaha** (`industry`) yang dipilih saat membuat proyek dan bisa diubah di Pengaturan proyek. Ada 13 pilihan untuk konteks Indonesia (kafe/kedai, restoran, toko retail, salon, klinik, bengkel, laundry, penginapan, kursus, kontraktor, jasa profesional, logistik, lainnya) dengan tabel di `src/client/features/lokaseo/industries.ts`.
- Kolom ini **tidak merusak cadangan lama**: `industry` diberi nilai bawaan kosong, jadi cadangan dari versi sebelumnya tetap bisa dibuka. Ada uji khusus untuk itu.
- Jenis usaha tampil pada baris informasi proyek dan ikut tertulis di laporan Markdown (“Jenis usaha: …”).
- **Radar:** modul baru `lokaradar/profil.py`. Perintah `profil` bisa menampilkan, mengatur, atau **mengimpor langsung dari cadangan LokaSEO** (`lokaseo-cadangan.json`), lalu memakai jenis usaha sebagai kunci utama:
  - data terstruktur yang diperiksa (misalnya `CafeOrCoffeeShop` untuk kafe),
  - ambang rating papan reputasi (misalnya 4,3 untuk usaha makanan; bisa ditimpa `--min-rating`),
  - kata kunci awal untuk usulan konten,
  - catatan jenis usaha pada laporan,
  - pemisahan **“Situs sendiri”** dan **“Pesaing / mitra”** pada laporan serta penanda “(usaha Anda)” pada papan reputasi.
- Radar menambahkan catatan (bukan perubahan riwayat) ketika situs sendiri belum memuat data terstruktur yang wajar untuk jenis usahanya.
- Uji bertambah: 162 → **190** di radar (termasuk uji silang yang memastikan daftar jenis usaha di `industries.ts` dan `profil.py` tidak pernah berbeda), dan 50 → **52** di LokaSEO. Skrip contoh baru: `radar/contoh/demo-jenis-usaha.sh`.
- Belum ada: pengiriman profil dari aplikasi desktop ke radar secara otomatis (masih lewat unduh cadangan atau perintah `profil`).

---

# 14 Oktober 2026 — papan reputasi lokal (LokaRadar fase 2)

- Modul baru `lokaradar/reputasi.py`: **papan reputasi lokal** yang menyusun peringkat rating dan jumlah ulasan beberapa usaha sekaligus (usaha sendiri dan pesaing sekitar).
- Angka yang dihitung: rating dan jumlah ulasan terbaru, selisih keduanya dibanding awal periode, **laju ulasan per minggu**, dan pangsa ulasan terhadap total di papan. Laju butuh minimal dua potret, dan bila datanya kurang, radar mengatakannya — bukan menebak.
- **Tanda perhatian**: `rating_rendah` (di bawah ambang `--min-rating`), `rating_turun` (≥ 0,1), `ulasan_menurun` (jumlah ulasan berkurang, kemungkinan ulasan dihapus platform), `ulasan_lambat`, `belum_ada_rating`, `data_kurang`, dan `tempat_resmi`.
- Perintah baru: `reputasi [--days N] [--min-rating X] [--out FOLDER]` dan `tempat <place_id>`.
- **Sumber resmi opsional** (`lokaradar/places.py`): sasaran berawalan `tempat:<place_id>` dibaca lewat Google Places API (New) memakai kunci milik pengguna sendiri (`LOKARADAR_PLACES_KEY` atau `--places-key`). Kunci hanya di memori proses; tidak pernah masuk basis data, laporan, atau catatan. Yang disimpan hanya `place_id` dan angka agregat.
- Halaman Google Maps dan hasil pencarian Google **tidak** dipakai sebagai jalur bawaan: robots.txt Google melarang jalur peta/pencarian dan Ketentuan Layanan Google Maps Platform §3.2.3 melarang penyalinan nama, alamat, serta ulasan. Sasaran tanpa kunci dilaporkan gagal dengan jelas.
- Papan reputasi ikut masuk ke laporan Markdown dan paket wawasan (`reputasi` + usulan ide konten serta butir ceklis di `lokaseo`), misalnya "tindak lanjuti ulasan yang menurunkan rating" dan "minta ulasan ke pelanggan terakhir".
- Sasaran yang belum pernah berhasil diperiksa tidak lagi memenuhi papan; ringkasan putaran sudah melaporkan kegagalannya.
- Uji bertambah dari 121 menjadi **162** (papan reputasi, laju ulasan, tanda perhatian, sumber Places API, sasaran `tempat:`, dan perintah baris baru). Ditambah skrip contoh `radar/contoh/demo-reputasi.sh`.
- Belum diuji dengan kunci Places API sungguhan atau kuota nyata; seluruh pengujian modul itu memakai pemanggil tiruan.

---

# 14 Oktober 2026 — LokaRadar: radar pemantauan situs publik

- Modul baru **`radar/`** (paket Python `lokaradar`, versi 0.1.0): memantau halaman publik milik pesaing atau mitra, menyimpan riwayatnya di komputer sendiri, dan menyusun bahan kerja untuk LokaSEO.
- Dibangun di atas **[Scrapling](https://github.com/d4vinci/Scrapling)**; bila Scrapling tidak terpasang, modul jatuh ke pustaka standar Python tanpa penyempurnaan header.
- **Sopan secara bawaan:** `robots.txt` dinilai per alamat (aturan `Disallow` tidak lagi berlaku sebagai izin menyeluruh), jeda 2,5 detik per host dengan `Crawl-delay` sebagai batas minimum, maksimal 40 halaman per putaran, User-Agent jujur tanpa penyamaran peramban, dan penolakan menjelajah bila `robots.txt` tidak dapat dipercaya.
- **Riwayat lokal:** SQLite (`radar.sqlite3`) dengan tabel sasaran, potret, perubahan, dan keadaan. Tidak ada server, akun, maupun pengiriman data ke layanan daring. Retensi 180 hari dengan minimal 3 potret per sasaran.
- **Deteksi perubahan:** harga (`harga_turun`, `harga_naik`, `harga_baru`, `harga_hilang`), rating dan jumlah ulasan, judul, deskripsi, bagian baru atau hilang pada heading, `noindex`, `canonical`, teks tanpa perubahan kata berarti, gambar tanpa alt, dan data terstruktur bisnis lokal. Ambang derau 1 % + Rp1 agar selisih pembulatan tidak dilaporkan.
- **Keluaran:** `laporan-<stempel>.md` sebagai laporan Markdown berbahasa Indonesia dan `wawasan-<stempel>.json` berskema `lokaradar.insight.v1` berisi usulan ide konten serta butir ceklis untuk ruang kerja LokaSEO.
- **Antarmuka baris perintah:** `status`, `add`, `list`, `remove`, `run`, `changes`, `report`, `export`, dan `scrape`.
- **121 uji tanpa jaringan** (pengambil, jam, dan `robots.txt` palsu) ditambah skrip demo lokal `contoh/demo-lokal.sh` yang menjalankan server contoh di komputer sendiri.
- Dua bug ditemukan saat pengujian dengan server sungguhan dan sudah diperbaiki: (1) `response.text` pada Scrapling bukan teks halaman (tipenya `TextHandler` dan sering kosong), sehingga `robots.txt` terbaca kosong dan teks halaman tidak pernah terbaca — kini isi dibaca dari `html_content`/`body` dan teks terbaca dari `get_all_text()`; (2) halaman dengan status galat (404/5xx) tidak lagi disimpan sebagai potret, melainkan dilaporkan sebagai kegagalan sasaran.
- Hanya angka agregat (rating, jumlah ulasan) yang disimpan; nama, isi, dan identitas penulis ulasan tidak pernah masuk laporan.
- Belum ada: antarmuka grafis (masih baris perintah), pembacaan halaman berat JavaScript (`DynamicFetcher`/`StealthyFetcher` belum dipakai), penembus CAPTCHA, dan penggabungan ke dalam aplikasi desktop.

---

# 12 Oktober 2026 — antarmuka aplikasi di peramban

- Bawaan aplikasi diubah: antarmuka dibuka di **peramban** (`--window browser` kini bawaan), bukan jendela aplikasi. WebView2 tidak lagi diperlukan.
- Menambahkan ikon **system tray** (`desktop/lokaseo_desktop/tray.py`) dengan menu Buka LokaSEO dan Hentikan LokaSEO, memakai `pystray` + Pillow.
- Menambahkan halaman `GET /hentikan` (HTML tanpa sumber daya luar) dan endpoint `POST /api/lokaseo/hentikan`, serta `GET /api/lokaseo/info` untuk menandai mode desktop.
- Endpoint penghentian memakai pemeriksaan Host/Origin yang sama; permintaan lintas situs ditolak 403 dan tidak menghentikan aplikasi.
- Menambahkan opsi `--no-tray`; pesan konsol kini menunjuk halaman `/hentikan`.
- Paket dibersihkan: modul besar yang tidak dipakai (numpy, matplotlib, scipy, pandas, setuptools, pip, pydoc, doctest, pdb, xmlrpc) dikecualikan sehingga biner turun dari 48 MB ke 30 MB pada pengujian Linux.
- Aset ikon ikut dibundel ke dalam paket (`assets/`) agar ikon tray tersedia di `.exe`.
- Uji bertambah menjadi 61: halaman dan endpoint penghentian, penolakan asal lintas situs, serta pemeriksaan biner hasil build. Alur Actions juga menguji halaman hentikan dan endpoint info pada `.exe` Windows.
- Bukti lokal: biner Linux hasil build membuka halaman `/hentikan`, menolak permintaan lintas situs (403), dan **berhenti sendiri** setelah menerima permintaan penghentian yang sah.
- Belum diuji: `.exe` Windows (dibangun lewat Actions), ikon tray di Windows, dan `--window native`.

---

# 12 Oktober 2026 — paket aplikasi Windows

- Sasaran paket dibatasi ke **Windows**: alur otomasi hanya `windows-latest`, dokumen dan skrip menyesuaikan.
- Menambahkan `desktop/build-windows.ps1` (build antarmuka, uji, PyInstaller, paket zip berisi `.exe` + `LICENSE.txt` + `CARA-PAKAI.txt`) dan `desktop/run-windows.bat`.
- Menambahkan sumber daya Windows: `version_info.txt` (nama, versi, atribusi MIT) dan `lokaseo.manifest` (`asInvoker`, sadar DPI per-monitor, long path).
- Spec kini membuat dua target: `LokaSEO.exe` berjendela (bila `pywebview` terpasang saat build) dan `LokaSEO-console.exe` untuk menelusuri masalah.
- Alur Actions menguji `.exe` hasil build pada runner Windows: halaman utama, header keamanan, penolakan Host asing, dan mode luring yang tidak memanggil penyedia.
- Menambahkan 15 uji baru (total 54): berkas paket Windows, versi, ikon, serta pengujian biner hasil build termasuk memastikan API key tidak masuk catatan aplikasi.
- Memperbaiki spec: pengecualian modul `email` membuat `http.server` gagal dimuat pada biner hasil build; kini hanya `tkinter` yang dikecualikan.
- Belum diuji: `.exe` Windows dibangun dari mesin Linux ini; yang teruji di sini biner Linux dan seluruh unit test.

---

# 12 Oktober 2026 — aplikasi desktop lokal

- Menambahkan `desktop/`: server lokal Python tanpa dependency (stdlib) yang menyajikan antarmuka dan menyediakan endpoint AI, launcher dengan pilihan jendela, ikon aplikasi, dan berkas PyInstaller.
- Bawaan hanya mengikat `127.0.0.1`, tanpa header CORS, dengan pemeriksaan Host/Origin, batas body 64 KiB/5 detik, 32 pembaca, 8 pemanggilan penyedia, dan daftar tujuan keluar tertutup.
- Mode luring (`--offline`) mematikan seluruh panggilan AI dan menjawab dengan hasil kosong agar pekerjaan manual tetap tenang.
- Ikon dipindah ke `studio/public/` dan dipasang sebagai `publicDir`, sehingga build mandiri kini membawa favicon dan manifest.
- Verifikasi: 35 unit test Python, 5 skrip browser, dan regresi keamanan lulus terhadap server Python tanpa mengubah tes. Biner Linux hasil PyInstaller (22,8 MB) diuji: menyajikan aplikasi, menolak Host asing (421), dan mematikan AI dalam mode luring.
- Belum diuji: biner Windows/macOS, jendela `pywebview`, dan panggilan penyedia AI dengan key nyata.

---

# 12 Oktober 2026 — nama folder dan pembersihan akhir

- Folder kerja diganti dari `open-seo` menjadi `loka-seo`.
- Arsip audit lokal dan berkas bantu di luar repo dihapus, termasuk skrip utilitas sementara, log instalasi, tangkapan layar lama, dan hasil tes yang dapat dibuat ulang.
- Dokumentasi dan laporan keamanan diperbarui: bukti mentah dinyatakan sudah dihapus, bukan diarsipkan.
- Smoke test browser diperketat: menunggu penyimpanan asinkron selesai sebelum memeriksa data, dan menunggu nilai formulir AI terisi. Lima skrip browser lulus tiga putaran berturut-turut setelah penyesuaian ini.
- Tautan simbolik `.claude/skills` yang hilang dipulihkan.
- Tidak ada perubahan pada perilaku aplikasi.

---

# 12 Oktober 2026 — dokumentasi Indonesia dan sumber proyek

- Menambahkan `ASAL-PROYEK.md`: repositori GitHub awal, commit sumber, lisensi, batas atribusi, dan gagasan pengembangan LokaSEO.
- Menonjolkan sumber kode OpenSEO dalam README dan materi LinkedIn.
- Memperjelas bahwa panduan utama LokaSEO berbahasa Indonesia; dokumen teknis warisan yang belum diterjemahkan dan teks lisensi tetap dipertahankan dalam bahasa asli.
- Menyertakan petunjuk mengambil salinan OpenSEO pada commit sumber untuk dipelajari secara terpisah.
- Perubahan tahap ini hanya dokumentasi; tidak mengubah perilaku aplikasi.

---

# 12 Oktober 2026 — perapian repository publik

- Dokumentasi dipusatkan di `docs/lokaseo/`; teks LinkedIn di `docs/social/`.
- Smoke test dan regresi keamanan dipindah ke `tests/lokaseo/`; perintah npm diperbarui.
- Log, hasil probe historis, dan snapshot sementara dikeluarkan dari source publik.
- README baru, screenshot data contoh, panduan kontribusi, dan kebijakan keamanan ditambahkan.
- Workflow upstream yang melakukan deployment/publishing/upload sourcemap dijadikan contoh nonaktif; CI LokaSEO hanya memeriksa kode dan build.
- Regresi smoke test edit konten menunggu commit penyimpanan asinkron, bukan membaca storage langsung setelah klik.
- Setelah perapian: typecheck modul, build, 50 tes modul, 26 tes upstream terpilih, enam skrip browser, serta probe slow body lulus lokal. GitHub Actions remote belum dijalankan.

Catatan di bawah adalah riwayat tahap sebelumnya; angka tes di masing-masing bagian mencerminkan saat tahap itu dikerjakan.

---

# Pembaruan terbaru — AI opsional

Buka **AI & token → Koneksi & cadangan** untuk memasukkan key milik sendiri. Didukung OpenAI, OpenRouter, DeepSeek, dan Groq; maksimal lima koneksi aktif/nonaktif dengan urutan yang dapat diubah. Mode awal tetap **Tanpa AI**.

Setelah mengaktifkan AI, pilih bantuan ide konten, brief, atau saran perbaikan. Jika satu koneksi gagal, aplikasi mencoba koneksi aktif berikutnya. Hasil menampilkan jalur percobaan. **Penggunaan token** menyediakan ringkasan, filter, rincian setiap percobaan, dan ekspor CSV. Angka yang tidak dikembalikan penyedia diberi keterangan, bukan dianggap nol.

Key hanya untuk sesi tab; reload menghapusnya. Riwayat token tetap di browser. Jawaban AI belum otomatis disimpan atau diterbitkan. Lihat [panduan AI](./ai-guide.md) untuk batasan dan pengamanan deployment. Pengujian AI memakai simulasi, bukan API berbayar nyata.

---

# Pembaruan terbaru — mudah untuk pemula

Buka Live Preview dan refresh. **Panduan pemula** aktif secara default untuk browser yang belum memilih mode. Jika sebelumnya dimatikan, aktifkan melalui tombol di bagian atas.

1. Klik **Mulai dengan usaha saya**, isi nama, lalu simpan. Alamat situs dan kota tidak wajib.
2. Klik **Cek informasi bisnis**. Buka petunjuk dan tandai hanya informasi yang benar-benar sudah diperiksa.
3. Kembali ke Ringkasan, lalu **Rencanakan tulisan pertama**. Isi produk atau layanan untuk mendapatkan contoh judul yang bisa diedit.
4. Setelah menyimpan rencana, kembali ke Ringkasan dan unduh cadangan. Tiga langkah selesai tidak berarti seluruh SEO sudah selesai.

Angka dan audit teknis tidak lagi menjadi tampilan utama. Semua fitur lama tetap tersedia. Panduan per halaman, kamus istilah, unggah HTML, serta penjelasan kesalahan URL membantu pengguna belajar tanpa harus memahami kode sejak awal.

Enam belas unit test dan empat skrip browser (alur dasar, pematangan fitur, responsif, dan pemula) telah diuji. Penyimpanan masih di browser, bukan database daring.

---

# Pembaruan LokaSEO — pematangan fitur

## Yang bisa dicoba di preview

1. Buka tombol **Pengaturan proyek** (ikon pengaturan di kanan atas), lalu ubah nama, domain, atau wilayah. Data audit dan konten tetap ada.
2. Hapus proyek melalui pengaturan. Anda harus mengetik nama proyek yang sama; proyek terakhir tidak boleh dihapus. Tersedia tombol cadangan sebelum menghapus.
3. Buka **Kalender konten**, tambahkan rencana, lalu gunakan ikon pensil untuk mengubah judul, kata kunci, tanggal, dan status.
4. Pilih **Bulanan** untuk kalender Senin–Minggu. Klik tanda tambah pada tanggal, gunakan pemilih bulan, atau tombol bulan sebelumnya/berikutnya. Pada ponsel tampil agenda bulanan.
5. Gunakan filter **Lewat jadwal** untuk rencana yang belum terbit dan tanggalnya telah berlalu. Filter status dan pencarian juga berlaku pada kalender bulanan.
6. Hapus konten lalu tekan **Urungkan hapus**. Pemulihan ini berlaku untuk satu penghapusan terakhir selama sesi berjalan, bukan riwayat permanen.
7. Gunakan **Cari semua** atau Ctrl/Cmd+K untuk mencari proyek, judul, atau kata kunci di seluruh ruang kerja. Klik hasil konten untuk membuka brief pada proyek yang benar.
8. Pada ponsel, gunakan enam menu navigasi, pilihan proyek, kartu konten, dan tombol panduan yang kini langsung terlihat.

## Perbaikan validasi

- Tanggal harus nyata, termasuk aturan tahun kabisat; tahun dibatasi 1900–2100.
- Nama proyek dan judul konten tidak boleh hanya spasi.
- Cadangan diperiksa konsistensi ID, proyek aktif, daftar checklist, dan hitungan audit.
- Data lokal rusak tidak ditimpa otomatis. Tersedia unduhan data asli untuk pemulihan manual.
- Impor yang gagal tidak mengganti proyek yang sedang dipakai.
- Kondisi saat semua konten sudah terbit tidak lagi menampilkan area kosong tanpa penjelasan.

## Hasil pengujian

TypeScript modul, build produksi, 13 unit test, uji browser alur dasar, uji browser fitur baru, dan pemeriksaan lebar responsif semuanya lulus. Tidak ditemukan exception JavaScript pada alur yang diuji. Skrip dapat dijalankan ulang dari `package.json`.

## Batasan yang belum berubah

Data tetap di browser perangkat dan belum tersinkron ke database OpenSEO. Tidak ada kolaborasi waktu nyata atau jaminan keamanan penulisan bersamaan dari beberapa tab; gunakan satu tab untuk mengedit dan unduh cadangan rutin. Build dan integrasi backend penuh belum terverifikasi. Modul audit tetap memakai HTML yang ditempel, bukan crawling URL.

## Rekomendasi tahap berikutnya (belum diimplementasikan)

Prioritas pertama adalah penyimpanan database dan autentikasi self-hosted agar data tidak bergantung pada satu browser. Setelah itu, riwayat audit beserta perbandingan temuan akan lebih berguna untuk menilai hasil perbaikan. Pratinjau hasil pencarian dan generator JSON-LD bisnis lokal dapat ditambahkan sebagai alat pendukung tanpa API berbayar.
