// Browser regression: all workflow writes are mocked; no model calls or saved-data changes.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    let workflow, complete, requests = 0;
    await page.route('**/api/analyst-workflow?*', async route => {
      if (!workflow) {
        const response = await route.fetch();
        workflow = await response.json();
        workflow.preparing = false;
        workflow.brief_progress = null;
      }
      await route.fulfill({ json: workflow });
    });
    await page.route('**/api/analyst-workflow', async route => {
      assert.equal(route.request().postDataJSON().action, 'prepare');
      requests++;
      await new Promise(resolve => { complete = resolve; });
      if (requests === 1) return route.fulfill({ status: 400, json: { detail: 'Test: model unavailable. Existing briefs retained.' } });
      workflow = { ...workflow, revision: workflow.revision + 1, briefs: [...workflow.briefs,
        { version: 99, title: 'Browser test brief', body: 'Test body', markdown: 'Browser test brief and annex', created_at: new Date().toISOString(), stale: false }] };
      await route.fulfill({ json: workflow });
    });
    await page.route('**/api/report?*', async route => {
      const response = await route.fetch();
      const report = await response.json();
      await route.fulfill({ json: { ...report, empty: false, notes: 'Saved assessment for browser verification.' } });
    });
    await page.goto((process.env.WSD_UI_URL || 'http://127.0.0.1:5173') + '/?view=notices&tab=notes&scenario=ukraine2022&notice=notice-8f9869999a00', { waitUntil: 'networkidle' });
    assert.equal(await page.locator('.notice-header .primary-action').count(), 0, 'Header must not duplicate tab navigation as commands');
    await page.getByRole('button', { name: /4\s*Intelligence brief/ }).click();
    assert.ok(await page.locator('#prepare-brief').isVisible());
    assert.equal(await page.locator('#review-proposals').isVisible(), false);
    const prepare = page.getByRole('button', { name: 'Prepare new brief version', exact: true });
    await prepare.click();
    await page.getByRole('heading', { name: 'Preparing intelligence brief', exact: true }).waitFor();
    await page.getByRole('progressbar').waitFor();
    assert.ok(await page.getByRole('button', { name: 'Model is drafting the brief…', exact: true }).isDisabled());
    await page.getByRole('button', { name: /1\s*Review findings/ }).click();
    assert.ok(await page.getByRole('progressbar').isVisible(), 'Preparation remains visible in another step');
    complete();
    await page.getByRole('alert').filter({ hasText: 'Test: model unavailable' }).waitFor();
    await page.waitForTimeout(9000);
    assert.ok(await page.getByRole('alert').filter({ hasText: 'Test: model unavailable' }).isVisible(), 'Background refresh must not erase action failure');
    await page.getByRole('button', { name: /4\s*Intelligence brief/ }).click();
    await prepare.click();
    await page.waitForFunction(() => !!document.querySelector('progress'));
    while (requests < 2) await page.waitForTimeout(20);
    complete();
    await page.getByText('Brief version 99 is ready for review.', { exact: false }).waitFor();
    assert.ok(await page.getByText('Test body', { exact: true }).isVisible());
    assert.equal(await page.getByText('Browser test brief and annex', { exact: true }).count(), 0);
    assert.equal(requests, 2, 'Only explicit clicks start preparation');
    for (const width of [1440, 1024, 390, 360]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `No overflow at ${width}`);
      assert.ok(await page.locator('#prepare-brief').isVisible());
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.emulateMedia({ colorScheme: 'dark' });
    if (process.env.WSD_UI_SCREENSHOT) await page.screenshot({ path: process.env.WSD_UI_SCREENSHOT });
    assert.deepEqual(errors, []);
    console.log('PASS: distinct navigation, visible preparation across steps, failure, retry, new-version preview, responsive layout. No backend writes.');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
