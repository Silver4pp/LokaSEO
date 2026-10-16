import { expect, it } from "vitest";
import { readRequestJson } from "./read-json";
function request(body: ReadableStream<Uint8Array>) {
  return new Request("https://example.test", {
    method: "POST",
    body,
    duplex: "half",
  } as RequestInit);
}
it("rejects a streaming upload that never completes within the absolute deadline", async () => {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("{"));
    },
  });
  await expect(readRequestJson(request(body), 20)).rejects.toMatchObject({
    status: 408,
  });
});
it("enforces byte limits even if content-length is absent", async () => {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new Uint8Array(65537));
      controller.close();
    },
  });
  await expect(readRequestJson(request(body))).rejects.toMatchObject({
    status: 413,
  });
});
it("parses valid UTF-8 JSON and rejects invalid JSON", async () => {
  await expect(
    readRequestJson(
      new Request("https://example.test", {
        method: "POST",
        body: '{"name":"Usaha"}',
      }),
    ),
  ).resolves.toEqual({ name: "Usaha" });
  await expect(
    readRequestJson(
      new Request("https://example.test", { method: "POST", body: "invalid" }),
    ),
  ).rejects.toMatchObject({ status: 400 });
});
