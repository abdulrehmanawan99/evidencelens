import { chromium, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";

// Requires a running API, worker, migrated database, and built frontend.
const browser = await chromium.launch({
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
    : {}),
  headless: true,
});
const context = await browser.newContext({ viewport: { width: 1440, height: 1080 }, timezoneId: "Asia/Karachi" });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const base = process.env.E2E_BASE_URL || "http://127.0.0.1:3000";
let collectionId;
try {
  await page.goto(base);
  await expect(
    page.getByRole("button", { name: "Open sample collection" }),
  ).toBeVisible();
  const created = page.waitForResponse(
    (r) =>
      new URL(r.url()).pathname.endsWith("/api/v1/sample") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Open sample collection" }).click();
  collectionId = (await (await created).json()).id;
  await expect(page.getByText("4 OF 4 SOURCES READY")).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Investigate claim" }).click();
  await expect(
    page.getByRole("heading", { name: "conflicting evidence" }),
  ).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".finding-card")).toHaveCount(3);
  await page
    .getByRole("button", { name: "Accept", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("button", { name: "Accepted", exact: true }),
  ).toBeVisible();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export reviewed brief" }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toMatch(/evidencelens-.*-r1\.md/);
  await mkdir("../../docs/screenshots", { recursive: true });
  await page.screenshot({
    path: "../../docs/screenshots/evidence-board.png",
    fullPage: true,
  });
  if (process.env.E2E_ACCESSIBILITY === "1") {
    const accessibility = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    await (await import("node:fs/promises")).writeFile("../../docs/screenshots/accessibility-evidence.json", JSON.stringify(accessibility.violations, null, 2));
    expect(accessibility.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }))).toEqual([]);
  }

  await page.getByRole("button", { name: "Read in source" }).first().click();
  await expect(page.locator("mark")).toHaveText(
    "Q2 ridership was 1.20 million journeys across the Harbor Transit network.",
  );
  await expect(
    page.getByText("Showing the exact passage cited in this finding."),
  ).toBeVisible();
  await page.screenshot({
    path: "../../docs/screenshots/source-reader.png",
    fullPage: true,
  });

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Harbor Transit · Q2 review" }),
  ).toBeVisible();
  await expect(page.getByText("4 OF 4 SOURCES READY")).toBeVisible({
    timeout: 10_000,
  });
  await page.locator(".history button").first().click();
  await expect(
    page.getByRole("button", { name: "Accepted", exact: true }),
  ).toBeVisible();

  await page
    .getByLabel("Claim to investigate")
    .fill("Harbor Transit recorded 1.20 million journeys in Q3.");
  await page.getByRole("button", { name: "Investigate claim" }).click();
  await expect(
    page.getByRole("heading", { name: "insufficient evidence" }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(page.locator(".finding-card")).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../../docs/screenshots/mobile-reading-room.png",
    fullPage: true,
  });
  await page.getByRole("tab", { name: /Source reader/ }).click();
  await expect(
    page.getByRole("button", { name: "Add a source", exact: false }),
  ).toBeVisible();
  await page
    .getByLabel("Upload UTF-8 text sources", { exact: true })
    .setInputFiles({
      name: "my-note.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "My source note.\n\n<script>alert('untrusted')</script>\n",
      ),
    });
  await expect(
    page.locator(".document-row").filter({ hasText: "my-note.txt" }),
  ).toContainText("ready", { timeout: 10_000 });
  await page
    .locator(".document-open")
    .filter({ hasText: "my-note.txt" })
    .click();
  await expect(page.locator(".source-paper")).toContainText(
    "<script>alert('untrusted')</script>",
  );
  expect(await page.locator(".source-paper script").count()).toBe(0);
  expect(errors).toEqual([]);
  console.log(
    "PASS: sample ingestion, investigation, exact citation navigation, persisted review, Markdown download, insufficient evidence, mobile layout, custom text upload, and safe source rendering.",
  );
} finally {
  // Remove only the collection this test created; retain other local work.
  if (collectionId)
    await page.request.delete(`${base}/api/v1/collections/${collectionId}`);
  await browser.close();
}
