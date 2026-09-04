const assert = require("node:assert/strict");
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    let saveMode = "conflict";
    let saved;
    await context.route("**/*", async (route) => {
      const req = route.request();
      if (["GET", "HEAD", "OPTIONS"].includes(req.method()) || req.url().endsWith("/api/scenario/validate")) return route.continue();
      if (req.url().endsWith("/api/scenario/save")) {
        saved = req.postDataJSON();
        return route.fulfill({ status: saveMode === "conflict" ? 409 : 200, contentType: "application/json", body: JSON.stringify(saveMode === "conflict" ?
          { detail: "Scenario changed on disk. Reload and reconcile your draft before saving" } :
          { scenario_id: saved.scenario, text: saved.text, revision: "test-revision", frozen: false, valid: true, warnings: [] }) });
      }
      return route.abort();
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (err) => { errors.push(err.message); console.error("Browser error:", err.message); });
    page.on("dialog", (dialog) => dialog.accept());
    await page.goto((process.env.WSD_UI_URL || "http://127.0.0.1:5173") + "/?view=scenarios&scenario=ukraine2022", { waitUntil: "networkidle" });
    await page.getByLabel("Research question", { exact: true }).waitFor();
    if (process.env.WSD_UI_SCREENSHOT) await page.screenshot({ path: process.env.WSD_UI_SCREENSHOT.replace(".png", "-editor.png") });
    const original = await page.getByLabel("Research question", { exact: true }).inputValue();
    const marker = "Browser-only scenario draft";
    await page.getByLabel("Research question", { exact: true }).fill(marker);
    await page.getByRole("button", { name: "Validate", exact: true }).click();
    await page.getByText("Scenario is valid.", { exact: false }).waitFor();
    await page.getByLabel("Scenario file").selectOption("deu2018quiet");
    await page.getByLabel("Research question", { exact: true }).waitFor();
    assert.notEqual(await page.getByLabel("Research question", { exact: true }).inputValue(), marker);
    await page.getByLabel("Scenario file").selectOption("ukraine2022");
    await page.getByLabel("Research question", { exact: true }).waitFor();
    assert.equal(await page.getByLabel("Research question", { exact: true }).inputValue(), marker);
    await page.reload({ waitUntil: "networkidle" });
    assert.equal(await page.getByLabel("Research question", { exact: true }).inputValue(), marker);
    await page.getByRole("button", { name: "Save scenario", exact: true }).click();
    await page.getByText("Scenario changed on disk.", { exact: false }).waitFor();
    assert.equal(await page.getByLabel("Research question", { exact: true }).inputValue(), marker);
    saveMode = "success";
    await page.getByRole("button", { name: "Save scenario", exact: true }).click();
    await page.getByText("Scenario saved.", { exact: false }).waitFor();
    assert.equal(saved.scenario, "ukraine2022");
    assert.equal(await page.evaluate(() => localStorage.getItem("wsd-scenario-draft:ukraine2022")), null);
    await page.getByRole("button", { name: "Advanced JSON", exact: true }).click();
    await page.getByLabel("Scenario JSON").fill('{"invalid":');
    await page.getByRole("button", { name: "Validate", exact: true }).click();
    await page.locator('.scenario-editor [role="alert"]').waitFor();
    assert.equal(await page.getByLabel("Scenario JSON").inputValue(), '{"invalid":');
    await page.getByRole("button", { name: "Discard draft", exact: true }).click();

    await page.getByRole("button", { name: "Collection artefacts", exact: true }).click();
    await page.getByRole("heading", { name: "Recorded collection gaps", exact: true }).waitFor();
    assert.ok(await page.locator(".gap-bars button").count() > 0);
    await page.locator(".gap-bars button").first().click();
    assert.equal(await page.locator(".gap-bars button").first().getAttribute("aria-pressed"), "true");
    await page.getByLabel("Find artefacts", { exact: true }).fill("collection-20260828T204613Z-6e2190/manifest.json");
    await page.locator(".artifact-file-list button").first().click();
    await page.getByRole("heading", { name: "Source coverage", exact: true }).waitFor();
    assert.ok(await page.locator("meter").count() > 0);
    if (process.env.WSD_UI_SCREENSHOT) await page.screenshot({ path: process.env.WSD_UI_SCREENSHOT.replace(".png", "-coverage.png") });
    await page.getByLabel("Find artefacts", { exact: true }).fill("collection-20260828T204613Z-6e2190/observations/viirs_incident");
    await page.locator(".artifact-file-list button").first().click();
    await page.getByLabel("Plot field", { exact: true }).waitFor();
    assert.ok(await page.locator(".artifact-detail svg").count() > 0);
    await page.getByText("Raw JSONL", { exact: false }).click();
    assert.ok(await page.locator(".artifact-raw pre").isVisible());
    const link = await page.getByRole("link", { name: "Download original", exact: true }).getAttribute("href");
    assert.ok(link.includes("viirs_incident"));
    for (const width of [1024, 390, 360]) {
      await page.setViewportSize({ width, height: 900 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `No overflow at ${width}px`);
    }
    await page.locator("main").evaluate((element) => element.scrollTop = 0);
    if (process.env.WSD_UI_SCREENSHOT) await page.screenshot({ path: process.env.WSD_UI_SCREENSHOT });
    const actual = await (await context.request.get("http://127.0.0.1:5173/api/scenario?scenario=ukraine2022")).json();
    assert.equal(JSON.parse(actual.text).research_question, original, "Real scenario must remain unchanged");
    assert.deepEqual(errors, []);
    console.log("PASS: scenario editing, validation, isolated/restored drafts, mocked conflict/save, real file unchanged, gaps, coverage, observations, raw access and responsive layouts.");
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
