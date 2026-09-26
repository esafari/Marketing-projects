const charts = {};
const PAGE = document.body.dataset.page;
let LAST = null;

function money(value) {
  return `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function money1(value) {
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
  const res = await fetch("/api/clv/latest");
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Could not load CLV results");
  LAST = data;
  return data;
}

function renderKpis(data, extra = "") {
  const m = data.metrics;
  const host = document.getElementById("kpis");
  if (!host) return;
  host.innerHTML = `
    <div class="kpi"><b>${money(m.mean_clv)}</b><span>Mean blend CLV</span><p>Expected contribution margin over the next ${m.horizon_weeks} weeks, average customer.</p></div>
    <div class="kpi"><b>${money(m.total_clv)}</b><span>Portfolio CLV</span><p>Sum of blend scores. This is the CRM-addressable value of the base, not company revenue.</p></div>
    <div class="kpi"><b>${(m.mean_p_alive * 100).toFixed(0)}%</b><span>Mean P(alive)</span><p>BG/NBD probability the average customer has not dropped out by the snapshot.</p></div>
    <div class="kpi"><b>${m.holdout_spearman.toFixed(2)}</b><span>Holdout Spearman</span><p>Rank correlation of blend CLV vs actual post-snapshot margin. This is the ranking test.</p></div>
    <div class="kpi"><b>${m.holdout_mape.toFixed(1)}%</b><span>Holdout MAPE</span><p>Percent miss among customers who actually spent after the cut.</p></div>
    <div class="kpi"><b>${m.n_customers.toLocaleString()}</b><span>Households</span><p>${extra || `Snapshot week ${m.snapshot_week}. Continuing margin ${(m.margin * 100).toFixed(0)}% CAD.`}</p></div>`;
}

function renderAssumptions(data) {
  const host = document.getElementById("assumptions");
  if (!host || !data.assumptions) return;
  host.innerHTML = `<h3>Assumptions used on this run</h3>
    <div class="problem-grid">${data.assumptions
      .map(
        (row) => `<article><h4>${row.name}</h4><p><strong>${row.value}</strong></p><p>${row.why}</p></article>`
      )
      .join("")}</div>`;
}

function renderOverview(data) {
  const m = data.metrics;
  const ranked = [...data.by_channel].sort((a, b) => b.mean_clv - a.mean_clv);
  const best = ranked[0];
  const worst = ranked[ranked.length - 1];
  const oneDone = ((m.one_and_done_share || 0) * 100).toFixed(0);
  const skip = ((m.mean_skip_rate || 0) * 100).toFixed(0);
  const family = ((m.family_share || 0) * 100).toFixed(0);
  document.getElementById("story").innerHTML = `
    <p><strong>What this run says.</strong> ${m.n_customers.toLocaleString()} X Canada households scored at week ${m.snapshot_week} in CAD. Mean blend CLV is ${money(m.mean_clv)} contribution over the next ${m.horizon_weeks} weeks at ${(m.margin * 100).toFixed(0)}% continuing-box margin (first box is planned at ${((m.first_box_margin || 0.06) * 100).toFixed(0)}%). Holdout Spearman is ${m.holdout_spearman.toFixed(2)}. ${oneDone}% never took a second box (promo cliff). Mean skip rate ${skip}%. Family plans ${family}% of the base.</p>
    <p><strong>${best.name}</strong> is the highest-value first-touch channel (mean ${money(best.mean_clv)}). <strong>${worst.name}</strong> is the lowest (mean ${money(worst.mean_clv)}). That is the meal-kit harvest story: paid search sells the cheap first box; referral and TV sell households that still ship after the promo ends. Rank on blend CLV, not on P(alive) — a new first-box buyer can look alive and still be low value.</p>`;
  renderAssumptions(data);
  renderKpis(data);

  const labels = [];
  for (let i = 0; i < data.series.clv_hist.length; i += 1) {
    labels.push(Math.round(data.series.clv_bins[i]));
  }
  destroyChart("hist");
  charts.hist = new Chart(document.getElementById("histChart"), {
    type: "bar",
    data: { labels, datasets: [{ label: "Customers", data: data.series.clv_hist, backgroundColor: "#1e3a5f" }] },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  destroyChart("scatter");
  charts.scatter = new Chart(document.getElementById("scatterChart"), {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Customer",
          data: data.series.pred.map((x, i) => ({ x, y: data.series.actual[i] * m.margin })),
          backgroundColor: "rgba(30, 58, 95, 0.35)",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: "Blend CLV $" } },
        y: { title: { display: true, text: "Holdout margin $" } },
      },
    },
  });

  destroyChart("channel");
  charts.channel = new Chart(document.getElementById("channelChart"), {
    type: "bar",
    data: {
      labels: data.by_channel.map((r) => r.name),
      datasets: [{ label: "Mean CLV", data: data.by_channel.map((r) => r.mean_clv), backgroundColor: ["#1f5c57", "#1e3a5f", "#3f6f6a", "#9a3412", "#b45309"] }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  destroyChart("lift");
  charts.lift = new Chart(document.getElementById("liftChart"), {
    type: "bar",
    data: {
      labels: data.lift.map((r) => `D${r.decile}`),
      datasets: [{ label: "Lift vs average", data: data.lift.map((r) => r.lift), backgroundColor: "#1f5c57" }],
    },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { title: { display: true, text: "Lift" } } } },
  });

  document.getElementById("results").hidden = false;
}

function customerRows(data) {
  const q = (document.getElementById("search")?.value || "").trim().toLowerCase();
  const funnel = document.getElementById("funnelFilter")?.value || "";
  const tier = document.getElementById("tierFilter")?.value || "";
  return data.customers.filter((row) => {
    if (funnel && row.funnel !== funnel) return false;
    if (tier && row.segment !== tier) return false;
    if (!q) return true;
    const blob = `${row.id} ${row.channel} ${row.funnel} ${row.segment} ${row.rfm_segment} ${row.plan_size === 4 ? "family" : "2-person"}`.toLowerCase();
    return blob.includes(q);
  });
}

function renderCustomers(data) {
  renderKpis(data, "Filter the table. Other pages keep this same run.");
  const rows = customerRows(data);
  document.getElementById("tableHost").innerHTML = table(
    [
      { label: "Rank", num: true },
      { label: "ID" },
      { label: "Channel" },
      { label: "Plan" },
      { label: "Funnel" },
      { label: "RFM" },
      { label: "Tier" },
      { label: "x", num: true },
      { label: "Recency", num: true },
      { label: "P(alive)", num: true },
      { label: "E[ord]", num: true },
      { label: "E[AOV]", num: true },
      { label: "BG/NBD", num: true },
      { label: "Ridge", num: true },
      { label: "Blend CLV", num: true },
      { label: "Holdout $", num: true },
    ],
    rows.slice(0, 400).map((r) => [
      r.rank,
      r.id,
      r.channel,
      r.plan_size === 4 ? "Family" : "2-person",
      r.funnel,
      r.rfm_segment,
      r.segment,
      r.frequency.toFixed(0),
      r.recency.toFixed(1),
      (r.p_alive * 100).toFixed(0) + "%",
      r.e_purchases.toFixed(2),
      money1(r.e_aov),
      money1(r.clv_bgnbd),
      money1(r.clv_ml),
      money1(r.clv_blend),
      money1(r.holdout_spend),
    ])
  );
}

function renderSegments(data) {
  renderKpis(data);
  destroyChart("funnel");
  charts.funnel = new Chart(document.getElementById("funnelChart"), {
    type: "bar",
    data: {
      labels: data.by_funnel.map((r) => r.name),
      datasets: [
        { label: "Total CLV", data: data.by_funnel.map((r) => r.total_clv), backgroundColor: "#1e3a5f" },
        { label: "Mean CLV", data: data.by_funnel.map((r) => r.mean_clv), backgroundColor: "#1f5c57" },
      ],
    },
    options: { responsive: true },
  });
  destroyChart("tier");
  charts.tier = new Chart(document.getElementById("tierChart"), {
    type: "bar",
    data: {
      labels: data.by_value.map((r) => r.name),
      datasets: [
        { label: "Customers", data: data.by_value.map((r) => r.customers), backgroundColor: "#9a3412" },
        { label: "Total CLV", data: data.by_value.map((r) => r.total_clv), backgroundColor: "#1e3a5f" },
      ],
    },
    options: { responsive: true },
  });
  destroyChart("rfm");
  charts.rfm = new Chart(document.getElementById("rfmChart"), {
    type: "bar",
    data: {
      labels: data.by_rfm.map((r) => r.name),
      datasets: [{ label: "Mean CLV", data: data.by_rfm.map((r) => r.mean_clv), backgroundColor: "#b45309" }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });
  destroyChart("alive");
  charts.alive = new Chart(document.getElementById("aliveChart"), {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "P(alive)",
          data: data.series.recency.map((x, i) => ({ x, y: data.series.p_alive[i] })),
          backgroundColor: "rgba(31, 92, 87, 0.35)",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: "Recency (weeks since first-to-last)" } },
        y: { title: { display: true, text: "P(alive)" }, min: 0, max: 1 },
      },
    },
  });
  document.getElementById("channelTable").innerHTML = table(
    [
      { label: "Channel" },
      { label: "N", num: true },
      { label: "Mean CLV", num: true },
      { label: "P(alive)", num: true },
      { label: "AOV", num: true },
      { label: "Holdout $", num: true },
    ],
    data.by_channel.map((r) => [r.name, r.customers, money(r.mean_clv), `${(r.mean_p_alive * 100).toFixed(0)}%`, money(r.mean_aov), money(r.mean_holdout)])
  );
  document.getElementById("rfmTable").innerHTML = table(
    [{ label: "Segment" }, { label: "N", num: true }, { label: "Mean CLV", num: true }, { label: "Total CLV", num: true }],
    data.by_rfm.map((r) => [r.name, r.customers, money(r.mean_clv), money(r.total_clv)])
  );
  document.getElementById("results").hidden = false;
}

async function runClv() {
  const btn = document.getElementById("runClv");
  setStatus("", true);
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Scoring…";
  }
  try {
    const res = await fetch("/api/clv/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        n_customers: Number(document.getElementById("nCustomers").value),
        snapshot_week: Number(document.getElementById("snapshotWeek").value),
        horizon_weeks: Number(document.getElementById("horizonWeeks").value),
        margin: Number(document.getElementById("margin").value),
        seed: Number(document.getElementById("seed").value),
        calendar_weeks: 156,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "CLV run failed");
    LAST = data;
    renderOverview(data);
    setStatus(`Finished. ${data.metrics.n_customers} customers scored.`, true);
  } catch (err) {
    setStatus(err.message, false);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Run CLV models";
    }
  }
}

async function boot() {
  try {
    const data = await fetchLatest();
    if (PAGE === "overview") {
      renderOverview(data);
      setStatus(`Loaded last run: ${data.metrics.n_customers} customers.`, true);
    } else if (PAGE === "customers") {
      renderCustomers(data);
    } else if (PAGE === "segments") {
      renderSegments(data);
    }
  } catch (err) {
    setStatus(err.message, false);
  }
}

document.getElementById("runClv")?.addEventListener("click", runClv);
["search", "funnelFilter", "tierFilter"].forEach((id) => {
  document.getElementById(id)?.addEventListener("input", () => LAST && renderCustomers(LAST));
  document.getElementById(id)?.addEventListener("change", () => LAST && renderCustomers(LAST));
});

if (PAGE !== "methods") {
  boot();
}
