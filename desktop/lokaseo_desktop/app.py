"""Masuk aplikasi desktop: jalankan server lokal lalu buka antarmuka di peramban.

Bawaan aplikasi adalah mode peramban: tanpa jendela aplikasi, tanpa jendela konsol
bila `pystray` tersedia. Penghentian tersedia lewat ikon tray, halaman
`/hentikan`, atau jendela konsol pada versi konsol.
"""

import argparse
import logging
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

from . import config, jadwal, kesiapan, paths, radar, tray
from .server import STOP_REQUESTED, create_server

LOG = logging.getLogger("lokaseo")
DEFAULT_HOST = "127.0.0.1"


def siapkan_konsol() -> None:
    """Buat keluaran konsol aman di Windows.

    Konsol Windows memakai code page sendiri (sering cp1252/cp437), sehingga
    karakter seperti "·" atau "—" bisa muncul sebagai tanda tanya atau membuat
    `print` gagal. Dengan `errors="replace"` keluaran tidak pernah meledak; bila
    UTF-8 tersedia (Windows Terminal, `chcp 65001`), teksnya tampil utuh.
    """
    for aliran in (sys.stdout, sys.stderr):
        if aliran is None:
            continue
        try:
            aliran.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):  # pragma: no cover - aliran aneh
            continue


def pasang_catatan_galat_latar() -> None:
    """Ubah galat di thread latar menjadi satu baris yang manusiawi.

    Ikon tray dijalankan di thread sendiri oleh `pystray`. Bila Windows menolak
    pembuatannya (kebijakan perusahaan, sesi jarak jauh, atau lingkungan tanpa
    desktop), pengguna dulu melihat traceback Python penuh di jendela hitam —
    menakutkan, padahal aplikasinya baik-baik saja. Sekarang galatnya tetap masuk
    berkas log untuk ditelusuri, tetapi di layar hanya muncul satu kalimat.
    """
    def tangani(argument: threading.ExceptHookArgs) -> None:
        LOG.error(
            "Galat di thread latar (%s): %s",
            getattr(argument.thread, "name", "?"),
            argument.exc_value,
            exc_info=(argument.exc_type, argument.exc_value, argument.exc_traceback),
        )
        # Sumbernya dilihat dari berkas di dalam jejak galat, bukan dari nama
        # thread: nama thread tidak memberi tahu apa pun, dan menebak dari pesan
        # galat bisa salah kategori.
        berkas_jejak = []
        langkah = argument.exc_traceback
        while langkah is not None:
            berkas_jejak.append(str(langkah.tb_frame.f_code.co_filename).lower())
            langkah = langkah.tb_next
        dari_tray = any("pystray" in nama_berkas for nama_berkas in berkas_jejak)
        if dari_tray or "ikon tray" in str(argument.exc_value).lower():
            pesan = (
                "Catatan: ikon tray tidak bisa ditampilkan di komputer ini; aplikasi tetap "
                "berjalan seperti biasa. Untuk berhenti: tombol \"Hentikan aplikasi\" di halaman "
                "radar, halaman http://127.0.0.1:<port>/hentikan, atau tutup jendela ini."
            )
        else:
            pesan = f"Catatan: ada galat di latar belakang ({argument.exc_value}). Aplikasi tetap berjalan."
        # Kalimatnya ikut masuk berkas log: bila aplikasi dijalankan tanpa jendela
        # konsol (mis. dari Penjadwal Tugas), layar tidak bisa menunjukkan apa pun.
        LOG.info(pesan)
        cetak(pesan)

    threading.excepthook = tangani


def cetak(teks: str = "") -> None:
    """Cetak bila ada tujuan keluaran.

    `LokaSEO.exe` versi tanpa konsol tidak punya `sys.stdout`. Penjadwal Windows
    memanggil versi itu supaya tidak ada jendela hitam yang berkedip setiap pagi,
    jadi setiap cetakan harus tahan menghadapi tujuan keluaran yang tidak ada.
    """
    if sys.stdout is None:
        return
    try:
        print(teks)
    except (OSError, ValueError):  # pragma: no cover - konsol bisa hilang mendadak
        pass


def periksa_radar(verbose: bool = False) -> int:
    """Mode `--radar-periksa`: periksa sekali, lalu keluar.

    Inilah yang dipanggil tugas Windows Task Scheduler. Tidak membuka peramban,
    tidak menyalakan server, dan tidak menampilkan ikon tray. Catatannya masuk
    ke berkas log aplikasi supaya bisa diperiksa belakangan.
    """
    kode, ringkas = radar.periksa_dari_baris_perintah(verbose=verbose)
    cetak(ringkas)
    LOG.info("Pemeriksaan terjadwal selesai dengan kode %s: %s", kode, ringkas)
    try:
        jadwal.catat_jadwal(jadwal.status())
    except jadwal.JadwalError:
        LOG.debug("Status jadwal tidak bisa dibaca saat pemeriksaan terjadwal.")
    return kode


def cetak_kesiapan() -> int:
    """Mode `--kesiapan`: cetak laporan kesiapan ke layar lalu keluar.

    Berguna saat antarmuka tidak mau terbuka: laporannya juga ditulis ke
    `laporan-kesiapan.txt` di folder data supaya bisa dibuka dengan Notepad.
    """
    laporan = kesiapan.periksa()
    cetak(laporan["teks"])
    tujuan = paths.data_dir() / "laporan-kesiapan.txt"
    try:
        tujuan.write_text(laporan["teks"], encoding="utf-8")
        cetak(f"Laporan juga disimpan di: {tujuan}")
    except OSError as error:
        cetak(f"Laporan tidak bisa disimpan ke berkas: {error}")
    return 0 if laporan["ringkasan"]["gagal"] == 0 else 1


def free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


def webview_available() -> bool:
    try:
        import webview  # type: ignore  # noqa: F401
    except ImportError:
        return False
    return True


def run_native_window(url: str) -> None:
    """Jendela aplikasi asli; hanya dipakai bila diminta lewat `--window native`."""
    import webview  # type: ignore

    webview.create_window(
        f"{config.APP_NAME} — ruang kerja SEO Indonesia",
        url,
        width=1280,
        height=860,
        min_size=(900, 640),
    )
    webview.start()


def _wait_until_stop(thread: threading.Thread, icon) -> None:
    while not STOP_REQUESTED.is_set() and thread.is_alive():
        STOP_REQUESTED.wait(0.5)
    if icon is not None:
        try:
            icon.visible = False
            icon.stop()
        except Exception:  # noqa: BLE001 - tray sudah berhenti
            LOG.debug("Ikon tray sudah berhenti.")


def run(root: Path, host: str, port: int, offline: bool, window: str, open_browser: bool, use_tray: bool) -> int:
    server = create_server(root, host, port, offline=offline)
    actual_port = server.server_address[1]
    display_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    url = f"http://{display_host}:{actual_port}/"
    thread = threading.Thread(target=server.serve_forever, name="lokaseo-http", daemon=True)
    thread.start()
    LOG.info("Aplikasi berjalan di %s (offline=%s, root=%s)", url, offline, root)
    print(f"{config.APP_NAME} {config.APP_VERSION} berjalan di {url}")
    print(f"Antarmuka terbuka di peramban. Hentikan lewat {url}hentikan bila perlu.")
    print(f"Data lokal: {paths.data_dir()}")
    if offline:
        print("Mode luring aktif: penghubung AI dinonaktifkan.")
    icon = None
    try:
        if window == "native" and webview_available():
            print("Jendela aplikasi dibuka. Tutup jendela untuk keluar.")
            run_native_window(url)
        else:
            if window == "native":
                LOG.warning("pywebview tidak tersedia; memakai peramban bawaan.")
            if open_browser:
                webbrowser.open(url, new=2)
            if use_tray and tray.tray_available():
                icon = tray.start(
                    url,
                    paths.asset_path("lokaseo.png"),
                    on_open=lambda: webbrowser.open(url, new=2),
                    on_quit=STOP_REQUESTED.set,
                )
            if icon is None:
                print("Tekan Ctrl+C untuk berhenti (atau buka " + url + "hentikan).")
        _wait_until_stop(thread, icon)
    except KeyboardInterrupt:
        print("\nBerhenti.")
    finally:
        STOP_REQUESTED.set()
        server.shutdown()
        server.server_close()
        print("LokaSEO dihentikan.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=config.APP_ID,
        description="LokaSEO sebagai aplikasi lokal; antarmuka terbuka di peramban.",
    )
    parser.add_argument("--root", type=Path, default=None, help="direktori build frontend")
    parser.add_argument("--host", default=DEFAULT_HOST, help="alamat bind (bawaan 127.0.0.1)")
    parser.add_argument("--port", type=int, default=0, help="0 memilih port kosong otomatis")
    parser.add_argument(
        "--window",
        choices=("browser", "native"),
        default="browser",
        help="browser (bawaan): antarmuka di peramban; native: jendela aplikasi bila pywebview ada",
    )
    parser.add_argument("--offline", action="store_true", help="matikan seluruh panggilan AI")
    parser.add_argument(
        "--kesiapan",
        action="store_true",
        help="cetak laporan kesiapan aplikasi lalu keluar (berguna saat antarmuka tidak terbuka)",
    )
    parser.add_argument(
        "--radar-periksa",
        action="store_true",
        help="periksa sasaran radar sekali lalu keluar (dipakai penjadwal Windows)",
    )
    parser.add_argument("--no-open", action="store_true", help="jangan buka peramban otomatis")
    parser.add_argument("--no-tray", action="store_true", help="jangan tampilkan ikon tray")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    siapkan_konsol()
    paths.configure_logging(args.verbose)
    pasang_catatan_galat_latar()
    if args.kesiapan:
        return cetak_kesiapan()
    if args.radar_periksa:
        return periksa_radar(args.verbose)
    root = paths.static_root(args.root)
    if not (root / "index.html").is_file():
        print(
            f"Berkas aplikasi tidak ditemukan di {root}. Jalankan `pnpm build:loka` lebih dahulu.",
            file=sys.stderr,
        )
        return 2
    env_flag = os.environ.get("LOKA_OFFLINE", "").strip().lower()
    offline = args.offline or env_flag in ("1", "true", "yes", "on")
    port = args.port or free_port(args.host)
    return run(root, args.host, port, offline, args.window, not args.no_open, not args.no_tray)


if __name__ == "__main__":
    raise SystemExit(main())
