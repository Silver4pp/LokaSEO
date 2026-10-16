/**
 * Jenis usaha yang dipilih saat proyek dibuat.
 *
 * Pilihan ini menjadi kunci utama kerja LokaSEO: dari sini ditentukan data
 * terstruktur apa yang diharapkan pada situs, kata kunci awal yang masuk akal,
 * dan — lewat modul radar (`radar/`) — ambang rating serta sumber pemantauan
 * reputasi yang dipakai.
 *
 * `id` di sini harus sama dengan daftar di `radar/lokaradar/profil.py`; ada uji
 * silang di `radar/tests/test_profil.py` yang menjaga keduanya tidak berbeda.
 */
export type Industry = {
  id: string;
  label: string;
  group: string;
  /** Tipe schema.org yang wajar dipakai situs usaha jenis ini. */
  schema: string[];
  /** Contoh kata kunci awal; bukan data volume pencarian. */
  keywords: string[];
};

export const industries: Industry[] = [
  {
    id: "kafe-kedai",
    label: "Kafe, kedai kopi, atau tempat makan kecil",
    group: "Makanan & minuman",
    schema: ["CafeOrCoffeeShop", "Restaurant", "LocalBusiness"],
    keywords: ["kedai kopi", "menu", "pesan antar"],
  },
  {
    id: "restoran",
    label: "Restoran atau rumah makan",
    group: "Makanan & minuman",
    schema: ["Restaurant", "LocalBusiness"],
    keywords: ["rumah makan", "menu", "reservasi"],
  },
  {
    id: "toko-retail",
    label: "Toko retail atau toko daring",
    group: "Perdagangan",
    schema: ["Store", "OnlineStore", "LocalBusiness"],
    keywords: ["toko", "harga", "kirim"],
  },
  {
    id: "jasa-kecantikan",
    label: "Salon, barbershop, atau perawatan kecantikan",
    group: "Jasa perawatan",
    schema: ["HealthAndBeautyBusiness", "BeautySalon", "LocalBusiness"],
    keywords: ["salon", "potong rambut", "perawatan"],
  },
  {
    id: "klinik-kesehatan",
    label: "Klinik, apotek, atau praktik kesehatan",
    group: "Kesehatan",
    schema: ["MedicalClinic", "Pharmacy", "LocalBusiness"],
    keywords: ["klinik", "dokter", "jadwal praktik"],
  },
  {
    id: "bengkel-otomotif",
    label: "Bengkel, cuci mobil, atau layanan otomotif",
    group: "Otomotif",
    schema: ["AutoRepair", "AutoWash", "LocalBusiness"],
    keywords: ["bengkel", "servis", "sparepart"],
  },
  {
    id: "laundry",
    label: "Laundry atau layanan harian",
    group: "Jasa harian",
    schema: ["DryCleaningOrLaundry", "LocalBusiness"],
    keywords: ["laundry", "harga per kilo", "antar jemput"],
  },
  {
    id: "penginapan",
    label: "Penginapan, hotel, atau homestay",
    group: "Akomodasi",
    schema: ["Hotel", "LodgingBusiness", "LocalBusiness"],
    keywords: ["penginapan", "kamar", "harga per malam"],
  },
  {
    id: "pendidikan-kursus",
    label: "Kursus, bimbel, atau sekolah",
    group: "Pendidikan",
    schema: ["EducationalOrganization", "LocalBusiness"],
    keywords: ["kursus", "biaya", "jadwal kelas"],
  },
  {
    id: "jasa-konstruksi",
    label: "Kontraktor, renovasi, atau pertukangan",
    group: "Konstruksi",
    schema: ["HomeAndConstructionBusiness", "GeneralContractor", "LocalBusiness"],
    keywords: ["jasa renovasi", "biaya borongan", "portofolio"],
  },
  {
    id: "jasa-profesional",
    label: "Jasa profesional (konsultan, notaris, advokat)",
    group: "Jasa profesional",
    schema: ["LegalService", "ProfessionalService", "LocalBusiness"],
    keywords: ["jasa", "konsultasi", "biaya"],
  },
  {
    id: "logistik-pengiriman",
    label: "Pengiriman, ekspedisi, atau sewa kendaraan",
    group: "Logistik",
    schema: ["MovingCompany", "LocalBusiness"],
    keywords: ["ekspedisi", "ongkir", "sewa"],
  },
  {
    id: "lainnya",
    label: "Jenis usaha lain",
    group: "Lainnya",
    schema: ["LocalBusiness"],
    keywords: ["layanan", "harga"],
  },
];

export const industryIds = industries.map((item) => item.id);

export function industryById(id: string): Industry | undefined {
  return industries.find((item) => item.id === id);
}

export function industryLabel(id: string): string {
  return industryById(id)?.label ?? "";
}
