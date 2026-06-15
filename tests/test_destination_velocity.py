# tests/test_destination_velocity.py
"""
Tests for destination-level velocity tracking.

Key property: a single sender hitting one destination repeatedly
is caught by the existing per-customer velocity engine.
Many different senders hitting one destination is caught by this module.
These are different fraud patterns requiring different detectors.
"""
import time
from app.core.destination_velocity import record_destination, get_destination_features


def test_single_sender_not_flagged():
    """One customer sending to one destination = no unusual signal."""
    for i in range(4):
        record_destination("DEST-CLEAN-001", 150.0, "SENDER-ALWAYS-SAME")

    f = get_destination_features("DEST-CLEAN-001")
    assert f["dest_unique_senders_10min"] == 1  # all same sender


def test_multiple_senders_detected():
    """
    5 different customers all sending to same destination in short window.
    This is the card testing pattern — each sender looks clean individually.
    """
    for i in range(5):
        record_destination("DEST-SUSPICIOUS-001", 150.0, f"SENDER-{i:04d}")

    f = get_destination_features("DEST-SUSPICIOUS-001")
    assert f["dest_unique_senders_10min"] == 5


def test_total_inflow_computed():
    for i in range(3):
        record_destination("DEST-INFLOW-001", 1000.0, f"S{i}")

    f = get_destination_features("DEST-INFLOW-001")
    assert f["dest_total_inflow_10min"] == 3000.0


def test_average_amount_computed():
    for i in range(4):
        record_destination("DEST-AVG-001", 200.0, f"AVG-SENDER-{i}")

    f = get_destination_features("DEST-AVG-001")
    assert f["dest_avg_amount_10min"] == 200.0


def test_unknown_destination_returns_zeros():
    f = get_destination_features("DEST-NEVER-SEEN")
    assert f["dest_unique_senders_10min"] == 0
    assert f["dest_total_inflow_10min"] == 0.0


def test_micro_fraud_rule_fires():
    """
    End-to-end: 5 different senders → same destination →
    rules engine should flag MICRO_FRAUD_DESTINATION.
    """
    from app.core.rules_engine import apply_rules
    from app.core.feature_engineer import FEATURE_COLUMNS

    dest_id = "DEST-MICRO-FRAUD-001"
    for i in range(6):
        record_destination(dest_id, 150.0, f"MICRO-SENDER-{i:04d}")

    dest_vel = get_destination_features(dest_id)
    features = {c: 0 for c in FEATURE_COLUMNS}

    result = apply_rules(
        features       = features,
        current_decision = "APPROVE",
        velocity       = {},
        dest_velocity  = dest_vel,
        transaction_data = {"amount": 150},
    )

    assert result["final_decision"] == "REVIEW"
    assert any("MICRO_FRAUD_DESTINATION" in r for r in result["triggered_rules"])