"""Causal inference versus correlation for commercial decisions.

A geo panel is generated twice: once with a confounded rollout (high-growth
geos get the treatment) and once as a randomized experiment. Observational
OLS, difference-in-differences, and the randomized contrast are scored
against the true lift so stakeholders can see why correlation is not impact.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LinearRegression


def run_causal_scenario(
    n_geos: int = 20,
    n_weeks: int = 80,
    treat_week: int = 48,
    n_treated: int = 6,
    true_lift: float = 0.12,
    seed: int = 42,
) -> dict:
    rng = np.random.default_rng(int(seed))
    n_geos = max(8, int(n_geos))
    n_weeks = max(40, int(n_weeks))
    treat_week = min(max(16, int(treat_week)), n_weeks - 8)
    n_treated = min(max(3, int(n_treated)), n_geos // 2)
    true_lift = float(true_lift)

    confounded = _simulate_panel(rng, n_geos, n_weeks, treat_week, n_treated, true_lift, randomize=False)
    randomized = _simulate_panel(rng, n_geos, n_weeks, treat_week, n_treated, true_lift, randomize=True)

    obs = _observational(confounded, treat_week)
    did_c = _diff_in_diff(confounded, treat_week)
    ols_c = _controlled_ols(confounded, treat_week)
    rct = _diff_in_diff(randomized, treat_week)
    elas_obs = _elasticity_style(confounded, treat_week)
    elas_rct = _elasticity_style(randomized, treat_week)

    methods = [
        {"method": "Observational pre/post (treated geos only)", "estimate": obs, "true": true_lift, "setting": "confounded"},
        {"method": "Difference-in-differences (confounded rollout)", "estimate": did_c, "true": true_lift, "setting": "confounded"},
        {"method": "OLS with geo and week dummies (confounded)", "estimate": ols_c, "true": true_lift, "setting": "confounded"},
        {"method": "Randomized geo experiment (difference-in-differences)", "estimate": rct, "true": true_lift, "setting": "randomized"},
        {"method": "Elasticity-style (observational log change)", "estimate": elas_obs, "true": true_lift, "setting": "confounded"},
        {"method": "Elasticity-style (randomized log change)", "estimate": elas_rct, "true": true_lift, "setting": "randomized"},
    ]
    for row in methods:
        row["bias"] = float(row["estimate"] - true_lift)
        row["abs_bias"] = abs(row["bias"])

    best = min((m for m in methods if m["setting"] == "randomized"), key=lambda r: r["abs_bias"])
    return {
        "metrics": {
            "n_geos": n_geos,
            "n_weeks": n_weeks,
            "treat_week": treat_week,
            "n_treated": n_treated,
            "true_lift": true_lift,
            "obs_bias": float(obs - true_lift),
            "did_confounded_bias": float(did_c - true_lift),
            "rct_bias": float(rct - true_lift),
            "best_method": best["method"],
        },
        "methods": methods,
        "series": {
            "week": list(range(1, n_weeks + 1)),
            "treated_confounded": _weekly_mean(confounded, treated=True),
            "control_confounded": _weekly_mean(confounded, treated=False),
            "treated_rct": _weekly_mean(randomized, treated=True),
            "control_rct": _weekly_mean(randomized, treated=False),
            "treat_week": treat_week,
        },
        "geos": _geo_table(confounded, treat_week),
        "story": (
            f"True lift is {true_lift * 100:.1f}%. Observational pre/post on the confounded rollout "
            f"estimates {obs * 100:.1f}% (bias {(obs - true_lift) * 100:+.1f} points) because faster geos "
            f"were selected for treatment. The randomized experiment recovers {rct * 100:.1f}%."
        ),
    }


def _simulate_panel(
    rng: np.random.Generator,
    n_geos: int,
    n_weeks: int,
    treat_week: int,
    n_treated: int,
    true_lift: float,
    randomize: bool,
) -> list[dict]:
    growth = rng.normal(0.002, 0.0015, n_geos)
    level = rng.normal(180.0, 25.0, n_geos)
    if randomize:
        treated = np.zeros(n_geos, dtype=int)
        treated[rng.choice(n_geos, size=n_treated, replace=False)] = 1
    else:
        # Confound: treat the fastest-growing geos.
        treated = np.zeros(n_geos, dtype=int)
        treated[np.argsort(-growth)[:n_treated]] = 1

    rows = []
    for g in range(n_geos):
        for t in range(1, n_weeks + 1):
            season = 12.0 * np.sin(2 * np.pi * t / 52.0)
            base = level[g] * np.exp(growth[g] * t) + season + rng.normal(0, 6.0)
            post = 1 if t >= treat_week else 0
            y = base * (1.0 + true_lift * treated[g] * post)
            rows.append(
                {
                    "geo": int(g),
                    "week": int(t),
                    "y": float(max(y, 20.0)),
                    "treated": int(treated[g]),
                    "post": int(post),
                    "growth": float(growth[g]),
                }
            )
    return rows


def _observational(rows: list[dict], treat_week: int) -> float:
    treated = [r for r in rows if r["treated"] == 1]
    pre = np.mean([r["y"] for r in treated if r["week"] < treat_week])
    post = np.mean([r["y"] for r in treated if r["week"] >= treat_week])
    return float(post / max(pre, 1e-6) - 1.0)


def _diff_in_diff(rows: list[dict], treat_week: int) -> float:
    def gap(flag: int) -> float:
        part = [r for r in rows if r["treated"] == flag]
        pre = np.mean([r["y"] for r in part if r["week"] < treat_week])
        post = np.mean([r["y"] for r in part if r["week"] >= treat_week])
        return float(np.log(max(post, 1e-6)) - np.log(max(pre, 1e-6)))

    return float(np.exp(gap(1) - gap(0)) - 1.0)


def _controlled_ols(rows: list[dict], treat_week: int) -> float:
    y = np.log(np.array([r["y"] for r in rows], dtype=float))
    treat_post = np.array([r["treated"] * r["post"] for r in rows], dtype=float)
    geos = np.array([r["geo"] for r in rows])
    weeks = np.array([r["week"] for r in rows])
    # Two-way demeaning (geo and week) then OLS on treat×post.
    y_d = _double_demean(y, geos, weeks)
    x_d = _double_demean(treat_post, geos, weeks).reshape(-1, 1)
    model = LinearRegression(fit_intercept=False)
    model.fit(x_d, y_d)
    return float(np.exp(model.coef_[0]) - 1.0)


def _double_demean(v: np.ndarray, geos: np.ndarray, weeks: np.ndarray) -> np.ndarray:
    out = v.astype(float).copy()
    for g in np.unique(geos):
        mask = geos == g
        out[mask] -= out[mask].mean()
    for t in np.unique(weeks):
        mask = weeks == t
        out[mask] -= out[mask].mean()
    return out


def _elasticity_style(rows: list[dict], treat_week: int) -> float:
    """Percent change in treated minus percent change in control — elasticity-style contrast."""
    return _diff_in_diff(rows, treat_week)


def _weekly_mean(rows: list[dict], treated: bool) -> list[float]:
    flag = 1 if treated else 0
    weeks = sorted({r["week"] for r in rows})
    out = []
    for t in weeks:
        vals = [r["y"] for r in rows if r["week"] == t and r["treated"] == flag]
        out.append(float(np.mean(vals)) if vals else 0.0)
    return out


def _geo_table(rows: list[dict], treat_week: int) -> list[dict]:
    geos = sorted({r["geo"] for r in rows})
    table = []
    for g in geos:
        part = [r for r in rows if r["geo"] == g]
        pre = np.mean([r["y"] for r in part if r["week"] < treat_week])
        post = np.mean([r["y"] for r in part if r["week"] >= treat_week])
        table.append(
            {
                "geo": g,
                "treated": int(part[0]["treated"]),
                "growth": float(part[0]["growth"]),
                "pre": float(pre),
                "post": float(post),
                "change_pct": float(post / max(pre, 1e-6) - 1.0) * 100.0,
            }
        )
    table.sort(key=lambda r: (-r["treated"], -r["growth"]))
    return table
