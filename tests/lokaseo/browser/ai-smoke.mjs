import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { readFile, mkdir } from "node:fs/promises";
await mkdir("test-results", { recursive: true });
const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox"],
});
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let calls = 0;
  let mode = "fallback";
  const requestBodies = [];
  await page.route("**/api/loka-ai/generate", async (route) => {
    calls++;
    const input = route.request().postDataJSON();
    requestBodies.push(input);
    const attempts = input.connections.map((c, i) => ({
      connectionId: c.id,
      label: c.label,
      provider: c.provider,
      model: c.model,
      status: i === 1 ? "success" : "failed",
      code: i === 1 ? "ok" : "auth",
      startedAt: new Date().toISOString(),
      durationMs: 25,
      inputTokens: i === 1 ? 80 : null,
      outputTokens: i === 1 ? 40 : null,
      totalTokens: i === 1 ? 120 : null,
    }));
    let text = "Jawaban simulasi pengujian. Bukan keluaran penyedia nyata.";
    if (mode === "unknown") {
      attempts.splice(1);
      Object.assign(attempts[0], {
        status: "success",
        code: "ok",
        inputTokens: null,
        outputTokens: null,
        totalTokens: null,
      });
    }
    if (mode === "all-failed") {
      text = null;
      for (const a of attempts)
        Object.assign(a, {
          status: "failed",
          code: "rate_limit",
          inputTokens: null,
          outputTokens: null,
          totalTokens: null,
        });
    }
    if (mode === "slow") {
      await new Promise((r) => setTimeout(r, 2000));
    }
    await route
      .fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ text, attempts, cancelled: false }),
      })
      .catch(() => {});
  });
  const click = (name) =>
    page.getByRole("button", { name, exact: true }).first().click();
  await page.goto("http://127.0.0.1:3000");
  await click("AI & token");
  assert.equal(
    await page.getByLabel("Aktifkan AI", { exact: true }).isChecked(),
    false,
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Buat dengan AI", exact: true })
      .isDisabled(),
    true,
  );
  await click("Koneksi & cadangan");
  async function add(label, provider, key) {
    await page.getByLabel("Nama koneksi", { exact: true }).fill(label);
    await page
      .getByLabel("Penyedia AI", { exact: true })
      .selectOption(provider);
    await page.getByLabel("Model AI", { exact: true }).fill("model-test");
    await page.getByLabel("API key", { exact: true }).fill(key);
    await click("Tambah koneksi");
  }
  await add("Utama uji", "openai", "fake-key-private-a");
  await add("Cadangan uji", "groq", "fake-key-private-b");
  assert.equal(calls, 0);
  await click("Edit Utama uji");
  await page
    .getByLabel("Penyedia AI", { exact: true })
    .selectOption("deepseek");
  await click("Simpan koneksi");
  await page
    .getByRole("alert")
    .filter({ hasText: "Lengkapi API key" })
    .waitFor();
  await click("Batal edit");
  await click("Turunkan Utama uji");
  await click("Naikkan Utama uji");
  await page
    .getByLabel("Aktifkan koneksi Cadangan uji", { exact: true })
    .uncheck();
  await page
    .getByLabel("Aktifkan koneksi Cadangan uji", { exact: true })
    .check();
  await page.getByLabel("Aktifkan AI", { exact: true }).check();
  assert.equal(calls, 0);
  await click("Asisten");
  await page
    .getByLabel("Jenis bantuan AI", { exact: true })
    .selectOption("brief");
  await page
    .getByLabel("Topik AI", { exact: true })
    .fill("Topik unik privat pengujian 89123");
  await page
    .getByLabel("Batas token jawaban", { exact: true })
    .selectOption("600");
  await click("Buat dengan AI");
  await page
    .getByText("Jawaban simulasi pengujian. Bukan keluaran penyedia nyata.", {
      exact: true,
    })
    .waitFor();
  assert.equal(calls, 1);
  assert.deepEqual(
    requestBodies[0].connections.map((c) => c.label),
    ["Utama uji", "Cadangan uji"],
  );
  assert.equal(requestBodies[0].maxTokens, 600);
  assert.equal(requestBodies[0].connections[0].apiKey, "fake-key-private-a");
  const storage = () =>
    page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }));
  assert.equal((await storage()).includes("fake-key-private"), false);
  assert.equal((await storage()).includes("89123"), false);
  await click("Penggunaan token");
  await page.getByText("1 permintaan", { exact: true }).waitFor();
  await page.getByText("2 percobaan", { exact: true }).waitFor();
  await page.getByText("1 percobaan cadangan", { exact: true }).waitFor();
  let history = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("lokaseo.ai-usage.v1")),
  );
  assert.equal(history.length, 2);
  assert.equal(history[0].totalTokens, null);
  assert.equal(history[1].totalTokens, 120);
  const [csv] = await Promise.all([
    page.waitForEvent("download"),
    click("Ekspor token CSV"),
  ]);
  const csvText = await readFile(await csv.path(), "utf8");
  assert.ok(csvText.includes("Tidak dilaporkan"));
  assert.ok(csvText.includes("120"));
  assert.equal(csvText.includes("fake-key-private"), false);
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({
    path: "test-results/lokaseo-ai-token-test.png",
    fullPage: true,
  });
  await page
    .getByLabel("Filter penyedia AI", { exact: true })
    .selectOption("groq");
  assert.equal(await page.locator("tbody tr").count(), 1);
  await page
    .getByLabel("Filter penyedia AI", { exact: true })
    .selectOption("all");
  mode = "unknown";
  await click("Asisten");
  await click("Buat dengan AI");
  await page
    .getByText("Jawaban simulasi pengujian. Bukan keluaran penyedia nyata.", {
      exact: true,
    })
    .waitFor();
  await click("Penggunaan token");
  await page.getByText("2 permintaan", { exact: true }).waitFor();
  history = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("lokaseo.ai-usage.v1")),
  );
  assert.equal(history.filter((a) => a.totalTokens === null).length, 2);
  assert.equal(
    history.reduce((n, a) => n + (a.totalTokens ?? 0), 0),
    120,
  );
  mode = "all-failed";
  await click("Asisten");
  await click("Buat dengan AI");
  await page
    .getByRole("alert")
    .filter({ hasText: "Semua koneksi yang aktif gagal" })
    .waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Unduh jawaban", exact: true })
      .count(),
    0,
  );
  mode = "slow";
  await click("Buat dengan AI");
  await click("Batalkan permintaan");
  await page
    .getByRole("alert")
    .filter({ hasText: "Permintaan dihentikan" })
    .waitFor();
  await page.getByLabel("Aktifkan AI", { exact: true }).uncheck();
  assert.equal(
    await page
      .getByRole("button", { name: "Buat dengan AI", exact: true })
      .isDisabled(),
    true,
  );
  await click("Laporan");
  const [backup] = await Promise.all([
    page.waitForEvent("download"),
    click("Unduh cadangan .json"),
  ]);
  assert.equal(
    (await readFile(await backup.path(), "utf8")).includes("fake-key-private"),
    false,
  );
  await page.reload();
  await click("AI & token");
  assert.equal(
    await page.getByLabel("Aktifkan AI", { exact: true }).isChecked(),
    false,
  );
  await click("Koneksi & cadangan");
  assert.equal(
    await page
      .getByRole("button", { name: "Edit Utama uji", exact: true })
      .count(),
    0,
  );
  await page
    .getByText(
      "Belum ada koneksi. Tambahkan satu, lalu tambahkan cadangan bila perlu.",
      { exact: true },
    )
    .waitFor();
  await click("Penggunaan token");
  await page.getByText("3 permintaan", { exact: true }).waitFor();
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const tab of ["Asisten", "Koneksi & cadangan", "Penggunaan token"]) {
      await click(tab);
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
        `${width} ${tab} overflow`,
      );
    }
  }
  const nilaiStabil = async (locator, cocok, pesan) => {
    let nilai = "";
    for (let i = 0; i < 50; i += 1) {
      nilai = await locator.inputValue();
      if (cocok(nilai)) return nilai;
      await page.waitForTimeout(100);
    }
    assert.fail(`${pesan} (nilai terakhir: "${nilai}")`);
  };
  page.once("dialog", (d) => d.accept());
  await click("Hapus riwayat");
  await page
    .getByText(
      "Belum ada riwayat yang cocok. Tidak ada angka contoh atau token perkiraan.",
      { exact: true },
    )
    .waitFor();
  const callsBeforeContext = calls;
  await click("Kalender konten");
  await click("Siapkan ide AI (opsional)");
  // Nilai formulir diisi lewat efek React, jadi tunggu sampai benar-benar terisi.
  assert.equal(
    await nilaiStabil(
      page.getByLabel("Jenis bantuan AI", { exact: true }),
      (value) => value === "ideas",
      "Jenis bantuan AI tidak memakai nilai awal ideas",
    ),
    "ideas",
  );
  await nilaiStabil(
    page.getByLabel("Topik AI", { exact: true }),
    (value) => value.includes("Kebun Kopi"),
    "Topik AI tidak memuat nama proyek aktif",
  );
  await click("Proyek baru");
  await page
    .getByLabel("Nama proyek", { exact: true })
    .fill("Proyek konteks terpisah");
  await click("Buat proyek");
  await click("AI & token");
  await nilaiStabil(
    page.getByLabel("Topik AI", { exact: true }),
    (value) => value === "",
    "Topik AI tidak dikosongkan setelah proyek berganti",
  );
  assert.equal(calls, callsBeforeContext);
  assert.deepEqual(errors, []);
  console.log(
    "PASS (simulated gateway only): optional AI, multi-key setup/order/toggles, provider-change key protection, no background AI calls, fallback display, unknown usage, export/filter/history, all-fail manual mode, cancellation, no secrets/prompts in browser storage or backups, keys forgotten on reload, responsive AI screens.",
  );
} finally {
  await browser.close();
}
