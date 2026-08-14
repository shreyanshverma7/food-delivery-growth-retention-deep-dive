"""
STRETCH GOAL — SIMULATED A/B TEST. NO REAL EXPERIMENT WAS RUN.

zomato.db has no experiment/variant column. This script takes the real,
observed checkout population and baseline conversion rate from the funnel
(sql/06_ab_test_checkout_simulation.sql), then FABRICATES a "new checkout
flow" treatment effect on top of it to demonstrate how a Product Analyst
would size and test a launch. Every number after the baseline is synthetic.

Method: split the real checkout-stage population 50/50 (seeded, reproducible),
assume the control group converts at the real observed baseline rate, assume
the treatment group gets an assumed +6pp lift, simulate individual outcomes
with a seeded coin flip per user at each group's rate, then run a
two-proportion z-test (implemented from scratch, no scipy dependency) on the
SIMULATED outcomes to see whether an effect of this size would have been
detectable at this sample size.
"""

import math
import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "zomato.db"
SEED = 42
ASSUMED_LIFT_PP = 6.0  # assumed absolute lift in percentage points, clearly a made-up input


def real_baseline():
    con = sqlite3.connect(DB_PATH)
    checkout_users = con.execute(
        "SELECT COUNT(DISTINCT user_id) FROM app_events WHERE event_name = 'checkout'"
    ).fetchone()[0]
    ordered_users = con.execute(
        "SELECT COUNT(DISTINCT user_id) FROM app_events WHERE event_name = 'order_placed'"
    ).fetchone()[0]
    con.close()
    return checkout_users, ordered_users / checkout_users


def two_proportion_z_test(x1, n1, x2, n2):
    p1, p2 = x1 / n1, x2 / n2
    p_pool = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se
    # two-tailed p-value from the standard normal CDF (via erf, no scipy needed)
    p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return z, p_value, p1, p2


def main():
    random.seed(SEED)
    checkout_users, baseline_rate = real_baseline()

    n_control = checkout_users // 2
    n_treatment = checkout_users - n_control
    treatment_rate = baseline_rate + ASSUMED_LIFT_PP / 100

    control_conversions = sum(1 for _ in range(n_control) if random.random() < baseline_rate)
    treatment_conversions = sum(1 for _ in range(n_treatment) if random.random() < treatment_rate)

    z, p_value, p1, p2 = two_proportion_z_test(
        control_conversions, n_control, treatment_conversions, n_treatment
    )

    print("=" * 72)
    print("SIMULATED A/B TEST — checkout flow — SYNTHETIC, NOT A REAL EXPERIMENT")
    print("=" * 72)
    print(f"Real observed baseline (checkout -> order_placed): {baseline_rate*100:.2f}% "
          f"of {checkout_users} users")
    print(f"Assumed treatment lift (made up for this simulation): +{ASSUMED_LIFT_PP:.1f}pp")
    print()
    print(f"Control    (n={n_control}): {control_conversions} simulated conversions, "
          f"{p1*100:.2f}%")
    print(f"Treatment  (n={n_treatment}): {treatment_conversions} simulated conversions, "
          f"{p2*100:.2f}%")
    print()
    print(f"Two-proportion z-test:  z = {z:.3f},  p = {p_value:.4f}")
    verdict = "SIGNIFICANT at alpha=0.05" if p_value < 0.05 else "NOT significant at alpha=0.05"
    print(f"Verdict: {verdict}")
    print()
    print("Reminder: every number above except the baseline rate and checkout")
    print("population size is simulated. This demonstrates test design and")
    print("significance-testing methodology, not a real product result.")


if __name__ == "__main__":
    main()
