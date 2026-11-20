"""
Forecast the drivers for the months after the last actual month.

Approach:
- New customers have trend and seasonality, so they are forecast with
  Holt-Winters exponential smoothing (statsmodels), separately for each segment.
- The other drivers move slowly, so they are forecast with recent averages
  (for example churn = average of the last 6 months).

The forecast drivers then go through the same revenue model as the actuals.

This file also has:
- a backtest that checks how accurate the method was in the past,
  compared with two simple benchmarks;
- scenarios (downside / base / upside).
"""

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

import config
from revenue_model import build_pnl, closing_position, add_periods

# How many recent months to average for each driver
AVERAGE_WINDOW = {
    "churn_rate": 6,
    "expansion_rate": 12,
    "discount_rate": 3,
    "partner_share": 3,
    "commission_rate": 1,
    "onboarding_fee": 1,
    "hosting_cost_per_cust": 3,
    "support_cost_per_cust": 3,
    "services_cost_pct": 6,
    "licence_cost_pct": 1,
}


def forecast_new_customers(history, n_months):
    """Holt-Winters forecast of monthly new customers. `history` is a Series indexed by month."""
    model = ExponentialSmoothing(
        history.astype(float).asfreq("MS"),
        trend="add",
        damped_trend=True,
        seasonal="add",
        seasonal_periods=12,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # statsmodels warns about frequency and convergence; not important here
        fit = model.fit()
    prediction = fit.forecast(n_months)
    return np.clip(prediction.values, 0, None)  # cannot win a negative number of customers


def forecast_drivers(actual_drivers, last_actual_month, last_forecast_month):
    """Forecast drivers for the months after `last_actual_month` up to `last_forecast_month`."""
    last_actual_month = pd.Timestamp(last_actual_month)
    future_months = pd.date_range(last_actual_month + pd.offsets.MonthBegin(1), last_forecast_month, freq="MS")
    history = actual_drivers[actual_drivers["month"] <= last_actual_month]
    rows = []

    for segment in config.SEGMENTS:
        seg = history[history["segment"] == segment].sort_values("month").set_index("month")
        new_customers = forecast_new_customers(seg["new_customers"], len(future_months))
        last_january_increase = seg.loc[seg.index.month == 1, "price_increase"].iloc[-1]

        for i, month in enumerate(future_months):
            row = {"month": month, "segment": segment, "new_customers": new_customers[i]}
            row["price_increase"] = last_january_increase if month.month == 1 else 0.0
            for driver, window in AVERAGE_WINDOW.items():
                row[driver] = seg[driver].tail(window).mean()
            rows.append(row)

    return pd.DataFrame(rows)[["month", "segment"] + config.DRIVER_COLUMNS]


def make_outlook(actual_drivers, last_actual_month, year):
    """
    Outlook for a full year = actual months + forecast for the rest of the year.
    For example actuals to September + forecast October to December is a "9+3" outlook.
    Returns the drivers and the P&L.
    """
    year_start = pd.Timestamp(f"{year}-01-01")
    year_end = pd.Timestamp(f"{year}-12-01")

    actual_part = actual_drivers[(actual_drivers["month"] >= year_start) &
                                 (actual_drivers["month"] <= last_actual_month)]
    forecast_part = forecast_drivers(actual_drivers, last_actual_month, year_end)
    drivers = pd.concat([actual_part, forecast_part], ignore_index=True)
    drivers["is_actual"] = drivers["month"] <= pd.Timestamp(last_actual_month)

    opening = opening_from_actuals(actual_drivers, year_start - pd.offsets.MonthBegin(1))
    pnl = add_periods(build_pnl(drivers, opening))
    return drivers, pnl


def opening_from_actuals(actual_drivers, month):
    """Closing customers and fee at the end of `month`, calculated from the actual drivers."""
    history = actual_drivers[actual_drivers["month"] <= pd.Timestamp(month)]
    actual_pnl = build_pnl(history, config.OPENING)
    return closing_position(actual_pnl, month)


def apply_scenario(drivers, scenario, from_month):
    """Multiply forecast drivers (months after `from_month`) by the scenario factors in config."""
    drivers = drivers.copy()
    future = drivers["month"] > pd.Timestamp(from_month)
    for driver, factor in config.SCENARIOS[scenario].items():
        drivers.loc[future, driver] = drivers.loc[future, driver] * factor
    return drivers


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def mape(actual, forecast):
    """Mean absolute percentage error, in %."""
    actual = np.asarray(actual, dtype=float)
    forecast = np.asarray(forecast, dtype=float)
    return float(np.mean(np.abs(forecast - actual) / np.abs(actual)) * 100)


def backtest(actual_drivers, cutoff, horizon=12):
    """
    Pretend we are at `cutoff`, forecast the next `horizon` months and compare with what happened.

    Compares the driver-based forecast with two benchmarks on monthly net revenue:
    - seasonal naive: same month last year, scaled by the growth of the last 12 months
    - Holt-Winters directly on total net revenue (no drivers)
    """
    cutoff = pd.Timestamp(cutoff)
    end = cutoff + pd.offsets.MonthBegin(horizon)

    # actual P&L for the whole period, totals per month
    actual_pnl = build_pnl(actual_drivers[actual_drivers["month"] <= end], config.OPENING)
    actual_total = actual_pnl.groupby("month")[["net_revenue", "gross_profit"]].sum()
    test = actual_total.loc[actual_total.index > cutoff]
    train = actual_total.loc[actual_total.index <= cutoff]

    # 1) driver-based forecast
    future_drivers = forecast_drivers(actual_drivers, cutoff, end)
    opening = closing_position(actual_pnl, cutoff)
    driver_pnl = build_pnl(future_drivers, opening).groupby("month")[["net_revenue", "gross_profit"]].sum()

    # 2) seasonal naive benchmark
    growth = train["net_revenue"].iloc[-12:].sum() / train["net_revenue"].iloc[-24:-12].sum()
    naive = []
    for month in test.index:
        same_month_last_year = month - pd.DateOffset(years=1)
        naive.append(actual_total.loc[same_month_last_year, "net_revenue"] * growth)

    # 3) Holt-Winters on total revenue
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hw = ExponentialSmoothing(train["net_revenue"].asfreq("MS"), trend="add", seasonal="add",
                                  seasonal_periods=12).fit()
    hw_forecast = hw.forecast(len(test)).values

    comparison = pd.DataFrame({
        "actual": test["net_revenue"].values,
        "driver_based": driver_pnl["net_revenue"].values,
        "seasonal_naive": naive,
        "holt_winters_total": hw_forecast,
    }, index=test.index)

    scores = pd.DataFrame({
        "method": ["Driver-based (this model)", "Seasonal naive", "Holt-Winters on total revenue"],
        "mape_net_revenue_pct": [
            mape(comparison["actual"], comparison["driver_based"]),
            mape(comparison["actual"], comparison["seasonal_naive"]),
            mape(comparison["actual"], comparison["holt_winters_total"]),
        ],
        "full_period_error_pct": [
            (comparison[col].sum() / comparison["actual"].sum() - 1) * 100
            for col in ["driver_based", "seasonal_naive", "holt_winters_total"]
        ],
    })
    return comparison, scores
