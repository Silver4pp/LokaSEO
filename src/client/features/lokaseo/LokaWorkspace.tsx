import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type FormEvent,
} from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Bot,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  ClipboardCheck,
  FileText,
  FolderOpen,
  Globe2,
  Layers3,
  LayoutDashboard,
  Leaf,
  MapPin,
  Plus,
  Pencil,
  Settings2,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import {
  articleSchema,
  localDateKey,
  removeProject,
  searchWorkspace,
  clusterKeywords,
  csvCell,
  evaluateAudit,
  localTasks,
  newProject,
  workspaceSchema,
  type Article,
  type Project,
  type Workspace,
} from "./model";
import {
  BeginnerStart,
  PageHelp,
  IdeaStarter,
  SeoGlossary,
} from "./BeginnerGuide";
import { AiWorkspace, type AiSeed } from "./AiWorkspace";
import { useAi } from "./useAi";
import { MonthCalendar } from "./MonthCalendar";
import { withStorageLock } from "./storage-lock";
import { parseHtmlAudit } from "./html-audit";
import { industries, industryLabel } from "./industries";

const STORE = "lokaseo.workspace.v1";
const tabs = [
  { id: "overview", title: "Ringkasan", icon: LayoutDashboard },
  { id: "audit", title: "Audit halaman", icon: ClipboardCheck },
  { id: "local", title: "SEO lokal", icon: MapPin },
  { id: "keywords", title: "Klaster kata kunci", icon: Layers3 },
  { id: "calendar", title: "Kalender konten", icon: CalendarDays },
  { id: "reports", title: "Laporan", icon: BarChart3 },
  { id: "ai", title: "AI & token", icon: Bot },
];
function initialWorkspace(): Workspace {
  const p = newProject("Kebun Kopi Bogor", "kebunkopi.example", "Bogor");
  p.id = "contoh";
  p.keywords =
    "kopi bogor\nkedai kopi terdekat\ncafe bogor\nharga kopi arabika\nbeli biji kopi\ncara menyeduh kopi\ntips memilih kopi\napa itu kopi arabika\nkopi nusantara\nmanual brew\nkopi susu\npesan kopi";
  p.checks = ["profile", "nap"];
  p.audit = {
    title: "Kebun Kopi Bogor — Kopi Lokal dan Ruang Berkumpul",
    description:
      "Kenali kopi pilihan dari petani Indonesia, menu seduhan, dan jadwal kegiatan di Kebun Kopi Bogor. Temukan lokasi serta jam buka kedai kami.",
    h1: 1,
    lang: "id",
    canonical: false,
    images: 8,
    missingAlt: 3,
    viewport: true,
    noindex: false,
    localSchema: false,
  };
  p.auditedAt = "2026-10-12T08:00:00+07:00";
  p.articles = [
    {
      id: "c1",
      title: "Panduan memilih biji kopi untuk seduhan di rumah",
      keyword: "tips memilih kopi",
      date: "2026-10-14",
      status: "Ditulis",
    },
    {
      id: "c2",
      title: "Mencari kedai kopi yang tenang di Bogor",
      keyword: "kopi bogor",
      date: "2026-10-16",
      status: "Ide",
    },
    {
      id: "c3",
      title: "Kenali rasa kopi arabika dari petani lokal",
      keyword: "apa itu kopi arabika",
      date: "2026-10-19",
      status: "Ide",
    },
    {
      id: "c4",
      title: "Cara menyeduh kopi tanpa mesin espresso",
      keyword: "cara menyeduh kopi",
      date: "2026-10-21",
      status: "Ide",
    },
  ];
  return { version: 1, activeId: p.id, projects: [p] };
}
const button =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-[background-color,transform] hover:bg-black/5 active:scale-[0.96] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 disabled:opacity-50";
const field =
  "mt-2 w-full rounded-lg border border-[#d9ded7] bg-white px-3 py-2.5 text-sm outline-none focus:border-[#28664f] focus:ring-2 focus:ring-[#28664f]/15";
const box = "rounded-xl border border-[#e2e5de] bg-white";
function download(name: string, content: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function SectionHeading({
  title,
  note,
  action,
}: {
  title: string;
  note?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        {note && <p className="mt-1 text-xs text-[#737b70]">{note}</p>}
      </div>
      {action}
    </div>
  );
}
function Badge({
  children,
  muted = false,
}: {
  children: ReactNode;
  muted?: boolean;
}) {
  return (
    <span
      className={`inline-flex rounded-md px-2 py-1 text-[11px] font-medium ${muted ? "bg-[#f2f3ef] text-[#65705f]" : "bg-[#eaf2e7] text-[#346348]"}`}
    >
      {children}
    </span>
  );
}

export function LokaWorkspace({
  standalone = false,
}: {
  standalone?: boolean;
}) {
  const ai = useAi();
  const [aiSeed, setAiSeed] = useState<AiSeed | null>(null);
  const [ws, setWs] = useState<Workspace>(initialWorkspace);
  const storedSnapshot = useRef<string | null>(null);
  const storedState = useRef<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [beginner, setBeginner] = useState(true);
  const [articleDraft, setArticleDraft] = useState({ title: "", keyword: "" });
  const htmlUploadRef = useRef<HTMLInputElement>(null);
  const [page, setPage] = useState("overview");
  const [toast, setToast] = useState("");
  const [storageError, setStorageError] = useState("");
  const [rawRecovery, setRawRecovery] = useState<string | null>(null);
  const [modal, setModal] = useState<
    | "project"
    | "article"
    | "help"
    | "settings"
    | "delete-project"
    | "search"
    | null
  >(null);
  const [brief, setBrief] = useState<Article | null>(null);
  const [html, setHtml] = useState("");
  const [auditError, setAuditError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("Semua");
  const [editingArticle, setEditingArticle] = useState<Article | null>(null);
  const [plannedDate, setPlannedDate] = useState("");
  const [formError, setFormError] = useState("");
  const [deleteName, setDeleteName] = useState("");
  const [globalQuery, setGlobalQuery] = useState("");
  const [calendarView, setCalendarView] = useState<"list" | "month">("list");
  const [month, setMonth] = useState(() =>
    localDateKey(new Date()).slice(0, 7),
  );
  const [deletedArticle, setDeletedArticle] = useState<{
    projectId: string;
    article: Article;
  } | null>(null);
  const [onlyOverdue, setOnlyOverdue] = useState(false);
  const [busy, setBusy] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const p = ws.projects.find((p) => p.id === ws.activeId) ?? ws.projects[0];
  const checks = p.audit ? evaluateAudit(p.audit) : [];
  const passed = checks.filter((c) => c.pass).length;
  const score = checks.length
    ? Math.round((passed / checks.length) * 100)
    : null;
  const clusters = clusterKeywords(p.keywords);
  const keywordCount = Object.values(clusters).flat().length;
  const openTasks = checks.filter((c) => !c.pass);
  const articles = p.articles
    .filter(
      (a) =>
        `${a.title} ${a.keyword}`
          .toLowerCase()
          .includes(search.toLowerCase()) &&
        (!onlyOverdue ||
          (a.status !== "Terbit" && a.date < localDateKey(new Date()))) &&
        (statusFilter === "Semua" || a.status === statusFilter),
    )
    .sort((a, b) => a.date.localeCompare(b.date));
  const globalResults =
    modal === "search" ? searchWorkspace(ws, globalQuery) : [];
  const overdueCount = p.articles.filter(
    (a) => a.status !== "Terbit" && a.date < localDateKey(new Date()),
  ).length;
  const published = p.articles.filter((a) => a.status === "Terbit").length;
  const activeTab = tabs.find((t) => t.id === page)!;
  useEffect(() => {
    try {
      setBeginner(localStorage.getItem("lokaseo.guide") !== "off");
    } catch {
      /* Guidance remains available when storage is blocked. */
    }
  }, []);
  function toggleGuide() {
    setBeginner((value) => !value);
    try {
      localStorage.setItem("lokaseo.guide", beginner ? "off" : "on");
    } catch {
      setToast("Pilihan panduan hanya berlaku selama sesi ini.");
    }
  }
  useEffect(() => {
    let raw: string | null = null;
    try {
      raw = localStorage.getItem(STORE);
      storedSnapshot.current = raw;
      if (raw) {
        const parsed = workspaceSchema.parse(JSON.parse(raw));
        storedState.current = JSON.stringify(parsed);
        setWs(parsed);
      }
    } catch {
      setRawRecovery(raw);
      setStorageError(
        raw
          ? "Data lama tidak valid. Penyimpanan dihentikan agar berkas asli tidak tertimpa. Unduh data asli, lalu pulihkan cadangan valid lewat Laporan."
          : "Penyimpanan browser tidak dapat dibaca. Gunakan ekspor cadangan.",
      );
    }
    setLoaded(true);
  }, []);
  useEffect(() => {
    if (!loaded || storageError) return;
    const next = JSON.stringify(ws);
    // Reading a backup must not rewrite it just because schema parsing reordered object keys.
    if (next === storedState.current) return;
    let cancelled = false;
    void withStorageLock(STORE, () => {
      if (cancelled) return;
      const current = localStorage.getItem(STORE);
      if (current !== storedSnapshot.current)
        throw new Error(
          "Data di tab lain berubah. Penyimpanan tab ini dihentikan agar perubahan tidak tertimpa. Ekspor perubahan tab ini sebelum memuat ulang.",
        );
      if (current !== next) localStorage.setItem(STORE, next);
      storedSnapshot.current = next;
      storedState.current = next;
    }).catch((error) => {
      if (!cancelled)
        setStorageError(
          error instanceof Error && error.message.includes("tab lain")
            ? error.message
            : "Perubahan belum tersimpan. Penyimpanan penuh, diblokir, atau browser tidak mendukung Web Locks. Unduh cadangan sekarang.",
        );
    });
    return () => {
      cancelled = true;
    };
  }, [ws, loaded, storageError]);
  useEffect(() => {
    const changed = (event: StorageEvent) => {
      if (event.key !== STORE && event.key !== null) return;
      try {
        if (localStorage.getItem(STORE) !== storedSnapshot.current)
          setStorageError(
            "Data di tab lain berubah. Penyimpanan tab ini dihentikan agar perubahan tidak tertimpa. Ekspor perubahan tab ini sebelum memuat ulang.",
          );
      } catch {
        setStorageError(
          "Penyimpanan browser tidak dapat dibaca. Unduh cadangan perubahan tab ini.",
        );
      }
    };
    window.addEventListener("storage", changed);
    return () => window.removeEventListener("storage", changed);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    if (modal || brief) dialogRef.current?.showModal();
    else dialogRef.current?.close();
  }, [modal, brief]);
  useEffect(() => {
    setFormError("");
  }, [modal, editingArticle]);
  useEffect(() => {
    setSearch("");
    setStatusFilter("Semua");
    setOnlyOverdue(false);
    setHtml("");
    setAuditError("");
  }, [ws.activeId]);
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if (
        (event.ctrlKey || event.metaKey) &&
        event.key.toLowerCase() === "k" &&
        !dialogRef.current?.open
      ) {
        event.preventDefault();
        setModal("search");
      }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, []);
  function openArticle(
    article: Article | null = null,
    date = "",
    draft = { title: "", keyword: "" },
  ) {
    setArticleDraft(draft);
    setEditingArticle(article);
    setPlannedDate(date);
    setBrief(null);
    setModal("article");
  }
  function deleteArticle(article: Article) {
    if (!window.confirm(`Hapus rencana “${article.title}”?`)) return;
    setDeletedArticle({ projectId: p.id, article });
    update({ articles: p.articles.filter((a) => a.id !== article.id) });
    setToast("Konten dihapus. Anda masih bisa membatalkannya.");
  }
  function undoDelete() {
    if (!deletedArticle) return;
    const project = ws.projects.find(
      (item) => item.id === deletedArticle.projectId,
    );
    if (
      !project ||
      project.articles.length >= 2000 ||
      project.articles.some((a) => a.id === deletedArticle.article.id)
    ) {
      setToast(
        "Konten tidak dapat dipulihkan: proyek hilang, penuh, atau konten sudah ada.",
      );
      return;
    }
    setWs((w) => ({
      ...w,
      projects: w.projects.map((item) =>
        item.id === project.id
          ? { ...item, articles: [...item.articles, deletedArticle.article] }
          : item,
      ),
    }));
    setDeletedArticle(null);
    setToast("Konten dipulihkan.");
  }
  function saveSettings(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const name = String(data.get("name")).trim();
    if (!name) {
      setFormError("Nama proyek tidak boleh hanya spasi.");
      return;
    }
    update({
      name,
      domain: String(data.get("domain")).trim(),
      city: String(data.get("city")).trim(),
      industry: String(data.get("industry")).trim(),
    });
    setModal(null);
    setToast("Informasi proyek diperbarui. Audit dan konten tetap tersimpan.");
  }
  function update(patch: Partial<Project>) {
    setWs((w) => ({
      ...w,
      projects: w.projects.map((item) =>
        item.id === p.id ? { ...item, ...patch } : item,
      ),
    }));
  }
  function go(tab: string) {
    setPage(tab);
    setSearch("");
  }
  function exportBackup() {
    download(
      "lokaseo-cadangan.json",
      JSON.stringify(ws, null, 2),
      "application/json",
    );
    setToast("Cadangan proyek sudah diunduh.");
  }
  function saveProject(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    const project = newProject(
      String(d.get("name")).trim(),
      String(d.get("domain")).trim(),
      String(d.get("city")).trim(),
      String(d.get("industry")).trim(),
    );
    if (!project.name) {
      setFormError("Nama proyek tidak boleh hanya spasi.");
      return;
    }
    if (ws.projects.length >= 100) {
      setToast("Batas 100 proyek tercapai.");
      return;
    }
    setWs((w) => ({
      ...w,
      activeId: project.id,
      projects: [...w.projects, project],
    }));
    setModal(null);
    setHtml("");
    setAuditError("");
    setPage("overview");
    setToast("Proyek dibuat. Mulai dengan audit halaman pertama.");
  }
  function saveArticle(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    if (!editingArticle && p.articles.length >= 2000) {
      setFormError("Batas 2.000 konten per proyek tercapai.");
      return;
    }
    const parsed = articleSchema.safeParse({
      id: editingArticle?.id ?? crypto.randomUUID(),
      title: String(d.get("title")).trim(),
      keyword: String(d.get("keyword")).trim(),
      date: String(d.get("date")),
      status: editingArticle ? String(d.get("status")) : "Ide",
    });
    if (!parsed.success) {
      setFormError("Periksa judul dan tanggal. Gunakan tahun 1900–2100.");
      return;
    }
    update({
      articles: editingArticle
        ? p.articles.map((a) => (a.id === editingArticle.id ? parsed.data : a))
        : [...p.articles, parsed.data],
    });
    setMonth(parsed.data.date.slice(0, 7));
    setModal(null);
    setEditingArticle(null);
    setToast(
      editingArticle
        ? "Konten dan jadwal diperbarui."
        : "Rencana konten ditambahkan.",
    );
  }

  async function audit() {
    setAuditError("");
    setBusy(true);
    try {
      const facts = parseHtmlAudit(html);
      update({ audit: facts, auditedAt: new Date().toISOString() });
      setToast(
        "Audit selesai. Buka temuan untuk menentukan langkah berikutnya.",
      );
    } catch (e) {
      setAuditError(
        e instanceof Error ? e.message : "HTML tidak dapat diperiksa.",
      );
    } finally {
      setBusy(false);
    }
  }
  const reportText = () =>
    `# Laporan SEO — ${p.name}\n\nSitus: ${p.domain}\nWilayah: ${p.city}\nJenis usaha: ${industryLabel(p.industry) || "belum dipilih"}\nDibuat: ${new Date().toLocaleString("id-ID")}\n${p.id === "contoh" ? "DATA CONTOH, bukan hasil pemeriksaan situs nyata.\n" : ""}\n## Audit HTML\nSkor checklist: ${score ?? "Belum diaudit"}${score === null ? "" : "/100"}\n${p.auditedAt ? `Waktu audit: ${p.auditedAt}` : ""}\n\n${checks.map((c) => `- [${c.pass ? "x" : " "}] ${c.name} (${c.priority}): ${c.detail}`).join("\n")}\n\nSkor ini adalah panduan checklist, bukan skor Google atau jaminan peringkat. Audit tidak memeriksa HTTP, robots.txt, performa, atau halaman yang dirender JavaScript.\n\n## SEO lokal\n${localTasks.map((t) => `- [${p.checks.includes(t.id) ? "x" : " "}] ${t.title}`).join("\n")}\n\n## Kalender konten\n${p.articles.map((a) => `- ${a.date}: ${a.title} — ${a.status}`).join("\n")}`;
  const briefText = (a: Article) =>
    `# Brief: ${a.title}\n\nKata kunci utama: ${a.keyword || "Tentukan kata kunci"}\nTarget wilayah: ${p.city || "Indonesia"}\nTanggal rencana: ${a.date}\n\n## Tujuan\nJawab kebutuhan pembaca yang mencari “${a.keyword || a.title}”. Pastikan isi sesuai layanan ${p.name}.\n\n## Kerangka awal\n1. Jawaban singkat atas pertanyaan utama\n2. Penjelasan dan contoh yang relevan\n3. Informasi lokal yang sudah diverifikasi di ${p.city || "wilayah layanan"}\n4. Pertanyaan yang sering diajukan pelanggan\n5. Langkah berikutnya dan tautan kontak\n\n## Sebelum terbit\n- Verifikasi harga, alamat, dan jam operasional.\n- Gunakan pengalaman nyata, jangan mengarang ulasan.\n- Tulis judul dan deskripsi yang sesuai isi.\n- Tambahkan tautan internal yang membantu pembaca.\n\nIni templat berbasis aturan, bukan riset SERP atau keluaran AI.`;

  return (
    <div className="min-h-screen bg-[#f7f8f3] font-[Arial,sans-serif] text-[#283c31] antialiased selection:bg-[#d9e9c9] [&_button]:cursor-pointer [&_a]:cursor-pointer [&_h1]:text-balance [&_p]:text-pretty [&_svg]:shrink-0 [font-variant-numeric:tabular-nums] motion-reduce:[&_*]:transition-none">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-[#e0e5db] bg-[#f0f3eb] px-5 py-7 lg:flex">
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            go("overview");
          }}
          className="flex items-center gap-2.5 px-3 text-2xl font-bold tracking-[-1px]"
        >
          <span className="flex size-9 items-center justify-center rounded-xl bg-[#285c43] text-white">
            <Leaf size={22} />
          </span>
          LokaSEO
          <span className="mb-3 size-1.5 rounded-full bg-[#7eaa5d]" />
        </a>
        <p className="mt-2 px-3 text-[11px] tracking-[.08em] text-[#7c8778]">
          TUMBUH DARI PENCARIAN LOKAL
        </p>
        <div className="mt-9 rounded-lg border border-[#dbe1d4] bg-white/70 p-3">
          <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold tracking-widest text-[#7d8676]">
            <FolderOpen size={13} /> RUANG KERJA
          </div>
          <label className="sr-only" htmlFor="project-select">
            Pilih proyek
          </label>
          <select
            id="project-select"
            value={p.id}
            onChange={(e) => {
              setWs((w) => ({ ...w, activeId: e.target.value }));
              setHtml("");
              setAuditError("");
            }}
            className="w-full bg-transparent text-xs font-semibold outline-offset-4"
          >
            {ws.projects.map((pr) => (
              <option key={pr.id} value={pr.id}>
                {pr.name}
              </option>
            ))}
          </select>
        </div>
        <p className="mb-3 mt-8 px-3 text-[10px] font-semibold tracking-[.13em] text-[#88917f]">
          KELOLA SEO
        </p>
        <nav className="space-y-1">
          {tabs.map((t) => (
            <button
              key={t.id}
              aria-label={t.title}
              aria-current={page === t.id ? "page" : undefined}
              onClick={() => go(t.id)}
              className={`flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-[13px] transition-colors ${page === t.id ? "bg-[#dce8d2] font-semibold text-[#244a31]" : "text-[#6d786a] hover:bg-[#e5eadd]"}`}
            >
              <t.icon size={18} strokeWidth={page === t.id ? 2 : 1.5} />
              {t.title}
              {t.id === "audit" && openTasks.length > 0 && (
                <span className="ml-auto rounded bg-[#e5dbc0] px-1.5 py-0.5 text-[10px] text-[#795b27]">
                  {openTasks.length}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="mt-auto">
          <div className="rounded-xl border border-[#dce3d5] bg-[#e9efe1] p-4">
            <ShieldCheck size={20} className="mb-3 text-[#64874e]" />
            <p className="text-xs font-semibold">Milik Anda, sepenuhnya.</p>
            <p className="mt-2 text-[11px] leading-5 text-[#75806c]">
              Tanpa paket berbayar.
              <br />
              Tanpa batas kredit aplikasi.
            </p>
          </div>
          <button
            onClick={() => setModal("help")}
            className={`${button} mt-4 w-full justify-start text-[#6b7864]`}
          >
            <CircleHelp size={17} />
            Panduan & penyimpanan
          </button>
          <div className="mt-4 flex items-center gap-3 border-t border-[#dde2d5] px-2 pt-5">
            <span className="flex size-8 items-center justify-center rounded-full bg-[#dce4d2] text-xs font-semibold">
              ID
            </span>
            <div>
              <p className="text-xs font-semibold">Ruang kerja pribadi</p>
              <p className="mt-1 text-[10px] text-[#7b8771]">
                Indonesia · edisi mandiri
              </p>
            </div>
          </div>
        </div>
      </aside>
      <div className="lg:ml-60">
        <header className="flex min-h-18 flex-wrap items-center justify-between gap-3 border-b border-[#e5e8df] bg-white/70 px-5 py-4 md:px-9">
          <div className="flex items-center gap-2 text-xs text-[#7d8777]">
            <span className="font-bold text-[#315039] lg:hidden">
              LokaSEO /
            </span>
            <span>Ruang kerja</span>
            <span className="mx-1 text-[#bbc1b3]">/</span>
            <span className="text-[#364731]">{activeTab.title}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={toggleGuide}
              aria-pressed={beginner}
              className={`${button} border border-[#ceddc3] text-xs ${beginner ? "bg-[#e7f0df] text-[#325a26]" : "bg-white"}`}
            >
              <CircleHelp size={16} />
              Panduan pemula
              <span className="text-[10px]">
                {beginner ? "Aktif" : "Nonaktif"}
              </span>
            </button>
            <button
              aria-label="Cari semua proyek dan konten"
              onClick={() => setModal("search")}
              className={`${button} border border-[#dce1d5] bg-white text-xs`}
            >
              <Search size={16} />
              <span className="hidden sm:inline">Cari semua</span>
              <kbd className="hidden text-[10px] text-[#75866a] xl:inline">
                Ctrl K
              </kbd>
            </button>
            <button
              aria-label="Pengaturan proyek"
              onClick={() => setModal("settings")}
              className={`${button} border border-[#dce1d5] bg-white px-3`}
            >
              <Settings2 size={16} />
            </button>
            <span className="flex items-center gap-1.5 text-[11px] text-[#6c7864]">
              <span
                className={`size-1.5 rounded-full ${storageError ? "bg-red-500" : "bg-[#729f52]"}`}
              />
              {storageError ? "Belum tersimpan" : "Proyek tersimpan di browser"}
            </span>
            <button
              onClick={() => setModal("project")}
              className={`${button} border border-[#dce1d5] bg-white text-xs`}
            >
              <Plus size={15} />
              Proyek baru
            </button>
          </div>
        </header>
        <nav
          aria-label="Navigasi seluler"
          className="sticky top-0 z-10 border-b border-[#e0e5db] bg-[#f7f8f3] px-4 py-3 lg:hidden"
        >
          <div className="mb-3 flex items-center gap-2">
            <label className="sr-only" htmlFor="mobile-project">
              Pilih proyek seluler
            </label>
            <select
              id="mobile-project"
              value={p.id}
              onChange={(e) =>
                setWs((w) => ({ ...w, activeId: e.target.value }))
              }
              className="min-h-11 w-full min-w-0 rounded-lg border border-[#dce3d2] bg-white px-3 text-sm"
            >
              {ws.projects.map((pr) => (
                <option key={pr.id} value={pr.id}>
                  {pr.name}
                </option>
              ))}
            </select>
            <button
              aria-label="Panduan seluler"
              onClick={() => setModal("help")}
              className={`${button} px-3`}
            >
              <CircleHelp size={18} />
            </button>
          </div>
          <div className="grid grid-cols-3 gap-1">
            {tabs.map((t) => (
              <button
                key={t.id}
                aria-label={t.title}
                aria-current={page === t.id ? "page" : undefined}
                onClick={() => go(t.id)}
                className={`flex min-h-12 items-center justify-center gap-1.5 rounded-lg px-1 text-[11px] ${page === t.id ? "bg-[#dce8d2] font-semibold" : "hover:bg-[#edf1e7]"}`}
              >
                <t.icon size={14} />
                {t.title}
              </button>
            ))}
          </div>
        </nav>
        <main className="mx-auto max-w-[1440px] px-5 py-7 md:px-9 md:py-8">
          {storageError && (
            <div
              role="alert"
              className="mb-5 rounded-lg bg-amber-100 p-4 text-sm"
            >
              {storageError}
              <button
                onClick={() => {
                  if (
                    window.confirm(
                      "Muat ulang akan membuang perubahan tab ini yang belum tersimpan dan menghapus key AI sesi. Unduh cadangan terlebih dahulu. Lanjutkan?",
                    )
                  )
                    window.location.reload();
                }}
                className={`${button} ml-2 border border-amber-300`}
              >
                Muat ulang data terbaru
              </button>
              {rawRecovery !== null && (
                <button
                  onClick={() => download("lokaseo-data-asli.txt", rawRecovery)}
                  className={`${button} ml-2 underline`}
                >
                  Unduh data asli
                </button>
              )}
              <button
                onClick={exportBackup}
                className={`${button} ml-2 underline`}
              >
                Unduh cadangan
              </button>
            </div>
          )}
          <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-2 flex items-center gap-2 text-xs text-[#849075]">
                <span className="text-[10px] font-semibold tracking-[.14em]">
                  {page === "overview" ? "GAMBARAN PROYEK" : "RUANG KERJA SEO"}
                </span>
                <span>·</span>
                <span>{p.city || "Indonesia"}</span>
              </div>
              <h1 className="text-[29px] font-semibold tracking-[-1px] text-[#273f2d] md:text-[32px]">
                {page === "overview"
                  ? "Langkah kecil, jangkauan lebih luas."
                  : activeTab.title}
              </h1>
              <p className="mt-2 text-[13px] text-[#7b8475]">
                {page === "overview"
                  ? "Lihat kondisi situs Anda dan tentukan apa yang perlu dikerjakan hari ini."
                  : {
                      audit:
                        "Periksa struktur halaman tanpa mengirim HTML ke layanan lain.",
                      local: `Bantu pelanggan menemukan ${p.name} di ${p.city || "wilayah Anda"}.`,
                      keywords:
                        "Kelompokkan kata kunci berdasarkan niat pencarian pembaca.",
                      calendar:
                        "Dari ide pertama sampai artikel terbit. Semua rencana di satu tempat.",
                      ai: "Pilih memakai AI atau tetap manual. Atur koneksi, cadangan, dan lihat token yang dilaporkan.",
                      reports:
                        "Simpan hasil pekerjaan, bagikan temuan, dan cadangkan proyek.",
                    }[page]}
              </p>
            </div>
            <button
              onClick={() => {
                if (page === "overview" && beginner) {
                  setModal("help");
                  return;
                }
                if (page === "ai") {
                  setModal("help");
                  return;
                }
                if (page === "calendar") openArticle();
                else if (page === "reports") exportBackup();
                else if (page === "local" || page === "keywords")
                  go("calendar");
                else go("audit");
              }}
              className={`${button} bg-[#285e46] text-white hover:bg-[#1e4936]`}
            >
              {page === "calendar" ? (
                <Plus size={16} />
              ) : page === "reports" ? (
                <ArrowDownToLine size={16} />
              ) : (
                <ClipboardCheck size={16} />
              )}
              {page === "ai"
                ? "Bantuan & privasi"
                : page === "calendar"
                  ? "Tambah konten"
                  : page === "reports"
                    ? "Cadangkan proyek"
                    : page === "overview" && beginner
                      ? "Bantuan & arti istilah"
                      : page === "local" || page === "keywords"
                        ? "Lanjut ke rencana konten"
                        : "Audit halaman"}
              {page === "overview" && <ArrowUpRight size={15} />}
            </button>
          </div>
          <div className="mb-7 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#e1e6d9] bg-[#eff3e9] px-4 py-3">
            <div className="flex flex-wrap items-center gap-3">
              <Globe2 size={16} className="text-[#738866]" />
              <span className="text-xs font-semibold">
                {p.domain || p.name}
              </span>
              <span className="text-[#ced6c3]">|</span>
              <span className="flex items-center gap-1 text-xs text-[#7e8874]">
                <MapPin size={12} />
                {p.city || "Indonesia"}
              </span>
              {p.industry && (
                <>
                  <span className="text-[#ced6c3]">|</span>
                  <span className="text-xs text-[#7e8874]">
                    {industryLabel(p.industry)}
                  </span>
                </>
              )}
              {p.id === "contoh" && <Badge>Data contoh</Badge>}
            </div>
            <span className="text-[11px] text-[#7c8871]">
              {p.id === "contoh"
                ? "Proyek ilustrasi. Buat proyek baru untuk data Anda."
                : "Data proyek disimpan hanya pada perangkat ini."}
            </span>
          </div>

          {page === "ai" && <AiWorkspace ai={ai} project={p} seed={aiSeed} />}
          {beginner && page !== "overview" && <PageHelp page={page} />}
          {(page === "calendar" || (page === "audit" && p.audit)) && (
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#d7e2cc] bg-white px-4 py-3">
              <p className="text-xs leading-6 text-[#627653]">
                Butuh bantuan tambahan? AI bersifat opsional. Data belum dikirim
                sebelum Anda meninjau permintaan.
              </p>
              <button
                onClick={() => {
                  setAiSeed({
                    projectId: p.id,
                    id: crypto.randomUUID(),
                    task: page === "audit" ? "recommendations" : "ideas",
                    topic:
                      page === "audit"
                        ? `Prioritas perbaikan SEO untuk ${p.name}`
                        : `Ide konten untuk ${p.name}`,
                    notes:
                      page === "audit" && p.audit
                        ? evaluateAudit(p.audit)
                            .map(
                              (c) =>
                                `${c.pass ? "Lolos" : "Perlu diperiksa"}: ${c.name}. ${c.detail}`,
                            )
                            .join("\n")
                        : "",
                  });
                  setPage("ai");
                }}
                className={`${button} border border-[#ceddc1] text-xs`}
              >
                <Bot size={15} />
                {page === "audit"
                  ? "Siapkan saran AI (opsional)"
                  : "Siapkan ide AI (opsional)"}
              </button>
            </div>
          )}

          {beginner && page === "calendar" && (
            <IdeaStarter
              key={p.id}
              city={p.city}
              onPlan={(title, keyword) =>
                openArticle(null, localDateKey(new Date()), { title, keyword })
              }
            />
          )}
          {page === "overview" && (
            <>
              {beginner && (
                <BeginnerStart
                  project={p}
                  onCreate={() => setModal("project")}
                  onGo={go}
                  onBackup={exportBackup}
                />
              )}
              <details
                key={beginner ? "guided" : "expert"}
                open={!beginner}
                className="mb-5"
              >
                <summary
                  className={
                    beginner
                      ? "mb-5 cursor-pointer rounded-lg border border-[#dce3d2] bg-white px-4 py-4 text-sm font-semibold text-[#466d35]"
                      : "hidden"
                  }
                >
                  Lihat angka dan temuan teknis (opsional)
                </summary>
                <div className="mb-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {[
                    {
                      label: "Kesehatan halaman",
                      value: score === null ? "—" : `${score}`,
                      unit: score === null ? "" : "/ 100",
                      icon: ShieldCheck,
                      sub:
                        score === null
                          ? "Jalankan audit pertama"
                          : `${passed} dari ${checks.length} pemeriksaan lolos`,
                      badge: "audit",
                    },
                    {
                      label: "Kata kunci terkumpul",
                      value: keywordCount,
                      unit: "kata kunci",
                      icon: Search,
                      sub: `${Object.keys(clusters).length} klaster niat pencarian`,
                      badge: "keywords",
                    },
                    {
                      label: "Rencana konten",
                      value: p.articles.length,
                      unit: "artikel",
                      icon: FileText,
                      sub: `${published} terbit · ${p.articles.length - published} dalam rencana`,
                      badge: "calendar",
                    },
                    {
                      label: "Kesiapan SEO lokal",
                      value: `${p.checks.length}`,
                      unit: `/ ${localTasks.length} langkah`,
                      icon: MapPin,
                      sub:
                        p.checks.length === localTasks.length
                          ? "Semua langkah sudah ditandai"
                          : `${localTasks.length - p.checks.length} langkah masih perlu diperiksa`,
                      badge: "local",
                    },
                  ].map((m) => (
                    <button
                      key={m.label}
                      onClick={() => go(m.badge)}
                      className={`${box} p-5 text-left transition-shadow hover:shadow-md focus-visible:outline-2 focus-visible:outline-[#285e46]`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-[#7a8472]">
                          {m.label}
                        </span>
                        <m.icon
                          size={17}
                          strokeWidth={1.5}
                          className="text-[#8b977f]"
                        />
                      </div>
                      <div className="mb-3 mt-5 flex items-baseline gap-2">
                        <span className="text-4xl font-medium tracking-[-1.5px]">
                          {m.value}
                        </span>
                        <span className="text-xs text-[#8e9786]">{m.unit}</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-[11px] text-[#77876a]">
                        <span className="size-1 rounded-full bg-[#83a765]" />
                        {m.sub}
                      </div>
                    </button>
                  ))}
                </div>
                <div className="grid gap-5 xl:grid-cols-[1.65fr_1fr]">
                  <section className={`${box} p-6`}>
                    <SectionHeading
                      title="Yang perlu didahulukan"
                      note="Selesaikan temuan yang paling memengaruhi struktur halaman."
                      action={<Badge>{openTasks.length} temuan</Badge>}
                    />
                    <div className="space-y-1">
                      {openTasks.length ? (
                        openTasks.slice(0, 4).map((c, i) => (
                          <button
                            onClick={() => go("audit")}
                            key={c.id}
                            className="flex w-full items-start gap-3 rounded-lg border-b border-[#edf0e8] px-1 py-4 text-left last:border-0 hover:bg-[#f8faf4]"
                          >
                            <span className="mt-0.5 flex size-7 items-center justify-center rounded-lg bg-[#f4eee1] text-xs text-[#987b44]">
                              0{i + 1}
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-[13px] font-semibold">
                                  {c.name}
                                </span>
                                <Badge muted>{c.priority}</Badge>
                              </div>
                              <p className="mt-1.5 text-xs leading-5 text-[#818975]">
                                {c.detail}
                              </p>
                            </div>
                            <ArrowUpRight
                              size={16}
                              className="mt-1 text-[#849278]"
                            />
                          </button>
                        ))
                      ) : (
                        <div className="py-9 text-center">
                          <CheckCircle2 className="mx-auto mb-3 text-[#71945a]" />
                          <p className="text-sm">
                            {score === null
                              ? "Belum ada audit untuk proyek ini."
                              : "Semua pemeriksaan HTML lolos."}
                          </p>
                          <p className="mt-2 text-xs text-[#89917f]">
                            {score === null
                              ? "Tempel HTML halaman untuk melihat langkah perbaikan."
                              : "Lanjutkan dengan checklist SEO lokal dan konten."}
                          </p>
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => go("audit")}
                      className={`${button} mt-3 w-full border border-[#e1e6da] text-xs`}
                    >
                      Buka hasil audit
                      <ArrowRight size={14} />
                    </button>
                  </section>
                  <section className="relative overflow-hidden rounded-xl border border-[#dce5cc] bg-[#eaf0df] p-6">
                    <div className="absolute -right-10 -top-10 size-44 rounded-full border border-[#d7e1c5]" />
                    <div className="absolute -right-3 -top-3 size-30 rounded-full border border-[#d7e1c5]" />
                    <div className="relative">
                      <Badge>
                        <MapPin size={12} className="mr-1" /> FOKUS LOKAL
                      </Badge>
                      <h2 className="mt-5 max-w-60 text-[23px] font-medium leading-8 tracking-tight">
                        Lebih mudah ditemukan
                        <br />
                        di {p.city || "kota Anda"}.
                      </h2>
                      <p className="mt-3 max-w-70 text-xs leading-6 text-[#7a8668]">
                        Mulai dari informasi bisnis yang akurat. Bantu orang di
                        sekitar Anda menemukan layanan yang mereka butuhkan.
                      </p>
                      <div className="mb-2 mt-6 flex justify-between text-[11px]">
                        <span>Checklist bisnis lokal</span>
                        <span className="font-semibold">
                          {p.checks.length} / {localTasks.length}
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-[#d7e1c6]">
                        <div
                          className="h-full rounded-full bg-[#6d9155]"
                          style={{
                            width: `${(p.checks.length / localTasks.length) * 100}%`,
                          }}
                        />
                      </div>
                      <button
                        onClick={() => go("local")}
                        className={`${button} mt-5 w-full bg-white/80 text-xs hover:bg-white`}
                      >
                        Lanjutkan checklist
                        <ArrowRight size={14} />
                      </button>
                    </div>
                  </section>
                </div>
                <section className={`${box} mt-5 p-6`}>
                  <SectionHeading
                    title="Konten berikutnya"
                    note="Jadwal yang Anda rencanakan untuk proyek ini."
                    action={
                      <button
                        className={`${button} text-xs text-[#60814b]`}
                        onClick={() => go("calendar")}
                      >
                        Lihat kalender
                        <ArrowRight size={14} />
                      </button>
                    }
                  />
                  {p.articles.some((a) => a.status !== "Terbit") ? (
                    <div className="grid gap-4 md:grid-cols-3">
                      {[...p.articles]
                        .filter((a) => a.status !== "Terbit")
                        .sort((a, b) => a.date.localeCompare(b.date))
                        .slice(0, 3)
                        .map((a) => (
                          <button
                            key={a.id}
                            onClick={() => setBrief(a)}
                            className="rounded-lg border border-[#e7eadf] p-4 text-left hover:bg-[#f9fbf6]"
                          >
                            <div className="flex items-center justify-between">
                              <span className="flex items-center gap-1.5 text-[11px] text-[#839076]">
                                <CalendarDays size={13} />
                                {new Date(
                                  a.date + "T12:00:00",
                                ).toLocaleDateString("id-ID", {
                                  day: "numeric",
                                  month: "short",
                                })}
                              </span>
                              <Badge muted={a.status === "Ide"}>
                                {a.status}
                              </Badge>
                            </div>
                            <p className="mb-4 mt-3 text-[13px] font-semibold leading-5">
                              {a.title}
                            </p>
                            <span className="text-[11px] text-[#8e977e]">
                              {a.keyword || "Kata kunci belum dipilih"}
                            </span>
                          </button>
                        ))}
                    </div>
                  ) : (
                    <button
                      className={`${button} w-full border border-dashed border-[#cbd6bd] py-8 text-[#7b876e]`}
                      onClick={() => openArticle()}
                    >
                      <Plus size={16} />
                      {p.articles.length
                        ? "Semua konten sudah terbit. Rencanakan konten berikutnya"
                        : "Rencanakan konten pertama"}
                    </button>
                  )}
                </section>
              </details>
            </>
          )}

          {page === "audit" && (
            <div className="grid items-start gap-5 xl:grid-cols-[1fr_1.2fr]">
              <section className={`${box} p-6`}>
                <SectionHeading
                  title="Audit dari kode HTML"
                  note="Memeriksa kode halaman yang Anda berikan. Bukan memindai alamat situs otomatis."
                />
                {beginner && (
                  <div className="mb-5 rounded-lg bg-[#f0f5e9] p-4 text-sm leading-6">
                    <p>
                      Belum punya kode halaman? Tidak apa-apa. Anda bisa mulai
                      dari informasi bisnis yang terlihat oleh pelanggan.
                    </p>
                    <button
                      onClick={() => go("local")}
                      className={`${button} mt-2 border border-[#ceddc3] bg-white text-xs`}
                    >
                      Mulai tanpa kode HTML
                      <ArrowRight size={14} />
                    </button>
                  </div>
                )}
                <button
                  onClick={() => htmlUploadRef.current?.click()}
                  className={`${button} mb-4 border border-[#ceddc3] text-xs`}
                >
                  <Upload size={15} />
                  Pilih berkas HTML
                </button>
                <input
                  ref={htmlUploadRef}
                  aria-label="Unggah berkas HTML"
                  type="file"
                  accept=".html,.htm,text/html"
                  className="hidden"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (!file) return;
                    if (!/\.html?$/i.test(file.name)) {
                      setAuditError(
                        "Pilih berkas .html atau .htm, bukan gambar atau PDF.",
                      );
                      return;
                    }
                    if (file.size > 2_000_000) {
                      setAuditError(
                        "Berkas terlalu besar. Batas unggahan adalah 2 MB.",
                      );
                      return;
                    }
                    try {
                      const text = await file.text();
                      setHtml(text);
                      setAuditError("");
                      setToast(
                        "Berkas dimuat. Klik Periksa HTML untuk melihat hasilnya.",
                      );
                    } catch {
                      setAuditError(
                        "Berkas tidak dapat dibaca. Coba salin dan tempel kode halaman.",
                      );
                    }
                  }}
                />
                <label htmlFor="html" className="text-xs font-medium">
                  Kode sumber halaman
                </label>
                <textarea
                  id="html"
                  value={html}
                  onChange={(e) => setHtml(e.target.value)}
                  maxLength={2000000}
                  placeholder={
                    '<!doctype html>\n<html lang="id">\n  <head>\n    <title>Judul halaman Anda</title>\n  </head>\n  ...\n</html>'
                  }
                  className={`${field} min-h-72 font-mono text-xs leading-6`}
                />
                <p className="mt-3 text-xs leading-5 text-[#7b8771]">
                  Buka situs → klik kanan → Lihat sumber halaman. Salin HTML ke
                  sini. Hanya struktur HTML yang diperiksa, bukan kecepatan,
                  status HTTP, atau peringkat Google.
                </p>
                {auditError && (
                  <p role="alert" className="mt-3 text-sm text-red-700">
                    {auditError}
                  </p>
                )}
                <button
                  disabled={busy || !html.trim()}
                  onClick={() => void audit()}
                  className={`${button} mt-5 w-full bg-[#285e46] text-white hover:bg-[#1e4936]`}
                >
                  <ClipboardCheck size={16} />
                  {busy ? "Memeriksa…" : "Periksa HTML"}
                </button>
              </section>
              <section className={`${box} p-6`}>
                <SectionHeading
                  title={
                    score === null
                      ? "Hasil pemeriksaan"
                      : `Skor checklist: ${score}/100`
                  }
                  note={
                    p.auditedAt
                      ? `Audit terakhir: ${new Date(p.auditedAt).toLocaleString("id-ID")}`
                      : "Hasil akan muncul setelah Anda menjalankan audit."
                  }
                />
                {checks.map((c) => (
                  <details
                    key={c.id}
                    className="border-b border-[#e8ebdf] py-4"
                  >
                    <summary className="flex cursor-pointer items-center gap-3 text-xs font-semibold">
                      {c.pass ? (
                        <CheckCircle2 size={17} className="text-[#648a4d]" />
                      ) : (
                        <span className="flex size-4 items-center justify-center rounded-full bg-amber-100 text-amber-800">
                          !
                        </span>
                      )}
                      <span className="flex-1">{c.name}</span>
                      <Badge muted>{c.pass ? "Lolos" : c.priority}</Badge>
                      <ChevronDown size={14} />
                    </summary>
                    <p className="pl-7 pt-3 text-xs leading-6 text-[#75806b]">
                      {c.detail}
                    </p>
                  </details>
                ))}
                <p className="mt-4 text-[11px] leading-5 text-[#87917d]">
                  Skor checklist adalah panduan perbaikan, bukan penilaian
                  Google. Rentang panjang judul dan deskripsi merupakan panduan
                  editorial, bukan aturan peringkat.
                </p>
              </section>
            </div>
          )}

          {page === "local" && (
            <section className={`${box} p-6`}>
              <SectionHeading
                title={`Checklist bisnis di ${p.city || "wilayah Anda"}`}
                note="Tandai setelah Anda memeriksa dan menyelesaikan langkahnya."
                action={
                  <Badge>
                    {p.checks.length} dari {localTasks.length} selesai
                  </Badge>
                }
              />
              {localTasks.map((t) => (
                <label
                  key={t.id}
                  aria-label={t.title}
                  className="flex cursor-pointer items-start gap-4 border-b border-[#e7ebdf] py-6 last:border-0"
                >
                  <input
                    type="checkbox"
                    checked={p.checks.includes(t.id)}
                    onChange={(e) =>
                      update({
                        checks: e.target.checked
                          ? [...p.checks, t.id]
                          : p.checks.filter((id) => id !== t.id),
                      })
                    }
                    className="mt-1 size-5 accent-[#285e46]"
                  />
                  <div className="flex-1">
                    <p
                      className={`text-sm font-semibold ${p.checks.includes(t.id) ? "text-[#809074] line-through" : ""}`}
                    >
                      {t.title}
                    </p>
                    <p className="mt-2 text-xs leading-6 text-[#7d8774]">
                      {t.detail}
                    </p>
                  </div>
                  <Badge muted>{t.tag}</Badge>
                </label>
              ))}
              <p className="mt-4 text-xs text-[#7d8774]">
                Checklist manual. LokaSEO tidak terhubung ke Profil Bisnis
                Google dan tidak memverifikasi perubahan secara otomatis.
              </p>
            </section>
          )}

          {page === "keywords" && (
            <div className="grid items-start gap-5 xl:grid-cols-[.9fr_1.3fr]">
              <section className={`${box} p-6`}>
                <SectionHeading
                  title="Kumpulan kata kunci"
                  note="Satu kata kunci per baris, atau pisahkan dengan koma."
                />
                <label htmlFor="keywords" className="sr-only">
                  Daftar kata kunci
                </label>
                <textarea
                  id="keywords"
                  value={p.keywords}
                  maxLength={50000}
                  onChange={(e) => update({ keywords: e.target.value })}
                  placeholder="kedai kopi bogor\nharga kopi arabika\ncara menyeduh kopi"
                  className={`${field} min-h-80 leading-7`}
                />
                <p className="mt-3 text-xs leading-6 text-[#7d8774]">
                  Otomatis dikelompokkan dengan aturan kata sederhana. Maksimal
                  500 kata kunci unik. Bukan riset volume pencarian atau
                  pengelompokan semantik AI.
                </p>
                <button
                  onClick={() => {
                    const csv =
                      "Klaster,Kata kunci\r\n" +
                      Object.entries(clusters)
                        .flatMap(([group, keywords]) =>
                          keywords.map(
                            (k) => `${csvCell(group)},${csvCell(k)}`,
                          ),
                        )
                        .join("\r\n");
                    download(
                      "klaster-kata-kunci.csv",
                      "\ufeff" + csv,
                      "text/csv;charset=utf-8",
                    );
                  }}
                  disabled={!keywordCount}
                  className={`${button} mt-4 border border-[#dae2d0]`}
                >
                  <ArrowDownToLine size={16} />
                  Ekspor CSV
                </button>
              </section>
              <div className="space-y-4">
                {Object.entries(clusters).map(([group, keywords]) => (
                  <section key={group} className={`${box} p-5`}>
                    <SectionHeading
                      title={group}
                      action={<Badge>{keywords.length} kata kunci</Badge>}
                    />
                    <div className="flex flex-wrap gap-2">
                      {keywords.map((k) => (
                        <span
                          key={k}
                          className="rounded-md border border-[#e0e6d7] bg-[#f7f9f2] px-3 py-2 text-xs"
                        >
                          {k}
                        </span>
                      ))}
                    </div>
                  </section>
                ))}
                {!keywordCount && (
                  <div
                    className={`${box} p-10 text-center text-sm text-[#7d8774]`}
                  >
                    <Layers3 className="mx-auto mb-4" />
                    Klaster akan muncul saat kata kunci ditambahkan.
                  </div>
                )}
              </div>
            </div>
          )}

          {page === "calendar" && (
            <section className={`${box} overflow-hidden`}>
              <div className="flex flex-wrap items-center justify-between gap-4 p-5">
                <div className="flex items-center gap-2 rounded-lg border border-[#dfe5d6] px-3">
                  <Search size={15} className="text-[#87967a]" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Cari judul konten…"
                    aria-label="Cari judul konten"
                    className="min-h-10 max-w-60 bg-transparent text-xs outline-none"
                  />
                </div>
                <select
                  aria-label="Filter status"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="min-h-10 rounded-lg border border-[#dfe5d6] bg-white px-3 text-xs"
                >
                  {["Semua", "Ide", "Ditulis", "Terbit"].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div className="flex flex-wrap items-center gap-3 border-t border-[#e4e8dc] px-5 py-3">
                <div className="inline-flex gap-1 rounded-lg bg-[#eef2e7] p-1">
                  <button
                    aria-pressed={calendarView === "list"}
                    onClick={() => setCalendarView("list")}
                    className={`${button} text-xs ${calendarView === "list" ? "bg-white shadow-sm" : ""}`}
                  >
                    Daftar
                  </button>
                  <button
                    aria-pressed={calendarView === "month"}
                    onClick={() => setCalendarView("month")}
                    className={`${button} text-xs ${calendarView === "month" ? "bg-white shadow-sm" : ""}`}
                  >
                    <CalendarDays size={14} />
                    Bulanan
                  </button>
                </div>
                <label className="flex min-h-11 cursor-pointer items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={onlyOverdue}
                    onChange={(e) => setOnlyOverdue(e.target.checked)}
                    className="size-4 accent-[#285e46]"
                  />
                  Lewat jadwal ({overdueCount})
                </label>
                {(search || statusFilter !== "Semua" || onlyOverdue) && (
                  <button
                    className={`${button} text-xs underline`}
                    onClick={() => {
                      setSearch("");
                      setStatusFilter("Semua");
                      setOnlyOverdue(false);
                    }}
                  >
                    Reset filter
                  </button>
                )}
              </div>
              {calendarView === "month" && (
                <MonthCalendar
                  month={month}
                  onMonth={setMonth}
                  articles={articles}
                  onEdit={(a) => openArticle(a)}
                  onAdd={(date) => openArticle(null, date)}
                />
              )}
              <div
                className={
                  calendarView === "list"
                    ? "hidden overflow-x-auto sm:block"
                    : "hidden"
                }
              >
                <table className="w-full min-w-[650px] text-left text-xs">
                  <thead className="border-y border-[#e4e8dc] bg-[#f7f9f2] text-[10px] uppercase tracking-wider text-[#8a957e]">
                    <tr>
                      <th className="px-6 py-4">Tanggal</th>
                      <th>Judul & kata kunci</th>
                      <th>Status</th>
                      <th className="pr-5 text-right">Tindakan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {articles.map((a) => (
                      <tr key={a.id} className="border-b border-[#e9ecdf]">
                        <td className="whitespace-nowrap px-6 py-6 text-[#859175]">
                          {new Date(a.date + "T12:00:00").toLocaleDateString(
                            "id-ID",
                            { day: "numeric", month: "short", year: "numeric" },
                          )}
                        </td>
                        <td className="max-w-100 py-5 pr-5">
                          <button
                            onClick={() => setBrief(a)}
                            className="text-left font-semibold hover:underline"
                          >
                            {a.title}
                          </button>
                          <p className="mt-2 text-[11px] text-[#8a947e]">
                            {a.keyword || "Tanpa kata kunci"}
                          </p>
                        </td>
                        <td>
                          <select
                            aria-label={`Status ${a.title}`}
                            value={a.status}
                            onChange={(e) =>
                              update({
                                articles: p.articles.map((item) =>
                                  item.id === a.id
                                    ? {
                                        ...item,
                                        status: e.target
                                          .value as Article["status"],
                                      }
                                    : item,
                                ),
                              })
                            }
                            className="min-h-10 rounded-lg bg-[#edf2e5] px-2 text-xs"
                          >
                            {["Ide", "Ditulis", "Terbit"].map((s) => (
                              <option key={s}>{s}</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-4 text-right">
                          <button
                            aria-label={`Edit ${a.title}`}
                            onClick={() => openArticle(a)}
                            className={`${button} px-2`}
                          >
                            <Pencil size={15} />
                          </button>
                          <button
                            aria-label={`Buka brief ${a.title}`}
                            onClick={() => setBrief(a)}
                            className={`${button} px-2`}
                          >
                            <FileText size={16} />
                          </button>
                          <button
                            aria-label={`Hapus ${a.title}`}
                            onClick={() => deleteArticle(a)}
                            className={`${button} px-2 text-[#9a8b79]`}
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {calendarView === "list" && (
                <div className="space-y-3 px-4 pb-4 sm:hidden">
                  {articles.map((a) => (
                    <article
                      key={a.id}
                      className="rounded-xl border border-[#dce3d2] bg-[#fafbf7] p-4"
                    >
                      <div className="mb-3 flex items-center justify-between gap-2">
                        <time
                          dateTime={a.date}
                          className="text-xs text-[#677b5b]"
                        >
                          {new Date(a.date + "T12:00:00").toLocaleDateString(
                            "id-ID",
                          )}
                        </time>
                        <Badge muted>{a.status}</Badge>
                      </div>
                      <h2 className="text-sm font-semibold">{a.title}</h2>
                      <p className="mt-2 text-xs text-[#677b5b]">
                        {a.keyword || "Tanpa kata kunci"}
                      </p>
                      <div className="mt-4 flex flex-wrap gap-1">
                        <button
                          aria-label={`Edit seluler ${a.title}`}
                          onClick={() => openArticle(a)}
                          className={`${button} border border-[#dce3d2] text-xs`}
                        >
                          <Pencil size={14} />
                          Edit
                        </button>
                        <button
                          aria-label={`Brief seluler ${a.title}`}
                          onClick={() => setBrief(a)}
                          className={`${button} text-xs`}
                        >
                          <FileText size={14} />
                          Brief
                        </button>
                        <button
                          aria-label={`Hapus seluler ${a.title}`}
                          onClick={() => deleteArticle(a)}
                          className={`${button} ml-auto px-3 text-red-700`}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
              {calendarView === "list" && !articles.length && (
                <div className="p-12 text-center text-sm text-[#7d8774]">
                  {p.articles.length
                    ? "Tidak ada konten yang cocok dengan filter."
                    : "Belum ada rencana konten. Tambahkan ide pertama Anda."}
                </div>
              )}
              <div className="flex flex-wrap justify-between gap-2 p-5 text-[11px] text-[#8b957e]">
                <span>
                  {calendarView === "month"
                    ? articles.filter((a) => a.date.startsWith(month)).length
                    : articles.length}{" "}
                  rencana ditampilkan
                </span>
                <span>Jadwal manual · tidak menerbitkan artikel otomatis</span>
              </div>
            </section>
          )}

          {page === "reports" && (
            <>
              <div className="grid gap-5 md:grid-cols-3">
                {[
                  {
                    title: "Laporan audit & SEO lokal",
                    text: "Temuan, prioritas perbaikan, checklist lokal, dan kalender dalam berkas Markdown.",
                    icon: ClipboardCheck,
                    label: "Unduh laporan .md",
                    click: () =>
                      download(
                        "laporan-lokaseo.md",
                        reportText(),
                        "text/markdown;charset=utf-8",
                      ),
                  },
                  {
                    title: "Kalender konten",
                    text: "Buka rencana konten di aplikasi spreadsheet atau bagikan dengan penulis Anda.",
                    icon: CalendarDays,
                    label: "Unduh kalender .csv",
                    click: () =>
                      download(
                        "kalender-lokaseo.csv",
                        "\ufeffTanggal,Judul,Kata kunci,Status\r\n" +
                          p.articles
                            .map((a) =>
                              [a.date, a.title, a.keyword, a.status]
                                .map(csvCell)
                                .join(","),
                            )
                            .join("\r\n"),
                        "text/csv;charset=utf-8",
                      ),
                  },
                  {
                    title: "Cadangan semua proyek",
                    text: "Simpan seluruh data browser. Gunakan berkas ini untuk memindahkan ruang kerja ke perangkat lain.",
                    icon: FolderOpen,
                    label: "Unduh cadangan .json",
                    click: exportBackup,
                  },
                ].map((r) => (
                  <section key={r.title} className={`${box} flex flex-col p-6`}>
                    <r.icon
                      size={25}
                      strokeWidth={1.5}
                      className="mb-6 text-[#72945b]"
                    />
                    <h2 className="text-sm font-semibold">{r.title}</h2>
                    <p className="mb-6 mt-3 flex-1 text-xs leading-6 text-[#7d8774]">
                      {r.text}
                    </p>
                    <button
                      onClick={r.click}
                      className={`${button} border border-[#dce3d2] text-xs`}
                    >
                      <ArrowDownToLine size={15} />
                      {r.label}
                    </button>
                  </section>
                ))}
              </div>
              <section
                className={`${box} mt-5 flex flex-wrap items-center justify-between gap-4 p-6`}
              >
                <div>
                  <h2 className="text-sm font-semibold">
                    Pulihkan ruang kerja
                  </h2>
                  <p className="mt-2 text-xs text-[#7d8774]">
                    Impor cadangan LokaSEO. Data saat ini akan diganti setelah
                    konfirmasi.
                  </p>
                </div>
                <button
                  className={`${button} border border-[#dce3d2]`}
                  onClick={() => importRef.current?.click()}
                >
                  <Upload size={16} />
                  Impor JSON
                </button>
                <input
                  ref={importRef}
                  type="file"
                  accept=".json,application/json"
                  className="hidden"
                  onChange={async (e) => {
                    const f = e.target.files?.[0];
                    e.target.value = "";
                    if (!f) return;
                    if (f.size > 5000000) {
                      setToast("Berkas terlalu besar. Maksimal 5 MB.");
                      return;
                    }
                    try {
                      const data = workspaceSchema.parse(
                        JSON.parse(await f.text()),
                      );
                      if (
                        window.confirm(
                          "Ganti seluruh ruang kerja dengan cadangan ini? Unduh cadangan saat ini lebih dahulu jika masih dibutuhkan.",
                        )
                      ) {
                        // Explicit replacement was confirmed; establish a fresh compare-and-write baseline.
                        try {
                          storedSnapshot.current = localStorage.getItem(STORE);
                        } catch {
                          /* the save effect reports a storage failure */
                        }
                        storedState.current = null;
                        setRawRecovery(null);
                        setDeletedArticle(null);
                        setWs(data);
                        setStorageError("");
                        setHtml("");
                        setToast("Cadangan berhasil dipulihkan.");
                      }
                    } catch {
                      setToast(
                        "Berkas tidak valid. Pilih cadangan JSON LokaSEO versi 1.",
                      );
                    }
                  }}
                />
              </section>
            </>
          )}
          {deletedArticle && (
            <div
              role="status"
              className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#d3dfc7] bg-[#edf3e7] p-4 text-xs"
            >
              <span>“{deletedArticle.article.title}” dihapus.</span>
              <div className="flex gap-2">
                <button
                  onClick={undoDelete}
                  className={`${button} border border-[#c9d8bc] text-xs`}
                >
                  Urungkan hapus
                </button>
                <button
                  aria-label="Tutup pemulihan konten"
                  onClick={() => setDeletedArticle(null)}
                  className={`${button} px-2`}
                >
                  <X size={15} />
                </button>
              </div>
            </div>
          )}
          <footer className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-[#e2e7d9] pt-5 text-[10px] text-[#98a18d]">
            <span className="flex items-center gap-1.5">
              <Leaf size={12} /> LokaSEO · Dirancang untuk tumbuh, bukan
              berlangganan.
            </span>
            <span>
              Berbasis OpenSEO · MIT {standalone ? "· Modul mandiri" : ""}
            </span>
          </footer>
        </main>
      </div>
      {toast && (
        <div
          role="status"
          className="fixed bottom-6 left-5 right-5 z-50 mx-auto flex max-w-xl items-center gap-3 rounded-xl bg-[#253e2e] px-5 py-4 text-sm text-white shadow-lg"
        >
          <Check size={18} />
          <span className="flex-1">{toast}</span>
          <button aria-label="Tutup pesan" onClick={() => setToast("")}>
            <X size={16} />
          </button>
        </div>
      )}
      <dialog
        ref={dialogRef}
        aria-labelledby="workspace-dialog-title"
        onCancel={() => {
          setModal(null);
          setBrief(null);
        }}
        className="fixed inset-0 m-auto max-h-[90vh] w-[calc(100%-32px)] max-w-lg overflow-y-auto rounded-2xl bg-[#fafbf7] p-7 text-[#283c31] shadow-xl backdrop:bg-[#1b3027]/40"
      >
        <div className="mb-6 flex items-center justify-between gap-4">
          <h2
            id="workspace-dialog-title"
            className="text-xl font-semibold tracking-tight"
          >
            {brief
              ? "Brief artikel"
              : modal === "project"
                ? "Buat proyek baru"
                : modal === "settings"
                  ? "Pengaturan proyek"
                  : modal === "delete-project"
                    ? "Hapus proyek"
                    : modal === "search"
                      ? "Cari di ruang kerja"
                      : modal === "article"
                        ? editingArticle
                          ? "Edit konten & jadwal"
                          : "Rencanakan konten"
                        : "Tentang ruang kerja ini"}
          </h2>
          <button
            onClick={() => {
              setModal(null);
              setBrief(null);
            }}
            aria-label="Tutup dialog"
            className={`${button} px-2`}
          >
            <X size={20} />
          </button>
        </div>
        {formError && (
          <p
            role="alert"
            className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700"
          >
            {formError}
          </p>
        )}
        {modal === "project" && (
          <form onSubmit={saveProject} className="space-y-5">
            {beginner && (
              <p className="rounded-lg bg-[#edf3e5] p-4 text-sm leading-6 text-[#506b42]">
                Proyek adalah tempat menyimpan pekerjaan untuk satu usaha atau
                situs. Cukup isi nama dulu. Kolom lain boleh dikosongkan, tetapi
                mengisi jenis usaha dan kota membuat panduan serta radar menjadi
                lebih tepat.
              </p>
            )}
            <label className="block text-xs font-medium">
              Nama proyek
              <input
                autoFocus
                name="name"
                required
                maxLength={80}
                className={field}
                placeholder="Misalnya: Kedai Roti Bogor"
              />
            </label>
            <label className="block text-xs font-medium">
              Domain situs
              <input
                name="domain"
                maxLength={250}
                className={field}
                placeholder="kedairoti.id"
              />
            </label>
            <label className="block text-xs font-medium">
              Kota / wilayah layanan
              <input
                name="city"
                maxLength={80}
                className={field}
                placeholder="Bogor"
              />
            </label>
            <label className="block text-xs font-medium">
              Jenis usaha
              <select name="industry" className={field} defaultValue="">
                <option value="">Belum dipilih</option>
                {industries.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-[11px] leading-4 text-[#7d8774]">
                Dipakai untuk menyiapkan pemeriksaan data terstruktur, usulan
                kata kunci, dan ambang rating pada radar pemantauan.
              </span>
            </label>
            <p className="text-xs leading-5 text-[#7d8774]">
              Domain adalah alamat situs, misalnya kedairoti.id. Jika belum
              punya situs, kosongkan saja. Data tersimpan di browser ini; unduh
              cadangan secara berkala.
            </p>
            <button
              className={`${button} w-full bg-[#285e46] text-white hover:bg-[#1e4936]`}
              type="submit"
            >
              <Plus size={16} />
              Buat proyek
            </button>
          </form>
        )}
        {modal === "article" && (
          <form
            key={editingArticle?.id ?? plannedDate}
            onSubmit={saveArticle}
            className="space-y-5"
          >
            {beginner && (
              <p className="rounded-lg bg-[#edf3e5] p-4 text-sm leading-6 text-[#506b42]">
                Isi judul tulisan dan tanggal rencana. Kata kunci boleh kosong.
                Menyimpan rencana tidak menerbitkan artikel ke situs.
              </p>
            )}
            <label className="block text-xs font-medium">
              Judul konten
              <input
                autoFocus
                name="title"
                defaultValue={editingArticle?.title ?? articleDraft.title}
                required
                maxLength={200}
                className={field}
                placeholder="Apa yang ingin Anda tulis?"
              />
            </label>
            <label className="block text-xs font-medium">
              Kata kunci utama
              <input
                name="keyword"
                defaultValue={editingArticle?.keyword ?? articleDraft.keyword}
                maxLength={200}
                className={field}
                placeholder="Contoh: toko roti bogor"
                list="project-keywords"
              />
              <datalist id="project-keywords">
                {Object.values(clusters)
                  .flat()
                  .map((k) => (
                    <option key={k} value={k} />
                  ))}
              </datalist>
            </label>
            <label className="block text-xs font-medium">
              Tanggal rencana terbit
              <input
                name="date"
                type="date"
                required
                min="1900-01-01"
                max="2100-12-31"
                defaultValue={editingArticle?.date ?? plannedDate}
                className={field}
              />
            </label>
            {editingArticle && (
              <label className="block text-xs font-medium">
                Status konten
                <select
                  name="status"
                  aria-label="Status konten"
                  defaultValue={editingArticle.status}
                  className={field}
                >
                  {["Ide", "Ditulis", "Terbit"].map((status) => (
                    <option key={status}>{status}</option>
                  ))}
                </select>
              </label>
            )}
            <button
              className={`${button} w-full bg-[#285e46] text-white hover:bg-[#1e4936]`}
              type="submit"
            >
              <Plus size={16} />
              {editingArticle ? "Simpan perubahan" : "Simpan rencana"}
            </button>
          </form>
        )}
        {brief && (
          <>
            <div className="mb-4 rounded-lg border border-[#dce3d2] bg-[#edf3e5] p-4">
              <p className="text-xs leading-6 text-[#5c7250]">
                Brief ini memakai templat tanpa AI. Anda boleh meminta bantuan
                AI; topik akan disiapkan, tetapi belum dikirim sebelum Anda
                menekan Buat dengan AI.
              </p>
              <button
                onClick={() => {
                  setAiSeed({
                    projectId: p.id,
                    id: crypto.randomUUID(),
                    task: "brief",
                    topic: brief.title,
                    notes: `Kata kunci: ${brief.keyword || "belum dipilih"}`,
                  });
                  setBrief(null);
                  setModal(null);
                  setPage("ai");
                }}
                className={`${button} mt-2 border border-[#cbdabe] bg-white text-xs`}
              >
                <Bot size={15} />
                Perkaya brief dengan AI (opsional)
              </button>
            </div>
            <button
              onClick={() => openArticle(brief)}
              className={`${button} mb-4 border border-[#dce3d2]`}
            >
              <Pencil size={15} />
              Edit konten & jadwal
            </button>
            <pre className="whitespace-pre-wrap rounded-lg border border-[#e0e6d6] bg-white p-4 font-sans text-xs leading-6">
              {briefText(brief)}
            </pre>
            <button
              onClick={() =>
                download(
                  "brief-artikel.md",
                  briefText(brief),
                  "text/markdown;charset=utf-8",
                )
              }
              className={`${button} mt-5 w-full bg-[#285e46] text-white hover:bg-[#1e4936]`}
            >
              <ArrowDownToLine size={16} />
              Unduh brief
            </button>
          </>
        )}
        {modal === "settings" && (
          <form key={p.id} onSubmit={saveSettings} className="space-y-5">
            <label className="block text-xs font-medium">
              Nama proyek
              <input
                autoFocus
                required
                name="name"
                maxLength={80}
                defaultValue={p.name}
                className={field}
              />
            </label>
            <label className="block text-xs font-medium">
              Domain situs
              <input
                name="domain"
                maxLength={250}
                defaultValue={p.domain}
                className={field}
              />
            </label>
            <label className="block text-xs font-medium">
              Kota / wilayah layanan
              <input
                name="city"
                maxLength={80}
                defaultValue={p.city}
                className={field}
              />
            </label>
            <label className="block text-xs font-medium">
              Jenis usaha
              <select name="industry" className={field} defaultValue={p.industry}>
                <option value="">Belum dipilih</option>
                {industries.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-[11px] leading-4 text-[#7d8774]">
                Jenis usaha menentukan pemeriksaan data terstruktur, usulan kata
                kunci, dan ambang rating pada radar pemantauan.
              </span>
            </label>
            <p className="text-xs leading-5 text-[#697b5d]">
              Mengubah informasi ini tidak menghapus audit, kata kunci, atau
              rencana konten.
            </p>
            <button
              type="submit"
              className={`${button} w-full bg-[#285e46] text-white hover:bg-[#1e4936]`}
            >
              Simpan proyek
            </button>
            <div className="border-t border-[#e0e6d7] pt-5">
              <button
                type="button"
                disabled={ws.projects.length === 1}
                onClick={() => {
                  setDeleteName("");
                  setModal("delete-project");
                }}
                className={`${button} w-full border border-red-200 text-red-700`}
              >
                <Trash2 size={16} />
                Hapus proyek ini
              </button>
              <p className="mt-2 text-xs text-[#697b5d]">
                {ws.projects.length === 1
                  ? "Proyek terakhir tidak dapat dihapus. Buat proyek pengganti dahulu."
                  : "Seluruh data proyek akan dihapus. Cadangkan dahulu jika masih diperlukan."}
              </p>
            </div>
          </form>
        )}
        {modal === "delete-project" && (
          <form
            className="space-y-5"
            onSubmit={(e) => {
              e.preventDefault();
              if (deleteName !== p.name || ws.projects.length === 1) return;
              setWs((w) => removeProject(w, p.id));
              setDeletedArticle(null);
              setModal(null);
              setPage("overview");
              setToast("Proyek dihapus. Proyek lain tidak berubah.");
            }}
          >
            <p className="text-sm leading-6">
              Anda akan menghapus <strong>{p.name}</strong> beserta{" "}
              {p.articles.length} rencana konten, kata kunci, dan hasil
              auditnya. Tindakan ini tidak dapat dibatalkan tanpa cadangan.
            </p>
            <button
              type="button"
              onClick={exportBackup}
              className={`${button} w-full border border-[#dce3d2]`}
            >
              <ArrowDownToLine size={16} />
              Cadangkan sebelum menghapus
            </button>
            <label className="block text-xs font-medium">
              Ketik nama proyek untuk konfirmasi
              <input
                autoFocus
                value={deleteName}
                onChange={(e) => setDeleteName(e.target.value)}
                className={field}
                autoComplete="off"
              />
            </label>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setModal("settings")}
                className={`${button} flex-1 border border-[#dce3d2]`}
              >
                Batal
              </button>
              <button
                type="submit"
                disabled={deleteName !== p.name || ws.projects.length === 1}
                className={`${button} flex-1 bg-red-700 text-white hover:bg-red-800`}
              >
                Hapus permanen
              </button>
            </div>
          </form>
        )}
        {modal === "search" && (
          <div>
            <label className="sr-only" htmlFor="global-query">
              Pencarian lintas proyek
            </label>
            <input
              id="global-query"
              autoFocus
              value={globalQuery}
              onChange={(e) => setGlobalQuery(e.target.value)}
              placeholder="Cari proyek, konten, atau kata kunci…"
              className={field}
            />
            <p className="my-3 text-xs text-[#697b5d]">
              {globalQuery.trim()
                ? `${globalResults.length} hasil · maksimal 50 hasil`
                : "Ketik nama, domain, kota, judul, atau kata kunci. Semua proyek ikut dicari."}
            </p>
            <div className="max-h-80 space-y-2 overflow-y-auto">
              {globalResults.map((result, i) => (
                <button
                  key={`${result.projectId}-${result.kind}-${i}`}
                  onClick={() => {
                    const target = ws.projects.find(
                      (project) => project.id === result.projectId,
                    )!;
                    setWs((w) => ({ ...w, activeId: target.id }));
                    setPage(result.page);
                    setSearch("");
                    setStatusFilter("Semua");
                    setOnlyOverdue(false);
                    setModal(null);
                    if (result.articleId) {
                      const article = target.articles.find(
                        (a) => a.id === result.articleId,
                      )!;
                      setMonth(article.date.slice(0, 7));
                      setBrief(article);
                    }
                  }}
                  className="block min-h-14 w-full rounded-lg border border-[#dce3d2] bg-white p-3 text-left hover:bg-[#edf2e5]"
                >
                  <span className="mb-1 block text-[10px] text-[#6f815f]">
                    {result.kind} · {result.projectName}
                  </span>
                  <span className="break-words text-sm font-semibold">
                    {result.title}
                  </span>
                </button>
              ))}
            </div>
            {globalQuery.trim() && !globalResults.length && (
              <p className="py-8 text-center text-sm text-[#697b5d]">
                Tidak ada hasil. Coba kata yang lebih singkat.
              </p>
            )}
          </div>
        )}
        {modal === "help" && (
          <div className="space-y-4 text-sm leading-6 text-[#738168]">
            <div className="rounded-lg bg-[#edf3e5] p-4">
              <h3 className="font-semibold text-[#283c31]">
                Baru mulai? Ikuti tiga langkah ini.
              </h3>
              <ol className="ml-4 mt-2 list-decimal space-y-2 text-sm">
                <li>
                  Buat proyek untuk usaha Anda; alamat situs boleh kosong.
                </li>
                <li>Buka SEO lokal dan periksa satu informasi bisnis.</li>
                <li>Buka Kalender konten untuk menjadwalkan satu tulisan.</li>
              </ol>
              <p className="mt-3 text-xs">
                Audit HTML tidak wajib di langkah awal. Aktifkan Panduan pemula
                untuk melihat petunjuk pada setiap halaman.
              </p>
            </div>
            <div className="rounded-lg bg-[#edf3e5] p-4 text-sm leading-6">
              <h3 className="font-semibold text-[#283c31]">
                AI adalah pilihan, bukan kewajiban.
              </h3>
              <p className="mt-2">
                Buka AI & token untuk memasukkan API key sesi dari OpenAI,
                OpenRouter, DeepSeek, atau Groq. Mode awal tanpa AI. Saat
                diaktifkan dan permintaan dijalankan, konteks yang Anda lihat
                dikirim ke penyedia aktif sesuai urutan. Key hilang setelah
                reload; riwayat token anonim terhadap isi prompt disimpan di
                browser, terpisah dari cadangan proyek.
              </p>
            </div>
            <SeoGlossary />
            <p>
              LokaSEO adalah fork MIT dari OpenSEO. Modul Indonesia ini bekerja
              di browser tanpa biaya aplikasi.
            </p>
            <p>
              Audit memakai HTML yang Anda tempel, bukan crawling langsung.
              Klaster dan brief menggunakan aturan serta templat, bukan AI atau
              data pencarian langsung.
            </p>
            <p>
              Data tidak tersinkron antarperangkat. Jika data browser dihapus,
              proyek ikut hilang. Unduh cadangan lewat menu Laporan secara
              berkala.
            </p>
            <p>
              Mesin OpenSEO asli tetap ada dalam repo. DataForSEO, Google Search
              Console, serta deployment Cloudflare memerlukan konfigurasi
              sendiri. Biaya layanan pihak ketiga tidak termasuk.
            </p>
            {!standalone && (
              <a
                href="/projects"
                className={`${button} w-full border border-[#dce3d2]`}
              >
                Buka mesin riset OpenSEO
                <ArrowUpRight size={15} />
              </a>
            )}
            <button
              onClick={exportBackup}
              className={`${button} w-full bg-[#285e46] text-white hover:bg-[#1e4936]`}
            >
              Unduh cadangan sekarang
            </button>
          </div>
        )}
      </dialog>
    </div>
  );
}
