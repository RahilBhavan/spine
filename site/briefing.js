'use strict';

// Compare with the nearest saved snapshot to 24 h before the displayed book, within 6 h.
// Anchor to the data timestamp, so a stale book never appears to describe today's change.
function dailyBaseline(rows, key, asOf) {
  const now = Date.parse(asOf), target = now - 864e5;
  return rows.filter(r => r.market === key && Date.parse(r.utc_ts) < now && Math.abs(Date.parse(r.utc_ts) - target) <= 216e5)
    .sort((a, b) => Math.abs(Date.parse(a.utc_ts) - target) - Math.abs(Date.parse(b.utc_ts) - target))[0] || null;
}

function deltaText(current, previous, kind) {
  if (current == null || previous == null) return 'Not comparable';
  const d = current - previous;
  if (Math.abs(d) < (kind === 'points' ? 0.00005 : 0.5)) return 'No change';
  return (d > 0 ? '+' : '−') + (kind === 'points' ? (Math.abs(d) * 100).toFixed(1) + ' pp' : usd(Math.abs(d)));
}

function worstReplay(bt, key, metric) {
  return WINDOWS.map(w => todayRow(bt, key, w)).filter(Boolean)
    .sort((a, b) => metric(b) - metric(a))[0] || null;
}

function renderBriefing() {
  const el = document.getElementById('risk-briefing');
  if (!el || !DATA) return;
  const s = DATA.markets[market].state, d = s.distance_to_capacity;
  const loss = BT && worstReplay(BT, market, METRICS['Loss by end of path']);
  const trough = BT && worstReplay(BT, market, METRICS['Exposure at trough']);
  const lossText = loss ? usd(METRICS['Loss by end of path'](loss)) : 'Unavailable';
  const exposure = trough ? usd(METRICS['Exposure at trough'](trough)) : 'Unavailable';
  el.innerHTML = '<dl class="briefing-rows">' +
    '<div><dt>Observed book · all nine markets</dt><dd><strong id="brief-borrow">' + usd(DATA.totals.borrow_usd) + '</strong> borrowed <a href="#book">Explore positions →</a></dd></div>' +
    '<div><dt>Modeled capacity threshold · ' + market + '</dt><dd><strong id="brief-distance">' + (d == null ? '>70%' : pct(d, 0)) + '</strong> price fall to exceed capacity · ' + band(d)[3] + ' <a href="#liquidations">Inspect capacity →</a></dd></div>' +
    '<div><dt>Worst replay · ' + market + ' · AB</dt><dd id="brief-worst"><strong>' + lossText + '</strong> end-of-path loss' + (loss ? ' (' + loss.window + ')' : '') +
    '<span class="brief-exposure">' + exposure + ' underwater at trough' + (trough ? ' (' + trough.window + ')' : '') + ' · separate measure</span> <a href="#stress">Review stress assumptions →</a></dd></div></dl>' +
    '<p class="muted briefing-date">Book: ' + utc(Date.parse(DATA.generated_at)) + '. ' + (BT ? 'Replay book: ' + esc(BT.latest_book) + '; historical scenarios, not forecasts.' : 'Replay loading or unavailable.') + '</p>';
}

function renderDailyChanges() {
  const el = document.getElementById('daily-changes');
  if (!el || HIST == null) return;
  const before = dailyBaseline(HIST, market, DATA.generated_at), s = DATA.markets[market].state;
  if (!before) {
    el.innerHTML = '<h3>Change over roughly 24 hours · ' + market + '</h3><p class="muted">No saved snapshot within 6 hours of the prior-day comparison time. Daily changes are unavailable for this book.</p>';
    return;
  }
  const entries = [['Borrowed', s.borrow_usd, before.borrow_usd, 'money'], ['Stressed capacity', s.capacity_ab_usd, before.capacity_ab_usd, 'money'], ['Price fall to capacity', s.distance_to_capacity, before.distance_to_capacity, 'points']];
  const cell = (v, kind) => kind === 'points' ? v == null ? '>70%' : pct(v, 0) : usd(v);
  el.innerHTML = '<h3>Change over roughly 24 hours · ' + market + '</h3><p class="muted">' + utc(Date.parse(before.utc_ts)) + ' → ' + utc(Date.parse(DATA.generated_at)) + '. Capacity and distance are model estimates; pp means percentage points.</p>' +
    '<div class="scroll-x" tabindex="0" role="region" aria-label="Daily market comparison"><table><thead><tr><th scope="col">Measure</th><th scope="col">Prior</th><th scope="col">Book snapshot</th><th scope="col">Change</th></tr></thead><tbody>' +
    entries.map(([name, current, prior, kind]) => '<tr><th scope="row">' + name + '</th><td>' + cell(prior, kind) + '</td><td>' + cell(current, kind) + '</td><td>' + deltaText(current, prior, kind) + '</td></tr>').join('') + '</tbody></table></div>' +
    '<p class="muted">A smaller price-fall threshold means less room before capacity is exceeded. Capacity combines market depth and stress assumptions; its change is not a measurement of depth alone.</p>';
}

function renderConfidence(bt) {
  const el = document.getElementById('model-confidence');
  if (!bt) { el.textContent = 'Replay unavailable. Current book observations remain available above.'; return; }
  const c = bt.calibrated || {}, held = (c.held_out_cbBTC || []).map(k => c.ratios[k]).filter(Number.isFinite);
  el.innerHTML = '<p><b>Modeled estimate · modest confidence.</b> Replay book: ' + esc(bt.latest_book) + '; run: ' + utc(bt.generated_at * 1000) + '. Current observations above use a separate snapshot.</p>' +
    '<p>Heatmap scenario ' + btScenario + ': ' + ({A: 'on-chain liquidators only.', AB: 'on-chain and exchange-hedged liquidators, with limited daily capital.', ABC: 'hypothetical Coinbase backstop; unlimited disposal depth is an assumption, not a committed facility.'})[btScenario] + '</p>' +
    '<details><summary>Assumptions and validation limits</summary><p>Borrower response: ' + pct(c.resp_share, 0) + ' within ' + c.react_min + ' minutes. Depth retained: DEX ' + pct(bt.defaults.k_dex, 0) + ', CEX ' + pct(bt.defaults.k_cex, 0) + '. Exchange-liquidator daily capital: ' + usd(bt.cexCap) + '.</p>' +
    '<p>' + (held.length ? 'Across ' + held.length + ' held-out cbBTC events, simulated/observed liquidation volume ranges from ' + Math.min(...held).toFixed(2) + '× to ' + Math.max(...held).toFixed(2) + '×. This is a validation range, not a loss confidence interval. ' : 'Held-out validation is unavailable in this dataset. ') +
    'Historical crash depth is uncertain, and observed capital is a floor rather than a proven crash limit. Calibration on cbBTC does not establish the same accuracy for other assets.</p>' +
    '<p>End-of-path loss and underwater exposure at the trough occur at different moments; do not add them. <a href="writeup.html">Read the methodology</a>.</p></details>';
}
