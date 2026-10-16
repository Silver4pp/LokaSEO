# LokaSEO — laporan bug hunting & security hunting

**Tanggal:** 12 Oktober 2026  
**Target:** fork lokal OpenSEO/LokaSEO dan build mandiri yang dijalankan di workspace.  
**Hasil:** sejumlah bug berhasil direproduksi dan diperbaiki. Build terbaru sudah diuji ulang. **Ini bukan sertifikasi bahwa seluruh fork bebas kerentanan atau siap dipublikasikan tanpa konfigurasi keamanan.**

## Ringkasan

- Lima masalah direproduksi sebelum perbaikan: kehilangan perubahan antartab, robots tidak terbaca benar, symbolic link keluar folder build, penerimaan Host/Origin arbitrer yang cocok, serta unggahan lambat yang menghabiskan slot API.
- Peninjauan kode menghasilkan perbaikan tambahan pada penggabungan riwayat token, ekspor CSV, penanda jawaban AI terpotong, ketidakpastian token saat HTTP 5xx, serta batas input.
- Audit dependency utama: **3 critical / 7 high / 2 moderate → 0 critical / 1 high / 1 moderate**. Dua advisory tersisa belum memiliki versi perbaikan menurut hasil registry saat audit.
- Audit lockfile situs marketing `web/`: **2 high → 0 temuan** pada audit ulang. Build situs marketing tidak diuji ulang.
- Verifikasi akhir: **50 unit/integration test**, **26 tes keamanan upstream terpilih**, **6 skrip browser**, TypeScript lingkup modul, dan build produksi lulus.
- Tidak menggunakan API key nyata, tidak membuat panggilan provider berbayar, dan tidak menguji sistem pihak lain.

## Temuan dan tindakan

Tingkat dampak di bawah merupakan penilaian praktis, bukan skor CVSS. Bug integritas data tidak disamakan dengan eksploitasi akun atau server.

| ID  | Temuan                                                                              | Dampak / kondisi                                                                                                                                                                                             | Status                                                                                                                                                                                                                                                                                                |
| --- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F01 | Tab usang menimpa perubahan proyek dari tab lain                                    | **Tinggi untuk integritas data.** Nama proyek yang diubah di tab A kembali menjadi nama lama setelah tab B mengubah checklist.                                                                               | **Diperbaiki dan diuji ulang.** Penulisan memakai Web Locks dan pemeriksaan snapshot. Tab berkonflik berhenti menyimpan, memberi peringatan, serta menyediakan ekspor dan reload dengan konfirmasi. Membuka tab baru saja tidak menulis ulang data.                                                   |
| F02 | Riwayat token menggunakan pola overwrite dari state tab masing-masing               | **Sedang.** Ditemukan lewat peninjauan kode; pola tersebut dapat menghilangkan catatan tab lain. Baseline kehilangan riwayat tidak direproduksi terpisah.                                                    | **Diperbaiki.** Append membaca riwayat terbaru di bawah lock, kemudian menggabungkannya. Pengujian dua permintaan serentak mempertahankan dua catatan dan 240 token simulasi.                                                                                                                         |
| F03 | Server statis mengikuti symlink ke luar folder build                                | **Sedang, bersyarat.** Membutuhkan kemampuan menaruh/mengubah symlink di folder build; bukan bukti bahwa pengguna HTTP dapat membuatnya. Probe membaca sentinel buatan, bukan rahasia.                       | **Diperbaiki.** Pemeriksaan realpath, containment, jenis file, batas ukuran, dan penolakan dotfile. Symlink `.css` ke sentinel di luar build kini 404. Folder build tetap harus tidak dapat ditulis pihak tak tepercaya.                                                                              |
| F04 | Origin hanya dibandingkan dengan Host yang disuplai pemanggil                       | **Sedang, defense-in-depth.** Host/Origin `untrusted.example` yang cocok lolos guard ke validasi body. Ini kekurangan validasi host terhadap skenario rebinding, bukan bukti pencurian key atau bypass akun. | **Diperbaiki.** Allowlist loopback, host preview sesi, dan origin HTTPS yang dikonfigurasi. Host asing pada server produksi kini 421; middleware API menolak dengan 403. Origin/host checking tetap bukan autentikasi.                                                                                |
| F05 | Body yang tidak selesai memakai slot generasi AI                                    | **Sedang, ketersediaan.** Delapan request dengan body belum selesai membuat request kesembilan mendapat 429 tanpa satu pun panggilan provider.                                                               | **Diperbaiki/ditahan.** Slot pembaca terpisah dari slot provider, tenggat body 5 detik, batas 64 KiB, serta rate limit socket pada server mandiri. Probe kesembilan kini mencapai validasi body (400). Tes deadline mendapat 408 tanpa panggilan AI. Ini tidak menggantikan proteksi DDoS di ingress. |
| F06 | Audit mengabaikan `robots=none` dan tag robots tambahan                             | **Rendah, ketepatan audit.** Kedua kasus semula menghasilkan `noindex=false`.                                                                                                                                | **Diperbaiki.** Semua meta robots/googlebot ditinjau; `none` dikenali sebagai pemblokiran indeks. Kasus none, index saja, dan index+noindex lulus regresi browser.                                                                                                                                    |
| F07 | Ekspor CSV belum menetralkan formula yang didahului spasi/control character         | **Rendah–sedang, bersyarat pada aplikasi spreadsheet.** Ditemukan dari aturan escaping; eksekusi formula pada Excel/LibreOffice tidak diuji.                                                                 | **Diperkuat dan diuji di tingkat output.** Tambahan prefix aman untuk formula dengan whitespace, BOM, atau control character. Jangan menganggap ini bukti pengujian semua perilaku spreadsheet.                                                                                                       |
| F08 | Jawaban provider dengan `finish_reason=length` tidak dibedakan dari jawaban lengkap | **Rendah, kualitas hasil/biaya.** Jawaban dapat terpotong karena batas token.                                                                                                                                | **Diperbaiki.** Status khusus ditampilkan; tidak memanggil cadangan otomatis setelah respons sukses terpotong. Tes memastikan hanya satu panggilan provider mock.                                                                                                                                     |
| F09 | HTTP 5xx tidak menyalakan indikator ketidakpastian pemakaian                        | **Rendah–sedang, pelaporan.** Request mungkin sempat diproses sebelum respons server gagal.                                                                                                                  | **Diperbaiki.** UI mengingatkan bahwa token permintaan tidak tercakup dalam total terlapor. Tidak mengarang angka nol atau perkiraan biaya.                                                                                                                                                           |
| F10 | Advisory dependency pada root dan situs marketing                                   | Severity mengikuti registry; **belum berarti eksploit aplikasi terbukti**. Beberapa jalur merupakan tooling atau fitur upstream yang tidak digunakan server mandiri.                                         | Versi berpatch diperbarui; dua advisory root masih terbuka, rinciannya di bawah.                                                                                                                                                                                                                      |

### Penguatan tambahan

- CSP produksi membatasi script dan koneksi ke origin sendiri; menambahkan `nosniff`, `no-referrer`, dan pembatasan izin browser.
- Di luar Arena, `frame-ancestors` default hanya `self`. Pada preview Arena pembatasan framing ini tidak diterapkan agar embedding preview bekerja. Deployment sendiri perlu kebijakan frame sesuai kebutuhan.
- ID proyek/konten dan panjang daftar checklist dibatasi pada validasi cadangan.
- Adapter API TanStack memakai pembacaan body berbatas ukuran/waktu dan memisahkan pembacaan dari slot provider. Helper-nya diuji; deployment adapter penuh belum diuji end-to-end.
- Tidak menyimpan API key/prompt/jawaban dalam riwayat token. Pengujian browser dengan key palsu memeriksa localStorage, sessionStorage, backup, dan penghapusan key setelah reload.

## Bukti sebelum dan sesudah

| Probe                                  | Sebelum                                                     | Sesudah                                                       |
| -------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------- |
| Host + Origin asing yang cocok         | 400, berarti melewati guard awal                            | 421 pada server produksi; 403 pada unit test middleware       |
| Symlink file ke luar build             | 200, isi sentinel terbaca                                   | 404; tes menggunakan ekstensi `.css` yang normalnya diizinkan |
| Rename tab A lalu checklist tab B      | Nama baru hilang                                            | Nama baru tetap; tab B mendapat peringatan                    |
| `robots=none`                          | `noindex=false`                                             | `noindex=true`                                                |
| Meta robots `index` lalu `noindex`     | `noindex=false`                                             | `noindex=true`                                                |
| 8 unggahan tidak selesai, request ke-9 | 429                                                         | 400 validasi body; slot provider tidak terpakai               |
| HTML berisi script, onerror, iframe    | Tidak dieksekusi; tidak ada beacon pada Chromium yang diuji | Tetap tidak dieksekusi/tidak ada beacon                       |
| Dua hasil AI bersamaan pada dua tab    | Pola overwrite ditemukan lewat review                       | Dua catatan tersimpan; total mock 240 token                   |

Artefak mentah dan script baseline lama sudah dihapus dari mesin pengerjaan pada 12 Oktober 2026 dan tidak pernah disertakan dalam source publik. Ringkasan di atas mempertahankan hasil audit historis. Tes yang dapat diulang tersedia di `tests/lokaseo/security/`; hasil browser terbaru ditulis ke `test-results/security/` (diabaikan Git).

## Dependency: perubahan dan risiko yang tersisa

Paket dengan versi berpatch dinaikkan melalui manifest/override dan lockfile: `@modelcontextprotocol/client`, `@modelcontextprotocol/sdk`, `seroval`, `source-map-js`, `proxy-addr`, `sharp`, `shell-quote`, dan `smol-toml`. Pengecualian minimum release age ditambahkan untuk versi perbaikan keamanan yang ditargetkan. Situs marketing juga mendapat pembaruan lockfile terpisah.

| Paket tersisa      | Severity registry | Jalur tercatat                               | Keadaan                                                                                                                                                             |
| ------------------ | ----------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `braces@3.0.3`     | High              | `alchemy → fast-glob → micromatch → braces`  | [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm), stack exhaustion pada pola bersarang. Registry belum menyediakan patched version.         |
| `sprintf-js@1.1.3` | Moderate          | `@cloudflare/think → just-bash → sprintf-js` | [GHSA-hp3w-g68c-fv3c](https://github.com/advisories/GHSA-hp3w-g68c-fv3c), DoS melalui precision specifier tak terbatas. Registry belum menyediakan patched version. |

Kedua jalur bukan bagian dari alur HTTP server mandiri yang ditinjau. Itu **bukan** jaminan aman untuk semua fitur upstream. Jangan memberikan pola glob/format tak tepercaya ke jalur tersebut; evaluasi penghapusan/substitusi dependency bila fitur upstream terkait akan diaktifkan. Audit ulang ketika patch tersedia.

Instalasi masih melaporkan peer warning pada paket upstream, termasuk `agents` yang mengharapkan MCP client 2.0.0 sedangkan versi security fix yang digunakan 2.2.0. Ada pula warning Vite/Drizzle/AI SDK. Modul mandiri lulus tes, tetapi kompatibilitas penuh upstream setelah perubahan dependency **belum dibuktikan**. Jangan menurunkan versi security fix hanya untuk menghilangkan warning tanpa menilai advisory.

## Verifikasi yang benar-benar dijalankan

1. TypeScript terarah: `tsc --noEmit -p studio/tsconfig.json` — **lulus**.
2. Build Vite produksi modul mandiri — **lulus**, 1.754 modul.
3. Unit/integration modul: **50 tes, 7 berkas, lulus**. Mencakup provider mock/fallback/cancel, body deadline dan ukuran, rate limiting, origin/host, static containment, CSV, validasi, serta kebijakan monetisasi.
4. Upstream terpilih: **26 tes, 4 berkas, lulus** untuk URL policy, URL utilities, klasifikasi error access token, dan MCP public origin. Ini bukan seluruh suite backend.
5. Browser Chromium: enam skrip lulus — alur dasar, project/content/calendar, responsif 320–1440 px, pemula, AI mock, dan regresi keamanan. Tidak ada exception browser dalam pengujian tersebut.
6. Audit dependency ulang root dan `web/` — hasil sebagaimana tabel di atas.
7. Scan pola credential pada 22 berkas modul/service/studio tidak menemukan kandidat untuk pola yang diperiksa. Ini pemeriksaan heuristik terbatas, bukan pembuktian bahwa semua format rahasia tidak ada.
8. Host preview yang sah tetap mendapat HTTP 200; preview menggunakan server produksi, bukan Vite dev server.

### Mengulang pengujian

Dari root repo, setelah install dependency dan menyalakan `start:loka` pada port 3000:

```sh
pnpm check:loka
pnpm test:loka:security
pnpm exec vitest run --config tests/lokaseo/security/legacy-vitest.config.ts
node tests/lokaseo/browser/smoke.mjs
node tests/lokaseo/browser/polish-smoke.mjs
node tests/lokaseo/browser/responsive-smoke.mjs
node tests/lokaseo/browser/beginner-smoke.mjs
node tests/lokaseo/browser/ai-smoke.mjs
pnpm audit --json
pnpm --dir web audit --json
```

Audit root masih mengembalikan exit code nonzero karena dua advisory tersisa. Jangan menyamakan itu dengan kegagalan tes regresi.

## Batas audit dan keputusan deployment

**Belum diverifikasi:** provider dengan key nyata, kesesuaian tagihan, end-to-end Cloudflare Access/Docker/database/MCP/crawler/Google Search Console, seluruh otorisasi multi-tenant upstream, seluruh repo typecheck, beban besar, semua browser, dan semua aplikasi spreadsheet. Situs marketing hanya diaudit dependency-nya. Tidak ada pemindaian ofensif terhadap target eksternal.

- Server mandiri tetap tidak memiliki login bawaan. Sebelum dipublikasikan, gunakan HTTPS dan proteksi akses/rate limit di reverse proxy; jangan mengekspos Vite atau `local_noauth` upstream ke internet.
- Set `LOKA_PUBLIC_ORIGIN` ke origin HTTPS domain sendiri. Header Host/Origin dan CSP bukan pengganti autentikasi.
- Jangan log body/header yang memuat key pada proxy, APM, atau gateway. Key hanya disimpan di memori aplikasi, tetapi tetap transit melalui server dan provider; hal itu bukan enkripsi end-to-end yang menyembunyikan key dari operator server.
- Gunakan browser modern melalui localhost atau HTTPS. Bila Web Locks tidak tersedia atau storage penuh/diblokir, aplikasi memberi peringatan dan tidak mengklaim perubahan sudah tersimpan; ekspor cadangan sebelum menutup tab.
- Konflik proyek tidak digabung otomatis. Ekspor perubahan tab usang sebelum memuat ulang. Riwayat token digabung lintas tab, tetapi tidak lintas perangkat dan tetap dibatasi 1.000 percobaan.
- Hilangnya koneksi atau penutupan tab tetap dapat membuat usage tidak tercatat. Dashboard provider adalah acuan tagihan.
- Dependency advisory yang belum berpatch dan peer warning upstream adalah pekerjaan terbuka sebelum mengaktifkan seluruh fork di produksi.

**Kesimpulan:** masalah yang direproduksi pada modul mandiri telah ditangani dan regresinya lulus. Versi terbaru lebih kuat untuk penggunaan lokal/preview. Tidak ada dasar untuk menyatakan seluruh fork “100% aman” atau semua jalur produksi sudah lolos pentest.
