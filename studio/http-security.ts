import type { IncomingMessage, ServerResponse } from "node:http";

/** Only known hosts may serve the app/API; Host/Origin matching alone is not a rebinding defense. */
export function allowedHost(host: string | undefined) {
  if (!host || /[\s/@?#\\]/.test(host)) return false;
  let url: URL;
  try {
    url = new URL(`http://${host}`);
  } catch {
    return false;
  }
  if (url.host !== host.toLowerCase()) return false;
  if (["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) return true;
  const publicOrigin = process.env.LOKA_PUBLIC_ORIGIN;
  if (publicOrigin) {
    try {
      const configured = new URL(publicOrigin);
      if (configured.protocol === "https:" && configured.host === url.host)
        return true;
    } catch {
      /* fail closed */
    }
  }
  const sandbox = process.env.E2B_SANDBOX_ID;
  return Boolean(
    sandbox && url.host === `${process.env.PORT ?? "3000"}-${sandbox}.e2b.app`,
  );
}
export function allowedOrigin(req: IncomingMessage) {
  if (!allowedHost(req.headers.host)) return false;
  try {
    const url = new URL(req.headers.origin ?? "");
    if (url.origin !== req.headers.origin || url.host !== req.headers.host)
      return false;
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    return (
      (url.protocol === "https:" || (local && url.protocol === "http:")) &&
      (!req.headers["sec-fetch-site"] ||
        ["same-origin", "none"].includes(String(req.headers["sec-fetch-site"])))
    );
  } catch {
    return false;
  }
}
export class BodyError extends Error {
  constructor(public status: number) {
    super("Invalid request body");
  }
}
export function readBody(
  req: IncomingMessage,
  maxBytes = 65536,
  timeoutMs = 5000,
): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let size = 0;
    let finished = false;
    const cleanup = () => {
      clearTimeout(timer);
      req.off("data", data);
      req.off("end", end);
      req.off("error", error);
      req.off("aborted", aborted);
    };
    const fail = (status: number) => {
      if (finished) return;
      finished = true;
      cleanup();
      req.pause();
      reject(new BodyError(status));
    };
    const data = (part: Buffer) => {
      size += part.length;
      if (size > maxBytes) return fail(413);
      chunks.push(part);
    };
    const end = () => {
      if (finished) return;
      finished = true;
      cleanup();
      resolve(Buffer.concat(chunks));
    };
    const error = () => fail(400);
    const aborted = () => fail(400);
    const timer = setTimeout(() => fail(408), timeoutMs);
    req.on("data", data);
    req.once("end", end);
    req.once("error", error);
    req.once("aborted", aborted);
  });
}
export function securityHeaders(res: ServerResponse) {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("Referrer-Policy", "no-referrer");
  res.setHeader(
    "Permissions-Policy",
    "camera=(), microphone=(), geolocation=()",
  );
  // Arena embeds previews cross-origin. Production defaults to self-only framing.
  const ancestors =
    process.env.LOKA_FRAME_ANCESTORS ??
    (process.env.E2B_SANDBOX_ID ? "" : "'self'");
  res.setHeader(
    "Content-Security-Policy",
    `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-src 'none'${ancestors ? `; frame-ancestors ${ancestors}` : ""}`,
  );
}
