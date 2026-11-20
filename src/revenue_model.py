"""
Driver-based revenue and gross margin model.

The same function turns drivers into a P&L for actuals, budget, forecast and plan.
This way the budget and the outlook are always calculated in the same way,
and differences between them come only from different drivers.

Revenue logic for one segment and one month:

    closing customers   = opening customers + new customers - churned customers
    fee per customer    = last month's fee x (1 + price increase) x (1 + expansion)
    gross subscription  = closing customers x fee per customer
    discounts           = gross subscription x discount rate
    partner commission  = (gross subscription - discounts) x partner share x commission rate
    net subscription    = gross subscription - discounts - partner commission
    services revenue    = new customers x onboarding fee
    net revenue         = net subscription + services revenue

Cost of revenue: hosting, customer support, services delivery and third-party licences.
"""

import pandas as pd


def build_pnl(drivers, opening):
    """
    drivers : DataFrame with one row per month and segment (columns: month, segment + drivers)
    opening : dict like {"Mid-market": {"customers": 420, "fee_per_customer": 1400}, ...}
              customers and fee at the end of the month before the first month in `drivers`

    Returns a DataFrame with the drivers plus customers, revenue lines, costs and margin.
    """
    results = []

    for segment, seg_drivers in drivers.groupby("segment", sort=False):
        seg_drivers = seg_drivers.sort_values("month")
        customers = opening[segment]["customers"]
        fee = opening[segment]["fee_per_customer"]

        for _, row in seg_drivers.iterrows():
            opening_customers = customers
            churned = opening_customers * row["churn_rate"]
            customers = opening_customers + row["new_customers"] - churned
            fee = fee * (1 + row["price_increase"]) * (1 + row["expansion_rate"])

            gross_subscription = customers * fee
            discounts = gross_subscription * row["discount_rate"]
            commission = (gross_subscription - discounts) * row["partner_share"] * row["commission_rate"]
            net_subscription = gross_subscription - discounts - commission
            services = row["new_customers"] * row["onboarding_fee"]
            net_revenue = net_subscription + services

            hosting = customers * row["hosting_cost_per_cust"]
            support = customers * row["support_cost_per_cust"]
            services_delivery = services * row["services_cost_pct"]
            licences = gross_subscription * row["licence_cost_pct"]
            cost_of_revenue = hosting + support + services_delivery + licences

            result = row.to_dict()
            result.update({
                "opening_customers": opening_customers,
                "churned_customers": churned,
                "closing_customers": customers,
                "fee_per_customer": fee,
                "gross_subscription": gross_subscription,
                "discounts": discounts,
                "partner_commission": commission,
                "net_subscription": net_subscription,
                "services_revenue": services,
                "net_revenue": net_revenue,
                "hosting_cost": hosting,
                "support_cost": support,
                "services_delivery_cost": services_delivery,
                "licence_cost": licences,
                "cost_of_revenue": cost_of_revenue,
                "gross_profit": net_revenue - cost_of_revenue,
                "subscription_gross_profit": net_subscription - hosting - support - licences,
                "services_gross_profit": services - services_delivery,
                "arr": net_subscription * 12,  # annual recurring revenue at month-end run rate
            })
            results.append(result)

    pnl = pd.DataFrame(results)
    pnl["gross_margin"] = pnl["gross_profit"] / pnl["net_revenue"]
    return pnl


def closing_position(pnl, month):
    """Customers and fee per customer at the end of `month`, to use as the opening of the next run."""
    month = pd.Timestamp(month)
    rows = pnl[pnl["month"] == month]
    opening = {}
    for _, row in rows.iterrows():
        opening[row["segment"]] = {
            "customers": row["closing_customers"],
            "fee_per_customer": row["fee_per_customer"],
        }
    return opening


# Lines that can be added up across months and segments
SUM_COLUMNS = [
    "new_customers", "churned_customers",
    "gross_subscription", "discounts", "partner_commission", "net_subscription",
    "services_revenue", "net_revenue",
    "hosting_cost", "support_cost", "services_delivery_cost", "licence_cost",
    "cost_of_revenue", "gross_profit", "subscription_gross_profit", "services_gross_profit",
]


def summarise(pnl, by):
    """
    Add up a P&L by period, e.g. by="quarter" or by="year" (the column must exist).
    Closing customers and ARR are taken from the last month of each period, not summed.
    """
    totals = pnl.groupby(by)[SUM_COLUMNS].sum()

    last_month = pnl.groupby(by)["month"].transform("max")
    closing = pnl[pnl["month"] == last_month].groupby(by)[["closing_customers", "arr"]].sum()

    summary = totals.join(closing)
    summary["gross_margin"] = summary["gross_profit"] / summary["net_revenue"]
    summary["subscription_share"] = summary["net_subscription"] / summary["net_revenue"]
    return summary


def add_periods(pnl):
    """Add year and quarter columns (e.g. 2026 and '2026-Q3')."""
    pnl = pnl.copy()
    pnl["year"] = pnl["month"].dt.year
    pnl["quarter"] = pnl["month"].dt.year.astype(str) + "-Q" + pnl["month"].dt.quarter.astype(str)
    return pnl
