import numpy as np
import pandas as pd
import pytest

import config
from make_data import make_actual_drivers
from revenue_model import build_pnl, add_periods
from forecast import make_outlook, opening_from_actuals, forecast_drivers
from plan import make_budget
from variance import bridge


@pytest.fixture(scope="module")
def actual_drivers():
    return make_actual_drivers()


@pytest.fixture(scope="module")
def actual_pnl(actual_drivers):
    return add_periods(build_pnl(actual_drivers, config.OPENING))


def test_customer_counts_are_whole_numbers(actual_pnl):
    # actual churn rates come from whole numbers of cancelled customers,
    # so rebuilding the P&L from the drivers must give whole numbers of customers again
    assert np.allclose(actual_pnl["closing_customers"], actual_pnl["closing_customers"].round())


def test_customer_roll_forward(actual_pnl):
    roll = actual_pnl["opening_customers"] + actual_pnl["new_customers"] - actual_pnl["churned_customers"]
    assert np.allclose(roll, actual_pnl["closing_customers"])


def test_revenue_adds_up(actual_pnl):
    p = actual_pnl
    net = p["gross_subscription"] - p["discounts"] - p["partner_commission"] + p["services_revenue"]
    assert np.allclose(net, p["net_revenue"])
    assert np.allclose(p["net_revenue"] - p["cost_of_revenue"], p["gross_profit"])
    assert np.allclose(p["subscription_gross_profit"] + p["services_gross_profit"], p["gross_profit"])


def test_outlook_keeps_actual_months(actual_drivers, actual_pnl):
    _, outlook = make_outlook(actual_drivers, config.LAST_ACTUAL_MONTH, config.OUTLOOK_YEAR)
    actual_months = outlook["month"] <= config.LAST_ACTUAL_MONTH
    actual_ytd = actual_pnl[(actual_pnl["year"] == config.OUTLOOK_YEAR)]
    assert np.isclose(outlook.loc[actual_months, "net_revenue"].sum(), actual_ytd["net_revenue"].sum())
    assert outlook["month"].nunique() == 12


def test_forecast_drivers_are_sensible(actual_drivers):
    fc = forecast_drivers(actual_drivers, "2026-09-01", "2026-12-01")
    assert len(fc) == 3 * len(config.SEGMENTS)
    assert (fc["new_customers"] >= 0).all()
    assert fc["churn_rate"].between(0, 0.1).all()


def test_bridge_adds_up_to_total_difference(actual_drivers):
    year = config.OUTLOOK_YEAR
    opening = opening_from_actuals(actual_drivers, f"{year - 1}-12-01")
    budget_drivers, budget_pnl = make_budget(actual_drivers, opening, year)
    outlook_drivers, outlook_pnl = make_outlook(actual_drivers, config.LAST_ACTUAL_MONTH, year)

    result = bridge(budget_drivers, outlook_drivers.drop(columns="is_actual"), opening)
    steps = result["net_revenue"].iloc[1:-1].sum()
    assert np.isclose(result["net_revenue"].iloc[0], budget_pnl["net_revenue"].sum())
    assert np.isclose(result["net_revenue"].iloc[-1], outlook_pnl["net_revenue"].sum())
    assert np.isclose(result["net_revenue"].iloc[0] + steps, result["net_revenue"].iloc[-1])
