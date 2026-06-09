# app/core/rules_engine.py
"""
Rules engine for business logic that overlays the ML model.

Rules run AFTER ML scoring. They can:
- Escalate an APPROVE to REVIEW
- Escalate a REVIEW to BLOCK
- Never de-escalate (rules only increase risk, never decrease it)

Why a rules engine alongside ML:
  ML is probabilistic — it says "this looks 72% like fraud based
  on historical patterns." Rules are deterministic — they say
  "our policy is to always review first-time large transfers."
  
  These are different things. A mature fraud system needs both.
  ML handles known patterns. Rules handle business policies.

Adding new rules requires no model retraining — just add a function.
"""
from app.config import AML_CTR_THRESHOLD


def apply_rules(
    features: dict,
    current_decision: str,
    velocity: dict,
    transaction_data: dict,
) -> dict:
    """
    Apply business rules to a transaction.

    Args:
        features:         Engineered feature dict
        current_decision: Current ML decision (APPROVE/REVIEW/BLOCK)
        velocity:         Velocity features dict
        transaction_data: Raw transaction fields

    Returns:
        Dict with final_decision and triggered_rules list
    """
    triggered = []
    decision  = current_decision
    amount    = float(transaction_data.get("amount", 0))

    def escalate(to: str, rule: str):
        nonlocal decision
        triggered.append(rule)
        # Rules only escalate, never de-escalate
        priority = ["APPROVE", "REVIEW", "BLOCK"]
        if priority.index(to) > priority.index(decision):
            decision = to

    # ── Rule 1: Large first-time transfer ─────────────────────────
    # High-value transfers from accounts with no velocity history
    # are high risk regardless of ML score
    if (
        amount >= 1_000_000
        and velocity.get("txn_count_24hour", 0) == 0
        and features.get("is_transfer", 0) == 1
    ):
        escalate("REVIEW", "LARGE_FIRST_TRANSFER: ₦1M+ with no prior activity")

    # ── Rule 2: Multiple high-value transactions in 10 minutes ────
    if velocity.get("txn_count_10min", 0) >= 3:
        escalate("REVIEW", "HIGH_VELOCITY_10MIN: 3+ transactions in 10 minutes")

    # ── Rule 3: Account completely drained ─────────────────────────
    if (
        features.get("orig_balance_zeroed", 0) == 1
        and features.get("dest_balance_zero_before", 0) == 1
    ):
        escalate("BLOCK", "FULL_DRAIN_MULE: Account drained to zero-balance destination")

    # ── Rule 4: Hourly total exceeds threshold ─────────────────────
    if velocity.get("txn_total_1hour", 0) >= AML_CTR_THRESHOLD:
        escalate("REVIEW", f"HIGH_HOURLY_TOTAL: ₦{velocity['txn_total_1hour']:,.0f} in 1 hour")

    # ── Rule 5: Night-time large transaction ──────────────────────
    hour = features.get("hour_of_day", 12)
    if hour < 5 and amount >= 500_000:
        escalate("REVIEW", "NIGHT_LARGE: Large transaction between midnight and 5am")

    return {
        "final_decision":  decision,
        "triggered_rules": triggered,
        "rules_applied":   len(triggered),
    }