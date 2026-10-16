# Asal Proyek, Sumber Kode, dan Kredit

## Pernyataan asal proyek

**LokaSEO dikembangkan dari salinan kode OpenSEO, bukan dibuat seluruhnya dari nol.** Dasar kode diambil dari repositori `every-app/open-seo`, lalu dimodifikasi untuk menghadirkan ruang kerja SEO berbahasa Indonesia dengan tampilan, panduan, dan fitur tambahan.

Istilah *fork* dalam dokumentasi ini berarti pengembangan turunan dari kode sumber tersebut. Pernyataan ini tidak berarti repository LokaSEO sudah dibuat melalui tombol **Fork** di GitHub atau sudah diterbitkan secara daring.

## Sumber kode awal

| Keterangan | Sumber |
|---|---|
| Nama proyek asal | OpenSEO |
| Repositori GitHub | **https://github.com/every-app/open-seo** |
| Pemilik repositori sumber | Akun/organisasi GitHub `every-app` |
| Commit yang menjadi dasar salinan | `89e5a00717cdf049b7c2b4e29646edb3a7d4995b` |
| Kode pada commit tersebut | [Lihat versi sumber](https://github.com/every-app/open-seo/tree/89e5a00717cdf049b7c2b4e29646edb3a7d4995b) |
| Lisensi sumber | MIT; lihat [LICENSE](LICENSE) |
| Pemberitahuan hak cipta pada lisensi sumber | Copyright (c) 2026 Ben Senescu |

Commit sumber juga dicatat dalam [catatan asal salinan](docs/lokaseo/upstream-origin.txt). Keterangan ini menunjuk versi yang menjadi dasar pengembangan, bukan mengklaim bahwa salinan selalu sama dengan versi OpenSEO terbaru.

## Gagasan pengembangan LokaSEO

LokaSEO berfokus pada pengguna berbahasa Indonesia yang membutuhkan tempat untuk menata pekerjaan SEO tanpa harus langsung menggunakan layanan AI atau menyiapkan sistem server lengkap.

Arah pengembangannya:

- Menyediakan panduan awal dan penjelasan istilah untuk pemula.
- Memusatkan checklist bisnis lokal, audit HTML, kata kunci, dan rencana konten.
- Memungkinkan pekerjaan manual tanpa API key.
- Menyediakan AI sebagai pilihan dengan key milik pengguna, bukan kewajiban.
- Memperjelas penyimpanan data, keterbatasan audit, dan pencatatan token.

Arah tersebut merupakan fokus pengembangan turunan LokaSEO; bukan klaim bahwa konsep SEO, kalender konten, atau koneksi AI pertama kali diciptakan oleh proyek ini.

## Bagian yang berasal dari OpenSEO

Dasar aplikasi lengkap, struktur dan fitur backend, integrasi layanan, perangkat deployment, migrasi database, plugin, serta situs marketing upstream tetap dipertahankan dalam repository. Struktur yang diwarisi tersebar di `src/`, `deploy/`, `drizzle/`, `plugins/`, `web/`, dan direktori pendukung.

Sebagian file di area tersebut juga telah dimodifikasi untuk kebutuhan fork. Karena itu, pembagian di halaman ini menjelaskan asal komponen secara umum, bukan inventaris kepengarangan per baris. Membandingkan kode dengan commit sumber merupakan cara yang lebih tepat untuk meninjau perubahan rinci.

## Perubahan dan tambahan LokaSEO

| Area | Pengembangan dalam LokaSEO |
|---|---|
| Antarmuka | Ruang kerja berbahasa Indonesia dengan tampilan berbeda dan panduan pemula. |
| Pengelolaan proyek | Modul mandiri dengan penyimpanan browser, ekspor/pemulihan cadangan, serta perlindungan konflik antartab. |
| Pekerjaan SEO | Audit HTML yang diberikan pengguna, checklist lokal, pengelompokan kata kunci berbasis aturan, dan kalender konten. |
| AI opsional | Koneksi ke empat penyedia, urutan koneksi cadangan, key di memori sesi, dan pencatatan token yang dilaporkan penyedia. |
| Penguatan keamanan | Perbaikan server statis, validasi host/origin, batas pembacaan request, penanganan data, serta tes regresi. |
| Dokumentasi | README dan panduan LokaSEO berbahasa Indonesia, laporan audit, panduan publikasi, serta materi LinkedIn. |

Kode modul utama berada di `src/client/features/lokaseo/`, `src/server/features/loka-ai/`, `src/shared/loka-ai.ts`, dan `studio/`. Ringkasan perubahan tersedia di [riwayat pengembangan](docs/lokaseo/changelog.md).

## Referensi antarmuka dan penulisan

Selain basis kode OpenSEO, pengerjaan juga menggunakan arahan dari repositori berikut:

| Referensi | Kegunaan |
|---|---|
| [make-interfaces-feel-better](https://github.com/jakubkrehel/make-interfaces-feel-better) | Panduan perbaikan interaksi dan detail antarmuka. |
| [better-icons](https://github.com/better-auth/better-icons) | Referensi pencarian dan penggunaan ikon. |
| [anti-ai-slop-writing](https://github.com/jalaalrd/anti-ai-slop-writing) | Panduan penulisan yang lebih jelas dan tidak berlebihan. |
| [superdesign](https://github.com/superdesigndev/superdesign) | Referensi hierarki visual dan penyusunan antarmuka. |
| [humanizer](https://github.com/blader/humanizer) | Panduan penyuntingan bahasa agar lebih alami. |

Referensi tersebut tidak otomatis menjadi sumber seluruh kode aplikasi. Penyebutan nama dan tautan tidak menyiratkan afiliasi, persetujuan, atau dukungan dari pemiliknya. Ketentuan setiap referensi dan dependency tetap mengikuti lisensinya masing-masing.

## Lisensi dan atribusi

- Pertahankan file [LICENSE](LICENSE) serta pemberitahuan hak cipta sumber.
- Teks lisensi MIT asli tetap dipertahankan dalam bahasa Inggris. Penjelasan bahasa Indonesia pada halaman ini tidak menggantikan teks lisensi.
- Jangan menyatakan seluruh kode LokaSEO dibuat dari nol atau menghapus atribusi OpenSEO saat mendistribusikannya.
- Hak atas nama, merek, dan komponen pihak ketiga tidak otomatis dialihkan oleh lisensi kode.

## Cara mendapatkan kode sumber awal secara terpisah

Jika ingin mempelajari atau membandingkan versi sebelum perubahan LokaSEO, jalankan di folder lain:

```sh
git clone https://github.com/every-app/open-seo.git open-seo-sumber
cd open-seo-sumber
git switch --detach 89e5a00717cdf049b7c2b4e29646edb3a7d4995b
```

Perintah terakhir membuka commit sumber dalam keadaan *detached HEAD*, cocok untuk meninjau versi tersebut. Untuk mengembangkannya lebih lanjut, buat cabang baru terlebih dahulu. Ini petunjuk pengambilan sumber; tidak menjalankan atau men-deploy aplikasi upstream.

## Teks atribusi singkat untuk publikasi

> LokaSEO merupakan proyek turunan dari OpenSEO (https://github.com/every-app/open-seo), yang berlisensi MIT. Pengembangannya berfokus pada ruang kerja SEO berbahasa Indonesia, panduan pemula, fitur manual, serta AI opsional dengan key milik pengguna. Kode dasar dan atribusi OpenSEO tetap dipertahankan.
