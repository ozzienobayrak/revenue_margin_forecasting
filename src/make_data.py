"""
Create synthetic monthly actuals (January 2022 to September 2026).

The output is a driver table: one row per month and segment with new customers,
churn, price, discount, partner commission and unit costs.
The P&L is then calculated from these drivers with src/revenue_model.py,
exactly like the budget and the forecast.
"""

import numpy as np
import pandas as pd

import config


def make_actual_drivers():
    rng = np.random.default_rng(config.RANDOM_SEED)
    months = pd.date_range(config.FIRST_MONTH, config.LAST_ACTUAL_MONTH, freq="MS")
    events = config.EVENTS_2026
    rows = []

    for segment in config.SEGMENTS:
        s = config.ACTUALS_SETTINGS[segment]
        customers = config.OPENING[segment]["customers"]

        for month in months:
            years_since_start = month.year - 2022
            season = config.NEW_CUSTOMER_SEASONALITY[month.month - 1]

            # --- new customers: growing trend x seasonality, with random noise (Poisson)
            expected_new = s["new_customers_2022"] * (1 + s["new_customers_growth"]) ** years_since_start * season
            if segment == "Enterprise" and month.year == 2026 and month.quarter == 3:
                expected_new += events["enterprise_extra_wins_q3"]
            new_customers = rng.poisson(expected_new)

            # --- churn: each opening customer cancels with probability churn_rate
            churn_rate = s["churn_rate"]
            if segment == "Mid-market" and month >= pd.Timestamp("2026-04-01"):
                churn_rate = events["midmarket_churn_from_april"]
            churned = rng.binomial(customers, churn_rate)
            realised_churn_rate = churned / customers  # what finance would see in the data

            # --- price: list price increase each January (from 2023; 2022 prices are the opening prices)
            price_increase = s["annual_price_increase"] if month.month == 1 and month.year > 2022 else 0.0

            # --- discount and partner share, with small noise
            discount_rate = s["discount_rate"]
            partner_share = s["partner_share"]
            if segment == "Mid-market" and month.year == 2026:
                partner_share = events["midmarket_partner_share"]
                if month.quarter == 2:
                    discount_rate = events["midmarket_discount_q2"]
                elif month.quarter >= 3:
                    discount_rate = events["midmarket_discount_after_q2"]
            discount_rate += rng.normal(0, 0.003)
            partner_share += rng.normal(0, 0.01)

            # --- unit costs: support cost goes up with wage inflation (3% per year)
            support_cost = s["support_cost_per_cust"] * 1.03 ** years_since_start

            rows.append({
                "month": month,
                "segment": segment,
                "new_customers": new_customers,
                "churn_rate": realised_churn_rate,
                "price_increase": price_increase,
                "expansion_rate": s["expansion_rate"] + rng.normal(0, 0.001),
                "discount_rate": round(discount_rate, 4),
                "partner_share": round(partner_share, 4),
                "commission_rate": s["commission_rate"],
                "onboarding_fee": s["onboarding_fee"],
                "hosting_cost_per_cust": s["hosting_cost_per_cust"] * (1 + rng.normal(0, 0.02)),
                "support_cost_per_cust": support_cost,
                "services_cost_pct": s["services_cost_pct"] + rng.normal(0, 0.02),
                "licence_cost_pct": s["licence_cost_pct"],
            })

            customers = customers + new_customers - churned

    return pd.DataFrame(rows)


if __name__ == "__main__":
    drivers = make_actual_drivers()
    drivers.to_csv("data/actual_drivers.csv", index=False)
    print(f"Saved {len(drivers)} rows to data/actual_drivers.csv")
