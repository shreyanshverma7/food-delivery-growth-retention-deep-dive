-- Q: Does a slow FIRST delivery predict whether a user ever comes back for a second order?
-- Scoped to delivered orders only: a cancelled order's delivery_time_min doesn't reflect
-- a real delivery experience, so it would be meaningless to fold into this analysis.
WITH first_order AS (
    SELECT user_id, delivery_time_min,
           ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY order_date, order_id) AS rn
    FROM orders
    WHERE order_status = 'delivered'
),
delivered_counts AS (
    SELECT user_id, COUNT(*) AS delivered_orders
    FROM orders
    WHERE order_status = 'delivered'
    GROUP BY user_id
)
SELECT
    CASE
        WHEN f.delivery_time_min < 30 THEN '1: <30 min'
        WHEN f.delivery_time_min < 45 THEN '2: 30-44 min'
        WHEN f.delivery_time_min < 60 THEN '3: 45-59 min'
        ELSE '4: 60+ min'
    END AS first_order_delivery_bucket,
    COUNT(*) AS users,
    SUM(CASE WHEN d.delivered_orders >= 2 THEN 1 ELSE 0 END) AS reordered,
    ROUND(100.0 * SUM(CASE WHEN d.delivered_orders >= 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS reorder_rate_pct
FROM first_order f
JOIN delivered_counts d ON d.user_id = f.user_id
WHERE f.rn = 1
GROUP BY first_order_delivery_bucket
ORDER BY first_order_delivery_bucket;
