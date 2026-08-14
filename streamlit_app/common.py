"""Shared DB access, filters, and chart styling for every page of the app."""

import sqlite3
import time
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent.parent / "database" / "zomato.db"

# Single-hue sequential blue + one status color, matching the repo's static
# dashboard (see the dataviz palette this project used: references/palette.md
# in the dataviz skill). These are the validated DARK-surface tokens (the app
# runs dark-only — see .streamlit/config.toml) recovered from that same
# earlier dark-mode pass, not re-invented.
COLOR_SERIES = "#3987e5"
COLOR_CRITICAL = "#e66767"
COLOR_MUTED = "#898781"
COLOR_SURFACE = "#1a1a19"
COLOR_GRIDLINE = "#2c2c2a"
COLOR_TEXT = "#ffffff"
SEQUENTIAL_SCALE = [
    [0.0, "#184f95"], [0.25, "#256abf"], [0.5, "#3987e5"], [0.75, "#5598e7"], [1.0, "#b7d3f6"],
]

# Plotly defaults to a white chart background regardless of Streamlit's own
# theme, so every figure needs this merged in explicitly or it renders as a
# bright box on the dark page.
PLOTLY_DARK_LAYOUT = dict(
    paper_bgcolor=COLOR_SURFACE, plot_bgcolor=COLOR_SURFACE, font=dict(color=COLOR_TEXT)
)


def style_axes(fig):
    fig.update_xaxes(gridcolor=COLOR_GRIDLINE, zerolinecolor="#383835", linecolor="#383835")
    fig.update_yaxes(gridcolor=COLOR_GRIDLINE, zerolinecolor="#383835", linecolor="#383835")


def _lerp_color(c1, c2, t):
    c1 = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
    c2 = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(round(c1[k] + (c2[k] - c1[k]) * t) for k in range(3))


def _scale_color(t, scale):
    t = max(0.0, min(1.0, t))
    for (pos0, col0), (pos1, col1) in zip(scale, scale[1:]):
        if pos0 <= t <= pos1:
            step = 0 if pos1 == pos0 else (t - pos0) / (pos1 - pos0)
            return _lerp_color(col0, col1, step)
    return _lerp_color(scale[-1][1], scale[-1][1], 0)


def cell_text_color(pct, scale=SEQUENTIAL_SCALE, light="#ffffff", dark="#0b0b0b"):
    """Picks readable text color for a value plotted against a continuous
    sequential heatmap fill — the dark-mode ramp runs dark-to-light with
    rising value, so a fixed text color loses contrast at one end."""
    r, g, b = _scale_color(pct / 100, scale)
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return dark if luminance > 0.45 else light


@st.cache_resource
def get_connection():
    # uri=True + mode=ro opens the file read-only at the SQLite/OS level —
    # even a malicious INSERT/UPDATE/DROP raises "attempt to write a
    # readonly database" rather than touching the committed file.
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    con.execute("PRAGMA query_only = ON;")
    return con


@st.cache_data(ttl=3600)
def run_query(sql, params=()):
    con = get_connection()
    return pd.read_sql_query(sql, con, params=params)


@st.cache_data(ttl=3600)
def available_months():
    df = run_query(
        "SELECT DISTINCT strftime('%Y-%m', order_date) AS ym FROM orders ORDER BY ym"
    )
    return df["ym"].tolist()


@st.cache_data(ttl=3600)
def available_cities():
    return run_query("SELECT DISTINCT city FROM users ORDER BY city")["city"].tolist()


@st.cache_data(ttl=3600)
def available_payment_methods():
    return run_query("SELECT DISTINCT payment_method FROM orders ORDER BY payment_method")[
        "payment_method"
    ].tolist()


@st.cache_data(ttl=3600)
def available_platforms():
    return run_query("SELECT DISTINCT platform FROM app_events ORDER BY platform")[
        "platform"
    ].tolist()


def render_sidebar_filters():
    """Renders the global filter widgets once; every page calls this so the
    same widget keys keep selections in sync as you navigate between pages."""
    months = available_months()
    cities = available_cities()
    payments = available_payment_methods()
    platforms = available_platforms()

    st.sidebar.header("Filters")
    month_range = st.sidebar.select_slider(
        "Month range", options=months, value=(months[0], months[-1]), key="f_months"
    )
    selected_cities = st.sidebar.multiselect("City", cities, default=cities, key="f_cities")
    selected_payments = st.sidebar.multiselect(
        "Payment method", payments, default=payments, key="f_payments"
    )
    selected_platforms = st.sidebar.multiselect(
        "Platform", platforms, default=platforms, key="f_platforms"
    )
    st.sidebar.caption(
        "Filters apply per-page to whichever tables that page's charts pull from "
        "(orders vs. app_events don't share every dimension)."
    )
    return {
        "month_start": month_range[0],
        "month_end": month_range[1],
        "cities": selected_cities or cities,
        "payments": selected_payments or payments,
        "platforms": selected_platforms or platforms,
    }


def in_clause(values):
    """('?,?,?', [v1,v2,v3]) for a parameterized IN (...) fragment."""
    placeholders = ",".join("?" for _ in values)
    return placeholders, list(values)


def run_readonly_sql(sql, row_limit=500, timeout_seconds=5):
    """Executes an arbitrary user-supplied query safely for the SQL playground page.

    Defense in depth: the connection is opened read-only at the SQLite/OS
    level (see get_connection), PRAGMA query_only blocks writes even to temp
    objects, only a single SELECT/WITH statement is allowed, and a progress
    handler aborts anything that runs past timeout_seconds so one visitor
    can't hang the shared app.
    """
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        raise ValueError("Only a single statement is allowed.")
    if not stripped.lower().startswith(("select", "with")):
        raise ValueError("Only SELECT / WITH ... SELECT queries are allowed.")

    con = get_connection()
    deadline = time.time() + timeout_seconds

    def _abort_if_slow():
        return time.time() > deadline

    con.set_progress_handler(_abort_if_slow, 1000)
    try:
        cur = con.execute(stripped)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(row_limit + 1)
        truncated = len(rows) > row_limit
        rows = rows[:row_limit]
        return pd.DataFrame(rows, columns=cols), truncated
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            raise TimeoutError(f"Query exceeded the {timeout_seconds}s time budget and was stopped.")
        raise
    finally:
        con.set_progress_handler(None, 0)
