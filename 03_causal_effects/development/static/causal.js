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
function pct(value) {
  return `${(100 * value).toFixed(1)}%`;
}

function renderOverview(data) {
  const m = data.metrics;
  document.getElementById("story").innerHTML = `<p><strong>What this run says.</strong> ${data.story}</p>`;
  document.getElementById("kpis").innerHTML = `
    <div class="kpi"><b>${pct(m.true_lift)}</b><span>True lift</span><p>Planted on treated geos after week ${m.treat_week}.</p></div>
    <div class="kpi"><b>${pct(m.obs_bias)}</b><span>Observational bias</span><p>Treated-only pre/post minus truth.</p></div>
    <div class="kpi"><b>${pct(m.did_confounded_bias)}</b><span>Confounded DiD bias</span><p>Still off if pre-trends are not parallel.</p></div>
    <div class="kpi"><b>${pct(m.rct_bias)}</b><span>Randomized DiD bias</span><p>Should sit near zero on this design.</p></div>`;

  destroyChart("conf");
  charts.conf = new Chart(document.getElementById("confChart"), {
    type: "line",
    data: {
      labels: data.series.week,
      datasets: [
        { label: "Treated (selected for growth)", data: data.series.treated_confounded, borderColor: "#9a3412", pointRadius: 0, borderWidth: 2 },
        { label: "Control", data: data.series.control_confounded, borderColor: "#1e3a5f", pointRadius: 0, borderWidth: 2 },
      ],
    },
    options: { responsive: true, plugins: { tooltip: { mode: "index", intersect: false } } },
  });

  destroyChart("bias");
  charts.bias = new Chart(document.getElementById("biasChart"), {
    type: "bar",
    data: {
      labels: data.methods.map((r) => r.method.replace(" (confounded)", "").replace(" (randomized)", "")),
      datasets: [
        { label: "Estimate", data: data.methods.map((r) => 100 * r.estimate), backgroundColor: "#1e3a5f" },
        { label: "True lift", data: data.methods.map(() => 100 * m.true_lift), backgroundColor: "#c4b5a0" },
      ],
    },
    options: { responsive: true, indexAxis: "y" },
  });

  document.getElementById("methodTable").innerHTML = table(
    [{ label: "Method" }, { label: "Setting" }, { label: "Estimate", num: true }, { label: "Bias", num: true }],
    data.methods.map((r) => [r.method, r.setting, pct(r.estimate), pct(r.bias)])
  );
  document.getElementById("results").hidden = false;
}

function renderExperiments(data) {
  document.getElementById("story").innerHTML = `<p><strong>Design.</strong> ${data.story}</p>`;
  destroyChart("rct");
  charts.rct = new Chart(document.getElementById("rctChart"), {
    type: "line",
    data: {
      labels: data.series.week,
      datasets: [
        { label: "Treated (random geos)", data: data.series.treated_rct, borderColor: "#1f5c57", pointRadius: 0, borderWidth: 2 },
        { label: "Control", data: data.series.control_rct, borderColor: "#1e3a5f", pointRadius: 0, borderWidth: 2 },
      ],
    },
    options: { responsive: true },
  });
  document.getElementById("geoTable").innerHTML = table(
    [{ label: "Geo" }, { label: "Treated" }, { label: "Growth", num: true }, { label: "Pre", num: true }, { label: "Post", num: true }, { label: "Change %", num: true }],
    data.geos.map((g) => [g.geo, g.treated ? "yes" : "no", g.growth.toFixed(4), g.pre.toFixed(1), g.post.toFixed(1), g.change_pct.toFixed(1)])
  );
  document.getElementById("results").hidden = false;
}

async function boot() {
  const res = await fetch("/api/causal/latest");
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Causal failed");
  if (PAGE === "overview") renderOverview(data);
  if (PAGE === "experiments") renderExperiments(data);
  setStatus("Loaded last causal run.", true);
}

document.getElementById("runCausal")?.addEventListener("click", async () => {
  const btn = document.getElementById("runCausal");
  btn.disabled = true;
  try {
    const res = await fetch("/api/causal/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        n_geos: Number(document.getElementById("nGeos").value),
        n_weeks: Number(document.getElementById("nWeeks").value),
        true_lift: Number(document.getElementById("trueLift").value),
        seed: Number(document.getElementById("seed").value),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Causal failed");
    renderOverview(data);
    setStatus("Finished causal run.", true);
  } catch (err) {
    setStatus(err.message, false);
  } finally {
    btn.disabled = false;
  }
});

if (PAGE) {
  boot().catch((err) => setStatus(err.message, false));
}
