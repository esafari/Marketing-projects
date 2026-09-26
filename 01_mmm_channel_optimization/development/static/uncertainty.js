const charts = {};
const PAGE = document.body.dataset.page;

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
  const res = await fetch("/api/uncertainty/latest");
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Could not load uncertainty");
  return data;
}

function renderKpis(data) {
  const m = data.metrics;
  const host = document.getElementById("kpis");
  if (!host) return;
  host.innerHTML = `
    <div class="kpi"><b>${m.n_boot}</b><span>Bootstrap draws</span><p>Residual and block each use this many refits. More draws smooth the tails.</p></div>
    <div class="kpi"><b>${m.ship}</b><span>Ship gates</span><p>Channels (or price) whose lower tail still clears the hurdle.</p></div>
    <div class="kpi"><b>${m.watch}</b><span>Watch gates</span><p>Interval crosses zero or the 1.0 iROAS line. Keep the lock; test if you can.</p></div>
    <div class="kpi"><b>${m.kill}</b><span>Kill gates</span><p>Upper tail is still unprofitable or the effect is negative.</p></div>
    <div class="kpi"><b>${m.profit_lift_p.toFixed(3)}</b><span>Reallocation p-value</span><p>Share of bootstrap profit gaps ≤ 0. Below 0.05: last-touch is beaten on purpose, not by luck.</p></div>
    <div class="kpi"><b>${m.price_perm_p.toFixed(3)}</b><span>Price permutation p</span><p>Would a shuffled price series look this strong? Below 0.05: price is identified.</p></div>`;
}

function mediaBetas(data) {
  return data.residual.parameters.filter((p) => p.name.startsWith("trans_")).map((p) => ({ ...p, label: p.name.replace("trans_", "") }));
}

function renderOverview(data) {
  const m = data.metrics;
  const gap = data.residual.profit_gap;
  document.getElementById("story").innerHTML = `
    <p><strong>What the intervals say.</strong> ${m.n_boot} residual draws and ${m.n_boot} block draws on ${m.n_weeks} weeks. ${m.ship} Ship, ${m.watch} Watch, ${m.kill} Kill. The profit gap versus last-touch is ${money(gap.estimate)}k per week at the point estimate; 90% bootstrap interval [${money(gap.p05)}k, ${money(gap.p95)}k]. Reallocation p-value ${m.profit_lift_p.toFixed(3)}.</p>
    <p>Brief the interval, not a single iROAS. If residual and block widths disagree, believe the wider one. Classical t-tests on the tests page will look over-confident whenever weeks cluster.</p>`;
  renderKpis(data);

  const betas = mediaBetas(data);
  destroyChart("beta");
  charts.beta = new Chart(document.getElementById("betaChart"), {
    type: "bar",
    data: {
      labels: betas.map((r) => r.label),
      datasets: [
        { label: "5th pct", data: betas.map((r) => r.p05), backgroundColor: "#c4b5a0" },
        { label: "OLS", data: betas.map((r) => r.estimate), backgroundColor: "#1e3a5f" },
        { label: "95th pct", data: betas.map((r) => r.p95), backgroundColor: "#1f5c57" },
      ],
    },
    options: { responsive: true },
  });

  destroyChart("iroas");
  charts.iroas = new Chart(document.getElementById("iroasChart"), {
    type: "bar",
    data: {
      labels: data.residual.iroas.map((r) => r.name),
      datasets: [
        { label: "p10", data: data.residual.iroas.map((r) => r.p10), backgroundColor: "#c4b5a0" },
        { label: "iROAS", data: data.residual.iroas.map((r) => r.estimate), backgroundColor: "#1e3a5f" },
        { label: "p90", data: data.residual.iroas.map((r) => r.p90), backgroundColor: "#1f5c57" },
      ],
    },
    options: { responsive: true },
  });

  const widthNames = ["log_price", ...betas.map((b) => b.name)];
  const residMap = Object.fromEntries(data.residual.parameters.map((p) => [p.name, p]));
  const blockMap = Object.fromEntries(data.block.parameters.map((p) => [p.name, p]));
  destroyChart("width");
  charts.width = new Chart(document.getElementById("widthChart"), {
    type: "bar",
    data: {
      labels: widthNames.map((n) => n.replace("trans_", "").replace("log_price", "Price")),
      datasets: [
        { label: "Residual 90% width", data: widthNames.map((n) => residMap[n].p95 - residMap[n].p05), backgroundColor: "#1e3a5f" },
        { label: "Block 90% width", data: widthNames.map((n) => blockMap[n].p95 - blockMap[n].p05), backgroundColor: "#9a3412" },
      ],
    },
    options: { responsive: true },
  });

  const ph = gap.hist;
  const labels = [];
  for (let i = 0; i < ph.counts.length; i += 1) labels.push(ph.edges[i].toFixed(1));
  destroyChart("profitHist");
  charts.profitHist = new Chart(document.getElementById("profitHist"), {
    type: "bar",
    data: { labels, datasets: [{ label: "Draws", data: ph.counts, backgroundColor: "#1f5c57" }] },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  const ciRows = [...mediaBetas(data), ...data.residual.iroas.map((r) => ({ ...r, label: `iROAS ${r.name}` })), { ...data.residual.profit_gap, label: "Profit gap" }];
  document.getElementById("ciTable").innerHTML = table(
    [
      { label: "Quantity" },
      { label: "Estimate", num: true },
      { label: "p05", num: true },
      { label: "p10", num: true },
      { label: "p90", num: true },
      { label: "p95", num: true },
    ],
    ciRows.map((r) => [r.label || r.name, r.estimate.toFixed(2), r.p05.toFixed(2), r.p10.toFixed(2), r.p90.toFixed(2), r.p95.toFixed(2)])
  );
  document.getElementById("gateTable").innerHTML = table(
    [{ label: "Lever" }, { label: "Gate" }, { label: "iROAS / β", num: true }, { label: "p10", num: true }, { label: "p90", num: true }, { label: "Read as" }],
    data.gates.map((g) => [g.name, `<span class="gate-${g.gate}">${g.gate}</span>`, g.iROAS.toFixed(2), g.iROAS_p10.toFixed(2), g.iROAS_p90.toFixed(2), g.note])
  );
  document.getElementById("results").hidden = false;
}

function renderTests(data) {
  const rejects = data.tests.filter((t) => t.reject_05).length;
  document.getElementById("story").innerHTML = `
    <p><strong>What the tests say.</strong> ${rejects} of ${data.tests.length} nulls reject at 5% on the residual bootstrap. Price permutation p = ${data.metrics.price_perm_p.toFixed(3)}. Classical OLS p-values will usually look smaller — that is leftover weekly dependence, not a better test.</p>
    <p>Use a rejected iROAS hurdle to defend adding budget. Use a failed TV-vs-Search contrast to stop a slide that claims they are equal. Use a failed profit-lift test to keep last-touch for one more quarter.</p>`;
  renderKpis(data);

  destroyChart("p");
  charts.p = new Chart(document.getElementById("pChart"), {
    type: "bar",
    data: {
      labels: data.tests.map((t) => t.id),
      datasets: [{ label: "Bootstrap p", data: data.tests.map((t) => t.p_value), backgroundColor: data.tests.map((t) => (t.p_value < 0.05 ? "#1f5c57" : "#9a3412")) }],
    },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { min: 0, max: 1 } } },
  });

  const ph = data.permutation_price.hist;
  const labels = [];
  for (let i = 0; i < ph.counts.length; i += 1) labels.push(ph.edges[i].toFixed(0));
  destroyChart("perm");
  charts.perm = new Chart(document.getElementById("permChart"), {
    type: "bar",
    data: { labels, datasets: [{ label: "Null β_P", data: ph.counts, backgroundColor: "#1e3a5f" }] },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  document.getElementById("testTable").innerHTML = table(
    [
      { label: "Hypothesis" },
      { label: "Estimate", num: true },
      { label: "Boot p", num: true },
      { label: "OLS p", num: true },
      { label: "Reject 5%?" },
      { label: "Method" },
    ],
    data.tests.map((t) => [
      t.hypothesis,
      t.estimate.toFixed(2),
      t.p_value.toFixed(3),
      t.classical_p == null ? "—" : t.classical_p.toExponential(2),
      t.reject_05 ? "Yes" : "No",
      t.method,
    ])
  );
  document.getElementById("olsTable").innerHTML = table(
    [
      { label: "Parameter" },
      { label: "Estimate", num: true },
      { label: "SE", num: true },
      { label: "t", num: true },
      { label: "p", num: true },
      { label: "95% lo", num: true },
      { label: "95% hi", num: true },
    ],
    data.classical.map((r) => [r.parameter, r.estimate.toFixed(2), r.std_err.toFixed(2), r.t_stat.toFixed(2), r.p_value.toExponential(2), r.ci_lo.toFixed(2), r.ci_hi.toFixed(2)])
  );
  document.getElementById("results").hidden = false;
}

async function runUnc() {
  const btn = document.getElementById("runUnc");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Bootstrapping…";
  }
  try {
    const res = await fetch("/api/uncertainty/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        n_weeks: Number(document.getElementById("nWeeks").value),
        n_boot: Number(document.getElementById("nBoot").value),
        block_len: Number(document.getElementById("blockLen").value),
        seed: Number(document.getElementById("seed").value),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Run failed");
    renderOverview(data);
    setStatus(`Finished. ${data.metrics.n_boot} draws. ${data.metrics.ship} Ship / ${data.metrics.watch} Watch / ${data.metrics.kill} Kill.`, true);
  } catch (err) {
    setStatus(err.message, false);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Run bootstrap";
    }
  }
}

async function boot() {
  try {
    const data = await fetchLatest();
    if (PAGE === "overview") {
      renderOverview(data);
      setStatus(`Loaded last run. ${data.metrics.n_boot} draws.`, true);
    } else if (PAGE === "tests") {
      renderTests(data);
    }
  } catch (err) {
    setStatus(err.message, false);
  }
}

document.getElementById("runUnc")?.addEventListener("click", runUnc);
if (PAGE !== "methods") {
  boot();
}
