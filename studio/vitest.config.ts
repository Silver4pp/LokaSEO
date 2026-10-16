import { defineConfig } from "vitest/config";
export default defineConfig({
  test: {
    environment: "node",
    maxWorkers: 1,
    clearMocks: true,
    restoreMocks: true,
    include: [
      "src/client/features/lokaseo/model.test.ts",
      "src/server/features/loka-ai/service.test.ts",
      "studio/ai-middleware.test.ts",
      "studio/security.test.ts",
      "src/server/features/loka-ai/read-json.test.ts",
      "src/lib/lokaseo-policy.test.ts",
      "src/server/billing/lokaseo-billing.test.ts",
    ],
  },
});
