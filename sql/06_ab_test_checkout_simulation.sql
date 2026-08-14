-- Supporting query for the stretch A/B test simulation (analysis/ab_test_simulation.py).
-- Pulls the REAL, observed checkout -> order_placed conversion rate from app_events,
-- which the Python script uses as the control-group baseline before simulating a
-- treatment-group lift. This query alone does not run any A/B test.
WITH step_users AS (
    SELECT event_name, COUNT(DISTINCT user_id) AS users
    FROM app_events
    WHERE event_name IN ('checkout', 'order_placed')
    GROUP BY event_name
)
SELECT
    MAX(CASE WHEN event_name = 'checkout' THEN users END) AS checkout_users,
    MAX(CASE WHEN event_name = 'order_placed' THEN users END) AS order_placed_users,
    ROUND(100.0 * MAX(CASE WHEN event_name = 'order_placed' THEN users END)
                / MAX(CASE WHEN event_name = 'checkout' THEN users END), 2) AS baseline_conversion_pct
FROM step_users;
