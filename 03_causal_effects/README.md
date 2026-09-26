# Project 03 — Causal effects (multi-problem suite)

**Question.** A national mix model can be right on average and still be wrong about a launch, a price, an offer, or a site test. Which estimator matches *this* design — and is the number incremental?

**Company.** X Canada is a weekly meal-kit subscription (same economics as HelloFresh). Hard problems are not “did the dashboard go up.” They are: extra YouTube in metros that were already growing; list price raised in January; a 40% win-back redeemed by people who still open the app; a national New Year flight with no holdout; a homepage that stacks “$4.99 a serving” with free first delivery. Those are twelve different designs. One estimator cannot cover them.

**Production cloud.** Amazon Web Services, `ca-central-1`. Isolated from the Azure mix-model and CLV marts.  
**Grain.** Depends on the test: geo × week, national week, household, or session.

Live (from the studio root: `python run_webapp.py`):

| Stage | URL |
|---|---|
| Problem | `/causal/problem` |
| Data engineering | `/causal/data-engineering` |
| Development (geo story) | `/causal` |
| **12-method suite** | `/causal/suite` |
| Production | `/causal/production` |
| Lab test | `/` card 03 |

---

## Problem

Commercial teams roll extra YouTube into the fastest first-box metros. Pricing harvests New Year demand. CRM mails 40% off to cancels who were coming back. Brand runs a national resolution flight with no control metro. The same 50% stay offer helps skippers and wastes margin on weekly loyalists.

Each of those is a *different* causal problem. This project states twelve of them, each with units, a naive trap, a mathematical estimator, and a test you can run. In the lab the true effect is known, so we score bias instead of arguing from narrative.

**Decision this model is allowed to change.** Whether a first-box YouTube burst, price-per-serving hike, Ontario TV flight, 40% win-back, New Year package, pause-save, or $4.99 homepage is called incremental; who gets the next discount; and whether an observational readout is allowed in the finance pack at all.

**Out of scope.** National weekly budget optimization (project 01). Customer lifetime scores (project 02). Creative tests at 200 geos, CUPED, continuous dose-response, rewriting the treatment file after lock.

---

## Why a suite, not one estimator

| Approach | Why we did not stop there |
|---|---|
| Treated-only pre/post | Confounds growth, season, and treatment. The usual “it worked” slide. |
| National mix-model coefficient | Wrong grain. Cannot see who was treated. |
| Matching on last week’s sales | Does not fix diverging pre-trends. Still observational. |
| One favourite estimator for every brief | DiD does not identify a single-province flight; IPW does not identify a national TV week. |
| **One problem per estimator, each with a planted truth** | **Selected.** Stakeholders see why the number moved. |

The failure mode is usually **selection**, not lack of a fancy model. We show the naive number and the better number on one card.

---

## The twelve tests (meal-kit problems)

Each card on `/causal/suite` has: situation, decision, units, naive trap, success, math, and a plain-language read after you run it.

| # | Estimator | Real problem | Naive trap | Planted truth / gate |
|---|---|---|---|---|
| 1 | Difference-in-differences | Extra YouTube in the five fastest first-box metros | Treated-only pre/post credits January growth you selected on | ~10% multiplicative lift; DiD closer than naive |
| 2 | Instrumental variables (2SLS) | Everyday price-per-serving raised when January demand is already high | OLS of boxes on price looks flat | Causal slope ~ −1.20; first-stage F > 10 |
| 3 | Synthetic control | Ontario-only brand TV before a second-province rollout | Ontario pre/post counts Ontario’s own trend | Post gap ~ +18 first boxes vs donor twin |
| 4 | Inverse probability weighting | Win-back: 40% off the next two boxes | Redeemer vs non-redeemer mixes selection | ATE ~ +4.5 extra boxes on the mailed file |
| 5 | Time-series causal impact | National New Year flight, no holdout geo | Post − pre includes the resolution spike | Forecast gap ~ +12 first boxes |
| 6 | Double machine learning | Pause-to-skip / 50% stay with a wide CRM file | Raw gap or brittle OLS+X | ATE ~ +3.0 after residual-on-residual |
| 7 | Meta-learners (S / T / X) | Who should get the 50% stay offer | One average says mail everyone | High vs low CATE gap ~ 3; low PEHE |
| 8 | A/B and 2×2 factorial | Homepage: $4.99/serving × free first delivery | Two sequential A/Bs miss the combination | Mains ~ 3 and 5; interaction ~ 1.2 |
| 9 | Bootstrap | Checkout meal-picker lift of +2.4 | Treat the first week’s point as exact | 90% interval covers 2.4 and excludes 0 |
| 10 | t-test and ANOVA | Did the $4.99 badge move conversion? | p < 0.05 is not “the badge is worth the margin” | Both nulls reject when effects are real |
| 11 | Uncertainty (two 90% CIs) | Reactivation SMS +1.8 | Ship on the narrower interval | Both intervals exclude 0 and cover truth |
| 12 | TARNet-style deep CATE | First-box discount when lift is not a straight line | Assume linear CATE, or assume “deep is better” | Neural PEHE < linear PEHE |

---

## Mathematical models (one line each)

```
DiD:     τ = (Y_t,post / Y_t,pre) / (Y_c,post / Y_c,pre) − 1
IV:      Price = π0 + π1 Z + v;   Y = α + τ Pricê + e
SC:      min_w ||Y_1,pre − Σ w_j Y_j,pre||² ,  w≥0, 1'w=1
IPW:     E[D Y / e(X)] − E[(1−D) Y / (1−e(X))]
ITS:     Y_t = b0 + b1 t + season;   τ = mean_post (Y − Ŷ)
DML:     Y_res = Y − ĝ(X),  D_res = D − m̂(X),  τ from Y_res ~ D_res
CATE:    τ(x) = E[Y(1)−Y(0)|X=x];  PEHE = √E[(τ̂−τ)²]
2×2:     Y = μ + τ_A A + τ_B B + τ_AB A B + e
Boot:    CI_90 = [q0.05, q0.95] of resampled ATEs
t / F:   H0: equal means;  reject at 5% is not effect size
Unc.:    ship iff both 90% lower bounds > 0 and both cover truth
TARNet:  τ̂(x) = MLP_1(x) − MLP_0(x)
```

---

## Assumptions (shared)

- **Stable unit treatment.** Treating Toronto does not spill demand into a control FSA through ads or fulfillment.
- **Locked assignment.** After `lock_ts`, a geo cannot move from control to treated in gold. Rewrites are audit events on Amazon Simple Storage Service versioning.
- **Parallel trends (for DiD).** Required on the observational design; we do not assume it. The randomized design is what makes it plausible.
- **Outcome.** Ship-week net boxes or revenue, same spirit as mix-model `Y`, never Google conversion value.
- **One treatment per test.** On/off or a 2-by-2, not a continuous bid or five stacked tactics on the same row.
- **Label the design.** Missing randomization log means the row stays observational. The pack title must say so.

---

## Data engineering

- **Sources.** Geo-week boxes, locked treatment file (who, when, observational vs randomized), CRM take-up and covariates, site assignment logs.
- **Gold.** `mart_causal_geo_week` plus per-method tables. The treatment file is versioned and locked.
- **Fail closed.** Changing treatment after lock; writing into the Azure mix-model or CLV marts; labeling an observational readout as a trial.

---

## Production (Amazon Web Services)

Region `ca-central-1`. Amazon Simple Storage Service for bronze/gold, AWS Glue for the panel, Amazon Redshift or Athena for the mart, Amazon Elastic Container Service for the suite job. This landing zone cannot overwrite Azure `mart_mmm_weekly` or `mart_clv_customer`. If the randomization log is missing, the pack title stays “observational.”

---

## Layout

```
problem/              project problem + all 12 statements
data_engineering/     geo-week and treatment contract
development/          causal.py (geo story) + causal_suite.py (12 methods)
production/           AWS runbook page
```

---

## How to test

On `/causal/suite`, set the seed (42 is the default) and click **Run this test** or **Run all 12**. Each card prints PASS/FAIL and a plain-language read (estimate vs planted truth). The original geo DiD vs observational vs RCT story remains on `/causal`.

---

## What would change the choice

If we have one large treated province and many donors, add synthetic control — do not delete DiD. If units interfere (national television leaking into control geos), redesign the experiment; do not “fix it” in ordinary least squares. Mix-model budget questions stay on Azure in project 01. Lifetime scores stay on Azure in project 02.
