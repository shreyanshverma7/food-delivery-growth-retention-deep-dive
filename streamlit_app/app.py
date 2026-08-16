import streamlit as st
from common import (
    fmt_money,
    in_clause,
    inject_css,
    render_sidebar_filters,
    render_stat_tile,
    run_query,
)

st.set_page_config(
    page_title="Overview · Food Delivery Analytics",
    page_icon="🛵",
    layout="wide",
)
inject_css()

st.title("Food-Delivery Growth & Retention Deep-Dive")
st.caption(
    "6,387 orders across 2,000 users, 300 restaurants, and 7 cities over 2024 — "
    "where the funnel leaks, which cohorts stick, what drives GMV, and where "
    "cancellations are quietly costing the most."
)

f = render_sidebar_filters()
placeholders, city_params = in_clause(f["cities"])
pay_placeholders, pay_params = in_clause(f["payments"])
plat_placeholders, plat_params = in_clause(f["platforms"])

with st.spinner("Loading overview…"):
    gmv_row = run_query(
        f"""
        SELECT ROUND(SUM(o.order_amount), 2) AS gmv, COUNT(*) AS orders
        FROM orders o JOIN users u ON u.user_id = o.user_id
        WHERE o.order_status = 'delivered'
          AND strftime('%Y-%m', o.order_date) BETWEEN ? AND ?
          AND u.city IN ({placeholders})
          AND o.payment_method IN ({pay_placeholders})
        """,
        (f["month_start"], f["month_end"], *city_params, *pay_params),
    ).iloc[0]

    risk_row = run_query(
        f"""
        SELECT ROUND(SUM(CASE WHEN o.order_status = 'cancelled' THEN o.order_amount ELSE 0 END), 2) AS risk
        FROM orders o JOIN users u ON u.user_id = o.user_id
        WHERE strftime('%Y-%m', o.order_date) BETWEEN ? AND ?
          AND u.city IN ({placeholders})
          AND o.payment_method IN ({pay_placeholders})
        """,
        (f["month_start"], f["month_end"], *city_params, *pay_params),
    ).iloc[0]

    funnel_row = run_query(
        f"""
        SELECT
            COUNT(DISTINCT CASE WHEN event_name = 'app_open' THEN user_id END) AS opened,
            COUNT(DISTINCT CASE WHEN event_name = 'order_placed' THEN user_id END) AS ordered
        FROM app_events
        WHERE platform IN ({plat_placeholders})
        """,
        tuple(plat_params),
    ).iloc[0]

    # Unfiltered baselines, purely for the "vs full dataset" deltas below —
    # always computable regardless of which filters are active.
    full_gmv_row = run_query(
        "SELECT ROUND(SUM(order_amount), 2) AS gmv, COUNT(*) AS orders FROM orders WHERE order_status = 'delivered'"
    ).iloc[0]
    full_risk_row = run_query(
        "SELECT ROUND(SUM(CASE WHEN order_status = 'cancelled' THEN order_amount ELSE 0 END), 2) AS risk FROM orders"
    ).iloc[0]
    full_funnel_row = run_query(
        """
        SELECT
            COUNT(DISTINCT CASE WHEN event_name = 'app_open' THEN user_id END) AS opened,
            COUNT(DISTINCT CASE WHEN event_name = 'order_placed' THEN user_id END) AS ordered
        FROM app_events
        """
    ).iloc[0]


gmv, orders = gmv_row["gmv"] or 0, int(gmv_row["orders"] or 0)
risk = risk_row["risk"] or 0
opened, ordered = funnel_row["opened"] or 0, funnel_row["ordered"] or 0
full_gmv, full_orders = full_gmv_row["gmv"] or 1, int(full_gmv_row["orders"] or 1)
full_risk = full_risk_row["risk"] or 1
full_opened, full_ordered = full_funnel_row["opened"] or 1, full_funnel_row["ordered"] or 0

conv_pct = 100 * ordered / opened if opened else 0
full_conv_pct = 100 * full_ordered / full_opened if full_opened else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    render_stat_tile(
        "Delivered GMV", fmt_money(gmv),
        sub=f"{orders:,} delivered orders",
        delta=f"{100*gmv/full_gmv:.0f}% of full year",
    )
with col2:
    render_stat_tile(
        "Delivered orders", f"{orders:,}",
        sub=f"of {full_orders:,} full-year orders",
        delta=f"{100*orders/full_orders:.0f}% of full year",
    )
with col3:
    render_stat_tile(
        "app_open → order_placed", f"{conv_pct:.1f}%",
        sub=f"{ordered:,} of {opened:,} users convert",
        delta=f"full year: {full_conv_pct:.1f}%",
    )
with col4:
    render_stat_tile(
        "Revenue at risk (cancelled)", fmt_money(risk),
        sub="filtered by month, city, payment",
        delta=f"{100*risk/full_risk:.0f}% of full year",
    )

# Full-width, so the guardrail sits next to the number it qualifies without
# making the fourth tile taller than the other three.
st.markdown(
    '<div class="kpi-note">All amounts in ₹ (synthetic data). The ~29% cancellation rate behind '
    '<em>revenue at risk</em> is a constant baked into the data generator — a real food-delivery '
    'business runs ~1–3% — so treat the sizing method as the takeaway, not the level.</div>',
    unsafe_allow_html=True,
)

st.divider()

with st.container(border=True):
    st.subheader("Top 3 findings")
    st.markdown(
        """
1. **The funnel's worst leak is checkout, not awareness.** Conversion falls from 67.2% to 54.8% between checkout and order_placed — the single biggest step-to-step drop — and platform isn't the reason.
2. **Cancellations size the biggest pool of at-risk revenue — but no breakdown survives multiple-comparison correction.** ₹1.24M (41.7% of delivered GMV) sits in cancelled orders. Neither the city spread (p=0.95) nor the payment-method spread (p=0.019, above the Bonferroni threshold of 0.0125) is actionable. See **Statistical Tests** for why, and for the ground truth on this synthetic data.
3. **Retention looks like it's improving across 2024 — that curve is the observation window, not the product.** Month-1 retention rises from ~20% to 74%, but later cohorts have less time left in the data, so more of their orders necessarily land in "month + 1". Against a zero-retention baseline the observed curve tracks pure exposure to within 2.3 percentage points. See **Retention**.
        """
    )
    st.caption(
        "All amounts in ₹. This dataset is synthetic and the generator draws order status, "
        "payment method, delivery time and city independently — so the true effect in every "
        "significance test here is zero, and the rate *levels* (a ~29% cancel rate vs. ~1–3% in "
        "the real world) are generator constants. What transfers is the method, not the numbers."
    )

st.divider()
with st.container(border=True):
    st.markdown(
        """
    Use the pages in the sidebar to explore each question:

    - **Funnel** — step-by-step drop-off, and whether it differs by platform
    - **Retention** — the cohort retention triangle, with the data-window caveat made explicit
    - **GMV & Leaderboard** — month-over-month growth and top restaurants per city, with drill-down
    - **Cancellations** — revenue at risk by city and payment method, with live significance testing
    - **Platform & Delivery** — the platform funnel and delivery-time-vs-repeat-purchase analysis
    - **Statistical Tests** — every chi-square test in one place, plus an interactive A/B test power calculator
    - **SQL Playground** — run your own read-only query against the live database

    Full write-up, real numbers, and the underlying SQL for each question:
    [README on GitHub](https://github.com/shreyanshverma7/food-delivery-growth-retention-deep-dive).
    """
    )
