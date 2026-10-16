import { defineConfig } from "vitest/config";
import tsConfigPaths from "vite-tsconfig-paths";
export default defineConfig({
  plugins: [tsConfigPaths()],
  test: {
    environment: "node",
    maxWorkers: 1,
    clearMocks: true,
    restoreMocks: true,
    include: [
      "src/server/lib/audit/url-policy.test.ts",
      "src/server/lib/audit/url-utils.test.ts",
      "src/middleware/ensure-user/accessTokenErrors.test.ts",
      "src/server/mcp/public-origin.test.ts",
    ],
  },
});
