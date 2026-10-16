import { z } from "zod";
export const providerSchema = z.enum([
  "openai",
  "openrouter",
  "deepseek",
  "groq",
]);
export type AiProvider = z.infer<typeof providerSchema>;
export const providerNames: Record<AiProvider, string> = {
  openai: "OpenAI",
  openrouter: "OpenRouter",
  deepseek: "DeepSeek",
  groq: "Groq",
};
export const modelExamples: Record<AiProvider, string> = {
  openai: "gpt-4.1-mini",
  openrouter: "openai/gpt-4o-mini",
  deepseek: "deepseek-chat",
  groq: "llama-3.3-70b-versatile",
};
export const connectionSchema = z.object({
  id: z.string().min(1).max(80),
  label: z.string().trim().min(1).max(50),
  provider: providerSchema,
  model: z
    .string()
    .trim()
    .min(1)
    .max(150)
    .regex(/^[a-zA-Z0-9_./:@+-]+$/),
  apiKey: z
    .string()
    .trim()
    .min(4)
    .max(512)
    .regex(/^[\x21-\x7e]+$/),
  enabled: z.boolean(),
});
export type AiConnection = z.infer<typeof connectionSchema>;
export const taskSchema = z.enum(["ideas", "brief", "recommendations"]);
export type AiTask = z.infer<typeof taskSchema>;
export const taskNames: Record<AiTask, string> = {
  ideas: "Ide konten",
  brief: "Brief artikel",
  recommendations: "Saran perbaikan SEO",
};
export const aiRequestSchema = z.object({
  connections: z
    .array(connectionSchema)
    .min(1)
    .max(5)
    .refine(
      (rows) =>
        new Set(rows.map((r) => r.id)).size === rows.length &&
        rows.some((r) => r.enabled),
    ),
  task: taskSchema,
  context: z.object({
    business: z.string().trim().min(1).max(80),
    city: z.string().max(80),
    domain: z.string().max(250),
    topic: z.string().trim().min(1).max(500),
    notes: z.string().max(12000),
  }),
  maxTokens: z.number().int().min(128).max(4000),
});
export type AiRequest = z.infer<typeof aiRequestSchema>;
export const attemptSchema = z.object({
  connectionId: z.string().max(80),
  label: z.string().max(50),
  provider: providerSchema,
  model: z.string().max(150),
  status: z.enum(["success", "failed", "cancelled"]),
  code: z.string().max(50),
  startedAt: z.string().datetime(),
  durationMs: z.number().nonnegative(),
  inputTokens: z.number().int().nonnegative().nullable(),
  outputTokens: z.number().int().nonnegative().nullable(),
  totalTokens: z.number().int().nonnegative().nullable(),
});
export type AiAttempt = z.infer<typeof attemptSchema>;
export const aiResultSchema = z.object({
  text: z.string().max(100000).nullable(),
  attempts: z.array(attemptSchema).max(5),
  cancelled: z.boolean(),
});
export type AiResult = z.infer<typeof aiResultSchema>;
export const usageEventSchema = attemptSchema.extend({
  id: z.string(),
  requestId: z.string(),
  task: taskSchema,
  fallback: z.boolean(),
});
export type UsageEvent = z.infer<typeof usageEventSchema>;
export const usageHistorySchema = z.array(usageEventSchema).max(1000);
export const aiErrorNames: Record<string, string> = {
  ok: "Berhasil",
  truncated: "Batas token tercapai; jawaban terpotong",
  auth: "API key ditolak",
  quota: "Saldo atau kuota tidak cukup",
  rate_limit: "Batas permintaan tercapai",
  model: "Model atau parameter ditolak",
  timeout: "Batas waktu 20 detik",
  network: "Koneksi penyedia gagal",
  provider: "Gangguan penyedia",
  invalid_response: "Jawaban tidak dapat dibaca",
  empty: "Jawaban kosong",
  cancelled: "Dibatalkan",
  transport: "Koneksi ke server terputus",
};
export function summarizeUsage(rows: UsageEvent[]) {
  return {
    requests: new Set(rows.map((r) => r.requestId)).size,
    attempts: rows.length,
    success: rows.filter((r) => r.status === "success").length,
    failed: rows.filter((r) => r.status === "failed").length,
    fallback: rows.filter((r) => r.fallback).length,
    input: rows.reduce((n, r) => n + (r.inputTokens ?? 0), 0),
    output: rows.reduce((n, r) => n + (r.outputTokens ?? 0), 0),
    total: rows.reduce((n, r) => n + (r.totalTokens ?? 0), 0),
    unknown: rows.filter((r) => r.totalTokens === null).length,
  };
}
