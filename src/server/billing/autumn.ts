import type { Autumn } from "autumn-js";

// Fail closed: no Autumn client or billing network requests exist in this fork.
function loadAutumn(): Promise<Autumn> {
  return Promise.reject(new Error("Monetisasi dinonaktifkan pada LokaSEO."));
}

/** Shape-preserving lazy facade over the SDK client: call sites keep the
 *  plain `autumn.check(...)` form. Covers only the methods we use — add a
 *  line here when adopting a new one. */
export const autumn = {
  check: (...args: Parameters<Autumn["check"]>) =>
    loadAutumn().then((client) => client.check(...args)),
  track: (...args: Parameters<Autumn["track"]>) =>
    loadAutumn().then((client) => client.track(...args)),
  customers: {
    getOrCreate: (...args: Parameters<Autumn["customers"]["getOrCreate"]>) =>
      loadAutumn().then((client) => client.customers.getOrCreate(...args)),
    get: (...args: Parameters<Autumn["customers"]["get"]>) =>
      loadAutumn().then((client) => client.customers.get(...args)),
  },
  balances: {
    // Confirms or releases a hold taken by `check({ lock })`. Not in the
    // SDK's fail-open set, so a lost deduction surfaces as an error.
    finalize: (...args: Parameters<Autumn["balances"]["finalize"]>) =>
      loadAutumn().then((client) => client.balances.finalize(...args)),
  },
  billing: {
    attach: (...args: Parameters<Autumn["billing"]["attach"]>) =>
      loadAutumn().then((client) => client.billing.attach(...args)),
    openCustomerPortal: (
      ...args: Parameters<Autumn["billing"]["openCustomerPortal"]>
    ) =>
      loadAutumn().then((client) => client.billing.openCustomerPortal(...args)),
  },
};

// track() has no idempotency key, so replaying a deduction Autumn already
// processed (5xx after a successful write, dropped connection) would
// double-charge. Retry only 429s, which are rejected before processing.
// Lock checks and balances.finalize() use the same options: a replayed lock
// check surfaces 409 lock_already_exists, and a replayed finalize surfaces
// "Lock not found", on the caller's first attempt, where neither can be told
// apart from a real failure. None sets a per-call timeoutMs, so all get the
// client-wide 10s; finalize does not fail open, so a shorter deadline would
// drop deductions that Autumn completes in 5-10s.
export const AUTUMN_TRACK_RETRY_OPTIONS: Parameters<Autumn["track"]>[1] = {
  retryCodes: ["429"],
  retries: {
    strategy: "backoff",
    backoff: {
      initialInterval: 250,
      maxInterval: 2000,
      exponent: 1.5,
      maxElapsedTime: 8000,
    },
    retryConnectionErrors: false,
  },
};
