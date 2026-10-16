export class RequestBodyError extends Error {
  constructor(public status: number) {
    super("Body permintaan tidak valid.");
  }
}
/** Absolute read deadline, independent of platform timeouts or bytes sent by a slow client. */
export async function readRequestJson(
  request: Request,
  timeoutMs = 5000,
): Promise<unknown> {
  if (!request.body) throw new RequestBodyError(400);
  const reader = request.body.getReader();
  let size = 0;
  const chunks: Uint8Array[] = [];
  let timer: ReturnType<typeof setTimeout>;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new RequestBodyError(408)), timeoutMs);
  });
  try {
    for (;;) {
      const { value, done } = await Promise.race([reader.read(), deadline]);
      if (done) break;
      size += value.length;
      if (size > 65536) throw new RequestBodyError(413);
      chunks.push(value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.length;
    }
    try {
      return JSON.parse(new TextDecoder().decode(bytes));
    } catch {
      throw new RequestBodyError(400);
    }
  } finally {
    clearTimeout(timer!);
    void reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
