"""Membandingkan dua potret halaman dan menyimpulkan perubahan yang berarti.

Setiap perubahan membawa jenis, tingkat kepentingan, pesan bahasa Indonesia yang
siap dibaca, serta nilai sebelum dan sesudah. Perubahan kecil seperti pergeseran
harga di bawah ambang diabaikan agar laporan tetap berguna.
"""

from . import config
from .extract import format_amount


def _format(amount: float, currency: str) -> str:
    return format_amount(amount, currency)


def _severity_rank(name: str) -> int:
    return config.SEVERITY_ORDER.get(name, 0)


def _change(kind: str, severity: str, message: str, before=None, after=None) -> dict:
    return {
        "type": kind,
        "severity": severity,
        "message": message,
        "before": before,
        "after": after,
    }


def compare(previous: dict | None, current: dict) -> list[dict]:
    """Kembalikan daftar perubahan dari `previous` ke `current`."""
    if not previous:
        return [
            _change(
                "pemantauan_dimulai",
                "info",
                "Pemantauan pertama: potret awal disimpan sebagai dasar pembanding.",
                None,
                {"title": current.get("title", ""), "harga": current.get("prices", [])},
            )
        ]
    changes: list[dict] = []

    # -- harga --------------------------------------------------------------
    # Pencocokan harga berlapis, karena uji lapangan menunjukkan satu masalah
    # nyata: dulu harga dicocokkan **berdasarkan nama**, sehingga begitu halaman
    # mengubah keterangan (atau keterangannya baru terbaca), laporan berteriak
    # "harga hilang" dan "harga baru" padahal angkanya sama persis.
    #
    #   1. nama + mata uang sama  -> bandingkan angkanya (naik/turun harga barang yang sama)
    #   2. angkanya sama persis   -> tidak ada perubahan yang perlu dilaporkan
    #   3. sisanya                -> benar-benar hilang, atau benar-benar baru
    previous_prices = previous.get("prices", [])
    current_prices = current.get("prices", [])
    lama_dipakai: set[int] = set()
    baru_dipakai: set[int] = set()

    for posisi_baru, now in enumerate(current_prices):
        nama = str(now.get("name") or "").strip()
        if not nama:
            continue
        posisi_lama = next(
            (
                posisi
                for posisi, old in enumerate(previous_prices)
                if posisi not in lama_dipakai
                and str(old.get("name") or "").strip() == nama
                and old.get("currency") == now.get("currency")
            ),
            None,
        )
        if posisi_lama is None:
            continue
        old = previous_prices[posisi_lama]
        lama_dipakai.add(posisi_lama)
        baru_dipakai.add(posisi_baru)
        if old.get("amount", 0) <= 0:
            continue
        delta = now["amount"] - old["amount"]
        percent = abs(delta) / old["amount"] * 100
        # Abaikan perubahan di bawah ambang persen, atau perubahan sepeser pun.
        if percent < config.PRICE_CHANGE_THRESHOLD_PERCENT or abs(delta) < 1:
            continue
        if delta < 0:
            changes.append(
                _change(
                    "harga_turun",
                    "tinggi" if percent >= 5 else "sedang",
                    f"{nama} turun {percent:.1f}% menjadi {_format(now['amount'], now['currency'])}.",
                    _format(old["amount"], old["currency"]),
                    _format(now["amount"], now["currency"]),
                )
            )
        else:
            changes.append(
                _change(
                    "harga_naik",
                    "sedang" if percent >= 5 else "rendah",
                    f"{nama} naik {percent:.1f}% menjadi {_format(now['amount'], now['currency'])}.",
                    _format(old["amount"], old["currency"]),
                    _format(now["amount"], now["currency"]),
                )
            )

    # Lapis kedua: angka yang sama persis dianggap barang yang sama, meski
    # keterangannya berubah atau hilang dari halaman.
    for posisi_baru, now in enumerate(current_prices):
        if posisi_baru in baru_dipakai:
            continue
        posisi_lama = next(
            (
                posisi
                for posisi, old in enumerate(previous_prices)
                if posisi not in lama_dipakai
                and old.get("currency") == now.get("currency")
                and abs(float(old.get("amount", 0)) - float(now["amount"])) < 0.01
            ),
            None,
        )
        if posisi_lama is None:
            continue
        lama_dipakai.add(posisi_lama)
        baru_dipakai.add(posisi_baru)

    for posisi, old in enumerate(previous_prices):
        if posisi in lama_dipakai:
            continue
        changes.append(
            _change(
                "harga_hilang",
                "sedang",
                f"Harga {old.get('name') or 'yang dipantau'} tidak lagi tampak di halaman.",
                _format(old["amount"], old["currency"]),
                None,
            )
        )
    for posisi, now in enumerate(current_prices):
        if posisi in baru_dipakai:
            continue
        changes.append(
            _change(
                "harga_baru",
                "rendah",
                f"Harga baru muncul: {now.get('name') or 'item baru'} {_format(now['amount'], now['currency'])}.",
                None,
                _format(now["amount"], now["currency"]),
            )
        )

    # -- rating dan jumlah ulasan -------------------------------------------
    old_rating = previous.get("rating") or {}
    new_rating = current.get("rating") or {}
    if old_rating and new_rating:
        if old_rating.get("value") is not None and new_rating.get("value") is not None:
            shift = new_rating["value"] - old_rating["value"]
            if abs(shift) >= 0.1:
                changes.append(
                    _change(
                        "rating_berubah",
                        "sedang",
                        f"Rating agregat berubah dari {old_rating['value']} menjadi {new_rating['value']}.",
                        old_rating["value"],
                        new_rating["value"],
                    )
                )
        old_count = old_rating.get("count")
        new_count = new_rating.get("count")
        if isinstance(old_count, int) and isinstance(new_count, int) and new_count != old_count:
            growth = new_count - old_count
            changes.append(
                _change(
                    "jumlah_ulasan_berubah",
                    "sedang" if abs(growth) >= 5 else "rendah",
                    f"Jumlah ulasan {'bertambah' if growth > 0 else 'berkurang'} {abs(growth)} "
                    f"(dari {old_count} menjadi {new_count}).",
                    old_count,
                    new_count,
                )
            )
        scale_changed = old_rating.get("scale") != new_rating.get("scale")
        if scale_changed and new_rating.get("value") is not None:
            changes.append(
                _change(
                    "skala_rating_berubah",
                    "info",
                    "Skala penilaian berubah; bandingkan nilai dengan hati-hati.",
                    old_rating.get("scale"),
                    new_rating.get("scale"),
                )
            )

    # -- elemen SEO halaman --------------------------------------------------
    if previous.get("title") != current.get("title"):
        changes.append(
            _change(
                "judul_berubah",
                "sedang",
                "Judul halaman berubah.",
                previous.get("title"),
                current.get("title"),
            )
        )
    if previous.get("description") != current.get("description"):
        changes.append(
            _change(
                "deskripsi_berubah",
                "rendah",
                "Meta description berubah.",
                previous.get("description"),
                current.get("description"),
            )
        )
    if not previous.get("noindex") and current.get("noindex"):
        changes.append(
            _change(
                "noindex_aktif",
                "tinggi",
                "Halaman kini memakai noindex. Kompetitor mungkin menarik halaman ini dari hasil pencarian.",
                False,
                True,
            )
        )
    if previous.get("noindex") and not current.get("noindex"):
        changes.append(_change("noindex_dihapus", "info", "Noindex dihapus dari halaman.", True, False))
    if previous.get("canonical") != current.get("canonical"):
        changes.append(
            _change(
                "canonical_berubah",
                "sedang",
                "Alamat canonical berubah, bisa menandakan perpindahan halaman.",
                previous.get("canonical") or "(kosong)",
                current.get("canonical") or "(kosong)",
            )
        )
    old_sections = [row for row in (previous.get("h2") or []) if row]
    new_sections = [row for row in (current.get("h2") or []) if row]
    for heading in new_sections:
        if heading not in old_sections:
            changes.append(
                _change(
                    "bagian_baru",
                    "sedang",
                    f"Bagian baru di halaman: \u201c{heading[:80]}\u201d. Bisa menandakan layanan atau penawaran baru.",
                    None,
                    heading[:120],
                )
            )
    for heading in old_sections:
        if heading not in new_sections:
            changes.append(
                _change(
                    "bagian_hilang",
                    "rendah",
                    f"Bagian tidak lagi tampak: \u201c{heading[:80]}\u201d.",
                    heading[:120],
                    None,
                )
            )
    if previous.get("content_hash") and previous["content_hash"] != current.get("content_hash"):
        delta_words = (current.get("word_count") or 0) - (previous.get("word_count") or 0)
        if abs(delta_words) >= 20:
            arah = "bertambah" if delta_words > 0 else "berkurang"
            changes.append(
                _change(
                    "isi_berubah",
                    "sedang",
                    f"Isi halaman {arah} {abs(delta_words)} kata. Periksa bagian yang berubah.",
                    previous.get("word_count"),
                    current.get("word_count"),
                )
            )
        else:
            # Uji lapangan 14 Okt 2026: sebagian situs mengganti sedikit teksnya di
            # setiap permintaan (penghitung, testimoni bergilir, stempel waktu), sehingga
            # sidik isi selalu berbeda tanpa ada yang benar-benar berubah. Karena itu
            # catatan ini diberi tingkat "info" dan kalimatnya menyebut apa adanya —
            # bukan "rendah", yang terbaca seperti temuan padahal belum tentu.
            changes.append(
                _change(
                    "isi_berubah",
                    "info",
                    "Teks halaman berbeda sedikit dari pemeriksaan sebelumnya; harga, judul, dan "
                    "data terstruktur tidak berubah. Situs dengan elemen berganti sendiri memang "
                    "sering begitu.",
                )
            )
    if (previous.get("images_without_alt") or 0) < (current.get("images_without_alt") or 0):
        changes.append(
            _change(
                "alt_gambar_berkurang",
                "rendah",
                "Jumlah gambar tanpa teks alternatif bertambah.",
                previous.get("images_without_alt"),
                current.get("images_without_alt"),
            )
        )
    if previous.get("has_viewport") and not current.get("has_viewport"):
        changes.append(_change("viewport_hilang", "rendah", "Penanda viewport untuk seluler hilang."))
    if not previous.get("has_local_business") and current.get("has_local_business"):
        changes.append(
            _change(
                "schema_lokal_baru",
                "info",
                "Kompetitor mulai memakai data terstruktur bisnis lokal.",
                False,
                True,
            )
        )

    # Bila judul, harga, atau deskripsi sudah berubah, "isi berubah" hanya mengulang
    # kabar yang sama.
    explained = any(
        row["type"] != "isi_berubah" and _severity_rank(row["severity"]) >= _severity_rank("sedang")
        for row in changes
    )
    if explained:
        changes = [
            row
            for row in changes
            if not (
                row["type"] == "isi_berubah"
                and row["severity"] == "info"
                and "berbeda sedikit dari pemeriksaan sebelumnya" in row["message"]
            )
        ]

    changes.sort(key=lambda row: (-_severity_rank(row["severity"]), row["type"]))
    return changes


def highest_severity(changes: list[dict]) -> str:
    if not changes:
        return "info"
    return max((row["severity"] for row in changes), key=_severity_rank)
