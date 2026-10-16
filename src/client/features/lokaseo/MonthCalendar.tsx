import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { localDateKey, monthDays, type Article } from "./model";

export function MonthCalendar({
  month,
  onMonth,
  articles,
  onEdit,
  onAdd,
}: {
  month: string;
  onMonth: (month: string) => void;
  articles: Article[];
  onEdit: (article: Article) => void;
  onAdd: (date: string) => void;
}) {
  const [year, index] = month.split("-").map(Number);
  const title = new Date(year, index - 1, 1, 12).toLocaleDateString("id-ID", {
    month: "long",
    year: "numeric",
  });
  const today = localDateKey(new Date());
  const days = monthDays(month);
  const items = articles.filter((a) => a.date.startsWith(month));
  const button =
    "inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-[#dce3d2] px-3 text-xs hover:bg-[#edf2e5] focus-visible:outline-2 focus-visible:outline-emerald-700 disabled:opacity-40";
  function move(delta: number) {
    onMonth(localDateKey(new Date(year, index - 1 + delta, 1, 12)).slice(0, 7));
  }
  return (
    <div className="border-t border-[#e4e8dc] p-3 sm:p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="mt-1 text-xs text-[#65745d]">
            {items.length} rencana sesuai filter · klik konten untuk mengedit
          </p>
        </div>
        <div className="flex max-w-full flex-wrap items-center gap-2">
          <button
            className={button}
            aria-label="Bulan sebelumnya"
            disabled={month === "1900-01"}
            onClick={() => move(-1)}
          >
            <ChevronLeft size={16} />
          </button>
          <button className={button} onClick={() => onMonth(today.slice(0, 7))}>
            Bulan ini
          </button>
          <button
            className={button}
            aria-label="Bulan berikutnya"
            disabled={month === "2100-12"}
            onClick={() => move(1)}
          >
            <ChevronRight size={16} />
          </button>
          <label className="sr-only" htmlFor="calendar-month">
            Pilih bulan
          </label>
          <input
            id="calendar-month"
            type="month"
            min="1900-01"
            max="2100-12"
            value={month}
            onChange={(e) => {
              if (
                /^(19\d{2}|20\d{2}|2100)-(0[1-9]|1[0-2])$/.test(e.target.value)
              )
                onMonth(e.target.value);
            }}
            className="min-h-11 min-w-0 max-w-40 rounded-lg border border-[#dce3d2] bg-white px-2 text-xs"
          />
        </div>
      </div>
      <div className="hidden sm:block">
        <div className="grid grid-cols-7 text-center text-[11px] font-semibold text-[#6d7e61]">
          {["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"].map((d) => (
            <div key={d} className="py-3">
              {d}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 overflow-hidden rounded-lg border-l border-t border-[#e0e6d7]">
          {days.map((day, i) => (
            <div
              key={day ?? `pad-${i}`}
              className={`min-h-32 min-w-0 border-b border-r border-[#e0e6d7] p-2 ${!day ? "bg-[#f5f7f0]" : day === today ? "bg-[#edf4e5]" : "bg-white"}`}
            >
              {day && (
                <>
                  <div className="flex items-center justify-between">
                    <span
                      className={`flex size-7 items-center justify-center rounded-full text-xs ${day === today ? "bg-[#285e46] text-white" : ""}`}
                    >
                      {Number(day.slice(-2))}
                    </span>
                    <button
                      className="flex size-10 items-center justify-center rounded-lg text-[#708562] hover:bg-[#e5eddc]"
                      aria-label={`Tambah konten ${day}`}
                      onClick={() => onAdd(day)}
                    >
                      <Plus size={13} />
                    </button>
                  </div>
                  <div className="space-y-1">
                    {items
                      .filter((a) => a.date === day)
                      .map((a) => (
                        <button
                          title={a.title}
                          key={a.id}
                          onClick={() => onEdit(a)}
                          className={`w-full rounded-md border-l-2 px-2 py-2 text-left text-[11px] leading-4 ${a.status === "Terbit" ? "border-[#458562] bg-[#e6f1e8]" : a.status === "Ditulis" ? "border-[#ae8b45] bg-[#f7f0df]" : "border-[#93a58b] bg-[#f0f3eb]"}`}
                        >
                          <span className="line-clamp-2 break-words">
                            {a.title}
                          </span>
                          <span className="mt-1 block text-[10px] text-[#62745a]">
                            {a.status}
                          </span>
                        </button>
                      ))}
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="space-y-3 sm:hidden" aria-label="Agenda bulanan seluler">
        {[...new Set(items.map((a) => a.date))].sort().map((day) => (
          <section
            key={day}
            className="rounded-lg border border-[#e1e6d9] bg-white p-3"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold">
                {new Date(day + "T12:00:00").toLocaleDateString("id-ID", {
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                })}
              </h3>
              <button
                className={button}
                aria-label={`Tambah konten ${day}`}
                onClick={() => onAdd(day)}
              >
                <Plus size={14} />
              </button>
            </div>
            {items
              .filter((a) => a.date === day)
              .map((a) => (
                <button
                  key={a.id}
                  className="mt-2 block min-h-11 w-full rounded-md bg-[#f2f5ec] p-3 text-left text-xs"
                  onClick={() => onEdit(a)}
                >
                  {a.title}
                  <span className="mt-1 block text-[10px] text-[#69795e]">
                    {a.status}
                  </span>
                </button>
              ))}
          </section>
        ))}
      </div>
      {!items.length && (
        <p className="py-8 text-center text-sm text-[#65745d]">
          Tidak ada konten yang cocok di bulan ini. Tambahkan rencana atau ubah
          bulan dan filter.
        </p>
      )}
      <div className="mt-5 flex flex-wrap items-center gap-3 text-[11px] text-[#69795e]">
        <span>Ide · Ditulis · Terbit</span>
        <button
          className={`${button} ml-auto`}
          onClick={() =>
            onAdd(month === today.slice(0, 7) ? today : month + "-01")
          }
        >
          <Plus size={14} className="mr-1" />
          Tambah di bulan ini
        </button>
      </div>
    </div>
  );
}
