# Struktur dan publikasi repository

## Pembagian tanggung jawab

- `studio/`: entry point, konfigurasi, server mandiri, dan tes yang dekat dengan server.
- `src/client/features/lokaseo/`: UI dan logika workspace.
- `src/server/features/loka-ai/`, `src/shared/loka-ai.ts`: layanan AI dan kontraknya.
- `tests/lokaseo/browser/`: lima smoke test fitur.
- `tests/lokaseo/security/`: regresi browser, probe slow body, dan config tes upstream terpilih.
- `docs/lokaseo/`: panduan produk dan catatan teknis publik.
- `docs/social/`: teks pengenalan proyek, bukan dokumentasi runtime.
- `docs/assets/`: screenshot publik dengan data contoh.
- `desktop/alat/`: alat pembangun Windows — spesifikasi PyInstaller, skrip build,
  dan pembuat paket. Sengaja terpisah dari `desktop/lokaseo_desktop/`, yang berisi
  kode aplikasi, supaya pembangun tidak tercampur dengan yang dibangun.

Direktori source, migrasi, plugin, serta deployment upstream tidak dipindah secara
massal. Mempertahankan path-nya mengurangi risiko mematahkan import dan tooling.

## Yang dikeluarkan dari repo publik

Log audit, raw response audit dependency, dump hasil probe lama, snapshot
`package.before.json`/`pnpm-workspace.before.txt`, dan script baseline sekali pakai
sudah dihapus dari mesin pengerjaan pada 12 Oktober 2026. Laporan publik dan tes
regresi yang dapat diulang tetap dipertahankan.

Hasil tes berikutnya masuk `test-results/`. `.env.local` tetap lokal untuk
pengembangan, tetapi diabaikan Git dan tidak dimasukkan ke ZIP source publik.
Build, dependency terpasang, archive distribusi, credential, serta log juga
dikecualikan melalui `.gitignore`.

Workflow deployment/publishing/sourcemap upstream dipindah menjadi contoh di
`docs/maintainers/upstream-workflows/`. Workflow aktif hanya pemeriksaan LokaSEO;
tidak mengunggah sourcemap ke layanan upstream atau menerbitkan image otomatis.

## Checklist sebelum push

1. Buat repository milik sendiri; pertahankan atribusi OpenSEO, `LICENSE`, dan `ASAL-PROYEK.md`.
2. Pastikan identitas pemilik, URL repo, dan kanal kontak keamanan benar. Dokumen
   tidak mengarang URL repository atau alamat email pemilik.
3. Aktifkan private vulnerability reporting di pengaturan GitHub bila tersedia.
4. Jalankan tes sesuai README dan audit dependency ulang.
5. Periksa `git status --short`, `git diff --stat`, serta `git diff --cached`.
   Pastikan tidak ada rahasia atau data pengguna dalam file yang akan dikirim.
6. `.gitignore` tidak membersihkan file yang sudah tracked/histori lama. Jika
   rahasia pernah ter-push, rotasi terlebih dahulu lalu bersihkan histori dengan
   koordinasi semua kontributor. Perapian ini tidak menulis ulang histori Git.
7. Commit dan push hanya setelah review. Tidak ada push remote otomatis dalam
   pekerjaan ini; GitHub Actions remote belum dijalankan.

Untuk LinkedIn, gunakan [draf post](../social/linkedin.md), tambahkan tautan repo
setelah publikasi, dan lampirkan screenshot data contoh bila diinginkan.

## Catatan unggah manual

ZIP source tidak membawa 13 tautan simbolik `.claude/skills/*` yang menunjuk ke
`.agents/skills/*`, karena ZIP menyimpan berkas biasa. Jika mengunggah lewat
antarmuka GitHub, unggahan tetap berjalan, tetapi tautan tersebut akan tampak
terhapus. Untuk menghindarinya, gunakan `git clone` atau biarkan Git membuat
ulang tautan tersebut dari paket source yang dilacak Git.
