// A score can nominate a candidate; rendered evidence and a reader review accept it.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { renderFailures, comprehensionFailures } from './gates.mjs';

const [bestDir, candDir] = process.argv.slice(2);
const read = d => readFileSync(path.join(d, 'metrics.json'));
const best = JSON.parse(read(bestDir)), bytes = read(candDir), cand = JSON.parse(bytes);
const fails = renderFailures(cand, candDir);
if (best.browser !== cand.browser) fails.push('Baseline and candidate must use the same browser');
if (best.schemaVersion !== 2) fails.push('Baseline uses an old scoring contract; create a new baseline');
for (const c of cand.runs) {
  const b = best.runs.find(r => r.tag === c.tag);
  if (!b) { fails.push(`${c.tag}: absent from baseline`); continue; }
  if (JSON.stringify(c.keyText) !== JSON.stringify(b.keyText)) fails.push(`${c.tag}: headline evidence changed; review and explicitly rebaseline intentional content changes`);
}
const terms = new Set([...Object.keys(best.byTerm), ...Object.keys(cand.byTerm)]);
const delta = Object.fromEntries([...terms].map(t => [t, +((cand.byTerm[t] || 0) - (best.byTerm[t] || 0)).toFixed(2)]).filter(([, d]) => d));
const diff = +(cand.penalty - best.penalty).toFixed(2);
let review = null;
try { review = JSON.parse(readFileSync(path.join(candDir, 'review.json'), 'utf8')); } catch {}
const pending = comprehensionFailures(review, bytes);
const verdict = fails.length || diff > 0 ? 'REJECT' : pending.length ? 'REVIEW' : 'ACCEPT';
console.log(JSON.stringify({ verdict, best: best.penalty, candidate: cand.penalty, diff, delta, fails, pending }, null, 2));
process.exit(verdict === 'REJECT' ? 1 : 0);
