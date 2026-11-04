import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFile, writeFile } from "node:fs/promises";

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1080 }, timezoneId: "Asia/Karachi" });
const page = await context.newPage();
const base = process.env.E2E_BASE_URL || "http://127.0.0.1:3000";
const errors = [];
page.on("pageerror", error => errors.push(error.message));
let collectionId;
try {
  await page.goto(base);
  const created = page.waitForResponse(response => new URL(response.url()).pathname.endsWith("/api/v1/sample") && new URL(response.url()).searchParams.get("format") === "pdf");
  await page.getByRole("button", { name: "Open PDF sample", exact: true }).click();
  collectionId = (await (await created).json()).id;
  await expect(page.getByText("4 OF 4 SOURCES READY")).toBeVisible({ timeout: 60000 });
  await page.getByRole("button", { name: "Investigate claim" }).click();
  await expect(page.getByRole("heading", { name: "conflicting evidence" })).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: "Read in source" }).first().click();
  await expect(page.locator("mark")).toContainText("1.20 million");
  await expect(page.getByRole("img", { name: "Original PDF page 1" })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Rendering source page…")).not.toBeVisible({ timeout: 15000 });
  const pixels = await page.locator("canvas").evaluate(canvas => { const data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data; let ink = 0; for (let i = 0; i < data.length; i += 4) if (data[i] < 220 && data[i + 1] < 220 && data[i + 2] < 220) ink++; return ink; });
  expect(pixels).toBeGreaterThan(100);
  await page.screenshot({ path: "../../docs/screenshots/pdf-source-reader.png", fullPage: true });

  await page.getByRole("button", { name: "Suggest claims from this passage", exact: true }).first().click();
  await expect(page.getByText("Choose a claim to review before investigating:")).toBeVisible({ timeout: 15000 });
  await page.locator(".suggestion-results button").first().click();
  await expect(page.getByLabel("Claim to investigate")).toHaveValue("Harbor Transit recorded 1.20 million journeys in Q2.");
  await expect(page.getByText("Suggested claim selected. Review it, then choose Investigate claim to confirm.")).toBeVisible();
  expect(await page.locator(".history>button").count()).toBe(1);

  await page.getByRole("tab", { name: /Source reader/ }).click();
  await page.getByLabel("Upload UTF-8 text sources", { exact: true }).setInputFiles({ name: "two-page.pdf", mimeType: "application/pdf", buffer: await readFile("../../fixtures/pdf/two-page.pdf") });
  const sourceRow = page.locator(".document-row").filter({ hasText: "two-page.pdf" });
  await expect(sourceRow).toContainText("ready", { timeout: 20000 });
  await sourceRow.locator(".document-open").click();
  await expect(page.getByRole("img", { name: "Original PDF page 1" })).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: "Next PDF page" }).click();
  await expect(page.getByRole("img", { name: "Original PDF page 2" })).toBeVisible({ timeout: 15000 });
  await expect(page.locator(".passages")).toContainText("Page two: the measured value was 42 units.");
  await expect(page.getByText("Rendering source page…")).not.toBeVisible({ timeout: 15000 });
  await page.getByLabel("Upload replacement source", { exact: true }).setInputFiles({ name: "replacement.txt", mimeType: "text/plain", buffer: Buffer.from("A revised source.\n\nThe measured value changed to 43 units.\n") });
  const replacement = page.locator(".document-row").filter({ hasText: "replacement.txt" });
  await expect(replacement).toContainText("ready", { timeout: 15000 });
  await replacement.locator(".document-open").click();
  await expect(page.getByRole("combobox", { name: "Source version" })).toContainText("v2");
  const oldValue = await page.getByRole("option", { name: /v1.*retained/ }).getAttribute("value");
  await page.getByRole("combobox", { name: "Source version" }).selectOption(oldValue);
  await expect(page.getByRole("img", { name: "Original PDF page 1" })).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: "Use this version" }).click();
  await expect(page.locator(".document-row").filter({ hasText: "two-page.pdf" })).toContainText("ready");
  await page.locator(".document-row").filter({ hasText: "two-page.pdf" }).locator(".document-open").click();
  await expect(page.getByRole("img", { name: "Original PDF page 1" })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Rendering source page…")).not.toBeVisible({ timeout: 15000 });

  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "../../docs/screenshots/mobile-pdf-reader.png", fullPage: true });
  await page.getByRole("tab", { name: /Evidence board/ }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /Source reader/ })).toBeFocused();
  await page.keyboard.press("Home");
  await expect(page.getByRole("tab", { name: /Evidence board/ })).toBeFocused();

  if (process.env.E2E_ACCESSIBILITY === "1") {
    await page.getByRole("tab", { name: /Source reader/ }).click();
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    await writeFile("../../docs/screenshots/accessibility-pdf.json", JSON.stringify(result.violations, null, 2));
    expect(result.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }))).toEqual([]);
  }
  expect(errors).toEqual([]);
  console.log("PASS: PDF sample investigation, actual canvas rendering, exact citation, claim suggestion confirmation, page navigation, replacement/retained-version restoration, mobile PDF layout, and keyboard tabs.");
} catch (error) {
  await page.screenshot({ path: "../../docs/screenshots/pdf-failure.png", fullPage: true }).catch(() => {});
  throw error;
} finally {
  if (collectionId) await page.request.delete(`${base}/api/v1/collections/${collectionId}`);
  await browser.close();
}
