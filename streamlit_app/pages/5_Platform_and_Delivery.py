import plotly.graph_objects as go
import streamlit as st
from scipy.stats import chi2_contingency

from common import (
    COLOR_SERIES,
    PLOTLY_DARK_LAYOUT,
    render_sidebar_filters,
    render_significance_caption,
    run_query,
    style_axes,
)

st.set_page_config(page_title="Platform & Delivery · Food Delivery Analytics", page_icon="🛵", layout="wide")
st.title("Platform & delivery-time deep dive")

f = render_sidebar_filters()

with st.spinner("Loading platform & delivery-time data…"):
    by_platform = run_query(
        """
        SELECT platform,
               COUNT(DISTINCT CASE WHEN event_name = 'app_open' THEN user_id END) AS opened,
               COUNT(DISTINCT CASE WHEN event_name = 'order_placed' THEN user_id END) AS converted
        FROM app_events GROUP BY platform ORDER BY platform
        """
    )
    buckets = run_query(
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
            COUNT(*) AS users,
            SUM(CASE WHEN d.delivered_orders >= 2 THEN 1 ELSE 0 END) AS reordered,
            SUM(CASE WHEN d.delivered_orders < 2 THEN 1 ELSE 0 END) AS did_not_reorder
        FROM first_order f JOIN delivered_counts d ON d.user_id = f.user_id
        WHERE f.rn = 1
        GROUP BY bucket ORDER BY bucket
        """
    )

by_platform["not_converted"] = by_platform["opened"] - by_platform["converted"]
by_platform["conversion_pct"] = (100 * by_platform["converted"] / by_platform["opened"]).round(2)
buckets["reorder_rate_pct"] = (100 * buckets["reordered"] / buckets["users"]).round(2)

st.subheader("Funnel conversion by platform")
with st.container(border=True):
    fig = go.Figure(
        go.Bar(
            x=by_platform["conversion_pct"], y=by_platform["platform"], orientation="h",
            marker_color=COLOR_SERIES, text=[f"{v:.1f}%" for v in by_platform["conversion_pct"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        height=260, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="app_open → order_placed %",
        **PLOTLY_DARK_LAYOUT,
    )
    style_axes(fig)
    st.plotly_chart(fig, width='stretch')

    chi2, p, dof, _ = chi2_contingency(by_platform[["converted", "not_converted"]].values)
    render_significance_caption(
        chi2, p,
        note_if_not="Platforms convert the same, within noise.",
    )

st.divider()
st.subheader("Does a slow first delivery cost you the second order?")
with st.container(border=True):
    fig2 = go.Figure(
        go.Bar(
            x=buckets["bucket"], y=buckets["reorder_rate_pct"], marker_color=COLOR_SERIES,
            text=[f"{v:.1f}%" for v in buckets["reorder_rate_pct"]], textposition="outside",
        )
    )
    fig2.update_layout(
        height=280, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="reorder rate %",
        **PLOTLY_DARK_LAYOUT,
    )
    style_axes(fig2)
    st.plotly_chart(fig2, width='stretch')
    st.dataframe(buckets, width='stretch', hide_index=True)

    chi2b, pb, dofb, _ = chi2_contingency(buckets[["reordered", "did_not_reorder"]].values)
    render_significance_caption(
        chi2b, pb,
        note_if_significant="This is the only comparison in the family that clears the corrected "
                            "threshold — and it is still not actionable: the buckets are "
                            "non-monotonic (the fastest bucket doesn't reorder best), and the "
                            "generator draws delivery time independently of everything else, so "
                            "the true effect is zero. Open question, not a recommendation.",
        note_if_not="No measurable delivery-time-to-retention link in this data.",
    )
