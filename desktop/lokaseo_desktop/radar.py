"""Jembatan antara aplikasi desktop LokaSEO dan modul radar (LokaRadar).

Radar adalah modul Python terpisah di `radar/`. Berkas ini menyambungkannya ke
server lokal supaya pengguna tidak perlu membuka terminal: satu tombol di
antarmuka, hasilnya muncul di peramban.

Prinsip yang dipegang sama seperti bagian lain aplikasi ini:

- **Semua data tinggal di komputer pengguna.** Folder datanya `radar/` di dalam
  folder data LokaSEO (lihat `paths.data_dir()`).
- **Tidak ada permintaan keluar selain ke alamat yang dipantau pengguna sendiri**,
  dan radar tetap menghormati `robots.txt` serta jeda per host.
- **Radar tidak wajib ada.** Bila foldernya tidak ditemukan (mis. paket tidak
  lengkap), aplikasi tetap berjalan dan antarmuka menjelaskan apa yang kurang.
- **Satu pemeriksaan pada satu waktu.** Menjalankan dua pemeriksaan sekaligus
  justru membuat permintaan menumpuk ke situs orang.
"""

import importlib.util
import logging
import os
import sys
import threading
import time
from pathlib import Path

from . import config, jadwal as _jadwal, paths

LOG = logging.getLogger("lokaseo")

# Nama variabel lingkungan yang dipakai modul radar untuk lokasi datanya.
RADAR_DATA_ENV = "LOKARADAR_DATA"
RADAR_ROOT_ENV = "LOKARADAR_ROOT"

# Hasil satu pemeriksaan bisa panjang; disimpan apa adanya untuk ditampilkan.
MAX_RIWAYAT = 50


class RadarError(RuntimeError):
    """Radar tidak bisa dipakai atau permintaan tidak sah."""


class TidakDitemukan(RadarError):
    """Sasaran yang diminta tidak ada."""


class MasukanTidakSah(RadarError):
    """Data yang dikirim antarmuka tidak bisa dipakai (mis. jenis usaha asing)."""


_MODUL: dict = {}
_CIKAL = threading.Lock()
_KUNCI_PEKERJAAN = threading.Lock()
_PEKERJAAN: dict = {
    "id": 0,
    "keadaan": "belum pernah",
    "mulai": None,
    "selesai": None,
    "ringkasan": None,
    "hasil": None,
    "galat": None,
}


def radar_root() -> Path | None:
    """Cari folder paket radar: lewat env, di dalam bundel, di repo, atau di samping .exe."""
    kandidat: list[Path] = []
    override = os.environ.get(RADAR_ROOT_ENV)
    if override:
        kandidat.append(Path(override).expanduser())
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        kandidat.append(Path(bundled) / "radar")
    modul_dir = Path(__file__).resolve().parent
    kandidat.append(modul_dir.parent / "radar")  # desktop/radar (bila diletakkan berdampingan)
    kandidat.append(modul_dir.parent.parent / "radar")  # <repo>/radar saat dijalankan dari sumber
    kandidat.append(Path(sys.executable).resolve().parent / "radar")  # di samping .exe
    kandidat.append(Path.cwd() / "radar")
    for kandidat_folder in kandidat:
        if (kandidat_folder / "lokaradar" / "__init__.py").is_file():
            return kandidat_folder
    return None


def _bisa_impor() -> bool:
    """Apakah `lokaradar` bisa diimpor langsung, mis. dari dalam bundel .exe."""
    try:
        return importlib.util.find_spec("lokaradar") is not None
    except (ImportError, ValueError):
        return False


def tersedia() -> bool:
    return radar_root() is not None or _bisa_impor()


def data_dir() -> Path:
    """Folder data radar di dalam folder data aplikasi, bukan di tempat lain."""
    override = os.environ.get(RADAR_DATA_ENV)
    arah = Path(override).expanduser() if override else paths.data_dir() / "radar"
    arah.mkdir(parents=True, exist_ok=True)
    return arah


def _modul():
    """Impor modul radar satu kali saja, dengan folder data yang sudah diatur."""
    with _CIKAL:
        if _MODUL:
            return _MODUL
        akar = radar_root()
        if akar is None and not _bisa_impor():
            raise RadarError(
                "Modul radar tidak ditemukan. Pastikan folder `radar/` ada di dalam paket "
                "aplikasi, atau setel LOKARADAR_ROOT ke foldernya."
            )
        os.environ.setdefault(RADAR_DATA_ENV, str(data_dir()))
        if akar is not None and str(akar) not in sys.path:
            sys.path.insert(0, str(akar))
        from lokaradar import config as radar_config  # noqa: PLC0415 - impor sengaja lambat
        from lokaradar import fetch as radar_fetch
        from lokaradar import peramban as radar_peramban
        from lokaradar import places as radar_places
        from lokaradar import profil as radar_profil
        from lokaradar import report as radar_report
        from lokaradar import reputasi as radar_reputasi
        from lokaradar import ringkasan as radar_ringkasan
        from lokaradar import run as radar_run
        from lokaradar import sasaran as radar_sasaran
        from lokaradar.store import Store as RadarStore

        _MODUL.update(
            {
                "config": radar_config,
                "fetch": radar_fetch,
                "peramban": radar_peramban,
                "places": radar_places,
                "profil": radar_profil,
                "report": radar_report,
                "reputasi": radar_reputasi,
                "ringkasan": radar_ringkasan,
                "run": radar_run,
                "sasaran": radar_sasaran,
                "Store": RadarStore,
                "akar": akar,
                "dari_bundel": akar is None,
            }
        )
        return _MODUL


def _store():
    return _modul()["Store"]()


# -- pembacaan ---------------------------------------------------------------
def status() -> dict:
    """Ringkasan keadaan radar untuk ditampilkan di antarmuka."""
    if not tersedia():
        return {"tersedia": False, "galat": "Modul radar tidak ditemukan."}
    try:
        modul = _modul()
    except RadarError as error:
        return {"tersedia": False, "galat": str(error)}
    with modul["Store"]() as store:
        statistik = store.stats()
        terakhir = store.get_state("terakhir_jalan")
        jumlah_tempat = len(
            [row for row in store.targets() if str(row["url"]).startswith(modul["places"].SCHEME)]
        )
    # Peramban yang benar-benar bisa dipakai mesin ini. Sejak ada jalur peramban
    # lokal, "dynamic_available()" saja tidak cukup: Scrapling bisa terpasang
    # sementara perambannya belum diunduh — dan sebaliknya, Scrapling tidak ada
    # sama sekali tetapi Microsoft Edge sudah terpasang sejak awal. Tanpa
    # pemeriksaan ini, chip di halaman radar akan menulis "permintaan biasa"
    # padahal kartu di bawahnya baru saja menyatakan peramban siap.
    peramban = "belum terunduh"
    if modul["peramban"].tersedia() or modul["fetch"].browser_ready():
        peramban = "siap"
    elif modul["fetch"].dynamic_available():
        peramban = "scrapling ada, peramban belum terunduh"
    return {
        "tersedia": True,
        "versi": _versi(modul),
        "data": str(data_dir()),
        "sasaran": statistik["sasaran"],
        "sasaran_aktif": statistik["sasaran_aktif"],
        "potret": statistik["potret"],
        "perubahan": statistik["perubahan"],
        "terakhir_jalan": terakhir,
        "sasaran_tempat": jumlah_tempat,
        "peramban": peramban,
        "kunci_places": bool(modul["places"].key_from_env() or os.environ.get("LOKARADAR_PLACES_KEY")),
        "peramban_info": modul["peramban"].ketersediaan(),
        "pekerjaan": pekerjaan(),
        "profil": _ringkas_profil(modul),
    }


def _versi(modul) -> str:
    try:
        from lokaradar import __version__  # noqa: PLC0415 - hanya untuk tampilan

        return str(__version__)
    except Exception:  # noqa: BLE001 - versi tidak penting
        return "0.1.0"


def _ringkas_profil(modul) -> dict | None:
    """Profil usaha dalam bentuk yang siap ditampilkan antarmuka."""
    profil = modul["profil"].load()
    if profil is None:
        return None
    return {
        "nama": profil.nama,
        "jenis": profil.jenis,
        "jenis_label": profil.jenis_label,
        "kota": profil.kota,
        "situs": profil.situs,
        "sumber": profil.sumber,
        "ambang_rating": profil.ambang_rating,
        "rating_penting": profil.rating_penting,
        "schema": list(profil.schema_diharapkan),
        "kata_kunci": list(profil.kata_kunci),
        "catatan": list(profil.catatan),
        "ringkas": modul["profil"].ringkas(profil),
    }


def daftar_jenis() -> list[dict]:
    """Daftar jenis usaha yang dikenal radar, untuk pilihan di antarmuka."""
    modul = _modul()
    return [
        {
            "id": kunci,
            "label": nilai.get("label", kunci),
            "min_rating": nilai.get("min_rating"),
            "rating_penting": bool(nilai.get("rating_penting")),
        }
        for kunci, nilai in modul["profil"].INDUSTRI.items()
    ]


def simpan_profil(payload: dict) -> dict:
    """Simpan profil usaha dari antarmuka.

    Dua bentuk masukan diterima:

    - **pengaturan LokaSEO** (yang dikirim halaman radar dari penyimpanan
      peramban): memuat `projects` dan `activeId`, sama seperti berkas cadangan.
      Inilah jalur utama: pilihan jenis usaha yang dibuat di awal proyek LokaSEO
      langsung menjadi kunci kerja radar.
    - **isian manual** untuk keadaan darurat (mis. proyek belum punya jenis
      usaha): `nama`, `jenis`, `kota`, `situs`.
    """
    if not isinstance(payload, dict):
        raise MasukanTidakSah("Data pengaturan tidak sah.")
    modul = _modul()
    sumber = "pengaturan LokaSEO di aplikasi desktop"
    if isinstance(payload.get("projects"), list):
        try:
            profil = modul["profil"].from_lokaseo_backup(payload, sumber=sumber)
        except ValueError as error:
            raise MasukanTidakSah(str(error)) from error
    else:
        jenis = str(payload.get("jenis", "") or "").strip()
        if jenis and jenis not in modul["profil"].INDUSTRI:
            raise MasukanTidakSah(
                "Jenis usaha tidak dikenal. Pilih salah satu jenis yang tersedia di daftar."
            )
        profil = modul["profil"].Profil(
            nama=str(payload.get("nama", "") or "").strip()[:80],
            jenis=jenis,
            kota=str(payload.get("kota", "") or "").strip()[:80],
            situs=str(payload.get("situs", "") or "").strip()[:250],
            min_rating=payload.get("min_rating"),
            sumber=str(payload.get("sumber", "") or "")[:120] or "diatur dari halaman radar",
        )
    berkas = modul["profil"].save(profil)
    LOG.info("Profil radar diperbarui dari antarmuka: jenis=%s", profil.jenis or "(belum dipilih)")
    ringkas = _ringkas_profil(modul) or {}
    ringkas["berkas"] = str(berkas)
    return ringkas


def _fakta(snapshot: dict | None) -> dict:
    if not snapshot:
        return {}
    return snapshot.get("facts") or {}


def sasaran() -> list[dict]:
    """Daftar sasaran beserta angka terakhir yang terbaca."""
    modul = _modul()
    hasil = []
    with modul["Store"]() as store:
        for target in store.targets():
            snapshot = store.latest_snapshot(int(target["id"]))
            fakta = _fakta(snapshot)
            harga = fakta.get("prices") or []
            rating = fakta.get("rating") or {}
            hasil.append(
                {
                    "id": int(target["id"]),
                    "url": target["url"],
                    "label": target["label"] or target["url"],
                    "jenis": target["kind"],
                    "aktif": bool(target["enabled"]),
                    "diperiksa_pada": snapshot.get("fetched_at") if snapshot else None,
                    "sumber": (snapshot.get("sumber") or "") if snapshot else "",
                    "catatan": (snapshot.get("catatan") or "") if snapshot else "",
                    "judul": fakta.get("title", ""),
                    "kata": fakta.get("word_count"),
                    "rating": rating.get("value"),
                    "jumlah_ulasan": rating.get("count"),
                    "harga_terendah": harga[0] if harga else None,
                    "jumlah_perubahan": len(
                        store.changes(target_id=int(target["id"]), limit=100)
                    ),
                }
            )
    return hasil


def perubahan(since: str | None = None, limit: int = 50) -> list[dict]:
    """Perubahan terakhir, terbaru lebih dulu."""
    modul = _modul()
    with modul["Store"]() as store:
        baris = store.changes(since=since, limit=limit)
    return [
        {
            "id": int(row["id"]),
            "target_id": int(row["target_id"]),
            "pada": row["detected_at"],
            "jenis": row["type"],
            "tingkat": row["severity"],
            "pesan": row["message"],
        }
        for row in baris
    ]


def papan(days: int = 30) -> dict | None:
    """Papan reputasi; None bila profil usaha belum diatur."""
    modul = _modul()
    with modul["Store"]() as store:
        profil = modul["profil"].load()
        return modul["reputasi"].board(store, days=days, profil=profil)


def ringkasan(hari: int = 7) -> dict:
    """Ringkasan pemantauan: perubahan penting di atas, pola bising dinyatakan."""
    if not tersedia():
        raise RadarError("Modul radar tidak ditemukan.")
    modul = _modul()
    with modul["Store"]() as store:
        return modul["ringkasan"].bikin(store, hari=hari)


def profil_usaha() -> dict | None:
    modul = _modul()
    profil = modul["profil"].load()
    return profil.to_dict() if profil is not None else None


def laporan_terbaru() -> dict | None:
    """Laporan Markdown terbaru beserta waktu pembuatannya."""
    modul = _modul()
    folder = modul["report"].laporan_dir() if hasattr(modul["report"], "laporan_dir") else None
    if folder is None:
        folder = modul["config"].report_dir()
    berkas = sorted(Path(folder).glob("laporan-*.md"))
    if not berkas:
        return None
    terbaru = max(berkas, key=lambda item: item.stat().st_mtime)
    return {
        "nama": terbaru.name,
        "waktu": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(terbaru.stat().st_mtime)),
        "markdown": terbaru.read_text(encoding="utf-8", errors="replace"),
    }


# -- perubahan data ----------------------------------------------------------
def tambah(url: str, label: str = "", jenis: str = "halaman") -> dict:
    modul = _modul()
    with modul["Store"]() as store:
        target = store.add_target(url, label, jenis)
    LOG.info("Sasaran radar #%s ditambahkan dari antarmuka desktop.", target["id"])
    return {"id": int(target["id"]), "url": target["url"], "label": target["label"]}


def hapus(identifier: str) -> dict:
    modul = _modul()
    try:
        with modul["Store"]() as store:
            target_id = store.remove_target(str(identifier))
    except KeyError as error:
        raise TidakDitemukan(str(error).strip("'")) from error
    return {"id": int(target_id)}


def ekspor_sasaran() -> dict:
    """Isi berkas daftar sasaran, siap diunduh pengguna."""
    modul = _modul()
    profil = profil_usaha() or {}
    with modul["Store"]() as store:
        berkas = modul["sasaran"].ekspor(store, profil=profil)
    berkas["nama_berkas"] = modul["sasaran"].nama_berkas()
    return berkas


def impor_sasaran(teks: str, nama: str = "") -> dict:
    """Gabungkan daftar sasaran dari berkas yang dipilih pengguna.

    Tidak menghapus apa pun dan tidak menghubungi situs mana pun: yang disimpan
    hanya alamatnya. Berkas yang tidak bisa dibaca dijawab dengan alasan, bukan
    dengan diam.
    """
    if not isinstance(teks, str) or not teks.strip():
        raise MasukanTidakSah("Berkas yang dipilih kosong. Pilih berkas daftar sasaran LokaRadar.")
    modul = _modul()
    ukuran = len(teks.encode("utf-8", errors="replace"))
    if ukuran > modul["sasaran"].MAKS_BITA:
        raise MasukanTidakSah(
            f"Berkas terlalu besar ({ukuran // 1024} KB). Batasnya "
            f"{modul['sasaran'].MAKS_BITA // 1000} KB."
        )
    try:
        with modul["Store"]() as store:
            hasil = modul["sasaran"].impor(store, teks, maksimum=config.RADAR_MAX_TARGETS)
    except modul["sasaran"].BerkasTidakSah as error:
        raise MasukanTidakSah(str(error)) from error
    hasil["nama_berkas"] = nama
    hasil["ringkasan"] = modul["sasaran"].ringkas(hasil)
    LOG.info(
        "Daftar sasaran diimpor dari %s: %s ditambahkan, %s sudah ada.",
        nama or "berkas pilihan pengguna",
        hasil["ditambahkan"],
        hasil["sudah_ada"],
    )
    return hasil


# -- menjalankan pemeriksaan -------------------------------------------------
def pekerjaan() -> dict:
    with _KUNCI_PEKERJAAN:
        return dict(_PEKERJAAN)


def sedang_berjalan() -> bool:
    with _KUNCI_PEKERJAAN:
        return _PEKERJAAN["keadaan"] == "berjalan"


def _lakukan_pemeriksaan(*, max_pages: int, render: str, tunggu: str | None, hanya: int | None) -> dict:
    """Pekerjaan sebenarnya. Dipisah agar bisa diganti pada pengujian."""
    modul = _modul()
    with modul["Store"]() as store:
        if getattr(store, "concurrent_pemeriksaan", False):  # pragma: no cover - penjaga
            raise RadarError("Pemeriksaan lain sedang berjalan.")
        fetcher = modul["fetch"].Fetcher(
            obey_robots=True,
            render=render,
            render_wait=tunggu,
        )
        places_key = modul["places"].key_from_env()
        with fetcher.render_session():
            hasil = modul["run"].run_once(
                store,
                fetcher,
                max_pages=max_pages,
                only_id=hanya,
                places_key=places_key,
                profil=modul["profil"].load(),
            )
        store.set_state("terakhir_jalan", hasil["selesai"])
        ringkasan = {
            "diperiksa": hasil["diperiksa"],
            "gagal": hasil["gagal"],
            "dilewati": hasil["dilewati"],
            "durasi_detik": hasil["durasi_detik"],
        }
        perubahan_tercatat = sum(len(row.get("changes", [])) for row in hasil["sasaran"])
        ringkasan["perubahan"] = perubahan_tercatat
        sasaran_ringkas = [
            {
                "label": row.get("label") or row["url"],
                "url": row["url"],
                "galat": row.get("error"),
                "dirender": bool(row.get("dirender")),
                "catatan": list(row.get("catatan_render", []) or [])
                + list(row.get("catatan_profil", []) or []),
                "perubahan": [
                    {"tingkat": item["severity"], "pesan": item["message"]}
                    for item in row.get("changes", [])
                ],
            }
            for row in hasil["sasaran"]
        ]
        ringkasan["sasaran"] = sasaran_ringkas[:MAX_RIWAYAT]
    return ringkasan


def mulai_periksa(
    *,
    max_pages: int = 40,
    render: str | None = None,
    tunggu: str | None = None,
    hanya: int | None = None,
) -> dict:
    """Mulai satu pemeriksaan di latar belakang. Menolak bila masih ada yang berjalan."""
    if not tersedia():
        raise RadarError("Modul radar tidak ditemukan.")
    if sedang_berjalan():
        raise RadarError("Pemeriksaan lain masih berjalan. Tunggu sampai selesai.")
    modul = _modul()
    mode = render or _mode_render_bawaan(modul)
    with _KUNCI_PEKERJAAN:
        _PEKERJAAN.update(
            {
                "id": _PEKERJAAN["id"] + 1,
                "keadaan": "berjalan",
                "mulai": _sekarang(),
                "selesai": None,
                "ringkasan": None,
                "hasil": None,
                "galat": None,
            }
        )
        nomor = _PEKERJAAN["id"]

    def pekerja() -> None:
        try:
            ringkasan = _lakukan_pemeriksaan(
                max_pages=max_pages, render=mode, tunggu=tunggu, hanya=hanya
            )
        except Exception as error:  # noqa: BLE001 - galat apa pun harus sampai ke pengguna
            LOG.exception("Pemeriksaan radar gagal")
            with _KUNCI_PEKERJAAN:
                _PEKERJAAN.update(
                    {"keadaan": "gagal", "selesai": _sekarang(), "galat": str(error)}
                )
            return
        with _KUNCI_PEKERJAAN:
            _PEKERJAAN.update(
                {
                    "keadaan": "selesai",
                    "selesai": _sekarang(),
                    "ringkasan": ringkasan,
                    "hasil": ringkasan.get("sasaran"),
                }
            )
        LOG.info("Pemeriksaan radar selesai: %s", ringkasan)

    threading.Thread(target=pekerja, name=f"lokaradar-{nomor}", daemon=True).start()
    return pekerjaan()


def periksa_langsung(
    *,
    max_pages: int | None = None,
    render: str | None = None,
    tunggu: str | None = None,
    hanya: int | None = None,
) -> dict:
    """Jalankan satu pemeriksaan sampai tuntas, bukan di latar belakang.

    Dipakai oleh mode `--radar-periksa` yang dipanggil penjadwal Windows: tidak
    ada antarmuka yang menunggu, jadi hasilnya harus sudah lengkap saat kembali.
    Pemeriksaan yang sedang berjalan di jendela aplikasi tetap dijaga oleh basis
    data: bila bentrok, galatnya dilaporkan apa adanya.
    """
    if not tersedia():
        raise RadarError("Modul radar tidak ditemukan.")
    modul = _modul()
    return _lakukan_pemeriksaan(
        max_pages=int(max_pages or config.RADAR_MAX_PAGES),
        render=render or _mode_render_bawaan(modul),
        tunggu=tunggu,
        hanya=hanya,
    )


def periksa_dari_baris_perintah(*, verbose: bool = False) -> tuple[int, str]:
    """Bentuk yang dipakai penjadwal: kode keluar + satu kalimat ringkas.

    Kode keluar 0 berarti radar selesai memeriksa; 1 berarti ada masalah yang
    perlu dilihat pengguna (mis. radar tidak tersedia atau sebagian sasaran
    gagal). Penjadwal Windows hanya mencatat kode itu.
    """
    try:
        ringkasan = periksa_langsung()
    except RadarError as error:
        return 1, f"Pemeriksaan tidak bisa dijalankan: {error}"
    except Exception as error:  # noqa: BLE001 - apa pun harus jadi kode keluar yang jelas
        LOG.exception("Pemeriksaan terjadwal gagal")
        return 1, f"Pemeriksaan gagal: {error}"
    if not ringkasan.get("diperiksa") and not ringkasan.get("gagal"):
        return 0, "Belum ada sasaran yang dipantau, jadi tidak ada yang diperiksa."
    # Dua angka di belakang koma: pemeriksaan lokal bisa selesai di bawah 0,1 detik,
    # dan "0.0 detik" terbaca seperti pemeriksaan yang tidak jadi berjalan.
    durasi = float(ringkasan.get("durasi_detik") or 0)
    baris = (
        f"Pemeriksaan selesai: {ringkasan['diperiksa']} halaman diperiksa, "
        f"{ringkasan['gagal']} gagal, {ringkasan['dilewati']} dilewati, "
        f"{ringkasan['perubahan']} perubahan tercatat "
        f"({durasi:.2f} detik)."
    )
    if ringkasan.get("gagal"):
        return 1, baris + " Buka halaman radar untuk melihat sebabnya."
    return 0, baris


# -- peramban ----------------------------------------------------------------
def peramban(*, refresh: bool = False) -> dict:
    """Keadaan peramban: ada atau tidak, versi berapa, dan mode render yang dipakai.

    `refresh=True` dipakai tombol "Periksa ulang": hasil pencarian peramban
    disimpan sementara supaya halaman tidak melambat, jadi peramban yang baru
    dipasang hanya terlihat setelah diminta ulang.
    """
    if not tersedia():
        return {"tersedia": False, "pesan": "Modul radar tidak ditemukan.", "mode_render": "tidak"}
    modul = _modul()
    info = modul["peramban"].ketersediaan(refresh=refresh)
    instalator = _instalator_peramban(modul)
    info["mode_render"] = _mode_render_bawaan(modul)
    info["instalator"] = instalator
    info["versi_radar"] = getattr(modul["config"], "VERSION", "") or ""
    return info


def _instalator_peramban(modul) -> bool:
    """Apakah paket ini membawa alat untuk mengunduh Chromium Scrapling.

    Di dalam `.exe` berkas Scrapling sengaja tidak dibundel (menambah lebih dari
    70 MB dan tetap butuh unduhan peramban terpisah), jadi jalan itu tidak
    ditawarkan di sana. Yang ditawarkan adalah peramban yang sudah terpasang.
    """
    try:
        return bool(modul["fetch"].dynamic_available())
    except Exception:  # noqa: BLE001 - informasi tambahan, bukan syarat
        return False


def uji_peramban(jalur: str | None = None) -> dict:
    """Buktikan rendering benar-benar berjalan: buka satu halaman uji milik radar sendiri.

    Halaman ujinya adalah `data:` bawaan `peramban.uji()`, jadi pengujian ini tidak
    menghubungi situs siapa pun. Bila tidak ada peramban, jawabannya menjelaskan
    apa yang kurang — bukan tombol yang diam saja.

    `jalur` diisi bila pengguna menunjuk sendiri berkas perambannya: berkas itu
    diuji, dan baru disimpan sebagai pilihan setelah terbukti bisa merender.
    """
    if not tersedia():
        raise RadarError("Modul radar tidak ditemukan.")
    if sedang_berjalan():
        raise RadarError(
            "Pemeriksaan sedang berjalan. Tunggu sampai selesai sebelum menguji peramban."
        )
    modul = _modul()
    if not jalur and not modul["peramban"].tersedia():
        raise MasukanTidakSah(modul["peramban"].PETUNJUK_TANPA_PERAMBAN)
    LOG.info("Uji rendering diminta dari antarmuka.")
    hasil = modul["peramban"].uji(jalur)
    LOG.info("Uji rendering selesai: %s", hasil.get("pesan"))
    return hasil


def peramban_pakai(jalur: str) -> dict:
    """Tunjuk sendiri berkas peramban yang dipakai, lalu uji dan simpan."""
    if not tersedia():
        raise RadarError("Modul radar tidak ditemukan.")
    modul = _modul()
    LOG.info("Peramban ditunjuk dari antarmuka: %s", jalur)
    return modul["peramban"].uji(jalur)


# -- penjadwalan -------------------------------------------------------------
def jadwal() -> dict:
    """Keadaan tugas pemeriksaan otomatis.

    Penjadwal Windows bisa menolak dibaca — kebijakan perusahaan, Windows
    berbahasa lain, atau memang tidak ada penjadwalnya. Itu bukan kegagalan
    aplikasi, jadi keadaannya dikembalikan sebagai "belum terpasang" beserta
    alasannya. Dilempar sebagai galat, satu permintaan yang gagal akan membuat
    seluruh halaman radar ikut kosong.
    """
    try:
        return _jadwal.status()
    except _jadwal.JadwalError as error:
        LOG.warning("Keadaan penjadwal tidak terbaca: %s", error)
        return _jadwal.tak_terbaca(str(error))


def jadwal_aktifkan(*, waktu: str, frekuensi: str = "harian", hari: str = "") -> dict:
    """Pasang atau perbarui tugas pemeriksaan otomatis."""
    hasil = _jadwal.aktifkan(waktu=waktu, frekuensi=frekuensi, hari=hari)
    _jadwal.catat_jadwal(hasil)
    LOG.info("Jadwal radar dipasang dari antarmuka: %s %s", hasil.get("frekuensi"), hasil.get("waktu"))
    return hasil


def jadwal_matikan() -> dict:
    """Hapus tugas pemeriksaan otomatis."""
    hasil = _jadwal.matikan()
    _jadwal.catat_jadwal(hasil)
    LOG.info("Jadwal radar dihapus dari antarmuka.")
    return hasil


def jadwal_jalankan() -> dict:
    """Minta penjadwal menjalankan tugasnya sekarang (bukti rangkaiannya bekerja)."""
    return _jadwal.jalankan_sekarang()


def _mode_render_bawaan(modul) -> str:
    """Mode render bawaan untuk aplikasi desktop.

    Rendering baru bisa dipakai bila ada peramban. Dua jalan yang tersedia:

    - **peramban yang sudah terpasang** di komputer (Microsoft Edge di Windows,
      Chrome, atau Chromium) — dipakai lewat `lokaradar.peramban`, hanya dengan
      pustaka standar, jadi jalur ini bekerja di dalam `.exe`;
    - Scrapling beserta Chromium yang diunduhnya, bila memang dipasang.

    Bila tidak ada keduanya, bawaannya "tidak": radar tetap berjalan dengan
    permintaan biasa, dan antarmuka menyebutkan alasannya apa adanya.
    """
    if modul["peramban"].tersedia() or modul["fetch"].dynamic_available():
        return "auto"
    return "tidak"


def _sekarang() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
