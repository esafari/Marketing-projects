# Project 01 — Mix modeling and channel optimization

This README is the studio HTML, written as markdown: problem, warehouse, methods, controls, Azure production, and the supporting pages (attribution, forecast, demand, pricing, scenarios, uncertainty).

X Canada is a weekly meal-kit subscription (HelloFresh-class). Grain is one Canada week. Production is Azure, Canada Central.

Run from the repo root: `python run_webapp.py` → http://127.0.0.1:5050/mmm


---

# Page: mmm data engineering

Source: `projects/01_mmm_channel_optimization/data_engineering/templates/mmm_data_engineering.html`

### MMM data engineering Sources

Google Ads (Search, Performance Max, YouTube), later television and Meta, Google Search Console brand queries, X order ledger on ship-week, Statistics Canada unemployment and consumer prices, holiday and promo calendars, share of voice.

### Bronze → silver → gold

Bronze keeps vendor names and load timestamps. Silver converts Canadian dollars, America/Toronto weeks, and YouTube versus Paid Search. Gold is the star schema. The engine reads only mart_mmm_weekly at geo_key = 0.

### Tests that fail the week closed

One row per week. Y is net box revenue after credits and cancels, not Google conversion_value. M is organic branded clicks, not paid brand clicks. Spend columns are non-negative. A red test does not start Sequential Least Squares Programming.

## Contract the development engine is allowed to see

| Mart column | Meaning | Used for |
| --- | --- | --- |
| sales_Y | Ship-week net revenue | Stage 2 outcome |
| queries_M | Organic brand search | Stage 1 mediator |
| spend_* | Channel Canadian dollars | Adstock + Hill, then alpha / beta |
| price, promo_depth, holiday, sov | Non-media week | Controls, not channels |

Problem statement Full warehouse and field dictionary X Canada case Development studio Production on Azure

---

# Page: attribution

Source: `projects/01_mmm_channel_optimization/development/templates/attribution.html`

Attribution frameworks Incremental media mix versus last-touch, first-touch, linear, and time-decay. Price is a second lever. Investment allocation then spends one envelope two ways (last-touch vs incremental) and searches a price index 96–104.

Run the attribution engine. Pass if last-touch over-credits Paid Search versus incremental, TV is not zero incremental, and a +$10k or +1 price point has a signed effect. Incremental profit on the investment page should beat last-touch.

Last-touch ≈ incremental: no upper-funnel variation. Price ≈ 0: price did not move in blocks. Search still wins incremental: Y is a platform conversion. One channel takes the whole envelope: check Hill K and then Uncertainty before you ship.

Weeks Holdout weeks Weekly media budget ($k) Seed Run frameworks

### Credit share by framework (%)

Each group of bars is a channel. Black is true incremental share from the DGP. Rust last-touch piles credit on Search. Navy MMM and teal calibrated MMM should sit near black. Share MAE is the average absolute miss versus truth — that is the framework score.

### Framework error vs true incremental

Lower share MAE is better. Last-touch and first-touch usually lose. Time-decay is a milder version of the same bias. Lift-calibrated MMM applies geo-lift scales. When MMM already recovers truth, those priors can over-correct — that is useful, not a bug.

### Incremental sales of +$10k / +1 price point

Media bars are extra weekly sales $k from $10k more spend at the historical mean. The price bar is the sales change from raising the index one point. Negative price impact is expected: you sell less, but margin per unit rises — that trade-off is on the investment page.

### Holdout sales fit (incremental MMM)

OLS on Hill-adstocked spend plus log price, season, and holiday. Fit on the first 80%, scored on the last 26 weeks. If this line tracks, the incrementals above are usable. If it misses holiday price cuts, the elasticity is the first suspect.

### Price contribution: true vs estimated ($k)

Weekly sales attributed to the price index. When price is above 100, this series is negative. Matching the two lines means spend did not steal the price story — the usual omitted-variable failure when price is left out of MMM.

### Framework shares (%)

### Incrementals

Spend-plus-price allocation is on Investment allocation. Formulas are on Attribution methods.

---

# Page: attribution investment

Source: `projects/01_mmm_channel_optimization/development/templates/attribution_investment.html`

Investment allocation

### Weekly media $k: last-touch vs incremental

Rust follows last-click shares. Navy follows incremental iROAS. Both sum to the same budget. Moving money from Search to TV is the usual correction once price and carryover are in the model.

### iROAS at the incremental mix

Extra weekly sales from $1k more at the recommended spend. A bar below 1.0 is on a bound or on the flat of the Hill curve. Price is not on this chart — it is a level, not a spend line.

### Profit vs price index (incremental mix held fixed)

Contribution profit = 38% × (baseline + media + price effect) × (index/100) − media spend. Elasticity pulls units down as the index rises; revenue per unit goes up. The peak is the recommended list-price stance, not a promo depth.

### Last-touch plan

### Incremental plan

---

# Page: attribution methods

Source: `projects/01_mmm_channel_optimization/development/templates/attribution_methods.html`

Attribution methods Pipeline Media mix Pricing Attribution frameworks Calibration iROAS Allocation Production

## Solving approach

- Simulate (or ingest) weekly sales, price index, holiday, and spend on TV, Social, Search, Email.
- Transform spend with geometric adstock and Hill saturation. Price enters as log(P/100).
- Fit an incremental MMM by OLS on the first 80% of weeks. Hold out the last 26.
- Build last-touch, first-touch, linear, and time-decay credits from a Search-heavy touch process.
- Compare each framework’s channel shares to true incremental shares (DGP). Score with share MAE.
- Scale MMM totals by geo-lift factors (Search down, Social slightly up) to get a calibrated view.
- Compute iROAS and the sales effect of +1 price-index point. Reallocate media with SLSQP, then search price 96–104.

## Incremental media mix model

```
A_{c,t} = spend_{c,t} + θ_c A_{c,t−1}
x̃_{c,t} = A_{c,t} / (K_c + A_{c,t})

Y_t = β0 + γ t + season_t + δ holiday_t
    + β_P log(P_t / 100)
    + Σ_c β_c x̃_{c,t}
    + ε_t

Fit: OLS on train weeks. Price stays in the equation so media
cannot steal everyday-price movement.
```
True DGP betas: TV 210, Social 105, Search 155, Email 48, price scale 420 (on log price). TV flights on/off so carryover is identified. Search is always-on and last-touch dominant — that is the trap.

## Pricing incrementality

```
True:   price_effect_t = 420 * log(P_t / 100)
Est.:   price_effect_t = β̂_P * log(P_t / 100)

+1 index point at mean P̄:
  ΔlogP = log((P̄+1)/P̄)
  ΔY    = β̂_P * ΔlogP

Contribution profit at index P:
  π(P) = 0.38 * (Y_media + Y_price(P) + 1850) * (P/100) − media spend
```
Raising price cuts units (elasticity) and raises revenue per remaining unit. The investment page finds the peak of π(P) on [96, 104] with the incremental media mix held fixed. That is a list-price stance, not a TPR — TPR lives on the trade-forecast pages.

## Attribution frameworks

| Framework | Rule | What it gets wrong |
| --- | --- | --- |
| Last-touch | Week’s sales × Search-heavy touch probabilities (60/20/15/5 Search/Social/Email/TV) | Harvest media eats awareness. TV looks worthless. |
| First-touch | Credit the earliest channel with spend in an 8-week window; TV wins if it flew | Opposite bias. Over-pays TOFU, ignores closer conversion. |
| Linear MTA | Split Y_t by that week’s spend shares | No carryover, no saturation, no price. Still over-weights always-on Search. |
| Time-decay MTA | Weight spend_{t−ℓ} by 0.5^ℓ for ℓ = 0..7, then split Y_t | Better memory than linear, still not incremental, still not price. |
| MMM incremental | Σ_t β̂_c x̃_{c,t} | Can overstate Search if price/holiday are incomplete. Needs holdout and lift tests. |
| Lift-calibrated | MMM totals × {TV 0.88, Social 1.05, Search 0.72, Email 0.95} | Priors must come from real geo tests, not these defaults, in production. |
| True incremental | DGP β_c x̃_{c,t} | Only available here because the data are synthetic. |

```
share_c(F) = 100 * Credit_c(F) / Σ_j Credit_j(F)
MAE(F) = (1/4) Σ_c | share_c(F) − share_c(true) |
```

## Why calibrate Search down

Last-touch and uncalibrated MMM both like Search: it is always on, it correlates with demand, and it sits next to conversion. A geo holdout typically finds branded search incremental ROAS well below platform ROAS. The 0.72 factor is a stand-in for that experiment. TV is scaled 0.88 because long-adstock channels are easy to overfit to season.

## Incremental ROAS and +$10k

```
x_ss(s) = s / (1 − θ)
T(s)    = x_ss / (K + x_ss)
T'(s)   = K / (K + x_ss)²  *  1/(1−θ)

iROAS_c(s) = β̂_c * T'(s)
+$10k sales ≈ 10 * iROAS_c(s̄_c)
```
iROAS is evaluated at the channel’s historical mean spend (overview) and again at the recommended mix (investment page). Equimarginal allocation wants iROAS close across channels that are not on a bound.

## Investment allocation

```
Last-touch plan:  s_c ∝ platform touch share,  Σ s_c = B
Incremental plan: max_s  π(s, P=100)
                  s.t. Σ s_c = B,  8 ≤ s_c ≤ 80

Then: P* = arg max_{P ∈ [96,104]} π(s*, P)

Report:
  media lift  = π(s*, 100) − π(s_last, 100)
  price lift  = π(s*, P*) − π(s*, 100)
  total lift  = media lift + price lift
```
Same media dollars. The gain is reallocation plus a deliberate price stance. That is “improve investment allocation” for spend and pricing together.

## How to estimate this on real data

- Keep the funnel 2SLS model for mediated TOFU. Use ads + price + holiday on this page for the attribution bake-off finance will actually argue about.
- Last-touch and MTA come from your existing pathing table (GA4, Adobe, or a warehouse last-non-direct). Do not rebuild them inside the MMM mart.
- Fit the incremental MMM on mart_mmm_weekly with price_index required, not optional.
- Register geo-lift / matched-market tests in fact_experiment. Those posteriors replace the 0.88 / 0.72 defaults.
- Score frameworks every quarter: share MAE versus the calibrated MMM, not versus last-touch.
- Lock media bounds to ±30% of last year before SLSQP. Search price on a narrow band the pricing committee already owns.
- Never add incremental media sales to incremental price sales and also to promo lift from the trade model without a hierarchy: price/trade first, media on the residual, or a single stacked equation.

---

# Page: demand

Source: `projects/01_mmm_channel_optimization/development/templates/demand.html`

Demand trends 13-week trend + week-of-year season + residual, then seasonal naive versus Ridge ARX on the level. Ensemble by inverse holdout error. Horizon uses known calendar and frozen promo / price. Grow / Hold / Cut compares the next 13 weeks to the last 13 and to last year.

Click Run demand trends (156 weeks, 26 holdout, 13 horizon, seed 42). Pass if ensemble weighted absolute percent error beats naive, 80% coverage is near 80, the holdout line tracks holidays, and the planning table gate matches the year-over-year chart. Then open Demand diagnostics and name the week-80 level shift.

Naive wins: features are not helping. Coverage < 60% or Durbin–Watson far from 2: do not use the band for capacity. Promo residual very negative: do not raise intro-code depth. Mean-break nowhere near week 80: the scan is chasing a seasonal edge. Gate disagrees with year-over-year: do not lock volume.

Weeks Holdout weeks Horizon weeks Seed Run demand trends

### Weekly demand, trend, and fitted forecast

Black is observed national units (meal-kit-like Canada weekly boxes). Teal is the 13-week trend. Dashed is the Ridge ARX fit. The vertical cut is the holdout start. A trend that flattens while the fit still tracks holiday spikes is a mature category, not a broken model.

### Holdout actual versus ensemble

Last holdout weeks only, with an 80 percent residual band. Weighted absolute percent error is the planning miss. Coverage should sit near 80 percent if the residual scale is honest.

### Forward horizon with 80 and 90 percent bands

Calendar (holiday, payday, season) is known. Promo depth, price, and temperature stay at the last eight-week mean. Lock the plan at the solid line; size slots and inventory off the high band.

### Year-over-year percent

This week versus the same week last year. A run of negative bars after a detected level shift is a regime change, not a seasonal dip.

### Seasonal component (units)

Week-of-year mean of demand after the 13-week trend is removed. Winter / New Year high and midsummer low is the meal-kit pattern planted in the data generating process.

### Model bake-off on holdout

### Planning decisions

Residual forensics, anomalies, and driver weights are on Demand diagnostics. Formulas are on Demand methods.

---

# Page: demand diagnostics

Source: `projects/01_mmm_channel_optimization/development/templates/demand_diagnostics.html`

Demand diagnostics Same national series as Demand trends. Here you inspect what the decomposition could not explain: residual, standardized Ridge weights, last-26 vs prior-26 trend slope, price vs promo context, and |z| ≥ 2.5 anomaly weeks.

Load the last run (or run from Demand trends first). Pass if you can point to a mean-break near week 80, Durbin–Watson is reported, lag-1 residual correlation is not 1, and each anomaly row has a reason you could take to operations.

Holidays all flagged: seasonal term is too weak. Promo residual < −8 while quiet weeks are fine: depth is not delivering. Price step lines up with the mean break: treat it as a regime, not a new Fourier term. Acceleration negative after the break: the annual plan must not average through week 80.

### Residual after trend and season

What the 13-week trend plus week-of-year season did not explain. Clusters of negative residuals on deep-promo weeks mean the discount is papering over a soft trend. Isolated spikes are usually operations or weather.

### Standardized driver weights

Ridge coefficients on scaled features. Lag 1 and lag 52 will dominate a persistent series. The planning-relevant bars are price, promo depth, holiday, and the slow week trend.

### Trend slope: last 26 weeks versus the 26 before

Units per week on the extracted trend. Acceleration is recent slope minus prior slope. Negative acceleration after a level shift is the regime the annual plan must not average through.

### Price index versus promo depth

Context for the residual. A price step that lines up with the detected mean break is the usual X-like list-price reset, not a seasonal story.

### Anomaly weeks (|z| at least 2.5)

### Driver notes

The volume lock and Grow / Hold / Cut gates are on Demand trends. Formulas are on Demand methods.

---

# Page: demand methods

Source: `projects/01_mmm_channel_optimization/development/templates/demand_methods.html`

Demand methods Pipeline What is generated Decomposition Forecast Diagnostics Planning gates Production How to test

## Solving approach

- Build a national weekly demand series with trend, season, holiday, payday, promo depth, price, temperature, one mid-sample level shift, and two operational shocks.
- Decompose demand into a 13-week moving-average trend, a week-of-year seasonal, and a residual.
- Hold out the last 26 weeks. Nothing in the bake-off is fit on those weeks.
- Fit seasonal naive (same week-of-year mean) and Ridge ARX on the observed level.
- Blend the two models by inverse holdout root mean squared error.
- Project the next 4–26 weeks with known calendar and frozen commercial drivers.
- Run diagnostics: year-over-year, slope acceleration, Durbin–Watson, residual anomalies, a mean-break scan, holdout band coverage.
- Translate the forecast and the residual into Grow / Hold / Cut planning decisions.

## What is being forecasted

One national weekly series, meal-kit-like Canada box demand. Units, not media spend. The data generating process is additive so the decomposition has a ground truth.

```
Y_t = trend_t + season_t + 48 holiday_t + 18 payday_t
    + 310 promo_t − 4.2 (price_t − 100) − 2.4 (temp_t − 8)
    + level_shift_t + shock_t + ε_t

trend_t        = 980 + 1.15 t − 0.0018 t^2
season_t       = 220 [ 0.10 sin(2π (w−6)/52) + 0.04 sin(4π w/52) ]
level_shift_t  = −55 from week 80 (competitor / list-price reset)
holiday weeks  = New Year, Super Bowl, Canada Thanksgiving, Black Friday / Cyber Monday, Christmas
ε_t            ~ Normal(0, 22)

Two random shock weeks (stockout or weather) sit in the residual on purpose.
```

## Trend, season, residual

```
trend_t     = 13-week centered moving average of Y_t (ends padded)
detrended_t = Y_t − trend_t
season_w    = mean(detrended_t | week-of-year = w), then de-meaned
residual_t  = Y_t − trend_t − season_{w(t)}
yoy_t       = Y_t / Y_{t−52} − 1   for t > 52
```
This is a classical additive decomposition, not a full seasonal-trend loess. It is enough to tell planning whether a miss is trend, calendar, or a one-week shock. Campaign identifiers never enter.

## Forecast models

```
Seasonal naive
  Ŷ_t = mean( Y_s | week-of-year(s) = week-of-year(t) ) on the training window

Ridge ARX (α = 2.5) on standardized features
  Y_t ~ lag_1 + lag_52 + week + sin1 + cos1 + sin2 + cos2
        + holiday + payday + promo_depth + price_index + temperature

Ensemble
  Ŷ = (w_naive * naive + w_ridge * ridge) / (w_naive + w_ridge)
  w = 1 / holdout RMSE

Horizon
  holiday, payday, Fourier: known calendar
  promo, price, temperature: last 8-week mean (or same week-of-year temperature)
  lag_1 walks forward on predicted values
  80% band = Ŷ ± 1.28 σ    90% band = Ŷ ± 1.64 σ
  σ widens 4% per horizon step
```
Weighted absolute percent error is the planning metric (total absolute error over total units). Mean absolute percentage error is shown but is not how volume is locked.

## Diagnostic analytics

| Diagnostic | What it answers | Planning use |
| --- | --- | --- |
| Year-over-year, last 26 versus prior 26 | Is growth slowing after the level shift? | Do not lock last year’s quarter if recent year-over-year has flipped. |
| Trend slope, last 26 versus prior 26 | Acceleration of the extracted trend. | Grow / Hold / Cut on the outlook. |
| Durbin–Watson on the residual | Leftover weekly correlation after trend and season. | If far from 2, the holdout band is too tight. |
| Lag-1 autocorrelation | Same question, one number. | Confirms whether Ridge needed the lag_1 term. |
| Mean-break scan | Week that maximizes a two-sample mean gap. | Treat that week as a new regime. The data generating process plants one near week 80. |
| Anomaly /z/ ≥ 2.5 | Which weeks the decomposition cannot explain. | Investigate operations before adding a new seasonal term. |
| Promo-week versus quiet residual | Is depth delivering? | If promo residuals are negative, do not raise intro codes to “fix” a soft trend. |
| Holdout 80% coverage | Is σ honest? | Capacity uses the band only if coverage is near 80%. |

## Planning gates

```
gap% = 100 * (mean Ŷ_{T+1..T+H} − mean Y_{T−12..T}) / mean Y_{T−12..T}

Grow  if gap% ≥ 3 and recent trend slope > 0.15
Cut   if gap% ≤ −3 or recent trend slope  1.12 × last-13 mean → pre-book fulfillment
  otherwise do not add a shift
```
Gates are planning language, not media Ship / Watch / Kill. A Cut means “do not lock last year’s volume,” not “kill the brand.”

## Production

- Replace the data generating process with gold.mart_mmm_weekly at geo_key = 0. Use sales_Y or a units column finance signs. Same Monday week grain as the marketing mix.
- Keep holiday and payday from dim_date. Keep promo depth, price index, and temperature from fact_ops / fact_macro.
- Do not feed campaign identifiers or Google conversion value into this model.
- Refit weekly after the Monday gold build. Do not refit daily — the grain is weekly.
- Persist the outlook, the horizon band, and the anomaly list on gold.model_run_log so finance can restore last week’s lock.
Demand forecast (trade allocation) still answers where to place temporary price reduction dollars. This page answers what volume next quarter should lock, and why last quarter missed.

## How to test and diagnose (this suite)

- On Demand trends, run seed 42. Record holdout weighted absolute percent error, 80% coverage, outlook gate, and the horizon vs last-13 gap.
- Confirm the ensemble beats seasonal naive. If it does not, Ridge features are not identified — do not lock the horizon.
- On Demand diagnostics, find the mean-break week (planted near 80) and list |z| ≥ 2.5 weeks with a named cause.
- If promo-week residual is below −8, refuse a deeper intro-code plan. If Durbin–Watson is far from 2, refuse the capacity band.
- Change only the seed or only the horizon and re-run. If the gate flips with no story in year-over-year, the lock is not stable.
The same three-step write-up for every site tab is on MMM studio → 5. Model, test, diagnose.

---

# Page: forecast

Source: `projects/01_mmm_channel_optimization/development/templates/forecast.html`

Demand forecast Seasonal naive versus Ridge ARX on log units (price, holiday, payday, TPR, feature, display). Inverse-RMSE ensemble. Channel ordinary least squares reads promo lifts used on Trade allocation.

Click Run forecast (156 weeks, 26 holdout, $180k trade). Pass if ensemble weighted absolute percent error beats naive and the holdout line catches TPR / feature spikes. Then open Trade allocation: optimized profit should beat an equal split.

Naive wins: not enough promo variation. Misses only on feature weeks: the feature flag is weak. High lift but low recommended spend: margin is thin — that is correct. National volume lock is on Demand trends, not this page.

Weeks Holdout weeks Weekly trade budget ($k) Seed Run forecast

### National units: actual vs promo-aware forecast

Black is summed units across Grocery, Mass, Drug, Club, and E-comm. Teal is the Ridge ARX forecast. The cut is the holdout start. Spikes that both lines catch are usually holiday + TPR. A miss on a feature week means the promo coefficients are weak.

### Holdout actual vs ensemble

Last 26 weeks only. WAPE is the planning metric: total absolute error over total units. Finance uses this more than MAPE on small Drug weeks.

### Model bake-off (holdout WAPE)

Lower is better. Seasonal naive copies last year. Ridge ARX sees this year’s promo calendar. Ensemble blends them by inverse RMSE so a weak model cannot dominate.

### Promo vs non-promo average units

Observed lift when TPR is above 8%. This is descriptive, not causal. The structural model on the allocation page is the one used to spend money.

### Weekly trade spend ($k)

What the simulated retailer already spent. The allocation page asks whether that envelope should move toward Drug/E-comm or stay in Mass/Grocery.

### Holdout accuracy by channel

### Observed promo lift

Recommended trade mix is on Trade allocation. Formulas are on Forecast methods.

---

# Page: forecast allocation

Source: `projects/01_mmm_channel_optimization/development/templates/forecast_allocation.html`

Trade allocation

### Weekly trade $k: equal vs optimized

Rust is an even split. Navy is the optimizer. Both sum to the same weekly budget. A shift out of Mass into Drug or E-comm usually means Mass is already on the flat part of its Hill curve, or its margin cannot pay for the TPR.

### Trade ROI by channel at the optimized mix

ROI = (incremental units × $4.20 × channel margin) / trade $. Below 1.0 the last dollar of trade does not earn its keep. Efficiency is incremental units per trade dollar — volume planners use that; finance uses ROI.

### Recovered promo coefficients vs truth

Because this is synthetic we know the DGP lifts. Close grouped bars mean the log-demand regression separated TPR, feature, and display. A miss on display in E-comm is expected: that tactic barely exists online.

### Incremental units over the horizon

Optimized vs equal, same spend. This is the planning number that goes into the promo calendar: extra cases, not extra revenue from list-price fiction.

### Optimized plan

### Equal-split plan

---

# Page: forecast methods

Source: `projects/01_mmm_channel_optimization/development/templates/forecast_methods.html`

Forecast methods Pipeline Demand DGP Forecast models Promo lift Allocation Metrics Production

## Solving approach

- Build a weekly panel: channel × week of units, list-price index, TPR depth, feature, display, holiday, payday.
- Hold out the last 26 weeks. Nothing in the bake-off is fit on those weeks.
- Fit seasonal naive (same week-of-year mean) and Ridge ARX on log units.
- Fit a channel-level OLS on log units to read TPR, feature, display, and price elasticity.
- Blend naive and Ridge by inverse holdout RMSE.
- Turn lift coefficients + Hill saturation into a weekly trade-response curve per channel.
- SLSQP reallocates the weekly trade budget. Score both plans on incremental margin minus trade cost.

## What is being forecasted

Five trade channels, not media channels: Grocery, Mass, Drug, Club, E-comm. Units follow a log-linear demand system with channel-specific price elasticity and promo lifts.

```
log U_{c,t} = α_c + γ t + season_t + δ_hol holiday_t + δ_pay payday_t
             + β_c^price log(P_{c,t}/100)
             + β_c^tpr TPR_{c,t}
             + β_c^feat Feature_{c,t}
             + β_c^disp Display_{c,t}
             + ε_{c,t}

True lifts used in the DGP
  Grocery   TPR 1.45   Feature 0.28   Display 0.22   ε_price −1.15
  Mass      TPR 1.70   Feature 0.20   Display 0.18   ε_price −1.40
  Drug      TPR 1.10   Feature 0.34   Display 0.26   ε_price −0.85
  Club      TPR 0.85   Feature 0.16   Display 0.30   ε_price −0.70
  E-comm    TPR 1.95   Feature 0.40   Display 0.08   ε_price −1.55

A TPR of 0.20 in Grocery multiplies units by e^{1.45×0.20} ≈ 1.34 (about +34%).
```

## Forecast models

### 1. Seasonal naive

```
Û_{c,t} = mean{ U_{c,s} : s < split, s mod 52 = t mod 52 }
```
This is the plan many category teams still use: “same week last year.” It is the accuracy floor. Beating it is the first test that promo information is worth the meeting.

### 2. Ridge ARX (promo-aware)

```
log U = Xθ + e
X = [t, sin52, cos52, sin26, cos26, log(P/100), holiday, payday,
     TPR, feature, display, channel dummies]

θ̂ = arg min_θ ||y − Zθ||² + 1.5 ||θ||²
Z = StandardScaler(X)
Û = exp(Zθ̂)
```

### 3. Ensemble

```
w_m = 1 / RMSE_m^{holdout}
Û_ens = (w_naive Û_naive + w_ridge Û_ridge) / (w_naive + w_ridge)
```

### 4. Channel OLS (used for allocation, not the line chart)

```
For each channel c, OLS on train:
  log U_{c,t} = α + γt + sin + cos + hol + payday + β_p log P
              + β_tpr TPR + β_feat Feature + β_disp Display
```
This is the interpretable lift model. Ridge is better at holdout tracking because it shares seasonality across channels. OLS is better at telling a buyer why Drug display is worth the fee.

## From coefficients to a promo plan

```
Approximate weekly incremental units at trade spend s_c:

depth  = clip(0.60 s_c / cost_of_a_point_of_TPR, 0, 0.40)
feat   = clip(0.25 s_c / feature_fee, 0, 1)
disp   = clip(0.15 s_c / display_fee, 0, 1)

raw_lift = β_tpr depth + β_feat feat + β_disp disp
sat      = s_c / (K_c + s_c)          # Hill, s = 1
ΔU_c(s)  = base_c * max(raw_lift, 0) * sat * 1.15
```
The 60/25/15 split is the default tactic mix inside a trade dollar. K_c is a channel saturation constant (Mass saturates later than Drug). Changing the mix is a buyer decision; the optimizer moves the dollar envelope first.

## Trade allocation (SLSQP)

```
max_s   Σ_c [ H * ΔU_c(s_c) * 4.20 * margin_c  −  H * s_c ]

s.t.    Σ_c s_c = B          weekly trade budget ($k)
        4 ≤ s_c ≤ 0.55 B     no channel is starved or given the whole bag

H = horizon weeks (the holdout length on this site)
4.20 = contribution $ per unit before channel margin
Equal-split twin: s_c = B / 5

Profit lift = π(s*) − π(s_equal)   same B, different mix
```
This is how investment efficiency shows up: not more trade money, a different channel split. ROI_c = (H ΔU_c 4.20 margin_c) / (H s_c). Efficiency_c = ΔU_c / s_c.

## How we know the forecast is good enough to spend against

| Metric | Formula | Planning use |
| --- | --- | --- |
| WAPE | Σ/U − Û/ / Σ/U/ | National volume miss. Target under ~8% on this DGP. |
| MAPE | mean /U − Û/ / /U/ | Punishes Drug/Club. Use with WAPE, not alone. |
| RMSE | sqrt(mean error²) | Ensemble weights. |
| Bias | mean(Û − U) | Positive = overbuy. Dangerous for supply. |
| Holdout R² | 1 − SS_res/SS_tot | Did we beat a flat line on unseen weeks? |
| Profit lift | π_opt − π_equal | The only number that justifies moving the trade lock. |

## How to estimate this on real shipments

- Grain: week × banner or channel × item (or item cluster). Units = shipments or POS, pick one and keep it.
- Promo file: TPR depth from invoice/scan, feature/display from retailer recap or Circana. Do not use “any discount” as TPR.
- Fit the log-demand OLS by channel (or store cluster). Keep price in the model or TPR will steal the everyday-price story.
- Bake off against seasonal naive and last year’s locked calendar on a rolling 13-week origin, not one lucky holdout.
- Feed the lift curves into the allocator with this year’s trade budget and each banner’s fee card (feature and display are not free).
- Constraint the solver to retailer contracts (min feature weeks, Club shipper commitments) before you show a “optimal” mix.
- Join to MMM: media creates the baseline the trade plan harvests. Do not double-count a holiday TV flight as trade lift.
MMM asks what national media did to sales. CLV asks which buyers that media created. This page asks where the next trade dollar should go so the promo calendar is not an even split across banners.

---

# Page: index

Source: `projects/01_mmm_channel_optimization/development/templates/index.html`

### Funnel MMM Studio Concepts: what this model is doing Marketing Mix Model (MMM)

MMM estimates how each media channel contributed to sales over time. It does not use cookies or last-click paths. It uses weekly spend, carryover, saturation, and a sales equation.

### The funnel

TOFU (TV, OOH) creates demand. It raises brand-search intent, but does not sell directly. MOFU (Social, YouTube) both creates intent and converts some of it. BOFU (Paid Search) harvests people who already intend to buy. If TOFU is starved, BOFU hits a wall.

### Adstock decay

Advertising memory fades. A value near 0.65 means last week’s TV still matters a lot. A value near 0.08 means search dies almost immediately. That is why awareness channels need a longer memory than harvesting channels.

### Hill K (saturation)

Each extra dollar returns less than the last. Hill K is the spend level where the channel is at half of its maximum effect. Pushing far above K wastes budget on the flat part of the curve.

### Alpha and beta

Alpha is how strongly a channel lifts the intent pool M (brand search). Beta is the direct effect on sales Y. TOFU has alpha only. BOFU has beta only. MOFU has both. Beta_M is how much one unit of intent turns into sales.

### 2SLS (two-stage least squares)

Stage 1 predicts intent from TOFU/MOFU. Stage 2 predicts sales from that fitted intent plus MOFU/BOFU. Using fitted intent, not raw search volume, stops the model from giving harvest media credit for demand that awareness already created.

### Direct vs indirect sales

Direct is sales from the channel’s own beta. Indirect is sales that traveled through intent: alpha × beta_M. TV can show $0 direct and still be the largest total contributor.

### Naive vs funnel-aware budget

The naive optimizer only sees direct betas, so it piles money into search. The funnel-aware optimizer also values the intent that TOFU creates. Both mixes spend the same weekly budget. The lift is reallocation, not more spend.

### mROI

Marginal ROI is the extra sales from one more $1k on that channel, at the recommended mix. Direct + indirect = total. A healthy optimum equalizes total mROI across channels. Below 1.0 means the last dollar returned less than it cost.

### Holdout R² and MAPE

The last 20% of weeks are never used to fit. R² is variance explained on those weeks (1.0 is a perfect track). MAPE is average percent miss. High in-sample fit can still be a bad incrementality model; holdout is the first sanity check.

### Coefficient recovery

Because this studio uses synthetic data, we know the true alphas and betas. Estimated vs true tells you whether 2SLS recovered the structure. MOFU split (direct vs mediated) is the hardest piece to identify.

### Controls on this page

Weekly budget is the $k envelope the optimizer must spend. Weeks is the length of the simulated history. Seed fixes the random draws so a rerun is identical. Min/max $k are trust-region bounds so the solver cannot invent spend levels you never observed.

### Real-world controls

Sales move for reasons that are not ads. The engine now simulates and estimates holiday, payday, promo depth, price vs 100, stockouts, competitor share of voice, unemployment, CPI YoY, and temperature. Dropping them would leak into media betas (omitted-variable bias).

Adstock + Hill, then two-stage least squares: stage 1 predicts intent M from top/mid-funnel spend; stage 2 predicts sales Y from fitted intent and mid/bottom-funnel spend. Sequential Least Squares Programming reallocates a fixed weekly budget. Naive mix ignores the mediator; funnel mix does not.

Click Run model (208 weeks, seed 42, $160k). Holdout is the last 20% of weeks. Pass if holdout fit tracks holidays, funnel mix shrinks Paid Search versus naive, and TV can show $0 direct but large total. Then open tab 5 for the pass/fail table.

Durbin–Watson far from 2: leftover weekly correlation. High variance inflation on search + intent: harvest bias. Funnel mix = naive mix: mediator not identified. Search still huge: Y is a platform conversion or M includes paid clicks. Full diagnosis for every tab is on tab 5.

Weekly budget ($k) Weeks Seed Reset default mix Run model

## Every attribute on this page

These are the inputs on the run bar and on each channel card. Hover a field for a short tip. This table is the full meaning, including what is DGP-only (shapes the fake history) versus what the optimizer reads. Symbols match tab 3.

Run bar Name and funnel Decay and Hill K Alpha and beta Spend and bounds Holiday and flighting

### Run bar (applies to the whole mix)

| Attribute | What it is | Typical value here | If you change it |
| --- | --- | --- | --- |
| Weekly budget (B) | The $k envelope SLSQP must spend: every recommended mix sums to this. It is not annual plan dollars and not a request for more media. | 160 | Raise it and both naive and funnel mixes scale up inside min/max. If the sum of mins exceeds B, the run fails. If the sum of maxes is below B, the run also fails. |
| Weeks (N) | Length of the synthetic panel. First 80% is train; last 20% is holdout. One row is one week. | 208 (4 years) | Shorter history → noisier alphas/betas and a weaker holdout. Floor is 80. Production replaces this with however many weeks are in mart_mmm_weekly. |
| Seed | Fixes the random draws (spend noise, controls, residuals) so a rerun with the same cards is identical. | 42 | A new seed is a new fake retailer, not a new model. Use it only to see whether a result was a lucky draw. |
| Reset default mix | Reloads TV, Radio, Social, Paid Search with the blueprint numbers. | — | Discards card edits. Does not run the model. |
| Run model | Builds the panel, transforms spend, fits 2SLS, scores holdout, then runs naive and funnel SLSQP. See tab 3 for the seven steps. | — | Results below replace the last run. Nothing is saved to a warehouse from this laptop studio. |

### Channel identity

| Attribute | What it is | What it is not | If you change it |
| --- | --- | --- | --- |
| Name | Label for this card (TV, Radio, Social, Paid Search, or anything you add). Must be unique. The engine slugs it to an id. | Not a campaign name from Google Ads. In production, 200 campaigns collapse to a few parent names via dim_channel. | Rename only. It does not change decay, alpha, or funnel role. |
| Funnel (TOFU / MOFU / BOFU) | Which equation the channel is allowed into. TOFU: alpha only (raises M). MOFU: alpha and beta. BOFU: beta only (harvests M). | Not a Google/Meta “campaign objective.” It is a structural exclusion: who may create demand vs who may sell. | Set by which lane you add the card to. TOFU beta is forced to 0; BOFU alpha is forced to 0. You need at least one TOFU or MOFU so M can move. |

### Transforms (applied to spend before 2SLS)

| Attribute | Symbol | What it is | Typical | If you change it |
| --- | --- | --- | --- | --- |
| Adstock decay | θ | Share of last week’s advertising stock that is still alive: A_t = spend_t + θ A_{t−1}. High = long memory (TV). Low = dies in days (search). Half-life ≈ ln(0.5)/ln(θ) weeks. Clamped 0.01–0.95. | TV 0.65; Radio 0.45; Social 0.25; Search 0.08 | In the studio this is a known DGP truth and the estimator uses the same value. Raising TV θ makes one flight linger into later weeks (more leftover demand for search to harvest). In production you would estimate θ, not type it. |
| Hill K | K | Half-saturation of the Hill curve. At adstock A = K the channel is at 50% of its max effect. Higher K = saturates later (you can spend more before the curve flattens). Must be positive. Not a budget cap. | TV 75; Radio 35; Social 40; Search 45 | Lower K and the same mean spend sits further right on the curve (flat, low mROI). That is why the funnel optimizer often pulls search back: default search already lives near K. Production estimates K with θ. |

### Structural effects (true DGP coefficients on this card)

| Attribute | Symbol | What it is | Typical | If you change it |
| --- | --- | --- | --- | --- |
| Intent alpha | α | How much one unit of transformed spend x̃ raises the intent pool M. Shown on TOFU and MOFU only. BOFU is forced to 0 — search does not create the pool; it spends it. Units: intent per unit x̃. | TV 280; Radio 140; Social 85 | This is the true alpha used to simulate history. 2SLS then tries to recover it (see “estimated vs true”). Bigger TV alpha → more indirect sales and more reason for the funnel mix to fund TOFU. Hidden on BOFU cards. |
| Direct beta | β | How much one unit of x̃ raises sales Y without going through M. Shown on MOFU and BOFU only. TOFU is forced to 0 — TV does not ring the register by itself in this structure. Units: $k sales per unit x̃. | Social 110; Search 320 | True DGP beta. A huge search beta is why the naive optimizer piles money into BOFU. Hidden on TOFU cards. MOFU having both α and β is the hardest split to recover. |

β_M (intent-to-sales) is not a card field. It is a single number for the whole market, recovered in Stage 2. TOFU only pays off if β_M is positive. See tab 3.

### Spend level and optimizer bounds

| Attribute | Symbol | What it is | Typical | If you change it |
| --- | --- | --- | --- | --- |
| Mean spend $k | x̄ | Average weekly dollars ($ thousands) used to generate the fake spend series. TOFU then gets lumpy flighting around this mean; MOFU/BOFU spend every week with noise. Must be positive. | TV 48; Radio 21; Social 35; Search 43 | This is history, not the recommendation. The optimizer may leave this mean. Raising it moves the Hill operating point (marker on the saturation chart) and changes how much leftover adstock exists. |
| Min $k | L | Trust-region lower bound. SLSQP cannot recommend less than this, even if mROI is poor. Stops the solver from shutting a channel you would never actually zero. Must be ≥ 0.5. | TV 10; Radio 5; Social 10; Search 15 | Sum of mins must be ≤ weekly budget. Tight mins freeze a bad historical mix. Loose mins let the funnel plan cut search harder. |
| Max $k | U | Trust-region upper bound. SLSQP cannot recommend more than this. Stops Hill-curve extrapolation into spend you never observed. Must exceed min. | TV 80; Radio 40; Social 60; Search 75 | Sum of maxes must be ≥ weekly budget. If TV’s total mROI stays high after the run, this max is binding — that is a trust-region result, not a solver bug. Do not open U to 5× history just to “let it optimize.” |

### Holiday uplift and TOFU flighting (DGP only)

These fields shape the fake history so it looks like real media (everyone ramps at Christmas; TV is bought in flights). The estimator does not treat them as coefficients. They are why holiday and TV are not the same column.

| Attribute | What it is | Typical | If you change it |
| --- | --- | --- | --- |
| Holiday uplift | Fractional extra spend in holiday weeks (studio: roughly weeks 47–1). 0.25 means holiday-week spend is about 25% above that channel’s non-holiday level. Creates the real-world pile-up of media on Christmas. Must be ≥ 0. | TV 0.25; Radio 0; Social 0.35; Search 0.45 | Set everyone to 0 and holiday sales are easier to separate from media (less realistic, prettier coefficients). Set everyone high and holiday + TV + search become collinear — VIF rises, control recovery gets worse. That is the identification lesson. |
| Flight on wks (TOFU only) | How many weeks the channel is “on air” inside each cycle. 4 means a month-long burst. 0 with cycle 1 would be always-on (not used for default TOFU). | TV 4; Radio 3 | Lumpy flighting is what identifies a long-memory channel separately from smooth seasonality. Always-on TV looks like the Fourier season term and alpha recovery suffers. |
| Flight cycle (TOFU only) | Length of the on/off pattern in weeks. TV 4 on / cycle 8 = on a month, off a month. Radio 3 on / cycle 6 = on half the time, shorter bursts. | TV 8; Radio 6 | Must be ≥ 1. On-weeks cannot exceed the cycle. MOFU/BOFU are always-on (cycle 1, on 0 treated as always-on in the DGP) because search and social are not bought as TV flights. |

Production mapping: mean spend, decay, and K become estimated or historical facts, not typed truths. Alpha and beta become Stage-1 / Stage-2 outputs, not inputs. Holiday uplift and flighting disappear — the warehouse already has the actualized weekly spend series. Min/max stay as the finance trust region (~±30% of last year).

## Results

These numbers are from the mix you just ran. Read the headline interpretation first, then each block.

### Direct vs indirect attribution ($k)

Stacked bars are historical sales credited to each channel over the full sample. Navy is sales the channel booked itself. Teal is sales that arrived later through brand search intent. A tall teal bar on TV or Radio is the point of this model: those channels look worthless in last-click reports.

### Naive vs funnel-aware weekly mix ($k)

Rust is the harvest-only plan. Navy is the funnel plan. Both sum to your weekly budget. If rust is piled on Paid Search and navy moves money to TOFU, the engine is correcting the search-bias trap.

### Holdout sales fit

Black is actual sales in the last 20% of weeks. Amber is the 2SLS forecast, using only coefficients learned on earlier weeks. If the two lines track, the system generalizes. If they diverge on holidays or flights, the model is missing a baseline or a lag.

### Full-sample sales vs fitted

Navy is actual weekly sales. Teal is the Stage-2 fitted value (train) plus holdout prediction. The dashed line is the train/holdout cut. Spikes that both lines catch are usually holiday + promo. Spikes only in black are leftover residual (noise or a missing shock).

### Weekly contribution stack ($k)

Stage-2 decomposition of predicted sales. Calendar is trend/season/holiday/payday/temperature. Commercial is promo, price, and stockouts. Competitive/macro is competitor SOV, unemployment, and CPI. Intent is the mediated funnel (M-hat). Direct media is MOFU/BOFU Hill exposures. Residual is actual minus predicted.

### Control mean weekly contribution ($k)

Average Stage-2 term for each control: estimated beta times the mean of that series. Negative bars are expected for price, stockouts, competitor SOV, unemployment, and CPI. Those are the demand leaks media cannot buy back.

### Control recovery (true vs estimated)

Because this is synthetic, we know the DGP betas. Close grouped bars mean 2SLS separated media from the baseline. A large miss on promo or holiday usually means those weeks also stacked media spend (collinearity).

### Real-world controls (z-scored overlay)

Each series is centered and scaled so different units can share one axis. Holiday and payday are 0/1 pulses. Price, CPI, and unemployment wander like macro series. Stockouts and promo jump with Q4. This is the variation that identifies control betas separately from TV flights.

### Hill saturation curves

Response vs adstock, expressed in units of each channel's K. The marker is the historical mean operating point. Left of 1.0 is the steep region (more budget still pays). Right of 1.5 is the flat region (diminishing returns).

### Stage-2 residuals over time

Train residuals from the sales equation. A random band around zero is healthy. Waves at lag 52 mean leftover seasonality. Clusters on holiday weeks mean the holiday dummy is too crude (add promo depth or a second dummy).

### Variance inflation (VIF)

VIF above 10 flags collinearity. High VIF on two social variants or on holiday + promo is a warning, not a crash: coefficients get noisy, mROI ranking can flip. Ridge or combining channels is the usual fix. See tab 3 for the formula.

### Attribution table

Same split as the stacked chart, in dollars. Indirect share of 100% means the channel only works through intent. 0% means it only harvests. MOFU should sit in between.

### Budget allocation table

Naive $k ignores awareness. Funnel $k includes it. Shift is funnel minus naive. Positive shift on TOFU and negative shift on BOFU is the usual correction.

### Chain-rule mROI at the funnel mix

Total mROI = direct dY/dx + (dY/dM) x (dM/dx). That is the extra weekly sales from one more $1k, evaluated at the funnel-aware spend. The optimizer tries to equalize total mROI so the last dollar is equally hard-working everywhere.

### Coefficient recovery

True is the number we used to generate the fake history. Estimated is what 2SLS recovered. A small abs error on TOFU alpha and on beta_M means the mediator was identified. A large error on MOFU direct beta is common: that channel appears in both stages.

### Real-world control coefficients

Intent-stage rows are alphas on M. Sales-stage rows are betas on Y. True values are the DGP (holiday +95 $k, promo +240 per unit depth, price -32 per index point, stockout -480, competitor SOV -210, unemployment -22, CPI -14, temperature +1.6, payday +28). Mean contribution is estimated beta times the average of that control.

### Sales-equation contribution totals

Sum of each Stage-2 term over the full sample. Use this to see whether baseline (intercept + calendar + commercial + macro) still dominates media, which is the usual real-world pattern.

X case Questions Data sources Source fields Field dictionary Into the warehouse Architecture Data model MMM weekly mart Source → MMM flow Quality and governance Azure / AWS path

## X Canada — the complete MMM case

Who they are Why MMM Y — boxes and revenue M — brand search Funnel and channels X controls Questions this model answers Full data map Dim and fact fields First source only How to use this studio

### Who X is (in this case)

X is a meal-kit subscription. A household picks a weekly plan (2–6+ meals, 2–4 people), chooses recipes, and receives a refrigerated box of pre-portioned ingredients. Canada is a distinct P&L: CAD pricing, Ontario/BC/Quebec delivery footprints, biweekly pay culture, and rivals that are not the US set (Goodfood, Chef’s Plate — which X owns — Factor, grocery meal kits, Uber Eats).

Two revenue engines sit in every week, and MMM must not mix them up:

- Acquisition. A new customer takes the first-box discount (often 40–60% off, free shipping) and becomes a subscriber. This is what TV, YouTube, Meta, and generic search are for.
- Retention / repeat boxes. An existing subscriber does not skip, pause, or cancel, and the box ships. This is mostly product, menu, price, and service — not last-click search. Media still matters at the margin (brand reminders, win-back), but most repeat $ is baseline.
If you put “Google box-order conversions” in as Y, you mostly measure discounted first boxes that search harvested. You will over-fund branded search and starve the TV that created the subscriber. That is the search-bias trap with X numbers on it.

### Why X needs a funnel MMM

### What last-click tells them

A person sees a Super Bowl or CTV spot, Googles “x”, clicks the brand ad, orders. Google Ads and GA4 give 100% of that box to Paid Search. TV looks like $0. Finance cuts the brand budget. Next quarter, branded query volume falls and search CPA rises. The harvest channel was never the demand.

### What this engine is for

Stage 1: did TV / YouTube / Meta raise organic “x” search (M)? Stage 2: given that intent, how many net boxes and how much net revenue (Y) did search, PMax, and the offer actually convert? SLSQP then reallocates a fixed weekly CAD envelope so TOFU is not starved.

### Y — what “sales” means at X

Pick one and freeze it with finance. Do not switch mid-year.

| Candidate Y | What it is | Use it when | Do not use |
| --- | --- | --- | --- |
| Net box revenue (default) | Shipped boxes this week × price paid, minus credits, refunds, failed payments, and cancelled-after-cutoff. CAD. Includes new and repeat. | Finance wants “what media moved the P&L.” | Gross before credits. Google conversion_value. First-box only if you still count the discount as full price. |
| New subscribers | Count (or revenue) of first paid boxes from customers with no ship in the last 12 months. | The CMO question is “cheap new customers,” and you will run a second model for repeat. | As the only Y. You will ignore the repeat base that pays for the company. |
| Contribution margin | Net revenue − food − packaging − last-mile − payment fees. First-box margin is often near zero or negative because of the intro discount. | The board cares about unit economics, not vanity orders. | If food cost and last-mile are not stable week to week in the extract. |

Source: X order / subscription ledger (their own platform or SAP), not Shopify-as-marketing. Grain: ship-week (when the box left the DC), not click-week. A Sunday click that ships next Wednesday belongs to next week’s Y. That is how operations books it.

### M — X intent

M is organic branded demand: people already looking for X this week. Source: Google Search Console queries that match a brand dictionary, summed to Canada-week.

| Keep in M | Leave out of M |
| --- | --- |
| x, x canada, x login, x recipes, chef’s plate (if that brand is in the same P&L and you have chosen to pool) | Paid branded clicks from Google Ads (that is BOFU delivery). “meal kit”, “dinner box”, “healthy meals delivered” (category demand — optional later as a second mediator, not M). |

If GSC history is short, Google Trends for “x” in Canada (weekly, 0–100) is the fallback. Do not splice Trends and GSC into one column without documenting the splice.

### X funnel → studio channels

Map X media onto the three lanes. Names on the cards can stay TV / Social / Paid Search; the taxonomy behind them is X-specific.

| Funnel | X channels | Role | Studio card | Typical θ / K intuition |
| --- | --- | --- | --- | --- |
| TOFU | Linear TV, CTV / streaming, radio, OOH (transit, grocery), podcasts | Creates “I should try a meal kit / I should come back to X.” Does not take the order. Alpha only. | TV, Radio, OOH | Long memory (θ ~ 0.5–0.7). Flights, not always-on. High holiday uplift around Super Bowl, January “new year diet,” and Q4 gifting. |
| MOFU | YouTube, Meta / Instagram, TikTok, influencers, email to prospects | Shows the box, the recipes, the 40% off. Raises brand search and some people convert in-feed. Alpha and beta. | Social, YouTube | θ ~ 0.2–0.35. Always-on with creative bursts. First-box offer creative is not a separate channel — it is the promo control. |
| BOFU | Google Brand Search, Generic Search, Shopping, Performance Max, Microsoft Ads, affiliates, retargeting | Harvests people who already want X. Beta only. Last-click hero. Alpha forced to 0. | Paid Search | θ ~ 0.08. Lives near Hill K (saturated brand terms). Funnel SLSQP usually pulls $ off brand search toward YouTube/TV. |

Owned email to existing subscribers is retention, not media mix — put win-back email in MOFU only if you have a prospect/lapsed file and a spend or send-cost. Push notifications to current boxes do not belong in this MMM.

### X controls (the non-media week)

A X week moves when the menu is good, the first-box code is 60% off, payday hits, or Goodfood is on TV. Those are controls, not channels.

| Control | X meaning | How you build it | If you omit it |
| --- | --- | --- | --- |
| Holiday dummy | Weeks people reset habits or gift food: New Year, Super Bowl, Easter, Thanksgiving CA, BFCM, Christmas. Also “skip weeks” around travel (late Dec, summer long weekends) — those can be a second dummy if the first is only peaks. | Retail calendar, not only statutory holidays. 0/1 on dim_date. | January TV and January sign-ups become the same story. You will say TV “worked” when it was New Year. |
| Payday dummy | Biweekly pay Friday. Meal-kit sign-up and un-pause cluster after payday; skips cluster before the next rent week. | Every-other-Friday Canada payroll calendar. | Search CPA looks better on pay weeks. You will over-fund search. |
| Promo depth | The intro code and site-wide offer: 40% / 50% / 60% off first box, free breakfast, free shipping. Average depth on new boxes that week, plus any win-back code on lapsed. | Promo calendar + order-level discount / list. 0.50 = 50% off. This is the offer, not the YouTube ad that showed it. | A 60% off week looks like a Meta win. |
| Price vs 100 | Everyday plan price (e.g. $12.49/serving) indexed to 100. Separate from the intro discount. Price rises and “meals from $X” copy change this, not the 50% code. | Plan catalog / PIM, volume-weighted by plan size. | A list-price increase looks like media stopped working. |
| Stockout rate | At X this is menu / capacity: sold-out recipes, delivery slots full, postal codes paused, DC labour shortages. People wanted a box and could not get one. | Share of visits or checkouts that hit “sold out” / no-slot, or 1 − fill rate of promised boxes. | A sold-out Sunday looks like search failed. |
| Competitor SOV | Goodfood, Factor, grocery kits, Uber Eats / Skip meal plans. Rival TV and paid social in Canada. | Pathmatics / Kantar / agency competitive. First mart: one national SOV is enough. | Goodfood’s Super Bowl spend becomes “X TV didn’t work.” |
| Unemployment, CPI | Meal kits are discretionary. When jobs or food-at-home inflation jump, people skip or go back to grocery. | StatsCan monthly, carried to weeks. | A recession quarter gets blamed on the media mix. |
| Temperature | Hot weeks: more “I don’t want to cook” (good for kits) but also more “I don’t want a box on the porch.” Cold / dark weeks: more cooking-at-home intent. | ERA5 or Environment Canada weekly mean for populated delivery geos, averaged to national. | A heat wave looks like a YouTube lift. |
| Trend / season | January diet peak, summer skip trough, September back-to-routine. Slow share of meal-kit category. | Computed from week_start. Do not make season do the holiday job. | Q1 growth becomes “we should spend more on search.” |

### Questions the X model is allowed to answer

- If the weekly Canada media budget stays $B, how much should move from Brand Search to YouTube / CTV so next quarter’s net boxes rise?
- If we cut linear TV $20k/week, how much branded GSC demand do we lose, and how much of that would search have harvested anyway?
- Is Brand Search already on the flat part of Hill (high spend, mROI < 1)? That is the usual X finding.
- Did a 60% intro code, not Meta, create last week’s new boxes?
- How much of Paid Search “ROAS” is leftover demand from a CTV flight two weeks ago?
This model should not answer: which recipe creative won on TikTok; whether one keyword should go exact; the LTV of a subscriber beyond what a separate CLV model already scores; what happens at 5× historical YouTube.

### Complete X data map

Same bronze → silver → gold → mart lane as the rest of the playbook. X systems in the source column.

| Mart column | X source | Silver rule | Engine |
| --- | --- | --- | --- |
| week_start | America/Toronto business calendar, Monday | Ship-week for Y; impression-week for media (document the one-day lag; do not mix) | t |
| geo_key | Canada national first. Later: ON / BC / Rest if volume supports it | Delivery postal → province. Do not model Yukon as a DMA. | Start at 0 = CA |
| spend_tv | Agency TV/CTV invoice + CM360 / The Trade Desk | Actualized CAD. Map IO names → TV. TOFU. | Stage 1 alpha |
| spend_social | Meta, TikTok, (optional) Pinterest | Ads API spend, not purchase value. MOFU. | Stage 1 + 2 |
| spend_youtube | Google Ads campaign_type = VIDEO (same account as search) | Split out of Google Ads. MOFU. Do not leave YouTube inside spend_search. | Stage 1 + 2 |
| spend_search | Google Ads Search + Shopping + PMax + Microsoft Ads | cost_micros/1e6. BOFU. Brand vs generic can stay one column at first. | Stage 2 beta |
| queries_M | GSC brand dictionary (x, x, …) | Organic clicks (or impressions). No paid branded clicks. | M |
| sales_Y | Order/subscription ledger: shipped boxes, credits, cancels | Net CAD on ship-week. New + repeat unless finance chose new-only. | Y |
| holiday, payday | HF retail calendar; Canada biweekly Friday | 0/1 | Controls |
| promo_depth | Intro/win-back code calendar + order discounts | discount / list on new (and win-back) boxes | Stage 2 |
| price_index | Plan price list ($/serving by plan size) | Index to 100 | Stage 2 |
| stockout_rate | Menu sell-outs, slot caps, paused FSAs | Failed checkouts / promised boxes | Stage 2 |
| competitor_sov | Pathmatics / agency: Goodfood, Factor, Uber Eats | 0–1 national | Stage 1 + 2 |
| unemployment, cpi_yoy, temperature | StatsCan + Environment Canada | Month carried to weeks; temp weekly | Stage 2 (temp also Stage 1) |

### First build: one media source only

If you implement only one media feed, it is still Google Ads (X Canada). Split it into Paid Search (BOFU) and YouTube (MOFU). TV and Meta wait. Y still has to come from the order ledger — that is not a second media source; without it there is no model.

| Google Ads field | X meaning | Silver rule | Mart column |
| --- | --- | --- | --- |
| customer_id | X Canada ads account (not every country MCC child). | Filter to the CA account only. | — |
| date | Delivery day in America/Toronto. | Local date → Monday week_start. | week_start |
| campaign_name / campaign_type | CA_Search_Brand, CA_Search_Generic, CA_PMax_Acquire, CA_YT_Demand. | Brand + Generic + Shopping + PMax → Paid Search. Video / YouTube → YouTube. | spend_search vs spend_youtube |
| cost_micros | What X paid Google that day, millionths of CAD. | spend_cad = cost_micros / 1e6. Already CAD. | the spend number |
| impressions | How often an X ad was shown. | Optional delivery. Not in 2SLS next to spend. | optional impressions_* |
| geo_target | Usually Canada; sometimes ON/BC bid modifiers. | Roll to geo_key = 0. | geo_key |
| conversions, conversion_value | Google’s “X box order” tag. | Drop. Not Y. | — |

```
X Google Ads (CA)
    → bronze_gads_x_ca
    → silver: spend_cad, Paid Search | YouTube, week_start, geo = CA
    → gold.fact_media_spend
    → mart.spend_search + spend_youtube
    → x̃ → 2SLS + SLSQP
X order ledger (required for Y, not a media source)
    → bronze_x_orders  (ship_ts, plan, list, paid, credit, cancel, new_vs_repeat)
    → silver: net_cad on ship-week
    → gold.fact_sales → mart.sales_Y
```

### How to drive this studio as X

- On tab 1, treat TV as linear + CTV, Social as Meta/TikTok, Paid Search as Brand + Generic + PMax. Add a YouTube MOFU card if you want it separate from Social.
- Set weekly budget B to an X Canada-sized envelope (the control is $k; e.g. 160 = $160k/week in the toy DGP, not their real number).
- Keep Brand Search min/max tight if legal/brand always bids — that is a real trust region, not a solver bug.
- Read indirect teal on TV/YouTube as “subscribers search later created.” If navy search is huge and teal TV is tiny after a run, you are looking at the naive world; compare the funnel mix.
- Promo depth in the DGP is the stand-in for a 40–60% first-box code. In production, put the real code calendar in fact_ops.
- Ship a mix only if holdout track is acceptable and Brand Search is Ship or an explicit Watch (geo test), not because Google ROAS looked good.

## Questions this analysis can answer

These are decision questions, not dashboard vanity metrics. The engine answers them only when spend, intent, sales, and baseline controls share the same week and geo grain.

### Budget and mix

- If the weekly media budget is fixed, how should we split it across TOFU, MOFU, and BOFU?
- If we cut TV by $20k/week, how much incremental sales do we lose after search has less intent to harvest?
- Where is each channel on its Hill curve — still in the steep region, or already saturated?
- What is the marginal ROI of the next $1k on each channel?

### Attribution and finance

- How much of Paid Search “success” is really leftover demand from TV, OOH, or Social?
- What is Radio’s total effect if last-click gives it $0?
- What share of sales is baseline (trend, season, holiday, promo) versus media?
- Did a reallocation raise revenue without raising spend?

### Planning and risk

- If we must stay inside ±30% of last year’s weekly spend, what is the best mix?
- Which channel’s incrementality is too unstable to trust without a geo test?
- How much holdout error should finance expect in the next quarter’s forecast?

### Questions this model should not answer alone

- Which keyword or creative won? (too granular; use experiments or MTA, not national weekly MMM)
- What is the ROI of a one-day flash sale? (need promo/price as controls, or a dedicated test)
- What did one user see before buying? (MMM is aggregate, not user-level)
- What will happen at 5× historical spend? (outside the trust region)

## Real-world data sources

In production you stop synthesizing spend. You collect the same concepts from operational systems, then roll them to a weekly national (or DMA) panel.

| Funnel role | What you need | Typical sources | How it lands |
| --- | --- | --- | --- |
| TOFU delivery and cost | Weekly GRPs / impressions and actualized $ | Nielsen / Numeris, Kantar, WideOrbit, Broadsign, DV360, The Trade Desk, Campaign Manager 360 | API or agency file → bronze media |
| MOFU paid social / video | Spend, impressions, clicks, reach | Meta Ads, TikTok Ads, LinkedIn, Pinterest, YouTube / Google Ads video, Amazon DSP | Official Ads APIs or Fivetran / Supermetrics |
| BOFU harvest | Spend, clicks, branded vs non-branded split | Google Ads, Microsoft Ads, Amazon Ads, affiliate networks (CJ, Impact), retail media | Ads API + search-query classification |
| Intent mediator M | Brand search demand, not paid clicks | Google Search Console, Google Trends, SEMrush / Semrush, YouGov brand index | Search Console API + Trends; never use paid branded clicks as M |
| Outcome Y | Net sales, orders, margin | Shopify, Salesforce, SAP S/4, Oracle, NetSuite, POS, Stripe | ERP / commerce extract; use net revenue after returns |
| Baseline / endogeneity | Holidays, promo depth, price, stockouts, competitor | Internal promo calendar, PIM, inventory, Pathmatics / Sensor Tower, StatsCan / FRED, weather | Finance + ops sheets + macro APIs |
| Calibration | Causal lift from holdouts | Geo-lift / matched-market tests, incrementality platforms, MMM prior logs | Experiment registry table |

## Fields those sources actually have

You do not feed raw platform dumps into 2SLS. You keep the source fields in bronze, then map a few of them into the weekly MMM mart. The compact lists below are an index. The field dictionary explains every column: what it is, an example, and whether you keep it, roll it, or drop it.

### Google Ads / Microsoft Ads (BOFU, some MOFU)

| Field | Use in MMM |
| --- | --- |
| date, customer_id, campaign_id, ad_group_id, keyword_text | Grain and hierarchy |
| campaign_type, network, device | Roll to channel (Search / Shopping / YouTube) |
| cost, impressions, clicks, conversions, conversion_value | Spend and delivery; do not use platform conversions as Y |
| search_term, match_type, impression_share, abs_top_is | Brand vs generic split; auction pressure |
| average_cpc, quality_score | Cost-shifter instrument if needed |
| geo_target, currency | DMA / country grain and FX |

### Meta / TikTok / LinkedIn / Pinterest Ads (MOFU)

| Field | Use in MMM |
| --- | --- |
| date_start, date_stop, account_id, campaign_id, adset_id, ad_id | Grain |
| objective, optimization_goal, buying_type | Awareness vs conversion campaigns |
| spend, impressions, reach, frequency, clicks, inline_link_clicks | Spend and saturated reach |
| actions, action_values, video_p25/p50/p100 | Quality of delivery, not sales Y |
| publisher_platform, placement, age, gender, country, region | Optional geo / demo splits |
| cpm, cpc, quality_ranking | Auction cost shifter |

### DV360 / The Trade Desk / CM360 (TOFU display, CTV, video)

| Field | Use in MMM |
| --- | --- |
| date, advertiser_id, insertion_order, line_item, creative_id | Flighting |
| media_cost, data_cost, impressions, measurable_imps, viewable_imps | True cost and viewable delivery |
| clicks, complete_views, companion_views | Delivery quality |
| exchange, inventory_type, device, dma_id | Channel and geo |
| cm360: floodlight_activity, total_conversions | Do not replace finance sales |

### TV / Radio / OOH (TOFU offline)

| Field | Use in MMM |
| --- | --- |
| air_datetime, market / DMA, station / title, daypart | Flight calendar |
| planned_spend, actualized_spend, GRPs, TRPs, spots | Exposure; prefer actualized $ and GRPs |
| reach, frequency, creative_id, isci / ad_id | Carryover and creative changes |
| OOH: face_id, plays, circulation, dwell_time | Weekly impression proxy |
| invoice_id, agency_fee, production_cost | Fully loaded cost vs media-only |

### Google Search Console + Trends (intent M)

| Field | Use in MMM |
| --- | --- |
| date, query, page, country, device | Brand-query filter |
| clicks, impressions, ctr, position | Organic branded demand index |
| Trends: term, geo, timeframe, interest_score 0–100 | Alternate M if GSC history is short |

### GA4 / Adobe Analytics (site, not sales of record)

| Field | Use in MMM |
| --- | --- |
| event_date, session_id, user_pseudo_id | Do not model at user grain |
| sessions, engaged_sessions, purchases, item_revenue | Optional MOFU mediator (organic visits) |
| session_source, medium, campaign, default_channel_group | Last-touch context only |
| item_id, item_category, coupon | Join to promo, not to media spend |

### Commerce / CRM / ERP (sales Y)

| Field | Use in MMM |
| --- | --- |
| order_id, order_ts, customer_id, store_id, channel (web/store) | Roll to week × geo |
| gross_sales, discounts, returns, net_sales, cogs, contribution_margin | Y is net sales or margin — pick one and keep it |
| units, sku, category, list_price, paid_price | Price and mix controls |
| promo_id, promo_flag, discount_pct | Omitted-variable controls |
| fulfillment_status, stockout_flag | Operational confounders |

### Promo, inventory, competitor, macro

| Source | Fields | Use |
| --- | --- | --- |
| Promo calendar | promo_id, start, end, mechanic, depth_pct, featured_sku | holiday / promo_depth |
| Inventory | sku, date, on_hand, stockout_hours, fill_rate | Demand that media cannot convert |
| Pathmatics / similar | competitor, channel, estimated_spend, share_of_voice | Competitive pressure |
| FRED / StatsCan / weather | cpi, unemployment, fx, temperature, precipitation | Macro baseline |
| Geo-lift logs | test_id, geo, treatment_flag, start, end, channel, lift, ci | Bayesian / calibration priors |

## How those feeds get into the warehouse

- Extract. SaaS connectors (Fivetran, Airbyte, Supermetrics) for ads and GSC. SFTP / S3 for agency TV invoices and Nielsen. CDC or nightly dump for ERP/Shopify. HTTP for FRED and weather.
- Land in bronze. One schema per source, raw types, load timestamp, file name, source_system. Do not rename Google’s cost_micros yet.
- Conform in silver (dbt). Convert currency to CAD/USD, timezone to a business calendar, map campaign names to a channel taxonomy, classify branded search terms, actualize planned vs billed TV spend.
- Aggregate in gold. Daily facts roll to week_start × geo × channel. That is the only grain the 2SLS model should see.
- Publish. A single table mart_mmm_weekly plus dimension tables. The studio / batch job reads only gold, never bronze.
Cadence: ads and web daily; ERP nightly; TV weekly after actualization; macro monthly with carry-forward. Late invoices get a version column so you can restated weeks.

## Warehouse architecture

Medallion layout on Snowflake, BigQuery, Fabric, or Databricks. Orchestrate with Airflow, ADF, MWAA, or Dagster. Transform with dbt. Keep PII out of the MMM mart. The exact Azure and AWS service names, account setup, and go-live gates are on tab 4.

#### Sources

Google Ads, Meta, DV360, Nielsen, GSC, Shopify/SAP, promo, FRED, geo tests

#### → Ingest

Fivetran / Airbyte / S3 / APIs. Orchestrator retries and SLAs.

#### → Bronze

Raw, append-only, partitioned by load date. Source field names kept.

#### → Silver

Conformed dates, FX, channel map, brand-query flag, net sales.

#### → Gold

Star schema + mart_mmm_weekly. What the model consumes.

#### → Serve

This studio, notebooks, Looker/Power BI, optimizer job, model registry.

```
source systems
    |  connectors + object store
    v
bronze_ads_* / bronze_erp_* / bronze_nielsen_*     (raw)
    |  dbt tests: not null, unique, accepted values
    v
silver_media_daily / silver_sales_daily / silver_intent_daily
    |  week rollup, taxonomy, FX
    v
gold star schema  →  mart_mmm_weekly  →  2SLS + SLSQP
    |
    +→ experiment_registry (geo-lift priors)
    +→ model_run_log (coefficients, MAPE, allocation)
```

## Data model (star schema)

Grain of every fact below is stated. Surrogate keys are integers. Business keys stay in the dimensions so finance can audit a week back to an invoice. What each column means is in the field dictionary (source tables first, then these dimensions and facts).

### Dimensions

| Table | Keys and attributes |
| --- | --- |
| dim_date | date_key, date, week_start_mon, iso_week, month, quarter, year, is_holiday, holiday_name, fiscal_week |
| dim_geo | geo_key, country, region, dma_code, dma_name, store_cluster |
| dim_channel | channel_key, channel_name, funnel (TOFU/MOFU/BOFU), media_family, platform, brand_vs_generic |
| dim_campaign | campaign_key, source_campaign_id, name, objective, start, end (SCD2) |
| dim_product | product_key, sku, category, brand (only if you model SKU-level Y) |
| dim_promo | promo_key, mechanic, depth_band, feature_flag |

### Facts

| Table | Grain | Measures |
| --- | --- | --- |
| fact_media_spend | date × geo × channel × campaign | spend, fees, impressions, clicks, reach, grps, viewable_imps |
| fact_search_intent | date × geo | branded_queries, branded_gsc_clicks, trends_index |
| fact_web | date × geo | sessions, organic_sessions, revenue_ga (audit only) |
| fact_sales | date × geo [× product] | orders, units, gross, discount, returns, net_sales, margin |
| fact_ops | date × geo | promo_depth, avg_discount, stockout_rate, list_price_index |
| fact_macro | date × geo | cpi, unemployment, fx, temperature |
| fact_sov | date × geo × channel | competitor_spend, share_of_voice |
| fact_experiment | test × geo × date × channel | treatment, observed_lift, ci_low, ci_high |

## Field dictionary (source tables, then dimensions and facts)

Read “Keep / roll / drop” as what silver does. Keep = needed to build a mart column. Roll = used only to group or classify, then discarded at week × geo. Drop = stay in bronze for audit; never enter 2SLS. Dimensions live in gold. Source tables keep the vendor’s field names in bronze.

Google / Microsoft Ads Paid social DV360 / TTD / CM360 TV / Radio / OOH Search Console / Trends GA4 / Adobe Commerce / ERP Promo / inventory / macro Dimensions dim_date dim_geo dim_channel dim_campaign Facts

### Google Ads / Microsoft Ads — source fields

Bronze grain is usually date × campaign × ad group × keyword × device × geo. Silver rolls that to date × geo × parent channel.

| Field | What it is | Example | Keep / roll / drop |
| --- | --- | --- | --- |
| date | Reporting day in the account timezone (or UTC — check the API). | 2026-03-12 | Keep. Map to local date → week_start. |
| customer_id | Ads account number. One brand can have many accounts (brand, generic, shopping). | 123-456-7890 | Roll. Join to a mapping table that says which accounts belong to this advertiser. |
| campaign_id | Stable numeric id of the campaign. Survives a rename. | 18442001234 | Roll into dim_campaign (SCD2). Never a 2SLS column. |
| ad_group_id | Cluster of ads/keywords under a campaign. | 98765001 | Drop for MMM. Too fine. Useful only if you later split brand vs generic inside search. |
| keyword_text | The keyword you bid on (not always what the user typed). | buy running shoes | Roll if you classify brand vs generic. Drop the text itself from gold. |
| search_term | What the user actually typed. Better than keyword for brand detection. | acme shoes official | Roll: flag brand-dictionary matches. Do not use as M — that is paid demand, not organic intent. |
| match_type | How tightly the keyword had to match (exact / phrase / broad). | EXACT | Drop for national MMM. Optional audit. |
| campaign_type | Search, Shopping, Performance Max, Video, Display. | SHOPPING | Roll into dim_channel (Paid Search vs YouTube vs Shopping). |
| network | Google Search, Search partners, YouTube, Discover. | YOUTUBE_WATCH | Roll. YouTube watch is MOFU, not BOFU. |
| device | Desktop / mobile / tablet. | MOBILE | Drop unless you model device-level Y (you should not at first). |
| cost / cost_micros | What you paid that day. Micros are millionths of the account currency. | cost_micros = 12500000 → $12.50 | Keep. This becomes spend_search after /1e6 and FX. |
| impressions | How many times an ad was shown. | 48,200 | Keep optional as delivery. Use instead of spend only if cost is missing. Do not put both in 2SLS for the same channel. |
| clicks | Paid clicks on the ad. | 1,104 | Drop for 2SLS. Useful to build CPC = cost/clicks as an optional instrument. |
| conversions, conversion_value | Platform-attributed sales. Last-click or data-driven inside Google. | 37 conversions, $4,120 | Drop. This is not Y. Finance sales from ERP replace it. |
| impression_share | Share of eligible auctions you appeared in (0–1). | 0.72 | Drop for the first mart. Optional auction-pressure control later. |
| abs_top_is | Share of impressions in the absolute top slot. | 0.31 | Drop. Creative/auction diagnostic, not a spend series. |
| average_cpc | cost / clicks that day. | 1.84 CAD | Roll into optional cpm_index / CPC instrument. Not a channel spend. |
| quality_score | Google’s 1–10 relevance score on the keyword. | 7 | Drop. Changes slowly; not weekly media. |
| geo_target | The targeting you set (country, province, DMA) — not always where the user was. | Canada / Toronto DMA | Roll to dim_geo. If you target nationally, all spend goes to geo_key = 0. |
| currency | Account currency of cost. | CAD, USD | Keep until silver FX converts everything to one reporting currency. |

### Meta / TikTok / LinkedIn / Pinterest — source fields

| Field | What it is | Example | Keep / roll / drop |
| --- | --- | --- | --- |
| date_start, date_stop | Reporting window. Daily pulls should have start = stop. | both 2026-03-12 | Keep. If someone pulled a weekly range, explode to days or reject the file. |
| account_id | Ad account. Several brands or regions can sit in one Business Manager. | act_112233 | Roll to advertiser mapping. |
| campaign_id, adset_id, ad_id | Hierarchy: campaign → ad set (budget/audience) → ad (creative). | 120210998 | Roll campaign into dim_campaign. Drop ad set and ad for MMM. |
| objective | What the campaign was optimized for (awareness, traffic, conversions). | OUTCOME_AWARENESS | Roll: awareness/video → MOFU; catalog conversions can stay MOFU unless you split. |
| optimization_goal | The event the auction maximized (impressions, landing-page views, purchase). | LANDING_PAGE_VIEWS | Roll with objective. Drop the raw code from gold. |
| buying_type | Auction vs reserved (reach-and-frequency). | AUCTION | Drop unless you treat reserved as a different channel. |
| spend | Amount billed that day in account currency. | 8,440.12 | Keep. This is spend_social after FX. |
| impressions | Paid views of the ad. | 2.1M | Keep optional as delivery / reach saturation. |
| reach | Unique people (platform estimate) who saw the ad. | 640,000 | Drop for 2SLS. Optional quality series; not spend. |
| frequency | impressions / reach. How often the same person saw it. | 3.3 | Drop. Diagnostic that you are fatiguing the audience. |
| clicks, inline_link_clicks | All clicks vs clicks that left the platform. | 12,400 link clicks | Drop. CPC can be derived; not a mart column. |
| actions, action_values | Platform-attributed events and their value (purchases, add-to-cart). | purchase: 90, value: 7,200 | Drop. Not Y. Meta’s attribution window is not finance. |
| video_p25/p50/p100 | How many views reached 25/50/100% of the video. | p50 = 80,000 | Drop. Creative quality, not weekly spend. |
| publisher_platform, placement | Facebook, Instagram, Audience Network; feed vs stories vs reels. | instagram / story | Roll into Social unless you have years of weeks to split Stories vs Feed. |
| age, gender | Audience breakouts the API will give if you ask. | 25–34, female | Drop. National weekly MMM has no demo Y. |
| country, region | Delivery geo (where Facebook says the user was). | CA / ON | Roll to dim_geo. |
| cpm, cpc | Cost per thousand impressions / per click. | CPM 14.20 | Roll optional into cpm_index. |
| quality_ranking | Meta’s above/average/below average creative rank. | AVERAGE | Drop. |

### DV360 / The Trade Desk / CM360 — source fields

| Field | What it is | Example | Keep / roll / drop |
| --- | --- | --- | --- |
| date | Delivery day. | 2026-03-12 | Keep → week. |
| advertiser_id | The brand seat in the DSP / CM360. | 3847561 | Roll to advertiser mapping. |
| insertion_order | Flight-level budget container (often “Q1 CTV Brand”). | IO-8891 | Roll into dim_campaign. This is the offline equivalent of a campaign. |
| line_item | A buy inside the IO (CTV vs display, a deal id). | LI-CTV-Open | Roll to channel (CTV, display, video). Drop the id from the mart. |
| creative_id | The asset that ran. | CR-2044 | Drop. Creative tests are not weekly MMM. |
| media_cost | What you paid the exchange / publisher for media. | 22,100 | Keep. Core of TOFU digital spend. |
| data_cost | What you paid for audience segments on top of media. | 1,340 | Keep if finance wants fully loaded cost (add to media_cost). Else drop and document. |
| impressions | Served ads, whether viewable or not. | 3.4M | Keep optional. |
| measurable_imps | Impressions where viewability could be measured. | 3.1M | Drop. Quality filter, not spend. |
| viewable_imps | Impressions that met MRC viewability (e.g. 50% in view for 1s). | 2.4M | Keep only if you model exposure instead of spend. |
| clicks | Clicks on the display/video unit. | 4,200 | Drop. |
| complete_views | Video played to the end (or to the billed complete). | 180,000 | Drop. Delivery quality. |
| companion_views | Views of a companion banner next to video. | 12,000 | Drop. |
| exchange, inventory_type | Where it ran (OpenX, private marketplace, YouTube reserve). | PMP | Roll into media_family if you split CTV vs open display. |
| device | CTV, desktop, mobile app, etc. | CONNECTED_TV | Roll. CTV often sits with TOFU video, not social. |
| dma_id | Nielsen DMA of delivery. | 501 (NY) | Roll to dim_geo. |
| floodlight_activity, total_conversions | CM360 tracking pixels and their counts. | fl_purchase = 210 | Drop. Not Y. Audit only. |

### TV / Radio / OOH — source fields

| Field | What it is | Example | Keep / roll / drop |
| --- | --- | --- | --- |
| air_datetime | When the spot ran (local station time). | 2026-03-12 20:03 ET | Keep. Bucket into the business week. |
| market / DMA | The city or Nielsen market that saw the spot. | Toronto / 504 | Roll to dim_geo. National MMM sums all markets. |
| station / title | Call letters or program the spot sat in. | CITY-TV / Hockey Night | Drop after you have mapped it to TV vs Radio. |
| daypart | Daypart bucket (prime, daytime, late fringe). | PRIME | Drop for the first mart. Optional later if prime vs daytime has different θ. |
| planned_spend | What the IO said you would spend. Often wrong after make-goods. | 180,000 | Drop as the spend series. Keep in bronze to reconcile vs actualized. |
| actualized_spend | What the invoice says you paid after make-goods. | 172,400 | Keep. This is spend_tv / spend_radio. |
| GRPs / TRPs | Gross / target rating points — reach × frequency in the population (or target demo). | 42 GRPs that week | Keep optional as exposure if the invoice is late. Do not use GRPs and $ together in 2SLS. |
| spots | Count of airings. | 28 | Drop. Weak exposure proxy next to GRPs or $. |
| reach, frequency | Unique audience and average times seen, from the ratings vendor. | reach 38%, freq 2.1 | Drop for 2SLS. Useful to check the Hill operating point. |
| creative_id / isci / ad_id | Industry code of the creative that aired. | ACME1234000H | Drop. Creative rotation is not a weekly channel. |
| face_id (OOH) | The physical board or screen. | FACE-88421 | Roll to market, then drop the id. |
| plays (OOH) | How many times the loop showed your creative. | 14,400 | Keep as an impression proxy if OOH $ is monthly. |
| circulation, dwell_time | Estimated passers-by and how long they look. | circ 52,000/day | Drop or roll into a weekly impression estimate. Not spend. |
| invoice_id | The billing document. | INV-2026-031 | Drop from gold. Keep in bronze so finance can tie a week back. |
| agency_fee | What the agency charged on top of media. | 15,000 | Keep if Y is judged on fully loaded cost; add into spend. Else document and drop. |
| production_cost | Cost to shoot the spot. Usually not weekly media. | 240,000 one-time | Drop from weekly spend. Amortize only if finance insists, and say so. |

### Google Search Console + Trends — source fields

| Field | What it is | Example | Keep / roll / drop |
| --- | --- | --- | --- |
| date | Day the query appeared in GSC (UTC; shift to local). | 2026-03-12 | Keep → week. |
| query | The search string. This is organic, not a paid keyword. | acme running shoes | Roll: keep if it matches the brand dictionary; drop generic queries. |
| page | The site URL that ranked. | /products/pegasus | Drop. Page-level is not M. |
| country, device | Where / on what device the search happened. | can, MOBILE | Roll country → geo. Drop device. |
| clicks | Organic clicks from that query to your site. | 640 | Keep (sum brand queries) as the usual queries_M. |
| impressions | How often the query showed your site in organic results. | 18,200 | Keep as an alternate M if clicks are sparse. Do not add clicks + impressions. |
| ctr | clicks / impressions. | 0.035 | Drop. A ratio, not a demand stock. |
| position | Average organic rank. | 3.2 | Drop. SEO quality, not weekly intent. |
| term (Trends) | The phrase you asked Trends for. | acme | Roll: one brand-term list, then average or take the brand term. |
| geo, timeframe (Trends) | Country and window of the Trends pull. | CA, weekly | Keep geo → dim_geo. Pull weekly, not monthly, if you can. |
| interest_score | Trends index 0–100, relative to the pull window — not a count of searches. | 67 | Keep as fallback M only. Rescale if you splice two pulls. Never mix with GSC clicks in the same column without documenting the splice. |

### GA4 / Adobe — source fields (site, not sales of record)

| Field | What it is | Example | Keep / roll / drop |
| --- | --- | --- | --- |
| event_date | Day of the hit. | 20260312 | Keep only if you build fact_web. |
| session_id | One visit. | a8f2… | Drop. Count sessions; do not store the id in gold. |
| user_pseudo_id | GA4 cookie-ish id. PII-adjacent. | 1234.5678 | Drop. Never in the MMM mart. |
| sessions, engaged_sessions | Visit counts. | 42,100 sessions | Keep only as an optional second mediator. Not M if you have GSC. Not Y. |
| purchases, item_revenue | On-site purchase events and GA’s revenue. | $88,000 | Drop as Y. Audit vs ERP only. GA misses stores and mis-attributes returns. |
| session_source, medium, campaign | Last-touch tags (google / cpc / brand_2026). | google / cpc | Drop for 2SLS. This is last-click context, the thing MMM is built to replace. |
| default_channel_group | GA4’s Paid Search / Organic / Direct bucket. | Paid Search | Drop. Do not let GA’s grouping override dim_channel. |
| item_id, item_category, coupon | Product and offer on the hit. | SKU-44, SPRING20 | Roll coupon into promo if ERP promo is missing. Drop item_id unless SKU-level Y. |

### Commerce / CRM / ERP — source fields

| Field | What it is | Example | Keep / roll / drop |
| --- | --- | --- | --- |
| order_id | Unique order. One customer can have many. | SO-1002948 | Drop after you have aggregated. Keep in bronze for audit. |
| order_ts | When the order was placed (or invoiced — pick one and freeze it). | 2026-03-12 18:41 ET | Keep. This is the date that becomes the week of Y. |
| customer_id | Who bought. PII if it joins to email. | CUST-88 | Drop from gold. Count orders, not people, in the MMM mart. |
| store_id | Store or DC or “WEB”. | ST-104 / WEB | Roll to dim_geo (and optional store_cluster). |
| channel (web/store) | Sales channel, not media channel. | retail | Roll if you ever split Y by store vs e-comm. Default: sum them into one Y. |
| gross_sales | List or pre-discount product $. | 120.00 | Keep as an input to net. Not Y by itself. |
| discounts | Promo and markdown $ taken off the order. | 24.00 | Keep. Used for net and for promo_depth = discounts/list. |
| returns | Refunded $ (often posted days later). | 12.00 | Keep. Net must subtract them. Restate the original week if finance does. |
| net_sales | gross − discounts − returns. The usual Y. | 84.00 | Keep. This is sales_Y if you chose net. |
| cogs | Cost of goods for the lines on the order. | 41.00 | Keep only if Y is margin (net − cogs). Else drop from the mart. |
| contribution_margin | net − cogs − maybe variable shipping. | 38.00 | Keep as Y if finance optimizes profit, not sales. Do not switch mid-year. |
| units | Quantity sold. | 2 | Keep for price index weights. Not Y unless you model units. |
| sku, category | What was sold. | PEG-42, Footwear | Roll to dim_product only if Y is SKU or category. Default national MMM drops sku. |
| list_price, paid_price | Shelf price vs what the customer paid. | 160 vs 128 | Keep. list → price_index. (list−paid)/list → promo_depth. |
| promo_id, promo_flag, discount_pct | Which offer applied. | SPRING20, 0.20 | Roll into fact_ops.promo_depth and dim_promo. |
| fulfillment_status | pending / shipped / cancelled. | cancelled | Roll: drop cancelled from Y, or finance will not sign the mart. |
| stockout_flag | Line was OOS or substituted. | 1 | Roll into stockout_rate if inventory tables are late. Prefer WMS hours. |

### Promo, inventory, competitor, macro, experiments — source fields

| Source field | What it is | Example | Keep / roll / drop |
| --- | --- | --- | --- |
| promo_id | Offer identifier from the promo calendar. | P-2026-W11 | Roll to dim_promo. |
| start, end | Inclusive dates the mechanic is on. | 2026-03-09 to 2026-03-15 | Keep. Explode to days, then week. |
| mechanic | How the deal works: TPR, bogo, feature, display. | TPR | Roll to dim_promo.mechanic. Default MMM uses depth, not mechanic dummies. |
| depth_pct | Discount as a fraction of list. | 0.20 | Keep. Volume-weight to promo_depth. |
| featured_sku | Which items were on the flyer. | PEG-42 | Drop unless category-level Y. |
| sku, date (inventory) | Which item on which day. | PEG-42, 2026-03-12 | Roll to week × geo. |
| on_hand | Units in the DC or store at day end. | 140 | Drop as a mart column. Used only to build stockout. |
| stockout_hours | Hours that day the item could not be sold. | 6 | Keep. stockout_rate = stockout_hours / selling_hours. |
| fill_rate | Share of demand that was fulfilled (0–1). | 0.93 | Keep as alternate: stockout_rate ≈ 1 − fill_rate. |
| competitor | Rival name in the SOV file. | RivalCo | Roll: sum all rivals, or keep a top-3 split later. |
| channel (SOV file) | Which media the rival spent on. | TV | Roll. First mart can ignore channel and use national SOV. |
| estimated_spend | Vendor’s $ estimate of rival media. Noisy. | 1.2M that week | Keep to build SOV = rival / (rival + you). |
| share_of_voice | Vendor’s 0–1 SOV, if they already computed it. | 0.41 | Keep as competitor_sov if you trust it more than DIY. |
| cpi | Consumer price index level or already YoY. | 161.2 or 2.8 | Keep. If it is a level, compute 12-month % → cpi_yoy. Carry month to each week. |
| unemployment | Labour force unemployment rate in percentage points. | 6.1 | Keep. Carry month to weeks. Not a 0–1 share. |
| fx | Exchange rate used to convert spend and sales. | 1.36 CAD/USD | Keep in silver for FX. Drop from the 2SLS mart unless you sell in many currencies. |
| temperature | Daily mean °C at a station. | 4.2 | Keep. Average stations → geo → week. |
| precipitation | Daily mm of rain/snow. | 8.0 | Drop for the first mart. Optional later for weather-sensitive categories. |
| test_id | Geo-experiment identifier. | GEO-24-Q4-TV | Keep in fact_experiment. Not a 2SLS regressor. |
| treatment_flag | 1 = geo saw extra media, 0 = holdout. | 1 | Keep. Defines the lift calculation. |
| lift, ci | Estimated incremental % or $ and its interval. | 8.4% [3.1, 13.6] | Keep as the prior you calibrate totals toward after 2SLS. |

### Dimension tables — every field (X Canada)

A dimension is the noun (when, where, which channel, which plan, which offer). Facts hold the numbers and join here on *_key. Examples below are X Canada. Surrogate keys are integers; business keys stay on the dim so finance can audit a week back to an invoice or campaign.

#### dim_date — one row per calendar day

The mart does not use the day. It groups to week_start_mon. Every fact still stores date_key so you can rebuild a week.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| date_key | int PK | Surrogate, usually YYYYMMDD. Facts join on this. | 20260112 | Join only. Not a regressor. |
| date | date | The calendar day in America/Toronto. | 2026-01-12 (Mon) | Audit. Media uses impression date; Y uses ship date — both map through this table. |
| week_start_mon | date | Monday that starts the business week. This is time t. | 2026-01-12 | Yes. Mart grain. Train = first 80% of these Mondays. |
| iso_week | int 1–53 | ISO week number. | 3 | Used to build season Fourier and to flag weeks 47–1 as holiday-ish. |
| month | int 1–12 | Calendar month. | 1 | Reporting (January diet peak). Not a 2SLS column; season already captures the year shape. |
| quarter | int 1–4 | Calendar quarter. | 1 | Reporting only. |
| year | int | Calendar year. | 2026 | Reporting only. |
| is_holiday | 0/1 | Retail-peak or habit-reset week X actually promotes (not only civic holidays). | 1 on New Year week, Super Bowl week, CA Thanksgiving, BFCM, Christmas | Yes. Mart holiday. Stage 1 and Stage 2. Stops January TV from stealing New Year sign-ups. |
| holiday_name | string | Which peak, if any. | New Year, Super Bowl, BFCM | Audit. Do not make one dummy per name in the first model. |
| fiscal_week | string | X / retail 4-5-4 week if finance books that way. | FY26-W03 | Reconcile Y to the finance pack. Engine still prefers ISO Monday weeks unless finance forbids it. |
| is_payday | 0/1 | Canada biweekly pay Friday week. | 1 every other Friday | Yes. Mart payday. Stage 2 only. Sign-ups cluster after payday; skips before rent. |

#### dim_geo — one row per planning geography

Start with one national Canada row. Do not model Yukon as a DMA. Add ON / BC only when weekly boxes are stable enough for holdout.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| geo_key | int PK | Surrogate. Convention: 0 = national ALL. | 0 = Canada | Yes. Mart grain with week_start. |
| country | char(2) | ISO country. Filters GSC, StatsCan, Google Ads account. | CA | Filter. One country per mart. |
| region | string | Province / state of delivery. | ON, BC, QC, Rest | Optional later split. Not in the first national 2SLS. |
| dma_code | string | Nielsen / Numeris market id for TV buying. | 504 Toronto, 511 Montreal | Join TV invoices and DV360. Sum to geo_key 0 for the first model. |
| dma_name | string | Market name. | Toronto | Human audit of TV actualization. |
| store_cluster | string | For X this is a delivery cluster (DC + postal FSA), not a store banner. | GTA, Lower Mainland, Rest of CA | Optional if you ever split Y by fulfillment region. Skip at first. |

#### dim_channel — one parent channel the engine may see

This taxonomy collapses hundreds of X campaigns into a few columns. The engine never sees a campaign id.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| channel_key | int PK | Surrogate. Facts join here. | 1 TV, 2 YouTube, 3 Social, 4 Paid Search | Join only. |
| channel_name | string unique | Parent name. Becomes the mart suffix spend_*. | TV, YouTube, Social, Paid Search | Yes. Pivots to spend_tv, spend_youtube, … |
| funnel | TOFU / MOFU / BOFU | Which equation the channel may enter. Structural exclusion, not a Google objective. | TV = TOFU; YouTube/Social = MOFU; Paid Search = BOFU | Yes. TOFU → Stage 1 only. BOFU → Stage 2 only. MOFU → both. |
| media_family | string | Coarser family for reporting. | broadcast, video, social, search | BI only. Not extra 2SLS columns. |
| platform | string | Vendor that produced the spend. | Google Ads, Meta, TikTok, Numeris, The Trade Desk | Audit. Many platforms can share one channel_name (PMax + Microsoft → Paid Search). |
| brand_vs_generic | brand / generic / mixed | Search only: did the campaign bid on X-name queries? | CA_Search_Brand = brand; CA_Search_Generic + PMax = generic/mixed | Optional later split of search. First model: one spend_search. Never use brand paid clicks as M. |

#### dim_campaign — one campaign version (SCD2)

When media ops renames CA_Search_Brand to CA_SEM_Brand_FY27, you add a new row with a new campaign_key and close the old end. History keeps the old mapping to Paid Search.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| campaign_key | int PK | New surrogate on every SCD2 version. | 88421 | Join from fact_media_spend only. Not on the weekly mart. |
| source_campaign_id | string | Vendor id that survives a rename. | Google 18442001234; Meta 120210998; TTD IO-8891 | Audit a week back to the Google/Meta UI. |
| name | string | What ops called it that season. | CA_Search_Brand, CA_PMax_Acquire, CA_YT_Demand, CA_Meta_Prospect | Human. Silver uses name + type to assign channel_key. |
| objective | string | Awareness / traffic / conversions as they set it. | YouTube = awareness; PMax = conversions | Helps assign funnel when the name is messy. Not a regressor. |
| start | date | First day this version is valid. | 2026-01-01 | Point-in-time join. |
| end | date | Last day this version is valid (null = current). | 2026-03-31 or null | A rename on 1 Apr must not rewrite Q1 spend. |

#### dim_product — X plan / box (optional)

National X MMM can skip this and keep one Y. Use it only if you later split Classic vs Veggie vs Family, or Chef’s Plate vs X.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| product_key | int PK | Surrogate. | 19 | Join from fact_sales only if Y is plan-level. |
| sku | string | Plan or box code (not a grocery SKU). | HF-CA-2P-3M (2-person, 3-meal) | Weights for price_index. Not a 2SLS dummy at first. |
| category | string | Plan family. | Classic, Veggie, Family, Calorie Smart, Chef’s Plate | Only if you run a plan-family MMM. |
| brand | string | Brand on the box. | X, Chef’s Plate, Factor | Filter Y to the advertised brand. Do not pool Factor into X Y without a decision. |

#### dim_promo — intro and win-back offers

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| promo_key | int PK | Surrogate for one offer version. | 55 | Join from fact_ops / orders if you keep mechanic splits. |
| mechanic | string | How the deal works. | intro_percent, free_breakfast, free_shipping, winback_percent | Default mart collapses to one promo_depth. Keep mechanic if you later add dummies. |
| depth_band | string | Binned discount for reporting. | 40-50, 50-60, 60+ | BI. Engine wants continuous depth (0.50), not the band. |
| feature_flag | 0/1 | 1 if the offer was merchandised on homepage / paid social (the code was the hero). | 1 during a 60% national burst | Optional extra control. Not required. The YouTube ad that showed the code is media, not this flag. |

### Fact tables — every key and measure (X Canada)

Facts are the numbers at a stated grain. Keys on the left join dimensions. Measures on the right become mart columns. 2SLS never reads a fact row directly — it reads the weekly pivot.

#### fact_media_spend

Grain: date_key × geo_key × channel_key × campaign_key. One row = one campaign’s delivery that day in one geo.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| date_key | FK → dim_date | Impression / air day. | 20260112 | Rolls to week_start. |
| geo_key | FK → dim_geo | Where it delivered. | 0 = CA | Mart grain. |
| channel_key | FK → dim_channel | Parent channel after taxonomy. | Paid Search | Picks which spend_* column. |
| campaign_key | FK → dim_campaign | The campaign version that spent. | CA_Search_Brand | Dropped at the mart. Audit only. |
| spend | float CAD | Actualized media $ (plus fees if fully loaded). | $18,400 on Brand Search that day | Yes. Sum → spend_search → adstock + Hill → x̃. |
| fees | float CAD | Agency / data fees split out. | $1,200 on a CTV IO | Add to spend or report separately. Do not double-count. |
| impressions | int | Served ads. | 2.1M Meta impressions | Optional. Not in 2SLS next to spend. |
| clicks | int | Paid clicks. | 11,200 Brand Search clicks | No. CPC = spend/clicks only if you later want an instrument. |
| reach | float | Unique people (platform or ratings). | 640k Meta reach | No. |
| grps | float | TV/radio rating points. | 42 GRPs on a CTV flight week | Optional exposure if the TV invoice is late. |
| viewable_imps | int | MRC-viewable digital impressions. | 1.6M viewable CTV | Optional exposure for CTV/display. |

#### fact_search_intent

Grain: date_key × geo_key. This is how we build M. No campaign key — intent is not a media row.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| date_key, geo_key | FKs | Day and Canada (or province). | 20260112, CA | Roll to week × geo. |
| branded_queries | int | Count of distinct brand-dictionary queries that day. | 1,140 distinct queries containing x | Usually not M. Unstable. Prefer clicks. |
| branded_gsc_clicks | int | Organic clicks on those brand queries. | 8,400 clicks on x / x | Yes. Default queries_M / M. Stage 1 LHS. |
| trends_index | 0–100 | Google Trends for “x” in CA, weekly (repeat the week’s score on each day). | 67 | Fallback M if GSC history is short. Do not add to clicks. |

#### fact_web

Grain: date_key × geo_key. X.com / app traffic. Optional. Not Y.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| date_key, geo_key | FKs | Day and geo of the session. | CA | Roll to week. |
| sessions | int | All site/app sessions. | 92,000 | Optional second mediator. Not M if GSC exists. Not Y. |
| organic_sessions | int | Sessions GA called organic. | 18,000 | Optional. Worse than GSC branded clicks as M. |
| revenue_ga | float | GA4 item_revenue on x.ca. | $140k | Audit vs ledger only. Never sales_Y. Misses credits and ops cancels. |

#### fact_sales

Grain: date_key × geo_key [× product_key if you split plans]. Date is ship-week day, not click day. A Sunday click that ships Wednesday belongs here on Wednesday.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| date_key | FK → dim_date | Ship date (DC out). | 2026-01-14 ship | Rolls to week of Y. |
| geo_key | FK → dim_geo | Delivery region. | 0 = CA | Mart grain. |
| product_key | FK → dim_product, nullable | Plan if you split Y. | HF-CA-2P-3M | Null for national one-Y model. |
| orders | int | Boxes that shipped (or were supposed to). | 41,200 boxes | Weight. Not default Y. |
| units | int | Meals or servings inside those boxes. | 246,000 meals | Weight for $/serving price index. |
| gross | float CAD | List / pre-discount box $. | $4.1M | Input to net. Not Y. |
| discount | float CAD | Intro codes, win-back, credits applied at order. | $980k (lots of 50% first boxes) | Input to net and to promo_depth. |
| returns | float CAD | Refunds, failed payments, cancelled-after-cutoff, credits posted later. | $120k | Subtract. Restate the original ship week if finance does. |
| net_sales | float CAD | gross − discount − returns. New + repeat. | $3.0M | Yes. Default sales_Y. |
| margin | float CAD | net − food − packaging − last-mile − payment fees. | $410k (first boxes can be ~0) | Alternate Y if finance optimizes unit economics. Do not mix with net mid-year. |

#### fact_ops

Grain: date_key × geo_key. Offer, everyday price, and capacity. Not media.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| date_key, geo_key | FKs | Day and geo the offer/capacity applied. | CA, 2026-01-12 | Roll to week. |
| promo_key | FK → dim_promo, nullable | Dominant offer that day (optional). | 60% first box | Join for audit. Engine uses depth, not the key. |
| promo_depth | 0–1 | Volume-weighted discount / list on new and win-back boxes. | 0.52 in a 50–60% burst | Yes. Mart promo_depth. Stage 2. A 60% week is not a Meta win. |
| avg_discount | float CAD | Average $ off per box. | $48 off a first box | Audit. Engine uses the 0–1 depth. |
| stockout_rate | 0–1 | Share of demand that could not be fulfilled: sold-out recipes, no delivery slot, paused FSA, DC labour. | 0.08 on a sold-out Sunday | Yes. Mart stockout_rate. Stage 2. Media cannot convert a full slot. |
| list_price_index | float | Everyday plan price ($/serving) indexed to 100 in a reference year. | 103 after a $0.50/serving increase | Yes. Mart price_index; engine uses price_dev = index − 100. Not the intro code. |

#### fact_macro

Grain: date_key × geo_key. Monthly series are copied onto every day of the month.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| date_key, geo_key | FKs | Day (carried) and CA. | every day in Mar 2026, CA | Roll to week (same value all month for CPI/unemp). |
| cpi | float | StatsCan CPI level, or already YoY. | 161.2 or 2.8% | If level, compute 12-month % → mart cpi_yoy. Stage 2. Food-at-home inflation → more skips. |
| unemployment | float pp | StatsCan unemployment rate. | 6.1 | Yes. Stage 2. Discretionary meal kits shrink when jobs weaken. |
| fx | float | CAD/USD if any US-billed media leaked in. | 1.36 | Silver conversion. X CA Google Ads is already CAD — usually unused in 2SLS. |
| temperature | °C | Weekly mean over populated delivery geos. | −6 Jan; 24 Jul | Yes. Stage 1 and 2. Heat vs porch-spoilage; dark-evening cooking. |

#### fact_sov

Grain: date_key × geo_key × channel_key (channel optional). Rival voice in Canada.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| date_key, geo_key | FKs | Week/day and CA. | CA | Roll to week. |
| channel_key | FK, nullable | Which media the rival bought. Null = all-media SOV. | TV vs social; null at first | First mart: ignore channel, one national SOV. |
| competitor_spend | float CAD | Estimated rival $ (noisy). | Goodfood + Factor TV that week | Used to build SOV = rival / (rival + X). |
| share_of_voice | 0–1 | Vendor SOV, or the ratio you computed. | 0.41 | Yes. Mart competitor_sov. Stage 1 and 2. Goodfood Super Bowl is not “HF TV failed.” |

#### fact_experiment

Grain: test_id × geo_key × date_key × channel_key. Not a 2SLS regressor. Used after holdout to scale a channel toward a geo-lift prior.

| Field | Type | What it is | X example | In the engine? |
| --- | --- | --- | --- | --- |
| test_id | string | Experiment name. | GEO-26-Q1-CTV-ON | Registry key. Not a regressor. |
| date_key, geo_key, channel_key | FKs | When, where, which channel was tested. | ON DMAs, CTV, 6 weeks | Join only. |
| treatment | 0/1 | 1 = geo saw extra X media. | 1 in treated FSAs | Defines the lift calc. |
| observed_lift | float | Incremental boxes or % vs holdout. | +8.4% new boxes | Calibration prior after 2SLS. Then re-run SLSQP. |
| ci_low, ci_high | float | Uncertainty on that lift. | [3.1%, 13.6%] | Do not calibrate harder than the interval supports. |

Keys never enter 2SLS. Measures enter only after they are rolled to mart_mmm_weekly. If a new X column is not in this list, it stays in bronze until you add a row and decide whether it is a key, a measure, or a drop.

## MMM feature mart (what the model actually reads)

One row per week_start × geo (start with national geo = ALL). This is the production equivalent of the studio’s synthetic panel.

| Column | Type | Origin |
| --- | --- | --- |
| week_start | date | dim_date |
| geo_key | int | dim_geo |
| spend_<channel> | float | sum fact_media_spend.spend |
| impressions_<channel> / grps_<channel> | float | delivery (optional vs spend) |
| queries_M | float | branded GSC or Trends index |
| sales_Y | float | net sales or margin |
| trend | float | week index or local linear trend |
| fourier_sin1, cos1, sin2, cos2 | float | computed from week_start |
| holiday | 0/1 | dim_date |
| promo_depth | float | fact_ops |
| price_index, stockout_rate | float | fact_ops |
| competitor_sov | float | fact_sov |
| unemployment, cpi_yoy | float | fact_macro (StatsCan / FRED) |
| temperature | float | weather station / ERA5 weekly mean C |
| payday | 0/1 | biweekly pay calendar |
| cpm_index | float | spend / impressions (instrument) |

Channel columns are wide (one spend column per parent channel), not long, because 2SLS wants named regressors. The taxonomy in dim_channel decides how 200 campaigns collapse to “TV”, “Social”, “Paid Search”.

### Example dbt rollup

```
select
  d.week_start,
  g.geo_key,
  sum(case when c.channel_name = 'TV' then f.spend end) as spend_tv,
  sum(case when c.channel_name = 'Paid Search' then f.spend end) as spend_search,
  max(i.branded_queries) as queries_M,
  sum(s.net_sales) as sales_Y,
  max(o.promo_depth) as promo_depth
from gold.fact_media_spend f
join gold.dim_date d    on d.date_key = f.date_key
join gold.dim_geo g     on g.geo_key = f.geo_key
join gold.dim_channel c on c.channel_key = f.channel_key
join gold.fact_search_intent i on i.date_key = f.date_key and i.geo_key = f.geo_key
join gold.fact_sales s  on s.date_key = f.date_key and s.geo_key = f.geo_key
join gold.fact_ops o    on o.date_key = f.date_key and o.geo_key = f.geo_key
group by 1, 2
```

## Data flow: source → warehouse → MMM, for every input

Every series the 2SLS engine reads must arrive as one number per week_start × geo on mart_mmm_weekly. Nothing raw from an ads API is allowed into the regression. The lane is the same for every input; only the source system and the silver rule change.

```
Source system (API, SFTP, ERP, StatsCan, weather)
    |  extract: Fivetran / Airbyte / ADF / Glue / SFTP
    v
bronze_*          raw fields, load_ts, source_system, native grain
    |  dbt: timezone, FX, taxonomy, brand-query flag, net after returns
    v
silver_*          daily, conformed, still long
    |  roll to week × geo [× channel]
    v
gold.fact_*  +  dim_date / dim_geo / dim_channel
    |  wide pivot
    v
gold.mart_mmm_weekly     one row per week × geo
    |  load_weekly_mart()
    v
hierarchical_mmm_engine
    adstock θ + Hill K → x̃
    Stage 1  M ~ TOFU/MOFU x̃ + intent controls
    Stage 2  Y ~ M̂ + MOFU/BOFU x̃ + sales controls
    SLSQP inside L, U, B
```
Grain Media Intent M Sales Y Calendar Commercial Macro / competitive Computed Calibration

### Shared grain (every flow must land here)

| MMM column | Source | Extract | Bronze | Silver | Gold | Into the engine |
| --- | --- | --- | --- | --- | --- | --- |
| week_start | Business calendar (Monday start) | Seeded once | — | Map every source timestamp to local date, then to ISO week starting Monday | dim_date | Panel index t. Train = first 80% of weeks. |
| geo_key | Country / DMA / store cluster | From each source’s geo field | Keep native geo (dma_id, country, store_id) | Map to a single geo spine. Start with one national row (geo_key = 0) | dim_geo | Start national. DMA-level is a later split, not a first mart. |

### Media spend (the x_c columns)

Each parent channel becomes one wide column (spend_tv, spend_radio, spend_social, spend_search, …). Campaigns die in silver via dim_channel. The engine never sees a campaign id.

| MMM column | Source system | Extract | Bronze (keep raw names) | Silver rule | Gold | Into the engine |
| --- | --- | --- | --- | --- | --- | --- |
| spend_tv | Nielsen / Numeris, WideOrbit, agency invoice, CM360 | Weekly SFTP or agency workbook; CM360 API for digital TV / CTV | bronze_nielsen_*, bronze_tv_invoice: air_datetime, planned_spend, actualized_spend, GRPs, dma, isci | Prefer actualized $ plus agency fee if finance wants fully loaded cost. Map station/title → channel TV. Date → week. FX to CAD/USD. | fact_media_spend where funnel = TOFU and name = TV | Adstock θ + Hill K → x̃_tv. Stage 1 only (alpha). No Stage-2 beta. |
| spend_radio / OOH | Radio: WideOrbit / agency. OOH: Broadsign, face-level playlogs | SFTP / invoice | spots, GRPs, face_id, plays, circulation, actualized_spend | Same as TV. OOH plays → weekly impression proxy if $ is late. Taxonomy → Radio or OOH. | fact_media_spend TOFU | Same as TV: Stage 1 alpha only. |
| spend_social (and YouTube / influencer) | Meta Ads, TikTok, LinkedIn, Pinterest, Google Ads video | Ads API or Fivetran / Supermetrics, daily | bronze_meta_ads etc.: date_start, campaign_id, spend, impressions, reach, objective | Use spend, not action_values. Map objective + campaign name → Social / YouTube. Do not use platform tags as Y. | fact_media_spend MOFU | x̃_social in Stage 1 (alpha) and Stage 2 (beta). |
| spend_search (and Shopping / retail media) | Google Ads, Microsoft Ads, Amazon Ads, affiliate | Ads API, daily | cost / cost_micros, campaign_type, search_term, geo_target, currency | cost_micros / 1e6, FX. Roll Shopping + Search → Paid Search unless you have enough weeks to split. Brand vs generic is a taxonomy flag, not Y. | fact_media_spend BOFU | x̃_search in Stage 2 only (beta). Alpha forced to 0. |
| impressions_* / grps_* (optional) | Same platforms | Same extract | impressions, viewable_imps, GRPs | Use as the exposure series instead of spend only if cost is missing (late TV invoice). Do not put both spend and GRPs in 2SLS for the same channel. | fact_media_spend | Alternate input to adstock. Default studio path uses spend. |

```
Google Ads cost_micros  →  bronze_gads.cost_micros
    → silver: cost_cad = cost_micros/1e6 * fx, channel = Paid Search
    → gold.fact_media_spend.spend
    → mart.spend_search
    → A = spend + θ A_lag  →  x̃ = Hill(A, K)
    → Stage 2: Y ~ … + β_search x̃_search
```

### Intent M (never paid clicks)

| MMM column | Source system | Extract | Bronze | Silver rule | Gold | Into the engine |
| --- | --- | --- | --- | --- | --- | --- |
| queries_M | Google Search Console (primary). Google Trends or Semrush if GSC history is short. | Search Console API daily by query × country. Trends HTTP for a brand-term list. | bronze_gsc_query: date, query, country, clicks, impressions. bronze_trends: term, geo, interest_score. | Keep queries that match a brand dictionary. Sum organic clicks or impressions. Drop any join to Google Ads branded click or cost. Trends 0–100 rescaled if used as a fallback. | fact_search_intent (date × geo) | This is M. Stage 1 left-hand side. Stage 2 sees only fitted M̂. |

GA4 sessions can be an optional second mediator later. They do not replace GSC. GA4 item_revenue is not Y.

### Sales Y (finance is the system of record)

| MMM column | Source system | Extract | Bronze | Silver rule | Gold | Into the engine |
| --- | --- | --- | --- | --- | --- | --- |
| sales_Y | SAP S/4, Oracle, NetSuite, Shopify, POS, Stripe — the ledger finance signs | Nightly CDC or dump. Order grain. | bronze_erp_order: order_id, order_ts, store_id, gross, discount, returns, cogs, channel | Net sales = gross − discounts − returns (or contribution margin). Pick one and freeze it. Timestamp → local week. Store → geo. No user_id into gold. | fact_sales (date × geo) | This is Y. Stage 2 left-hand side. Never replace it with Google Ads conversions or Meta action_values. |

### Calendar controls

| MMM column | Source system | Extract | Bronze | Silver rule | Gold | Into the engine |
| --- | --- | --- | --- | --- | --- | --- |
| holiday | Retail calendar (Black Friday through New Year, plus civic days you actually promote) | Seeded spreadsheet or finance calendar | bronze_holiday_calendar: date, holiday_name, is_retail_peak | 0/1 on dim_date. Studio uses weeks 47–1. Do not use only statutory holidays — BFCM is the spike. | dim_date.is_holiday | Stage 1 and Stage 2 dummy. Stops Christmas from becoming “TV worked.” |
| payday | Payroll calendar (biweekly Friday is the usual Canadian / US pattern) | HR file, or a generated every-other-week rule | bronze_pay_calendar or a seed | 0/1. Not a holiday. Not “payday loan.” | dim_date.is_payday | Stage 2 only. People had cash; they did not search more because of the flag. |
| temperature | Environment Canada / NOAA station, or ERA5 | HTTP daily mean °C for the geo’s stations | bronze_weather: date, station, temp_c, precip | Average stations to geo, then to week. | fact_macro.temperature | Stage 1 and Stage 2. A shifter media did not buy. |

### Commercial controls (offer, price, shelf)

| MMM column | Source system | Extract | Bronze | Silver rule | Gold | Into the engine |
| --- | --- | --- | --- | --- | --- | --- |
| promo_depth | Promo calendar + PIM / ERP discounts | Nightly. promo_id, start, end, mechanic, depth_pct, featured_sku | bronze_promo, plus discount $ from orders | Depth = discount / list, volume-weighted to week × geo. 0.20 = 20% off. | fact_ops.promo_depth | Stage 2. A flyer week is not a search win. |
| price_index → price_dev | PIM / ERP list or average selling price | SKU × day price | bronze_price: sku, date, list_price, paid_price | Index to 100 in a reference year. price_dev = index − 100. Everyday price, not promo depth. | fact_ops.list_price_index | Stage 2. −32 $k per point in the studio DGP. |
| stockout_rate | Inventory / WMS / e-comm OOS flags | sku, date, on_hand, stockout_hours, fill_rate | bronze_inventory | Rate = stockout hours / selling hours (or 1 − fill_rate), rolled to week × geo. | fact_ops.stockout_rate | Stage 2. Media cannot convert an empty shelf. |

### Macro and competitive

| MMM column | Source system | Extract | Bronze | Silver rule | Gold | Into the engine |
| --- | --- | --- | --- | --- | --- | --- |
| competitor_sov | Pathmatics, Kantar, Sensor Tower, agency competitive | Weekly file or API: competitor, channel, estimated_spend | bronze_sov | Rival spend / (rival + yours) or vendor SOV 0–1, week × geo. National SOV is enough at first. | fact_sov | Stage 1 and Stage 2. Can wait a quarter if the contract is not signed. |
| unemployment | StatsCan Labour Force or FRED UNRATE | Monthly HTTP | bronze_macro_unemp | Carry the month forward onto each week. Percentage points, not a 0–1 share. | fact_macro.unemployment | Stage 2 only. |
| cpi_yoy | StatsCan CPI or FRED CPIAUCSL | Monthly HTTP | bronze_macro_cpi | 12-month % change, carried to weeks. Economy inflation, not your shelf price. | fact_macro.cpi_yoy | Stage 2 only. |

### Computed on the mart (no source system)

| MMM column | Built from | Rule | Into the engine |
| --- | --- | --- | --- |
| trend | week_start | Week index 0..N or a local linear trend. Not ingested. | Stage 2. “We grew anyway.” |
| seasonality / Fourier terms | week_start | Sine/cosine of week-of-year. Keep holiday as its own dummy. | Stage 1 and Stage 2. |
| cpm_index (optional) | spend / impressions | Auction cost shifter if you later add IV. Not required for default 2SLS. | Unused in the default engine path. |
| x̃_c, M̂ | Mart spend + GSC, plus θ, K | Computed inside the job, not stored as bronze. Persist on the run snapshot if you need to audit a week. | The actual regressors. Raw spend never enters OLS. |

### Calibration (after 2SLS, not a regressor)

| MMM object | Source | Extract | Bronze → gold | Into the engine |
| --- | --- | --- | --- | --- |
| Geo-lift prior | Matched-market / geo experiment platform | test_id, geo, treatment, start, end, channel, lift, CI | bronze_experiment → fact_experiment | Not a 2SLS column. After holdout, scale a channel’s total effect toward the experiment posterior, then re-run SLSQP. |
| model_run_log | The engine job | — | Coefficients, MAPE, mix, git SHA, mart as-of date, gates | Output, not an input. BI and the studio read the latest row. |

### What never enters the MMM mart

- Google Ads / Meta conversions and conversion_value (not Y).
- Paid branded clicks or branded CPC (not M).
- GA4 user_pseudo_id, email, device id (PII; stop at geo-week).
- Campaign, keyword, or creative ids (taxonomy collapses them in silver).
- Holiday uplift on a studio card — that is DGP-only fake spend. Production already has actualized weekly $.

## Quality, security, and operating model

- Tests. dbt: unique week×geo, spend ≥ 0, sales not null, channel in taxonomy, brand-query share between 0 and 1, FX rate present.
- Reconciliation. Weekly gold spend must tie to finance actuals within an agreed tolerance (agency fees called out separately).
- PII. Stop at geo-week. No emails, no user_id in gold. GA4 user tables stay in a restricted bronze zone.
- SCD. Campaign names change; dim_campaign is type 2 so last year’s “Brand_Search_CA” still maps to Paid Search.
- Model registry. Each run stores coefficients, holdout MAPE, allocation, git SHA, and mart snapshot date.
- Human loop. Finance signs off Y (net vs gross). Media ops signs off taxonomy. Science signs off holdout and geo-lift calibration before a budget is shipped.
Pipeline Parameters (M, Y, …) Card attributes Structural models Two equations Adstock Hill saturation Controls What each control is 2SLS How we estimate Attribution mROI SLSQP Diagnostics Production estimation

## Solving approach (what runs when you click Run model)

The studio is a closed loop: a known data-generating process, a two-equation structural model, chronological validation, then a constrained budget solver. Nothing is fit on the holdout weeks. The letters below (especially M) are the same symbols used in the seven steps and in the equations further down this tab.

- Build the weekly panel. Simulate 80–416 weeks of spend x, intent M, sales Y, and the full control set (or, in production, read mart_mmm_weekly).
- Transform media. Geometric adstock (θ), then Hill saturation (K). The result is x̃. Raw spend never enters the regressions.
- Split in time. First 80% of weeks = train. Last 20% = holdout. No shuffle, no k-fold that leaks the future. Index t is the week.
- Stage 1 OLS. Predict brand-search intent M from TOFU/MOFU transformed spend plus intent controls. This produces fitted intent M̂ (M-hat).
- Stage 2 OLS (2SLS). Predict sales Y from that fitted intent M̂, MOFU/BOFU transformed spend, and sales controls. The coefficient on M̂ is β_M.
- Attribute and score. Chain-rule totals (direct β plus indirect α × β_M), holdout R² / RMSE / MAPE, Durbin–Watson, VIF.
- Optimize. SLSQP reallocates a fixed weekly budget B. Naive objective uses only direct betas. Funnel-aware objective also values the intent that TOFU/MOFU create, inside min/max bounds L, U.

### What each parameter is

Read this as a glossary for the pipeline, not a second model. Production names are in the last column so you can map a warehouse field onto the same letter.

| Symbol | Name | What it is | What it is not | In production |
| --- | --- | --- | --- | --- |
| t | Week | Time index. One row of the panel is one week (optionally × geo). | Not a user, session, or campaign day. | week_start |
| M or M_t | Intent pool (the mediator) | How many people already want the brand this week — the demand that harvest media can convert. In the studio it is simulated brand-search volume. Awareness (TOFU/MOFU) raises M. If M is starved, paid search hits a wall even if you spend more on it. | Not sales. Not paid branded clicks (those are BOFU delivery). Not last-click conversions. Not “everyone on the internet.” | Organic branded queries from Google Search Console, or a brand Trends index. Column queries_M. Never use Google Ads branded clicks as M — that confuses the mediator with the harvest channel. |
| M̂ (M-hat) | Fitted intent | Stage 1’s prediction of M from media and controls only. Stage 2 uses this instead of raw M so a demand shock that hit search volume does not get credited to Paid Search. | Not a forecast of next quarter. Not a replacement for M on a dashboard — it is an instrumented regressor. | Built in the job after you fit Stage 1. You do not store M-hat as a source field. |
| Y or Y_t | Sales (the outcome) | What finance cares about this week, in $ thousands. The Stage-2 left-hand side. Attribution and the optimizer are both about moving Y. | Not platform-reported conversions, GA4 revenue, or add-to-cart. | Net sales or contribution margin from ERP/commerce. Pick one and keep it. Column sales_Y. |
| x_c or spend_c | Raw weekly spend | Dollars (studio: $k) on channel c in week t. The optimizer’s decision variable. | Not impressions, GRPs, or clicks — those are delivery, used only if you model exposure instead of spend. | spend_tv, spend_search, … on the weekly mart. |
| A_c,t | Adstock (memory) | Spend this week plus a fraction of last week’s leftover advertising stock: A_t = x_t + θ A_{t−1}. | Not a brand-equity survey. Just lagged spend. | Computed, not ingested. |
| θ (theta) | Adstock decay | How much of last week’s stock is still alive. Near 0.65 = TV-like memory. Near 0.08 = search dies in days. Half-life ≈ ln(0.5)/ln(θ) weeks. | Not ROI and not a discount rate in finance’s sense. | A channel card in the studio; estimated in production (outer grid on holdout RMSE). |
| K | Hill half-saturation | The adstock level where the channel is at half of its maximum effect. Spend far above K is on the flat part of the curve. | Not a budget cap. The optimizer can still spend above K; it just earns little. | Same as θ: known here, estimated in production. |
| x̃_c,t (x-tilde) | Transformed spend | Hill(adstock(x_c)). This is what actually enters Stage 1 and Stage 2. One number per channel per week, already carrying carryover and diminishing returns. | Not a dollar you can add up to the media invoice. | Computed from x, θ, K. |
| α_c (alpha) | Intent elasticity | How much one more unit of x̃_c raises M. TOFU and MOFU have alphas. BOFU’s alpha is forced to 0 (search does not create the intent pool; it spends it). | Not “awareness points” from a brand tracker unless you have chosen that as M. | Stage-1 coefficient. Indirect sales = α_c × β_M × x̃_c. |
| β_c (beta) | Direct sales elasticity | How much one more unit of x̃_c raises Y without going through M. MOFU and BOFU have betas. TOFU’s beta is forced to 0 (TV does not ring the register by itself in this structure). | Not last-click ROAS and not iROAS until you multiply by T'(x). | Stage-2 coefficient. Direct sales = β_c × x̃_c. |
| β_M (beta-M) | Intent-to-sales conversion | How much one more unit of the intent pool becomes weekly sales. It is the bridge: TOFU only pays off if β_M is real and positive. Total effect of a TOFU channel is α_c × β_M, not α_c alone. | Not a media channel. You cannot “buy β_M.” Conversion rate, price, stockouts, and the offer move it. | Stage-2 coefficient on M̂. |
| α0, β0 | Intercepts | Baseline intent and baseline sales when media and controls are at the origin of the design. Most of Y usually lives here plus calendar, not in media. | Not “brand value” unless you have identified it that way. | Stage-1 / Stage-2 constants. |
| η_t, ε_t | Residuals | η is unexplained intent (Stage 1). ε is unexplained sales (Stage 2). Holiday, promo, and stockouts are pulled out of these on purpose so media does not eat them. | Not a KPI. Do not minimize them by adding the outcome as a regressor. | Used for Durbin–Watson, VIF, and the bootstrap on the uncertainty pages. |
| B | Weekly budget | The envelope the optimizer must spend: Σ x_c = B. Default in the studio is the control you set at the top of tab 1. | Not annual plan dollars and not a recommended increase. The lift is reallocation inside B. | Finance’s weekly media envelope. |
| L_c, U_c | Trust-region bounds | Min/max weekly $k on the channel cards. Stops SLSQP from inventing a mix you have never observed (where Hill is unidentified). | Not the Hill K. You can have U > K. | About ±30% of last year’s weekly spend is the usual production rule. |
| N | Weeks | Length of the panel on the run bar. Train is the first 80%. | Not the holdout length (that is 0.2 N). | Row count of mart_mmm_weekly. |
| Seed | Random seed | Fixes DGP draws so a rerun matches. | Not a model hyperparameter. | Unused once you read a warehouse. |
| x̄_c | Mean spend $k | Average weekly spend used to simulate history on that card. | Not the SLSQP recommendation. | Historical mean of spend_*. |
| Holiday uplift | Holiday spend bump | Fractional extra spend in holiday weeks in the DGP (0.25 ≈ +25%). | Not the holiday dummy coefficient (+95 on Y). | Already inside actualized weekly spend. Do not double-count. |
| Flight on / cycle | TOFU flighting | On-weeks and cycle length that make TV/Radio lumpy. Identifies long memory vs season. | Not adstock θ. Flighting is when you buy; θ is how long it lingers. | The warehouse spend series already has flights. Drop these fields. |

### Where each card attribute is used

The long “what if I change this” catalog sits on tab 1 under Every attribute on this page (open Model studio, then scroll below the lanes). One-line map:

| Card field | Used by the DGP (fake history) | Used by 2SLS | Used by SLSQP |
| --- | --- | --- | --- |
| Name / funnel | Labels and exclusion (who may have α or β) | Same exclusions | Same exclusions |
| Adstock decay θ | Yes — builds A and x̃ | Yes — same θ, treated as known | Yes — inside T(x) and T'(x) |
| Hill K | Yes | Yes — known | Yes — saturation of the mix |
| Intent alpha | Yes — true α that creates M | Target to recover, not an input | Uses the estimated α |
| Direct beta | Yes — true β that creates Y | Target to recover | Uses the estimated β |
| Mean spend | Yes — level of the spend series | No (it sees the series, not the mean field) | No — starts from equal split of B |
| Min / max $k | No | No | Yes — L and U |
| Holiday uplift | Yes — Christmas pile-up | No (holiday dummy is a separate control) | No |
| Flight on / cycle | Yes — TOFU lumps | No | No |

Why M exists at all. A one-equation MMM is Y ~ media + controls. That equation cannot see that TV created the shoppers search later harvested, so it under-funds TOFU and over-funds BOFU. M is the missing middle: Stage 1 explains who wants the brand; Stage 2 explains who bought. You only need M if you believe awareness and harvest are not the same action. If you do not have a clean intent series, do not invent one from paid branded clicks — that is the search-bias trap this studio is built to show.

### Funnel roles (the other letters on the page)

TOFU (TV, Radio, OOH): α only. Raises M. Credit is 100% indirect (α × β_M).

MOFU (Social, YouTube): both α and β. Hardest split to estimate.

BOFU (Paid Search): β only. Converts existing M. Looks like the hero in last-click data.

### Controls in one line

Holiday, payday, promo depth, price, stockout, competitor SOV, unemployment, CPI, temperature, trend, season. They belong in the equations so media is not credited for a storm, a 20% off week, or Christmas. Their true DGP values are in the controls table below.

## Structural models (what “the model” actually is)

Structural means we write the story first, then estimate the numbers in that story. The story is: awareness raises intent M, intent plus harvest media raise sales Y, ads linger and saturate, and non-media shocks are controls. That is different from a reduced-form model (Y ~ all spend columns) or a black-box learner that predicts sales without saying who created demand. Four pieces work together; only the last two are “fit.”

### 1. Data-generating process (studio only)

What it is. A fake Canada-like retailer whose true alphas, betas, and control effects we know. The engine simulates spend, M, Y, and controls from the same two equations you estimate.

Why it exists. So “estimated vs true” on the studio tab is a real score, not a vibe. If 2SLS cannot recover TV’s alpha here, it will not recover it on messy warehouse data either.

What it is not. Not a forecast of your business. Production deletes this step and reads mart_mmm_weekly. The equations do not change.

### 2. Media transforms (adstock + Hill)

What it is. A two-step filter applied to every channel before regression: memory (θ) then diminishing returns (K). Output is x̃.

Why it exists. Last week’s TV still sells; the 200th search dollar does not sell like the first. Putting raw x in OLS pretends both facts are false.

What it is not. Not a second sales model. Weibull is in the engine as an alternate memory kernel; the studio uses geometric (one θ per channel).

### 3. Two-equation SEM, estimated by 2SLS

What it is. A structural equation model with two identities: an intent equation for M and a sales equation for Y. We estimate them with two-stage least squares so M is not treated as a free leftover in the sales line.

Why it exists. One sales regression cannot see that TV created the shoppers search later harvested. The mediator M is that missing middle.

What it is not. Not two unrelated forecasts. Stage 2 is not allowed to use raw search volume. Not a neural net and not last-click attribution.

### 4. SLSQP budget program

What it is. A constrained optimizer. Decision variables are next week’s spend mix. Objective is incremental sales from the structural equations. Constraint: spend sums to budget B inside min/max L, U.

Why it exists. Coefficients alone do not tell finance where to move money. The naive twin drops the α × β_M path so you can see the search-bias trap.

What it is not. Not a forecast of next quarter’s category. Not permission to spend 5× history. The lift is reallocation, not more budget.

### The two structural equations, in English then math

Intent equation (Stage 1 story). This week’s brand-search demand M equals a baseline, plus calendar and competitive weather, plus every TOFU/MOFU channel’s transformed spend times its alpha, plus a leftover shock η. Paid Search is absent here on purpose: harvest does not create the pool.

Sales equation (Stage 2 story). This week’s sales Y equal a baseline, plus trend, season, promo, price, stockouts, macro, plus β_M times the intent pool, plus every MOFU/BOFU channel’s transformed spend times its beta, plus leftover ε. TV/Radio are absent as direct betas on purpose: they only sell through M.

Let x̃_c,t = Hill(adstock(spend_c,t)). Those stories are:

```
Intent (who wants the brand this week)
M_t = α0
    + α_season * season_t
    + α_hol * holiday_t
    + α_sov * competitor_sov_t
    + α_temp * temperature_t
    + Σ_{c in TOFU,MOFU} α_c * x̃_c,t
    + η_t

Sales (who bought this week)
Y_t = β0
    + 1 * trend_t
    + 1 * season_t
    + β_hol * holiday_t
    + β_promo * promo_depth_t
    + β_price * price_dev_t
    + β_stock * stockout_rate_t
    + β_sov * competitor_sov_t
    + β_unemp * unemployment_t
    + β_cpi * cpi_yoy_t
    + β_temp * temperature_t
    + β_pay * payday_t
    + β_M * M_t
    + Σ_{c in MOFU,BOFU} β_c * x̃_c,t
    + ε_t
```
| Term | Plain reading |
| --- | --- |
| α0, β0 | Intent / sales you would still see if media and the listed controls were at the design origin. Most of retail Y lives here plus calendar. |
| α_season, α_hol, α_sov, α_temp | Non-media movers of brand search. Holiday and rival SOV also hit sales, so they appear in both equations. |
| Σ α_c x̃_c | The only media that is allowed to create demand. TOFU + MOFU. |
| η_t | Intent we cannot explain (a news event, a viral moment). This leftover is why raw M is endogenous in the sales line. |
| trend, season on Y | Category motion. Coefficients are 1 in the DGP so media cannot steal the year. |
| promo, price, stockout, unemp, CPI, payday | Commercial and macro shifters of Y that do not go through brand search (or only weakly). Omit them and media betas absorb a 20% off week. |
| β_M * M_t | The bridge. One more unit of intent becomes this many $k of sales. TOFU is worthless in this model if β_M is zero. |
| Σ β_c x̃_c | Direct harvest. MOFU + BOFU only. |
| ε_t | Sales we cannot explain after media, intent, and controls. |

Exclusion restrictions (the structure, not a software default): TOFU has α and no β. BOFU has β and no α. MOFU has both — that split is the hardest to identify. When we estimate, we replace raw M with Stage-1 fitted M̂. That substitution is what makes this 2SLS rather than OLS on observed search. A reduced-form MMM drops the first equation and puts every x̃ only in Y; TV then looks weak and search looks like a hero.

## Adstock (carryover)

Ads do not die at midnight on Sunday. Adstock is the leftover stock of exposure. Without it, a TV flight in week 10 cannot explain sales in week 12, so the model under-credits awareness and over-credits whatever harvested that leftover demand.

### Geometric (used in this studio)

Each week you add this week’s spend and keep a fraction θ of last week’s stock. One number per channel. High θ = long memory (TV). Low θ = dies in days (search).

```
A_t = spend_t + θ * A_{t-1}

Example: spend = 40, 0, 0 and θ = 0.6
  A = 40,  then 24,  then 14.4   (still 36% of the flight two weeks later)

Steady state at constant spend x:
  A_ss = x / (1 − θ)     e.g. x=40, θ=0.6 → A_ss = 100

Half-life ≈ ln(0.5) / ln(θ) weeks
  θ = 0.65 → ~1.6 weeks;  θ = 0.08 → a few days
```
Typical θ: TV 0.55–0.70, social 0.20–0.35, paid search 0.05–0.12. The studio treats θ as known on the channel card, matching the DGP, so 2SLS is tested fairly. In production you estimate θ (outer grid, last section).

### Weibull PDF (in the engine, not the default studio path)

Geometric always peaks at lag 0 and decays. Weibull can peak later — useful for TV if the first week is mostly make-goods and the brand effect arrives in week 2–3. k is shape, λ is scale, L is how many lags you keep.

```
w(ℓ) ∝ (k/λ) * ((ℓ+1)/λ)^{k−1} * exp(−((ℓ+1)/λ)^k)
A_t = Σ_{ℓ=0}^{L−1} w(ℓ) * spend_{t−ℓ}

k < 1  peak at lag 0 (search-like)
k > 1  delayed peak (TV-like)
```

## Hill saturation (diminishing returns)

The 200th weekly dollar on a channel does not buy the same increment as the first. Hill maps adstock A into a 0–1 effect. K is the adstock level where you are at half of the channel’s maximum. Spend far above K is on the flat part of the curve — that is where the naive optimizer loves to park search.

```
h(A) = A^s / (K^s + A^s)

h'(A) = s * K^s * A^{s−1} / (K^s + A^s)^2

This studio uses s = 1 (smooth concave, not an S-curve):
  h(A) = A / (K + A)
  h'(A) = K / (K + A)^2

At A = K, h = 0.5 (half-saturation).
At A = 3K, h = 0.75 — three times the stock, not three times the effect.
```
s > 1 would add a slow start (S-shape). We do not use that here; weekly national spend is already past the toe of the curve. The optimizer never uses raw spend. It uses the steady-state composition of adstock then Hill, and the slope of that composition for mROI:

```
T(x)  = h(x / (1 − θ))           long-run effect of a constant weekly x
T'(x) = h'(x / (1 − θ)) / (1 − θ)  extra effect of one more $1k, forever
```
K is not a budget cap. SLSQP can still spend above K; it just earns little, so a funnel-aware optimum usually pulls search back from that wall. In the studio K is on the channel card. In production it is estimated with θ.

## Real-world controls and DGP values

A control is anything that moves M or Y that is not your media. Leave it out and 2SLS will give that movement to TV, search, or β_M (omitted-variable bias). The table is the studio’s truth: simulated range, the DGP coefficient on Y ($k of weekly sales), whether it also hits M, and why finance should care. In production you ingest these; you do not invent them.

| Control | Simulated range | True effect on Y | Also on M? | Why it belongs in MMM |
| --- | --- | --- | --- | --- |
| Holiday dummy | weeks 47–1 | +95 | yes, +22 on M | Demand and media both spike; omit it and TV/search steal holiday sales. |
| Payday dummy | biweekly 0/1 | +28 | no | Cash-flow weeks in retail, independent of ads. |
| Promo depth | 0.00–0.48 | +240 per 1.0 depth | no | A 20% off week is +48 $k. Media stacked on promo looks like media if you skip this. |
| Price vs 100 | index 93–111 | −32 per point | no | List/net price. A +3 index move is about −96 $k. |
| Stockout rate | 0–0.28 | −480 per 1.0 rate | no | Media cannot convert what is not on the shelf. Holiday stockouts are common. |
| Competitor SOV | 0.12–0.62 | −210 | yes, −55 on M | Rival share of voice crowds brand search and sales. |
| Unemployment | 4.4–9.2 pp | −22 per pp | no | Labour-market drag on discretionary spend. |
| CPI YoY | 0.4–6.8 pp | −14 per pp | no | Inflation tax on real demand. |
| Temperature C | roughly −12 to 28 | +1.6 per C | yes, +0.45 on M | Weather for seasonal categories; also a cheap instrument-like shifter. |
| Trend / season | slope 0.08; Fourier mix | coefficient 1 on both series | season 0.5 on M | Baseline category motion. Media should not eat the year. |

Identification idea: controls must move when media does not (or not one-for-one). Temperature and unemployment help. Holiday is the dangerous one because everyone advertises then — that is why lumpy TOFU flighting exists in the DGP.

### What each control actually is

A dummy is a 0/1 switch (the week is a payday, or it is not). A rate / index / depth is a continuous number. Effects below are the studio DGP truths on weekly sales Y in $ thousands. None of these are media channels. You do not buy them on a card; the engine simulates them, then 2SLS estimates their betas so TV and search cannot steal them.

| Control | Kind | What it measures | Example week | True effect in this studio | Where it comes from in production |
| --- | --- | --- | --- | --- | --- |
| Holiday dummy | 0 or 1 | Is this a holiday-demand week? Studio: weeks 47–1 (late November through New Year). Both shoppers and media ramp, which is why omitting it gives Christmas to TV/search. | Week of Black Friday = 1. A quiet March week = 0. | +95 $k on Y when the flag is 1. Also +22 on intent M. | dim_date.is_holiday (your retail calendar, not just statutory holidays). |
| Payday dummy | 0 or 1 | Is this a biweekly pay week? Many Canadian / US hourly households get paid every two weeks. Those weeks have more cash for grocery and discretionary baskets even if nobody advertised. The studio turns the flag on when week_of_year mod 4 is 0 or 2. | A Friday pay week = 1. The week in between = 0. About half the year is 1. | +28 $k on Y when the flag is 1. Does not enter the intent equation — people already wanted the brand; they just had cash. | A payroll calendar (every other Friday), not an ads API. Do not confuse with the holiday dummy. |
| Promo depth | 0.00–0.48 continuous | How deep the discount is this week, as a share of list price. 0.00 = no deal. 0.20 = 20% off. 0.40 = 40% off. Feature/display weeks sit higher. This is the offer, not the media that advertised the offer. | A 20% TPR week = 0.20 → about +48 $k (= 0.20 × 240). A holiday stack of ~0.22 depth is common in the DGP. | +240 $k on Y per 1.0 of depth (a theoretical 100% off). Sales only; not on M. | Promo calendar / PIM: mechanic, depth %, featured SKU. Average to week × geo. If you skip this, a flyer week looks like a search win. |
| Price vs 100 (price_dev) | Index points | List/net price index minus 100. 100 = the reference year. 103 = prices 3% above reference. This is regular price, not the promo depth on top of it. The two are different levers: everyday price vs this week’s deal. | Index 103 → price_dev = +3 → about −96 $k (= 3 × −32). | −32 $k on Y per +1 index point. Sales only. | ERP / PIM average selling or list price, indexed. Not Google Ads CPC. |
| Stockout rate | 0.00–0.28 share | Share of SKU-hours the item was not on the shelf (or site OOS). 0.00 = fully in stock. 0.10 = 10% of the assortment-hours missing. Media cannot convert a shopper if the SKU is gone. Holiday weeks in the DGP run hotter stockouts on purpose. | 10% OOS = 0.10 → about −48 $k (= 0.10 × −480). A bad holiday week at 0.20 is −96 $k. | −480 $k on Y per 1.0 rate (a theoretical 100% OOS). Sales only. | Inventory: on-hand, stockout hours, fill rate. Complement of fill-rate, rolled to week × geo. |
| Competitor SOV | 0–1 share | Share of category voice that rivals own this week. 0.40 means competitors bought about 40% of estimated category media. High SOV crowds your brand search and steals sales. It is the only competitive control that also hits M. | SOV 0.40 vs 0.20 is +0.20 → about −42 $k on sales and −11 on intent. | −210 $k on Y per 1.0 share. Also −55 on M. | Pathmatics, Kantar, Sensor Tower, or an agency competitive estimate. Hardest control to get; do not block the lake on it in the first 90 days. |
| Unemployment | Percentage points | Labour-market rate (StatsCan / FRED style). When more people are out of work, discretionary baskets shrink. Moves slowly compared with a TV flight, which is why it helps identify media separately from the economy. | A +1 pp rise (e.g. 6% → 7%) is −22 $k that week, every week it stays there. | −22 $k on Y per percentage point. Sales only. | StatsCan Labour Force or FRED UNRATE, carried forward across weeks in the month. |
| CPI YoY | Percentage points | 12-month inflation. Higher CPI is a tax on real demand (people buy less volume at the same nominal price). Separate from your own price index: CPI is the economy; price vs 100 is your shelf. | CPI YoY 4.0 vs 2.0 is +2 pp → −28 $k. | −14 $k on Y per percentage point. Sales only. | StatsCan CPI or FRED CPIAUCSL, year-over-year, monthly carried to weeks. |
| Temperature | Degrees C | Weekly mean air temperature (Southern Ontario-like in the DGP). Weather moves seasonal categories and a bit of brand search. It is a useful shifter because heat waves are not bought by the media team. | +5 C vs last week is about +8 $k on sales and a small lift on M. | +1.6 $k on Y per °C. Also +0.45 on M. | Weather station or ERA5 weekly mean for the geo. |
| Trend | Week index | Slow category drift (population, distribution, brand equity). A straight line through the years. Media should not be credited for “we grew 3% a year anyway.” | Coefficient 1.0 in the DGP on the scaled trend series. | Baseline on Y only (not a media lever). | Computed: week number or a local linear trend. Not ingested. |
| Seasonality | Fourier mix | The repeating annual shape (back-to-school, summer lull, Q4). Built from sine/cosine of the week, not from a holiday dummy. Holiday is the extra spike on top of season. | Coefficient 1.0 on Y, 0.5 on M in the DGP. | Baseline calendar. Omit it and Q4 becomes “TV worked.” | Computed from week_start. Keep holiday as its own dummy; do not make season do both jobs. |

Dummy vs depth, in one line. Payday and holiday answer “was this that kind of week?” (0 or 1). Promo depth and stockout rate answer “how strong was it?” (0.20 is twice 0.10). Price, unemployment, CPI, and temperature are measured levels. Holiday uplift on a channel card is different again: that is extra media spend at Christmas, not the holiday dummy on sales.

## Two-stage least squares

The problem. Observed brand search M is endogenous: ads, season, and unobserved demand shocks all move it. If you drop raw M into the sales equation (ordinary OLS), any week people wanted the brand for a reason you did not measure looks like a win for Paid Search — because search spend and that shock travel together. That is the search-bias trap.

The fix. 2SLS keeps only the part of M that TOFU/MOFU and the listed controls can explain. That part is M̂. Stage 2 is then a sales regression on M̂ plus harvest media plus sales controls. Search can no longer steal a demand shock that awareness (or Christmas) created.

```
Stage 1  (train only) — “who wanted the brand, that we can explain?”
  M_t = Z_t' α + η_t
  Z_t = [1, season, holiday, SOV, temp, x̃_TOFU, x̃_MOFU]
  M̂_t = Z_t' α̂

Stage 2 — “given that explained intent, who bought?”
  Y_t = W_t' β + ε_t
  W_t = [1, trend, season, holiday, promo, price_dev, stockout,
         SOV, unemp, CPI, temp, payday, M̂_t, x̃_MOFU, x̃_BOFU]

Holdout: build M̂_test with α̂ from train, then predict Y_test with β̂ from train.
Never refit on the last 20% of weeks.
```
| If you instead… | What goes wrong |
| --- | --- |
| Regress Y on raw M and search | Search beta is too big. TV alpha is never seen. |
| Regress Y on all x̃ and drop M | Reduced-form MMM. TV looks weak; you defund awareness. |
| Use last-click | You see only harvest paths. Radio can be $0 with a real α. |
| Fit Stage 2 on test weeks | Holdout dies. Finance gets an in-sample fairy tale. |

Each stage is ordinary least squares. Closed form and the three scores we print:

```
θ̂ = (X'X)^{−1} X'y     (here θ̂ is the coefficient vector, not adstock)

R²   = 1 − SSE / SST              share of variance explained
MAPE = (100/n) Σ |y_t − ŷ_t| / |y_t|   typical percent miss
RMSE = sqrt( (1/n) Σ (y_t − ŷ_t)² )    typical $k miss
```

## How the studio estimates (step by step)

This is the code path behind Run model. Transforms are treated as known so the page can ask a clean question: did 2SLS recover the funnel when carryover and saturation were not the thing being searched?

- Read θ_c, K_c, and Hill shape s = 1 from the channel cards (known, matching the DGP).
- Compute adstock A_c,t and transformed spend x̃_c,t for every channel and week.
- Cut at week floor(0.8 N). Train = past. Holdout = future. No shuffle.
- Fit Stage 1 by OLS on train. Store every α̂, including control alphas.
- Build M̂ on train (fitted values) and on holdout (predict with the same α̂).
- Fit Stage 2 by OLS on train. Store β̂_M, direct β̂_c, and control betas.
- Score holdout weeks (R², MAPE, RMSE). Durbin–Watson uses Stage-2 train residuals.
- VIF on the Stage-1 and Stage-2 train design matrices — a high VIF means two columns are telling the same story.
- Attribute (next section) and run both SLSQP problems (naive vs funnel).
What is not estimated here, and would be in production: adstock θ, Hill K and s, a geo hierarchy, and Bayesian priors from lift tests. See the last section.

## Attribution (who gets credit for sales)

Attribution here is not a user path. It is the chain rule on the structural equations: how much of fitted sales came through a channel’s own beta versus through the intent it created. Last-click reports approximately see only the first line. Funnel MMM exists to recover the second.

```
Direct_c   = Σ_t  β̂_c * x̃_c,t          MOFU/BOFU only (else 0)
Indirect_c = Σ_t  α̂_c * β̂_M * x̃_c,t    TOFU/MOFU only (else 0)
Total_c    = Direct_c + Indirect_c

Chain rule, one week:
  dY / d x̃_c = ∂Y/∂x̃_c + (∂Y/∂M)(∂M/∂x̃_c)
              = β_c + β_M α_c

Example: TV has β=0, α=0.8, β_M=2.0 → total = 1.6 sales units per unit x̃
         Search has β=1.4, α=0 → total = 1.4. Search can still win last-click
         and lose this table if TV created the pool search harvested.
```
The stacked bar on the studio tab is these two sums over the full sample. Navy = Direct. Teal = Indirect. A tall teal bar on TV or Radio is the point of the model.

## Marginal ROI (the next dollar, not the average dollar)

Average ROI is total attributed sales over total spend — backward-looking, and kind to a saturated channel that was great at the start of the curve. mROI is the extra sales from one more $1k at the mix you are about to recommend. That is the number the optimizer equalizes. Below 1.0 means the last dollar returned less than it cost.

```
At constant weekly spend x_c (steady state):

mROI_c = [ β_c + β_M α_c ] * T'(x_c)

T'(x) = h'(x/(1−θ)) / (1−θ)

Equimarginal rule: at an interior optimum,
  mROI_c = λ   for every channel that is not stuck on a min or max bound.
```
If one channel’s total mROI stays much higher than the others, a min/max bound is binding. That is a trust-region result, not a solver failure. Direct mROI uses only β_c; total mROI adds the β_M α_c path — that is why TV can beat search at the margin after you reallocate.

## Budget optimizer (SLSQP)

SLSQP is Sequential Least Squares Programming: a numerical solver for “maximize this smooth function, subject to equalities and bounds.” It is not a second model. It takes the fitted alphas/betas as given and moves the spend vector. Two twins run from the same start (equal split of B).

```
max_x   R(x) = β_M * Σ_{c: intent} α_c T_c(x_c)
               + Σ_{c: direct} β_c T_c(x_c)

s.t.    Σ_c x_c = B          spend the whole weekly envelope
        L_c ≤ x_c ≤ U_c      do not leave the historical trust region

Funnel-aware: uses the full R(x) (direct + mediated).
Naive twin:    drops the β_M α_c term — harvest-only, the search-bias trap.

Net lift = funnel R(x*_funnel) − funnel R(x*_naive)
Same B, different mix, both scored on the funnel surface
so the comparison is apples-to-apples.
```
SLSQP linearizes the Lagrangian and updates a BFGS-like Hessian. If it parks on a bound, read the mROI table: the channel that still wants more money is the one whose total mROI is highest. Do not loosen U past ~30% above history just to satisfy the solver — Hill is unidentified out there.

## Diagnostics and what they mean

These are gates, not vanity fit stats. A beautiful in-sample R² with a dead holdout is a model that memorized the past. Ship the mix only when holdout track, residual structure, and coefficient recovery (studio) all agree.

| Metric | Formula / rule | How to read it |
| --- | --- | --- |
| Holdout R² | 1 − SS_res / SS_tot on last 20% | Share of future weekly sales the sales equation tracks. >0.75 strong; <0.5 do not ship the mix. High train R² with low holdout R² means leakage or an overfit transform. |
| MAPE | mean /e///y/ | Typical percent miss. This is the number to give finance for “how wrong could next quarter be if we only had the model.” |
| RMSE | sqrt(mean e²) | Typical miss in $k. Use this to compare two specs; MAPE to talk to finance. |
| Durbin–Watson | Σ (e_t − e_{t−1})² / Σ e_t² | ~2 means leftovers look like white noise. <1.5 means weeks still cluster (missing lag, Fourier, or a promo you did not code). Then residual bootstrap on the uncertainty tab is too optimistic — believe the block bootstrap. |
| VIF | 1 / (1 − R²_j) from regressing column j on the others | >10 those two regressors move together; >30 the split between them is not identified (often MOFU vs M̂, or two lookalike social buys). Collapse the taxonomy or add a prior. |
| Abs error vs true | /estimate − DGP truth/ | Studio only. Small error on TOFU α and on β_M means the mediator was identified. A large error on MOFU direct β is common: that channel sits in both stages. |

## How to estimate the same system on real data

Same two equations, same 2SLS, same SLSQP. Three things change: you read a warehouse mart instead of the DGP, you search θ and K instead of reading them off a card, and you calibrate totals to a geo-lift before anyone ships spend. The studio skips that outer search on purpose — it is the textbook check that the funnel is identified when transforms are known.

- Freeze the grain. One row per week × geo. Y = net sales or margin, never platform conversions. M = organic branded queries, never paid branded clicks. The source → bronze → silver → gold → mart path for every column is on the playbook tab, Source → MMM flow.
- Grid or nested optimize θ and K. Outer loop: candidate (θ_c, K_c). Inner loop: the 2SLS above. Pick the pair that minimizes rolling-origin holdout RMSE, not in-sample R². Optionally use Weibull (k, λ) for TV.
- Keep controls that move. Drop a control only if it has no variation. Do not drop holiday because it is collinear with TV — that is omitted-variable bias, the failure mode this engine was built to show.
- Regularize if VIF explodes. Ridge / Bayesian prior toward geo-lift, or collapse lookalike channels (feed + stories → Social).
- Calibrate. Multiply a channel’s total effect so that implied lift matches a geo experiment’s posterior, then re-run SLSQP inside ±30% of last year’s weekly spend.
- Do not extrapolate. Bounds L_c, U_c should be historical min/max padded by ~30%. Hill curves are unidentified in the far tail.
The studio skips the outer θ/K search because the DGP already used those values. That lets the page show whether 2SLS and the controls recover the funnel when the transforms are known — the usual textbook identification check before you add a nonlinear search on real messy data.

What you deploy Phase 0 on both clouds Warehouse contract From-zero command line Azure steps Amazon Web Services steps This repo → services Code you must change CI/CD and secrets Weekly cadence First 90 days Go-live gates

## What this project becomes in the cloud

Today this repo is a laptop studio: Flask on port 5050, a synthetic DGP, 2SLS, SLSQP, and in-memory last-run caches. Production keeps those equations and lands the exact warehouse from tab 2 (X Canada: bronze → silver → gold dims/facts → mart_mmm_weekly). Azure and AWS are two landings of that same star schema. Do not invent extra tables and do not rewrite 2SLS as AutoML.

#### 1. Identity + network

One tenant/org, Entra ID or IAM Identity Center, a private VNet/VPC, no public lake.

#### → 2. Ingest

Ads APIs, ERP/commerce, GSC, Nielsen SFTP, FRED/StatsCan. Land raw files only.

#### → 3. Lake + mart

Bronze / silver / gold. dbt builds mart_mmm_weekly. PII stops before gold.

#### → 4. Engine job

run_mmm_engine.py as a scheduled container: 2SLS, holdout, SLSQP, bootstrap.

#### → 5. Registry

Coefficients, MAPE, mix, git SHA, mart snapshot date. Finance reads this, not a notebook.

#### → 6. Studio + BI

This Flask app behind SSO. Power BI or QuickSight on gold and the run log.

```
empty cloud account
    |  billing cap, region (Canada Central / ca-central-1), naming
    v
identity + private network
    |  connectors + object store
    v
bronze → silver → gold.mart_mmm_weekly
    |  weekly job: this Python engine (no DGP)
    v
gold.model_run_log + container registry image
    |
    +→ private studio (this webapp) for science
    +→ BI pack for finance
    +→ Ship / Watch / Kill from the uncertainty suite
```

## Phase 0 — do this before you click a service (both clouds)

- Pick a home region and stay there. Canadian retailer data: Azure Canada Central or AWS ca-central-1. Do not split the lake across US and Canada “because GPU was cheaper.”
- Turn on billing alerts on day one. Hard monthly cap for the sandbox. Most first-year MMM cost is the warehouse and the BI seats, not the 2SLS job.
- Create three environments. dev (synthetic + a masked 26-week slice), stage (full mart, no SSO to the business), prod (SSO, no DGP, finance sign-off). Same names on resource groups / accounts.
- Name things once. X Canada: x-mmm-{env}-lake, x-mmm-{env}-job, x-mmm-{env}-studio. Same strings appear in ADF, Glue, IAM, and the run log.
- Put this repo in Git with branch protection. Main deploys to stage. A tagged release deploys to prod. The model run log stores the git SHA.
- Containerize the studio before you buy a warehouse. If the image does not run locally with docker run -p 8000:8000, you are not ready for Container Apps or ECS.
- Decide Y and M with finance before ingest. X: Y = net box revenue on ship-week (after credits/cancels). M = GSC organic branded clicks (x, x). Not Google conversion_value. Cloud will not fix a wrong grain.
```
# image used on both clouds (Linux; gunicorn is not for Windows laptops)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY . .
ENV PORT=8000
EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "webapp.app:app"]
```
Local Windows stay on python run_webapp.py (port 5050). The container is the production contract. GET /health already returns 200 so the load balancer does not execute 2SLS.

## Warehouse contract you must land (same objects on Azure and AWS)

Do not design a new model in the cloud. Land the star schema from tab 2 — data model and the X map from X case. Folder names below are the contract. Azure uses ADLS containers; AWS uses the same paths under one S3 bucket.

```
lake / {bronze|silver|gold}/
  bronze/google_ads/x_ca/dt=YYYY-MM-DD/          raw cost_micros, campaign_name, geo
  bronze/x_orders/dt=YYYY-MM-DD/                 ship_ts, plan, list, paid, credit, cancel, new_vs_repeat
  bronze/gsc/x_ca/dt=YYYY-MM-DD/                 query, clicks, impressions, country
  bronze/meta_ads/x_ca/dt=YYYY-MM-DD/            later
  bronze/tv_invoice/dt=YYYY-MM-DD/                later
  bronze/statscan/unemp/dt=YYYY-MM/               monthly
  bronze/statscan/cpi/dt=YYYY-MM/
  bronze/weather/ca/dt=YYYY-MM-DD/
  bronze/promo_calendar/                          seed
  bronze/holiday_calendar/                        seed
  silver/media_daily/                             date, geo, channel_name, campaign_id, spend_cad, impressions
  silver/sales_daily/                             ship_date, geo, gross, discount, returns, net_cad
  silver/intent_daily/                            date, geo, branded_gsc_clicks
  silver/ops_daily/                               date, geo, promo_depth, price_index, stockout_rate
  gold/   (SQL schema, not files)
    dim_date, dim_geo, dim_channel, dim_campaign, dim_product, dim_promo
    fact_media_spend, fact_search_intent, fact_web, fact_sales
    fact_ops, fact_macro, fact_sov, fact_experiment
    mart_mmm_weekly, model_run_log, allocation_recommended
```
Every bronze object keeps vendor names plus _load_ts, source_system, source_file. Silver is the first place cost_micros / 1e6 becomes spend_cad. Gold keys match the field dictionary. The engine SELECTs only gold.mart_mmm_weekly where geo_key = 0.

| First X feeds (do these before TV/Meta) | Bronze path | Gold target |
| --- | --- | --- |
| Google Ads CA (Search + PMax + YouTube) | bronze/google_ads/x_ca/ | fact_media_spend → spend_search, spend_youtube |
| Order / subscription ledger (ship-week net $) | bronze/x_orders/ | fact_sales.net_sales → sales_Y |
| Google Search Console brand queries | bronze/gsc/x_ca/ | fact_search_intent.branded_gsc_clicks → queries_M |
| Seeded holiday + payday calendars | bronze/holiday_calendar/ | dim_date.is_holiday, is_payday |

## From-zero CLI (run once per environment)

These are the first commands after Phase 0. They create the empty landing zone that A1–A7 / W1–W7 then fill. Replace {env} with dev, stage, or prod. Do not create prod until stage has 80 green weeks.

### Azure (Canada Central)

```
az login
az account set --subscription <sub>
az group create -n rg-x-mmm-{env} -l canadacentral
az network vnet create -g rg-x-mmm-{env} -n vnet-x-mmm-{env} \
  --address-prefix 10.40.0.0/16 \
  --subnet-name snet-data --subnet-prefix 10.40.1.0/24
az network vnet subnet create -g rg-x-mmm-{env} --vnet-name vnet-x-mmm-{env} \
  -n snet-app --address-prefix 10.40.2.0/24
az storage account create -g rg-x-mmm-{env} -n stxmmm{env} \
  -l canadacentral --sku Standard_GRS --kind StorageV2 \
  --enable-hierarchical-namespace true --https-only true --min-tls-version TLS1_2 --allow-blob-public-access false
az storage fs create --account-name stxmmm{env} -n bronze
az storage fs create --account-name stxmmm{env} -n silver
az storage fs create --account-name stxmmm{env} -n gold
az keyvault create -g rg-x-mmm-{env} -n kv-x-mmm-{env} -l canadacentral --enable-purge-protection true
az identity create -g rg-x-mmm-{env} -n id-x-mmm-{env}
az acr create -g rg-x-mmm-{env} -n acrxmmm{env} --sku Basic -l canadacentral
az datafactory create -g rg-x-mmm-{env} -n adf-x-mmm-{env} -l canadacentral
az containerapp env create -g rg-x-mmm-{env} -n cae-x-mmm-{env} -l canadacentral
```

### AWS (ca-central-1)

```
aws configure  # region ca-central-1
aws s3api create-bucket --bucket x-mmm-lake-{env} \
  --region ca-central-1 \
  --create-bucket-configuration LocationConstraint=ca-central-1
aws s3api put-public-access-block --bucket x-mmm-lake-{env} \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket x-mmm-lake-{env} \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket x-mmm-lake-{env} \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms"}}]}'
aws s3api put-object --bucket x-mmm-lake-{env} --key bronze/google_ads/x_ca/
aws s3api put-object --bucket x-mmm-lake-{env} --key bronze/x_orders/
aws s3api put-object --bucket x-mmm-lake-{env} --key bronze/gsc/x_ca/
aws glue create-database --database-input '{"Name":"x_mmm_{env}"}'
aws ecr create-repository --repository-name x-mmm --region ca-central-1
aws secretsmanager create-secret --name gads-customer-id-ca --region ca-central-1
aws redshift-serverless create-namespace --namespace-name x-mmm-{env}
aws redshift-serverless create-workgroup --workgroup-name x-mmm-{env} \
  --namespace-name x-mmm-{env} --base-capacity 8 --publicly-accessible false
```
After the CLI: seed dim_date / dim_geo / dim_channel (A3 / W3), then stand up the three bronze pipelines. Do not run the engine until dbt tests pass on ≥ 80 weeks.

## Azure — end-to-end technical steps

Home region is Canada Central. Use one Azure subscription and three resource groups. Gold structured query language tables live in Microsoft Fabric Warehouse (or Azure Synapse serverless if Fabric is not licensed). Azure Data Factory copies raw files. The data build tool turns silver files into gold tables. Azure Container Apps run this repository. X names are used below; change the x prefix only if the brand code changes. Resource names such as adf-x-mmm-prod stay as identifiers; the prose never shortens service names.

### A0. Identity, subscription, and names

- In Microsoft Entra Identifier, create three security groups: mmm-platform (network, vault, billing), mmm-science (stage deploy and gold read), mmm-finance-read (Power BI and the run log only). The subscription Owner is a cloud-only break-glass account. A person’s daily login is never Owner.
- Create or select one Azure subscription. On day one open Cost Management + Billing and add a monthly budget with email to platform and finance. Set a hard sandbox cap so a misconfigured copy activity cannot run all month unnoticed.
- Create three resource groups in canadacentral: rg-x-mmm-dev (synthetic data generating process plus a masked 26-week slice), rg-x-mmm-stage (full mart, no business single sign-on), rg-x-mmm-prod (single sign-on, warehouse only, finance sign-off). Do not put development and production in the same resource group or the same storage account.
- Lock names before you click Create. Storage account stxmmm{env} (24 characters, lowercase). Key Vault kv-x-mmm-{env}. Azure Data Factory adf-x-mmm-{env}. Azure Container Registry acrxmmm{env}. Studio Container App ca-x-mmm-studio-{env}. Engine Container Apps Job caj-x-mmm-engine-{env}. User-assigned managed identity id-x-mmm-{env}. Virtual Network vnet-x-mmm-{env}.
- Register resource providers if the subscription is new: Microsoft.Storage, Microsoft.KeyVault, Microsoft.DataFactory, Microsoft.App, Microsoft.ContainerRegistry, Microsoft.Network, Microsoft.Insights, Microsoft.OperationalInsights, Microsoft.Fabric (or Microsoft.Synapse).

### A1. Network, private endpoints, and secrets

- Create Virtual Network vnet-x-mmm-{env} with address space 10.40.0.0/16. Subnet snet-data (10.40.1.0/24) holds Azure Data Lake Storage private endpoints, Microsoft Fabric or Synapse, and the Azure Data Factory integration runtime. Subnet snet-app (10.40.2.0/24) holds Azure Container Apps. Add a third subnet snet-pe (10.40.3.0/24) reserved for private endpoints if your landing-zone standard requires it.
- Turn on a network security group on each subnet. Allow port 443 from snet-app to snet-data. Allow Azure Data Factory to reach Google Ads, Google Search Console, Statistics Canada, and the X order host on port 443 (and port 22 only if the ledger arrives by Secure File Transfer Protocol). Deny inbound from the public internet on the lake and the warehouse.
- Create private endpoints: storage blob, storage data-lake file system (dfs), Key Vault, and the Fabric / Synapse structured query language endpoint. Register a private Domain Name System zone for each (privatelink.blob.core.windows.net, privatelink.dfs.core.windows.net, privatelink.vaultcore.azure.net, and the Fabric warehouse zone). Azure Data Factory and Container Apps must resolve those names to the private internet protocol address, not the public one.
- Create Key Vault kv-x-mmm-{env} with purge protection and soft delete. Soft-delete retention is 90 days in production. Disable public access; allow the Virtual Network and the Azure Data Factory integration runtime only.
- Create empty secret names first, then fill values after the Google Ads and X credentials exist. Exact names (the application reads these strings): gads-developer-token (Google Ads manager developer token), gads-client-id and gads-client-secret (OAuth application), gads-refresh-token (offline access for the Canada customer), gads-customer-id-ca (X Canada customer identifier, digits only), gsc-service-account-json (Google Search Console service-account key as one string), x-orders-sql-dsn (Open Database Connectivity string or Secure File Transfer Protocol password for the order ledger), mmm-warehouse-odbc (Open Database Connectivity string to Fabric Warehouse), statscan-app-key if Statistics Canada requires a registered application key.
- Create user-assigned managed identity id-x-mmm-{env}. Assign it to Azure Data Factory, the Container Apps environment, the engine job, and the data build tool job. Role assignments on the storage account: Storage Blob Data Contributor. On Key Vault: Key Vault Secrets User. On Fabric Warehouse: database data reader for the studio, database data writer for the engine job only. Never put storage access keys or a personal token inside a pipeline parameter or a Docker image.

### A2. Lake folders that match the warehouse tab

- Create storage account stxmmm{env} as Azure Data Lake Storage Generation 2: hierarchical namespace on, kind StorageV2, replication Standard geo-redundant storage, Transport Layer Security 1.2 minimum, HTTPS only, public blob access disabled, shared key access disabled after the managed identity works, blob soft delete 14 days, container soft delete 14 days.
- Create three file systems (containers) with those exact names: bronze, silver, gold. Gold tables live in Fabric Warehouse structured query language. The gold file system only stores run snapshots (parquet copies of coefficients and recommended mix).
- Create the X prefixes from the warehouse contract, including bronze/google_ads/x_ca/, bronze/x_orders/, bronze/gsc/x_ca/, bronze/statscan/unemp/, bronze/statscan/cpi/, bronze/weather/ca/, bronze/holiday_calendar/, bronze/promo_calendar/, silver/media_daily/, silver/sales_daily/, silver/intent_daily/, silver/ops_daily/, gold/runs/. An empty _SUCCESS marker file in each prefix is enough to prove the path exists.
- Lifecycle management: bronze objects older than 90 days move to Cool; older than 365 days move to Archive. Silver stays Hot. Gold run snapshots stay Hot for 400 days so finance can restore last year’s mix.
- Storage firewall: selected Virtual Networks and the Azure Data Factory integration runtime only. Add the platform group’s jump host if they must browse with Storage Explorer. Science does not get Contributor on bronze in production.

### A3. Seed the dimensions before any ads pull

- Create a Microsoft Fabric workspace ws-x-mmm-{env} in Canada Central, attached to a capacity you already pay for (or Azure Synapse serverless if that is the firm standard). Create a Warehouse named wh_x_mmm_{env}. Create three schemas: bronze, silver, gold.
- Load gold.dim_date for every calendar day from 2019-01-01 through today plus 400 days. Required columns: date_key (integer yyyymmdd), calendar_date, week_start_mon (Monday of that week, America/Toronto), iso_week, iso_year, month_start, is_holiday, is_payday. Holiday list is the X retail calendar: New Year’s week, Super Bowl, Canada Thanksgiving, Black Friday and Cyber Monday, Christmas week. is_payday equals 1 on every other Friday (Canadian biweekly pay). Do not leave these as file-only seeds; the engine joins them as structured query language.
- Load gold.dim_geo with one national row: geo_key = 0, country = 'CA', region null, dma_code null, geo_name = 'Canada'. Provincial rows come later. The engine always filters geo_key = 0.
Load gold.dim_channel with the four X parent channels. Funnel values in documentation are full words (top of funnel, middle of funnel, bottom of funnel); the stored codes stay as in the warehouse tab so the mart column names do not change:
```
(1, 'TV',          'TOFU', 'broadcast', 'agency',     null)
(2, 'YouTube',     'MOFU', 'video',     'Google Ads', null)
(3, 'Social',      'MOFU', 'social',    'Meta',       null)
(4, 'Paid Search', 'BOFU', 'search',    'Google Ads', 'mixed')
```
- Television and Social spend are zero until those bronze paths exist. YouTube and Paid Search must both exist from week one so Google Ads is not collapsed into a single regressor.
- Create empty gold tables dim_campaign, dim_product, dim_promo. They are loaded as slowly changing dimension type 2 from silver (new row when name, objective, or product mix changes; previous row gets an end date). Also create empty gold.model_run_log and gold.allocation_recommended so the engine job can insert on the first Monday.

### A4. Ingest — Azure Data Factory pipelines

- Create factory adf-x-mmm-{env} in Canada Central. Attach a managed virtual network and an Azure integration runtime in Canada Central so copy activities stay on the private network. If the X order host is on-premises, install a self-hosted integration runtime on a locked-down virtual machine in snet-data.
- Linked services (each uses the managed identity or a Key Vault reference, never a password in the JavaScript Object Notation): Azure Data Lake Storage Generation 2 on stxmmm{env}; Key Vault kv-x-mmm-{env}; RestService for Google Ads (base https://googleads.googleapis.com, OAuth from the four gads-* secrets); RestService for Google Search Console (base https://searchconsole.googleapis.com, service-account secret); Azure Structured Query Language, Secure File Transfer Protocol, or SAP Open Data Protocol for the order ledger — use whatever X finance actually issues; Hypertext Transfer Protocol for Statistics Canada and the weather feed.
- Datasets: source is the vendor response (JavaScript Object Notation or delimited). Sink is Parquet, Snappy, one file per day, folder dt={yyyy-mm-dd}. Do not convert types in the copy activity except to write Parquet. Add additional columns on every sink: _load_ts (pipeline trigger time, Coordinated Universal Time), source_system, source_file.
- Pipeline pl_bronze_gads_x_ca, tumbling trigger daily at 02:00 America/Toronto. Google Ads Search Stream (or the older reporting endpoint) for the Canada customer in gads-customer-id-ca. Resource: campaign performance. Fields you must request: segments.date, customer.id, campaign.id, campaign.name, campaign.advertising_channel_type, metrics.cost_micros, metrics.impressions, metrics.clicks, geographic_view.country_criterion_id or the geo target you are given, customer.currency_code, metrics.conversions, metrics.conversions_value. Write to bronze/google_ads/x_ca/dt={date}/part-000.parquet. Keep cost_micros. Do not divide by one million here. Do not convert United States dollars to Canadian dollars here. Do not drop conversions in bronze — drop them in the data build tool so the raw file stays auditable. Parameters: p_date (defaults to yesterday). Retry policy: 3 attempts, 10 minutes between. On success write _SUCCESS. On a weekday, if the copy writes zero rows, fail the pipeline (weekend zeros can be real).
- Pipeline pl_bronze_x_orders, nightly after the distribution center closes (ask operations for the real clock; a common start is 23:30 America/Toronto). Extract order_id, ship_ts, plan_sku, list_cad, paid_cad, credit_cad, cancel_flag, new_vs_repeat, fsa (Forward Sortation Area, first three characters of the postal code — not the full address). Partition folder by ship date, not click date or order-create date: bronze/x_orders/dt={ship_date}/. Column mapping must drop email, phone, full name, and customer identifier before the sink. If the source cannot drop them, add a data-flow select that removes those columns. Gold must never see them.
- Pipeline pl_bronze_gsc_x_ca, daily after Google Search Console data is typically available (often 03:00 America/Toronto; a two-day lag is normal). Search Analytics query: site URL for X Canada, country filter Canada, dimension query plus date. Land raw query, clicks, impressions, country at bronze/gsc/x_ca/dt={date}/. Do not apply the brand dictionary here. Brand matching is a silver rule so you can change the dictionary without re-extracting history.
- Pipeline pl_bronze_macro, monthly on calendar day 8 (Statistics Canada Labour Force Survey and Consumer Price Index usually revise in the first week). Unemployment rate into bronze/statscan/unemp/dt={yyyy-mm}/. Consumer Price Index year-over-year into bronze/statscan/cpi/dt={yyyy-mm}/. Daily mean temperature (Celsius) into bronze/weather/ca/dt={date}/ from the weather host you choose (Environment and Climate Change Canada or a licensed grid). Carry the month value to every day later in gold; do not interpolate a fake weekly unemployment series in bronze.
- Shared pipeline settings: concurrency 1 per feed (do not overlap two Google Ads pulls), activity timeout 2 hours, logging to a Log Analytics workspace log-x-mmm-{env}, diagnostic settings on. Alert if any bronze pipeline fails twice in a row.

### A5. Data build tool — silver, then gold (names locked to the warehouse tab)

Repository folder transform/x_mmm/. Target is Fabric Warehouse (adapter fabric-warehouse or synapse). The same model filenames and column names are used on Amazon Web Services. File profiles.yml reads mmm-warehouse-odbc from the environment; it is never committed.

```
models/
  staging/
    stg_gads_x_ca.sql          -- spend in Canadian dollars = cost_micros / 1e6; timezone America/Toronto
    stg_x_orders.sql           -- net Canadian dollars = list - discount - credit - cancel
    stg_gsc_x_ca.sql           -- brand_flag from seed brand_dictionary
    stg_statscan.sql
  intermediate/
    int_media_daily.sql         -- date, geo_key = 0, channel_name, campaign_id, spend in Canadian dollars
    int_sales_daily.sql         -- ship_date, geo_key = 0, gross, discount, returns, net Canadian dollars
    int_intent_daily.sql        -- date, geo_key = 0, branded Google Search Console clicks
  gold/
    dim_campaign.sql            -- slowly changing dimension type 2 on source campaign identifier + name + objective
    fact_media_spend.sql
    fact_search_intent.sql
    fact_sales.sql
    fact_ops.sql                -- promo_depth from order discount / list; stockout when the feed exists
    fact_macro.sql              -- month value carried to each date_key
    mart_mmm_weekly.sql         -- the only engine input
    model_run_log.sql           -- empty table; the engine job writes rows
    allocation_recommended.sql
```
- stg_gads_x_ca: keep only the X Canada customer. Convert timestamps to America/Toronto and align to the Monday week. spend_cad = cost_micros / 1000000.0. Set channel_name = 'YouTube' when campaign_type is VIDEO or VIDEO_ACTION, or when campaign_name matches %_YT_%. Set channel_name = 'Paid Search' for SEARCH, SHOPPING, and PERFORMANCE_MAX. Display campaigns wait until you add a parent channel. Forbidden: SELECT * into gold. conversions and conversion_value are selected in staging for audit, then excluded from every intermediate and gold model.
- stg_gsc_x_ca: inner join seed brand_dictionary on normalized query text. Seed rows at minimum: x, x canada, x login, x recipes. Sum clicks to one row per date and geo_key = 0. Paid branded clicks from Google Ads never enter this model. That is the mediator queries_M.
- stg_x_orders: drop cancelled boxes. net_cad = list_cad - coalesce(discount, 0) - coalesce(credit, 0). Grain is ship date, not the click date Google would prefer. New versus repeat is kept on silver for diagnostics and is not a two-stage least squares regressor unless finance later asks for a split outcome.
- int_media_daily joins gold.dim_channel on channel_name and upserts dim_campaign as slowly changing dimension type 2. Campaign identifiers die here. The engine never sees a campaign identifier.
- fact_ops: promo_depth is 1 minus (paid / list) on ship-day boxes, clipped to 0–1. price_index is list price versus a 13-week trailing baseline. stockout_rate is null until slot or sell-out data arrives — do not invent zeros.
mart_mmm_weekly grain is week_start_mon times geo_key. This is the only table the engine reads:
```
select
  d.week_start_mon as week_start,
  0 as geo_key,
  sum(case when c.channel_name = 'TV' then f.spend end) as spend_tv,
  sum(case when c.channel_name = 'YouTube' then f.spend end) as spend_youtube,
  sum(case when c.channel_name = 'Social' then f.spend end) as spend_social,
  sum(case when c.channel_name = 'Paid Search' then f.spend end) as spend_search,
  sum(i.branded_gsc_clicks) as queries_M,
  sum(s.net_sales) as sales_Y,
  max(d.is_holiday) as holiday,
  max(d.is_payday) as payday,
  avg(o.promo_depth) as promo_depth,
  avg(o.list_price_index) as price_index,
  avg(o.stockout_rate) as stockout_rate,
  avg(m.unemployment) as unemployment,
  avg(m.cpi_yoy) as cpi_yoy,
  avg(m.temperature) as temperature
from gold.fact_media_spend f
join gold.dim_date d on d.date_key = f.date_key
join gold.dim_channel c on c.channel_key = f.channel_key
left join gold.fact_search_intent i on i.date_key = f.date_key and i.geo_key = f.geo_key
left join gold.fact_sales s on s.date_key = f.date_key and s.geo_key = f.geo_key
left join gold.fact_ops o on o.date_key = f.date_key and o.geo_key = f.geo_key
left join gold.fact_macro m on m.date_key = f.date_key and m.geo_key = f.geo_key
where f.geo_key = 0
group by 1, 2
```
- Data build tool tests — any failure kills the week: unique combination of week_start and geo_key; sales_Y is not null; spend_search greater than or equal to 0; queries_M greater than or equal to 0; promo_depth between 0 and 1 when present; dim_channel.funnel accepted values are the stored top-of-funnel / middle-of-funnel / bottom-of-funnel codes; row count at least 80 before the engine job is allowed to start.
- Azure Data Factory pipeline pl_dbt_gold starts an Azure Container Apps Job (or a Fabric pipeline) that runs dbt build --target {env} only after Saturday and Sunday bronze _SUCCESS markers exist for Google Ads, orders, and Google Search Console. On test failure the pipeline stops. It does not start the engine.

### A6. Engine job — two-stage least squares and the optimizer

- Build the repository Dockerfile on a Linux agent. Push to Azure Container Registry acrxmmm{env} tagged x-mmm:{git-commit} and also x-mmm:{env}. Scan the image (Microsoft Defender for Containers or Trivy). Production runs a digest, not the floating latest tag.
- Create Container Apps Job caj-x-mmm-engine-{env} in environment cae-x-mmm-{env}, 2 virtual central processing units, 4 gibibytes memory, replica timeout 2 hours, retry 1. Identity: id-x-mmm-{env}. Environment variables: MMM_DATA_MODE=warehouse, MMM_GEO_KEY=0, MMM_DSN sourced from Key Vault reference mmm-warehouse-odbc. Command: python run_mmm_engine.py after hierarchical_mmm_engine/io_mart.py exists (see the code section). The job selects only gold.mart_mmm_weekly where geo_key = 0.
- On success the job inserts one batch into gold.model_run_log (run identifier, git commit, mart as-of date, holdout mean absolute percentage error, holdout R-squared, Durbin–Watson, naive mix, funnel mix, Ship / Watch / Kill per channel) and one batch into gold.allocation_recommended (channel, recommended spend, bound low, bound high). It also writes parquet to gold/runs/{as_of}/ so finance can restore a week without the warehouse being online.
- This stack is ordinary least squares, Sequential Least Squares Programming, and a few hundred bootstrap draws. Do not attach a graphics processing unit. Do not replace the job with Azure Machine Learning automated machine learning — that throws away the mediator.

### A7. Studio application and the front door

- Create Container App ca-x-mmm-studio-{env} from the same image. Ingress is internal (Virtual Network only). Minimum replicas 1 in production, 0 in development. Central processing unit 1, memory 2 gibibytes. Same managed identity. MMM_DATA_MODE=warehouse in production and stage; synthetic only in development.
- Health probe: Hypertext Transfer Protocol Get /health, port 8000, interval 10 seconds. The probe must not execute two-stage least squares. Gunicorn binds 0.0.0.0:8000 as in the Dockerfile. The laptop Flask server on port 5050 is never published.
- The studio reads the latest model_run_log row. It does not keep production state only in the in-memory LAST_* caches. If the warehouse is unreachable, show an error; do not silently fall back to the data generating process in production.
- Put Azure Application Gateway or Azure Front Door in front, Web Application Firewall policy on, private origin. Restrict to Microsoft Entra Identifier groups mmm-science and mmm-finance-read. Finance is read-only. Do not grant the studio identity Storage Blob Data Contributor.
- Application Insights on the Container App: request failures, dependency failures to the warehouse, and a custom metric “last model run age in hours.”

### A8. Weekly orchestration, Power BI, and alerts

- Parent pipeline pl_x_mmm_week, scheduled trigger Monday 06:00 America/Toronto. Step 1: Until activity — wait until _SUCCESS exists for Saturday and Sunday on bronze/google_ads/x_ca, bronze/x_orders, and bronze/gsc/x_ca (timeout 4 hours). Step 2: Execute pipeline pl_dbt_gold. Step 3: If condition — data build tool tests passed (pipeline status Succeeded). Step 4a: Start Container Apps Job caj-x-mmm-engine-prod. Step 4b: Lookup model_run_log.holdout_mape for today’s run. If it is below the agreed cap (for example 0.12), post Microsoft Teams to the finance channel with the recommended Search versus YouTube mix. If it is at or above the cap, fail the pipeline and page science. Never publish a new mix from a failed holdout.
- Power BI workspace in the same Microsoft Entra Identifier tenant. Dataset mode DirectQuery (or Import if the mart is under a few hundred thousand rows). Tables allowed: gold.mart_mmm_weekly, gold.model_run_log, gold.allocation_recommended, gold.dim_channel, gold.dim_date. No bronze, no silver, no Google Ads conversion columns. Row-level security is not required at national grain; hide the workspace from everyone except mmm-finance-read and mmm-science.
- Alerts that must exist before you call it production: Azure Data Factory pipeline failed; Container Apps Job failed; Application Insights server errors on the studio; “no model_run_log row with run_ts after last Tuesday 10:00 America/Toronto”; Cost Management forecast over budget on rg-x-mmm-prod.

### A9. What you verify after each Azure step

- After A2: Storage Explorer (from the jump host) lists the X prefixes and cannot list them from a public laptop.
- After A3: SELECT COUNT(*) FROM gold.dim_date is about 2,600+ days; dim_geo has one row; dim_channel has four rows.
- After A4: a weekday Google Ads folder contains a parquet file whose cost_micros column is still integers; the orders folder has no email column.
- After A5: SELECT COUNT(*) FROM gold.mart_mmm_weekly is at least 80; spend_youtube is not identical to spend_search; sales_Y ties to a finance extract within the agreed tolerance.
- After A6–A8: one model_run_log row exists for the tagged image digest; Power BI refresh succeeds; a person in mmm-finance-read can open the report and a person outside the groups cannot.
```
Microsoft Entra Identifier groups + rg-x-mmm-prod + Virtual Network (snet-data, snet-app)
    +→ kv-x-mmm-prod     Google Ads secrets, order ledger, warehouse connection
    +→ stxmmmprod        bronze/google_ads/x_ca | x_orders | gsc/x_ca
    +→ adf-x-mmm-prod    daily bronze pipelines; Monday parent pipeline
    +→ Fabric Warehouse   gold dimension and fact tables; gold.mart_mmm_weekly
    +→ data build tool    staging to intermediate to gold (tests fail-closed)
    +→ engine job         select mart where geo_key = 0; write model_run_log
    +→ studio app         Microsoft Entra Identifier, /health
    +→ Power BI           gold tables only
```

## Amazon Web Services — end-to-end technical steps

The warehouse contract is identical to Azure. Home region is ca-central-1 (Canada Central). Amazon Simple Storage Service is the lake. Amazon Glue plus the data build tool (Redshift adapter, or Athena if you are not ready for Redshift) build the same gold tables. Amazon Elastic Container Service on Fargate runs this repository. Do not add Amazon SageMaker Autopilot. Resource names such as x-mmm-lake-prod stay as identifiers.

### W0. Organization, accounts, and names

- Create or use an Amazon Web Services Organization. Turn on Amazon Identity and Access Management Identity Center (successor to Single Sign-On). Create permission sets MMMPlatform (network, secrets, billing), MMMScience (stage deploy, gold read), MMMFinanceRead (QuickSight and the run log). Assign them to the same human groups as Azure.
- Prefer three accounts: x-mmm-dev, x-mmm-stage, x-mmm-prod. If the firm will only give you one account, use prefixes and separate Key Management Service keys — and accept that a bad identity and access management policy can see everything. Attach a Service Control Policy that denies creating data services (Simple Storage Service buckets, Redshift, Glue databases) outside ca-central-1.
- On day one: Amazon Budgets monthly cap plus a CloudWatch billing alarm to platform and finance email. Root user in a hardware-key safe. Daily work uses Identity Center permission sets, not long-lived access keys.
- Lock names: lake bucket x-mmm-lake-{env}, Glue database x_mmm_{env}, Redshift Serverless namespace and workgroup x-mmm-{env}, Elastic Container Registry repository x-mmm, engine service x-mmm-engine-{env}, studio service x-mmm-studio-{env}, secrets prefix the same logical names as Azure Key Vault.
- Enable Amazon GuardDuty and Amazon CloudTrail in the production account before the first Google Ads pull. CloudTrail must log Simple Storage Service object-level writes on bronze so you can prove who landed a file.

### W1. Virtual Private Cloud, endpoints, and secrets

- Create a Virtual Private Cloud 10.50.0.0/16 in ca-central-1 across two availability zones. Private subnets data-a / data-b (10.50.1.0/24, 10.50.2.0/24) for Redshift, Glue, and endpoints. Private subnets app-a / app-b (10.50.3.0/24, 10.50.4.0/24) for Elastic Container Service. No public subnet for the lake or the warehouse.
- Gateway endpoint for Amazon Simple Storage Service so Glue and the engine never pay Network Address Translation charges to read the lake. Interface endpoints for Secrets Manager, Elastic Container Registry, CloudWatch Logs, and Redshift. A Network Address Translation gateway is allowed only for egress to Google Ads, Google Search Console, and Statistics Canada.
- Security groups: sg-glue egress 443 to the internet (via Network Address Translation) and to the lake endpoint; sg-redshift ingress 5439 from sg-glue, sg-engine, and sg-studio only; sg-engine and sg-studio egress to Redshift and Secrets Manager; sg-alb ingress 443 from the corporate classless inter-domain routing block only.
- Create an Amazon Key Management Service customer-managed key x-mmm-{env} with key rotation. Encrypt the lake, the secrets, Redshift, and CloudWatch Logs with that key — not the account default — so finance can separate this project from the rest of the organization.
- Amazon Secrets Manager secrets with the same logical names as Azure: gads-developer-token, gads-client-id, gads-client-secret, gads-refresh-token, gads-customer-id-ca, gsc-service-account-json, x-orders-sql-dsn, mmm-warehouse-odbc. Application code still reads os.environ["MMM_DSN"]; the task definition injects the secret. Rotate Google Ads tokens on a calendar (90 days).
- Identity and access management roles (no access keys on laptops for production): x-mmm-glue-role — read/write the lake prefixes, read secrets, write Glue catalog; x-mmm-engine-task — read gold.mart_mmm_weekly, write model_run_log and allocation_recommended, write s3://x-mmm-lake-{env}/gold/runs/; x-mmm-studio-task — read the two gold run tables only; x-mmm-stepfn-role — start Glue and Elastic Container Service tasks. The studio role must not be able to write bronze.

### W2. Lake prefixes (identical to the Azure folder contract)

- Create bucket x-mmm-lake-{env} in ca-central-1. Block all public access. Versioning on. Default encryption Amazon Key Management Service. Bucket key enabled. Intelligent-Tiering on bronze. Optional Object Lock (compliance mode) later on bronze/tv_invoice/ when television invoices arrive.
- Create the same prefixes as Azure A2: bronze/google_ads/x_ca/, bronze/x_orders/, bronze/gsc/x_ca/, Statistics Canada, weather, holiday and promo seeds, silver daily folders, gold/runs/. A zero-byte object named _SUCCESS proves the prefix exists.
- Bucket policy: deny object reads unless the request uses the customer-managed key and comes from the Virtual Private Cloud endpoint or the listed roles. Deny delete on bronze without an extra mmm-platform condition.
- Amazon Glue Data Catalog database x_mmm_{env}. Crawlers on bronze are for debugging only and run in development. Production science and QuickSight use curated Glue tables on silver and gold (or Redshift native tables). Nobody builds a production dashboard on raw Google Ads JavaScript Object Notation.

### W3. Seed dimensions in Redshift Serverless (or Athena plus Iceberg)

- Create Redshift Serverless namespace x-mmm-{env} and workgroup x-mmm-{env} in ca-central-1, base capacity 8 Redshift processing units to start, publicly accessible false, subnets data-a and data-b, security group sg-redshift, encrypted with x-mmm-{env} key. Create schemas bronze, silver, gold.
- Load the same gold.dim_date, gold.dim_geo (one row, geo_key = 0, Canada), and four-row gold.dim_channel as Azure A3. Use the same surrogate keys (1 television, 2 YouTube, 3 Social, 4 Paid Search) so a dump can move clouds without remapping the mart.
- If Redshift is not approved yet: Amazon Athena plus Apache Iceberg tables in the gold prefix, same column names. The data build tool Athena adapter must still produce gold.mart_mmm_weekly. The engine job then uses the Athena Open Database Connectivity driver. Do not let Athena become a second undocumented schema.
- Create empty gold.model_run_log and gold.allocation_recommended with a distribution key on run_id (or EVEN if the table stays small). Grant SELECT on gold to x-mmm-studio-task and INSERT on the two run tables to x-mmm-engine-task.

### W4. Ingest — Glue, EventBridge, and optional AppFlow

- Amazon EventBridge Scheduler (timezone America/Toronto) starts four Glue jobs. Glue version 4.0, worker type G.1X, 2–5 workers, job bookmark off for the daily slice (you pass --p_date), timeout 60 minutes, retry 2. Role x-mmm-glue-role. Python libraries: Google Ads client, Google Search Console client, plus the firm’s Java Database Connectivity driver if the ledger is a database.
- Job glue-bronze-gads-x-ca at 02:00 America/Toronto. Same Google Ads field list as Azure A4 (date, customer, campaign identifier and name, advertising channel type, cost_micros, impressions, clicks, geo, currency, conversions, conversion value). Write parquet to s3://x-mmm-lake-{env}/bronze/google_ads/x_ca/dt={date}/. Keep cost_micros. Add _load_ts and source_system = 'google_ads'. Write _SUCCESS only after a non-empty weekday pull. If you prefer Amazon AppFlow’s Google Ads connector, the destination must be this prefix — never AppFlow’s default bucket.
- Job glue-bronze-x-orders after the distribution center closes. Java Database Connectivity or Secure File Transfer Protocol from the X ledger. Same columns as Azure (order identifier, ship timestamp, plan stock-keeping unit, list / paid / credit in Canadian dollars, cancel flag, new versus repeat, Forward Sortation Area). Strip email and customer identifier in the Glue script before the write. Folder bronze/x_orders/dt={ship_date}/.
- Job glue-bronze-gsc-x-ca: Google Search Console Search Analytics, country Canada, query grain, land bronze/gsc/x_ca/dt={date}/. Brand dictionary is not applied here.
- Job glue-bronze-macro on calendar day 8: Statistics Canada Labour Force Survey unemployment and Consumer Price Index into monthly prefixes; daily weather into bronze/weather/ca/.
- Amazon Transfer Family is not started until television invoices arrive by Secure File Transfer Protocol. When they do, land them at bronze/tv_invoice/dt={date}/ and nowhere else.
- Each job emits a custom CloudWatch metric BronzeRows with dimensions Feed and Date. An EventBridge rule fails the weekly state machine if a weekday BronzeRows is zero.

### W5. Data build tool — the same models as Azure

- Use the identical repository folder transform/x_mmm/. Target redshift (or athena). Model filenames, column names, and tests do not change. profiles.yml reads MMM_DSN from Secrets Manager through the task environment.
- YouTube versus Paid Search split, brand dictionary, ship-week net Canadian dollars, slowly changing dimension type 2 on dim_campaign, and the mart_mmm_weekly select statement are copy-paste from Azure A5. Do not “improve” names on Amazon Web Services.
- Run dbt build --target prod as a Glue Python Shell job or, cleaner, as an Elastic Container Service Fargate task using the same image plus the data build tool package. Amazon Step Functions starts that task only after Saturday and Sunday bronze _SUCCESS objects exist. If tests fail, the state machine goes to Fail and does not start the engine.

### W6. Engine task and studio service

- Create Elastic Container Registry repository x-mmm in ca-central-1. GitHub Actions builds the same Dockerfile as Azure, scans it, and pushes x-mmm:{git-commit}. Production task definitions pin the digest.
- Elastic Container Service cluster x-mmm-{env} on Fargate, platform version latest, capacity provider FARGATE. Task definition x-mmm-engine-{env}: 2 virtual central processing units, 4 gigabytes memory, task role x-mmm-engine-task, execution role that can pull from the registry and read secrets. Environment MMM_DATA_MODE=warehouse, MMM_GEO_KEY=0, secret MMM_DSN. Command python run_mmm_engine.py. Logs to CloudWatch log group /x-mmm/{env}/engine, 90-day retention.
- The engine writes gold.model_run_log, gold.allocation_recommended, and s3://x-mmm-lake-{env}/gold/runs/{as_of}/. Same columns as Azure so Power BI and QuickSight can share a semantic model later.
- Task definition x-mmm-studio-{env}: 1 virtual central processing unit, 2 gigabytes, task role x-mmm-studio-task. Service desired count 1 in production. Health check Hypertext Transfer Protocol Get /health on port 8000, grace period 30 seconds. Do not use the Flask development server.
- Internal Application Load Balancer in the app subnets, listener 443, certificate from Amazon Certificate Manager on the corporate domain, Web Application Firewall web access control list associated. Authenticate with Identity Center through the load balancer OpenID Connect action (or Amazon Cognito if Identity Center is not wired). Allowed groups: MMMScience and MMMFinanceRead. Do not put CloudFront in front unless legal requires a web application firewall at the edge; most marketing mix studios stay private.

### W7. Weekly state machine, QuickSight, and alarms

- Amazon Step Functions state machine sf-x-mmm-week, standard workflow, started by EventBridge Scheduler Monday 06:00 America/Toronto. State WaitForBronze: a Lambda or Glue check that Saturday and Sunday _SUCCESS objects exist for Google Ads, orders, and Google Search Console (retry 15 minutes, max 16 attempts). State RunDbt: start the data build tool Elastic Container Service task; wait for stopped plus exit code 0. State TestsPassed: Choice on the data build tool exit code and a Glue / Redshift query that gold.mart_mmm_weekly has at least 80 rows. State RunEngine (only on Yes): start the engine task; wait for exit code 0. State NotifyFinance: Amazon Simple Notification Service email or Slack webhook with channel, recommended spend, and holdout mean absolute percentage error. State FailClosed (on any No): fail the execution, page science, do not insert a new recommended mix.
- Amazon QuickSight (or Microsoft Power BI through the Redshift connector) on gold.mart_mmm_weekly, model_run_log, allocation_recommended, and dim_channel only. Direct query. Dataset permissions for MMMFinanceRead. No bronze.
- CloudWatch alarms: engine task failed (non-zero exit); Step Functions execution failed; studio target 5xx on the load balancer; a metric math alarm that no model_run_log insert has occurred since Tuesday 10:00 America/Toronto (custom metric published by the engine); Amazon Budgets on the x-mmm-prod account.

### W8. What you verify after each Amazon Web Services step

- After W2: from a public laptop, listing the production lake bucket is denied. From the platform role inside the Virtual Private Cloud, the X prefixes list.
- After W3: SELECT COUNT(*) FROM gold.dim_date is about 2,600+; dim_channel has four rows with the same keys as Azure.
- After W4: a weekday Google Ads prefix has parquet whose cost_micros is still integer micros; the orders prefix has no email field in the Glue table schema.
- After W5: gold.mart_mmm_weekly has at least 80 rows; spend_youtube is not equal to spend_search on weeks where both flew; sales_Y matches the finance ship-week extract.
- After W6–W7: one model_run_log row exists for the image digest; QuickSight refresh works; Identity Center users outside the two groups cannot open the load balancer.
```
Identity Center + x-mmm-prod + Virtual Private Cloud (app, data) + Simple Storage Service gateway
    +→ Secrets Manager     same secret names as Azure Key Vault
    +→ x-mmm-lake-prod    bronze/google_ads/x_ca | x_orders | gsc/x_ca
    +→ Glue jobs           daily bronze; data build tool on Monday
    +→ Redshift Serverless gold dimension and fact tables; gold.mart_mmm_weekly
    +→ sf-x-mmm-week      bronze present → data build tool → engine → notify
    +→ engine task + studio service + Application Load Balancer + Web Application Firewall
    +→ QuickSight          gold tables only
```

## How this repo maps onto those services

| In this repo | What it is | Azure | AWS |
| --- | --- | --- | --- |
| run_webapp.py / webapp/ | Interactive studio | ca-x-mmm-studio + Azure Container Registry + Microsoft Entra Identifier | x-mmm-studio Elastic Container Service + Elastic Container Registry + Application Load Balancer + Identity Center |
| run_mmm_engine.py | Batch 2SLS + SLSQP | caj-x-mmm-engine after pl_dbt_gold | x-mmm-engine ECS after Step Functions dbt |
| dgp.py / studio DGP | Synthetic Canada-like panel | Dev only. Prod reads Fabric/Databricks gold | Dev only. Prod reads Redshift/Athena gold |
| Playbook bronze/silver/gold | Medallion + mart_mmm_weekly | Azure Data Lake Storage stxmmm{env} + Fabric + transform/x_mmm | Simple Storage Service x-mmm-lake-{env} + Glue + Redshift + same data build tool |
| estimation.py 2SLS | Stage-1 / Stage-2 OLS | Same code in the job. Statsmodels, not a cloud AutoML endpoint |
| optimization.py SLSQP | Naive vs funnel mix | Same job. Write allocation_recommended |
| uncertainty.py | Bootstrap CIs, tests, gates | Same job or a follow-on job. Persist Ship/Watch/Kill |
| outputs/*.csv | Local artifacts | Azure Data Lake Storage gold/runs/yyyy-mm-dd/ + structured query language log | Simple Storage Service gold/runs/yyyy-mm-dd/ + Redshift log |
| In-memory LAST_* | Studio cache | Replace with a read of the latest registry row. Do not keep prod state only in the container |
| CLV / forecast / attribution / scenarios tabs | Sister engines | Same image, extra jobs or extra routes. Do not give each tab its own warehouse |

## Code you must change before prod (the engine stays)

- Add a mart loader. hierarchical_mmm_engine/io_mart.py that pulls mart_mmm_weekly with a SQL driver (ODBC to Fabric/Redshift, or pandas.read_sql). Same columns as tab 2. Fail if a week is missing Y or a spend column.
- Feature-flag the DGP. MMM_DATA_MODE=synthetic|warehouse. Studio in dev can still synthesize. Container Apps / ECS in prod set warehouse only.
- Persist every run. Stop treating LAST_UNCERTAINTY as the system of record. Write parquet/CSV to the lake and a SQL row the BI pack can join.
- Health and config. GET /health → 200. Read warehouse DSN and env from Key Vault / Secrets Manager, not from a checked-in .env.
- Do not port-forward 5050 to the internet. The Flask dev server in run_webapp.py is for the laptop. Prod is gunicorn in the image above.
```
def load_weekly_mart(conn, as_of=None):
    # X national panel — columns match gold.mart_mmm_weekly
    sql = """
      select week_start, geo_key, sales_Y, queries_M,
             spend_tv, spend_youtube, spend_social, spend_search,
             holiday, payday, promo_depth, price_index, stockout_rate,
             competitor_sov, unemployment, cpi_yoy, temperature
      from gold.mart_mmm_weekly
      where geo_key = 0
      order by week_start
    """
    frame = pd.read_sql(sql, conn)
    assert frame["sales_Y"].notna().all()
    assert (frame["spend_search"] >= 0).all()
    assert len(frame) >= 80
    return frame
```

## CI/CD, identity, and secrets

### GitHub Actions (both clouds)

On pull request: pytest / a 40-week synthetic smoke of run_flexible_scenario. On merge to main: build the image, scan it, push to ACR or ECR, deploy to stage. On a signed tag: deploy that digest to prod. The weekly engine job pins that digest so a Friday UI tweak cannot silently change Monday’s mix.

### Who can do what

Science: deploy stage, run the job with a “dry-run” flag, read gold. Finance: read Power BI / QuickSight and the run log, cannot push an image. Platform: Key Vault / IAM, network, billing. No personal access keys on laptops for prod. Managed identity / task role only.

### Azure secrets

Key Vault plus Container Apps / Azure Data Factory managed identity. Grant get on named secrets. Rotate Ads application programming interface tokens. Purge protection on the production vault.

### AWS secrets

Secrets Manager plus Elastic Container Service task role. Same names as Azure so the app code is os.environ["MMM_DSN"] either way. Key Management Service customer-managed key, not the account default, if finance requires a separable key.

## Weekly operating cadence (X, both clouds)

- Daily 02:00 America/Toronto. pl_bronze_gads_x_ca / glue-bronze-gads-x-ca and Google Search Console land yesterday. After the distribution center closes, pl_bronze_x_orders lands ship-day boxes. Do not refit two-stage least squares daily.
- Monday 06:00 ET. Parent orchestrator waits for Sat+Sun _SUCCESS on Google Ads, orders, and GSC. dbt builds silver → gold. Unique week×geo, Y not null, spend ≥ 0, ≥ 80 weeks must pass or the week dies.
- Monday night. Engine job: SELECT mart_mmm_weekly WHERE geo_key=0, 2SLS, holdout, SLSQP, residual + block bootstrap. Write model_run_log and allocation_recommended.
- Tuesday. Science reads Ship/Watch/Kill and holdout MAPE. Brand Search usually Watch (last-click over-credits it). If a gate flips vs last week, do not ship the mix until someone writes why.
- Wednesday. Finance pack on gold only. Budget owner accepts or rejects the reallocation inside the trust region (Search vs YouTube first; TV/Meta when those bronze paths exist).
- Quarterly. Add Meta + TV invoices. Geo-lift on a metro. Revisit Hill K / adstock if PMax vs Search mix shifted.

## First 90 days — X first sources only

| Days | Outcome (tab 2 warehouse) | Azure | Amazon Web Services |
| --- | --- | --- | --- |
| 0–14 | Canada Central / ca-central-1, billing cap, Git, image, GET /health, empty bronze prefixes, seeded dim_date / dim_geo=0 / four-row dim_channel | rg-x-mmm-dev + Azure Container Registry + one Container App on synthetic data generating process | x-mmm-dev + Elastic Container Registry + one Fargate service on synthetic data generating process |
| 15–45 | Three bronze feeds only: Google Ads Canada, order ledger (Y), Google Search Console brand queries (M). Silver daily plus slowly changing dimension type 2 dim_campaign | pl_bronze_gads_x_ca, pl_bronze_x_orders, pl_bronze_gsc_x_ca + data build tool staging | glue-bronze-gads-x-ca, orders, Google Search Console + data build tool staging |
| 46–70 | National mart_mmm_weekly (at least 80 weeks, geo_key=0), MMM_DATA_MODE=warehouse in stage, first honest two-stage least squares (Search versus YouTube split) | Fabric gold + caj-x-mmm-engine | Redshift gold + x-mmm-engine Elastic Container Service task |
| 71–90 | Single sign-on studio, business intelligence on gold, Monday fail-closed week, one signed-off Search/YouTube mix. Meta and television invoices wait until this works | Microsoft Entra Identifier + Power BI + pl_x_mmm_week | Identity Center + QuickSight + sf-x-mmm-week |

Start national Canada, four parent channels (television empty, YouTube, Social empty, Paid Search). Do not block the lake on Pathmatics share of voice or slot-level stockouts — leave those columns null until the feed exists. Designated market area splits and 30-channel taxonomies come after holdout mean absolute percentage error is boring.

## Go-live gates and things that look like progress but are not

### You may call it production when

- Y ties to finance actuals within the agreed tolerance.
- Gold has no user_id, email, or device id.
- dbt unique-week test is in the orchestrator, not a wiki.
- The job is the tagged image, not a laptop.
- Holdout MAPE and Durbin–Watson are in the BI pack.
- Every shipped channel is Ship or an explicit Watch with a geo-test date.
- Someone other than the modeler can restore last week’s mix from the registry.

### Do not do this

- Lift-and-shift the Flask debug server onto a public VM.
- Train in Databricks AutoML / SageMaker Autopilot and throw away 2SLS. You lose the mediator.
- Give the studio Contributor on the lake “so science can move fast.”
- Put Ads tokens in GitHub Variables as plaintext.
- Run prod and the sandbox in the same storage account.
- Stand up Azure and AWS at once “for optionality.” Pick one lake. The model does not care.
- Scale to GPU SKUs. This stack is OLS, SLSQP, and a few hundred boots.
Pick Azure if the firm already has Entra, Fabric, and Power BI (common for a Canadian retailer). Pick AWS if the lake is already S3 and the orchestrator is already Airflow/MWAA. The code change is the mart loader and the registry write. The cloud work is plumbing around an engine you already have.

Every tab has the same three moves: name the model, run a test the model did not train on, then diagnose why it passed or failed before you ship a number. This page is the field guide. Open the tab, run the default seed first, then change one knob.

MMM studio Playbook MMM methods Cloud CLV Demand forecast Demand trends Attribution Scenarios Uncertainty

## MMM studio — funnel two-stage least squares

### 1. The model

Geometric adstock then Hill saturation turn weekly spend into x̃. Stage 1: brand-search intent M from top- and mid-funnel x̃ plus intent controls. Stage 2: sales Y from fitted intent M̂, mid- and bottom-funnel x̃, and sales controls. Sequential Least Squares Programming then reallocates a fixed weekly budget. Naive mix uses only direct betas. Funnel mix also values the intent that awareness creates.

### 2. The test

Click Run model (default 208 weeks, seed 42, $160k). The last 20% of weeks are holdout — nothing is fit on them. Pass if holdout R-squared is high, mean absolute percentage error is not wild versus the data generating process, and the funnel mix is not identical to the naive mix (search should shrink). Repeat with 80 weeks (noisy) and 312 weeks (should tighten).

### 3. The diagnosis

Durbin–Watson far from 2: leftover weekly correlation (adstock too short or a missing control). Variance inflation factor high on search + intent: harvest bias, stage 1 is weak. Mid-funnel beta near zero: not enough independent flighting. Paid Search still huge after 2SLS: you used raw M instead of M̂, or Y is Google conversion value. Controls with the wrong sign: they were too smooth in the data generating process. Read the failure-mode cards and the attribute catalog on this tab.

| What you look at | Healthy default (seed 42) | Fail / do not ship |
| --- | --- | --- |
| Holdout R-squared / MAPE | Fit tracks Y through holidays; holdout not a cliff | Holdout MAPE blows up versus train — overfit or a regime shift |
| Naive vs funnel mix | Search and other harvest lose share; TV / YouTube gain | Both mixes identical — the mediator is not identified |
| Direct vs indirect | TV can be $0 direct and still large total | Every channel is “direct only” — you dropped stage 1 |
| Durbin–Watson, VIF | DW near 2; VIF on search not extreme | DW < 1.2 or VIF > 10 on harvest + M |

## MMM playbook — questions, sources, warehouse

### 1. The model

No regression lives here. The “model” is the star schema: dim_date, dim_geo, dim_channel, facts, then mart_mmm_weekly. X: Y = net box revenue on ship-week; M = Google Search Console branded organic clicks; first media is Google Ads split into Paid Search vs YouTube.

### 2. The test

For every field, apply keep / roll / drop. Grain test: one number per Monday week × geo_key = 0. Uniqueness test on week_start + geo_key. Y not null. Spend ≥ 0. Promo depth in 0–1. At least 80 weeks before you allow the engine. Y must tie to a finance extract, not Google conversion_value.

### 3. The diagnosis

If 2SLS over-credits Brand Search, Y is still a click conversion or M includes paid branded clicks. If YouTube and Search move 1:1, campaign_type never split VIDEO. If ship-week Y leads spend, you used order-create date. Campaign identifiers in the mart: silver taxonomy failed. Empty sales_Y on a holiday week: the ledger join missed the week.

## MMM methods — equations and estimation

### 1. The model

Same two equations as the studio, written in symbols: adstock θ, Hill K, stage 1, stage 2, chain-rule totals, mROI, Sequential Least Squares Programming inside L, U, B. Controls are listed with the sign the data generating process used.

### 2. The test

This tab does not fit. Use it as the answer key while you run tab 1. Check that recovered alphas / betas have the same sign as the “if you instead” table. Confirm payday, promo depth, and stockout are in the equation you think they are (intent vs sales).

### 3. The diagnosis

If a recovered control has the opposite sign, the series was too smooth or collinear (temperature vs season). If Hill K looks unidentified, spend never crossed K. If θ is stuck at the bound, you have no off weeks. Do not “fix” it by dropping the control — that is the failure mode the methods tab names.

## MMM cloud — Azure and Amazon Web Services

### 1. The model

Same engine. The cloud lands the playbook warehouse and runs the container after the data build tool. Nothing AutoML. MMM_DATA_MODE=warehouse in production.

### 2. The test

After each landing-zone step: prefixes exist and are private; dim_date has ~2,600 days; dim_channel has four rows; weekday Google Ads parquet still has integer cost_micros; orders have no email; mart_mmm_weekly ≥ 80 rows; spend_youtube ≠ spend_search; GET /health is 200; one model_run_log row for the image digest.

### 3. The diagnosis

Empty weekday bronze: token or customer id. Engine wrote a mix after a failed data-build-tool test: orchestrator is not fail-closed. Studio shows the data generating process in production: MMM_DATA_MODE is wrong. Power BI on bronze: stop. Holdout MAPE worse in the warehouse than in the studio: Y grain or the Search / YouTube split drifted.

## Customer lifetime value — overview, customers, segments

### 1. The model

Overview: BG/NBD (P(alive) and expected purchases) × Gamma-Gamma (expected order value) × margin, plus an out-of-fold Ridge on recency / frequency / monetary and acquisition channel. Customers: one row per person at the snapshot. Segments: top 20% / mid 40% / bottom 40% of blend CLV, and RFM labels. Join to the funnel: top-of-funnel acquirers should live longer than paid-search acquirers.

### 2. The test

Click Run CLV (1,800 customers, snapshot 130, horizon 26, margin 0.35). Holdout is the weeks after the snapshot — Ridge never sees that customer’s own future. Pass if rank correlation (blend vs realized) is clearly above 0, Gamma-Gamma mean is near observed AOV, and search-acquired buyers have lower P(alive) than TV / YouTube.

### 3. The diagnosis

Everyone P(alive) ≈ 1: snapshot is too early or there is no churn in the data generating process. Ridge beats BG/NBD by a lot: you leaked the holdout into RFM. Search segment is the high-CLV tier: last-click acquisition is polluting the label (same harvest bias as MMM). Bottom-tier mass from one channel: that channel is filling the base with one-box buyers — do not raise its MMM beta just because it converts.

Pages: CLV overview · CLV customers · CLV segments · CLV methods

## Demand forecast and trade allocation

### 1. The model

Forecast: seasonal naive vs Ridge ARX on log units with price, holiday, payday, TPR, feature, display; inverse-RMSE ensemble. Channel-level ordinary least squares reads promo lifts. Allocation: those lifts + Hill saturation on trade dollars, Sequential Least Squares Programming on a fixed weekly trade envelope. Profit = incremental margin minus trade cost.

### 2. The test

Run forecast (156 weeks, 26 holdout, $180k trade). Pass if ensemble weighted absolute percent error beats seasonal naive, holdout tracks feature/TPR spikes, and optimized profit ≥ equal-split profit. Then open Trade allocation: Drug / E-comm should not be starved if their ROI is high; Mass should not keep every dollar just because it is large.

### 3. The diagnosis

Naive wins: promo coefficients are noise (not enough TPR variation). Holdout misses only feature weeks: the feature flag is weak or collinear with TPR. Optimized profit below equal: bounds or Hill K are crushing the response. High observed lift + low recommended spend: margin is thin — that is correct, not a bug. Do not use this page to lock national volume; that is Demand trends.

Pages: Demand forecast · Trade allocation · Forecast methods

## Demand trends, diagnostics, and methods

### 1. The model

Trends: additive split (13-week trend + week-of-year season + residual), then seasonal naive vs Ridge ARX on the level, ensemble, 13-week horizon with 80/90 percent bands. Diagnostics: year-over-year, slope acceleration, Durbin–Watson, lag-1 residual correlation, mean-break scan, |z| ≥ 2.5 anomalies, promo-week vs quiet residual. Methods: the formulas and Grow / Hold / Cut rules.

### 2. The test

On Demand trends click Run demand trends (156 / 26 / 13, seed 42). Pass if holdout weighted absolute percent error is below naive, 80% band coverage is near 80, the horizon is not a flat copy of last year, and the planning table has a Grow / Hold / Cut that matches the year-over-year chart. Then open Demand diagnostics — you must be able to name the week-80 level shift and at least one shock week.

### 3. The diagnosis

Coverage far from 80%: residual scale is wrong (Durbin–Watson will also be off). Horizon always Grow: you froze promo at a high mean. Negative promo residual: depth is papering over a soft trend — do not raise intro codes. Anomaly on a holiday: season is under-fit. Mean-break week nowhere near 80: the scan is chasing a seasonal edge — lengthen the minimum window. Cut gate + rising year-over-year: you compared to the last 13 weeks that still included a shock; read the year-over-year panel before you lock.

| Diagnostic | How you test it | What failure looks like |
| --- | --- | --- |
| Holdout WAPE / R-squared | Trends page bake-off table | Naive wins → Ridge features are not helping |
| 80% coverage | KPI on Trends; band on holdout chart | < 60% or > 95% → do not use the band for capacity |
| Year-over-year | Bar chart after week 52 | Sign flip after week 80 is the planted regime, not noise |
| Durbin–Watson, lag-1 | Diagnostics KPIs | DW < 1.2 → horizon bands too tight |
| Mean-break week | Diagnostics KPI vs planted week 80 | Break at week 10 or 150 → scan is edge-hunting |
| Anomaly /z/ ≥ 2.5 | Anomaly table | Dozen of holidays flagged → seasonal term missing |
| Promo vs quiet residual | Diagnostics story | Promo residual < −8 → do not add depth |
| Grow / Hold / Cut | Planning table on Trends | Gate disagrees with year-over-year → do not lock |

Pages: Demand trends · Demand diagnostics · Demand methods

## Attribution and investment allocation

### 1. The model

Attribution: incremental MMM (same structural idea) versus last-touch, first-touch, linear, and time-decay credit. Price is a second lever. Investment: last-touch mix vs incremental mix on one media envelope, plus a price-index search (96–104) for contribution profit.

### 2. The test

Run attribution (156 weeks). Pass if last-touch over-credits Paid Search versus the incremental column, TV is not zero incremental, and a +$10k or +1 price-index point has a signed sales effect. On Investment, incremental profit should beat last-touch; price should not slam to a bound unless elasticity is huge.

### 3. The diagnosis

Last-touch ≈ incremental: you have no upper-funnel spend variation. Price coefficient ~0: price did not move in blocks (needs ~13-week price steps). Search still “wins” incremental: Y is a platform conversion. Investment slams all dollars to one channel: Hill K is too small or iROAS is a point estimate — go to Uncertainty before you ship.

Pages: Attribution · Investment allocation · Attribution methods

## Scenarios and the planner

### 1. The model

One response surface for media and trade. Named plans: locked, harvest, brand-led, promo-led, risk-off, ROI-optimal. Each plan is a media mix plus a promo mix. Downside band multiplies every lift by 0.70. The planner is the same surface with your shares, normalized to the two weekly envelopes.

### 2. The test

Run scenarios (default envelopes). Pass if ROI-optimal is not identical to harvest, risk-off has the tightest downside, promo-led wins units but not always profit, and a custom planner mix scores between the named bookends. Change downside from 0.70 to 0.50 — rank should be able to flip.

### 3. The diagnosis

Every plan has the same profit: the surface is flat (no diminishing returns). Harvest always wins: upper-funnel iROAS is ~0 (go back to MMM identification). Planner mix does not match what you typed: shares were renormalized — read the note. Downside never changes rank: you are not stressing lifts, you are stressing a constant.

Pages: Scenarios · Scenario planner · Scenario methods

## Uncertainty and statistical tests

### 1. The model

Uncertainty: residual bootstrap and moving-block bootstrap on media betas, iROAS, and the profit gap vs last-touch. Ship / Watch / Kill uses the lower tail. Tests: bootstrap p-values on “is beta > 0”, “is iROAS > 1”, and a price permutation null. Classical ordinary-least-squares p-values sit beside them so you can see when they are too sure.

### 2. The test

Run bootstrap (156 weeks, 280 draws, block 8). Pass if some channels are Watch or Kill (a wall of Ship is a red flag), block intervals are wider than residual intervals, and profit-gap mass is not sitting on zero. On Statistical tests, price permutation should put the observed price coefficient outside the shuffled pile if price moved in blocks.

### 3. The diagnosis

All Ship: intervals collapsed (too few weeks or no leftover residual). Block ≫ residual width: weekly correlation remains — do not brief residual p-values. Singular-matrix skips: overlapping blocks hit a collinear draw; that is logged, not a crash. Kill on TV iROAS: lower tail < 1 — do not ship TV as proven incremental; schedule a geo-lift. Classical p < 0.05 but bootstrap p > 0.10: believe the bootstrap.

Pages: Uncertainty · Statistical tests · Uncertainty methods

## Shared test ritual (every engine)

- Run the default seed once. That is the known classroom answer.
- Change only one knob (weeks, holdout, budget, seed). If everything jumps, the object is not identified.
- Read the holdout / out-of-time metric before the pretty in-sample line.
- Name a failure mode from this page before you change the model.
- Do not ship a mix, a CLV tier, a trade envelope, or a volume lock until the diagnosis has a cause (data grain, missing control, or a real regime).

---

# Page: pricing

Source: `projects/01_mmm_channel_optimization/development/templates/pricing.html`

Price elasticity Units = base × (price index / 100)^elasticity. Profit = units × (list × index/100 − cost). Thompson sampling, UCB, and epsilon-greedy choose the next arm. Elasticity is refit on the traffic the bandit actually saw.

Click Run pricing (240 rounds, seed 42). Pass if recovered elasticity is near −1.35, Thompson cumulative profit beats random, and the oracle arm (usually 96) is pulled more than the extremes as rounds accumulate.

Elasticity near 0: not enough price variation (epsilon too small too early). Thompson worse than random: prior variance collapsed. All pulls on 92: the bandit is chasing units, not profit — check unit cost.

Rounds Epsilon Seed Run pricing

### Cumulative contribution profit

Thompson, UCB, epsilon-greedy, and random on the same demand draws. The gap versus random is the value of balancing exploration and exploitation.

### True profit by price arm

Oracle is the tallest bar. A 92 index sells more boxes but can lose margin. 108 keeps margin and loses volume.

Round-by-round prices and regret are on Online bandit. Formulas are on Pricing methods.

---

# Page: pricing bandit

Source: `projects/01_mmm_channel_optimization/development/templates/pricing_bandit.html`

Online pricing bandit

### Price index chosen each round (Thompson)

### Cumulative regret

Elasticity recovery is on Price elasticity.

---

# Page: pricing methods

Source: `projects/01_mmm_channel_optimization/development/templates/pricing_methods.html`

## Pricing methods Demand and profit

```
U(p) = 420 × (p / 100)^{−1.35}
margin(p) = 12 × (p / 100) − 5.40
π(p) = U(p) × margin(p)

Arms p ∈ {92, 96, 100, 104, 108}
Observed units are lognormal around U(p).
```

## Elasticity

```
log U_t = a + ε log(p_t / 100) + e_t
ε̂ is ordinary least squares on the traffic the policy actually served.
```

## Policies

```
Thompson   draw π_i ~ Normal(mean_i, var_i / n_i); take argmax
UCB        mean_i + c √(log t / n_i)
ε-greedy   with probability ε pick a random arm; else the current best
Random     uniform (baseline)

Regret_t = π(oracle) − π(p_t)
```
Production replaces the five arms with the live price grid and the reward with contribution after returns. Do not run the bandit on last-click conversions.

---

# Page: scenarios

Source: `projects/01_mmm_channel_optimization/development/templates/scenarios.html`

Strategy scenarios One response surface for media and trade. Named plans (locked, harvest, brand-led, promo-led, risk-off, ROI-optimal) plus the planner. Downside multiplies every lift by 0.70 (or the slider you set).

Run the default envelopes. Pass if ROI-optimal ≠ harvest, risk-off has the tightest downside, and a custom planner mix scores between the named bookends. Drop downside to 0.50 — rank should be allowed to flip.

Every plan the same profit: the surface is flat. Harvest always wins: upper-funnel iROAS is ~0 — go back to MMM identification. Planner mix ≠ what you typed: shares were renormalized to the envelopes.

Weekly media $k Weekly promo $k Horizon weeks Downside lift Seed Score scenarios

### Horizon profit by strategy ($k)

Navy is the planning (base) profit. The thin rust whiskers in the table are p10–p90 from lift noise. Promo-led moves dollars from media into trade; it is not an even split of the two envelopes.

### ROI vs incremental sales

The useful frontier is up and to the right. Status quo is the lock. Harvest often buys volume with a worse ROI. ROI-optimal should sit near the top of the profit ranking unless a bound is binding.

### Media mix by strategy ($k / week)

TV / Social / Search / Email. Harvest piles Search. Brand-led piles TV. Risk-off flattens the shares to cut concentration.

### Promo mix by strategy ($k / week)

Grocery / Mass / Drug / E-comm trade. Promo-led inflates this bag by taking money out of media. Mass is cheap volume; Drug is high margin.

### Scorecard

Set your own shares on Scenario planner. Formulas are on Scenario methods.

---

# Page: scenarios methods

Source: `projects/01_mmm_channel_optimization/development/templates/scenarios_methods.html`

Scenario methods Pipeline Named strategies Response surface ROI and profit Risk bands ROI-optimal Production

## Solving approach

- Fix a weekly media envelope B_m and a weekly promo envelope B_p, plus a horizon H (default 13 weeks).
- Write each strategy as two share vectors. Shares are normalized to the envelopes. Promo-led is the exception: it moves 28% of media dollars into promo so the total bag stays B_m + B_p.
- Score incremental sales from Hill media plus saturated promo lifts.
- Convert to profit and ROI. Add a downside (lifts × 0.70) and an 80-draw noise band.
- Solve one SLSQP plan (ROI-optimal) inside channel bounds.
- Rank plans on horizon profit. Plot the ROI–volume frontier.

## Named strategies

| Plan | Media idea | Promo idea | Why it exists |
| --- | --- | --- | --- |
| Status quo | Last-year lock, scaled to B_m | Last-year lock, scaled to B_p | The meeting starts here. |
| Harvest | Search 58% | Mass-heavy | What last-click and many retailers ask for. |
| Brand-led | TV 46% + Social 26% | Grocery + Drug | Awareness and higher-margin banners. |
| Promo-led | Cut media 28% | That 28% plus B_p | Trade calendar takes the growth job. |
| Risk-off | Flatter shares | Flatter shares | Lower concentration (HHI), less single-channel bet. |
| ROI-optimal | SLSQP | SLSQP | Planning optimum inside bounds. |
| Custom | Planner sliders | Planner sliders | The stakeholder’s “what if.” |

## Response surface

```
Media (weekly, $k sales)
  T_c(s) = hill( s / (1 − θ_c) ; K_c )
  Inc_media = Σ_c β_c T_c(s_c)

Promo (weekly, units then $)
  Inc_units = Σ_b β_b * (s_b / (K_b + s_b)) * 90
  Inc_promo = Inc_units * 4.20

Inc_total = Inc_media + Inc_promo
```
Media betas match the attribution DGP (TV 210, Social 105, Search 155, Email 48). Promo betas are channel lifts (Grocery 1.35 … E-comm 1.80). The two systems are added, not multiplied: a national brand plan and a trade calendar that harvests it. Do not also add the trade-forecast page’s incrementals on top of these or you double-count.

## ROI and profit

```
Invest_week = Σ media + Σ promo
π_week      = 0.36 * Inc_total − Invest_week
ROI         = π_week / Invest_week

Horizon: multiply incremental, investment, and profit by H.
ROI is a rate, so it is not multiplied.
```
0.36 is a blended contribution margin across media-driven and promo-driven units. Banner-specific margins (Mass 0.24, Drug 0.38) sit inside the promo engine on the forecast pages; here the question is strategy ranking, not invoice-level trade ROI.

## Risk bands

```
Downside:  score again with every β scaled by 0.70
Upside:    every β scaled by 1.25
p10 / p90: 80 draws, scale ~ Normal(1, 0.12), clip not applied

HHI = 0.5 Σ (media share)² + 0.5 Σ (promo share)²
High risk if HHI > 0.38 or the plan is Harvest.
```
The downside is the planning question finance will ask: “If incrementality is 30% light, do we still beat the lock?” A plan that wins at 1.0× and loses at 0.7× is not robust.

## ROI-optimal (SLSQP)

```
max_{s,u}   0.36 * Inc(s,u) − (1's + 1'u)
s.t.        1's = B_m
            1'u = B_p
            L_c ≤ s_c ≤ U_c    media trust region
            L_b ≤ u_b ≤ U_b    promo trust region
```
Promo-led is allowed to break the two-envelope split. ROI-optimal is not: it keeps B_m and B_p so the comparison to status quo is a pure mix change, except for that one named strategy that moves the bags.

## How to run this on a real lock

- Replace β and K with the live MMM and the live trade model. Do not keep these DGP numbers in a board pack.
- Lock B_m and B_p to the finance envelopes for the quarter. Add retailer min-feature constraints as extra SLSQP inequalities.
- Put last year’s actualized mix in Status quo, not the original plan.
- Show the scorecard and the downside column in the same table. Hide iROAS-only slides; they skip the promo bag.
- Custom scenarios come from stakeholders. Score them in this engine so “what if” is comparable, not a new spreadsheet.
- If Custom never beats ROI-optimal, that is expected. Use Custom to test political constraints (cannot cut Search, must keep Club).

---

# Page: scenarios planner

Source: `projects/01_mmm_channel_optimization/development/templates/scenarios_planner.html`

Scenario planner Weekly media $k Weekly promo $k Horizon weeks Score custom mix

### TV Social Search Email Grocery Mass Drug E-comm Custom vs named strategies (profit)

### Custom vs named (ROI)

### Scorecard including Custom

---

# Page: uncertainty

Source: `projects/01_mmm_channel_optimization/development/templates/uncertainty.html`

Model uncertainty Residual bootstrap and moving-block bootstrap on media betas, iROAS, and the profit gap versus last-touch. Ship if the lower tail of beta is above 0 and iROAS is above 1. Statistical tests add bootstrap p-values and a price permutation null.

Click Run bootstrap (156 weeks, 280 draws, block 8). Pass if the page is not a wall of Ship, block intervals are wider than residual intervals, and Statistical tests put the observed price coefficient outside the shuffled pile.

All Ship: intervals collapsed. Block much wider than residual: leftover weekly correlation — do not brief residual p-values. Classical p < 0.05 but bootstrap p > 0.10: believe the bootstrap. Kill on TV iROAS: do not ship TV as proven; schedule a geo-lift.

Weeks Bootstrap draws Block length Seed Run bootstrap

### Media beta — residual bootstrap 90% CI

Dot is the OLS point estimate. Whiskers are the 5th and 95th percentiles of residual-bootstrap betas. If the whisker crosses zero, do not brief that channel as proven incremental.

### iROAS — 80% bootstrap interval

Evaluated at historical mean spend. The dashed line is the 1.0 hurdle. A bar whose lower whisker sits above 1.0 is a Ship candidate.

### Residual vs block-bootstrap width

Block bootstrap keeps 8-week chunks so leftover weekly correlation inflates the interval. If block CIs are much wider than residual CIs, the residual bootstrap was too optimistic.

### Profit gap vs last-touch (bootstrap)

Distribution of incremental-mix profit minus last-touch profit. Mass to the right of zero is the reallocation case. The p-value is the share of draws ≤ 0.

### Residual-bootstrap intervals

### Recommendation gates

Hypothesis tests and permutation for price are on Statistical tests. Formulas are on Uncertainty methods.

---

# Page: uncertainty methods

Source: `projects/01_mmm_channel_optimization/development/templates/uncertainty_methods.html`

Uncertainty methods Pipeline Point model Residual bootstrap Block bootstrap Percentile intervals Tests Ship / Watch / Kill Production

## Solving approach

- Fit the incremental MMM (adstock + Hill spend, log price, season, holiday) by OLS.
- Draw B residual-bootstrap coefficient vectors (default 280).
- Draw B moving-block bootstrap coefficient vectors (block length 8 weeks).
- Map each draw to iROAS at mean spend and to the profit gap versus a last-touch mix.
- Report 90% and 80% percentile intervals. Compare interval widths across the two bootstraps.
- One-sided and two-sided bootstrap p-values, plus a permutation test that breaks the price–sales link.
- Translate intervals into Ship / Watch / Kill so the recommendation pack is not a wall of p-values.

## Point model

```
Y = Xθ + ε
X = [1, season, holiday, log(P/100), x̃_TV, x̃_Social, x̃_Search, x̃_Email]
θ̂ = (X'X)^{−1} X'Y

Classical (shown only as a foil):
  se_j = s √(X'X)⁻¹_jj
  t_j  = θ̂_j / se_j  ~ t_{n−k}   under iid normal ε
  95% CI = θ̂_j ± t_{0.975, n−k} se_j
```
Weekly media residuals are almost never iid. That is why the bootstrap is the number we brief, and the t-test is the “what a textbook would have said” column.

## Residual bootstrap

```
Fit:  Ŷ = Xθ̂,   e = Y − Ŷ
Draw: e* ~ sample(e) with replacement
      Y* = Ŷ + e*
      θ* = (X'X)⁻¹ X'Y*

Repeat B times. This keeps the design X fixed and treats
the residual cloud as the sampling distribution of noise.
```

## Moving-block bootstrap

```
Split the n weeks into blocks of length L (default 8).
Draw blocks with replacement until n rows are filled.
Refit OLS on the concatenated blocks.

If leftover autocorrelation or holiday clusters matter,
Var*(θ_block) > Var*(θ_residual).
```
We do not use a naive iid pairs bootstrap on weeks: that would break adstock structure already baked into x̃. Residual and block are the two honest options once transforms are treated as known.

## Percentile intervals and iROAS

```
90% CI:  [Q_0.05(θ*), Q_0.95(θ*)]
80% CI:  [Q_0.10(θ*), Q_0.90(θ*)]

iROAS_c* = θ*_c * T'(s̄_c)
T'(s)    = [K / (K + s/(1−θ))²] / (1−θ)

Profit gap* = π(even mix; θ*) − π(last-touch mix; θ*)
```

## Hypothesis tests

| Null | p-value | Stakeholder reading |
| --- | --- | --- |
| β_c ≤ 0 | share of θ*_c ≤ 0 | Is this channel incremental at all? |
| iROAS_c ≤ 1 | share of iROAS*_c ≤ 1 | Does the next $1k pay for itself? |
| β_P = 0 | two-sided tail of θ*_P | Is price identified? |
| iROAS_TV − iROAS_Search = 0 | two-sided tail of the contrast | Are we allowed to move money between them? |
| π_inc − π_last ≤ 0 | share of profit-gap* ≤ 0 | Is the reallocation a fluke? |
| Price permutation | share of /θ*_P,perm/ ≥ /θ̂_P/ | Would a shuffled price series look this strong? |

```
Permutation of price:
  For b = 1..B_perm: shuffle log P, refit, store θ_P^{(b)}
  p = mean( |θ_P^{(b)}| ≥ |θ̂_P| )
```

## Ship / Watch / Kill

```
Ship  if Q_0.05(β*) > 0  and  Q_0.10(iROAS*) > 1
Kill  if Q_0.95(β*) < 0  or   Q_0.90(iROAS*) < 1
Watch otherwise
```
These are decision rules, not p-value theater. Watch means “keep the lock and go get a geo test,” not “the model failed.” Kill means do not ask for more budget on that channel from this evidence.

## How to run this on a real model

- Treat adstock θ and Hill K as fixed for the inner OLS, or nest a thinner bootstrap around a grid of (θ, K) if those were estimated.
- Prefer block or circular bootstrap on weeks. Residual bootstrap is the speed option when DW is near 2.
- B = 1,000 for a board pack. B = 280 is enough to see the shape on this studio.
- Brief the interval and the gate, not the p-value alone. Finance can read “TV iROAS 1.4 to 2.1” without a statistics lesson.
- If classical p < 0.001 and bootstrap p is 0.08, believe the bootstrap. Weekly MMM residuals are clustered.
- Do not ship a price move unless the permutation test and the CI agree.

---

# Page: uncertainty tests

Source: `projects/01_mmm_channel_optimization/development/templates/uncertainty_tests.html`

Statistical tests

### Bootstrap p-values

Below 0.05 we reject the null at 5%. One-sided tests are used for “is this positive / above hurdle?” Two-sided tests are used for contrasts and price.

### Price permutation null

Shuffle log-price, refit, collect the fake β_P. The observed coefficient should sit outside the null pile if price is identified. This does not assume residual normality.

### Tests

### Classical OLS (for comparison)

---

# Page: mmm problem

Source: `projects/01_mmm_channel_optimization/problem/templates/mmm_problem.html`

## MMM problem statement Problem

X Canada is a weekly meal-kit subscription (same economics as HelloFresh). It spends a weekly budget B across television, YouTube, social, and paid search to buy first boxes, while last-click tags credit branded search (“X meal kit”, “X Canada”) for people who already decided after a TV ad. Finance sees last-touch return that makes branded search look like the only profitable lever. Brand teams see those queries fall when television is cut. First-box promo depth, payday weeks, and popular-recipe stockouts also move ship-week revenue. We need a national weekly model that estimates incremental channel effects on net ship-week box revenue and recommends a feasible mix under min/max bounds.

## Scope

### In scope

National week grain. Media spend by parent channel. Price and promo depth as controls. Organic branded search as the mediator M. Ship-week net revenue as Y. Budget optimization under box constraints. Incremental mix versus last-touch, trade forecast, scenarios, bootstrap, and demand diagnostics as supporting development pages.

### Out of scope

Creative testing, keyword bidding, frequency caps, geo-level mix (v1), customer-level scoring (that is project 02), and claiming a geo test is identified from this mart (that is project 03).

### Decision this model is allowed to change

Next quarter’s weekly mix: how many dollars move from search to television or YouTube, and whether branded search is already on the flat part of the Hill curve.

## Questions

- If we cut television by $10k/week, how much branded search intent and net revenue do we lose over the adstock horizon?
- How much of paid search’s last-touch revenue is harvest of demand that upper-funnel already created?
- Where is each channel on its Hill curve, and what is the next-dollar total return (direct plus through intent)?
- Does a price or promo week look like a media win if we omit those controls?
- Is the holdout fit strong enough that Sequential Least Squares Programming should ship, watch, or kill the recommendation?

## Approaches we considered

| Approach | What it does | Why we did not stop there |
| --- | --- | --- |
| Last-touch / multi-touch rules | Assigns the box to the last or a weighted click. | Credits harvest. Cannot answer a spend cut. |
| Ordinary least squares of sales on spend | One equation, all channels enter Y. | Search is endogenous with demand. Coefficients steal television’s effect. |
| Black-box AutoML on the mart | Fits whatever predicts Y. | No structural M, no mROI, no constrained optimizer finance will sign. |
| Full Bayesian media mix | Priors on adstock and saturation. | Right later, heavier to produce weekly. Not required to teach the funnel identification story. |
| Funnel two-stage least squares + Sequential Least Squares Programming | Stage 1: media → intent. Stage 2: intent + harvest → sales. Then optimize B. | Selected. Matches the bias we are hired to fix. |

## Why we selected this approach

- The business process is two-step: people search for X, then they convert. A one-equation sales model cannot represent that.
- Two-stage least squares gives an instrumented intent series so harvest channels do not eat upper-funnel coefficients.
- Geometric or Weibull adstock and Hill saturation are the minimum shapes finance already debates (memory and diminishing returns).
- Sequential Least Squares Programming respects the same weekly envelope and channel floors/caps the media team already uses.
- The studio can recover known data-generating-process truth, so a stakeholder can see identification fail when we omit a control or flatten television flighting.

## Assumptions

- Grain. One Canada week. Ship-week net revenue is the outcome operations books, not click-week Google value.
- Exclusion. Top-of-funnel spend moves sales only through intent M (alpha path). Bottom-of-funnel has no alpha.
- Transforms. Adstock is a known decay; Hill K is a saturation location, not a budget cap.
- Controls. Price, promo depth, holiday, payday, stockout, and share of voice are not channels. Omit them and media steals their weeks.
- Budget. The optimizer cannot invent money. Sum of recommended spend equals B inside bounds.
- Transfer. Synthetic data in the lab has the same equations as production. Production only changes the warehouse feed, not the likelihood.

## What would change the choice

If finance requires geo incremental return, we do not stretch this national mart — we open project 03. If the question is “which customers are worth a win-back,” we open project 02. If holdout MAPE stays above the lab gate after controls and flighting are honest, we watch or kill the mix and do not ship Sequential Least Squares Programming.

Run the test on the lab Data engineering Development Production — Azure

---

# Page: mmm production

Source: `projects/01_mmm_channel_optimization/production/templates/mmm_production.html`

### MMM production — Azure Landing zone

One subscription, three resource groups: rg-x-mmm-dev, rg-x-mmm-stage, rg-x-mmm-prod. Azure Data Lake Storage Generation 2 account stxmmm{env}. Key Vault kv-x-mmm-{env}. Virtual Network private endpoints. No public lake.

### Monday job

Parent pipeline pl_x_mmm_week at 06:00 America/Toronto. Wait for _SUCCESS on Google Ads, orders, and Search Console. Run data build tool tests. If any unique-week test fails, skip the engine and page finance.

### What ships

Tagged image x-mmm:{git-commit} on Azure Container Registry. Job writes gold.model_run_log and gold.allocation_recommended (spend per channel). Power BI workspace reads gold. Nobody edits the allocation in a notebook after Monday.

## Azure services in this project

| Service | Role |
| --- | --- |
| Azure Data Lake Storage Generation 2 | bronze / silver / gold folders |
| Azure Data Factory | Daily copies and the Monday parent |
| Microsoft Fabric Warehouse | Star schema and mart_mmm_weekly |
| Azure Container Apps Job | Engine fit and channel optimizer |
| Azure Container Apps | This studio, read-only against gold |
| Microsoft Entra Identifier + Power BI | Finance pack, gold only |

Zero-to-weekly Azure steps (hashes stay on the studio file) Azure section Data engineering contract Development

Legacy URL /production still opens this Azure page. Amazon Web Services production lives on the causal project.
