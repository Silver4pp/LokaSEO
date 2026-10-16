import { expect, it, vi } from "vitest";
import { autumn } from "./autumn";
it("rejects checkout and usage without making a network request", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  await expect(
    autumn.billing.attach({ customerId: "local", planId: "test" }),
  ).rejects.toThrow("Monetisasi dinonaktifkan");
  await expect(
    autumn.check({ customerId: "local", featureId: "test" }),
  ).rejects.toThrow("Monetisasi dinonaktifkan");
  expect(fetchSpy).not.toHaveBeenCalled();
});
