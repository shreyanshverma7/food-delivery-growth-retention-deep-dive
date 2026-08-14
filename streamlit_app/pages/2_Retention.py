import numpy as np
import plotly.graph_objects as go
import streamlit as st

from common import (
    COLOR_MUTED,
    PLOTLY_DARK_LAYOUT,
    SEQUENTIAL_SCALE,
    cell_text_color,
    render_sidebar_filters,
    run_query,
    style_axes,
)

st.set_page_config(page_title="Retention", layout="wide")
st.title("Cohort retention")
st.caption("% of each signup cohort placing a delivered order 1–3 calendar months after signup.")

f = render_sidebar_filters()

df = run_query(
    """
    WITH cohort AS (
        SELECT user_id, signup_date, strftime('%Y-%m', signup_date) AS cohort_month
        FROM users
    ),
    delivered AS (
        SELECT user_id, order_date FROM orders WHERE order_status = 'delivered'
    )
    SELECT
        c.cohort_month,
        COUNT(DISTINCT c.user_id) AS cohort_size,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN strftime('%Y-%m', d.order_date)
            = strftime('%Y-%m', date(c.signup_date, 'start of month', '+1 month'))
            THEN d.user_id END) / COUNT(DISTINCT c.user_id), 2) AS m1,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN strftime('%Y-%m', d.order_date)
            = strftime('%Y-%m', date(c.signup_date, 'start of month', '+2 month'))
            THEN d.user_id END) / COUNT(DISTINCT c.user_id), 2) AS m2,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN strftime('%Y-%m', d.order_date)
            = strftime('%Y-%m', date(c.signup_date, 'start of month', '+3 month'))
            THEN d.user_id END) / COUNT(DISTINCT c.user_id), 2) AS m3
    FROM cohort c
    LEFT JOIN delivered d ON d.user_id = c.user_id
    GROUP BY c.cohort_month
    ORDER BY c.cohort_month
    """
)

last_month = run_query("SELECT MAX(strftime('%Y-%m', order_date)) AS m FROM orders")["m"].iloc[0]


def months_after(ym, n):
    y, m = int(ym[:4]), int(ym[5:7])
    total = y * 12 + (m - 1) + n
    return f"{total // 12}-{(total % 12) + 1:02d}"


cols = ["m1", "m2", "m3"]
z = df[cols].values.astype(float)
observable = np.array(
    [[months_after(cm, i + 1) <= last_month for i in range(3)] for cm in df["cohort_month"]]
)
z_masked = np.where(observable, z, np.nan)
col_labels = ["M+1", "M+2", "M+3"]

fig = go.Figure(
    go.Heatmap(
        z=z_masked,
        x=col_labels,
        y=df["cohort_month"],
        colorscale=SEQUENTIAL_SCALE,
        hovertemplate="%{y} cohort, %{x}: %{z:.2f}%<extra></extra>",
        colorbar=dict(title="retained %"),
    )
)
fig.update_layout(
    yaxis=dict(autorange="reversed"),
    height=460,
    margin=dict(l=10, r=10, t=10, b=10),
    **PLOTLY_DARK_LAYOUT,
)
style_axes(fig)

# Per-cell annotations instead of a uniform texttemplate: the dark-mode
# sequential ramp runs dark-to-light with rising value, so a single fixed
# text color would lose contrast at one end of the scale.
for i, cohort_month in enumerate(df["cohort_month"]):
    for j, col in enumerate(col_labels):
        if observable[i][j]:
            fig.add_annotation(
                x=col, y=cohort_month, text=f"{z[i][j]:.1f}%", showarrow=False,
                font=dict(color=cell_text_color(z[i][j]), size=12),
            )
        else:
            fig.add_annotation(
                x=col, y=cohort_month, text="–", showarrow=False,
                font=dict(color=COLOR_MUTED, size=12),
            )

st.plotly_chart(fig, width='stretch')
st.caption(
    f"Blank cells (–) fall after {last_month}, the last month with data — not yet observable, "
    "not zero retention. Compare trend only across cohorts with a full window."
)

with st.expander("Table view"):
    st.dataframe(df, width='stretch', hide_index=True)
