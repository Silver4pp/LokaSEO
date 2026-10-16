// Uji antarmuka "Peramban untuk halaman ber-JavaScript" pada aplikasi desktop
// yang benar-benar berjalan: server dijalankan sendiri oleh skrip ini, halaman
// /radar dibuka di peramban sungguhan, lalu kartunya dipakai sebagaimana
// pengguna memakainya.
//
// Yang dibuktikan:
// - bila peramban ada, tombol "Uji rendering" bisa ditekan dan melapor;
// - bila peramban TIDAK ada, tombol yang pudar tidak pernah berdiri sendiri:
//   selalu ada alasan, tombol "Periksa ulang", daftar "Yang sudah dicari", dan
//   kolom untuk menunjuk sendiri berkas perambannya. Ini berangkat dari
//   laporan nyata: di Windows 11 tombolnya mati tanpa keterangan apa pun.
//
// Skrip ini tidak menghubungi situs pihak ketiga: uji rendering bawaan memakai
// halaman uji milik radar sendiri (`data:`).
import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile, chmod } from "node:fs/promises";
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

const data = await mkdtemp(path.join(tmpdir(), "lokaseo-peramban-"));
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
      const balasan = await fetch(`${alamat}/api/radar/peramban`);
      if (balasan.ok) return await balasan.json();
    } catch {
      /* server belum menerima sambungan */
    }
    await new Promise((tunggu) => setTimeout(tunggu, 500));
  }
  throw new Error("server desktop tidak juga siap:\n" + log);
};

// Keadaan "tidak ada peramban" ditiru dengan menyadap permintaan, supaya
// jalurnya teruji di mesin mana pun — termasuk mesin yang kebetulan tidak
// punya Chrome.
const TANPA_PERAMBAN = {
  tersedia: false,
  jalur: "",
  nama: "",
  versi: "",
  sumber: "",
  mode_render: "tidak",
  instalator: false,
  versi_radar: "0.1.0",
  pesan: "Peramban tidak ditemukan.",
  alasan:
    "Tidak ada berkas peramban di 34 lokasi yang diperiksa. Pasang Microsoft " +
    "Edge atau Google Chrome, lalu klik \u201cPeriksa ulang\u201d.",
  dicari: [
    { jalur: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", ada: false, alasan: "berkas tidak ada" },
    { jalur: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", ada: true, alasan: "ada, tetapi gagal dijalankan" },
  ],
};

let browser;
try {
  const keadaan = await menungguSiap();
  browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  const rapi = (teks) => teks.replace(/\s+/g, " ").trim();

  // -- Skenario A: tidak ada peramban -------------------------------------
  {
    const page = await browser.newPage({ viewport: { width: 1180, height: 1500 } });
    const galat = [];
    page.on("pageerror", (e) => galat.push(e.message));
    await page.route("**/api/radar/peramban*", (rute) => {
      if (rute.request().method() === "POST") {
        return rute.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ berhasil: false, pesan: "Berkas tidak ditemukan: C:\\bukan-peramban.exe" }),
        });
      }
      return rute.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(TANPA_PERAMBAN) });
    });

    await page.goto(`${alamat}/radar`);
    await page.waitForSelector("#peramban .kartu");
    const kartu = async () => rapi(await page.innerText("#peramban"));

    // Tombol uji memang pudar — tetapi tidak pernah berdiri sendiri.
    assert.equal(await page.getByRole("button", { name: "Uji rendering" }).isDisabled(), true);
    const isi = await kartu();
    assert.match(isi, /^Belum ada peramban:/, `kartu harus membuka dengan keadaannya, dapat: ${isi}`);
    assert.match(isi, /34 lokasi yang diperiksa/, `kartu harus menyebut alasannya, dapat: ${isi}`);
    assert.match(isi, /Periksa ulang/, "kartu harus menawarkan tombol periksa ulang");
    assert.match(isi, /Pakai berkas ini/, "kartu harus menawarkan kolom penunjuk berkas");
    await page.screenshot({ path: "test-results/peramban-1-tanpa-peramban.png", clip: await page.locator("#peramban").boundingBox() });

    // Tombol periksa ulang benar-benar bekerja.
    await page.getByRole("button", { name: "Periksa ulang" }).click();
    await page.waitForFunction(() => /Pencarian peramban diulang/.test(document.querySelector("#pesan")?.innerText || ""), null, { timeout: 30000 });
    assert.match(await kartu(), /^Belum ada peramban:/, "kartu harus tetap menggambarkan keadaan setelah diulang");

    // Jejak pencarian: jalur yang diperiksa berikut alasannya.
    const rincian = page.locator("#peramban details");
    assert.equal(await rincian.count(), 1, "kartu harus memuat daftar 'Yang sudah dicari'");
    await rincian.locator("summary").click();
    const butir = rincian.locator("li");
    assert.equal(await butir.count(), 2, "kedua jalur yang diperiksa harus tampil");
    assert.match(rapi(await butir.first().innerText()), /msedge.exe .* berkas tidak ada/);
    assert.match(rapi(await butir.nth(1).innerText()), /chrome.exe .* gagal dijalankan/);

    // Jalan keluar terakhir: tunjuk sendiri berkasnya.
    await page.fill("#peramban input[type=text]", "C:\\bukan-peramban.exe");
    await page.getByRole("button", { name: "Pakai berkas ini" }).click();
    await page.waitForFunction(() => /tidak ditemukan|tidak bisa dipakai|tidak menjawab/.test(document.querySelector("#pesan")?.innerText || ""), null, { timeout: 30000 });
    await page.screenshot({ path: "test-results/peramban-2-tanpa-peramban.png", fullPage: true });
    assert.deepEqual(galat, [], "kartu tanpa peramban tidak boleh melempar galat");
    await page.close();
    console.log("peramban-ui: OK — skenario tanpa peramban memberi alasan, jejak, dan jalan keluar");
  }

  // -- Skenario B: peramban sungguhan, bila mesin memilikinya --------------
  if (!keadaan.tersedia) {
    console.log("peramban-ui: OK (skenario peramban sungguhan dilewati — tidak ada peramban di mesin ini)");
  } else {
    const page = await browser.newPage({ viewport: { width: 1180, height: 1500 } });
    const galat = [];
    const luar = [];
    page.on("pageerror", (e) => galat.push(e.message));
    page.on("request", (r) => {
      const url = r.url();
      if (!url.startsWith(alamat)) luar.push(url);
    });

    await page.goto(`${alamat}/radar`);
    await page.waitForSelector("#peramban .kartu");
    assert.deepEqual(galat, [], "halaman radar tidak boleh melempar galat");
    assert.deepEqual(luar, [], "halaman radar tidak boleh memanggil alamat luar");

    const kartu = rapi(await page.innerText("#peramban"));
    const tombolUji = page.getByRole("button", { name: "Uji rendering" });
    assert.equal(await tombolUji.isDisabled(), false, "tombol uji harus bisa ditekan di aplikasi sungguhan");
    assert.match(kartu, /Tidak ada yang perlu diunduh/, "kartu harus menyebut tidak ada unduhan");
    // Chip ringkasan di atas halaman tidak boleh bertentangan dengan kartu di bawahnya.
    const chip = rapi(await page.innerText("#chip"));
    assert.match(chip, /Rendering: peramban siap/, `chip "Rendering" harus sejalan dengan kartu, dapat: ${chip}`);
    await page.screenshot({ path: "test-results/peramban-3-kartu.png", clip: await page.locator("#peramban").boundingBox() });

    await tombolUji.click();
    await page.waitForFunction(() => /\S/.test(document.querySelector("#pesan")?.innerText || ""), null, { timeout: 90000 });
    const pesan = rapi(await page.innerText("#pesan"));
    await page.screenshot({ path: "test-results/peramban-4-hasil.png", fullPage: true });
    assert.match(pesan, /Rendering berjalan/, `tombol harus melaporkan keberhasilan, dapat: ${pesan}`);
    assert.match(pesan, new RegExp(keadaan.nama.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")), "pesan harus menyebut peramban yang dipakai");
    assert.deepEqual(galat, [], "kartu tidak boleh melempar galat setelah diuji");
    await page.close();
    console.log(`peramban-ui: OK — ${pesan}`);
  }
} finally {
  await browser?.close();
  server.kill("SIGTERM");
  await rm(data, { recursive: true, force: true });
}
