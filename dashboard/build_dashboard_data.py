import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "zomato.db"
OUT_PATH = Path(__file__).parent / "dashboard_data.json"
TEMPLATE_PATH = Path(__file__).parent / "template.html"
HTML_OUT_PATH = Path(__file__).parent / "index.html"

FUNNEL_STEPS = ["app_open", "search", "restaurant_view", "add_to_cart", "checkout", "order_placed"]


def funnel(con):
    rows = dict(con.execute(
        "SELECT event_name, COUNT(DISTINCT user_id) FROM app_events GROUP BY event_name"
    ).fetchall())
    return [{"step": s, "users": rows.get(s, 0)} for s in FUNNEL_STEPS]


def cohort_retention(con):
    query = """
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
    cols = ["cohort_month", "cohort_size", "m1", "m2", "m3"]
    return [dict(zip(cols, row)) for row in con.execute(query).fetchall()]


def monthly_gmv(con):
    query = """
    SELECT strftime('%Y-%m', order_date) AS ym, ROUND(SUM(order_amount), 2) AS gmv
    FROM orders WHERE order_status = 'delivered'
    GROUP BY ym ORDER BY ym
    """
    return [{"month": ym, "gmv": gmv} for ym, gmv in con.execute(query).fetchall()]


def city_leaderboard(con):
    query = """
    SELECT u.city, COUNT(*) AS orders, ROUND(SUM(o.order_amount), 2) AS revenue
    FROM orders o JOIN users u ON u.user_id = o.user_id
    WHERE o.order_status = 'delivered'
    GROUP BY u.city ORDER BY revenue DESC
    """
    return [{"city": c, "orders": o, "revenue": r} for c, o, r in con.execute(query).fetchall()]


def top_restaurants_per_city(con):
    query = """
    WITH rev AS (
        SELECT r.restaurant_id, r.name, r.city, SUM(o.order_amount) AS revenue
        FROM orders o JOIN restaurants r ON r.restaurant_id = o.restaurant_id
        WHERE o.order_status = 'delivered'
        GROUP BY r.restaurant_id, r.name, r.city
    ),
    ranked AS (
        SELECT *, DENSE_RANK() OVER (PARTITION BY city ORDER BY revenue DESC) AS city_rank
        FROM rev
    )
    SELECT city, name, ROUND(revenue, 2), city_rank FROM ranked WHERE city_rank <= 3
    ORDER BY city, city_rank
    """
    out = {}
    for city, name, revenue, rank in con.execute(query).fetchall():
        out.setdefault(city, []).append({"name": name, "revenue": revenue, "rank": rank})
    return out


def pareto(con):
    query = """
    WITH per_user AS (
        SELECT user_id, SUM(order_amount) AS user_gmv
        FROM orders WHERE order_status = 'delivered' GROUP BY user_id
    ),
    ranked AS (
        SELECT user_id, user_gmv, NTILE(20) OVER (ORDER BY user_gmv DESC) AS ventile
        FROM per_user
    )
    SELECT
        CASE WHEN ventile = 1 THEN 'top_5_pct' ELSE 'remaining_95_pct' END AS segment,
        COUNT(*) AS users,
        ROUND(SUM(user_gmv), 2) AS segment_gmv,
        ROUND(100.0 * SUM(user_gmv) / SUM(SUM(user_gmv)) OVER (), 2) AS pct_of_total_gmv
    FROM ranked GROUP BY segment
    """
    return {seg: {"users": u, "segment_gmv": g, "pct_of_total_gmv": p}
            for seg, u, g, p in con.execute(query).fetchall()}


def cancellations(con):
    query = """
    SELECT u.city,
           COUNT(*) AS total_orders,
           ROUND(100.0 * SUM(CASE WHEN o.order_status = 'cancelled' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cancel_rate_pct,
           ROUND(SUM(CASE WHEN o.order_status = 'cancelled' THEN o.order_amount ELSE 0 END), 2) AS revenue_at_risk
    FROM orders o JOIN users u ON u.user_id = o.user_id
    GROUP BY u.city ORDER BY cancel_rate_pct DESC
    """
    return [{"city": c, "total_orders": t, "cancel_rate_pct": r, "revenue_at_risk": v}
            for c, t, r, v in con.execute(query).fetchall()]


def main():
    con = sqlite3.connect(DB_PATH)
    data = {
        "funnel": funnel(con),
        "cohort_retention": cohort_retention(con),
        "monthly_gmv": monthly_gmv(con),
        "city_leaderboard": city_leaderboard(con),
        "top_restaurants_per_city": top_restaurants_per_city(con),
        "pareto": pareto(con),
        "cancellations": cancellations(con),
    }
    con.close()
    OUT_PATH.write_text(json.dumps(data, indent=2))
    print(f"Wrote {OUT_PATH}")

    template = TEMPLATE_PATH.read_text()
    html = template.replace("__DASHBOARD_DATA__", json.dumps(data))
    HTML_OUT_PATH.write_text(html)
    print(f"Wrote {HTML_OUT_PATH}")


if __name__ == "__main__":
    main()
