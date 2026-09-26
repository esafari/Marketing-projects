"""Scenario planning for alternative media investment and promotional strategies.

Compares locked, harvest, brand, promo-led, risk-off, and ROI-optimal plans on
the same envelopes. Each plan is scored for incremental sales, ROI, profit, and
a downside band if lifts come in at 70% of the planning estimate.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from hierarchical_mmm_engine.transforms import hill_saturation, steady_state_transform

MEDIA = {
    "TV": {"decay": 0.62, "k": 72.0, "beta": 210.0, "last": 46.0, "lo": 10.0, "hi": 80.0},
    "Social": {"decay": 0.28, "k": 38.0, "beta": 105.0, "last": 34.0, "lo": 8.0, "hi": 60.0},
    "Search": {"decay": 0.08, "k": 44.0, "beta": 155.0, "last": 40.0, "lo": 12.0, "hi": 75.0},
    "Email": {"decay": 0.15, "k": 16.0, "beta": 48.0, "last": 12.0, "lo": 4.0, "hi": 28.0},
}

PROMO = {
    "Grocery": {"beta": 1.35, "k": 55.0, "last": 42.0, "lo": 8.0, "hi": 90.0, "margin": 0.32},
    "Mass": {"beta": 1.55, "k": 48.0, "last": 36.0, "lo": 6.0, "hi": 80.0, "margin": 0.24},
    "Drug": {"beta": 1.15, "k": 22.0, "last": 14.0, "lo": 4.0, "hi": 40.0, "margin": 0.38},
    "E-comm": {"beta": 1.80, "k": 28.0, "last": 18.0, "lo": 4.0, "hi": 50.0, "margin": 0.36},
}

MEDIA_NAMES = list(MEDIA)
PROMO_NAMES = list(PROMO)
UNIT_VALUE = 4.2
HORIZON = 13


def run_scenario_framework(
    media_budget: float = 140.0,
    promo_budget: float = 120.0,
    horizon: int = 13,
    downside: float = 0.70,
    upside: float = 1.25,
    custom: dict | None = None,
    seed: int = 42,
) -> dict:
    """Score named strategies plus an optional custom mix on shared envelopes."""
    rng = np.random.default_rng(int(seed))
    media_budget = float(np.clip(media_budget, 40.0, 400.0))
    promo_budget = float(np.clip(promo_budget, 20.0, 400.0))
    horizon = int(np.clip(horizon, 4, 26))
    last_media = _scale_last(MEDIA, media_budget)
    last_promo = _scale_last(PROMO, promo_budget)
    plans = {
        "Status quo": (last_media, last_promo),
        "Harvest": (
            _mix(media_budget, {"TV": 0.14, "Social": 0.16, "Search": 0.58, "Email": 0.12}, MEDIA_NAMES),
            _mix(promo_budget, {"Grocery": 0.28, "Mass": 0.42, "Drug": 0.10, "E-comm": 0.20}, PROMO_NAMES),
        ),
        "Brand-led": (
            _mix(media_budget, {"TV": 0.46, "Social": 0.26, "Search": 0.18, "Email": 0.10}, MEDIA_NAMES),
            _mix(promo_budget, {"Grocery": 0.40, "Mass": 0.22, "Drug": 0.18, "E-comm": 0.20}, PROMO_NAMES),
        ),
        "Promo-led": (
            _mix(media_budget * 0.72, {"TV": 0.28, "Social": 0.22, "Search": 0.38, "Email": 0.12}, MEDIA_NAMES),
            _mix(promo_budget + media_budget * 0.28, {"Grocery": 0.34, "Mass": 0.30, "Drug": 0.12, "E-comm": 0.24}, PROMO_NAMES),
        ),
        "Risk-off": (
            _mix(media_budget, {"TV": 0.30, "Social": 0.25, "Search": 0.30, "Email": 0.15}, MEDIA_NAMES),
            _mix(promo_budget, {"Grocery": 0.30, "Mass": 0.28, "Drug": 0.20, "E-comm": 0.22}, PROMO_NAMES),
        ),
    }
    opt_media, opt_promo = _optimize(media_budget, promo_budget)
    plans["ROI-optimal"] = (opt_media, opt_promo)
    if custom:
        plans["Custom"] = (
            _mix(media_budget, custom.get("media") or {}, MEDIA_NAMES),
            _mix(promo_budget, custom.get("promo") or {}, PROMO_NAMES),
        )

    scored = []
    for name, (media, promo) in plans.items():
        scored.append(_score_plan(name, media, promo, horizon, downside, upside, rng))
    scored = sorted(scored, key=lambda row: row["profit"], reverse=True)
    frontier = [{"name": r["name"], "investment": r["investment"], "roi": r["roi"], "profit": r["profit"], "incremental": r["incremental"]} for r in scored]
    best = scored[0]
    status = next(r for r in scored if r["name"] == "Status quo")
    return {
        "metrics": {
            "media_budget": media_budget,
            "promo_budget": promo_budget,
            "horizon": horizon,
            "downside": downside,
            "upside": upside,
            "best": best["name"],
            "best_profit": best["profit"],
            "best_roi": best["roi"],
            "status_profit": status["profit"],
            "status_roi": status["roi"],
            "profit_vs_status": best["profit"] - status["profit"],
            "roi_vs_status": best["roi"] - status["roi"],
        },
        "plans": scored,
        "frontier": frontier,
        "levers": {
            "media": MEDIA_NAMES,
            "promo": PROMO_NAMES,
            "last_media": last_media,
            "last_promo": last_promo,
        },
    }


def _scale_last(spec: dict, budget: float) -> dict[str, float]:
    raw = {name: float(item["last"]) for name, item in spec.items()}
    total = sum(raw.values()) or 1.0
    return {name: budget * value / total for name, value in raw.items()}


def _mix(budget: float, shares: dict[str, float], catalog: list[str]) -> dict[str, float]:
    weights = {name: max(float(shares.get(name, 0.0)), 0.0) for name in catalog}
    if sum(weights.values()) <= 0:
        weights = {name: 1.0 for name in catalog}
    total = sum(weights.values())
    return {name: budget * weights[name] / total for name in catalog}


def _media_sales(spend: dict[str, float]) -> float:
    total = 0.0
    for name, spec in MEDIA.items():
        total += spec["beta"] * steady_state_transform(float(spend.get(name, 0.0)), spec["decay"], spec["k"], 1.0)
    return total


def _promo_units(spend: dict[str, float]) -> float:
    total = 0.0
    for name, spec in PROMO.items():
        sat = float(hill_saturation(float(spend.get(name, 0.0)), k=spec["k"], s=1.0))
        total += spec["beta"] * sat * 90.0
    return total


def _profit(media: dict[str, float], promo: dict[str, float], lift_scale: float = 1.0) -> tuple[float, float, float]:
    media_inc = _media_sales(media) * lift_scale
    promo_inc = _promo_units(promo) * lift_scale
    incremental = media_inc + promo_inc * UNIT_VALUE
    investment = sum(media.values()) + sum(promo.values())
    profit = 0.36 * incremental - investment
    return incremental, investment, profit


def _score_plan(
    name: str,
    media: dict[str, float],
    promo: dict[str, float],
    horizon: int,
    downside: float,
    upside: float,
    rng: np.random.Generator,
) -> dict:
    inc, invest, profit = _profit(media, promo, 1.0)
    lo_inc, _, lo_profit = _profit(media, promo, downside)
    hi_inc, _, hi_profit = _profit(media, promo, upside)
    draws = []
    for _ in range(80):
        scale = float(rng.normal(1.0, 0.12))
        draws.append(_profit(media, promo, scale)[2])
    roi = profit / invest if invest else 0.0
    media_share = sum(media.values()) / invest if invest else 0.0
    hhi = _hhi(media) * 0.5 + _hhi(promo) * 0.5
    return {
        "name": name,
        "media": {k: float(v) for k, v in media.items()},
        "promo": {k: float(v) for k, v in promo.items()},
        "incremental": float(inc * horizon),
        "investment": float(invest * horizon),
        "profit": float(profit * horizon),
        "roi": float(roi),
        "downside_profit": float(lo_profit * horizon),
        "upside_profit": float(hi_profit * horizon),
        "p10_profit": float(np.quantile(draws, 0.10) * horizon),
        "p90_profit": float(np.quantile(draws, 0.90) * horizon),
        "media_share": float(100.0 * media_share),
        "promo_share": float(100.0 * (1.0 - media_share)),
        "concentration": float(hhi),
        "risk_flag": "High" if hhi > 0.38 or name == "Harvest" else ("Low" if name in {"Risk-off", "Status quo"} else "Medium"),
    }


def _hhi(spend: dict[str, float]) -> float:
    total = sum(spend.values()) or 1.0
    return float(sum((v / total) ** 2 for v in spend.values()))


def _optimize(media_budget: float, promo_budget: float) -> tuple[dict[str, float], dict[str, float]]:
    n_m, n_p = len(MEDIA_NAMES), len(PROMO_NAMES)

    def unpack(x: np.ndarray) -> tuple[dict[str, float], dict[str, float]]:
        media = {MEDIA_NAMES[i]: float(x[i]) for i in range(n_m)}
        promo = {PROMO_NAMES[i]: float(x[n_m + i]) for i in range(n_p)}
        return media, promo

    def objective(x: np.ndarray) -> float:
        media, promo = unpack(x)
        return -_profit(media, promo)[2]

    start = np.array(
        [media_budget / n_m] * n_m + [promo_budget / n_p] * n_p,
        dtype=float,
    )
    bounds = [(MEDIA[n]["lo"], MEDIA[n]["hi"]) for n in MEDIA_NAMES] + [(PROMO[n]["lo"], PROMO[n]["hi"]) for n in PROMO_NAMES]
    constraints = [
        {"type": "eq", "fun": lambda x: np.sum(x[:n_m]) - media_budget},
        {"type": "eq", "fun": lambda x: np.sum(x[n_m:]) - promo_budget},
    ]
    res = minimize(objective, start, method="SLSQP", bounds=bounds, constraints=constraints)
    x = np.asarray(res.x, dtype=float)
    x[:n_m] = x[:n_m] * media_budget / max(x[:n_m].sum(), 1e-6)
    x[n_m:] = x[n_m:] * promo_budget / max(x[n_m:].sum(), 1e-6)
    return unpack(x)
