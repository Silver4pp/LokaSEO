"""Daftar sasaran yang bisa dipindah dan dibagikan: ekspor dan impor.

Berkasnya JSON sederhana supaya bisa diperiksa dengan mata sendiri, dikirim ke
teman lewat surel, atau disimpan sebagai cadangan sebelum komputer diganti:

    {
      "format": "lokaradar.sasaran.v1",
      "dibuat_pada": "2026-10-14T06:30:00Z",
      "jumlah": 4,
      "sasaran": [
        {"url": "https://pesaing.example/menu", "label": "Pesaing Kopi", "jenis": "harga", "aktif": true}
      ]
    }

Tiga janji modul ini:

1. **Impor tidak menghapus apa pun.** Daftar yang ada digabung, bukan diganti.
2. **Impor tidak menghubungi situs mana pun.** Yang disimpan hanya alamatnya;
   pemeriksaan pertama terjadi saat pengguna menjalankan pemeriksaan berikutnya.
3. **Semua yang ditolak disebutkan alasannya.** Berkas yang salah format tidak
   diam-diam dianggap berhasil.
"""

import json
import time
from pathlib import Path

from . import __version__

FORMAT = "lokaradar.sasaran.v1"
JENIS_SAH = ("halaman", "harga", "layanan", "reputasi")
MAKS_ENTRI = 500
MAKS_BITA = 1_000_000  # 1 MB: cukup untuk ratusan alamat, tetap jauh dari berkas raksasa
LABEL_MAKS = 60


class BerkasTidakSah(ValueError):
    """Isi berkas tidak bisa dibaca sebagai daftar sasaran."""


def _sekarang() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def nama_berkas() -> str:
    """Nama berkas yang ramah: sasaran-radar-2026-10-14.json"""
    return f"sasaran-radar-{time.strftime('%Y-%m-%d', time.gmtime())}.json"


def ekspor(store, *, profil: dict | None = None) -> dict:
    """Susun isi berkas daftar sasaran dari basis data pengguna."""
    daftar = []
    for target in store.targets():
        daftar.append(
            {
                "url": str(target["url"]),
                "label": str(target["label"] or ""),
                "jenis": str(target["kind"] or "halaman"),
                "aktif": bool(target["enabled"]),
            }
        )
    berkas = {
        "format": FORMAT,
        "aplikasi": "LokaRadar",
        "versi_aplikasi": __version__,
        "dibuat_pada": _sekarang(),
        "jumlah": len(daftar),
        "sasaran": daftar,
    }
    if profil:
        # Ikut dibaca supaya penerima tahu daftar ini disusun untuk usaha jenis
        # apa. Saat impor, bagian ini **tidak** dipakai: jenis usaha diatur
        # pengguna sendiri, bukan dari berkas orang lain.
        berkas["profil"] = {
            "jenis_usaha": str(profil.get("jenis_usaha") or profil.get("jenis") or ""),
            "nama": str(profil.get("nama") or ""),
            "kota": str(profil.get("kota") or ""),
        }
    return berkas


def tulis(store, berkas: Path, *, profil: dict | None = None) -> dict:
    """Tulis daftar sasaran ke cakram dan kembalikan ringkasannya."""
    isi = ekspor(store, profil=profil)
    berkas.parent.mkdir(parents=True, exist_ok=True)
    berkas.write_text(json.dumps(isi, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"berkas": str(berkas), "jumlah": isi["jumlah"]}


def baca(teks: str) -> tuple[list[dict], list[str], str]:
    """Baca isi berkas menjadi daftar entri.

    Menerima tiga bentuk supaya pengguna tidak perlu menghafal format:

    - berkas JSON buatan LokaRadar (`format: lokaradar.sasaran.v1`),
    - JSON sederhana berupa daftar alamat atau daftar objek `{url, label, jenis}`,
    - teks biasa: satu alamat per baris, baris `#` dianggap catatan.

    Kembaliannya: (entri, catatan, nama format yang terbaca).
    """
    if not isinstance(teks, str):
        raise BerkasTidakSah("Isi berkas harus berupa teks.")
    if len(teks.encode("utf-8", errors="replace")) > MAKS_BITA:
        raise BerkasTidakSah(
            f"Berkas lebih besar dari {MAKS_BITA // 1000} KB. Ekspor ulang atau pecah berkasnya."
        )
    jika_kosong = teks.strip()
    if not jika_kosong:
        raise BerkasTidakSah("Berkas kosong: tidak ada alamat di dalamnya.")

    catatan: list[str] = []
    mentah: list = []
    format_terbaca = "teks"

    if jika_kosong[0] in "[{":
        try:
            isi = json.loads(jika_kosong)
        except json.JSONDecodeError as error:
            raise BerkasTidakSah(
                f"Berkas dimulai seperti JSON tetapi tidak bisa dibaca ({error.msg}, baris {error.lineno})."
            ) from error
        if isinstance(isi, dict):
            format_terbaca = str(isi.get("format") or "tanpa keterangan")
            if format_terbaca not in (FORMAT, "tanpa keterangan"):
                catatan.append(
                    f"Berkas ditulis dengan format “{format_terbaca}”; dibaca sebisanya, "
                    f"format yang dikenal sekarang “{FORMAT}”."
                )
            for kunci in ("sasaran", "targets", "daftar"):
                if isinstance(isi.get(kunci), list):
                    mentah = isi[kunci]
                    break
            else:
                raise BerkasTidakSah(
                    "Di dalam berkas tidak ada daftar bernama “sasaran”. "
                    "Pastikan ini berkas daftar sasaran, bukan laporan atau hasil pemeriksaan."
                )
            if isinstance(isi.get("profil"), dict) and isi["profil"]:
                jenis = str(isi["profil"].get("jenis_usaha") or "").strip()
                catatan.append(
                    "Berkas berisi profil usaha"
                    + (f" “{jenis}”" if jenis else "")
                    + "; profil tidak diimpor — atur jenis usaha di aplikasi."
                )
        elif isinstance(isi, list):
            format_terbaca = "json-daftar"
            mentah = isi
        else:
            raise BerkasTidakSah("Isi JSON harus berupa objek atau daftar.")
    else:
        mentah = [baris for baris in jika_kosong.splitlines()]

    entri: list[dict] = []
    kosong = 0
    for item in mentah:
        if isinstance(item, dict):
            url = str(item.get("url") or item.get("alamat") or "").strip()
            label = str(item.get("label") or item.get("nama") or "").strip()
            jenis = str(item.get("jenis") or item.get("kind") or "").strip().lower()
        else:
            url = str(item or "").strip()
            label = ""
            jenis = ""
        if not url or url.startswith("#"):
            kosong += 1
            continue
        entri.append({"url": url, "label": label, "jenis": jenis})
    if kosong:
        catatan.append(f"{kosong} baris kosong atau komentar diabaikan.")
    if not entri:
        raise BerkasTidakSah("Tidak ada satu pun alamat yang bisa dibaca dari berkas itu.")
    if len(entri) > MAKS_ENTRI:
        catatan.append(f"Hanya {MAKS_ENTRI} entri pertama yang dibaca (berkas memuat {len(entri)}).")
        entri = entri[:MAKS_ENTRI]
    return entri, catatan, format_terbaca


def impor(store, teks: str, *, maksimum: int | None = None, uji_coba: bool = False) -> dict:
    """Gabungkan daftar sasaran dari berkas ke basis data pengguna.

    `maksimum` adalah batas jumlah sasaran yang masih boleh disimpan; entri di
    atas batas itu dilaporkan sebagai `tertunda`, bukan dibuang diam-diam.
    `uji_coba=True` menghitung hasilnya tanpa menulis apa pun ke basis data.
    """
    entri, catatan, format_terbaca = baca(teks)

    hasil = {
        "format": format_terbaca,
        "total_entri": len(entri),
        "ditambahkan": 0,
        "diperbarui": 0,
        "sudah_ada": 0,
        "ganda": 0,
        "ditolak": [],
        "tertunda": 0,
        "uji_coba": bool(uji_coba),
        "catatan": list(catatan),
    }

    sudah = {str(row["url"]) for row in store.targets()}
    terpakai = len(sudah)
    dilihat: set[str] = set()

    for entri_satu in entri:
        url = entri_satu["url"]
        if url in dilihat:
            hasil["ganda"] += 1
            continue
        dilihat.add(url)

        # Jenis kosong berarti "terserah yang sudah ada" — berkas teks yang hanya
        # memuat alamat tidak boleh diam-diam mengubah jenis pantauan sasaran lama.
        jenis = entri_satu["jenis"]
        if jenis and jenis not in JENIS_SAH:
            catatan_jenis = f"Jenis “{jenis}” tidak dikenal; dipakai “halaman”."
            if catatan_jenis not in hasil["catatan"]:
                hasil["catatan"].append(catatan_jenis)
            jenis = "halaman"
        label = entri_satu["label"][:LABEL_MAKS]

        ada = store.find_target(url)
        if ada is None:
            if maksimum is not None and terpakai >= maksimum:
                hasil["tertunda"] += 1
                continue
            try:
                if not uji_coba:
                    store.add_target(url, label, jenis or "halaman")
            except ValueError as error:
                hasil["ditolak"].append({"entri": url, "alasan": str(error)})
                continue
            hasil["ditambahkan"] += 1
            terpakai += 1
            sudah.add(url)
            continue

        # Label kosong di berkas berarti "pertahankan yang sudah ada", bukan
        # "kosongkan labelnya" — dan karena itu bukan perubahan.
        label_dipakai = label or str(ada["label"] or "")
        jenis_dipakai = jenis or str(ada["kind"] or "halaman")
        berubah = (
            str(ada["label"] or "") != label_dipakai
            or str(ada["kind"] or "") != jenis_dipakai
            or not ada["enabled"]
        )
        if not berubah:
            hasil["sudah_ada"] += 1
            continue
        try:
            if not uji_coba:
                store.add_target(url, label_dipakai, jenis_dipakai)
        except ValueError as error:
            hasil["ditolak"].append({"entri": url, "alasan": str(error)})
            continue
        hasil["diperbarui"] += 1

    if hasil["tertunda"]:
        batas = f" {maksimum}" if maksimum is not None else ""
        hasil["catatan"].append(
            f"{hasil['tertunda']} entri tidak diimpor karena daftar sudah mencapai{batas} sasaran; "
            "hapus sasaran yang tidak dipakai lalu impor lagi."
        )
    hasil["sasaran_sekarang"] = terpakai
    return hasil


def ringkas(hasil: dict) -> list[str]:
    """Ubah hasil impor menjadi baris-baris kalimat untuk dicetak atau ditampilkan."""
    baris = []
    if hasil["uji_coba"]:
        baris.append("Uji coba: tidak ada yang disimpan.")
    bagian = []
    if hasil["ditambahkan"]:
        bagian.append(f"{hasil['ditambahkan']} ditambahkan")
    if hasil["diperbarui"]:
        bagian.append(f"{hasil['diperbarui']} diperbarui")
    if hasil["sudah_ada"]:
        bagian.append(f"{hasil['sudah_ada']} sudah ada")
    if hasil["ganda"]:
        bagian.append(f"{hasil['ganda']} ganda di dalam berkas")
    baris.append(
        ("Daftar sasaran: " + ", ".join(bagian) + ".") if bagian else "Tidak ada sasaran baru di berkas itu."
    )
    if hasil["tertunda"]:
        baris.append(f"{hasil['tertunda']} entri tertunda karena batas jumlah sasaran.")
    if hasil["ditolak"]:
        baris.append(f"{len(hasil['ditolak'])} entri ditolak:")
        for item in hasil["ditolak"][:10]:
            baris.append(f"  - {item['entri']}: {item['alasan']}")
        if len(hasil["ditolak"]) > 10:
            baris.append(f"  … dan {len(hasil['ditolak']) - 10} entri lain.")
    for satu in hasil["catatan"]:
        baris.append(f"Catatan: {satu}")
    if not hasil["uji_coba"]:
        baris.append(
            "Belum ada halaman yang dihubungi. Pemeriksaan pertama dilakukan saat pemeriksaan berikutnya."
        )
    return baris
