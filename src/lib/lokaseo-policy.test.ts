import { expect, it } from "vitest";
import { getAuthMode, isHostedAuthMode } from "./auth-mode";
it("rejects hosted SaaS instead of silently weakening authentication", () => {
  expect(() => getAuthMode("hosted")).toThrow("LokaSEO");
});
it("preserves public Access authentication and trusted local mode", () => {
  expect(getAuthMode(undefined)).toBe("cloudflare_access");
  expect(getAuthMode("cloudflare_access")).toBe("cloudflare_access");
  expect(getAuthMode("local_noauth")).toBe("local_noauth");
  expect(isHostedAuthMode("cloudflare_access")).toBe(false);
});
