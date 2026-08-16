-- Q: Which signup cohorts retain best, and is retention improving month over month?

-- READ 09_retention_exposure_check.sql BEFORE INTERPRETING THIS. The month-1
-- numbers below rise steadily across the year, which looks like improving
-- retention. It is not: later cohorts have fewer months left in the dataset, so
-- a larger share of their orders necessarily lands in month+1. Query 09
-- computes the retention you would expect from pure exposure and shows the
-- observed curve tracks it to within a few points. Do not read a trend here.

-- M1/M2/M3 retention per signup cohort in one pass: for each cohort, what % placed
-- a delivered order in the 1st/2nd/3rd calendar month after their signup month.
-- Conditional COUNT(DISTINCT CASE ...) avoids three separate self-joins.
WITH cohort AS (
    SELECT user_id, signup_date, strftime('%Y-%m', signup_date) AS cohort_month
    FROM users
),
delivered AS (
    SELECT user_id, order_date
    FROM orders
    WHERE order_status = 'delivered'
)
SELECT
    c.cohort_month,
    COUNT(DISTINCT c.user_id) AS cohort_size,
    COUNT(DISTINCT CASE WHEN strftime('%Y-%m', d.order_date)
        = strftime('%Y-%m', date(c.signup_date, 'start of month', '+1 month'))
        THEN d.user_id END) AS retained_m1,
    COUNT(DISTINCT CASE WHEN strftime('%Y-%m', d.order_date)
        = strftime('%Y-%m', date(c.signup_date, 'start of month', '+2 month'))
        THEN d.user_id END) AS retained_m2,
    COUNT(DISTINCT CASE WHEN strftime('%Y-%m', d.order_date)
        = strftime('%Y-%m', date(c.signup_date, 'start of month', '+3 month'))
        THEN d.user_id END) AS retained_m3,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN strftime('%Y-%m', d.order_date)
        = strftime('%Y-%m', date(c.signup_date, 'start of month', '+1 month'))
        THEN d.user_id END) / COUNT(DISTINCT c.user_id), 2) AS retention_m1_pct,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN strftime('%Y-%m', d.order_date)
        = strftime('%Y-%m', date(c.signup_date, 'start of month', '+2 month'))
        THEN d.user_id END) / COUNT(DISTINCT c.user_id), 2) AS retention_m2_pct,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN strftime('%Y-%m', d.order_date)
        = strftime('%Y-%m', date(c.signup_date, 'start of month', '+3 month'))
        THEN d.user_id END) / COUNT(DISTINCT c.user_id), 2) AS retention_m3_pct
FROM cohort c
LEFT JOIN delivered d ON d.user_id = c.user_id
GROUP BY c.cohort_month
ORDER BY c.cohort_month;
