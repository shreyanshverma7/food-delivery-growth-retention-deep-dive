import plotly.graph_objects as go
import streamlit as st

from common import COLOR_SERIES, in_clause, render_sidebar_filters, run_query

st.set_page_config(page_title="GMV & Leaderboard", layout="wide")
st.title("GMV drivers")

f = render_sidebar_filters()
city_ph, city_params = in_clause(f["cities"])
pay_ph, pay_params = in_clause(f["payments"])

st.subheader("Monthly delivered GMV")
monthly = run_query(
    f"""
    SELECT strftime('%Y-%m', o.order_date) AS ym, ROUND(SUM(o.order_amount), 2) AS gmv
    FROM orders o JOIN users u ON u.user_id = o.user_id
    WHERE o.order_status = 'delivered'
      AND strftime('%Y-%m', o.order_date) BETWEEN ? AND ?
      AND u.city IN ({city_ph}) AND o.payment_method IN ({pay_ph})
    GROUP BY ym ORDER BY ym
    """,
    (f["month_start"], f["month_end"], *city_params, *pay_params),
)
fig = go.Figure(
    go.Scatter(
        x=monthly["ym"], y=monthly["gmv"], mode="lines+markers",
        line=dict(color=COLOR_SERIES, width=2), fill="tozeroy",
        fillcolor="rgba(42,120,214,0.1)",
    )
)
fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="delivered GMV ($)")
st.plotly_chart(fig, width='stretch')

st.subheader("City leaderboard")
by_city = run_query(
    f"""
    SELECT u.city, COUNT(*) AS orders, ROUND(SUM(o.order_amount), 2) AS revenue
    FROM orders o JOIN users u ON u.user_id = o.user_id
    WHERE o.order_status = 'delivered'
      AND strftime('%Y-%m', o.order_date) BETWEEN ? AND ?
      AND u.city IN ({city_ph}) AND o.payment_method IN ({pay_ph})
    GROUP BY u.city ORDER BY revenue DESC
    """,
    (f["month_start"], f["month_end"], *city_params, *pay_params),
)
fig2 = go.Figure(
    go.Bar(
        x=by_city["revenue"], y=by_city["city"], orientation="h", marker_color=COLOR_SERIES,
        text=[f"${v:,.0f}" for v in by_city["revenue"]], textposition="outside",
    )
)
fig2.update_layout(
    yaxis=dict(autorange="reversed"), height=320, margin=dict(l=10, r=10, t=10, b=10),
    xaxis_title="delivered revenue ($)",
)
st.plotly_chart(fig2, width='stretch')

st.subheader("Drill down: top restaurants in a city")
if len(by_city):
    chosen_city = st.selectbox("City", by_city["city"].tolist())
    top_restaurants = run_query(
        """
        SELECT r.name, r.cuisine, r.rating, COUNT(*) AS orders,
               ROUND(SUM(o.order_amount), 2) AS revenue
        FROM orders o JOIN restaurants r ON r.restaurant_id = o.restaurant_id
        WHERE o.order_status = 'delivered' AND r.city = ?
        GROUP BY r.restaurant_id, r.name, r.cuisine, r.rating
        ORDER BY revenue DESC
        LIMIT 10
        """,
        (chosen_city,),
    )
    st.dataframe(top_restaurants, width='stretch', hide_index=True)
else:
    st.info("No cities match the current filters.")
