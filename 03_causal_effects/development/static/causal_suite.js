const charts = {};

function setStatus(id, message, ok) {
  const el = document.getElementById(id);
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
  el.className = ok ? "status ok" : "status";
}

function renderResult(data) {
  const id = data.id;
  const m = data.metrics;
  const gate = document.getElementById(`gt-${id}`);
  gate.hidden = false;
  gate.className = m.passed ? "lab-gate pass" : "lab-gate fail";
  gate.textContent = `${m.passed ? "PASS" : "FAIL"} — ${m.gate}`;
  document.getElementById(`kp-${id}`).innerHTML = (data.kpis || [])
    .map((row) => `<div class="kpi"><b>${row.value}</b><span>${row.label}</span></div>`)
    .join("");
  const table = data.table || { headers: [], rows: [] };
  document.getElementById(`tb-${id}`).innerHTML = `<table><thead><tr>${table.headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${(table.rows || []).map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  document.getElementById(`sy-${id}`).textContent = data.story || "";
  const box = document.getElementById(`ex-${id}`);
  if (box) {
    box.hidden = false;
    box.innerHTML = `<h3>What this result means</h3><p>${data.result_explain || data.story || ""}</p>`;
  }
  drawChart(id, data.series || {});
}

function drawChart(id, series) {
  if (charts[id]) {
    charts[id].destroy();
    charts[id] = null;
  }
  const canvas = document.getElementById(`ch-${id}`);
  if (!canvas || !series.labels) return;
  const datasets = [];
  if (series.treated && series.control) {
    datasets.push({ label: "Treated", data: series.treated, borderColor: "#9a3412", pointRadius: 0, borderWidth: 2 });
    datasets.push({ label: "Control / synthetic / forecast", data: series.control, borderColor: "#1e3a5f", pointRadius: 0, borderWidth: 2 });
    if (series.synthetic) datasets[1].data = series.synthetic;
  } else if (series.actual && series.forecast) {
    datasets.push({ label: "Actual", data: series.actual, borderColor: "#1e3a5f", pointRadius: 0, borderWidth: 2 });
    datasets.push({ label: "Pre-period forecast", data: series.forecast, borderColor: "#9a3412", pointRadius: 0, borderWidth: 2, borderDash: [5, 4] });
  } else if (series.values) {
    datasets.push({ label: "Value", data: series.values, backgroundColor: "#1e3a5f" });
  } else {
    return;
  }
  const isLine = Boolean(series.treated || series.actual);
  charts[id] = new Chart(canvas, {
    type: isLine ? "line" : "bar",
    data: { labels: series.labels, datasets },
    options: { responsive: true, plugins: { legend: { display: datasets.length > 1 } } },
  });
}

async function runOne(method) {
  const button = document.querySelector(`[data-method="${method}"]`);
  if (button) button.disabled = true;
  setStatus(`st-${method}`, "Running…", true);
  try {
    const res = await fetch("/api/causal/suite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ method, seed: Number(document.getElementById("suiteSeed").value) || 42 }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Suite call failed");
    renderResult(data);
    setStatus(`st-${method}`, "Finished.", true);
    return data.metrics.passed;
  } catch (err) {
    setStatus(`st-${method}`, err.message, false);
    return false;
  } finally {
    if (button) button.disabled = false;
  }
}

async function runAll() {
  const button = document.getElementById("runAllSuite");
  button.disabled = true;
  const methods = [...document.querySelectorAll(".run-one")].map((el) => el.dataset.method);
  let passed = 0;
  setStatus("suiteStatus", "Running all twelve…", true);
  for (const method of methods) {
    if (await runOne(method)) passed += 1;
  }
  setStatus("suiteStatus", `${passed} of ${methods.length} gates passed.`, passed === methods.length);
  button.disabled = false;
}

document.querySelectorAll(".run-one").forEach((el) => {
  el.addEventListener("click", () => runOne(el.dataset.method));
});
document.getElementById("runAllSuite").addEventListener("click", runAll);
