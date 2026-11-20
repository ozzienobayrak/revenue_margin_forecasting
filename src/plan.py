"""
Budget and long-term plan.

A plan year is built from the drivers of the year before plus the assumptions in config:
- new customers  = last year's total x (1 + planned growth), spread over months with the usual seasonality
- price increase = planned January price increase
- churn, expansion and services cost = last year's average
- discount, partner share and unit costs = level of last year's final quarter
  (the most recent level), support cost grows with wage inflation

The 2026 budget is built in December 2025 from 2025 actuals.
The long-term plan (2027-2029) starts from the 2026 Q3 outlook.
"""

import pandas as pd

import config
from revenue_model import build_pnl, closing_position, add_periods


def plan_drivers(previous_year_drivers, year):
    rows = []
    for segment in config.SEGMENTS:
        prev = previous_year_drivers[previous_year_drivers["segment"] == segment].sort_values("month")
        last_quarter = prev.tail(3)
        assumptions = config.PLAN_ASSUMPTIONS[year][segment]
        total_new = prev["new_customers"].sum() * (1 + assumptions["new_customers_growth"])

        for month in pd.date_range(f"{year}-01-01", f"{year}-12-01", freq="MS"):
            season = config.NEW_CUSTOMER_SEASONALITY[month.month - 1]
            rows.append({
                "month": month,
                "segment": segment,
                "new_customers": total_new / 12 * season,
                "churn_rate": prev["churn_rate"].mean(),
                "price_increase": assumptions["price_increase"] if month.month == 1 else 0.0,
                "expansion_rate": prev["expansion_rate"].mean(),
                "discount_rate": last_quarter["discount_rate"].mean(),
                "partner_share": last_quarter["partner_share"].mean(),
                "commission_rate": prev["commission_rate"].iloc[-1],
                "onboarding_fee": prev["onboarding_fee"].iloc[-1],
                "hosting_cost_per_cust": last_quarter["hosting_cost_per_cust"].mean(),
                "support_cost_per_cust": last_quarter["support_cost_per_cust"].mean() * (1 + config.SUPPORT_COST_INFLATION),
                "services_cost_pct": prev["services_cost_pct"].mean(),
                "licence_cost_pct": prev["licence_cost_pct"].iloc[-1],
            })
    return pd.DataFrame(rows)


def make_budget(actual_drivers, opening_position, year):
    """Budget for `year`, built from the actual drivers of the year before."""
    previous = actual_drivers[actual_drivers["month"].dt.year == year - 1]
    drivers = plan_drivers(previous, year)
    pnl = add_periods(build_pnl(drivers, opening_position))
    return drivers, pnl


def make_long_term_plan(outlook_drivers, outlook_pnl):
    """Plan years in config.PLAN_YEARS, each starting from the year before."""
    previous_drivers = outlook_drivers
    opening = closing_position(outlook_pnl, outlook_pnl["month"].max())
    all_years = []

    for year in config.PLAN_YEARS:
        drivers = plan_drivers(previous_drivers, year)
        pnl = add_periods(build_pnl(drivers, opening))
        all_years.append(pnl)
        previous_drivers = drivers
        opening = closing_position(pnl, pnl["month"].max())

    return pd.concat(all_years, ignore_index=True)
