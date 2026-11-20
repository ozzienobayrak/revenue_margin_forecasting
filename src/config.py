"""
All assumptions live in this file, so no number is hardcoded in the other scripts.

The company is fictional: a B2B SaaS company selling EHS / ESG compliance software
(health & safety, environment, sustainability reporting) to mid-sized and large firms.
All amounts are in EUR.
"""

# ---------------------------------------------------------------------------
# Time settings
# ---------------------------------------------------------------------------
FIRST_MONTH = "2022-01-01"      # first month of synthetic actuals
LAST_ACTUAL_MONTH = "2026-09-01"  # Q3 2026 is closed, so actuals run to September
OUTLOOK_YEAR = 2026
PLAN_YEARS = [2027, 2028, 2029]   # long-term plan (2027 is also the budget year)

SEGMENTS = ["Mid-market", "Enterprise"]

RANDOM_SEED = 1

# ---------------------------------------------------------------------------
# Driver names
# These are the inputs of the revenue model (src/revenue_model.py).
# Actuals, budget, forecast and plan all use the same drivers.
# ---------------------------------------------------------------------------
DRIVER_COLUMNS = [
    "new_customers",          # customers won in the month
    "churn_rate",             # share of opening customers who cancel in the month
    "price_increase",         # list price increase (only in January, otherwise 0)
    "expansion_rate",         # monthly growth of fee per customer from upsell (more modules, users)
    "discount_rate",          # average discount / coupon on the list fee
    "partner_share",          # share of subscription revenue sold through reseller partners
    "commission_rate",        # commission paid to partners on partner revenue
    "onboarding_fee",         # one-off implementation fee per new customer (services revenue)
    "hosting_cost_per_cust",  # monthly cloud hosting cost per customer
    "support_cost_per_cust",  # monthly customer support cost per customer
    "services_cost_pct",      # delivery cost as % of services revenue
    "licence_cost_pct",       # third-party software licences as % of gross subscription revenue
]

# ---------------------------------------------------------------------------
# Settings used to generate the synthetic actuals (src/make_data.py)
# ---------------------------------------------------------------------------
OPENING = {
    # customers and monthly list fee per customer at the end of December 2021
    "Mid-market": {"customers": 420, "fee_per_customer": 1400},
    "Enterprise": {"customers": 70, "fee_per_customer": 8500},
}

ACTUALS_SETTINGS = {
    "Mid-market": {
        "new_customers_2022": 8,      # average new customers per month in 2022
        "new_customers_growth": 0.12,  # yearly growth in new customer wins
        "churn_rate": 0.010,
        "annual_price_increase": 0.05,
        "expansion_rate": 0.002,
        "discount_rate": 0.08,
        "partner_share": 0.30,
        "commission_rate": 0.20,
        "onboarding_fee": 6000,
        "hosting_cost_per_cust": 120,
        "support_cost_per_cust": 95,
        "services_cost_pct": 0.70,
        "licence_cost_pct": 0.03,
    },
    "Enterprise": {
        "new_customers_2022": 1.3,
        "new_customers_growth": 0.15,
        "churn_rate": 0.006,
        "annual_price_increase": 0.04,
        "expansion_rate": 0.004,
        "discount_rate": 0.15,
        "partner_share": 0.10,
        "commission_rate": 0.15,
        "onboarding_fee": 40000,
        "hosting_cost_per_cust": 650,
        "support_cost_per_cust": 420,
        "services_cost_pct": 0.65,
        "licence_cost_pct": 0.03,
    },
}

# Seasonality of new customer wins (B2B software: weak summer, strong year end).
# Index 0 = January. The values average to 1.
NEW_CUSTOMER_SEASONALITY = [0.85, 0.90, 1.05, 1.00, 1.00, 0.95,
                            0.75, 0.70, 1.05, 1.10, 1.15, 1.50]

# Things that happened in 2026 and that the budget did not expect.
# They give the outlook something to explain.
EVENTS_2026 = {
    # mid-market churn goes up from April (a competitor launched a cheaper product)
    "midmarket_churn_from_april": 0.015,
    # a coupon campaign in Q2 raised the average mid-market discount
    "midmarket_discount_q2": 0.13,
    "midmarket_discount_after_q2": 0.10,
    # more mid-market deals come through partners
    "midmarket_partner_share": 0.36,
    # one extra large enterprise deal per month in Q3
    "enterprise_extra_wins_q3": 1,
}

# ---------------------------------------------------------------------------
# Budget and long-term plan assumptions (src/plan.py)
# Each year's plan starts from the drivers of the year before.
# ---------------------------------------------------------------------------
PLAN_ASSUMPTIONS = {
    2026: {  # budget set in December 2025
        "Mid-market": {"new_customers_growth": 0.12, "price_increase": 0.05},
        "Enterprise": {"new_customers_growth": 0.15, "price_increase": 0.04},
    },
    2027: {
        "Mid-market": {"new_customers_growth": 0.10, "price_increase": 0.04},
        "Enterprise": {"new_customers_growth": 0.15, "price_increase": 0.04},
    },
    2028: {
        "Mid-market": {"new_customers_growth": 0.08, "price_increase": 0.03},
        "Enterprise": {"new_customers_growth": 0.12, "price_increase": 0.03},
    },
    2029: {
        "Mid-market": {"new_customers_growth": 0.08, "price_increase": 0.03},
        "Enterprise": {"new_customers_growth": 0.10, "price_increase": 0.03},
    },
}

# ---------------------------------------------------------------------------
# Scenarios for the outlook: multipliers on the base forecast drivers
# ---------------------------------------------------------------------------
SCENARIOS = {
    "Downside": {"new_customers": 0.80, "churn_rate": 1.30, "discount_rate": 1.15},
    "Base": {"new_customers": 1.00, "churn_rate": 1.00, "discount_rate": 1.00},
    "Upside": {"new_customers": 1.15, "churn_rate": 0.85, "discount_rate": 0.95},
}

# Yearly increase of support cost per customer assumed in budget and plan (wage inflation)
SUPPORT_COST_INFLATION = 0.03
