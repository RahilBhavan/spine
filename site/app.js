'use strict';

let DATA = null;
let BT = null;  // backtest.json, loaded on first visit to the Backtest tab
let market = 'cbBTC';
let cbOnly = false;
let logY = false;
let curveLogY = true;
let tab = 'live';
let btMarket = 'cbBTC';
let btScenario = 'AB';

const WINDOWS = ['Mar2020', 'May2021', 'FTX2022', 'Aug2024', 'Oct2025', 'Feb2026', 'Jun2026'];
const LLTVS = [0.86, 0.80, 0.77, 0.70, 0.625];
const GAUGE_BANDS = [[0.10, 'red'], [0.20, 'amber'], [Infinity, 'green']];

function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function usd(x) {
  if (x == null || isNaN(x)) return '-';
  const a = Math.abs(x);
  if (a >= 1e9) return '$' + (x / 1e9).toFixed(2) + 'B';
  if (a >= 1e6) return '$' + (x / 1e6).toFixed(1) + 'M';
  if (a >= 1e3) return '$' + (x / 1e3).toFixed(1) + 'k';
  return '$' + x.toFixed(0);
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

function musd(x) {
  if (x == null) return '';
  if (x < 5e4) return '0';
  return '$' + (x / 1e6).toFixed(x < 1e6 ? 2 : 1) + 'M';
}

function dur(min) {
  if (min == null) return '-';
  if (min < 120) return min.toFixed(0) + ' min';
  if (min < 48 * 60) return (min / 60).toFixed(0) + ' h';
  return (min / 1440).toFixed(1) + ' d';
}

function baseLayout(extra) {
  const fg = css('--fg'), muted = css('--muted'), grid = css('--grid');
  return Object.assign({
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: fg, family: 'inherit', size: 12 },
    margin: { l: 56, r: 56, t: 12, b: 64 },
    xaxis: { gridcolor: grid, zeroline: false, color: muted },
    yaxis: { gridcolor: grid, zeroline: false, color: muted },
    legend: { orientation: 'h', y: -0.18, x: 0 },
    hovermode: 'x unified',
    showlegend: true,
  }, extra || {});
}

const PLOT_CONFIG = { displayModeBar: false, responsive: true };

// Explicit USD ticks: Plotly's SI format prints 1.4G, we want $1.4B.
function usdTicks(values, log) {
  const pos = values.filter(v => v > 0);
  const max = Math.max(...pos, 1);
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
  return { tickmode: 'array', tickvals: vals, ticktext: vals.map(usd) };
}

function renderHeader() {
  const t = DATA.totals;
  document.getElementById('generated-at').textContent = DATA.generated_at.replace('T', ' ').replace('+00:00', ' UTC');
  cards(document.getElementById('totals'), [
    ['Total borrow', usd(t.borrow_usd)],
    ['Total collateral', usd(t.collateral_usd)],
    ['Book LTV', pct(t.borrow_usd / t.collateral_usd)],
    ['Positions with debt', num(t.n_positions)],
    ['Coinbase share', pct(t.coinbase_share_borrow)],
  ]);
}

function buttons(id, keys, current, onpick) {
  const el = document.getElementById(id);
  el.innerHTML = keys.map(k => '<button data-k="' + k + '" class="' + (k === current ? 'active' : '') + '">' + k + '</button>').join('');
  el.querySelectorAll('button').forEach(b => b.onclick = () => onpick(b.dataset.k));
}

function renderButtons() {
  buttons('market-buttons', Object.keys(DATA.markets), market, k => { market = k; renderAll(); });
}

function renderGauges() {
  const el = document.getElementById('gauges');
  cards(el, Object.entries(DATA.markets).map(([name, m]) => {
    const d = m.state.distance_to_capacity;
    const band = d == null ? 'green' : GAUGE_BANDS.find(([lim]) => d < lim)[1];
    return [name, d == null ? '> 70%' : '-' + pct(d, 0), band];
  }));
  el.querySelectorAll('.card').forEach((c, i) => c.onclick = () => { market = Object.keys(DATA.markets)[i]; showTab('live'); renderAll(); });
}

function showTab(name) {
  tab = name;
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.getElementById('tab-live').hidden = name !== 'live';
  document.getElementById('tab-backtest').hidden = name !== 'backtest';
  if (name === 'backtest') renderBacktest();
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
  const x = m.ltv_hist.map(b => b.lo + 0.01);
  const accent = css('--accent'), danger = css('--danger'), muted = css('--muted');
  const traces = [
    { type: 'bar', x, y: m.ltv_hist.map(b => b[k + 'borrow_usd']), name: 'Borrow USD', marker: { color: accent }, width: 0.02,
      hovertemplate: 'LTV %{x:.0%}: %{y:$,.3s}<extra></extra>' },
    { type: 'scatter', mode: 'lines', x, y: m.ltv_hist.map(b => b[k + 'count']), name: 'Positions', yaxis: 'y2',
      line: { color: muted, width: 1.5 }, hovertemplate: '%{y} positions<extra></extra>' },
  ];
  const vline = (v, color, text) => ({ type: 'line', x0: v, x1: v, y0: 0, y1: 1, yref: 'paper', line: { color, width: 1.5, dash: 'dash' }, label: { text, textposition: 'end', font: { color } } });
  const layout = baseLayout({
    barmode: 'overlay', margin: { l: 56, r: 56, t: 40, b: 64 },  // room for the rotated LLTV / 1/LIF labels above the plot
    xaxis: { title: 'LTV', tickformat: '.0%', range: [0, 1], gridcolor: css('--grid'), color: muted },
    yaxis: Object.assign({ title: 'Borrow USD', automargin: true, type: logY ? 'log' : 'linear', gridcolor: css('--grid'), color: muted }, usdTicks(traces[0].y, logY)),
    yaxis2: { title: 'Positions', overlaying: 'y', side: 'right', showgrid: false, type: logY ? 'log' : 'linear', color: muted },
    shapes: [vline(m.state.lltv, danger, 'LLTV ' + pct(m.state.lltv)), vline(m.state.bad_debt_ltv, danger, '1/LIF ' + pct(m.state.bad_debt_ltv))],
  });
  Plotly.react('chart-ltv', traces, layout, PLOT_CONFIG);
}

function renderHf(m) {
  const accent = css('--accent'), danger = css('--danger'), muted = css('--muted');
  const traces = [{ type: 'scatter', mode: 'lines', x: m.hf_cdf.map(p => p.hf), y: m.hf_cdf.map(p => p.share), name: 'Share of borrow with HF below',
    line: { color: accent, width: 2.5, shape: 'hv' }, fill: 'tozeroy', fillcolor: css('--band'), hovertemplate: 'HF < %{x:.2f}: %{y:.1%} of borrow<extra></extra>' }];
  const layout = baseLayout({
    margin: { l: 56, r: 56, t: 40, b: 64 },
    xaxis: { title: 'Health factor', range: [1, 3], gridcolor: css('--grid'), color: muted },
    showlegend: false,
    yaxis: { title: 'Share of borrow USD', tickformat: '.0%', range: [0, 1], gridcolor: css('--grid'), color: muted },
    shapes: [{ type: 'line', x0: 1.1, x1: 1.1, y0: 0, y1: 1, yref: 'paper', line: { color: danger, width: 1.5, dash: 'dash' }, label: { text: 'HF 1.1', textposition: 'end', font: { color: danger } } }],
  });
  Plotly.react('chart-hf', traces, layout, PLOT_CONFIG);
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
  const x = m.liquidatable_curve.map(c => c.drop);
  const accent = css('--accent'), danger = css('--danger'), muted = css('--muted');
  const cap = capacity(m);
  const traces = [
    { type: 'scatter', mode: 'lines', x, y: m.liquidatable_curve.map(c => c[k + 'borrow_usd']), name: 'Liquidatable borrow',
      line: { color: accent, width: 2.5 }, fill: 'tozeroy', fillcolor: css('--band'), hovertemplate: '%{y:$,.3s}<extra>liquidatable</extra>' },
    { type: 'scatter', mode: 'lines', x, y: m.liquidatable_curve.map(c => c[k + 'bad_borrow_usd']), name: 'Bad-debt zone (LTV > 1/LIF)',
      line: { color: danger, width: 2 }, hovertemplate: '%{y:$,.3s}<extra>bad-debt zone</extra>' },
  ];
  const shapes = [], annotations = [];
  // Labels sit at the left, above their line; in linear mode both lines hug zero so the upper one is shifted up.
  const hline = (y, text, color, yshift) => {
    if (y == null) return;
    const yy = curveLogY ? Math.log10(y) : y;  // annotations take log10 units on a log axis; shapes take raw values
    shapes.push({ type: 'line', x0: 0, x1: 1, xref: 'paper', yref: 'y', y0: y, y1: y, layer: 'above', line: { color, width: 1.5, dash: 'dash' } });
    annotations.push({ x: 0.005, xref: 'paper', yref: 'y', y: yy, yshift, text: text + ' ' + usd(y), showarrow: false, xanchor: 'left', yanchor: 'bottom', font: { color, size: 11 } });
  };
  hline(cap.cex, 'Coinbase bids within 4.38%', muted, curveLogY ? 0 : 16);
  hline(cap.dex, 'DEX capacity at 4.38%', muted, 0);
  const layout = baseLayout({
    xaxis: { title: 'Instantaneous price drop', tickformat: '.0%', gridcolor: css('--grid'), color: muted },
    yaxis: Object.assign({ title: 'Borrow USD', automargin: true, type: curveLogY ? 'log' : 'linear', rangemode: curveLogY ? 'normal' : 'tozero', gridcolor: css('--grid'), color: muted },
      usdTicks(traces[0].y.concat(traces[1].y, [cap.cex, cap.dex]), curveLogY)),
    shapes, annotations,
  });
  Plotly.react('chart-curve', traces, layout, PLOT_CONFIG);
}

function renderLiq(m) {
  const days = m.liquidations_daily;
  const muted = css('--muted'), accent = css('--accent');
  const top = days.slice().sort((a, b) => b.repaid_usd - a.repaid_usd).slice(0, 5);
  const traces = [{
    type: 'bar', x: days.map(d => d.day), y: days.map(d => d.repaid_usd), name: 'Repaid USD', marker: { color: accent },
    customdata: days.map(d => d.n), hovertemplate: '%{y:$,.3s} (%{customdata} liquidations)<extra></extra>',
  }];
  const layout = baseLayout({
    showlegend: false,
    xaxis: { type: 'date', gridcolor: css('--grid'), color: muted },
    yaxis: Object.assign({ title: 'Repaid USD', gridcolor: css('--grid'), color: muted }, usdTicks(traces[0].y, false)),
    annotations: top.map(d => ({ x: d.day, y: d.repaid_usd, text: d.day + ' ' + usd(d.repaid_usd), showarrow: true, arrowhead: 0, arrowcolor: muted, ax: 0, ay: -28, font: { size: 10, color: muted } })),
  });
  Plotly.react('chart-liq', traces, layout, PLOT_CONFIG);
}

function renderBorrowers(m) {
  const rows = (cbOnly ? m.top_borrowers.filter(b => b.is_coinbase) : m.top_borrowers);
  document.getElementById('table-borrowers').innerHTML =
    '<tr><th>#</th><th>Address</th><th>Borrow</th><th>Collateral</th><th>LTV</th><th>HF</th></tr>' +
    rows.map((b, i) =>
      '<tr><td>' + (i + 1) + '</td><td>' + link(b.user) + (b.is_coinbase ? '<span class="badge">Coinbase</span>' : '') +
      '</td><td>' + usd(b.borrow_usd) + '</td><td>' + usd(b.collateral_usd) + '</td><td>' + pct(b.ltv) +
      '</td><td>' + (b.health_factor == null ? '-' : b.health_factor.toFixed(2)) + '</td></tr>').join('');
}

function renderLiquidators(m) {
  document.getElementById('table-liquidators').innerHTML =
    '<tr><th>#</th><th>Liquidator</th><th>Liquidations</th><th>Repaid</th><th>Share</th></tr>' +
    m.liquidators_top.map((l, i) =>
      '<tr><td>' + (i + 1) + '</td><td>' + link(l.liquidator) + '</td><td>' + num(l.count) +
      '</td><td>' + usd(l.repaid_usd) + '</td><td>' + pct(l.share) + '</td></tr>').join('');
}

// ---- Backtest (data/backtest.json). Also used by writeup.html, which loads this file and calls renderHeatmap / renderWarn.

async function loadBacktest() {
  if (BT) return BT;
  const r = await fetch('../data/backtest.json');
  if (!r.ok) return null;
  // json.dump writes the unlimited-capital rows as Infinity, which JSON.parse rejects; 1e999 parses to Infinity.
  BT = JSON.parse((await r.text()).replace(/\bInfinity\b/g, '1e999'));
  const d = BT.defaults, c = BT.calibrated || {};
  const grid = BT.runs.filter(r => r.book === 'today');
  const counts = {};
  grid.forEach(r => counts[r.cex_cap_usd] = (counts[r.cex_cap_usd] || 0) + 1);
  BT.cexCap = +Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0];
  BT.base = r => r.book === 'today' && r.k_dex === d.k_dex && r.k_cex === d.k_cex && r.lag_bars === d.lag_bars && r.margin === d.margin &&
    r.resp_share === c.resp_share && r.react_min === c.react_min &&
    ['beta', 'seed', 'close_target', 'full_below_usd'].every(k => !(k in d) || r[k] === d[k]);  // sensitivity sweeps stay out of the grid view
  return BT;
}

function btRows(bt, f) {
  return bt.runs.filter(r => bt.base(r) && Object.keys(f).every(k => r[k] === f[k]));
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

function heat(el, rowLabels, colLabels, z, xtitle) {
  const muted = css('--muted');
  const flat = z.flat().filter(v => v != null);
  const traces = [{ type: 'heatmap', x: colLabels, y: rowLabels, z, text: z.map(row => row.map(musd)), texttemplate: '%{text}',
    textfont: { size: 12 }, colorscale: [[0, css('--card')], [1, css('--danger')]], zmin: 0, zmax: Math.max(...flat, 1), showscale: false,
    xgap: 2, ygap: 2, hovertemplate: '%{y} / %{x}: %{text}<extra></extra>' }];
  const layout = baseLayout({ showlegend: false, hovermode: 'closest', margin: { l: 56, r: 12, t: 12, b: 48 },
    xaxis: { title: xtitle || '', type: 'category', side: 'bottom', gridcolor: css('--grid'), color: muted },
    yaxis: { title: 'LLTV', type: 'category', autorange: 'reversed', gridcolor: css('--grid'), color: muted } });
  Plotly.react(el, traces, layout, PLOT_CONFIG);
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
  heat(el, lltvs.map(l => pct(l, 0)), caps.map(c => c === Infinity ? 'depth-limited only' : (c / bt.cexCap).toFixed(0) + 'x'), z, 'Liquidator daily capital, multiple of ' + usd(bt.cexCap));
}

function renderWarn(el, bt, mkt) {
  const muted = css('--muted'), accent = css('--accent');
  const y = WINDOWS.map(w => { const r = pickCap(btRows(bt, { market: mkt, window: w, lltv: 0.86, scenario: 'AB', cex_cap_usd: bt.cexCap })); return r ? r.warn_minutes_p50 : null; });
  const traces = [{ type: 'bar', x: WINDOWS, y: y.map(v => v == null ? null : v / 60), text: y.map(dur), textposition: 'outside', name: 'Warning time p50',
    marker: { color: accent }, cliponaxis: false, hovertemplate: '%{text}<extra></extra>' }];
  const layout = baseLayout({ showlegend: false, hovermode: 'closest', margin: { l: 56, r: 12, t: 24, b: 48 },
    xaxis: { type: 'category', gridcolor: css('--grid'), color: muted },
    yaxis: { title: 'Hours', gridcolor: css('--grid'), color: muted, rangemode: 'tozero' } });
  Plotly.react(el, traces, layout, PLOT_CONFIG);
}

async function renderBacktest() {
  const bt = await loadBacktest();
  const note = document.getElementById('bt-note');
  if (!bt) { note.textContent = 'failed to load ../data/backtest.json'; return; }
  const markets = [...new Set(bt.runs.filter(bt.base).map(r => r.market))];
  if (!markets.includes(btMarket)) btMarket = markets[0];
  const c = bt.calibrated || {};
  note.textContent = 'Grid rows at the fitted borrower response (' + pct(c.resp_share, 0) + ' within ' + c.react_min + ' min), depth multipliers DEX ' +
    bt.defaults.k_dex + ' / CEX ' + bt.defaults.k_cex + ', liquidator daily capital ' + usd(bt.cexCap) + '. Max draw 75%, or 60% where the LLTV is below 75%.';
  buttons('bt-market-buttons', markets, btMarket, k => { btMarket = k; renderBacktest(); });
  buttons('bt-scenario-buttons', ['A', 'AB', 'ABC'], btScenario, k => { btScenario = k; renderBacktest(); });
  buttons('bt-metric-buttons', Object.keys(METRICS), btMetric, k => { btMetric = k; renderBacktest(); });
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
  renderHf(m);
  renderCurve(m);
  renderLiq(m);
  renderBorrowers(m);
  renderLiquidators(m);
}

async function main() {
  if (!document.getElementById('totals')) return;  // writeup.html loads this file for the backtest figures only
  const r = await fetch('../data/summary.json');
  if (!r.ok) {
    document.getElementById('generated-at').textContent = 'failed to load ../data/summary.json (' + r.status + ')';
    return;
  }
  DATA = await r.json();
  if (DATA.markets[location.hash.slice(1)]) market = location.hash.slice(1);  // #cbXRP deep link
  if (!DATA.markets[market]) market = Object.keys(DATA.markets)[0];
  document.getElementById('cb-only').onchange = e => { cbOnly = e.target.checked; renderAll(); };
  document.getElementById('log-y').onchange = e => { logY = e.target.checked; renderLtv(DATA.markets[market]); };
  document.getElementById('chart-curve').insertAdjacentHTML('beforebegin',
    '<p class="muted"><label class="toggle"><input type="checkbox" id="log-y-curve" checked> log y</label></p>');
  document.getElementById('log-y-curve').onchange = e => { curveLogY = e.target.checked; renderCurve(DATA.markets[market]); };
  document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => showTab(b.dataset.tab));
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { renderAll(); if (tab === 'backtest') renderBacktest(); });
  renderHeader();
  renderAll();
  if (location.hash === '#backtest') showTab('backtest');
}

main();
