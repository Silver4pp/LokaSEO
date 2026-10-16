import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";
await mkdir("test-results", { recursive: true });
const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const state = () =>
  page.evaluate(() => JSON.parse(localStorage.getItem("lokaseo.workspace.v1")));
const nav = async (name) =>
  page.getByRole("button", { name, exact: true }).first().click();
async function addArticle(title, date) {
  await page
    .getByRole("button", { name: "Tambah konten", exact: true })
    .click();
  await page.getByLabel("Judul konten", { exact: true }).fill(title);
  await page.getByLabel("Kata kunci utama").fill("kata uji");
  await page.getByLabel("Tanggal rencana terbit").fill(date);
  await page
    .getByRole("button", { name: "Simpan rencana", exact: true })
    .click();
}
try {
  await page.goto("http://127.0.0.1:3000");
  await page
    .getByRole("heading", { name: "Langkah kecil, jangkauan lebih luas." })
    .waitFor();
  await page
    .getByRole("button", { name: "Pengaturan proyek", exact: true })
    .click();
  assert.equal(
    await page
      .getByRole("button", { name: "Hapus proyek ini", exact: true })
      .isDisabled(),
    true,
  );
  await page
    .getByLabel("Nama proyek", { exact: true })
    .fill("Kopi yang Diperbarui");
  await page
    .getByRole("button", { name: "Simpan proyek", exact: true })
    .click();
  await page
    .getByText(
      "Informasi proyek diperbarui. Audit dan konten tetap tersimpan.",
      { exact: true },
    )
    .waitFor();
  let ws = await state();
  assert.equal(ws.projects[0].name, "Kopi yang Diperbarui");
  assert.equal(ws.projects[0].articles.length, 4);
  assert.equal(ws.projects[0].checks.length, 2);
  assert.equal(ws.projects[0].audit.images, 8);
  await page.getByRole("button", { name: "Proyek baru", exact: true }).click();
  await page.getByLabel("Nama proyek", { exact: true }).fill("Uji Poles");
  await page.getByLabel("Kota / wilayah layanan").fill("Surabaya");
  await page.getByRole("button", { name: "Buat proyek", exact: true }).click();
  await nav("Kalender konten");
  await addArticle("Artikel sebelum diedit", "2026-11-06");
  await page
    .getByRole("button", { name: "Edit Artikel sebelum diedit", exact: true })
    .click();
  await page.getByLabel("Judul konten", { exact: true }).fill("   ");
  await page
    .getByRole("button", { name: "Simpan perubahan", exact: true })
    .click();
  await page.getByRole("alert").waitFor();
  await page
    .getByLabel("Judul konten", { exact: true })
    .fill("Artikel hasil edit");
  await page.getByLabel("Tanggal rencana terbit").fill("2026-12-09");
  await page
    .getByLabel("Status konten", { exact: true })
    .selectOption("Ditulis");
  await page
    .getByRole("button", { name: "Simpan perubahan", exact: true })
    .click();
  // Web Locks persistence is asynchronous; wait for the committed edit, not just the click.
  await page.waitForFunction(() => {
    const saved = JSON.parse(localStorage.getItem("lokaseo.workspace.v1"));
    const article = saved?.projects.find((p) => p.id === saved.activeId)
      ?.articles[0];
    return (
      article?.title === "Artikel hasil edit" &&
      article?.date === "2026-12-09" &&
      article?.status === "Ditulis"
    );
  });
  ws = await state();
  let project = ws.projects.find((p) => p.id === ws.activeId);
  assert.deepEqual(
    project.articles.map((a) => [a.title, a.date, a.status]),
    [["Artikel hasil edit", "2026-12-09", "Ditulis"]],
  );
  await nav("Bulanan");
  await page
    .getByRole("heading", { name: "Desember 2026", exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: "Tambah konten 2026-12-10", exact: true })
    .click();
  assert.equal(
    await page.getByLabel("Tanggal rencana terbit").inputValue(),
    "2026-12-10",
  );
  await page.getByLabel("Judul konten", { exact: true }).fill("Dari kalender");
  await page
    .getByRole("button", { name: "Simpan rencana", exact: true })
    .click();
  await page.screenshot({
    path: "test-results/lokaseo-calendar-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Bulan berikutnya", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Januari 2027", exact: true })
    .waitFor();
  await page.getByLabel("Pilih bulan", { exact: true }).fill("2026-12");
  await page
    .getByRole("heading", { name: "Desember 2026", exact: true })
    .waitFor();
  await nav("Daftar");
  await addArticle("Lewat jadwal", "2001-01-01");
  await page.getByRole("checkbox", { name: /^Lewat jadwal/ }).check();
  await page
    .getByRole("button", { name: "Edit Lewat jadwal", exact: true })
    .waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Edit Artikel hasil edit", exact: true })
      .count(),
    0,
  );
  await nav("Reset filter");
  page.once("dialog", (d) => d.accept());
  await page
    .getByRole("button", { name: "Hapus Artikel hasil edit", exact: true })
    .click();
  await nav("Urungkan hapus");
  await page
    .getByRole("button", { name: "Edit Artikel hasil edit", exact: true })
    .waitFor();
  await page.keyboard.press("Control+k");
  await page.getByLabel("Pencarian lintas proyek").fill("kopi yang");
  await page
    .getByRole("button", {
      name: "Proyek · Kopi yang Diperbarui Kopi yang Diperbarui",
      exact: true,
    })
    .click();
  await page.getByText("kebunkopi.example", { exact: true }).waitFor();
  await page
    .getByRole("button", { name: "Cari semua proyek dan konten", exact: true })
    .click();
  await page.getByLabel("Pencarian lintas proyek").fill("artikel hasil edit");
  await page
    .getByRole("button", {
      name: "Konten · Uji Poles Artikel hasil edit",
      exact: true,
    })
    .click();
  await page
    .getByRole("heading", { name: "Brief artikel", exact: true })
    .waitFor();
  ws = await state();
  assert.equal(ws.projects.find((p) => p.id === ws.activeId).name, "Uji Poles");
  await nav("Tutup dialog");
  await page.reload();
  await page.getByText("Uji Poles", { exact: true }).last().waitFor();
  await nav("Laporan");
  const [backup] = await Promise.all([
    page.waitForEvent("download"),
    nav("Unduh cadangan .json"),
  ]);
  const backupJson = JSON.parse(await readFile(await backup.path(), "utf8"));
  const badBackup = { ...backupJson, activeId: "missing-project" };
  await page.locator("input[type=file]").setInputFiles({
    name: "invalid.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(badBackup)),
  });
  await page
    .getByText("Berkas tidak valid. Pilih cadangan JSON LokaSEO versi 1.", {
      exact: true,
    })
    .waitFor();
  await page.waitForFunction((expected) => {
    const saved = JSON.parse(localStorage.getItem("lokaseo.workspace.v1"));
    return (
      saved?.activeId === expected.activeId &&
      saved?.projects.length === expected.projects.length
    );
  }, backupJson);
  assert.deepEqual(await state(), backupJson);
  await page
    .getByRole("button", { name: "Pengaturan proyek", exact: true })
    .click();
  await nav("Hapus proyek ini");
  assert.equal(
    await page
      .getByRole("button", { name: "Hapus permanen", exact: true })
      .isDisabled(),
    true,
  );
  await page.getByLabel("Ketik nama proyek untuk konfirmasi").fill("Uji Poles");
  await nav("Hapus permanen");
  await page.waitForFunction(
    () =>
      JSON.parse(localStorage.getItem("lokaseo.workspace.v1")).projects
        .length === 1,
  );
  assert.equal((await state()).projects.length, 1);
  await nav("Laporan");
  page.once("dialog", (d) => d.accept());
  await page.locator("input[type=file]").setInputFiles({
    name: "backup.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(backupJson)),
  });
  await page
    .getByText("Cadangan berhasil dipulihkan.", { exact: true })
    .waitFor();
  await page.waitForFunction((expected) => {
    const saved = JSON.parse(localStorage.getItem("lokaseo.workspace.v1"));
    return (
      saved?.activeId === expected.activeId &&
      saved?.projects.length === expected.projects.length
    );
  }, backupJson);
  assert.deepEqual(await state(), backupJson);
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("navigation", { name: "Navigasi seluler" })
    .getByRole("button", { name: "Kalender konten", exact: true })
    .click();
  await page
    .getByRole("button", {
      name: "Edit seluler Artikel hasil edit",
      exact: true,
    })
    .click();
  await page.getByLabel("Tanggal rencana terbit").fill("2026-12-12");
  await nav("Simpan perubahan");
  await nav("Bulanan");
  await page.getByLabel("Agenda bulanan seluler").waitFor();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "test-results/lokaseo-calendar-mobile.png",
    fullPage: true,
  });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  await nav("Panduan seluler");
  await page
    .getByRole("heading", { name: "Tentang ruang kerja ini", exact: true })
    .waitFor();
  await nav("Tutup dialog");
  assert.deepEqual(errors, []);
  // Corrupt local data must remain downloadable, not be replaced by example data.
  const recovery = await browser.newPage();
  await recovery.addInitScript(() =>
    localStorage.setItem("lokaseo.workspace.v1", "{broken json"),
  );
  await recovery.goto("http://127.0.0.1:3000");
  await recovery.getByRole("alert").waitFor();
  const [raw] = await Promise.all([
    recovery.waitForEvent("download"),
    recovery
      .getByRole("button", { name: "Unduh data asli", exact: true })
      .click(),
  ]);
  assert.equal(await readFile(await raw.path(), "utf8"), "{broken json");
  assert.equal(
    await recovery.evaluate(() => localStorage.getItem("lokaseo.workspace.v1")),
    "{broken json",
  );
  console.log(
    "PASS: project edit/data retention, protected deletion, content edit/reschedule/status, whitespace validation, monthly calendar/year navigation, add by date, overdue filter, undo deletion, Ctrl+K/cross-project search, persistence, invalid backup rejection, valid backup restore, mobile cards/calendar/help, corrupt-data recovery, zero JS exceptions.",
  );
} finally {
  await browser.close();
}
