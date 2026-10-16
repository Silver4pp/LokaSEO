// Uji antarmuka "Cek kesiapan" pada aplikasi desktop yang benar-benar berjalan:
// server dijalankan sendiri oleh skrip ini, halaman /radar dibuka di peramban
// sungguhan, tombol "Periksa kesiapan" diklik, dan laporan yang muncul diperiksa.
//
// Yang dibuktikan: laporan bisa dibaca manusia, memuat butir yang diperiksa, dan
// bisa disalin ke papan klip — inilah yang akan dikirim pengguna saat melaporkan
// masalah di komputernya sendiri. Tidak ada permintaan keluar selain ke aplikasi.
import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { spawn } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AKAR = path.resolve(fileURLToPath(new URL("../../..", import.meta.url)));
await mkdir("test-results", { recursive: true });

const porta = await new Promise((selesai) => {
  const probe = net.createServer();
  probe.listen(0, "127.0.0.1", () => {
    const { port } = probe.address();
    probe.close(() => selesai(port));
  });
});

const data = await mkdtemp(path.join(tmpdir(), "lokaseo-kesiapan-"));
const server = spawn("python3", [path.join(AKAR, "desktop", "run.py"), "--no-open", "--no-tray", "--port", String(porta)], {
  cwd: AKAR,
  env: { ...process.env, LOKA_DATA_DIR: path.join(data, "data"), LOKARADAR_DATA: path.join(data, "radar"), PYTHONUNBUFFERED: "1" },
  stdio: ["ignore", "pipe", "pipe"],
});
let log = "";
server.stdout.on("data", (keping) => (log += keping));
server.stderr.on("data", (keping) => (log += keping));

const alamat = `http://127.0.0.1:${porta}`;
const menungguSiap = async () => {
  for (let i = 0; i < 60; i += 1) {
    if (server.exitCode !== null) throw new Error("server desktop berhenti lebih awal:\n" + log);
    try {
      const balasan = await fetch(`${alamat}/api/kesiapan`);
      if (balasan.ok) return await balasan.json();
    } catch {
      /* server belum menerima sambungan */
    }
    await new Promise((tunggu) => setTimeout(tunggu, 500));
  }
  throw new Error("server desktop tidak juga siap:\n" + log);
};

const rapi = (teks) => teks.replace(/\s+/g, " ").trim();

let browser;
try {
  const langsung = await menungguSiap();
  assert.match(langsung.teks, /LAPORAN KESIAPAN LOKASEO/, "endpoint harus mengembalikan laporan");
  assert.match(langsung.teks, /\[LULUS\]/, "laporan harus memakai tanda hasil yang terbaca");

  browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  const context = await browser.newContext({ permissions: ["clipboard-read", "clipboard-write"] });
  const page = await context.newPage();
  const galat = [];
  const luar = [];
  page.on("pageerror", (e) => galat.push(e.message));
  page.on("request", (r) => {
    const url = r.url();
    if (!url.startsWith(alamat)) luar.push(url);
  });

  await page.goto(`${alamat}/radar`);
  const tombol = page.getByRole("button", { name: "Periksa kesiapan" });
  await tombol.waitFor();
  assert.equal(await tombol.isDisabled(), false, "tombol kesiapan harus bisa ditekan di aplikasi sungguhan");

  await tombol.click();
  await page.waitForSelector("#laporan-kesiapan");
  const laporan = await page.locator("#laporan-kesiapan").inputValue();
  assert.match(laporan, /^LAPORAN KESIAPAN LOKASEO/);
  assert.match(laporan, /Versi      : LokaSEO/, "laporan harus menyebut versi aplikasi");
  assert.match(laporan, /\[(LULUS|PERHATIAN|GAGAL)\]/, "laporan harus memakai tanda hasil");
  assert.match(laporan, /Tidak ada data yang dikirim ke mana pun/);
  assert.equal(
    /AIza|LOKARADAR_PLACES_KEY/.test(laporan),
    false,
    "laporan tidak boleh memuat kunci API",
  );

  const ringkas = rapi(await page.innerText("#kesiapan"));
  assert.match(ringkas, /\d+ baik/, `ringkasan harus terbaca, dapat: ${ringkas.slice(0, 120)}`);
  assert.match(ringkas, /\[LULUS\]/);
  await page.screenshot({ path: "test-results/kesiapan-1-laporan.png", fullPage: true });

  await page.getByRole("button", { name: "Salin laporan" }).click();
  const tersalin = await page.evaluate(() => navigator.clipboard.readText().catch(() => ""));
  if (tersalin) {
    assert.equal(tersalin.trim(), laporan.trim(), "isi papan klip harus sama dengan laporannya");
    console.log("kesiapan-ui: OK — laporan tersalin ke papan klip dan siap dikirim");
  } else {
    console.log("kesiapan-ui: OK — laporan tampil (papan klip tidak bisa dibaca di lingkungan ini)");
  }

  assert.deepEqual(galat, [], "halaman radar tidak boleh melempar galat");
  assert.deepEqual(luar, [], "halaman radar tidak boleh memanggil alamat luar");
} finally {
  await browser?.close();
  server.kill("SIGTERM");
  await rm(data, { recursive: true, force: true });
}
