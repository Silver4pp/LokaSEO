// Local browser regressions. All AI responses are mocked; no actual keys/provider calls.
import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { request } from "node:http";
import { writeFile, symlink, unlink, mkdir } from "node:fs/promises";
await mkdir("test-results/security", { recursive: true });
const base = "http://127.0.0.1:3000";
const report = {};
report.hostStatus = await new Promise((resolve, reject) => {
  const req = request(
    base + "/api/loka-ai/generate",
    {
      method: "POST",
      headers: {
        Host: "untrusted.example:3000",
        Origin: "http://untrusted.example:3000",
        "Content-Type": "application/json",
      },
    },
    (res) => {
      res.resume();
      res.on("end", () => resolve(res.statusCode));
    },
  );
  req.on("error", reject);
  req.end("{}");
});
assert.equal(report.hostStatus, 421);
await writeFile("test-results/security/sentinel.css", "HARMLESS_OUTSIDE_BUILD");
try {
  await symlink(
    "../test-results/security/sentinel.css",
    "loka-release/probe.css",
  );
  const response = await fetch(base + "/probe.css");
  report.symlinkStatus = response.status;
  assert.equal(response.status, 404);
  assert.ok(!(await response.text()).includes("HARMLESS_OUTSIDE_BUILD"));
} finally {
  await unlink("loka-release/probe.css").catch(() => {});
  await unlink("test-results/security/sentinel.css");
}
const response = await fetch(base);
assert.ok(
  response.headers.get("content-security-policy").includes("script-src 'self'"),
);
const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox"],
});
try {
  const context = await browser.newContext();
  const errors = [];
  context.on("page", (p) => p.on("pageerror", (e) => errors.push(e.message)));
  const a = await context.newPage();
  await a.goto(base);
  await a.waitForFunction(() => localStorage.getItem("lokaseo.workspace.v1"));
  const b = await context.newPage();
  await b.goto(base);
  await b
    .getByRole("heading", { name: "Langkah kecil, jangkauan lebih luas." })
    .waitFor();
  const click = (p, name) =>
    p.getByRole("button", { name, exact: true }).first().click();
  await click(a, "Pengaturan proyek");
  await a
    .getByLabel("Nama proyek", { exact: true })
    .fill("Perubahan aman dari tab A");
  await click(a, "Simpan proyek");
  await a.waitForFunction(
    () =>
      JSON.parse(localStorage.getItem("lokaseo.workspace.v1")).projects[0]
        .name === "Perubahan aman dari tab A",
  );
  await b.getByText(/Data di tab lain berubah/).waitFor();
  await click(b, "SEO lokal");
  await b.getByRole("checkbox").last().check();
  assert.equal(
    await a.evaluate(
      () =>
        JSON.parse(localStorage.getItem("lokaseo.workspace.v1")).projects[0]
          .name,
    ),
    "Perubahan aman dari tab A",
  );
  report.crossTab = "rename retained; stale tab warns and cannot overwrite";
  await click(a, "Audit halaman");
  for (const [meta, expected] of [
    ['<meta name="robots" content="none">', true],
    ['<meta name="robots" content="index">', false],
    [
      '<meta name="robots" content="index"><meta name="robots" content="noindex">',
      true,
    ],
  ]) {
    await a
      .getByLabel("Kode sumber halaman")
      .fill(
        `<html lang="id"><head><title>Robots regression test</title>${meta}</head><body><h1>Test</h1></body></html>`,
      );
    await click(a, "Periksa HTML");
    await a.waitForFunction(
      (expected) =>
        JSON.parse(localStorage.getItem("lokaseo.workspace.v1")).projects[0]
          .audit.noindex === expected,
      expected,
    );
  }
  report.robots =
    "none and duplicate noindex detected; index alone stays indexable";
  const network = [];
  await a.route("https://audit-beacon.invalid/**", async (route) => {
    network.push(route.request().url());
    await route.abort();
  });
  await a
    .getByLabel("Kode sumber halaman")
    .fill(
      '<html><head><title>Hostile HTML test</title></head><body><script>window.__auditExecuted=1</script><img src="https://audit-beacon.invalid/image" onerror="window.__auditExecuted=1"><iframe src="https://audit-beacon.invalid/frame"></iframe><h1>Test</h1></body></html>',
    );
  await click(a, "Periksa HTML");
  await a.waitForFunction(
    () =>
      JSON.parse(localStorage.getItem("lokaseo.workspace.v1")).projects[0].audit
        .title === "Hostile HTML test",
  );
  assert.equal(await a.evaluate(() => Boolean(window.__auditExecuted)), false);
  assert.equal(network.length, 0);
  report.htmlInjection = "no execution or outbound request in tested Chromium";
  await b.reload();
  await b
    .getByRole("heading", { name: "Langkah kecil, jangkauan lebih luas." })
    .waitFor();
  assert.equal(await b.getByText(/Data di tab lain berubah/).count(), 0);
  let mode = "success",
    calls = 0;
  const pending = [];
  let release;
  const barrier = new Promise((r) => (release = r));
  await context.route("**/api/loka-ai/generate", async (route) => {
    calls++;
    const input = route.request().postDataJSON();
    if (mode === "500") {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: "{}",
      });
      return;
    }
    pending.push(input);
    if (pending.length === 2) release();
    await barrier;
    const connection = input.connections[0];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        text: '<img src=x onerror="window.__aiExecuted=1"> Jawaban aman sebagai teks.',
        attempts: [
          {
            connectionId: connection.id,
            label: connection.label,
            provider: connection.provider,
            model: connection.model,
            status: "success",
            code: "ok",
            startedAt: new Date().toISOString(),
            durationMs: 20,
            inputTokens: 80,
            outputTokens: 40,
            totalTokens: 120,
          },
        ],
        cancelled: false,
      }),
    });
  });
  async function setup(p, label) {
    await click(p, "AI & token");
    await click(p, "Koneksi & cadangan");
    await p.getByLabel("Nama koneksi", { exact: true }).fill(label);
    await p.getByLabel("Model AI", { exact: true }).fill("mock-model");
    await p
      .getByLabel("API key", { exact: true })
      .fill("fake-security-key-" + label.replaceAll(" ", "-"));
    await click(p, "Tambah koneksi");
    await p.getByLabel("Aktifkan AI", { exact: true }).check();
    await click(p, "Asisten");
    await p
      .getByLabel("Topik AI", { exact: true })
      .fill("Topik privat " + label);
  }
  await setup(a, "Tab A");
  await setup(b, "Tab B");
  assert.equal(calls, 0);
  await Promise.all([click(a, "Buat dengan AI"), click(b, "Buat dengan AI")]);
  await a.waitForFunction(
    () =>
      JSON.parse(localStorage.getItem("lokaseo.ai-usage.v1") ?? "[]").length ===
      2,
  );
  const history = await a.evaluate(() =>
    JSON.parse(localStorage.getItem("lokaseo.ai-usage.v1")),
  );
  assert.deepEqual(
    new Set(history.map((x) => x.label)),
    new Set(["Tab A", "Tab B"]),
  );
  assert.equal(
    history.reduce((s, x) => s + x.totalTokens, 0),
    240,
  );
  for (const p of [a, b]) {
    await p
      .getByText(
        '<img src=x onerror="window.__aiExecuted=1"> Jawaban aman sebagai teks.',
        { exact: true },
      )
      .waitFor();
    assert.equal(await p.evaluate(() => Boolean(window.__aiExecuted)), false);
    const stored = await p.evaluate(() =>
      JSON.stringify({ ...localStorage, ...sessionStorage }),
    );
    assert.ok(!stored.includes("fake-security-key-"));
    assert.ok(!stored.includes("Topik privat"));
  }
  report.tokenConcurrency =
    "both simultaneous requests retained: 2 attempts, 240 mock tokens";
  report.keyStorage =
    "fake keys and prompts absent from localStorage/sessionStorage";
  mode = "500";
  await click(a, "Buat dengan AI");
  await a
    .getByText(/Permintaan terputus tidak masuk hitungan token terlapor/i)
    .waitFor();
  report.serverFailure =
    "HTTP 500 displays usage uncertainty rather than claiming zero tokens";
  assert.deepEqual(errors, []);
  report.browserErrors = errors;
} finally {
  await browser.close();
}
await writeFile(
  "test-results/security/regression-browser.json",
  JSON.stringify(report, null, 2),
);
console.log(JSON.stringify(report, null, 2));
