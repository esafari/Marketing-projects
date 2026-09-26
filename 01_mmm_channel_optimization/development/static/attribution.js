const charts = {};
const PAGE = document.body.dataset.page;
const CHANNELS = ["TV", "Social", "Search", "Email"];
const SHARE_COLORS = {
  "True incremental": "#1c1914",
  "Last-touch": "#9a3412",
  "First-touch": "#a8a29e",
  "Linear MTA": "#c4b5a0",
  "Time-decay MTA": "#b45309",
  "MMM incremental": "#1e3a5f",
  "Lift-calibrated MMM": "#1f5c57",
};

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
  const res = await fetch("/api/attribution/latest");
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Could not load attribution");
  return data;
}

function renderKpis(data) {
  const m = data.metrics;
  const host = document.getElementById("kpis");
  if (!host) return;
  host.innerHTML = `
    <div class="kpi"><b>${m.mmm_mae.toFixed(1)} pp</b><span>MMM share MAE</span><p>Average absolute miss of incremental MMM shares vs true incremental. Lower is better.</p></div>
    <div class="kpi"><b>${m.last_touch_mae.toFixed(1)} pp</b><span>Last-touch share MAE</span><p>How far the platform report is from incrementality. This is usually the largest error on the page.</p></div>
    <div class="kpi"><b>${m.calibrated_mae.toFixed(1)} pp</b><span>Calibrated MAE</span><p>MMM after geo-lift scales. If this is worse than raw MMM, the priors are over-correcting a model that was already close.</p></div>
    <div class="kpi"><b>${m.test_r2.toFixed(2)}</b><span>Holdout R-squared</span><p>Incremental MMM on the last ${m.holdout_weeks} weeks.</p></div>
    <div class="kpi"><b>${money(m.total_lift)}k</b><span>Spend + price lift</span><p>Profit vs last-touch mix at index 100, after incremental media and the recommended price.</p></div>
    <div class="kpi"><b>${m.recommended_price.toFixed(1)}</b><span>Recommended price index</span><p>Peak contribution profit on 96–104 given the incremental media mix.</p></div>`;
}

function renderOverview(data) {
  const m = data.metrics;
  const last = data.frameworks.find((f) => f.framework === "Last-touch");
  const truth = data.frameworks.find((f) => f.framework === "True incremental");
  document.getElementById("story").innerHTML = `
    <p><strong>What this run says.</strong> Incremental MMM holdout R² is ${m.test_r2.toFixed(2)}. Share MAE is ${m.mmm_mae.toFixed(1)} pp for MMM vs ${m.last_touch_mae.toFixed(1)} pp for last-touch. Search last-touch share is ${last.shares.Search.toFixed(0)}% against a true incremental ${truth.shares.Search.toFixed(0)}%.</p>
    <p>Price beta recovered at ${m.price_beta.toFixed(0)} versus true ${m.true_price_beta.toFixed(0)}. Reallocating media and moving the index to ${m.recommended_price.toFixed(1)} is worth ${money(m.total_lift)}k versus following last-touch at 100. That is the investment-allocation number.</p>`;
  renderKpis(data);

  const compare = data.frameworks.filter((f) => ["True incremental", "Last-touch", "MMM incremental", "Lift-calibrated MMM"].includes(f.framework));
  destroyChart("share");
  charts.share = new Chart(document.getElementById("shareChart"), {
    type: "bar",
    data: {
      labels: CHANNELS,
      datasets: compare.map((f) => ({
        label: f.framework,
        data: CHANNELS.map((c) => f.shares[c]),
        backgroundColor: SHARE_COLORS[f.framework],
      })),
    },
    options: { responsive: true },
  });

  const scored = data.frameworks.filter((f) => !f.is_truth);
  destroyChart("mae");
  charts.mae = new Chart(document.getElementById("maeChart"), {
    type: "bar",
    data: {
      labels: scored.map((f) => f.framework),
      datasets: [{ label: "Share MAE (pp)", data: scored.map((f) => f.share_mae), backgroundColor: scored.map((f) => (f.framework.includes("MMM") ? "#1f5c57" : "#9a3412")) }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  destroyChart("inc");
  charts.inc = new Chart(document.getElementById("incChart"), {
    type: "bar",
    data: {
      labels: data.incrementals.map((r) => r.name),
      datasets: [
        { label: "Estimated", data: data.incrementals.map((r) => r.plus_10k_sales), backgroundColor: "#1e3a5f" },
        { label: "True", data: data.incrementals.map((r) => r.true_plus_10k), backgroundColor: "#1c1914" },
      ],
    },
    options: { responsive: true },
  });

  destroyChart("fit");
  charts.fit = new Chart(document.getElementById("fitChart"), {
    type: "line",
    data: {
      labels: data.series.test_week,
      datasets: [
        { label: "Actual sales", data: data.series.test_actual, borderColor: "#1c1914", tension: 0.15, pointRadius: 0 },
        { label: "Incremental MMM", data: data.series.test_pred, borderColor: "#b45309", tension: 0.15, pointRadius: 0 },
      ],
    },
    options: { responsive: true },
  });

  destroyChart("price");
  charts.price = new Chart(document.getElementById("priceChart"), {
    type: "line",
    data: {
      labels: data.series.week,
      datasets: [
        { label: "True price $k", data: data.series.true_price, borderColor: "#1c1914", tension: 0.15, pointRadius: 0 },
        { label: "Estimated price $k", data: data.series.est_price, borderColor: "#1f5c57", tension: 0.15, pointRadius: 0, borderDash: [5, 3] },
      ],
    },
    options: { responsive: true, plugins: { tooltip: { mode: "index", intersect: false } } },
  });

  document.getElementById("shareTable").innerHTML = table(
    [{ label: "Framework" }, { label: "MAE", num: true }, ...CHANNELS.map((c) => ({ label: c, num: true }))],
    data.frameworks.map((f) => [f.framework, f.share_mae.toFixed(1), ...CHANNELS.map((c) => `${f.shares[c].toFixed(1)}%`)])
  );
  document.getElementById("incTable").innerHTML = table(
    [
      { label: "Lever" },
      { label: "Mean" },
      { label: "Est. β", num: true },
      { label: "True β", num: true },
      { label: "iROAS / ΔY", num: true },
      { label: "+$10k or +1pt", num: true },
    ],
    data.incrementals.map((r) => [
      r.name,
      r.kind === "price" ? r.mean_spend.toFixed(1) : money(r.mean_spend),
      r.estimated_beta.toFixed(1),
      r.true_beta.toFixed(1),
      r.iroas.toFixed(2),
      money(r.plus_10k_sales),
    ])
  );
  document.getElementById("results").hidden = false;
}

function planTable(rows) {
  return table(
    [{ label: "Channel" }, { label: "Spend $k", num: true }, { label: "Share", num: true }, { label: "iROAS", num: true }],
    rows.map((r) => [r.name, money(r.spend), `${r.share.toFixed(0)}%`, r.iroas.toFixed(2)])
  );
}

function renderInvestment(data) {
  const a = data.allocation;
  const m = data.metrics;
  document.getElementById("story").innerHTML = `
    <p><strong>What this plan says.</strong> Same ${money(a.budget)}k weekly media. Incremental mix earns ${money(a.media_lift)}k more contribution profit than last-touch at price 100. Moving the index to <strong>${a.recommended_price.toFixed(1)}</strong> adds another ${money(a.price_lift)}k. Combined lift vs last-touch at 100 is ${money(a.total_lift)}k.</p>
    <p>Use last-touch only as the “what the platforms asked for” baseline. Ship the incremental mix plus the price stance, inside whatever guardrails pricing already owns.</p>`;
  renderKpis(data);

  destroyChart("mix");
  charts.mix = new Chart(document.getElementById("mixChart"), {
    type: "bar",
    data: {
      labels: a.incremental.map((r) => r.name),
      datasets: [
        { label: "Last-touch", data: a.last_touch.map((r) => r.spend), backgroundColor: "#9a3412" },
        { label: "Incremental", data: a.incremental.map((r) => r.spend), backgroundColor: "#1e3a5f" },
      ],
    },
    options: { responsive: true },
  });

  destroyChart("iroas");
  charts.iroas = new Chart(document.getElementById("iroasChart"), {
    type: "bar",
    data: {
      labels: a.incremental.map((r) => r.name),
      datasets: [{ label: "iROAS", data: a.incremental.map((r) => r.iroas), backgroundColor: a.incremental.map((r) => (r.iroas >= 1 ? "#1f5c57" : "#9a3412")) }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  destroyChart("priceOpt");
  charts.priceOpt = new Chart(document.getElementById("priceOptChart"), {
    type: "line",
    data: {
      labels: a.price_curve.map((r) => r.price.toFixed(1)),
      datasets: [
        { label: "Contribution profit $k", data: a.price_curve.map((r) => r.profit), borderColor: "#1e3a5f", tension: 0.15, pointRadius: 3 },
      ],
    },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { title: { display: true, text: "Price index" } } } },
  });

  document.getElementById("lastTable").innerHTML = planTable(a.last_touch);
  document.getElementById("incPlanTable").innerHTML = planTable(a.incremental);
  document.getElementById("results").hidden = false;
}

async function runAttr() {
  const btn = document.getElementById("runAttr");
  setStatus("", true);
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Fitting…";
  }
  try {
    const res = await fetch("/api/attribution/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        n_weeks: Number(document.getElementById("nWeeks").value),
        holdout_weeks: Number(document.getElementById("holdoutWeeks").value),
        media_budget: Number(document.getElementById("mediaBudget").value),
        seed: Number(document.getElementById("seed").value),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Run failed");
    renderOverview(data);
    setStatus(`Finished. MMM MAE ${data.metrics.mmm_mae.toFixed(1)} pp vs last-touch ${data.metrics.last_touch_mae.toFixed(1)} pp.`, true);
  } catch (err) {
    setStatus(err.message, false);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Run frameworks";
    }
  }
}

async function boot() {
  try {
    const data = await fetchLatest();
    if (PAGE === "overview") {
      renderOverview(data);
      setStatus(`Loaded last run. Holdout R² ${data.metrics.test_r2.toFixed(2)}.`, true);
    } else if (PAGE === "investment") {
      renderInvestment(data);
    }
  } catch (err) {
    setStatus(err.message, false);
  }
}

document.getElementById("runAttr")?.addEventListener("click", runAttr);
if (PAGE !== "methods") {
  boot();
}
