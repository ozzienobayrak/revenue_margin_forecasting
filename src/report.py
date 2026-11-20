"""
Charts and the quarterly board outlook report.
All numbers in the report are calculated here from the model outputs, nothing is typed in by hand.
"""

import matplotlib
matplotlib.use("Agg")  # save charts to files without opening a window
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates
import pandas as pd

import config
from revenue_model import summarise

YEAR = config.OUTLOOK_YEAR
FIG_DIR = "outputs/figures"
REPORT_PATH = f"reports/board_outlook_{YEAR}_Q3.md"

COLORS = {"actual": "#1f3b57", "budget": "#9aa5b1", "q2": "#e8a33d", "q3": "#d1495b", "plan": "#2a9d8f"}

plt.rcParams.update({
    "figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.3, "font.size": 10,
})


def eur_m(value):
    return f"€{value / 1e6:,.1f}m"


def eur_k(value):
    """Signed thousands, e.g. +€539k or -€628k."""
    sign = "+" if value >= 0 else "-"
    return f"{sign}€{abs(value) / 1e3:,.0f}k"


def pct(value, decimals=1):
    return f"{value * 100:.{decimals}f}%"


def millions_axis(ax):
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"€{x / 1e6:.1f}m"))


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def chart_monthly_revenue(actual_pnl, budget_pnl, q3_pnl, scenarios_monthly=None):
    actual = actual_pnl[actual_pnl["month"] >= f"{YEAR - 1}-01-01"].groupby("month")["net_revenue"].sum()
    budget = budget_pnl.groupby("month")["net_revenue"].sum()
    outlook = q3_pnl.groupby("month")["net_revenue"].sum()
    forecast = outlook[outlook.index >= actual.index.max()]  # start at last actual month so lines connect

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(actual.index, actual.values, color=COLORS["actual"], lw=2.2, label="Actual")
    ax.plot(budget.index, budget.values, color=COLORS["budget"], lw=2, ls="--", label=f"Budget {YEAR}")
    ax.plot(forecast.index, forecast.values, color=COLORS["q3"], lw=2.2, ls=":", marker="o", ms=4,
            label="Q3 outlook forecast")
    ax.set_title("Monthly net revenue: actual, budget and Q3 outlook", loc="left", fontweight="bold")
    millions_axis(ax)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/01_monthly_net_revenue.png")
    plt.close(fig)


def chart_bridge(revenue_bridge):
    """Waterfall chart from budget to outlook net revenue."""
    # steps with no effect on revenue (e.g. unit costs only affect gross profit) are left out of the chart
    revenue_bridge = revenue_bridge[revenue_bridge["net_revenue"].abs() > 1]
    steps = revenue_bridge["step"].tolist()
    values = revenue_bridge["net_revenue"].tolist()

    bottoms, heights, colors = [], [], []
    running = 0
    for i, value in enumerate(values):
        if i == 0 or i == len(values) - 1:  # budget and outlook bars start at zero
            bottoms.append(0)
            heights.append(value)
            colors.append(COLORS["budget"] if i == 0 else COLORS["q3"])
            running = value
        else:
            bottoms.append(running if value >= 0 else running + value)
            heights.append(abs(value))
            colors.append("#4c956c" if value >= 0 else "#bc4749")
            running += value

    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar(steps, heights, bottom=bottoms, color=colors, width=0.6)
    for i, value in enumerate(values):
        label = eur_m(value) if i in (0, len(values) - 1) else eur_k(value)
        ax.text(i, bottoms[i] + heights[i], label, ha="center", va="bottom", fontsize=9)

    low = min(bottoms[1:-1] + [values[-1]]) * 0.97
    high = max(b + h for b, h in zip(bottoms, heights)) * 1.01
    ax.set_ylim(low, high)
    millions_axis(ax)
    ax.set_title(f"FY{YEAR} net revenue: budget to Q3 outlook", loc="left", fontweight="bold")
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/02_bridge_budget_to_outlook.png")
    plt.close(fig)


def chart_quarterly_versions(budget_pnl, q2_pnl, q3_pnl):
    versions = {"Budget": budget_pnl, "Q2 outlook (6+6)": q2_pnl, "Q3 outlook (9+3)": q3_pnl}
    colors = [COLORS["budget"], COLORS["q2"], COLORS["q3"]]
    revenue = pd.DataFrame({name: summarise(pnl, "quarter")["net_revenue"] for name, pnl in versions.items()})
    margin = pd.DataFrame({name: summarise(pnl, "quarter")["gross_margin"] for name, pnl in versions.items()})

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    revenue.plot(kind="bar", ax=ax1, color=colors, width=0.75, rot=0)
    ax1.set_title("Net revenue by quarter", loc="left", fontweight="bold")
    ax1.set_xlabel("")
    ax1.set_ylim(revenue.min().min() * 0.9, revenue.max().max() * 1.03)
    millions_axis(ax1)
    ax1.legend(frameon=False, fontsize=8)

    for name, color in zip(margin.columns, colors):
        ax2.plot(margin.index, margin[name] * 100, marker="o", color=color, lw=2, label=name)
    ax2.set_title("Gross margin by quarter (%)", loc="left", fontweight="bold")
    ax2.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/03_versions_by_quarter.png")
    plt.close(fig)


def chart_drivers(actual_drivers, q3_drivers, budget_drivers):
    """The three drivers behind the variance: mid-market churn, discount, enterprise wins."""
    data = q3_drivers[q3_drivers["month"].dt.year == YEAR]
    history = actual_drivers[actual_drivers["month"].dt.year == YEAR - 1]
    data = pd.concat([history.assign(is_actual=True), data])

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    panels = [
        ("Mid-market", "churn_rate", "Mid-market monthly churn (%)", 100),
        ("Mid-market", "discount_rate", "Mid-market average discount (%)", 100),
        ("Enterprise", "new_customers", "Enterprise new customers", 1),
    ]
    for ax, (segment, driver, title, scale) in zip(axes, panels):
        seg = data[data["segment"] == segment]
        act = seg[seg["is_actual"]]
        fc = seg[~seg["is_actual"]]
        ax.plot(act["month"], act[driver] * scale, color=COLORS["actual"], lw=2, label="Actual")
        ax.plot(fc["month"], fc[driver] * scale, color=COLORS["q3"], lw=2, ls=":", marker="o", ms=3,
                label="Forecast")
        bud = budget_drivers[budget_drivers["segment"] == segment]
        ax.plot(bud["month"], bud[driver] * scale, color=COLORS["budget"], lw=2, ls="--", label="Budget")
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %y"))
        ax.set_title(title, loc="left", fontweight="bold", fontsize=10)
        ax.tick_params(axis="x", rotation=45)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/04_key_drivers.png")
    plt.close(fig)


def chart_backtest(backtest_detail):
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(backtest_detail.index, backtest_detail["actual"], color=COLORS["actual"], lw=2.2, label="Actual")
    ax.plot(backtest_detail.index, backtest_detail["driver_based"], color=COLORS["q3"], lw=2,
            label="Driver-based forecast")
    ax.plot(backtest_detail.index, backtest_detail["seasonal_naive"], color=COLORS["budget"], lw=1.6, ls="--",
            label="Seasonal naive")
    ax.plot(backtest_detail.index, backtest_detail["holt_winters_total"], color=COLORS["q2"], lw=1.6, ls="-.",
            label="Holt-Winters on total revenue")
    start = backtest_detail.index.min().strftime("%b %Y")
    ax.set_title(f"Backtest: 12-month forecast made before {start} vs actual", loc="left", fontweight="bold")
    millions_axis(ax)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/05_backtest.png")
    plt.close(fig)


def chart_long_term_plan(actual_pnl, q3_pnl, long_term_plan):
    actual = summarise(actual_pnl[actual_pnl["year"] < YEAR], "year")
    outlook = summarise(q3_pnl, "year")
    plan = summarise(long_term_plan, "year")
    table = pd.concat([actual, outlook, plan])
    colors = ([COLORS["actual"]] * len(actual) + [COLORS["q3"]] * len(outlook) + [COLORS["plan"]] * len(plan))

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(table.index.astype(str), table["net_revenue"], color=colors, width=0.6)
    for x, (revenue, margin) in enumerate(zip(table["net_revenue"], table["gross_margin"])):
        ax.text(x, revenue, f"{eur_m(revenue)}\nGM {pct(margin, 0)}", ha="center", va="bottom", fontsize=8)
    ax.set_ylim(0, table["net_revenue"].max() * 1.18)
    millions_axis(ax)
    ax.set_title("Net revenue by year: actual, outlook and long-term plan", loc="left", fontweight="bold")
    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS[k]) for k in ["actual", "q3", "plan"]]
    ax.legend(handles, ["Actual", f"{YEAR} Q3 outlook", "Plan"], frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(f"{FIG_DIR}/06_long_term_plan.png")
    plt.close(fig)


def make_charts(actual_pnl, budget_pnl, q2_pnl, q3_pnl, revenue_bridge, scenarios,
                backtest_detail, long_term_plan, actual_drivers, q3_drivers, budget_drivers):
    chart_monthly_revenue(actual_pnl, budget_pnl, q3_pnl)
    chart_bridge(revenue_bridge)
    chart_quarterly_versions(budget_pnl, q2_pnl, q3_pnl)
    chart_drivers(actual_drivers, q3_drivers, budget_drivers)
    chart_backtest(backtest_detail)
    chart_long_term_plan(actual_pnl, q3_pnl, long_term_plan)


# ---------------------------------------------------------------------------
# Board report (Markdown)
# ---------------------------------------------------------------------------

def markdown_table(df):
    """Simple Markdown table without extra packages."""
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    line = "|" + "|".join("---" for _ in df.columns) + "|"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.values]
    return "\n".join([header, line] + rows)


def write_board_report(actual_pnl, budget_pnl, budget_drivers, q2_pnl, q3_pnl, q3_drivers,
                       full_year, revenue_bridge, segments, scenarios, backtest_scores, long_term_plan):
    fy = full_year
    q2 = summarise(q2_pnl, "year").iloc[0]
    prior = summarise(actual_pnl[actual_pnl["year"] == YEAR - 1], "year").iloc[0]
    q4_budget = summarise(budget_pnl, "quarter").loc[f"{YEAR}-Q4"]
    q4_outlook = summarise(q3_pnl, "quarter").loc[f"{YEAR}-Q4"]

    # driver facts used in the commentary
    actual_ytd = q3_drivers[q3_drivers["is_actual"]]
    mm_act = actual_ytd[actual_ytd["segment"] == "Mid-market"]
    mm_bud = budget_drivers[budget_drivers["segment"] == "Mid-market"]
    ent_act = actual_ytd[actual_ytd["segment"] == "Enterprise"]
    ent_bud = budget_drivers[(budget_drivers["segment"] == "Enterprise") &
                             (budget_drivers["month"] <= actual_ytd["month"].max())]
    churn_apr_sep = mm_act[mm_act["month"] >= f"{YEAR}-04-01"]["churn_rate"].mean()
    churn_budget = mm_bud["churn_rate"].mean()
    discount_q2 = mm_act[mm_act["month"].dt.quarter == 2]["discount_rate"].mean()
    discount_q3 = mm_act[mm_act["month"].dt.quarter == 3]["discount_rate"].mean()
    discount_budget = mm_bud["discount_rate"].mean()
    partner_ytd = mm_act["partner_share"].mean()
    partner_budget = mm_bud["partner_share"].mean()

    steps = revenue_bridge.set_index("step")["net_revenue"]
    middle = steps.iloc[1:-1]

    # ---- headline table
    headline = pd.DataFrame({
        "": ["Net revenue", "  of which subscription", "  of which services", "Gross profit", "Gross margin",
             "Customers (Dec)", "ARR (Dec)"],
        f"Budget {YEAR}": [eur_m(fy.loc["net_revenue", "budget"]), eur_m(fy.loc["net_subscription", "budget"]),
                          eur_m(fy.loc["services_revenue", "budget"]), eur_m(fy.loc["gross_profit", "budget"]),
                          pct(fy.loc["gross_margin", "budget"]), f"{fy.loc['closing_customers', 'budget']:,.0f}",
                          eur_m(fy.loc["arr", "budget"])],
        "Q2 outlook": [eur_m(q2["net_revenue"]), eur_m(q2["net_subscription"]), eur_m(q2["services_revenue"]),
                       eur_m(q2["gross_profit"]), pct(q2["gross_margin"]), f"{q2['closing_customers']:,.0f}",
                       eur_m(q2["arr"])],
        "Q3 outlook": [eur_m(fy.loc["net_revenue", "outlook"]), eur_m(fy.loc["net_subscription", "outlook"]),
                       eur_m(fy.loc["services_revenue", "outlook"]), eur_m(fy.loc["gross_profit", "outlook"]),
                       pct(fy.loc["gross_margin", "outlook"]), f"{fy.loc['closing_customers', 'outlook']:,.0f}",
                       eur_m(fy.loc["arr", "outlook"])],
        "Q3 outlook vs budget": [
            f"{eur_k(fy.loc['net_revenue', 'variance'])} ({fy.loc['net_revenue', 'variance_pct']:+.1f}%)",
            f"{eur_k(fy.loc['net_subscription', 'variance'])} ({fy.loc['net_subscription', 'variance_pct']:+.1f}%)",
            f"{eur_k(fy.loc['services_revenue', 'variance'])} ({fy.loc['services_revenue', 'variance_pct']:+.1f}%)",
            f"{eur_k(fy.loc['gross_profit', 'variance'])} ({fy.loc['gross_profit', 'variance_pct']:+.1f}%)",
            f"{fy.loc['gross_margin', 'variance_pct']:+.1f} pp",
            f"{fy.loc['closing_customers', 'variance']:+,.0f}",
            f"{eur_k(fy.loc['arr', 'variance'])} ({fy.loc['arr', 'variance_pct']:+.1f}%)",
        ],
    })

    bridge_table = pd.DataFrame({
        "Step": revenue_bridge["step"],
        "Net revenue": [eur_m(v) if i in (0, len(revenue_bridge) - 1) else eur_k(v)
                        for i, v in enumerate(revenue_bridge["net_revenue"])],
        "Gross profit": [eur_m(v) if i in (0, len(revenue_bridge) - 1) else eur_k(v)
                         for i, v in enumerate(revenue_bridge["gross_profit"])],
    })

    segment_table = pd.DataFrame({
        "Segment": segments.index,
        "Budget net revenue": [eur_m(v) for v in segments["budget_net_revenue"]],
        "Outlook net revenue": [eur_m(v) for v in segments["outlook_net_revenue"]],
        "Variance": [eur_k(v) for v in segments["net_revenue_variance"]],
        "Gross profit variance": [eur_k(v) for v in segments["gross_profit_variance"]],
    })

    scenario_table = pd.DataFrame({
        "Scenario": scenarios["scenario"],
        f"Net revenue {YEAR}": [eur_m(v) for v in scenarios[f"net_revenue_{YEAR}"]],
        f"ARR Dec {YEAR}": [eur_m(v) for v in scenarios[f"arr_dec_{YEAR}"]],
        f"Net revenue {YEAR + 1}": [eur_m(v) for v in scenarios[f"net_revenue_{YEAR + 1}"]],
        f"Gross margin {YEAR + 1}": [pct(v) for v in scenarios[f"gross_margin_{YEAR + 1}"]],
    })
    scenario_rules = "; ".join(
        f"{name}: new customers x{s['new_customers']}, churn x{s['churn_rate']}, discount x{s['discount_rate']}"
        for name, s in config.SCENARIOS.items() if name != "Base")

    plan = summarise(long_term_plan, "year")
    outlook_year = summarise(q3_pnl, "year")
    plan_all = pd.concat([outlook_year, plan])
    plan_table = pd.DataFrame({
        "Year": [f"{YEAR} (Q3 outlook)"] + [str(y) for y in plan.index],
        "Net revenue": [eur_m(v) for v in plan_all["net_revenue"]],
        "Growth": [pct(fy.loc["net_revenue", "outlook"] / prior["net_revenue"] - 1)] +
                  [pct(v) for v in plan_all["net_revenue"].pct_change().iloc[1:]],
        "Gross margin": [pct(v) for v in plan_all["gross_margin"]],
        "Customers (Dec)": [f"{v:,.0f}" for v in plan_all["closing_customers"]],
        "ARR (Dec)": [eur_m(v) for v in plan_all["arr"]],
    })

    avg_scores = backtest_scores.groupby("method", sort=False)[["mape_net_revenue_pct", "full_period_error_pct"]]
    avg_scores = avg_scores.agg(lambda x: x.abs().mean()).reset_index()
    backtest_table = pd.DataFrame({
        "Method": avg_scores["method"],
        "Average monthly error (MAPE)": [f"{v:.1f}%" for v in avg_scores["mape_net_revenue_pct"]],
        "Average error on 12-month total": [f"{v:.1f}%" for v in avg_scores["full_period_error_pct"]],
    })

    worst = middle.idxmin()
    best = middle.idxmax()
    rev_var = fy.loc["net_revenue", "variance"]
    direction = "below" if rev_var < 0 else "above"

    text = f"""# Quarterly outlook {YEAR}: Q3 (9+3)

*Fictional EHS / ESG software company. Synthetic data. Actuals to September {YEAR}, forecast October to December.*

## Summary

- The Q3 outlook for net revenue is **{eur_m(fy.loc['net_revenue', 'outlook'])}**, €{abs(rev_var) / 1e3:,.0f}k ({abs(fy.loc['net_revenue', 'variance_pct']):.1f}%) {direction} budget and {pct(fy.loc['net_revenue', 'outlook'] / prior['net_revenue'] - 1)} above {YEAR - 1}.
- Compared with the Q2 outlook, the full-year number changed by {eur_k(fy.loc['net_revenue', 'outlook'] - q2['net_revenue'])}. The Q2 outlook was made while the coupon campaign was running and assumed the higher discount would continue; in Q3 the discount came down and enterprise wins were strong.
- Gross margin is {pct(fy.loc['gross_margin', 'outlook'])}, {fy.loc['gross_margin', 'variance_pct']:+.1f} pp against budget.
- The largest negative item in the bridge is **{worst.lower()}** ({eur_k(middle[worst])}); the largest positive item is **{best.lower()}** ({eur_k(middle[best])}).
- December ARR is expected at {eur_m(fy.loc['arr', 'outlook'])} against {eur_m(fy.loc['arr', 'budget'])} in the budget. This is the starting point for the {YEAR + 1} budget.

![Monthly net revenue](../outputs/figures/01_monthly_net_revenue.png)

## Full year {YEAR}: budget vs outlook

{markdown_table(headline)}

## What explains the difference

{markdown_table(bridge_table)}

![Bridge](../outputs/figures/02_bridge_budget_to_outlook.png)

- **Churn.** Mid-market churn averaged {pct(churn_apr_sep, 2)} per month from April to September, against {pct(churn_budget, 2)} in the budget. Each month we lose more customers than planned, and the effect grows every month because lost customers do not come back in the forecast.
- **Discounts.** The Q2 coupon campaign raised the average mid-market discount to {pct(discount_q2)} (budget {pct(discount_budget)}). In Q3 it came down to {pct(discount_q3)} but did not go back to the budget level.
- **Partner commission.** The share of mid-market revenue sold through partners is {pct(partner_ytd)} so far this year (budget {pct(partner_budget)}), so we pay more commission.
- **New customers.** Enterprise won {ent_act['new_customers'].sum():.0f} new customers to September against {ent_bud['new_customers'].sum():.0f} in the budget. This brings both subscription and onboarding revenue and offsets part of the mid-market gap.

{markdown_table(segment_table)}

![Key drivers](../outputs/figures/04_key_drivers.png)

## By quarter

Q4 net revenue: budget {eur_m(q4_budget['net_revenue'])}, Q3 outlook {eur_m(q4_outlook['net_revenue'])} ({eur_k(q4_outlook['net_revenue'] - q4_budget['net_revenue'])}).

![Versions by quarter](../outputs/figures/03_versions_by_quarter.png)

## Scenarios

Only Q4 is still open in {YEAR}, so the range for this year is narrow. The effect on next year is larger, because the December customer base and the same driver changes carry into {YEAR + 1}.

{markdown_table(scenario_table)}

Scenario rules (applied to forecast months only): {scenario_rules}.

## Risks and opportunities

- Risk: mid-market churn stays at the current level or rises further. Worth a churn analysis by customer cohort and by reason for cancellation, together with Customer Success.
- Risk: discounts stay above budget if sales keeps using coupons to close deals.
- Opportunity: enterprise wins are ahead of budget. If Q4 wins are in line with Q3, services revenue and ARR end above the outlook.
- Opportunity: the January price increase for {YEAR + 1} is not yet decided. Each 1% on the list price adds roughly {eur_m(fy.loc['arr', 'outlook'] * 0.01)} to ARR.

## Long-term plan

{markdown_table(plan_table)}

![Long-term plan](../outputs/figures/06_long_term_plan.png)

## How reliable is the forecast?

The same forecast method was tested on three past periods (forecast made in September 2024, March 2025 and September 2025, each for the next 12 months) and compared with two simple benchmarks.

{markdown_table(backtest_table)}

![Backtest](../outputs/figures/05_backtest.png)

Subscription revenue is stable, so even simple methods are close on the total. The value of the driver-based forecast is that every change can be explained by a business driver (customers, churn, price, discount, commission), and the same drivers can be used for budget, outlook and plan.
"""
    with open(REPORT_PATH, "w") as f:
        f.write(text)
