-- Q: Does the funnel leak differently by platform (iOS / Android / Web)?
-- Note: app_events.platform is recorded per SESSION, not per user, so a user
-- who opened the app on both iOS and Android contributes to both platforms'
-- counts below. This is a session-level funnel, same convention as sql/01.

-- Step-to-step conversion, split by platform.
WITH step_users AS (
    SELECT platform, event_name, COUNT(DISTINCT user_id) AS users
    FROM app_events
    GROUP BY platform, event_name
),
ordered AS (
    SELECT platform, event_name, users,
           CASE event_name
               WHEN 'app_open' THEN 1 WHEN 'search' THEN 2
               WHEN 'restaurant_view' THEN 3 WHEN 'add_to_cart' THEN 4
               WHEN 'checkout' THEN 5 WHEN 'order_placed' THEN 6 END AS step
    FROM step_users
)
SELECT platform, event_name, users,
       LAG(users) OVER (PARTITION BY platform ORDER BY step) AS prev_step_users,
       ROUND(100.0 * users / LAG(users) OVER (PARTITION BY platform ORDER BY step), 2) AS step_conv_pct
FROM ordered
ORDER BY platform, step;

-- Overall open -> order conversion by platform, for a single headline comparison.
WITH funnel_ends AS (
    SELECT platform,
        COUNT(DISTINCT CASE WHEN event_name = 'app_open' THEN user_id END) AS opened,
        COUNT(DISTINCT CASE WHEN event_name = 'order_placed' THEN user_id END) AS ordered
    FROM app_events
    GROUP BY platform
)
SELECT platform, opened, ordered,
       ROUND(100.0 * ordered / opened, 2) AS open_to_order_pct
FROM funnel_ends
ORDER BY open_to_order_pct DESC;
