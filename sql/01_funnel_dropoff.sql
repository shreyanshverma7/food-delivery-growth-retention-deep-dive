-- Q: Where is the biggest drop-off between app_open and order_placed?

-- Step-to-step conversion through the funnel, in order.
-- LAG gets the previous step's user count so we can compute step_conv_pct without a self-join.
WITH step_users AS (
    SELECT event_name, COUNT(DISTINCT user_id) AS users
    FROM app_events
    GROUP BY event_name
),
ordered AS (
    SELECT event_name, users,
           CASE event_name
               WHEN 'app_open' THEN 1 WHEN 'search' THEN 2
               WHEN 'restaurant_view' THEN 3 WHEN 'add_to_cart' THEN 4
               WHEN 'checkout' THEN 5 WHEN 'order_placed' THEN 6 END AS step
    FROM step_users
)
SELECT event_name, users,
       LAG(users) OVER (ORDER BY step) AS prev_step_users,
       ROUND(100.0 * users / LAG(users) OVER (ORDER BY step), 2) AS step_conv_pct
FROM ordered
ORDER BY step;

-- Overall funnel conversion: of everyone who opened the app, what % ever placed an order?
WITH funnel_ends AS (
    SELECT
        COUNT(DISTINCT CASE WHEN event_name = 'app_open' THEN user_id END) AS opened,
        COUNT(DISTINCT CASE WHEN event_name = 'order_placed' THEN user_id END) AS ordered
    FROM app_events
)
SELECT ROUND(100.0 * ordered / opened, 2) AS open_to_order_pct
FROM funnel_ends;
