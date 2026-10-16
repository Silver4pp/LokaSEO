import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowDown,
  ArrowUp,
  ArrowDownToLine,
  Bot,
  Check,
  CircleHelp,
  Copy,
  KeyRound,
  Plus,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import {
  connectionSchema,
  providerNames,
  modelExamples,
  taskNames,
  aiErrorNames,
  summarizeUsage,
  type AiConnection,
  type AiProvider,
  type AiTask,
} from "../../../shared/loka-ai";
import { csvCell, evaluateAudit, type Project } from "./model";
import type { AiController } from "./useAi";
const box = "rounded-xl border border-[#dce3d2] bg-white p-5";
const button =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[#d2ddc7] px-3 py-2 text-xs font-semibold hover:bg-[#edf3e5] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 disabled:cursor-not-allowed disabled:opacity-40";
const field =
  "mt-2 min-h-11 w-full rounded-lg border border-[#d2ddc7] bg-white px-3 py-2 text-sm outline-emerald-700";
function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export type AiSeed = {
  projectId: string;
  id: string;
  task: AiTask;
  topic: string;
  notes: string;
};
export function AiWorkspace({
  ai,
  project,
  seed,
}: {
  ai: AiController;
  project: Project;
  seed: AiSeed | null;
}) {
  const [view, setView] = useState<"assistant" | "settings" | "usage">(
    "assistant",
  );
  const [task, setTask] = useState<AiTask>("ideas");
  const [topic, setTopic] = useState("");
  const [notes, setNotes] = useState("");
  const [provider, setProvider] = useState<AiProvider>("openai");
  const [model, setModel] = useState(modelExamples.openai);
  const [label, setLabel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [formError, setFormError] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [range, setRange] = useState("30");
  const [filterProvider, setFilterProvider] = useState("all");
  const [notice, setNotice] = useState("");
  const [status, setStatus] = useState("all");
  useEffect(() => {
    setTopic("");
    setNotes("");
    if (seed && seed.projectId === project.id) {
      setTask(seed.task);
      setTopic(seed.topic);
      setNotes(seed.notes);
      setView("assistant");
    }
  }, [project.id, seed?.id]);
  const visible = ai.events.filter(
    (event) =>
      (range === "all" ||
        Date.now() - Date.parse(event.startedAt) < Number(range) * 86400000) &&
      (filterProvider === "all" || filterProvider === event.provider) &&
      (status === "all" || status === event.status),
  );
  const totals = summarizeUsage(visible);
  const token = (value: number | null) =>
    value === null ? "Tidak dilaporkan" : value.toLocaleString("id-ID");
  function move(index: number, delta: number) {
    ai.setConnections((old) => {
      const rows = [...old];
      [rows[index], rows[index + delta]] = [rows[index + delta], rows[index]];
      return rows;
    });
  }
  function resetForm() {
    setEditing(null);
    setLabel("");
    setApiKey("");
    setFormError("");
  }
  function saveConnection(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const old = ai.connections.find((c) => c.id === editing);
    const parsed = connectionSchema.safeParse({
      id: editing ?? crypto.randomUUID(),
      label: label || `${providerNames[provider]} ${ai.connections.length + 1}`,
      provider,
      model,
      apiKey: apiKey || (old?.provider === provider ? old.apiKey : undefined),
      enabled: old?.enabled ?? true,
    });
    if (!parsed.success) {
      setFormError(
        "Lengkapi API key dan nama model. Nama model hanya boleh berisi huruf, angka, garis, titik, /, :, @, atau +.",
      );
      return;
    }
    if (!editing && ai.connections.length >= 5) {
      setFormError("Maksimal lima koneksi per sesi.");
      return;
    }
    ai.setConnections((previous) =>
      editing
        ? previous.map((c) => (c.id === editing ? parsed.data : c))
        : [...previous, parsed.data],
    );
    resetForm();
    setNotice(
      "Koneksi disimpan untuk tab ini. Menyimpan koneksi tidak mengirim permintaan ke penyedia.",
    );
  }
  function editConnection(c: AiConnection) {
    setEditing(c.id);
    setProvider(c.provider);
    setModel(c.model);
    setLabel(c.label);
    setApiKey("");
    setFormError("");
  }
  function csv() {
    const rows = [
      [
        "Waktu",
        "Koneksi",
        "Penyedia",
        "Model",
        "Tugas",
        "Status",
        "Kode",
        "Cadangan",
        "Token input",
        "Token output",
        "Token total",
        "Durasi ms",
      ],
      ...visible.map((e) => [
        e.startedAt,
        e.label,
        providerNames[e.provider],
        e.model,
        taskNames[e.task],
        e.status,
        e.code,
        e.fallback ? "Ya" : "Tidak",
        e.inputTokens === null ? "Tidak dilaporkan" : String(e.inputTokens),
        e.outputTokens === null ? "Tidak dilaporkan" : String(e.outputTokens),
        e.totalTokens === null ? "Tidak dilaporkan" : String(e.totalTokens),
        String(e.durationMs),
      ]),
    ];
    download(
      "lokaseo-penggunaan-ai.csv",
      "\ufeff" + rows.map((row) => row.map(csvCell).join(",")).join("\r\n"),
      "text/csv;charset=utf-8",
    );
  }
  return (
    <div className="space-y-5">
      <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[#d2dfc6] bg-[#edf3e5] p-5">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <Bot size={20} />
            Pakai AI hanya saat Anda membutuhkannya.
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#546b47]">
            Mode manual tetap berfungsi tanpa API key. AI memakai akun penyedia
            Anda sendiri; biaya mengikuti penyedia, bukan LokaSEO.
          </p>
        </div>
        <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg bg-white px-4 text-sm font-semibold">
          <input
            type="checkbox"
            aria-label="Aktifkan AI"
            checked={ai.enabled}
            disabled={ai.busy}
            onChange={(e) => ai.setEnabled(e.target.checked)}
            className="size-5 accent-[#285e46]"
          />
          {ai.enabled ? "AI aktif" : "Tanpa AI"}
        </label>
      </section>
      <nav aria-label="Menu AI" className="flex flex-wrap gap-2">
        {(
          [
            ["assistant", "Asisten"],
            ["settings", "Koneksi & cadangan"],
            ["usage", "Penggunaan token"],
          ] as const
        ).map(([id, name]) => (
          <button
            key={id}
            aria-pressed={view === id}
            onClick={() => setView(id)}
            className={`${button} ${view === id ? "bg-[#285e46] text-white hover:bg-[#285e46]" : "bg-white"}`}
          >
            {name}
          </button>
        ))}
      </nav>
      {notice && (
        <div
          role="status"
          className="flex items-center gap-3 rounded-lg bg-[#eaf2e3] p-3 text-sm"
        >
          <Check size={16} />
          <span className="flex-1">{notice}</span>
          <button
            aria-label="Tutup pesan AI"
            onClick={() => setNotice("")}
            className={button}
          >
            <X size={14} />
          </button>
        </div>
      )}
      {view === "settings" && (
        <div className="grid items-start gap-5 xl:grid-cols-2">
          <section className={box}>
            <h2 className="text-base font-semibold">
              {editing ? "Edit koneksi" : "Tambah koneksi AI"}
            </h2>
            <p className="mt-2 text-xs leading-6 text-[#64765a]">
              Endpoint penyedia dipilih otomatis. Model di bawah hanya contoh;
              pastikan tersedia di akun Anda. Bisa memakai beberapa key atau
              model dari penyedia yang sama.
            </p>
            <form onSubmit={saveConnection} className="mt-5 space-y-4">
              <fieldset disabled={ai.busy} className="space-y-4">
                <label className="block text-xs font-semibold">
                  Nama koneksi
                  <input
                    name="label"
                    aria-label="Nama koneksi"
                    value={label}
                    maxLength={50}
                    onChange={(e) => setLabel(e.target.value)}
                    placeholder="Misalnya: Utama atau Cadangan tim"
                    className={field}
                  />
                </label>
                <label className="block text-xs font-semibold">
                  Penyedia AI
                  <select
                    aria-label="Penyedia AI"
                    value={provider}
                    onChange={(e) => {
                      const next = e.target.value as AiProvider;
                      setProvider(next);
                      setModel(modelExamples[next]);
                      setApiKey("");
                    }}
                    className={field}
                  >
                    {Object.entries(providerNames).map(([id, name]) => (
                      <option key={id} value={id}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-xs font-semibold">
                  Model
                  <input
                    aria-label="Model AI"
                    required
                    value={model}
                    maxLength={150}
                    onChange={(e) => setModel(e.target.value)}
                    className={field}
                    spellCheck={false}
                  />
                </label>
                <label className="block text-xs font-semibold">
                  API key
                  <input
                    aria-label="API key"
                    type="password"
                    autoComplete="off"
                    spellCheck={false}
                    required={!editing}
                    value={apiKey}
                    maxLength={512}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={
                      editing
                        ? "Kosongkan untuk tetap memakai key sesi ini"
                        : "Tempel key hanya di kolom ini"
                    }
                    className={field}
                  />
                </label>
                {editing && (
                  <p className="text-xs text-[#64765a]">
                    Key lama tidak ditampilkan. Jika mengganti penyedia,
                    masukkan key baru.
                  </p>
                )}
                {formError && (
                  <p role="alert" className="text-sm text-red-700">
                    {formError}
                  </p>
                )}
                <div className="flex flex-wrap gap-2">
                  <button
                    type="submit"
                    className={`${button} bg-[#285e46] text-white hover:bg-[#1e4936]`}
                  >
                    <Plus size={16} />
                    {editing ? "Simpan koneksi" : "Tambah koneksi"}
                  </button>
                  {editing && (
                    <button
                      type="button"
                      className={button}
                      onClick={resetForm}
                    >
                      Batal edit
                    </button>
                  )}
                </div>
              </fieldset>
            </form>
            <div className="mt-5 rounded-lg bg-[#f3f6ee] p-4 text-xs leading-6 text-[#5d7251]">
              <ShieldCheck size={18} className="mb-2" />
              Key hanya di memori tab ini. Reload atau tutup tab akan
              menghapusnya. Key dikirim ke server LokaSEO dan penyedia yang Anda
              pilih saat permintaan dijalankan, tanpa penyimpanan key oleh
              aplikasi. Gunakan HTTPS untuk akses publik. Gunakan instance yang
              Anda percayai.
            </div>
          </section>
          <section className={box}>
            <h2 className="text-base font-semibold">Urutan percobaan</h2>
            <p className="mt-2 text-xs leading-6 text-[#64765a]">
              Mulai dari koneksi aktif paling atas. Jika ditolak, kuota habis,
              model bermasalah, jaringan gagal, atau melewati 20 detik, coba
              koneksi aktif berikutnya. Maksimal lima koneksi, tanpa pengulangan
              ke koneksi yang sama.
            </p>
            <ol className="mt-4 space-y-3">
              {ai.connections.map((c, i) => (
                <li
                  key={c.id}
                  className="rounded-lg border border-[#dce4d2] p-4"
                >
                  <div className="flex items-start gap-3">
                    <span className="flex size-7 items-center justify-center rounded-full bg-[#eaf1e0] text-xs">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="break-words text-sm font-semibold">
                        {c.label}
                      </p>
                      <p className="mt-1 break-all text-xs text-[#687b5d]">
                        {providerNames[c.provider]} · {c.model}
                      </p>
                      <p className="mt-2 flex items-center gap-1 text-[11px] text-[#687b5d]">
                        <KeyRound size={12} />
                        Key tersedia di sesi · disembunyikan
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      aria-label={`Aktifkan koneksi ${c.label}`}
                      checked={c.enabled}
                      disabled={ai.busy}
                      onChange={(e) =>
                        ai.setConnections((old) =>
                          old.map((row) =>
                            row.id === c.id
                              ? { ...row, enabled: e.target.checked }
                              : row,
                          ),
                        )
                      }
                      className="size-5 accent-[#285e46]"
                    />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      aria-label={`Naikkan ${c.label}`}
                      disabled={ai.busy || i === 0}
                      onClick={() => move(i, -1)}
                      className={button}
                    >
                      <ArrowUp size={14} />
                    </button>
                    <button
                      aria-label={`Turunkan ${c.label}`}
                      disabled={ai.busy || i === ai.connections.length - 1}
                      onClick={() => move(i, 1)}
                      className={button}
                    >
                      <ArrowDown size={14} />
                    </button>
                    <button
                      disabled={ai.busy}
                      onClick={() => editConnection(c)}
                      className={button}
                    >
                      Edit {c.label}
                    </button>
                    <button
                      aria-label={`Hapus koneksi ${c.label}`}
                      disabled={ai.busy}
                      onClick={() => {
                        ai.setConnections((old) =>
                          old.filter((row) => row.id !== c.id),
                        );
                        if (editing === c.id) resetForm();
                      }}
                      className={`${button} ml-auto text-red-700`}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </li>
              ))}
            </ol>
            {!ai.connections.length && (
              <p className="my-6 rounded-lg border border-dashed border-[#ceddc1] p-5 text-center text-sm text-[#687b5d]">
                Belum ada koneksi. Tambahkan satu, lalu tambahkan cadangan bila
                perlu.
              </p>
            )}
            <button
              disabled={ai.busy || !ai.connections.length}
              onClick={() => {
                if (
                  window.confirm(
                    "Lupakan semua API key pada tab ini? Riwayat token tetap ada.",
                  )
                ) {
                  ai.forget();
                  resetForm();
                  setNotice(
                    "Semua koneksi dan key sesi telah dilupakan. AI nonaktif.",
                  );
                }
              }}
              className={`${button} mt-5 text-red-700`}
            >
              Lupakan semua key
            </button>
            <p className="mt-4 text-xs leading-6 text-[#687b5d]">
              Pindah penyedia berarti konteks yang sama dikirim ke penyedia
              cadangan. Percobaan yang timeout mungkin tetap ditagih oleh
              penyedia pertama. Periksa kebijakan data masing-masing penyedia.
            </p>
          </section>
        </div>
      )}
      {view === "assistant" && (
        <div className="grid items-start gap-5 xl:grid-cols-2">
          <section className={box}>
            <h2 className="text-base font-semibold">Apa yang ingin dibantu?</h2>
            <p className="mt-2 text-xs leading-6 text-[#64765a]">
              Proyek: <strong>{project.name}</strong>. Permintaan hanya dikirim
              setelah Anda menekan Buat dengan AI.
            </p>
            {!ai.enabled && (
              <p className="mt-4 rounded-lg bg-[#f2f5ec] p-4 text-sm leading-6">
                Anda sedang menggunakan mode tanpa AI. Templat, checklist, dan
                kalender tetap dapat digunakan. Aktifkan AI di atas bila ingin
                mencoba.
              </p>
            )}
            {!ai.connections.some((c) => c.enabled) && (
              <button
                className={`${button} mt-4`}
                onClick={() => setView("settings")}
              >
                Atur koneksi AI dahulu
                <ArrowUp size={14} />
              </button>
            )}
            <form
              className="mt-5 space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                setNotice("");
                void ai.generate(
                  {
                    business: project.name,
                    city: project.city,
                    domain: project.domain,
                    topic: topic.trim(),
                    notes,
                  },
                  task,
                );
              }}
            >
              <fieldset disabled={ai.busy} className="space-y-4">
                <label className="block text-xs font-semibold">
                  Jenis bantuan
                  <select
                    aria-label="Jenis bantuan AI"
                    value={task}
                    onChange={(e) => setTask(e.target.value as AiTask)}
                    className={field}
                  >
                    {Object.entries(taskNames).map(([id, name]) => (
                      <option key={id} value={id}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-xs font-semibold">
                  Topik / tujuan
                  <textarea
                    aria-label="Topik AI"
                    required
                    maxLength={500}
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Contoh: artikel tentang memilih roti ulang tahun di Bogor"
                    className={`${field} min-h-24`}
                  />
                </label>
                <label className="block text-xs font-semibold">
                  Catatan tambahan (opsional)
                  <textarea
                    aria-label="Catatan untuk AI"
                    value={notes}
                    maxLength={12000}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Sertakan fakta yang sudah Anda ketahui. Jangan masukkan API key atau data pribadi pelanggan."
                    className={`${field} min-h-32`}
                  />
                </label>
                {task === "recommendations" && (
                  <button
                    type="button"
                    disabled={!project.audit}
                    onClick={() =>
                      setNotes(
                        evaluateAudit(project.audit!)
                          .map(
                            (c) =>
                              `${c.pass ? "Lolos" : "Perlu diperiksa"}: ${c.name}. ${c.detail}`,
                          )
                          .join("\n"),
                      )
                    }
                    className={button}
                  >
                    Isi catatan dari audit tersimpan
                  </button>
                )}
                <label className="block text-xs font-semibold">
                  Batas token jawaban
                  <select
                    aria-label="Batas token jawaban"
                    value={ai.maxTokens}
                    onChange={(e) => ai.setMaxTokens(Number(e.target.value))}
                    className={field}
                  >
                    {[600, 1200, 2400, 4000].map((n) => (
                      <option key={n} value={n}>
                        {n.toLocaleString("id-ID")} token
                      </option>
                    ))}
                  </select>
                </label>
                <p className="text-xs leading-6 text-[#64765a]">
                  Batas ini berlaku per percobaan, bukan batas tagihan. Token
                  input tetap dihitung penyedia. Model tertentu mungkin tidak
                  menerima parameter standar ini.
                </p>
                <details className="rounded-lg bg-[#f4f7ef] p-3 text-xs text-[#566f49]">
                  <summary className="min-h-10 cursor-pointer py-2 font-semibold">
                    Data apa yang dikirim?
                  </summary>
                  <p className="leading-6">
                    Nama usaha: {project.name}; wilayah:{" "}
                    {project.city || "kosong"}; domain:{" "}
                    {project.domain || "kosong"}; topik dan catatan di atas.
                    Tidak mengirim seluruh proyek, daftar pelanggan, atau HTML
                    mentah secara otomatis. AI tidak merayapi situs.
                  </p>
                </details>
                <button
                  disabled={
                    !ai.enabled ||
                    !ai.connections.some((c) => c.enabled) ||
                    !topic.trim()
                  }
                  className={`${button} w-full bg-[#285e46] text-white hover:bg-[#1e4936]`}
                >
                  <Bot size={16} />
                  Buat dengan AI
                </button>
              </fieldset>
            </form>
            {ai.busy && (
              <div
                role="status"
                className="mt-4 rounded-lg bg-[#edf3e5] p-4 text-sm leading-6"
              >
                <p>
                  Sedang meminta jawaban. Koneksi cadangan dicoba hanya jika
                  koneksi sebelumnya gagal. Maksimal sekitar 100 detik untuk
                  lima koneksi.
                </p>
                <button onClick={ai.cancel} className={`${button} mt-3`}>
                  Batalkan permintaan
                </button>
              </div>
            )}
            {ai.error && (
              <p
                role="alert"
                className="mt-4 rounded-lg bg-amber-50 p-4 text-sm leading-6 text-amber-900"
              >
                {ai.error}
              </p>
            )}
          </section>
          <section className={box}>
            <h2 className="text-base font-semibold">Hasil & jalur koneksi</h2>
            {!ai.result && !ai.busy && (
              <div className="py-12 text-center text-sm leading-6 text-[#687b5d]">
                <Bot size={30} className="mx-auto mb-4" />
                Belum ada jawaban. Koneksi tidak diuji atau ditagih hanya karena
                Anda menambahkan API key.
              </div>
            )}
            {ai.result && (
              <>
                <p className="mt-2 text-xs text-[#687b5d]">
                  Hasil untuk {ai.result.projectName} ·{" "}
                  {taskNames[ai.result.task]}
                </p>
                <ol className="my-4 space-y-2">
                  {ai.result.attempts.map((a, i) => (
                    <li
                      key={`${a.connectionId}-${i}`}
                      className={`rounded-lg p-3 text-xs ${a.status === "success" ? "bg-[#eaf3e4]" : "bg-[#fff5e5]"}`}
                    >
                      <p className="font-semibold">
                        {i + 1}. {a.label} · {providerNames[a.provider]}{" "}
                        {i > 0 ? "· koneksi cadangan" : ""}
                      </p>
                      <p className="mt-1">
                        {aiErrorNames[a.code] ?? a.code} ·{" "}
                        {(a.durationMs / 1000).toFixed(1)} detik ·{" "}
                        {a.totalTokens === null
                          ? "token tidak dilaporkan"
                          : `${token(a.totalTokens)} token`}
                      </p>
                    </li>
                  ))}
                </ol>
                {ai.result.text && (
                  <>
                    <p className="mb-3 text-xs leading-6 text-[#64765a]">
                      Periksa fakta sebelum dipakai. Jawaban AI belum diterapkan
                      ke proyek dan tidak tersimpan setelah reload.
                    </p>
                    <pre className="max-h-[600px] overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-[#e0e6d6] bg-[#fafbf8] p-4 font-sans text-sm leading-7">
                      {ai.result.text}
                    </pre>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(
                              ai.result!.text!,
                            );
                            setNotice("Jawaban disalin.");
                          } catch {
                            setNotice(
                              "Browser menolak penyalinan. Gunakan unduh Markdown.",
                            );
                          }
                        }}
                        className={button}
                      >
                        <Copy size={15} />
                        Salin jawaban
                      </button>
                      <button
                        onClick={() =>
                          download(
                            "lokaseo-jawaban-ai.md",
                            `# ${taskNames[ai.result!.task]} — ${ai.result!.projectName}\n\n${ai.result!.text}`,
                            "text/markdown;charset=utf-8",
                          )
                        }
                        className={button}
                      >
                        <ArrowDownToLine size={15} />
                        Unduh jawaban
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
            {ai.uncertain && (
              <p className="mt-4 text-xs leading-6 text-amber-900">
                Permintaan terputus tidak masuk hitungan token terlapor.
                Dashboard ini bukan pengganti catatan penyedia.
              </p>
            )}
          </section>
        </div>
      )}
      {view === "usage" && (
        <>
          <section className={box}>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold">Penggunaan token AI</h2>
                <p className="mt-2 text-xs leading-6 text-[#64765a]">
                  Riwayat di browser ini, maksimal 1.000 percobaan terakhir.
                  Token bukan jumlah kata. Dashboard tidak menarik penggunaan
                  dari aplikasi lain atau akun penyedia.
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  disabled={!visible.length}
                  onClick={csv}
                  className={button}
                >
                  <ArrowDownToLine size={15} />
                  Ekspor token CSV
                </button>
                <button
                  disabled={ai.busy}
                  onClick={() => {
                    if (
                      window.confirm(
                        "Hapus riwayat token pada browser ini? Ini tidak menghapus tagihan di penyedia.",
                      )
                    )
                      ai.clearHistory();
                  }}
                  className={`${button} text-red-700`}
                >
                  <Trash2 size={15} />
                  Hapus riwayat
                </button>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-3">
              <select
                aria-label="Rentang penggunaan"
                value={range}
                onChange={(e) => setRange(e.target.value)}
                className={`${field} !mt-0 !w-auto`}
              >
                <option value="7">7 hari terakhir</option>
                <option value="30">30 hari terakhir</option>
                <option value="all">Semua riwayat</option>
              </select>
              <select
                aria-label="Filter penyedia AI"
                value={filterProvider}
                onChange={(e) => setFilterProvider(e.target.value)}
                className={`${field} !mt-0 !w-auto`}
              >
                <option value="all">Semua penyedia</option>
                {Object.entries(providerNames).map(([id, name]) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
              </select>
              <select
                aria-label="Filter status AI"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className={`${field} !mt-0 !w-auto`}
              >
                <option value="all">Semua status</option>
                <option value="success">Berhasil</option>
                <option value="failed">Gagal</option>
                <option value="cancelled">Dibatalkan</option>
              </select>
            </div>
            {ai.storageWarning && (
              <p role="alert" className="mt-4 text-sm text-amber-900">
                {ai.storageWarning}
              </p>
            )}
          </section>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              ["Token terlapor", totals.total],
              ["Token input terlapor", totals.input],
              ["Token output terlapor", totals.output],
              ["Percobaan tanpa total token", totals.unknown],
            ].map(([name, value]) => (
              <div key={name} className={box}>
                <p className="text-xs text-[#687b5d]">{name}</p>
                <p className="mt-3 text-3xl font-semibold">
                  {Number(value).toLocaleString("id-ID")}
                </p>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-4 rounded-lg bg-[#edf3e5] p-4 text-xs">
            <span>{totals.requests} permintaan</span>
            <span>{totals.attempts} percobaan</span>
            <span>{totals.success} berhasil</span>
            <span>{totals.failed} gagal</span>
            <span>{totals.fallback} percobaan cadangan</span>
          </div>
          <section className={box}>
            <h3 className="text-sm font-semibold">
              Menurut penyedia (sesuai filter)
            </h3>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {Object.entries(providerNames).map(([id, name]) => {
                const sum = summarizeUsage(
                  visible.filter((e) => e.provider === id),
                );
                return (
                  <div key={id} className="rounded-lg bg-[#f4f7ee] p-4">
                    <div className="flex justify-between text-xs">
                      <span>{name}</span>
                      <strong>
                        {sum.total.toLocaleString("id-ID")} token terlapor
                      </strong>
                    </div>
                    <div className="mt-3 h-2 rounded-full bg-[#dde7d2]">
                      <div
                        className="h-2 rounded-full bg-[#6a9154]"
                        style={{
                          width: `${totals.total ? (sum.total / totals.total) * 100 : 0}%`,
                        }}
                      />
                    </div>
                    <p className="mt-2 text-[11px] text-[#687b5d]">
                      {sum.attempts} percobaan · {sum.unknown} tanpa total token
                    </p>
                  </div>
                );
              })}
            </div>
            <p className="mt-4 text-xs leading-6 text-[#64765a]">
              Jumlah di atas hanya menjumlahkan angka yang benar-benar
              dilaporkan API. Percobaan gagal, timeout, atau pembatalan mungkin
              tetap dikenai biaya. Jika koneksi browser terputus, catatan
              percobaan tersebut bisa tidak diterima. Biaya rupiah tidak
              dihitung karena tarif berbeda menurut model dan penyedia.
            </p>
          </section>
          <section className={`${box} overflow-hidden`}>
            <h3 className="mb-4 text-sm font-semibold">Riwayat percobaan</h3>
            {!visible.length ? (
              <p className="py-8 text-center text-sm text-[#687b5d]">
                Belum ada riwayat yang cocok. Tidak ada angka contoh atau token
                perkiraan.
              </p>
            ) : (
              <div className="max-h-[500px] overflow-auto">
                <table className="w-full min-w-[720px] text-left text-xs">
                  <thead className="bg-[#f0f4e9]">
                    <tr>
                      {[
                        "Waktu",
                        "Koneksi / model",
                        "Status",
                        "Input",
                        "Output",
                        "Total",
                      ].map((h) => (
                        <th key={h} className="p-3">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((e) => (
                      <tr key={e.id} className="border-b border-[#e1e7d9]">
                        <td className="whitespace-nowrap p-3">
                          {new Date(e.startedAt).toLocaleString("id-ID")}
                          <span className="mt-1 block text-[10px] text-[#687b5d]">
                            {taskNames[e.task]}
                          </span>
                        </td>
                        <td className="max-w-56 break-words p-3">
                          {e.label}
                          <span className="mt-1 block text-[10px] text-[#687b5d]">
                            {providerNames[e.provider]} · {e.model}
                            {e.fallback ? " · cadangan" : ""}
                          </span>
                        </td>
                        <td className="p-3">
                          {aiErrorNames[e.code] ?? e.code}
                        </td>
                        <td className="p-3">{token(e.inputTokens)}</td>
                        <td className="p-3">{token(e.outputTokens)}</td>
                        <td className="p-3">{token(e.totalTokens)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
      <p className="flex items-start gap-2 text-xs leading-6 text-[#6b7e5f]">
        <CircleHelp size={16} className="mt-1" />
        Untuk pemakaian publik, lindungi server dengan autentikasi atau reverse
        proxy yang Anda kelola. Jangan memasukkan key ke instance milik orang
        yang tidak dipercaya. Koneksi AI tidak ikut cadangan proyek.
      </p>
    </div>
  );
}
