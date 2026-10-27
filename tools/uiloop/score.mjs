// Scores the dashboard for the UI hill-climbing loop (tools/uiloop/README.md).
// Usage: node tools/uiloop/score.mjs <out-dir>
// Serves the repo root, loads /site/ at phone and desktop widths in light and dark mode,
// writes screenshots, metrics.json and a penalty (lower is better) to <out-dir>.
import { chromium, firefox } from 'playwright';
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { hash } from './gates.mjs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const AXE_SRC = readFileSync(createRequire(import.meta.url).resolve('axe-core/axe.min.js'), 'utf8');
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const OUT = path.resolve(process.argv[2] || 'uiloop-out');
const PORT = 8700 + Math.floor(Math.random() * 200);
const VIEWPORTS = [
  { name: 'phone', width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
  { name: 'desktop', width: 1440, height: 900, deviceScaleFactor: 1 },
];
const SCHEMES = ['light', 'dark'];
const IMPACT = { critical: 10, serious: 5, moderate: 2, minor: 1 };

// Penalty weights: one unit is roughly one small, real defect a visitor could hit.
const WEIGHTS = {
  axe: 1,            // impact-weighted axe nodes, capped per rule
  contrast: 2,       // distinct text/background pairs under WCAG AA (axe's own rule hangs on this page)
  overflowPx: 0.05,  // page wider than the viewport, per pixel
  clipped: 2,        // text elements wider than their own box
  smallTargets: 0.5, // controls under 24x24 CSS px (WCAG 2.5.8), inline text links exempt
  tinyText: 0.2,     // visible text elements under 12px
  longLines: 0.5,    // paragraphs set wider than 90 characters
  foldMiss: 4,       // headline answers below the first screen, scaled by distance
  cls: 20,           // cumulative layout shift
  emptyCharts: 5,    // chart containers still empty after load
  errors: 10,        // console and page errors
};

const server = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], { cwd: ROOT, stdio: 'ignore' });
await new Promise(r => setTimeout(r, 600));
mkdirSync(OUT, { recursive: true });
const engine = process.env.UILOOP_BROWSER || 'firefox';
if (!['firefox', 'chromium'].includes(engine)) throw new Error('UILOOP_BROWSER must be firefox or chromium');
let browser;
const runs = [];

try {
  browser = await ({ firefox, chromium })[engine].launch();
  for (const vp of VIEWPORTS) for (const scheme of SCHEMES) runs.push(await scoreOne(vp, scheme));
} finally {
  if (browser) await browser.close();
  server.kill();
}

const total = {};
for (const r of runs) for (const [k, v] of Object.entries(r.penalty)) total[k] = (total[k] || 0) + v;
const penalty = Object.values(total).reduce((a, b) => a + b, 0);
const sourceHashes = Object.fromEntries(readdirSync(path.join(ROOT, 'site')).filter(f => /\.(html|css|js)$/.test(f)).map(f => ['site/' + f, hash(readFileSync(path.join(ROOT, 'site', f)))]));
const report = { schemaVersion: 2, browser: engine, sourceHashes, penalty: +penalty.toFixed(2), byTerm: roundAll(total), runs };
writeFileSync(path.join(OUT, 'metrics.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify({ penalty: report.penalty, byTerm: report.byTerm }, null, 2));

function step(s) { if (process.env.UILOOP_DEBUG) console.error(new Date().toISOString().slice(17, 23), s); }
async function scoreOne(vp, scheme) {
  const tag = `${vp.name}-${scheme}`;
  const ctx = await browser.newContext({ ...vp, viewport: { width: vp.width, height: vp.height }, colorScheme: scheme, reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  page.setDefaultTimeout(180000);
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push(String(e)));
  await page.addInitScript(() => {
    window.__cls = 0;
    new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
      .observe({ type: 'layout-shift', buffered: true });
  });

  const t0 = Date.now();
  await page.goto(`http://127.0.0.1:${PORT}/site/`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => {
    const el = document.getElementById('hero-borrow');
    return el && el.textContent.trim() && el.textContent.trim() !== '-';
  }, null, { timeout: 60000 }).catch(() => {});
  const answerMs = Date.now() - t0;
  step(`${tag} answer`);
  await page.waitForLoadState('networkidle', { timeout: 60000 }).catch(() => {});
  // Charts draw lazily as they near the viewport, so walk the page once, then return to the top.
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y < height; y += vp.height / 2) { await page.evaluate(y => scrollTo(0, y), y); await page.waitForTimeout(250); }
  await page.waitForLoadState('networkidle', { timeout: 60000 }).catch(() => {});
  await page.evaluate(() => scrollTo(0, 0));
  await page.waitForTimeout(800);
  step(`${tag} settled`);

  const m = await page.evaluate(() => {
    const vw = innerWidth, vh = innerHeight;
    const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
    const overflowPx = Math.max(0, document.documentElement.scrollWidth - vw);

    const small = [];
    for (const el of document.querySelectorAll('a[href], button, input, select, summary, label.toggle')) {
      if (!visible(el) || el.closest('.js-plotly-plot')) continue;
      if (el.tagName === 'A' && el.closest('p, dd, li, td, footer') && !el.closest('nav')) continue; // inline links are exempt
      if (el.tagName === 'INPUT' && el.closest('label')) continue; // the wrapping label is the target, measured on its own
      const r = el.getBoundingClientRect();
      if (r.width < 24 || r.height < 24) small.push(`${el.tagName.toLowerCase()}#${el.id || ''}.${el.className || ''} "${(el.textContent || el.value || '').trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
    }

    const tiny = [];
    for (const el of document.querySelectorAll('body *')) {
      if (el.closest('svg, .js-plotly-plot') || !visible(el)) continue;
      const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
      if (own && parseFloat(getComputedStyle(el).fontSize) < 12) tiny.push(`${el.tagName.toLowerCase()} "${el.textContent.trim().slice(0, 30)}"`);
    }

    const long = [];
    for (const p of document.querySelectorAll('p, dd, li')) {
      if (!visible(p) || p.textContent.trim().length < 120) continue;
      const fs = parseFloat(getComputedStyle(p).fontSize);
      const chars = p.clientWidth / (fs * 0.5);
      if (chars > 90) long.push(`${p.tagName.toLowerCase()} ${Math.round(chars)}ch "${p.textContent.trim().slice(0, 30)}"`);
    }

    const answers = ['#brief-borrow', '#brief-distance', '#brief-worst'].map(sel => {
      const el = document.querySelector(sel); if (!el) return { sel, top: null };
      return { sel, top: Math.round(el.getBoundingClientRect().top + scrollY) };
    });
    // Each headline answer costs up to 1 by how far it sits below the first screen, so compaction is rewarded before it fully lands.
    const foldMiss = answers.reduce((s, a) => s + (a.top === null ? 1 : Math.min(1, Math.max(0, a.top - (vh - 40)) / vh)), 0);
    const emptyCharts = [...document.querySelectorAll('.chart')].filter(c => visible(c) && !c.querySelector('svg')).map(c => c.id);
    const keyText = [...document.querySelectorAll('.hero, .card .value, #worst-sentence, #distance-sentence, #brief-borrow, #brief-distance, #brief-worst, .briefing-date')].map(e => e.textContent.trim());
    // Text contrast: own text colour against the nearest opaque background behind it.
    const rgba = c => { const v = c.match(/[\d.]+/g).map(Number); return { r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1 }; };
    const over = (top, bot) => ({ r: top.r * top.a + bot.r * (1 - top.a), g: top.g * top.a + bot.g * (1 - top.a), b: top.b * top.a + bot.b * (1 - top.a), a: 1 });
    const bgOf = el => {
      const layers = [];
      for (let e = el; e; e = e.parentElement) { const c = rgba(getComputedStyle(e).backgroundColor); if (c.a > 0) { layers.push(c); if (c.a >= 1) break; } }
      let bg = { r: 255, g: 255, b: 255, a: 1 };
      if (!layers.length || layers[layers.length - 1].a < 1) bg = matchMedia('(prefers-color-scheme: dark)').matches ? { r: 0, g: 0, b: 0, a: 1 } : bg;
      for (const l of layers.reverse()) bg = over(l, bg);
      return bg;
    };
    const lum = c => { const f = x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
    const pairs = new Map();
    for (const el of document.querySelectorAll('body *')) {
      if (el.closest('svg, .js-plotly-plot, .sr-only') || !visible(el)) continue;
      if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
      const st = getComputedStyle(el), bg = bgOf(el), fg = over(rgba(st.color), bg);
      const l1 = lum(fg), l2 = lum(bg), ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
      const size = parseFloat(st.fontSize), large = size >= 24 || (size >= 18.66 && +st.fontWeight >= 700);
      if (ratio < (large ? 3 : 4.5)) {
        const key = `${st.color} on ${JSON.stringify(bg)} ${large ? 'large' : 'body'}`;
        if (!pairs.has(key)) pairs.set(key, `${ratio.toFixed(2)} ${el.tagName.toLowerCase()}.${el.className} "${el.textContent.trim().slice(0, 30)}"`);
      }
    }
    const contrast = [...pairs.values()];
    // Text wider than its own box (a long word in a narrow card) spills over its neighbours; scroll regions are exempt.
    const clipped = [];
    for (const el of document.querySelectorAll('body *')) {
      if (el.closest('svg, .js-plotly-plot, .scroll-x, nav, .sr-only') || !visible(el)) continue;
      if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
      if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).display !== 'inline') clipped.push(`${el.tagName.toLowerCase()}.${el.className} "${el.textContent.trim().slice(0, 30)}" ${el.scrollWidth}>${el.clientWidth}`);
    }
    return { contrast, clipped, overflowPx, small, tiny, long, answers, foldMiss, emptyCharts, keyText, cls: window.__cls, docHeight: document.documentElement.scrollHeight };
  });

  step(`${tag} metrics`);
  // axe.run directly: the @axe-core/playwright wrapper stalls on this page, and so does axe's color-contrast rule.
  await page.evaluate(AXE_SRC);
  let axeTimer;
  const axeViolations = await Promise.race([
    page.evaluate(async () => {
      const r = await axe.run({ exclude: [['.js-plotly-plot']] }, {
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa', 'best-practice'] },
        rules: { 'color-contrast': { enabled: false } }, resultTypes: ['violations'],
      });
      return r.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, sample: v.nodes.slice(0, 3).map(n => n.target.join(' ')) }));
    }),
    new Promise((_, fail) => { axeTimer = setTimeout(() => fail(new Error(`${tag}: axe took over 120 s`)), 120000); }),
  ]).finally(() => clearTimeout(axeTimer));
  const axeScore = axeViolations.reduce((s, v) => s + (IMPACT[v.impact] || 1) * Math.min(v.nodes, 5), 0);

  step(`${tag} axe`);
  // Missing frame capture is a hard acceptance failure, never a constant penalty to ignore.
  const shots = await page.screenshot({ path: path.join(OUT, `${tag}-fold.png`), timeout: 15000 })
    .then(() => page.screenshot({ path: path.join(OUT, `${tag}-full.png`), fullPage: true, timeout: 30000 }))
    .then(() => true, () => false);
  const screenshotHashes = {};
  if (shots) for (const suffix of ['fold', 'full']) {
    const name = `${tag}-${suffix}.png`;
    screenshotHashes[name] = hash(readFileSync(path.join(OUT, name)));
  }
  await ctx.close();

  const penalty = {
    axe: WEIGHTS.axe * axeScore,
    contrast: WEIGHTS.contrast * m.contrast.length,
    overflowPx: WEIGHTS.overflowPx * m.overflowPx,
    clipped: WEIGHTS.clipped * m.clipped.length,
    smallTargets: WEIGHTS.smallTargets * m.small.length,
    tinyText: WEIGHTS.tinyText * m.tiny.length,
    longLines: WEIGHTS.longLines * m.long.length,
    foldMiss: WEIGHTS.foldMiss * m.foldMiss,
    cls: WEIGHTS.cls * m.cls,
    emptyCharts: WEIGHTS.emptyCharts * m.emptyCharts.length,
    errors: WEIGHTS.errors * errors.length,
  };
  return { tag, shots, screenshotHashes, answerMs, errors, axeViolations, ...m, penalty: roundAll(penalty) };
}

function roundAll(o) { return Object.fromEntries(Object.entries(o).map(([k, v]) => [k, +v.toFixed(2)])); }
