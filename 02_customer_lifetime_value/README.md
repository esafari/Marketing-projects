# Project 02 — Customer lifetime value

This README is the studio HTML, written as markdown: problem, assumptions, methods, customers, segments, data engineering, and Azure production.

X Canada is a weekly meal-kit subscription (HelloFresh-class). Grain is one household at snapshot Saturday. Production is Azure (Sunday job, separate from the mix-model Monday parent).

Run from the repo root: `python run_webapp.py` → http://127.0.0.1:5050/clv


---

# Page: clv data engineering

Source: `projects/02_customer_lifetime_value/data_engineering/templates/clv_data_engineering.html`

### CLV data engineering Sources

X subscription ledger (household key, ship timestamp, net CAD paid, skip flag, pause flag, cancel flag, plan size 2 vs 4, first-box promo flag), acquisition campaign → first-touch channel (television, YouTube, referral, social, paid search), and a hashed customer identifier. Email never leaves bronze.

### Bronze → silver → gold

Bronze: raw boxes, skips, and a slowly changing household dim. Silver: one event per kept box (net CAD) plus skip events with amount zero; first-box rows tagged. Gold: mart_clv_customer at Saturday T — recency, repeat frequency, continuing AOV, skip rate, plan size, first-box discount, first-touch channel, tenure. Holdout boxes after T stay in a sealed table.

### Tests that fail the week closed

No future boxes in snapshot features. Frequency counts shipped boxes, not clicks or skips. First-box net paid is not the Gamma-Gamma AOV. Acquisition is first-touch, not last click or the coupon on box one. Duplicate household keys fail. Continuing margin is the finance 32% planning rate, not a Google value.

## Contract the development engine is allowed to see

| Mart column | Meaning | Used for |
| --- | --- | --- |
| customer_key | Surrogate, not email | Join only |
| recency_weeks, frequency, monetary | RFM at snapshot T. Frequency is repeat shipped boxes. | BG/NBD + Ridge |
| aov_continuing | Mean net CAD on boxes after the first | Gamma-Gamma. First-box promo is excluded. |
| plan_size, skip_rate, first_box_discount | 2 vs 4 person; skips / eligible weeks; first-box off list | Ridge features; segment story |
| acq_channel | First media: TV, YouTube, Referral, Social, Paid Search | Ridge; harvest test vs mix model |
| holdout_value | Net paid in (T, T+h] | Test only — not a fit feature |

Problem statement Development — BG/NBD studio Production on Azure Mix-model warehouse (different grain)

---

# Page: clv

Source: `projects/02_customer_lifetime_value/development/templates/clv.html`

CLV overview BG/NBD for P(alive) and expected future boxes, Gamma-Gamma for expected continuing-box AOV (first-box discount excluded), times 32% continuing contribution. Ridge is fit out-of-fold on RFM plus plan size, skip rate, first-box discount, and first-touch channel so it cannot use that household’s own future boxes.

Click Run CLV (1,800 households, snapshot 130, 26-week horizon, 32% continuing margin). Pass if blend rank tracks sealed holdout margin (Spearman ≥ 0.25), referral/TV mean CLV sits above paid search, and family plans beat 2-person. Do not pass on P(alive) alone — a new first-box buyer can look alive and still be low value.

Everyone still alive: snapshot is too early. Ridge crushes BG/NBD: holdout leaked into RFM. Search is the high-CLV tier: we scored first-box discount as if it were continuing AOV, or last-click leaked. Search P(alive) above TV is possible (short tenure after box one) — rank on blend CLV, not on alive. Diagnose on Customers and Segments before you change the mix model.

Customers Snapshot week Horizon weeks Continuing margin Seed Run CLV models

### Predicted CLV distribution

Blend score (65% BG/NBD × Gamma-Gamma, 35% Ridge) over the horizon, in contribution-margin dollars. A long right tail is normal: a few champions carry a large share of value.

### Predicted vs holdout margin

Each point is a customer. The x-axis is the blend CLV. The y-axis is actual contribution margin in the weeks after the snapshot. Rank correlation matters more than a tight 45-degree line.

### Mean CLV by acquisition channel

Referral and TV should sit above YouTube above Social above Paid Search. That is the meal-kit harvest story: search sells the cheap first box; brand and friends sell households that still ship after week 4.

### Holdout lift by predicted decile

Decile 10 is the top 10% by predicted CLV. Lift is their mean future spend versus the average customer. A monotone staircase means the ranking is usable for CRM.

Customer-level rows are on CLV customers. Segment charts are on CLV segments. Formulas are on CLV methods.

---

# Page: clv customers

Source: `projects/02_customer_lifetime_value/development/templates/clv_customers.html`

CLV customers Search id / channel Funnel All TOFU MOFU BOFU Value tier All High Medium Low

### Ranked customers

Holdout $ is actual post-snapshot spend (not yet multiplied by margin). Blend CLV is expected contribution margin over the horizon.

---

# Page: clv methods

Source: `projects/02_customer_lifetime_value/development/templates/clv_methods.html`

CLV methods Pipeline Customer DGP RFM BG/NBD Gamma-Gamma CLV formula Ridge Validation Production

## Solving approach

- Simulate (or ingest) a purchase log: customer, week, amount, acquisition channel, funnel.
- Cut at a snapshot week. Everything before the cut is history. Everything after is holdout.
- Build RFM: frequency = repeat orders, recency = time of last purchase since first, T = age, AOV, monetary.
- Fit BG/NBD by maximum likelihood on (frequency, recency, T). That gives P(alive) and expected future orders.
- Fit Gamma-Gamma by MLE on customers with at least one repeat purchase. That gives expected AOV.
- CLV_prob = E[orders in horizon] × E[AOV] × margin.
- Fit Ridge on RFM + channel + P(alive) to holdout margin, with 5-fold out-of-fold predictions.
- Blend = 0.65 × CLV_prob + 0.35 × CLV_ridge. Rank, segment, and score holdout lift.

## Meal-kit data-generating process

Each household is acquired by TV, YouTube, Referral, Social, or Paid Search. They pick a 2-person (~CAD 79) or family (~CAD 139) plan. The first box always ships at a deep discount. Then each week they skip, take a continuing box, or lapse. Paid search has the steepest promo cliff (about half never take box two).

| Channel | Funnel | First-box off | No 2nd box | Weekly skip | Weekly lapse | Family share |
| --- | --- | --- | --- | --- | --- | --- |
| Referral | TOFU | 25% | 14% | 9% | 2.2% | 62% |
| TV | TOFU | 40% | 22% | 11% | 2.8% | 58% |
| YouTube | TOFU | 45% | 26% | 13% | 3.2% | 50% |
| Social | MOFU | 50% | 38% | 18% | 4.5% | 38% |
| Paid Search | BOFU | 60% | 52% | 22% | 5.5% | 28% |

```
plan_i = 4-person with probability family_p_channel, else 2-person
list_i ≈ $79 (2p) or $139 (family), lognormal noise 8%
first box always ships at list_i × (1 − first_disc_channel)
with probability early_churn_channel: stop (one-and-done)
else each later week:
  lapse with hazard dropout_week × 1.35 if fewer than 4 boxes
  else skip with probability skip_i
  else ship continuing box at list_i × (1 − small loyalty promo)

Gamma-Gamma AOV uses continuing boxes only.
CLV_prob = E[future boxes] × E[continuing AOV] × 0.32
First-box contribution is planned at 6% and is not the rank object.
```

## RFM at the snapshot

```
x_i  = frequency = (# orders in (0, T]) − 1     # repeat buys
t_x  = recency   = time of last order − first order
T_i  = age       = snapshot − acquire week
m_i  = AOV       = mean order value
M_i  = monetary  = sum of order values
```
BG/NBD needs x, t_x, T. Gamma-Gamma needs x and m for customers with x ≥ 1. One-time buyers still get a P(alive) and the population mean AOV.

## BG/NBD (Fader, Hardie, Lee 2005)

Purchase rate λ ~ Gamma(r, α). Dropout probability p ~ Beta(a, b), independent of λ. After each purchase the customer leaves with probability p, otherwise waits Exp(λ) for the next order.

```
Likelihood for customer i (x, t_x, T):

A1 = ln Γ(r+x) − ln Γ(r) + r ln α
A2 = ln Γ(a+b) + ln Γ(b+x) − ln Γ(b) − ln Γ(a+b+x)
A3 = −(r+x) ln(α + T)
A4 = ln a − ln(b+x−1) − (r+x) ln(α + t_x)     if x > 0

ℓ_i = A1 + A2 + A3                 if x = 0
ℓ_i = A1 + A2 + log(e^{A3} + e^{A4})   if x > 0

(r, α, a, b) = arg max Σ ℓ_i
  with a > 1 so expected-purchase formulas stay finite.
```

### P(alive) and expected future orders

```
P(alive | x, t_x, T) = 1 / (
    1 + [a / (b + x)] * [(α + T)/(α + t_x)]^{r+x}
)

E[X*(t) | x, t_x, T] = P(alive)
  * (a + b + x − 1) / (a − 1)
  * ( 1 − [(α+T)/(α+T+t)]^{r+x}
        * ₂F₁(r+x, b+x; a+b+x−1; t/(α+T+t)) )
```
t is the horizon in weeks (26 on the default run). ₂F₁ is the Gaussian hypergeometric function.

## Gamma-Gamma spend model

Order values are independent of the arrival process. Customer mean spend heterogeneity is Gamma. We use the sufficient-stat likelihood on (x, m).

```
ℓ(p, q, ν | m, x) =
    ln Γ(p x + q) − ln Γ(p x) − ln Γ(q)
  + q ln ν + (p x − 1) ln m + p x ln x
  − (p x + q) ln(x m + ν)

E[M | m, x] = [(q − 1) / (p x + q − 1)] * (ν/p + x m)
  for x ≥ 1

E[M] population = ν p / (q − 1)
  for one-time buyers (x = 0)
```
Need q > 1 so the mean exists. Amounts are assumed independent of frequency — if high-frequency buyers systematically have smaller baskets, check that residual before shipping.

## CLV formulas used on these pages

```
CLV_prob,i = E[X*(H) | x_i, t_x,i, T_i] * E[M_i] * margin

CLV_ridge,i = max(0, x_i' β̂)     # OOF prediction of holdout * margin

CLV_blend,i = 0.65 CLV_prob,i + 0.35 CLV_ridge,i

Value tier: High = top 20% of blend, Medium = next 40%, Low = bottom 40%
```
Default continuing-box margin is 0.32 (variable contribution after food and last-mile, not revenue and not first-box promo). Change it on the overview page. First-box contribution is planned at 6% and is not the rank object. Heuristic CLV is (x / T) × continuing AOV × H × P(alive) × margin — a sanity check only.

## Ridge (second model)

```
y_i = holdout spend_i × margin

features = [x, t_x, T, monetary, AOV, continuing AOV, discount rate, return rate,
            P(alive), skip rate, plan size, first-box discount, n skips,
            funnel dummies, channel dummies]

z = StandardScaler(features)
β̂ = arg min_β  Σ (y − zβ)² + 2.5 ||β||²

Predictions on the site are 5-fold out-of-fold:
  each customer is scored by a model that did not see that customer's y.
```
Ridge is there to pick up return rate and promo depth that BG/NBD ignores. It is not a substitute for the probabilistic model on new customers with short history.

## How we know the scores are usable

| Metric | What it is | How to read it |
| --- | --- | --- |
| Spearman vs holdout margin | Rank correlation | >0.4 is useful for ranking CRM; >0.6 is strong on this DGP |
| Holdout R² | Variance of future margin explained by blend | Level accuracy; often weaker than rank |
| MAPE on buyers who spent | Percent miss among customers with holdout > $1 | Inflated by small tickets; use with lift |
| Decile lift | Mean holdout in decile k / overall mean | Must be monotone. Top-decile lift of 2–4× is the CRM test |
| Ridge fold R² | Mean test R² across 5 folds | If this is high and Spearman is not, the model is fitting levels not ranks |

## How to estimate this on real customers

- Build a purchase fact at order grain: customer_id, order_ts, net_amount, channel of first click or first-touch campaign, returns flag.
- Choose a snapshot (e.g. last Sunday) and a horizon that matches your CRM cycle (13 or 26 weeks).
- Exclude wholesale, employees, and gift-card redemptions. Use net of returns for amounts.
- Fit BG/NBD and Gamma-Gamma on customers with T ≥ 8 weeks. Grid a mild penalizer if a, b wander.
- Calibrate predicted spend to a later holdout quarter. If Gamma-Gamma overstates AOV for Search, add a channel intercept to E[M].
- Do not use last-click revenue as the CLV target. Do not score CLV on the same window used to fit without OOF or a time cut.
- Join to MMM: expected new-buyer CLV by acquisition channel × expected new buyers from the funnel mix. That is how a TV dollar can be worth more than its short-run MMM sale.
The MMM page answers “what did media do to this week’s sales?” This CLV stack answers “which buyers did that media create, and what are they worth next half-year?” Both are needed before you starve TOFU.

---

# Page: clv segments

Source: `projects/02_customer_lifetime_value/development/templates/clv_segments.html`

CLV segments

### Total CLV by funnel

Sum of predicted horizon margin. MOFU often wins on headcount. TOFU should win on value per buyer.

### Value-tier mix

High-CLV customers are few. If Search dominates Low, the acquisition mix is buying cheap buyers, not valuable ones.

### RFM segments

Champions: high frequency and recent. At risk: used to buy, recency has gone cold. Hibernating: one-and-done and likely dead.

### P(alive) vs recency

BG/NBD drops the alive probability as the last purchase recedes, faster when historical frequency was low. That is the dropout process.

### By acquisition channel

### By RFM segment

---

# Page: clv problem

Source: `projects/02_customer_lifetime_value/problem/templates/clv_problem.html`

## CLV problem statement Company setting

Think HelloFresh, Goodfood, or Factor in Canada. A customer is a household on a weekly plan. They pick meals, skip a week when they travel, pause for a month, or cancel. Revenue is ship-week net paid in Canadian dollars — the box that left the fulfillment centre — not a click and not Google conversion value. The first box is sold at a deep discount. Most of the money, and almost all of the contribution margin, is in boxes two through N. Paid search and affiliates are very good at selling box one. Television, YouTube, and friend-referral are better at selling someone who is still taking a box in week 12.

## Problem

Growth reports a cheap first-box CAC from branded search. Finance sees last-touch revenue that makes search look like the best channel. Lifecycle wants to know who is still “alive” (will take a future box), what they will pay after the promo ends, and whether search-acquired subscribers look valuable only because last-click harvested someone who already wanted the brand after TV. A first-box-heavy discount also makes new cohorts look cheap to acquire and weak on lifetime value. We need a customer-level expected contribution margin over a fixed horizon (default 26 weeks) that can be segmented by first-touch channel and by plan size (2-person vs family).

## Scope

### In scope

One row per subscriber at snapshot T. Recency, frequency (repeat boxes), continuing-box average order value, tenure, skip rate, plan size, first-box discount, first-touch channel. Probability alive, expected future boxes, expected continuing AOV, times finance continuing margin. Holdout net paid in (T, T+h] used only to test ranks. Azure production scores the base weekly after Saturday’s ledger lands.

### Out of scope

National weekly media mix (project 01). Geo experiments (project 03). Next-best recipe, individual list prices, sending raw email files to an agency. Media CAC payback as the CLV number (CAC stays in the mix-model pack). Real-time session scoring. Infinity-horizon “lifetime.”

### Decision this model is allowed to change

Win-back depth (40% off next two boxes vs a skip reminder), welcome-series investment, whether search-heavy acquisition is treated as high lifetime value or as harvest of first-box hunters, and whether family-plan champions get a different save offer than 2-person promo buyers.

## Questions

- What is the expected contribution margin of each active subscriber over the next h weeks (default 26)?
- What is P(alive) at the snapshot — and does a recently acquired first-box buyer look “alive” only because tenure is short?
- After the first-box discount ends, who still takes a second, fourth, and twelfth box?
- Does a simple RFM sort already rank the holdout, or does BG/NBD plus continuing-box Gamma-Gamma plus leak-safe Ridge add rank correlation?
- Is mean CLV by first-touch channel telling the same harvest story as last-touch media mix? (Search should be low value, referral and TV high.)
- Do family plans (4-person) carry more horizon margin than 2-person plans after we account for skip and dropout?
- If last week’s sealed-holdout Spearman drops, do we keep last week’s scores or fail the job closed?

## Approaches we considered

| Approach | What it does | Why we did not stop there |
| --- | --- | --- |
| Historic average spend × remaining tenure | One number per segment. | Ignores dropout and skip. Treats a lapsed first-box hunter like a weekly family plan. |
| RFM quintiles only | Recency / frequency / monetary ranks. | Good baseline. No P(alive), no continuing AOV, easy to leak holdout if you compute RFM after T. |
| Contractual survival on cancel date | Kaplan–Meier until the customer hits cancel. | Meal-kit “alive” is latent. People skip, then return, or silently lapse without cancelling. Cancel-date survival overstates the base. |
| Revenue × 35% on all boxes including first | Simple margin. | First-box contribution is near zero after the promo. Using list or first-box net paid as AOV makes search look like a small-basket shopper instead of a promo hunter. |
| Gradient boosting on everything including future boxes | High in-sample R². | Leaks the answer. Production would look brilliant and then fail on new Saturdays. |
| BG/NBD + Gamma-Gamma on continuing AOV + out-of-fold Ridge | Repeat-buy and dropout, then continuing-box value, then a ranker that cannot see that subscriber’s future. | Selected. Standard non-contractual CLV, plus meal-kit features (skip, plan, first-box discount) on a leak-safe score. |

## Why we selected this approach

- X Canada is non-contractual in practice: skips and silent churn, not only a cancel flag. That is a buy-till-you-die setting, not a mobile-phone contract.
- BG/NBD separates “how often they take a box while alive” from “whether they dropped out after the promo.”
- Gamma-Gamma is fit on continuing-box AOV so the first-box 40–60% discount does not look like a permanently small household.
- Out-of-fold Ridge on RFM plus plan size, skip rate, first-box discount, and first-touch channel is the piece CRM can sort on without using that person’s post-snapshot boxes.
- First-touch channel as a feature lets us test the harvest hypothesis at customer grain, which the mix model cannot see.

## Realistic assumptions (HelloFresh-class)

These are planning assumptions for the lab and for a Canadian meal-kit P&L conversation. They are not a HelloFresh filing. Change the continuing margin on the development page; the rest are locked in the data-generating process so a reviewer can see what we claimed.

| Assumption | Planning value | Why we use it |
| --- | --- | --- |
| Currency | Canadian dollars, ship-week net paid | Same Y spirit as the mix model. Never Google conversion value or list price before promo. |
| 2-person plan list | About $79 per continuing box (3 recipes) | Typical Canadian 2-person weekly kit after a realistic menu mix. Not the advertised $4.99 first-box serving. |
| Family plan list | About $139 per continuing box (4-person) | Family plans are the AOV story. About 28–62% of a channel’s new customers, highest on referral and TV. |
| First-box discount | About 25% referral, 40% TV, 45% YouTube, 50% social, 60% paid search | Acquisition sells box one. Search and social are deepest. Friend-get-friend is shallowest. |
| First-box contribution | 6% of first-box net paid | Food, packaging, and last-mile eat the promo. Box one is often a customer-acquisition cost, not a profit centre. We do not subtract media CAC here — that is project 01. |
| Continuing contribution | 32% of continuing net paid (slider on the studio) | Variable margin after food and fulfillment, before overhead and media. A finance planning rate, not the year-end close. |
| Promo cliff | About 14% (referral) to 52% (paid search) never take a second box | The usual HelloFresh-class loss after the discount ends. Frequency = 0 means first-box-only, not a broken key. |
| Weekly skip | About 9–22% of eligible weeks, higher on search | Skip is not death. BG/NBD must see a gap in purchases without treating the household as cancelled. |
| Weekly lapse after box 2 | About 2.2–5.5% per week, higher in the first four boxes | Early tenure is fragile. Hazard falls once the household has taken four boxes (habit). |
| Recipe credit / return | About 2–2.5% of boxes | Meal kits rarely “return.” We keep a small credit rate so Ridge can see quality issues without pretending this is apparel. |
| Horizon | 26 weeks (two CRM quarters) | Welcome series and win-back are quarterly. Infinity-horizon CLV cannot be compared to a campaign cost. |
| Calendar | 156 weeks of history, snapshot at week 130 | Enough tenure for BG/NBD; 26 weeks sealed after T for the rank test. |
| Independence | One surrogate key, one household | Two emails in one kitchen inflate frequency. We do not split or merge households in v1. |
| First-touch channel | TV, YouTube, Referral, Social, Paid Search | Collapsed to the same TOFU / MOFU / BOFU language as the mix model. Not last click, not the coupon code on box one. |
| Gamma-Gamma | Continuing AOV ⊥ frequency / customer | If family plans both ship every week and have larger boxes in a forbidden way, AOV residuals will show it. First-box net paid is excluded from the spend model. |
| P(alive) vs value | A new first-box buyer can have a high P(alive) and a low CLV | Short tenure makes BG/NBD think they are still in play. Expected future boxes and continuing AOV are small. Rank on blend CLV, not on P(alive) alone. |
| Holdout sealed | No ship-week after T in features | If Spearman is brilliant and Ridge crushs BG/NBD, we leaked. Production fails closed if last sealed Spearman drops. |

## What success looks like on a run

- Holdout Spearman of blend CLV vs sealed future margin ≥ 0.25 (lab gate). On this meal-kit DGP, 0.5+ is typical.
- Mean CLV: Referral and TV above YouTube above Social above Paid Search.
- Family plans above 2-person plans on mean horizon margin.
- A long right tail: a few weekly family champions carry a large share of portfolio CLV.
- Decile lift monotone. Top decile 2–4× the average household.
- If Search is the high-CLV tier, the snapshot leaked last-click or we scored first-box discount as if it were continuing AOV.

## What would change the choice

If almost every subscriber has a contractual renew date and silent churn disappears, we would switch to a contractual survival model. If holdout Spearman stays near zero after we fix leakage, we do not put deciles into CRM. If first-box margin becomes a finance-owned number (promo fund), we take it from the ledger instead of the 6% planning rate. Media mix questions stay in project 01; we do not add weekly spend columns to this mart to “explain” CLV.

Run the test on the lab Data engineering Development Methods and formulas Production — Azure

---

# Page: clv production

Source: `projects/02_customer_lifetime_value/production/templates/clv_production.html`

### CLV production — Azure Landing zone

Resource group rg-x-clv-prod next to the mix-model groups, not inside them. Lake folders bronze/x_orders/, bronze/x_customers/, gold/mart_clv_customer/. Shared Key Vault can hold the ledger secret; the managed identity for this job cannot read mix-model allocation tables.

### Weekly score job

Azure Data Factory pipeline pl_x_clv_week Sunday 07:00 America/Toronto. Data build tool builds the snapshot at last Saturday. Azure Container Apps Job runs BG/NBD, Gamma-Gamma, and out-of-fold Ridge. Writes gold.clv_scores and gold.clv_run_log (snapshot date, MAPE vs last sealed holdout).

### What ships

Image x-clv:{git-commit}. Power BI segment view for lifecycle marketing. CRM export is a hashed key plus decile, not a raw email file. If holdout rank correlation drops, the job fails closed and keeps last week’s scores.

## Azure services in this project

| Service | Role |
| --- | --- |
| Azure Data Lake Storage Generation 2 | Customer and order bronze, CLV gold |
| Azure Data Factory | Ledger copy and Sunday parent |
| Microsoft Fabric Warehouse | mart_clv_customer, sealed holdout |
| Azure Container Apps Job | BG/NBD + Gamma-Gamma + Ridge score |
| Azure Container Apps | CLV studio pages, gold read-only |
| Power BI | Deciles and acquisition-channel segments |

Data engineering contract Development CLV methods
