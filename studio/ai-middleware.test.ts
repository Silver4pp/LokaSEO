import { afterAll, beforeAll, beforeEach, expect, it, vi } from "vitest";
import { createServer, type Server } from "node:http";
import { aiMiddleware } from "./ai-middleware";
import { runAi } from "../src/server/features/loka-ai/service";
vi.mock("../src/server/features/loka-ai/service", () => ({ runAi: vi.fn() }));
let server: Server;
let origin = "";
beforeEach(() => {
  vi.mocked(runAi).mockResolvedValue({
    text: "Test",
    attempts: [],
    cancelled: false,
  });
});
beforeAll(async () => {
  server = createServer(
    (req, res) =>
      void aiMiddleware(req, res, () => {
        res.writeHead(404);
        res.end();
      }),
  );
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("address");
  origin = `http://127.0.0.1:${address.port}`;
});
afterAll(async () => {
  server.closeAllConnections();
  await new Promise<void>((resolve) => server.close(() => resolve()));
});
const input = {
  connections: [
    {
      id: "a",
      label: "Test",
      provider: "openai",
      model: "test",
      apiKey: "fake-key",
      enabled: true,
    },
  ],
  task: "ideas",
  context: { business: "Test", city: "", domain: "", topic: "Roti", notes: "" },
  maxTokens: 600,
};
it("rejects cross-origin calls before touching a provider", async () => {
  const res = await fetch(origin + "/api/loka-ai/generate", {
    method: "POST",
    headers: {
      Origin: "https://evil.example",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });
  expect(res.status).toBe(403);
  expect(runAi).not.toHaveBeenCalled();
});
it("rejects invalid bodies without returning keys or schema internals", async () => {
  const res = await fetch(origin + "/api/loka-ai/generate", {
    method: "POST",
    headers: { Origin: origin, "Content-Type": "application/json" },
    body: JSON.stringify({ ...input, task: "invalid" }),
  });
  expect(res.status).toBe(400);
  expect(await res.text()).not.toContain("fake-key");
  expect(runAi).not.toHaveBeenCalled();
});
it("returns no-store results for a valid same-origin request", async () => {
  const res = await fetch(origin + "/api/loka-ai/generate", {
    method: "POST",
    headers: { Origin: origin, "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  expect(res.status).toBe(200);
  expect(res.headers.get("cache-control")).toBe("no-store");
  expect((await res.json()).text).toBe("Test");
  expect(runAi).toHaveBeenCalledOnce();
});
it("rejects oversize bodies before calling AI", async () => {
  const res = await fetch(origin + "/api/loka-ai/generate", {
    method: "POST",
    headers: { Origin: origin, "Content-Type": "application/json" },
    body: JSON.stringify({ ...input, extra: "x".repeat(70000) }),
  });
  expect(res.status).toBe(413);
  expect(runAi).not.toHaveBeenCalled();
});
