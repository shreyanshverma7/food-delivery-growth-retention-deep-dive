import plotly.graph_objects as go
import streamlit as st
from scipy.stats import chi2_contingency

from common import COLOR_CRITICAL, COLOR_SERIES, in_clause, render_sidebar_filters, run_query

st.set_page_config(page_title="Funnel", layout="wide")
st.title("Funnel: where users drop off")

f = render_sidebar_filters()
placeholders, platform_params = in_clause(f["platforms"])

FUNNEL_STEPS = ["app_open", "search", "restaurant_view", "add_to_cart", "checkout", "order_placed"]

funnel = run_query(
    f"""
    SELECT event_name, COUNT(DISTINCT user_id) AS users
    FROM app_events
    WHERE platform IN ({placeholders})
    GROUP BY event_name
    """,
    tuple(platform_params),
).set_index("event_name")["users"]
funnel = funnel.reindex(FUNNEL_STEPS).fillna(0).astype(int)

drops = funnel.pct_change().fillna(0) * -100
biggest_drop_step = drops[1:].idxmax() if len(drops) > 1 else None

fig = go.Figure(
    go.Bar(
        x=funnel.values,
        y=[s.replace("_", " ") for s in funnel.index],
        orientation="h",
        marker_color=[COLOR_CRITICAL if s == biggest_drop_step else COLOR_SERIES for s in funnel.index],
        text=[f"{v:,}" for v in funnel.values],
        textposition="outside",
    )
)
fig.update_layout(
    yaxis=dict(autorange="reversed"),
    xaxis_title="distinct users",
    height=380,
    margin=dict(l=10, r=10, t=10, b=10),
)
st.plotly_chart(fig, width='stretch')

if funnel.iloc[0] > 0:
    st.caption(
        f"Biggest step-to-step drop: **{biggest_drop_step.replace('_', ' ')}** "
        f"({-drops[biggest_drop_step]:.1f}% of the prior step lost). "
        f"Overall app_open → order_placed conversion: "
        f"**{100*funnel.iloc[-1]/funnel.iloc[0]:.1f}%**."
    )

st.subheader("By platform")
by_platform = run_query(
    """
    SELECT platform,
           COUNT(DISTINCT CASE WHEN event_name = 'app_open' THEN user_id END) AS opened,
           COUNT(DISTINCT CASE WHEN event_name = 'order_placed' THEN user_id END) AS converted
    FROM app_events
    GROUP BY platform
    ORDER BY platform
    """
)
by_platform["not_converted"] = by_platform["opened"] - by_platform["converted"]
by_platform["conversion_pct"] = (100 * by_platform["converted"] / by_platform["opened"]).round(2)
st.dataframe(
    by_platform[["platform", "opened", "converted", "conversion_pct"]],
    width='stretch',
    hide_index=True,
)

if len(by_platform) >= 2:
    chi2, p, dof, _ = chi2_contingency(by_platform[["converted", "not_converted"]].values)
    verdict = "significant" if p < 0.05 else "not significant"
    st.caption(
        f"Chi-square test across platforms: chi2={chi2:.2f}, p={p:.3f} — **{verdict}** at alpha=0.05. "
        + ("Platform is a real driver of conversion here." if p < 0.05
           else "The platform-to-platform spread is consistent with noise — this is a checkout-flow "
                "problem, not a device-specific one.")
    )
