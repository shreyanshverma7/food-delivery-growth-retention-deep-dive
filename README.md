# Food-Delivery Growth & Retention Deep-Dive

[![CI](https://github.com/shreyanshverma7/food-delivery-growth-retention-deep-dive/actions/workflows/ci.yml/badge.svg)](https://github.com/shreyanshverma7/food-delivery-growth-retention-deep-dive/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](requirements.txt)

I analysed 6,387 orders from a food-delivery app (2,000 users, 300 restaurants, 7 cities, 2024) to find where users drop off in the funnel and which cohorts retain, then recommended where growth should invest.

## Top 3 findings

1. **The funnel's worst leak is checkout, not awareness.** Conversion falls from 67.2% to 54.8% between checkout and order_placed — the single biggest step-to-step drop in the funnel, and platform (iOS/Android/Web) isn't the reason (see "Platform" below) — this is a checkout-flow problem, not a device-specific one.
2. **Cancellations are the single biggest lever in this dataset — but only the payment-method breakdown holds up statistically.** $1.24M of gross order value — 41.7% of delivered GMV — sits in cancelled orders. UPI's 32.2% cancellation rate vs. 26.8% for the best payment method **is statistically significant** (chi-square p=0.019); the city-to-city spread (Pune 30.7% vs. Delhi 28.6%) **is not** (p=0.95) — see "Statistical rigor pass" below. Chasing "Pune operations" would have been chasing noise.
3. **Retention is genuinely improving, but the ceiling is still low.** Among cohorts with a full 3-month observation window (Jan–Sep signups), month-1 retention climbs from ~20% to ~38–44% over the year — a real trend — but even the best cohorts see fewer than half of signups place a second order.

**Recommendation:** prioritize a checkout-flow fix and a UPI-specific cancellation investigation (payment failures/fraud checks, not a city-ops issue) over further top-of-funnel acquisition spend — cancellations alone are worth more than most funnel or retention tweaks combined.

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

## The 7 questions

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

**Caveat, confirmed in the statistical rigor pass below:** the city-to-city spread above (28.6%–30.7%) is *not* statistically significant (chi-square p=0.95) — with 850–985 orders per city, that range is what you'd expect from noise alone. The payment-method spread *is* significant (p=0.019). Don't action the city ranking; do action UPI.

### 6. Platform: does the funnel leak differently by device? — [`sql/07_platform_funnel.sql`](sql/07_platform_funnel.sql)

| Platform | app_open | order_placed | Conversion |
|---|---:|---:|---:|
| iOS | 607 | 164 | 27.02% |
| Android | 595 | 154 | 25.88% |
| Web | 607 | 154 | 25.37% |

Close enough to call — and a chi-square test confirms it (p=0.80, not significant). The checkout-flow problem from Q1 is universal, not concentrated on one platform, so there's no case here for a platform-specific fix.

### 7. Does a slow first delivery cost you the second order? — [`sql/08_delivery_time_repeat_purchase.sql`](sql/08_delivery_time_repeat_purchase.sql)

| First-order delivery time | Users | Reorder rate |
|---|---:|---:|
| <30 min | 318 | 64.15% |
| 30–44 min | 396 | 57.07% |
| 45–59 min | 420 | 68.33% |
| 60+ min | 427 | 61.83% |

The reorder rate does vary significantly by bucket (chi-square p=0.009) — but **not in a clean "slower delivery = fewer reorders" line**: the 45–59 min bucket has the *highest* reorder rate, and 30–44 min has the lowest. Statistically real, but not a story to build a delivery-speed initiative on without digging further — this is flagged as an open question, not a recommendation.

### Statistical rigor pass — [`analysis/statistical_tests.py`](analysis/statistical_tests.py)

Every rate comparison above was point-estimated first, then chi-square tested for whether the spread is distinguishable from chance:

| Comparison | p-value | Verdict |
|---|---:|---|
| Cancellation rate by city | 0.951 | Not significant — noise |
| Cancellation rate by payment method | 0.019 | **Significant** — UPI is really worse |
| app_open→order_placed conversion by platform | 0.800 | Not significant — noise |
| Reorder rate by first-delivery-time bucket | 0.009 | **Significant**, but non-monotonic |

The script also runs a **power analysis** for the stretch A/B test: detecting a +6pp lift on the real 54.76% baseline at 80% power needs **~1,060 users per group** — the real checkout population (862 total, ~431/group) is well short of that, which is exactly why [the simulated A/B test](analysis/ab_test_simulation.py) came back non-significant. At the actual sample size available, only a lift of roughly +10pp or more would be reliably detectable.

## Interactive dashboard (Streamlit)

![Dashboard screenshot](screenshots/dashboard.png)

**Live demo:** not yet deployed — see "Deploy it live" below (~2 minutes on Streamlit Community Cloud, free).

A real multi-page app running live queries against `zomato.db`, not a static export:

- **Global filters** (city, month range, platform, payment method) in the sidebar, shared across every page
- **Drill-downs** — e.g. pick a city on the GMV page to see its top-10 restaurants
- **Live significance testing** — every cancellation/funnel/delivery-time chart recomputes its chi-square test on whatever you've currently filtered to, not a cached number
- **An interactive A/B test power calculator** — drag the baseline/lift/power sliders and watch the required sample size update
- **A read-only SQL playground** — run your own query against the live database (sandboxed: OS-level read-only connection, single-statement, 500-row cap, 5s timeout)

Run it locally:

```bash
pip install -r requirements.txt
streamlit run streamlit_app/app.py
```

**Deploy it live** (so the link works from a resume/LinkedIn, not just `git clone`):
1. Push this repo to GitHub (already done if you're reading this on GitHub).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, click "New app."
3. Pick this repo, branch `main`, main file path `streamlit_app/app.py`. Deploy.
4. Streamlit Cloud installs `requirements.txt` and serves the app at a public `*.streamlit.app` URL — paste that URL into this README once it's up.

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
# install dependencies (scipy for the statistical rigor pass)
pip install -r requirements.txt

# regenerate the database (deterministic, seed 42)
python3 database/build_zomato_db.py

# run any SQL deliverable
sqlite3 -header -column database/zomato.db < sql/01_funnel_dropoff.sql

# launch the interactive dashboard
streamlit run streamlit_app/app.py

# run the stretch A/B test simulation
python3 analysis/ab_test_simulation.py

# run the statistical rigor pass (chi-square tests + A/B power analysis)
python3 analysis/statistical_tests.py
```
