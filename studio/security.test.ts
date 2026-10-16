import { afterAll, beforeAll, afterEach, expect, it, vi } from "vitest";
import { createServer, request as httpRequest, type Server } from "node:http";
import { mkdtemp, mkdir, writeFile, symlink, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createAiMiddleware } from "./ai-middleware";
import { serveStatic } from "./static-handler";
import { allowedHost, securityHeaders } from "./http-security";
import { runAi } from "../src/server/features/loka-ai/service";
vi.mock("../src/server/features/loka-ai/service", () => ({ runAi: vi.fn() }));
let folder: string;
let root: string;
beforeAll(async () => {
  folder = await mkdtemp(join(tmpdir(), "loka-security-"));
  root = join(folder, "public");
  await mkdir(root);
  await writeFile(join(root, "index.html"), "<h1>Safe</h1>");
  await writeFile(join(folder, "sentinel.css"), "OUTSIDE_BUILD");
  await symlink(join(folder, "sentinel.css"), join(root, "leak.css"));
});
afterAll(async () => {
  await rm(folder, { recursive: true, force: true });
});
afterEach(() => vi.unstubAllEnvs());
async function listen(server: Server) {
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const address = server.address();
  if (!address || typeof address === "string") throw Error("address");
  return `http://127.0.0.1:${address.port}`;
}
async function close(server: Server) {
  server.closeAllConnections();
  await new Promise<void>((r) => server.close(() => r()));
}
function staticServer() {
  return createServer((req, res) => {
    securityHeaders(res);
    if (!allowedHost(req.headers.host)) {
      res.writeHead(421);
      res.end();
      return;
    }
    void serveStatic(req, res, root);
  });
}
it("blocks encoded traversal and symbolic links outside the build folder", async () => {
  const server = staticServer();
  const base = await listen(server);
  try {
    expect((await fetch(base + "/")).status).toBe(200);
    for (const path of [
      "/leak.css",
      "/%2e%2e%2fsentinel.css",
      "/.env",
      "/not-found.map",
    ]) {
      const response = await fetch(base + path);
      expect(response.status).toBe(404);
      expect(await response.text()).not.toContain("OUTSIDE_BUILD");
    }
  } finally {
    await close(server);
  }
});
it("serves restrictive CSP with self-only framing outside the preview environment", async () => {
  vi.stubEnv("E2B_SANDBOX_ID", "");
  const server = staticServer();
  const base = await listen(server);
  try {
    const response = await fetch(base);
    const csp = response.headers.get("content-security-policy");
    expect(csp).toContain("script-src 'self'");
    expect(csp).toContain("frame-ancestors 'self'");
    expect(csp).toContain("object-src 'none'");
    expect(response.headers.get("referrer-policy")).toBe("no-referrer");
  } finally {
    await close(server);
  }
});
it("rejects unknown hosts instead of trusting matching Host and Origin supplied by a caller", async () => {
  const handler = createAiMiddleware();
  const server = createServer(
    (req, res) => void handler(req, res, () => res.end()),
  );
  const base = await listen(server);
  try {
    const status = await new Promise<number | undefined>((resolve, reject) => {
      const req = httpRequest(
        base + "/api/loka-ai/generate",
        {
          method: "POST",
          headers: {
            Host: "rebinding.example",
            Origin: "http://rebinding.example",
            "Content-Type": "application/json",
          },
        },
        (res) => {
          res.resume();
          res.on("end", () => resolve(res.statusCode));
        },
      );
      req.on("error", reject);
      req.end("{}");
    });
    expect(status).toBe(403);
    expect(runAi).not.toHaveBeenCalled();
  } finally {
    await close(server);
  }
});
it("incomplete uploads do not consume the eight AI-generation slots", async () => {
  const handler = createAiMiddleware({
    bodyTimeoutMs: 1000,
    requestsPerMinute: 100,
  });
  let received = 0;
  let ready!: () => void;
  const barrier = new Promise<void>((r) => (ready = r));
  const server = createServer((req, res) => {
    void handler(req, res, () => res.end());
    if (++received === 8) ready();
  });
  const base = await listen(server);
  const held = Array.from({ length: 8 }, () => {
    const req = httpRequest(base + "/api/loka-ai/generate", {
      method: "POST",
      headers: { Origin: base, "Content-Type": "application/json" },
    });
    req.on("error", () => {});
    req.write("{");
    return req;
  });
  try {
    await barrier;
    const response = await fetch(base + "/api/loka-ai/generate", {
      method: "POST",
      headers: { Origin: base, "Content-Type": "application/json" },
      body: "{}",
    });
    expect(response.status).toBe(400);
    expect(runAi).not.toHaveBeenCalled();
  } finally {
    held.forEach((r) => r.destroy());
    await close(server);
  }
});
it("expires a slow upload with HTTP 408 and no AI call", async () => {
  const handler = createAiMiddleware({ bodyTimeoutMs: 30 });
  const server = createServer(
    (req, res) => void handler(req, res, () => res.end()),
  );
  const base = await listen(server);
  try {
    const status = await new Promise<number | undefined>((resolve, reject) => {
      const req = httpRequest(
        base + "/api/loka-ai/generate",
        {
          method: "POST",
          headers: { Origin: base, "Content-Type": "application/json" },
        },
        (res) => {
          res.resume();
          res.on("end", () => resolve(res.statusCode));
        },
      );
      req.on("error", reject);
      req.write("{");
    });
    expect(status).toBe(408);
    expect(runAi).not.toHaveBeenCalled();
  } finally {
    await close(server);
  }
});
it("rate-limits before contacting any provider and does not trust forwarded IP headers", async () => {
  const handler = createAiMiddleware({ requestsPerMinute: 2 });
  const server = createServer(
    (req, res) => void handler(req, res, () => res.end()),
  );
  const base = await listen(server);
  try {
    const statuses = [];
    for (let i = 0; i < 3; i++) {
      statuses.push(
        (
          await fetch(base + "/api/loka-ai/generate", {
            method: "POST",
            headers: {
              Origin: base,
              "Content-Type": "application/json",
              "X-Forwarded-For": `192.0.2.${i}`,
            },
            body: "{}",
          })
        ).status,
      );
    }
    expect(statuses).toEqual([400, 400, 429]);
    expect(runAi).not.toHaveBeenCalled();
  } finally {
    await close(server);
  }
});
