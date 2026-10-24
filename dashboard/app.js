'use strict';
let D, S = {};
const $ = s => document.querySelector(s), esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const mname = id => (D.models[id] || {}).name || id, mvend = id => (D.models[id] || {}).vendor || 'Unknown';
const label = m => { const k = D.key.find(k => k.metric === m.id); return k ? k.label : m.name.replace(/_/g, ' '); };
const fmt = (v, u) => v == null ? '-' : (u && u.startsWith('USD') ? '$' + (+v).toFixed(v < 1 ? 3 : 2) : Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : (+v).toFixed(Math.abs(v) < 1 ? 3 : 1));
const cite = asof => `<div class="cite asof">As of ${esc(asof || 'n/a')}</div>`;
const mlink = id => `<a class="m" href="#model=${encodeURIComponent(id)}">${esc(mname(id))}</a>`;
function readHash() { S = Object.fromEntries(new URLSearchParams(location.hash.slice(1))); }
function writeHash() { const p = new URLSearchParams(); for (const k of ['vendor','metric','from','to','q']) if (S[k]) p.set(k, S[k]); location.hash = p.toString(); }
function inRange(d) { return (!S.from || !d || d >= S.from) && (!S.to || !d || d <= S.to); }
function rows(mid) { // filtered latest rows for a metric, sorted best first
  const m = D.metrics[mid]; if (!m) return [];
  let r = (D.latest[mid] || []).filter(x => inRange(x[2]) && (!S.vendor || mvend(x[0]) === S.vendor) && (!S.q || mname(x[0]).toLowerCase().includes(S.q.toLowerCase())));
  return r.sort((a, b) => m.hib ? b[1] - a[1] : a[1] - b[1]);
}
function blended(id) { const p = D.prices[id]; if (!p || !p.input || !p.output) return null; return {usd: (3 * p.input.usd + p.output.usd) / 4, fp: p.input.list && p.output.list, at: p.output.at}; }
function initFilters() {
  const vs = [...new Set(Object.values(D.models).map(m => m.vendor))].sort();
  $('#f-vendor').innerHTML = '<option value="">All vendors</option>' + vs.map(v => `<option>${esc(v)}</option>`).join('');
  const ms = Object.values(D.metrics).sort((a, b) => b.n - a.n);
  $('#f-metric').innerHTML = '<option value="">Key metrics</option>' + ms.map(m => `<option value="${m.id}">${esc(label(m))} (${m.n})</option>`).join('');
  $('#dl-models').innerHTML = Object.values(D.models).slice(0, 3000).map(m => `<option value="${esc(m.name)}">`).join('');
  for (const [k, el] of [['vendor','#f-vendor'],['metric','#f-metric'],['from','#f-from'],['to','#f-to'],['q','#f-model']])
    $(el).addEventListener('change', e => { S[k] = e.target.value; delete S.model; writeHash(); });
  $('#f-reset').onclick = () => { S = {}; writeHash(); };
}
function syncFilters() { for (const [k, el] of [['vendor','#f-vendor'],['metric','#f-metric'],['from','#f-from'],['to','#f-to'],['q','#f-model']]) $(el).value = S[k] || ''; }
function leaderCard(mid, lab, n = 6) {
  const m = D.metrics[mid], r = rows(mid).slice(0, n); if (!r.length) return '';
  const asof = r.reduce((a, x) => x[2] > a ? x[2] : a, '') || m.as_of;
  return `<div class="card"><h3>${esc(lab || label(m))}<small>${m.hib ? 'higher is better' : 'lower is better'}</small></h3><ol class="lead">${r.map((x, i) => `<li><span class="r">${i + 1}</span><span class="n">${mlink(x[0])} <span class="vd">${esc(mvend(x[0]))}</span></span><span class="v">${fmt(x[1], m.unit)}</span></li>`).join('')}</ol>${cite(asof)}</div>`;
}
function scatter(mid) {
  const m = D.metrics[mid], W = 860, H = 420, P = 50;
  const pts = rows(mid).map(x => ({id: x[0], y: x[1], p: blended(x[0])})).filter(o => o.p && o.p.usd > 0);
  if (pts.length < 3) return `<div class="note">Not enough models with both a price and ${esc(label(m))} under these filters.</div>`;
  const lx = v => Math.log10(v), xs = pts.map(o => lx(o.p.usd)), ys = pts.map(o => o.y);
  const x0 = Math.floor(Math.min(...xs)), x1 = Math.ceil(Math.max(...xs)), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const X = v => P + (lx(v) - x0) / (x1 - x0 || 1) * (W - 2 * P), Y = v => H - P - (v - y0) / (y1 - y0 || 1) * (H - 2 * P);
  let g = '';
  for (let e = x0; e <= x1; e++) g += `<line x1="${X(10 ** e)}" x2="${X(10 ** e)}" y1="${P / 2}" y2="${H - P}" stroke="#EFE8D6"/><text x="${X(10 ** e)}" y="${H - P + 18}" font-size="11" text-anchor="middle" fill="#5C6480">$${10 ** e >= 1 ? 10 ** e : (10 ** e).toFixed(Math.abs(e))}</text>`;
  for (let i = 0; i <= 4; i++) { const v = y0 + (y1 - y0) * i / 4; g += `<line x1="${P}" x2="${W - P}" y1="${Y(v)}" y2="${Y(v)}" stroke="#EFE8D6"/><text x="${P - 6}" y="${Y(v) + 4}" font-size="11" text-anchor="end" fill="#5C6480">${fmt(v)}</text>`; }
  const top = new Set(), placed = []; for (const o of [...pts].sort((a, b) => m.hib ? b.y - a.y : a.y - b.y).slice(0, 14)) { const px = X(o.p.usd), py = Y(o.y); if (top.size < 7 && !placed.some(q => Math.abs(q[0] - px) < 170 && Math.abs(q[1] - py) < 15)) { top.add(o.id); placed.push([px, py]); } }
  const dots = pts.map(o => `<a href="#model=${encodeURIComponent(o.id)}"><circle cx="${X(o.p.usd)}" cy="${Y(o.y)}" r="5.5" fill="${o.p.fp ? '#C6A241' : '#fff'}" stroke="${o.p.fp ? '#8A6410' : '#28336B'}" stroke-width="1.5"><title>${esc(mname(o.id))}: ${fmt(o.y)} at $${o.p.usd.toFixed(3)}/1M blended (${o.p.fp ? 'list price' : 'market price'})</title></circle>${top.has(o.id) ? `<text x="${X(o.p.usd) + 8}" y="${Y(o.y) + 4}" font-size="11" fill="#1C2135">${esc(mname(o.id))}</text>` : ''}</a>`).join('');
  const asof = pts.reduce((a, o) => o.p.at > a ? o.p.at : a, '');
  return `<svg class="chart" viewBox="0 0 ${W} ${H}">${g}${dots}<text x="${W / 2}" y="${H - 8}" font-size="12" text-anchor="middle" fill="#1C2135">Blended price, USD per 1M tokens (3:1 input:output, log scale)</text><text transform="translate(14 ${H / 2}) rotate(-90)" font-size="12" text-anchor="middle" fill="#1C2135">${esc(label(m))}</text></svg>
  <div class="cite">Y: ${esc(label(m))} · as of ${esc(m.as_of)}. X: price per model, vendor list price where available (gold), otherwise market price (hollow) · latest price as of ${esc(asof)}. ${pts.length} models plotted.</div>`;
}
function vendorShare(mid) {
  const r = rows(mid).slice(0, 50), c = {}; r.forEach(x => c[mvend(x[0])] = (c[mvend(x[0])] || 0) + 1);
  const t = Object.entries(c).sort((a, b) => b[1] - a[1]).slice(0, 12), mx = t.length ? t[0][1] : 1;
  const all = {}; Object.values(D.models).forEach(m => { if (!S.vendor || m.vendor === S.vendor) all[m.vendor] = (all[m.vendor] || 0) + 1; });
  const ta = Object.entries(all).filter(e => e[0] !== 'Unknown' && e[0] !== 'unknown').sort((a, b) => b[1] - a[1]).slice(0, 12), ma = ta.length ? ta[0][1] : 1;
  const bars = (t, mx, tot) => t.map(([v, n]) => `<div class="bar"><span class="l">${esc(v)}</span><span class="t"><span class="f" style="display:block;width:${100 * n / mx}%"></span></span><span class="c">${n}${tot ? ' · ' + Math.round(100 * n / tot) + '%' : ''}</span></div>`).join('');
  return `<div class="grid g2"><div class="card"><h3>Share of Top ${r.length} on ${esc(label(D.metrics[mid]))}</h3>${bars(t, mx, r.length)}${cite(D.metrics[mid].as_of)}</div>
  <div class="card"><h3>Models Tracked per Vendor</h3>${bars(ta, ma, 0)}<div class="cite">All tracked models · build ${esc(D.built.slice(0, 10))}</div></div></div>`;
}
function moversNew() {
  const mv = D.movers.filter(x => D.metrics[x.metric] && (!S.vendor || mvend(x.model) === S.vendor) && inRange(x.to_at)).filter((x, i, a) => a.findIndex(y => y.model === x.model) === i).slice(0, 14);
  const nw = D.new.filter(id => (!S.vendor || mvend(id) === S.vendor) && inRange(D.models[id].first)).slice(0, 14);
  return `<div class="grid g2"><div class="card"><h3>Score Movers<small>latest two dated readings</small></h3>${mv.length ? `<table><tr><th>Model</th><th>Metric</th><th>Change</th><th>Dates</th></tr>${mv.map(x => { const m = D.metrics[x.metric], d = x.to - x.from, good = m.hib ? d > 0 : d < 0; return `<tr><td>${mlink(x.model)}</td><td>${esc(label(m))}</td><td class="num ${good ? 'up' : 'down'}">${fmt(x.from, m.unit)} → ${fmt(x.to, m.unit)}</td><td class="vd">${x.from_at} to ${x.to_at}</td></tr>`; }).join('')}</table>` : '<div class="note">No dated score changes under these filters yet. History builds as the daily sweep runs.</div>'}</div>
  <div class="card"><h3>Newest Models<small>first dated appearance</small></h3><table><tr><th>Model</th><th>Vendor</th><th>First seen</th></tr>${nw.map(id => `<tr><td>${mlink(id)}</td><td>${esc(mvend(id))}</td><td class="num">${D.models[id].first}</td></tr>`).join('')}</table></div></div>`;
}
function pricePanel() {
  const tl = D.price_timeline.filter(x => inRange(x.at)), days = [...new Set(tl.map(x => x.at))].sort();
  const W = 860, H = 200, P = 36, mx = Math.max(1, ...tl.map(x => x.n)), bw = Math.max(6, (W - 2 * P) / Math.max(days.length, 1) / 2.4);
  const X = i => P + (i + .5) * (W - 2 * P) / Math.max(days.length, 1);
  const bars = days.map((d, i) => ['list', 'market'].map((k, j) => { const o = tl.find(x => x.at === d && x.kind === k); if (!o) return ''; const h = (H - 2 * P) * o.n / mx; return `<rect x="${X(i) + (j - 1) * bw}" y="${H - P - h}" width="${bw}" height="${h}" fill="${k === 'list' ? '#C6A241' : '#28336B'}"><title>${d}: ${o.n} ${k} price points</title></rect>`; }).join('') + (days.length < 16 || i % 3 === 0 ? `<text x="${X(i)}" y="${H - P + 14}" font-size="10" text-anchor="middle" fill="#5C6480">${d.slice(5)}</text>` : '')).join('');
  const gaps = (D.price_gaps || []).filter(g => !S.vendor || mvend(g.model) === S.vendor).sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff)).slice(0, 12);
  const chart = `<div class="card"><h3>Price Observations Over Time<small><span class="tag fp">list</span> <span class="tag tp">market</span></small></h3><svg class="chart" viewBox="0 0 ${W} ${H}">${bars}</svg><div class="cite">Price points recorded per day. List: vendor list prices. Market: observed market prices.</div></div>`;
  if (!gaps.length) return chart;
  const usd = v => '$' + (+v).toFixed(v < 1 ? 3 : 2);
  return `<div class="grid g2">${chart}
  <div class="card"><h3>List vs Market Price Gaps</h3><p class="lede" style="margin:0 0 8px">Where the market price differs from the vendor's official price</p><table><tr><th>Model</th><th>Unit</th><th>List</th><th>Market</th><th>Difference</th></tr>${gaps.map(g => `<tr><td>${mlink(g.model)}</td><td>${g.unit}</td><td class="num">${g.free ? 'free at list' : usd(g.list.usd)}<div class="vd">${g.list.at}</div></td><td class="num">${usd(g.market.usd)}<div class="vd">${g.market.at}</div></td><td class="num ${g.diff > 0 ? 'down' : 'up'}">${g.diff > 0 ? '+' : '-'}${usd(Math.abs(g.diff))}${g.pct != null ? ' (' + (g.pct > 0 ? '+' : '') + g.pct.toFixed(0) + '%)' : ''}</td></tr>`).join('')}</table><div class="cite">USD per 1M tokens. Verified rows only.</div></div></div>`;
}
function rankTable(mid) {
  const m = D.metrics[mid], r = rows(mid);
  return `<div class="card"><h3>${esc(label(m))} <small>${r.length} models · ${esc(m.unit || 'score')}</small></h3><div class="scroll"><table><tr><th>#</th><th>Model</th><th>Vendor</th><th>Value</th><th>Price (blended)</th><th>As of</th></tr>${r.slice(0, 300).map((x, i) => { const p = blended(x[0]); return `<tr><td class="num">${i + 1}</td><td>${mlink(x[0])}</td><td>${esc(mvend(x[0]))}</td><td class="num">${fmt(x[1], m.unit)}</td><td class="num">${p ? '$' + p.usd.toFixed(3) + ' <span class="tag ' + (p.fp ? 'fp">list' : 'tp">market') + '</span>' : '-'}</td><td class="vd">${x[2] || ''}</td></tr>`; }).join('')}</table></div>${cite(m.as_of)}</div>`;
}
function overview() {
  const metric = S.metric && D.metrics[S.metric] ? +S.metric : null;
  const scatterMetric = metric || (D.key[0] || {}).metric;
  const last = D.updated;
  let h = `<div class="kpis"><div class="kpi"><b>${D.counts.models.toLocaleString()}</b><span>models tracked</span></div><div class="kpi"><b>${D.counts.vendors}</b><span>vendors</span></div><div class="kpi"><b>${D.counts.metrics}</b><span>metrics</span></div><div class="kpi"><b class="date">${esc(last)}</b><span>latest sweep</span></div></div>`;
  const filt = ['vendor', 'metric', 'q', 'from', 'to'].filter(k => S[k]);
  if (filt.length) h += `<div class="note">Filtered view: ${filt.map(k => `${k} = <b>${esc(k === 'metric' ? label(D.metrics[S[k]]) : S[k])}</b>`).join(', ')}</div>`;
  h += `<h2>Leaders by Key Metric</h2><p class="lede">Top models on each headline metric, with as-of dates.</p><div class="grid g4">${(metric ? [{metric, label: label(D.metrics[metric])}] : D.key).map(k => leaderCard(k.metric, k.label)).join('') || '<div class="note">No models match these filters.</div>'}</div>`;
  h += `<h2>Price vs Capability</h2><p class="lede">Each dot is a model. Up and to the left is more capability per dollar.</p><div class="card">${scatter(scatterMetric)}</div>`;
  h += `<h2>Movers and New Models</h2>${moversNew()}`;
  h += `<h2>Vendor Share</h2>${vendorShare(metric || D.key[1].metric)}`;
  h += `<h2>Prices</h2><p class="lede">Vendor list prices are preferred; market prices are labeled.</p>${pricePanel()}`;
  h += `<h2>Full Ranking</h2>${rankTable(metric || D.key[1].metric)}`;
  return h;
}
function spark(series, m) {
  const W = 300, H = 70, ys = series.map(s => s[1]), a = Math.min(...ys), b = Math.max(...ys);
  const pts = series.map((s, i) => `${10 + i * (W - 20) / (series.length - 1)},${H - 10 - (s[1] - a) / (b - a || 1) * (H - 20)}`).join(' ');
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}"><polyline points="${pts}" fill="none" stroke="#C6A241" stroke-width="2"/></svg><div class="vd">${series.map(s => `${s[0]}: ${fmt(s[1], m.unit)}`).join(' · ')}</div>`;
}
function drill(id) {
  const mod = D.models[id]; if (!mod) return `<div class="note">Model not found.</div>`;
  const by = {};
  for (const [mid, r] of Object.entries(D.latest)) { const x = r.find(x => x[0] === id); if (x) { const m = D.metrics[mid]; (by.all = by.all || []).push({m, x, n: r.length}); } }
  const p = D.price_obs[id] || {};
  const ptab = Object.keys(p).length ? `<table><tr><th>Unit</th><th>USD / 1M</th><th>Type</th><th>Observed</th></tr>${Object.entries(p).flatMap(([u, obs]) => obs.map(o => `<tr><td>${u.replace('_', ' ')}</td><td class="num">$${o.usd}</td><td><span class="tag ${o.list ? 'fp">list' : 'tp">market'}</span></td><td class="vd">${o.at}</td></tr>`)).join('')}</table>` : '<div class="note">No price on record for this model.</div>';
  const hs = Object.entries(D.history).filter(([k]) => k.startsWith(id + '|')).map(([k, s]) => { const m = D.metrics[k.split('|')[1]]; return m ? `<div class="card"><h3>${esc(label(m))}</h3>${spark(s, m)}${cite(s[s.length - 1][0])}</div>` : ''; }).join('');
  return `<div class="drill"><a class="back" href="#">← Back to overview</a><h1>${esc(mod.name)}</h1><p class="vd" style="font-size:14px">${esc(mod.vendor)} · first dated appearance ${esc(mod.first || 'n/a')}</p>
  <div class="grid g3"><div class="card"><h3>Prices<small>list price preferred</small></h3>${ptab}</div><div class="card"><h3>Capability vs Price Snapshot</h3>${(() => { const b = blended(id); return b ? `<p style="font:500 30px var(--disp);margin:4px 0;color:var(--navy)">$${b.usd.toFixed(3)}</p><p class="vd">blended per 1M tokens, ${b.fp ? 'list price' : 'market price'} · ${b.at}</p>` : '<p class="vd">No blended price available.</p>'; })()}</div></div>
  ${hs ? `<h2>History</h2><div class="grid g4">${hs}</div>` : '<div class="note">Only one dated reading per metric so far for this model; trend lines appear as daily sweeps accumulate.</div>'}
  <h2>All Metrics</h2><div class="grid g2">${Object.entries(by).map(([sid, list]) => `<div class="card"><h3>Metrics<small>${list.length} metrics</small></h3><div class="scroll" style="max-height:320px"><table><tr><th>Metric</th><th>Value</th><th>Rank</th><th>As of</th></tr>${list.sort((a, b) => b.n - a.n).map(o => `<tr><td>${esc(label(o.m))}</td><td class="num">${fmt(o.x[1], o.m.unit)}</td><td class="num">${o.x[3]} / ${o.n}</td><td class="vd">${o.x[2] || ''}</td></tr>`).join('')}</table></div>${cite(list.map(o => o.x[2]).filter(Boolean).sort().pop())}</div>`).join('')}</div></div>`;
}
function render() {
  readHash(); syncFilters();
  $('#main').innerHTML = S.model ? drill(S.model) : overview();
  if (S.model) window.scrollTo(0, 0);
}
fetch('data/dashboard.json').then(r => r.json()).then(d => {
  D = d; $('#built').textContent = 'Updated ' + d.built.replace('T', ' ').slice(0, 16) + ' CT';
  $('#foot').innerHTML = `<p>Data updated ${esc(d.updated || 'n/a')}. Prices in USD per 1M tokens; vendor list prices preferred. © 2026 AgentU · agentu.ai</p>`;
  initFilters(); render(); window.addEventListener('hashchange', render);
});
