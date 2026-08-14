import streamlit as st
from common import COLOR_SERIES, in_clause, render_sidebar_filters, run_query

st.set_page_config(
    page_title="Food-Delivery Growth & Retention Deep-Dive",
    layout="wide",
)

st.title("Food-Delivery Growth & Retention Deep-Dive")
st.caption(
    "6,387 orders across 2,000 users, 300 restaurants, and 7 cities over 2024 — "
    "where the funnel leaks, which cohorts stick, what drives GMV, and where "
    "cancellations are quietly costing the most."
)

f = render_sidebar_filters()
placeholders, city_params = in_clause(f["cities"])

gmv_row = run_query(
    f"""
    SELECT ROUND(SUM(o.order_amount), 2) AS gmv, COUNT(*) AS orders
    FROM orders o JOIN users u ON u.user_id = o.user_id
    WHERE o.order_status = 'delivered'
      AND strftime('%Y-%m', o.order_date) BETWEEN ? AND ?
      AND u.city IN ({placeholders})
      AND o.payment_method IN ({in_clause(f['payments'])[0]})
    """,
    (f["month_start"], f["month_end"], *city_params, *f["payments"]),
).iloc[0]

risk_row = run_query(
    f"""
    SELECT ROUND(SUM(CASE WHEN o.order_status = 'cancelled' THEN o.order_amount ELSE 0 END), 2) AS risk
    FROM orders o JOIN users u ON u.user_id = o.user_id
    WHERE strftime('%Y-%m', o.order_date) BETWEEN ? AND ?
      AND u.city IN ({placeholders})
      AND o.payment_method IN ({in_clause(f['payments'])[0]})
    """,
    (f["month_start"], f["month_end"], *city_params, *f["payments"]),
).iloc[0]

funnel_row = run_query(
    f"""
    SELECT
        COUNT(DISTINCT CASE WHEN event_name = 'app_open' THEN user_id END) AS opened,
        COUNT(DISTINCT CASE WHEN event_name = 'order_placed' THEN user_id END) AS ordered
    FROM app_events
    WHERE platform IN ({in_clause(f['platforms'])[0]})
    """,
    tuple(f["platforms"]),
).iloc[0]

gmv = gmv_row["gmv"] or 0
risk = risk_row["risk"] or 0
opened, ordered = funnel_row["opened"] or 0, funnel_row["ordered"] or 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Delivered GMV", f"${gmv/1e6:.2f}M" if gmv >= 1e6 else f"${gmv/1e3:.1f}K")
col2.metric("Delivered orders", f"{int(gmv_row['orders'] or 0):,}")
col3.metric(
    "app_open → order_placed",
    f"{(100*ordered/opened if opened else 0):.1f}%",
    help="Filtered by the platform selection in the sidebar.",
)
col4.metric(
    "Revenue at risk (cancelled)",
    f"${risk/1e6:.2f}M" if risk >= 1e6 else f"${risk/1e3:.1f}K",
    help="Filtered by month range, city, and payment method.",
)

st.divider()
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
