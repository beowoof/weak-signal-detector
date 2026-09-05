// Read-only browser regression against a running desk. Requires Playwright + Chrome.
// POSTs are mocked or blocked; this never edits backend reports, notices or collections.
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    let saveMode = "fail";
    let savedBody;
    await context.route("**/*", async (route) => {
      const request = route.request();
      if (["GET", "HEAD", "OPTIONS"].includes(request.method())) return route.continue();
      if (request.url().endsWith("/api/report") && request.method() === "POST") {
        savedBody = request.postDataJSON();
        return route.fulfill({ status: saveMode === "fail" ? 503 : 200, contentType: "application/json",
          body: JSON.stringify(saveMode === "fail" ? { detail: "Test save failure" } : {
            ...savedBody, report_id: "ui-test-only", updated_at: new Date().toISOString(), empty: false,
          }) });
      }
      return route.abort();
    });
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("dialog", (dialog) => dialog.accept());
    await page.goto(process.env.WSD_UI_URL || "http://127.0.0.1:5173", { waitUntil: "networkidle" });
    await page.locator(".product-hero").waitFor();
    assert.ok(await page.locator(".alert-row").count() >= 2, "Requires two notices for switching regression");
    assert.equal(await page.locator(".report-read:visible").count(), 0, "Notes must not precede overview");
    const top = await page.locator(".notice-header").boundingBox();
    assert.ok(top.y < 100, "Notice identity is visible immediately");
    const body = page.locator(".notice-body");
    await body.evaluate((el) => el.scrollTop = 700);
    assert.ok(await body.evaluate((el) => el.scrollTop) > 0, "Detail scrolls independently");
    assert.equal((await page.locator(".notice-header").boundingBox()).y, top.y);

    await page.getByRole("tab", { name: "Collection", exact: true }).click();
    assert.equal(await page.locator(".collect-task[open]").count(), 0, "Collection starts collapsed");
    await page.getByRole("tab", { name: "Evidence", exact: true }).click();
    const windowPicker = page.getByLabel("Window", { exact: true });
    await windowPicker.selectOption({ index: 1 });
    const chosenWindow = await windowPicker.inputValue();
    await page.getByRole("button", { name: "Combined z-scores", exact: true }).click();
    const legend = page.locator("#panel-evidence .legend button").first();
    await legend.click();
    const choice = await legend.getAttribute("aria-pressed");
    await page.waitForTimeout(9000);
    assert.equal(await legend.getAttribute("aria-pressed"), choice, "Poll must preserve visibility");
    assert.equal(await windowPicker.inputValue(), chosenWindow, "Poll must preserve measurement window");

    await page.getByRole("tab", { name: "Notes & assessment", exact: true }).click();
    await page.getByRole("button", { name: /3\s*Your assessment/ }).click();
    await page.getByRole("button", { name: /^(Edit|Write) assessment$/ }).click();
    const marker = "Unsaved analyst draft — browser regression only";
    await page.getByLabel("Your notes and assessment", { exact: true }).fill(marker);
    const firstId = new URL(page.url()).searchParams.get("notice");
    await page.locator(".alert-row").nth(1).click();
    assert.equal(await page.locator("textarea").count(), 0, "Other notice must not inherit draft");
    await page.locator(".alert-row").first().click();
    assert.equal(await page.locator("textarea").inputValue(), marker, "Switch restores draft");
    await page.reload({ waitUntil: "networkidle" });
    assert.equal(await page.locator("textarea").inputValue(), marker, "Reload restores draft");
    await page.getByRole("button", { name: "Save assessment", exact: true }).click();
    await page.getByText("Notes were not saved.", { exact: false }).waitFor();
    assert.equal(await page.locator("textarea").inputValue(), marker);
    assert.equal(savedBody.notice_id, firstId);
    saveMode = "success";
    await page.getByRole("button", { name: "Save assessment", exact: true }).click();
    await page.locator("#prepare-brief").waitFor();
    assert.equal(await page.evaluate((id) => localStorage.getItem(`wsd-notes-draft:${id}`), firstId), null);

    await page.getByRole("button", { name: "Explorer", exact: true }).click();
    const picker = page.getByLabel("Result set", { exact: true });
    await picker.waitFor();
    const different = await picker.locator("option").evaluateAll((options) => options.find((option) => option.value.startsWith("deu"))?.value);
    assert.ok(different, "Requires a separate result set");
    await picker.selectOption(different);
    await page.waitForFunction(() => document.querySelector(".result-summary strong")?.textContent.startsWith("deu"));
    assert.equal(await page.locator(".assessment-panel").count(), 0, "Explorer must not show notice assessment");
    assert.equal(await page.locator(".notice-span").count(), 0, "Explorer must not imply a notice focus");
    await page.goBack();
    await page.goBack();
    assert.equal(new URL(page.url()).searchParams.get("tab"), "notes", "Back restores section");
    await page.getByRole("tab", { name: "Overview", exact: true }).click();
    await page.getByRole("tab", { name: "Overview", exact: true }).press("ArrowRight");
    assert.equal(await page.getByRole("tab", { name: "Evidence", exact: true }).getAttribute("aria-selected"), "true");

    await page.getByRole("button", { name: "Operations", exact: true }).click();
    await page.getByLabel("Notice", { exact: true }).selectOption({ index: 1 });
    assert.equal(new URL(page.url()).searchParams.get("view"), "operations");
    await page.getByRole("button", { name: "Desk", exact: true }).click();
    await page.getByRole("tab", { name: "Overview", exact: true }).click();
    for (const width of [1024, 390, 360]) {
      await page.setViewportSize({ width, height: 844 });
      if (width < 700) {
        if (await page.locator(".alert-row").first().isVisible()) await page.locator(".alert-row").first().click();
        await page.getByRole("button", { name: "← Notices", exact: true }).click();
        await page.locator(".alert-row").first().click();
      }
      await page.locator(".product-hero").waitFor();
      await page.waitForFunction(() => {
        const element = document.querySelector(".notice-body");
        return element && element.scrollHeight > element.clientHeight;
      });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `No page overflow at ${width}px`);
      assert.ok((await body.boundingBox()).height > 300, `Readable detail height at ${width}px`);
      await body.evaluate((el) => el.scrollTop = 500);
      assert.ok(await body.evaluate((el) => el.scrollTop) > 0);
      await body.evaluate((el) => el.scrollTop = 0);
    }
    await page.emulateMedia({ colorScheme: "dark" });
    if (process.env.WSD_UI_SCREENSHOT) await page.screenshot({ path: process.env.WSD_UI_SCREENSHOT });
    assert.deepEqual(errors, [], "No browser runtime errors");
    console.log("PASS: layout, tabs, polling, drafts, reload, mocked save failure/success, Explorer isolation, back, keyboard, Operations and responsive widths.");
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
