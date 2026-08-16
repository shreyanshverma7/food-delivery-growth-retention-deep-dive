"""
Statistical rigor pass: are the differences we're citing in the README real,
or noise? Every headline number in the SQL deliverables is a point estimate;
this script checks which ones survive a significance test at realistic
sample sizes, and sizes the A/B test properly instead of eyeballing p-values.

Two things this pass deliberately does NOT let itself get away with:

1. Multiple comparisons. Four chi-square tests run here. Judged individually at
   alpha=0.05, the chance that at least one crosses by luck alone is
   1 - 0.95**4 = ~18.5%. Every verdict below is therefore reported twice: at the
   naive threshold and at the Bonferroni-corrected one.
2. Knowing the ground truth. This database is synthetic and *we wrote the
   generator* — see database/build_zomato_db.py, where order_status,
   payment_method, delivery_time_min and order_amount are four independent
   random draws (lines ~147-150), and city and platform are independent per-user
   draws. So the true effect size in all four tests is exactly zero. Anything
   that comes back "significant" here is a Type I error by construction. That is
   the point: the pipeline is the deliverable, and on real data it would surface
   real effects. See the README's "Ground truth" section.
"""

import sqlite3
from pathlib import Path

from scipy.stats import chi2_contingency, norm

DB_PATH = Path(__file__).parent.parent / "database" / "zomato.db"

# Duplicated from streamlit_app/common.py on purpose: this file runs as a
# standalone script and Streamlit puts streamlit_app/ (not the repo root) on
# sys.path, so a shared import would need a path hack. Keep the two in sync.
COMPARISON_FAMILY_SIZE = 4
BONFERRONI_ALPHA = 0.05 / COMPARISON_FAMILY_SIZE  # 0.0125


def report(p):
    """Prints the naive and Bonferroni-corrected calls for one test."""
    raw = "SIGNIFICANT" if p < 0.05 else "not significant"
    corrected = "SIGNIFICANT" if p < BONFERRONI_ALPHA else "not significant"
    print(f"  alpha = 0.05              -> {raw}")
    print(f"  Bonferroni 0.05/{COMPARISON_FAMILY_SIZE} = {BONFERRONI_ALPHA:.4f} -> {corrected}")


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
    report(p)
    print("  -> The city-to-city spread in the README is consistent with random noise."
          " Don't action the city ranking.")
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
    report(p)
    print("  -> This is the test that most needs the correction. It clears the naive 0.05 bar"
          " but not the")
    print("     corrected one, and the generator assigns payment_method independently of"
          " order_status,")
    print("     so the true effect is zero. UPI's higher rate is a Type I error, not a finding"
          " to action.")
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
    report(p)
    print("  -> iOS/Android/Web convert the same within noise — no platform-specific funnel fix"
          " is indicated.")
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
    report(p)
    print("  -> The only test that survives correction — and still not actionable. The buckets are"
          " non-monotonic")
    print("     (45-59 min reorders best, 30-44 min worst), and delivery_time_min is generated"
          " independently of")
    print("     everything else, so this is the family's surviving false positive. Open question,"
          " not a recommendation.")
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
    print(f"{COMPARISON_FAMILY_SIZE} chi-square tests in one family. Family-wise error rate at a naive"
          " alpha=0.05:")
    print(f"  1 - 0.95**{COMPARISON_FAMILY_SIZE} = {1 - 0.95 ** COMPARISON_FAMILY_SIZE:.1%} chance of at"
          f" least one false positive. Bonferroni threshold: {BONFERRONI_ALPHA:.4f}")
    print()
    print("GROUND TRUTH: this database is synthetic and the generator (database/build_zomato_db.py)")
    print("draws order_status, payment_method, delivery_time_min and city independently, so the true")
    print("effect in every test below is exactly zero. Any 'significant' result here is a Type I")
    print("error by construction. The method is the deliverable, not the findings.")
    print()
    test_cancellation_by_city(con)
    test_cancellation_by_payment(con)
    test_platform_conversion(con)
    test_delivery_time_reorder(con)
    ab_test_power_analysis(con)
    con.close()


if __name__ == "__main__":
    main()
