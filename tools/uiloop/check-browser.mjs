// Run the real dashboard with the frozen data; no writes to data/ or external accounts.
import { chromium, firefox } from 'playwright';
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root = path.resolve('.');
const out = process.env.UILOOP_ARTIFACTS || path.join(process.env.HOME, 'scratch/spine-workstation/browser');
await mkdir(out, { recursive:true });
const server = createServer(async (req,res) => {
  const file = path.resolve(root, '.' + new URL(req.url, 'http://localhost').pathname.replace(/\/$/, '/index.html'));
  if (!file.startsWith(root + '/')) {res.writeHead(403).end();return;}
  try { const data=await readFile(file);res.setHeader('Content-Type', ({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.csv':'text/csv'})[path.extname(file)] || 'application/octet-stream');res.end(data); } catch {res.writeHead(404).end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base = `http://127.0.0.1:${server.address().port}/site/`;
let browser;
try {
  browser = await (process.env.UILOOP_BROWSER === 'chromium' ? chromium : firefox).launch();
  for (const width of [320,390,768,1440,1920]) for (const colorScheme of ['light','dark']) {
    const ctx=await browser.newContext({viewport:{width,height:width<=390?844:900},colorScheme,reducedMotion:'reduce'}),page=await ctx.newPage();
    page.setDefaultTimeout(15000);
    const errors=[];page.on('pageerror',e=>errors.push(String(e)));
    if (process.env.UILOOP_PLOTLY) await page.route('https://cdn.jsdelivr.net/npm/plotly.js-cartesian-dist-min@2.35.2/plotly-cartesian.min.js', route => route.fulfill({path:process.env.UILOOP_PLOTLY,contentType:'text/javascript'}));
    await page.goto(base+'?market=WETH&scenario=ABC#stress');
    await page.waitForFunction(()=>document.querySelector('#model-confidence')?.textContent.includes('hypothetical'));
    assert.equal(await page.locator('#selected-market').inputValue(),'WETH');
    assert.match(await page.locator('#brief-distance').textContent(),/%/);
    assert.match(await page.locator('#daily-changes').textContent(),/WETH/);
    assert.match(await page.locator('#market-title').textContent(),/^WETH/);
    assert.match(await page.locator('#supplier-exposure summary').textContent(),/WETH/);
    await page.locator('#selected-market').selectOption('cbXRP');
    await page.waitForFunction(()=>document.querySelector('#market-title').textContent.startsWith('cbXRP'));
    assert.equal(new URL(page.url()).searchParams.get('market'),'cbXRP');
    assert.match(await page.locator('#bt-market-buttons button.active').textContent(),/cbXRP/);
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('#market-title').textContent.startsWith('cbXRP'));
    assert.equal(await page.locator('#selected-market').inputValue(),'cbXRP');
    await page.goto(base+'?market=not-a-market&scenario=invalid&metric=invalid');
    await page.waitForFunction(()=>document.querySelector('#brief-worst')?.textContent.includes('end-of-path'));
    assert.equal(await page.locator('#selected-market').inputValue(),'cbBTC');
    assert.equal(new URL(page.url()).searchParams.get('scenario'),'AB');
    if (width === 390) assert.equal(await page.locator('#daily-changes .scroll-x').evaluate(el => el.scrollWidth <= el.clientWidth + 1), true, 'Daily change column fits on phones');
    await page.locator('#daily-changes').screenshot({path:path.join(out,`${width}-${colorScheme}-daily.png`)});
    await page.locator('#model-confidence').screenshot({path:path.join(out,`${width}-${colorScheme}-confidence.png`)});
    await page.locator('#selected-market').focus();
    assert.equal(await page.locator('#selected-market').evaluate(el => el === document.activeElement), true);
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('#market-title').textContent.startsWith('WETH'));
    assert.equal(new URL(page.url()).searchParams.get('market'), 'WETH');
    await page.locator('#selected-market').selectOption('cbBTC');
    await page.waitForFunction(() => document.querySelector('#market-title').textContent.startsWith('cbBTC'));
    await page.evaluate(() => scrollTo(0,0));
    assert.equal(await page.locator('.watchlist-table [data-market]').count(), 9);
    await page.locator('#filter-attention').click();
    assert.equal(new URL(page.url()).searchParams.get('filter'), 'attention');
    assert.ok(await page.locator('.watchlist-table [data-market]').count() < 9);
    await page.locator('#market-sort').selectOption('distance');
    assert.equal(new URL(page.url()).searchParams.get('sort'), 'distance');
    const first = page.locator('.watchlist-table [data-market]').first();
    const key = await first.getAttribute('data-market');
    await first.click();
    assert.equal(await page.locator('#selected-market').inputValue(), key);
    await page.goBack();
    await page.waitForFunction(() => document.querySelector('#selected-market').value === 'cbBTC');
    await page.locator('#filter-all').click();
    await page.locator('[data-shock="10"]').click();
    assert.match(await page.locator('#shock-result h3').textContent(), /10%/);
    await page.locator('[data-shock="30"]').click();
    assert.equal(new URL(page.url()).searchParams.get('shock'), '30');
    await page.goBack();
    await page.waitForFunction(() => document.querySelector('#shock-label').textContent === '10%');
    await page.locator('#theme-choice').selectOption('dark');
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#brief-worst')?.textContent.includes('end-of-path'));
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
    await page.locator('#theme-choice').selectOption('system');
    await page.locator('#copy-view').click();
    await page.waitForFunction(() => document.querySelector('#copy-feedback').textContent.length > 0);
    await page.locator('#check-address').fill('invalid');
    await page.locator('#check-form button').click();
    assert.equal(await page.locator('#check-address').getAttribute('aria-invalid'), 'true');
    assert.match(await page.locator('#check-result').textContent(), /40 hex characters/);
    assert.equal(await page.locator('#check-form button').isDisabled(), false);
    await page.evaluate(() => scrollTo(0,0));
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    assert.equal(overflow,false,'No horizontal page overflow');
    const fold=await page.locator('#brief-worst').boundingBox();
    // Fixture data is stale: its visible stale banner is intentionally part of the first screen.
    if (width === 390) assert.ok(fold.y+fold.height<=844,'All three briefing answers fit the first screen');
    const height=await page.evaluate(()=>document.documentElement.scrollHeight);
    for(let y=0;y<height;y+=700){await page.evaluate(y=>scrollTo(0,y),y);await page.waitForTimeout(75);}
    let charts;
    try {await page.waitForFunction(()=>[...document.querySelectorAll('.chart')].every(el=>el.querySelector('svg')),null,{timeout:20000});charts=true;}catch{charts=false;}
    await page.evaluate(()=>scrollTo(0,0));
    let screenshot=true;
    try{await page.screenshot({path:path.join(out,`${width}-${colorScheme}.png`),timeout:5000});}catch{screenshot=false;}
    assert.deepEqual(errors,[]);
    assert.equal(charts,true,'Every chart rendered');
    assert.equal(screenshot,true,'Screenshot captured');
    console.log(JSON.stringify({width,colorScheme,behavior:'passed',charts,screenshot}));
    await writeFile(path.join(out,`${width}-${colorScheme}.json`),JSON.stringify({width,colorScheme,behavior:'passed',charts,screenshot,errors},null,2));
    await ctx.close();
  }
  // Missing sources remain truthful, and a failed chart download retains its data table.
  for (const missing of ['summary.json', 'history.csv', 'backtest.json', 'plotly']) {
    const ctx = await browser.newContext(), page = await ctx.newPage(), errors = [];
    page.setDefaultTimeout(15000);
    page.on('pageerror', e => errors.push(String(e)));
    if (missing === 'plotly') await page.route('**/plotly-cartesian.min.js', route => route.abort());
    else await page.route('**/data/' + missing, route => route.fulfill({status:503,body:'unavailable'}));
    await page.goto(base);
    if (missing === 'summary.json') {
      await page.waitForFunction(() => document.querySelector('#retry-data') != null);
      assert.equal(await page.locator('#selected-market').isDisabled(), true);
      assert.deepEqual(errors, []);
      console.log(JSON.stringify({failureState:missing,result:'passed'}));
      await ctx.close();
      continue;
    }
    await page.waitForFunction(() => document.querySelector('#brief-borrow')?.textContent.includes('$'));
    if (missing === 'history.csv') {
      await page.waitForFunction(() => document.querySelector('#daily-changes').textContent.includes('unavailable'));
    } else if (missing === 'backtest.json') {
      await page.waitForFunction(() => document.querySelector('#model-confidence').textContent.includes('unavailable'));
      assert.match(await page.locator('#brief-worst').textContent(), /Unavailable/);
    } else {
      await page.locator('#chart-ltv').scrollIntoViewIfNeeded();
      await page.waitForFunction(() => document.querySelector('#chart-ltv').textContent.includes('Chart unavailable'));
      await page.locator('[aria-controls="chart-ltv-table"]').click();
      assert.equal(await page.locator('#chart-ltv-table').isVisible(), true);
    }
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({failureState:missing,result:'passed'}));
    await ctx.close();
  }
} finally {if(browser)await browser.close();await new Promise(r=>server.close(r));}
