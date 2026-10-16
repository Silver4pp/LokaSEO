import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";
import { aiRequestSchema } from "../src/shared/loka-ai";
import { runAi } from "../src/server/features/loka-ai/service";
import { allowedOrigin, BodyError, readBody } from "./http-security";
function reply(res: ServerResponse, status: number, value: unknown) {
  if (res.destroyed || res.writableEnded) return;
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  });
  res.end(JSON.stringify(value));
}
/** Bound both slow uploads and provider work; upload slots never consume provider slots. */
export function createAiMiddleware(
  options: { bodyTimeoutMs?: number; requestsPerMinute?: number } = {},
) {
  let running = 0,
    readers = 0;
  const rate = new Map<string, { count: number; until: number }>();
  return async function handle(
    req: IncomingMessage,
    res: ServerResponse,
    next: () => void,
  ) {
    if (req.url?.split("?")[0] !== "/api/loka-ai/generate") return next();
    if (req.method !== "POST")
      return reply(res, 405, { error: "Gunakan POST untuk permintaan AI." });
    if (!allowedOrigin(req))
      return reply(res, 403, { error: "Origin atau host tidak diizinkan." });
    if (
      req.headers["content-type"]?.split(";")[0].trim().toLowerCase() !==
      "application/json"
    )
      return reply(res, 415, { error: "Gunakan application/json." });
    const now = Date.now();
    for (const [key, value] of rate) if (value.until <= now) rate.delete(key);
    // Ignore X-Forwarded-For supplied by clients; shared reverse proxies should rate-limit at ingress too.
    const ip = req.socket.remoteAddress ?? "unknown";
    const bucket = rate.get(ip) ?? { count: 0, until: now + 60000 };
    if (
      bucket.count >= (options.requestsPerMinute ?? 30) ||
      (!rate.has(ip) && rate.size >= 1000) ||
      readers >= 32
    )
      return reply(res, 429, {
        error: "Terlalu banyak permintaan. Coba lagi dalam satu menit.",
      });
    bucket.count++;
    rate.set(ip, bucket);
    readers++;
    let raw: unknown;
    try {
      raw = JSON.parse(
        (await readBody(req, 65536, options.bodyTimeoutMs)).toString("utf8"),
      );
    } catch (error) {
      const status = error instanceof BodyError ? error.status : 400;
      if (error instanceof BodyError) {
        res.setHeader("Connection", "close");
        res.once("finish", () => req.destroy());
      }
      reply(res, status, {
        error:
          status === 408
            ? "Unggahan terlalu lambat. Coba lagi."
            : status === 413
              ? "Permintaan terlalu besar."
              : "Format permintaan tidak valid.",
      });
      return;
    } finally {
      readers--;
    }
    const parsed = aiRequestSchema.safeParse(raw);
    if (!parsed.success)
      return reply(res, 400, {
        error:
          "Periksa koneksi AI, model, dan topik. Jangan masukkan API key ke kolom selain API key.",
      });
    if (running >= 8)
      return reply(res, 429, {
        error: "Server sedang sibuk. Coba lagi sebentar.",
      });
    const controller = new AbortController();
    const close = () => {
      if (!res.writableEnded) controller.abort();
    };
    res.on("close", close);
    if (res.destroyed) return;
    running++;
    try {
      reply(res, 200, await runAi(parsed.data, { signal: controller.signal }));
    } catch {
      reply(res, 500, {
        error:
          "Permintaan AI tidak dapat diselesaikan. Penggunaan token mungkin tidak diketahui.",
      });
    } finally {
      running--;
      res.off("close", close);
    }
  };
}
export const aiMiddleware = createAiMiddleware();
export function lokaAiPlugin(): Plugin {
  return {
    name: "lokaseo-ai-proxy",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        void aiMiddleware(req, res, next);
      });
    },
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        void aiMiddleware(req, res, next);
      });
    },
  };
}
