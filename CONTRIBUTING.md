# Berkontribusi ke LokaSEO

Terima kasih sudah membantu. Jelaskan masalah dan langkah reproduksi sebelum
mengusulkan perubahan besar, terutama pada backend upstream.

## Alur kerja

1. Buat branch terpisah dan jalankan modul mengikuti [README](README.md).
2. Pertahankan bahasa Indonesia dan fitur manual yang tidak bergantung pada AI.
3. Tambahkan regression test untuk bug yang diperbaiki. Unit test berdampingan
   dengan modul; tes browser LokaSEO ada di `tests/lokaseo/`.
4. Jalankan `pnpm check:loka`, `pnpm test:loka`,
   `pnpm test:loka:upstream-security`, dan `pnpm build:loka`.
5. Untuk perubahan UI/API, jalankan skrip browser terkait dengan server produksi
   lokal aktif. Jangan memakai key provider nyata dalam test otomatis.
6. Jelaskan cakupan perubahan, hasil tes, dan batas yang belum diverifikasi di PR.

## Jangan commit

API key, `.env` lokal, data pelanggan, backup workspace pengguna, log request,
output build, hasil tes, `node_modules`, dan ZIP distribusi lokal. Periksa
`git diff --cached` sebelum push. `.gitignore` tidak menghapus rahasia yang sudah
terlanjur masuk Git; cabut/rotasi credential yang bocor sebelum membersihkan histori.

Laporkan kerentanan sesuai [SECURITY.md](SECURITY.md), bukan melalui issue publik
berisi payload atau rahasia. Panduan pengembangan upstream ada di
[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md); pertahankan lisensi dan atribusinya.
