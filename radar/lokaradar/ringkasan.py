"""Ringkasan pemantauan: apa yang berubah, diurutkan menurut yang penting.

Daftar perubahan apa adanya tidak bisa dipakai untuk mengambil keputusan. Dengan
lima sasaran yang diperiksa setiap hari, seminggu sudah menghasilkan puluhan
baris — dan yang penting tenggelam di antara "isi halaman berubah" yang sama
berulang-ulang. Modul ini menyusunnya ulang:

- perubahan dikelompokkan menurut **sasaran + jenis + pesan**, lalu dihitung
  berapa kali terjadi. Pola yang muncul belasan kali dalam seminggu hampir
  selalu bising (situs yang menukar teks kecilnya sendiri), dan lebih baik
  dinyatakan terus terang daripada ditulis 14 kali;
- yang **perlu dilihat** (tingkat tinggi dan sedang) ditaruh paling atas;
- sasaran yang tidak berubah disebut sekali sebagai satu baris, bukan lima blok.

Daftar perubahan kronologis tidak diulang di sini: halaman radar sudah
memuatnya dari endpoint sendiri, dan mengirim duplikatnya hanya akan menambah
dua sumber kebenaran untuk baris yang sama.
"""

from __future__ import annotations

import calendar
import time
from collections import Counter

# Urutan tingkat, dari yang paling perlu dilihat.
URUTAN_TINGKAT = ("tinggi", "sedang", "rendah", "info")
# Tingkat yang masuk bagian "perlu dilihat".
TINGKAT_PENTING = ("tinggi", "sedang")
LABEL_TINGKAT = {
    "tinggi": "Penting",
    "sedang": "Perlu dilihat",
    "rendah": "Catatan",
    "info": "Informasi",
}

# Berapa kali sebuah pola harus muncul sebelum disebut "berulang".
AMBANG_BERULANG = 3


def _iso(detik: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(detik or time.time()))


def _pangkat(tingkat: str) -> int:
    """Nomor urut tingkat; tingkat yang tidak dikenal paling akhir."""
    return URUTAN_TINGKAT.index(tingkat) if tingkat in URUTAN_TINGKAT else len(URUTAN_TINGKAT)


def _detik(stempel: str | None) -> int:
    """Stempel ISO jadi detik UTC, untuk mengurutkan. 0 bila kosong."""
    teks = str(stempel or "").strip()
    if len(teks) < 19:
        return 0
    try:
        return calendar.timegm(time.strptime(teks[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return 0


def _tanggal(nilai: str | None) -> str:
    """`2026-10-14T02:31:00Z` -> `14 Okt`. Kosong bila tidak terbaca."""
    teks = str(nilai or "").strip()
    if len(teks) < 10:
        return ""
    bulan = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "Mei", "06": "Jun",
        "07": "Jul", "08": "Agu", "09": "Sep", "10": "Okt", "11": "Nov", "12": "Des",
    }
    try:
        hari = int(teks[8:10])
    except ValueError:
        return ""
    return f"{hari} {bulan.get(teks[5:7], teks[5:7])}"


def _nama_sasaran(baris: dict) -> str:
    return (baris.get("label") or "").strip() or baris.get("url") or "(tanpa nama)"


# -- penyusunan ---------------------------------------------------------------

def _rekap_potret(store, sasaran: list[dict], sejak: str) -> tuple[int, str, dict[int, int]]:
    """Hitung potret per sasaran: (total, stempel terakhir, jumlah per sasaran)."""
    total = 0
    terakhir = ""
    per_sasaran: dict[int, int] = {}
    for target in sasaran:
        potret = store.snapshots(target["id"], since=sejak)
        per_sasaran[int(target["id"])] = len(potret)
        total += len(potret)
        for item in potret:
            pada = str(item.get("fetched_at") or "")
            if pada > terakhir:
                terakhir = pada
    return total, terakhir, per_sasaran


def _kelompokkan(perubahan: list[dict]) -> list[dict]:
    """Perubahan yang sama pada sasaran yang sama jadi satu baris berhitungan."""
    kumpulan: dict[tuple, dict] = {}
    for baris in perubahan:
        kunci = (baris.get("target_id"), baris.get("type"), (baris.get("message") or "").strip())
        if kunci not in kumpulan:
            kumpulan[kunci] = {
                "target_id": baris.get("target_id"),
                "sasaran": _nama_sasaran(baris),
                "url": baris.get("url") or "",
                "jenis": baris.get("type") or "",
                "tingkat": baris.get("severity") or "info",
                "pesan": (baris.get("message") or "").strip(),
                "stempel": [],
            }
        kumpulan[kunci]["stempel"].append(str(baris.get("detected_at") or ""))

    hasil = []
    for item in kumpulan.values():
        # Stempel ISO urut menurut abjad sama seperti menurut waktu, jadi
        # cukup diurutkan; yang kosong dibuang agar tidak jadi yang terlama.
        stempel = sorted(s for s in item.pop("stempel") if s)
        item["jumlah"] = len(stempel)
        item["pertama"] = stempel[0] if stempel else ""
        item["terakhir"] = stempel[-1] if stempel else ""
        hasil.append(item)
    return hasil


def _urutkan(kelompok: list[dict]) -> list[dict]:
    """Tingkat paling dulu, lalu yang paling sering muncul, lalu yang paling baru.

    Semua kunci digabung dalam satu `sorted()`. Dua kali urut berurutan membuat
    yang kedua menimpa yang pertama — dan pernah membuat urutan waktu terbuang
    walau komentarnya mengatakan sebaliknya.
    """
    return sorted(
        kelompok,
        key=lambda item: (_pangkat(item["tingkat"]), -item["jumlah"], -_detik(item["terakhir"])),
    )


def _tanpa_perubahan(
    sasaran: list[dict],
    punya_perubahan: set,
    hitung_potret: dict[int, int],
) -> tuple[list[dict], list[dict]]:
    """Pisahkan "tidak berubah" dari "belum pernah diperiksa".

    "Tidak berubah" adalah klaim: radar sudah melihat isinya dan tidak menemukan
    beda. Sasaran yang belum pernah diambil tidak punya dasar untuk klaim itu,
    jadi tidak boleh digabung dengannya.
    """
    diam: list[dict] = []
    belum: list[dict] = []
    for target in sasaran:
        if target.get("id") in punya_perubahan:
            continue
        butir = {"sasaran": _nama_sasaran(target), "url": target.get("url") or ""}
        if hitung_potret.get(int(target["id"]), 0):
            diam.append(butir)
        else:
            belum.append(butir)
    return diam, belum


def bikin(store, *, hari: int = 7) -> dict:
    """Susun ringkasan pemantauan untuk `hari` hari terakhir.

    `store` adalah `lokaradar.store.Store` yang sudah terbuka.
    """
    hari = max(1, min(int(hari), 90))
    sejak = _iso(time.time() - hari * 86400)

    sasaran = [dict(t) for t in store.targets(enabled_only=True)]
    perubahan = store.changes(since=sejak, limit=1000)

    diperiksa, terakhir, hitung_potret = _rekap_potret(store, sasaran, sejak)
    kelompok = _urutkan(_kelompokkan(perubahan))
    per_tingkat = Counter(baris.get("severity") or "info" for baris in perubahan)
    diam, belum = _tanpa_perubahan(
        sasaran, {baris.get("target_id") for baris in perubahan}, hitung_potret
    )

    return {
        "hari": hari,
        "sejak": sejak,
        "sasaran": len(sasaran),
        "diperiksa": diperiksa,
        "perubahan": len(perubahan),
        "per_tingkat": {tingkat: per_tingkat.get(tingkat, 0) for tingkat in URUTAN_TINGKAT},
        "penting": [item for item in kelompok if item["tingkat"] in TINGKAT_PENTING],
        "berulang": [item for item in kelompok if item["jumlah"] >= AMBANG_BERULANG],
        "diam": diam,
        "belum_diperiksa": belum,
        "terakhir_diperiksa": terakhir or None,
        "ambang_berulang": AMBANG_BERULANG,
    }


# -- tampilan teks ------------------------------------------------------------

def _rentang(item: dict) -> str:
    awal = _tanggal(item.get("pertama"))
    akhir = _tanggal(item.get("terakhir"))
    if awal and akhir and awal != akhir:
        return f"{awal}–{akhir}"
    return awal or akhir or ""


def baris_ringkas(item: dict) -> str:
    """Satu baris untuk satu pola, mis. `**Klinik Sehat** — Harga turun (2x · 12–14 Okt)`."""
    bagian = [teks for teks in (f"{item['jumlah']}x" if item["jumlah"] > 1 else "", _rentang(item)) if teks]
    # Keterangan diletakkan dalam tanda kurung sesudah pesannya: pesan perubahan
    # sudah diakhiri titik, jadi menambahkan koma menghasilkan dua tanda baca.
    akhir = f" ({' · '.join(bagian)})" if bagian else ""
    return f"**{item['sasaran']}** — {item['pesan']}{akhir}"


def markdown(data: dict) -> str:
    """Ringkasan dalam Markdown, untuk laporan dan untuk disalin pengguna."""
    baris = [f"## Sorotan {data['hari']} hari terakhir\n"]
    if not data["sasaran"]:
        baris.append("Belum ada sasaran yang dipantau.\n")
        return "\n".join(baris)

    rincian = " · ".join(
        f"{LABEL_TINGKAT.get(tingkat, tingkat)} {data['per_tingkat'].get(tingkat, 0)}"
        for tingkat in URUTAN_TINGKAT
        if data["per_tingkat"].get(tingkat)
    )
    baris.append(
        f"{data['diperiksa']} kali pemeriksaan · {data['sasaran']} sasaran · "
        f"{data['perubahan']} perubahan" + (f" ({rincian})" if rincian else "") + "\n"
    )
    if data.get("terakhir_diperiksa"):
        baris.append(f"Pemeriksaan terakhir: {data['terakhir_diperiksa']}\n")

    baris.append("### Yang perlu dilihat\n")
    if data["penting"]:
        baris += [f"- {baris_ringkas(item)}" for item in data["penting"]]
    elif data["perubahan"]:
        baris.append("- Tidak ada perubahan bertingkat tinggi atau sedang.")
    else:
        baris.append(
            "- Belum ada perubahan sama sekali. Radar hanya bisa membandingkan "
            "setelah satu sasaran diperiksa dua kali."
        )
    baris.append("")

    if data["berulang"]:
        baris.append("### Pola berulang (kemungkinan bising)\n")
        for item in data["berulang"]:
            # Dua spasi di akhir baris: pemisah baris keras di Markdown, supaya
            # kalimat penjelasnya menempel pada pola yang dijelaskannya.
            baris.append(f"- {baris_ringkas(item)}  ")
            baris.append(
                "  Pola ini muncul berkali-kali pada sasaran yang sama; biasanya situsnya "
                "memang mengubah teks kecilnya sendiri setiap kali diminta."
            )
        baris.append("")

    if data["diam"]:
        nama = ", ".join(item["sasaran"] for item in data["diam"])
        baris.append(f"### Tidak berubah: {nama}\n")

    if data.get("belum_diperiksa"):
        nama = ", ".join(item["sasaran"] for item in data["belum_diperiksa"])
        baris += [
            "### Belum diperiksa dalam periode ini\n",
            f"{nama}\n",
            "Sasaran ini belum pernah diambil dalam periode ini, jadi belum ada yang "
            "bisa dibandingkan. Jalankan pemeriksaan minimal dua kali supaya radar "
            "punya dua potret.\n",
        ]

    return "\n".join(baris)
