"""Menjalankan pemeriksaan radar untuk semua sasaran aktif."""

import logging
import time

from . import config, places
from . import profil as profil_mod
from .diff import compare, highest_severity
from .extract import page_facts
from .fetch import BlockedError, FetchError, page_perlu_render, page_tipis

LOG = logging.getLogger("lokaradar")


def _iso(seconds: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds or time.time()))


LABEL_SUMBER = {
    "permintaan-biasa": "permintaan biasa",
    "peramban": "peramban",
    "places-api": "Places API",
    "": "tidak diketahui",
}


def _perubahan_sumber(lama: str | None, baru: str) -> dict | None:
    """Perubahan cara pengambilan bukan perubahan situs.

    Bila cara pengambilan berubah (mis. peramban baru dipasang), isi halaman
    yang terbaca ikut berubah banyak — bukan karena situsnya berubah. Menghitung
    perbedaan isi pada keadaan itu hanya melahirkan alarm palsu, jadi potret
    dibandingkan ulang dari nol dan pembaca diberi tahu sebabnya.
    """
    sebelumnya = str(lama or "").strip()
    if not sebelumnya or sebelumnya == baru:
        return None
    return {
        "type": "cara_pengambilan_berubah",
        "severity": "info",
        "message": (
            f"Cara pengambilan berubah dari {LABEL_SUMBER.get(sebelumnya, sebelumnya)} "
            f"menjadi {LABEL_SUMBER.get(baru, baru)}. Isi halaman bisa terbaca berbeda karena itu, "
            "bukan karena situsnya berubah — pembandingan isi dimulai ulang dari potret ini."
        ),
        "before": sebelumnya,
        "after": baru,
    }


def _catatan_profil(profil, url: str, facts: dict) -> list[str]:
    """Catatan dari jenis usaha untuk situs sendiri (tidak mengubah riwayat)."""
    if profil is None or not profil.is_milik_sendiri(url):
        return []
    diharapkan = set(profil.schema_diharapkan)
    terlihat = {str(item) for item in (facts.get("schema_types") or [])}
    if diharapkan and not (terlihat & diharapkan):
        return [
            "Data terstruktur untuk jenis usaha "
            f"({profil.jenis_label or profil.jenis or 'belum dipilih'}) belum terlihat; "
            f"yang wajar antara lain: {', '.join(sorted(diharapkan))}."
        ]
    return []


def run_once(
    store,
    fetcher,
    *,
    max_pages: int = config.DEFAULT_MAX_PAGES_PER_RUN,
    only_id: int | None = None,
    places_key: str | None = None,
    places_loader=None,
    profil: "profil_mod.Profil | None" = None,
) -> dict:
    """Periksa setiap sasaran aktif dan simpan potret serta perubahannya.

    Sasaran biasa (`http`/`https`) diambil lewat pengambil halaman. Sasaran
    `tempat:<place_id>` diambil lewat Google Places API memakai kunci milik
    pengguna; tanpa kunci, sasaran itu dicatat sebagai kegagalan, bukan dilewati
    diam-diam.
    """
    targets = store.targets(enabled_only=True)
    if only_id is not None:
        targets = [row for row in targets if int(row["id"]) == int(only_id)]
    rows: list[dict] = []
    checked = failed = blocked = 0
    started = time.time()
    for target in targets:
        if checked + failed + blocked >= max_pages:
            LOG.info("Batas %s halaman per putaran tercapai; sisanya dilewati.", max_pages)
            break
        url = target["url"]
        row = {
            "target_id": int(target["id"]),
            "url": url,
            "label": target["label"],
            "kind": target["kind"],
            "changes": [],
        }
        if str(url).startswith(places.SCHEME):
            try:
                place = places.lookup(
                    places.place_id_of(str(url)),
                    places_key or places.key_from_env() or "",
                    **({"loader": places_loader} if places_loader else {}),
                )
            except (places.PlacesError, ValueError) as error:
                failed += 1
                row.update({"status": 0, "error": str(error), "changes": []})
                LOG.warning("Gagal membaca %s: %s", url, error)
                rows.append(row)
                continue
            facts = places.place_facts(place)
            previous = store.latest_snapshot(int(target["id"]))
            changes = compare(previous["facts"] if previous else None, facts)
            store.save_snapshot(int(target["id"]), 200, facts, 0, sumber="places-api")
            if changes:
                store.save_changes(int(target["id"]), changes)
            checked += 1
            row.update(
                {
                    "status": 200,
                    "facts": facts,
                    "changes": changes,
                    "fetched_at": _iso(),
                    "severity": highest_severity(changes),
                }
            )
            LOG.info("Diperiksa %s (%s perubahan)", url, len(changes))
            rows.append(row)
            continue
        try:
            page = fetcher.get(url)
        except BlockedError as error:
            blocked += 1
            row.update({"status": 0, "error": str(error), "blocked": True, "changes": []})
            LOG.warning("Dilewati: %s", error)
            rows.append(row)
            continue
        except FetchError as error:
            failed += 1
            row.update({"status": 0, "error": str(error), "changes": []})
            LOG.warning("Gagal mengambil %s: %s", url, error)
            rows.append(row)
            continue
        facts = page_facts(page.final_url or url, page.html, page.text)
        catatan_profil = _catatan_profil(profil, url, facts)
        sumber = "peramban" if bool(getattr(page, "rendered", False)) else "permintaan-biasa"
        dirender = sumber == "peramban"
        render_gagal = str(getattr(page, "render_gagal", "") or "")
        # Catatan rendering dipisahkan dari catatan jenis usaha supaya keduanya
        # bisa dibaca sendiri-sendiri tanpa saling mengaburkan.
        catatan_render: list[str] = []
        if dirender:
            LOG.info("Halaman %s diambil ulang dengan peramban (isi dibuat JavaScript).", url)
            catatan_render.append(
                "Halaman ini diambil ulang dengan peramban karena isi aslinya dibuat JavaScript, "
                "jadi angkanya baru terbaca setelah dirender."
            )
        if render_gagal:
            LOG.warning("Catatan rendering untuk %s: %s", url, render_gagal)
            catatan_render.append(render_gagal)
        perlu_render = bool(not dirender and page_perlu_render(page))
        if not dirender and perlu_render:
            catatan_render.append(
                f"Halaman hampir tanpa teks ({facts.get('word_count', 0)} kata) dan terlihat seperti "
                "kerangka JavaScript; jalankan dengan `--render selalu` bila peramban sudah terpasang."
            )
        elif not dirender and page_tipis(page):
            catatan_render.append(
                f"Halaman ini pendek ({facts.get('word_count', 0)} kata). Kalau isinya ternyata disusun "
                "JavaScript, jalankan `--render selalu`."
            )
        previous = store.latest_snapshot(int(target["id"]))
        pindah_sumber = _perubahan_sumber(previous.get("sumber") if previous else None, sumber)
        changes = [pindah_sumber] if pindah_sumber else compare(previous["facts"] if previous else None, facts)
        if pindah_sumber:
            # Cukup dicatat sekali lewat baris perubahan di bawah; mengulanginya
            # sebagai catatan hanya membuat keluaran berbunyi dua kali.
            LOG.info("Cara pengambilan berubah untuk %s; pembandingan isi dimulai ulang.", url)
        store.save_snapshot(
            int(target["id"]),
            page.status,
            facts,
            page.elapsed_ms,
            sumber=sumber,
            catatan=" | ".join(catatan_render),
        )
        if changes:
            store.save_changes(int(target["id"]), changes)
        checked += 1
        row.update(
            {
                "status": page.status,
                "facts": facts,
                "changes": changes,
                "fetched_at": _iso(),
                "severity": highest_severity(changes),
                "milik_sendiri": bool(profil is not None and profil.is_milik_sendiri(url)),
                "catatan_profil": catatan_profil,
                "dirender": dirender,
                "render_gagal": render_gagal,
                "catatan_render": catatan_render,
                "perlu_render": perlu_render,
                "sumber": sumber,
                "kata_statis": getattr(page, "kata_statis", None),
                "render_ms": getattr(page, "render_ms", None),
                "jumlah_kata": facts.get("word_count"),
            }
        )
        LOG.info(
            "Diperiksa %s (%s ms, %s perubahan)",
            url,
            page.elapsed_ms,
            len(changes),
        )
        rows.append(row)
    store.prune_snapshots()
    return {
        "mulai": _iso(started),
        "selesai": _iso(),
        "durasi_detik": round(time.time() - started, 1),
        "diperiksa": checked,
        "gagal": failed,
        "dilewati": blocked,
        "sasaran": rows,
    }
