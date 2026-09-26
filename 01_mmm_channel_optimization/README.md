# Project 01 — Mix modeling and channel optimization

**Question.** How should X Canada split a fixed weekly media envelope across advertising channels so the next dollar is incremental ship-week box revenue, not last-click harvest?

**Company.** X Canada is a weekly meal-kit subscription (same economics as HelloFresh). It buys *first boxes* with television, YouTube, social, and paid search. Last-click tags credit branded search (“X meal kit”, “X Canada”) for people who already decided after a TV ad. Finance sees last-touch return that makes search look like the only profitable lever. Brand teams see those queries fall when television is cut. First-box promo depth, payday weeks, and popular-recipe stockouts also move ship-week revenue.

**Production cloud.** Azure, Canada Central.  
**Grain.** One Canada week. Outcome `Y` is ship-week net box revenue, not Google conversion value.

Live (from the studio root: `python run_webapp.py`):

| Stage | URL |
|---|---|
| Problem | `/mmm/problem` |
| Data engineering | `/mmm/data-engineering` |
| Development | `/mmm` |
| Production | `/mmm/production` |
| Lab test | `/` card 01 |

---

## Problem

A weekly budget `B` is spent across top-of-funnel (TV, YouTube), mid-funnel (social), and bottom-of-funnel (paid search). Last-touch and multi-touch rules assign the box to the harvest click. Ordinary least squares of sales on spend lets search steal television’s effect because search and unobserved demand move together. We need a national weekly model that:

1. Estimates *incremental* channel effects after intent, price, promo, and season are held fixed.
2. Recommends a feasible mix under min/max bounds that still sums to `B`.

**Decision this model is allowed to change.** Next quarter’s weekly mix: how many dollars move from search to television or YouTube, and whether branded search is already on the flat part of the Hill curve.

**Out of scope.** Creative testing, keyword bidding, frequency caps, geo-level mix (that is project 03), customer-level scoring (that is project 02).

---

## Questions

1. If we cut television by $10k/week, how much branded search intent and net revenue do we lose over the adstock horizon?
2. How much of paid search’s last-touch revenue is harvest of demand that upper-funnel already created?
3. Where is each channel on its Hill curve, and what is the next-dollar total return (direct plus through intent)?
4. Does a price or promo week look like a media win if we omit those controls?
5. Is the holdout fit strong enough that Sequential Least Squares Programming should ship, watch, or kill the recommendation?

---

## Approach we selected (and why)

| Approach | Why we did not stop there |
|---|---|
| Last-touch / multi-touch rules | Credits harvest. Cannot answer a spend cut. |
| Ordinary least squares of sales on spend | Search is endogenous with demand. Coefficients steal television. |
| Black-box AutoML on the mart | No structural intent `M`, no mROI, no constrained optimizer finance will sign. |
| Full Bayesian media mix | Right later; heavier than the funnel identification story we need weekly. |
| **Funnel 2SLS + SLSQP** | **Selected.** Stage 1: media → branded search intent `M`. Stage 2: intent + harvest → sales `Y`. Then optimize `B`. |

Why this stack:

- The business process is two-step: people search for X, then they convert. A one-equation sales model cannot represent that.
- Two-stage least squares instruments intent so harvest channels do not eat upper-funnel coefficients.
- Geometric or Weibull adstock and Hill saturation are the minimum shapes finance already debates (memory and diminishing returns).
- Sequential Least Squares Programming respects the same weekly envelope and channel floors/caps the media team already uses.
- The studio can recover known data-generating-process truth, so a stakeholder can see identification fail when we omit a control or flatten television flighting.

---

## Mathematical model (short)

```
Adstock:     A_c,t = spend_c,t + λ_c A_c,t−1          (or Weibull)
Hill:        H(A) = A^s / (A^s + K^s)
Stage 1:     M_t = α' H(A_TOFU/MOFU) + controls + u
Stage 2:     Y_t = β_M M̂_t + β' H(A_BOFU) + controls + e
mROI_c:      chain-rule dY/d spend_c  (direct plus through M)
SLSQP:       max predicted Y  s.t.  Σ spend = B,  lo_c ≤ spend_c ≤ hi_c
```

`M` is organic branded search (not paid clicks). Top-of-funnel spend is assumed to move sales only through `M`. Bottom-of-funnel has no alpha path.

**Lab gate.** Chronological 80/20 holdout: R² ≥ 0.45 and MAPE ≤ 8% before a mix recommendation is allowed to ship.

---

## Assumptions

- **Grain.** One Canada week. Ship-week net revenue is what operations books.
- **Exclusion.** Top-of-funnel spend moves sales only through intent `M`.
- **Transforms.** Adstock is a known decay. Hill `K` is a saturation location, not a budget cap.
- **Controls.** Price, promo depth, holiday, payday, stockout, and share of voice are not channels. Omit them and media steals their weeks.
- **Budget.** The optimizer cannot invent money. Sum of recommended spend equals `B` inside bounds.
- **Transfer.** Synthetic data in the lab uses the same equations as production. Production only changes the warehouse feed.

---

## Data engineering

Nothing raw from an ads API enters 2SLS. Campaign ids die in silver via `dim_channel`.

- **Bronze.** Ads platforms, Google Search Console, order ledger, promo, ops, macro.
- **Silver.** Spend rolled to parent channel; ship-week boxes; branded clicks as `M`.
- **Gold.** `mart_mmm_weekly` — one row per Canada week with spend columns, `M`, `Y`, and controls.

Field dictionary and keep/roll/drop rules live on `/mmm#tab-playbook` (do not split `index.html`; hashes depend on it).

---

## Development pages (under this project)

Attribution (last-touch vs incremental), trade-spend forecast, pricing, scenarios, bootstrap uncertainty, and demand-trend diagnostics stay here. They support the mix decision; they do not replace it.

---

## Production (Azure)

Canada Central. Azure Data Lake Storage Generation 2, Azure Data Factory, Microsoft Fabric / warehouse, Azure Container Apps Job. Monday parent is fail-closed: if holdout MAPE or R² miss the gate, last week’s mix stays. This job does not write the CLV mart (project 02, Sunday) or the causal treatment file (project 03, Amazon Web Services).

---

## Layout

```
problem/              problem statement page
data_engineering/     warehouse contract
development/          engines + studio templates (mix, attribution, forecast, …)
production/           Azure runbook page
```

---

## What would change the choice

If finance requires geo incremental return, do not stretch this national mart — open project 03. If the question is which households are worth a win-back, open project 02. If holdout MAPE stays above the lab gate after controls and flighting are honest, watch or kill the mix; do not ship SLSQP.
