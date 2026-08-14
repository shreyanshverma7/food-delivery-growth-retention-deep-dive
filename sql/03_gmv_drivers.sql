-- Q: What's the MoM GMV growth, and which restaurants drive it in each city?

-- Month-over-month delivered GMV and % growth vs the previous month.
WITH monthly AS (
    SELECT strftime('%Y-%m', order_date) AS ym, SUM(order_amount) AS gmv
    FROM orders
    WHERE order_status = 'delivered'
    GROUP BY strftime('%Y-%m', order_date)
)
SELECT ym,
       ROUND(gmv, 2) AS gmv,
       ROUND(LAG(gmv) OVER (ORDER BY ym), 2) AS prev_gmv,
       ROUND(100.0 * (gmv - LAG(gmv) OVER (ORDER BY ym)) / LAG(gmv) OVER (ORDER BY ym), 2) AS mom_growth_pct
FROM monthly
ORDER BY ym;

-- Top-3 restaurants by delivered revenue in each city ("top N per group" via DENSE_RANK).
WITH rev AS (
    SELECT r.restaurant_id, r.name, r.city,
           SUM(o.order_amount) AS revenue
    FROM orders o
    JOIN restaurants r ON r.restaurant_id = o.restaurant_id
    WHERE o.order_status = 'delivered'
    GROUP BY r.restaurant_id, r.name, r.city
),
ranked AS (
    SELECT *, DENSE_RANK() OVER (PARTITION BY city ORDER BY revenue DESC) AS city_rank
    FROM rev
)
SELECT city, name, ROUND(revenue, 2) AS revenue, city_rank
FROM ranked
WHERE city_rank <= 3
ORDER BY city, city_rank;
