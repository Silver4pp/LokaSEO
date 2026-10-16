# Workflow upstream — referensi, tidak aktif

Workflow OpenSEO lama disimpan dengan ekstensi `.example`, di luar `.github/workflows`.
Beberapa mengacu ke registry upstream, deployment Cloudflare, atau upload sourcemap
PostHog. Menyalakannya tanpa penyesuaian tidak tepat untuk fork LokaSEO.

Workflow aktif `lokaseo-ci.yml` hanya memeriksa modul mandiri: TypeScript,
unit/integration test, tes upstream keamanan terpilih, dan build. Tidak melakukan
deployment, menerbitkan image, atau mengunggah sourcemap. Eksekusi GitHub Actions
sendiri belum diverifikasi pada repo remote.

Jika memerlukan pipeline backend penuh, tinjau contoh satu per satu, ubah tujuan
repository/registry, tetapkan izin minimum dan secrets sendiri, lalu uji di staging.
Jangan menambahkan `pull_request_target` untuk mengeksekusi kode fork dengan secrets.
