"""
Run the whole project from the project folder:

    python src/main.py

Steps:
1. create synthetic actuals (drivers) and calculate the actual P&L
2. build the 2026 budget (as set in December 2025)
3. build the Q2 outlook (6+6) and the Q3 outlook (9+3)
4. compare budget vs outlooks and explain the difference with a bridge
5. scenarios, backtest and long-term plan
6. save tables, charts and the board report
"""

import pandas as pd

import config
from make_data import make_actual_drivers
from revenue_model import build_pnl, add_periods, closing_position
from forecast import make_outlook, opening_from_actuals, apply_scenario, backtest
from plan import make_budget, make_long_term_plan, plan_drivers
from variance import compare_versions, variance_table, bridge, segment_variance
import report

YEAR = config.OUTLOOK_YEAR
LAST_ACTUAL = pd.Timestamp(config.LAST_ACTUAL_MONTH)
Q2_CLOSE = pd.Timestamp(f"{YEAR}-06-01")


def run_scenarios(actual_drivers, outlook_drivers):
    """FY outlook, December ARR and next-year plan under each scenario."""
    rows = []
    for scenario in config.SCENARIOS:
        # this year: change only the forecast months
        drivers = apply_scenario(outlook_drivers, scenario, LAST_ACTUAL)
        opening = opening_from_actuals(actual_drivers, f"{YEAR - 1}-12-01")
        pnl = build_pnl(drivers, opening)

        # next year: plan drivers with the same scenario factors, starting from this scenario's December
        next_drivers = plan_drivers(drivers, YEAR + 1)
        next_drivers = apply_scenario(next_drivers, scenario, f"{YEAR}-12-01")
        next_pnl = build_pnl(next_drivers, closing_position(pnl, f"{YEAR}-12-01"))

        rows.append({
            "scenario": scenario,
            f"net_revenue_{YEAR}": pnl["net_revenue"].sum(),
            f"gross_margin_{YEAR}": pnl["gross_profit"].sum() / pnl["net_revenue"].sum(),
            f"arr_dec_{YEAR}": pnl.loc[pnl["month"] == pnl["month"].max(), "arr"].sum(),
            f"net_revenue_{YEAR + 1}": next_pnl["net_revenue"].sum(),
            f"gross_margin_{YEAR + 1}": next_pnl["gross_profit"].sum() / next_pnl["net_revenue"].sum(),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    # 1. actuals
    actual_drivers = make_actual_drivers()
    actual_drivers.to_csv("data/actual_drivers.csv", index=False)
    actual_pnl = add_periods(build_pnl(actual_drivers, config.OPENING))

    # 2. budget, built from the position at the end of last year
    opening_this_year = opening_from_actuals(actual_drivers, f"{YEAR - 1}-12-01")
    budget_drivers, budget_pnl = make_budget(actual_drivers, opening_this_year, YEAR)

    # 3. outlooks
    q2_drivers, q2_pnl = make_outlook(actual_drivers, Q2_CLOSE, YEAR)
    q3_drivers, q3_pnl = make_outlook(actual_drivers, LAST_ACTUAL, YEAR)
    q3_drivers_only = q3_drivers.drop(columns="is_actual")

    # 4. comparison and bridge
    versions = {"Budget": budget_pnl, "Q2 Outlook (6+6)": q2_pnl, "Q3 Outlook (9+3)": q3_pnl}
    quarterly = compare_versions(versions, "quarter")
    full_year = variance_table(budget_pnl, q3_pnl)
    revenue_bridge = bridge(budget_drivers, q3_drivers_only, opening_this_year)
    segments = segment_variance(budget_pnl, q3_pnl)

    # 5. scenarios, backtest, long-term plan
    scenarios = run_scenarios(actual_drivers, q3_drivers_only)

    backtest_scores = []
    backtest_detail = None
    for cutoff in ["2024-09-01", "2025-03-01", "2025-09-01"]:
        detail, scores = backtest(actual_drivers, cutoff)
        scores["cutoff"] = cutoff
        backtest_scores.append(scores)
        backtest_detail = detail  # keep the latest one for the chart
    backtest_scores = pd.concat(backtest_scores, ignore_index=True)

    long_term_plan = make_long_term_plan(q3_drivers_only, q3_pnl)

    # 6. save outputs
    actual_pnl.to_csv("outputs/actual_pnl.csv", index=False)
    budget_pnl.to_csv(f"outputs/budget_{YEAR}_pnl.csv", index=False)
    q3_pnl.to_csv(f"outputs/outlook_{YEAR}_q3_pnl.csv", index=False)
    quarterly.to_csv("outputs/versions_by_quarter.csv")
    full_year.to_csv("outputs/full_year_budget_vs_outlook.csv")
    revenue_bridge.to_csv("outputs/bridge_budget_to_outlook.csv", index=False)
    segments.to_csv("outputs/segment_variance.csv")
    scenarios.to_csv("outputs/scenarios.csv", index=False)
    backtest_scores.to_csv("outputs/backtest_scores.csv", index=False)
    long_term_plan.to_csv("outputs/long_term_plan.csv", index=False)

    report.make_charts(actual_pnl, budget_pnl, q2_pnl, q3_pnl, revenue_bridge,
                       scenarios, backtest_detail, long_term_plan, actual_drivers, q3_drivers, budget_drivers)
    report.write_board_report(actual_pnl, budget_pnl, budget_drivers, q2_pnl, q3_pnl, q3_drivers,
                              full_year, revenue_bridge, segments, scenarios,
                              backtest_scores, long_term_plan)

    print("Done. Tables in outputs/, charts in outputs/figures/, board report in reports/.")
    print()
    print(full_year.round(3).to_string())
