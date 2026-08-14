-- Q: Which cities/payment methods have the worst cancellation rates, and what's the revenue at risk?

-- By city: cancellation rate, plus the gross order value tied up in cancelled orders.
SELECT u.city,
       COUNT(*) AS total_orders,
       SUM(CASE WHEN o.order_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_orders,
       ROUND(100.0 * SUM(CASE WHEN o.order_status = 'cancelled' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cancel_rate_pct,
       ROUND(SUM(CASE WHEN o.order_status = 'cancelled' THEN o.order_amount ELSE 0 END), 2) AS revenue_at_risk
FROM orders o
JOIN users u ON u.user_id = o.user_id
GROUP BY u.city
ORDER BY cancel_rate_pct DESC;

-- By payment method: same shape, different cut.
SELECT payment_method,
       COUNT(*) AS total_orders,
       SUM(CASE WHEN order_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_orders,
       ROUND(100.0 * SUM(CASE WHEN order_status = 'cancelled' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cancel_rate_pct,
       ROUND(SUM(CASE WHEN order_status = 'cancelled' THEN order_amount ELSE 0 END), 2) AS revenue_at_risk
FROM orders
GROUP BY payment_method
ORDER BY cancel_rate_pct DESC;
