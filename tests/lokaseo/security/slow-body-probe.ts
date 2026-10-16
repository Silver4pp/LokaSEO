import { createServer, request } from "node:http";
import { aiMiddleware } from "../../../studio/ai-middleware";
let received = 0;
let ready!: () => void;
const all = new Promise<void>((r) => (ready = r));
const server = createServer((req, res) => {
  received++;
  void aiMiddleware(req, res, () => res.end());
  if (received === 8) ready();
});
await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
const addr = server.address();
if (!addr || typeof addr === "string") throw Error("address");
const base = `http://127.0.0.1:${addr.port}`;
const held = Array.from({ length: 8 }, () => {
  const req = request(base + "/api/loka-ai/generate", {
    method: "POST",
    headers: {
      Origin: base,
      "Content-Type": "application/json",
      "Transfer-Encoding": "chunked",
    },
  });
  req.on("error", () => {});
  req.write("{");
  return req;
});
await all;
const res = await fetch(base + "/api/loka-ai/generate", {
  method: "POST",
  headers: { Origin: base, "Content-Type": "application/json" },
  body: "{}",
});
console.log(
  JSON.stringify({
    incompleteBodies: 8,
    ninthResponse: res.status,
    expectedAfterHardening: 400,
  }),
);
held.forEach((req) => req.destroy());
server.closeAllConnections();
await new Promise<void>((r) => server.close(() => r()));
