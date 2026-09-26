const charts = {};
const PAGE = document.body.dataset.page;

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

function gate(name) {
  return `<span class="gate-${name}">${name}</span>`;
}

function units(value, digits) {
  const d = digits == null ? 0 : digits;
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: d });
}

async function fetchLatest() {
  const res = await fetch("/api/demand/latest");
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Could not load demand trends");
  return data;
}

function renderOverview(data) {
  const m = data.metrics;
  const p = data.planning;
  document.getElementById("story").innerHTML = `
    <p><strong>What this run says.</strong> ${data.story}</p>
    <p>Planning gate: ${gate(p.gate)}. Next ${m.horizon_weeks} weeks average ${units(p.next_13)} units versus ${units(p.last_13)} in the last 13 (${p.gap_pct >= 0 ? "+" : ""}${p.gap_pct.toFixed(1)}%). Same weeks last year: ${p.vs_ly >= 0 ? "+" : ""}${p.vs_ly.toFixed(1)}%.</p>`;

  document.getElementById("kpis").innerHTML = `
    <div class="kpi"><b>${m.ensemble_wape.toFixed(1)}%</b><span>Holdout weighted absolute percent error</span><p>Ensemble miss on weeks the models never trained on. This is the volume-planning error.</p></div>
    <div class="kpi"><b>${m.ensemble_r2.toFixed(2)}</b><span>Holdout R-squared</span><p>Variance explained on the holdout window.</p></div>
    <div class="kpi"><b>${m.recent_yoy >= 0 ? "+" : ""}${m.recent_yoy.toFixed(1)}%</b><span>Recent year-over-year</span><p>Mean of the last 26 year-over-year weeks.</p></div>
    <div class="kpi"><b>${m.gap_pct >= 0 ? "+" : ""}${m.gap_pct.toFixed(1)}%</b><span>Horizon versus last 13</span><p>Forward average versus the current run-rate.</p></div>
    <div class="kpi"><b>${gate(m.outlook_gate)}</b><span>Outlook</span><p>${p.outlook}</p></div>
    <div class="kpi"><b>${m.holdout_coverage_80.toFixed(0)}%</b><span>Holdout 80% coverage</span><p>Share of holdout weeks inside the residual band. Near 80 means the band is usable for capacity.</p></div>`;

  destroyChart("fit");
  charts.fit = new Chart(document.getElementById("fitChart"), {
    type: "line",
    data: {
      labels: data.series.week,
      datasets: [
        { label: "Observed demand", data: data.series.demand, borderColor: "#1c1914", tension: 0.15, pointRadius: 0, borderWidth: 2 },
        { label: "13-week trend", data: data.series.trend, borderColor: "#1f5c57", tension: 0.15, pointRadius: 0, borderWidth: 2 },
        { label: "Ridge ARX fit", data: data.series.fitted, borderColor: "#b45309", tension: 0.15, pointRadius: 0, borderWidth: 2, borderDash: [5, 3] },
      ],
    },
    options: {
      responsive: true,
      plugins: { tooltip: { mode: "index", intersect: false } },
      scales: { x: { title: { display: true, text: `Week (holdout starts ${data.series.split_week})` } } },
    },
  });

  destroyChart("holdout");
  charts.holdout = new Chart(document.getElementById("holdoutChart"), {
    type: "line",
    data: {
      labels: data.holdout.week,
      datasets: [
        { label: "Actual", data: data.holdout.actual, borderColor: "#1c1914", tension: 0.15, pointRadius: 0, borderWidth: 2 },
        { label: "Ensemble", data: data.holdout.pred, borderColor: "#b45309", tension: 0.15, pointRadius: 0, borderWidth: 2 },
        { label: "80% low", data: data.holdout.lo80, borderColor: "#c4b5a0", tension: 0.15, pointRadius: 0, borderWidth: 1, borderDash: [4, 3] },
        { label: "80% high", data: data.holdout.hi80, borderColor: "#c4b5a0", tension: 0.15, pointRadius: 0, borderWidth: 1, borderDash: [4, 3] },
      ],
    },
    options: { responsive: true, plugins: { tooltip: { mode: "index", intersect: false } } },
  });

  destroyChart("horizon");
  charts.horizon = new Chart(document.getElementById("horizonChart"), {
    type: "line",
    data: {
      labels: data.horizon.week,
      datasets: [
        { label: "p50 forecast", data: data.horizon.pred, borderColor: "#1e3a5f", tension: 0.15, pointRadius: 2, borderWidth: 2 },
        { label: "80% low", data: data.horizon.lo80, borderColor: "#1f5c57", tension: 0.15, pointRadius: 0, borderDash: [4, 3] },
        { label: "80% high", data: data.horizon.hi80, borderColor: "#1f5c57", tension: 0.15, pointRadius: 0, borderDash: [4, 3] },
        { label: "90% low", data: data.horizon.lo90, borderColor: "#c4b5a0", tension: 0.15, pointRadius: 0, borderDash: [2, 3] },
        { label: "90% high", data: data.horizon.hi90, borderColor: "#c4b5a0", tension: 0.15, pointRadius: 0, borderDash: [2, 3] },
      ],
    },
    options: { responsive: true, plugins: { tooltip: { mode: "index", intersect: false } } },
  });

  destroyChart("yoy");
  charts.yoy = new Chart(document.getElementById("yoyChart"), {
    type: "bar",
    data: {
      labels: data.series.week,
      datasets: [{ label: "Year-over-year %", data: data.series.yoy, backgroundColor: data.series.yoy.map((v) => (v == null || v >= 0 ? "#1f5c57" : "#9a3412")) }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  destroyChart("season");
  charts.season = new Chart(document.getElementById("seasonChart"), {
    type: "line",
    data: {
      labels: data.series.week,
      datasets: [{ label: "Seasonal units", data: data.series.seasonal, borderColor: "#6d28d9", tension: 0.2, pointRadius: 0 }],
    },
    options: { responsive: true },
  });

  const scoreRows = Object.entries(data.scores).map(([name, s]) => [
    name.replace(/_/g, " "),
    s.wape.toFixed(1) + "%",
    s.mape.toFixed(1) + "%",
    s.r2.toFixed(2),
    s.bias.toFixed(1),
  ]);
  document.getElementById("scoreTable").innerHTML = table(
    [{ label: "Model" }, { label: "WAPE", num: true }, { label: "MAPE", num: true }, { label: "R2", num: true }, { label: "Bias", num: true }],
    scoreRows
  );

  document.getElementById("planTable").innerHTML = table(
    [{ label: "Comparison" }, { label: "Forecast", num: true }, { label: "Baseline", num: true }, { label: "Delta", num: true }, { label: "Decision" }],
    p.decisions.map((d) => [
      d.horizon,
      units(d.forecast, 1),
      units(d.baseline, 1),
      `${d.delta_pct >= 0 ? "+" : ""}${d.delta_pct.toFixed(1)}`,
      gate(d.decision),
    ])
  );

  document.getElementById("results").hidden = false;
}

function renderDiagnostics(data) {
  const d = data.diagnostics;
  const p = data.planning;
  document.getElementById("story").innerHTML = `
    <p><strong>Diagnostics.</strong> Durbin–Watson ${d.durbin_watson.toFixed(2)} (2 is no leftover weekly correlation). Lag-1 autocorrelation ${d.lag1_acf.toFixed(2)}.
    A mean break of ${d.level_shift_size >= 0 ? "+" : ""}${d.level_shift_size.toFixed(0)} units is estimated at week ${d.level_shift_week}
    (planted near week ${d.true_shift_week}). ${d.anomaly_count} week(s) have |z| at least 2.5.</p>
    <p>${p.actions.map((a) => `<strong>${a.title}.</strong> ${a.detail}`).join(" ")}</p>`;

  document.getElementById("kpis").innerHTML = `
    <div class="kpi"><b>${d.durbin_watson.toFixed(2)}</b><span>Durbin–Watson</span><p>Residual after trend and season. Far from 2 means the holdout band is optimistic.</p></div>
    <div class="kpi"><b>${d.lag1_acf.toFixed(2)}</b><span>Lag-1 residual correlation</span><p>Why Ridge keeps last week's demand as a feature.</p></div>
    <div class="kpi"><b>${d.level_shift_week}</b><span>Detected mean-break week</span><p>${d.level_shift_size >= 0 ? "+" : ""}${d.level_shift_size.toFixed(0)} units after the break. Treat as a new regime.</p></div>
    <div class="kpi"><b>${d.recent_yoy >= 0 ? "+" : ""}${d.recent_yoy.toFixed(1)}%</b><span>Recent year-over-year</span><p>Prior 26 weeks: ${d.prior_yoy >= 0 ? "+" : ""}${d.prior_yoy.toFixed(1)}%.</p></div>
    <div class="kpi"><b>${d.acceleration >= 0 ? "+" : ""}${d.acceleration.toFixed(2)}</b><span>Trend acceleration</span><p>Recent 26-week slope minus the 26 weeks before. Units per week.</p></div>
    <div class="kpi"><b>${d.anomaly_count}</b><span>Anomaly weeks</span><p>|residual / sigma| at least 2.5. Investigate operations before rewriting seasonality.</p></div>`;

  destroyChart("resid");
  charts.resid = new Chart(document.getElementById("residChart"), {
    type: "bar",
    data: {
      labels: data.series.week,
      datasets: [{
        label: "Residual",
        data: data.series.residual,
        backgroundColor: data.series.residual.map((v, i) => (Math.abs(v) / Math.max(...data.series.residual.map(Math.abs), 1) > 0.55 ? "#9a3412" : "#1e3a5f")),
      }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  const topDrivers = data.drivers.slice(0, 8);
  destroyChart("driver");
  charts.driver = new Chart(document.getElementById("driverChart"), {
    type: "bar",
    data: {
      labels: topDrivers.map((r) => r.name),
      datasets: [{ label: "Standardized coefficient", data: topDrivers.map((r) => r.coef), backgroundColor: topDrivers.map((r) => (r.coef >= 0 ? "#1f5c57" : "#9a3412")) }],
    },
    options: { indexAxis: "y", responsive: true, plugins: { legend: { display: false } } },
  });

  destroyChart("slope");
  charts.slope = new Chart(document.getElementById("slopeChart"), {
    type: "bar",
    data: {
      labels: ["Prior 26 weeks", "Recent 26 weeks"],
      datasets: [{ label: "Trend slope (units / week)", data: [d.trend_slope_prior, d.trend_slope_recent], backgroundColor: ["#c4b5a0", "#1e3a5f"] }],
    },
    options: { responsive: true },
  });

  destroyChart("drvSeries");
  charts.drvSeries = new Chart(document.getElementById("driverSeriesChart"), {
    type: "line",
    data: {
      labels: data.series.week,
      datasets: [
        { label: "Price index", data: data.series.price_index, borderColor: "#9a3412", tension: 0.15, pointRadius: 0, yAxisID: "y" },
        { label: "Promo depth", data: data.series.promo_depth, borderColor: "#1f5c57", tension: 0.15, pointRadius: 0, yAxisID: "y1" },
      ],
    },
    options: {
      responsive: true,
      plugins: { tooltip: { mode: "index", intersect: false } },
      scales: {
        y: { title: { display: true, text: "Price index" } },
        y1: { position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "Promo depth" } },
      },
    },
  });

  const anomalies = d.anomalies.length
    ? d.anomalies.map((a) => [a.week, units(a.demand), a.residual.toFixed(1), a.z.toFixed(2), a.reason])
    : [["—", "—", "—", "—", "No week cleared |z| 2.5 on this run."]];
  document.getElementById("anomalyTable").innerHTML = table(
    [{ label: "Week" }, { label: "Demand", num: true }, { label: "Residual", num: true }, { label: "z", num: true }, { label: "Read" }],
    anomalies
  );

  document.getElementById("driverTable").innerHTML = table(
    [{ label: "Feature" }, { label: "Coefficient", num: true }, { label: "Why it is here" }],
    data.drivers.map((r) => [r.name, r.coef.toFixed(2), r.note])
  );

  document.getElementById("results").hidden = false;
}

async function runDemand() {
  const btn = document.getElementById("runDemand");
  setStatus("", true);
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Fitting…";
  }
  try {
    const res = await fetch("/api/demand/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        n_weeks: Number(document.getElementById("nWeeks").value),
        holdout_weeks: Number(document.getElementById("holdoutWeeks").value),
        horizon_weeks: Number(document.getElementById("horizonWeeks").value),
        seed: Number(document.getElementById("seed").value),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Demand engine failed");
    renderOverview(data);
    setStatus(`Finished. ${data.planning.gate} outlook, holdout weighted absolute percent error ${data.metrics.ensemble_wape.toFixed(1)}%.`, true);
  } catch (err) {
    setStatus(err.message, false);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Run demand trends";
    }
  }
}

async function boot() {
  try {
    const data = await fetchLatest();
    if (PAGE === "overview") {
      renderOverview(data);
      setStatus(`Loaded last run. Outlook ${data.planning.gate}.`, true);
    } else if (PAGE === "diagnostics") {
      renderDiagnostics(data);
      setStatus(`Loaded last run. ${data.diagnostics.anomaly_count} anomaly week(s).`, true);
    }
  } catch (err) {
    setStatus(err.message, false);
  }
}

document.getElementById("runDemand")?.addEventListener("click", runDemand);
if (PAGE !== "methods") {
  boot();
}
