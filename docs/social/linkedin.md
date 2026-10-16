# Materi LinkedIn — LokaSEO

Draf berikut ditulis dari sudut pandang pemilik proyek. Tambahkan URL repository
Anda setelah repo benar-benar diterbitkan. Jangan memakai URL preview sementara
sebagai demo publik tanpa proteksi akses yang sesuai.

## Post peluncuran

Saya sedang mengembangkan LokaSEO, ruang kerja SEO berbahasa Indonesia yang bisa digunakan tanpa harus mengaktifkan AI.

Proyek ini merupakan pengembangan turunan dari kode OpenSEO berlisensi MIT, bukan aplikasi yang seluruhnya saya buat dari nol. Sumber kode awalnya: https://github.com/every-app/open-seo. Fokus pengembangannya ada pada pengalaman pengguna: panduan untuk pemula, checklist SEO lokal, audit HTML, pengelompokan kata kunci, dan kalender konten dalam satu tempat.

Kalau membutuhkan bantuan AI, pengguna bisa memasukkan API key sendiri dari OpenAI, OpenRouter, DeepSeek, atau Groq. Ada koneksi cadangan otomatis dan dashboard token. Key hanya berada di memori sesi tab dan hilang setelah reload—namun tetap melewati server dan provider yang digunakan.

Bagian yang cukup banyak saya perhatikan adalah keandalan data. Dalam pengujian, perubahan proyek dari satu tab ternyata bisa tertimpa oleh tab lain. Alur penyimpanannya kini dilengkapi penguncian dan deteksi konflik. Server, penanganan request lambat, serta pencatatan token juga mendapat perbaikan.

Modul mandirinya sudah melewati tes lokal. Pengujian AI masih memakai simulasi, dan backend penuh belum saya anggap siap produksi. LokaSEO juga tidak menjanjikan kenaikan ranking: auditnya memeriksa HTML yang diberikan, bukan seluruh kondisi situs.

Saya ingin mendapatkan masukan, terutama dari pemilik usaha kecil dan pengelola konten: bagian pekerjaan SEO mana yang paling membingungkan ketika baru mulai?

#OpenSource #SEO #WebDevelopment #BuildInPublic

**Tambahkan di akhir post:** tautan repository GitHub Anda.

## Ringkasan untuk Featured / Projects

**Judul:** LokaSEO — ruang kerja SEO berbahasa Indonesia

**Deskripsi:** Fork OpenSEO berlisensi MIT dengan UI Indonesia, panduan pemula, audit HTML, checklist bisnis lokal, dan kalender konten. AI bersifat opsional: memakai key sendiri, koneksi cadangan, serta pencatatan token. Data proyek tersimpan di browser. Modul mandiri diuji lokal; deployment backend penuh belum diverifikasi.

## Ide lampiran

Gunakan `docs/assets/lokaseo-overview.png` sebagai screenshot dengan keterangan
“LokaSEO — tampilan proyek contoh”. Hindari screenshot yang berisi key, data
pelanggan, atau dashboard biaya nyata. Jangan mengklaim jumlah pengguna, performa
bisnis, atau hasil ranking yang belum diukur.

## Kredit sumber untuk deskripsi proyek

LokaSEO dikembangkan dari OpenSEO: https://github.com/every-app/open-seo.
Lisensi MIT dan atribusi sumber dipertahankan. Fokus perubahan LokaSEO ada pada
antarmuka Indonesia, panduan pemula, ruang kerja mandiri, dan AI opsional.
Rincian asal kode tersedia pada [Asal Proyek](../../ASAL-PROYEK.md).
