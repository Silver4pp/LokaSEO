import { z } from "zod";

export const auditFactSchema = z.object({
  title: z.string(),
  description: z.string(),
  h1: z.number().int().nonnegative(),
  lang: z.string(),
  canonical: z.boolean(),
  images: z.number().int().nonnegative(),
  missingAlt: z.number().int().nonnegative(),
  viewport: z.boolean(),
  noindex: z.boolean(),
  localSchema: z.boolean(),
});
export type AuditFacts = z.infer<typeof auditFactSchema>;
export function evaluateAudit(f: AuditFacts) {
  return [
    {
      id: "title",
      name: "Judul halaman jelas",
      pass: f.title.length >= 20 && f.title.length <= 65,
      priority: "Tinggi",
      detail: `Judul ${f.title.length} karakter. Usahakan 20–65 karakter yang menjelaskan isi halaman.`,
    },
    {
      id: "description",
      name: "Deskripsi pencarian terisi",
      pass: f.description.length >= 70 && f.description.length <= 170,
      priority: "Sedang",
      detail: `Deskripsi ${f.description.length} karakter. Tulis ringkasan yang spesifik, sekitar 70–170 karakter.`,
    },
    {
      id: "h1",
      name: "Satu judul utama (H1)",
      pass: f.h1 === 1,
      priority: "Tinggi",
      detail: `Ditemukan ${f.h1} H1. Gunakan satu judul utama agar struktur halaman mudah dipahami.`,
    },
    {
      id: "index",
      name: "Tidak memblokir pengindeksan",
      pass: !f.noindex,
      priority: "Tinggi",
      detail:
        "Periksa meta robots. Hapus noindex hanya jika halaman memang perlu muncul di Google.",
    },
    {
      id: "canonical",
      name: "URL kanonis tersedia",
      pass: f.canonical,
      priority: "Sedang",
      detail:
        'Tambahkan link rel="canonical" yang mengarah ke URL utama halaman.',
    },
    {
      id: "alt",
      name: "Gambar memiliki atribut alt",
      pass: f.missingAlt === 0,
      priority: "Sedang",
      detail: `${f.missingAlt} dari ${f.images} gambar tidak memiliki atribut alt. Alt kosong boleh untuk gambar dekoratif.`,
    },
    {
      id: "lang",
      name: "Bahasa halaman Indonesia",
      pass: /^id(?:-|$)/i.test(f.lang),
      priority: "Rendah",
      detail:
        'Gunakan lang="id" atau "id-ID" pada elemen html untuk konten Indonesia.',
    },
    {
      id: "viewport",
      name: "Pengaturan layar seluler",
      pass: f.viewport,
      priority: "Sedang",
      detail: "Tambahkan meta viewport dengan width=device-width.",
    },
    {
      id: "local",
      name: "Data terstruktur bisnis lokal",
      pass: f.localSchema,
      priority: "Rendah",
      detail:
        "Untuk situs bisnis lokal, tambahkan JSON-LD LocalBusiness atau subtipenya. Tidak wajib untuk semua situs.",
    },
  ];
}
export type AuditCheck = ReturnType<typeof evaluateAudit>[number];
export function clusterKeywords(input: string) {
  const keywords = [
    ...new Set(
      input
        .split(/\n|,/)
        .map((s) => s.trim().toLocaleLowerCase("id-ID"))
        .filter(Boolean),
    ),
  ].slice(0, 500);
  const clusters: Record<string, string[]> = {};
  for (const keyword of keywords) {
    const group =
      /\b(bogor|jakarta|bandung|surabaya|terdekat|depok|bekasi|bali|tangerang)\b/.test(
        keyword,
      )
        ? "Pencarian lokal"
        : /\b(harga|beli|jual|pesan|biaya|murah)\b/.test(keyword)
          ? "Siap membeli"
          : /\b(cara|apa|panduan|tips|mengapa)\b/.test(keyword)
            ? "Informasi & panduan"
            : "Topik umum";
    (clusters[group] ??= []).push(keyword);
  }
  return clusters;
}
export function csvCell(value: string) {
  return (
    '"' +
    (/^(?:[\s\u0000-\u001f\u007f\ufeff]*[=+\-@]|[\t\r\n])/u.test(value)
      ? "'" + value
      : value
    ).replaceAll('"', '""') +
    '"'
  );
}
export const articleSchema = z.object({
  id: z.string().min(1).max(80),
  title: z.string().trim().min(1).max(200),
  keyword: z.string().max(200),
  date: z
    .string()
    .refine(isValidDate, "Pilih tanggal yang valid (tahun 1900–2100)."),
  status: z.enum(["Ide", "Ditulis", "Terbit"]),
});
export type Article = z.infer<typeof articleSchema>;
export const projectSchema = z.object({
  id: z.string().min(1).max(80),
  name: z.string().trim().min(1).max(80),
  domain: z.string().max(250),
  city: z.string().max(80),
  // Kunci utama kerja LokaSEO. Dibuat berdefault "" agar cadangan lama tetap
  // bisa dibuka tanpa kehilangan data.
  industry: z.string().max(60).default(""),
  keywords: z.string().max(50000),
  articles: z.array(articleSchema).max(2000),
  checks: z.array(z.string().max(40)).max(6),
  audit: auditFactSchema.nullable(),
  auditedAt: z.string().datetime({ offset: true }).nullable(),
});
export type Project = z.infer<typeof projectSchema>;
export const workspaceSchema = z
  .object({
    version: z.literal(1),
    projects: z.array(projectSchema).min(1).max(100),
    activeId: z.string().min(1).max(80),
  })
  .refine(
    (w) =>
      new Set(w.projects.map((p) => p.id)).size === w.projects.length &&
      w.projects.some((p) => p.id === w.activeId),
    "Identitas proyek tidak valid.",
  )
  .refine(
    (w) =>
      w.projects.every(
        (p) =>
          new Set(p.articles.map((a) => a.id)).size === p.articles.length &&
          new Set(p.checks).size === p.checks.length &&
          p.checks.every((id) => localTasks.some((t) => t.id === id)) &&
          (!p.audit || p.audit.missingAlt <= p.audit.images),
      ),
    "Data proyek tidak konsisten.",
  );
export type Workspace = z.infer<typeof workspaceSchema>;
export function newProject(
  name: string,
  domain: string,
  city: string,
  industry = "",
): Project {
  return {
    id: crypto.randomUUID(),
    name,
    domain,
    city,
    industry,
    keywords: "",
    articles: [],
    checks: [],
    audit: null,
    auditedAt: null,
  };
}
export const localTasks = [
  {
    id: "profile",
    title: "Lengkapi Profil Bisnis Google",
    detail:
      "Isi kategori usaha, jam operasional, situs, serta foto tempat usaha.",
    tag: "Profil bisnis",
  },
  {
    id: "nap",
    title: "Samakan nama, alamat, dan nomor telepon",
    detail: "Gunakan informasi yang sama di situs, peta, dan direktori bisnis.",
    tag: "Konsistensi",
  },
  {
    id: "location",
    title: "Buat halaman untuk wilayah layanan",
    detail:
      "Jelaskan layanan, cakupan wilayah, dan cara menuju lokasi. Hindari halaman kota yang isinya sama.",
    tag: "Konten lokal",
  },
  {
    id: "reviews",
    title: "Minta ulasan dari pelanggan sebenarnya",
    detail:
      "Bagikan tautan ulasan setelah layanan selesai. Jangan membeli atau membuat ulasan palsu.",
    tag: "Reputasi",
  },
  {
    id: "schema",
    title: "Tambahkan data terstruktur bisnis",
    detail:
      "Cantumkan alamat dan kontak dalam JSON-LD sesuai informasi yang terlihat di halaman.",
    tag: "Teknis",
  },
  {
    id: "mobile",
    title: "Periksa kontak dari ponsel",
    detail:
      "Pastikan tautan telepon, petunjuk arah, dan formulir bisa dipakai di layar kecil.",
    tag: "Pengalaman pengguna",
  },
];

/** Calendar dates are local dates, never UTC instants. */
export function localDateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
export function isValidDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  return (
    year >= 1900 &&
    year <= 2100 &&
    localDateKey(new Date(year, month - 1, day, 12)) === value
  );
}
export function monthDays(month: string) {
  const [year, index] = month.split("-").map(Number);
  const first = new Date(year, index - 1, 1, 12);
  const offset = (first.getDay() + 6) % 7;
  const count = new Date(year, index, 0, 12).getDate();
  const slots = Math.ceil((offset + count) / 7) * 7;
  return Array.from({ length: slots }, (_, i) =>
    i < offset || i >= offset + count
      ? null
      : localDateKey(new Date(year, index - 1, i - offset + 1, 12)),
  );
}
export function removeProject(w: Workspace, id: string): Workspace {
  if (w.projects.length === 1 || !w.projects.some((p) => p.id === id)) return w;
  const projects = w.projects.filter((p) => p.id !== id);
  return {
    ...w,
    projects,
    activeId: w.activeId === id ? projects[0].id : w.activeId,
  };
}
export type SearchResult = {
  projectId: string;
  projectName: string;
  title: string;
  kind: "Proyek" | "Konten" | "Kata kunci";
  page: string;
  articleId?: string;
};
export function searchWorkspace(w: Workspace, query: string): SearchResult[] {
  const q = query.trim().toLocaleLowerCase("id-ID");
  if (!q) return [];
  const results: SearchResult[] = [];
  for (const p of w.projects) {
    const base = { projectId: p.id, projectName: p.name };
    if (
      `${p.name} ${p.domain} ${p.city}`.toLocaleLowerCase("id-ID").includes(q)
    )
      results.push({
        ...base,
        title: p.name,
        kind: "Proyek",
        page: "overview",
      });
    for (const a of p.articles) {
      if (`${a.title} ${a.keyword}`.toLocaleLowerCase("id-ID").includes(q))
        results.push({
          ...base,
          title: a.title,
          kind: "Konten",
          page: "calendar",
          articleId: a.id,
        });
    }
    for (const k of Object.values(clusterKeywords(p.keywords)).flat()) {
      if (k.includes(q))
        results.push({
          ...base,
          title: k,
          kind: "Kata kunci",
          page: "keywords",
        });
    }
  }
  return results.slice(0, 50);
}
