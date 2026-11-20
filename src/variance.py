"""
Compare versions (budget, earlier outlook, latest outlook) and explain the differences.

The bridge from budget to outlook uses step-by-step substitution:
start with all budget drivers, then replace one group of drivers at a time with the
outlook values and record how much revenue and gross profit change at each step.
Because the revenue model is the same for both versions, the steps add up exactly
to the total difference. (The size of each step depends a little on the order of the
steps; the order used here goes from volume to price to mix, as is common in FP&A.)
"""

import pandas as pd

from revenue_model import build_pnl, summarise

KEY_LINES = ["net_revenue", "net_subscription", "services_revenue", "gross_profit",
             "gross_margin", "closing_customers", "arr"]

BRIDGE_STEPS = [
    ("New customers", ["new_customers"]),
    ("Churn", ["churn_rate"]),
    ("Price and upsell", ["price_increase", "expansion_rate"]),
    ("Discounts and coupons", ["discount_rate"]),
    ("Partner mix and commission", ["partner_share", "commission_rate"]),
    ("Onboarding fees", ["onboarding_fee"]),  # zero in this data set: the fee did not change
    ("Unit costs", ["hosting_cost_per_cust", "support_cost_per_cust", "services_cost_pct", "licence_cost_pct"]),
]


def compare_versions(versions, by):
    """
    versions : dict like {"Budget": budget_pnl, "Q3 Outlook": outlook_pnl}
    by       : "quarter" or "year"
    Returns one long table with a row per period, line and version.
    """
    tables = []
    for name, pnl in versions.items():
        summary = summarise(pnl, by)[KEY_LINES]
        summary = summary.reset_index().melt(id_vars=by, var_name="line", value_name="value")
        summary["version"] = name
        tables.append(summary)
    long = pd.concat(tables, ignore_index=True)
    return long.pivot_table(index=[by, "line"], columns="version", values="value", sort=False)


def variance_table(budget_pnl, outlook_pnl, by="year"):
    """Budget, outlook, difference and difference in % for the key lines."""
    budget = summarise(budget_pnl, by)[KEY_LINES].T
    outlook = summarise(outlook_pnl, by)[KEY_LINES].T
    table = pd.DataFrame({"budget": budget.iloc[:, 0], "outlook": outlook.iloc[:, 0]})
    table["variance"] = table["outlook"] - table["budget"]
    table["variance_pct"] = table["variance"] / table["budget"] * 100
    # for the margin a % difference is confusing, so show the change in percentage points instead
    table.loc["gross_margin", "variance_pct"] = table.loc["gross_margin", "variance"] * 100
    return table


def bridge(budget_drivers, outlook_drivers, opening):
    """Explain the full-year difference in net revenue and gross profit, driver group by driver group."""
    key = ["month", "segment"]
    budget = budget_drivers.sort_values(key).reset_index(drop=True)
    outlook = outlook_drivers.sort_values(key).reset_index(drop=True)

    def totals(drivers):
        pnl = build_pnl(drivers, opening)
        return pnl["net_revenue"].sum(), pnl["gross_profit"].sum()

    current = budget.copy()
    revenue, profit = totals(current)
    rows = [{"step": "Budget", "net_revenue": revenue, "gross_profit": profit}]

    for step_name, columns in BRIDGE_STEPS:
        current[columns] = outlook[columns].values
        new_revenue, new_profit = totals(current)
        rows.append({"step": step_name,
                     "net_revenue": new_revenue - revenue,
                     "gross_profit": new_profit - profit})
        revenue, profit = new_revenue, new_profit

    rows.append({"step": "Outlook", "net_revenue": revenue, "gross_profit": profit})
    return pd.DataFrame(rows)


def segment_variance(budget_pnl, outlook_pnl):
    """Full-year net revenue and gross profit by segment: budget vs outlook."""
    lines = ["net_revenue", "gross_profit"]
    budget = budget_pnl.groupby("segment")[lines].sum().add_prefix("budget_")
    outlook = outlook_pnl.groupby("segment")[lines].sum().add_prefix("outlook_")
    table = budget.join(outlook)
    table["net_revenue_variance"] = table["outlook_net_revenue"] - table["budget_net_revenue"]
    table["gross_profit_variance"] = table["outlook_gross_profit"] - table["budget_gross_profit"]
    return table
