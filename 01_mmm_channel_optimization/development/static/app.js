const SUGGESTIONS = {
  TOFU: ["OOH", "Podcast", "Display", "Cinema", "Streaming TV"],
  MOFU: ["YouTube", "Influencer", "Email", "Pinterest"],
  BOFU: ["Shopping", "Affiliate", "Retargeting", "Comparison"],
};

const TIER_DEFAULTS = {
  TOFU: { decay: 0.55, k_hill: 70, alpha: 160, beta: 0, mean_spend: 36, bound_low: 8, bound_high: 70, flight_on: 4, flight_cycle: 8, holiday_uplift: 0.2 },
  MOFU: { decay: 0.25, k_hill: 40, alpha: 80, beta: 95, mean_spend: 32, bound_low: 8, bound_high: 55, flight_on: 0, flight_cycle: 1, holiday_uplift: 0.3 },
  BOFU: { decay: 0.08, k_hill: 45, alpha: 0, beta: 240, mean_spend: 38, bound_low: 12, bound_high: 70, flight_on: 0, flight_cycle: 1, holiday_uplift: 0.4 },
};

let channels = [];
let uid = 0;
const charts = {};
const PALETTE = ["#1e3a5f", "#1f5c57", "#9a3412", "#b45309", "#7c3aed", "#0f766e", "#be185d", "#365314"];
const GROUP_COLORS = {
  Intercept: "#c4b5a0",
  Calendar: "#1f5c57",
  Commercial: "#9a3412",
  "Competitive / macro": "#6d28d9",
  "Intent (M_hat)": "#b45309",
  "Direct media": "#1e3a5f",
  Residual: "#a8a29e",
};

const FIELD_HELP = {
  decay: "θ: share of last week's adstock still alive. TV ~0.65 (long memory). Search ~0.08 (dies in days). Known DGP truth in this studio.",
  k_hill: "K: adstock level at 50% of max effect. Not a budget cap. Higher K saturates later. Search near K is why the funnel plan pulls it back.",
  alpha: "True α: lift in intent M per unit of transformed spend. TOFU/MOFU only. 2SLS tries to recover this. Hidden on BOFU.",
  beta: "True β: direct lift in sales Y per unit of transformed spend, not through M. MOFU/BOFU only. Hidden on TOFU.",
  mean_spend: "Average weekly $k used to simulate history. Not the recommended mix. Moves where you sit on the Hill curve.",
  bound_low: "L: SLSQP cannot spend below this. Sum of mins must be ≤ weekly budget.",
  bound_high: "U: SLSQP cannot spend above this. Stops extrapolation. Sum of maxes must be ≥ weekly budget.",
  holiday_uplift: "DGP only: extra holiday-week spend (0.25 = +25%). Not the holiday dummy on Y. Makes media and Christmas move together.",
  flight_on: "DGP only (TOFU): weeks on-air inside each cycle. 4 = a month-long burst. Lumpy flights identify TV vs season.",
  flight_cycle: "DGP only (TOFU): on+off length in weeks. TV 4 on / cycle 8 = on a month, off a month.",
};

function field(ch, key, label, step = "any") {
  const tip = FIELD_HELP[key] || "";
  return `<label title="${tip}">${label}<input data-key="${key}" data-uid="${ch.uid}" type="number" step="${step}" value="${ch[key]}" title="${tip}" /></label>`;
}

function renderLanes() {
  ["TOFU", "MOFU", "BOFU"].forEach((funnel) => {
    const host = document.getElementById(`lane-${funnel}`);
    host.innerHTML = channels
      .filter((c) => c.funnel === funnel)
      .map((ch) => {
        const intent = funnel !== "BOFU";
        const direct = funnel !== "TOFU";
        return `
          <div class="card">
            <div class="card-head">
              <input type="text" data-key="name" data-uid="${ch.uid}" value="${ch.name}" />
              <button class="remove" data-remove="${ch.uid}" type="button">Remove</button>
            </div>
            <div class="grid">
              ${field(ch, "decay", "Adstock decay")}
              ${field(ch, "k_hill", "Hill K")}
              ${intent ? field(ch, "alpha", "Intent alpha") : ""}
              ${direct ? field(ch, "beta", "Direct beta") : ""}
              ${field(ch, "mean_spend", "Mean spend $k")}
              ${field(ch, "bound_low", "Min $k")}
              ${field(ch, "bound_high", "Max $k")}
              ${field(ch, "holiday_uplift", "Holiday uplift")}
              ${funnel === "TOFU" ? field(ch, "flight_on", "Flight on wks", "1") : ""}
              ${funnel === "TOFU" ? field(ch, "flight_cycle", "Flight cycle", "1") : ""}
            </div>
          </div>`;
      })
      .join("");
  });
}

function readCardsIntoState() {
  document.querySelectorAll("[data-key]").forEach((input) => {
    const ch = channels.find((c) => String(c.uid) === input.dataset.uid);
    if (!ch) return;
    const key = input.dataset.key;
    ch[key] = input.type === "number" ? Number(input.value) : input.value;
  });
}

function nextName(funnel) {
  const used = new Set(channels.map((c) => c.name.toLowerCase()));
  const pool = SUGGESTIONS[funnel];
  const fresh = pool.find((name) => !used.has(name.toLowerCase()));
  if (fresh) return fresh;
  return `${funnel} channel ${channels.filter((c) => c.funnel === funnel).length + 1}`;
}

function addChannel(funnel) {
  readCardsIntoState();
  channels.push({ uid: ++uid, name: nextName(funnel), funnel, ...TIER_DEFAULTS[funnel] });
  renderLanes();
}

function setChannelsFromPreset(list) {
  channels = list.map((item) => ({ uid: ++uid, ...item }));
  renderLanes();
}

async function loadPreset() {
  const res = await fetch("/api/presets");
  const data = await res.json();
  setChannelsFromPreset(data.channels);
}

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

function topBy(rows, key) {
  return [...rows].sort((a, b) => b[key] - a[key])[0];
}

function interpretRun(data) {
  const m = data.metrics;
  const attr = data.attribution;
  const alloc = data.allocation;
  const mroi = data.mroi;
  const biggestTotal = topBy(attr, "total");
  const biggestIndirect = topBy(attr, "indirect");
  const harvest = alloc.filter((r) => r.funnel === "BOFU");
  const awareness = alloc.filter((r) => r.funnel === "TOFU");
  const harvestCut = harvest.reduce((s, r) => s + Math.min(0, r.shift), 0);
  const tofuGain = awareness.reduce((s, r) => s + Math.max(0, r.shift), 0);
  const naiveHero = topBy(alloc, "naive");
  const maxMroi = topBy(mroi, "total_mroi");
  const minMroi = [...mroi].sort((a, b) => a.total_mroi - b.total_mroi)[0];
  const betaM = data.coefficients.find((r) => r.parameter.startsWith("beta_M"));
  const hardId = [...data.coefficients].sort((a, b) => b.abs_error - a.abs_error)[0];

  const fitNote =
    m.test_r2 >= 0.75
      ? "The holdout fit is strong: the 2SLS system is tracking unseen weeks, not just memorizing seasonality."
      : m.test_r2 >= 0.5
        ? "The holdout fit is acceptable. Channel effects are usable, but treat small coefficient gaps as noise."
        : "The holdout fit is weak. Add more weeks, simplify the mix, or check that at least one TOFU/MOFU channel can move intent.";

  document.getElementById("story").innerHTML = `
    <p><strong>What this run says.</strong> With a $${m.weekly_budget.toFixed(0)}k weekly envelope, the funnel-aware mix earns ${money(m.funnel_return)}k incremental sales versus ${money(m.naive_return)}k for the naive mix — a ${m.pct_gain >= 0 ? "+" : ""}${m.pct_gain.toFixed(1)}% lift without spending more.</p>
    <p>Historically, <strong>${biggestTotal.name}</strong> is the largest attributed channel (${money(biggestTotal.total)}k total). <strong>${biggestIndirect.name}</strong> carries the most indirect (intent-mediated) sales (${money(biggestIndirect.indirect)}k). The naive plan leans on <strong>${naiveHero.name}</strong> because that is where the direct beta is most visible.</p>
    <p>${fitNote} Train weeks: ${m.train_weeks}. Holdout weeks: ${m.test_weeks}. Durbin-Watson ${m.durbin_watson.toFixed(2)} (near 2.0 means residuals are not obviously autocorrelated).</p>`;

  document.getElementById("kpiExplain").textContent =
    `Funnel-aware weekly yield is incremental sales under the 2SLS response surface at the recommended mix. Lift vs naive is the value of counting indirect effects. Holdout R-squared ${m.test_r2.toFixed(3)} is variance explained on weeks the model never trained on. MAPE ${m.test_mape.toFixed(2)}% is the average percent miss on those weeks.`;

  document.getElementById("attrStory").textContent =
    `${biggestIndirect.name} shows that awareness can dominate even with $0 direct sales. Read "Indirect share" as the percent of that channel's credit that a last-click report would miss.`;

  document.getElementById("allocStory").textContent =
    tofuGain > 0.5
      ? `The funnel mix moves about $${tofuGain.toFixed(1)}k/week into TOFU and pulls about $${Math.abs(harvestCut).toFixed(1)}k/week out of BOFU. That is the search-bias correction.`
      : "In this mix the optimizer did not need a large TOFU shift. Check whether BOFU bounds are already tight, or whether awareness alphas are small.";

  document.getElementById("mroiStory").textContent =
    Math.abs(maxMroi.total_mroi - minMroi.total_mroi) < 0.35
      ? `Total mROI is nearly equalized (${minMroi.total_mroi.toFixed(2)} to ${maxMroi.total_mroi.toFixed(2)}). That is equimarginal allocation: the last dollar is about as productive on every channel.`
      : `mROI is not fully equalized (${minMroi.name} ${minMroi.total_mroi.toFixed(2)} vs ${maxMroi.name} ${maxMroi.total_mroi.toFixed(2)}). A bound is likely binding — the solver wanted more of the high-mROI channel but hit min/max.`;

  document.getElementById("coefStory").textContent = betaM
    ? `Intent-to-sales beta_M recovered at ${betaM.estimated.toFixed(2)} versus true ${betaM.true.toFixed(2)}. The largest miss is ${hardId.parameter} (error ${hardId.abs_error.toFixed(1)}). That is expected when a MOFU channel sits in both equations.`
    : "";

  const salesControls = (data.control_coefficients || []).filter((r) => r.stage === "sales");
  if (salesControls.length) {
    const worst = [...salesControls].sort((a, b) => b.abs_error - a.abs_error)[0];
    const price = salesControls.find((r) => r.id === "price_dev");
    const stock = salesControls.find((r) => r.id === "stockout_rate");
    document.getElementById("controlStory").textContent =
      `Largest control miss: ${worst.label} (true ${worst.true.toFixed(1)}, estimated ${worst.estimated.toFixed(1)}). ` +
      (price ? `Price recovered at ${price.estimated.toFixed(1)} vs true ${price.true.toFixed(1)} per index point. ` : "") +
      (stock ? `Stockouts recovered at ${stock.estimated.toFixed(1)} vs true ${stock.true.toFixed(1)}. ` : "") +
      `Mean weekly sales ${money(m.mean_sales)}k; media-attributed ${money(m.media_weekly)}k/week; net control contribution ${money(m.control_net_weekly)}k/week.`;
  }
}

function renderResults(data) {
  const m = data.metrics;
  document.getElementById("kpis").innerHTML = `
    <div class="kpi"><b>${money(m.funnel_return)}k</b><span>Funnel-aware weekly yield</span><p>Incremental weekly sales if you follow the funnel mix. Not total company revenue — only the media-driven piece the optimizer can change.</p></div>
    <div class="kpi"><b>${m.pct_gain >= 0 ? "+" : ""}${m.pct_gain.toFixed(1)}%</b><span>Lift vs naive mix</span><p>Same budget, different split. Positive means counting indirect awareness paid off versus a harvest-only plan.</p></div>
    <div class="kpi"><b>${m.test_r2.toFixed(3)}</b><span>Holdout R-squared</span><p>1.0 = the forecast matches every wiggle in the last 20% of weeks. 0 = no better than predicting the mean.</p></div>
    <div class="kpi"><b>${m.test_mape.toFixed(2)}%</b><span>Holdout MAPE</span><p>Average absolute percent error on holdout weeks. Under ~2% is tight on this synthetic sales scale.</p></div>
    <div class="kpi"><b>${money(m.control_net_weekly || 0)}k</b><span>Net control $k / week</span><p>Sum of Stage-2 control terms at their sample means. Negative is normal: price, stockouts, SOV, unemployment, and CPI pull sales down.</p></div>
    <div class="kpi"><b>${m.durbin_watson.toFixed(2)}</b><span>Durbin-Watson</span><p>Near 2.0 means Stage-2 residuals are not obviously autocorrelated. Below 1.5 means leftover weekly memory.</p></div>`;
  interpretRun(data);

  document.getElementById("attrTable").innerHTML = table(
    [{ label: "Channel" }, { label: "Funnel" }, { label: "Direct $k", num: true }, { label: "Indirect $k", num: true }, { label: "Total $k", num: true }, { label: "Indirect share", num: true }],
    data.attribution.map((r) => [r.name, r.funnel, money(r.direct), money(r.indirect), money(r.total), `${r.indirect_share.toFixed(0)}%`])
  );
  document.getElementById("allocTable").innerHTML = table(
    [{ label: "Channel" }, { label: "Naive $k", num: true }, { label: "Funnel $k", num: true }, { label: "Shift", num: true }],
    data.allocation.map((r) => [r.name, money(r.naive), money(r.funnel_aware), `${r.shift >= 0 ? "+" : ""}${r.shift.toFixed(1)}`])
  );
  document.getElementById("mroiTable").innerHTML = table(
    [{ label: "Channel" }, { label: "Direct", num: true }, { label: "Indirect", num: true }, { label: "Total mROI", num: true }],
    data.mroi.map((r) => [r.name, r.direct_mroi.toFixed(2), r.indirect_mroi.toFixed(2), r.total_mroi.toFixed(2)])
  );
  document.getElementById("coefTable").innerHTML = table(
    [{ label: "Parameter" }, { label: "True", num: true }, { label: "Estimated", num: true }, { label: "Abs error", num: true }],
    data.coefficients.map((r) => [r.parameter, r.true.toFixed(1), r.estimated.toFixed(1), r.abs_error.toFixed(1)])
  );
  document.getElementById("controlTable").innerHTML = table(
    [
      { label: "Control" },
      { label: "Stage" },
      { label: "Unit" },
      { label: "Real range" },
      { label: "Mean", num: true },
      { label: "True β", num: true },
      { label: "Est. β", num: true },
      { label: "Abs error", num: true },
      { label: "Mean $k/wk", num: true },
    ],
    (data.control_coefficients || []).map((r) => [
      r.label,
      r.stage,
      r.unit,
      r.real_range,
      r.mean.toFixed(2),
      r.true.toFixed(2),
      r.estimated.toFixed(2),
      r.abs_error.toFixed(2),
      money(r.mean_contribution),
    ])
  );
  document.getElementById("contribTable").innerHTML = table(
    [{ label: "Term" }, { label: "Total $k", num: true }, { label: "Mean weekly $k", num: true }],
    (data.control_contributions || []).map((r) => [r.name, money(r.total), money(r.mean_weekly)])
  );

  const names = data.attribution.map((r) => r.name);
  destroyChart("attr");
  charts.attr = new Chart(document.getElementById("attrChart"), {
    type: "bar",
    data: {
      labels: names,
      datasets: [
        { label: "Direct", data: data.attribution.map((r) => r.direct), backgroundColor: "#1e3a5f" },
        { label: "Indirect", data: data.attribution.map((r) => r.indirect), backgroundColor: "#1f5c57" },
      ],
    },
    options: { responsive: true, scales: { x: { stacked: true }, y: { stacked: true } } },
  });

  destroyChart("budget");
  charts.budget = new Chart(document.getElementById("budgetChart"), {
    type: "bar",
    data: {
      labels: data.allocation.map((r) => r.name),
      datasets: [
        { label: "Naive", data: data.allocation.map((r) => r.naive), backgroundColor: "#9a3412" },
        { label: "Funnel-aware", data: data.allocation.map((r) => r.funnel_aware), backgroundColor: "#1e3a5f" },
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
        { label: "Actual sales", data: data.series.test_actual, borderColor: "#1c1914", tension: 0.2, pointRadius: 0 },
        { label: "2SLS forecast", data: data.series.test_pred, borderColor: "#b45309", tension: 0.2, pointRadius: 0 },
      ],
    },
    options: { responsive: true },
  });

  renderAnalysisCharts(data);

  document.getElementById("results").hidden = false;
  document.getElementById("results").scrollIntoView({ behavior: "smooth", block: "start" });
}

function fmtVif(value) {
  if (value == null || !Number.isFinite(value)) return "inf";
  return value.toFixed(1);
}

function renderAnalysisCharts(data) {
  const weeks = data.series.week;
  const split = data.series.split_week;
  if (!data.series.fitted || !data.control_coefficients) {
    return;
  }

  destroyChart("fullFit");
  charts.fullFit = new Chart(document.getElementById("fullFitChart"), {
    type: "line",
    data: {
      labels: weeks,
      datasets: [
        { label: "Actual sales", data: data.series.sales, borderColor: "#1e3a5f", tension: 0.15, pointRadius: 0, borderWidth: 2 },
        { label: "Fitted / forecast", data: data.series.fitted, borderColor: "#1f5c57", tension: 0.15, pointRadius: 0, borderWidth: 2, borderDash: [5, 3] },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        annotation: undefined,
        tooltip: { mode: "index", intersect: false },
      },
      scales: { x: { title: { display: true, text: `Week (split at ${split})` } } },
    },
  });

  const groups = data.series.contribution_groups || {};
  destroyChart("contrib");
  charts.contrib = new Chart(document.getElementById("contribChart"), {
    type: "bar",
    data: {
      labels: weeks,
      datasets: Object.keys(GROUP_COLORS)
        .filter((name) => groups[name])
        .map((name) => ({
          label: name,
          data: groups[name],
          backgroundColor: GROUP_COLORS[name],
          stack: "contrib",
          borderWidth: 0,
        })),
    },
    options: {
      responsive: true,
      plugins: { tooltip: { mode: "index", intersect: false } },
      scales: { x: { stacked: true, ticks: { maxTicksLimit: 16 } }, y: { stacked: true } },
    },
  });

  const salesControls = (data.control_coefficients || []).filter((r) => r.stage === "sales");
  destroyChart("controlContrib");
  charts.controlContrib = new Chart(document.getElementById("controlContribChart"), {
    type: "bar",
    data: {
      labels: salesControls.map((r) => r.label),
      datasets: [
        {
          label: "Mean weekly $k",
          data: salesControls.map((r) => r.mean_contribution),
          backgroundColor: salesControls.map((r) => (r.mean_contribution >= 0 ? "#1f5c57" : "#9a3412")),
        },
      ],
    },
    options: { responsive: true, indexAxis: "y", plugins: { legend: { display: false } } },
  });

  destroyChart("controlCoef");
  charts.controlCoef = new Chart(document.getElementById("controlCoefChart"), {
    type: "bar",
    data: {
      labels: salesControls.map((r) => r.label),
      datasets: [
        { label: "True", data: salesControls.map((r) => r.true), backgroundColor: "#1c1914" },
        { label: "Estimated", data: salesControls.map((r) => r.estimated), backgroundColor: "#b45309" },
      ],
    },
    options: { responsive: true, scales: { x: { ticks: { maxRotation: 50, minRotation: 0 } } } },
  });

  const z = data.series.controls_z || {};
  const zKeys = [
    ["price_index", "Price index"],
    ["promo_depth", "Promo depth"],
    ["stockout_rate", "Stockout"],
    ["competitor_sov", "Competitor SOV"],
    ["unemployment", "Unemployment"],
    ["cpi_yoy", "CPI YoY"],
    ["temperature", "Temperature"],
    ["holiday", "Holiday"],
    ["payday", "Payday"],
  ];
  destroyChart("controlZ");
  charts.controlZ = new Chart(document.getElementById("controlZChart"), {
    type: "line",
    data: {
      labels: weeks,
      datasets: zKeys.filter(([key]) => z[key]).map(([key, label], i) => ({
        label,
        data: z[key],
        borderColor: PALETTE[i % PALETTE.length],
        tension: 0.15,
        pointRadius: 0,
        borderWidth: key === "holiday" || key === "payday" ? 1 : 2,
      })),
    },
    options: {
      responsive: true,
      plugins: { tooltip: { mode: "index", intersect: false } },
      scales: { y: { title: { display: true, text: "z-score" } }, x: { ticks: { maxTicksLimit: 16 } } },
    },
  });

  destroyChart("hill");
  const hill = data.hill_curves || [];
  charts.hill = new Chart(document.getElementById("hillChart"), {
    type: "line",
    data: {
      labels: hill[0] ? hill[0].x_over_k.map((v) => v.toFixed(2)) : [],
      datasets: hill.flatMap((ch, i) => {
        const color = PALETTE[i % PALETTE.length];
        const opIdx = Math.round((ch.mean_x_over_k / 3) * (ch.x_over_k.length - 1));
        const marker = ch.x_over_k.map((_, j) => (j === opIdx ? ch.mean_response : null));
        return [
          {
            label: ch.name,
            data: ch.y,
            borderColor: color,
            tension: 0.15,
            pointRadius: 0,
            borderWidth: 2,
          },
          {
            label: `${ch.name} now`,
            data: marker,
            borderColor: color,
            backgroundColor: color,
            pointRadius: 5,
            showLine: false,
          },
        ];
      }),
    },
    options: {
      responsive: true,
      plugins: { tooltip: { mode: "index", intersect: false } },
      scales: { x: { title: { display: true, text: "Adstock / K" } }, y: { title: { display: true, text: "Hill response" }, min: 0, max: 1 } },
    },
  });

  destroyChart("resid");
  charts.resid = new Chart(document.getElementById("residChart"), {
    type: "bar",
    data: {
      labels: data.series.train_week || weeks,
      datasets: [{ label: "Stage-2 residual", data: data.series.train_resid || data.series.residual, backgroundColor: "#1e3a5f" }],
    },
    options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { maxTicksLimit: 12 } } } },
  });

  const vifRows = [...(data.vif?.stage1 || []).map((r) => ({ ...r, stage: "S1" })), ...(data.vif?.stage2 || []).map((r) => ({ ...r, stage: "S2" }))];
  destroyChart("vif");
  charts.vif = new Chart(document.getElementById("vifChart"), {
    type: "bar",
    data: {
      labels: vifRows.map((r) => `${r.stage} ${r.feature}`),
      datasets: [
        {
          label: "VIF",
          data: vifRows.map((r) => (r.vif == null || !Number.isFinite(r.vif) ? 40 : Math.min(r.vif, 40))),
          backgroundColor: vifRows.map((r) => (r.vif != null && r.vif > 10 ? "#9a3412" : "#1f5c57")),
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `VIF ${fmtVif(vifRows[ctx.dataIndex].vif)}`,
          },
        },
      },
      scales: { y: { title: { display: true, text: "VIF (capped at 40)" } } },
    },
  });
}

async function runModel() {
  readCardsIntoState();
  const status = document.getElementById("status");
  const btn = document.getElementById("runBtn");
  status.hidden = true;
  btn.disabled = true;
  btn.textContent = "Running…";
  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        weekly_budget: Number(document.getElementById("weeklyBudget").value),
        n_weeks: Number(document.getElementById("nWeeks").value),
        seed: Number(document.getElementById("seed").value),
        channels,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Run failed");
    renderResults(data);
    status.textContent = `Finished. ${data.metrics.n_weeks} weeks, ${data.channels.length} channels.`;
    status.className = "status ok";
    status.hidden = false;
  } catch (err) {
    status.textContent = err.message;
    status.className = "status";
    status.hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = "Run model";
  }
}

document.addEventListener("click", (event) => {
  const add = event.target.dataset.add;
  if (add) addChannel(add);
  const remove = event.target.dataset.remove;
  if (remove) {
    readCardsIntoState();
    channels = channels.filter((c) => String(c.uid) !== String(remove));
    renderLanes();
  }
});
document.getElementById("runBtn").addEventListener("click", runModel);
document.getElementById("resetBtn").addEventListener("click", loadPreset);

function openStudioTab(id) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === id));
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.hidden = panel.id !== `tab-${id}`;
  });
  if (id === "studio") {
    Object.values(charts).forEach((c) => c && c.resize && c.resize());
  }
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    const id = btn.dataset.tab;
    openStudioTab(id);
    const hash = `#tab-${id}`;
    if (location.hash !== hash) {
      history.replaceState(null, "", hash);
    }
  });
});

loadPreset();

function applyStudioHash() {
  if (location.hash === "#q-hellofresh") {
    location.replace(location.pathname + location.search + "#q-x");
    return;
  }
  const hash = location.hash;
  if (hash === "#tab-playbook" || hash.startsWith("#q-") || hash.startsWith("#d-") || hash.startsWith("#hf-")) {
    openStudioTab("playbook");
  }
  if (hash === "#tab-methods" || hash === "#m-ctrl-what" || hash === "#m-controls" || hash === "#m-cards") {
    openStudioTab("methods");
  }
  if (hash === "#tab-cloud" || hash.startsWith("#c-")) openStudioTab("cloud");
  if (hash === "#tab-test" || hash.startsWith("#td-")) openStudioTab("test");
  if (hash === "#tab-studio") openStudioTab("studio");
  if (hash === "#studio-attrs" || hash.startsWith("#attr-")) openStudioTab("studio");
}

applyStudioHash();
window.addEventListener("hashchange", applyStudioHash);
