// Uji antarmuka "Unduh / Impor daftar sasaran" pada aplikasi desktop yang benar-benar
// berjalan: server dijalankan sendiri oleh skrip ini, halaman /radar dibuka di peramban
// sungguhan, tombol unduh diklik, lalu berkasnya diimpor kembali.
//
// Yang dibuktikan:
//   1. berkas yang diunduh benar-benar terbentuk dan isinya berkas daftar sasaran yang sah;
//   2. impor menggabung — sasaran lama tetap ada, yang baru bertambah;
//   3. berkas yang salah dijawab dengan alasan yang terbaca pengguna;
//   4. tidak ada permintaan keluar ke alamat mana pun selain aplikasi itu sendiri.
import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
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

const data = await mkdtemp(path.join(tmpdir(), "lokaseo-sasaran-"));
const server = spawn("python3", [path.join(AKAR, "desktop", "run.py"), "--no-open", "--no-tray", "--port", String(porta)], {
  cwd: AKAR,
  env: { ...process.env, LOKARADAR_DATA: path.join(data, "radar"), PYTHONUNBUFFERED: "1" },
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
      const balasan = await fetch(`${alamat}/api/radar/sasaran`);
      if (balasan.ok) return;
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
  await menungguSiap();
  browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  const page = await browser.newPage({ viewport: { width: 1180, height: 1500 } });
  const galat = [];
  const luar = [];
  page.on("pageerror", (e) => galat.push(e.message));
  page.on("request", (r) => {
    const url = r.url();
    if (!url.startsWith(alamat)) luar.push(url);
  });

  await page.goto(`${alamat}/radar`);
  await page.waitForSelector("#sasaran");
  assert.equal(await page.getByRole("button", { name: "Unduh daftar sasaran" }).isDisabled(), false);
  assert.equal(await page.getByRole("button", { name: "Impor daftar sasaran" }).isDisabled(), false);

  // 1. Tambah dua sasaran lewat borang, seperti yang dilakukan pengguna.
  for (const [url, label, jenis] of [
    ["https://pesaing-a.example/menu", "Pesaing A", "harga"],
    ["https://pesaing-b.example/", "Pesaing B", "halaman"],
  ]) {
    await page.getByLabel("Alamat halaman pesaing").fill(url);
    await page.getByLabel("Nama singkat").fill(label);
    await page.getByLabel("Jenis pantauan").selectOption(jenis);
    await page.getByRole("button", { name: "Tambah", exact: true }).click();
    await page.waitForFunction((teks) => document.querySelector("#sasaran").innerText.includes(teks), label);
  }

  // 2. Unduh daftarnya dan periksa isi berkasnya.
  const [unduhan] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Unduh daftar sasaran" }).click(),
  ]);
  const namaBerkas = unduhan.suggestedFilename();
  assert.match(namaBerkas, /^sasaran-radar-\d{4}-\d{2}-\d{2}\.json$/, `nama berkas: ${namaBerkas}`);
  const jalur = await unduhan.path();
  const isiBerkas = JSON.parse(await readFile(jalur, "utf8"));
  assert.equal(isiBerkas.format, "lokaradar.sasaran.v1");
  assert.deepEqual(
    isiBerkas.sasaran.map((item) => item.url),
    ["https://pesaing-a.example/menu", "https://pesaing-b.example/"],
  );
  const pesanUnduh = rapi(await page.innerText("#pesan-sasaran"));
  assert.match(pesanUnduh, /2 sasaran dikirim ke folder Unduhan/, `pesan: ${pesanUnduh}`);
  await page.screenshot({ path: "test-results/sasaran-1-unduh.png", clip: await page.locator("#sasaran").boundingBox() });

  // 3. Impor berkas yang sama: tidak ada yang bertambah, dan itu dikatakan apa adanya.
  await page.locator("#berkas-sasaran").setInputFiles({
    name: namaBerkas,
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(isiBerkas)),
  });
  await page.waitForFunction(() => document.querySelector("#pesan-sasaran").innerText.includes("sasaran"));
  const pesanSama = rapi(await page.innerText("#pesan-sasaran"));
  assert.match(pesanSama, /2 sudah ada/, `pesan impor ulang: ${pesanSama}`);
  assert.match(pesanSama, /Belum ada halaman yang dihubungi/, "impor tidak boleh menghubungi situs mana pun");

  // 4. Impor berkas dari komputer lain: satu sasaran bergabung, satu sudah ada.
  const berkasTeman = {
    format: "lokaradar.sasaran.v1",
    dibuat_pada: "2026-10-14T00:00:00Z",
    jumlah: 2,
    sasaran: [
      { url: "https://pesaing-c.example/", label: "Pesaing C", jenis: "reputasi", aktif: true },
      { url: "https://pesaing-a.example/menu", label: "Pesaing A", jenis: "harga", aktif: true },
    ],
  };
  await page.locator("#berkas-sasaran").setInputFiles({
    name: "dari-rekan.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(berkasTeman)),
  });
  await page.waitForFunction(() => document.querySelector("#pesan-sasaran").innerText.includes("ditambahkan"));
  // Pesan muncul sebelum daftar selesai digambar ulang; tunggu daftarnya juga.
  await page.waitForFunction(() => document.querySelector("#sasaran").innerText.includes("Pesaing C"));
  const pesanGabung = rapi(await page.innerText("#pesan-sasaran"));
  assert.match(pesanGabung, /1 ditambahkan/, `pesan impor: ${pesanGabung}`);
  assert.match(pesanGabung, /1 sudah ada/, `pesan impor: ${pesanGabung}`);
  assert.match(rapi(await page.innerText("#sasaran")), /Pesaing C/, "sasaran baru harus muncul di daftar");
  assert.match(rapi(await page.innerText("#sasaran")), /Pesaing A/, "sasaran lama tidak boleh hilang");

  // 5. Berkas yang salah dijawab dengan alasan, bukan diam.
  await page.locator("#berkas-sasaran").setInputFiles({
    name: "laporan.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ perubahan: [] })),
  });
  await page.waitForFunction(() => document.querySelector("#pesan-sasaran .galat") !== null);
  const pesanSalah = rapi(await page.innerText("#pesan-sasaran"));
  assert.match(pesanSalah, /tidak ada daftar bernama/, `pesan berkas salah: ${pesanSalah}`);
  await page.screenshot({ path: "test-results/sasaran-2-impor.png", fullPage: true });

  assert.deepEqual(galat, [], "halaman radar tidak boleh melempar galat");
  assert.deepEqual(luar, [], "halaman radar tidak boleh memanggil alamat luar");
  console.log(`sasaran-ui: OK — ${namaBerkas} diunduh dan diimpor; ${pesanGabung}`);
} finally {
  await browser?.close();
  server.kill("SIGTERM");
  await rm(data, { recursive: true, force: true });
}
