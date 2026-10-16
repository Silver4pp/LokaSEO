// Uji tampilan radar tanpa server: berkas contoh harus bisa dibuka langsung
// dari cakram, mengambil data dari `window.__RADAR_DATA__`, dan tidak boleh
// memanggil alamat luar mana pun.
import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";

await mkdir("test-results", { recursive: true });

const ALAMAT = new URL("../../../desktop/contoh/tampilan-radar.html", import.meta.url).href;
const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
try {
  const page = await browser.newPage({ viewport: { width: 1180, height: 1400 } });
  const galat = [];
  const luar = [];
  page.on("pageerror", (e) => galat.push(e.message));
  page.on("request", (r) => {
    const url = r.url();
    if (!url.startsWith("file:") && !url.startsWith("data:")) luar.push(url);
  });

  await page.goto(ALAMAT);
  await page.waitForSelector("#sasaran .kartu");

  assert.deepEqual(galat, [], "halaman contoh tidak boleh melempar galat");
  assert.deepEqual(luar, [], "halaman contoh tidak boleh memanggil sumber luar");

  // innerText menaruh baris baru di antara label dan nilainya; rapikan dulu.
  const rapi = (teks) => teks.replace(/\s+/g, " ").trim();
  const chip = rapi(await page.innerText("#chip"));
  assert.match(chip, /Sasaran: 6 \(6 aktif\)/);
  assert.match(chip, /Perubahan tercatat: 7/);
  assert.match(chip, /Rendering: peramban siap/);

  const profil = rapi(await page.innerText("#profil"));
  assert.match(profil, /Kopi Ranah/);
  assert.match(profil, /Kafe, kedai kopi, atau tempat makan kecil/);
  assert.match(profil, /Ambang rating: 4\.3/);
  assert.match(profil, /CafeOrCoffeeShop/);

  const kartu = await page.locator("#sasaran .kartu").count();
  assert.equal(kartu, 6, "enam sasaran contoh harus tampil");
  const daftarSasaran = rapi(await page.innerText("#sasaran"));
  assert.match(daftarSasaran, /Pesaing Roastery Selatan/);
  assert.match(daftarSasaran, /diambil dengan peramban/);
  assert.match(daftarSasaran, /Rating: 4\.6 dari 239 ulasan/);

  // -- ringkasan pemantauan: yang penting di atas, pola bising dinyatakan ----
  const ringkasan = rapi(await page.innerText("#ringkasan"));
  assert.match(ringkasan, /Yang perlu dilihat/);
  assert.match(ringkasan, /Rating turun dari 4,5 menjadi 4,4/,
    "perubahan bertingkat tinggi harus berada di bagian atas");
  assert.match(ringkasan, /Pola berulang \(kemungkinan bising\)/);
  assert.match(ringkasan, /14x/, "pola yang muncul 14 kali harus diringkas jadi satu baris");
  assert.match(ringkasan, /Tidak berubah/);
  assert.match(ringkasan, /Pesaing Kafe Barat/,
    "sasaran yang tidak berubah harus disebut, bukan dihilangkan");
  // Sasaran yang belum pernah diambil tidak boleh dibilang "tidak berubah".
  assert.match(ringkasan, /Belum diperiksa/);
  assert.match(ringkasan, /Katering Timur/);

  // Urutan: tingkat tinggi lebih dulu daripada sedang.
  const tingkat = await page.$$eval("#ringkasan h3 ~ ul.sorot li .tingkat", (n) =>
    n.map((e) => e.className.replace("tingkat", "").trim()),
  );
  assert.deepEqual(tingkat.slice(0, 3), ["tinggi", "sedang", "sedang"],
    "urutan ringkasan harus menurut tingkat, bukan menurut waktu");

  // Lencana hitungan ("14x") harus sebaris dengan pesannya. Pernah jatuh ke
  // baris sendiri di bawah tanggal karena ditambahkan sesudah baris tanggal.
  const melenceng = await page.$$eval("#ringkasan .sorot li", (daftar) =>
    daftar
      .map((li) => {
        const pesan = li.querySelector("span:not(.tingkat):not(.nama):not(.ulang)");
        const ulang = li.querySelector(".ulang");
        if (!pesan || !ulang) return null;
        return Math.round(
          Math.abs(pesan.getBoundingClientRect().y - ulang.getBoundingClientRect().y),
        );
      })
      .filter((beda) => beda !== null && beda > 6),
  );
  assert.deepEqual(melenceng, [], "lencana hitungan harus sebaris dengan pesannya");

  const tombolPeriode = await page.$$eval("#ringkasan .baris-pilih button", (n) =>
    n.map((e) => e.textContent.trim()),
  );
  assert.deepEqual(tombolPeriode, ["7 hari", "30 hari"], "tombol periode ringkasan harus ada");

  const perubahan = await page.locator("#perubahan li").count();
  assert.equal(perubahan, 6, "enam perubahan contoh harus tampil");
  assert.match(rapi(await page.innerText("#perubahan")), /Rating turun dari 4,5 menjadi 4,4/);

  const peramban = rapi(await page.innerText("#peramban"));
  assert.match(peramban, /Siap: Microsoft Edge \(Microsoft Edge 141\.0\.3537\.57\)/);
  assert.match(peramban, /Tidak ada yang perlu diunduh/);
  assert.match(peramban, /mode “auto”/);
  assert.equal(await page.isDisabled("#peramban button"), true, "pada contoh, tombol uji peramban mati");

  const berkas = rapi(await page.innerText("#sasaran + .kartu, .kartu:has(#unduh-sasaran)"));
  assert.match(berkas, /Impor menggabung daftar yang ada — tidak pernah menghapus/);
  assert.equal(
    await page.isDisabled("#unduh-sasaran"),
    true,
    "pada contoh, tombol unduh daftar sasaran harus mati",
  );
  assert.equal(await page.isDisabled("#pilih-impor"), true, "pada contoh, tombol impor harus mati");

  assert.equal(
    await page.isDisabled("#periksa-kesiapan"),
    true,
    "pada contoh, tombol cek kesiapan harus mati karena tidak ada server di belakangnya",
  );

  const jadwal = rapi(await page.innerText("#jadwal"));
  assert.match(jadwal, /Aktif: radar memeriksa sendiri setiap hari pukul 07:00/);
  assert.match(jadwal, /Perintah yang didaftarkan: "C:\\Program Files\\LokaSEO\\LokaSEO\.exe" --radar-periksa/);
  assert.match(jadwal, /tidak memeriksa lebih sering dari sekali sehari/);
  assert.equal(
    await page.locator("#jadwal button:disabled").count(),
    3,
    "pada contoh, tombol jadwal harus mati karena tidak ada penjadwal di belakangnya",
  );

  // Tombol periksa wajib mati pada contoh: tidak ada server di belakangnya.
  assert.equal(await page.isDisabled("#periksa"), true, "tombol periksa harus mati pada contoh");
  assert.match(rapi(await page.innerText("#pesan")), /contoh tampilan/);

  await page.screenshot({ path: "test-results/radar-contoh.png", fullPage: true });
  console.log(
    "radar-contoh: OK — ringkasan, 6 sasaran, 6 perubahan, kartu peramban, jadwal, berkas daftar sasaran, dan kartu kesiapan, tanpa sumber luar",
  );
} finally {
  await browser.close();
}
