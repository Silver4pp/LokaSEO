"""Antarmuka baris perintah LokaRadar."""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

from . import __version__, config, fetch, places, report
from . import profil as profil_mod
from .fetch import Fetcher
from .reputasi import _skala_text
from .reputasi import board as reputation_board
from .reputasi import board_markdown
from .run import run_once
from . import sasaran as sasaran_mod
from .store import Store

LOG = logging.getLogger("lokaradar")


def _parse_since(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d+)([dhm])", value.strip().lower())
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        seconds = {"d": 86400, "h": 3600, "m": 60}[unit] * amount
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds))
    return value


def _print_table(rows: list[list[str]], headers: list[str]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))
    line = "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    print(line)
    print("-" * len(line))
    for row in rows:
        print("  ".join(str(cell).ljust(widths[index]) for index, cell in enumerate(row)))


def _muat_profil(args=None):
    """Profil usaha dari berkas (atau None bila belum diatur)."""
    path = getattr(args, "profil", None) if args is not None else None
    return profil_mod.load(Path(path) if path else None)


def _mode_render(args) -> str:
    mode = getattr(args, "render", None) or config.DEFAULT_RENDER
    return mode if mode in config.RENDER_MODES else config.DEFAULT_RENDER


def _make_fetcher(args) -> Fetcher:
    return Fetcher(
        timeout=args.timeout,
        delay=args.delay,
        obey_robots=not args.ignore_robots,
        stealthy=getattr(args, "stealthy", False),
        render=_mode_render(args),
        render_wait=getattr(args, "tunggu", None) or None,
    )


# -- perintah ---------------------------------------------------------------
def cmd_status(args) -> int:
    with Store() as store:
        stats = store.stats()
        last = store.get_state("terakhir_jalan")
        tempat = [row for row in store.targets() if str(row["url"]).startswith(places.SCHEME)]
    print(f"LokaRadar {__version__}")
    print(f"Mesin pengambil : {'Scrapling' if fetch.scrapling_available() else 'urllib (sederhana)'}")
    print(f"Basis data      : {stats['database']}")
    print(f"Sasaran         : {stats['sasaran']} ({stats['sasaran_aktif']} aktif)")
    print(f"Potret tersimpan: {stats['potret']}")
    print(f"Perubahan       : {stats['perubahan']}")
    if last:
        print(f"Pemeriksaan terakhir: {last}")
    print(f"Jeda per host   : {config.DEFAULT_DELAY_SECONDS} detik (bawaan)")
    info_peramban = fetch.peramban.ketersediaan()
    if fetch.session_available() and info_peramban["tersedia"]:
        peramban = f"siap ({info_peramban['nama'] or 'Scrapling'}, sesi dipakai ulang)"
    elif info_peramban["tersedia"]:
        peramban = f"siap ({info_peramban['nama']}{', ' + info_peramban['versi'] if info_peramban['versi'] else ''})"
    elif fetch.dynamic_available():
        peramban = "belum terunduh (scrapling install)"
    else:
        peramban = "tidak ada (pasang Microsoft Edge, Google Chrome, atau Scrapling)"
    print(f"Rendering       : {config.DEFAULT_RENDER} · peramban: {peramban}")
    kunci = "terpasang" if places.key_from_env() else "belum diatur"
    print(f"Kunci Places API: {kunci} ({places.KEY_ENV}; kunci tidak pernah disimpan)")
    print(f"Sasaran tempat  : {len(tempat)} (rating resmi lewat {places.SCHEME}<place_id>)")
    return 0


def cmd_add(args) -> int:
    with Store() as store:
        row = store.add_target(args.url, args.label or "", args.kind)
    print(f"Sasaran #{row['id']} disimpan: {row['url']}")
    if not row["label"]:
        print("Tip: tambahkan --label agar laporan lebih mudah dibaca.")
    return 0


def cmd_list(args) -> int:
    with Store() as store:
        rows = store.targets()
        if not rows:
            print("Belum ada sasaran. Tambahkan dengan: python -m lokaradar add <alamat>")
            return 0
        table = []
        for row in rows:
            snapshot = store.latest_snapshot(int(row["id"]))
            harga = ""
            if snapshot:
                from .extract import lowest_price

                low = lowest_price(snapshot["facts"])
                harga = f"{low['currency']} {low['amount']:,.0f}".replace(",", ".") if low else "-"
            table.append(
                [
                    str(row["id"]),
                    "aktif" if row["enabled"] else "nonaktif",
                    row["label"] or "-",
                    row["url"],
                    harga,
                    snapshot["fetched_at"] if snapshot else "belum",
                ]
            )
        _print_table(table, ["ID", "Status", "Label", "Alamat", "Harga terendah", "Diperiksa"])
    return 0


def cmd_remove(args) -> int:
    with Store() as store:
        target_id = store.remove_target(args.identifier)
    print(f"Sasaran #{target_id} beserta riwayatnya dihapus.")
    return 0


def cmd_run(args) -> int:
    with Store() as store:
        if not store.targets(enabled_only=True):
            print("Belum ada sasaran aktif.")
            return 1
        if getattr(args, "stealthy", False):
            print("Peringatan: mode menyamar aktif. Permintaan akan tampak sebagai peramban biasa,")
            print("sehingga pemilik situs tidak bisa mengenali LokaRadar. Pakai hanya bila benar-benar perlu.")
        render = _mode_render(args)
        if render != "tidak" and not fetch.browser_ready():
            print(f"Catatan: rendering '{render}' diminta, tetapi {fetch.PETUNJUK_PERAMBAN}")
            print("Sementara itu halaman tetap diambil dengan permintaan biasa.")
        elif render != "tidak":
            print(f"Rendering: {render} (halaman ber-JavaScript diambil ulang dengan peramban headless).")
        fetcher = _make_fetcher(args)
        places_key = getattr(args, "places_key", None) or places.key_from_env()
        # Satu peramban untuk seluruh putaran, bukan satu per halaman.
        with fetcher.render_session():
            result = run_once(
                store,
                fetcher,
                max_pages=args.max_pages,
                only_id=args.target,
                places_key=places_key,
                profil=_muat_profil(args),
            )
        if fetcher.sesi_terpakai:
            print("Peramban dipakai ulang untuk seluruh putaran ini (satu peluncuran).")
        store.set_state("terakhir_jalan", result["selesai"])
        print(
            f"Selesai dalam {result['durasi_detik']} detik: "
            f"{result['diperiksa']} diperiksa, {result['gagal']} gagal, {result['dilewati']} dilewati."
        )
        total_changes = sum(len(row.get("changes", [])) for row in result["sasaran"])
        if total_changes:
            print(f"{total_changes} perubahan terdeteksi:")
            for row in result["sasaran"]:
                for change in row.get("changes", []):
                    nama = row.get("label") or row["url"]
                    print(f"  [{change['severity']}] {nama}: {change['message']}")
        else:
            print("Tidak ada perubahan pada putaran ini.")
        for row in result["sasaran"]:
            if row.get("error"):
                print(f"  ! {row['url']}: {row['error']}")
            for catatan in row.get("catatan_profil", []) + row.get("catatan_render", []):
                print(f"  · {row.get('label') or row['url']}: {catatan}")
    if args.report:
        return cmd_report(argparse.Namespace(days=args.days, out=args.out, quiet=False))
    return 0


def cmd_changes(args) -> int:
    since = _parse_since(args.since)
    severities = tuple(args.severity) if args.severity else None
    with Store() as store:
        rows = store.changes(since=since, severities=severities, limit=args.limit)
        if not rows:
            print("Tidak ada perubahan pada rentang itu.")
            return 0
        table = [
            [
                row["detected_at"],
                row["severity"],
                row["label"] or row["url"][:40],
                row["message"],
            ]
            for row in rows
        ]
        _print_table(table, ["Waktu", "Tingkat", "Sasaran", "Perubahan"])
    return 0


def cmd_report(args) -> int:
    since = _parse_since(f"{args.days}d") if args.days else None
    store = Store()
    rows = []
    for target in store.targets():
        snapshot = store.latest_snapshot(int(target["id"]))
        if not snapshot:
            continue
        changes = store.changes(target_id=int(target["id"]), since=since, limit=100)
        rows.append(
            {
                "url": target["url"],
                "label": target["label"],
                "kind": target["kind"],
                "fetched_at": snapshot["fetched_at"],
                "status": snapshot["status"],
                "facts": snapshot["facts"],
                "changes": changes,
                # Keterangan pengambilan ikut dari potret, supaya laporan yang
                # dibuat belakangan tetap tahu halaman itu dirender atau tidak.
                "dirender": snapshot.get("sumber") == "peramban",
                "jumlah_kata": (snapshot["facts"] or {}).get("word_count"),
                "catatan_ambil": snapshot.get("catatan") or "",
            }
        )
    if not rows:
        print("Belum ada potret. Jalankan dulu: python -m lokaradar run")
        store.close()
        return 1
    pack = report.build_pack(
        rows,
        since=since,
        store=store,
        days=args.days or 30,
        profil=_muat_profil(args),
    )
    directory = Path(args.out).expanduser() if args.out else config.report_dir()
    paths = report.write_reports(pack, directory)
    print(f"Laporan Markdown : {paths['markdown']}")
    print(f"Paket wawasan    : {paths['json']}")
    print(
        f"Ringkasan: {pack['ringkasan']['sasaran']} sasaran, "
        f"{pack['ringkasan']['perubahan']} perubahan, "
        f"{len(pack['lokaseo']['ide_konten'])} usulan ide konten."
    )
    store.close()
    return 0


def cmd_reputasi(args) -> int:
    """Tampilkan papan reputasi lokal dan simpan salinannya bila diminta."""
    with Store() as store:
        if not store.targets(enabled_only=True):
            print("Belum ada sasaran aktif.")
            return 1
        profil = _muat_profil(args)
        papan = reputation_board(
            store,
            days=args.days,
            min_rating=args.min_rating if args.min_rating is not None else None,
            profil=profil,
        )
        ada_potret = any(row["jumlah_potret"] for row in papan["peringkat"] + papan["perhatian"])
    if not ada_potret:
        print("Belum ada potret rating. Jalankan dulu: python -m lokaradar run")
        return 1

    ringkas = papan["ringkasan"]
    if papan.get("usaha"):
        print(f"Usaha: {papan['usaha']}")
    print(
        f"Papan reputasi {papan['periode_hari']} hari · ambang rating {papan['ambang_rating']} · "
        f"{ringkas['usaha']} usaha ({ringkas['dengan_rating']} punya rating terbaca)"
    )
    if ringkas["rata_rata_rating"] is not None:
        setara = ringkas.get("rata_rata_setara_5")
        setara_teks = f" (setara {setara} dari 5)" if setara is not None else ""
        print(
            f"Rata-rata rating: {ringkas['rata_rata_rating']}{setara_teks} · "
            f"total ulasan: {ringkas['total_ulasan'] if ringkas['total_ulasan'] is not None else '—'} · "
            f"ulasan baru: {ringkas['total_ulasan_baru'] if ringkas['total_ulasan_baru'] is not None else '—'}"
        )
    print()
    if papan["peringkat"]:
        tabel = []
        for row in papan["peringkat"]:
            tabel.append(
                [
                    row["peringkat"],
                    row["label"][:28],
                    f"{row['rating']}/{_skala_text(row['skala'])}" if row["rating"] is not None else "—",
                    f"{round((row.get('rasio') or 0) * 5, 2)}/5" if row.get("rasio") else "—",
                    row["ulasan"] if isinstance(row["ulasan"], int) else "—",
                    row["ulasan_baru"] if isinstance(row["ulasan_baru"], int) else "—",
                    row["laju_mingguan"] if row["laju_mingguan"] is not None else "—",
                    "Places API" if row["sumber"] == "places-api" else "halaman",
                ]
            )
        _print_table(tabel, ["#", "Usaha", "Rating", "Setara", "Ulasan", "Baru", "Laju/minggu", "Sumber"])
    else:
        print("Belum ada rating terbaca pada sasaran mana pun.")
        print("Pastikan halaman memuat data rating, atau pakai sasaran tempat:<place_id> dengan kunci Places API Anda.")

    if papan["perhatian"]:
        print()
        print("Perlu perhatian:")
        from .reputasi import LAMBANG_TANDA

        for row in papan["perhatian"]:
            tanda_teks = ", ".join(LAMBANG_TANDA.get(kode, kode) for kode in row["tanda"])
            print(f"  - {row['label']}: {tanda_teks}")

    if args.out:
        directory = Path(args.out).expanduser()
        directory.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = directory / f"reputasi-{stamp}.md"
        # Judul dinaikkan satu tingkat supaya berkas berdiri sendiri,
        # tanpa mengulang judul yang sama dua kali.
        isi = board_markdown(papan).replace("## Papan reputasi lokal", "# Papan reputasi lokal", 1)
        path.write_text(isi, encoding="utf-8")
        print()
        print(f"Salinan Markdown  : {path}")
    return 0


def cmd_profil(args) -> int:
    """Tampilkan, atur, atau impor profil usaha (kunci utama radar)."""
    if args.dari:
        try:
            profil = profil_mod.from_lokaseo_file(Path(args.dari))
        except ValueError as error:
            print(f"Gagal membaca cadangan LokaSEO: {error}")
            return 4
        profil.sumber = f"cadangan LokaSEO: {args.dari}"
        tujuan = profil_mod.save(profil, Path(args.profil) if args.profil else None)
        print("Profil usaha diambil dari cadangan LokaSEO.")
        _cetak_profil(profil)
        print(f"\nDisimpan di: {tujuan}")
        return 0

    if args.jenis or args.nama or args.kota or args.situs or args.min_rating is not None:
        dasar = profil_mod.load(Path(args.profil) if args.profil else None) or profil_mod.Profil()
        if args.jenis:
            if args.jenis not in profil_mod.INDUSTRI:
                print("Jenis usaha tidak dikenal. Pilihan yang tersedia:")
                for kunci, item in profil_mod.INDUSTRI.items():
                    print(f"  {kunci:22s} {item['label']}")
                return 4
            dasar.jenis = args.jenis
        if args.nama:
            dasar.nama = args.nama
        if args.kota:
            dasar.kota = args.kota
        if args.situs:
            dasar.situs = args.situs
        if args.min_rating is not None:
            dasar.min_rating = args.min_rating
        dasar.sumber = "diatur lewat perintah profil"
        tujuan = profil_mod.save(dasar, Path(args.profil) if args.profil else None)
        print("Profil usaha disimpan.")
        _cetak_profil(dasar)
        print(f"\nDisimpan di: {tujuan}")
        return 0

    profil = _muat_profil(args)
    if profil is None:
        print("Belum ada profil usaha.")
        print("Isi dengan salah satu cara berikut:")
        print("  1. Impor cadangan LokaSEO : python -m lokaradar profil --dari lokaseo-cadangan.json")
        print("  2. Atur langsung           : python -m lokaradar profil --jenis kafe-kedai --nama \"Kedai Kopi\" --kota Bogor --situs kopi.example")
        print("\nJenis usaha yang tersedia:")
        for kunci, item in profil_mod.INDUSTRI.items():
            print(f"  {kunci:22s} {item['label']}")
        return 1
    _cetak_profil(profil)
    asal = profil.sumber or str(profil_mod.profile_path())
    print(f"\nAsal data: {asal}")
    return 0


def _cetak_profil(profil) -> None:
    print(f"Nama usaha   : {profil.nama or '(belum diisi)'}")
    print(f"Jenis usaha  : {profil.jenis_label or '(belum dipilih)'}")
    print(f"Kota         : {profil.kota or '(belum diisi)'}")
    print(f"Situs sendiri: {profil.situs or '(belum diisi)'}")
    print(f"Ambang rating: {profil.ambang_rating}")
    if profil.schema_diharapkan:
        print(f"Data terstruktur diharapkan: {', '.join(profil.schema_diharapkan)}")
    if profil.kata_kunci:
        print(f"Kata kunci awal: {', '.join(profil.kata_kunci)}")
    for baris in profil.catatan:
        if baris:
            print(f"Catatan      : {baris}")


def cmd_cari(args) -> int:
    """Cari tempat di Google Places untuk mendapatkan place_id yang sah."""
    key = args.places_key or places.key_from_env()
    if not key:
        print(
            f"Butuh kunci Places API Anda sendiri. Setel variabel lingkungan {places.KEY_ENV}, "
            "lalu jalankan lagi."
        )
        print("Pencarian ini memakai SKU Text Search pada kuota Google Cloud Anda.")
        return 3
    try:
        hasil = places.search_text(args.kata, key, kota=args.kota or "", max_results=args.max)
    except (places.PlacesError, ValueError) as error:
        print(f"Pencarian gagal: {error}")
        return 4
    if not hasil:
        print("Tidak ada tempat yang cocok. Coba tambahkan kota atau nama jalan.")
        return 1
    print(f"Ditemukan {len(hasil)} tempat (kuota Text Search Anda terpakai 1 permintaan):")
    print()
    tabel = []
    for nomor, row in enumerate(hasil, start=1):
        rating = f"{row['rating']} ({row['count']})" if row["rating"] is not None else "belum ada"
        tabel.append([nomor, row["name"][:32], rating, row["address"][:44]])
    _print_table(tabel, ["#", "Nama", "Rating (ulasan)", "Alamat"])
    print()
    for nomor, row in enumerate(hasil, start=1):
        print(f"{nomor}. python -m lokaradar add {places.SCHEME}{row['place_id']} --label \"{row['name']}\" --kind reputasi")
    if args.tambah:
        pilihan = [row for row in hasil if int(args.tambah) == hasil.index(row) + 1]
        if not pilihan:
            print(f"\nNomor {args.tambah} tidak ada pada daftar di atas.")
            return 4
        row = pilihan[0]
        with Store() as store:
            tersimpan = store.add_target(
                places.target_url(row["place_id"]), row["name"] or "", "reputasi"
            )
        print(f"\nSasaran ditambahkan: #{tersimpan['id']} {tersimpan['label']} ({tersimpan['url']})")
    return 0


def cmd_tempat(args) -> int:
    """Baca angka agregat satu tempat lewat Google Places API (kunci milik pengguna)."""
    key = args.places_key or places.key_from_env()
    if not key:
        print(
            f"Butuh kunci Places API Anda sendiri. Setel variabel lingkungan {places.KEY_ENV}, "
            "lalu jalankan lagi."
        )
        return 3
    try:
        place = places.lookup(places.place_id_of(args.identifier) if args.identifier.startswith(places.SCHEME) else args.identifier, key)
    except (places.PlacesError, ValueError) as error:
        print(f"Gagal membaca tempat: {error}")
        return 4
    print(f"Nama   : {place['name'] or '(tanpa nama)'}")
    if place["address"]:
        print(f"Alamat : {place['address']}")
    rating = place["rating"]
    print(f"Rating : {rating if rating is not None else 'belum ada'}")
    print(f"Ulasan : {place['count'] if place['count'] is not None else 'belum ada'}")
    print()
    print(f"Tambahkan sebagai sasaran: python -m lokaradar add {places.SCHEME}{place['place_id']} --label \"Nama usaha\"")
    return 0


def cmd_export(args) -> int:
    if getattr(args, "sasaran", False):
        with Store() as store:
            ringkasan = sasaran_mod.tulis(store, Path(args.out).expanduser())
        print(f"Daftar {ringkasan['jumlah']} sasaran diekspor ke {ringkasan['berkas']}")
        print("Berkas ini bisa dikirim ke komputer lain lalu diimpor dengan: lokaradar import BERKAS")
        return 0
    since = _parse_since(args.since)
    with Store() as store:
        rows = store.changes(since=since, limit=args.limit)
    payload = {"dibuat_pada": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "perubahan": rows}
    target = Path(args.out).expanduser()
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rows)} perubahan diekspor ke {target}")
    return 0


def cmd_import(args) -> int:
    """Impor daftar sasaran dari berkas: menggabung, tidak pernah menghapus."""
    berkas = Path(args.berkas).expanduser()
    if not berkas.is_file():
        print(f"Berkas tidak ditemukan: {berkas}")
        return 2
    if berkas.stat().st_size > sasaran_mod.MAKS_BITA:
        print(
            f"Berkas terlalu besar ({berkas.stat().st_size // 1024} KB). "
            f"Batasnya {sasaran_mod.MAKS_BITA // 1000} KB."
        )
        return 2
    try:
        teks = berkas.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"Berkas {berkas} bukan teks UTF-8. Simpan ulang sebagai UTF-8 atau tempel ulang daftarnya.")
        return 2
    try:
        with Store() as store:
            hasil = sasaran_mod.impor(store, teks, uji_coba=args.dry_run)
    except sasaran_mod.BerkasTidakSah as error:
        print(f"Impor dibatalkan: {error}")
        return 2
    for baris in sasaran_mod.ringkas(hasil):
        print(baris)
    print(f"Sasaran tersimpan sekarang: {hasil['sasaran_sekarang']}")
    return 0


def cmd_scrape(args) -> int:
    """Ambil satu halaman sekali untuk memeriksa hasil pembacaan."""
    fetcher = _make_fetcher(args)
    render = _mode_render(args)
    if render != "tidak" and not fetch.browser_ready():
        print(f"Catatan: rendering '{render}' diminta, tetapi {fetch.PETUNJUK_PERAMBAN}")
    from .extract import page_facts, readable_prices

    page = fetcher.get(args.url)
    facts = page_facts(page.final_url or args.url, page.html, page.text)
    print(f"Status        : {page.status} ({page.elapsed_ms} ms)")
    print(f"Judul         : {facts['title']}")
    print(f"Deskripsi     : {facts['description'][:120]}")
    print(f"Harga terbaca : {readable_prices(facts)}")
    print(f"Rating        : {facts['rating']}")
    print(f"Data terstruktur: {', '.join(facts['schema_types'][:10]) or '-'}")
    print(f"Gambar tanpa alt: {facts['images_without_alt']} dari {facts['images']}")
    kata_statis = getattr(page, "kata_statis", None)
    if page.rendered and kata_statis is not None and kata_statis != facts["word_count"]:
        print(f"Jumlah kata   : {facts['word_count']} (permintaan biasa hanya terbaca {kata_statis})")
    else:
        print(f"Jumlah kata   : {facts['word_count']}")
    if page.rendered:
        tambahan = ""
        if kata_statis is not None and kata_statis != facts["word_count"]:
            tambahan = f"; permintaan biasa hanya {kata_statis} kata"
        if getattr(page, "render_ms", None):
            tambahan += f", {page.render_ms} ms"
        print(f"Pengambilan   : dengan peramban headless (isi dibuat JavaScript{tambahan})")
        if page.render_gagal:
            print(f"Catatan       : {page.render_gagal}")
    elif page.render_gagal:
        print(f"Rendering     : gagal — {page.render_gagal}")
    elif facts["word_count"] < config.RENDER_MIN_WORDS:
        if render == "selalu":
            print("Halaman tetap hampir tanpa teks meskipun sudah diambil dengan peramban.")
        else:
            print(
                "Pengambilan   : hanya permintaan biasa dan halaman hampir tanpa teks; "
                "coba lagi dengan `--render selalu`."
            )
    return 0


# -- argumen ----------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lokaradar",
        description="Radar pemantauan situs publik untuk LokaSEO (berjalan lokal, tanpa layanan daring).",
    )
    parser.add_argument("--verbose", action="store_true", help="tampilkan catatan rinci")
    parser.add_argument("--timeout", type=float, default=config.DEFAULT_TIMEOUT)
    parser.add_argument("--delay", type=float, default=config.DEFAULT_DELAY_SECONDS, help="jeda antar permintaan per host")
    parser.add_argument("--ignore-robots", action="store_true", help="abaikan robots.txt (tidak disarankan)")
    parser.add_argument(
        "--stealthy",
        action="store_true",
        help="menyamar sebagai peramban (tidak disarankan; melanggar janji identitas jujur)",
    )
    parser.add_argument(
        "--tunggu",
        default=None,
        metavar="SELEKTOR",
        help="tunggu selektor CSS ini muncul sebelum peramban menyerahkan halaman (mis. \"#harga\")",
    )
    parser.add_argument(
        "--render",
        default=config.DEFAULT_RENDER,
        choices=list(config.RENDER_MODES),
        help="ambil ulang halaman ber-JavaScript dengan peramban: auto (bawaan), selalu, atau tidak",
    )
    parser.add_argument(
        "--profil",
        default=None,
        help="berkas profil usaha (bawaan: usaha.json di folder data radar)",
    )
    parser.add_argument(
        "--places-key",
        default=None,
        help=f"kunci Google Places API untuk sasaran tempat:<place_id> (bisa juga lewat {places.KEY_ENV}; tidak disimpan)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="ringkasan basis data dan mesin pengambil").set_defaults(func=cmd_status)

    add = sub.add_parser(
        "add",
        help="tambah sasaran pemantauan (alamat http/https, atau tempat:<place_id> untuk Google Places)",
    )
    add.add_argument("url", help="https://… atau tempat:<place_id>")
    add.add_argument("--label", default="", help="nama yang mudah dibaca")
    add.add_argument("--kind", default="halaman", choices=["halaman", "harga", "layanan", "reputasi"])
    add.set_defaults(func=cmd_add)

    sub.add_parser("list", help="daftar sasaran dan harga terakhir").set_defaults(func=cmd_list)

    remove = sub.add_parser("remove", help="hapus sasaran beserta riwayatnya")
    remove.add_argument("identifier", help="ID atau alamat sasaran")
    remove.set_defaults(func=cmd_remove)

    run = sub.add_parser("run", help="periksa semua sasaran aktif")
    run.add_argument("--max-pages", type=int, default=config.DEFAULT_MAX_PAGES_PER_RUN)
    run.add_argument(
        "--render", default=argparse.SUPPRESS, choices=list(config.RENDER_MODES),
        help="ambil ulang halaman ber-JavaScript dengan peramban",
    )
    run.add_argument(
        "--tunggu", default=argparse.SUPPRESS, metavar="SELEKTOR",
        help="tunggu selektor CSS ini muncul sebelum halaman diserahkan",
    )
    run.add_argument("--target", type=int, default=None, help="batasi ke satu ID sasaran")
    run.add_argument("--report", action="store_true", help="buat laporan setelah selesai")
    run.add_argument("--days", type=int, default=14)
    run.add_argument("--out", default=None)
    run.add_argument(
        "--profil", default=argparse.SUPPRESS, help="berkas profil usaha yang dipakai"
    )
    run.set_defaults(func=cmd_run)

    changes = sub.add_parser("changes", help="tampilkan perubahan yang terdeteksi")
    changes.add_argument("--since", default=None, help="7d, 24h, 30m, atau tanggal ISO")
    changes.add_argument("--severity", action="append", choices=["info", "rendah", "sedang", "tinggi"])
    changes.add_argument("--limit", type=int, default=100)
    changes.set_defaults(func=cmd_changes)

    rep = sub.add_parser("report", help="tulis laporan Markdown dan paket wawasan JSON")
    rep.add_argument("--days", type=int, default=14)
    rep.add_argument("--out", default=None, help="folder keluaran (bawaan: folder data radar)")
    rep.add_argument(
        "--profil", default=argparse.SUPPRESS, help="berkas profil usaha yang dipakai"
    )
    rep.set_defaults(func=cmd_report)

    profil_cmd = sub.add_parser(
        "profil",
        help="tampilkan, atur, atau impor profil usaha (kunci utama radar)",
    )
    # Diterima juga di sini supaya `profil --profil berkas.json` tidak salah pakai.
    profil_cmd.add_argument(
        "--profil", default=argparse.SUPPRESS, help="berkas profil usaha yang dipakai"
    )
    profil_cmd.add_argument("--dari", default=None, help="berkas cadangan LokaSEO (lokaseo-cadangan.json)")
    profil_cmd.add_argument("--jenis", default=None, help="id jenis usaha, misalnya kafe-kedai")
    profil_cmd.add_argument("--nama", default=None, help="nama usaha")
    profil_cmd.add_argument("--kota", default=None, help="kota atau wilayah layanan")
    profil_cmd.add_argument("--situs", default=None, help="domain atau alamat situs sendiri")
    profil_cmd.add_argument("--min-rating", type=float, default=None, help="ambang rating untuk papan reputasi")
    profil_cmd.set_defaults(func=cmd_profil)

    rep2 = sub.add_parser(
        "reputasi",
        help="papan reputasi lokal: rating dan jumlah ulasan usaha yang dipantau",
    )
    rep2.add_argument("--days", type=int, default=30, help="periode riwayat yang dihitung")
    rep2.add_argument(
        "--min-rating",
        type=float,
        default=None,
        help="ambang peringatan rating (bawaan: mengikuti jenis usaha pada profil)",
    )
    rep2.add_argument("--out", default=None, help="folder untuk menyimpan salinan Markdown")
    rep2.add_argument(
        "--profil", default=argparse.SUPPRESS, help="berkas profil usaha yang dipakai"
    )
    rep2.set_defaults(func=cmd_reputasi)

    cari = sub.add_parser(
        "cari",
        help="cari tempat di Google Places untuk mendapatkan place_id (memakai kuota Anda)",
    )
    cari.add_argument("kata", help="nama usaha atau kata kunci, misalnya \"Klinik Gigi Bogor\"")
    cari.add_argument("--kota", default="", help="tambahkan kota/wilayah pada pencarian")
    cari.add_argument("--max", type=int, default=5, help=f"jumlah hasil (1-{places.MAX_SEARCH_RESULTS})")
    cari.add_argument("--tambah", type=int, default=None, help="langsung tambahkan hasil nomor ini sebagai sasaran")
    cari.set_defaults(func=cmd_cari)

    tempat = sub.add_parser(
        "tempat",
        help="baca rating agregat satu tempat lewat Google Places API (kunci Anda sendiri)",
    )
    tempat.add_argument("identifier", help="place_id atau tempat:<place_id>")
    tempat.set_defaults(func=cmd_tempat)

    export = sub.add_parser("export", help="ekspor perubahan atau daftar sasaran ke JSON")
    export.add_argument("out")
    export.add_argument("--since", default=None)
    export.add_argument("--limit", type=int, default=1000)
    export.add_argument(
        "--sasaran",
        action="store_true",
        help="ekspor daftar sasaran (bukan perubahan) agar bisa dipindah atau dibagikan",
    )
    export.set_defaults(func=cmd_export)

    impor = sub.add_parser(
        "import",
        help="impor daftar sasaran dari berkas (menggabung, tidak menghapus apa pun)",
    )
    impor.add_argument("berkas", help="berkas JSON atau teks berisi alamat halaman")
    impor.add_argument(
        "--dry-run",
        action="store_true",
        help="periksa berkas dan tampilkan hasilnya tanpa menyimpan",
    )
    impor.set_defaults(func=cmd_import)

    scrape = sub.add_parser("scrape", help="ambil satu halaman untuk mencoba pembacaan")
    scrape.add_argument("url")
    scrape.add_argument(
        "--render", default=argparse.SUPPRESS, choices=list(config.RENDER_MODES),
        help="ambil ulang halaman ber-JavaScript dengan peramban",
    )
    scrape.add_argument(
        "--tunggu", default=argparse.SUPPRESS, metavar="SELEKTOR",
        help="tunggu selektor CSS ini muncul sebelum halaman diserahkan",
    )
    scrape.set_defaults(func=cmd_scrape)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nDihentikan.")
        return 130
    except fetch.BlockedError as error:
        print(f"Ditolak: {error}", file=sys.stderr)
        return 3
    except fetch.FetchError as error:
        print(f"Gagal mengambil halaman: {error}", file=sys.stderr)
        return 4
    except KeyError as error:
        print(str(error), file=sys.stderr)
        return 5
