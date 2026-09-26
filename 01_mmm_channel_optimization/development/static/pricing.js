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

function renderOverview(data) {
  const m = data.metrics;
  document.getElementById("story").innerHTML = `<p><strong>What this run says.</strong> ${data.story}</p>`;
  document.getElementById("kpis").innerHTML = `
    <div class="kpi"><b>${m.est_elasticity.toFixed(2)}</b><span>Recovered elasticity</span><p>True value is ${m.true_elasticity.toFixed(2)}. Fit on Thompson traffic only.</p></div>
    <div class="kpi"><b>${m.oracle_arm.toFixed(0)}</b><span>Oracle price index</span><p>Highest expected contribution profit.</p></div>
    <div class="kpi"><b>${m.thompson_profit.toFixed(0)}</b><span>Thompson profit</span><p>Versus ${m.random_profit.toFixed(0)} for random prices.</p></div>
    <div class="kpi"><b>${(100 * m.explore_share).toFixed(0)}%</b><span>Explore share</span><p>Rounds where Thompson did not pick the current empirical best.</p></div>
    <div class="kpi"><b>${m.winner}</b><span>Best policy this seed</span><p>Highest cumulative profit among Thompson, UCB, and epsilon-greedy.</p></div>
    <div class="kpi"><b>${m.elasticity_r2.toFixed(2)}</b><span>Log-log R-squared</span><p>How cleanly units follow price in the observed traffic.</p></div>`;

  destroyChart("profit");
  charts.profit = new Chart(document.getElementById("profitChart"), {
    type: "line",
    data: {
      labels: data.series.round,
      datasets: [
        { label: "Thompson", data: data.series.cum_thompson, borderColor: "#1e3a5f", pointRadius: 0, borderWidth: 2 },
        { label: "UCB", data: data.series.cum_ucb, borderColor: "#1f5c57", pointRadius: 0 },
        { label: "Epsilon-greedy", data: data.series.cum_epsilon, borderColor: "#b45309", pointRadius: 0 },
        { label: "Random", data: data.series.cum_random, borderColor: "#c4b5a0", pointRadius: 0 },
      ],
    },
    options: { responsive: true, plugins: { tooltip: { mode: "index", intersect: false } } },
  });

  destroyChart("arm");
  charts.arm = new Chart(document.getElementById("armChart"), {
    type: "bar",
    data: {
      labels: data.arms.map((a) => String(a.price)),
      datasets: [
        { label: "True profit", data: data.arms.map((a) => a.true_profit), backgroundColor: data.arms.map((a) => (a.is_oracle ? "#1f5c57" : "#c4b5a0")) },
      ],
    },
    options: { responsive: true },
  });

  document.getElementById("armTable").innerHTML = table(
    [{ label: "Price index" }, { label: "True units", num: true }, { label: "True profit", num: true }, { label: "Thompson pulls", num: true }, { label: "Mean profit", num: true }],
    data.arms.map((a) => [a.price, a.true_units.toFixed(1), a.true_profit.toFixed(1), a.thompson_pulls, a.thompson_mean_profit.toFixed(1)])
  );
  document.getElementById("results").hidden = false;
}

function renderBandit(data) {
  const m = data.metrics;
  document.getElementById("story").innerHTML = `<p><strong>Bandit path.</strong> ${data.story} Cumulative Thompson regret ${m.thompson_regret.toFixed(0)} versus epsilon-greedy ${data.series.cum_regret_epsilon[data.series.cum_regret_epsilon.length - 1].toFixed(0)}.</p>`;
  document.getElementById("kpis").innerHTML = `
    <div class="kpi"><b>${m.thompson_regret.toFixed(0)}</b><span>Thompson regret</span><p>Profit short of the oracle across ${m.n_rounds} rounds.</p></div>
    <div class="kpi"><b>${(100 * m.explore_share).toFixed(0)}%</b><span>Explore share</span><p>Not the current empirical best.</p></div>
    <div class="kpi"><b>${m.oracle_arm.toFixed(0)}</b><span>Oracle index</span><p>Where late-round prices should cluster.</p></div>`;

  destroyChart("price");
  charts.price = new Chart(document.getElementById("priceChart"), {
    type: "line",
    data: {
      labels: data.series.round,
      datasets: [{ label: "Price index", data: data.series.price, borderColor: "#1e3a5f", pointRadius: 2, showLine: false }],
    },
    options: { responsive: true },
  });
  destroyChart("regret");
  charts.regret = new Chart(document.getElementById("regretChart"), {
    type: "line",
    data: {
      labels: data.series.round,
      datasets: [
        { label: "Thompson", data: data.series.cum_regret_thompson, borderColor: "#1e3a5f", pointRadius: 0 },
        { label: "UCB", data: data.series.cum_regret_ucb, borderColor: "#1f5c57", pointRadius: 0 },
        { label: "Epsilon-greedy", data: data.series.cum_regret_epsilon, borderColor: "#b45309", pointRadius: 0 },
      ],
    },
    options: { responsive: true },
  });
  document.getElementById("results").hidden = false;
}

async function boot() {
  const res = await fetch("/api/pricing/latest");
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Pricing failed");
  if (PAGE === "overview") renderOverview(data);
  if (PAGE === "bandit") renderBandit(data);
  setStatus("Loaded last pricing run.", true);
}

document.getElementById("runPricing")?.addEventListener("click", async () => {
  const btn = document.getElementById("runPricing");
  btn.disabled = true;
  try {
    const res = await fetch("/api/pricing/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        n_rounds: Number(document.getElementById("nRounds").value),
        epsilon: Number(document.getElementById("epsilon").value),
        seed: Number(document.getElementById("seed").value),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Pricing failed");
    renderOverview(data);
    setStatus("Finished pricing run.", true);
  } catch (err) {
    setStatus(err.message, false);
  } finally {
    btn.disabled = false;
  }
});

if (PAGE) {
  boot().catch((err) => setStatus(err.message, false));
}
