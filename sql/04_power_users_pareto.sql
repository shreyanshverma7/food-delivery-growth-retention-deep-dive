-- Q: Do the top 5% of users drive a disproportionate share of GMV?

-- Rank users into 20 equal-sized buckets (ventiles) by their own delivered GMV;
-- ventile = 1 is the top 5%.
WITH per_user AS (
    SELECT user_id, COUNT(*) AS orders, SUM(order_amount) AS user_gmv
    FROM orders
    WHERE order_status = 'delivered'
    GROUP BY user_id
),
ranked AS (
    SELECT user_id, orders, user_gmv,
           NTILE(20) OVER (ORDER BY user_gmv DESC) AS ventile
    FROM per_user
)
-- The power users themselves, for reference.
SELECT user_id, orders, ROUND(user_gmv, 2) AS user_gmv
FROM ranked
WHERE ventile = 1
ORDER BY user_gmv DESC
LIMIT 20;

-- The actual Pareto split: top-5% segment vs everyone else, share of total delivered GMV.
WITH per_user AS (
    SELECT user_id, SUM(order_amount) AS user_gmv
    FROM orders
    WHERE order_status = 'delivered'
    GROUP BY user_id
),
ranked AS (
    SELECT user_id, user_gmv,
           NTILE(20) OVER (ORDER BY user_gmv DESC) AS ventile
    FROM per_user
)
SELECT
    CASE WHEN ventile = 1 THEN 'Top 5% (power users)' ELSE 'Remaining 95%' END AS segment,
    COUNT(*) AS users,
    ROUND(SUM(user_gmv), 2) AS segment_gmv,
    ROUND(100.0 * SUM(user_gmv) / SUM(SUM(user_gmv)) OVER (), 2) AS pct_of_total_gmv
FROM ranked
GROUP BY segment
ORDER BY segment;
