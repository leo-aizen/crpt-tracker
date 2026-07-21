/* Price / cumulative-return line chart, hand-built SVG (no chart libs —
   matches the SURF no-build stack). Two modes off the same server series so
   they can never disagree:
     "price" — CRPT alone, real dollars (the accurate fund-specific view)
     "pct"   — CRPT vs benchmarks, each rebased to 0% at window start (the
               only honest way to overlay a $12 fund on a $600 index: one
               axis, indexed to a common base — never dual axes)
   Crosshair + tooltip, legend chips + direct end-labels in compare mode,
   and a table fallback for accessibility.

   Series colors are the validated dark-mode categorical palette (CVD-checked
   against the #0d0d0d card surface): CRPT #3987e5 · IBIT #c98500 ·
   BITQ #d55181 · SPY #9085e9. Assigned by entity, never by rank. */
"use strict";

const CHART_COLORS = { CRPT: "#3987e5", IBIT: "#c98500", BITQ: "#d55181", SPY: "#9085e9" };
const FALLBACK_COLOR = "#9085e9";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmtDay = (ts) => { const d = new Date(ts * 1000); return `${MONTHS[d.getMonth()]} ${d.getDate()}`; };
const fmtDayTime = (ts) => {
  const d = new Date(ts * 1000);
  return `${MONTHS[d.getMonth()]} ${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
};
const fmtFull = (ts, intraday) => {
  const d = new Date(ts * 1000);
  const base = `${MONTHS[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
  return intraday ? `${base} ${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}` : base;
};
const fmtRet = (v) => (v > 0 ? "+" : "") + v.toFixed(2) + "%";
const fmtPx = (v) => "$" + v.toFixed(2);

function niceTicks(lo, hi, n = 5) {
  const span = hi - lo, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= n) || 10 * mag;
  const ticks = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(+v.toFixed(6));
  return ticks;
}

/* data = /api/chart payload (points: [ts, price, pct]); mode = "price"|"pct" */
function renderReturnChart(container, data, mode = "pct") {
  const priceMode = mode === "price";
  const all = priceMode ? data.series.filter((s) => s.symbol === "CRPT") : data.series;
  const live = all.filter((s) => s.points.length >= 2);
  const dead = all.filter((s) => s.points.length < 2);
  const val = priceMode ? (p) => p[1] : (p) => p[2];
  const fmtVal = priceMode ? fmtPx : fmtRet;
  container.innerHTML = "";

  // Legend only in compare mode — a single named series needs no legend box.
  if (!priceMode) {
    const legend = document.createElement("div");
    legend.className = "crpt-legend";
    legend.innerHTML = data.series.map((s) => {
      const c = CHART_COLORS[s.symbol] || FALLBACK_COLOR;
      const off = s.points.length < 2;
      return `<span class="crpt-legend-item ${off ? "nodata" : ""}" title="${s.label}">
        <span class="sw" style="background:${off ? "transparent" : c};border-color:${c}"></span>
        ${s.symbol}${off ? " (no data)" : ""}</span>`;
    }).join("");
    container.appendChild(legend);
  }

  if (!live.length) {
    const p = document.createElement("p");
    p.className = "crpt-footnote nodata";
    p.textContent = "no data — the market-data source returned nothing for this window.";
    container.appendChild(p);
    return;
  }

  // Geometry
  const W = Math.max(320, container.clientWidth || 640);
  const H = 260, ML = priceMode ? 52 : 46, MR = priceMode ? 14 : 56, MT = 10, MB = 24;
  const IW = W - ML - MR, IH = H - MT - MB;

  const allTs = live.flatMap((s) => s.points.map((p) => p[0]));
  const allV = live.flatMap((s) => s.points.map(val)).concat(priceMode ? [] : [0]);
  const t0 = Math.min(...allTs), t1 = Math.max(...allTs);
  let v0 = Math.min(...allV), v1 = Math.max(...allV);
  const pad = (v1 - v0) * 0.06 || 1; v0 -= pad; v1 += pad;
  const x = (t) => ML + ((t - t0) / (t1 - t0 || 1)) * IW;
  const y = (v) => MT + (1 - (v - v0) / (v1 - v0 || 1)) * IH;

  const intraday = (t1 - t0) < 8 * 86400;

  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("class", "crpt-chart-svg");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", priceMode
    ? `CRPT price, ${fmtPx(live[0].points.at(-1)[1])}, ${fmtRet(live[0].points.at(-1)[2])} over the window`
    : "Cumulative return, " + live.map((s) => `${s.symbol} ${fmtRet(s.points.at(-1)[2])}`).join(", "));

  const el = (tag, attrs, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    (parent || svg).appendChild(n);
    return n;
  };

  // Recessive horizontal grid + y labels; zero line emphasized only in % mode
  for (const tv of niceTicks(v0, v1)) {
    const gy = y(tv);
    el("line", { x1: ML, x2: W - MR, y1: gy, y2: gy, class: (!priceMode && tv === 0) ? "grid zero" : "grid" });
    el("text", { x: ML - 7, y: gy + 3.5, class: "axis ylab", "text-anchor": "end" })
      .textContent = priceMode ? "$" + (+tv.toFixed(2)) : (tv > 0 ? "+" : "") + tv + "%";
  }
  // X labels
  const master = live.reduce((a, b) => (a.points.length >= b.points.length ? a : b)).points;
  const nx = Math.min(4, master.length);
  for (let i = 0; i < nx; i++) {
    const p = master[Math.round((i / (nx - 1 || 1)) * (master.length - 1))];
    el("text", { x: x(p[0]), y: H - 6, class: "axis", "text-anchor": i === 0 ? "start" : i === nx - 1 ? "end" : "middle" })
      .textContent = intraday ? fmtDayTime(p[0]) : fmtDay(p[0]);
  }

  // Series lines (2px) — CRPT drawn last so the protagonist sits on top
  const ordered = [...live].sort((a, b) => (a.symbol === "CRPT") - (b.symbol === "CRPT"));
  for (const s of ordered) {
    const d = s.points.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(val(p)).toFixed(1)}`).join("");
    el("path", { d, class: "series", stroke: CHART_COLORS[s.symbol] || FALLBACK_COLOR });
  }

  // Direct end-labels only in compare mode (≤4 series → label all)
  if (!priceMode) {
    const ends = live.map((s) => ({ sym: s.symbol, color: CHART_COLORS[s.symbol] || FALLBACK_COLOR, ty: y(val(s.points.at(-1))) }))
      .sort((a, b) => a.ty - b.ty);
    for (let i = 1; i < ends.length; i++) ends[i].ty = Math.max(ends[i].ty, ends[i - 1].ty + 14);
    for (let i = ends.length - 1; i > 0; i--) ends[i - 1].ty = Math.min(ends[i - 1].ty, ends[i].ty - 14);
    for (const e2 of ends) {
      el("circle", { cx: W - MR + 8, cy: e2.ty, r: 3, fill: e2.color });
      el("text", { x: W - MR + 14, y: e2.ty + 3.5, class: "endlab" }).textContent = e2.sym;
    }
  }

  // Hover: crosshair + ≥8px marker + tooltip
  const cross = el("line", { x1: 0, x2: 0, y1: MT, y2: MT + IH, class: "crosshair", visibility: "hidden" });
  const marks = live.map((s) => el("circle", { r: 4.5, class: "hovermark", visibility: "hidden", fill: CHART_COLORS[s.symbol] || FALLBACK_COLOR }));

  const wrap = document.createElement("div");
  wrap.className = "crpt-chartwrap";
  wrap.appendChild(svg);
  const tip = document.createElement("div");
  tip.className = "crpt-tip";
  tip.hidden = true;
  wrap.appendChild(tip);
  container.appendChild(wrap);

  const nearest = (pts, t) => {
    let lo = 0, hi = pts.length - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; (pts[mid][0] < t ? (lo = mid) : (hi = mid)); }
    return (t - pts[lo][0] <= pts[hi][0] - t) ? pts[lo] : pts[hi];
  };

  function onMove(clientX, clientY) {
    const r = svg.getBoundingClientRect();
    const t = t0 + ((clientX - r.left) / r.width * W - ML) / IW * (t1 - t0);
    if (t < t0 || t > t1) return onLeave();
    const snap = nearest(master, Math.round(t));
    const cx = x(snap[0]);
    cross.setAttribute("x1", cx); cross.setAttribute("x2", cx);
    cross.setAttribute("visibility", "visible");
    const rows = [];
    live.forEach((s, i) => {
      const p = nearest(s.points, snap[0]);
      marks[i].setAttribute("cx", x(p[0]));
      marks[i].setAttribute("cy", y(val(p)));
      marks[i].setAttribute("visibility", "visible");
      rows.push({ sym: s.symbol, p, color: CHART_COLORS[s.symbol] || FALLBACK_COLOR });
    });
    rows.sort((a, b) => val(b.p) - val(a.p));
    tip.innerHTML = `<div class="d">${fmtFull(snap[0], intraday)}</div>` + rows.map((rw) => {
      const v = val(rw.p);
      const extra = priceMode ? ` <span class="v ${rw.p[2] > 0 ? "pos" : rw.p[2] < 0 ? "neg" : ""}">${fmtRet(rw.p[2])}</span>` : "";
      return `<div class="r"><span class="sw" style="background:${rw.color}"></span>${rw.sym}` +
        `<span class="v ${priceMode ? "" : (v > 0 ? "pos" : v < 0 ? "neg" : "")}">${fmtVal(v)}</span>${extra}</div>`;
    }).join("");
    tip.hidden = false;
    const relX = (cx / W) * r.width;
    tip.style.left = Math.min(relX + 12, r.width - tip.offsetWidth - 4) + "px";
    tip.style.top = Math.max(0, clientY - r.top - tip.offsetHeight - 12) + "px";
  }
  function onLeave() {
    cross.setAttribute("visibility", "hidden");
    marks.forEach((m) => m.setAttribute("visibility", "hidden"));
    tip.hidden = true;
  }
  svg.addEventListener("mousemove", (ev) => onMove(ev.clientX, ev.clientY));
  svg.addEventListener("mouseleave", onLeave);
  svg.addEventListener("touchmove", (ev) => { const t2 = ev.touches[0]; onMove(t2.clientX, t2.clientY); }, { passive: true });
  svg.addEventListener("touchend", onLeave);

  // Accessible table fallback: the chart's takeaway in plain text
  const det = document.createElement("details");
  det.className = "crpt-tablefallback";
  det.innerHTML = `<summary>View as table</summary>
    <div class="crpt-tablewrap"><table class="crpt-table">
      <thead><tr><th>Series</th><th>Window</th>${priceMode ? "<th>Start</th><th>End</th>" : ""}<th>Cumulative return</th></tr></thead>
      <tbody>${all.map((s) => {
        const has = s.points.length >= 2;
        const ret = has ? s.points.at(-1)[2] : null;
        return `<tr><th>${s.symbol} — ${s.label}</th>
          <td>${has ? `${fmtDay(s.points[0][0])} → ${fmtDay(s.points.at(-1)[0])}` : "—"}</td>
          ${priceMode ? `<td>${has ? fmtPx(s.points[0][1]) : "—"}</td><td>${has ? fmtPx(s.points.at(-1)[1]) : "—"}</td>` : ""}
          <td class="${has ? (ret > 0 ? "pos" : ret < 0 ? "neg" : "") : "nodata"}">${has ? fmtRet(ret) : "no data"}</td></tr>`;
      }).join("")}</tbody>
    </table></div>`;
  container.appendChild(det);

  if (dead.length) {
    const p = document.createElement("p");
    p.className = "crpt-footnote";
    p.textContent = "no data for " + dead.map((s) => s.symbol).join(", ") + " in this window (provider returned nothing — not an app guess).";
    container.appendChild(p);
  }
}

window.renderReturnChart = renderReturnChart;
