"""N-channel funnel DGP, 2SLS, attribution, and SLSQP optimizer."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import minimize
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error, r2_score
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson

from hierarchical_mmm_engine.channels import ChannelSpec, validate_channel_set
from hierarchical_mmm_engine.config import DGPConfig
from hierarchical_mmm_engine.transforms import (
    geometric_adstock,
    hill_saturation,
    steady_state_transform,
    steady_state_transform_derivative,
)


@dataclass
class FlexibleEstimates:
    stage1_params: dict[str, float]
    stage2_params: dict[str, float]
    alphas: dict[str, float]
    betas: dict[str, float]
    beta_m: float
    stage1_r2: float
    stage2_r2: float
    test_r2: float
    test_rmse: float
    test_mape: float
    durbin_watson: float
    train: pd.DataFrame
    test: pd.DataFrame
    train_predictions: pd.Series
    test_predictions: pd.Series
    stage1_resid: pd.Series
    stage2_resid: pd.Series


STAGE1_CONTROLS = ["seasonality", "holiday", "competitor_sov", "temperature"]
STAGE2_CONTROLS = [
    "trend",
    "seasonality",
    "holiday",
    "promo_depth",
    "price_dev",
    "stockout_rate",
    "competitor_sov",
    "unemployment",
    "cpi_yoy",
    "temperature",
    "payday",
]

CONTROL_META = {
    "trend": {
        "label": "Linear trend",
        "unit": "per week index (series already includes slope)",
        "typical": "Slow baseline drift in category demand",
        "real_range": "week index 0..n",
        "group": "calendar",
    },
    "seasonality": {
        "label": "Seasonality",
        "unit": "Fourier mix (sales $k units)",
        "typical": "Annual sine/cosine, stronger in Q4 retail",
        "real_range": "about -30 to +30 $k equivalent",
        "group": "calendar",
    },
    "holiday": {
        "label": "Holiday week",
        "unit": "0/1 dummy",
        "typical": "Black Friday through New Year weeks",
        "real_range": "0 or 1",
        "group": "calendar",
    },
    "payday": {
        "label": "Payday week",
        "unit": "0/1 dummy",
        "typical": "Biweekly pay cycles in Canada / US",
        "real_range": "0 or 1",
        "group": "calendar",
    },
    "temperature": {
        "label": "Temperature",
        "unit": "degrees C",
        "typical": "Southern Ontario weekly mean",
        "real_range": "-12 to 28 C",
        "group": "calendar",
    },
    "promo_depth": {
        "label": "Promo depth",
        "unit": "discount share of list",
        "typical": "Feature/display weeks, 5-40% off",
        "real_range": "0.00 to 0.48",
        "group": "commercial",
    },
    "price_dev": {
        "label": "Price vs 100",
        "unit": "index points vs 100",
        "typical": "List/net price index, PIM or ERP",
        "real_range": "93 to 111",
        "group": "commercial",
    },
    "stockout_rate": {
        "label": "Stockout rate",
        "unit": "share of SKU-hours unavailable",
        "typical": "Inventory fill-rate complement",
        "real_range": "0.00 to 0.28",
        "group": "commercial",
    },
    "competitor_sov": {
        "label": "Competitor SOV",
        "unit": "share of category voice 0-1",
        "typical": "Pathmatics / Kantar estimated competitor spend",
        "real_range": "0.12 to 0.62",
        "group": "competitive",
    },
    "unemployment": {
        "label": "Unemployment",
        "unit": "percentage points",
        "typical": "StatsCan / FRED labour series",
        "real_range": "4.4 to 9.2 pp",
        "group": "macro",
    },
    "cpi_yoy": {
        "label": "CPI YoY",
        "unit": "percentage points",
        "typical": "StatsCan CPI 12-month change",
        "real_range": "0.4 to 6.8 pp",
        "group": "macro",
    },
}


def _true_stage2(cfg: DGPConfig, name: str) -> float:
    mapping = {
        "trend": 1.0,
        "seasonality": 1.0,
        "holiday": cfg.holiday_sales_lift,
        "promo_depth": cfg.promo_sales_lift,
        "price_dev": cfg.true_beta_price,
        "stockout_rate": cfg.true_beta_stockout,
        "competitor_sov": cfg.true_beta_sov,
        "unemployment": cfg.true_beta_unemp,
        "cpi_yoy": cfg.true_beta_cpi,
        "temperature": cfg.true_beta_temp,
        "payday": cfg.true_beta_payday,
    }
    return float(mapping[name])


def _true_stage1(cfg: DGPConfig, name: str) -> float:
    mapping = {
        "seasonality": cfg.season_on_intent,
        "holiday": cfg.holiday_intent_lift,
        "competitor_sov": cfg.true_alpha_sov,
        "temperature": cfg.true_alpha_temp,
    }
    return float(mapping[name])


def generate_flexible_panel(
    channels: list[ChannelSpec],
    dgp: DGPConfig | None = None,
) -> pd.DataFrame:
    """Synthesize weekly sales from an arbitrary TOFU/MOFU/BOFU mix plus controls."""
    cfg = dgp or DGPConfig()
    np.random.seed(cfg.seed)
    n = cfg.n_weeks
    time_idx = np.arange(n)
    controls = _simulate_controls(cfg, time_idx, n)

    frame = pd.DataFrame({"week": time_idx, **controls})

    intent = (
        cfg.true_alpha_0
        + cfg.season_on_intent * frame["seasonality"].to_numpy()
        + cfg.holiday_intent_lift * frame["holiday"].to_numpy()
        + cfg.true_alpha_sov * frame["competitor_sov"].to_numpy()
        + cfg.true_alpha_temp * frame["temperature"].to_numpy()
    )
    sales_media = np.zeros(n)

    for channel in channels:
        spend = _simulate_spend(channel, time_idx, frame["holiday"].to_numpy(), n)
        adstocked = geometric_adstock(spend, channel.decay)
        transformed = hill_saturation(adstocked, k=channel.k_hill, s=cfg.hill_shape)
        cid = channel.channel_id
        frame[f"spend_{cid}"] = spend
        frame[f"adstock_{cid}"] = adstocked
        frame[f"trans_{cid}"] = transformed
        if channel.drives_intent:
            intent = intent + channel.alpha * transformed
        if channel.drives_sales_direct:
            sales_media = sales_media + channel.beta * transformed

    intent = intent + np.random.normal(0.0, cfg.intent_noise_sd, size=n)
    sales = (
        cfg.true_beta_0
        + frame["trend"].to_numpy()
        + frame["seasonality"].to_numpy()
        + cfg.holiday_sales_lift * frame["holiday"].to_numpy()
        + cfg.promo_sales_lift * frame["promo_depth"].to_numpy()
        + cfg.true_beta_price * frame["price_dev"].to_numpy()
        + cfg.true_beta_stockout * frame["stockout_rate"].to_numpy()
        + cfg.true_beta_sov * frame["competitor_sov"].to_numpy()
        + cfg.true_beta_unemp * frame["unemployment"].to_numpy()
        + cfg.true_beta_cpi * frame["cpi_yoy"].to_numpy()
        + cfg.true_beta_temp * frame["temperature"].to_numpy()
        + cfg.true_beta_payday * frame["payday"].to_numpy()
        + cfg.true_beta_m * intent
        + sales_media
        + np.random.normal(0.0, cfg.sales_noise_sd, size=n)
    )
    frame["queries_M"] = intent
    frame["sales_Y"] = sales
    return frame


def _simulate_controls(cfg: DGPConfig, time_idx: np.ndarray, n: int) -> dict[str, np.ndarray]:
    """Canada-like weekly controls with realistic ranges and holiday stacking."""
    fourier_sin1 = np.sin(2 * np.pi * time_idx / cfg.season_period)
    fourier_cos1 = np.cos(2 * np.pi * time_idx / cfg.season_period)
    fourier_sin2 = np.sin(4 * np.pi * time_idx / cfg.season_period)
    fourier_cos2 = np.cos(4 * np.pi * time_idx / cfg.season_period)
    seasonality = cfg.season_sin_amp * fourier_sin1 - cfg.season_cos_amp * fourier_cos2
    week_of_year = time_idx % int(cfg.season_period)
    holiday = ((week_of_year >= 46) | (week_of_year <= 1)).astype(float)
    payday = (((week_of_year % 4) == 0) | ((week_of_year % 4) == 2)).astype(float)

    price_index = np.clip(
        100.0
        + 3.2 * fourier_sin1
        + 1.6 * np.sin(2 * np.pi * time_idx / 26.0)
        + np.cumsum(np.random.normal(0.0, 0.22, n)) * 0.10
        + np.random.normal(0.0, 0.35, n),
        93.0,
        111.0,
    )
    stockout_rate = np.clip(
        0.018 + 0.07 * holiday + np.random.beta(1.4, 18.0, n) * 0.35,
        0.0,
        0.28,
    )
    competitor_sov = np.clip(
        0.31
        + 0.07 * fourier_sin1
        + 0.05 * holiday
        + 0.06 * np.sin(2 * np.pi * time_idx / 17.0)
        + np.random.normal(0.0, 0.032, n),
        0.12,
        0.62,
    )
    unemployment = np.clip(
        6.1
        + 0.65 * np.sin(2 * np.pi * time_idx / 78.0)
        + np.cumsum(np.random.normal(0.0, 0.045, n)) * 0.05
        + np.random.normal(0.0, 0.09, n),
        4.4,
        9.2,
    )
    cpi_yoy = np.clip(
        2.5
        + 1.05 * np.sin(2 * np.pi * time_idx / 64.0)
        + 0.35 * fourier_sin2
        + np.cumsum(np.random.normal(0.0, 0.03, n)) * 0.07
        + np.random.normal(0.0, 0.12, n),
        0.4,
        6.8,
    )
    temperature = (
        7.5
        + 16.5 * np.sin(2 * np.pi * (time_idx - 12) / cfg.season_period)
        + np.random.normal(0.0, 1.7, n)
    )
    promo_depth = np.clip(
        0.045 + 0.17 * holiday + 0.04 * payday + np.random.normal(0.0, 0.028, n),
        0.0,
        0.48,
    )
    return {
        "trend": cfg.trend_slope * time_idx,
        "seasonality": seasonality,
        "fourier_sin1": fourier_sin1,
        "fourier_cos1": fourier_cos1,
        "fourier_sin2": fourier_sin2,
        "fourier_cos2": fourier_cos2,
        "holiday": holiday,
        "payday": payday,
        "promo_depth": promo_depth,
        "price_index": price_index,
        "price_dev": price_index - 100.0,
        "stockout_rate": stockout_rate,
        "competitor_sov": competitor_sov,
        "unemployment": unemployment,
        "cpi_yoy": cpi_yoy,
        "temperature": temperature,
        "cpm_index": np.clip(18.0 + 6.0 * competitor_sov + np.random.normal(0.0, 1.4, n), 10.0, 40.0),
    }


def _simulate_spend(channel: ChannelSpec, time_idx: np.ndarray, holiday: np.ndarray, n: int) -> np.ndarray:
    if channel.flight_on > 0 and channel.flight_cycle > channel.flight_on:
        mask = ((time_idx % channel.flight_cycle) < channel.flight_on).astype(float)
        duty = channel.flight_on / channel.flight_cycle
        spend = mask * np.random.gamma(shape=4.0, scale=channel.mean_spend / (4.0 * duty), size=n)
    else:
        lo = channel.mean_spend * 0.55
        hi = channel.mean_spend * 1.45
        spend = np.random.uniform(lo, hi, size=n)
    return spend * (1.0 + channel.holiday_uplift * holiday)


def fit_flexible_2sls(
    frame: pd.DataFrame,
    channels: list[ChannelSpec],
    train_ratio: float,
) -> FlexibleEstimates:
    split_idx = int(len(frame) * train_ratio)
    train = frame.iloc[:split_idx].copy()
    test = frame.iloc[split_idx:].copy()

    intent_cols = [f"trans_{c.channel_id}" for c in channels if c.drives_intent]
    sales_cols = [f"trans_{c.channel_id}" for c in channels if c.drives_sales_direct]
    stage1_cols = [*STAGE1_CONTROLS, *intent_cols]
    stage2_cols = [*STAGE2_CONTROLS, "M_hat", *sales_cols]

    x1_train = sm.add_constant(train[stage1_cols], has_constant="add")
    stage1 = sm.OLS(train["queries_M"], x1_train).fit()
    train["M_hat"] = stage1.fittedvalues
    x1_test = sm.add_constant(test[stage1_cols], has_constant="add")
    test["M_hat"] = stage1.predict(x1_test)

    x2_train = sm.add_constant(train[stage2_cols], has_constant="add")
    stage2 = sm.OLS(train["sales_Y"], x2_train).fit()
    x2_test = sm.add_constant(test[stage2_cols], has_constant="add")
    test_pred = stage2.predict(x2_test)

    alphas = {
        c.channel_id: float(stage1.params.get(f"trans_{c.channel_id}", 0.0))
        for c in channels
        if c.drives_intent
    }
    betas = {
        c.channel_id: float(stage2.params.get(f"trans_{c.channel_id}", 0.0))
        for c in channels
        if c.drives_sales_direct
    }
    actual = test["sales_Y"].to_numpy()
    pred = np.asarray(test_pred)
    return FlexibleEstimates(
        stage1_params={str(k): float(v) for k, v in stage1.params.items()},
        stage2_params={str(k): float(v) for k, v in stage2.params.items()},
        alphas=alphas,
        betas=betas,
        beta_m=float(stage2.params["M_hat"]),
        stage1_r2=float(stage1.rsquared),
        stage2_r2=float(stage2.rsquared),
        test_r2=float(r2_score(actual, pred)),
        test_rmse=float(np.sqrt(mean_squared_error(actual, pred))),
        test_mape=float(mean_absolute_percentage_error(actual, pred) * 100.0),
        durbin_watson=float(durbin_watson(stage2.resid)),
        train=train,
        test=test,
        train_predictions=pd.Series(np.asarray(stage2.fittedvalues), index=train.index),
        test_predictions=pd.Series(pred, index=test.index),
        stage1_resid=pd.Series(np.asarray(stage1.resid), index=train.index),
        stage2_resid=pd.Series(np.asarray(stage2.resid), index=train.index),
    )


def attribute_channels(
    frame: pd.DataFrame,
    channels: list[ChannelSpec],
    estimates: FlexibleEstimates,
) -> list[dict]:
    rows = []
    for channel in channels:
        col = f"trans_{channel.channel_id}"
        direct = 0.0
        indirect = 0.0
        if channel.drives_intent:
            indirect = float(np.sum(estimates.alphas[channel.channel_id] * estimates.beta_m * frame[col]))
        if channel.drives_sales_direct:
            direct = float(np.sum(estimates.betas[channel.channel_id] * frame[col]))
        total = direct + indirect
        rows.append(
            {
                "id": channel.channel_id,
                "name": channel.name,
                "funnel": channel.funnel,
                "direct": direct,
                "indirect": indirect,
                "total": total,
                "indirect_share": (100.0 * indirect / total) if total else 0.0,
            }
        )
    return rows


def _steady_transforms(spend: np.ndarray, channels: list[ChannelSpec], hill_shape: float) -> dict[str, float]:
    return {
        ch.channel_id: steady_state_transform(float(spend[i]), ch.decay, ch.k_hill, hill_shape)
        for i, ch in enumerate(channels)
    }


def funnel_revenue(spend: np.ndarray, channels: list[ChannelSpec], estimates: FlexibleEstimates, hill_shape: float) -> float:
    trans = _steady_transforms(spend, channels, hill_shape)
    intent = sum(estimates.alphas.get(ch.channel_id, 0.0) * trans[ch.channel_id] for ch in channels if ch.drives_intent)
    direct = sum(estimates.betas.get(ch.channel_id, 0.0) * trans[ch.channel_id] for ch in channels if ch.drives_sales_direct)
    return estimates.beta_m * intent + direct


def naive_revenue(spend: np.ndarray, channels: list[ChannelSpec], estimates: FlexibleEstimates, hill_shape: float) -> float:
    trans = _steady_transforms(spend, channels, hill_shape)
    return sum(estimates.betas.get(ch.channel_id, 0.0) * trans[ch.channel_id] for ch in channels if ch.drives_sales_direct)


def optimize_flexible(
    channels: list[ChannelSpec],
    estimates: FlexibleEstimates,
    weekly_budget: float,
    hill_shape: float = 1.0,
) -> dict:
    n = len(channels)
    bounds = [(c.bound_low, c.bound_high) for c in channels]
    initial = np.full(n, weekly_budget / n)
    constraint = {"type": "eq", "fun": lambda s: np.sum(s) - weekly_budget}

    res_funnel = minimize(
        lambda s: -funnel_revenue(s, channels, estimates, hill_shape),
        initial,
        method="SLSQP",
        bounds=bounds,
        constraints=[constraint],
    )
    res_naive = minimize(
        lambda s: -naive_revenue(s, channels, estimates, hill_shape),
        initial,
        method="SLSQP",
        bounds=bounds,
        constraints=[constraint],
    )
    funnel_rev = funnel_revenue(res_funnel.x, channels, estimates, hill_shape)
    naive_rev = funnel_revenue(res_naive.x, channels, estimates, hill_shape)
    net = funnel_rev - naive_rev
    allocation = []
    for i, channel in enumerate(channels):
        allocation.append(
            {
                "id": channel.channel_id,
                "name": channel.name,
                "funnel": channel.funnel,
                "naive": float(res_naive.x[i]),
                "funnel_aware": float(res_funnel.x[i]),
                "shift": float(res_funnel.x[i] - res_naive.x[i]),
            }
        )
    return {
        "allocation": allocation,
        "naive_return": float(naive_rev),
        "funnel_return": float(funnel_rev),
        "net_gain": float(net),
        "pct_gain": float(100.0 * net / naive_rev) if naive_rev else 0.0,
        "mroi": _mroi_rows(res_funnel.x, channels, estimates, hill_shape),
    }


def _mroi_rows(
    spend: np.ndarray,
    channels: list[ChannelSpec],
    estimates: FlexibleEstimates,
    hill_shape: float,
) -> list[dict]:
    rows = []
    for i, channel in enumerate(channels):
        dtrans = steady_state_transform_derivative(float(spend[i]), channel.decay, channel.k_hill, hill_shape)
        direct = estimates.betas.get(channel.channel_id, 0.0) * dtrans if channel.drives_sales_direct else 0.0
        indirect = (
            estimates.beta_m * estimates.alphas.get(channel.channel_id, 0.0) * dtrans
            if channel.drives_intent
            else 0.0
        )
        rows.append(
            {
                "id": channel.channel_id,
                "name": channel.name,
                "funnel": channel.funnel,
                "direct_mroi": float(direct),
                "indirect_mroi": float(indirect),
                "total_mroi": float(direct + indirect),
            }
        )
    return rows


def coefficient_rows(
    channels: list[ChannelSpec],
    estimates: FlexibleEstimates,
    true_beta_m: float = 1.65,
) -> list[dict]:
    rows = []
    for channel in channels:
        if channel.drives_intent:
            rows.append(
                {
                    "parameter": f"alpha {channel.name} (intent)",
                    "true": channel.alpha,
                    "estimated": estimates.alphas.get(channel.channel_id, 0.0),
                }
            )
        if channel.drives_sales_direct:
            rows.append(
                {
                    "parameter": f"beta {channel.name} (direct sales)",
                    "true": channel.beta,
                    "estimated": estimates.betas.get(channel.channel_id, 0.0),
                }
            )
        true_total = channel.beta + channel.alpha * true_beta_m
        hat_total = estimates.betas.get(channel.channel_id, 0.0) + estimates.alphas.get(
            channel.channel_id, 0.0
        ) * estimates.beta_m
        rows.append(
            {
                "parameter": f"{channel.name} total effect",
                "true": true_total,
                "estimated": hat_total,
            }
        )
    rows.append(
        {
            "parameter": "beta_M (intent to sales)",
            "true": true_beta_m,
            "estimated": estimates.beta_m,
        }
    )
    for row in rows:
        row["abs_error"] = abs(row["estimated"] - row["true"])
    return rows


def _series_stats(values: np.ndarray) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "p10": float(np.quantile(arr, 0.10)),
        "p50": float(np.quantile(arr, 0.50)),
        "p90": float(np.quantile(arr, 0.90)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def _zscore(values: np.ndarray) -> list[float]:
    arr = np.asarray(values, dtype=float)
    sd = float(np.std(arr))
    if sd < 1e-12:
        return [0.0] * len(arr)
    return ((arr - float(np.mean(arr))) / sd).astype(float).tolist()


def _vif_rows(frame: pd.DataFrame, cols: list[str]) -> list[dict]:
    design = sm.add_constant(frame[cols], has_constant="add")
    rows = []
    for i, name in enumerate(design.columns):
        if name == "const":
            continue
        try:
            vif = float(variance_inflation_factor(design.to_numpy(dtype=float), i))
            if not np.isfinite(vif):
                vif = None
        except (ValueError, ZeroDivisionError):
            vif = None
        rows.append({"feature": str(name), "vif": vif})
    return rows


def control_coefficient_rows(
    frame: pd.DataFrame,
    estimates: FlexibleEstimates,
    dgp: DGPConfig,
) -> list[dict]:
    rows = []
    for name in STAGE1_CONTROLS:
        meta = CONTROL_META[name]
        estimated = estimates.stage1_params.get(name, 0.0)
        true = _true_stage1(dgp, name)
        values = frame[name].to_numpy(dtype=float)
        rows.append(
            {
                "id": name,
                "label": meta["label"],
                "stage": "intent",
                "group": meta["group"],
                "unit": meta["unit"],
                "typical": meta["typical"],
                "real_range": meta["real_range"],
                "true": true,
                "estimated": estimated,
                "abs_error": abs(estimated - true),
                "mean_contribution": float(estimated * np.mean(values)),
                **_series_stats(values),
            }
        )
    for name in STAGE2_CONTROLS:
        meta = CONTROL_META[name]
        estimated = estimates.stage2_params.get(name, 0.0)
        true = _true_stage2(dgp, name)
        values = frame[name].to_numpy(dtype=float)
        rows.append(
            {
                "id": name,
                "label": meta["label"],
                "stage": "sales",
                "group": meta["group"],
                "unit": meta["unit"],
                "typical": meta["typical"],
                "real_range": meta["real_range"],
                "true": true,
                "estimated": estimated,
                "abs_error": abs(estimated - true),
                "mean_contribution": float(estimated * np.mean(values)),
                **_series_stats(values),
            }
        )
    return rows


def control_contributions(
    frame: pd.DataFrame,
    channels: list[ChannelSpec],
    estimates: FlexibleEstimates,
) -> tuple[list[dict], dict[str, list[float]]]:
    m_hat = pd.concat([estimates.train["M_hat"], estimates.test["M_hat"]]).sort_index()
    p2 = estimates.stage2_params
    week_map: dict[str, np.ndarray] = {}
    intercept = np.full(len(frame), p2.get("const", 0.0), dtype=float)
    week_map["Intercept"] = intercept
    for name in STAGE2_CONTROLS:
        week_map[CONTROL_META[name]["label"]] = p2.get(name, 0.0) * frame[name].to_numpy(dtype=float)
    week_map["Intent M_hat"] = p2.get("M_hat", 0.0) * m_hat.to_numpy(dtype=float)
    for channel in channels:
        if channel.drives_sales_direct:
            col = f"trans_{channel.channel_id}"
            week_map[f"Direct {channel.name}"] = p2.get(col, 0.0) * frame[col].to_numpy(dtype=float)
    predicted = np.sum(np.vstack(list(week_map.values())), axis=0)
    residual = frame["sales_Y"].to_numpy(dtype=float) - predicted
    week_map["Residual"] = residual

    groups = {
        "Calendar": ["trend", "seasonality", "holiday", "payday", "temperature"],
        "Commercial": ["promo_depth", "price_dev", "stockout_rate"],
        "Competitive / macro": ["competitor_sov", "unemployment", "cpi_yoy"],
        "Intent (M_hat)": None,
        "Direct media": None,
        "Intercept": None,
        "Residual": None,
    }
    group_weekly: dict[str, np.ndarray] = {
        "Calendar": np.zeros(len(frame)),
        "Commercial": np.zeros(len(frame)),
        "Competitive / macro": np.zeros(len(frame)),
        "Intent (M_hat)": week_map["Intent M_hat"],
        "Direct media": np.zeros(len(frame)),
        "Intercept": intercept,
        "Residual": residual,
    }
    for name in STAGE2_CONTROLS:
        label = CONTROL_META[name]["label"]
        if name in groups["Calendar"]:
            group_weekly["Calendar"] = group_weekly["Calendar"] + week_map[label]
        elif name in groups["Commercial"]:
            group_weekly["Commercial"] = group_weekly["Commercial"] + week_map[label]
        elif name in groups["Competitive / macro"]:
            group_weekly["Competitive / macro"] = group_weekly["Competitive / macro"] + week_map[label]
    for channel in channels:
        if channel.drives_sales_direct:
            group_weekly["Direct media"] = group_weekly["Direct media"] + week_map[f"Direct {channel.name}"]

    totals = []
    for key, series in week_map.items():
        totals.append(
            {
                "name": key,
                "total": float(np.sum(series)),
                "mean_weekly": float(np.mean(series)),
            }
        )
    group_series = {k: v.astype(float).tolist() for k, v in group_weekly.items()}
    return totals, group_series


def hill_curve_payload(frame: pd.DataFrame, channels: list[ChannelSpec], hill_shape: float) -> list[dict]:
    rows = []
    grid = np.linspace(0.0, 3.0, 61)
    for channel in channels:
        k = channel.k_hill
        mean_adstock = float(frame[f"adstock_{channel.channel_id}"].mean())
        ys = np.asarray(hill_saturation(grid * k, k=k, s=hill_shape), dtype=float)
        rows.append(
            {
                "id": channel.channel_id,
                "name": channel.name,
                "funnel": channel.funnel,
                "k_hill": k,
                "x_over_k": grid.tolist(),
                "y": ys.tolist(),
                "mean_adstock": mean_adstock,
                "mean_x_over_k": mean_adstock / k if k else 0.0,
                "mean_response": float(hill_saturation(mean_adstock, k=k, s=hill_shape)),
            }
        )
    return rows


def run_flexible_scenario(
    channels: list[ChannelSpec],
    weekly_budget: float = 160.0,
    n_weeks: int = 208,
    seed: int = 42,
    train_ratio: float = 0.80,
) -> dict:
    """End-to-end run used by the web studio."""
    validate_channel_set(channels, weekly_budget)
    dgp = replace(DGPConfig(), n_weeks=int(n_weeks), seed=int(seed), train_ratio=train_ratio)
    frame = generate_flexible_panel(channels, dgp)
    estimates = fit_flexible_2sls(frame, channels, dgp.train_ratio)
    attribution = attribute_channels(frame, channels, estimates)
    optimization = optimize_flexible(channels, estimates, weekly_budget, dgp.hill_shape)
    split_idx = int(len(frame) * dgp.train_ratio)
    control_rows = control_coefficient_rows(frame, estimates, dgp)
    contrib_totals, group_series = control_contributions(frame, channels, estimates)
    sales_stage2_cols = [
        *STAGE2_CONTROLS,
        "M_hat",
        *[f"trans_{c.channel_id}" for c in channels if c.drives_sales_direct],
    ]
    intent_stage1_cols = [
        *STAGE1_CONTROLS,
        *[f"trans_{c.channel_id}" for c in channels if c.drives_intent],
    ]
    control_net = float(sum(r["mean_weekly"] for r in contrib_totals if r["name"] in {
        CONTROL_META[n]["label"] for n in STAGE2_CONTROLS
    }))
    media_weekly = float(sum(r["total"] for r in attribution) / len(frame))
    full_pred = pd.concat([estimates.train_predictions, estimates.test_predictions]).sort_index()
    full_resid = frame["sales_Y"].to_numpy(dtype=float) - full_pred.to_numpy(dtype=float)
    control_raw = {
        "holiday": frame["holiday"].astype(float).tolist(),
        "payday": frame["payday"].astype(float).tolist(),
        "promo_depth": frame["promo_depth"].astype(float).tolist(),
        "price_index": frame["price_index"].astype(float).tolist(),
        "stockout_rate": frame["stockout_rate"].astype(float).tolist(),
        "competitor_sov": frame["competitor_sov"].astype(float).tolist(),
        "unemployment": frame["unemployment"].astype(float).tolist(),
        "cpi_yoy": frame["cpi_yoy"].astype(float).tolist(),
        "temperature": frame["temperature"].astype(float).tolist(),
    }
    control_z = {key: _zscore(frame[col].to_numpy(dtype=float)) for key, col in {
        "promo_depth": "promo_depth",
        "price_index": "price_index",
        "stockout_rate": "stockout_rate",
        "competitor_sov": "competitor_sov",
        "unemployment": "unemployment",
        "cpi_yoy": "cpi_yoy",
        "temperature": "temperature",
        "holiday": "holiday",
        "payday": "payday",
    }.items()}
    return {
        "metrics": {
            "stage1_r2": estimates.stage1_r2,
            "stage2_r2": estimates.stage2_r2,
            "test_r2": estimates.test_r2,
            "test_rmse": estimates.test_rmse,
            "test_mape": estimates.test_mape,
            "durbin_watson": estimates.durbin_watson,
            "train_weeks": split_idx,
            "test_weeks": len(frame) - split_idx,
            "n_weeks": len(frame),
            "weekly_budget": weekly_budget,
            "naive_return": optimization["naive_return"],
            "funnel_return": optimization["funnel_return"],
            "net_gain": optimization["net_gain"],
            "pct_gain": optimization["pct_gain"],
            "control_net_weekly": control_net,
            "media_weekly": media_weekly,
            "mean_sales": float(frame["sales_Y"].mean()),
        },
        "channels": [c.to_dict() for c in channels],
        "attribution": attribution,
        "coefficients": coefficient_rows(channels, estimates, dgp.true_beta_m),
        "control_coefficients": control_rows,
        "control_contributions": contrib_totals,
        "vif": {
            "stage1": _vif_rows(estimates.train, intent_stage1_cols),
            "stage2": _vif_rows(estimates.train, sales_stage2_cols),
        },
        "stage_params": {
            "stage1": estimates.stage1_params,
            "stage2": estimates.stage2_params,
        },
        "allocation": optimization["allocation"],
        "mroi": optimization["mroi"],
        "hill_curves": hill_curve_payload(frame, channels, dgp.hill_shape),
        "series": {
            "week": frame["week"].astype(int).tolist(),
            "sales": frame["sales_Y"].astype(float).tolist(),
            "intent": frame["queries_M"].astype(float).tolist(),
            "fitted": full_pred.astype(float).tolist(),
            "residual": full_resid.astype(float).tolist(),
            "split_week": split_idx,
            "train_week": estimates.train["week"].astype(int).tolist(),
            "train_resid": estimates.stage2_resid.astype(float).tolist(),
            "test_week": estimates.test["week"].astype(int).tolist(),
            "test_actual": estimates.test["sales_Y"].astype(float).tolist(),
            "test_pred": estimates.test_predictions.astype(float).tolist(),
            "spends": {
                c.name: frame[f"spend_{c.channel_id}"].astype(float).tolist() for c in channels
            },
            "controls": control_raw,
            "controls_z": control_z,
            "contribution_groups": group_series,
        },
    }
