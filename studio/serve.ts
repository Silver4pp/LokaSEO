// Standalone build server. Key/session endpoints never expose source or development tooling.
import { createServer } from "node:http";
import { resolve } from "node:path";
import { aiMiddleware } from "./ai-middleware";
import { allowedHost, securityHeaders } from "./http-security";
import { serveStatic } from "./static-handler";
const root = resolve("loka-release");
const port = Number(process.env.PORT ?? 3000);
if (process.env.LOKA_PUBLIC_ORIGIN) {
  const origin = new URL(process.env.LOKA_PUBLIC_ORIGIN);
  if (
    origin.protocol !== "https:" ||
    origin.origin !== process.env.LOKA_PUBLIC_ORIGIN
  )
    throw Error("LOKA_PUBLIC_ORIGIN harus berupa origin HTTPS tanpa path.");
}
const server = createServer((req, res) => {
  securityHeaders(res);
  if (!allowedHost(req.headers.host)) {
    res.writeHead(421);
    res.end("Host tidak diizinkan.");
    return;
  }
  void aiMiddleware(req, res, () => {
    void serveStatic(req, res, root);
  });
});
server.requestTimeout = 15000;
server.headersTimeout = 10000;
server.maxRequestsPerSocket = 100;
server.listen(port, "0.0.0.0", () =>
  console.log(
    `LokaSEO production listening on port ${port}. Protect public access with your reverse proxy.`,
  ),
);
