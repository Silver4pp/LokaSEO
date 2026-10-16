# `desktop/` — aplikasi Windows LokaSEO (antarmuka di peramban)

Server Python kecil yang menyajikan antarmuka `loka-release/` dan menyediakan satu
titik masuk AI. Hanya memakai pustaka standar Python, sehingga paket aplikasi tetap
ringan dan tidak menambah dependency baru ke proyek.

Paket sasaran saat ini: **Windows**. Kode servernya lintas sistem sehingga tetap dapat
dijalankan dari source di Linux dan macOS.

```
desktop/
  run.py                    titik masuk (source dan PyInstaller)
  assets/                   ikon (.png, .ico) dan manifest Windows (DPI, asInvoker)
  alat/                     membangun .exe dan membuat paket rilis — bukan bagian aplikasi
    build-windows.ps1         perintah tunggal: build antarmuka, uji, bikin .exe, paket zip
    lokaseo.spec              berkas PyInstaller (dua target: berjendela dan konsol)
    version_info.txt          sumber daya versi Windows (dipakai EXE)
    buat-paket-rilis.py       membuat tiga zip bernama tetap dari satu .exe
  lokaseo_desktop/
    config.py               alamat penyedia, batas, prompt
    validation.py           skema permintaan (padanan aiRequestSchema)
    ai.py                   pemanggilan penyedia + urutan cadangan
    security.py             Host/Origin, header keamanan, pembacaan body
    server.py               penyaji statis + endpoint AI
    tray.py                 ikon tray: buka antarmuka dan hentikan aplikasi
    paths.py                folder data, log, pencarian berkas build dan aset
    app.py                  argumen, pemilihan port, pembuka peramban
  tests/                    unit test (unittest, tanpa dependency)
```

Bawaan aplikasi: antarmuka dibuka di peramban, ikon tray disediakan untuk menghentikan
aplikasi, dan halaman `/hentikan` menjadi cara cadangan. Jendela aplikasi asli hanya
bila `pywebview` terpasang dan `--window native` diminta.

Aturan yang dijaga antara lain:

- Bawaan mengikat hanya ke `127.0.0.1`.
- Tanpa header CORS; permintaan lintas situs ditolak lewat Origin dan `Sec-Fetch-Site`.
- Ukuran body maksimum 64 KiB dengan tenggat 5 detik; 32 pembaca dan 8 pemanggilan
  penyedia bersamaan; 30 permintaan per menit per soket.
- Berkas statis: daftar ekstensi tetap, penolakan segmen tersembunyi, pemeriksaan
  `realpath` agar tautan simbolik keluar build tidak tersaji, batas 8 MB.
- Alamat penyedia AI dipatok di server; daftar tujuan keluar tertutup dan diuji.
- Badan galat penyedia tidak pernah dikembalikan atau dicatat.
- Manifest Windows: `asInvoker` (tanpa hak admin), sadar DPI `permonitorv2`.

Uji, termasuk menjalankan biner hasil build:

```sh
python3 -m unittest discover -s desktop/tests -t desktop -v
```

Bila kontrak AI berubah di `src/shared/loka-ai.ts`, ubah `validation.py` bersamaan.
Panduan pemakaian untuk pengguna akhir ada di [cara-pakai-desktop.txt](../docs/lokaseo/cara-pakai-desktop.txt),
dan panduan uji Windows di [cara-uji-windows.txt](../docs/lokaseo/cara-uji-windows.txt).
Dokumentasi lengkap: [aplikasi-desktop.md](../docs/lokaseo/aplikasi-desktop.md).
