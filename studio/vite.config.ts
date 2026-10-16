import { lokaAiPlugin } from "./ai-middleware";
import { defineConfig } from "vite";
import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";
export default defineConfig({
  root: "studio",
  // Ikon disalin ke studio/public agar build mandiri dan paket desktop punya favicon.
  publicDir: resolve("studio/public"),
  plugins: [react(), tailwind(), lokaAiPlugin()],
  server: { host: "0.0.0.0", port: 3000, allowedHosts: [".e2b.app"] },
  build: { outDir: "../loka-release", emptyOutDir: true },
});
