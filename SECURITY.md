# Keamanan

LokaSEO masih dalam pengembangan. Modul mandiri telah diuji secara terarah;
seluruh backend upstream belum mendapat verifikasi end-to-end. Tidak ada jaminan
bebas kerentanan atau SLA security release.

## Melaporkan kerentanan

Gunakan **GitHub → Security → Report a vulnerability** bila pemilik repository
sudah mengaktifkan private vulnerability reporting. Bila belum tersedia, hubungi
maintainer melalui kanal privat yang tercantum pada profilnya. Jangan membuka
issue publik dengan API key, data pribadi, atau detail eksploit sebelum koordinasi.

Sertakan commit/version, komponen terdampak, langkah reproduksi dengan data palsu,
dampak, serta lingkungan pengujian. Jangan menguji sistem pihak lain tanpa izin.

## Sebelum hosting publik

- HTTPS, autentikasi/proteksi akses, dan rate limit di reverse proxy.
- Jangan expose Vite dev server atau mode upstream `local_noauth` ke internet.
- Jangan mencatat body atau header yang memuat credential.
- Gunakan `LOKA_PUBLIC_ORIGIN` untuk server mandiri pada domain sendiri.
- Jalankan audit dependency; tinjau temuan dan peer warning upstream.

[Laporan audit 12 Oktober 2026](docs/lokaseo/security-audit.md) menjelaskan perbaikan,
dua advisory yang saat itu belum berpatch, dan batas pengujian. Key AI hanya
berada di memori sesi aplikasi, tetapi tetap transit lewat server dan provider.
