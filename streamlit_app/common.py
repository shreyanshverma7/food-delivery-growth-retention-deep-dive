"""Shared DB access, filters, and chart styling for every page of the app."""

import sqlite3
import time
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent.parent / "database" / "zomato.db"

# Single-hue sequential blue + one status color, matching the repo's static
# dashboard (see the dataviz palette this project used: references/palette.md
# in the dataviz skill). Kept as plain constants here since Plotly doesn't
# consume CSS custom properties.
COLOR_SERIES = "#2a78d6"
COLOR_SERIES_DARK = "#184f95"
COLOR_MUTED = "#898781"
COLOR_CRITICAL = "#d03b3b"
SEQUENTIAL_SCALE = [
    [0.0, "#cde2fb"], [0.25, "#6da7ec"], [0.5, "#2a78d6"], [0.75, "#1c5cab"], [1.0, "#0d366b"],
]


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
