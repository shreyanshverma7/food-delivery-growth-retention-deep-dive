# Food-Delivery Growth & Retention Deep-Dive

I analysed 6,387 orders from a food-delivery app (2,000 users, 300 restaurants, 7 cities, 2024) to find where users drop off in the funnel and which cohorts retain, then recommended where growth should invest.

## Top 3 findings

1. **The funnel's worst leak is checkout, not awareness.** Conversion falls from 67.2% to 54.8% between checkout and order_placed — the single biggest step-to-step drop in the funnel. More users are lost at the final payment step than anywhere earlier.
2. **Cancellations are the single biggest lever in this dataset.** $1.24M of gross order value — 41.7% of delivered GMV — sits in cancelled orders, worst on UPI payments (32.2% cancellation rate) and in Pune (30.7%).
3. **Retention is genuinely improving, but the ceiling is still low.** Among cohorts with a full 3-month observation window (Jan–Sep signups), month-1 retention climbs from ~20% to ~38–44% over the year — a real trend — but even the best cohorts see fewer than half of signups place a second order.

**Recommendation:** prioritize a checkout-flow fix and a cancellation root-cause investigation (UPI payment failures, Pune operations) over further top-of-funnel acquisition spend — cancellations alone are worth more than most funnel or retention tweaks combined.

## Data

A synthetic Zomato-style dataset (`database/build_zomato_db.py`, seed 42 — fully reproducible) modeling a food-delivery app over 2024.

| Table | Rows | Grain |
|---|---|---|
| `users` | 2,000 | one row per user |
| `restaurants` | 300 | one row per restaurant |
| `orders` | 6,387 | one row per order (`delivered` or `cancelled`) |
| `order_items` | ~15,900 | one row per dish in an order |
| `app_events` | ~13,200 | one row per funnel event (`app_open → search → restaurant_view → add_to_cart → checkout → order_placed`) |

GMV figures throughout exclude cancelled orders unless explicitly labeled "revenue at risk."

## The 5 questions

### 1. Funnel: where's the biggest drop-off? — [`sql/01_funnel_dropoff.sql`](sql/01_funnel_dropoff.sql)

| Step | Users | Conversion from prior step |
|---|---:|---:|
| app_open | 1,809 | — |
| search | 1,739 | 96.1% |
| restaurant_view | 1,570 | 90.3% |
| add_to_cart | 1,282 | 81.7% |
| checkout | 862 | 67.2% |
| order_placed | 472 | **54.8%** ← biggest drop |

Only 26.1% of everyone who opens the app ever places an order. The checkout → order_placed step loses more users, in relative terms, than any earlier step — the payment/confirmation experience is the highest-priority fix.

### 2. Retention: which cohorts retain best? — [`sql/02_cohort_retention.sql`](sql/02_cohort_retention.sql)

Month-1 retention by signup cohort (cohorts with a full 3-month observable window, Jan–Sep 2024):

| Cohort | M+1 | M+2 | M+3 |
|---|---:|---:|---:|
| 2024-01 | 20.4% | 16.1% | 15.3% |
| 2024-03 | 19.1% | 23.9% | 22.3% |
| 2024-05 | 22.6% | 22.6% | 22.1% |
| 2024-07 | 30.0% | 30.0% | 32.0% |
| 2024-09 | 38.2% | 44.1% | 39.4% |

Retention climbs steadily across the year for cohorts with a complete window. **October and November cohorts show even higher numbers (49.5%, 74.0%) in the dashboard — that's a data-window artifact, not accelerating retention:** those users' orders are compressed into the one or two remaining months of the dataset, inflating near-term retention. Only compare cohorts with a full window.

### 3. GMV drivers: MoM growth and top restaurants — [`sql/03_gmv_drivers.sql`](sql/03_gmv_drivers.sql)

Delivered GMV grew every month in 2024, from $13.9K (Jan) to $735.8K (Dec) — strong but decelerating growth (100%+ MoM early in the year, settling to ~25–33% by Q4, a normal maturation curve). No single restaurant dominates a city: the top restaurant per city caps out around 5.7% of that city's revenue (Bangalore's Restaurant 106), so GMV isn't fragile to any one restaurant churning.

### 4. Power users: do the top 5% drive a disproportionate share of GMV? — [`sql/04_power_users_pareto.sql`](sql/04_power_users_pareto.sql)

The top 5% of users (79 people) generate **17.19%** of total delivered GMV ($510K of $2.97M) — 3.4x their population share. Meaningful, but not a fragile 80/20 Pareto dependency; the business isn't existentially exposed to losing its heaviest users.

### 5. Cancellations: where's the revenue at risk? — [`sql/05_cancellation_revenue_at_risk.sql`](sql/05_cancellation_revenue_at_risk.sql)

| City | Cancel rate | Revenue at risk |
|---|---:|---:|
| Pune | 30.72% | $177.9K |
| Chennai | 29.90% | $173.8K |
| Hyderabad | 29.17% | $183.8K |
| Mumbai | 28.91% | $180.1K |
| Bangalore | 28.74% | $171.0K |
| Kolkata | 28.63% | $181.6K |
| Delhi | 28.56% | $167.5K |

By payment method, UPI is worst at 32.21% cancelled (vs. 26.82% for NetBanking, the best). Total revenue at risk across all cancelled orders: **$1.24M — 41.7% of delivered GMV.**

## Dashboard

![Dashboard screenshot](screenshots/dashboard.png)

Interactive, self-contained (no external dependencies) — open [`dashboard/index.html`](dashboard/index.html) directly in a browser. Regenerate it from the live database with:

```bash
python3 dashboard/build_dashboard_data.py
```

## Stretch: simulated A/B test — [`sql/06_ab_test_checkout_simulation.sql`](sql/06_ab_test_checkout_simulation.sql), [`analysis/ab_test_simulation.py`](analysis/ab_test_simulation.py)

`zomato.db` has no real experiment data, so this is a **fully synthetic simulation**, clearly labeled as such in the script and its output — not a real result. It takes the real checkout-stage population (862 users) and the real baseline conversion rate (54.76%), splits users 50/50, assumes an illustrative +6pp lift for a "new checkout flow" treatment group, simulates individual outcomes with a seeded coin flip, and runs a two-proportion z-test on the simulated data:

```
Control    (n=431): 54.29% simulated conversion
Treatment  (n=431): 58.70% simulated conversion
z = -1.305, p = 0.1918 → NOT significant at alpha=0.05
```

The instructive result: at this sample size (~430/group), even a 6-point lift on a ~55% baseline isn't statistically detectable — a realistic illustration of why checkout-flow experiments need a real power analysis before shipping, not just "did the number go up."

## Reproduce

```bash
# regenerate the database (deterministic, seed 42)
python3 database/build_zomato_db.py

# run any SQL deliverable
sqlite3 -header -column database/zomato.db < sql/01_funnel_dropoff.sql

# rebuild the dashboard
python3 dashboard/build_dashboard_data.py

# run the stretch A/B test simulation
python3 analysis/ab_test_simulation.py
```
