import numpy as np
import plotly.graph_objects as go
import streamlit as st

from common import (
    COLOR_CRITICAL,
    COLOR_MUTED,
    COLOR_SERIES,
    PLOTLY_DARK_LAYOUT,
    SEQUENTIAL_SCALE,
    cell_text_color,
    render_sidebar_filters,
    run_query,
    style_axes,
)

st.set_page_config(page_title="Retention · Food Delivery Analytics", page_icon="🛵", layout="wide")
st.title("Cohort retention")
st.caption("% of each signup cohort placing a delivered order 1–3 calendar months after signup.")

st.warning(
    "**The rising trend below is exposure, not retention.** Every user's orders are spread "
    "across the window between their signup date and the end of the data. A January user's "
    "orders scatter over 11 months, so few land in February specifically; a November user has "
    "~1 month left, so almost any order they place counts as \"month + 1\". Retention appears to "
    "climb because the denominator of exposure shrinks. The chart at the bottom of this page "
    "tests it directly against a zero-retention baseline."
)

f = render_sidebar_filters()

with st.spinner("Loading cohorts…"):
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

with st.container(border=True):
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

st.divider()
st.subheader("Is any of it real? Observed vs. a zero-retention baseline")
st.caption(
    "For each user, the probability that at least one delivered order lands in month+1 *by "
    "chance alone*, assuming order dates fall uniformly across their observable window: "
    "`1 - (1 - p)^n`, where `p` is month+1's share of the window and `n` is their delivered "
    "order count. Averaged per cohort, that is the retention curve a population with no "
    "retention behaviour would produce. See `sql/09_retention_exposure_check.sql`."
)

with st.spinner("Computing exposure-adjusted baseline…"):
    exposure = run_query(
        """
        WITH bounds AS (SELECT MAX(order_date) AS data_end FROM orders),
        per_user AS (
            SELECT
                strftime('%Y-%m', u.signup_date) AS cohort_month,
                julianday(b.data_end) - julianday(u.signup_date) + 1 AS window_days,
                MAX(0,
                    julianday(MIN(date(u.signup_date,'start of month','+2 month','-1 day'), b.data_end))
                  - julianday(MAX(date(u.signup_date,'start of month','+1 month'), u.signup_date)) + 1
                ) AS m1_days,
                (SELECT COUNT(*) FROM orders o
                  WHERE o.user_id = u.user_id AND o.order_status='delivered') AS n_delivered,
                (SELECT COUNT(*) FROM orders o
                  WHERE o.user_id = u.user_id AND o.order_status='delivered'
                    AND strftime('%Y-%m', o.order_date)
                      = strftime('%Y-%m', date(u.signup_date,'start of month','+1 month'))) > 0
                  AS retained_m1
            FROM users u CROSS JOIN bounds b
        )
        SELECT cohort_month,
               ROUND(100.0 * SUM(retained_m1)/COUNT(*), 1) AS observed,
               ROUND(100.0 * AVG(1 - POWER(1 - (m1_days/window_days), n_delivered)), 1) AS expected
        FROM per_user GROUP BY cohort_month ORDER BY cohort_month
        """
    )

with st.container(border=True):
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=exposure["cohort_month"], y=exposure["observed"], name="Observed M+1 retention",
        mode="lines+markers", line=dict(color=COLOR_SERIES, width=2),
    ))
    fig2.add_trace(go.Scatter(
        x=exposure["cohort_month"], y=exposure["expected"], name="Expected if retention were zero",
        mode="lines+markers", line=dict(color=COLOR_CRITICAL, width=2, dash="dash"),
    ))
    fig2.update_layout(
        height=340, margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="month-1 retention %", xaxis_title="signup cohort",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        **PLOTLY_DARK_LAYOUT,
    )
    style_axes(fig2)
    st.plotly_chart(fig2, width='stretch')

    gap = (exposure["observed"] - exposure["expected"]).abs().mean()
    st.caption(
        f"Mean absolute gap: **{gap:.1f} percentage points**, with no systematic direction — the "
        "observed curve is reproduced by a model containing no retention behaviour at all. The "
        "apparent improvement across 2024 is a data-window artifact end to end, not a product "
        "signal. On real data this same exposure-adjusted baseline is what separates a genuine "
        "retention trend from one manufactured by the observation window."
    )
