"""Promo-aware demand forecasting and trade-spend allocation.

National MMM answers media mix. This module answers a different question:
given a weekly category, how should trade dollars (TPR, feature, display)
be placed across retail channels so incremental volume per dollar is highest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

from hierarchical_mmm_engine.transforms import hill_saturation

TRADE_CHANNELS = {
    "Grocery": {
        "base": 820.0,
        "elasticity": -1.15,
        "tpr": 1.45,
        "feature": 0.28,
        "display": 0.22,
        "k_trade": 55.0,
        "margin": 0.32,
        "share": 0.38,
    },
    "Mass": {
        "base": 610.0,
        "elasticity": -1.40,
        "tpr": 1.70,
        "feature": 0.20,
        "display": 0.18,
        "k_trade": 48.0,
        "margin": 0.24,
        "share": 0.27,
    },
    "Drug": {
        "base": 190.0,
        "elasticity": -0.85,
        "tpr": 1.10,
        "feature": 0.34,
        "display": 0.26,
        "k_trade": 22.0,
        "margin": 0.38,
        "share": 0.10,
    },
    "Club": {
        "base": 340.0,
        "elasticity": -0.70,
        "tpr": 0.85,
        "feature": 0.16,
        "display": 0.30,
        "k_trade": 36.0,
        "margin": 0.29,
        "share": 0.14,
    },
    "E-comm": {
        "base": 260.0,
        "elasticity": -1.55,
        "tpr": 1.95,
        "feature": 0.40,
        "display": 0.08,
        "k_trade": 28.0,
        "margin": 0.36,
        "share": 0.11,
    },
}


def run_forecast_scenario(
    n_weeks: int = 156,
    holdout_weeks: int = 26,
    trade_budget: float = 180.0,
    seed: int = 42,
) -> dict:
    """Simulate channel demand, fit forecast models, and allocate trade spend."""
    rng = np.random.default_rng(int(seed))
    n_weeks = int(np.clip(n_weeks, 80, 312))
    holdout_weeks = int(np.clip(holdout_weeks, 8, 52))
    panel = _simulate_panel(rng, n_weeks).sort_values(["week", "channel"]).reset_index(drop=True)
    split = n_weeks - holdout_weeks
    train = panel[panel["week"] < split].copy()
    test = panel[panel["week"] >= split].copy()

    models = _fit_models(train, test)
    panel = _attach_forecasts(panel, models, split)
    allocation = _allocate_trade(models["structural"], trade_budget, holdout_weeks)

    holdout = panel[panel["week"] >= split]
    return _payload(panel, holdout, models, allocation, split, trade_budget, holdout_weeks)


def _simulate_panel(rng: np.random.Generator, n_weeks: int) -> pd.DataFrame:
    time_idx = np.arange(n_weeks)
    week_of_year = time_idx % 52
    holiday = ((week_of_year >= 46) | (week_of_year <= 1)).astype(float)
    payday = (((week_of_year % 4) == 0) | ((week_of_year % 4) == 2)).astype(float)
    season = 0.12 * np.sin(2 * np.pi * time_idx / 52.0) - 0.05 * np.cos(4 * np.pi * time_idx / 52.0)
    rows = []
    for channel, spec in TRADE_CHANNELS.items():
        price = np.clip(100.0 + 2.8 * np.sin(2 * np.pi * time_idx / 26.0) + rng.normal(0.0, 0.9, n_weeks), 92.0, 112.0)
        tpr = np.clip(0.02 + 0.14 * holiday + rng.normal(0.0, 0.035, n_weeks), 0.0, 0.40)
        feature = ((rng.random(n_weeks) < (0.18 + 0.22 * holiday)) | (tpr > 0.16)).astype(float)
        display = ((rng.random(n_weeks) < (0.12 + 0.18 * holiday)) | ((feature > 0) & (rng.random(n_weeks) < 0.45))).astype(float)
        # On-off promo flights so lift is identifiable
        offset = list(TRADE_CHANNELS).index(channel)
        flight = ((time_idx + offset) % 6 < 2).astype(float)
        tpr = np.clip(tpr * (0.35 + 0.90 * flight), 0.0, 0.40)
        feature = feature * np.maximum(flight, holiday)
        display = display * np.maximum(flight, (week_of_year >= 44).astype(float))
        trade = (
            spec["base"] * 0.012 * tpr * 100.0
            + spec["base"] * 0.035 * feature
            + spec["base"] * 0.028 * display
        )
        log_y = (
            np.log(spec["base"])
            + 0.0011 * time_idx
            + season
            + 0.08 * holiday
            + 0.025 * payday
            + spec["elasticity"] * np.log(price / 100.0)
            + spec["tpr"] * tpr
            + spec["feature"] * feature
            + spec["display"] * display
            + rng.normal(0.0, 0.045, n_weeks)
        )
        units = np.exp(log_y)
        baseline = spec["base"] * np.exp(0.0011 * time_idx + season + 0.08 * holiday + 0.025 * payday + spec["elasticity"] * np.log(price / 100.0))
        incremental = np.maximum(units - baseline, 0.0)
        for week in range(n_weeks):
            rows.append(
                {
                    "week": week,
                    "channel": channel,
                    "units": float(units[week]),
                    "baseline": float(baseline[week]),
                    "incremental": float(incremental[week]),
                    "price": float(price[week]),
                    "tpr": float(tpr[week]),
                    "feature": float(feature[week]),
                    "display": float(display[week]),
                    "holiday": float(holiday[week]),
                    "payday": float(payday[week]),
                    "season": float(season[week]),
                    "trade_spend": float(trade[week]),
                    "margin": spec["margin"],
                }
            )
    return pd.DataFrame(rows)


def _feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["sin1"] = np.sin(2 * np.pi * out["week"] / 52.0)
    out["cos1"] = np.cos(2 * np.pi * out["week"] / 52.0)
    out["sin2"] = np.sin(4 * np.pi * out["week"] / 52.0)
    out["cos2"] = np.cos(4 * np.pi * out["week"] / 52.0)
    out["log_price"] = np.log(out["price"] / 100.0)
    dummies = pd.get_dummies(out["channel"], prefix="ch", drop_first=True)
    return pd.concat([out, dummies], axis=1)


FEATURE_COLS = [
    "week",
    "sin1",
    "cos1",
    "sin2",
    "cos2",
    "log_price",
    "holiday",
    "payday",
    "tpr",
    "feature",
    "display",
]


def _design(frame: pd.DataFrame) -> pd.DataFrame:
    cols = FEATURE_COLS + [c for c in frame.columns if c.startswith("ch_")]
    return frame[cols]


def _fit_models(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    train_f = _feature_frame(train)
    test_f = _feature_frame(test)
    y_train = np.log(train_f["units"].to_numpy(dtype=float))
    x_train = _design(train_f)
    x_test = _design(test_f)
    scaler = StandardScaler()
    z_train = scaler.fit_transform(x_train.to_numpy(dtype=float))
    z_test = scaler.transform(x_test.to_numpy(dtype=float))

    ridge = Ridge(alpha=1.5)
    ridge.fit(z_train, y_train)
    ridge_pred = np.exp(ridge.predict(z_test))
    ridge_fitted = np.exp(ridge.predict(z_train))

    # Interpretable promo structural model on log units (unscaled, for lift)
    struct_cols = ["week", "sin1", "cos1", "holiday", "payday", "log_price", "tpr", "feature", "display"]
    channel_lifts = {}
    for channel in TRADE_CHANNELS:
        part = train_f[train_f["channel"] == channel]
        xs = part[struct_cols].to_numpy(dtype=float)
        ys = np.log(part["units"].to_numpy(dtype=float))
        beta, _, _, _ = np.linalg.lstsq(np.column_stack([np.ones(len(part)), xs]), ys, rcond=None)
        names = ["intercept", *struct_cols]
        channel_lifts[channel] = {name: float(val) for name, val in zip(names, beta)}

    naive_pred = _seasonal_naive(train, test)
    scores = {
        "seasonal_naive": _score(test["units"].to_numpy(), naive_pred),
        "ridge_arx": _score(test["units"].to_numpy(), ridge_pred),
    }
    # Ensemble weights inverse RMSE
    w_naive = 1.0 / max(scores["seasonal_naive"]["rmse"], 1e-6)
    w_ridge = 1.0 / max(scores["ridge_arx"]["rmse"], 1e-6)
    total = w_naive + w_ridge
    ensemble = (w_naive * naive_pred + w_ridge * ridge_pred) / total
    scores["ensemble"] = _score(test["units"].to_numpy(), ensemble)
    winner = min(scores, key=lambda key: scores[key]["wape"])
    return {
        "ridge": ridge,
        "scaler": scaler,
        "feature_names": list(x_train.columns),
        "structural": channel_lifts,
        "scores": scores,
        "winner": winner,
        "weights": {"seasonal_naive": w_naive / total, "ridge_arx": w_ridge / total},
        "test_pred": {
            "seasonal_naive": naive_pred.astype(float).tolist(),
            "ridge_arx": ridge_pred.astype(float).tolist(),
            "ensemble": ensemble.astype(float).tolist(),
        },
        "train_fitted": ridge_fitted.astype(float).tolist(),
        "ridge_coef": {name: float(val) for name, val in zip(x_train.columns, ridge.coef_)},
    }


def _seasonal_naive(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    preds = []
    for row in test.itertuples(index=False):
        hist = train[(train["channel"] == row.channel) & (train["week"] % 52 == row.week % 52)]
        if hist.empty:
            hist = train[train["channel"] == row.channel]
        preds.append(float(hist["units"].mean()) if len(hist) else float(row.units))
    return np.asarray(preds, dtype=float)


def _score(actual: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    wape = float(np.sum(np.abs(actual - pred)) / np.maximum(np.sum(np.abs(actual)), 1e-8) * 100.0)
    mape = float(mean_absolute_percentage_error(actual, np.maximum(pred, 1e-6)) * 100.0)
    rmse = float(np.sqrt(mean_squared_error(actual, pred)))
    bias = float(np.mean(pred - actual))
    r2 = float(r2_score(actual, pred)) if actual.std() > 0 else 0.0
    return {"wape": wape, "mape": mape, "rmse": rmse, "bias": bias, "r2": r2}


def _attach_forecasts(panel: pd.DataFrame, models: dict, split: int) -> pd.DataFrame:
    out = panel.sort_values(["week", "channel"]).reset_index(drop=True)
    test_mask = out["week"] >= split
    out.loc[test_mask, "pred_naive"] = models["test_pred"]["seasonal_naive"]
    out.loc[test_mask, "pred_ridge"] = models["test_pred"]["ridge_arx"]
    out.loc[test_mask, "pred_ensemble"] = models["test_pred"]["ensemble"]
    # Reconstruct ridge on full sample for a continuous line
    full_f = _feature_frame(out)
    z = models["scaler"].transform(_design(full_f).to_numpy(dtype=float))
    out["pred_full"] = np.exp(models["ridge"].predict(z))
    return out


def _allocate_trade(channel_lifts: dict[str, dict[str, float]], budget: float, horizon: int) -> dict:
    names = list(TRADE_CHANNELS)
    n = len(names)
    # Expected incremental units per week at a given weekly trade $ (Hill on spend)
    def incremental(spend: np.ndarray) -> np.ndarray:
        out = np.zeros(n)
        for i, name in enumerate(names):
            spec = TRADE_CHANNELS[name]
            lifts = channel_lifts[name]
            # Map spend into a typical promo mix: 60% TPR, 25% feature, 15% display
            depth = np.clip(0.60 * spend[i] / max(spec["base"] * 0.012 * 100.0, 1e-6), 0.0, 0.40)
            feat = np.clip(0.25 * spend[i] / max(spec["base"] * 0.035, 1e-6), 0.0, 1.0)
            disp = np.clip(0.15 * spend[i] / max(spec["base"] * 0.028, 1e-6), 0.0, 1.0)
            sat = float(hill_saturation(spend[i], k=spec["k_trade"], s=1.0))
            raw = (
                lifts.get("tpr", spec["tpr"]) * depth
                + lifts.get("feature", spec["feature"]) * feat
                + lifts.get("display", spec["display"]) * disp
            )
            out[i] = spec["base"] * max(raw, 0.0) * sat * 1.15
        return out

    def profit(spend: np.ndarray) -> float:
        units = incremental(spend)
        margins = np.array([TRADE_CHANNELS[n]["margin"] for n in names])
        # units are weekly; horizon weeks; list price index ~ $4.2 contribution base unit
        unit_value = 4.2 * margins
        return float(np.sum(horizon * units * unit_value - spend * horizon))

    bounds = [(4.0, max(8.0, budget * 0.55)) for _ in names]
    start = np.full(n, budget / n)
    constraint = {"type": "eq", "fun": lambda s: np.sum(s) - budget}
    equal = start.copy()
    res = minimize(lambda s: -profit(s), start, method="SLSQP", bounds=bounds, constraints=[constraint])
    opt = np.clip(res.x, 4.0, None)
    if abs(opt.sum() - budget) > 0.5:
        opt = opt * budget / opt.sum()

    def pack(spend: np.ndarray) -> list[dict]:
        units = incremental(spend)
        rows = []
        for i, name in enumerate(names):
            spec = TRADE_CHANNELS[name]
            inc_units = float(units[i] * horizon)
            trade = float(spend[i] * horizon)
            profit_i = inc_units * 4.2 * spec["margin"] - trade
            rows.append(
                {
                    "channel": name,
                    "weekly_trade": float(spend[i]),
                    "horizon_trade": trade,
                    "incremental_units": inc_units,
                    "roi": float((inc_units * 4.2 * spec["margin"]) / trade) if trade else 0.0,
                    "efficiency": float(inc_units / trade) if trade else 0.0,
                    "profit": profit_i,
                    "tpr_coef": float(channel_lifts[name].get("tpr", 0.0)),
                    "feature_coef": float(channel_lifts[name].get("feature", 0.0)),
                    "display_coef": float(channel_lifts[name].get("display", 0.0)),
                    "price_elasticity": float(channel_lifts[name].get("log_price", spec["elasticity"])),
                    "true_tpr": spec["tpr"],
                    "true_feature": spec["feature"],
                    "true_display": spec["display"],
                }
            )
        return rows

    equal_rows = pack(equal)
    opt_rows = pack(opt)
    equal_profit = float(sum(r["profit"] for r in equal_rows))
    opt_profit = float(sum(r["profit"] for r in opt_rows))
    return {
        "equal": equal_rows,
        "optimized": opt_rows,
        "equal_profit": equal_profit,
        "optimized_profit": opt_profit,
        "profit_lift": opt_profit - equal_profit,
        "pct_lift": float(100.0 * (opt_profit - equal_profit) / abs(equal_profit)) if equal_profit else 0.0,
        "weekly_budget": float(budget),
        "horizon_weeks": int(horizon),
    }


def _payload(
    panel: pd.DataFrame,
    holdout: pd.DataFrame,
    models: dict,
    allocation: dict,
    split: int,
    trade_budget: float,
    holdout_weeks: int,
) -> dict:
    weekly = (
        panel.groupby("week", as_index=False)
        .agg(units=("units", "sum"), baseline=("baseline", "sum"), trade=("trade_spend", "sum"), pred=("pred_full", "sum"))
        .sort_values("week")
    )
    holdout_weekly = weekly[weekly["week"] >= split]
    by_channel = []
    for channel, part in holdout.groupby("channel"):
        actual = part["units"].to_numpy()
        pred = part["pred_ensemble"].to_numpy() if "pred_ensemble" in part else part["pred_full"].to_numpy()
        by_channel.append(
            {
                "channel": channel,
                **_score(actual, pred),
                "mean_units": float(part["units"].mean()),
                "mean_trade": float(part["trade_spend"].mean()),
                "mean_incremental": float(part["incremental"].mean()),
                "promo_weeks": float((part["tpr"] + part["feature"] + part["display"] > 0.08).mean() * 100.0),
            }
        )
    by_channel = sorted(by_channel, key=lambda row: row["mean_units"], reverse=True)

    promo_effect = []
    for channel, part in panel.groupby("channel"):
        on = part[part["tpr"] > 0.08]
        off = part[part["tpr"] <= 0.08]
        promo_effect.append(
            {
                "channel": channel,
                "promo_units": float(on["units"].mean()) if len(on) else 0.0,
                "base_units": float(off["units"].mean()) if len(off) else 0.0,
                "lift_pct": float(100.0 * (on["units"].mean() / off["units"].mean() - 1.0)) if len(on) and len(off) and off["units"].mean() else 0.0,
                "trade_per_week": float(on["trade_spend"].mean()) if len(on) else 0.0,
            }
        )

    return {
        "metrics": {
            "n_weeks": int(panel["week"].nunique()),
            "holdout_weeks": int(holdout_weeks),
            "split_week": int(split),
            "trade_budget": float(trade_budget),
            "winner": models["winner"],
            **{f"{name}_{k}": v for name, score in models["scores"].items() for k, v in score.items()},
            "ensemble_wape": models["scores"]["ensemble"]["wape"],
            "ensemble_mape": models["scores"]["ensemble"]["mape"],
            "ensemble_r2": models["scores"]["ensemble"]["r2"],
            "profit_lift": allocation["profit_lift"],
            "pct_lift": allocation["pct_lift"],
            "optimized_profit": allocation["optimized_profit"],
            "equal_profit": allocation["equal_profit"],
        },
        "scores": models["scores"],
        "weights": models["weights"],
        "ridge_coef": models["ridge_coef"],
        "allocation": allocation,
        "by_channel": by_channel,
        "promo_effect": promo_effect,
        "series": {
            "week": weekly["week"].astype(int).tolist(),
            "units": weekly["units"].astype(float).tolist(),
            "baseline": weekly["baseline"].astype(float).tolist(),
            "pred": weekly["pred"].astype(float).tolist(),
            "trade": weekly["trade"].astype(float).tolist(),
            "split_week": int(split),
            "holdout_week": holdout_weekly["week"].astype(int).tolist(),
            "holdout_actual": holdout_weekly["units"].astype(float).tolist(),
            "holdout_pred": holdout_weekly["pred"].astype(float).tolist(),
            "by_channel": {
                channel: {
                    "week": part["week"].astype(int).tolist(),
                    "units": part["units"].astype(float).tolist(),
                    "pred": part["pred_full"].astype(float).tolist(),
                    "tpr": part["tpr"].astype(float).tolist(),
                    "trade": part["trade_spend"].astype(float).tolist(),
                }
                for channel, part in panel.groupby("channel")
            },
        },
    }
