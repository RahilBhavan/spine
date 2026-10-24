'use strict';
// Plotly plumbing shared by the dashboard and the writeup: axes, layout, ticks, the table view, lazy Plotly loading and the heatmap.
// Loaded before app.js, whose formatters (usd, pct, css) and banner() these call at draw time.

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
