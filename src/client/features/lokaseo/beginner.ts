import type { Project } from "./model";

export function beginnerProgress(project: Project) {
  const own = project.id !== "contoh";
  return [
    own,
    own && project.checks.length > 0,
    own && project.articles.length > 0,
  ];
}
export function contentIdeas(topic: string, city: string) {
  const subject = topic.trim().slice(0, 80);
  if (!subject) return [];
  const local = city.trim() ? ` di ${city.trim()}` : "";
  return [
    {
      title: `Panduan memilih ${subject}${local}`,
      keyword: `${subject}${local}`,
    },
    {
      title: `Apa yang perlu diketahui sebelum membeli ${subject}?`,
      keyword: `tips memilih ${subject}`,
    },
    {
      title: `Pertanyaan pelanggan tentang ${subject}`,
      keyword: `pertanyaan tentang ${subject}`,
    },
  ];
}
export const beginnerHelp: Record<
  string,
  { title: string; text: string; steps: string[] }
> = {
  audit: {
    title: "Pemeriksaan teknis ini boleh dikerjakan belakangan.",
    text: "HTML adalah kode penyusun halaman situs. Anda tidak perlu memahami atau mengeditnya untuk mulai memakai LokaSEO.",
    steps: [
      "Di komputer, buka halaman situs Anda. Klik kanan → Lihat sumber halaman (atau Ctrl+U).",
      "Salin seluruh kode, lalu tempel di kotak di bawah. Anda juga dapat memilih berkas .html.",
      "Klik Periksa HTML. Buka temuan untuk membaca penjelasan. Jika tidak yakin, unduh laporannya dan minta bantuan pengelola situs.",
    ],
  },
  local: {
    title: "Mulai dari informasi yang dilihat pelanggan.",
    text: "SEO lokal membantu orang di sekitar menemukan usaha Anda. Daftar ini diperiksa sendiri, bukan oleh aplikasi.",
    steps: [
      "Buka profil usaha Anda di Google atau halaman kontak situs.",
      "Bandingkan nama, alamat, nomor telepon, dan jam buka dengan keadaan sebenarnya.",
      "Centang hanya langkah yang sudah Anda periksa. Tidak perlu menyelesaikan semuanya hari ini.",
    ],
  },
  keywords: {
    title: "Kata kunci = kata yang mungkin diketik pelanggan di Google.",
    text: "Contoh: “toko roti bogor” atau “harga roti ulang tahun”. Klaster artinya kelompok kata dengan tujuan serupa.",
    steps: [
      "Tulis beberapa pertanyaan atau kebutuhan pelanggan, satu per baris.",
      "Kelompok akan muncul otomatis. Data tidak menyertakan jumlah pencarian.",
      "Pilih satu topik untuk dijadikan artikel. Mulai dari pertanyaan yang paling sering Anda terima.",
    ],
  },
  calendar: {
    title: "Rencanakan satu artikel dulu.",
    text: "Konten adalah tulisan untuk situs Anda. Jadwal di sini hanya pengingat rencana; aplikasi tidak menerbitkan tulisan secara otomatis.",
    steps: [
      "Klik Tambah konten, atau gunakan contoh ide di bawah.",
      "Isi judul dan tanggal. Kata kunci boleh dikosongkan jika belum tahu.",
      "Ide = belum dikerjakan. Ditulis = sedang dikerjakan. Terbit = sudah Anda pasang di situs. Brief adalah kerangka untuk membantu menulis.",
    ],
  },
  reports: {
    title: "Cadangkan agar pekerjaan Anda tidak hilang.",
    text: "Data tersimpan di browser ini, bukan di akun daring. Menghapus data browser dapat menghapus proyek.",
    steps: [
      "Pilih Unduh cadangan .json untuk menyimpan semua proyek. Simpan berkas di tempat yang aman.",
      "Pilih Unduh laporan .md untuk membagikan temuan kepada orang yang mengelola situs. CSV bisa dibuka di aplikasi spreadsheet.",
      "Impor JSON mengembalikan cadangan, tetapi mengganti data yang sedang terbuka. Cadangkan data saat ini dahulu.",
    ],
  },
};
export const glossary = [
  [
    "SEO",
    "Upaya membuat isi dan struktur situs lebih mudah dipahami mesin pencari dan calon pelanggan. Tidak menjamin posisi pertama.",
  ],
  [
    "Audit",
    "Pemeriksaan untuk menemukan bagian halaman yang perlu diperbaiki.",
  ],
  [
    "Kata kunci",
    "Kata atau pertanyaan yang diketik orang ketika mencari sesuatu.",
  ],
  ["Klaster", "Kelompok kata kunci dengan tujuan pencarian yang mirip."],
  ["HTML", "Kode penyusun halaman situs; berbeda dari alamat situs atau URL."],
  ["H1", "Judul utama yang terlihat pada sebuah halaman."],
  [
    "Canonical",
    "Penanda alamat utama jika ada beberapa halaman yang isinya sama atau mirip. Biasanya diatur lewat pengaturan SEO situs.",
  ],
  [
    "Alt",
    "Teks keterangan gambar untuk membantu pembaca layar memahami isinya.",
  ],
  [
    "Schema / JSON-LD",
    "Format informasi tambahan agar mesin pencari dapat membaca detail bisnis. Biasanya dibantu pengelola situs.",
  ],
  [
    "Brief",
    "Kerangka tulisan: tujuan, topik yang dibahas, dan hal yang perlu dicek sebelum terbit.",
  ],
];
