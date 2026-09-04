const assert = require("node:assert/strict");
const { chromium } = require("playwright");

// No real collection, generation or report writes: every POST is mocked or blocked.
(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    let requests = 0;
    await context.route("**/*", (route) => {
      const req = route.request();
      if (["GET", "HEAD", "OPTIONS"].includes(req.method())) return route.continue();
      if (req.url().endsWith("/api/packet/draft")) {
        requests += 1;
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
          notes: `Mock machine draft ${requests}`, provider: "ollama", model: "mock", leakage: [], votes: false,
        }) });
      }
      return route.abort();
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(process.env.WSD_UI_URL || "http://127.0.0.1:5173", { waitUntil: "networkidle" });
    await page.getByRole("tab", { name: "Notes & assessment", exact: true }).click();
    await page.getByRole("button", { name: /^(Edit|Write) assessment$/ }).click();
    const editor = page.getByLabel("Your notes and assessment", { exact: true });
    await editor.fill("My unsaved assessment");
    await page.getByRole("button", { name: "Machine draft", exact: true }).click();
    await page.getByRole("heading", { name: "Machine draft ready for review" }).waitFor();
    assert.equal(await editor.inputValue(), "My unsaved assessment");
    page.once("dialog", (dialog) => dialog.dismiss());
    await page.getByRole("button", { name: "Use machine draft", exact: true }).click();
    assert.equal(await editor.inputValue(), "My unsaved assessment");
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Use machine draft", exact: true }).click();
    assert.equal(await editor.inputValue(), "Mock machine draft 1");
    await editor.fill("Human revision of draft");
    await page.locator(".alert-row").nth(1).click();
    await page.locator(".alert-row").first().click();
    assert.equal(await editor.inputValue(), "Human revision of draft", "Remount must not reapply seed");
    await page.getByRole("button", { name: "Machine draft", exact: true }).click();
    await page.getByRole("heading", { name: "Machine draft ready for review" }).waitFor();
    await page.getByRole("button", { name: "Keep my assessment", exact: true }).click();
    assert.equal(await editor.inputValue(), "Human revision of draft");
    assert.equal(requests, 2);
    assert.deepEqual(errors, []);
    console.log("PASS: generated drafts never silently replace analyst text; confirmation, dismissal and notice remount preserve edits.");
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
