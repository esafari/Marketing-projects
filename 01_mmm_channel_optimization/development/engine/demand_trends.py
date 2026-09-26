"""National demand trends, diagnostic analytics, and forward planning.

The trade-spend forecast answers where to place TPR dollars. This module
answers a different question: is demand accelerating or softening, what is
driving the residual, and what volume should next-quarter planning lock.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

DRIVER_NOTES = {
    "lag_1": "Last week's demand. High weight means persistence, not a new driver.",
    "lag_52": "Same week last year. The seasonal-naive competitor inside the regression.",
    "week": "Slow level / trend. Positive is a rising market; negative is a fade.",
    "sin1": "Annual cycle (first Fourier sine).",
    "cos1": "Annual cycle (first Fourier cosine).",
    "sin2": "Half-year cycle.",
    "cos2": "Half-year cycle.",
    "holiday": "Retail holiday week (New Year, Super Bowl, Canada Thanksgiving, Black Friday / Cyber Monday, Christmas).",
    "payday": "Biweekly Friday pay. Meal-kit and grocery demand usually ticks up.",
    "promo_depth": "Average intro-code / discount depth. Papering over a soft trend is a planning risk.",
    "price_index": "List-price index. Negative coefficient is the expected own-price response.",
    "temperature": "Weekly mean Celsius. Meal-kit demand usually eases in warm weeks.",
}


def run_demand_trend_scenario(
    n_weeks: int = 156,
    holdout_weeks: int = 26,
    horizon_weeks: int = 13,
    seed: int = 42,
) -> dict:
    """Simulate national weekly demand, decompose it, forecast, and brief planning."""
    n_weeks = max(104, int(n_weeks))
    holdout_weeks = max(8, min(int(holdout_weeks), n_weeks // 3))
    horizon_weeks = max(4, min(int(horizon_weeks), 26))
    rng = np.random.default_rng(int(seed))
    panel = _simulate_demand(n_weeks, rng)
    panel = _decompose(panel)
    split = int(panel["week"].max() - holdout_weeks + 1)
    models = _fit_forecast(panel, split)
    panel = _attach_fitted(panel, models)
    horizon = _project_horizon(panel, models, horizon_weeks)
    diagnostics = _diagnose(panel, models, split)
    planning = _plan(panel, horizon, diagnostics, horizon_weeks)
    return _payload(panel, models, horizon, diagnostics, planning, split, holdout_weeks, horizon_weeks)


def _simulate_demand(n_weeks: int, rng: np.random.Generator) -> pd.DataFrame:
    week = np.arange(1, n_weeks + 1)
    wow = ((week - 1) % 52) + 1
    # Meal-kit like Canada seasonality: winter / New Year high, midsummer low.
    seasonal = 0.10 * np.sin(2 * np.pi * (wow - 6) / 52.0) + 0.04 * np.sin(4 * np.pi * wow / 52.0)
    holiday = np.zeros(n_weeks)
    payday = ((week % 2) == 0).astype(float)
    for start in range(1, n_weeks + 1, 52):
        for offset in (1, 6, 42, 47, 51):
            idx = start + offset - 1
            if 0 <= idx < n_weeks:
                holiday[idx] = 1.0

    # Slow rise then flattening (category matures).
    trend = 980.0 + 1.15 * week - 0.0018 * week**2
    # Mid-sample level shift: competitor launch / price reset around week 78-82.
    shift_week = 80 if n_weeks > 100 else n_weeks // 2
    level_shift = np.where(week >= shift_week, -55.0, 0.0)

    promo = np.clip(0.08 + 0.04 * np.sin(2 * np.pi * week / 26.0) + rng.normal(0, 0.025, n_weeks), 0.0, 0.35)
    promo = np.where(holiday > 0, np.minimum(promo + 0.07, 0.40), promo)
    price = 100.0 + np.cumsum(rng.normal(0.02, 0.18, n_weeks))
    price = np.where(week >= shift_week, price + 3.4, price)
    temp = 8.0 + 13.0 * np.sin(2 * np.pi * (wow - 14) / 52.0) + rng.normal(0, 1.6, n_weeks)

    noise = rng.normal(0, 22.0, n_weeks)
    # Two operational shock weeks (stockout / weather miss).
    shock = np.zeros(n_weeks)
    for idx in rng.choice(np.arange(20, n_weeks - 8), size=2, replace=False):
        shock[idx] = float(rng.choice([-90.0, -70.0, 80.0]))

    demand = (
        trend
        + 220.0 * seasonal
        + 48.0 * holiday
        + 18.0 * payday
        + 310.0 * promo
        - 4.2 * (price - 100.0)
        - 2.4 * (temp - 8.0)
        + level_shift
        + shock
        + noise
    )
    demand = np.maximum(demand, 220.0)

    return pd.DataFrame(
        {
            "week": week.astype(int),
            "week_of_year": wow.astype(int),
            "demand": demand.astype(float),
            "holiday": holiday,
            "payday": payday,
            "promo_depth": promo,
            "price_index": price,
            "temperature": temp,
            "true_trend": trend + level_shift,
            "true_seasonal": 220.0 * seasonal,
            "true_shift_week": shift_week,
        }
    )


def _decompose(panel: pd.DataFrame) -> pd.DataFrame:
    y = panel["demand"].to_numpy(dtype=float)
    trend = _moving_average(y, window=13)
    detrended = y - trend
    wow = panel["week_of_year"].to_numpy(dtype=int)
    seasonal = np.zeros_like(y)
    for w in range(1, 53):
        mask = wow == w
        if mask.any():
            seasonal[mask] = float(np.mean(detrended[mask]))
    seasonal = seasonal - float(np.mean(seasonal))
    residual = y - trend - seasonal
    out = panel.copy()
    out["trend"] = trend
    out["seasonal"] = seasonal
    out["residual"] = residual
    out["yoy"] = _yoy(y)
    return out


def _moving_average(y: np.ndarray, window: int) -> np.ndarray:
    k = int(window)
    if k % 2 == 0:
        k += 1
    pad = k // 2
    padded = np.pad(y, (pad, pad), mode="edge")
    kernel = np.ones(k) / k
    return np.convolve(padded, kernel, mode="valid")


def _yoy(y: np.ndarray) -> np.ndarray:
    out = np.full_like(y, np.nan, dtype=float)
    if len(y) > 52:
        out[52:] = y[52:] / np.maximum(y[:-52], 1e-6) - 1.0
    return out


def _feature_frame(panel: pd.DataFrame) -> pd.DataFrame:
    frame = panel.copy()
    y = frame["demand"].to_numpy(dtype=float)
    frame["lag_1"] = np.concatenate([[y[0]], y[:-1]])
    if len(y) > 52:
        frame["lag_52"] = np.concatenate([y[:52], y[:-52]])
    else:
        frame["lag_52"] = y.mean()
    frame["sin1"] = np.sin(2 * np.pi * frame["week_of_year"] / 52.0)
    frame["cos1"] = np.cos(2 * np.pi * frame["week_of_year"] / 52.0)
    frame["sin2"] = np.sin(4 * np.pi * frame["week_of_year"] / 52.0)
    frame["cos2"] = np.cos(4 * np.pi * frame["week_of_year"] / 52.0)
    return frame


FEATURE_COLS = [
    "lag_1",
    "lag_52",
    "week",
    "sin1",
    "cos1",
    "sin2",
    "cos2",
    "holiday",
    "payday",
    "promo_depth",
    "price_index",
    "temperature",
]


def _fit_forecast(panel: pd.DataFrame, split: int) -> dict:
    featured = _feature_frame(panel)
    train = featured[featured["week"] < split].copy()
    test = featured[featured["week"] >= split].copy()
    x_train = train[FEATURE_COLS]
    x_test = test[FEATURE_COLS]
    y_train = train["demand"].to_numpy(dtype=float)
    y_test = test["demand"].to_numpy(dtype=float)

    scaler = StandardScaler()
    z_train = scaler.fit_transform(x_train.to_numpy(dtype=float))
    z_test = scaler.transform(x_test.to_numpy(dtype=float))
    ridge = Ridge(alpha=2.5, random_state=0)
    ridge.fit(z_train, y_train)
    ridge_pred = ridge.predict(z_test)
    ridge_fitted = ridge.predict(scaler.transform(featured[FEATURE_COLS].to_numpy(dtype=float)))

    naive = _seasonal_naive(train, test)
    scores = {
        "seasonal_naive": _score(y_test, naive),
        "ridge_arx": _score(y_test, ridge_pred),
    }
    w_naive = 1.0 / max(scores["seasonal_naive"]["rmse"], 1e-6)
    w_ridge = 1.0 / max(scores["ridge_arx"]["rmse"], 1e-6)
    total = w_naive + w_ridge
    ensemble = (w_naive * naive + w_ridge * ridge_pred) / total
    scores["ensemble"] = _score(y_test, ensemble)
    winner = min(scores, key=lambda key: scores[key]["wape"])

    resid = y_train - ridge.predict(z_train)
    sigma = float(np.std(resid, ddof=1))
    coefs = {name: float(val) for name, val in zip(FEATURE_COLS, ridge.coef_)}
    drivers = []
    for name, val in coefs.items():
        drivers.append(
            {
                "name": name,
                "coef": float(val),
                "importance": float(abs(val)),
                "note": DRIVER_NOTES.get(name, ""),
            }
        )
    drivers.sort(key=lambda row: row["importance"], reverse=True)

    return {
        "ridge": ridge,
        "scaler": scaler,
        "scores": scores,
        "winner": winner,
        "weights": {"seasonal_naive": w_naive / total, "ridge_arx": w_ridge / total},
        "sigma": sigma,
        "coefs": coefs,
        "drivers": drivers,
        "fitted": ridge_fitted.astype(float),
        "test_pred": {
            "seasonal_naive": naive.astype(float),
            "ridge_arx": ridge_pred.astype(float),
            "ensemble": ensemble.astype(float),
            "actual": y_test.astype(float),
            "week": test["week"].to_numpy(dtype=int),
        },
        "train_resid": resid.astype(float),
    }


def _seasonal_naive(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    preds = []
    for row in test.itertuples(index=False):
        hist = train[train["week_of_year"] == row.week_of_year]["demand"]
        if hist.empty:
            hist = train["demand"]
        preds.append(float(hist.mean()))
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


def _attach_fitted(panel: pd.DataFrame, models: dict) -> pd.DataFrame:
    out = panel.copy()
    out["fitted"] = models["fitted"]
    return out


def _project_horizon(panel: pd.DataFrame, models: dict, horizon_weeks: int) -> dict:
    last = panel.iloc[-1]
    last_week = int(last["week"])
    history = panel["demand"].to_numpy(dtype=float).tolist()
    rows = []
    promo = float(panel["promo_depth"].tail(8).mean())
    price = float(panel["price_index"].tail(8).mean())
    temp_hist = panel[["week_of_year", "temperature"]].copy()
    for step in range(1, horizon_weeks + 1):
        week = last_week + step
        wow = ((week - 1) % 52) + 1
        holiday = 1.0 if wow in {1, 6, 42, 47, 51} else 0.0
        payday = 1.0 if week % 2 == 0 else 0.0
        temp_same = temp_hist[temp_hist["week_of_year"] == wow]["temperature"]
        temp = float(temp_same.mean()) if len(temp_same) else float(panel["temperature"].tail(8).mean())
        lag_1 = history[-1]
        lag_52 = history[-52] if len(history) >= 52 else float(np.mean(history))
        feat = pd.DataFrame(
            [
                {
                    "lag_1": lag_1,
                    "lag_52": lag_52,
                    "week": float(week),
                    "sin1": np.sin(2 * np.pi * wow / 52.0),
                    "cos1": np.cos(2 * np.pi * wow / 52.0),
                    "sin2": np.sin(4 * np.pi * wow / 52.0),
                    "cos2": np.cos(4 * np.pi * wow / 52.0),
                    "holiday": holiday,
                    "payday": payday,
                    "promo_depth": promo,
                    "price_index": price,
                    "temperature": temp,
                }
            ]
        )
        pred = float(models["ridge"].predict(models["scaler"].transform(feat[FEATURE_COLS].to_numpy(dtype=float)))[0])
        pred = max(pred, 180.0)
        history.append(pred)
        sigma = models["sigma"] * (1.0 + 0.04 * step)
        rows.append(
            {
                "week": week,
                "week_of_year": wow,
                "pred": pred,
                "lo80": pred - 1.28 * sigma,
                "hi80": pred + 1.28 * sigma,
                "lo90": pred - 1.64 * sigma,
                "hi90": pred + 1.64 * sigma,
                "holiday": holiday,
                "payday": payday,
                "promo_depth": promo,
                "price_index": price,
            }
        )
    return {
        "rows": rows,
        "week": [r["week"] for r in rows],
        "pred": [r["pred"] for r in rows],
        "lo80": [r["lo80"] for r in rows],
        "hi80": [r["hi80"] for r in rows],
        "lo90": [r["lo90"] for r in rows],
        "hi90": [r["hi90"] for r in rows],
    }


def _diagnose(panel: pd.DataFrame, models: dict, split: int) -> dict:
    resid = panel["residual"].to_numpy(dtype=float)
    sigma = float(np.std(resid, ddof=1))
    z = resid / max(sigma, 1e-6)
    anomalies = []
    for i, row in panel.iterrows():
        if abs(float(z[i])) >= 2.5:
            reason = "ops / weather shock" if abs(float(z[i])) >= 3.2 else "unusual residual week"
            if row["holiday"] >= 1 and float(z[i]) > 0:
                reason = "holiday demand above seasonal"
            if row["promo_depth"] > 0.18 and float(z[i]) < 0:
                reason = "promo week missed — depth did not deliver"
            anomalies.append(
                {
                    "week": int(row["week"]),
                    "demand": float(row["demand"]),
                    "residual": float(row["residual"]),
                    "z": float(z[i]),
                    "reason": reason,
                }
            )

    dw = _durbin_watson(resid)
    lag1 = float(np.corrcoef(resid[1:], resid[:-1])[0, 1]) if len(resid) > 3 else 0.0
    shift_week, shift_size = _level_shift(panel["demand"].to_numpy(dtype=float))

    holdout = panel[panel["week"] >= split]
    pred = models["test_pred"]["ensemble"]
    actual = models["test_pred"]["actual"]
    sig = models["sigma"]
    covered = float(np.mean((actual >= pred - 1.28 * sig) & (actual <= pred + 1.28 * sig)) * 100.0)

    recent = panel.tail(26)
    prior = panel.iloc[-52:-26] if len(panel) >= 52 else panel.head(26)
    recent_slope = _slope(recent["week"].to_numpy(), recent["trend"].to_numpy())
    prior_slope = _slope(prior["week"].to_numpy(), prior["trend"].to_numpy())
    recent_yoy = float(np.nanmean(recent["yoy"].to_numpy())) if recent["yoy"].notna().any() else 0.0
    prior_yoy = float(np.nanmean(prior["yoy"].to_numpy())) if prior["yoy"].notna().any() else 0.0

    promo_mask = panel["promo_depth"] > 0.16
    promo_resid = float(panel.loc[promo_mask, "residual"].mean()) if promo_mask.any() else 0.0
    quiet_resid = float(panel.loc[~promo_mask, "residual"].mean()) if (~promo_mask).any() else 0.0

    return {
        "durbin_watson": dw,
        "lag1_acf": lag1,
        "residual_sigma": sigma,
        "level_shift_week": shift_week,
        "level_shift_size": shift_size,
        "holdout_coverage_80": covered,
        "recent_yoy": recent_yoy * 100.0,
        "prior_yoy": prior_yoy * 100.0,
        "trend_slope_recent": recent_slope,
        "trend_slope_prior": prior_slope,
        "acceleration": recent_slope - prior_slope,
        "promo_residual": promo_resid,
        "quiet_residual": quiet_resid,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies[:12],
        "true_shift_week": int(panel["true_shift_week"].iloc[0]),
    }


def _durbin_watson(resid: np.ndarray) -> float:
    resid = np.asarray(resid, dtype=float)
    if len(resid) < 3:
        return 2.0
    return float(np.sum(np.diff(resid) ** 2) / np.maximum(np.sum(resid**2), 1e-8))


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3 or np.std(x) < 1e-8:
        return 0.0
    beta = np.polyfit(x, y, 1)
    return float(beta[0])


def _level_shift(y: np.ndarray) -> tuple[int, float]:
    y = np.asarray(y, dtype=float)
    best_t, best_stat = 26, 0.0
    for t in range(26, len(y) - 26):
        left = y[:t]
        right = y[t:]
        se = np.sqrt(left.var() / len(left) + right.var() / max(len(right), 1))
        stat = abs(right.mean() - left.mean()) / max(se, 1e-6)
        if stat > best_stat:
            best_stat = stat
            best_t = t + 1
    size = float(y[best_t - 1 :].mean() - y[: best_t - 1].mean())
    return int(best_t), size


def _plan(panel: pd.DataFrame, horizon: dict, diagnostics: dict, horizon_weeks: int) -> dict:
    last_13 = float(panel["demand"].tail(13).mean())
    next_13 = float(np.mean(horizon["pred"]))
    gap_pct = 100.0 * (next_13 - last_13) / max(last_13, 1e-6)
    ly = panel["demand"].tail(13 + 52).head(13)
    vs_ly = 100.0 * (next_13 - float(ly.mean())) / max(float(ly.mean()), 1e-6) if len(ly) == 13 else gap_pct

    slope = diagnostics["trend_slope_recent"]
    if gap_pct >= 3.0 and slope > 0.15:
        outlook, gate = "Demand is accelerating. Lock the next quarter above the last 13-week run-rate.", "Grow"
    elif gap_pct <= -3.0 or slope < -0.15:
        outlook, gate = "Demand is softening. Do not lock last year's volume without a price or promo offset.", "Cut"
    else:
        outlook, gate = "Demand is steady. Hold the current run-rate and spend the week on diagnostics, not a new plan.", "Hold"

    actions = [
        {
            "title": "Lock next-quarter volume at the p50 forecast",
            "detail": f"Average weekly demand over the next {horizon_weeks} weeks is {next_13:,.0f} versus {last_13:,.0f} in the last 13 weeks ({gap_pct:+.1f}%). Use the 80 percent band for capacity, not the point.",
            "gate": gate,
        },
        {
            "title": "Read the residual before you add promo",
            "detail": (
                "Promo-week residual is "
                f"{diagnostics['promo_residual']:+.1f} versus {diagnostics['quiet_residual']:+.1f} on quiet weeks. "
                + (
                    "Depth is not delivering — raising intro codes will not fix a soft trend."
                    if diagnostics["promo_residual"] < -8
                    else "Promo weeks are doing their job. Keep depth inside the recent range."
                )
            ),
            "gate": "Watch" if diagnostics["promo_residual"] < -8 else "Hold",
        },
        {
            "title": "Treat the detected level shift as a regime, not noise",
            "detail": (
                f"A mean break of {diagnostics['level_shift_size']:+.1f} units is estimated around week {diagnostics['level_shift_week']} "
                f"(data generating process planted one near week {diagnostics['true_shift_week']}). "
                "Do not average through it when you set the annual plan."
            ),
            "gate": "Watch" if abs(diagnostics["level_shift_size"]) > 25 else "Hold",
        },
        {
            "title": "Capacity and inventory from the forecast band",
            "detail": (
                f"Week {horizon['week'][-1]} 80 percent high is {horizon['hi80'][-1]:,.0f}; "
                f"80 percent low is {horizon['lo80'][-1]:,.0f}. "
                + (
                    "Fulfillment should pre-book the high band."
                    if horizon["hi80"][-1] > last_13 * 1.12
                    else "The high band is close to the recent run-rate — do not add a shift."
                )
            ),
            "gate": "Grow" if horizon["hi80"][-1] > last_13 * 1.12 else "Hold",
        },
    ]
    if diagnostics["anomaly_count"]:
        top = diagnostics["anomalies"][0]
        actions.append(
            {
                "title": f"Investigate week {top['week']} before you rewrite the model",
                "detail": f"Residual z = {top['z']:+.2f}. {top['reason'].capitalize()}. Ops and weather come before a new seasonal term.",
                "gate": "Watch",
            }
        )

    decisions = [
        {
            "horizon": f"Next {horizon_weeks} weeks vs last 13",
            "forecast": next_13,
            "baseline": last_13,
            "delta_pct": gap_pct,
            "decision": gate,
        },
        {
            "horizon": f"Next {horizon_weeks} weeks vs same weeks last year",
            "forecast": next_13,
            "baseline": float(ly.mean()) if len(ly) == 13 else last_13,
            "delta_pct": vs_ly,
            "decision": "Grow" if vs_ly > 2 else ("Cut" if vs_ly < -2 else "Hold"),
        },
        {
            "horizon": "Recent 26-week trend slope (units / week)",
            "forecast": diagnostics["trend_slope_recent"],
            "baseline": diagnostics["trend_slope_prior"],
            "delta_pct": diagnostics["acceleration"],
            "decision": "Grow" if diagnostics["acceleration"] > 0.1 else ("Cut" if diagnostics["acceleration"] < -0.1 else "Hold"),
        },
    ]
    return {
        "outlook": outlook,
        "gate": gate,
        "last_13": last_13,
        "next_13": next_13,
        "gap_pct": gap_pct,
        "vs_ly": vs_ly,
        "actions": actions,
        "decisions": decisions,
    }


def _payload(
    panel: pd.DataFrame,
    models: dict,
    horizon: dict,
    diagnostics: dict,
    planning: dict,
    split: int,
    holdout_weeks: int,
    horizon_weeks: int,
) -> dict:
    yoy_plot = [None if np.isnan(v) else float(v * 100.0) for v in panel["yoy"].to_numpy()]
    holdout_week = [int(w) for w in models["test_pred"]["week"]]
    holdout_pred = [float(v) for v in models["test_pred"]["ensemble"]]
    sig = models["sigma"]
    winner = models["winner"]
    win = models["scores"][winner]
    story = (
        f"{len(panel)} weekly observations, last {holdout_weeks} held out, {horizon_weeks} weeks projected. "
        f"Ensemble weighted absolute percent error is {models['scores']['ensemble']['wape']:.1f}% "
        f"(winner: {winner.replace('_', ' ')}). "
        f"{planning['outlook']} Year-over-year in the last 26 weeks is {diagnostics['recent_yoy']:+.1f}%."
    )
    return {
        "story": story,
        "metrics": {
            "n_weeks": int(len(panel)),
            "holdout_weeks": int(holdout_weeks),
            "horizon_weeks": int(horizon_weeks),
            "split_week": int(split),
            "winner": winner,
            "ensemble_wape": models["scores"]["ensemble"]["wape"],
            "ensemble_mape": models["scores"]["ensemble"]["mape"],
            "ensemble_r2": models["scores"]["ensemble"]["r2"],
            "ensemble_bias": models["scores"]["ensemble"]["bias"],
            "best_wape": win["wape"],
            "recent_yoy": diagnostics["recent_yoy"],
            "gap_pct": planning["gap_pct"],
            "outlook_gate": planning["gate"],
            "anomaly_count": diagnostics["anomaly_count"],
            "durbin_watson": diagnostics["durbin_watson"],
            "holdout_coverage_80": diagnostics["holdout_coverage_80"],
        },
        "scores": models["scores"],
        "weights": models["weights"],
        "coefs": models["coefs"],
        "drivers": models["drivers"],
        "diagnostics": diagnostics,
        "planning": planning,
        "series": {
            "week": [int(v) for v in panel["week"]],
            "demand": [float(v) for v in panel["demand"]],
            "trend": [float(v) for v in panel["trend"]],
            "seasonal": [float(v) for v in panel["seasonal"]],
            "residual": [float(v) for v in panel["residual"]],
            "fitted": [float(v) for v in panel["fitted"]],
            "yoy": yoy_plot,
            "promo_depth": [float(v) for v in panel["promo_depth"]],
            "price_index": [float(v) for v in panel["price_index"]],
            "holiday": [int(v) for v in panel["holiday"]],
            "split_week": int(split),
        },
        "holdout": {
            "week": holdout_week,
            "actual": [float(v) for v in models["test_pred"]["actual"]],
            "pred": holdout_pred,
            "lo80": [float(v - 1.28 * sig) for v in holdout_pred],
            "hi80": [float(v + 1.28 * sig) for v in holdout_pred],
        },
        "horizon": {
            "week": horizon["week"],
            "pred": [float(v) for v in horizon["pred"]],
            "lo80": [float(v) for v in horizon["lo80"]],
            "hi80": [float(v) for v in horizon["hi80"]],
            "lo90": [float(v) for v in horizon["lo90"]],
            "hi90": [float(v) for v in horizon["hi90"]],
        },
    }
