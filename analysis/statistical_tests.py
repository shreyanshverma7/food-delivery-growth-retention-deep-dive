"""
Statistical rigor pass: are the differences we're citing in the README real,
or noise? Every headline number in the SQL deliverables is a point estimate;
this script checks which ones survive a significance test at realistic
sample sizes, and sizes the A/B test properly instead of eyeballing p-values.
"""

import sqlite3
from pathlib import Path

from scipy.stats import chi2_contingency, norm

DB_PATH = Path(__file__).parent.parent / "database" / "zomato.db"


def chi_square_on_groups(con, group_col, group_table_sql):
    """Runs a chi-square test of independence on a [group] x [delivered, cancelled] table."""
    rows = con.execute(group_table_sql).fetchall()
    labels = [r[0] for r in rows]
    table = [[r[1], r[2]] for r in rows]  # [delivered, cancelled] per group
    chi2, p, dof, _ = chi2_contingency(table)
    return labels, table, chi2, p, dof


def test_cancellation_by_city(con):
    sql = """
        SELECT u.city,
               SUM(CASE WHEN o.order_status = 'delivered' THEN 1 ELSE 0 END) AS delivered,
               SUM(CASE WHEN o.order_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
        FROM orders o JOIN users u ON u.user_id = o.user_id
        GROUP BY u.city ORDER BY u.city
    """
    labels, table, chi2, p, dof = chi_square_on_groups(con, "city", sql)
    print("Cancellation rate by CITY")
    print(f"  chi2 = {chi2:.3f}, dof = {dof}, p = {p:.4f}")
    print(f"  -> {'SIGNIFICANT' if p < 0.05 else 'NOT significant'} at alpha=0.05: the city-to-city"
          f" differences in the README {'reflect a real effect.' if p < 0.05 else 'are consistent with random noise.'}")
    print()


def test_cancellation_by_payment(con):
    sql = """
        SELECT payment_method,
               SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END) AS delivered,
               SUM(CASE WHEN order_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
        FROM orders
        GROUP BY payment_method ORDER BY payment_method
    """
    labels, table, chi2, p, dof = chi_square_on_groups(con, "payment_method", sql)
    print("Cancellation rate by PAYMENT METHOD")
    print(f"  chi2 = {chi2:.3f}, dof = {dof}, p = {p:.4f}")
    print(f"  -> {'SIGNIFICANT' if p < 0.05 else 'NOT significant'} at alpha=0.05: the payment-method"
          f" differences {'reflect a real effect' if p < 0.05 else 'are consistent with random noise'}"
          f" — UPI's higher cancellation rate is {'likely real.' if p < 0.05 else 'not distinguishable from chance at this sample size.'}")
    print()


def test_platform_conversion(con):
    sql = """
        SELECT platform,
               COUNT(DISTINCT CASE WHEN event_name = 'order_placed' THEN user_id END) AS converted,
               COUNT(DISTINCT CASE WHEN event_name = 'app_open' THEN user_id END)
                 - COUNT(DISTINCT CASE WHEN event_name = 'order_placed' THEN user_id END) AS not_converted
        FROM app_events
        GROUP BY platform ORDER BY platform
    """
    labels, table, chi2, p, dof = chi_square_on_groups(con, "platform", sql)
    print("app_open -> order_placed conversion by PLATFORM")
    print(f"  chi2 = {chi2:.3f}, dof = {dof}, p = {p:.4f}")
    print(f"  -> {'SIGNIFICANT' if p < 0.05 else 'NOT significant'} at alpha=0.05: iOS/Android/Web conversion"
          f" {'differ for a real reason, worth investigating per-platform UX.' if p < 0.05 else 'is effectively the same platform-to-platform — no platform-specific funnel fix is indicated by this data.'}")
    print()


def test_delivery_time_reorder(con):
    sql = """
        WITH first_order AS (
            SELECT user_id, delivery_time_min,
                   ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_date, order_id) AS rn
            FROM orders WHERE order_status = 'delivered'
        ),
        delivered_counts AS (
            SELECT user_id, COUNT(*) AS delivered_orders
            FROM orders WHERE order_status = 'delivered' GROUP BY user_id
        ),
        bucketed AS (
            SELECT
                CASE WHEN f.delivery_time_min < 30 THEN '1: <30 min'
                     WHEN f.delivery_time_min < 45 THEN '2: 30-44 min'
                     WHEN f.delivery_time_min < 60 THEN '3: 45-59 min'
                     ELSE '4: 60+ min' END AS bucket,
                d.delivered_orders
            FROM first_order f JOIN delivered_counts d ON d.user_id = f.user_id
            WHERE f.rn = 1
        )
        SELECT bucket,
               SUM(CASE WHEN delivered_orders >= 2 THEN 1 ELSE 0 END) AS reordered,
               SUM(CASE WHEN delivered_orders < 2 THEN 1 ELSE 0 END) AS did_not_reorder
        FROM bucketed GROUP BY bucket ORDER BY bucket
    """
    labels, table, chi2, p, dof = chi_square_on_groups(con, "bucket", sql)
    print("Reorder rate by FIRST-ORDER DELIVERY-TIME bucket")
    print(f"  chi2 = {chi2:.3f}, dof = {dof}, p = {p:.4f}")
    print(f"  -> {'SIGNIFICANT' if p < 0.05 else 'NOT significant'} at alpha=0.05: a slow first delivery"
          f" {'measurably hurts repeat purchase in this data.' if p < 0.05 else 'shows no measurable effect on repeat purchase here — the bucket-to-bucket spread is noise, not a real delivery-quality-to-retention link.'}")
    print()


def ab_test_power_analysis(con):
    """How many users per group would the checkout-flow test need to reliably
    detect the assumed lift used in analysis/ab_test_simulation.py?"""
    baseline = con.execute(
        "SELECT COUNT(DISTINCT user_id) FROM app_events WHERE event_name = 'order_placed'"
    ).fetchone()[0] / con.execute(
        "SELECT COUNT(DISTINCT user_id) FROM app_events WHERE event_name = 'checkout'"
    ).fetchone()[0]

    alpha, power = 0.05, 0.80
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)

    print("A/B TEST POWER ANALYSIS (checkout -> order_placed)")
    print(f"  Real observed baseline: {baseline*100:.2f}%")
    print(f"  {'lift (pp)':>10}  {'required n / group':>20}")
    for lift_pp in (3, 6, 10):
        p2 = baseline + lift_pp / 100
        n = ((z_alpha + z_beta) ** 2 * (baseline * (1 - baseline) + p2 * (1 - p2))) / (lift_pp / 100) ** 2
        print(f"  {lift_pp:>10}  {math_ceil(n):>20,}")
    checkout_users = con.execute(
        "SELECT COUNT(DISTINCT user_id) FROM app_events WHERE event_name = 'checkout'"
    ).fetchone()[0]
    print(f"\n  Actual checkout population available: {checkout_users} users (~{checkout_users//2} per group"
          " if split 50/50)")
    print("  -> This is why the simulated +6pp result in ab_test_simulation.py came back non-significant:")
    print("     the real checkout traffic is well under what a 6pp lift needs to be reliably detected.")
    print()


def math_ceil(x):
    import math
    return math.ceil(x)


def main():
    con = sqlite3.connect(DB_PATH)
    print("=" * 76)
    print("STATISTICAL RIGOR PASS")
    print("=" * 76)
    print()
    test_cancellation_by_city(con)
    test_cancellation_by_payment(con)
    test_platform_conversion(con)
    test_delivery_time_reorder(con)
    ab_test_power_analysis(con)
    con.close()


if __name__ == "__main__":
    main()
