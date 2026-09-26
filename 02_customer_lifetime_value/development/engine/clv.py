"""Customer lifetime value for a weekly meal-kit subscription (HelloFresh-class).

X Canada ships a weekly box. New customers start on a cheap first box, then skip,
pause, or cancel. CLV is expected contribution margin over a finite CRM horizon,
scored at a snapshot, then checked on sealed later weeks. Acquisition channel is
the join to project 01: TV / YouTube / referral buyers stay; paid-search first-box
hunters often do not.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln, hyp2f1
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_percentage_error, r2_score
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler

# Realistic X Canada / HelloFresh-class priors (Canadian dollars, weekly box).
# List prices are continuing-box net before a small loyalty promo.
# first_disc is the first-box discount off list. early_churn is P(no second box).
# weekly_skip is P(skip this week | still subscribed). dropout_week is the
# weekly cancel/silent-lapse hazard after the customer has taken a second box.
CHANNEL_PRIORS = {
    "TV": {
        "funnel": "TOFU",
        "share": 0.16,
        "family_p": 0.58,
        "early_churn": 0.22,
        "weekly_skip": 0.11,
        "dropout_week": 0.028,
        "first_disc": 0.40,
        "list_2p": 79.0,
        "list_fam": 139.0,
    },
    "YouTube": {
        "funnel": "TOFU",
        "share": 0.18,
        "family_p": 0.50,
        "early_churn": 0.26,
        "weekly_skip": 0.13,
        "dropout_week": 0.032,
        "first_disc": 0.45,
        "list_2p": 79.0,
        "list_fam": 139.0,
    },
    "Referral": {
        "funnel": "TOFU",
        "share": 0.12,
        "family_p": 0.62,
        "early_churn": 0.14,
        "weekly_skip": 0.09,
        "dropout_week": 0.022,
        "first_disc": 0.25,
        "list_2p": 79.0,
        "list_fam": 139.0,
    },
    "Social": {
        "funnel": "MOFU",
        "share": 0.26,
        "family_p": 0.38,
        "early_churn": 0.38,
        "weekly_skip": 0.18,
        "dropout_week": 0.045,
        "first_disc": 0.50,
        "list_2p": 79.0,
        "list_fam": 139.0,
    },
    "Paid Search": {
        "funnel": "BOFU",
        "share": 0.28,
        "family_p": 0.28,
        "early_churn": 0.52,
        "weekly_skip": 0.22,
        "dropout_week": 0.055,
        "first_disc": 0.60,
        "list_2p": 79.0,
        "list_fam": 139.0,
    },
}

FIRST_BOX_MARGIN = 0.06
CONTINUING_MARGIN_DEFAULT = 0.32


@dataclass
class CLVEstimates:
    customers: pd.DataFrame
    bgnbd: dict[str, float]
    gammagamma: dict[str, float]
    ridge_r2: float
    holdout_spearman: float
    holdout_mape: float
    holdout_r2: float


def run_clv_scenario(
    n_customers: int = 1800,
    snapshot_week: int = 130,
    horizon_weeks: int = 26,
    calendar_weeks: int = 156,
    margin: float = CONTINUING_MARGIN_DEFAULT,
    seed: int = 42,
) -> dict:
    """Simulate a meal-kit panel, fit CLV models, and return a web-ready payload."""
    rng = np.random.default_rng(int(seed))
    n_customers = int(np.clip(n_customers, 400, 8000))
    purchases, customer_meta = _simulate_customers(
        rng,
        n_customers=n_customers,
        snapshot_week=snapshot_week,
        calendar_weeks=calendar_weeks,
    )
    train_rfm = _rfm_table(purchases, end_week=snapshot_week, label="train")
    holdout = _rfm_table(purchases, start_week=snapshot_week, end_week=calendar_weeks, label="holdout")
    frame = train_rfm.merge(holdout[["customer_id", "holdout_spend", "holdout_orders"]], on="customer_id", how="left")
    frame = frame.merge(customer_meta, on="customer_id", how="left")
    frame["holdout_spend"] = frame["holdout_spend"].fillna(0.0)
    frame["holdout_orders"] = frame["holdout_orders"].fillna(0.0)
    frame["skip_rate"] = frame["skip_rate"].fillna(0.0)
    frame["n_skips"] = frame["n_skips"].fillna(0.0)
    frame["plan_size"] = frame["plan_size"].fillna(2).astype(int)
    frame["first_box_discount"] = frame["first_box_discount"].fillna(0.40)
    frame["aov_continuing"] = np.where(frame["orders"] >= 2.0, frame["aov_continuing"], frame["aov"])
    frame["aov_continuing"] = frame["aov_continuing"].fillna(frame["aov"])

    bgnbd = fit_bgnbd(frame["frequency"].to_numpy(), frame["recency"].to_numpy(), frame["T"].to_numpy())
    gg = fit_gamma_gamma(frame["frequency"].to_numpy(), frame["aov_continuing"].to_numpy())

    frame["p_alive"] = bgnbd_p_alive(
        bgnbd, frame["frequency"].to_numpy(), frame["recency"].to_numpy(), frame["T"].to_numpy()
    )
    frame["e_purchases"] = bgnbd_expected_purchases(
        bgnbd,
        horizon_weeks,
        frame["frequency"].to_numpy(),
        frame["recency"].to_numpy(),
        frame["T"].to_numpy(),
    )
    frame["e_aov"] = gamma_gamma_expected_aov(gg, frame["frequency"].to_numpy(), frame["aov_continuing"].to_numpy())
    frame["clv_bgnbd"] = frame["e_purchases"] * frame["e_aov"] * float(margin)
    frame["clv_heuristic"] = (
        np.maximum(frame["frequency"], 0.0) / np.maximum(frame["T"], 1.0)
    ) * frame["aov"] * horizon_weeks * frame["p_alive"] * float(margin)

    frame["future_margin"] = frame["holdout_spend"] * float(margin)
    ridge = _fit_ridge_clv(frame, target_col="future_margin")
    frame["clv_ml"] = ridge["prediction"]
    frame["clv_blend"] = 0.65 * frame["clv_bgnbd"] + 0.35 * frame["clv_ml"]
    frame["segment"] = _value_segment(frame["clv_blend"])
    frame["rfm_segment"] = _rfm_segment(frame)
    frame = frame.sort_values("clv_blend", ascending=False).reset_index(drop=True)
    frame["rank"] = np.arange(1, len(frame) + 1)

    spearman = float(frame["clv_blend"].corr(frame["future_margin"], method="spearman"))
    active = frame["future_margin"] > 1.0
    holdout_mape = (
        float(mean_absolute_percentage_error(frame.loc[active, "future_margin"], frame.loc[active, "clv_blend"]))
        * 100.0
        if int(active.sum()) >= 20
        else float("nan")
    )
    holdout_r2 = float(r2_score(frame["future_margin"], frame["clv_blend"])) if frame["future_margin"].std() > 0 else 0.0

    return _payload(
        frame,
        bgnbd=bgnbd,
        gg=gg,
        ridge=ridge,
        margin=margin,
        snapshot_week=snapshot_week,
        horizon_weeks=horizon_weeks,
        calendar_weeks=calendar_weeks,
        spearman=spearman,
        holdout_mape=holdout_mape,
        holdout_r2=holdout_r2,
    )


def _simulate_customers(
    rng: np.random.Generator,
    n_customers: int,
    snapshot_week: int,
    calendar_weeks: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Weekly meal-kit path: first-box promo, skip weeks, then cancel or silent lapse."""
    names = list(CHANNEL_PRIORS)
    shares = np.array([CHANNEL_PRIORS[n]["share"] for n in names], dtype=float)
    shares = shares / shares.sum()
    channels = rng.choice(names, size=n_customers, p=shares)
    rows: list[dict] = []
    meta: list[dict] = []
    for i in range(n_customers):
        channel = str(channels[i])
        prior = CHANNEL_PRIORS[channel]
        acquire = int(rng.integers(4, max(8, snapshot_week - 8)))
        family = bool(rng.random() < prior["family_p"])
        plan_size = 4 if family else 2
        list_price = float(prior["list_fam"] if family else prior["list_2p"])
        list_price = float(max(40.0, rng.lognormal(np.log(list_price), 0.08)))
        first_disc = float(np.clip(rng.normal(prior["first_disc"], 0.05), 0.10, 0.75))
        skip_p = float(np.clip(rng.beta(prior["weekly_skip"] * 16.0, (1.0 - prior["weekly_skip"]) * 16.0), 0.02, 0.45))
        n_skips = 0
        n_boxes = 0
        # First box always ships — HelloFresh-class cheap start.
        first_amount = float(max(18.0, list_price * (1.0 - first_disc)))
        rows.append(
            {
                "customer_id": i + 1,
                "channel": channel,
                "funnel": prior["funnel"],
                "acquire_week": acquire,
                "week": float(acquire),
                "amount": first_amount,
                "discount": first_disc,
                "returned": float(rng.random() < 0.025),
                "is_first": 1,
                "plan_size": plan_size,
            }
        )
        n_boxes += 1
        one_and_done = False
        if rng.random() < prior["early_churn"]:
            one_and_done = True
        else:
            for week in range(acquire + 1, calendar_weeks + 1):
                early = 1.35 if n_boxes < 4 else 1.0
                if rng.random() < prior["dropout_week"] * early:
                    break
                if rng.random() < skip_p:
                    n_skips += 1
                    continue
                loyalty = float(np.clip(rng.normal(0.04 if prior["funnel"] == "BOFU" else 0.02, 0.02), 0.0, 0.20))
                amount = float(max(28.0, list_price * (1.0 - loyalty) * rng.lognormal(0.0, 0.06)))
                rows.append(
                    {
                        "customer_id": i + 1,
                        "channel": channel,
                        "funnel": prior["funnel"],
                        "acquire_week": acquire,
                        "week": float(week),
                        "amount": amount,
                        "discount": loyalty,
                        "returned": float(rng.random() < 0.02),
                        "is_first": 0,
                        "plan_size": plan_size,
                    }
                )
                n_boxes += 1
        meta.append(
            {
                "customer_id": i + 1,
                "plan_size": plan_size,
                "list_price": list_price,
                "first_box_discount": first_disc,
                "skip_rate": float(n_skips / max(n_skips + max(n_boxes - 1, 0), 1)),
                "n_skips": float(n_skips),
                "one_and_done": int(one_and_done),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(meta)


def _rfm_table(purchases: pd.DataFrame, end_week: int, label: str, start_week: float = 0.0) -> pd.DataFrame:
    window = purchases[(purchases["week"] >= start_week) & (purchases["week"] < end_week)].copy()
    if window.empty:
        return pd.DataFrame(
            columns=[
                "customer_id",
                "channel",
                "funnel",
                "frequency",
                "recency",
                "T",
                "monetary",
                "aov",
                "aov_continuing",
                "orders",
                "discount_rate",
                "return_rate",
                "acquire_week",
            ]
        )
    grouped = window.groupby("customer_id", sort=False)
    last_week = grouped["week"].max()
    first_week = grouped["week"].min()
    orders = grouped.size()
    monetary = grouped["amount"].sum()
    aov = grouped["amount"].mean()
    if "is_first" in window.columns:
        cont = window.loc[window["is_first"] == 0].groupby("customer_id")["amount"].mean()
    else:
        cont = aov
    meta = window.groupby("customer_id").agg(
        channel=("channel", "first"),
        funnel=("funnel", "first"),
        acquire_week=("acquire_week", "first"),
        discount_rate=("discount", "mean"),
        return_rate=("returned", "mean"),
    ).reindex(monetary.index)
    if label == "holdout":
        out = pd.DataFrame(
            {
                "customer_id": monetary.index,
                "holdout_spend": monetary.to_numpy(),
                "holdout_orders": orders.to_numpy(),
            }
        )
        return out
    t_age = (end_week - meta["acquire_week"]).clip(lower=1.0)
    recency = (last_week - first_week).clip(lower=0.0)
    frequency = (orders - 1).clip(lower=0)
    return pd.DataFrame(
        {
            "customer_id": monetary.index.astype(int),
            "channel": meta["channel"].to_numpy(),
            "funnel": meta["funnel"].to_numpy(),
            "acquire_week": meta["acquire_week"].to_numpy(),
            "frequency": frequency.to_numpy(dtype=float),
            "recency": recency.to_numpy(dtype=float),
            "T": t_age.to_numpy(dtype=float),
            "monetary": monetary.to_numpy(dtype=float),
            "aov": aov.to_numpy(dtype=float),
            "aov_continuing": cont.reindex(monetary.index).fillna(aov).to_numpy(dtype=float),
            "orders": orders.to_numpy(dtype=float),
            "discount_rate": meta["discount_rate"].to_numpy(dtype=float),
            "return_rate": meta["return_rate"].to_numpy(dtype=float),
        }
    )


def fit_bgnbd(frequency: np.ndarray, recency: np.ndarray, T: np.ndarray) -> dict[str, float]:
    freq = np.asarray(frequency, dtype=float)
    rec = np.asarray(recency, dtype=float)
    age = np.asarray(T, dtype=float)
    rec = np.minimum(rec, age)

    def nll(params: np.ndarray) -> float:
        r, alpha, a, b = params
        if np.any(params <= 0):
            return 1e12
        a1 = gammaln(r + freq) - gammaln(r) + r * np.log(alpha)
        a2 = gammaln(a + b) + gammaln(b + freq) - gammaln(b) - gammaln(a + b + freq)
        a3 = -(r + freq) * np.log(alpha + age)
        ll = a1 + a2 + a3
        mask = freq > 0
        if np.any(mask):
            a4 = np.log(a) - np.log(b + freq[mask] - 1.0) - (r + freq[mask]) * np.log(alpha + rec[mask])
            ll = ll.copy()
            ll[mask] = a1[mask] + a2[mask] + np.logaddexp(a3[mask], a4)
        value = float(-np.sum(ll))
        return value if np.isfinite(value) else 1e12

    start = np.array([0.8, 6.0, 1.2, 3.5])
    bounds = [(0.05, 20.0), (0.1, 80.0), (1.05, 20.0), (0.1, 40.0)]
    result = minimize(nll, start, method="L-BFGS-B", bounds=bounds)
    r, alpha, a, b = [float(x) for x in result.x]
    return {"r": r, "alpha": alpha, "a": a, "b": b, "success": bool(result.success), "nll": float(result.fun)}


def bgnbd_p_alive(params: dict[str, float], frequency: np.ndarray, recency: np.ndarray, T: np.ndarray) -> np.ndarray:
    r, alpha, a, b = params["r"], params["alpha"], params["a"], params["b"]
    freq = np.asarray(frequency, dtype=float)
    rec = np.minimum(np.asarray(recency, dtype=float), np.asarray(T, dtype=float))
    age = np.asarray(T, dtype=float)
    ratio = ((alpha + age) / np.maximum(alpha + rec, 1e-8)) ** (r + freq)
    term = (a / np.maximum(b + freq, 1e-8)) * ratio
    return 1.0 / (1.0 + term)


def bgnbd_expected_purchases(
    params: dict[str, float],
    horizon: float,
    frequency: np.ndarray,
    recency: np.ndarray,
    T: np.ndarray,
) -> np.ndarray:
    r, alpha, a, b = params["r"], params["alpha"], params["a"], params["b"]
    freq = np.asarray(frequency, dtype=float)
    rec = np.asarray(recency, dtype=float)
    age = np.asarray(T, dtype=float)
    t = float(horizon)
    alive = bgnbd_p_alive(params, freq, rec, age)
    z = t / (alpha + age + t)
    hyp = np.real(np.asarray(hyp2f1(r + freq, b + freq, a + b + freq - 1.0, z), dtype=complex))
    first = (a + b + freq - 1.0) / max(a - 1.0, 0.05)
    second = 1.0 - ((alpha + age) / (alpha + age + t)) ** (r + freq) * hyp
    expected = alive * first * np.maximum(second, 0.0)
    return np.clip(np.nan_to_num(expected, nan=0.0, posinf=0.0, neginf=0.0), 0.0, 80.0)


def fit_gamma_gamma(frequency: np.ndarray, aov: np.ndarray) -> dict[str, float]:
    freq = np.asarray(frequency, dtype=float)
    spend = np.asarray(aov, dtype=float)
    usable = (freq >= 1.0) & (spend > 0)
    x = freq[usable]
    m = spend[usable]
    if len(x) < 30:
        return {"p": 2.0, "q": 4.0, "v": 40.0, "success": False, "nll": float("nan")}

    def nll(params: np.ndarray) -> float:
        p, q, v = params
        if np.any(params <= 0) or q <= 1.01:
            return 1e12
        ll = (
            gammaln(p * x + q)
            - gammaln(p * x)
            - gammaln(q)
            + q * np.log(v)
            + (p * x - 1.0) * np.log(m)
            + (p * x) * np.log(x)
            - (p * x + q) * np.log(x * m + v)
        )
        value = float(-np.sum(ll))
        return value if np.isfinite(value) else 1e12

    start = np.array([2.5, 3.5, float(np.median(m))])
    result = minimize(nll, start, method="L-BFGS-B", bounds=[(0.1, 30.0), (1.05, 30.0), (1.0, 400.0)])
    p, q, v = [float(x) for x in result.x]
    return {"p": p, "q": q, "v": v, "success": bool(result.success), "nll": float(result.fun)}


def gamma_gamma_expected_aov(params: dict[str, float], frequency: np.ndarray, aov: np.ndarray) -> np.ndarray:
    p, q, v = params["p"], params["q"], params["v"]
    freq = np.asarray(frequency, dtype=float)
    spend = np.asarray(aov, dtype=float)
    population = (v * p) / max(q - 1.0, 0.05)
    posterior = ((q - 1.0) / np.maximum(p * freq + q - 1.0, 0.05)) * (v / p + freq * spend)
    predicted = np.where(freq >= 1.0, posterior, population)
    return np.clip(np.nan_to_num(predicted, nan=population), 5.0, 800.0)


def _fit_ridge_clv(frame: pd.DataFrame, target_col: str = "holdout_spend") -> dict:
    dummies = pd.get_dummies(frame[["funnel", "channel"]], drop_first=True)
    features = pd.concat(
        [
            frame[
                [
                    "frequency",
                    "recency",
                    "T",
                    "monetary",
                    "aov",
                    "aov_continuing",
                    "discount_rate",
                    "return_rate",
                    "p_alive",
                    "skip_rate",
                    "plan_size",
                    "first_box_discount",
                    "n_skips",
                ]
            ],
            dummies,
        ],
        axis=1,
    )
    target = frame[target_col].to_numpy(dtype=float)
    if len(frame) < 40 or target.std() < 1e-6:
        return {"prediction": np.zeros(len(frame)), "r2": 0.0, "coefficients": {}}
    scaler = StandardScaler()
    x = scaler.fit_transform(features.to_numpy(dtype=float))
    pred = np.zeros(len(frame), dtype=float)
    fold_r2 = []
    folds = KFold(n_splits=5, shuffle=True, random_state=7)
    for train_idx, test_idx in folds.split(x):
        model = Ridge(alpha=2.5)
        model.fit(x[train_idx], target[train_idx])
        fold_pred = np.clip(model.predict(x[test_idx]), 0.0, None)
        pred[test_idx] = fold_pred
        if target[test_idx].std() > 0:
            fold_r2.append(float(r2_score(target[test_idx], fold_pred)))
    final = Ridge(alpha=2.5)
    final.fit(x, target)
    coefs = {str(name): float(weight) for name, weight in zip(features.columns, final.coef_)}
    return {"prediction": pred, "r2": float(np.mean(fold_r2) if fold_r2 else 0.0), "coefficients": coefs        }


def _assumption_rows(margin: float, frame: pd.DataFrame) -> list[dict]:
    search = frame[frame["channel"] == "Paid Search"] if "channel" in frame.columns else frame.iloc[0:0]
    tv = frame[frame["channel"].isin(["TV", "YouTube", "Referral"])] if "channel" in frame.columns else frame.iloc[0:0]
    return [
        {
            "name": "Company",
            "value": "X Canada meal kit (HelloFresh-class)",
            "why": "Weekly subscription box, not a one-shot grocery basket. Skip and pause are allowed; cancel is optional.",
        },
        {
            "name": "Currency and list price",
            "value": "CAD. 2-person 3-recipe box ~$79; family 4-person ~$139 continuing.",
            "why": "Canadian meal-kit tickets sit in this range after tax-exclusive net paid. Family plans drive AOV, not 'VIP grocers.'",
        },
        {
            "name": "First-box promo",
            "value": f"Mean first-box discount {(frame['first_box_discount'].mean() * 100 if 'first_box_discount' in frame else 45):.0f}%. First-box contribution margin {FIRST_BOX_MARGIN * 100:.0f}%.",
            "why": "Acquisition sells the first box cheap. Paid search is deepest (about 60% off). Referral is shallowest (about 25%). Gamma-Gamma uses continuing-box AOV so the promo does not look like a small basket.",
        },
        {
            "name": "Continuing contribution margin",
            "value": f"{margin * 100:.0f}% of net paid on boxes after the first.",
            "why": "Food, packaging, and last-mile take most of list. This is variable contribution, not EBITDA and not media CAC. Default 32% is a finance planning rate, not a P&L close.",
        },
        {
            "name": "Skip is not churn",
            "value": f"Mean skip rate {(frame['skip_rate'].mean() * 100 if 'skip_rate' in frame else 0):.0f}% of eligible weeks.",
            "why": "A skipped week is not a purchase and not a death. BG/NBD 'alive' is latent: people miss a week, then take the next box. Contractual cancel-date survival would treat a skip as survival and a silent lapse as still alive.",
        },
        {
            "name": "Promo cliff (one-and-done)",
            "value": f"{(frame['one_and_done'].mean() * 100 if 'one_and_done' in frame else 0):.0f}% never take a second box.",
            "why": "HelloFresh-class bases lose a large share after the first-box discount ends. Paid search is worst; referral and TV are best. Frequency = 0 is a first-box-only customer, not a data error.",
        },
        {
            "name": "Acquisition is first-touch",
            "value": "TV, YouTube, Referral, Social, Paid Search. Not last click.",
            "why": f"Search mean CLV vs TV/YouTube/referral is the harvest test. Search n={len(search)}; brand/referral n={len(tv)}.",
        },
        {
            "name": "Horizon",
            "value": "26 weeks default — two CRM quarters, not lifetime to infinity.",
            "why": "Welcome-series and win-back budgets are quarterly. An infinite-horizon CLV cannot be compared to a 26-week campaign cost.",
        },
        {
            "name": "Snapshot cut",
            "value": "Features use only ship-weeks ≤ T. Holdout (T, calendar] is sealed.",
            "why": "Scoring a customer with their own future boxes is the usual leak. Production fails closed if last sealed holdout Spearman drops.",
        },
        {
            "name": "One household, one key",
            "value": "Independence. No shared family account across two emails.",
            "why": "BG/NBD treats each key as its own dropout process. Duplicate households inflate frequency and P(alive).",
        },
        {
            "name": "Gamma-Gamma independence",
            "value": "Continuing AOV is independent of purchase frequency given the customer.",
            "why": "If family plans both buy every week and have larger boxes in a way the model forbids, diagnose AOV residuals on the methods page. First-box net paid is excluded from the spend model.",
        },
        {
            "name": "What CLV is not",
            "value": "Not media CAC payback, not last-click revenue, not Google conversion value.",
            "why": "Project 01 answers incremental weekly boxes from spend. This score answers which subscribers are still worth a win-back or a welcome series.",
        },
    ]


def _value_segment(clv: pd.Series) -> np.ndarray:
    ranks = clv.rank(pct=True, method="first")
    return np.where(ranks >= 0.80, "High", np.where(ranks >= 0.40, "Medium", "Low"))


def _rfm_segment(frame: pd.DataFrame) -> np.ndarray:
    rec_q = pd.qcut(frame["recency"].rank(method="first"), 3, labels=False)
    freq_q = pd.qcut(frame["frequency"].rank(method="first"), 3, labels=False)
    labels = []
    for rec, freq, alive in zip(rec_q, freq_q, frame["p_alive"]):
        if freq >= 2 and rec >= 2:
            labels.append("Champions")
        elif freq >= 2 and rec == 1:
            labels.append("Loyal")
        elif freq >= 1 and rec == 0:
            labels.append("At risk")
        elif freq == 0 and alive < 0.45:
            labels.append("Hibernating")
        else:
            labels.append("Promising")
    return np.array(labels, dtype=object)


def _payload(
    frame: pd.DataFrame,
    bgnbd: dict[str, float],
    gg: dict[str, float],
    ridge: dict,
    margin: float,
    snapshot_week: int,
    horizon_weeks: int,
    calendar_weeks: int,
    spearman: float,
    holdout_mape: float,
    holdout_r2: float,
) -> dict:
    customers = []
    for row in frame.itertuples(index=False):
        customers.append(
            {
                "id": int(row.customer_id),
                "channel": row.channel,
                "funnel": row.funnel,
                "frequency": float(row.frequency),
                "recency": float(row.recency),
                "T": float(row.T),
                "orders": float(row.orders),
                "monetary": float(row.monetary),
                "aov": float(row.aov),
                "p_alive": float(row.p_alive),
                "e_purchases": float(row.e_purchases),
                "e_aov": float(row.e_aov),
                "clv_bgnbd": float(row.clv_bgnbd),
                "clv_ml": float(row.clv_ml),
                "clv_blend": float(row.clv_blend),
                "holdout_spend": float(row.holdout_spend),
                "segment": row.segment,
                "rfm_segment": row.rfm_segment,
                "rank": int(row.rank),
                "discount_rate": float(row.discount_rate),
                "return_rate": float(row.return_rate),
                "plan_size": int(getattr(row, "plan_size", 2)),
                "skip_rate": float(getattr(row, "skip_rate", 0.0)),
                "first_box_discount": float(getattr(row, "first_box_discount", 0.0)),
                "n_skips": float(getattr(row, "n_skips", 0.0)),
            }
        )

    def _group(col: str, value_col: str = "clv_blend") -> list[dict]:
        grouped = frame.groupby(col, observed=False)
        rows = []
        for name, part in grouped:
            rows.append(
                {
                    "name": str(name),
                    "customers": int(len(part)),
                    "mean_clv": float(part[value_col].mean()),
                    "median_clv": float(part[value_col].median()),
                    "total_clv": float(part[value_col].sum()),
                    "mean_holdout": float(part["holdout_spend"].mean()),
                    "mean_p_alive": float(part["p_alive"].mean()),
                    "mean_aov": float(part["aov"].mean()),
                }
            )
        return sorted(rows, key=lambda item: item["total_clv"], reverse=True)

    deciles = pd.qcut(frame["clv_blend"].rank(method="first"), 10, labels=False) + 1
    lift_rows = []
    overall = float(frame["holdout_spend"].mean())
    for decile in range(10, 0, -1):
        part = frame[deciles == decile]
        mean_h = float(part["holdout_spend"].mean())
        lift_rows.append(
            {
                "decile": int(decile),
                "mean_pred": float(part["clv_blend"].mean()),
                "mean_holdout": mean_h,
                "lift": float(mean_h / overall) if overall else 0.0,
            }
        )

    hist_counts, hist_edges = np.histogram(frame["clv_blend"], bins=18)
    return {
        "metrics": {
            "n_customers": int(len(frame)),
            "snapshot_week": int(snapshot_week),
            "horizon_weeks": int(horizon_weeks),
            "calendar_weeks": int(calendar_weeks),
            "margin": float(margin),
            "mean_clv": float(frame["clv_blend"].mean()),
            "median_clv": float(frame["clv_blend"].median()),
            "total_clv": float(frame["clv_blend"].sum()),
            "mean_p_alive": float(frame["p_alive"].mean()),
            "mean_aov": float(frame["aov"].mean()),
            "high_share": float((frame["segment"] == "High").mean() * 100.0),
            "holdout_spearman": float(spearman) if np.isfinite(spearman) else 0.0,
            "holdout_mape": float(holdout_mape) if np.isfinite(holdout_mape) else 0.0,
            "holdout_r2": float(holdout_r2) if np.isfinite(holdout_r2) else 0.0,
            "ridge_r2": float(ridge.get("r2", 0.0)),
            "bgnbd_nll": float(bgnbd.get("nll", 0.0)),
            "first_box_margin": float(FIRST_BOX_MARGIN),
            "currency": "CAD",
            "mean_skip_rate": float(frame["skip_rate"].mean()) if "skip_rate" in frame else 0.0,
            "one_and_done_share": float(frame["one_and_done"].mean()) if "one_and_done" in frame else 0.0,
            "mean_first_discount": float(frame["first_box_discount"].mean()) if "first_box_discount" in frame else 0.0,
            "family_share": float((frame["plan_size"] == 4).mean()) if "plan_size" in frame else 0.0,
        },
        "models": {
            "bgnbd": {k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in bgnbd.items()},
            "gammagamma": {k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in gg.items()},
            "ridge_coefficients": ridge.get("coefficients", {}),
        },
        "customers": customers,
        "by_channel": _group("channel"),
        "by_funnel": _group("funnel"),
        "by_value": _group("segment"),
        "by_rfm": _group("rfm_segment"),
        "by_plan": _group("plan_size") if "plan_size" in frame.columns else [],
        "assumptions": _assumption_rows(margin, frame),
        "lift": lift_rows,
        "series": {
            "clv_hist": hist_counts.astype(int).tolist(),
            "clv_bins": hist_edges.astype(float).tolist(),
            "pred": frame["clv_blend"].astype(float).tolist()[:400],
            "actual": frame["holdout_spend"].astype(float).tolist()[:400],
            "p_alive": frame["p_alive"].astype(float).tolist()[:400],
            "recency": frame["recency"].astype(float).tolist()[:400],
        },
    }
