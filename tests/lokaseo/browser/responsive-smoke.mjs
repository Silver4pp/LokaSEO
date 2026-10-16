import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox"],
});
try {
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:3000");
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const name of [
      "Ringkasan",
      "Audit halaman",
      "SEO lokal",
      "Klaster kata kunci",
      "Kalender konten",
      "Laporan",
    ]) {
      await page.getByRole("button", { name, exact: true }).first().click();
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
        `${width}px ${name} overflows`,
      );
      if (name === "Kalender konten") {
        await page
          .getByRole("button", { name: "Bulanan", exact: true })
          .click();
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
          true,
          `${width}px monthly calendar overflows`,
        );
      }
    }
  }
  console.log(
    "PASS: six pages and monthly calendar have no horizontal overflow at 320, 390, 768, 1024, and 1440px.",
  );
} finally {
  await browser.close();
}
