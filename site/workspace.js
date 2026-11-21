'use strict';

let marketFilter = 'all';
let marketSort = 'borrow';
let shockDrop = 20;

function watchlistRows(markets, filter, sort) {
  return Object.entries(markets)
    .filter(([, m]) => filter !== 'attention' || (m.state.distance_to_capacity != null && m.state.distance_to_capacity <= 0.20))
    .sort((a, b) => sort === 'distance' ? (a[1].state.distance_to_capacity ?? Infinity) - (b[1].state.distance_to_capacity ?? Infinity) || b[1].state.borrow_usd - a[1].state.borrow_usd : b[1].state.borrow_usd - a[1].state.borrow_usd);
}

// Select an exact saved sample. No interpolation of position buckets or loss estimates.
function shockSample(curve, drop) {
  return curve.find(row => Math.abs(row.drop * 100 - drop) < 1e-7) || null;
}

function readWorkspaceUrl(q) {
  marketFilter = q.get('filter') === 'attention' ? 'attention' : 'all';
  marketSort = q.get('sort') === 'distance' ? 'distance' : 'borrow';
  const value = Number(q.get('shock') ?? 20);
  shockDrop = Number.isInteger(value) && value >= 0 && value <= 70 ? value : 20;
}

function writeWorkspaceUrl(url) {
  for (const [key, value, fallback] of [['filter', marketFilter, 'all'], ['sort', marketSort, 'borrow'], ['shock', shockDrop, 20]]) {
    if (value === fallback) url.searchParams.delete(key);
    else url.searchParams.set(key, value);
  }
}

function renderWatchlist() {
  const rows = watchlistRows(DATA.markets, marketFilter, marketSort);
  const el = document.getElementById('market-watchlist');
  document.getElementById('market-sort').value = marketSort;
  document.querySelectorAll('[data-filter]').forEach(b => {
    b.setAttribute('aria-pressed', String(b.dataset.filter === marketFilter));
    b.classList.toggle('active', b.dataset.filter === marketFilter);
  });
  document.getElementById('watchlist-count').textContent = rows.length + ' of ' + Object.keys(DATA.markets).length + ' markets' + (marketFilter === 'attention' ? ' with a threshold of 20% or less.' : '. Select a market name to investigate.') + (!rows.some(([key]) => key === market) ? ' Selected market ' + market + ' is outside this filter.' : '');
  if (!rows.length) {
    el.innerHTML = '<p class="empty">No market matches this filter. <button type="button" id="reset-market-filter">Show all markets</button></p>';
    document.getElementById('reset-market-filter').onclick = () => setMarketFilter('all');
    return;
  }
  el.innerHTML = '<div class="scroll-x" tabindex="0" role="region" aria-label="Market watchlist"><table class="watchlist-table"><thead><tr><th scope="col">Market</th><th scope="col">Borrowed <span class="muted">observed</span></th><th scope="col">Price fall to capacity <span class="muted">modeled</span></th><th scope="col" class="watch-extra">Stressed capacity</th><th scope="col">Status</th></tr></thead><tbody>' +
    rows.map(([key, m]) => {
      const s = m.state, d = s.distance_to_capacity;
      return '<tr' + (key === market ? ' class="is-selected"' : '') + '><th scope="row"><button type="button" data-market="' + key + '"' + (key === market ? ' aria-current="true"' : '') + '>' + key + '<span class="selected-label">' + (key === market ? 'Selected' : 'Inspect') + '</span></button></th><td>' + usd(s.borrow_usd) + '</td><td>' + (d == null ? '>70%' : pct(d, 0)) + '</td><td class="watch-extra">' + usd(s.capacity_ab_usd) + '</td><td><span class="market-state ' + band(d)[1] + '">' + band(d)[3] + '</span></td></tr>';
    }).join('') + '</tbody></table></div>';
  el.querySelectorAll('[data-market]').forEach(button => button.onclick = () => {
    const key = button.dataset.market;
    selectMarket(key);
    // Rerendering the selected row must not discard keyboard focus.
    el.querySelector('[data-market="' + key + '"]')?.focus({ preventScroll: true });
  });
}

function setMarketFilter(value) {
  marketFilter = value;
  syncViewUrl(true);
  renderWatchlist();
}

function capacityExplanation(m) {
  const d = m.depth || {}, dex = d.dex_capacity_usd?.['4.38'], cex = d.coinbase?.bid_depth_usd?.['4.38'];
  const total = m.state.capacity_ab_usd;
  if (dex == null || cex == null || total == null) return 'A complete venue breakdown is unavailable in this snapshot. The displayed capacity is the published model estimate.';
  // summarize.py publishes 50% of DEX + 30% of Coinbase depth. Only describe it
  // when the saved total actually reconciles; future snapshots may use other inputs.
  const expected = 0.5 * dex + 0.3 * cex;
  if (Math.abs(expected - total) > Math.max(1, Math.abs(total) * 0.001)) return 'Unstressed Coinbase bids ' + usd(cex) + ' and DEX capacity ' + usd(dex) + '; published stressed capacity ' + usd(total) + '. This snapshot does not expose a matching parameter breakdown.';
  return 'Capacity calculation: ' + usd(cex) + ' Coinbase bids × 30% + ' + usd(dex) + ' DEX capacity × 50% = ' + usd(total) + ' stressed capacity. Both venue figures use the 4.38% price-impact bucket; they are not the stressed total.';
}

function renderShock() {
  const m = DATA.markets[market], p = shockSample(m.liquidatable_curve, shockDrop);
  document.getElementById('shock-drop').value = shockDrop;
  document.getElementById('shock-label').textContent = shockDrop + '%';
  document.getElementById('shock-drop').setAttribute('aria-valuetext', shockDrop + ' percent instantaneous price fall');
  document.querySelectorAll('[data-shock]').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.shock) === shockDrop)));
  const el = document.getElementById('shock-result');
  if (!p) { el.innerHTML = '<p class="empty">No saved sample at this price fall for ' + market + '. Choose another point; no values have been interpolated.</p>'; return; }
  const cap = m.state.capacity_ab_usd;
  const gap = cap == null ? null : Math.max(0, p.borrow_usd - cap);
  el.innerHTML = '<h3>' + market + ' at a ' + shockDrop + '% price fall</h3><dl class="shock-values"><div><dt>Debt crossing liquidation</dt><dd>' + usd(p.borrow_usd) + '</dd></div><div><dt>Stressed sell capacity</dt><dd>' + usd(cap) + '</dd></div><div><dt>Above modeled capacity</dt><dd>' + usd(gap) + '</dd></div></dl>' +
    '<p class="shock-reading">' + (gap == null ? 'Capacity is unavailable for this book.' : gap > 0 ? usd(gap) + ' more debt is liquidatable than the modeled one-step capacity can absorb.' : 'Liquidatable debt is within the modeled one-step capacity at this sampled fall.') + '</p>' +
    '<p class="capacity-method muted">' + capacityExplanation(m) + '</p>' +
    '<p class="muted">' + num(p.count) + ' positions cross the line; ' + usd(p.bad_borrow_usd) + ' of debt is already past the bad-debt LTV. These are separate measures, not amounts to add.</p>';
}

function renderWorkspace() {
  renderWatchlist();
  renderShock();
  const d = DATA.markets[market].state.distance_to_capacity;
  const el = document.getElementById('selected-status');
  el.textContent = band(d)[3];
  el.className = 'status-word ' + band(d)[1];
}

function initWorkspace() {
  document.querySelectorAll('[data-filter]').forEach(b => b.onclick = () => setMarketFilter(b.dataset.filter));
  document.getElementById('market-sort').onchange = e => { marketSort = e.target.value; syncViewUrl(true); renderWatchlist(); };
  document.getElementById('shock-drop').oninput = e => { shockDrop = Number(e.target.value); syncViewUrl(); renderShock(); };
  document.querySelectorAll('[data-shock]').forEach(b => b.onclick = () => { shockDrop = Number(b.dataset.shock); syncViewUrl(true); renderShock(); });
  const theme = document.getElementById('theme-choice');
  theme.value = document.documentElement.dataset.theme || 'system';
  theme.onchange = () => {
    if (theme.value === 'system') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme.value;
    try { localStorage.setItem('spine-theme', theme.value); } catch {}
    renderAll(); renderBacktest();
  };
  document.getElementById('copy-view').onclick = async () => {
    const feedback = document.getElementById('copy-feedback');
    feedback.className = 'copy-feedback';
    try {
      await navigator.clipboard.writeText(document.getElementById('share-market').href);
      feedback.textContent = 'View link copied.';
    } catch { feedback.textContent = 'Copy the link from “Link to view” or your address bar.'; }
  };
  const nav = document.querySelector('nav.sections');
  const positions = new Map();
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => positions.set(e.target.id, e));
    const visible = [...positions.values()].filter(e => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
    if (!visible) return;
    nav.querySelectorAll('a[href^="#"]').forEach(a => {
      if (a.hash === '#' + visible.target.id) a.setAttribute('aria-current', 'location');
      else a.removeAttribute('aria-current');
    });
  }, { rootMargin: '-120px 0px -50% 0px' });
  document.querySelectorAll('main > section').forEach(el => observer.observe(el));
}

function renderPrimaryFailure() {
  document.body.dataset.unavailable = 'true';
  document.getElementById('data-age').textContent = 'unavailable';
  document.getElementById('selected-market').disabled = true;
  document.getElementById('risk-briefing').innerHTML = '<div class="empty" role="alert"><h3>The market snapshot could not be loaded.</h3><p>Your view is preserved. Retry the data, or read the saved methodology.</p><button id="retry-data" type="button">Retry data</button> <a href="writeup.html">Read the methodology</a></div>';
  document.getElementById('daily-changes').hidden = true;
  document.getElementById('now-evidence').hidden = true;
  document.getElementById('retry-data').onclick = () => location.reload();
}
