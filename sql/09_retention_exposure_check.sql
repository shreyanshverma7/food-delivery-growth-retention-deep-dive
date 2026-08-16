-- Q: Is the rising month-1 retention across 2024 cohorts a real trend, or an
--    artifact of later cohorts having less time left in the dataset?

-- Q2 (02_cohort_retention.sql) shows month-1 retention climbing from ~20% for
-- the January cohort to ~74% for November. That looks like a product getting
-- better at retaining. It isn't.
--
-- Every user's orders are spread across the window between their signup date
-- and the end of the data (2024-12-31). A January user's orders scatter over
-- 11 months, so few land in February specifically. A November user has only
-- ~1 month left, so almost any order they place lands in "month + 1" by
-- construction. Retention rises because the denominator of exposure shrinks,
-- not because behaviour changes.
--
-- This query makes that testable. For each user it computes the probability
-- that at least one of their delivered orders falls in month+1 PURELY BY
-- CHANCE, assuming order dates are uniform across their observable window:
--
--     p        = (days of month+1 inside the user's window) / (window days)
--     P(hit)   = 1 - (1 - p)^n        for n delivered orders
--
-- Averaged per cohort, that is the retention you would see from a population
-- with zero retention behaviour. Compare it to the observed number: if they
-- track, the "trend" in Q2 is entirely exposure.
WITH bounds AS (
    SELECT MAX(order_date) AS data_end FROM orders
),
per_user AS (
    SELECT
        u.user_id,
        strftime('%Y-%m', u.signup_date) AS cohort_month,
        -- days from signup to the end of the data, inclusive
        julianday(b.data_end) - julianday(u.signup_date) + 1 AS window_days,
        -- the calendar month after the signup month, clipped to the window
        MAX(0,
            julianday(MIN(date(u.signup_date, 'start of month', '+2 month', '-1 day'), b.data_end))
          - julianday(MAX(date(u.signup_date, 'start of month', '+1 month'), u.signup_date))
          + 1
        ) AS m1_days,
        (SELECT COUNT(*) FROM orders o
          WHERE o.user_id = u.user_id AND o.order_status = 'delivered') AS n_delivered,
        -- did they actually order in month+1?
        (SELECT COUNT(*) FROM orders o
          WHERE o.user_id = u.user_id AND o.order_status = 'delivered'
            AND strftime('%Y-%m', o.order_date)
              = strftime('%Y-%m', date(u.signup_date, 'start of month', '+1 month'))) > 0
          AS retained_m1
    FROM users u CROSS JOIN bounds b
)
SELECT
    cohort_month,
    COUNT(*)                                            AS cohort_size,
    ROUND(AVG(window_days) / 30.44, 1)                  AS avg_window_months,
    ROUND(100.0 * SUM(retained_m1) / COUNT(*), 1)       AS observed_m1_pct,
    -- expected under "orders land uniformly at random in the window"
    ROUND(100.0 * AVG(
        1 - POWER(1 - (m1_days / window_days), n_delivered)
    ), 1)                                               AS expected_if_no_retention_pct,
    ROUND(100.0 * SUM(retained_m1) / COUNT(*)
        - 100.0 * AVG(1 - POWER(1 - (m1_days / window_days), n_delivered)), 1)
                                                        AS excess_pct_points
FROM per_user
GROUP BY cohort_month
ORDER BY cohort_month;

-- Reading the result: observed and expected track each other to within a few
-- percentage points in both directions, with no systematic sign. The entire
-- 20% -> 74% "improvement" is reproduced by a model containing no retention
-- behaviour at all. Cohort retention in this synthetic dataset is not a
-- product signal; on real data this same exposure-adjusted baseline is what
-- separates a genuine retention trend from a data-window artifact.
