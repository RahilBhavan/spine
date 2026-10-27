import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import path from 'node:path';

export const RUN_TAGS = ['phone-light', 'phone-dark', 'desktop-light', 'desktop-dark'];
export const REVIEW_QUESTIONS = ['risk', 'change', 'assumptions'];
export const hash = bytes => createHash('sha256').update(bytes).digest('hex');

export function renderFailures(report, dir) {
  const failures = [];
  if (report.schemaVersion !== 2) failures.push('Rebaseline with the current scorer (schema 2)');
  if (report.runs?.length !== 4 || new Set(report.runs.map(r => r.tag)).size !== 4) failures.push('Four distinct viewport/theme runs required');
  for (const tag of RUN_TAGS) {
    const r = report.runs?.find(r => r.tag === tag);
    if (!r) { failures.push(`${tag}: missing run`); continue; }
    if (r.errors.length) failures.push(`${tag}: console/page errors`);
    if (r.emptyCharts.length) failures.push(`${tag}: charts did not render: ${r.emptyCharts.join(', ')}`);
    if (r.shots !== true) failures.push(`${tag}: screenshots missing`);
    for (const suffix of ['fold', 'full']) {
      const file = `${tag}-${suffix}.png`;
      try {
        const bytes = readFileSync(path.join(dir, file));
        if (bytes.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a' || hash(bytes) !== r.screenshotHashes?.[file]) failures.push(`${file}: screenshot hash mismatch`);
      } catch { failures.push(`${file}: unreadable screenshot`); }
    }
  }
  return failures;
}

export function comprehensionFailures(review, metricsBytes) {
  if (!review) return ['Reader review required in review.json'];
  const failures = [];
  if (review.metricsSha256 !== hash(metricsBytes)) failures.push('Reader review is for different metrics');
  if (!review.reviewer?.trim() || !review.reviewedAt || !Number.isFinite(Date.parse(review.reviewedAt))) failures.push('Named and dated reader review required');
  for (const key of REVIEW_QUESTIONS) {
    const answer = review.answers?.[key];
    if (answer?.pass !== true || !answer.response?.trim() || !answer.evidence?.trim()) failures.push(`Reader question ${key}: record a correct response and evidence`);
  }
  return failures;
}
