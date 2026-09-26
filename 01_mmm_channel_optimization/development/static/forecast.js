const charts = {};
const PAGE = document.body.dataset.page;
const PALETTE = ["#1e3a5f", "#1f5c57", "#9a3412", "#b45309", "#6d28d9"];

function money(value) {
  return `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })}`;
}

function table(headers, rows) {
  return `<table><thead><tr>${headers.map((h) => `<th${h.num ? ' class="num"' : ""}>${h.label}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${r.map((cell, i) => `<td${headers[i].num ? ' class="num"' : ""}>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function destroyChart(key) {
  if (charts[key]) {
    charts[key].destroy();
    charts[key] = null;
  }
}

function setStatus(message, ok) {
  const el = document.getElementById("status");
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
  el.className = ok ? "status ok" : "status";
}

async function fetchLatest() {
  const res = await fetch("/api/forecast/latest");
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Could not load forecast");
  return data;
}

function renderKpis(data) {
  const m = data.metrics;
  const win = data.scores[m.winner] || { wape: m.ensemble_wape, mape: m.ensemble_mape, r2: m.ensemble_r2 };
  const host = document.getElementById("kpis");
  if (!host) return;
  host.innerHTML = `
    <div class="kpi"><b>${win.wape.toFixed(1)}%</b><span>Best-model WAPE</span><p>Holdout weighted absolute percent error for ${m.winner.replace("_", " ")}. This is the volume-planning miss.</p></div>
    <div class="kpi"><b>${win.mape.toFixed(1)}%</b><span>Best-model MAPE</span><p>Average percent miss across channel-weeks. Inflated by Drug and Club.</p></div>
    <div class="kpi"><b>${m.ensemble_r2.toFixed(2)}</b><span>Holdout R-squared</span><p>Variance explained on weeks the models never trained on.</p></div>
    <div class="kpi"><b>${m.winner.replace("_", " ")}</b><span>Best holdout model</span><p>Lowest WAPE among naive, Ridge ARX, and the blend.</p></div>
    <div class="kpi"><b>${m.pct_lift >= 0 ? "+" : ""}${m.pct_lift.toFixed(1)}%</b><span>Trade profit lift</span><p>Optimized mix vs equal split, same weekly trade budget of ${money(m.trade_budget)}k.</p></div>
    <div class="kpi"><b>${money(m.optimized_profit)}k</b><span>Optimized horizon profit</span><p>Incremental margin minus trade cost over ${m.holdout_weeks} weeks.</p></div>`;
}

function renderOverview(data) {
  const m = data.metrics;
  const best = [...data.promo_effect].sort((a, b) => b.lift_pct - a.lift_pct)[0];
  document.getElementById("story").innerHTML = `
    <p><strong>What this run says.</strong> ${m.n_weeks} weeks, last ${m.holdout_weeks} held out. The ensemble WAPE is ${m.ensemble_wape.toFixed(1)}% (winner: ${m.winner.replace("_", " ")}). Reallocating a ${money(m.trade_budget)}k weekly trade envelope raises horizon profit by ${money(m.profit_lift)}k (${m.pct_lift >= 0 ? "+" : ""}${m.pct_lift.toFixed(1)}%) versus an even split.</p>
    <p>Observed TPR lift is largest in <strong>${best.channel}</strong> (+${best.lift_pct.toFixed(0)}% vs non-promo weeks). Use the allocation page to see whether that channel is also where the next dollar should go — high lift with a low margin can still lose money.</p>`;
  renderKpis(data);

  destroyChart("fit");
  charts.fit = new Chart(document.getElementById("fitChart"), {
    type: "line",
    data: {
      labels: data.series.week,
      datasets: [
        { label: "Actual units", data: data.series.units, borderColor: "#1c1914", tension: 0.15, pointRadius: 0, borderWidth: 2 },
        { label: "Ridge ARX", data: data.series.pred, borderColor: "#1f5c57", tension: 0.15, pointRadius: 0, borderWidth: 2, borderDash: [5, 3] },
        { label: "Baseline (no promo)", data: data.series.baseline, borderColor: "#a8a29e", tension: 0.15, pointRadius: 0, borderWidth: 1 },
      ],
    },
    options: { responsive: true, plugins: { tooltip: { mode: "index", intersect: false } }, scales: { x: { title: { display: true, text: `Week (holdout starts ${data.series.split_week})` } } } },
  });

  destroyChart("holdout");
  charts.holdout = new Chart(document.getElementById("holdoutChart"), {
    type: "line",
    data: {
      labels: data.series.holdout_week,
      datasets: [
        { label: "Actual", data: data.series.holdout_actual, borderColor: "#1c1914", tension: 0.15, pointRadius: 0 },
        { label: "Ensemble", data: data.series.holdout_pred, borderColor: "#b45309", tension: 0.15, pointRadius: 0 },
      ],
    },
    options: { responsive: true },
  });

  destroyChart("bakeoff");
  const names = Object.keys(data.scores);
  charts.bakeoff = new Chart(document.getElementById("bakeoffChart"), {
    type: "bar",
    data: {
      labels: names.map((n) => n.replace("_", " ")),
      datasets: [{ label: "WAPE %", data: names.map((n) => data.scores[n].wape), backgroundColor: ["#9a3412", "#1e3a5f", "#1f5c57"] }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  destroyChart("promo");
  charts.promo = new Chart(document.getElementById("promoChart"), {
    type: "bar",
    data: {
      labels: data.promo_effect.map((r) => r.channel),
      datasets: [
        { label: "Non-promo units", data: data.promo_effect.map((r) => r.base_units), backgroundColor: "#c4b5a0" },
        { label: "Promo units", data: data.promo_effect.map((r) => r.promo_units), backgroundColor: "#1e3a5f" },
      ],
    },
    options: { responsive: true },
  });

  destroyChart("trade");
  charts.trade = new Chart(document.getElementById("tradeChart"), {
    type: "line",
    data: {
      labels: data.series.week,
      datasets: [{ label: "Trade $k", data: data.series.trade, borderColor: "#9a3412", tension: 0.15, pointRadius: 0, fill: false }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  document.getElementById("channelTable").innerHTML = table(
    [
      { label: "Channel" },
      { label: "WAPE", num: true },
      { label: "MAPE", num: true },
      { label: "R²", num: true },
      { label: "Mean units", num: true },
      { label: "Promo weeks", num: true },
    ],
    data.by_channel.map((r) => [r.channel, `${r.wape.toFixed(1)}%`, `${r.mape.toFixed(1)}%`, r.r2.toFixed(2), r.mean_units.toFixed(0), `${r.promo_weeks.toFixed(0)}%`])
  );
  document.getElementById("promoTable").innerHTML = table(
    [{ label: "Channel" }, { label: "Lift vs base", num: true }, { label: "Trade $/promo week", num: true }],
    data.promo_effect.map((r) => [r.channel, `${r.lift_pct.toFixed(0)}%`, money(r.trade_per_week)])
  );
  document.getElementById("results").hidden = false;
}

function planTable(rows) {
  return table(
    [
      { label: "Channel" },
      { label: "Weekly $k", num: true },
      { label: "Horizon $k", num: true },
      { label: "Incr. units", num: true },
      { label: "ROI", num: true },
      { label: "Units / $", num: true },
      { label: "Profit $k", num: true },
      { label: "β TPR", num: true },
      { label: "β Feature", num: true },
      { label: "β Display", num: true },
    ],
    rows.map((r) => [
      r.channel,
      money(r.weekly_trade),
      money(r.horizon_trade),
      r.incremental_units.toFixed(0),
      r.roi.toFixed(2),
      r.efficiency.toFixed(2),
      money(r.profit),
      r.tpr_coef.toFixed(2),
      r.feature_coef.toFixed(2),
      r.display_coef.toFixed(2),
    ])
  );
}

function renderAllocation(data) {
  const a = data.allocation;
  const m = data.metrics;
  const shifted = a.optimized.map((row, i) => ({ name: row.channel, shift: row.weekly_trade - a.equal[i].weekly_trade }));
  const up = [...shifted].sort((x, y) => y.shift - x.shift)[0];
  const down = [...shifted].sort((x, y) => x.shift - y.shift)[0];
  document.getElementById("story").innerHTML = `
    <p><strong>What this plan says.</strong> Same ${money(a.weekly_budget)}k / week for ${a.horizon_weeks} weeks. Optimized horizon profit is ${money(a.optimized_profit)}k vs ${money(a.equal_profit)}k for an even split — ${a.pct_lift >= 0 ? "+" : ""}${a.pct_lift.toFixed(1)}%.</p>
    <p>The solver moves money into <strong>${up.name}</strong> (${up.shift >= 0 ? "+" : ""}${up.shift.toFixed(1)}k / week) and out of <strong>${down.name}</strong> (${down.shift.toFixed(1)}k / week). That is the efficiency gain: spend where lift × margin still sits on the steep part of the Hill curve.</p>`;
  renderKpis(data);

  destroyChart("alloc");
  charts.alloc = new Chart(document.getElementById("allocChart"), {
    type: "bar",
    data: {
      labels: a.optimized.map((r) => r.channel),
      datasets: [
        { label: "Equal", data: a.equal.map((r) => r.weekly_trade), backgroundColor: "#9a3412" },
        { label: "Optimized", data: a.optimized.map((r) => r.weekly_trade), backgroundColor: "#1e3a5f" },
      ],
    },
    options: { responsive: true },
  });

  destroyChart("roi");
  charts.roi = new Chart(document.getElementById("roiChart"), {
    type: "bar",
    data: {
      labels: a.optimized.map((r) => r.channel),
      datasets: [{ label: "ROI", data: a.optimized.map((r) => r.roi), backgroundColor: a.optimized.map((r) => (r.roi >= 1 ? "#1f5c57" : "#9a3412")) }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  destroyChart("lift");
  charts.lift = new Chart(document.getElementById("liftChart"), {
    type: "bar",
    data: {
      labels: a.optimized.map((r) => r.channel),
      datasets: [
        { label: "True TPR", data: a.optimized.map((r) => r.true_tpr), backgroundColor: "#1c1914" },
        { label: "Est. TPR", data: a.optimized.map((r) => r.tpr_coef), backgroundColor: "#b45309" },
        { label: "True feature", data: a.optimized.map((r) => r.true_feature), backgroundColor: "#1f5c57" },
        { label: "Est. feature", data: a.optimized.map((r) => r.feature_coef), backgroundColor: "#7c3aed" },
      ],
    },
    options: { responsive: true },
  });

  destroyChart("units");
  charts.units = new Chart(document.getElementById("unitsChart"), {
    type: "bar",
    data: {
      labels: a.optimized.map((r) => r.channel),
      datasets: [
        { label: "Equal incr. units", data: a.equal.map((r) => r.incremental_units), backgroundColor: "#c4b5a0" },
        { label: "Optimized incr. units", data: a.optimized.map((r) => r.incremental_units), backgroundColor: "#1e3a5f" },
      ],
    },
    options: { responsive: true },
  });

  document.getElementById("optTable").innerHTML = planTable(a.optimized);
  document.getElementById("eqTable").innerHTML = planTable(a.equal);
  document.getElementById("results").hidden = false;
}

async function runForecast() {
  const btn = document.getElementById("runForecast");
  setStatus("", true);
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Fitting…";
  }
  try {
    const res = await fetch("/api/forecast/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        n_weeks: Number(document.getElementById("nWeeks").value),
        holdout_weeks: Number(document.getElementById("holdoutWeeks").value),
        trade_budget: Number(document.getElementById("tradeBudget").value),
        seed: Number(document.getElementById("seed").value),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Forecast failed");
    renderOverview(data);
    setStatus(`Finished. Winner ${data.metrics.winner.replace("_", " ")}, WAPE ${data.metrics.ensemble_wape.toFixed(1)}%.`, true);
  } catch (err) {
    setStatus(err.message, false);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Run forecast";
    }
  }
}

async function boot() {
  try {
    const data = await fetchLatest();
    if (PAGE === "overview") {
      renderOverview(data);
      setStatus(`Loaded last run. Winner ${data.metrics.winner.replace("_", " ")}.`, true);
    } else if (PAGE === "allocation") {
      renderAllocation(data);
    }
  } catch (err) {
    setStatus(err.message, false);
  }
}

document.getElementById("runForecast")?.addEventListener("click", runForecast);
if (PAGE !== "methods") {
  boot();
}
