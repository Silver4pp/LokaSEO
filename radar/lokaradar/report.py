"""Menyusun laporan manusiawi dan paket wawasan untuk LokaSEO.

Dua keluaran:

- Laporan Markdown: enak dibaca, bisa dicetak atau dikirim ke klien.
- Paket wawasan JSON (`lokaradar.insight.v1`): berisi ide konten dan butir
  ceklis yang siap dipindahkan ke proyek LokaSEO.
"""

import json
import re
import time
from pathlib import Path

from . import config
from .extract import readable_prices
from . import profil as profil_mod
from .reputasi import board as reputation_board
from .reputasi import board_markdown, suggestions as reputation_suggestions

SEVERITY_LABEL = {
    "tinggi": "Penting",
    "sedang": "Perlu dilihat",
    "rendah": "Catatan",
    "info": "Informasi",
}


def _iso(seconds: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds or time.time()))


def _slug(text: str, limit: int = 60) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return clean[:limit] or "laporan"


def summarize(rows: list[dict]) -> dict:
    per_severity: dict[str, int] = {}
    per_type: dict[str, int] = {}
    for row in rows:
        for change in row.get("changes", []):
            per_severity[change["severity"]] = per_severity.get(change["severity"], 0) + 1
            per_type[change["type"]] = per_type.get(change["type"], 0) + 1
    return {
        "sasaran": len(rows),
        "perubahan": sum(len(row.get("changes", [])) for row in rows),
        "per_tingkat": per_severity,
        "per_jenis": per_type,
    }


def _keyword_hints(facts: dict, profil: "profil_mod.Profil | None" = None) -> list[str]:
    """Ambil usulan kata kunci dari judul bagian halaman yang dipantau."""
    hints: list[str] = []
    for heading in facts.get("h2", []) or []:
        words = [word for word in re.split(r"\s+", heading.strip()) if len(word) > 2]
        if 2 <= len(words) <= 6:
            hints.append(" ".join(heading.split())[:80].lower())
    if not hints and facts.get("title"):
        hints.append(" ".join(str(facts["title"]).split())[:80].lower())
    if not hints and profil is not None:
        # Jenis usaha dari proyek LokaSEO menjadi cadangan kata kunci.
        hints.extend(profil.kata_kunci)
    return hints[:6]


def lokaseo_suggestions(rows: list[dict], profil: "profil_mod.Profil | None" = None) -> dict:
    """Ubah temuan menjadi usulan konkret untuk ruang kerja LokaSEO."""
    ideas: list[dict] = []
    checks: list[dict] = []
    notes: list[str] = []
    seen_ideas: set[str] = set()

    def idea(title: str, reason: str, keywords: list[str]) -> None:
        if title in seen_ideas or len(ideas) >= 12:
            return
        seen_ideas.add(title)
        ideas.append(
            {
                "judul": title,
                "alasan": reason,
                "kata_kunci_usulan": keywords,
                "sumber": "LokaRadar",
            }
        )

    for row in rows:
        facts = row.get("facts", {})
        hints = _keyword_hints(facts, profil)
        label = row.get("label") or row["url"]
        for change in row.get("changes", []):
            kind = change["type"]
            if kind == "harga_turun":
                idea(
                    f"Menjelaskan nilai layanan saat harga pesaing turun ({label})",
                    change["message"],
                    hints[:3] or [f"{label} harga"],
                )
                checks.append(
                    {
                        "judul": "Tinjau harga dan paket sendiri",
                        "keterangan": f"{label}: {change['message']}",
                        "prioritas": change["severity"],
                    }
                )
            elif kind == "jumlah_ulasan_berubah" and (change.get("after") or 0) > (change.get("before") or 0):
                idea(
                    "Cara meminta ulasan pelanggan tanpa melanggar aturan Google",
                    change["message"],
                    ["meminta ulasan google", "ulasan pelanggan", "reputasi lokal"],
                )
                checks.append(
                    {
                        "judul": "Jalankan permintaan ulasan ke pelanggan lama",
                        "keterangan": change["message"],
                        "prioritas": "tinggi",
                    }
                )
            elif kind == "rating_berubah":
                idea(
                    "Menjawab ulasan negatif dengan benar",
                    change["message"],
                    ["menjawab ulasan negatif", "keluhan pelanggan"],
                )
            elif kind == "schema_lokal_baru":
                checks.append(
                    {
                        "judul": "Tambahkan data terstruktur LocalBusiness",
                        "keterangan": f"{label} sudah memakainya. Data terstruktur membantu mesin pencari memahami bisnis Anda.",
                        "prioritas": "sedang",
                    }
                )
            elif kind == "noindex_aktif":
                notes.append(
                    f"{label} memakai noindex. Ini kesempatan memeriksa halaman sendiri yang mungkin tidak sengaja diblokir."
                )
            elif kind == "bagian_baru":
                heading = str(change.get("after") or "").strip()
                idea(
                    f"Menyiapkan halaman layanan serupa: {heading}" if heading else "Menambah halaman layanan baru",
                    change["message"],
                    [heading.lower()] if heading else hints[:2],
                )
                checks.append(
                    {
                        "judul": "Periksa apakah layanan ini perlu Anda tawarkan",
                        "keterangan": f"{label}: {change['message']}",
                        "prioritas": change["severity"],
                    }
                )
            elif kind == "judul_berubah":
                checks.append(
                    {
                        "judul": "Perbarui judul halaman sendiri bila perlu",
                        "keterangan": f"{label}: {change['message']}",
                        "prioritas": "rendah",
                    }
                )
        if facts.get("has_local_business") and not any(
            check["judul"].startswith("Tambahkan data terstruktur") for check in checks
        ):
            checks.append(
                {
                    "judul": "Lengkapi profil bisnis lokal sendiri",
                    "keterangan": f"{label} memakai data terstruktur bisnis lokal; pastikan situs Anda juga mengenali kota layanan.",
                    "prioritas": "sedang",
                }
            )
        if facts.get("images_without_alt"):
            notes.append(
                f"{label}: {facts['images_without_alt']} gambar tanpa teks alternatif — periksa apakah situs Anda lebih rapi."
            )
    return {"ide_konten": ideas, "cek_list": checks[:12], "catatan": notes[:12]}


def _tanpa_kembar(baris: list[str]) -> list[str]:
    """Buang catatan yang sama tanpa mengubah urutannya.

    Satu jenis masalah (mis. peramban belum terunduh) bisa muncul untuk banyak
    sasaran sekaligus. Menuliskannya berulang membuat daftar saran sulit dibaca,
    padahal isinya sama saja.
    """
    dilihat: set[str] = set()
    hasil: list[str] = []
    for baris in baris:
        kunci = baris.strip()
        if not kunci or kunci in dilihat:
            continue
        dilihat.add(kunci)
        hasil.append(baris)
    return hasil


def build_pack(
    rows: list[dict],
    *,
    since: str | None = None,
    store=None,
    days: int = 30,
    min_rating: float | None = None,
    profil: "profil_mod.Profil | None" = None,
) -> dict:
    generated = _iso()
    targets = []
    for row in rows:
        facts = row.get("facts", {})
        targets.append(
            {
                "url": row["url"],
                "label": row.get("label") or "",
                "jenis": row.get("kind", "halaman"),
                "diperiksa_pada": row.get("fetched_at"),
                "status": row.get("status"),
                "judul": facts.get("title", ""),
                "deskripsi": facts.get("description", ""),
                "harga": facts.get("prices", []),
                "harga_terendah": (facts.get("prices") or [{}])[0] if facts.get("prices") else None,
                "rating": facts.get("rating"),
                "data_terstruktur": facts.get("schema_types", []),
                "ringkas_halaman": {
                    "jumlah_kata": facts.get("word_count"),
                    "judul_utama": facts.get("h1_count"),
                    "gambar_tanpa_alt": facts.get("images_without_alt"),
                    "noindex": facts.get("noindex"),
                },
                "perubahan": row.get("changes", []),
                "dirender": bool(row.get("dirender", False)),
                "render_gagal": row.get("render_gagal") or "",
                "catatan_ambil": row.get("catatan_ambil") or "",
                "perlu_render": bool(
                    row.get("perlu_render", False)
                    or (isinstance(row.get("jumlah_kata"), int) and row["jumlah_kata"] < config.RENDER_MIN_WORDS)
                ),
            }
        )
    lokaseo = lokaseo_suggestions(rows, profil)
    papan = None
    if store is not None:
        papan = reputation_board(store, days=days, min_rating=min_rating, profil=profil)
        ide, ceklis, catatan = reputation_suggestions(papan)
        lokaseo["ide_konten"].extend(ide)
        lokaseo["cek_list"].extend(ceklis)
        lokaseo["catatan"].extend(catatan)
    if profil is not None and profil.rating_penting:
        # Lubang yang ditemukan pada uji Bogor: hampir tidak ada usaha lokal yang
        # memuat rating di situsnya, jadi jalur resmi perlu diusulkan lebih dulu.
        # Sasaran tempat bisa belum punya potret (kunci belum dijalankan), jadi
        # daftar sasaran di basis data yang diperiksa lebih dulu.
        sumber_sasaran = store.targets() if store is not None else rows
        ada_tempat = any(str(row.get("url", "")).startswith("tempat:") for row in sumber_sasaran)
        if not ada_tempat:
            lokaseo["cek_list"].append(
                {
                    "judul": "Tambahkan sasaran rating resmi (Google Places API)",
                    "keterangan": (
                        f"Belum ada sasaran tempat:<place_id>. Untuk {profil.jenis_label or 'jenis usaha ini'}, "
                        "rating biasanya tidak ditulis di situs sendiri — pakai "
                        f"`python -m lokaradar cari \"{profil.nama or 'nama usaha'}\" --kota {profil.kota or 'kota Anda'}` "
                        "dengan kunci Places API Anda sendiri."
                    ),
                    "prioritas": "sedang",
                }
            )
            lokaseo["catatan"].append(f"Sumber rating — {profil.saran_sumber_rating}")
    # Halaman yang isinya dibuat JavaScript: pembacaan biasa hampir tidak
    # menghasilkan apa-apa, jadi pembaca laporan perlu tahu sebabnya.
    for row in rows:
        if str(row.get("url", "")).startswith("tempat:"):
            continue
        kata = row.get("jumlah_kata")
        if row.get("dirender"):
            lokaseo["catatan"].append(
                f"Halaman {row.get('label') or row['url']} diambil ulang dengan peramban karena "
                "isinya dibuat JavaScript."
            )
        elif row.get("render_gagal"):
            lokaseo["catatan"].append(f"Rendering — {row['render_gagal']}")
        elif row.get("catatan_ambil"):
            lokaseo["catatan"].append(f"Pengambilan — {row['catatan_ambil']}")
        elif row.get("perlu_render") and isinstance(kata, int) and kata < config.RENDER_MIN_WORDS:
            lokaseo["cek_list"].append(
                {
                    "judul": "Buka halaman dengan peramban (isi dibuat JavaScript)",
                    "keterangan": (
                        f"Halaman {row.get('label') or row['url']} hanya terbaca {kata} kata, "
                        "tanda isinya dibuat JavaScript. Jalankan `python -m lokaradar run --render selalu` "
                        "bila peramban (Chromium) sudah terpasang."
                    ),
                    "prioritas": "rendah",
                }
            )
    if profil is not None:
        # Pemeriksaan yang lahir dari jenis usaha: hanya berlaku untuk situs sendiri.
        for row in rows:
            if not profil.is_milik_sendiri(row["url"]):
                continue
            types = {str(item) for item in (row.get("facts", {}).get("schema_types") or [])}
            diharapkan = set(profil.schema_diharapkan)
            if diharapkan and not (types & diharapkan):
                lokaseo["cek_list"].append(
                    {
                        "judul": "Lengkapi data terstruktur sesuai jenis usaha",
                        "keterangan": (
                            f"Halaman {profil.nama or row['url']} belum memuat data terstruktur "
                            f"{', '.join(sorted(diharapkan))} yang wajar untuk {profil.jenis_label or 'jenis usaha ini'}."
                        ),
                        "prioritas": "sedang",
                    }
                )
        for baris in profil.catatan:
            if baris:
                lokaseo["catatan"].append(f"Jenis usaha — {baris}")
    lokaseo["catatan"] = _tanpa_kembar(lokaseo["catatan"])
    return {
        "schema": config.INSIGHT_SCHEMA,
        "dibuat_pada": generated,
        "sejak": since,
        "profil": profil.to_dict() if profil is not None else None,
        "ringkasan": summarize(rows),
        "sasaran": targets,
        "reputasi": papan,
        "lokaseo": lokaseo,
        "catatan_pemakaian": [
            "Data diambil dari halaman publik tanpa login, dengan jeda sopan dan menghormati robots.txt.",
            "Hanya angka agregat (rating, jumlah ulasan) yang disimpan; identitas penulis ulasan tidak diambil.",
            "Angka dapat berubah kapan saja; verifikasi sebelum memakai untuk keputusan penting.",
        ],
    }


def markdown(pack: dict) -> str:
    lines: list[str] = []
    ringkas = pack["ringkasan"]
    lines.append("# Laporan LokaRadar\n")
    profil = pack.get("profil")
    if profil:
        baris_profil = profil_mod.ringkas(profil_mod.Profil.from_dict(profil))
        if baris_profil:
            lines.append(f"Usaha: {baris_profil}\n")
    lines.append(f"Dibuat: {pack['dibuat_pada']}  ")
    if pack.get("sejak"):
        lines.append(f"Periode perubahan: sejak {pack['sejak']}  ")
    lines.append(f"Sasaran dipantau: {ringkas['sasaran']} · perubahan: {ringkas['perubahan']}\n")
    if ringkas["per_tingkat"]:
        rincian = ", ".join(
            f"{SEVERITY_LABEL.get(key, key)}: {value}" for key, value in sorted(ringkas["per_tingkat"].items())
        )
        lines.append(f"Tingkat: {rincian}\n")
    lines.append("---\n")

    model = profil_mod.Profil.from_dict(profil) if profil else None
    for target in pack["sasaran"]:
        nama = target["label"] or target["url"]
        lines.append(f"## {nama}\n")
        if model is not None:
            peran = "Situs sendiri" if model.is_milik_sendiri(target["url"]) else "Pesaing / mitra"
            lines.append(f"- Peran: {peran}")
        lines.append(f"- Alamat: {target['url']}")
        if target.get("dirender"):
            lines.append("- Pengambilan: dengan peramban (isi dibuat JavaScript)")
        lines.append(f"- Diperiksa: {target.get('diperiksa_pada')}")
        if target.get("judul"):
            lines.append(f"- Judul halaman: {target['judul']}")
        if target.get("harga"):
            lines.append(f"- Harga terbaca: {readable_prices({'prices': target['harga']})}")
        rating = target.get("rating")
        if rating and (rating.get("value") is not None or rating.get("count") is not None):
            scale = rating.get("scale")
            scale_text = f"{int(scale)}" if isinstance(scale, float) and scale.is_integer() else f"{scale}"
            lines.append(
                f"- Rating agregat: {rating.get('value')} dari {scale_text} "
                f"({rating.get('count')} ulasan)"
            )
        if target.get("data_terstruktur"):
            lines.append(f"- Data terstruktur: {', '.join(target['data_terstruktur'][:8])}")
        changes = target.get("perubahan") or []
        if changes:
            lines.append("\n**Perubahan terdeteksi**\n")
            for change in changes:
                lines.append(f"- [{SEVERITY_LABEL.get(change['severity'], change['severity'])}] {change['message']}")
        else:
            # Ringkas: laporan bisa memuat banyak sasaran, jadi ketiadaan perubahan
            # cukup ditulis sebagai satu butir, bukan paragraf.
            lines.append("- Perubahan: tidak ada dibanding pemeriksaan sebelumnya")
        if lines[-1] != "":
            lines.append("")

    papan = pack.get("reputasi")
    if papan:
        potongan = board_markdown(papan)
        if potongan:
            lines.append("---\n")
            lines.append(potongan)

    lokaseo = pack["lokaseo"]
    if lokaseo["ide_konten"]:
        lines.append("---\n\n## Usulan ide konten\n")
        for item in lokaseo["ide_konten"]:
            lines.append(f"### {item['judul']}\n")
            lines.append(f"- Alasan: {item['alasan']}")
            if item["kata_kunci_usulan"]:
                lines.append(f"- Kata kunci usulan: {', '.join(item['kata_kunci_usulan'])}")
            lines.append("")
    if lokaseo["cek_list"]:
        lines.append("## Butir ceklis\n")
        for item in lokaseo["cek_list"]:
            lines.append(f"- [{item['prioritas']}] **{item['judul']}** — {item['keterangan']}")
        lines.append("")
    if lokaseo["catatan"]:
        lines.append("## Catatan\n")
        for note in lokaseo["catatan"]:
            lines.append(f"- {note}")
        lines.append("")
    lines.append("---\n")
    for note in pack["catatan_pemakaian"]:
        lines.append(f"> {note}")
    lines.append("")
    return "\n".join(lines)


def write_reports(pack: dict, directory: Path, stamp: str | None = None) -> dict:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    json_path = directory / f"wawasan-{stamp}.json"
    md_path = directory / f"laporan-{stamp}.md"
    json_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown(pack), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
