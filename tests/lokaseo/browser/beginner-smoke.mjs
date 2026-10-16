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
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const nav = (name) =>
    page.getByRole("button", { name, exact: true }).first().click();
  const state = () =>
    page.evaluate(() =>
      JSON.parse(localStorage.getItem("lokaseo.workspace.v1")),
    );
  await page.goto("http://127.0.0.1:3000");
  await page.getByText("0 dari 3 langkah awal", { exact: true }).waitFor();
  assert.equal(
    await page
      .getByRole("heading", { name: "Yang perlu didahulukan", exact: true })
      .isVisible(),
    false,
  );
  await page.screenshot({
    path: "test-results/lokaseo-beginner-desktop.png",
    fullPage: true,
  });
  await nav("Mulai dengan usaha saya");
  await page.getByLabel("Nama proyek", { exact: true }).fill("Roti Pemula");
  await nav("Buat proyek");
  await page.getByText("1 dari 3 langkah awal", { exact: true }).waitFor();
  await nav("Cek informasi bisnis");
  await page
    .getByText("Mulai dari informasi yang dilihat pelanggan.", { exact: true })
    .waitFor();
  await page.getByText("Tunjukkan langkahnya", { exact: true }).click();
  await page
    .getByText("Buka profil usaha Anda di Google atau halaman kontak situs.", {
      exact: true,
    })
    .waitFor();
  await page.getByRole("checkbox").first().check();
  await nav("Ringkasan");
  await page.getByText("2 dari 3 langkah awal", { exact: true }).waitFor();
  await nav("Rencanakan tulisan pertama");
  await page
    .getByLabel("Produk atau layanan", { exact: true })
    .fill("roti ulang tahun");
  await page
    .getByRole("button", { name: "Jadwalkan ide ini", exact: true })
    .first()
    .click();
  assert.equal(
    await page.getByLabel("Judul konten", { exact: true }).inputValue(),
    "Panduan memilih roti ulang tahun",
  );
  assert.equal(
    await page.getByLabel("Kata kunci utama").inputValue(),
    "roti ulang tahun",
  );
  assert.match(
    await page.getByLabel("Tanggal rencana terbit").inputValue(),
    /^\d{4}-\d{2}-\d{2}$/,
  );
  await nav("Simpan rencana");
  await nav("Ringkasan");
  await page.getByText("3 dari 3 langkah awal", { exact: true }).waitFor();
  const [backup] = await Promise.all([
    page.waitForEvent("download"),
    nav("Simpan cadangan pertama"),
  ]);
  const saved = JSON.parse(await readFile(await backup.path(), "utf8"));
  const own = saved.projects.find((p) => p.id === saved.activeId);
  assert.equal(own.name, "Roti Pemula");
  assert.equal(own.domain, "");
  assert.equal(own.articles.length, 1);
  const guide = () => page.getByRole("button", { name: /^Panduan pemula/ });
  await guide().click();
  assert.equal(await guide().getAttribute("aria-pressed"), "false");
  await page
    .getByRole("heading", { name: "Yang perlu didahulukan", exact: true })
    .waitFor();
  await page.reload();
  await page.getByText("Roti Pemula", { exact: true }).last().waitFor();
  assert.equal(await guide().getAttribute("aria-pressed"), "false");
  assert.equal(
    (await state()).projects.find((p) => p.id === own.id).articles.length,
    1,
  );
  await guide().click();
  await nav("Audit halaman");
  await nav("Mulai tanpa kode HTML");
  await page
    .getByText("Mulai dari informasi yang dilihat pelanggan.", { exact: true })
    .waitFor();
  await nav("Audit halaman");
  await page.getByLabel("Unggah berkas HTML").setInputFiles({
    name: "halaman.html",
    mimeType: "text/html",
    buffer: Buffer.from(
      '<!doctype html><html lang="id"><head><title>Roti Pemula — Pesan Roti Ulang Tahun</title></head><body><h1>Roti segar</h1></body></html>',
    ),
  });
  await nav("Periksa HTML");
  await page.getByRole("heading", { name: /^Skor checklist:/ }).waitFor();
  // Penyimpanan terproteksi berjalan asinkron; tunggu hasil audit benar-benar tersimpan.
  await page.waitForFunction(
    (id) =>
      JSON.parse(localStorage.getItem("lokaseo.workspace.v1")).projects.find(
        (p) => p.id === id,
      )?.audit != null,
    own.id,
  );
  const audited = (await state()).projects.find((p) => p.id === own.id).audit;
  await page.getByLabel("Kode sumber halaman").fill("https://example.com");
  await nav("Periksa HTML");
  await page
    .getByRole("alert")
    .filter({ hasText: "Ini alamat situs, bukan kode HTML." })
    .waitFor();
  assert.deepEqual(
    (await state()).projects.find((p) => p.id === own.id).audit,
    audited,
  );
  await page.getByLabel("Unggah berkas HTML").setInputFiles({
    name: "foto.png",
    mimeType: "image/png",
    buffer: Buffer.from("not html"),
  });
  await page
    .getByRole("alert")
    .filter({ hasText: "Pilih berkas .html atau .htm" })
    .waitFor();
  await nav("Ringkasan");
  await nav("Bantuan & arti istilah");
  await page
    .getByRole("heading", { name: "Kamus singkat SEO", exact: true })
    .waitFor();
  await page
    .locator("summary")
    .filter({ hasText: /^Canonical$/ })
    .click();
  await page
    .getByText("Penanda alamat utama jika ada beberapa halaman", {
      exact: false,
    })
    .waitFor();
  await nav("Tutup dialog");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({
    path: "test-results/lokaseo-beginner-mobile.png",
    fullPage: true,
  });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  assert.deepEqual(errors, []);
  console.log(
    "PASS: beginner default, honest sample progress, project without website, guided checklist/content/backup, template prefill, advanced-mode persistence, data retention, HTML upload and friendly rejection, glossary, mobile layout, zero browser exceptions.",
  );
} finally {
  await browser.close();
}
