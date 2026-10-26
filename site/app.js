'use strict';

let DATA = null;
let BT = null;  // backtest.json, feeds the Stress test section and the worst-path tile
let VAULTS;  // vaults.json, feeds the "Who carries a loss" table; undefined until fetched, null when missing
let market = 'cbBTC';
let cbOnly = false;
let logY = false;
let curveLogY = true;
let btMarket = 'cbBTC';
let btScenario = 'AB';
let liqRange = 'all';
let HIST = null;  // history.csv rows, feeds the trend panel

const WINDOWS = ['Mar2020', 'May2021', 'FTX2022', 'Aug2024', 'Oct2025', 'Feb2026', 'Jun2026'];
const LLTVS = [0.86, 0.80, 0.77, 0.70, 0.625];
const MAJORS = ['cbBTC', 'WETH', 'cbETH'];  // everything else is an alt, shown collapsed
// The crashes the book has lived through, named on the history chart: [name, first day, last day] from data/windows.json.
const EVENTS = [['Oct 2025', '2025-10-09', '2025-10-12'], ['Feb 2026', '2026-02-02', '2026-02-08'], ['Jun 2026', '2026-06-01', '2026-06-27']];
const RANGES = { all: Infinity, '1y': 365, '90d': 90 };
// Distance-to-capacity bands: [upper bound, colour class, marker, word]. Marker and word carry the status without colour.
const GAUGE_BANDS = [[0.10, 'red', '▲', 'tight'], [0.20, 'amber', '◆', 'watch'], [Infinity, 'green', '●', 'clear']];
const PHONE = window.matchMedia('(max-width: 700px)').matches;  // read once; the layout rules in style.css switch at the same width

function band(d) {
  return d == null ? GAUGE_BANDS[2] : GAUGE_BANDS.find(([lim]) => d <= lim);
}

function mark(d) {
  const [, cls, icon, word] = band(d);
  return '<span class="mark ' + cls + '" title="' + word + '">' + icon + '</span>';
}

function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// $9.2M, $281k, $1B: one decimal below 100 of the unit, none above, a trailing .0 dropped. Ticks, tiles, tables and cells all use it.
function usd(x) {
  if (x == null || isNaN(x)) return '-';
  const a = Math.abs(x);
  const [div, unit] = a >= 1e9 ? [1e9, 'B'] : a >= 1e6 ? [1e6, 'M'] : a >= 1e3 ? [1e3, 'k'] : [1, ''];
  const m = x / div;
  return '$' + m.toFixed(unit && Math.abs(m) < 100 ? 1 : 0).replace(/\.0$/, '') + unit;
}

function pct(x, d) {
  return x == null ? '-' : (100 * x).toFixed(d == null ? 1 : d) + '%';
}

function num(x) {
  return x == null ? '-' : x.toLocaleString('en-US');
}

function short(addr) {
  return addr.slice(0, 6) + '…' + addr.slice(-4);
}

function link(addr) {
  return '<a href="https://basescan.org/address/' + addr + '" target="_blank" rel="noopener">' + short(addr) + '</a>';
}

function cards(el, items) {
  el.innerHTML = items.map(([label, value, cls]) =>
    '<div class="card' + (cls ? ' ' + cls : '') + '"><div class="label">' + label + '</div><div class="value">' + value + '</div></div>').join('');
}

function dur(min) {
  if (min == null) return '-';
  if (min < 120) return min.toFixed(0) + ' min';
  if (min < 48 * 60) return (min / 60).toFixed(0) + ' h';
  return (min / 1440).toFixed(1) + ' d';
}

// One red banner at the top naming every file that failed to load.
function banner(file) {
  let b = document.getElementById('banner');
  if (!b) {
    document.body.insertAdjacentHTML('afterbegin', '<p id="banner" class="banner" role="alert">failed to load </p>');
    b = document.getElementById('banner');
  }
  if (!b.textContent.includes(file)) b.textContent += (b.textContent.endsWith('load ') ? '' : ', ') + file;
}

// Text of data/<file>, or null (and the banner) on any failure.
async function get(file) {
  const r = await fetch('../data/' + file).catch(() => null);
  if (r && r.ok) return r.text();
  banner('../data/' + file);
  return null;
}

const STALE_HOURS = 8;  // the cron asks for hourly, but GitHub ran it every 4.9 h median, 7.1 h p90 (Oct 2026); past 8 h a run failed or the cron died

// Timestamp into el; past STALE_HOURS it turns red (class stale) so a dead cron shows on the page.
function stamp(el, text, ms) {
  el.textContent = text;
  el.classList.toggle('stale', (Date.now() - ms) / 36e5 > STALE_HOURS);
}

function utc(ms) {
  return new Date(ms).toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
}

function ago(ms) {
  const m = Math.max(0, (Date.now() - ms) / 6e4);
  return m < 90 ? Math.round(m) + ' min' : m < 2880 ? (m / 60).toFixed(m < 600 ? 1 : 0) + ' h' : (m / 1440).toFixed(1) + ' days';
}

// Data age on every page (#data-age: dashboard header, writeup nav) and a banner while the newest snapshot is past STALE_HOURS.
// main() reruns it every minute, so a tab left open goes stale too.
function renderFreshness(iso) {
  const ms = Date.parse(iso), stale = (Date.now() - ms) / 36e5 > STALE_HOURS, el = document.getElementById('data-age');
  if (el) stamp(el, utc(ms) + ' (' + ago(ms) + ' ago)', ms);
  let b = document.getElementById('stale-banner');
  if (!stale) { if (b) b.remove(); return; }
  if (!b) {
    document.body.insertAdjacentHTML('afterbegin', '<p id="stale-banner" class="banner" role="alert"></p>');
    b = document.getElementById('stale-banner');
  }
  b.textContent = 'Stale data: the newest snapshot is ' + ago(ms) + ' old (' + utc(ms) + '). The refresh has not landed since, so every number on this page is as of then.';
}

// Tile 1: the book. Large number is borrow; the rest as small cards.
function renderHeader() {
  const t = DATA.totals;
  document.getElementById('hero-borrow').textContent = usd(t.borrow_usd);
  cards(document.getElementById('totals'), [
    ['Collateral', usd(t.collateral_usd)],
    ['Book LTV', pct(t.borrow_usd / t.collateral_usd)],
    ['Positions', num(t.n_positions)],
    ['Coinbase share', pct(t.coinbase_share_borrow)],
  ]);
}

function split(keys) {
  return [keys.filter(k => MAJORS.includes(k)), keys.filter(k => !MAJORS.includes(k))];
}

// alts, when given, go under a collapsed "Alts" disclosure that opens only if the current pick is one of them.
function buttons(id, keys, current, onpick, alts) {
  const el = document.getElementById(id);
  const b = k => '<button data-k="' + k + '" class="' + (k === current ? 'active' : '') + '" aria-pressed="' + (k === current) + '">' + k + '</button>';
  el.innerHTML = keys.map(b).join('') + (alts && alts.length ?
    '<details class="alts"' + (alts.includes(current) ? ' open' : '') + '><summary>Alts</summary><div class="buttons">' + alts.map(b).join('') + '</div></details>' : '');
  el.querySelectorAll('button').forEach(x => x.onclick = () => onpick(x.dataset.k));
}

function renderButtons() {
  const [maj, alt] = split(Object.keys(DATA.markets));
  buttons('market-buttons', maj, market, k => { market = k; renderAll(); }, alt);
}

function distance(d) {
  return d == null ? '> 70%' : '-' + pct(d, 0);
}

// Tile 2: distance to capacity. cbBTC is the hero; the others sit in a list ordered by borrow, alts collapsed.
function renderGauges() {
  const d = DATA.markets.cbBTC.state.distance_to_capacity;
  const hero = document.getElementById('hero-distance');
  hero.className = 'hero ' + band(d)[1];
  hero.innerHTML = mark(d) + ' ' + distance(d);
  document.getElementById('distance-sentence').textContent = d == null ?
    'BTC has to fall more than 70% before more debt becomes liquidatable than liquidators can sell in one step.' :
    'BTC has to fall ' + pct(d, 0) + ' before more debt becomes liquidatable than liquidators can sell in one step.';
  const rows = Object.entries(DATA.markets).filter(([k]) => k !== 'cbBTC').sort((a, b) => b[1].state.borrow_usd - a[1].state.borrow_usd);
  const li = ([k, m]) => '<li><a href="#book" data-k="' + k + '">' + mark(m.state.distance_to_capacity) + ' ' + k +
    ' <b>' + distance(m.state.distance_to_capacity) + '</b> <span class="muted">' + usd(m.state.borrow_usd) + '</span></a></li>';
  const [maj, alt] = [rows.filter(([k]) => MAJORS.includes(k)), rows.filter(([k]) => !MAJORS.includes(k))];
  const el = document.getElementById('distance-list');
  el.innerHTML = maj.map(li).join('') + (alt.length ? '<li><details class="alts"><summary>Alts</summary><ol>' + alt.map(li).join('') + '</ol></details></li>' : '');
  el.querySelectorAll('a[data-k]').forEach(a => a.onclick = () => { market = a.dataset.k; renderAll(); });
}

function renderCards(m) {
  const s = m.state;
  const borrow = cbOnly ? s.borrow_usd * s.coinbase_share_borrow : s.borrow_usd;
  const n = cbOnly ? Math.round(s.n_positions * s.coinbase_share_count) : s.n_positions;
  document.getElementById('market-title').textContent = market + ' / USDC' + (cbOnly ? ' (Coinbase wallets only)' : '');
  cards(document.getElementById('market-cards'), [
    ['Borrow', usd(borrow)],
    ['Collateral', usd(s.collateral_usd)],
    ['Utilization', pct(s.utilization)],
    ['Borrow APY', pct(s.borrow_apy, 2)],
    ['LLTV', pct(s.lltv)],
    ['Liquidation bonus', pct(s.lif - 1, 2)],
    ['Bad-debt LTV', pct(s.bad_debt_ltv)],
    ['Price', '$' + s.price.toLocaleString('en-US', { maximumFractionDigits: s.price < 10 ? 4 : 0 })],
    ['Positions', num(n)],
    ['Coinbase share', pct(s.coinbase_share_borrow)],
  ]);
}

function renderLtv(m) {
  const k = cbOnly ? 'cb_' : '';
  const x = m.ltv_hist.map(b => b.lo + 0.01), y = m.ltv_hist.map(b => b[k + 'borrow_usd']), n = m.ltv_hist.map(b => b[k + 'count']);
  const bin = b => pct(b.lo, 0) + ' to ' + pct(b.lo + 0.02, 0);
  const hover = m.ltv_hist.map((b, i) => 'LTV ' + bin(b) + ': ' + usd(y[i]) + ', ' + num(n[i]) + ' positions');
  const traces = [{ type: 'bar', x, y, name: 'Borrow USD', marker: { color: css('--accent') }, width: 0.02, customdata: hover, hovertemplate: '%{customdata}<extra></extra>' }];
  // Threshold lines with their labels above the plot, each ending at its line; the bad-debt label takes the upper row so the two do not overlap.
  const vline = (v, text, padding) => ({ type: 'line', x0: v, x1: v, y0: 0, y1: 1, yref: 'paper', line: { color: css('--danger'), width: 1.5, dash: 'dash' },
    label: { text, textposition: 'end', textangle: 0, xanchor: 'right', yanchor: 'bottom', padding, font: { color: css('--danger'), size: 11 } } });
  const layout = baseLayout({
    margin: { l: 64, r: 16, t: 40, b: 80 },
    xaxis: Object.assign({ title: 'LTV', range: [0, 1] }, pctTicks([1])),
    yaxis: Object.assign({ title: 'Borrow USD', automargin: true, type: logY ? 'log' : 'linear' }, ticks(y, usd, logY)),
    shapes: [vline(m.state.lltv, 'liquidation ' + pct(m.state.lltv, 0), 2), vline(m.state.bad_debt_ltv, 'bad debt ' + pct(m.state.bad_debt_ltv), 18)],
  });
  plot('chart-ltv', traces, layout, ['LTV bin', 'Borrow', 'Positions'], m.ltv_hist.map((b, i) => [bin(b), usd(y[i]), num(n[i])]));
  const near = m.hf_cdf.reduce((a, p) => Math.abs(p.hf - 1.1) < Math.abs(a.hf - 1.1) ? p : a);  // the grid point nearest HF 1.1
  document.getElementById('ltv-stat').textContent = 'Share of borrow within 10% of liquidation (health factor below 1.1): ' + pct(near.share) + ' of the whole market.';
}

function capacity(m) {
  const d = m.depth || {};
  return {
    dex: d.dex_capacity_usd ? d.dex_capacity_usd['4.38'] : null,
    cex: d.coinbase ? d.coinbase.bid_depth_usd['4.38'] : null,
  };
}

function renderCurve(m) {
  const k = cbOnly ? 'cb_' : '';
  const c = m.liquidatable_curve, x = c.map(p => p.drop), y = c.map(p => p[k + 'borrow_usd']), bad = c.map(p => p[k + 'bad_borrow_usd']);
  const muted = css('--muted');
  const cap = capacity(m), total = m.state.capacity_ab_usd, d = m.state.distance_to_capacity;
  const traces = [
    { type: 'scatter', mode: 'lines', x, y, name: 'Liquidatable borrow', line: { color: css('--accent'), width: 2.5 }, fill: 'tozeroy', fillcolor: css('--band'),
      customdata: y.map(usd), hovertemplate: '%{customdata}<extra>liquidatable</extra>' },
    { type: 'scatter', mode: 'lines', x, y: bad, name: 'Past the bad-debt LTV', line: { color: css('--accent2'), width: 2 },
      customdata: bad.map(usd), hovertemplate: '%{customdata}<extra>bad-debt zone</extra>' },
  ];
  const ly = v => curveLogY ? Math.log10(v) : v;  // annotations and ranges take log10 units on a log axis; shapes take raw values
  const top = Math.max(...y, cap.cex || 0, cap.dex || 0) * 1.08, lo = Math.min(...y.filter(v => v > 0), total || Infinity) / 2;
  const shapes = [], annotations = [];
  // Capacity lines are traces so a phone can name them in the legend; a wide screen labels them at their right end instead.
  const hline = (v, text, yshift) => {
    if (!v) return;
    traces.push({ type: 'scatter', mode: 'lines', x: [x[0], x[x.length - 1]], y: [v, v], name: text + ' ' + usd(v), showlegend: PHONE, hoverinfo: 'skip', line: { color: muted, width: 1.5, dash: 'dash' } });
    if (!PHONE) annotations.push({ x: 0.995, xref: 'paper', yref: 'y', y: ly(v), yshift, text: text + ' within the bonus ' + usd(v), showarrow: false, xanchor: 'right', yanchor: 'bottom', font: { color: muted, size: 11 } });
  };
  hline(cap.cex, 'Coinbase bids', curveLogY ? 0 : 16);  // in linear mode both lines hug zero, so the upper label is shifted up
  hline(cap.dex, 'DEX capacity', 0);
  if (total) {
    shapes.push({ type: 'rect', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: total, y1: top, fillcolor: css('--shade'), line: { width: 0 }, layer: 'below' });
    annotations.push({ x: 0.005, xref: 'paper', y: 0.99, yref: 'paper', text: 'more than liquidators can sell', showarrow: false, xanchor: 'left', yanchor: 'top', font: { color: muted, size: 11 } });
  }
  if (d != null) {
    const yd = y[x.findIndex(v => Math.abs(v - d) < 1e-9)];
    traces.push({ type: 'scatter', mode: 'markers', x: [d], y: [yd], name: 'Distance to capacity', showlegend: false, marker: { color: css('--accent'), size: 10 }, hoverinfo: 'skip' });
    annotations.push({ x: d, y: ly(yd), text: '-' + pct(d, 0) + ': ' + usd(yd), showarrow: true, arrowhead: 0, arrowcolor: muted, ax: 56, ay: curveLogY ? 36 : -36, font: { size: 11 } });
  }
  const layout = baseLayout({
    xaxis: Object.assign({ title: 'Instantaneous price drop' }, pctTicks(x)),
    yaxis: Object.assign({ title: 'Borrow USD', automargin: true, type: curveLogY ? 'log' : 'linear', range: [curveLogY ? ly(lo) : 0, ly(top)] }, ticks(y.concat(bad, [cap.cex, cap.dex]), usd, curveLogY)),
    shapes, annotations,
  });
  plot('chart-curve', traces, layout, ['Price drop', 'Liquidatable', 'Past bad-debt LTV'], c.map((p, i) => [(p.drop ? '-' : '') + pct(p.drop, 0), usd(y[i]), usd(bad[i])]));
}

function renderLiq(m) {
  const since = liqRange === 'all' ? '' : new Date(Date.now() - RANGES[liqRange] * 864e5).toISOString().slice(0, 10);
  const days = m.liquidations_daily.filter(d => d.day >= since);
  const muted = css('--muted');
  buttons('liq-range-buttons', Object.keys(RANGES), liqRange, k => { liqRange = k; renderLiq(DATA.markets[market]); });
  const hover = days.map(d => usd(d.repaid_usd) + ' (' + num(d.n) + ' liquidations)');
  const traces = [{ type: 'bar', x: days.map(d => d.day), y: days.map(d => d.repaid_usd), name: 'Repaid USD', marker: { color: css('--accent') }, customdata: hover, hovertemplate: '%{customdata}<extra></extra>' }];
  // Each lived event is named at its largest day, when that day is in range.
  const peaks = EVENTS.map(([name, lo, hi]) => [name, days.filter(d => d.day >= lo && d.day <= hi).sort((a, b) => b.repaid_usd - a.repaid_usd)[0]]).filter(([, d]) => d);
  const layout = baseLayout({
    xaxis: { type: 'date' },
    yaxis: Object.assign({ title: 'Repaid USD' }, ticks(traces[0].y, usd, false)),
    annotations: peaks.map(([name, d]) => ({ x: d.day, y: d.repaid_usd, text: name + ' ' + usd(d.repaid_usd), showarrow: true, arrowhead: 0, arrowcolor: muted, ax: 0, ay: -28, font: { size: 11, color: muted } })),
  });
  plot('chart-liq', traces, layout, ['Day', 'Repaid', 'Liquidations'], days.map((d, i) => [d.day, usd(d.repaid_usd), num(d.n)]));
}

// history.csv: utc_ts, market, then numbers; an empty cell is null.
async function loadHistory() {
  const text = await get('history.csv');
  if (!text) return [];
  const [head, ...lines] = text.trim().split('\n');
  const cols = head.split(',');
  return lines.map(l => {
    const v = l.split(','), o = {};
    cols.forEach((c, i) => o[c] = i < 2 ? v[i] : (v[i] === '' || v[i] == null ? null : +v[i]));
    return o;
  });
}

// Three small multiples for the selected market, one series each, as stacked subplots sharing the time axis.
function renderTrend() {
  const el = document.getElementById('chart-trend');
  if (HIST == null) return;  // still loading
  const rows = HIST.filter(r => r.market === market);
  if (!rows.length) { el.textContent = 'not available'; return; }
  const x = rows.map(r => r.utc_ts);
  const series = [['book_ltv', 'Book LTV', v => pct(v), pctTicks], ['distance_to_capacity', 'Distance to capacity', v => v == null ? '> 70%' : pct(v, 0), pctTicks], ['liq_20', 'Liquidatable at -20%', usd, v => ticks(v, usd)]];
  const traces = series.map(([k, name, f], i) => {
    const y = rows.map(r => r[k]);
    return { type: 'scatter', mode: 'lines+markers', x, y, name, yaxis: 'y' + (i ? i + 1 : ''), line: { color: css('--accent'), width: 2 }, marker: { size: 5 },
      customdata: y.map(f), hovertemplate: '%{customdata}<extra>' + name + '</extra>' };
  });
  const layout = baseLayout({ grid: { rows: 3, columns: 1, pattern: 'coupled', ygap: 0.18 }, showlegend: false, xaxis: { type: 'date' }, annotations: [] });
  series.forEach(([k, name, f, tk], i) => {  // each subplot is named above its top-left corner; a y-axis title would collide with the tick labels on a phone
    const sfx = i ? i + 1 : '';
    layout['yaxis' + sfx] = axis(Object.assign({ rangemode: 'tozero' }, tk(traces[i].y.filter(v => v != null))));
    layout.annotations.push({ text: name, xref: 'paper', x: 0, yref: 'y' + sfx + ' domain', y: 1, xanchor: 'left', yanchor: 'bottom', showarrow: false, font: { size: 11, color: css('--muted') } });
  });
  plot(el, traces, layout, ['Time (UTC)', 'Book LTV', 'Distance to capacity', 'Liquidatable at -20%'],
    rows.map((r, i) => [r.utc_ts.slice(0, 16).replace('T', ' '), traces[0].customdata[i], traces[1].customdata[i], traces[2].customdata[i]]));
}

function renderBorrowers(m) {
  const rows = (cbOnly ? m.top_borrowers.filter(b => b.is_coinbase) : m.top_borrowers);
  document.getElementById('borrowers').innerHTML =
    '<tr><th>#</th><th>Address</th><th>Borrow</th><th>Collateral</th><th>LTV</th><th>HF</th></tr>' +
    rows.map((b, i) =>
      '<tr><td>' + (i + 1) + '</td><td>' + link(b.user) + (b.is_coinbase ? '<span class="badge">Coinbase</span>' : '') +
      '</td><td>' + usd(b.borrow_usd) + '</td><td>' + usd(b.collateral_usd) + '</td><td>' + pct(b.ltv) +
      '</td><td>' + (b.health_factor == null ? '-' : b.health_factor.toFixed(2)) + '</td></tr>').join('');
}

function renderLiquidators(m) {
  document.getElementById('liquidators').innerHTML =
    '<tr><th>#</th><th>Liquidator</th><th>Liquidations</th><th>Repaid</th><th>Share</th></tr>' +
    m.liquidators_top.map((l, i) =>
      '<tr><td>' + (i + 1) + '</td><td>' + link(l.liquidator) + '</td><td>' + num(l.count) +
      '</td><td>' + usd(l.repaid_usd) + '</td><td>' + pct(l.share) + '</td></tr>').join('');
}

// Merged stress-window leaderboard from data/calibration.json; market-independent, so rendered once from main().
async function renderLeaderboard() {
  const el = document.getElementById('leaderboard');
  const text = await get('calibration.json');
  const rows = text && JSON.parse(text).leaderboard;
  if (!rows) { el.innerHTML = '<tr><td class="muted">not available</td></tr>'; return; }
  const yn = b => b ? 'yes' : 'no';
  el.innerHTML =
    '<tr><th>#</th><th>Liquidator</th><th>Windows</th><th>Liquidations</th><th>Repaid</th><th>Gross bonus</th><th>Latency p50</th><th>Contract</th><th>Coinbase-affiliated</th></tr>' +
    rows.map((l, i) =>
      '<tr><td>' + (i + 1) + '</td><td>' + link(l.address) + '</td><td>' + l.windows.join(', ') + '</td><td>' + num(l.count) +
      '</td><td>' + usd(l.repaid_usd) + '</td><td>' + usd(l.gross_bonus_usd) + '</td><td>' + (l.latency_p50 == null ? '-' : l.latency_p50 + ' s') +
      '</td><td>' + yn(l.is_contract) + '</td><td>' + yn(l.coinbase_affiliated) + '</td></tr>').join('');
}

// ---- Backtest (data/backtest.json). Also used by writeup.html, which loads this file and calls renderHeatmap / renderWarn.

let btLoad = null;
function loadBacktest() {  // one fetch of the 5 MB file however many sections ask for it at once
  return btLoad ||= fetchBacktest();
}

async function fetchBacktest() {
  const text = await get('backtest.json');
  if (!text) return null;
  // json.dump writes the unlimited-capital rows as Infinity, which JSON.parse rejects; 1e999 parses to Infinity.
  BT = JSON.parse(text.replace(/\bInfinity\b/g, '1e999'));
  const d = BT.defaults, c = BT.calibrated || {};
  const grid = BT.runs.filter(r => r.book === BT.latest_book);
  const counts = {};
  grid.forEach(r => counts[r.cex_cap_usd] = (counts[r.cex_cap_usd] || 0) + 1);
  BT.cexCap = +Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0];
  const want = { k_dex: d.k_dex, k_cex: d.k_cex, lag_bars: d.lag_bars, margin: d.margin, resp_share: c.resp_share, react_min: c.react_min };
  ['beta', 'seed', 'close_target', 'full_below_usd', 'hold_bars', 'book_multiple'].forEach(k => { if (k in d) want[k] = d[k]; });  // sensitivity sweeps stay out of the grid view
  // over: defaults to replace for one lookup, e.g. { hold_bars: 288 } for the held-at-the-low row.
  BT.base = (r, over) => r.book === BT.latest_book && Object.entries(Object.assign({}, want, over)).every(([k, v]) => r[k] === v);
  return BT;
}

function btRows(bt, f, over) {
  const key = JSON.stringify(over || {});  // the base filter runs once per override, not once per heatmap cell
  const base = (bt.baseRows ||= {})[key] ||= bt.runs.filter(r => bt.base(r, over));
  return base.filter(r => Object.keys(f).every(k => r[k] === f[k]));
}

let btMetric = 'Loss by end of path';
const METRICS = {
  'Loss by end of path': r => r.realized_bad_debt_usd + r.unrealized_bad_debt_usd,  // realized on liquidations plus still underwater at the end
  'Exposure at trough': r => r.trough_exposure_usd || 0,                              // the same, marked at the lowest oracle print
};
function badDebt(r) {
  return METRICS[btMetric](r);
}

// Row at max draw 0.75, or 0.60 for the LLTVs below 0.75 where the grid has no 0.75 column.
function pickCap(rows) {
  return rows.find(r => r.cap === 0.75) || rows.find(r => r.cap === 0.60) || null;
}

function renderHeatmap(el, bt, mkt, scenario) {
  const z = LLTVS.map(l => WINDOWS.map(w => {
    const r = pickCap(btRows(bt, { market: mkt, window: w, lltv: l, scenario, cex_cap_usd: bt.cexCap }));
    return r ? badDebt(r) : null;
  }));
  heat(el, LLTVS.map(l => pct(l, l === 0.625 ? 1 : 0)), WINDOWS, z);
}

function renderCapital(el, bt) {
  const rows = btRows(bt, { market: 'cbBTC', window: 'Mar2020', scenario: 'AB', cap: 0.75 });
  const caps = [...new Set(rows.map(r => r.cex_cap_usd))].sort((a, b) => a - b);
  const lltvs = LLTVS.filter(l => rows.some(r => r.lltv === l));
  const z = lltvs.map(l => caps.map(c => { const r = rows.find(r => r.lltv === l && r.cex_cap_usd === c); return r ? badDebt(r) : null; }));
  heat(el, lltvs.map(l => pct(l, 0)), caps.map(c => c === Infinity ? 'unlimited' : (c / bt.cexCap).toFixed(0) + 'x'), z, 'Liquidator daily capital, multiple of ' + usd(bt.cexCap));
}

function renderWarn(el, bt, mkt) {
  const y = WINDOWS.map(w => { const r = pickCap(btRows(bt, { market: mkt, window: w, lltv: 0.86, scenario: 'AB', cex_cap_usd: bt.cexCap })); return r ? r.warn_minutes_p50 : null; });
  const text = y.map(dur);
  const traces = [{ type: 'bar', x: WINDOWS, y: y.map(v => v == null ? null : v / 60), text, textposition: 'outside', name: 'Warning time p50',
    marker: { color: css('--accent') }, cliponaxis: false, hovertemplate: '%{text}<extra></extra>' }];
  const layout = baseLayout({ showlegend: false, hovermode: 'closest', xaxis: { type: 'category' }, yaxis: { title: 'Hours', rangemode: 'tozero' } });
  plot(el, traces, layout, ['Path', 'Warning time (median)'], WINDOWS.map((w, i) => [w, text[i]]));
}

// The grid row for a market at today's terms: its live LLTV (0.86 without summary.json), scenario AB, max draw from pickCap.
// over: defaults to replace, e.g. { hold_bars: 288 } for the held-a-day row.
function todayRow(bt, mkt, w, over) {
  const lltv = DATA && DATA.markets[mkt] ? DATA.markets[mkt].state.lltv : 0.86;
  return pickCap(btRows(bt, { market: mkt, window: w, scenario: 'AB', lltv, cex_cap_usd: bt.cexCap }, over));
}

function lossCells(bt, mkt, w) {
  const row = todayRow(bt, mkt, w), held = todayRow(bt, mkt, w, { hold_bars: 288 });
  return row ? [usd(METRICS['Loss by end of path'](row)), usd(METRICS['Exposure at trough'](row)), held ? usd(METRICS['Loss by end of path'](held)) : 'not run'] : null;
}

// Tile 3: cbBTC on March 2020, scenario AB, at today's terms. Bridge from the dashboard to the writeup.
function renderWorst(bt) {
  const el = document.getElementById('worst'), p = document.getElementById('worst-sentence');
  const cells_ = bt && lossCells(bt, 'cbBTC', 'Mar2020');
  if (!cells_) { el.innerHTML = ''; p.textContent = 'not available'; return; }
  cards(el, [['Loss by end of path', cells_[0]], ['Exposure at trough', cells_[1]], ['Loss if held a day at the low', cells_[2]]]);
  p.innerHTML = "Today's cbBTC book replayed through March 2020 with liquidators selling on-chain and on exchanges (scenario AB): " +
    'what lenders lose by the end of the path, what sat underwater at the lowest print, and the loss if the low had held for a day. <a href="#stress">Stress test</a>';
}

// Six cells: the two paths that cost money, for the selected backtest market at today's terms.
function renderSummary(bt) {
  document.getElementById('bt-summary').innerHTML = '<tr><th>Path</th><th>Loss by end of path</th><th>Exposure at trough</th><th>Loss if held a day at the low</th></tr>' +
    ['Mar2020', 'May2021'].map(w => '<tr><td>' + w + '</td>' + (lossCells(bt, btMarket, w) || ['-', '-', '-']).map(v => '<td>' + v + '</td>').join('') + '</tr>').join('');
}

async function loadVaults() {
  if (VAULTS === undefined) VAULTS = JSON.parse(await get('vaults.json'));  // JSON.parse(null) is null
  return VAULTS;
}

// Who carries a loss: the selected market's vaults (top 10 plus direct suppliers) with their pro-rata cut of the same Mar2020 AB row renderSummary shows.
function renderVaults(vaults, bt) {
  const el = document.getElementById('bt-vaults');
  const m = vaults && vaults.markets[btMarket];
  if (!m) { el.innerHTML = '<tr><td class="muted">not available</td></tr>'; return; }
  const row = bt && todayRow(bt, btMarket, 'Mar2020'), held = bt && todayRow(bt, btMarket, 'Mar2020', { hold_bars: 288 });
  const loss = [row && METRICS['Loss by end of path'](row), row && METRICS['Exposure at trough'](row), held && METRICS['Loss by end of path'](held)];
  const rows = m.vaults.filter(v => v.kind !== 'direct').slice(0, 10).concat(m.vaults.filter(v => v.kind === 'direct'));
  const name = v => v.name.replace(/[<&]/g, c => c === '<' ? '&lt;' : '&amp;');
  const cell = v => v.address ? '<a href="https://app.morpho.org/base/vault/' + v.address + '" target="_blank" rel="noopener">' + name(v) + '</a>' : name(v);
  el.innerHTML = '<tr><th>Vault</th><th>Kind</th><th>Supplied to market</th><th>Share</th><th>Loss by end of path</th><th>Exposure at trough</th><th>Held a day</th><th>Held a day, % of vault</th></tr>' +
    rows.map(v => '<tr><td>' + cell(v) + '</td><td>' + (v.address ? v.kind.toUpperCase() : '-') + '</td><td>' + usd(v.supplied_usd) + '</td><td>' + pct(v.share) + '</td>' +
      loss.map(x => '<td>' + (x == null ? '-' : usd(x * v.share)) + '</td>').join('') +
      '<td>' + (loss[2] != null && v.vault_total_usd ? pct(loss[2] * v.share / v.vault_total_usd, 2) : '-') + '</td></tr>').join('');
}

async function renderBacktest() {
  const bt = await loadBacktest();
  const note = document.getElementById('bt-note');
  renderWorst(bt);
  renderVaults(await loadVaults(), bt);
  if (!bt) {
    ['bt-note', 'bt-generated-at', 'bt-summary', 'chart-heat', 'chart-capital', 'chart-warn'].forEach(id => document.getElementById(id).textContent = 'not available');
    return;
  }
  const [markets, alts] = split([...new Set(bt.runs.filter(r => bt.base(r)).map(r => r.market))]);
  if (!markets.concat(alts).includes(btMarket)) btMarket = markets[0];
  const c = bt.calibrated || {};
  note.textContent = 'Grid rows at the fitted borrower response (' + pct(c.resp_share, 0) + ' within ' + c.react_min + ' min), depth multipliers DEX ' +
    bt.defaults.k_dex + ' / CEX ' + bt.defaults.k_cex + ', liquidator daily capital ' + usd(bt.cexCap) + '. Max draw 75%, or 60% where the LLTV is below 75%.';
  stamp(document.getElementById('bt-generated-at'), 'book as of ' + bt.latest_book + ', run ' + new Date(bt.generated_at * 1000).toISOString().slice(0, 16).replace('T', ' ') + ' UTC', bt.generated_at * 1000);
  buttons('bt-market-buttons', markets, btMarket, k => { btMarket = k; renderBacktest(); }, alts);
  buttons('bt-scenario-buttons', ['A', 'AB', 'ABC'], btScenario, k => { btScenario = k; renderBacktest(); });
  buttons('bt-metric-buttons', Object.keys(METRICS), btMetric, k => { btMetric = k; renderBacktest(); });
  renderSummary(bt);
  renderHeatmap('chart-heat', bt, btMarket, btScenario);
  renderCapital('chart-capital', bt);
  renderWarn('chart-warn', bt, btMarket);
}

// ---- Check a loan: one address's positions, read live from Morpho's public API (CORS-open, no key) in the visitor's browser.

const MORPHO_API = 'https://blue-api.morpho.org/graphql';
const POSITIONS_Q = 'query($u:[String!],$m:[String!]){marketPositions(first:100,where:{chainId_in:[8453],userAddress_in:$u,marketUniqueKey_in:$m}){items{' +
  'healthFactor market{marketId lltv collateralAsset{symbol decimals price{usd}} loanAsset{symbol}} state{collateral borrowAssets borrowAssetsUsd collateralUsd}}}}';

function esc(s) {
  return String(s == null ? '' : s).replace(/[<>&"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' })[c]);
}

function marketName(m) {
  return m.tracked || esc(m.collateral) + ' / ' + esc(m.loan) + ' ' + pct(m.lltv);
}

// {market id: name} for every market on the page: Coinbase's nine plus the Base list.
function knownMarkets() {
  const out = {};
  (DATA.base_markets ? DATA.base_markets.markets : []).forEach(m => out[m.id.toLowerCase()] = marketName(m));
  Object.entries(DATA.markets).forEach(([k, m]) => { if (m.state.market_id) out[m.state.market_id.toLowerCase()] = k; });
  return out;
}

// One position at the oracle price: Morpho's health factor is LLTV / LTV, so the price can fall 1 - 1/HF before liquidation.
// drops: {path: peak-to-trough fall} from summary.json, present for Coinbase's nine only.
function loanRisk(p, drops) {
  const s = p.state, a = p.market.collateralAsset, lltv = Number(p.market.lltv) / 1e18;
  const debt = s.borrowAssetsUsd || 0, coll = s.collateralUsd || 0, units = Number(s.collateral) / 10 ** a.decimals;
  const hf = p.healthFactor != null ? p.healthFactor : debt && coll ? lltv * coll / debt : null;
  const price = units && coll ? coll / units : a.price && a.price.usd;
  const r = { debt, coll, units, lltv, hf, price, ltv: hf ? lltv / hf : null, badLtv: 1 / Math.min(1.15, 1 / (0.3 * lltv + 0.7)) };
  r.buffer = hf ? 1 - 1 / hf : null;
  r.liqPrice = hf && price ? price / hf : null;
  if (drops && hf && Object.keys(drops).length) {
    const paths = Object.entries(drops).sort((x, y) => y[1] - x[1]);
    r.worst = paths[0];
    r.troughLtv = r.ltv / (1 - r.worst[1]);
    r.hit = paths.filter(([, d]) => d >= r.buffer).length;
    r.paths = paths.length;
  }
  return r;
}

function price$(x) {
  return x == null ? '-' : '$' + x.toLocaleString('en-US', { maximumFractionDigits: x < 10 ? 4 : x < 1000 ? 2 : 0 });
}

function worstText(r, mkt, bt) {
  if (!r.worst) return r.debt ? 'No crash replay for this market.' : '-';
  const [w, d] = r.worst;
  const fate = r.buffer <= 0 ? 'Liquidatable already.' : d < r.buffer ? 'Survives the low with ' + pct(r.buffer - d, 0) + ' to spare.' :
    'Liquidated on the way down' + (r.troughLtv > r.badLtv ? '; if liquidators miss it, its LTV at the low is ' + pct(r.troughLtv, 0) + ', past the ' + pct(r.badLtv) + ' bad-debt line.' : '; its collateral still covers the debt at the low.');
  const cells = bt && lossCells(bt, mkt, w);
  return w + ', ' + pct(d, 0) + ' peak to low. ' + fate + ' Liquidated on ' + r.hit + ' of ' + r.paths + ' paths.' +
    (cells ? ' <span class="muted">Whole market on that path (scenario AB): loss by end of path ' + cells[0] + '; supply left unserved at the low, a separate measure, ' + cells[1] + '.</span>' : '');
}

async function checkLoan(raw) {
  const out = document.getElementById('check-result'), addr = raw.trim();
  if (!/^0x[0-9a-fA-F]{40}$/.test(addr)) {
    out.innerHTML = '<p class="stale" role="alert">That is not a Base address: it should be 0x followed by 40 hex characters.</p>';
    return;
  }
  history.replaceState(null, '', '?address=' + addr + location.hash);
  out.innerHTML = '<p class="muted">Asking Morpho…</p>';
  const known = knownMarkets();
  if (!Object.keys(known).length) {  // a summary.json from before market ids were published: an empty filter would match every market
    out.innerHTML = '<p class="muted">Not available until the next refresh publishes the market list.</p>';
    return;
  }
  let items;
  try {
    const r = await fetch(MORPHO_API, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: POSITIONS_Q, variables: { u: [addr.toLowerCase()], m: Object.keys(known) } }) });
    const j = await r.json();
    if (j.errors) throw new Error(j.errors[0].message);
    items = j.data.marketPositions.items.filter(p => Number(p.state.borrowAssets) > 0 || Number(p.state.collateral) > 0);
  } catch (e) {
    out.innerHTML = '<p class="stale" role="alert">Could not reach Morpho\'s API (' + esc(e.message) + '). Try again in a minute.</p>';
    return;
  }
  if (!items.length) {
    out.innerHTML = '<p class="empty">No loans or collateral for <code>' + short(addr) + '</code> in the ' + Object.keys(known).length +
      ' markets on this page. It may borrow on another chain or in a smaller Morpho market; <a href="https://app.morpho.org/portfolio?user=' + addr + '" target="_blank" rel="noopener">Morpho\'s app</a> shows every market.</p>';
    return;
  }
  const bt = await loadBacktest();
  const rows = items.map(p => {
    const id = p.market.marketId.toLowerCase(), mkt = DATA.markets[known[id]] ? known[id] : null;
    return [p, known[id], mkt, loanRisk(p, mkt && DATA.markets[mkt].crash_drops)];
  }).sort((x, y) => y[3].debt - x[3].debt);
  out.innerHTML = '<p>' + rows.length + ' position' + (rows.length > 1 ? 's' : '') + ' for ' + link(addr) + ', live from Morpho.</p><div class="scroll-x"><table id="check-table">' +
    '<tr><th>Market</th><th>Debt</th><th>Collateral</th><th>LTV / LLTV</th><th>Liquidation price</th><th>Buffer</th></tr>' +
    rows.map(([p, name, mkt, r]) => {
      const sym = esc(p.market.collateralAsset.symbol);
      return '<tr class="pos"><td>' + name + (mkt ? '<span class="badge">Coinbase</span>' : '') + '</td><td>' + (r.debt ? usd(r.debt) + ' ' + esc(p.market.loanAsset.symbol) : 'none') +
        '</td><td>' + r.units.toLocaleString('en-US', { maximumFractionDigits: 4 }) + ' ' + sym + ' (' + usd(r.coll) + ')</td>' +
        '<td>' + (r.ltv == null ? '-' : pct(r.ltv)) + ' / ' + pct(r.lltv) + '</td>' +
        '<td>' + (r.liqPrice == null ? '-' : price$(r.liqPrice) + ' <span class="muted">now ' + price$(r.price) + '</span>') + '</td>' +
        '<td>' + (r.buffer == null ? '-' : mark(Math.max(r.buffer, 0)) + ' ' + (r.buffer <= 0 ? 'liquidatable now' : '-' + pct(r.buffer, 1))) + '</td>' +
        '</tr><tr class="sub"><td colspan="6" class="wrap"><b>Worst replayed crash:</b> ' + worstText(r, mkt, bt) + '</td></tr>';
    }).join('') + '</table></div>';
}

// ---- All Base markets above the threshold, from summary.json's base_markets (spine/fetch_markets.py).

function renderBase() {
  const bm = DATA.base_markets, stat = document.getElementById('base-stat');
  if (!bm) { stat.textContent = 'Not available yet: the next refresh adds this list.'; return; }
  const listed = bm.markets.filter(m => m.listed), unlisted = bm.markets.filter(m => !m.listed);
  const sum = ms => ms.reduce((a, m) => a + m.borrow_usd, 0), ours = bm.markets.filter(m => m.tracked);
  stat.textContent = bm.markets.length + ' markets have more than ' + usd(bm.min_borrow_usd) + ' borrowed (' + usd(sum(bm.markets)) + '). Morpho lists ' + listed.length +
    ' of them (' + usd(sum(listed)) + '), and Coinbase\'s ' + ours.length + ' above the line are ' + pct(sum(ours) / sum(listed), 0) + ' of that. ' +
    'Coinbase\'s smaller alt markets sit under the line; the sections above cover them. Market list as of ' + utc(bm.fetched_at * 1000) + '.';
  const cell = m => '<a href="https://app.morpho.org/base/market/' + m.id + '" target="_blank" rel="noopener">' + esc(m.collateral) + ' / ' + esc(m.loan) + '</a>' +
    (m.tracked ? '<span class="badge">Coinbase</span>' : '');
  const here = m => m.tracked ? '<a href="#book" data-k="' + m.tracked + '">' + m.tracked + ' charts</a>' : '-';
  document.getElementById('base-listed').innerHTML = '<tr><th>Market</th><th>LLTV</th><th>Borrowed</th><th>Supplied</th><th>Utilization</th><th>Borrow APY</th><th>Collateral</th><th>Book LTV</th><th>On this page</th></tr>' +
    listed.map(m => '<tr><td>' + cell(m) + '</td><td>' + pct(m.lltv) + '</td><td>' + usd(m.borrow_usd) + '</td><td>' + usd(m.supply_usd) + '</td><td>' + pct(m.utilization) +
      '</td><td>' + pct(m.borrow_apy, 2) + '</td><td>' + usd(m.collateral_usd) + '</td><td>' + pct(m.book_ltv) + '</td><td>' + here(m) + '</td></tr>').join('');
  document.getElementById('base-unlisted-summary').textContent = unlisted.length + ' markets Morpho does not list (' + usd(sum(unlisted)) + ' borrowed)';
  document.getElementById('base-unlisted').innerHTML = '<tr><th>Market</th><th>LLTV</th><th>Borrowed</th><th>Utilization</th><th>Collateral value</th><th>Morpho warnings</th></tr>' +
    unlisted.map(m => '<tr><td>' + cell(m) + '</td><td>' + pct(m.lltv) + '</td><td>' + usd(m.borrow_usd) + '</td><td>' + pct(m.utilization) + '</td><td>' +
      (m.collateral_price_usd == null ? 'unpriced' : usd(m.collateral_usd)) + '</td><td class="wrap">' + esc(m.warnings.join(', ').replace(/_/g, ' ')) + '</td></tr>').join('');
  document.querySelectorAll('#base-listed a[data-k]').forEach(a => a.onclick = () => { market = a.dataset.k; renderAll(); });
}

function renderAll() {
  const m = DATA.markets[market];
  renderButtons();
  renderGauges();
  renderCards(m);
  renderLtv(m);
  renderCurve(m);
  renderLiq(m);
  renderTrend();
  renderBorrowers(m);
  renderLiquidators(m);
}

async function main() {
  const text = await get('summary.json');
  if (text) {
    DATA = JSON.parse(text);
    renderFreshness(DATA.generated_at);
    setInterval(() => renderFreshness(DATA.generated_at), 6e4);
  }
  if (!document.getElementById('totals')) return;  // writeup.html: the data age and stale banner; its own script draws the backtest figures
  if (PHONE) document.querySelectorAll('details.fold').forEach(d => d.open = false);  // tables fold on phones
  if (!DATA) { document.getElementById('data-age').textContent = 'not available'; return; }
  if (DATA.markets[location.hash.slice(1)]) market = location.hash.slice(1);  // #cbXRP deep link
  if (!DATA.markets[market]) market = Object.keys(DATA.markets)[0];
  document.getElementById('cb-only').onchange = e => { cbOnly = e.target.checked; renderAll(); };
  document.getElementById('log-y').onchange = e => { logY = e.target.checked; renderLtv(DATA.markets[market]); };
  document.getElementById('log-y-curve').onchange = e => { curveLogY = e.target.checked; renderCurve(DATA.markets[market]); };
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { renderAll(); renderBacktest(); });
  renderHeader();
  renderAll();
  renderBacktest();
  renderLeaderboard();
  renderBase();
  const form = document.getElementById('check-form'), input = document.getElementById('check-address');
  form.onsubmit = e => { e.preventDefault(); checkLoan(input.value); };
  const q = new URLSearchParams(location.search).get('address');  // ?address=0x… deep link, also what a check writes back to the URL
  if (q) { input.value = q; checkLoan(q); }
  loadHistory().then(h => { HIST = h; renderTrend(); });
  if (DATA.markets[location.hash.slice(1)]) document.getElementById('book').scrollIntoView();  // the market anchor has no element of its own
}

main();
