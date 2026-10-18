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

// Every axis: solid hairline grid one shade off the surface, no zero line, margins grow to fit long tick labels and the title.
function axis(extra) {
  return Object.assign({ gridcolor: css('--grid'), gridwidth: 1, zeroline: false, color: css('--muted'), automargin: true }, extra || {});
}

function baseLayout(extra) {
  extra = extra || {};
  return Object.assign({
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: css('--fg'), family: 'inherit', size: 12 },
    margin: { l: 64, r: 16, t: 28, b: 80 },  // bottom holds the tick labels, the axis title and a one-row legend
    legend: { orientation: 'h', yref: 'container', y: 0, yanchor: 'bottom', x: 0 },
    hovermode: 'x unified',
  }, extra, { xaxis: axis(extra.xaxis), yaxis: axis(extra.yaxis) });
}

const PLOT_CONFIG = { displayModeBar: false, responsive: true };

// Explicit ticks through our own formatters: Plotly's SI format prints 1.4G, we want $1.4B.
function ticks(values, fmt, log) {
  const pos = values.filter(v => v > 0);
  const max = Math.max(...pos, 1e-9);
  const vals = [];
  if (log) {
    const hi = Math.ceil(Math.log10(max));
    const lo = Math.max(Math.floor(Math.log10(Math.min(...pos))), hi - 6);
    for (let e = lo; e <= hi; e++) vals.push(10 ** e);
  } else {
    const raw = max / 5, p = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map(k => k * p).find(v => v >= raw);
    for (let v = 0; v <= max + step * 0.999; v += step) vals.push(v);
  }
  return { tickmode: 'array', tickvals: vals, ticktext: vals.map(fmt) };
}

function pctTicks(values) {
  return ticks(values, v => pct(v, Math.abs(v * 100 - Math.round(v * 100)) > 1e-9 ? 1 : 0), false);
}

// One "table" toggle per chart (aria-pressed): swaps the plot for the same numbers as a plain table.
function tableView(el, columns, rows) {
  let t = document.getElementById(el.id + '-table');
  if (!t) {
    el.insertAdjacentHTML('beforebegin', '<button type="button" class="table-toggle" aria-pressed="false" aria-controls="' + el.id + '-table">table</button>');
    el.insertAdjacentHTML('afterend', '<div class="scroll-x" hidden><table id="' + el.id + '-table"></table></div>');
    t = document.getElementById(el.id + '-table');
    const b = el.previousElementSibling;
    b.onclick = () => {
      const on = b.getAttribute('aria-pressed') !== 'true';
      b.setAttribute('aria-pressed', on);
      el.hidden = on;
      t.parentElement.hidden = !on;
      if (!on && DRAWN.has(el)) Plotly.Plots.resize(el);  // it was laid out at zero width while hidden
    };
  }
  t.innerHTML = '<tr>' + columns.map(c => '<th>' + c + '</th>').join('') + '</tr>' +
    rows.map(r => '<tr>' + r.map(v => '<td>' + v + '</td>').join('') + '</tr>').join('');
}

// Charts draw when they first come near the viewport, and Plotly (1.3 MB) loads then, not with the page; after that, on every call.
const PLOTLY_SRC = 'https://cdn.jsdelivr.net/npm/plotly.js-cartesian-dist-min@2.35.2/plotly-cartesian.min.js';
let plotlyLoad = null;
function loadPlotly() {
  return plotlyLoad ||= new Promise((ok, fail) => {
    const s = document.createElement('script');
    s.src = PLOTLY_SRC; s.onload = ok; s.onerror = () => { banner(PLOTLY_SRC); fail(); };
    document.head.append(s);
  });
}
const DRAWN = new WeakSet(), PENDING = new Map();
const NEAR = new IntersectionObserver(es => es.forEach(e => {
  if (!e.isIntersecting) return;
  NEAR.unobserve(e.target);
  loadPlotly().then(() => {  // plot() calls made while loading update PENDING; the latest one draws
    DRAWN.add(e.target);
    Plotly.react(e.target, ...PENDING.get(e.target));
    PENDING.delete(e.target);
  });
}), { rootMargin: '400px' });

// Every chart goes through here: legend only with two or more series, and the table view gets the same rows.
function plot(id, traces, layout, columns, rows) {
  const el = typeof id === 'string' ? document.getElementById(id) : id;
  if (layout.showlegend == null) layout.showlegend = traces.length > 1;
  if (!layout.showlegend) layout.margin.b = 48;  // no legend row; automargin still grows it for the tick labels and title
  if (DRAWN.has(el)) Plotly.react(el, traces, layout, PLOT_CONFIG);
  else { if (!PENDING.has(el)) NEAR.observe(el); PENDING.set(el, [traces, layout, PLOT_CONFIG]); }
  tableView(el, columns, rows);
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

// Timestamp into el; past 8 h it turns red (class stale) so a dead cron shows on the page.
function stamp(el, text, ms) {
  el.textContent = text;
  el.classList.toggle('stale', (Date.now() - ms) / 36e5 > 8);
}

// Tile 1: the book. Large number is borrow; the rest as small cards.
function renderHeader() {
  const t = DATA.totals;
  stamp(document.getElementById('generated-at'), DATA.generated_at.replace('T', ' ').replace('+00:00', ' UTC'), Date.parse(DATA.generated_at));
  const ageH = (Date.now() - Date.parse(DATA.generated_at)) / 36e5;  // past 12 h, say so in words, not just a red stamp
  if (ageH > 12) document.getElementById('generated-at').parentElement.insertAdjacentHTML('afterend',
    '<p class="muted notice" role="status">Data last refreshed ' + Math.round(ageH) + ' hours ago; the refresh job runs on GitHub\'s best-effort schedule.</p>');
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

async function loadBacktest() {
  if (BT) return BT;
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

// Sequential scale, surface to accent; cells carry their number.
function heat(el, rowLabels, colLabels, z, xtitle) {
  const flat = z.flat().filter(v => v != null), text = z.map(row => row.map(usd));
  const traces = [{ type: 'heatmap', x: colLabels, y: rowLabels, z, text, texttemplate: '%{text}',
    textfont: { size: PHONE ? 9 : 12 }, colorscale: [[0, css('--card')], [1, css('--accent')]], zmin: 0, zmax: Math.max(...flat, 1), showscale: false,
    xgap: 2, ygap: 2, hovertemplate: '%{y} / %{x}: %{text}<extra></extra>' }];
  const layout = baseLayout({ showlegend: false, hovermode: 'closest',
    xaxis: { title: xtitle || '', type: 'category', side: 'bottom' },
    yaxis: { title: { text: 'LLTV', standoff: 12 }, type: 'category', autorange: 'reversed' } });  // Plotly puts a category axis title flush against its tick labels without an explicit standoff
  plot(el, traces, layout, ['LLTV'].concat(colLabels), rowLabels.map((l, i) => [l].concat(text[i])));
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
  if (!document.getElementById('totals')) return;  // writeup.html loads this file for the backtest figures only
  if (PHONE) document.querySelectorAll('details.fold').forEach(d => d.open = false);  // tables fold on phones
  const text = await get('summary.json');
  if (!text) { document.getElementById('generated-at').textContent = 'not available'; return; }
  DATA = JSON.parse(text);
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
  loadHistory().then(h => { HIST = h; renderTrend(); });
  if (DATA.markets[location.hash.slice(1)]) document.getElementById('book').scrollIntoView();  // the market anchor has no element of its own
}

main();
