import plotly.graph_objects as go
import streamlit as st
from scipy.stats import chi2_contingency

from common import (
    COLOR_SERIES,
    PLOTLY_DARK_LAYOUT,
    fmt_money,
    in_clause,
    inject_css,
    render_sidebar_filters,
    render_significance_caption,
    render_stat_tile,
    run_query,
    style_axes,
)

st.set_page_config(page_title="Cancellations · Food Delivery Analytics", page_icon="🛵", layout="wide")
inject_css()
st.title("Cancellation revenue at risk")

f = render_sidebar_filters()
city_ph, city_params = in_clause(f["cities"])
pay_ph, pay_params = in_clause(f["payments"])


def bar_with_significance(df, label_col, title):
    df = df.sort_values("cancel_rate_pct", ascending=False)
    fig = go.Figure(
        go.Bar(
            x=df["cancel_rate_pct"], y=df[label_col], orientation="h", marker_color=COLOR_SERIES,
            text=[f"{v:.1f}%" for v in df["cancel_rate_pct"]], textposition="outside",
        )
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed"), height=280, margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="cancellation rate %", title=title,
        **PLOTLY_DARK_LAYOUT,
    )
    style_axes(fig)
    st.plotly_chart(fig, width='stretch')
    st.dataframe(df, width='stretch', hide_index=True)

    if len(df) >= 2:
        table = df[["delivered", "cancelled"]].values
        chi2, p, dof, _ = chi2_contingency(table)
        render_significance_caption(
            chi2, p,
            note_if_not="Not strong enough to survive correction for the project's four "
                        "comparisons — don't action this ranking.",
        )


with st.spinner("Loading cancellations…"):
    by_city = run_query(
        f"""
        SELECT u.city,
               SUM(CASE WHEN o.order_status = 'delivered' THEN 1 ELSE 0 END) AS delivered,
               SUM(CASE WHEN o.order_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
               SUM(CASE WHEN o.order_status = 'cancelled' THEN o.order_amount ELSE 0 END) AS revenue_at_risk
        FROM orders o JOIN users u ON u.user_id = o.user_id
        WHERE strftime('%Y-%m', o.order_date) BETWEEN ? AND ?
          AND u.city IN ({city_ph}) AND o.payment_method IN ({pay_ph})
        GROUP BY u.city
        """,
        (f["month_start"], f["month_end"], *city_params, *pay_params),
    )
    by_payment = run_query(
        f"""
        SELECT o.payment_method,
               SUM(CASE WHEN o.order_status = 'delivered' THEN 1 ELSE 0 END) AS delivered,
               SUM(CASE WHEN o.order_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
               SUM(CASE WHEN o.order_status = 'cancelled' THEN o.order_amount ELSE 0 END) AS revenue_at_risk
        FROM orders o JOIN users u ON u.user_id = o.user_id
        WHERE strftime('%Y-%m', o.order_date) BETWEEN ? AND ?
          AND u.city IN ({city_ph}) AND o.payment_method IN ({pay_ph})
        GROUP BY o.payment_method
        """,
        (f["month_start"], f["month_end"], *city_params, *pay_params),
    )

by_city["cancel_rate_pct"] = (100 * by_city["cancelled"] / (by_city["delivered"] + by_city["cancelled"])).round(2)
by_city["revenue_at_risk"] = by_city["revenue_at_risk"].round(2)
by_payment["cancel_rate_pct"] = (
    100 * by_payment["cancelled"] / (by_payment["delivered"] + by_payment["cancelled"])
).round(2)
by_payment["revenue_at_risk"] = by_payment["revenue_at_risk"].round(2)

st.subheader("By city")
with st.container(border=True):
    bar_with_significance(by_city, "city", "Cancellation rate by city")

st.subheader("By payment method")
with st.container(border=True):
    bar_with_significance(by_payment, "payment_method", "Cancellation rate by payment method")

total_risk = by_city["revenue_at_risk"].sum()
render_stat_tile(
    "Total revenue at risk (current filters)",
    fmt_money(total_risk),
)
st.caption(
    "**Realism guardrail:** the ~29% cancellation rate is a constant baked into the data "
    "generator (5 `delivered` to 2 `cancelled`), chosen so these queries return meaningful "
    "volume — a real food-delivery business runs ~1–3%. Because order value is generated "
    "independently of order status, the risk-to-GMV ratio has an expected value of exactly "
    "(2/7)/(5/7) = 40%; the 41.7% observed is that constant plus noise, not a finding. The "
    "transferable part is the method of sizing revenue-at-risk, not the level."
)
