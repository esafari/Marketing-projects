# Project 03 — Causal effects

This README is the studio HTML, written as markdown: problem, geo story, 12-method suite, data engineering, and Amazon Web Services production.

X Canada is a weekly meal-kit subscription (HelloFresh-class). Production is Amazon Web Services (`ca-central-1`), isolated from the Azure mix and CLV marts.

Run from the repo root: `python run_webapp.py` → http://127.0.0.1:5050/causal/suite


---

# Page: causal data engineering

Source: `projects/03_causal_effects/data_engineering/templates/causal_data_engineering.html`

### Causal data engineering Sources

Geo sales (Forward Sortation Area × week), planned extra media or offer (treatment start week, treated geos), pre-period covariates (baseline sales, unemployment), and a randomization log if the design was a geo experiment. Mix-model national spend is a covariate, not the treatment file.

### Bronze → silver → gold

Bronze: daily geo sales and the signed treatment CSV. Silver: Monday weeks, one row per geo-week, treatment flag that cannot flip after lock_ts. Gold: mart_causal_geo_week plus dim_experiment (design = observational vs randomized). The engine reads both designs on purpose.

### Tests that fail the week closed

Treated geos have a pre-period. No geo is both treated and control. Outcome is ship-week net, not Google conversions. If the randomization log is missing, the row is labeled observational and difference-in-differences is not sold as a trial.

## Contract the development engine is allowed to see

| Mart column | Meaning | Used for |
| --- | --- | --- |
| geo_key, week | Panel grain | Every estimator |
| y | Net outcome | Pre/post, DiD, two-way OLS |
| treat, post | Assignment and time | DiD contrast |
| design | observational vs randomized | Which bias story to tell |

Problem statement Development — estimators 12-method suite Production on Amazon Web Services Experiment page

---

# Page: causal

Source: `projects/03_causal_effects/development/templates/causal.html`

Causal inference Geo-week panel. True multiplicative lift on treated geos after the cut. Methods: treated-only pre/post, difference-in-differences, two-way demeaned OLS, and an elasticity-style log contrast. The same lift is also assigned at random as the experiment.

Click Run causal (20 geos, 80 weeks, 6 treated, seed 42). Pass if observational bias is clearly larger than the randomized difference-in-differences bias, and the treated line in the confounded chart was already rising before the cut.

Observational ≈ experiment: the confound was weak (growth gaps too small). Difference-in-differences still biased in the confounded world: trends were not parallel — that is the point of the randomized column. Do not brief the observational number to finance.

Geos Weeks True lift Seed Run causal

### Confounded rollout — treated were already faster

### Estimate versus truth

Geo-level pre/post and the randomized chart are on Experiments. The twelve-method suite (instruments, synthetic control, inverse probability weights, double machine learning, meta-learners, factorial tests, bootstrap, and neural CATE) is on 12-method suite.

---

# Page: causal experiments

Source: `projects/03_causal_effects/development/templates/causal_experiments.html`

Experiments

### Randomized experiment

### Confounded treated geos

Method bake-off is on Causal inference.

---

# Page: causal methods

Source: `projects/03_causal_effects/development/templates/causal_methods.html`

Causal methods
```
Y_{g,t} = level_g × exp(growth_g × t) × (1 + τ × Treated_g × Post_t) + season_t + e

Confounded assignment   Treated = 1 for the n geos with the largest growth_g
Randomized assignment   Treated = 1 for n geos drawn uniformly

Observational     (Ȳ_treated,post / Ȳ_treated,pre) − 1
DiD               exp( Δlog treated − Δlog control ) − 1
Two-way OLS       log Y on Treated×Post after geo and week demeaning
Elasticity-style  same contrast as DiD, reported as a percent lift

τ is known in the data generating process (default 0.12).
Bias = estimate − τ. Brief the randomized DiD, not the observational pre/post.
```
In production, register geo-lifts in fact_experiment and use those posteriors to scale a channel’s MMM total before Sequential Least Squares Programming. Do not put test_id into two-stage least squares as a regressor.

---

# Page: causal suite

Source: `projects/03_causal_effects/development/templates/causal_suite.html`

Causal suite — 12 methods Seed Run all 12 tests

/ 12 ·

### Problem statement

#### Situation

#### Decision this number is allowed to change

#### Units and grain

#### Why the naive number is wrong

#### What success looks like

### Why this estimator

Approach.

Assumptions.

### Mathematical model

How to read a run.

Run this test

---

# Page: causal problem

Source: `projects/03_causal_effects/problem/templates/causal_problem.html`

## Causal problem statement Company setting

Think HelloFresh, Goodfood, or Factor — a weekly meal kit. Revenue is ship-week boxes. The hard marketing problems are not “did the dashboard go up.” They are: first-box acquisition that looks cheap because last-click harvests brand search; everyday price-per-serving raised in January when people were going to subscribe anyway; a 40% win-back redeemed by people who still open the app; a pause-save discount taken by loyal family plans who never needed it; a national New Year flight with no holdout because brand TV is national; a homepage that stacks “$4.99 a serving” with free first delivery. Those are twelve different designs. One estimator cannot cover them.

## Problem

Commercial teams roll extra YouTube into metros that already have the fastest first-box growth. Pricing harvests New Year demand. CRM mails 40% off to cancels who were coming back. Brand runs a national resolution flight with no control metro. The same 50% stay offer helps skippers and wastes margin on weekly loyalists. Each of those is a different causal problem. This project states twelve of them, each with units, a naive trap, and a test. In the lab the true effect is known, so we score bias instead of arguing from narrative.

## Scope

### In scope

Twelve identification problems, each with its own design: geo difference-in-differences, cost-shock instruments for price, synthetic control for a single province, inverse probability weights for offer take-up, national interrupted time series, double machine learning with rich covariates, S/T/X meta-learners for heterogeneous effects, 2-by-2 site tests, bootstrap intervals, t-test and ANOVA, two uncertainty recipes, and a TARNet-style neural CATE. Production still lands on Amazon Web Services so these writes cannot overwrite the Azure mix-model mart.

### Out of scope

National weekly budget optimization (project 01). Customer lifetime scores (project 02). Creative multivariate tests, synthetic control at 200 geos, CUPED, and continuous dose-response as the v1 ship. Changing the treatment file after lock.

### Decision this model is allowed to change

Whether a first-box YouTube burst, price-per-serving hike, Ontario TV flight, 40% win-back, New Year package, pause-save, or $4.99 homepage is called incremental; who gets the next discount; and whether an observational readout is allowed in the finance pack at all.

## Questions this project answers (one per test)

- First-box YouTube in already-hot metros: incremental first boxes, or January growth we selected on?
- Everyday price-per-serving: if we raise it after New Year, how many weekly boxes do we lose?
- Ontario-only brand TV: what would Ontario first boxes have been without the flight?
- Win-back 40% off next two boxes: extra boxes on the cancel file, not on self-selected redeemers?
- National New Year flight with no holdout: what would first boxes have done if the package had not run?
- Pause-to-skip / 50% stay: extra boxes after we partial out plan size, tenure, and discount history?
- Who should get the 50% stay offer — at-risk skippers, or also loyal weekly family plans?
- Homepage 2-by-2: does “$4.99 a serving” plus free first delivery amplify first-box conversion?
- Checkout meal-picker A/B: how wide is +2.4 if we had drawn a different week of traffic?
- Did the $4.99 badge move first-box conversion, and do the four landing cells differ?
- Reactivation SMS: do two 90% intervals both sit above zero before we blast the next cancel file?
- Deeper first-box discount: does a small two-head net beat a linear T-learner on who actually needs it?

## Approaches we considered

| Approach | What it does | Why we did not stop there |
| --- | --- | --- |
| Treated-only pre/post | After minus before on treated geos. | Confounds growth, season, and treatment. The usual “it worked” slide. |
| National mix-model coefficient | Uses project 01 spend columns. | Wrong grain. Cannot see who was treated. Easy to call a correlation a launch effect. |
| Matching on last week’s sales only | Pairs geos that look similar at launch. | Does not fix diverging pre-trends. Still observational. |
| Synthetic control / matrix completion | Richer counterfactual for one treated unit. | Right for a later single-province launch. Heavier than the bias lesson we need first. |
| Observational suite plus randomized difference-in-differences | Show the same estimators on a confounded rollout and on a proper geo trial. | Selected. Stakeholders see why the number moved, not just a preferred estimator. |

## Why we selected this approach

- The failure mode is selection, not lack of a fancy estimator. We need the bad number and the better number on one page.
- Difference-in-differences is the language commercial already uses for “test versus control markets.”
- Two-way ordinary least squares is the regression form of the same contrast; if it disagrees, the panel is sick.
- Elasticity-style log change is what pricing and media people quote; we keep it so they can see it inherit the same bias.
- A known true lift in the lab is the only honest unit test for “did we separate impact from correlation.”

## Assumptions

- Stable unit treatment. Treating Toronto does not spill demand into a control FSA through ads or fulfillment. If it does, we understate interference, not just lift.
- Locked assignment. After lock_ts, a geo cannot move from control to treated in gold. Rewrites are audit events on Amazon Simple Storage Service versioning.
- Parallel trends (for DiD). Required on the observational design; we do not assume it. The randomized design is what makes the assumption plausible.
- Outcome. Ship-week net boxes or revenue, same spirit as mix-model Y, never Google conversion value.
- One treatment per test. Each card is on/off (or a 2-by-2), not a continuous bid or five stacked tactics on the same row.
- Label the design. Missing randomization log means the row stays observational. The pack title must say so.

## The twelve problem statements

Each block below is the full problem for one test. Open the suite to run the matching estimator.

/ 12 ·

#### Situation

#### Decision this number is allowed to change

#### Units and grain

#### Why the naive number is wrong

#### What success looks like

Open this test on the suite

## What would change the choice

If we have one large treated province and many donors, we add synthetic control as a second estimator — we do not delete difference-in-differences. If units interfere (national television leaking into control geos), we redesign the experiment; we do not “fix it” in ordinary least squares. Mix-model budget questions stay on Azure in project 01.

Run the geo test on the lab Run all 12 suite tests Data engineering Development Production — Amazon Web Services

---

# Page: causal production

Source: `projects/03_causal_effects/production/templates/causal_production.html`

### Causal production — Amazon Web Services Landing zone

Account and region ca-central-1. Lake bucket x-causal-lake-{env}. Prefixes bronze/geo_sales/, bronze/experiments/, gold/mart_causal_geo_week/. Secrets Manager holds the ledger and the treatment-file signer. Public access block on. Versioning on so a rewritten treatment file is an audit event.

### After-flight job

EventBridge rule when dim_experiment.status = 'ended' or a Monday 08:00 America/Toronto schedule. Glue jobs land geo-weeks. Data build tool tests the lock. Elastic Container Service task runs the causal engine, writes gold.causal_estimates (estimator, lift, bias vs any known holdout) and a Ship / Watch / Kill note for commercial.

### What ships

Image x-causal:{git-commit} on Elastic Container Registry. QuickSight dashboard on gold only. If the design is observational, the pack title says observational. Randomized geo tests get the difference-in-differences number first.

## Amazon Web Services in this project

| Service | Role |
| --- | --- |
| Amazon Simple Storage Service | bronze / gold prefixes, versioned treatment files |
| Amazon Glue | Geo-week parquet and catalog |
| Amazon Redshift Serverless | mart_causal_geo_week |
| Amazon Elastic Container Service | Causal engine task |
| Amazon EventBridge | End-of-flight and Monday schedule |
| Amazon QuickSight | Decision pack, gold only |

Data engineering contract Development Shared AWS from-zero notes (hashes on the MMM file)

---

## 12-method suite (from `/causal/suite`)

### 1. Difference-in-differences
**First-box YouTube in markets that were already hot**

**Problem.**
X Canada is a weekly meal-kit subscription (same economics as HelloFresh): new customers start on a cheap first box, then either stay on a weekly plan, skip, pause, or cancel. Growth marketing put extra YouTube into the five census metros that already had the fastest first-box growth — the usual 'put media where it is working' instinct. Those metros then ship more first boxes. The question is not whether first boxes went up. The question is whether those extra first boxes are incremental YouTube, or January / payday / word-of-mouth growth those metros were already on.

**Situation.**
Sixteen Canadian geos, sixty weeks, extra YouTube from week 36. Treated metros were chosen by ranking recent first-box growth (not a randomized holdout). Each geo keeps its own trend and recipe-season wiggle. The lab plants a true 10% multiplicative lift in first-box acquisitions after launch.

**Decision this number is allowed to change.**
Scale the YouTube burst to the rest of Canada, hold it in the five metros, or kill it and keep the first-box budget on paid search. Finance will not put a first-box CAC win in the board pack until we separate the burst from the growth we selected on.

**Units and grain.**
Grain: metro by week. Outcome Y = first-box (new-customer) ship-week boxes, not continuing boxes. Treatment D_i = 1 if the metro got extra YouTube. Post P_t = 1 after launch. Continuing subscribers are a different decision (lifetime value, project 02).

**Why the naive number is wrong.**
Treated-only pre/post credits the metros' own New Year / urban growth as media. Meal-kit first boxes already spike in January. Because we chose the fastest growers, the naive first-box lift is systematically too large and makes YouTube look cheaper than it is.

**What success looks like.**
Difference-in-differences (ratio-of-ratios) lands near the planted 10% first-box lift and closer to truth than treated-only pre/post. If DiD is still far off, parallel trends failed — we do not scale and we do not cut paid search on this number.

**Why this estimator.**
Meal-kit growth teams already brief 'test versus control markets' for TV and YouTube. DiD is that brief, written as an estimator. It fails when we picked the hottest metros — which is why this lab treats the fastest geos on purpose.

**Approach.**
Take the treated-minus-control first-box gap after launch and subtract the same gap before launch. We report the ratio-of-ratios form so the number is a percent lift, comparable to the planted 10% truth.

**Assumptions.**
Parallel trends (control would have tracked treated); no spillover into control geos; assignment locked; ship-week boxes.

**Mathematical model.**
```
Y_it = boxes in geo i, week t
D_i = 1 if geo is treated, P_t = 1 after launch
Ratio-of-ratios DiD:
  tau_hat = (Y_t,post / Y_t,pre) / (Y_c,post / Y_c,pre) - 1
Naive (wrong if trends differ):
  tau_naive = Y_t,post / Y_t,pre - 1
Two-way form (same idea): E[Y|D=1,P=1] - E[Y|D=1,P=0]
                         - (E[Y|D=0,P=1] - E[Y|D=0,P=0])
```

**How to read a run.**
If DiD is near the true 10% and naive pre/post is larger, the extra naive points are growth you would have gotten anyway. Brief DiD, not the treated-only chart.

### 2. Instrumental variables (two-stage least squares)
**Everyday price per serving when January demand is already high**

**Problem.**
X Canada prices a weekly box as price-per-serving (the HelloFresh-style $9.99 vs $11.49 decision). Pricing raises everyday price or shrinks the first-box discount in hot weeks — New Year resolutions, payday Fridays, Super Bowl. People still convert, so a regression of boxes on price looks almost flat and finance concludes 'customers are not price sensitive.' We need the causal slope: if we raised price-per-serving one unit while demand stayed the same, how many weekly boxes would we lose?

**Situation.**
National weekly series of continuing plus first boxes. Price and unobserved demand (resolutions, weather, a viral recipe) move together. A cost shock Z — chicken and produce inflation, or last-mile courier rates — also moves the shelf price, but households do not order more kits because protein cost went up except through that price.

**Decision this number is allowed to change.**
Whether we can lift everyday price after the New Year rush without crushing weekly boxes, and whether the first-box promo can be pulled back. Ordinary-least-squares elasticity is not a pricing tool here.

**Units and grain.**
Grain: national week. Outcome Y = ship-week boxes. Endogenous regressor = everyday price per serving (or first-box net price). Instrument Z = food or last-mile cost shock. Object is tau in Y = alpha + tau * Price + u, planted at -1.20.

**Why the naive number is wrong.**
OLS of boxes on price is biased toward zero: January has both higher prices (we harvest demand) and higher boxes, which looks like 'price barely hurts.' That is how meal-kit teams over-raise price and then watch skip and cancel rise two weeks later.

**What success looks like.**
Two-stage least squares recovers a slope near -1.20, and the first-stage F on the cost shock is above 10. If F is weak, we do not brief the IV number and we run a real price test instead.

**Why this estimator.**
Meal-kit price is chosen with demand. OLS is not an elasticity. A cost instrument is the fix when a randomized price test is not on the table this quarter.

**Approach.**
Use a food or last-mile cost shock Z that moves price-per-serving but does not belong in the demand equation. First stage: price on Z. Second stage: boxes on fitted price.

**Assumptions.**
Relevance: Z moves price (first-stage F > 10). Exclusion: Z affects boxes only through price. Monotonicity of the first stage.

**Mathematical model.**
```
Structural demand:  Y = alpha + tau * Price + u
Price is endogenous:  Corr(Price, u) != 0
Instrument Z (cost shock):
  Stage 1:  Price = pi_0 + pi_1 Z + v
  Stage 2:  Y     = alpha + tau * Price_hat + e
tau is the causal price coefficient we want (planted at -1.20).
```

**How to read a run.**
OLS closer to zero than IV means demand shocks hid the true negative price effect. Trust IV only if first-stage F is large. If IV and OLS agree, the endogeneity was weak.

### 3. Synthetic control
**Ontario-only brand TV before a second-province rollout**

**Problem.**
Brand buys a connected-TV and linear-TV flight only in Ontario — the largest meal-kit market — to see if a French or West-Coast flight is worth writing. There is no randomized twin and only one treated province, so a many-market DiD average does not apply. We need a counterfactual Ontario: how many first boxes would Ontario have shipped if that brand flight had not run?

**Situation.**
Ontario gets the flight; other provinces are unused donors (never in the buy). Ontario has its own hockey-season and January path. The lab plants an additive +18 first boxes after launch on Ontario only.

**Decision this number is allowed to change.**
Roll the same brand TV into Quebec or British Columbia, or keep the money on national YouTube and paid search. If the synthetic twin already tracks Ontario after launch, we do not scale.

**Units and grain.**
Grain: province by week. Treated path Y_1t = Ontario first-box (or total) boxes. Donors Y_jt = other provinces. Weights w_j >= 0 sum to 1. Effect is the post-period mean of Ontario minus the twin.

**Why the naive number is wrong.**
Ontario pre/post, or Ontario versus 'Quebec looks similar,' counts Ontario's own urban growth and January resolutions as brand TV. One donor is usually a bad twin for a meal-kit launch.

**What success looks like.**
Pre-period synthetic path hugs Ontario; post-period gap sits near +18 first boxes; a few donors carry most of the weight. Naive Ontario-only pre/post should look larger than the synthetic gap.

**Why this estimator.**
One large province, many unused donors. That is the geometry of a single-market meal-kit TV test. Synthetic control is built for it.

**Approach.**
Choose nonnegative donor weights that sum to 1 and match Ontario's pre-launch first-box path. After launch, lift is Ontario minus that weighted twin.

**Assumptions.**
Donors are untreated; no anticipation; weights >= 0 and sum to 1; no interference from Ontario ads into donors.

**Mathematical model.**
```
Treated path Y_1t. Donors Y_jt, j=2..J.
Choose w >= 0, 1'w = 1 to minimize
  || Y_1,pre - sum_j w_j Y_j,pre ||^2
Synthetic path:  Y*_t = sum_j w_j Y_jt
Post effect:  tau_hat = mean_t in post (Y_1t - Y*_t)
Truth in this lab is an additive +18 boxes after launch.
```

**How to read a run.**
The chart should hug before the cut and split after. If the post gap is near +18 and naive pre/post is larger, naive counted Ontario's own trend as 'lift.' Weights in the table are the twin — a few donors should carry most of the mass.

### 4. Inverse probability weighting
**Win-back: 40 percent off the next two boxes**

**Problem.**
CRM emails cancelled subscribers a HelloFresh-style win-back: 40% off the next two boxes. Redeem is voluntary. People who still open the app, who had many prior boxes, or who only paused last month are much more likely to click. Comparing redeemers to non-redeemers mixes the coupon with 'these people were coming back anyway.' We want the average extra boxes on the whole mailed cancel file — the number that pays for the discount margin.

**Situation.**
Customer-level rows after one win-back drop. Treatment D is redeem, not random assignment. X includes prior boxes, tenure, last-open recency, and plan size (two-person vs family). True average extra boxes is planted at +4.5 over the next horizon.

**Decision this number is allowed to change.**
Keep, shrink, or kill the 40% win-back for the next cancel cohort. If the incremental boxes do not cover the discount, we move to a skip reminder or a smaller 20% offer. Targeting who should get it is the meta-learner card.

**Units and grain.**
Grain: cancelled (or long-paused) customer. Outcome Y = boxes shipped in the next 8 weeks. Treatment D = 1 if the 40% code was redeemed. Population = everyone who was emailed, not only redeemers.

**Why the naive number is wrong.**
Redeemer-minus-non-redeemer is too large: engaged cancels redeem and would have resubscribed on a payday or a New Year anyway. That is how win-back ROAS looks great while incremental margin is thin.

**What success looks like.**
Inverse-probability weighted average sits near +4.5 extra boxes and below the naive gap. If weights explode (almost-sure redeemers or never-redeemers), overlap failed and we do not brief it.

**Why this estimator.**
Win-back is not randomized, but we observe the CRM fields that drove redeem. IPW recenters redeemers and non-redeemers onto one mailed cancel file.

**Approach.**
Fit propensity e(X) = P(redeem | prior boxes, tenure, recency, plan size). Reweight redeemed outcomes by 1/e and non-redeemed by 1/(1-e), then subtract.

**Assumptions.**
Unconfoundedness given X. Overlap: 0 < e(X) < 1 (we clip to [0.05, 0.95]). SUTVA.

**Mathematical model.**
```
e(X) = P(D=1 | X)
IPW ATE =
  E[ D Y / e(X) ]  -  E[ (1-D) Y / (1-e(X)) ]
Naive gap = E[Y|D=1] - E[Y|D=0]   (biased if X differs)
Planted ATE in this lab is +4.5.
```

**How to read a run.**
If naive is much larger than IPW, the extra is selection (engaged people take the offer). Brief IPW. If they match, selection was weak. If IPW is wild, overlap failed — someone had e near 0 or 1.

### 5. Time-series causal impact
**National New Year resolution flight with no holdout**

**Problem.**
Brand runs a national New Year (or Super Bowl) flight — TV, YouTube, and a homepage 'new year, new routine' first-box offer — starting one Monday. Every province is in the buy, so there is no holdout metro. First boxes always rise in January anyway. The only contrast left is time: what would national first boxes have done after that Monday if the flight and the offer had not run?

**Situation.**
One national weekly first-box series with trend and a 13-week seasonal wiggle (resolutions, then a spring slump). At week T0 the campaign adds a planted +12 first boxes on top of that path. No donor geos exist by design.

**Decision this number is allowed to change.**
Renew the New Year package next January, cut national TV and keep only the first-box discount, or move money into geo tests. A national mix-model coefficient is the wrong grain for one interrupted week.

**Units and grain.**
Grain: national week. Outcome Y_t = first-box acquisitions. Cut T0 = campaign Monday. Counterfactual = forecast from a pre-period trend-plus-season model. Effect = mean post (actual minus forecast).

**Why the naive number is wrong.**
Post mean minus pre mean includes the ordinary January resolution spike. Meal-kit teams brief that spike as media every year. It will look like a larger campaign than we planted.

**What success looks like.**
The forecast continues the pre-period wiggle; the gap after the cut sits near +12 first boxes. We do not brief this if a price change, a popular-recipe stockout, or payday landed the same week.

**Why this estimator.**
National meal-kit brand flights often have no geo holdout. Interrupted time series / CausalImpact-style is what is left.

**Approach.**
On the pre-period, fit trend plus weekly season (the resolution-then-slump shape). Forecast the post-period. Lift is actual first boxes minus that forecast, averaged after the cut.

**Assumptions.**
The pre-period model would have continued. No other national shock lands on the same week. Additive lift in this lab is +12.

**Mathematical model.**
```
Pre-period t < T0:
  Y_t = b0 + b1 t + b2 sin(2 pi t / 13) + b3 cos(2 pi t / 13) + e_t
Forecast Yhat_t for t >= T0 from that fit.
tau_hat = mean_{t >= T0} (Y_t - Yhat_t)
Naive = mean_post Y - mean_pre Y   (confounds trend and season).
```

**How to read a run.**
The forecast line should continue the pre-period wiggle. The gap after the cut is the campaign. If naive pre/post is bigger, you counted the ordinary upward trend as media. Do not brief this if another national event hit the same week.

### 6. Double machine learning
**Pause-to-skip offer with a messy CRM file**

**Problem.**
A subscriber hits cancel. CRM shows a HelloFresh-style save: 'Skip this week instead — or take 50% off your next box if you stay.' Who clicks depends on many things at once: weeks on the plan, two-person vs family, how many discounts they already used, whether they came from an affiliate or paid social, device, last recipe rating. A raw 'savers vs cancellers' gap is confounded. A single OLS that 'controls for everything' can still be wrong if that X specification is brittle. We want the average extra boxes kept after we partial out that rich file.

**Situation.**
Customer-level observational save offer. D = took the skip or 50% stay offer. Y = boxes in the next 8 weeks. X is the CRM file above. True average extra boxes is planted at +3.0, and X also moves Y directly (family plans already ship more).

**Decision this number is allowed to change.**
Whether the pause-save program has incremental boxes after we remove selection. If the average is real, we keep the program and then target with the next card. If it is not, we are paying margin to people who were going to skip anyway.

**Units and grain.**
Grain: subscriber who entered the cancel flow. Y = later boxes, D = took the save offer, X = tenure, plan size, discount history, acquisition channel, device. Object is tau in Y = tau D + g(X) + u.

**Why the naive number is wrong.**
The raw gap credits family-plan and high-tenure subscribers to the offer. One-shot OLS of Y on D and X can still bias tau if plan size or discount history is misspecified.

**What success looks like.**
Residual-on-residual double machine learning sits nearer +3.0 extra boxes than the naive gap. If it agrees with OLS-plus-X, a linear CRM specification was already enough.

**Why this estimator.**
Meal-kit CRM files are wide. Neyman orthogonality means small mistakes in those two first stages do not first-order bias the extra-box number.

**Approach.**
Residualize later boxes on the CRM file and offer take-up on the CRM file with Ridge. Then regress the Y residual on the D residual.

**Assumptions.**
Unconfoundedness given X; overlap; first stages are not wildly overfit (Ridge, not an unconstrained deep net).

**Mathematical model.**
```
Y = tau D + g(X) + u
D = m(X) + v
Y_res = Y - ghat(X),   D_res = D - mhat(X)
tau_hat = argmin_tau  || Y_res - tau D_res ||^2
Planted ATE is +3.0. Naive = E[Y|D=1]-E[Y|D=0].
```

**How to read a run.**
Read DML next to naive and OLS+X. If DML sits nearer +3 than the naive gap, the extra naive points are confounding. If DML and OLS agree, a linear g(X) was already enough.

### 7. Meta-learners (S / T / X)
**Who should get the pause-save discount — not the whole base**

**Problem.**
The same 50% stay offer does not help every subscriber. People who have skipped three weeks, rated meals poorly, or are on a two-person plan after a first-box promo get a large extra-box lift. Weekly family-plan loyalists take the 50% they did not need — you pay margin and they would have shipped anyway. An average can say 'mail the whole cancel-risk file' when one segment should not get the discount at all. We need CATE(x): expected extra boxes for a subscriber with features x.

**Situation.**
Customer-level save offer. True extra boxes are 1 for low-risk (loyal weekly) and 4 for high-risk (skipped / low rating / post-promo) — a jump of 3 when X1 > 0. We fit S, T, and X learners and score them against that known shape.

**Decision this number is allowed to change.**
Who gets the 50% stay offer next week. Mail only the high-CATE segment if the gap is real. Loyal weekly subscribers get a skip reminder or nothing — not a discount.

**Units and grain.**
Grain: subscriber. Y = later boxes, D = offer, X = skip history, rating, plan size, tenure, first-box promo flag. Object is tau(x) = E[Y(1)-Y(0)|X=x]. Score is PEHE versus true tau(x).

**Why the naive number is wrong.**
One average hides the loyal segment you should not discount. A single S-learner that only adds a treatment flag smears the jump and you keep mailing 50% to people who never pause.

**What success looks like.**
At least one learner recovers a high-versus-low extra-box gap near 3 and a low PEHE. We target high-CATE (at-risk) and withhold the same 50% from low-CATE loyalists.

**Why this estimator.**
CATE is the CRM targeting object. PEHE says which learner recovered 'at-risk vs loyal' instead of one average.

**Approach.**
S-learner: one model with an offer flag. T-learner: one model on those who got the save, one on those who did not, then subtract. X-learner: impute individual extra boxes, then a second-stage model blended by propensity.

**Assumptions.**
Unconfoundedness given X; enough treated and control in each segment we report.

**Mathematical model.**
```
True CATE in this lab:  tau(x) = 1 + 3 * 1{x1 > 0}
S:  mu(x,d) = E[Y|X=x,D=d],   tau_S = mu(x,1)-mu(x,0)
T:  mu1(x)=E[Y|X=x,D=1], mu0(x)=E[Y|X=x,D=0],  tau_T = mu1-mu0
X:  D_i=1:  tau~ = Y - mu0(X);  D_i=0:  tau~ = mu1(X) - Y
    tau_X(x) = e(x) tau_0(x) + (1-e(x)) tau_1(x)
PEHE = sqrt( E[ (tau_hat(X) - tau(X))^2 ] )
```

**How to read a run.**
Lower PEHE is better. If T or X PEHE is clearly below S, the single-model S-learner smeared the segment effect. The table's 'high' versus 'low' gap should sit near 3. Target the high-CATE segment; do not mail the low-CATE segment the same offer.

### 8. A/B and multivariate testing
**First-box landing page: $4.99 a serving times free delivery**

**Problem.**
The acquisition landing page can show a first-box price badge ('Meals from $4.99 a serving'), waive the delivery fee on box one, show both, or show neither (everyday price, paid delivery). Two sequential A/Bs — badge first, free delivery later — never see the combination. In meal kits those levers often amplify: the cheap first box plus 'no delivery fee' is how HelloFresh-class sites convert cold traffic. We need main effects and the interaction from one randomized 2-by-2.

**Situation.**
New-visitor sessions independently assigned to the four homepage cells. True effects are planted at +3 for the $4.99 badge, +5 for free first-box delivery, and +1.2 extra when both are on (they amplify).

**Decision this number is allowed to change.**
Which of the four first-box experiences is the default homepage. If the interaction is real, we must ship both — not the winner of a badge test and the winner of a later shipping test. Finance also cares because both levers cost margin on box one.

**Units and grain.**
Grain: new-visitor session. Outcome Y = first-box checkout conversion score. A = $4.99 badge on/off. B = free first delivery on/off. Objects: tau_A, tau_B, tau_AB from the four cell means.

**Why the naive number is wrong.**
Two sequential A/Bs miss the extra lift of cheap first box plus free delivery. Last-click 'paid search converted' also cannot say which homepage combination actually closed the box.

**What success looks like.**
Recover badge near 3, free delivery near 5, interaction near 1.2. The both-on cell should be the highest first-box conversion. Interaction near zero would mean we can ship them independently.

**Why this estimator.**
A factorial answers both first-box levers and whether they amplify, in one flight — the actual homepage decision.

**Approach.**
Assign each new visitor independently to badge in {0,1} and free delivery in {0,1}. Estimate the four first-box conversion means, then main effects and the interaction.

**Assumptions.**
Independent users; SUTVA; assignment is the experiment (not a later opt-in).

**Mathematical model.**
```
Y = mu + tau_A A + tau_B B + tau_AB A B + e
Planted: tau_A=3, tau_B=5, tau_AB=1.2
tau_A = 1/2 [(Y_10 - Y_00) + (Y_11 - Y_01)]
tau_B = 1/2 [(Y_01 - Y_00) + (Y_11 - Y_10)]
tau_AB = (Y_11 - Y_10) - (Y_01 - Y_00)
Y_ab = mean outcome in cell A=a, B=b.
```

**How to read a run.**
Read the four cell means first. Badge main effect near 3 and shipping near 5 means both levers work. Interaction near 1.2 means together they add a bit more than the sum of mains. If interaction is ~0, you can ship them independently.

### 9. Bootstrapping the average treatment effect
**Checkout meal-picker test — how wide is +2.4?**

**Problem.**
Product tests a HelloFresh-style checkout change: 'Choose your first 3 meals' versus a default pre-selected menu. The A/B reports +2.4 on first-box conversion. Finance's next question is not the point. It is how wide that +2.4 is if we had drawn a different week of the same new-visitor traffic. A point estimate cannot answer that, and first-box traffic is noisy (payday, weather, a TV burst).

**Situation.**
Randomized two-cell checkout test. Sessions are the resampling units. We redraw the week with replacement, keep each session's assignment, and recompute the first-box conversion lift each time.

**Decision this number is allowed to change.**
Ship the meal-picker as default checkout, or hold and collect another week. If the 90% interval still covers zero, we do not treat +2.4 as a fact — meal-picker engineering cost is not justified on a lucky sample.

**Units and grain.**
Grain: new-visitor checkout session. Object is the sampling distribution of first-box conversion ATE. We report the 5th and 95th percentiles. Planted ATE is +2.4.

**Why the naive number is wrong.**
Treating the first week's +2.4 as exact. A payday week can look like a win; the next week of the same experiment can cross zero.

**What success looks like.**
The 90% interval covers the planted 2.4 and excludes 0. A wide interval means we need more first-box traffic, not a different estimator.

**Why this estimator.**
Meal-kit conversion is noisy week to week. The interval is what a ship/kill gate should use, not the first point.

**Approach.**
Resample checkout sessions with replacement, keep assignment, recompute first-box conversion ATE many times. Report the 5th and 95th percentiles (90% interval).

**Assumptions.**
Users are i.i.d.; assignment stays with the user; 90% percentile interval.

**Mathematical model.**
```
ATE = E[Y|D=1] - E[Y|D=0]
For b=1..B: draw (Y*,D*) by sampling rows with replacement
  ATE*_b = mean(Y*|D*=1) - mean(Y*|D*=0)
CI_90 = [quantile_0.05(ATE*), quantile_0.95(ATE*)]
Planted ATE is +2.4. Gate: interval covers 2.4 and excludes 0.
```

**How to read a run.**
The histogram is the sampling distribution of the ATE. If 0 is left of the 5th percentile, the lift is not a fluke of one draw. If the interval is wide, you need more users, not a different point estimator.

### 10. Hypothesis testing (t-test and ANOVA)
**Did the $4.99 first-box badge actually move conversion?**

**Problem.**
After the homepage 2-by-2, the CMO and finance want two yes/no answers, not a lift chart: did the $4.99-a-serving badge move first-box conversion, and do the four landing-page cells differ as a set? Those are hypothesis tests. They are not a substitute for 'how many extra first boxes' or 'does the extra discount margin pay back.'

**Situation.**
Same randomized factorial as the landing-page card. We test (1) badge versus no-badge with a Welch t-test and (2) equality of the four homepage cells with one-way analysis of variance.

**Decision this number is allowed to change.**
Whether we can reject 'the first-box page did nothing' at 5%. A reject is permission to read magnitudes and margin on the factorial and uncertainty cards — it is not itself a ship of the $4.99 badge.

**Units and grain.**
Grain: new-visitor session. t-test compares first-box conversion with vs without the $4.99 badge. ANOVA compares the four cells. Outputs are t, F, and p-values.

**Why the naive number is wrong.**
Reading p < 0.05 as 'the badge is worth the first-box margin' or p > 0.05 as 'the badge does nothing.' A tiny conversion bump is significant on a huge January sample; a real bump can miss 5% in a quiet summer week.

**What success looks like.**
Both p-values fall below 0.05 when the planted first-box effects are real. We still pair this with cell magnitudes and uncertainty before we make $4.99 plus free delivery the default.

**Why this estimator.**
These are the tests already in an experiment readout. They only mean something after homepage assignment is randomized.

**Approach.**
Welch t-test on $4.99 badge versus no badge. One-way ANOVA across the four first-box landing cells.

**Assumptions.**
Independent users; Welch t-test allows unequal variance; ANOVA null is equal cell means.

**Mathematical model.**
```
t-test H0: mu_badge = mu_no_badge
  t = (Ybar_1 - Ybar_0) / sqrt(s1^2/n1 + s0^2/n0)
ANOVA H0: mu_00 = mu_01 = mu_10 = mu_11
  F = MS_between / MS_within
Reject H0 at 5% if p < 0.05. This does not measure how large the effect is.
```

**How to read a run.**
p < 0.05 means 'unlikely if the null were true,' not 'the effect is large.' Pair this card with the factorial and uncertainty cards. A tiny effect can be significant in a huge sample; a large effect can miss 5% in a small one.

### 11. Uncertainty estimation
**Reactivation SMS — ship only if the interval clears zero**

**Problem.**
Lifecycle sends a 'Come back this week — your favourites are on the menu' SMS to recently cancelled subscribers. The point lift is +1.8 extra boxes on a conversion-like score. That can be noise: SMS files are small and payday weeks bounce. The ship question is whether an honest interval still sits entirely above zero. We want two different 90% intervals on the same extra-box effect and a rule that requires both to agree before we blast the next cancel cohort.

**Situation.**
Randomized SMS vs holdout on a cancel file. Modest planted lift of +1.8 extra boxes. One interval recipe can look tight by accident. Finance gets both intervals and a binary ship/hold.

**Decision this number is allowed to change.**
Send the reactivation SMS to the next week's cancel file only if both lower bounds are above zero. Otherwise hold, write a different creative, or wait for a larger file. SMS cost is small; unsubscribes and brand damage are not.

**Units and grain.**
Grain: cancelled subscriber. ATE = extra boxes (SMS minus holdout). Normal interval uses a two-sample standard error. Bootstrap interval uses the 5th and 95th percentiles.

**Why the naive number is wrong.**
Shipping the SMS on a point +1.8, or on whichever interval is narrower. A tight normal interval that the bootstrap does not confirm is not a finance-ready lifecycle number.

**What success looks like.**
Both 90% intervals exclude 0, both cover +1.8, and the story does not depend on which recipe we picked. If they disagree, we brief the wider one and do not blast the file.

**Why this estimator.**
One recipe can look tight on a small cancel file. Two recipes that agree are what we take to finance before a national SMS.

**Approach.**
Normal interval using the two-sample standard error, and a bootstrap percentile interval. Ship the SMS only if both exclude 0 and both cover the planted truth.

**Assumptions.**
Independent users; 90% intervals; normal interval uses a Welch-style SE.

**Mathematical model.**
```
ATE = Ybar_1 - Ybar_0
SE = sqrt( s1^2/n1 + s0^2/n0 )
Normal 90%:  ATE ± z_0.95 * SE
Bootstrap 90%:  [q_0.05(ATE*), q_0.95(ATE*)]
Ship if 0 < both lower bounds and truth is inside both intervals.
Planted ATE is +1.8.
```

**How to read a run.**
If both lower bounds are above 0, ship is allowed on uncertainty grounds. If they disagree (normal tight, bootstrap wide), trust the wider one. Coverage of the planted 1.8 is the lab check that the interval is honest, not just narrow.

### 12. Deep learning causal effect (TARNet-style)
**First-box discount targeting when the lift is not a straight line**

**Problem.**
The extra boxes from a deeper first-box discount are not a straight line in the CRM file. Recent browsers who paused, or who came from social and have not subscribed, jump a lot. Current weekly subscribers who click the same '50% off your next box' take a discount they did not need (near-zero or negative incrementality). A linear T-learner can miss that shape and mail the discount to the wrong people. The question is whether two small neural nets — one for discounted outcomes, one for full-price — recover extra boxes given x more faithfully.

**Situation.**
Customer-level features (pause flag, recency, channel, plan size), treatment = deeper first-box or stay discount, Y = later boxes. True CATE is 0.8 + 2.6 * 1{X1>0} + 0.4 tanh(X2). We compare a 24-12 ReLU two-head net to a linear Ridge T-learner, without a graphics processor.

**Decision this number is allowed to change.**
Whether the next first-box / stay-discount file is scored by the neural CATE or by the linear T-learner. We do not ship a net that loses on PEHE just because it is 'deep,' and we do not discount loyal weekly subscribers if the net says their extra boxes are near zero.

**Units and grain.**
Grain: prospect or subscriber. mu_d(x) = expected later boxes given X and discount d. tau_hat(x) = extra boxes. Score is PEHE versus the known tau(x).

**Why the naive number is wrong.**
Assuming extra boxes rise linearly with 'engagement,' or assuming a neural net is better because it is more flexible. A small cancel file plus a flexible net overfits and can mail worse than Ridge.

**What success looks like.**
Neural PEHE is lower than linear PEHE, and the neural mean extra-box CATE is still near the true average. If the net loses, we target with the linear T-learner.

**Why this estimator.**
TARNet-style two-head nets are the practical deep CATE baseline for nonlinear meal-kit offers. We keep the net small so the lab stays reproducible without a GPU.

**Approach.**
Standardize CRM features. Fit one multilayer perceptron on discounted customers and one on full-price (TARNet-style two heads). Extra boxes = mu1(x) - mu0(x). Compare PEHE to a linear T-learner.

**Assumptions.**
Unconfoundedness given X; enough data for a 24-12 ReLU net; early stopping.

**Mathematical model.**
```
mu_d(x) ≈ MLP_d(x),   d in {0,1}
tau_hat(x) = mu_1(x) - mu_0(x)
True tau(x) = 0.8 + 2.6 * 1{x1>0} + 0.4 tanh(x2)
PEHE = sqrt( mean_i (tau_hat(X_i) - tau(X_i))^2 )
Linear T-learner is the same formula with Ridge instead of MLP.
```

**How to read a run.**
Compare the two PEHE numbers. Lower is closer to the true individual effects. Neural mean CATE should still sit near the true average. If neural PEHE is worse, the net overfit — fall back to the linear T-learner for targeting.
