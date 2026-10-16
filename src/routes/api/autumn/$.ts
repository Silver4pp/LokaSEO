import { createFileRoute } from "@tanstack/react-router";
const disabled = () =>
  new Response("Monetisasi dinonaktifkan.", { status: 410 });
export const Route = createFileRoute("/api/autumn/$")({
  server: { handlers: { GET: disabled, POST: disabled } },
});
