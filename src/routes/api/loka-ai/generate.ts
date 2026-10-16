import { createFileRoute } from "@tanstack/react-router";
import { resolveUserContextFromHeaders } from "@/middleware/ensure-user/resolve";
import { aiRequestSchema } from "@/shared/loka-ai";
import { runAi } from "@/server/features/loka-ai/service";
import {
  readRequestJson,
  RequestBodyError,
} from "@/server/features/loka-ai/read-json";
let running = 0,
  readers = 0;
const json = (value: unknown, status = 200) =>
  Response.json(value, { status, headers: { "Cache-Control": "no-store" } });
async function generate(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin)
    return json({ error: "Origin tidak diizinkan." }, 403);
  if (!request.headers.get("content-type")?.startsWith("application/json"))
    return json({ error: "Gunakan JSON." }, 415);
  try {
    await resolveUserContextFromHeaders(request.headers);
  } catch {
    return json({ error: "Autentikasi diperlukan." }, 401);
  }
  if (readers >= 32) return json({ error: "Server sibuk." }, 429);
  let raw: unknown;
  readers++;
  try {
    raw = await readRequestJson(request);
  } catch (error) {
    return json(
      { error: "Body permintaan tidak valid atau terlalu lambat." },
      error instanceof RequestBodyError ? error.status : 400,
    );
  } finally {
    readers--;
  }
  const input = aiRequestSchema.safeParse(raw);
  if (!input.success) return json({ error: "Permintaan tidak valid." }, 400);
  if (running >= 8) return json({ error: "Server sibuk." }, 429);
  running++;
  try {
    return json(await runAi(input.data, { signal: request.signal }));
  } catch {
    return json(
      {
        error:
          "Permintaan AI tidak dapat diselesaikan; penggunaan token mungkin tidak diketahui.",
      },
      500,
    );
  } finally {
    running--;
  }
}
export const Route = createFileRoute("/api/loka-ai/generate")({
  server: { handlers: { POST: ({ request }) => generate(request) } },
});
