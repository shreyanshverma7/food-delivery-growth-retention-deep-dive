import plotly.graph_objects as go
import streamlit as st
from scipy.stats import chi2_contingency

from common import COLOR_SERIES, PLOTLY_DARK_LAYOUT, in_clause, render_sidebar_filters, run_query, style_axes

st.set_page_config(page_title="Cancellations", layout="wide")
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
        verdict = "significant" if p < 0.05 else "not significant (noise)"
        st.caption(f"Chi-square test (live, on current filters): chi2={chi2:.2f}, p={p:.4f} — **{verdict}** at alpha=0.05.")


st.subheader("By city")
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
by_city["cancel_rate_pct"] = (100 * by_city["cancelled"] / (by_city["delivered"] + by_city["cancelled"])).round(2)
by_city["revenue_at_risk"] = by_city["revenue_at_risk"].round(2)
bar_with_significance(by_city, "city", "Cancellation rate by city")

st.subheader("By payment method")
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
by_payment["cancel_rate_pct"] = (
    100 * by_payment["cancelled"] / (by_payment["delivered"] + by_payment["cancelled"])
).round(2)
by_payment["revenue_at_risk"] = by_payment["revenue_at_risk"].round(2)
bar_with_significance(by_payment, "payment_method", "Cancellation rate by payment method")

total_risk = by_city["revenue_at_risk"].sum()
st.metric("Total revenue at risk (current filters)", f"${total_risk/1e6:.2f}M" if total_risk >= 1e6 else f"${total_risk/1e3:.1f}K")
