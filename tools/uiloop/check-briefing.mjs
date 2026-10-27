// Behavioral checks use the same public functions as the browser, with no network.
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import vm from 'node:vm';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { comprehensionFailures, hash, renderFailures } from './gates.mjs';
const ctx = vm.createContext({ usd: v => '$' + v, WINDOWS: ['a', 'b'], todayRow: (bt, key, w) => bt[w] });
vm.runInContext(readFileSync('site/briefing.js', 'utf8'), ctx);
const rows = [
  { market: 'cbBTC', utc_ts: '2026-10-24T23:00:00Z', borrow_usd: 100 },
  { market: 'cbBTC', utc_ts: '2026-10-25T01:00:00Z', borrow_usd: 110 },
  { market: 'WETH', utc_ts: '2026-10-25T00:00:00Z', borrow_usd: 20 },
  { market: 'cbBTC', utc_ts: '2026-10-26T00:00:00Z', borrow_usd: 120 },
];
assert.equal(ctx.dailyBaseline(rows, 'cbBTC', '2026-10-26T00:00:00Z').borrow_usd, 100);
assert.equal(ctx.dailyBaseline(rows, 'WETH', '2026-10-26T00:00:00Z').borrow_usd, 20);
assert.equal(ctx.dailyBaseline(rows, 'cbBTC', '2026-10-30T00:00:00Z'), null);
assert.equal(ctx.dailyBaseline(rows, 'SOL', '2026-10-26T00:00:00Z'), null);
assert.equal(ctx.deltaText(null, 0.5, 'points'), 'Not comparable');
assert.equal(ctx.deltaText(0.11, 0.12, 'points'), '−1.0 pp');
assert.equal(ctx.deltaText(0.11, 0.1, 'points'), '+1.0 pp');
assert.equal(ctx.deltaText(0, 0, 'money'), 'No change');
assert.equal(ctx.deltaText(110, 100, 'money'), '+$10');
assert.equal(ctx.worstReplay({a:{v:1},b:{v:3}}, 'cbBTC', r=>r.v).v, 3);
assert.equal(ctx.worstReplay({}, 'cbBTC', r=>r.v), null);
assert.ok(renderFailures({schemaVersion:1,runs:[]}, '/missing').length);
assert.ok(comprehensionFailures(null, 'bytes').length);
const review = { metricsSha256: hash('bytes'), reviewer:'Test reader', reviewedAt:'2026-10-26', answers:Object.fromEntries(['risk','change','assumptions'].map(k=>[k,{pass:true,response:'Recorded response',evidence:'Checked source'}])) };
assert.deepEqual(comprehensionFailures(review, 'bytes'), []);
assert.ok(comprehensionFailures(review, 'different artifact').length);
review.answers.risk.pass=false;
assert.ok(comprehensionFailures(review, 'bytes').length);
const dir = mkdtempSync(path.join(os.tmpdir(), 'spine-gates-'));
try {
  const png = Buffer.from('89504e470d0a1a0a', 'hex');
  const report = {schemaVersion:2,runs:['phone-light','phone-dark','desktop-light','desktop-dark'].map(tag=>({tag,errors:[],emptyCharts:[],shots:true,screenshotHashes:{}}))};
  for (const r of report.runs) for (const suffix of ['fold','full']) {
    const name = `${r.tag}-${suffix}.png`;
    writeFileSync(path.join(dir,name),png);
    r.screenshotHashes[name]=hash(png);
  }
  assert.deepEqual(renderFailures(report,dir),[]);
  report.runs[0].emptyCharts=['chart-ltv'];
  assert.ok(renderFailures(report,dir).some(f=>f.includes('charts did not render')));
  report.runs[0].emptyCharts=[];
  report.runs[0].shots=false;
  assert.ok(renderFailures(report,dir).some(f=>f.includes('screenshots missing')));
  report.runs[0].shots=true;
  writeFileSync(path.join(dir,'phone-light-fold.png'),'changed');
  assert.ok(renderFailures(report,dir).some(f=>f.includes('hash mismatch')));
} finally { rmSync(dir,{recursive:true,force:true}); }
console.log('20 briefing and acceptance checks passed');
