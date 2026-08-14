import time

import streamlit as st

from common import render_sidebar_filters, run_readonly_sql, run_query

st.set_page_config(page_title="SQL Playground", layout="wide")
st.title("SQL playground")
st.caption(
    "Run your own read-only query against the live database. The connection is opened "
    "read-only at the SQLite level (writes fail regardless of what you type), limited to "
    "a single SELECT/WITH statement, capped at 500 rows, and aborted after 5 seconds."
)
render_sidebar_filters()

with st.expander("Schema reference", expanded=False):
    schema = run_query(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
    )
    for _, row in schema.iterrows():
        st.code(row["sql"], language="sql")

default_query = (
    "SELECT city, COUNT(*) AS orders, ROUND(AVG(order_amount), 2) AS avg_order_value\n"
    "FROM orders o JOIN users u ON u.user_id = o.user_id\n"
    "WHERE o.order_status = 'delivered'\n"
    "GROUP BY city\n"
    "ORDER BY avg_order_value DESC;"
)
query = st.text_area("SQL query", value=default_query, height=140)

if st.button("Run query", type="primary"):
    start = time.time()
    try:
        result, truncated = run_readonly_sql(query)
        elapsed = time.time() - start
        st.success(f"{len(result)} row(s) in {elapsed:.2f}s" + (" (truncated at 500)" if truncated else ""))
        st.dataframe(result, width='stretch', hide_index=True)
    except TimeoutError as e:
        st.error(str(e))
    except ValueError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Query failed: {e}")
