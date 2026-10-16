# AI opsional di LokaSEO

## Mulai dari aplikasi

1. Buka menu **AI & token**. Keadaan awal selalu **Tanpa AI**.
2. Pilih **Koneksi & cadangan**.
3. Isi nama koneksi, penyedia, nama model, dan API key. Jangan masukkan key ke chat atau kolom topik.
4. Tambahkan koneksi lain jika ingin cadangan. Maksimal lima koneksi, termasuk beberapa model/key dari penyedia yang sama.
5. Gunakan panah naik/turun untuk mengatur urutan. Kotak centang per koneksi menentukan apakah koneksi boleh dipakai.
6. Aktifkan AI, buka **Asisten**, pilih jenis bantuan, lalu isi topik. Periksa bagian **Data apa yang dikirim?**.
7. Klik **Buat dengan AI**. Menyimpan key atau mengaktifkan mode AI saja tidak membuat permintaan berbayar.
8. Lihat hasil, jalur percobaan, dan **Penggunaan token**. Salin atau unduh jawaban setelah memeriksa faktanya.

Fitur AI: ide konten, brief artikel, dan rekomendasi berdasarkan catatan audit. Tombol **Perkaya brief dengan AI (opsional)** pada brief manual menyiapkan topik tanpa langsung mengirimnya. Catatan audit juga hanya dimasukkan jika pengguna menekan tombolnya. Jawaban tidak otomatis diterapkan ke proyek atau diterbitkan.

## Penyedia dan model

Didukung: OpenAI, OpenRouter, DeepSeek, dan Groq melalui format Chat Completions kompatibel OpenAI. Endpoint HTTPS dipilih di server dan tidak bisa diganti dari browser. Redirect diblokir agar header API key tidak mengikuti lokasi lain.

Nama model bisa diisi sendiri. Contoh model dalam formulir bukan jaminan ketersediaan, kuota, atau harga. Pastikan model aktif di akun penyedia. Model yang tidak menerima `max_tokens`, pesan system, atau respons teks Chat Completions bisa ditolak dan memicu koneksi cadangan.

Tidak ada langganan aplikasi LokaSEO; biaya API, penyimpanan, dan server dibayar langsung sesuai layanan yang digunakan.

## Cara kerja koneksi cadangan

- Hanya koneksi aktif yang dicoba, berurutan dari paling atas.
- Setiap koneksi dicoba satu kali. Hentikan rantai setelah respons teks berhasil.
- Key ditolak, kuota habis, HTTP 429, kesalahan model, gangguan penyedia, jaringan, respons tidak valid/kosong, atau timeout memicu koneksi berikutnya.
- Batas waktu per percobaan adalah 20 detik; lima koneksi dapat memerlukan sekitar 100 detik.
- Pembatalan pengguna menghentikan permintaan server dan tidak menjadwalkan cadangan berikutnya. Penyedia mungkin telah memproses atau menagih percobaan sebelum pembatalan/timeout diterima.
- Server membatasi delapan permintaan bersamaan per proses, body 64 KiB, dan respons penyedia 1 MB. Kelebihan beban menghasilkan pesan untuk mencoba kembali.

## Key dan privasi

Key hanya berada dalam state React pada tab aktif dan memori server selama permintaan. LokaSEO tidak memasukkannya ke localStorage, sessionStorage, riwayat token, ekspor CSV, atau cadangan proyek. Reload, menutup tab, atau **Lupakan semua key** menghapus koneksi sesi. Saat reload, mode kembali tanpa AI.

Key harus melewati server yang menjalankan LokaSEO agar server bisa memanggil penyedia. Karena itu, gunakan instance yang dipercaya. Untuk publik wajib gunakan HTTPS dan autentikasi pada reverse proxy/Cloudflare Access. Mode key-sesi tidak melindungi dari operator server yang jahat, ekstensi browser berbahaya, atau perangkat yang disusupi. Kode aplikasi tidak mencatat body permintaan; jangan mengaktifkan perekaman body/header pada proxy atau sistem logging deployment Anda.

Konteks yang dikirim: nama usaha, wilayah, domain, topik, dan catatan yang terlihat. Seluruh proyek dan HTML mentah tidak dikirim otomatis. Penyedia cadangan menerima konteks yang sama. Kebijakan retensi penyedia berlaku. Jangan masukkan data pribadi pelanggan atau rahasia ke prompt.

## Dashboard token

Riwayat berisi waktu, label koneksi, penyedia, model, jenis tugas, status, kode kesalahan generik, durasi, token input/output/total, dan penanda cadangan. Tidak menyimpan prompt, jawaban, atau API key.

- Angka berasal dari `usage.prompt_tokens`, `completion_tokens`, dan `total_tokens` respons penyedia. Jika total tidak diberikan tetapi input serta output ada, total dihitung dari keduanya.
- Jika angka tidak dilaporkan, statusnya **Tidak dilaporkan**, bukan nol. Kartu ringkasan hanya menjumlahkan angka yang diketahui.
- Percobaan yang gagal tetapi mengembalikan usage tetap dihitung.
- Jika browser menutup tab, membatalkan, atau kehilangan koneksi sebelum laporan server diterima, riwayat percobaan tersebut dapat hilang. Jangan menganggap total ini sebagai tagihan lengkap.
- Filter rentang 7/30 hari atau semua, penyedia, dan status; ekspor CSV mengikuti filter.
- Maksimal 1.000 percobaan terakhir, tersimpan pada browser tersebut. Penambahan riwayat digabung dan disinkronkan antartab pada origin/browser yang sama menggunakan Web Locks. Tidak ada sinkronisasi antarperangkat, riwayat tidak masuk cadangan proyek, dan tidak mengambil pemakaian dari aplikasi lain.
- Tidak ada perkiraan biaya rupiah karena harga, cache, reasoning token, dan kebijakan billing model berbeda. Periksa dashboard penyedia untuk angka tagihan resmi.

## Menjalankan dengan server

Pengembangan:

```sh
pnpm dev:loka
```

Build dan server mandiri:

```sh
pnpm build:loka
pnpm start:loka
```

Server produksi Node (`studio/serve.ts`) melayani build dan API pada origin yang sama; default port 3000, bind `0.0.0.0`. Gunakan `PORT` untuk menggantinya. Build statis yang diunggah ke hosting statis tanpa API tetap menjalankan fitur manual, tetapi **tidak bisa memanggil AI**. Server produksi tidak memerlukan konfigurasi key di environment karena key berasal dari sesi pengguna.

Server mandiri belum memiliki login bawaan; jangan jadikan instance publik tanpa perlindungan akses. Origin check dan pembatasan concurrency bukan pengganti autentikasi atau rate limit jaringan. Rute adapter TanStack `/api/loka-ai/generate` juga disediakan untuk fork penuh, memakai resolver autentikasi upstream. Route tree telah diregenerasi. Deployment penuh Cloudflare tetap belum diuji.

## Verifikasi yang dilakukan

- TypeScript modul dan build produksi lulus.
- Setelah audit keamanan: 50 unit/integration test lulus, termasuk keempat adapter, fallback HTTP 401/402/429/503/400, timeout, pembatalan, respons rusak, token tidak diketahui, validasi body, dan penolakan origin asing.
- Lima skrip browser fitur dan satu skrip regresi keamanan lulus pada build produksi: alur dasar, pematangan fitur, responsif, pemula, serta AI.
- Uji AI browser menggunakan gateway yang disimulasikan; tes service memakai fetch mock. Key pengujian adalah string palsu. Tidak ada panggilan AI berbayar atau validasi dengan API key nyata.
- Uji browser memastikan key/prompt tidak masuk storage atau cadangan, key hilang setelah reload, UI fallback berfungsi, dan tampilan AI tidak overflow pada 320/390/768/1440 piksel.

```sh
pnpm check:loka
pnpm test:loka
# Server harus aktif pada port 3000:
pnpm test:loka:ai
```

## Penguatan keamanan — 12 Oktober 2026

- Server produksi menolak host yang tidak dikenal. Untuk domain sendiri, set `LOKA_PUBLIC_ORIGIN=https://seo.domain-anda.example` (ganti dengan domain Anda, tanpa path atau slash akhir). Loopback dan host preview Arena sesi berjalan dikenali otomatis. Ini **bukan** mekanisme login.
- Gunakan HTTPS di luar localhost; API key melewati server Anda. Jangan mencatat request body atau header Authorization pada reverse proxy/APM. Jangan expose Vite/dev server ke publik.
- Body JSON maksimum 64 KiB dengan tenggat absolut 5 detik; maksimal 32 pembaca body dan 8 panggilan AI bersamaan. Server mandiri membatasi 30 permintaan per menit per alamat socket. Di belakang reverse proxy, beberapa pengguna mungkin berbagi batas ini; gunakan rate limit/akses di ingress. Header `X-Forwarded-For` tidak dipercaya begitu saja.
- CSP membatasi skrip dan koneksi ke origin sendiri. Di luar Arena, framing default hanya `self`. Preview Arena mengizinkan embedding agar preview tetap bekerja; untuk deployment sendiri, tentukan allowlist frame bila diperlukan lewat `LOKA_FRAME_ANCESTORS`.
- Konflik proyek antartab menghentikan penyimpanan tab usang. Ekspor perubahan tab tersebut sebelum **Muat ulang data terbaru**. Reload juga menghapus key sesi AI.
- Browser tanpa Web Locks tidak menulis diam-diam: perubahan tetap di memori dan muncul peringatan untuk mengekspor cadangan. Pakai browser terbaru melalui localhost atau HTTPS.
- Jika provider memberi `finish_reason=length`, hasil ditandai terpotong tanpa memanggil cadangan yang berpotensi menambah biaya. HTTP 5xx menampilkan ketidakpastian token, bukan menganggap pemakaian nol.

Lihat [laporan audit](./security-audit.md) untuk bukti, dua advisory dependency yang masih terbuka, dan batas pengujian.
