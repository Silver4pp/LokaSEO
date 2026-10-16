import { useState } from "react";
import { ArrowRight, Check, CircleHelp, Leaf, Plus } from "lucide-react";
import {
  beginnerHelp,
  beginnerProgress,
  contentIdeas,
  glossary,
} from "./beginner";
import type { Project } from "./model";
const button =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold hover:bg-[#e5eddd] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";

export function BeginnerStart({
  project,
  onCreate,
  onGo,
  onBackup,
}: {
  project: Project;
  onCreate: () => void;
  onGo: (page: string) => void;
  onBackup: () => void;
}) {
  const done = beginnerProgress(project);
  const count = done.filter(Boolean).length;
  const next = done.indexOf(false);
  const titles = [
    "Masukkan nama usaha Anda",
    "Periksa satu informasi bisnis",
    "Jadwalkan tulisan pertama",
  ];
  const notes = [
    "Cukup nama usaha. Alamat situs bisa diisi nanti.",
    "Misalnya, pastikan nomor telepon pelanggan sudah benar.",
    "Pilih satu pertanyaan pelanggan sebagai topik.",
  ];
  const actions = [onCreate, () => onGo("local"), () => onGo("calendar")];
  return (
    <section
      aria-label="Langkah awal pemula"
      className="mb-6 rounded-2xl border border-[#d2dfc5] bg-[#edf3e5] p-5 md:p-7"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="mb-2 flex items-center gap-2 text-xs font-semibold text-[#4e7040]">
            <Leaf size={16} />
            MULAI DI SINI
          </p>
          <h2 className="text-2xl font-semibold tracking-tight">
            {count === 3
              ? "Langkah pertama Anda sudah selesai."
              : "Tidak perlu mengerti SEO untuk mulai."}
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#53664b]">
            {project.id === "contoh"
              ? "Yang Anda lihat sekarang adalah data latihan, bukan hasil situs Anda. Buat proyek sendiri saat sudah siap."
              : count === 3
                ? "Ini baru langkah awal, bukan tanda seluruh SEO sudah selesai. Cadangkan data Anda, lalu lanjutkan checklist saat ada waktu."
                : "Kerjakan satu langkah setiap kali. Audit kode dan istilah teknis bisa dipelajari nanti."}
          </p>
        </div>
        <span className="rounded-full bg-white px-3 py-2 text-xs font-semibold">
          {count} dari 3 langkah awal
        </span>
      </div>
      <ol className="my-5 grid gap-3 md:grid-cols-3">
        {titles.map((title, i) => (
          <li
            key={title}
            className={`rounded-xl border p-4 ${i === next ? "border-[#94ad7d] bg-white" : "border-[#d8e2ce] bg-white/50"}`}
          >
            <div className="mb-3 flex items-center gap-2">
              <span
                className={`flex size-7 items-center justify-center rounded-full text-xs ${done[i] ? "bg-[#285e46] text-white" : "bg-[#e3ecd9] text-[#426334]"}`}
              >
                {done[i] ? <Check size={15} /> : i + 1}
              </span>
              <span className="text-xs text-[#65775c]">
                {done[i]
                  ? "Sudah dilakukan"
                  : i === next
                    ? "Langkah berikutnya"
                    : "Setelahnya"}
              </span>
            </div>
            <h3 className="text-sm font-semibold">{title}</h3>
            <p className="mt-2 text-xs leading-5 text-[#65775c]">{notes[i]}</p>
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={next === -1 ? onBackup : actions[next]}
          className={`${button} bg-[#285e46] text-white hover:bg-[#1e4936]`}
        >
          {next === -1
            ? "Simpan cadangan pertama"
            : [
                "Mulai dengan usaha saya",
                "Cek informasi bisnis",
                "Rencanakan tulisan pertama",
              ][next]}
          <ArrowRight size={16} />
        </button>
        <span className="text-xs text-[#617557]">
          Tanpa kartu pembayaran · boleh mulai tanpa situs
        </span>
      </div>
    </section>
  );
}
export function PageHelp({ page }: { page: string }) {
  const help = beginnerHelp[page];
  if (!help) return null;
  return (
    <aside className="mb-5 rounded-xl border border-[#dbe4d2] bg-[#f0f5e9] p-5">
      <div className="flex items-start gap-3">
        <CircleHelp size={19} className="mt-0.5 text-[#62814d]" />
        <div>
          <h2 className="text-sm font-semibold">{help.title}</h2>
          <p className="mt-2 text-sm leading-6 text-[#576b4d]">{help.text}</p>
          <details className="mt-3">
            <summary className="min-h-10 cursor-pointer py-2 text-xs font-semibold text-[#385e2a]">
              Tunjukkan langkahnya
            </summary>
            <ol className="ml-4 list-decimal space-y-2 text-sm leading-6 text-[#576b4d]">
              {help.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </details>
        </div>
      </div>
    </aside>
  );
}
export function IdeaStarter({
  city,
  onPlan,
}: {
  city: string;
  onPlan: (title: string, keyword: string) => void;
}) {
  const [topic, setTopic] = useState("");
  const ideas = contentIdeas(topic, city);
  return (
    <section
      aria-label="Bantuan ide tulisan"
      className="mb-5 rounded-xl border border-[#dce3d2] bg-white p-5"
    >
      <h2 className="text-sm font-semibold">Belum tahu mau menulis apa?</h2>
      <p className="mt-2 text-sm leading-6 text-[#617557]">
        Tulis produk atau layanan Anda. Kami siapkan kerangka judul sederhana,
        bukan hasil riset Google.
      </p>
      <label htmlFor="idea-topic" className="mt-4 block text-xs font-semibold">
        Produk atau layanan
        <input
          id="idea-topic"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          maxLength={80}
          placeholder="Misalnya: roti ulang tahun"
          className="mt-2 block min-h-11 w-full rounded-lg border border-[#cedbc4] px-3 text-sm outline-emerald-700"
        />
      </label>
      {ideas.length > 0 && (
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {ideas.map((idea) => (
            <div
              key={idea.title}
              className="flex flex-col rounded-lg bg-[#f5f8ef] p-4"
            >
              <p className="flex-1 text-sm leading-6">{idea.title}</p>
              <button
                onClick={() => onPlan(idea.title, idea.keyword)}
                className={`${button} mt-3 justify-start px-0 text-xs text-[#3e6931]`}
              >
                <Plus size={15} />
                Jadwalkan ide ini
              </button>
            </div>
          ))}
        </div>
      )}
      <p className="mt-3 text-xs text-[#6c7c62]">
        Judul, kata kunci, dan tanggal tetap bisa Anda ubah sebelum menyimpan.
      </p>
    </section>
  );
}
export function SeoGlossary() {
  return (
    <section>
      <h3 className="mb-3 text-base font-semibold text-[#283c31]">
        Kamus singkat SEO
      </h3>
      <div className="divide-y divide-[#dce3d2]">
        {glossary.map(([term, meaning]) => (
          <details key={term} className="py-2">
            <summary className="min-h-10 cursor-pointer py-2 text-sm font-semibold text-[#385e2a]">
              {term}
            </summary>
            <p className="pb-2 text-sm leading-6 text-[#586d4e]">{meaning}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
