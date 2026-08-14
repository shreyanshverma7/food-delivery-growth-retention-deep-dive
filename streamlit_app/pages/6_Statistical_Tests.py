import math

import streamlit as st
from scipy.stats import chi2_contingency, norm

from common import inject_css, render_sidebar_filters, render_stat_tile, run_query

st.set_page_config(page_title="Statistical Tests · Food Delivery Analytics", page_icon="🛵", layout="wide")
inject_css()
st.title("Statistical rigor pass")
st.caption(
    "Every rate comparison in this project, chi-square tested for whether the spread is "
    "distinguishable from chance — plus a live power calculator for the A/B test."
)
render_sidebar_filters()


def run_chi2(label, sql):
    df = run_query(sql)
    if len(df) < 2:
        return
    chi2, p, dof, _ = chi2_contingency(df.iloc[:, 1:3].values)
    verdict = "SIGNIFICANT" if p < 0.05 else "not significant"
    with st.container(border=True):
        st.markdown(f"**{label}** — chi2={chi2:.2f}, dof={dof}, p={p:.4f} — {verdict} at alpha=0.05")
        with st.expander("Show underlying table"):
            st.dataframe(df, width='stretch', hide_index=True)


with st.spinner("Running significance tests…"):
    run_chi2(
        "Cancellation rate by city",
        """
        SELECT u.city,
               SUM(CASE WHEN o.order_status = 'delivered' THEN 1 ELSE 0 END) AS delivered,
               SUM(CASE WHEN o.order_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
        FROM orders o JOIN users u ON u.user_id = o.user_id GROUP BY u.city ORDER BY u.city
        """,
    )
    run_chi2(
        "Cancellation rate by payment method",
        """
        SELECT payment_method,
               SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END) AS delivered,
               SUM(CASE WHEN order_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
        FROM orders GROUP BY payment_method ORDER BY payment_method
        """,
    )
    run_chi2(
        "app_open → order_placed conversion by platform",
        """
        SELECT platform,
               COUNT(DISTINCT CASE WHEN event_name = 'order_placed' THEN user_id END) AS converted,
               COUNT(DISTINCT CASE WHEN event_name = 'app_open' THEN user_id END)
                 - COUNT(DISTINCT CASE WHEN event_name = 'order_placed' THEN user_id END) AS not_converted
        FROM app_events GROUP BY platform ORDER BY platform
        """,
    )
    run_chi2(
        "Reorder rate by first-delivery-time bucket",
        """
        WITH first_order AS (
            SELECT user_id, delivery_time_min,
                   ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_date, order_id) AS rn
            FROM orders WHERE order_status = 'delivered'
        ),
        delivered_counts AS (
            SELECT user_id, COUNT(*) AS delivered_orders
            FROM orders WHERE order_status = 'delivered' GROUP BY user_id
        )
        SELECT
            CASE WHEN f.delivery_time_min < 30 THEN '1: <30 min'
                 WHEN f.delivery_time_min < 45 THEN '2: 30-44 min'
                 WHEN f.delivery_time_min < 60 THEN '3: 45-59 min'
                 ELSE '4: 60+ min' END AS bucket,
            SUM(CASE WHEN d.delivered_orders >= 2 THEN 1 ELSE 0 END) AS reordered,
            SUM(CASE WHEN d.delivered_orders < 2 THEN 1 ELSE 0 END) AS did_not_reorder
        FROM first_order f JOIN delivered_counts d ON d.user_id = f.user_id
        WHERE f.rn = 1 GROUP BY bucket ORDER BY bucket
        """,
    )

st.divider()
st.subheader("A/B test power calculator")
st.caption(
    "How many users per group would a checkout-flow experiment need to reliably detect a given "
    "lift? Adjust the assumptions and see the required sample size update live."
)

with st.spinner("Loading baseline conversion…"):
    baseline_row = run_query(
        """
        SELECT
            COUNT(DISTINCT CASE WHEN event_name = 'checkout' THEN user_id END) AS checkout_users,
            COUNT(DISTINCT CASE WHEN event_name = 'order_placed' THEN user_id END) AS ordered_users
        FROM app_events
        """
    ).iloc[0]
real_baseline = baseline_row["ordered_users"] / baseline_row["checkout_users"]

with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    baseline_pct = c1.slider("Baseline conversion %", 1.0, 99.0, round(real_baseline * 100, 1), 0.5)
    lift_pp = c2.slider("Assumed lift (percentage points)", 0.5, 20.0, 6.0, 0.5)
    power_pct = c3.slider("Desired power %", 50, 99, 80, 1)

    p1 = baseline_pct / 100
    p2 = p1 + lift_pp / 100
    alpha = 0.05
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power_pct / 100)
    n = ((z_alpha + z_beta) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2))) / (lift_pp / 100) ** 2
    required_n = math.ceil(n)

    render_stat_tile("Required sample size per group", f"{required_n:,}")
    st.caption(
        f"Real checkout population available: **{int(baseline_row['checkout_users']):,} users** "
        f"(~{int(baseline_row['checkout_users'])//2:,} per group if split 50/50). "
        + ("This is enough to detect the assumed lift." if baseline_row["checkout_users"] // 2 >= required_n
           else "**Not enough** — this is exactly why the simulated A/B test in `analysis/ab_test_simulation.py` "
                "came back non-significant at a 6pp assumed lift.")
    )
