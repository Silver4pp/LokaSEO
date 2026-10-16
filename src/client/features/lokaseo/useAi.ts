import { useEffect, useRef, useState } from "react";
import {
  aiResultSchema,
  usageHistorySchema,
  type AiConnection,
  type AiRequest,
  type AiResult,
  type UsageEvent,
} from "../../../shared/loka-ai";
import { withStorageLock } from "./storage-lock";
const USAGE_KEY = "lokaseo.ai-usage.v1";
export function useAi() {
  // API keys and generated text live only in React memory. Never persist these states.
  const [enabled, setEnabled] = useState(false);
  const [connections, setConnections] = useState<AiConnection[]>([]);
  const [events, setEvents] = useState<UsageEvent[]>([]);
  const [storageWarning, setStorageWarning] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const [result, setResult] = useState<
    (AiResult & { projectName: string; task: AiRequest["task"] }) | null
  >(null);
  const active = useRef<AbortController | null>(null);
  const [maxTokens, setMaxTokens] = useState(1200);
  useEffect(() => {
    try {
      const raw = localStorage.getItem(USAGE_KEY);
      if (raw) setEvents(usageHistorySchema.parse(JSON.parse(raw)));
    } catch {
      setStorageWarning(
        "Riwayat token tidak dapat dibaca. Data lama tidak ditimpa; hapus riwayat untuk memulai ulang.",
      );
    }
    return () => active.current?.abort();
  }, []);
  useEffect(() => {
    const changed = (event: StorageEvent) => {
      if (event.key !== USAGE_KEY && event.key !== null) return;
      try {
        setEvents(
          usageHistorySchema.parse(
            JSON.parse(localStorage.getItem(USAGE_KEY) ?? "[]"),
          ),
        );
      } catch {
        setStorageWarning(
          "Riwayat token di tab lain tidak valid. Ekspor catatan tab ini sebelum menghapus riwayat.",
        );
      }
    };
    window.addEventListener("storage", changed);
    return () => window.removeEventListener("storage", changed);
  }, []);
  function cancel() {
    active.current?.abort();
  }
  function forget() {
    cancel();
    setEnabled(false);
    setConnections([]);
    setResult(null);
    setError("");
  }
  async function generate(
    context: AiRequest["context"],
    task: AiRequest["task"],
  ) {
    if (active.current) return;
    if (!enabled) {
      setError("AI sedang nonaktif. Fitur manual tetap bisa digunakan.");
      return;
    }
    const enabledConnections = connections.filter((c) => c.enabled);
    if (!enabledConnections.length) {
      setError("Tambahkan dan aktifkan setidaknya satu koneksi AI.");
      return;
    }
    const controller = new AbortController();
    active.current = controller;
    setBusy(true);
    setError("");
    setUncertain(false);
    setResult(null);
    const requestId = crypto.randomUUID();
    // Last-resort transport deadline includes five sequential 20s provider deadlines.
    const timer = setTimeout(() => controller.abort(), 115_000);
    try {
      const response = await fetch("/api/loka-ai/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        signal: controller.signal,
        body: JSON.stringify({
          connections: enabledConnections,
          context,
          task,
          maxTokens,
        }),
      });
      if (!response.ok) {
        if (response.status >= 500) setUncertain(true);
        setError(
          response.status === 404
            ? "Server AI belum tersedia. Jalankan aplikasi dengan server LokaSEO, bukan hanya membuka build statis."
            : response.status === 429
              ? "Server sedang sibuk. Coba lagi nanti."
              : response.status === 400
                ? "Permintaan ditolak. Periksa model, panjang konteks, dan koneksi Anda."
                : "Server AI tidak dapat memproses permintaan. Periksa koneksi atau konfigurasi server.",
        );
        return;
      }
      const parsed = aiResultSchema.safeParse(await response.json());
      if (!parsed.success) throw new Error("transport");
      const data = parsed.data;
      setResult({ ...data, projectName: context.business, task });
      const additions = data.attempts.map((attempt, i) => ({
        ...attempt,
        id: crypto.randomUUID(),
        requestId,
        task,
        fallback: i > 0,
      }));
      try {
        const merged = await withStorageLock(USAGE_KEY, () => {
          const saved = usageHistorySchema.parse(
            JSON.parse(localStorage.getItem(USAGE_KEY) ?? "[]"),
          );
          const next = [...additions, ...saved].slice(0, 1000);
          localStorage.setItem(USAGE_KEY, JSON.stringify(next));
          return next;
        });
        setEvents(merged);
      } catch {
        setEvents((previous) => [...additions, ...previous].slice(0, 1000));
        setStorageWarning(
          "Riwayat token belum tersimpan. Penyimpanan diblokir, rusak, penuh, atau browser tidak mendukung Web Locks. Ekspor CSV sebelum menutup tab.",
        );
      }
      if (!data.text)
        setError(
          data.cancelled
            ? "Permintaan dibatalkan. Tidak ada keluaran yang diterapkan."
            : "Semua koneksi yang aktif gagal. Lihat rinciannya di bawah; fitur tanpa AI tetap tersedia.",
        );
    } catch {
      setUncertain(true);
      setError(
        controller.signal.aborted
          ? "Permintaan dihentikan. Penyedia mungkin sudah memprosesnya. Token percobaan ini tidak dapat dipastikan; tidak ada perpindahan koneksi baru yang diminta oleh browser."
          : "Koneksi ke server terputus atau respons tidak valid. Penggunaan token permintaan ini tidak diketahui. Periksa dashboard penyedia sebelum mencoba ulang.",
      );
    } finally {
      clearTimeout(timer);
      active.current = null;
      setBusy(false);
    }
  }
  async function clearHistory() {
    try {
      await withStorageLock(USAGE_KEY, () =>
        localStorage.setItem(USAGE_KEY, "[]"),
      );
      setEvents([]);
      setStorageWarning("");
    } catch {
      setStorageWarning(
        "Riwayat belum dapat dihapus dari browser. Coba lagi setelah penyimpanan tersedia.",
      );
    }
  }
  return {
    enabled,
    setEnabled,
    connections,
    setConnections,
    events,
    storageWarning,
    busy,
    error,
    uncertain,
    result,
    maxTokens,
    setMaxTokens,
    generate,
    cancel,
    forget,
    clearHistory,
  };
}
export type AiController = ReturnType<typeof useAi>;
