"""Papan reputasi lokal: rating dan jumlah ulasan agregat beberapa usaha.

Modul ini **tidak** mengambil ulasan, nama penulis, atau isi komentar. Yang
dihitung hanya angka agregat yang sudah dipublikasikan halaman (atau angka resmi
dari Google Places API bila pengguna memakai kuncinya sendiri):

- rating rata-rata dan skalanya,
- jumlah ulasan,
- laju pertumbuhan ulasan per minggu dari riwayat potret.

Dari angka itu disusun papan peringkat usaha lokal (milik sendiri dan pesaing
sekitar) beserta tanda perhatian, misalnya rating turun atau ulasan yang berhenti
bertambah.
"""

import time
from statistics import mean

from . import config
from . import profil as profil_mod

DEFAULT_MIN_RATING = 4.0
DEFAULT_MIN_WEEKLY_REVIEWS = 1.0
LAMBANG_TANDA = {
    "belum_ada_rating": "belum ada rating terbaca",
    "data_kurang": "riwayat masih kurang",
    "rating_rendah": "rating di bawah ambang",
    "rating_turun": "rating menurun",
    "ulasan_menurun": "jumlah ulasan berkurang",
    "ulasan_lambat": "ulasan bertambah lambat",
}


def _iso(seconds: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds or time.time()))


def _hari_antara(awal: str, akhir: str) -> float:
    def parse(stamp: str) -> float:
        try:
            return time.mktime(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
        except ValueError:
            return 0.0

    return max((parse(akhir) - parse(awal)) / 86400, 0.0)


def _titik(potret: dict) -> dict:
    rating = potret["facts"].get("rating") or {}
    return {
        "tanggal": potret["fetched_at"],
        "status": potret.get("status", 0),
        "rating": rating.get("value"),
        "ulasan": rating.get("count"),
        "skala": rating.get("scale"),
    }


def profile(store, target: dict, *, days: int = 30, max_points: int = 40) -> dict:
    """Ringkas reputasi satu sasaran dari riwayat potretnya."""
    sejak = _iso(time.time() - days * 86400)
    potret = store.snapshots(int(target["id"]), since=sejak)
    titik = [_titik(row) for row in potret]
    if len(titik) > max_points:
        langkah = max(len(titik) // max_points, 1)
        titik = titik[::langkah][-max_points:]

    berating = [row for row in titik if row["rating"] is not None]
    berhitung = [row for row in titik if isinstance(row["ulasan"], int)]

    hasil = {
        "target_id": int(target["id"]),
        "label": target["label"] or target["url"],
        "url": target["url"],
        "jenis": target["kind"],
        "sumber": "places-api" if str(target["url"]).startswith("tempat:") else "halaman",
        "periode_hari": days,
        "jumlah_potret": len(titik),
        "titik": titik,
        "rating": berating[-1]["rating"] if berating else None,
        "skala": berating[-1]["skala"] if berating else None,
        "rasio": None,
        "rating_awal": berating[0]["rating"] if berating else None,
        "perubahan_rating": None,
        "ulasan": berhitung[-1]["ulasan"] if berhitung else None,
        "ulasan_awal": berhitung[0]["ulasan"] if berhitung else None,
        "ulasan_baru": None,
        "laju_mingguan": None,
        "hari_terukur": None,
        "pangsa_ulasan": None,
    }
    if hasil["rating"] is not None and hasil["skala"]:
        # Skala bisa berbeda antar situs (4,5 dari 5 vs 9,9 dari 10). Peringkat
        # harus memakai rasio, bukan angka mentah.
        hasil["rasio"] = round(float(hasil["rating"]) / float(hasil["skala"]), 4)
    if len(berating) >= 2:
        hasil["perubahan_rating"] = round(berating[-1]["rating"] - berating[0]["rating"], 2)
    if len(berhitung) >= 2:
        hari = _hari_antara(berhitung[0]["tanggal"], berhitung[-1]["tanggal"])
        selisih = berhitung[-1]["ulasan"] - berhitung[0]["ulasan"]
        hasil["ulasan_baru"] = selisih
        hasil["hari_terukur"] = round(hari, 2)
        if hari >= 0.5:
            hasil["laju_mingguan"] = round(selisih / hari * 7, 2)
    return hasil


def tanda(profile_row: dict, *, min_rating: float = DEFAULT_MIN_RATING, min_weekly: float = DEFAULT_MIN_WEEKLY_REVIEWS) -> list[str]:
    """Tanda perhatian untuk satu profil reputasi."""
    hasil: list[str] = []
    if profile_row.get("rating") is None:
        hasil.append("belum_ada_rating")
    if profile_row.get("jumlah_potret", 0) < 2:
        hasil.append("data_kurang")
    if profile_row.get("rating") is not None and profile_row["rating"] < min_rating:
        hasil.append("rating_rendah")
    perubahan = profile_row.get("perubahan_rating")
    if perubahan is not None and perubahan <= -0.1:
        hasil.append("rating_turun")
    ulasan_baru = profile_row.get("ulasan_baru")
    if ulasan_baru is not None and ulasan_baru < 0:
        hasil.append("ulasan_menurun")
    laju = profile_row.get("laju_mingguan")
    if laju is not None and laju < min_weekly:
        hasil.append("ulasan_lambat")
    return hasil


def board(
    store,
    *,
    days: int = 30,
    min_rating: float | None = None,
    min_weekly: float = DEFAULT_MIN_WEEKLY_REVIEWS,
    only_rated: bool = False,
    profil: "profil_mod.Profil | None" = None,
) -> dict:
    """Papan peringkat reputasi untuk semua sasaran aktif.

    Ambang rating mengikuti jenis usaha pada profil bila tidak diberikan.
    Bila profil memuat situs sendiri, baris untuk situs itu ditandai
    `milik_sendiri` sehingga laporan bisa membedakan usaha sendiri dan pesaing.
    """
    if min_rating is None:
        min_rating = profil.ambang_rating if profil is not None else DEFAULT_MIN_RATING
    baris: list[dict] = []
    dilewati: list[dict] = []
    for target in store.targets(enabled_only=True):
        row = profile(store, target, days=days)
        if not row["jumlah_potret"]:
            # Belum pernah berhasil diperiksa: ringkasan putaran sudah melaporkan
            # kegagalannya, jadi sasaran ini tidak perlu memenuhi papan.
            row["tanda"] = []
            row["peringkat"] = None
            row["milik_sendiri"] = False
            dilewati.append(row)
            continue
        row["tanda"] = tanda(row, min_rating=min_rating, min_weekly=min_weekly)
        row["milik_sendiri"] = bool(profil is not None and profil.is_milik_sendiri(row["url"]))
        baris.append(row)

    berating = [row for row in baris if row["rating"] is not None]
    berating.sort(key=lambda row: (row.get("rasio") or 0, row["ulasan"] or 0), reverse=True)
    for index, row in enumerate(berating, start=1):
        row["peringkat"] = index
    for row in baris:
        row.setdefault("peringkat", None)

    total_baru = sum(row["ulasan_baru"] for row in berating if isinstance(row["ulasan_baru"], int))
    skala = {row["skala"] for row in berating if row["skala"] is not None}
    catatan = []
    if len(skala) > 1:
        catatan.append(
            "Skala rating berbeda antar usaha ("
            + ", ".join(str(int(item)) if float(item).is_integer() else str(item) for item in sorted(skala))
            + "). Peringkat memakai rasio terhadap skala masing-masing, bukan angka mentah."
        )
    papan = {
        "periode_hari": days,
        "dibuat_pada": _iso(),
        "usaha": profil_mod.ringkas(profil) if profil is not None else "",
        "jenis_usaha": profil.jenis_label if profil is not None else "",
        "ambang_rating": min_rating,
        "ambang_laju_mingguan": min_weekly,
        "ringkasan": {
            "usaha": len(baris),
            "dengan_rating": len(berating),
            "rata_rata_rating": round(mean([row["rating"] for row in berating]), 2) if berating else None,
            # Rata-rata mentah bisa menyesatkan bila skalanya berbeda, jadi
            # disediakan juga angka setara skala 5.
            "rata_rata_setara_5": (
                round(mean([row["rasio"] for row in berating if row.get("rasio")]) * 5, 2)
                if any(row.get("rasio") for row in berating)
                else None
            ),
            "total_ulasan": sum(row["ulasan"] for row in berating if isinstance(row["ulasan"], int)) or None,
            "total_ulasan_baru": total_baru if any(isinstance(row["ulasan_baru"], int) for row in berating) else None,
            "tanpa_rating": len(baris) - len(berating),
        },
        "peringkat": berating,
        "perhatian": [row for row in baris if row["tanda"]],
        "belum_terperiksa": [row["label"] for row in dilewati],
        "catatan": catatan,
    }
    # Pangsa ulasan dihitung setelah total diketahui.
    total = papan["ringkasan"]["total_ulasan"]
    if total:
        for row in berating:
            if isinstance(row["ulasan"], int):
                row["pangsa_ulasan"] = round(row["ulasan"] / total * 100, 1)
    return papan


def _skala_text(skala) -> str:
    if isinstance(skala, float) and skala.is_integer():
        return str(int(skala))
    return str(skala if skala is not None else 5)


def board_markdown(papan: dict) -> str:
    """Papan reputasi sebagai potongan Markdown berbahasa Indonesia."""
    if not papan["peringkat"] and not papan["perhatian"]:
        return ""
    baris = ["## Papan reputasi lokal", ""]
    ringkas = papan["ringkasan"]
    if papan.get("usaha"):
        baris.append(f"Usaha: {papan['usaha']}")
        baris.append("")
    baris.append(
        f"{ringkas['usaha']} usaha dipantau · {ringkas['dengan_rating']} punya rating terbaca · "
        f"periode {papan['periode_hari']} hari"
    )
    baris.append("")
    if papan["peringkat"]:
        baris.append("| # | Usaha | Rating | Setara | Ulasan | Ulasan baru | Laju/minggu | Sumber |")
        baris.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for row in papan["peringkat"]:
            rating = f"{row['rating']} / {_skala_text(row['skala'])}" if row["rating"] is not None else "—"
            ulasan = row["ulasan"] if isinstance(row["ulasan"], int) else "—"
            baru = row["ulasan_baru"] if isinstance(row["ulasan_baru"], int) else "—"
            laju = row["laju_mingguan"] if row["laju_mingguan"] is not None else "—"
            sumber = "Places API" if row["sumber"] == "places-api" else "halaman"
            nama = f"{row['label']} **(usaha Anda)**" if row.get("milik_sendiri") else row["label"]
            setara = f"{round((row.get('rasio') or 0) * 5, 2)} / 5" if row.get("rasio") else "—"
            baris.append(
                f"| {row['peringkat']} | {nama} | {rating} | {setara} | {ulasan} | {baru} | {laju} | {sumber} |"
            )
        baris.append("")
    if papan["perhatian"]:
        baris.append("**Perlu perhatian**")
        baris.append("")
        for row in papan["perhatian"]:
            catatan = ", ".join(LAMBANG_TANDA.get(kode, kode) for kode in row["tanda"])
            baris.append(f"- **{row['label']}** ({row['rating'] if row['rating'] is not None else 'tanpa rating'}): {catatan}")
        baris.append("")
    for baris_catatan in papan.get("catatan", []):
        baris.append(f"> {baris_catatan}")
        baris.append("")
    baris.append(
        "> Hanya angka agregat yang disimpan: rating, jumlah ulasan, dan waktu pengambilan. "
        "Isi ulasan dan identitas penulisnya tidak pernah diambil."
    )
    baris.append("")
    return "\n".join(baris)


def suggestions(papan: dict) -> tuple[list[dict], list[dict], list[str]]:
    """Usulan kerja LokaSEO dari papan reputasi: (ide konten, ceklis, catatan)."""
    ide: list[dict] = []
    ceklis: list[dict] = []
    catatan: list[str] = []
    for row in papan["perhatian"]:
        label = row["label"]
        kode = set(row["tanda"])
        if "rating_rendah" in kode or "rating_turun" in kode:
            ide.append(
                {
                    "judul": "Cara membalas ulasan pelanggan dengan sopan dan tetap manusiawi",
                    "alasan": f"{label}: rating sekarang {row['rating']} (ambang {papan['ambang_rating']}).",
                    "kata_kunci_usulan": ["membalas ulasan pelanggan", "layanan pelanggan"],
                    "sumber": "LokaRadar",
                }
            )
            ceklis.append(
                {
                    "judul": "Tindak lanjuti ulasan yang menurunkan rating",
                    "keterangan": f"{label}: rating {row['rating']}, perubahan {row['perubahan_rating']}.",
                    "prioritas": "tinggi",
                }
            )
        if "ulasan_lambat" in kode:
            ceklis.append(
                {
                    "judul": "Minta ulasan ke pelanggan terakhir",
                    "keterangan": f"{label}: laju {row['laju_mingguan']} ulasan per minggu — masih di bawah ambang.",
                    "prioritas": "sedang",
                }
            )
        if "ulasan_menurun" in kode:
            catatan.append(
                f"{label}: jumlah ulasan berkurang {abs(row['ulasan_baru'])}. Platform terkadang "
                "menghapus ulasan; periksa dasbor profil usaha Anda sebelum menyimpulkan."
            )
        if "belum_ada_rating" in kode:
            catatan.append(
                f"{label}: belum ada rating terbaca. Pastikan halaman yang dipantau memang memuat "
                "data rating, atau pakai sumber resmi Google Places API."
            )
    return ide, ceklis, catatan
