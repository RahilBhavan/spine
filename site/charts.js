'use strict';
// Plotly plumbing shared by the dashboard and the writeup: axes, layout, ticks, the table view, lazy Plotly loading and the heatmap.
// Loaded before app.js, whose formatters (usd, pct, css) and banner() these call at draw time.

// Every axis: solid hairline grid one shade off the surface, no zero line, margins grow to fit long tick labels and the title.
function chartColor(role) { return css('--chart-' + role); }

function axis(extra) {
  return Object.assign({ gridcolor:chartColor('grid'), gridwidth:1, showgrid:false, zeroline:false, color:chartColor('secondary'), tickfont:{size:12}, automargin:true }, extra || {});
}

function baseLayout(extra) {
  extra = extra || {};
  return Object.assign({
    paper_bgcolor:chartColor('bg'), plot_bgcolor:chartColor('bg'),
    font:{color:chartColor('ink'), family:'Arial, sans-serif', size:12},
    margin:{l:64,r:20,t:32,b:56},
    legend:{orientation:'h',yref:'container',y:0,yanchor:'bottom',x:0,font:{size:12}},
    hovermode:'x unified',
  }, extra, {xaxis:axis(extra.xaxis),yaxis:axis(Object.assign({showgrid:true},extra.yaxis))});
}

function chartTitle(el) {
  return el.closest('.fig')?.querySelector('h3')?.textContent || el.getAttribute('aria-label') || 'Chart';
}

function chartContext(id, summary, source, key) {
  const el = typeof id === 'string' ? document.getElementById(id) : id;
  let note = document.getElementById(el.id + '-summary');
  if (!note) {
    el.insertAdjacentHTML('beforebegin','<p class="chart-summary" id="' + el.id + '-summary"></p>');
    note = document.getElementById(el.id + '-summary');
    el.insertAdjacentHTML('afterend','<p class="chart-source" id="' + el.id + '-source"></p>');
  }
  note.textContent = summary;
  document.getElementById(el.id + '-source').textContent = source;
  el.setAttribute('role','figure');
  el.setAttribute('aria-label', chartTitle(el));
  el.setAttribute('aria-describedby',note.id + ' ' + el.id + '-source');
  if (key) {
    let list = document.getElementById(el.id + '-key');
    if (!list) { note.insertAdjacentHTML('afterend','<ul class="chart-key" id="' + el.id + '-key"></ul>'); list=document.getElementById(el.id + '-key'); }
    list.innerHTML = key.map(([label,kind]) => '<li><span aria-hidden="true" class="key-mark ' + kind + '"></span>' + esc(label) + '</li>').join('');
  }
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
  let t=document.getElementById(el.id + '-table');
  if (!t) {
    el.insertAdjacentHTML('beforebegin','<button type="button" class="table-toggle" aria-pressed="false" aria-controls="' + el.id + '-table">Data table</button>');
    el.insertAdjacentHTML('afterend','<div class="scroll-x chart-data" tabindex="0" role="region" hidden><table id="' + el.id + '-table"></table></div>');
    t=document.getElementById(el.id + '-table');
    const b=el.previousElementSibling;
    b.onclick=() => {
      const on=b.getAttribute('aria-pressed')!=='true';
      b.setAttribute('aria-pressed',String(on)); el.hidden=on; t.parentElement.hidden=!on;
      if (!on && DRAWN.has(el)) Plotly.Plots.resize(el);
    };
  }
  const title=chartTitle(el), b=document.querySelector('[aria-controls="' + t.id + '"]');
  b.setAttribute('aria-label','Data table: ' + title);
  t.parentElement.setAttribute('aria-label',title + ' data');
  t.innerHTML='<caption>' + esc(title) + '. Display values are rounded; missing estimates are labeled.</caption><thead><tr>' + columns.map(c=>'<th scope="col">'+esc(c)+'</th>').join('')+'</tr></thead><tbody>' +
    rows.map(r=>'<tr>'+r.map((v,i)=>i===0?'<th scope="row">'+esc(v)+'</th>':'<td>'+esc(v)+'</td>').join('')+'</tr>').join('')+'</tbody>';
}

// Charts draw when they first come near the viewport, and Plotly (1.3 MB) loads then, not with the page; after that, on every call.
const PLOTLY_SRC = 'https://cdn.jsdelivr.net/npm/plotly.js-cartesian-dist-min@2.35.2/plotly-cartesian.min.js';
let plotlyLoad = null;
function loadPlotly() {
  return plotlyLoad ||= new Promise((ok, fail) => {
    const s = document.createElement('script');
    s.src = PLOTLY_SRC; s.onload = ok; s.onerror = () => fail(new Error('Could not load chart library'));
    document.head.append(s);
  });
}
const DRAWN=new WeakSet(), PENDING=new Map(), PAINTING=new WeakSet();
async function paintChart(el) {
  if (PAINTING.has(el)) return;
  PAINTING.add(el);
  try {
    await loadPlotly();
    while (PENDING.has(el)) {
      const config=PENDING.get(el); PENDING.delete(el);
      await Plotly.react(el,...config); DRAWN.add(el);
    }
  } catch {
    DRAWN.delete(el);
    el.textContent='Chart unavailable. Use the Data table button for the same data.';
    banner(PLOTLY_SRC);
  } finally { PAINTING.delete(el); }
}
const NEAR=new IntersectionObserver(es=>es.forEach(e=>{
  if (!e.isIntersecting) return;
  NEAR.unobserve(e.target); paintChart(e.target);
}),{rootMargin:'400px'});

function plot(id,traces,layout,columns,rows) {
  const el=typeof id==='string'?document.getElementById(id):id;
  if (layout.showlegend==null) layout.showlegend=traces.length>1;
  PENDING.set(el,[traces,layout,PLOT_CONFIG]);
  tableView(el,columns,rows);
  if (DRAWN.has(el)) paintChart(el);
  else NEAR.observe(el);
}

// Every heat value has an opaque light backing. Contrast never depends on
// which shade of blue lies underneath, including simulated color-vision loss.
function heatText(value) { return chartColor(value==null?'secondary':'ink'); }

// Sequential scale, surface to accent; cells carry their number.
function heat(el,rowLabels,colLabels,z,xtitle,scaleMax) {
  const node=typeof el==='string'?document.getElementById(el):el;
  const phone=window.matchMedia('(max-width:700px)').matches;
  const max=Math.max(scaleMax || 0,...z.flat().filter(v=>v!=null),1);
  // On phones, five LLTV columns fit better than seven crash/capital columns.
  const x=phone?rowLabels:colLabels, y=phone?colLabels:rowLabels;
  const values=phone?colLabels.map((_,j)=>rowLabels.map((_,i)=>z[i][j])):z;
  const annotations=[];
  values.forEach((row,i)=>row.forEach((value,j)=>annotations.push({x:x[j],y:y[i],text:value==null?'Not run':usd(value),showarrow:false,font:{size:12,color:heatText(value)},bgcolor:chartColor('bg'),borderpad:1})));
  const traces=[{type:'heatmap',x,y,z:values,zmin:0,zmax:max,colorscale:[[0,chartColor('bg')],[1,chartColor('blue')]],showscale:false,xgap:2,ygap:2,hoverongaps:false,customdata:values.map(r=>r.map(v=>v==null?'Not run':usd(v))),hovertemplate:'%{y} / %{x}: %{customdata}<extra></extra>'}];
  node.style.height=(phone?Math.max(340,y.length*42+100):Math.max(300,y.length*44+100))+'px';
  const layout=baseLayout({showlegend:false,hovermode:'closest',margin:{l:phone?84:72,r:12,t:phone?48:20,b:phone?32:64},
    xaxis:{title:phone?'LLTV':xtitle||'',type:'category',side:phone?'top':'bottom',showgrid:false,tickfont:{size:12}},
    yaxis:{title:phone?'':{text:'LLTV',standoff:12},type:'category',autorange:'reversed',showgrid:false,tickfont:{size:12}},annotations});
  plot(node,traces,layout,['LLTV'].concat(colLabels),rowLabels.map((label,i)=>[label].concat(z[i].map(v=>v==null?'Not run':usd(v)))));
  let scale=document.getElementById(node.id+'-scale');
  if (!scale) {node.insertAdjacentHTML('afterend','<p class="chart-scale" id="'+node.id+'-scale"></p>');scale=document.getElementById(node.id+'-scale');}
  scale.innerHTML='<span>$0</span><span class="scale-ramp" aria-hidden="true"></span><span>'+usd(max)+'</span><span>Same scale across this market’s scenarios and capital settings. $0 = replay ran and modeled no amount for this measure. Not run = no matching replay result.</span>';
}
