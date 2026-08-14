"""
Build a realistic Zomato-style practice database for Product Analyst SQL prep.
Creates zomato.db (SQLite) with seeded, internally-consistent data so that
funnel, retention, cohort, ranking and window-function queries all return
meaningful results.

Run:  python3 build_zomato_db.py
"""
import sqlite3
import random
from datetime import date, timedelta

random.seed(42)  # reproducible

DB = "zomato.db"

CITIES = ["Bangalore", "Delhi", "Mumbai", "Hyderabad", "Pune", "Chennai", "Kolkata"]
PLATFORMS = ["iOS", "Android", "Web"]
CUISINES = ["North Indian", "South Indian", "Chinese", "Italian", "Fast Food",
            "Biryani", "Desserts", "Beverages", "Continental", "Mughlai"]
PAYMENTS = ["UPI", "Card", "Wallet", "Cash", "NetBanking"]
ORDER_STATUS = ["delivered", "delivered", "delivered", "delivered", "delivered",
                "cancelled", "cancelled"]  # ~71% delivered
EVENTS = ["app_open", "search", "restaurant_view", "add_to_cart", "checkout", "order_placed"]
DISHES = {
    "North Indian": ["Butter Chicken", "Paneer Tikka", "Dal Makhani", "Naan"],
    "South Indian": ["Masala Dosa", "Idli", "Vada", "Filter Coffee"],
    "Chinese": ["Hakka Noodles", "Manchurian", "Fried Rice", "Spring Roll"],
    "Italian": ["Margherita Pizza", "Pasta Alfredo", "Garlic Bread", "Lasagna"],
    "Fast Food": ["Burger", "Fries", "Wrap", "Nuggets"],
    "Biryani": ["Chicken Biryani", "Mutton Biryani", "Veg Biryani", "Egg Biryani"],
    "Desserts": ["Gulab Jamun", "Brownie", "Ice Cream", "Rasmalai"],
    "Beverages": ["Cold Coffee", "Lassi", "Mojito", "Fresh Juice"],
    "Continental": ["Grilled Sandwich", "Caesar Salad", "Steak", "Soup"],
    "Mughlai": ["Kebab Platter", "Rogan Josh", "Korma", "Sheermal"],
}

START = date(2024, 1, 1)
END = date(2024, 12, 31)


def rand_date(start, end):
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # ---- schema ----
    c.executescript("""
    DROP TABLE IF EXISTS order_items;
    DROP TABLE IF EXISTS orders;
    DROP TABLE IF EXISTS app_events;
    DROP TABLE IF EXISTS restaurants;
    DROP TABLE IF EXISTS users;

    CREATE TABLE users (
        user_id       INTEGER PRIMARY KEY,
        name          TEXT,
        city          TEXT,
        signup_date   TEXT,       -- YYYY-MM-DD
        signup_platform TEXT
    );

    CREATE TABLE restaurants (
        restaurant_id INTEGER PRIMARY KEY,
        name          TEXT,
        city          TEXT,
        cuisine       TEXT,
        rating        REAL,       -- 1.0 - 5.0
        is_active     INTEGER     -- 1/0
    );

    CREATE TABLE orders (
        order_id        INTEGER PRIMARY KEY,
        user_id         INTEGER,
        restaurant_id   INTEGER,
        order_date      TEXT,     -- YYYY-MM-DD
        order_status    TEXT,     -- delivered / cancelled
        order_amount    REAL,     -- gross bill value
        delivery_time_min INTEGER,
        payment_method  TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id),
        FOREIGN KEY(restaurant_id) REFERENCES restaurants(restaurant_id)
    );

    CREATE TABLE order_items (
        item_id    INTEGER PRIMARY KEY,
        order_id   INTEGER,
        dish_name  TEXT,
        quantity   INTEGER,
        price      REAL,
        FOREIGN KEY(order_id) REFERENCES orders(order_id)
    );

    CREATE TABLE app_events (
        event_id   INTEGER PRIMARY KEY,
        user_id    INTEGER,
        event_name TEXT,
        event_time TEXT,          -- YYYY-MM-DD HH:MM:SS
        platform   TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    """)

    # ---- users ----
    N_USERS = 2000
    users = []
    for uid in range(1, N_USERS + 1):
        city = random.choice(CITIES)
        sd = rand_date(START, date(2024, 11, 30))
        plat = random.choice(PLATFORMS)
        users.append((uid, f"user_{uid}", city, sd.isoformat(), plat))
    c.executemany("INSERT INTO users VALUES (?,?,?,?,?)", users)

    # ---- restaurants ----
    N_REST = 300
    restaurants = []
    for rid in range(1, N_REST + 1):
        city = random.choice(CITIES)
        cuisine = random.choice(CUISINES)
        rating = round(random.uniform(2.8, 5.0), 1)
        is_active = 1 if random.random() > 0.1 else 0
        restaurants.append((rid, f"Restaurant {rid}", city, cuisine, rating, is_active))
    c.executemany("INSERT INTO restaurants VALUES (?,?,?,?,?,?)", restaurants)
    rest_cuisine = {r[0]: r[3] for r in restaurants}

    # ---- orders + order_items ----
    # Some users are heavy repeaters -> good for retention/cohort queries.
    orders = []
    items = []
    oid = 0
    item_id = 0
    for uid, _, ucity, usd, _ in users:
        signup = date.fromisoformat(usd)
        # number of orders skewed: many light users, few heavy
        n_orders = random.choices([0, 1, 2, 3, 5, 8, 12],
                                  weights=[12, 25, 22, 15, 12, 8, 6])[0]
        for _ in range(n_orders):
            oid += 1
            # Restaurants 251-300 are "newly launched" and receive no orders yet,
            # so anti-join questions (high-rated restaurant, zero orders) return rows.
            rid = random.randint(1, 250)
            od = rand_date(signup, END)
            status = random.choice(ORDER_STATUS)
            amount = round(random.uniform(120, 1200), 2)
            dtime = random.randint(18, 75)
            pay = random.choice(PAYMENTS)
            orders.append((oid, uid, rid, od.isoformat(), status, amount, dtime, pay))
            # items for delivered/cancelled alike
            cuisine = rest_cuisine[rid]
            n_items = random.randint(1, 4)
            chosen = random.sample(DISHES[cuisine], k=min(n_items, len(DISHES[cuisine])))
            for dish in chosen:
                item_id += 1
                qty = random.randint(1, 3)
                price = round(random.uniform(60, 400), 2)
                items.append((item_id, oid, dish, qty, price))
    c.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)", orders)
    c.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", items)

    # ---- app_events (funnel) ----
    # For a subset of user-days, emit a partial funnel so funnel/drop-off queries work.
    events = []
    eid = 0
    funnel = ["app_open", "search", "restaurant_view", "add_to_cart", "checkout", "order_placed"]
    for uid, _, _, usd, plat in users:
        signup = date.fromisoformat(usd)
        n_sessions = random.choices([0, 1, 2, 3, 4], weights=[10, 30, 30, 18, 12])[0]
        for _ in range(n_sessions):
            ed = rand_date(signup, END)
            hh = random.randint(8, 23)
            mm = random.randint(0, 59)
            # user progresses through funnel until a random drop-off point
            depth = random.choices(range(1, 7), weights=[10, 18, 22, 20, 15, 15])[0]
            for step in range(depth):
                eid += 1
                ts = f"{ed.isoformat()} {hh:02d}:{(mm+step) % 60:02d}:00"
                events.append((eid, uid, funnel[step], ts, plat))
    c.executemany("INSERT INTO app_events VALUES (?,?,?,?,?)", events)

    conn.commit()

    # ---- report ----
    for t in ["users", "restaurants", "orders", "order_items", "app_events"]:
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"{t:15s}: {n:,} rows")
    conn.close()
    print("\nBuilt zomato.db successfully.")


if __name__ == "__main__":
    main()
