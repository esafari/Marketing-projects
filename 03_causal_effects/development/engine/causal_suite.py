"""Multi-problem causal suite: one commercial question per estimator family."""

from __future__ import annotations

import numpy as np
from scipy import stats
from scipy.optimize import minimize
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

METHOD_IDS = (
    "did",
    "iv",
    "synthetic_control",
    "ipw",
    "causal_impact",
    "dml",
    "meta_learner",
    "ab_mvt",
    "bootstrap",
    "hypothesis",
    "uncertainty",
    "deep_learning",
)


def list_methods() -> list[dict]:
    rows = []
    for method_id in METHOD_IDS:
        row = dict(_meta(method_id))
        row["id"] = method_id
        rows.append(row)
    return rows


def run_causal_method(method: str, seed: int = 42, **kwargs) -> dict:
    method = str(method).strip().lower()
    if method not in METHOD_IDS:
        raise ValueError(f"Unknown method: {method}")
    runner = {
        "did": _run_did,
        "iv": _run_iv,
        "synthetic_control": _run_sc,
        "ipw": _run_ipw,
        "causal_impact": _run_impact,
        "dml": _run_dml,
        "meta_learner": _run_meta,
        "ab_mvt": _run_ab,
        "bootstrap": _run_bootstrap,
        "hypothesis": _run_hypothesis,
        "uncertainty": _run_uncertainty,
        "deep_learning": _run_deep,
    }[method]
    result = runner(np.random.default_rng(int(seed)), **kwargs)
    result.update(_meta(method))
    result["id"] = method
    result["seed"] = int(seed)
    result["result_explain"] = _result_explain(method, result)
    return result


def _result_explain(method: str, result: dict) -> str:
    m = result["metrics"]
    est, truth, bias = m["estimate"], m["true"], m["bias"]
    gate = "PASS" if m["passed"] else "FAIL"
    extra = {
        "did": (
            f"True first-box lift is {100 * truth:.1f}%. Difference-in-differences estimates {100 * est:.1f}% "
            f"(error {100 * bias:+.1f} points). The naive treated-only pre/post is in the KPI row — "
            f"if it is larger, those extra points are first-box growth those metros would have had anyway "
            f"(January, payday, word of mouth). Brief the DiD percent to finance, not the treated YouTube line."
        ),
        "iv": (
            f"The causal price slope is planted at {truth:.2f}. Two-stage least squares recovers {est:.2f} "
            f"(error {bias:+.2f}). Ordinary least squares is the other KPI — if it is closer to zero, "
            f"January demand hid how much price-per-serving really hurts weekly boxes. Only trust IV if first-stage F is above 10."
        ),
        "synthetic_control": (
            f"The true post-launch add is {truth:.1f} first boxes in Ontario. The synthetic-control gap is {est:.1f} "
            f"(error {bias:+.1f}). Naive Ontario pre/post usually counts Ontario's own January path as brand TV. "
            f"The chart should match before the cut and split after. Donor weights are the twin province mix."
        ),
        "ipw": (
            f"True extra boxes from the 40% win-back are {truth:.2f}. Inverse probability weighting estimates {est:.2f} "
            f"(error {bias:+.2f}). The naive redeemer gap is larger when engaged cancels self-select. "
            f"Pay for the discount only on the IPW number, not the raw gap."
        ),
        "causal_impact": (
            f"The true national New Year add is {truth:.1f} first boxes. The forecast gap is {est:.1f} "
            f"(error {bias:+.1f}). Raw post-minus-pre also includes the ordinary January resolution spike. "
            f"Read the gap after the cut; that is the flight, not the calendar."
        ),
        "dml": (
            f"True extra boxes from the pause-save offer are {truth:.2f}. Double machine learning estimates {est:.2f} "
            f"(error {bias:+.2f}). If naive is higher, the difference is family-plan and tenure selection. "
            f"OLS-with-CRM is a simpler check; DML is the one we take when the cancel file is wide."
        ),
        "meta_learner": (
            f"Average CATE is planted at {truth:.2f}; the best learner's mean is {est:.2f}. "
            f"PEHE in the table is distance to the true individual effects — lower is better. "
            f"If T or X beats S, do not mail 50% stay to everyone: mail at-risk skippers, not loyal weekly family plans."
        ),
        "ab_mvt": (
            f"$4.99-a-serving badge main effect is planted at {truth:.1f}; we recovered {est:.2f}. "
            f"Free first delivery and the interaction are in the KPIs. The both-on homepage cell should be highest "
            f"if the levers amplify. Interaction near zero means we can ship badge and free delivery independently."
        ),
        "bootstrap": (
            f"Meal-picker first-box lift is {est:.2f} versus true {truth:.2f}. The 90% bootstrap interval is in the KPIs. "
            f"If the lower end is above 0, the lift is not a lucky payday week. "
            f"A wide interval means you need more checkout traffic, not a fancier point estimate."
        ),
        "hypothesis": (
            f"The $4.99 first-box badge contrast is {est:.2f} (planted main effect {truth:.1f}). "
            f"t-test p={m.get('p_ttest', 0):.4f} and ANOVA p={m.get('p_anova', 0):.4f}. "
            f"p < 0.05 rejects 'the homepage did nothing.' It does not say the badge is worth the first-box margin."
        ),
        "uncertainty": (
            f"Reactivation SMS extra boxes are {est:.2f} versus true {truth:.2f}. Normal and bootstrap 90% intervals are in the KPIs. "
            f"Blast the next cancel file only if both lower bounds are above 0 and both intervals contain the planted truth. "
            f"If the two intervals disagree, use the wider one and do not send."
        ),
        "deep_learning": (
            f"True mean extra boxes from the deeper discount are {truth:.2f}; the neural T-learner mean is {est:.2f}. "
            f"Neural PEHE={m.get('pehe_deep', 0):.2f} versus linear PEHE={m.get('pehe_linear', 0):.2f}. "
            f"Lower PEHE means closer individual extra-box scores. If the net is worse, it overfit — do not discount loyal weekly subscribers on the net."
        ),
    }
    body = extra.get(method, result.get("story", ""))
    return f"{gate} on the lab gate. {body}"


def run_causal_suite(seed: int = 42) -> dict:
    results = [run_causal_method(method_id, seed=int(seed)) for method_id in METHOD_IDS]
    passed = sum(1 for row in results if row["metrics"]["passed"])
    return {
        "n_methods": len(results),
        "n_passed": passed,
        "results": results,
        "story": f"{passed} of {len(results)} method gates passed on seed {seed}.",
    }


def _meta(method_id: str) -> dict:
    catalog = {
        "did": {
            "title": "Difference-in-differences",
            "commercial": "First-box YouTube in markets that were already hot",
            "problem": (
                "X Canada is a weekly meal-kit subscription (same economics as HelloFresh): new customers start on a "
                "cheap first box, then either stay on a weekly plan, skip, pause, or cancel. Growth marketing put extra "
                "YouTube into the five census metros that already had the fastest first-box growth — the usual "
                "'put media where it is working' instinct. Those metros then ship more first boxes. The question is "
                "not whether first boxes went up. The question is whether those extra first boxes are incremental "
                "YouTube, or January / payday / word-of-mouth growth those metros were already on."
            ),
            "situation": (
                "Sixteen Canadian geos, sixty weeks, extra YouTube from week 36. Treated metros were chosen by ranking "
                "recent first-box growth (not a randomized holdout). Each geo keeps its own trend and recipe-season "
                "wiggle. The lab plants a true 10% multiplicative lift in first-box acquisitions after launch."
            ),
            "decision": (
                "Scale the YouTube burst to the rest of Canada, hold it in the five metros, or kill it and keep the "
                "first-box budget on paid search. Finance will not put a first-box CAC win in the board pack until we "
                "separate the burst from the growth we selected on."
            ),
            "units": (
                "Grain: metro by week. Outcome Y = first-box (new-customer) ship-week boxes, not continuing boxes. "
                "Treatment D_i = 1 if the metro got extra YouTube. Post P_t = 1 after launch. Continuing subscribers "
                "are a different decision (lifetime value, project 02)."
            ),
            "naive_trap": (
                "Treated-only pre/post credits the metros' own New Year / urban growth as media. Meal-kit first boxes "
                "already spike in January. Because we chose the fastest growers, the naive first-box lift is "
                "systematically too large and makes YouTube look cheaper than it is."
            ),
            "success": (
                "Difference-in-differences (ratio-of-ratios) lands near the planted 10% first-box lift and closer to "
                "truth than treated-only pre/post. If DiD is still far off, parallel trends failed — we do not scale "
                "and we do not cut paid search on this number."
            ),
            "approach": "Take the treated-minus-control first-box gap after launch and subtract the same gap before launch. We report the ratio-of-ratios form so the number is a percent lift, comparable to the planted 10% truth.",
            "why": "Meal-kit growth teams already brief 'test versus control markets' for TV and YouTube. DiD is that brief, written as an estimator. It fails when we picked the hottest metros — which is why this lab treats the fastest geos on purpose.",
            "assumptions": "Parallel trends (control would have tracked treated); no spillover into control geos; assignment locked; ship-week boxes.",
            "math": (
                "Y_it = boxes in geo i, week t\n"
                "D_i = 1 if geo is treated, P_t = 1 after launch\n"
                "Ratio-of-ratios DiD:\n"
                "  tau_hat = (Y_t,post / Y_t,pre) / (Y_c,post / Y_c,pre) - 1\n"
                "Naive (wrong if trends differ):\n"
                "  tau_naive = Y_t,post / Y_t,pre - 1\n"
                "Two-way form (same idea): E[Y|D=1,P=1] - E[Y|D=1,P=0]\n"
                "                         - (E[Y|D=0,P=1] - E[Y|D=0,P=0])"
            ),
            "read": "If DiD is near the true 10% and naive pre/post is larger, the extra naive points are growth you would have gotten anyway. Brief DiD, not the treated-only chart.",
        },
        "iv": {
            "title": "Instrumental variables (two-stage least squares)",
            "commercial": "Everyday price per serving when January demand is already high",
            "problem": (
                "X Canada prices a weekly box as price-per-serving (the HelloFresh-style $9.99 vs $11.49 decision). "
                "Pricing raises everyday price or shrinks the first-box discount in hot weeks — New Year resolutions, "
                "payday Fridays, Super Bowl. People still convert, so a regression of boxes on price looks almost flat "
                "and finance concludes 'customers are not price sensitive.' We need the causal slope: if we raised "
                "price-per-serving one unit while demand stayed the same, how many weekly boxes would we lose?"
            ),
            "situation": (
                "National weekly series of continuing plus first boxes. Price and unobserved demand (resolutions, "
                "weather, a viral recipe) move together. A cost shock Z — chicken and produce inflation, or last-mile "
                "courier rates — also moves the shelf price, but households do not order more kits because protein "
                "cost went up except through that price."
            ),
            "decision": (
                "Whether we can lift everyday price after the New Year rush without crushing weekly boxes, and whether "
                "the first-box promo can be pulled back. Ordinary-least-squares elasticity is not a pricing tool here."
            ),
            "units": (
                "Grain: national week. Outcome Y = ship-week boxes. Endogenous regressor = everyday price per serving "
                "(or first-box net price). Instrument Z = food or last-mile cost shock. Object is tau in "
                "Y = alpha + tau * Price + u, planted at -1.20."
            ),
            "naive_trap": (
                "OLS of boxes on price is biased toward zero: January has both higher prices (we harvest demand) and "
                "higher boxes, which looks like 'price barely hurts.' That is how meal-kit teams over-raise price "
                "and then watch skip and cancel rise two weeks later."
            ),
            "success": (
                "Two-stage least squares recovers a slope near -1.20, and the first-stage F on the cost shock is "
                "above 10. If F is weak, we do not brief the IV number and we run a real price test instead."
            ),
            "approach": "Use a food or last-mile cost shock Z that moves price-per-serving but does not belong in the demand equation. First stage: price on Z. Second stage: boxes on fitted price.",
            "why": "Meal-kit price is chosen with demand. OLS is not an elasticity. A cost instrument is the fix when a randomized price test is not on the table this quarter.",
            "assumptions": "Relevance: Z moves price (first-stage F > 10). Exclusion: Z affects boxes only through price. Monotonicity of the first stage.",
            "math": (
                "Structural demand:  Y = alpha + tau * Price + u\n"
                "Price is endogenous:  Corr(Price, u) != 0\n"
                "Instrument Z (cost shock):\n"
                "  Stage 1:  Price = pi_0 + pi_1 Z + v\n"
                "  Stage 2:  Y     = alpha + tau * Price_hat + e\n"
                "tau is the causal price coefficient we want (planted at -1.20)."
            ),
            "read": "OLS closer to zero than IV means demand shocks hid the true negative price effect. Trust IV only if first-stage F is large. If IV and OLS agree, the endogeneity was weak.",
        },
        "synthetic_control": {
            "title": "Synthetic control",
            "commercial": "Ontario-only brand TV before a second-province rollout",
            "problem": (
                "Brand buys a connected-TV and linear-TV flight only in Ontario — the largest meal-kit market — "
                "to see if a French or West-Coast flight is worth writing. There is no randomized twin and only "
                "one treated province, so a many-market DiD average does not apply. We need a counterfactual "
                "Ontario: how many first boxes would Ontario have shipped if that brand flight had not run?"
            ),
            "situation": (
                "Ontario gets the flight; other provinces are unused donors (never in the buy). Ontario has its "
                "own hockey-season and January path. The lab plants an additive +18 first boxes after launch "
                "on Ontario only."
            ),
            "decision": (
                "Roll the same brand TV into Quebec or British Columbia, or keep the money on national YouTube "
                "and paid search. If the synthetic twin already tracks Ontario after launch, we do not scale."
            ),
            "units": (
                "Grain: province by week. Treated path Y_1t = Ontario first-box (or total) boxes. Donors Y_jt = "
                "other provinces. Weights w_j >= 0 sum to 1. Effect is the post-period mean of Ontario minus the twin."
            ),
            "naive_trap": (
                "Ontario pre/post, or Ontario versus 'Quebec looks similar,' counts Ontario's own urban growth "
                "and January resolutions as brand TV. One donor is usually a bad twin for a meal-kit launch."
            ),
            "success": (
                "Pre-period synthetic path hugs Ontario; post-period gap sits near +18 first boxes; a few donors "
                "carry most of the weight. Naive Ontario-only pre/post should look larger than the synthetic gap."
            ),
            "approach": "Choose nonnegative donor weights that sum to 1 and match Ontario's pre-launch first-box path. After launch, lift is Ontario minus that weighted twin.",
            "why": "One large province, many unused donors. That is the geometry of a single-market meal-kit TV test. Synthetic control is built for it.",
            "assumptions": "Donors are untreated; no anticipation; weights >= 0 and sum to 1; no interference from Ontario ads into donors.",
            "math": (
                "Treated path Y_1t. Donors Y_jt, j=2..J.\n"
                "Choose w >= 0, 1'w = 1 to minimize\n"
                "  || Y_1,pre - sum_j w_j Y_j,pre ||^2\n"
                "Synthetic path:  Y*_t = sum_j w_j Y_jt\n"
                "Post effect:  tau_hat = mean_t in post (Y_1t - Y*_t)\n"
                "Truth in this lab is an additive +18 boxes after launch."
            ),
            "read": "The chart should hug before the cut and split after. If the post gap is near +18 and naive pre/post is larger, naive counted Ontario's own trend as 'lift.' Weights in the table are the twin — a few donors should carry most of the mass.",
        },
        "ipw": {
            "title": "Inverse probability weighting",
            "commercial": "Win-back: 40 percent off the next two boxes",
            "problem": (
                "CRM emails cancelled subscribers a HelloFresh-style win-back: 40% off the next two boxes. "
                "Redeem is voluntary. People who still open the app, who had many prior boxes, or who only "
                "paused last month are much more likely to click. Comparing redeemers to non-redeemers mixes "
                "the coupon with 'these people were coming back anyway.' We want the average extra boxes on "
                "the whole mailed cancel file — the number that pays for the discount margin."
            ),
            "situation": (
                "Customer-level rows after one win-back drop. Treatment D is redeem, not random assignment. "
                "X includes prior boxes, tenure, last-open recency, and plan size (two-person vs family). "
                "True average extra boxes is planted at +4.5 over the next horizon."
            ),
            "decision": (
                "Keep, shrink, or kill the 40% win-back for the next cancel cohort. If the incremental boxes "
                "do not cover the discount, we move to a skip reminder or a smaller 20% offer. Targeting who "
                "should get it is the meta-learner card."
            ),
            "units": (
                "Grain: cancelled (or long-paused) customer. Outcome Y = boxes shipped in the next 8 weeks. "
                "Treatment D = 1 if the 40% code was redeemed. Population = everyone who was emailed, not only redeemers."
            ),
            "naive_trap": (
                "Redeemer-minus-non-redeemer is too large: engaged cancels redeem and would have resubscribed "
                "on a payday or a New Year anyway. That is how win-back ROAS looks great while incremental "
                "margin is thin."
            ),
            "success": (
                "Inverse-probability weighted average sits near +4.5 extra boxes and below the naive gap. "
                "If weights explode (almost-sure redeemers or never-redeemers), overlap failed and we do not brief it."
            ),
            "approach": "Fit propensity e(X) = P(redeem | prior boxes, tenure, recency, plan size). Reweight redeemed outcomes by 1/e and non-redeemed by 1/(1-e), then subtract.",
            "why": "Win-back is not randomized, but we observe the CRM fields that drove redeem. IPW recenters redeemers and non-redeemers onto one mailed cancel file.",
            "assumptions": "Unconfoundedness given X. Overlap: 0 < e(X) < 1 (we clip to [0.05, 0.95]). SUTVA.",
            "math": (
                "e(X) = P(D=1 | X)\n"
                "IPW ATE =\n"
                "  E[ D Y / e(X) ]  -  E[ (1-D) Y / (1-e(X)) ]\n"
                "Naive gap = E[Y|D=1] - E[Y|D=0]   (biased if X differs)\n"
                "Planted ATE in this lab is +4.5."
            ),
            "read": "If naive is much larger than IPW, the extra is selection (engaged people take the offer). Brief IPW. If they match, selection was weak. If IPW is wild, overlap failed — someone had e near 0 or 1.",
        },
        "causal_impact": {
            "title": "Time-series causal impact",
            "commercial": "National New Year resolution flight with no holdout",
            "problem": (
                "Brand runs a national New Year (or Super Bowl) flight — TV, YouTube, and a homepage "
                "'new year, new routine' first-box offer — starting one Monday. Every province is in the buy, "
                "so there is no holdout metro. First boxes always rise in January anyway. The only contrast "
                "left is time: what would national first boxes have done after that Monday if the flight "
                "and the offer had not run?"
            ),
            "situation": (
                "One national weekly first-box series with trend and a 13-week seasonal wiggle (resolutions, "
                "then a spring slump). At week T0 the campaign adds a planted +12 first boxes on top of that "
                "path. No donor geos exist by design."
            ),
            "decision": (
                "Renew the New Year package next January, cut national TV and keep only the first-box discount, "
                "or move money into geo tests. A national mix-model coefficient is the wrong grain for one "
                "interrupted week."
            ),
            "units": (
                "Grain: national week. Outcome Y_t = first-box acquisitions. Cut T0 = campaign Monday. "
                "Counterfactual = forecast from a pre-period trend-plus-season model. Effect = mean post "
                "(actual minus forecast)."
            ),
            "naive_trap": (
                "Post mean minus pre mean includes the ordinary January resolution spike. Meal-kit teams "
                "brief that spike as media every year. It will look like a larger campaign than we planted."
            ),
            "success": (
                "The forecast continues the pre-period wiggle; the gap after the cut sits near +12 first boxes. "
                "We do not brief this if a price change, a popular-recipe stockout, or payday landed the same week."
            ),
            "approach": "On the pre-period, fit trend plus weekly season (the resolution-then-slump shape). Forecast the post-period. Lift is actual first boxes minus that forecast, averaged after the cut.",
            "why": "National meal-kit brand flights often have no geo holdout. Interrupted time series / CausalImpact-style is what is left.",
            "assumptions": "The pre-period model would have continued. No other national shock lands on the same week. Additive lift in this lab is +12.",
            "math": (
                "Pre-period t < T0:\n"
                "  Y_t = b0 + b1 t + b2 sin(2 pi t / 13) + b3 cos(2 pi t / 13) + e_t\n"
                "Forecast Yhat_t for t >= T0 from that fit.\n"
                "tau_hat = mean_{t >= T0} (Y_t - Yhat_t)\n"
                "Naive = mean_post Y - mean_pre Y   (confounds trend and season)."
            ),
            "read": "The forecast line should continue the pre-period wiggle. The gap after the cut is the campaign. If naive pre/post is bigger, you counted the ordinary upward trend as media. Do not brief this if another national event hit the same week.",
        },
        "dml": {
            "title": "Double machine learning",
            "commercial": "Pause-to-skip offer with a messy CRM file",
            "problem": (
                "A subscriber hits cancel. CRM shows a HelloFresh-style save: 'Skip this week instead — or take "
                "50% off your next box if you stay.' Who clicks depends on many things at once: weeks on the plan, "
                "two-person vs family, how many discounts they already used, whether they came from an affiliate "
                "or paid social, device, last recipe rating. A raw 'savers vs cancellers' gap is confounded. "
                "A single OLS that 'controls for everything' can still be wrong if that X specification is brittle. "
                "We want the average extra boxes kept after we partial out that rich file."
            ),
            "situation": (
                "Customer-level observational save offer. D = took the skip or 50% stay offer. Y = boxes in the "
                "next 8 weeks. X is the CRM file above. True average extra boxes is planted at +3.0, and X also "
                "moves Y directly (family plans already ship more)."
            ),
            "decision": (
                "Whether the pause-save program has incremental boxes after we remove selection. If the average "
                "is real, we keep the program and then target with the next card. If it is not, we are paying "
                "margin to people who were going to skip anyway."
            ),
            "units": (
                "Grain: subscriber who entered the cancel flow. Y = later boxes, D = took the save offer, "
                "X = tenure, plan size, discount history, acquisition channel, device. Object is tau in "
                "Y = tau D + g(X) + u."
            ),
            "naive_trap": (
                "The raw gap credits family-plan and high-tenure subscribers to the offer. One-shot OLS of Y "
                "on D and X can still bias tau if plan size or discount history is misspecified."
            ),
            "success": (
                "Residual-on-residual double machine learning sits nearer +3.0 extra boxes than the naive gap. "
                "If it agrees with OLS-plus-X, a linear CRM specification was already enough."
            ),
            "approach": "Residualize later boxes on the CRM file and offer take-up on the CRM file with Ridge. Then regress the Y residual on the D residual.",
            "why": "Meal-kit CRM files are wide. Neyman orthogonality means small mistakes in those two first stages do not first-order bias the extra-box number.",
            "assumptions": "Unconfoundedness given X; overlap; first stages are not wildly overfit (Ridge, not an unconstrained deep net).",
            "math": (
                "Y = tau D + g(X) + u\n"
                "D = m(X) + v\n"
                "Y_res = Y - ghat(X),   D_res = D - mhat(X)\n"
                "tau_hat = argmin_tau  || Y_res - tau D_res ||^2\n"
                "Planted ATE is +3.0. Naive = E[Y|D=1]-E[Y|D=0]."
            ),
            "read": "Read DML next to naive and OLS+X. If DML sits nearer +3 than the naive gap, the extra naive points are confounding. If DML and OLS agree, a linear g(X) was already enough.",
        },
        "meta_learner": {
            "title": "Meta-learners (S / T / X)",
            "commercial": "Who should get the pause-save discount — not the whole base",
            "problem": (
                "The same 50% stay offer does not help every subscriber. People who have skipped three weeks, "
                "rated meals poorly, or are on a two-person plan after a first-box promo get a large extra-box "
                "lift. Weekly family-plan loyalists take the 50% they did not need — you pay margin and they "
                "would have shipped anyway. An average can say 'mail the whole cancel-risk file' when one "
                "segment should not get the discount at all. We need CATE(x): expected extra boxes for a "
                "subscriber with features x."
            ),
            "situation": (
                "Customer-level save offer. True extra boxes are 1 for low-risk (loyal weekly) and 4 for "
                "high-risk (skipped / low rating / post-promo) — a jump of 3 when X1 > 0. We fit S, T, and X "
                "learners and score them against that known shape."
            ),
            "decision": (
                "Who gets the 50% stay offer next week. Mail only the high-CATE segment if the gap is real. "
                "Loyal weekly subscribers get a skip reminder or nothing — not a discount."
            ),
            "units": (
                "Grain: subscriber. Y = later boxes, D = offer, X = skip history, rating, plan size, tenure, "
                "first-box promo flag. Object is tau(x) = E[Y(1)-Y(0)|X=x]. Score is PEHE versus true tau(x)."
            ),
            "naive_trap": (
                "One average hides the loyal segment you should not discount. A single S-learner that only "
                "adds a treatment flag smears the jump and you keep mailing 50% to people who never pause."
            ),
            "success": (
                "At least one learner recovers a high-versus-low extra-box gap near 3 and a low PEHE. We "
                "target high-CATE (at-risk) and withhold the same 50% from low-CATE loyalists."
            ),
            "approach": "S-learner: one model with an offer flag. T-learner: one model on those who got the save, one on those who did not, then subtract. X-learner: impute individual extra boxes, then a second-stage model blended by propensity.",
            "why": "CATE is the CRM targeting object. PEHE says which learner recovered 'at-risk vs loyal' instead of one average.",
            "assumptions": "Unconfoundedness given X; enough treated and control in each segment we report.",
            "math": (
                "True CATE in this lab:  tau(x) = 1 + 3 * 1{x1 > 0}\n"
                "S:  mu(x,d) = E[Y|X=x,D=d],   tau_S = mu(x,1)-mu(x,0)\n"
                "T:  mu1(x)=E[Y|X=x,D=1], mu0(x)=E[Y|X=x,D=0],  tau_T = mu1-mu0\n"
                "X:  D_i=1:  tau~ = Y - mu0(X);  D_i=0:  tau~ = mu1(X) - Y\n"
                "    tau_X(x) = e(x) tau_0(x) + (1-e(x)) tau_1(x)\n"
                "PEHE = sqrt( E[ (tau_hat(X) - tau(X))^2 ] )"
            ),
            "read": "Lower PEHE is better. If T or X PEHE is clearly below S, the single-model S-learner smeared the segment effect. The table's 'high' versus 'low' gap should sit near 3. Target the high-CATE segment; do not mail the low-CATE segment the same offer.",
        },
        "ab_mvt": {
            "title": "A/B and multivariate testing",
            "commercial": "First-box landing page: $4.99 a serving times free delivery",
            "problem": (
                "The acquisition landing page can show a first-box price badge ('Meals from $4.99 a serving'), "
                "waive the delivery fee on box one, show both, or show neither (everyday price, paid delivery). "
                "Two sequential A/Bs — badge first, free delivery later — never see the combination. In meal kits "
                "those levers often amplify: the cheap first box plus 'no delivery fee' is how HelloFresh-class "
                "sites convert cold traffic. We need main effects and the interaction from one randomized 2-by-2."
            ),
            "situation": (
                "New-visitor sessions independently assigned to the four homepage cells. True effects are "
                "planted at +3 for the $4.99 badge, +5 for free first-box delivery, and +1.2 extra when both "
                "are on (they amplify)."
            ),
            "decision": (
                "Which of the four first-box experiences is the default homepage. If the interaction is real, "
                "we must ship both — not the winner of a badge test and the winner of a later shipping test. "
                "Finance also cares because both levers cost margin on box one."
            ),
            "units": (
                "Grain: new-visitor session. Outcome Y = first-box checkout conversion score. A = $4.99 badge "
                "on/off. B = free first delivery on/off. Objects: tau_A, tau_B, tau_AB from the four cell means."
            ),
            "naive_trap": (
                "Two sequential A/Bs miss the extra lift of cheap first box plus free delivery. Last-click "
                "'paid search converted' also cannot say which homepage combination actually closed the box."
            ),
            "success": (
                "Recover badge near 3, free delivery near 5, interaction near 1.2. The both-on cell should "
                "be the highest first-box conversion. Interaction near zero would mean we can ship them independently."
            ),
            "approach": "Assign each new visitor independently to badge in {0,1} and free delivery in {0,1}. Estimate the four first-box conversion means, then main effects and the interaction.",
            "why": "A factorial answers both first-box levers and whether they amplify, in one flight — the actual homepage decision.",
            "assumptions": "Independent users; SUTVA; assignment is the experiment (not a later opt-in).",
            "math": (
                "Y = mu + tau_A A + tau_B B + tau_AB A B + e\n"
                "Planted: tau_A=3, tau_B=5, tau_AB=1.2\n"
                "tau_A = 1/2 [(Y_10 - Y_00) + (Y_11 - Y_01)]\n"
                "tau_B = 1/2 [(Y_01 - Y_00) + (Y_11 - Y_10)]\n"
                "tau_AB = (Y_11 - Y_10) - (Y_01 - Y_00)\n"
                "Y_ab = mean outcome in cell A=a, B=b."
            ),
            "read": "Read the four cell means first. Badge main effect near 3 and shipping near 5 means both levers work. Interaction near 1.2 means together they add a bit more than the sum of mains. If interaction is ~0, you can ship them independently.",
        },
        "bootstrap": {
            "title": "Bootstrapping the average treatment effect",
            "commercial": "Checkout meal-picker test — how wide is +2.4?",
            "problem": (
                "Product tests a HelloFresh-style checkout change: 'Choose your first 3 meals' versus a "
                "default pre-selected menu. The A/B reports +2.4 on first-box conversion. Finance's next "
                "question is not the point. It is how wide that +2.4 is if we had drawn a different week "
                "of the same new-visitor traffic. A point estimate cannot answer that, and first-box "
                "traffic is noisy (payday, weather, a TV burst)."
            ),
            "situation": (
                "Randomized two-cell checkout test. Sessions are the resampling units. We redraw the week "
                "with replacement, keep each session's assignment, and recompute the first-box conversion "
                "lift each time."
            ),
            "decision": (
                "Ship the meal-picker as default checkout, or hold and collect another week. If the 90% "
                "interval still covers zero, we do not treat +2.4 as a fact — meal-picker engineering cost "
                "is not justified on a lucky sample."
            ),
            "units": (
                "Grain: new-visitor checkout session. Object is the sampling distribution of first-box "
                "conversion ATE. We report the 5th and 95th percentiles. Planted ATE is +2.4."
            ),
            "naive_trap": (
                "Treating the first week's +2.4 as exact. A payday week can look like a win; the next "
                "week of the same experiment can cross zero."
            ),
            "success": (
                "The 90% interval covers the planted 2.4 and excludes 0. A wide interval means we need "
                "more first-box traffic, not a different estimator."
            ),
            "approach": "Resample checkout sessions with replacement, keep assignment, recompute first-box conversion ATE many times. Report the 5th and 95th percentiles (90% interval).",
            "why": "Meal-kit conversion is noisy week to week. The interval is what a ship/kill gate should use, not the first point.",
            "assumptions": "Users are i.i.d.; assignment stays with the user; 90% percentile interval.",
            "math": (
                "ATE = E[Y|D=1] - E[Y|D=0]\n"
                "For b=1..B: draw (Y*,D*) by sampling rows with replacement\n"
                "  ATE*_b = mean(Y*|D*=1) - mean(Y*|D*=0)\n"
                "CI_90 = [quantile_0.05(ATE*), quantile_0.95(ATE*)]\n"
                "Planted ATE is +2.4. Gate: interval covers 2.4 and excludes 0."
            ),
            "read": "The histogram is the sampling distribution of the ATE. If 0 is left of the 5th percentile, the lift is not a fluke of one draw. If the interval is wide, you need more users, not a different point estimator.",
        },
        "hypothesis": {
            "title": "Hypothesis testing (t-test and ANOVA)",
            "commercial": "Did the $4.99 first-box badge actually move conversion?",
            "problem": (
                "After the homepage 2-by-2, the CMO and finance want two yes/no answers, not a lift chart: "
                "did the $4.99-a-serving badge move first-box conversion, and do the four landing-page cells "
                "differ as a set? Those are hypothesis tests. They are not a substitute for 'how many extra "
                "first boxes' or 'does the extra discount margin pay back.'"
            ),
            "situation": (
                "Same randomized factorial as the landing-page card. We test (1) badge versus no-badge with a "
                "Welch t-test and (2) equality of the four homepage cells with one-way analysis of variance."
            ),
            "decision": (
                "Whether we can reject 'the first-box page did nothing' at 5%. A reject is permission to read "
                "magnitudes and margin on the factorial and uncertainty cards — it is not itself a ship of "
                "the $4.99 badge."
            ),
            "units": (
                "Grain: new-visitor session. t-test compares first-box conversion with vs without the $4.99 "
                "badge. ANOVA compares the four cells. Outputs are t, F, and p-values."
            ),
            "naive_trap": (
                "Reading p < 0.05 as 'the badge is worth the first-box margin' or p > 0.05 as 'the badge does "
                "nothing.' A tiny conversion bump is significant on a huge January sample; a real bump can "
                "miss 5% in a quiet summer week."
            ),
            "success": (
                "Both p-values fall below 0.05 when the planted first-box effects are real. We still pair this "
                "with cell magnitudes and uncertainty before we make $4.99 plus free delivery the default."
            ),
            "approach": "Welch t-test on $4.99 badge versus no badge. One-way ANOVA across the four first-box landing cells.",
            "why": "These are the tests already in an experiment readout. They only mean something after homepage assignment is randomized.",
            "assumptions": "Independent users; Welch t-test allows unequal variance; ANOVA null is equal cell means.",
            "math": (
                "t-test H0: mu_badge = mu_no_badge\n"
                "  t = (Ybar_1 - Ybar_0) / sqrt(s1^2/n1 + s0^2/n0)\n"
                "ANOVA H0: mu_00 = mu_01 = mu_10 = mu_11\n"
                "  F = MS_between / MS_within\n"
                "Reject H0 at 5% if p < 0.05. This does not measure how large the effect is."
            ),
            "read": "p < 0.05 means 'unlikely if the null were true,' not 'the effect is large.' Pair this card with the factorial and uncertainty cards. A tiny effect can be significant in a huge sample; a large effect can miss 5% in a small one.",
        },
        "uncertainty": {
            "title": "Uncertainty estimation",
            "commercial": "Reactivation SMS — ship only if the interval clears zero",
            "problem": (
                "Lifecycle sends a 'Come back this week — your favourites are on the menu' SMS to recently "
                "cancelled subscribers. The point lift is +1.8 extra boxes on a conversion-like score. That "
                "can be noise: SMS files are small and payday weeks bounce. The ship question is whether an "
                "honest interval still sits entirely above zero. We want two different 90% intervals on the "
                "same extra-box effect and a rule that requires both to agree before we blast the next cancel cohort."
            ),
            "situation": (
                "Randomized SMS vs holdout on a cancel file. Modest planted lift of +1.8 extra boxes. One "
                "interval recipe can look tight by accident. Finance gets both intervals and a binary ship/hold."
            ),
            "decision": (
                "Send the reactivation SMS to the next week's cancel file only if both lower bounds are above "
                "zero. Otherwise hold, write a different creative, or wait for a larger file. SMS cost is small; "
                "unsubscribes and brand damage are not."
            ),
            "units": (
                "Grain: cancelled subscriber. ATE = extra boxes (SMS minus holdout). Normal interval uses a "
                "two-sample standard error. Bootstrap interval uses the 5th and 95th percentiles."
            ),
            "naive_trap": (
                "Shipping the SMS on a point +1.8, or on whichever interval is narrower. A tight normal "
                "interval that the bootstrap does not confirm is not a finance-ready lifecycle number."
            ),
            "success": (
                "Both 90% intervals exclude 0, both cover +1.8, and the story does not depend on which recipe "
                "we picked. If they disagree, we brief the wider one and do not blast the file."
            ),
            "approach": "Normal interval using the two-sample standard error, and a bootstrap percentile interval. Ship the SMS only if both exclude 0 and both cover the planted truth.",
            "why": "One recipe can look tight on a small cancel file. Two recipes that agree are what we take to finance before a national SMS.",
            "assumptions": "Independent users; 90% intervals; normal interval uses a Welch-style SE.",
            "math": (
                "ATE = Ybar_1 - Ybar_0\n"
                "SE = sqrt( s1^2/n1 + s0^2/n0 )\n"
                "Normal 90%:  ATE ± z_0.95 * SE\n"
                "Bootstrap 90%:  [q_0.05(ATE*), q_0.95(ATE*)]\n"
                "Ship if 0 < both lower bounds and truth is inside both intervals.\n"
                "Planted ATE is +1.8."
            ),
            "read": "If both lower bounds are above 0, ship is allowed on uncertainty grounds. If they disagree (normal tight, bootstrap wide), trust the wider one. Coverage of the planted 1.8 is the lab check that the interval is honest, not just narrow.",
        },
        "deep_learning": {
            "title": "Deep learning causal effect (TARNet-style)",
            "commercial": "First-box discount targeting when the lift is not a straight line",
            "problem": (
                "The extra boxes from a deeper first-box discount are not a straight line in the CRM file. "
                "Recent browsers who paused, or who came from social and have not subscribed, jump a lot. "
                "Current weekly subscribers who click the same '50% off your next box' take a discount they "
                "did not need (near-zero or negative incrementality). A linear T-learner can miss that shape "
                "and mail the discount to the wrong people. The question is whether two small neural nets — "
                "one for discounted outcomes, one for full-price — recover extra boxes given x more faithfully."
            ),
            "situation": (
                "Customer-level features (pause flag, recency, channel, plan size), treatment = deeper first-box "
                "or stay discount, Y = later boxes. True CATE is 0.8 + 2.6 * 1{X1>0} + 0.4 tanh(X2). We compare "
                "a 24-12 ReLU two-head net to a linear Ridge T-learner, without a graphics processor."
            ),
            "decision": (
                "Whether the next first-box / stay-discount file is scored by the neural CATE or by the linear "
                "T-learner. We do not ship a net that loses on PEHE just because it is 'deep,' and we do not "
                "discount loyal weekly subscribers if the net says their extra boxes are near zero."
            ),
            "units": (
                "Grain: prospect or subscriber. mu_d(x) = expected later boxes given X and discount d. "
                "tau_hat(x) = extra boxes. Score is PEHE versus the known tau(x)."
            ),
            "naive_trap": (
                "Assuming extra boxes rise linearly with 'engagement,' or assuming a neural net is better "
                "because it is more flexible. A small cancel file plus a flexible net overfits and can mail "
                "worse than Ridge."
            ),
            "success": (
                "Neural PEHE is lower than linear PEHE, and the neural mean extra-box CATE is still near the "
                "true average. If the net loses, we target with the linear T-learner."
            ),
            "approach": "Standardize CRM features. Fit one multilayer perceptron on discounted customers and one on full-price (TARNet-style two heads). Extra boxes = mu1(x) - mu0(x). Compare PEHE to a linear T-learner.",
            "why": "TARNet-style two-head nets are the practical deep CATE baseline for nonlinear meal-kit offers. We keep the net small so the lab stays reproducible without a GPU.",
            "assumptions": "Unconfoundedness given X; enough data for a 24-12 ReLU net; early stopping.",
            "math": (
                "mu_d(x) ≈ MLP_d(x),   d in {0,1}\n"
                "tau_hat(x) = mu_1(x) - mu_0(x)\n"
                "True tau(x) = 0.8 + 2.6 * 1{x1>0} + 0.4 tanh(x2)\n"
                "PEHE = sqrt( mean_i (tau_hat(X_i) - tau(X_i))^2 )\n"
                "Linear T-learner is the same formula with Ridge instead of MLP."
            ),
            "read": "Compare the two PEHE numbers. Lower is closer to the true individual effects. Neural mean CATE should still sit near the true average. If neural PEHE is worse, the net overfit — fall back to the linear T-learner for targeting.",
        },
    }
    return catalog[method_id]


def _pack(estimate: float, truth: float, passed: bool, gate: str, **extra) -> dict:
    bias = float(estimate - truth)
    metrics = {
        "estimate": float(estimate),
        "true": float(truth),
        "bias": bias,
        "passed": bool(passed),
        "gate": gate,
    }
    metrics.update(extra)
    return {"metrics": metrics}


def _run_did(rng: np.random.Generator, **kwargs) -> dict:
    n_geos = int(kwargs.get("n_geos", 16))
    n_weeks = int(kwargs.get("n_weeks", 60))
    treat_week = 36
    n_treated = 5
    truth = 0.10
    growth = rng.normal(0.002, 0.0012, n_geos)
    level = rng.normal(160.0, 20.0, n_geos)
    treated = np.zeros(n_geos, dtype=int)
    treated[np.argsort(-growth)[:n_treated]] = 1
    y = np.zeros((n_geos, n_weeks))
    for g in range(n_geos):
        for t in range(n_weeks):
            season = 10.0 * np.sin(2 * np.pi * t / 52.0)
            base = level[g] * np.exp(growth[g] * (t + 1)) + season + rng.normal(0, 5.0)
            post = 1 if t >= treat_week else 0
            y[g, t] = base * (1.0 + truth * treated[g] * post)
    pre = slice(0, treat_week)
    post = slice(treat_week, n_weeks)
    t_pre, t_post = y[treated == 1, pre].mean(), y[treated == 1, post].mean()
    c_pre, c_post = y[treated == 0, pre].mean(), y[treated == 0, post].mean()
    estimate = float((t_post / max(t_pre, 1e-6)) / (c_post / max(c_pre, 1e-6)) - 1.0)
    naive = float(t_post / max(t_pre, 1e-6) - 1.0)
    passed = abs(estimate - truth) < abs(naive - truth)
    out = _pack(estimate, truth, passed, "DiD closer to truth than treated-only pre/post")
    out["kpis"] = [
        {"label": "DiD (approx %)", "value": f"{100 * estimate:.1f}%"},
        {"label": "Treated-only pre/post", "value": f"{100 * naive:.1f}%"},
        {"label": "True lift", "value": f"{100 * truth:.1f}%"},
    ]
    out["table"] = {
        "headers": ["Contrast", "Value"],
        "rows": [["True lift", f"{100 * truth:.1f}%"], ["DiD", f"{100 * estimate:.1f}%"], ["Naive pre/post", f"{100 * naive:.1f}%"]],
    }
    out["series"] = {
        "labels": list(range(1, n_weeks + 1)),
        "treated": y[treated == 1].mean(axis=0).tolist(),
        "control": y[treated == 0].mean(axis=0).tolist(),
        "cut": treat_week,
    }
    out["story"] = (
        f"Selected (fast-growth) geos got the burst. Naive pre/post is {100 * naive:.1f}%. "
        f"DiD is {100 * estimate:.1f}% versus true {100 * truth:.1f}%."
    )
    return out


def _run_iv(rng: np.random.Generator, **kwargs) -> dict:
    n = int(kwargs.get("n", 1400))
    truth = -1.20
    demand = rng.normal(0, 0.35, n)
    cost = rng.normal(0, 0.40, n)
    price = 4.0 + 0.85 * cost + 0.55 * demand + rng.normal(0, 0.15, n)
    y = 8.0 + truth * price + 1.4 * demand + rng.normal(0, 0.35, n)
    ols = LinearRegression().fit(price.reshape(-1, 1), y).coef_[0]
    stage1 = LinearRegression().fit(cost.reshape(-1, 1), price)
    price_hat = stage1.predict(cost.reshape(-1, 1))
    iv = LinearRegression().fit(price_hat.reshape(-1, 1), y).coef_[0]
    f_stat = float(
        (np.corrcoef(cost, price)[0, 1] ** 2) * (n - 2) / max(1e-8, 1 - np.corrcoef(cost, price)[0, 1] ** 2)
    )
    passed = abs(iv - truth) < abs(ols - truth) and f_stat > 10
    out = _pack(float(iv), truth, passed, "IV closer to true elasticity than OLS, first-stage F > 10")
    out["kpis"] = [
        {"label": "OLS slope", "value": f"{ols:.2f}"},
        {"label": "IV slope", "value": f"{iv:.2f}"},
        {"label": "True elasticity-style slope", "value": f"{truth:.2f}"},
        {"label": "First-stage F (approx)", "value": f"{f_stat:.1f}"},
    ]
    out["table"] = {
        "headers": ["Estimator", "Price coefficient"],
        "rows": [["Ordinary least squares", f"{ols:.2f}"], ["Two-stage least squares", f"{iv:.2f}"], ["Truth", f"{truth:.2f}"]],
    }
    out["series"] = {"labels": ["OLS", "IV", "Truth"], "values": [float(ols), float(iv), truth]}
    out["story"] = (
        f"Demand shocks move both price and boxes, so OLS is {ols:.2f}. "
        f"Cost-shock IV is {iv:.2f} (true {truth:.2f})."
    )
    return out


def _run_sc(rng: np.random.Generator, **kwargs) -> dict:
    n_donors = 10
    n_pre, n_post = 30, 16
    truth = 18.0
    t_idx = np.arange(n_pre + n_post)
    donors = []
    for _ in range(n_donors):
        level = rng.uniform(80, 140)
        slope = rng.normal(0.15, 0.08)
        series = level + slope * t_idx + 6 * np.sin(2 * np.pi * t_idx / 13.0) + rng.normal(0, 2.2, t_idx.size)
        donors.append(series)
    donors = np.vstack(donors)
    weights_true = rng.dirichlet(np.ones(n_donors))
    treated = weights_true @ donors
    treated[n_pre:] += truth + rng.normal(0, 1.2, n_post)

    y1_pre = treated[:n_pre]
    y0_pre = donors[:, :n_pre]

    def loss(w):
        return float(np.sum((y1_pre - w @ y0_pre) ** 2))

    cons = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
    bounds = [(0.0, 1.0)] * n_donors
    start = np.ones(n_donors) / n_donors
    fit = minimize(loss, start, bounds=bounds, constraints=cons, method="SLSQP")
    w = np.clip(fit.x, 0, None)
    w = w / w.sum()
    synth = w @ donors
    estimate = float((treated[n_pre:] - synth[n_pre:]).mean())
    naive = float(treated[n_pre:].mean() - treated[:n_pre].mean())
    passed = abs(estimate - truth) < abs(naive - truth)
    out = _pack(estimate, truth, passed, "Synthetic-control post gap closer to true additive lift than a simple pre/post")
    out["kpis"] = [
        {"label": "SC post gap", "value": f"{estimate:.1f}"},
        {"label": "Naive pre/post", "value": f"{naive:.1f}"},
        {"label": "True additive lift", "value": f"{truth:.1f}"},
    ]
    out["table"] = {
        "headers": ["Donor", "Weight"],
        "rows": [[f"Donor {i + 1}", f"{wi:.2f}"] for i, wi in enumerate(w) if wi > 0.03],
    }
    out["series"] = {
        "labels": list(range(1, n_pre + n_post + 1)),
        "treated": treated.tolist(),
        "control": synth.tolist(),
        "synthetic": synth.tolist(),
        "cut": n_pre,
    }
    out["story"] = f"Ontario-style single treated series. Synthetic control gap {estimate:.1f} versus true {truth:.1f}."
    return out


def _run_ipw(rng: np.random.Generator, **kwargs) -> dict:
    n = int(kwargs.get("n", 1600))
    truth = 4.5
    x = rng.normal(0, 1, size=(n, 4))
    logit = 0.2 + 0.8 * x[:, 0] + 0.4 * x[:, 1]
    e = 1 / (1 + np.exp(-logit))
    d = rng.binomial(1, e)
    y = 10 + truth * d + 2.2 * x[:, 0] + 1.1 * x[:, 1] + rng.normal(0, 1.4, n)
    naive = y[d == 1].mean() - y[d == 0].mean()
    e_hat = LogisticRegression(max_iter=400).fit(x, d).predict_proba(x)[:, 1]
    e_hat = np.clip(e_hat, 0.05, 0.95)
    ipw = np.mean(d * y / e_hat) - np.mean((1 - d) * y / (1 - e_hat))
    passed = abs(ipw - truth) < abs(naive - truth)
    out = _pack(float(ipw), truth, passed, "IPW ATE closer to truth than the raw taker gap")
    out["kpis"] = [
        {"label": "Naive gap", "value": f"{naive:.2f}"},
        {"label": "IPW ATE", "value": f"{ipw:.2f}"},
        {"label": "True ATE", "value": f"{truth:.2f}"},
    ]
    out["table"] = {
        "headers": ["Estimator", "ATE"],
        "rows": [["Raw taker minus refuser", f"{naive:.2f}"], ["Inverse probability weight", f"{ipw:.2f}"], ["Truth", f"{truth:.2f}"]],
    }
    out["series"] = {"labels": ["Naive", "IPW", "Truth"], "values": [float(naive), float(ipw), truth]}
    out["story"] = f"Engaged customers take the offer. Naive gap {naive:.2f}; IPW {ipw:.2f}; true {truth:.2f}."
    return out


def _run_impact(rng: np.random.Generator, **kwargs) -> dict:
    n_pre, n_post = 52, 16
    truth = 12.0
    t = np.arange(n_pre + n_post)
    y = 100 + 0.15 * t + 8 * np.sin(2 * np.pi * t / 13.0) + rng.normal(0, 2.5, t.size)
    y[n_pre:] += truth
    week = (t % 13).astype(float)
    x_pre = np.column_stack([t[:n_pre], np.sin(2 * np.pi * t[:n_pre] / 13.0), np.cos(2 * np.pi * t[:n_pre] / 13.0)])
    x_all = np.column_stack([t, np.sin(2 * np.pi * t / 13.0), np.cos(2 * np.pi * t / 13.0)])
    model = Ridge(alpha=1.0).fit(x_pre, y[:n_pre])
    yhat = model.predict(x_all)
    estimate = float((y[n_pre:] - yhat[n_pre:]).mean())
    naive = float(y[n_pre:].mean() - y[:n_pre].mean())
    passed = abs(estimate - truth) < abs(naive - truth)
    out = _pack(estimate, truth, passed, "Forecast-gap closer to true national lift than raw pre/post")
    out["kpis"] = [
        {"label": "Causal-impact gap", "value": f"{estimate:.1f}"},
        {"label": "Raw pre/post", "value": f"{naive:.1f}"},
        {"label": "True additive lift", "value": f"{truth:.1f}"},
    ]
    out["table"] = {
        "headers": ["Window", "Actual", "Forecast"],
        "rows": [
            ["Pre mean", f"{y[:n_pre].mean():.1f}", f"{yhat[:n_pre].mean():.1f}"],
            ["Post mean", f"{y[n_pre:].mean():.1f}", f"{yhat[n_pre:].mean():.1f}"],
        ],
    }
    out["series"] = {
        "labels": list(range(1, n_pre + n_post + 1)),
        "actual": y.tolist(),
        "forecast": yhat.tolist(),
        "cut": n_pre,
    }
    _ = week
    out["story"] = f"National series, no control geo. Impact gap {estimate:.1f} versus true {truth:.1f}."
    return out


def _run_dml(rng: np.random.Generator, **kwargs) -> dict:
    n = int(kwargs.get("n", 1800))
    p = 10
    truth = 3.0
    x = rng.normal(0, 1, size=(n, p))
    # Nonlinear-ish propensity and outcome so a misspecified short OLS hurts.
    e = 1 / (1 + np.exp(-(0.3 * x[:, 0] + 0.4 * x[:, 1] ** 2 / 3 + 0.2 * x[:, 2])))
    d = rng.binomial(1, np.clip(e, 0.08, 0.92))
    y = 5 + truth * d + 1.5 * x[:, 0] + 0.8 * x[:, 1] ** 2 / 3 + 0.5 * x[:, 3] + rng.normal(0, 1.2, n)
    naive = y[d == 1].mean() - y[d == 0].mean()
    ols = LinearRegression().fit(np.column_stack([d, x]), y).coef_[0]
    y_res = y - Ridge(alpha=1.0).fit(x, y).predict(x)
    d_res = d - Ridge(alpha=1.0).fit(x, d).predict(x)
    dml = LinearRegression().fit(d_res.reshape(-1, 1), y_res).coef_[0]
    passed = abs(dml - truth) < abs(naive - truth)
    out = _pack(float(dml), truth, passed, "DML ATE closer to truth than the naive gap")
    out["kpis"] = [
        {"label": "Naive", "value": f"{naive:.2f}"},
        {"label": "OLS with X", "value": f"{ols:.2f}"},
        {"label": "DML", "value": f"{dml:.2f}"},
        {"label": "True ATE", "value": f"{truth:.2f}"},
    ]
    out["table"] = {
        "headers": ["Estimator", "ATE"],
        "rows": [["Naive", f"{naive:.2f}"], ["OLS + X", f"{ols:.2f}"], ["Double ML", f"{dml:.2f}"], ["Truth", f"{truth:.2f}"]],
    }
    out["series"] = {"labels": ["Naive", "OLS", "DML", "Truth"], "values": [float(naive), float(ols), float(dml), truth]}
    out["story"] = f"Rich confounders. DML {dml:.2f} versus naive {naive:.2f} (true {truth:.2f})."
    return out


def _run_meta(rng: np.random.Generator, **kwargs) -> dict:
    n = int(kwargs.get("n", 1600))
    x = rng.normal(0, 1, size=(n, 3))
    high = (x[:, 0] > 0).astype(float)
    cate = 1.0 + 3.0 * high
    e = 0.45 + 0.1 * x[:, 1]
    d = rng.binomial(1, np.clip(e, 0.15, 0.85))
    y = 4 + cate * d + 0.6 * x[:, 1] + rng.normal(0, 1.0, n)
    # S-learner
    xs = np.column_stack([x, d])
    s_model = Ridge(alpha=1.0).fit(xs, y)
    s_cate = s_model.predict(np.column_stack([x, np.ones(n)])) - s_model.predict(np.column_stack([x, np.zeros(n)]))
    # T-learner
    t1 = Ridge(alpha=1.0).fit(x[d == 1], y[d == 1])
    t0 = Ridge(alpha=1.0).fit(x[d == 0], y[d == 0])
    t_cate = t1.predict(x) - t0.predict(x)
    # X-learner
    d_hat = LogisticRegression(max_iter=300).fit(x, d).predict_proba(x)[:, 1]
    tau1 = y[d == 1] - t0.predict(x[d == 1])
    tau0 = t1.predict(x[d == 0]) - y[d == 0]
    x1 = Ridge(alpha=1.0).fit(x[d == 1], tau1)
    x0 = Ridge(alpha=1.0).fit(x[d == 0], tau0)
    x_cate = d_hat * x0.predict(x) + (1 - d_hat) * x1.predict(x)
    pehe = {
        "S": float(np.sqrt(np.mean((s_cate - cate) ** 2))),
        "T": float(np.sqrt(np.mean((t_cate - cate) ** 2))),
        "X": float(np.sqrt(np.mean((x_cate - cate) ** 2))),
    }
    best = min(pehe, key=pehe.get)
    estimate = float(np.mean({"S": s_cate, "T": t_cate, "X": x_cate}[best]))
    truth = float(cate.mean())
    seg_true = float(cate[high == 1].mean() - cate[high == 0].mean())
    seg_hat = float(t_cate[high == 1].mean() - t_cate[high == 0].mean())
    passed = pehe[best] < 1.6 and abs(seg_hat - seg_true) < 1.2
    out = _pack(estimate, truth, passed, "Best meta-learner PEHE under 1.6 and segment gap recovered")
    out["kpis"] = [
        {"label": "True mean CATE", "value": f"{truth:.2f}"},
        {"label": f"{best}-learner mean", "value": f"{estimate:.2f}"},
        {"label": "T-learner PEHE", "value": f"{pehe['T']:.2f}"},
        {"label": "X-learner PEHE", "value": f"{pehe['X']:.2f}"},
    ]
    out["table"] = {
        "headers": ["Learner", "Mean CATE", "PEHE"],
        "rows": [
            ["S", f"{s_cate.mean():.2f}", f"{pehe['S']:.2f}"],
            ["T", f"{t_cate.mean():.2f}", f"{pehe['T']:.2f}"],
            ["X", f"{x_cate.mean():.2f}", f"{pehe['X']:.2f}"],
            ["Truth", f"{truth:.2f}", "0"],
        ],
    }
    out["series"] = {"labels": ["S PEHE", "T PEHE", "X PEHE"], "values": [pehe["S"], pehe["T"], pehe["X"]]}
    out["story"] = (
        f"High-tenure segment has a larger effect. Best learner is {best} "
        f"(PEHE {pehe[best]:.2f}). T-learner segment gap {seg_hat:.2f} vs true {seg_true:.2f}."
    )
    return out


def _factorial(rng: np.random.Generator, n: int = 2400):
    a = rng.integers(0, 2, n)
    b = rng.integers(0, 2, n)
    truth_a, truth_b, truth_ab = 3.0, 5.0, 1.2
    y = 20 + truth_a * a + truth_b * b + truth_ab * a * b + rng.normal(0, 4.0, n)
    return a, b, y, truth_a, truth_b, truth_ab


def _run_ab(rng: np.random.Generator, **kwargs) -> dict:
    a, b, y, ta, tb, tab = _factorial(rng, int(kwargs.get("n", 2400)))
    cells = {}
    for ia in (0, 1):
        for ib in (0, 1):
            cells[f"A{ia}B{ib}"] = float(y[(a == ia) & (b == ib)].mean())
    est_a = 0.5 * ((cells["A1B0"] - cells["A0B0"]) + (cells["A1B1"] - cells["A0B1"]))
    est_b = 0.5 * ((cells["A0B1"] - cells["A0B0"]) + (cells["A1B1"] - cells["A1B0"]))
    est_ab = (cells["A1B1"] - cells["A1B0"]) - (cells["A0B1"] - cells["A0B0"])
    passed = abs(est_a - ta) < 0.8 and abs(est_b - tb) < 0.8
    out = _pack(est_a, ta, passed, "Main effects recovered within 0.8 of truth")
    out["metrics"]["estimate_b"] = est_b
    out["metrics"]["estimate_ab"] = est_ab
    out["kpis"] = [
        {"label": "Badge main effect", "value": f"{est_a:.2f} (true {ta:.1f})"},
        {"label": "Shipping main effect", "value": f"{est_b:.2f} (true {tb:.1f})"},
        {"label": "Interaction", "value": f"{est_ab:.2f} (true {tab:.1f})"},
    ]
    out["table"] = {
        "headers": ["Cell", "Mean conversion-like score"],
        "rows": [[name, f"{val:.2f}"] for name, val in cells.items()],
    }
    out["series"] = {"labels": list(cells), "values": list(cells.values())}
    out["story"] = (
        f"2-by-2 site test. Badge {est_a:.2f}, shipping {est_b:.2f}, interaction {est_ab:.2f}."
    )
    return out


def _run_bootstrap(rng: np.random.Generator, **kwargs) -> dict:
    n = int(kwargs.get("n", 1600))
    n_boot = 280
    truth = 2.4
    d = rng.integers(0, 2, n)
    y = 10 + truth * d + rng.normal(0, 3.2, n)
    ate = y[d == 1].mean() - y[d == 0].mean()
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yy, dd = y[idx], d[idx]
        if dd.min() == dd.max():
            continue
        boots.append(yy[dd == 1].mean() - yy[dd == 0].mean())
    boots = np.array(boots)
    lo, hi = np.quantile(boots, [0.05, 0.95])
    passed = lo <= truth <= hi and lo > 0
    out = _pack(float(ate), truth, passed, "90% bootstrap interval covers truth and excludes zero")
    out["metrics"]["ci_low"] = float(lo)
    out["metrics"]["ci_high"] = float(hi)
    out["kpis"] = [
        {"label": "ATE", "value": f"{ate:.2f}"},
        {"label": "90% bootstrap CI", "value": f"[{lo:.2f}, {hi:.2f}]"},
        {"label": "True ATE", "value": f"{truth:.2f}"},
    ]
    out["table"] = {
        "headers": ["Quantity", "Value"],
        "rows": [["Draws", str(len(boots))], ["Percentile 5", f"{lo:.2f}"], ["Percentile 95", f"{hi:.2f}"]],
    }
    hist, edges = np.histogram(boots, bins=16)
    out["series"] = {"labels": [f"{edges[i]:.1f}" for i in range(len(hist))], "values": hist.astype(float).tolist()}
    out["story"] = f"Resampled ATE {ate:.2f} with 90% interval [{lo:.2f}, {hi:.2f}]."
    return out


def _run_hypothesis(rng: np.random.Generator, **kwargs) -> dict:
    a, b, y, ta, tb, _tab = _factorial(rng, int(kwargs.get("n", 2000)))
    badge = y[a == 1]
    none = y[a == 0]
    t_stat, p_t = stats.ttest_ind(badge, none, equal_var=False)
    groups = [y[(a == ia) & (b == ib)] for ia in (0, 1) for ib in (0, 1)]
    f_stat, p_a = stats.f_oneway(*groups)
    passed = p_t < 0.05 and p_a < 0.05
    estimate = float(badge.mean() - none.mean())
    out = _pack(estimate, ta, passed, "t-test and ANOVA both reject the null at 5%")
    out["metrics"]["p_ttest"] = float(p_t)
    out["metrics"]["p_anova"] = float(p_a)
    out["kpis"] = [
        {"label": "t statistic", "value": f"{float(t_stat):.2f}"},
        {"label": "t-test p-value", "value": f"{p_t:.4f}"},
        {"label": "ANOVA F", "value": f"{float(f_stat):.2f}"},
        {"label": "ANOVA p-value", "value": f"{p_a:.4f}"},
    ]
    out["table"] = {
        "headers": ["Test", "Null", "p-value"],
        "rows": [
            ["Welch t-test", "Badge mean = control mean", f"{p_t:.4f}"],
            ["One-way ANOVA", "All four cell means equal", f"{p_a:.4f}"],
        ],
    }
    out["series"] = {
        "labels": ["A0B0", "A0B1", "A1B0", "A1B1"],
        "values": [float(g.mean()) for g in groups],
    }
    out["story"] = f"Badge contrast p={p_t:.4f}; four-cell ANOVA p={p_a:.4f}."
    return out


def _run_uncertainty(rng: np.random.Generator, **kwargs) -> dict:
    n = int(kwargs.get("n", 1400))
    truth = 1.8
    d = rng.integers(0, 2, n)
    y = 8 + truth * d + rng.normal(0, 2.8, n)
    ate = y[d == 1].mean() - y[d == 0].mean()
    s1, s0 = y[d == 1].std(ddof=1), y[d == 0].std(ddof=1)
    n1, n0 = (d == 1).sum(), (d == 0).sum()
    se = float(np.sqrt(s1**2 / n1 + s0**2 / n0))
    z = stats.norm.ppf(0.95)
    nlo, nhi = ate - z * se, ate + z * se
    boots = []
    for _ in range(240):
        idx = rng.integers(0, n, n)
        yy, dd = y[idx], d[idx]
        if dd.min() == dd.max():
            continue
        boots.append(yy[dd == 1].mean() - yy[dd == 0].mean())
    blo, bhi = np.quantile(boots, [0.05, 0.95])
    covers = (nlo <= truth <= nhi) and (blo <= truth <= bhi)
    excludes0 = nlo > 0 and blo > 0
    passed = bool(covers and excludes0)
    out = _pack(float(ate), truth, passed, "Both 90% intervals cover truth and exclude zero")
    out["metrics"]["normal_ci"] = [float(nlo), float(nhi)]
    out["metrics"]["boot_ci"] = [float(blo), float(bhi)]
    out["kpis"] = [
        {"label": "ATE", "value": f"{ate:.2f}"},
        {"label": "Normal 90% CI", "value": f"[{nlo:.2f}, {nhi:.2f}]"},
        {"label": "Bootstrap 90% CI", "value": f"[{blo:.2f}, {bhi:.2f}]"},
        {"label": "SE", "value": f"{se:.2f}"},
    ]
    out["table"] = {
        "headers": ["Recipe", "Low", "High"],
        "rows": [["Normal", f"{nlo:.2f}", f"{nhi:.2f}"], ["Bootstrap", f"{blo:.2f}", f"{bhi:.2f}"]],
    }
    out["series"] = {"labels": ["ATE", "True"], "values": [float(ate), truth]}
    out["story"] = f"Ship only if both intervals exclude 0. ATE {ate:.2f}; SE {se:.2f}."
    return out


def _run_deep(rng: np.random.Generator, **kwargs) -> dict:
    n = int(kwargs.get("n", 1400))
    x = rng.normal(0, 1, size=(n, 4))
    high = (x[:, 0] > 0).astype(float)
    cate = 0.8 + 2.6 * high + 0.4 * np.tanh(x[:, 1])
    d = rng.binomial(1, 0.5, n)
    y = 3 + cate * d + 0.5 * x[:, 2] + rng.normal(0, 0.9, n)
    scaler = StandardScaler()
    xs = scaler.fit_transform(x)
    lin1 = Ridge(alpha=1.0).fit(xs[d == 1], y[d == 1])
    lin0 = Ridge(alpha=1.0).fit(xs[d == 0], y[d == 0])
    lin_cate = lin1.predict(xs) - lin0.predict(xs)
    net_kw = dict(hidden_layer_sizes=(24, 12), activation="relu", max_iter=400, random_state=0, early_stopping=True)
    mlp1 = MLPRegressor(**net_kw).fit(xs[d == 1], y[d == 1])
    mlp0 = MLPRegressor(**net_kw).fit(xs[d == 0], y[d == 0])
    deep_cate = mlp1.predict(xs) - mlp0.predict(xs)
    pehe_lin = float(np.sqrt(np.mean((lin_cate - cate) ** 2)))
    pehe_deep = float(np.sqrt(np.mean((deep_cate - cate) ** 2)))
    estimate = float(deep_cate.mean())
    truth = float(cate.mean())
    passed = pehe_deep <= pehe_lin + 0.15
    out = _pack(estimate, truth, passed, "Neural T-learner PEHE not worse than linear T-learner by more than 0.15")
    out["metrics"]["pehe_linear"] = pehe_lin
    out["metrics"]["pehe_deep"] = pehe_deep
    out["kpis"] = [
        {"label": "Neural mean CATE", "value": f"{estimate:.2f}"},
        {"label": "True mean CATE", "value": f"{truth:.2f}"},
        {"label": "Linear PEHE", "value": f"{pehe_lin:.2f}"},
        {"label": "Neural PEHE", "value": f"{pehe_deep:.2f}"},
    ]
    out["table"] = {
        "headers": ["Model", "Mean CATE", "PEHE"],
        "rows": [
            ["Linear T-learner", f"{lin_cate.mean():.2f}", f"{pehe_lin:.2f}"],
            ["Neural T-learner (TARNet-style heads)", f"{estimate:.2f}", f"{pehe_deep:.2f}"],
            ["Truth", f"{truth:.2f}", "0"],
        ],
    }
    out["series"] = {"labels": ["Linear PEHE", "Neural PEHE"], "values": [pehe_lin, pehe_deep]}
    out["story"] = (
        f"Two small multilayer perceptrons estimate treated and control outcomes. "
        f"Neural PEHE {pehe_deep:.2f} versus linear {pehe_lin:.2f}."
    )
    return out
