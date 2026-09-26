"""Media-mix incrementality, multi-touch attribution, and spend-plus-price allocation.

The funnel studio estimates a 2SLS structural system. This module answers a
different planning question: how much of observed sales is incremental to spend
and to price, how badly last-touch / linear / time-decay mis-credit that, and
where the next dollar (or price point) should go.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import minimize
from sklearn.metrics import r2_score

from hierarchical_mmm_engine.transforms import (
    geometric_adstock,
    hill_saturation,
    steady_state_transform,
    steady_state_transform_derivative,
)

MEDIA = {
    "TV": {"decay": 0.62, "k": 72.0, "beta": 210.0, "mean": 46.0, "touch": 0.05, "flight": (4, 8)},
    "Social": {"decay": 0.28, "k": 38.0, "beta": 105.0, "mean": 34.0, "touch": 0.20, "flight": (0, 1)},
    "Search": {"decay": 0.08, "k": 44.0, "beta": 155.0, "mean": 40.0, "touch": 0.60, "flight": (0, 1)},
    "Email": {"decay": 0.15, "k": 16.0, "beta": 48.0, "mean": 12.0, "touch": 0.15, "flight": (0, 1)},
}

TRUE_PRICE_ELASTICITY = -1.20
TRUE_PRICE_SCALE = 420.0  # $k sales per unit log-price (approx)
MARGIN = 0.38


def run_attribution_scenario(
    n_weeks: int = 156,
    holdout_weeks: int = 26,
    media_budget: float = 140.0,
    seed: int = 42,
) -> dict:
    rng = np.random.default_rng(int(seed))
    n_weeks = int(np.clip(n_weeks, 80, 312))
    holdout_weeks = int(np.clip(holdout_weeks, 8, 52))
    frame = _simulate(rng, n_weeks)
    split = n_weeks - holdout_weeks
    train = frame.iloc[:split].copy()
    test = frame.iloc[split:].copy()
    mmm = _fit_mmm(train, test, frame)
    frameworks = _attribution_frameworks(frame, mmm)
    incrementals = _incrementals(mmm, frame)
    allocation = _allocate(mmm, media_budget)
    return _payload(frame, test, mmm, frameworks, incrementals, allocation, split, media_budget, holdout_weeks)


def _simulate(rng: np.random.Generator, n: int) -> pd.DataFrame:
    t = np.arange(n)
    holiday = (((t % 52) >= 46) | ((t % 52) <= 1)).astype(float)
    season = 18.0 * np.sin(2 * np.pi * t / 52.0) - 8.0 * np.cos(4 * np.pi * t / 52.0)
    block = 13
    levels = rng.uniform(96.0, 105.0, size=(n // block) + 2)
    price = np.clip(np.repeat(levels, block)[:n] + rng.normal(0.0, 0.28, n), 93.0, 110.0)
    data: dict[str, np.ndarray] = {
        "week": t,
        "holiday": holiday,
        "season": season,
        "price": price,
        "log_price": np.log(price / 100.0),
    }
    media_sales = np.zeros(n)
    true_contrib = {}
    for name, spec in MEDIA.items():
        on, cycle = spec["flight"]
        if cycle > on > 0:
            mask = ((t % cycle) < on).astype(float)
            duty = on / cycle
            spend = mask * rng.gamma(4.0, spec["mean"] / (4.0 * duty), n)
        else:
            spend = rng.uniform(spec["mean"] * 0.55, spec["mean"] * 1.45, n)
        spend = spend * (1.0 + 0.22 * holiday * (name in {"Search", "Social", "TV"}))
        adstocked = geometric_adstock(spend, spec["decay"])
        trans = np.asarray(hill_saturation(adstocked, k=spec["k"], s=1.0), dtype=float)
        contrib = spec["beta"] * trans
        data[f"spend_{name}"] = spend
        data[f"trans_{name}"] = trans
        true_contrib[name] = contrib
        media_sales = media_sales + contrib
    price_effect = TRUE_PRICE_SCALE * data["log_price"]
    intercept = 1850.0
    sales = (
        intercept
        + 0.09 * t
        + season
        + 85.0 * holiday
        + price_effect
        + media_sales
        + rng.normal(0.0, 28.0, n)
    )
    data["sales"] = sales
    data["true_price"] = price_effect
    data["true_media"] = media_sales
    data["true_baseline"] = sales - media_sales - price_effect
    for name, contrib in true_contrib.items():
        data[f"true_{name}"] = contrib
    # Last-touch "reported conversions" — Search-heavy, not incremental
    touch_w = np.array([MEDIA[n]["touch"] for n in MEDIA])
    touch_w = touch_w / touch_w.sum()
    reported = np.zeros((n, len(MEDIA)))
    for i, name in enumerate(MEDIA):
        intensity = np.maximum(data[f"spend_{name}"], 0.1)
        reported[:, i] = intensity * touch_w[i]
    reported = reported / reported.sum(axis=1, keepdims=True)
    credited = reported * np.maximum(sales, 0.0)[:, None]
    for i, name in enumerate(MEDIA):
        data[f"last_{name}"] = credited[:, i]
        data[f"touch_{name}"] = reported[:, i]
    return pd.DataFrame(data)


def _fit_mmm(train: pd.DataFrame, test: pd.DataFrame, frame: pd.DataFrame) -> dict:
    trans_cols = [f"trans_{n}" for n in MEDIA]
    cols = ["season", "holiday", "log_price", *trans_cols]
    x_train = sm.add_constant(train[cols], has_constant="add")
    fit = sm.OLS(train["sales"], x_train).fit()
    x_test = sm.add_constant(test[cols], has_constant="add")
    pred = np.asarray(fit.predict(x_test), dtype=float)
    x_all = sm.add_constant(frame[cols], has_constant="add")
    fitted = np.asarray(fit.predict(x_all), dtype=float)
    params = {str(k): float(v) for k, v in fit.params.items()}
    contrib = {}
    for name in MEDIA:
        contrib[name] = params.get(f"trans_{name}", 0.0) * frame[f"trans_{name}"].to_numpy(dtype=float)
    price_contrib = params.get("log_price", 0.0) * frame["log_price"].to_numpy(dtype=float)
    return {
        "params": params,
        "test_r2": float(r2_score(test["sales"], pred)) if test["sales"].std() else 0.0,
        "test_mape": float(np.mean(np.abs(test["sales"] - pred) / np.maximum(np.abs(test["sales"]), 1.0)) * 100.0),
        "test_pred": pred,
        "fitted": fitted,
        "contrib": contrib,
        "price_contrib": price_contrib,
        "elasticity": float(params.get("log_price", 0.0) / max(float(np.mean(frame["sales"])), 1.0)),
        "price_beta": float(params.get("log_price", 0.0)),
    }


def _attribution_frameworks(frame: pd.DataFrame, mmm: dict) -> list[dict]:
    names = list(MEDIA)
    true_tot = {n: float(np.clip(frame[f"true_{n}"].sum(), 0.0, None)) for n in names}
    true_sum = sum(true_tot.values()) or 1.0
    last_tot = {n: float(frame[f"last_{n}"].sum()) for n in names}
    last_sum = sum(last_tot.values()) or 1.0

    spend = {n: frame[f"spend_{n}"].to_numpy(dtype=float) for n in names}
    linear = _weighted_credit(frame["sales"].to_numpy(), spend, decay=None)
    decayed = _weighted_credit(frame["sales"].to_numpy(), spend, decay=0.5)
    first = _first_touch(frame["sales"].to_numpy(), spend)

    mmm_tot = {n: float(np.clip(np.sum(mmm["contrib"][n]), 0.0, None)) for n in names}
    mmm_sum = sum(mmm_tot.values()) or 1.0

    # Geo-lift calibration: TV lift observed at 88% of MMM (typical downward calibration)
    lift_scale = {"TV": 0.82, "Social": 1.40, "Search": 0.90, "Email": 0.92}
    cal = {n: mmm_tot[n] * lift_scale[n] for n in names}
    cal_sum = sum(cal.values()) or 1.0

    rows = []
    for label, totals, denom in [
        ("True incremental", true_tot, true_sum),
        ("Last-touch", last_tot, last_sum),
        ("First-touch", first, sum(first.values()) or 1.0),
        ("Linear MTA", linear, sum(linear.values()) or 1.0),
        ("Time-decay MTA", decayed, sum(decayed.values()) or 1.0),
        ("MMM incremental", mmm_tot, mmm_sum),
        ("Lift-calibrated MMM", cal, cal_sum),
    ]:
        shares = {n: 100.0 * totals[n] / denom for n in names}
        mae = float(np.mean([abs(shares[n] - 100.0 * true_tot[n] / true_sum) for n in names]))
        rows.append(
            {
                "framework": label,
                "shares": shares,
                "totals": {n: float(totals[n]) for n in names},
                "share_mae": mae,
                "is_truth": label == "True incremental",
            }
        )
    return rows


def _weighted_credit(sales: np.ndarray, spend: dict[str, np.ndarray], decay: float | None) -> dict[str, float]:
    names = list(spend)
    credit = {n: 0.0 for n in names}
    for t, y in enumerate(sales):
        weights = np.zeros(len(names))
        for i, name in enumerate(names):
            if decay is None:
                weights[i] = max(spend[name][t], 0.0)
            else:
                lookback = min(8, t + 1)
                w = 0.0
                for lag in range(lookback):
                    w += spend[name][t - lag] * (decay**lag)
                weights[i] = w
        if weights.sum() <= 0:
            continue
        weights = weights / weights.sum()
        for i, name in enumerate(names):
            credit[name] += float(y * weights[i])
    return credit


def _first_touch(sales: np.ndarray, spend: dict[str, np.ndarray]) -> dict[str, float]:
    names = list(spend)
    credit = {n: 0.0 for n in names}
    for t, y in enumerate(sales):
        start = max(0, t - 7)
        window = {n: float(spend[n][start : t + 1].sum()) for n in names}
        # First-touch proxy: channel with earliest positive spend in the window
        winner = None
        for s in range(start, t + 1):
            present = [n for n in names if spend[n][s] > 1e-6]
            if present:
                # TOFU first if present
                winner = "TV" if "TV" in present else present[0]
                break
        if winner is None:
            winner = max(window, key=window.get)
        credit[winner] += float(y)
    return credit


def _incrementals(mmm: dict, frame: pd.DataFrame) -> list[dict]:
    rows = []
    mean_price = float(frame["price"].mean())
    for name, spec in MEDIA.items():
        spend = float(frame[f"spend_{name}"].mean())
        dtrans = steady_state_transform_derivative(spend, spec["decay"], spec["k"], 1.0)
        beta = mmm["params"].get(f"trans_{name}", 0.0)
        iroas = float(beta * dtrans)
        true_dtrans = steady_state_transform_derivative(spend, spec["decay"], spec["k"], 1.0)
        true_iroas = float(spec["beta"] * true_dtrans)
        rows.append(
            {
                "name": name,
                "kind": "media",
                "mean_spend": spend,
                "estimated_beta": beta,
                "true_beta": spec["beta"],
                "iroas": iroas,
                "true_iroas": true_iroas,
                "plus_10k_sales": float(10.0 * iroas),
                "true_plus_10k": float(10.0 * true_iroas),
            }
        )
    # +1 price-index point at the mean
    d_log = np.log((mean_price + 1.0) / mean_price)
    price_impact = float(mmm["price_beta"] * d_log)
    true_price_impact = float(TRUE_PRICE_SCALE * d_log)
    rows.append(
        {
            "name": "Price +1 idx",
            "kind": "price",
            "mean_spend": mean_price,
            "estimated_beta": mmm["price_beta"],
            "true_beta": TRUE_PRICE_SCALE,
            "iroas": price_impact,
            "true_iroas": true_price_impact,
            "plus_10k_sales": price_impact,
            "true_plus_10k": true_price_impact,
        }
    )
    return rows


def _allocate(mmm: dict, budget: float) -> dict:
    names = list(MEDIA)
    n = len(names)

    def media_sales(spend: np.ndarray) -> float:
        total = 0.0
        for i, name in enumerate(names):
            spec = MEDIA[name]
            trans = steady_state_transform(float(spend[i]), spec["decay"], spec["k"], 1.0)
            total += mmm["params"].get(f"trans_{name}", 0.0) * trans
        return total

    def profit(spend: np.ndarray, price_index: float) -> float:
        sales_media = media_sales(spend)
        d_log = np.log(price_index / 100.0)
        sales_price = mmm["price_beta"] * d_log
        revenue = (1850.0 + sales_media + sales_price) * (price_index / 100.0)
        return float(MARGIN * revenue - np.sum(spend))

    bounds = [(8.0, 80.0) for _ in names]
    start = np.full(n, budget / n)
    constraint = {"type": "eq", "fun": lambda s: np.sum(s) - budget}
    last_touch_mix = np.array([MEDIA[n]["touch"] for n in names])
    last_touch_mix = last_touch_mix / last_touch_mix.sum() * budget
    last_touch_mix = np.clip(last_touch_mix, 8.0, 80.0)
    last_touch_mix = last_touch_mix * budget / last_touch_mix.sum()

    res = minimize(lambda s: -profit(s, 100.0), start, method="SLSQP", bounds=bounds, constraints=[constraint])
    opt = np.clip(res.x, 8.0, 80.0)
    opt = opt * budget / opt.sum()

    # Best constant price in [96, 104] given optimized media
    prices = np.linspace(96.0, 104.0, 17)
    price_curve = [{"price": float(p), "profit": profit(opt, float(p))} for p in prices]
    best_price = max(price_curve, key=lambda row: row["profit"])

    def pack(spend: np.ndarray, label: str, price: float) -> list[dict]:
        rows = []
        for i, name in enumerate(names):
            spec = MEDIA[name]
            dtrans = steady_state_transform_derivative(float(spend[i]), spec["decay"], spec["k"], 1.0)
            iroas = float(mmm["params"].get(f"trans_{name}", 0.0) * dtrans)
            rows.append(
                {
                    "name": name,
                    "plan": label,
                    "spend": float(spend[i]),
                    "iroas": iroas,
                    "share": float(100.0 * spend[i] / budget),
                }
            )
        return rows

    last_profit = profit(last_touch_mix, 100.0)
    opt_profit = profit(opt, 100.0)
    priced_profit = profit(opt, best_price["price"])
    return {
        "last_touch": pack(last_touch_mix, "last-touch", 100.0),
        "incremental": pack(opt, "incremental", 100.0),
        "price_curve": price_curve,
        "recommended_price": best_price["price"],
        "last_profit": last_profit,
        "incremental_profit": opt_profit,
        "priced_profit": priced_profit,
        "media_lift": opt_profit - last_profit,
        "price_lift": priced_profit - opt_profit,
        "total_lift": priced_profit - last_profit,
        "budget": float(budget),
    }


def _payload(
    frame: pd.DataFrame,
    test: pd.DataFrame,
    mmm: dict,
    frameworks: list[dict],
    incrementals: list[dict],
    allocation: dict,
    split: int,
    budget: float,
    holdout_weeks: int,
) -> dict:
    names = list(MEDIA)
    return {
        "metrics": {
            "n_weeks": int(len(frame)),
            "holdout_weeks": int(holdout_weeks),
            "split_week": int(split),
            "budget": float(budget),
            "test_r2": mmm["test_r2"],
            "test_mape": mmm["test_mape"],
            "price_beta": mmm["price_beta"],
            "true_price_beta": TRUE_PRICE_SCALE,
            "last_touch_mae": next(r["share_mae"] for r in frameworks if r["framework"] == "Last-touch"),
            "mmm_mae": next(r["share_mae"] for r in frameworks if r["framework"] == "MMM incremental"),
            "calibrated_mae": next(r["share_mae"] for r in frameworks if r["framework"] == "Lift-calibrated MMM"),
            "media_lift": allocation["media_lift"],
            "price_lift": allocation["price_lift"],
            "total_lift": allocation["total_lift"],
            "recommended_price": allocation["recommended_price"],
        },
        "frameworks": frameworks,
        "incrementals": incrementals,
        "allocation": allocation,
        "mmm_params": mmm["params"],
        "series": {
            "week": frame["week"].astype(int).tolist(),
            "sales": frame["sales"].astype(float).tolist(),
            "fitted": mmm["fitted"].astype(float).tolist(),
            "price": frame["price"].astype(float).tolist(),
            "true_price": frame["true_price"].astype(float).tolist(),
            "est_price": mmm["price_contrib"].astype(float).tolist(),
            "split_week": int(split),
            "test_week": test["week"].astype(int).tolist(),
            "test_actual": test["sales"].astype(float).tolist(),
            "test_pred": mmm["test_pred"].astype(float).tolist(),
            "true_media": {n: frame[f"true_{n}"].astype(float).tolist() for n in names},
            "spend": {n: frame[f"spend_{n}"].astype(float).tolist() for n in names},
        },
    }
