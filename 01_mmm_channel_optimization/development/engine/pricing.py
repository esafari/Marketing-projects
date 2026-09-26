"""Price elasticity plus multi-armed bandit for online pricing.

A log-log elasticity model recovers how units move with price. Thompson
sampling, UCB, and epsilon-greedy then choose among discrete price arms
each period, balancing exploration and exploitation on contribution profit.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LinearRegression

PRICE_ARMS = [92.0, 96.0, 100.0, 104.0, 108.0]
TRUE_ELASTICITY = -1.35
BASE_UNITS = 420.0
LIST_PRICE = 12.0
UNIT_COST = 5.40


def run_pricing_scenario(
    n_rounds: int = 240,
    seed: int = 42,
    epsilon: float = 0.12,
) -> dict:
    rng = np.random.default_rng(int(seed))
    n_rounds = max(40, int(n_rounds))
    epsilon = float(np.clip(epsilon, 0.02, 0.50))
    arms = np.asarray(PRICE_ARMS, dtype=float)
    true_profit = np.array([_expected_profit(p) for p in arms])
    oracle = int(np.argmax(true_profit))

    thompson = _run_policy(rng, n_rounds, "thompson")
    ucb = _run_policy(rng, n_rounds, "ucb")
    greedy = _run_policy(rng, n_rounds, "epsilon", epsilon=epsilon)
    random = _run_policy(rng, n_rounds, "random")

    elas = _fit_elasticity(thompson["price"], thompson["units"])
    return {
        "metrics": {
            "n_rounds": n_rounds,
            "true_elasticity": TRUE_ELASTICITY,
            "est_elasticity": elas["elasticity"],
            "elasticity_r2": elas["r2"],
            "oracle_arm": float(arms[oracle]),
            "oracle_profit": float(true_profit[oracle]),
            "thompson_profit": float(np.sum(thompson["profit"])),
            "ucb_profit": float(np.sum(ucb["profit"])),
            "epsilon_profit": float(np.sum(greedy["profit"])),
            "random_profit": float(np.sum(random["profit"])),
            "thompson_regret": float(np.sum(thompson["regret"])),
            "explore_share": float(np.mean(thompson["explore"])),
            "winner": "thompson"
            if np.sum(thompson["profit"]) >= max(np.sum(ucb["profit"]), np.sum(greedy["profit"]))
            else ("ucb" if np.sum(ucb["profit"]) >= np.sum(greedy["profit"]) else "epsilon-greedy"),
            "epsilon": epsilon,
        },
        "arms": [
            {
                "price": float(p),
                "true_units": float(_expected_units(p)),
                "true_profit": float(true_profit[i]),
                "is_oracle": i == oracle,
                "thompson_pulls": int(np.sum(np.array(thompson["arm"]) == i)),
                "thompson_mean_profit": float(np.mean(np.array(thompson["profit"])[np.array(thompson["arm"]) == i]))
                if np.any(np.array(thompson["arm"]) == i)
                else 0.0,
            }
            for i, p in enumerate(arms)
        ],
        "series": {
            "round": list(range(1, n_rounds + 1)),
            "price": thompson["price"],
            "units": thompson["units"],
            "profit": thompson["profit"],
            "cum_thompson": _cumsum(thompson["profit"]),
            "cum_ucb": _cumsum(ucb["profit"]),
            "cum_epsilon": _cumsum(greedy["profit"]),
            "cum_random": _cumsum(random["profit"]),
            "cum_regret_thompson": _cumsum(thompson["regret"]),
            "cum_regret_ucb": _cumsum(ucb["regret"]),
            "cum_regret_epsilon": _cumsum(greedy["regret"]),
        },
        "elasticity": elas,
        "story": (
            f"{n_rounds} pricing rounds. True elasticity is {TRUE_ELASTICITY:.2f}; "
            f"the log-log fit on Thompson traffic recovers {elas['elasticity']:.2f} "
            f"(R-squared {elas['r2']:.2f}). Oracle list-price index is {arms[oracle]:.0f}. "
            f"Thompson cumulative profit is {np.sum(thompson['profit']):.0f} versus "
            f"{np.sum(random['profit']):.0f} for random prices."
        ),
    }


def _expected_units(price: float) -> float:
    return BASE_UNITS * (price / 100.0) ** TRUE_ELASTICITY


def _unit_margin(price: float) -> float:
    return LIST_PRICE * (price / 100.0) - UNIT_COST


def _expected_profit(price: float) -> float:
    return _expected_units(price) * _unit_margin(price)


def _draw_units(rng: np.random.Generator, price: float) -> float:
    mean = _expected_units(price)
    return float(max(rng.lognormal(np.log(mean), 0.12), 40.0))


def _run_policy(rng: np.random.Generator, n_rounds: int, policy: str, epsilon: float = 0.12) -> dict:
    k = len(PRICE_ARMS)
    pulls = np.zeros(k)
    profit_sum = np.zeros(k)
    profit_sq = np.zeros(k)
    rows = {key: [] for key in ("arm", "price", "units", "profit", "regret", "explore")}
    oracle_p = max(_expected_profit(p) for p in PRICE_ARMS)

    for t in range(n_rounds):
        if policy == "random" or np.min(pulls) == 0:
            arm = int(np.argmin(pulls)) if np.min(pulls) == 0 else int(rng.integers(0, k))
            explore = 1
        elif policy == "thompson":
            samples = []
            for i in range(k):
                mean = profit_sum[i] / max(pulls[i], 1)
                var = max(profit_sq[i] / max(pulls[i], 1) - mean**2, 4.0)
                samples.append(rng.normal(mean, np.sqrt(var / max(pulls[i], 1))))
            arm = int(np.argmax(samples))
            explore = int(arm != int(np.argmax(profit_sum / np.maximum(pulls, 1))))
        elif policy == "ucb":
            mean = profit_sum / np.maximum(pulls, 1)
            bonus = np.sqrt(2.0 * np.log(t + 1) / np.maximum(pulls, 1))
            arm = int(np.argmax(mean + 18.0 * bonus))
            explore = int(arm != int(np.argmax(mean)))
        else:
            if rng.random() < epsilon:
                arm = int(rng.integers(0, k))
                explore = 1
            else:
                arm = int(np.argmax(profit_sum / np.maximum(pulls, 1)))
                explore = 0

        price = PRICE_ARMS[arm]
        units = _draw_units(rng, price)
        profit = units * _unit_margin(price)
        pulls[arm] += 1
        profit_sum[arm] += profit
        profit_sq[arm] += profit**2
        rows["arm"].append(arm)
        rows["price"].append(float(price))
        rows["units"].append(float(units))
        rows["profit"].append(float(profit))
        rows["regret"].append(float(oracle_p - profit))
        rows["explore"].append(explore)
    return rows


def _fit_elasticity(prices: list[float], units: list[float]) -> dict:
    x = np.log(np.asarray(prices, dtype=float) / 100.0).reshape(-1, 1)
    y = np.log(np.maximum(np.asarray(units, dtype=float), 1e-6))
    model = LinearRegression()
    model.fit(x, y)
    pred = model.predict(x)
    sse = float(np.sum((y - pred) ** 2))
    sst = float(np.sum((y - y.mean()) ** 2))
    return {
        "elasticity": float(model.coef_[0]),
        "intercept": float(model.intercept_),
        "r2": float(1.0 - sse / max(sst, 1e-8)),
    }


def _cumsum(values: list[float]) -> list[float]:
    out = []
    total = 0.0
    for value in values:
        total += float(value)
        out.append(total)
    return out
