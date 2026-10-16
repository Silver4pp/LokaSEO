"""Profil usaha: kunci utama kerja radar.

Jenis usaha dipilih sekali di awal saat membuat proyek LokaSEO. Dari pilihan itu
radar menentukan:

- **data terstruktur apa yang diharapkan** pada situs sendiri (misalnya
  `CafeOrCoffeeShop` untuk kedai kopi),
- **ambang rating awal** untuk papan reputasi (misalnya 4,3 untuk usaha makanan),
- **gagasan kata kunci** yang wajar untuk jenis usaha tersebut,
- **mana yang milik sendiri dan mana pesaing** pada laporan dan papan.

Profil dibaca dari (berurutan): argumen perintah, variabel lingkungan
`LOKARADAR_PROFIL`, lalu berkas `usaha.json` di folder data radar. Berkas itu bisa
diisi sendiri lewat `lokaradar profil`, atau diimpor dari cadangan LokaSEO
(`lokaseo-cadangan.json`) yang memuat nama usaha, kota, domain, dan jenis usaha.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from . import config

PROFILE_ENV = "LOKARADAR_PROFIL"
PROFILE_FILENAME = "usaha.json"

# Ambang rating di sini adalah titik awal yang wajar, bukan standar industri.
# Pengguna dapat menimpanya dengan `--min-rating` atau di berkas profil.
INDUSTRI: dict[str, dict] = {
    "kafe-kedai": {
        "rating_penting": True,
        "label": "Kafe, kedai kopi, atau tempat makan kecil",
        "schema": ("CafeOrCoffeeShop", "Restaurant", "LocalBusiness"),
        "kata_kunci": ("kedai kopi", "menu", "pesan antar"),
        "min_rating": 4.3,
        "catatan": "Cantumkan jam buka terbaru, menu, dan pilihan pesan antar di halaman.",
    },
    "restoran": {
        "rating_penting": True,
        "label": "Restoran atau rumah makan",
        "schema": ("Restaurant", "LocalBusiness"),
        "kata_kunci": ("rumah makan", "menu", "reservasi"),
        "min_rating": 4.3,
        "catatan": "Pastikan menu, jam buka, dan cara reservasi mudah ditemukan.",
    },
    "toko-retail": {
        "rating_penting": True,
        "label": "Toko retail atau toko daring",
        "schema": ("Store", "OnlineStore", "LocalBusiness"),
        "kata_kunci": ("toko", "harga", "kirim"),
        "min_rating": 4.0,
        "catatan": "Tampilkan harga, ketersediaan, dan cara pengiriman yang jelas.",
    },
    "jasa-kecantikan": {
        "rating_penting": True,
        "label": "Salon, barbershop, atau perawatan kecantikan",
        "schema": ("HealthAndBeautyBusiness", "BeautySalon", "LocalBusiness"),
        "kata_kunci": ("salon", "potong rambut", "perawatan"),
        "min_rating": 4.2,
        "catatan": "Tulis daftar layanan beserta kisaran harga dan cara memesan waktu.",
    },
    "klinik-kesehatan": {
        "rating_penting": True,
        "label": "Klinik, apotek, atau praktik kesehatan",
        "schema": ("MedicalClinic", "Pharmacy", "LocalBusiness"),
        "kata_kunci": ("klinik", "dokter", "jadwal praktik"),
        "min_rating": 4.4,
        "catatan": "Cantumkan jadwal praktik, layanan, dan nomor kontak yang aktif.",
    },
    "bengkel-otomotif": {
        "rating_penting": True,
        "label": "Bengkel, cuci mobil, atau layanan otomotif",
        "schema": ("AutoRepair", "AutoWash", "LocalBusiness"),
        "kata_kunci": ("bengkel", "servis", "sparepart"),
        "min_rating": 4.0,
        "catatan": "Sebutkan jenis kendaraan yang dilayani dan estimasi biaya servis.",
    },
    "laundry": {
        "rating_penting": True,
        "label": "Laundry atau layanan harian",
        "schema": ("DryCleaningOrLaundry", "LocalBusiness"),
        "kata_kunci": ("laundry", "harga per kilo", "antar jemput"),
        "min_rating": 4.0,
        "catatan": "Tulis harga per kilo, lama pengerjaan, dan area antar jemput.",
    },
    "penginapan": {
        "rating_penting": True,
        "label": "Penginapan, hotel, atau homestay",
        "schema": ("Hotel", "LodgingBusiness", "LocalBusiness"),
        "kata_kunci": ("penginapan", "kamar", "harga per malam"),
        "min_rating": 4.2,
        "catatan": "Perbarui foto kamar, fasilitas, dan tarif musiman.",
    },
    "pendidikan-kursus": {
        "rating_penting": True,
        "label": "Kursus, bimbel, atau sekolah",
        "schema": ("EducationalOrganization", "LocalBusiness"),
        "kata_kunci": ("kursus", "biaya", "jadwal kelas"),
        "min_rating": 4.3,
        "catatan": "Jelaskan program, jadwal kelas, dan biaya yang berlaku.",
    },
    "jasa-konstruksi": {
        "rating_penting": True,
        "label": "Kontraktor, renovasi, atau pertukangan",
        "schema": ("HomeAndConstructionBusiness", "GeneralContractor", "LocalBusiness"),
        "kata_kunci": ("jasa renovasi", "biaya borongan", "portofolio"),
        "min_rating": 4.0,
        "catatan": "Tampilkan contoh pekerjaan selesai dan area layanan.",
    },
    "jasa-profesional": {
        "rating_penting": True,
        "label": "Jasa profesional (konsultan, notaris, advokat)",
        "schema": ("LegalService", "ProfessionalService", "LocalBusiness"),
        "kata_kunci": ("jasa", "konsultasi", "biaya"),
        "min_rating": 4.4,
        "catatan": "Tulis bidang layanan, pengalaman, dan cara menghubungi tim.",
    },
    "logistik-pengiriman": {
        "rating_penting": True,
        "label": "Pengiriman, ekspedisi, atau sewa kendaraan",
        "schema": ("MovingCompany", "LocalBusiness"),
        "kata_kunci": ("ekspedisi", "ongkir", "sewa"),
        "min_rating": 4.0,
        "catatan": "Sebutkan area jangkauan, estimasi waktu, dan tarif dasar.",
    },
    "lainnya": {
        "rating_penting": False,
        "label": "Jenis usaha lain",
        "schema": ("LocalBusiness",),
        "kata_kunci": ("layanan", "harga"),
        "min_rating": 4.0,
        "catatan": "Lengkapi nama, alamat, dan nomor telepon yang konsisten di semua tempat.",
    },
}

AMBANG_BAWAAN = 4.0


@dataclass
class Profil:
    """Profil usaha yang dipakai radar sebagai kunci utama."""

    nama: str = ""
    jenis: str = ""
    kota: str = ""
    situs: str = ""
    min_rating: float | None = None
    sumber: str = ""
    versi: int = 1
    catatan_tambahan: list[str] = field(default_factory=list)

    # -- turunan ------------------------------------------------------------
    @property
    def jenis_label(self) -> str:
        return INDUSTRI.get(self.jenis, {}).get("label", "")

    @property
    def schema_diharapkan(self) -> tuple[str, ...]:
        return tuple(INDUSTRI.get(self.jenis, {}).get("schema", ()))

    @property
    def kata_kunci(self) -> tuple[str, ...]:
        return tuple(INDUSTRI.get(self.jenis, {}).get("kata_kunci", ()))

    @property
    def ambang_rating(self) -> float:
        if self.min_rating is not None:
            return float(self.min_rating)
        return float(INDUSTRI.get(self.jenis, {}).get("min_rating", AMBANG_BAWAAN))

    @property
    def rating_penting(self) -> bool:
        """Apakah rating pelanggan biasanya menentukan pilihan pembeli jenis ini."""
        return bool(INDUSTRI.get(self.jenis, {}).get("rating_penting"))

    @property
    def saran_sumber_rating(self) -> str:
        """Saran sumber rating yang masuk akal untuk jenis usaha ini."""
        if self.rating_penting:
            return (
                "Rating penting untuk jenis usaha ini, tetapi jarang ditulis di situs usaha "
                "sendiri. Pakai sumber resmi Google Places API lewat sasaran "
                "tempat:<place_id> (kunci Anda sendiri), atau halaman direktori yang "
                "memuat rating."
            )
        return (
            "Jenis usaha ini biasanya tidak bergantung pada rating. Pemantauan halaman "
            "biasa sudah memadai."
        )

    @property
    def catatan(self) -> tuple[str, ...]:
        bawaan = INDUSTRI.get(self.jenis, {}).get("catatan")
        hasil = [bawaan] if bawaan else []
        return tuple(hasil) + tuple(self.catatan_tambahan)

    @property
    def host(self) -> str:
        """Host situs sendiri tanpa www, untuk memisahkan milik sendiri dan pesaing."""
        teks = (self.situs or "").strip()
        if not teks:
            return ""
        if "//" not in teks:
            teks = f"//{teks}"
        host = (urlsplit(teks).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host

    def is_milik_sendiri(self, url: str) -> bool:
        if not self.host:
            return False
        kandidat = (urlsplit(url).hostname or "").lower()
        kandidat = kandidat[4:] if kandidat.startswith("www.") else kandidat
        if not kandidat:
            return False
        return kandidat == self.host or kandidat.endswith(f".{self.host}")

    # -- penyimpanan --------------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "Profil":
        if not isinstance(payload, dict):
            raise ValueError("Profil harus berupa objek JSON")
        jenis = str(payload.get("jenis") or "").strip()
        if jenis and jenis not in INDUSTRI:
            jenis = "lainnya"
        min_rating = payload.get("min_rating")
        if min_rating is not None:
            try:
                min_rating = float(min_rating)
            except (TypeError, ValueError):
                min_rating = None
        catatan = payload.get("catatan_tambahan") or []
        if not isinstance(catatan, list):
            catatan = []
        return cls(
            nama=str(payload.get("nama") or "").strip()[:120],
            jenis=jenis,
            kota=str(payload.get("kota") or "").strip()[:80],
            situs=str(payload.get("situs") or "").strip()[:200],
            min_rating=min_rating,
            sumber=str(payload.get("sumber") or "")[:200],
            versi=int(payload.get("versi") or 1),
            catatan_tambahan=[str(item)[:200] for item in catatan][:10],
        )


# -- pemuatan dan penyimpanan ------------------------------------------------
def profile_path() -> Path:
    override = os.environ.get(PROFILE_ENV)
    if override:
        return Path(override).expanduser()
    return config.data_dir() / PROFILE_FILENAME


def load(path: Path | None = None) -> Profil | None:
    """Baca profil bila ada. Berkas rusak tidak menghentikan radar."""
    target = Path(path).expanduser() if path else profile_path()
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        return Profil.from_dict(payload)
    except ValueError:
        return None


def save(profil: Profil, path: Path | None = None) -> Path:
    target = Path(path).expanduser() if path else profile_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profil.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def from_lokaseo_backup(payload: dict, *, sumber: str = "") -> Profil:
    """Ambil profil dari cadangan LokaSEO (`lokaseo-cadangan.json`).

    Cadangan itu berbentuk {version, projects[], activeId}. Profil diambil dari
    proyek yang sedang aktif, karena itulah yang diatur pengguna di awal.
    """
    if not isinstance(payload, dict):
        raise ValueError("Cadangan LokaSEO harus berupa objek JSON")
    projects = payload.get("projects")
    if not isinstance(projects, list) or not projects:
        raise ValueError("Cadangan tidak memuat daftar proyek")
    active_id = payload.get("activeId")
    project = next((row for row in projects if isinstance(row, dict) and row.get("id") == active_id), None)
    if project is None:
        project = next((row for row in projects if isinstance(row, dict)), None)
    if project is None:
        raise ValueError("Cadangan tidak memuat proyek yang bisa dibaca")
    return Profil.from_dict(
        {
            "nama": project.get("name") or "",
            "jenis": project.get("industry") or "",
            "kota": project.get("city") or "",
            "situs": project.get("domain") or "",
            "sumber": sumber or "cadangan LokaSEO",
        }
    )


def from_lokaseo_file(path: Path) -> Profil:
    target = Path(path).expanduser()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"Berkas cadangan tidak dapat dibaca: {error}") from error
    except ValueError as error:
        raise ValueError("Berkas cadangan bukan JSON yang sah") from error
    return from_lokaseo_backup(payload, sumber=str(target))


# -- bantuan untuk laporan dan papan ----------------------------------------
def hints(profil: Profil | None) -> list[str]:
    return list(profil.kata_kunci) if profil else []


def ringkas(profil: Profil | None) -> str:
    """Satu baris ringkas untuk kepala laporan."""
    if profil is None:
        return ""
    bagian = [profil.nama or "(nama usaha belum diisi)"]
    if profil.jenis_label:
        bagian.append(f"jenis: {profil.jenis_label}")
    if profil.kota:
        bagian.append(f"kota: {profil.kota}")
    if profil.situs:
        bagian.append(f"situs: {profil.situs}")
    return " · ".join(bagian)
