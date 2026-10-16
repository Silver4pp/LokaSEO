import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
await mkdir("test-results", { recursive: true });
const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto("http://127.0.0.1:3000");
await page
  .getByRole("heading", { name: "Langkah kecil, jangkauan lebih luas." })
  .waitFor();
await page.screenshot({
  path: "test-results/lokaseo-desktop.png",
  fullPage: true,
});
await page.getByRole("button", { name: "Proyek baru", exact: true }).click();
await page.getByLabel("Nama proyek").fill("Uji Bisnis");
await page.getByLabel("Domain situs").fill("bisnis.example");
await page.getByLabel("Kota / wilayah layanan").fill("Bogor");
await page.getByRole("button", { name: "Buat proyek", exact: true }).click();
assert.equal(
  (await page.locator("#project-select").inputValue()) === "contoh",
  false,
);
await page
  .getByRole("button", { name: "Audit halaman", exact: true })
  .last()
  .click();
await page
  .getByLabel("Kode sumber halaman")
  .fill(
    '<html lang="id"><head><title>Judul bisnis lokal yang cukup panjang</title><meta name="description" content="' +
      "a".repeat(100) +
      '"><meta name="viewport" content="width=device-width"><link rel="canonical" href="https://bisnis.example"><script type="application/ld+json">{"@type":"LocalBusiness"}</script></head><body><h1>Bisnis</h1><img alt="" src="data:,x"></body></html>',
  );
await page.getByRole("button", { name: "Periksa HTML", exact: true }).click();
await page.getByRole("heading", { name: "Skor checklist: 100/100" }).waitFor();
await page
  .getByRole("button", { name: "SEO lokal", exact: true })
  .first()
  .click();
await page.getByRole("checkbox").first().check();
await page
  .getByRole("button", { name: "Klaster kata kunci", exact: true })
  .first()
  .click();
await page
  .getByLabel("Daftar kata kunci")
  .fill("toko bogor\nharga roti\ncara membuat roti");
await page.getByRole("heading", { name: "Pencarian lokal" }).waitFor();
await page
  .getByRole("button", { name: "Kalender konten", exact: true })
  .first()
  .click();
await page.getByRole("button", { name: "Tambah konten", exact: true }).click();
await page
  .getByLabel("Judul konten", { exact: true })
  .fill("Panduan roti Bogor");
await page.getByLabel("Kata kunci utama").fill("toko bogor");
await page.getByLabel("Tanggal rencana terbit").fill("2026-10-25");
await page.getByRole("button", { name: "Simpan rencana", exact: true }).click();
await page.getByLabel("Status Panduan roti Bogor").selectOption("Ditulis");
await page
  .getByRole("button", { name: "Buka brief Panduan roti Bogor", exact: true })
  .click();
await page
  .getByRole("heading", { name: "Brief artikel", exact: true })
  .waitFor();
await page.getByRole("button", { name: "Tutup dialog", exact: true }).click();
await page.reload();
await page.getByText("bisnis.example", { exact: true }).waitFor();
await page
  .getByRole("button", { name: "Laporan", exact: true })
  .first()
  .click();
const [dl] = await Promise.all([
  page.waitForEvent("download"),
  page.getByRole("button", { name: "Unduh laporan .md" }).click(),
]);
assert.equal(dl.suggestedFilename(), "laporan-lokaseo.md");
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({
  path: "test-results/lokaseo-mobile.png",
  fullPage: true,
});
assert.equal(
  await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  true,
);
assert.deepEqual(errors, []);
console.log(
  "PASS: project creation, HTML audit, checklist, clustering, content status, brief, persistence, export, mobile width, no browser exceptions.",
);
await browser.close();
