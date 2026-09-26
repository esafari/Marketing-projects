"""Bootstrap and hypothesis tests for incremental MMM recommendations.

Residual and moving-block bootstraps give percentile CIs on coefficients,
iROAS, and the profit gap versus a last-touch mix. Tests tell stakeholders
whether a channel is distinguishable from zero, whether the next dollar
clears a 1.0 iROAS hurdle, and whether reallocating away from last-touch
is a fluke.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tools.sm_exceptions import SingularMatrixWarning
from hierarchical_mmm_engine.attribution import MEDIA, _simulate
from hierarchical_mmm_engine.transforms import steady_state_transform, steady_state_transform_derivative

FEATURE_BASE = ["season", "holiday", "log_price"]


def run_uncertainty_suite(
    n_weeks: int = 156,
    n_boot: int = 280,
    block_len: int = 8,
    seed: int = 42,
    media_budget: float = 140.0,
) -> dict:
    rng = np.random.default_rng(int(seed))
    n_weeks = int(np.clip(n_weeks, 80, 260))
    n_boot = int(np.clip(n_boot, 80, 800))
    block_len = int(np.clip(block_len, 4, 20))
    frame = _simulate(rng, n_weeks)
    cols = [*FEATURE_BASE, *[f"trans_{n}" for n in MEDIA]]
    x = sm.add_constant(frame[cols], has_constant="add")
    y = frame["sales"].to_numpy(dtype=float)
    ols = sm.OLS(y, x).fit()
    point = {str(k): float(v) for k, v in ols.params.items()}
    classical = _classical_tests(ols)

    resid = np.asarray(ols.resid, dtype=float)
    fitted = np.asarray(ols.fittedvalues, dtype=float)
    residual_draws = _residual_bootstrap(rng, x, fitted, resid, n_boot)
    block_draws = _block_bootstrap(rng, x, y, n_boot, block_len)
    if residual_draws.shape[0] < 40 or block_draws.shape[0] < 40:
        raise RuntimeError("Too few valid bootstrap draws; increase weeks or reduce block length.")
    mean_spend = {name: float(frame[f"spend_{name}"].mean()) for name in MEDIA}

    residual_stats = _summarize_draws(residual_draws, point, mean_spend, media_budget)
    block_stats = _summarize_draws(block_draws, point, mean_spend, media_budget)
    tests = _hypothesis_tests(residual_draws, point, classical, mean_spend)
    gates = _recommendation_gates(residual_stats["parameters"], residual_stats["iroas"])
    perm_price = _permutation_price(rng, x, y, point.get("log_price", 0.0), n_perm=min(200, n_boot))

    return {
        "metrics": {
            "n_weeks": n_weeks,
            "n_boot": n_boot,
            "block_len": block_len,
            "r2": float(ols.rsquared),
            "ship": sum(1 for g in gates if g["gate"] == "Ship"),
            "watch": sum(1 for g in gates if g["gate"] == "Watch"),
            "kill": sum(1 for g in gates if g["gate"] == "Kill"),
            "profit_lift_p": next(t["p_value"] for t in tests if t["id"] == "profit_lift"),
            "price_perm_p": perm_price["p_value"],
            "n_residual_ok": int(residual_draws.shape[0]),
            "n_block_ok": int(block_draws.shape[0]),
        },
        "classical": classical,
        "residual": residual_stats,
        "block": block_stats,
        "tests": tests,
        "gates": gates,
        "permutation_price": perm_price,
        "histograms": {
            name: _hist(residual_draws[:, i])
            for i, name in enumerate(["const", *cols])
            if name in {"log_price", *[f"trans_{n}" for n in MEDIA]}
        },
        "point": point,
    }


def _classical_tests(ols) -> list[dict]:
    rows = []
    for name in ols.params.index:
        rows.append(
            {
                "parameter": str(name),
                "estimate": float(ols.params[name]),
                "std_err": float(ols.bse[name]),
                "t_stat": float(ols.tvalues[name]),
                "p_value": float(ols.pvalues[name]),
                "ci_lo": float(ols.conf_int().loc[name, 0]),
                "ci_hi": float(ols.conf_int().loc[name, 1]),
            }
        )
    return rows


def _fit_params(y_star: np.ndarray, x) -> np.ndarray | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SingularMatrixWarning)
            fit = sm.OLS(y_star, x).fit()
    except Exception:
        return None
    params = np.asarray(fit.params, dtype=float)
    if params.size == 0 or not np.all(np.isfinite(params)):
        return None
    if float(getattr(fit, "df_resid", 0.0)) <= 0:
        return None
    if float(getattr(fit, "condition_number", 0.0)) > 1e12:
        return None
    return params


def _residual_bootstrap(rng: np.random.Generator, x: pd.DataFrame, fitted: np.ndarray, resid: np.ndarray, n_boot: int) -> np.ndarray:
    draws = []
    attempts = 0
    limit = n_boot * 4
    while len(draws) < n_boot and attempts < limit:
        attempts += 1
        y_star = fitted + rng.choice(resid, size=len(resid), replace=True)
        params = _fit_params(y_star, x)
        if params is not None:
            draws.append(params)
    return np.vstack(draws) if draws else np.zeros((0, x.shape[1]))


def _block_bootstrap(rng: np.random.Generator, x: pd.DataFrame, y: np.ndarray, n_boot: int, block_len: int) -> np.ndarray:
    n = len(y)
    starts = np.arange(0, max(1, n - block_len + 1))
    draws = []
    x_values = x.to_numpy(dtype=float)
    attempts = 0
    limit = n_boot * 6
    while len(draws) < n_boot and attempts < limit:
        attempts += 1
        idx = []
        while len(idx) < n:
            start = int(rng.choice(starts))
            idx.extend(range(start, min(start + block_len, n)))
        idx = np.asarray(idx[:n])
        params = _fit_params(y[idx], x_values[idx])
        if params is not None:
            draws.append(params)
    return np.vstack(draws) if draws else np.zeros((0, x.shape[1]))


def _summarize_draws(draws: np.ndarray, point: dict[str, float], mean_spend: dict[str, float], budget: float) -> dict:
    names = list(point)
    parameters = []
    for i, name in enumerate(names):
        col = draws[:, i]
        parameters.append(_interval(name, float(point[name]), col))
    iroas_rows = []
    iroas_draws = {}
    for name, spec in MEDIA.items():
        key = f"trans_{name}"
        idx = names.index(key)
        dtrans = steady_state_transform_derivative(mean_spend[name], spec["decay"], spec["k"], 1.0)
        series = draws[:, idx] * dtrans
        iroas_draws[name] = series
        iroas_rows.append(_interval(name, float(point[key] * dtrans), series))
    profit_point, profit_series = _profit_gap_draws(draws, names, point, budget)
    return {
        "parameters": parameters,
        "iroas": iroas_rows,
        "profit_gap": _interval("incremental vs last-touch profit", profit_point, profit_series),
        "iroas_draws_p10": {k: float(np.quantile(v, 0.10)) for k, v in iroas_draws.items()},
        "iroas_draws_p90": {k: float(np.quantile(v, 0.90)) for k, v in iroas_draws.items()},
    }


def _profit_gap_draws(
    draws: np.ndarray,
    names: list[str],
    point: dict[str, float],
    budget: float,
) -> tuple[float, np.ndarray]:
    last_share = np.array([MEDIA[n]["touch"] for n in MEDIA], dtype=float)
    last_share = last_share / last_share.sum()
    last_spend = last_share * budget
    even = np.full(len(MEDIA), budget / len(MEDIA))

    def profit(betas: dict[str, float], spend: np.ndarray) -> float:
        sales = 0.0
        for i, name in enumerate(MEDIA):
            spec = MEDIA[name]
            sales += betas.get(f"trans_{name}", 0.0) * steady_state_transform(float(spend[i]), spec["decay"], spec["k"], 1.0)
        return 0.38 * sales - float(np.sum(spend))

    point_gap = profit(point, even) - profit(point, last_spend)
    gaps = []
    for row in draws:
        betas = {names[i]: float(row[i]) for i in range(len(names))}
        gaps.append(profit(betas, even) - profit(betas, last_spend))
    return float(point_gap), np.asarray(gaps, dtype=float)


def _interval(name: str, estimate: float, draws: np.ndarray) -> dict:
    return {
        "name": name,
        "estimate": estimate,
        "mean": float(np.mean(draws)),
        "std": float(np.std(draws, ddof=1)),
        "p05": float(np.quantile(draws, 0.05)),
        "p10": float(np.quantile(draws, 0.10)),
        "p50": float(np.quantile(draws, 0.50)),
        "p90": float(np.quantile(draws, 0.90)),
        "p95": float(np.quantile(draws, 0.95)),
        "hist": _hist(draws),
    }


def _hist(draws: np.ndarray) -> dict:
    counts, edges = np.histogram(draws, bins=16)
    return {"counts": counts.astype(int).tolist(), "edges": edges.astype(float).tolist()}


def _hypothesis_tests(
    draws: np.ndarray,
    point: dict[str, float],
    classical: list[dict],
    mean_spend: dict[str, float],
) -> list[dict]:
    names = list(point)
    tests = []
    for name in MEDIA:
        key = f"trans_{name}"
        idx = names.index(key)
        series = draws[:, idx]
        # H0: beta <= 0
        p_boot = float(np.mean(series <= 0.0))
        classic = next(r for r in classical if r["parameter"] == key)
        tests.append(
            {
                "id": f"beta_{name}",
                "hypothesis": f"H0: {name} incremental beta ≤ 0",
                "alternative": "Channel has a positive incremental effect",
                "estimate": float(point[key]),
                "p_value": p_boot,
                "classical_p": classic["p_value"],
                "reject_05": p_boot < 0.05,
                "method": "Residual bootstrap (one-sided)",
            }
        )
        dtrans = steady_state_transform_derivative(mean_spend[name], MEDIA[name]["decay"], MEDIA[name]["k"], 1.0)
        iroas = series * dtrans
        p_hurdle = float(np.mean(iroas <= 1.0))
        tests.append(
            {
                "id": f"iroas_{name}",
                "hypothesis": f"H0: {name} iROAS ≤ 1.0",
                "alternative": "The next $1k earns its keep",
                "estimate": float(point[key] * dtrans),
                "p_value": p_hurdle,
                "classical_p": None,
                "reject_05": p_hurdle < 0.05,
                "method": "Residual bootstrap (one-sided hurdle)",
            }
        )
    # Price: H0 beta_P = 0
    idx_p = names.index("log_price")
    series_p = draws[:, idx_p]
    p_price = 2.0 * min(float(np.mean(series_p >= 0.0)), float(np.mean(series_p <= 0.0)))
    classic_p = next(r for r in classical if r["parameter"] == "log_price")
    tests.append(
        {
            "id": "price",
            "hypothesis": "H0: price coefficient = 0",
            "alternative": "Price moves sales",
            "estimate": float(point["log_price"]),
            "p_value": min(p_price, 1.0),
            "classical_p": classic_p["p_value"],
            "reject_05": p_price < 0.05,
            "method": "Residual bootstrap (two-sided)",
        }
    )
    # TV iROAS - Search iROAS
    tv = draws[:, names.index("trans_TV")] * steady_state_transform_derivative(
        mean_spend["TV"], MEDIA["TV"]["decay"], MEDIA["TV"]["k"], 1.0
    )
    se = draws[:, names.index("trans_Search")] * steady_state_transform_derivative(
        mean_spend["Search"], MEDIA["Search"]["decay"], MEDIA["Search"]["k"], 1.0
    )
    diff = tv - se
    p_diff = 2.0 * min(float(np.mean(diff >= 0.0)), float(np.mean(diff <= 0.0)))
    tests.append(
        {
            "id": "tv_vs_search",
            "hypothesis": "H0: iROAS_TV − iROAS_Search = 0",
            "alternative": "TV and Search have different next-dollar returns",
            "estimate": float(np.mean(diff)),
            "p_value": min(p_diff, 1.0),
            "classical_p": None,
            "reject_05": p_diff < 0.05,
            "method": "Residual bootstrap (two-sided contrast)",
        }
    )
    _, profit_series = _profit_gap_draws(draws, names, point, 140.0)
    p_profit = float(np.mean(profit_series <= 0.0))
    tests.append(
        {
            "id": "profit_lift",
            "hypothesis": "H0: incremental mix profit − last-touch profit ≤ 0",
            "alternative": "Reallocation beats the last-touch mix",
            "estimate": float(np.mean(profit_series)),
            "p_value": p_profit,
            "classical_p": None,
            "reject_05": p_profit < 0.05,
            "method": "Residual bootstrap (one-sided)",
        }
    )
    return tests


def _recommendation_gates(parameters: list[dict], iroas: list[dict]) -> list[dict]:
    gates = []
    for row in iroas:
        beta = next(p for p in parameters if p["name"] == f"trans_{row['name']}")
        if beta["p05"] > 0 and row["p10"] > 1.0:
            gate = "Ship"
            note = "90% CI for beta is above 0 and 80% CI for iROAS is above 1. Safe to recommend more spend."
        elif beta["p95"] < 0 or row["p90"] < 1.0:
            gate = "Kill"
            note = "Upper tail is still unprofitable or the effect is negative. Do not add budget."
        else:
            gate = "Watch"
            note = "CI crosses a hurdle. Hold the lock, run a geo test, or shrink toward a prior."
        gates.append({"name": row["name"], "gate": gate, "note": note, "iROAS": row["estimate"], "iROAS_p10": row["p10"], "iROAS_p90": row["p90"]})
    price = next(p for p in parameters if p["name"] == "log_price")
    if price["p95"] < 0:
        gate = "Ship"
        note = "Price is incrementally negative on units with a CI that excludes 0. Use it as a lever, not a leftover."
    elif price["p05"] > 0:
        gate = "Watch"
        note = "CI says higher price raises units — usually a specification problem."
    else:
        gate = "Watch"
        note = "Price effect includes 0. Do not brief a price move from this model alone."
    gates.append({"name": "Price", "gate": gate, "note": note, "iROAS": price["estimate"], "iROAS_p10": price["p10"], "iROAS_p90": price["p90"]})
    return gates


def _permutation_price(rng: np.random.Generator, x: pd.DataFrame, y: np.ndarray, observed: float, n_perm: int) -> dict:
    x_work = x.copy()
    null = []
    price = x_work["log_price"].to_numpy(dtype=float)
    for _ in range(n_perm):
        x_work["log_price"] = rng.permutation(price)
        fit = sm.OLS(y, x_work).fit()
        null.append(float(fit.params["log_price"]))
    null_arr = np.asarray(null, dtype=float)
    p_value = float(np.mean(np.abs(null_arr) >= abs(observed)))
    return {
        "observed": float(observed),
        "p_value": p_value,
        "null_p95": float(np.quantile(np.abs(null_arr), 0.95)),
        "hist": _hist(null_arr),
        "reject_05": p_value < 0.05,
    }
