import { describe, expect, it, vi } from "vitest";
import { runAi } from "./service";
import {
  summarizeUsage,
  type AiRequest,
  type UsageEvent,
} from "../../../shared/loka-ai";
const request = (): AiRequest => ({
  connections: [
    {
      id: "a",
      label: "Utama",
      provider: "openai",
      model: "model-a",
      apiKey: "fake-key-a",
      enabled: true,
    },
    {
      id: "b",
      label: "Cadangan",
      provider: "groq",
      model: "model-b",
      apiKey: "fake-key-b",
      enabled: true,
    },
  ],
  task: "brief",
  context: {
    business: "Usaha",
    city: "Bogor",
    domain: "contoh.example",
    topic: "Roti",
    notes: "",
  },
  maxTokens: 600,
});
const success = (usage?: unknown) =>
  Response.json({
    choices: [
      { message: { content: "Jawaban uji, bukan panggilan provider nyata." } },
    ],
    ...(usage ? { usage } : {}),
  });
describe("AI sequential failover", () => {
  it("stops at the first success and records reported tokens", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        success({ prompt_tokens: 11, completion_tokens: 7, total_tokens: 18 }),
      );
    const result = await runAi(request(), { fetcher });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(result.attempts[0]).toMatchObject({
      status: "success",
      inputTokens: 11,
      outputTokens: 7,
      totalTokens: 18,
    });
  });
  it.each([
    [401, "auth"],
    [402, "quota"],
    [429, "rate_limit"],
    [503, "provider"],
    [400, "model"],
  ])(
    "fails over after HTTP %i without exposing provider error bodies",
    async (status, code) => {
      const fetcher = vi
        .fn<typeof fetch>()
        .mockResolvedValueOnce(
          new Response("fake-key-a sensitive provider response", {
            status: Number(status),
          }),
        )
        .mockResolvedValueOnce(success());
      const result = await runAi(request(), { fetcher });
      expect(result.attempts.map((a) => a.code)).toEqual([code, "ok"]);
      expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
        "https://api.openai.com/v1/chat/completions",
        "https://api.groq.com/openai/v1/chat/completions",
      ]);
      expect(JSON.stringify(result)).not.toContain("fake-key");
    },
  );
  it("does not turn unknown usage into zero", async () => {
    const result = await runAi(request(), {
      fetcher: vi.fn<typeof fetch>().mockResolvedValue(success()),
    });
    expect(result.attempts[0]).toMatchObject({
      inputTokens: null,
      outputTokens: null,
      totalTokens: null,
    });
  });
  it("times out one provider then attempts its backup", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockImplementationOnce(
        (_url, init) =>
          new Promise((_resolve, reject) =>
            init?.signal?.addEventListener("abort", () =>
              reject(new Error("timeout")),
            ),
          ),
      )
      .mockResolvedValueOnce(success());
    const result = await runAi(request(), { fetcher, timeoutMs: 5 });
    expect(result.attempts.map((a) => a.code)).toEqual(["timeout", "ok"]);
  });
  it("does not fail over after user cancellation", async () => {
    const controller = new AbortController();
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async () => {
      controller.abort();
      throw new Error("abort");
    });
    const result = await runAi(request(), {
      fetcher,
      signal: controller.signal,
    });
    expect(result.cancelled).toBe(true);
    expect(result.attempts[0].status).toBe("cancelled");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("skips disabled connections and refuses an all-disabled chain", async () => {
    const input = request();
    input.connections[0].enabled = false;
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(success());
    expect((await runAi(input, { fetcher })).attempts[0].connectionId).toBe(
      "b",
    );
    input.connections[1].enabled = false;
    await expect(runAi(input, { fetcher })).rejects.toThrow();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("returns every failed attempt rather than fabricating an AI answer", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockImplementation(async () => new Response("", { status: 503 }));
    const result = await runAi(request(), { fetcher });
    expect(result.text).toBeNull();
    expect(result.attempts).toHaveLength(2);
  });
  it("preserves tokens reported for an empty answer before fallback", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        Response.json({
          choices: [{ message: { content: "" } }],
          usage: { prompt_tokens: 4, completion_tokens: 0 },
        }),
      )
      .mockResolvedValueOnce(
        success({ prompt_tokens: 7, completion_tokens: 3 }),
      );
    const result = await runAi(request(), { fetcher });
    const rows: UsageEvent[] = result.attempts.map((a, i) => ({
      ...a,
      id: String(i),
      requestId: "one",
      task: "brief",
      fallback: i > 0,
    }));
    expect(result.attempts[0].code).toBe("empty");
    expect(summarizeUsage(rows)).toMatchObject({
      requests: 1,
      attempts: 2,
      total: 14,
      input: 11,
      output: 3,
      fallback: 1,
      failed: 1,
      success: 1,
      unknown: 0,
    });
  });
  it("rejects excessive chains before making any requests", async () => {
    const input = request();
    input.connections = Array.from({ length: 6 }, (_, i) => ({
      ...input.connections[0],
      id: String(i),
    }));
    const fetcher = vi.fn<typeof fetch>();
    await expect(runAi(input, { fetcher })).rejects.toThrow();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("uses only fixed endpoints and forbids redirecting authorization headers", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(success());
    const input = { ...request(), baseURL: "http://127.0.0.1/private" };
    await runAi(input, { fetcher });
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe("https://api.openai.com/v1/chat/completions");
    expect(init?.redirect).toBe("error");
    expect((init?.headers as Record<string, string>).Authorization).toBe(
      "Bearer fake-key-a",
    );
    expect(String(init?.body)).not.toContain("fake-key-a");
  });
});

it.each([
  ["openai", "https://api.openai.com/v1/chat/completions"],
  ["openrouter", "https://openrouter.ai/api/v1/chat/completions"],
  ["deepseek", "https://api.deepseek.com/chat/completions"],
  ["groq", "https://api.groq.com/openai/v1/chat/completions"],
] as const)("uses the compatible adapter for %s", async (provider, url) => {
  const input = request();
  input.connections = [{ ...input.connections[0], provider }];
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(success());
  await runAi(input, { fetcher });
  expect(fetcher.mock.calls[0][0]).toBe(url);
});
it("treats malformed provider JSON as failure and attempts the backup", async () => {
  const fetcher = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(new Response("not JSON"))
    .mockResolvedValueOnce(success());
  const result = await runAi(request(), { fetcher });
  expect(result.attempts.map((a) => a.code)).toEqual([
    "invalid_response",
    "ok",
  ]);
});

it("flags answers truncated by the token limit without charging a backup request", async () => {
  const fetcher = vi
    .fn<typeof fetch>()
    .mockResolvedValue(
      Response.json({
        choices: [
          {
            message: { content: "Kalimat yang belum" },
            finish_reason: "length",
          },
        ],
        usage: { prompt_tokens: 5, completion_tokens: 600, total_tokens: 605 },
      }),
    );
  const result = await runAi(request(), { fetcher });
  expect(result.attempts[0]).toMatchObject({
    status: "success",
    code: "truncated",
    totalTokens: 605,
  });
  expect(fetcher).toHaveBeenCalledTimes(1);
});
