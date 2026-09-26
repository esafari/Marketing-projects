const charts = {};
const PAGE = document.body.dataset.page;
const PLAN_COLORS = {
  "Status quo": "#c4b5a0",
  Harvest: "#9a3412",
  "Brand-led": "#1f5c57",
  "Promo-led": "#b45309",
  "Risk-off": "#6d28d9",
  "ROI-optimal": "#1e3a5f",
  Custom: "#be185d",
};

function money(value) {
  return `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
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

function payloadFromForm(extra) {
  const body = {
    media_budget: Number(document.getElementById("mediaBudget")?.value || 140),
    promo_budget: Number(document.getElementById("promoBudget")?.value || 120),
    horizon: Number(document.getElementById("horizon")?.value || 13),
    downside: Number(document.getElementById("downside")?.value || 0.7),
    seed: Number(document.getElementById("seed")?.value || 42),
  };
  return { ...body, ...extra };
}

async function runApi(body) {
  const res = await fetch("/api/scenarios/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Scenario run failed");
  return data;
}

async function fetchLatest() {
  const res = await fetch("/api/scenarios/latest");
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Could not load scenarios");
  return data;
}

function renderKpis(data) {
  const m = data.metrics;
  const host = document.getElementById("kpis");
  if (!host) return;
  host.innerHTML = `
    <div class="kpi"><b>${m.best}</b><span>Best profit plan</span><p>Highest horizon contribution profit among the scored strategies.</p></div>
    <div class="kpi"><b>${money(m.best_profit)}k</b><span>Best horizon profit</span><p>0.36 × incremental sales minus media and promo, over ${m.horizon} weeks.</p></div>
    <div class="kpi"><b>${m.best_roi.toFixed(2)}</b><span>Best ROI</span><p>Profit / investment for that winning plan. A rate, not a dollar.</p></div>
    <div class="kpi"><b>${m.profit_vs_status >= 0 ? "+" : ""}${money(m.profit_vs_status)}k</b><span>vs status quo</span><p>Same horizon. Positive means a named or custom plan beats last year’s lock.</p></div>
    <div class="kpi"><b>${(m.roi_vs_status >= 0 ? "+" : "") + m.roi_vs_status.toFixed(2)}</b><span>ROI gap vs lock</span><p>Best ROI minus status-quo ROI.</p></div>
    <div class="kpi"><b>${money(m.media_budget + m.promo_budget)}k</b><span>Weekly envelopes</span><p>Media ${money(m.media_budget)}k + promo ${money(m.promo_budget)}k. Promo-led reshuffles this split.</p></div>`;
}

function renderScoreTable(data) {
  const host = document.getElementById("scoreTable");
  if (!host) return;
  host.innerHTML = table(
    [
      { label: "Strategy" },
      { label: "Risk" },
      { label: "Invest $k", num: true },
      { label: "Incr. $k", num: true },
      { label: "Profit $k", num: true },
      { label: "ROI", num: true },
      { label: "Downside", num: true },
      { label: "p10", num: true },
      { label: "p90", num: true },
      { label: "Media %", num: true },
      { label: "HHI", num: true },
    ],
    data.plans.map((r) => [
      r.name,
      r.risk_flag,
      money(r.investment),
      money(r.incremental),
      money(r.profit),
      r.roi.toFixed(2),
      money(r.downside_profit),
      money(r.p10_profit),
      money(r.p90_profit),
      `${r.media_share.toFixed(0)}%`,
      r.concentration.toFixed(2),
    ])
  );
}

function renderOverview(data) {
  const m = data.metrics;
  const harvest = data.plans.find((p) => p.name === "Harvest");
  const opt = data.plans.find((p) => p.name === "ROI-optimal");
  document.getElementById("story").innerHTML = `
    <p><strong>What this lock says.</strong> Over ${m.horizon} weeks, <strong>${m.best}</strong> is the highest-profit plan at ${money(m.best_profit)}k (ROI ${m.best_roi.toFixed(2)}). That is ${money(m.profit_vs_status)}k versus status quo. Harvest ${harvest ? `prints ${money(harvest.incremental)}k incremental at ROI ${harvest.roi.toFixed(2)}` : "is volume-heavy"} — often more units, worse money.</p>
    <p>ROI-optimal profit is ${opt ? money(opt.profit) + "k" : "—"}. If a custom or brand-led plan is close on the downside column, pick the one operations can actually run. The frontier chart is the board view: do not pick a point that is down and to the left of the lock.</p>`;
  renderKpis(data);
  renderScoreTable(data);

  destroyChart("profit");
  charts.profit = new Chart(document.getElementById("profitChart"), {
    type: "bar",
    data: {
      labels: data.plans.map((p) => p.name),
      datasets: [{ label: "Profit $k", data: data.plans.map((p) => p.profit), backgroundColor: data.plans.map((p) => PLAN_COLORS[p.name] || "#1e3a5f") }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  if (document.getElementById("frontierChart")) {
    destroyChart("frontier");
    charts.frontier = new Chart(document.getElementById("frontierChart"), {
      type: "scatter",
      data: {
        datasets: data.frontier.map((p) => ({
          label: p.name,
          data: [{ x: p.incremental, y: p.roi }],
          backgroundColor: PLAN_COLORS[p.name] || "#1e3a5f",
          pointRadius: 7,
        })),
      },
      options: {
        responsive: true,
        scales: {
          x: { title: { display: true, text: "Horizon incremental $k" } },
          y: { title: { display: true, text: "ROI" } },
        },
      },
    });
  }

  if (document.getElementById("mediaChart")) {
    const mediaNames = data.levers.media;
    destroyChart("media");
    charts.media = new Chart(document.getElementById("mediaChart"), {
      type: "bar",
      data: {
        labels: data.plans.map((p) => p.name),
        datasets: mediaNames.map((name, i) => ({
          label: name,
          data: data.plans.map((p) => p.media[name] || 0),
          backgroundColor: ["#1e3a5f", "#1f5c57", "#9a3412", "#b45309"][i],
          stack: "media",
        })),
      },
      options: { responsive: true, scales: { x: { stacked: true }, y: { stacked: true } } },
    });
  }

  if (document.getElementById("promoChart")) {
    const promoNames = data.levers.promo;
    destroyChart("promo");
    charts.promo = new Chart(document.getElementById("promoChart"), {
      type: "bar",
      data: {
        labels: data.plans.map((p) => p.name),
        datasets: promoNames.map((name, i) => ({
          label: name,
          data: data.plans.map((p) => p.promo[name] || 0),
          backgroundColor: ["#1f5c57", "#9a3412", "#6d28d9", "#b45309"][i],
          stack: "promo",
        })),
      },
      options: { responsive: true, scales: { x: { stacked: true }, y: { stacked: true } } },
    });
  }

  if (document.getElementById("roiChart")) {
    destroyChart("roi");
    charts.roi = new Chart(document.getElementById("roiChart"), {
      type: "bar",
      data: {
        labels: data.plans.map((p) => p.name),
        datasets: [{ label: "ROI", data: data.plans.map((p) => p.roi), backgroundColor: data.plans.map((p) => PLAN_COLORS[p.name] || "#1e3a5f") }],
      },
      options: { responsive: true, plugins: { legend: { display: false } } },
    });
  }

  document.getElementById("results").hidden = false;
}

function customShares() {
  return {
    media: {
      TV: Number(document.getElementById("sh-TV").value),
      Social: Number(document.getElementById("sh-Social").value),
      Search: Number(document.getElementById("sh-Search").value),
      Email: Number(document.getElementById("sh-Email").value),
    },
    promo: {
      Grocery: Number(document.getElementById("sh-Grocery").value),
      Mass: Number(document.getElementById("sh-Mass").value),
      Drug: Number(document.getElementById("sh-Drug").value),
      "E-comm": Number(document.getElementById("sh-Ecomm").value),
    },
  };
}

async function runNamed() {
  const btn = document.getElementById("runScenarios");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Scoring…";
  }
  try {
    const data = await runApi(payloadFromForm({}));
    renderOverview(data);
    setStatus(`Finished. Best plan: ${data.metrics.best}.`, true);
  } catch (err) {
    setStatus(err.message, false);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Score scenarios";
    }
  }
}

async function runCustom() {
  const btn = document.getElementById("runCustom");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Scoring…";
  }
  try {
    const data = await runApi(payloadFromForm({ custom: customShares() }));
    renderOverview(data);
    const custom = data.plans.find((p) => p.name === "Custom");
    setStatus(custom ? `Custom profit ${money(custom.profit)}k, ROI ${custom.roi.toFixed(2)}. Best is ${data.metrics.best}.` : "Scored.", true);
  } catch (err) {
    setStatus(err.message, false);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Score custom mix";
    }
  }
}

async function boot() {
  try {
    if (PAGE === "overview") {
      const data = await fetchLatest();
      renderOverview(data);
      setStatus(`Loaded last run. Best: ${data.metrics.best}.`, true);
    } else if (PAGE === "planner") {
      setStatus("Set shares and score a custom mix. Named strategies are included for comparison.", true);
    }
  } catch (err) {
    setStatus(err.message, false);
  }
}

document.getElementById("runScenarios")?.addEventListener("click", runNamed);
document.getElementById("runCustom")?.addEventListener("click", runCustom);
if (PAGE !== "methods") {
  boot();
}
