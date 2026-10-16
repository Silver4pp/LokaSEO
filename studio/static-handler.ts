import type { IncomingMessage, ServerResponse } from "node:http";
import { readFile, realpath, stat } from "node:fs/promises";
import { resolve, extname, sep } from "node:path";
const mime: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
};
export async function serveStatic(
  req: IncomingMessage,
  res: ServerResponse,
  root: string,
) {
  if (req.method !== "GET" && req.method !== "HEAD") {
    res.writeHead(405);
    res.end();
    return;
  }
  try {
    const pathname = decodeURIComponent(
      new URL(req.url ?? "/", "http://internal").pathname,
    );
    const file = resolve(
      root,
      "." + (pathname === "/" ? "/index.html" : pathname),
    );
    if (
      !file.startsWith(resolve(root) + sep) ||
      pathname.split("/").some((p) => p.startsWith(".")) ||
      !mime[extname(file)]
    )
      throw Error("not found");
    const actualRoot = await realpath(root),
      actualFile = await realpath(file);
    if (!actualFile.startsWith(actualRoot + sep)) throw Error("not found");
    const info = await stat(actualFile);
    if (!info.isFile() || info.size > 8_000_000) throw Error("not found");
    const contents = await readFile(actualFile);
    res.writeHead(200, {
      "Content-Type": mime[extname(file)],
      "Cache-Control": pathname.startsWith("/assets/")
        ? "public, max-age=31536000, immutable"
        : "no-store",
    });
    res.end(req.method === "HEAD" ? undefined : contents);
  } catch {
    if (!res.headersSent) {
      res.writeHead(404);
      res.end("Tidak ditemukan. Jalankan build:loka terlebih dahulu.");
    } else res.end();
  }
}
