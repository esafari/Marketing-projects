# Project 02 — Customer lifetime value

**Question.** What is a meal-kit subscriber worth over the next two quarters — and did we buy a first box or a customer?

**Company.** X Canada is a weekly meal-kit subscription (same economics as HelloFresh, Goodfood, or Factor). A household picks meals, skips a week, pauses, or cancels. Revenue is **ship-week net paid in Canadian dollars**. The first box is sold cheap. Most contribution margin is in boxes two through N. Paid search is good at selling box one. Television, YouTube, and referral are better at selling someone still taking a box in week 12.

**Production cloud.** Azure, Canada Central (separate resource group and Sunday job from the mix-model Monday parent).  
**Grain.** One row per household at snapshot Saturday `T`. Holdout boxes in `(T, T+h]` are sealed and are not fit features.

Live (from the studio root: `python run_webapp.py`):

| Stage | URL |
|---|---|
| Problem | `/clv/problem` |
| Data engineering | `/clv/data-engineering` |
| Development | `/clv` · `/clv/customers` · `/clv/segments` · `/clv/methods` |
| Production | `/clv/production` |
| Lab test | `/` card 02 |

---

## Problem

Growth reports a cheap first-box CAC from branded search. Finance sees last-touch revenue that makes search look best. Lifecycle needs to know who is still “alive” (will take a future box), what they will pay after the promo ends, and whether search-acquired subscribers look valuable only because last-click harvested someone who already wanted the brand after TV.

We score **expected contribution margin** over a fixed horizon (default 26 weeks), segmented by first-touch channel and plan size (2-person vs family).

**Decision this model is allowed to change.** Win-back depth (40% off next two boxes vs a skip reminder), welcome-series investment, whether search-heavy acquisition is treated as high LTV or as harvest of first-box hunters, and whether family-plan champions get a different save offer than 2-person promo buyers.

**Out of scope.** National weekly mix (project 01). Geo experiments (project 03). Next-best recipe, individual list prices, raw email files to an agency, media CAC inside the CLV number, real-time session scoring, infinity-horizon “lifetime.”

---

## Questions

1. What is the expected contribution margin of each active subscriber over the next `h` weeks?
2. What is P(alive) at the snapshot — and does a new first-box buyer look “alive” only because tenure is short?
3. After the first-box discount ends, who still takes a second, fourth, and twelfth box?
4. Does RFM already rank the holdout, or do BG/NBD + continuing-box Gamma-Gamma + leak-safe Ridge add rank correlation?
5. Is mean CLV by first-touch the same harvest story as last-touch media mix? (Search should be low; referral and TV high.)
6. Do family plans carry more horizon margin than 2-person plans after skip and dropout?
7. If last week’s sealed-holdout Spearman drops, do we keep last week’s scores or fail the job closed?

---

## Approach we selected (and why)

| Approach | Why we did not stop there |
|---|---|
| Historic average × remaining tenure | Ignores dropout and skip. Treats a first-box hunter like a weekly family plan. |
| RFM quintiles only | No P(alive), no continuing AOV, easy to leak holdout. |
| Cancel-date Kaplan–Meier | Meal-kit “alive” is latent. Skip then return, or silent lapse without cancel. |
| Revenue × 35% on all boxes including first | First-box contribution is near zero after the promo. Search looks like a small basket instead of a promo hunter. |
| Boosting on future boxes | Leaks the answer. Looks brilliant in-sample and fails next Saturday. |
| **BG/NBD + Gamma-Gamma on continuing AOV + OOF Ridge** | **Selected.** Non-contractual CLV plus meal-kit features on a leak-safe ranker. |

Why this stack:

- X Canada is non-contractual: skips and silent churn, not only a cancel flag.
- BG/NBD separates “how often they take a box while alive” from “whether they dropped out after the promo.”
- Gamma-Gamma is fit on *continuing-box* AOV so a 40–60% first-box discount does not look like a permanently small household.
- Out-of-fold Ridge on RFM + plan size + skip rate + first-box discount + first-touch cannot see that household’s own future boxes.
- First-touch channel tests the harvest hypothesis at customer grain, which the mix model cannot see.

---

## Mathematical model (short)

```
x     = (# shipped boxes in (0, T]) − 1     # repeat boxes
t_x   = week of last box − week of first box
T     = snapshot − acquire week
m     = mean continuing-box net paid (first box excluded)

BG/NBD:     λ ~ Gamma(r, α),   p ~ Beta(a, b)
            P(alive | x, t_x, T),   E[future boxes over horizon h]
Gamma-Gamma: E[continuing AOV | m, x]
CLV_prob    = E[boxes] × E[continuing AOV] × 0.32
CLV_ridge   = OOF Ridge on RFM + plan + skip + first-box discount + channel
CLV_blend   = 0.65 CLV_prob + 0.35 CLV_ridge
```

**Lab gate.** Spearman rank correlation of blend CLV vs sealed holdout margin ≥ 0.25. On this meal-kit DGP, 0.5+ is typical. Rank on blend CLV, not on P(alive) alone — a new first-box buyer can look alive and still be low value.

---

## Realistic assumptions (HelloFresh-class)

These are planning values for the lab and a Canadian meal-kit P&L conversation. They are not a HelloFresh filing.

| Assumption | Planning value | Why |
|---|---|---|
| Currency | CAD, ship-week net paid | Same spirit as mix-model `Y`. Never Google conversion value. |
| 2-person list | ~$79 continuing box (3 recipes) | Typical Canadian 2-person kit. Not the advertised $4.99 first serving. |
| Family list | ~$139 continuing box (4-person) | Family plans drive AOV. Highest share on referral and TV. |
| First-box discount | ~25% referral → ~60% paid search | Acquisition sells box one. Search is deepest. |
| First-box contribution | 6% of first-box net paid | Food and last-mile eat the promo. Media CAC stays in project 01. |
| Continuing contribution | **32%** (slider on `/clv`) | Variable margin after food and fulfillment, before overhead. |
| Promo cliff | ~14% referral to ~52% search never take box two | Frequency = 0 means first-box-only, not a broken key. |
| Weekly skip | ~9–22% of eligible weeks | Skip is **not** churn. |
| Weekly lapse after box 2 | ~2.2–5.5%, higher in first four boxes | Early tenure is fragile; habit after four boxes. |
| Horizon | 26 weeks | Two CRM quarters. Not lifetime to infinity. |
| Calendar | 156 weeks, snapshot week 130 | Enough tenure; 26 weeks sealed for the rank test. |
| Independence | One surrogate key, one household | Two emails in one kitchen inflate frequency. |
| Channel | First-touch: TV, YouTube, Referral, Social, Paid Search | Not last click, not the coupon on box one. |

---

## What success looks like on a run

- Holdout Spearman ≥ 0.25 (lab). 0.5+ is typical here.
- Mean CLV: Referral and TV above YouTube above Social above Paid Search.
- Family plans above 2-person on mean horizon margin.
- Long right tail: a few weekly family champions carry a large share of portfolio CLV.
- Decile lift monotone; top decile about 2–4× the average household.
- If Search is the high-CLV tier, the snapshot leaked last-click or we scored first-box discount as continuing AOV.

---

## Data engineering

- **Sources.** Subscription ledger (household key, ship timestamp, net CAD, skip / pause / cancel, plan size, first-box promo flag), first-touch campaign map. Email never leaves bronze.
- **Bronze → silver → gold.** One event per kept box plus skip events (amount zero). Gold `mart_clv_customer` at Saturday `T`: recency, repeat frequency, continuing AOV, skip rate, plan size, first-box discount, first-touch, tenure.
- **Fail closed.** Future boxes in snapshot features, frequency counting clicks, first-box net paid used as Gamma-Gamma AOV, last-click as acquisition, duplicate household keys.

---

## Production (Azure)

Resource group `rg-x-clv-prod` next to mix-model groups, not inside them. Lake folders `bronze/x_orders/`, `bronze/x_customers/`, `gold/mart_clv_customer/`. Pipeline `pl_x_clv_week` Sunday 07:00 America/Toronto. Container job writes `gold.clv_scores`. CRM export is hashed key plus decile, not a raw email file. If holdout Spearman drops, keep last week’s scores.

---

## Layout

```
problem/              problem statement and assumption table
data_engineering/     snapshot contract
development/          clv.py engine, studio, customers, segments, methods
production/           Azure score-job page
```

---

## What would change the choice

If almost every subscriber has a contractual renew date and silent churn disappears, switch to contractual survival. If Spearman stays near zero after leakage is fixed, do not put deciles into CRM. Media mix stays in project 01; do not add weekly spend columns to this mart to “explain” CLV.
