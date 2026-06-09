# tests/test_feature_engineer.py
"""
Unit tests for feature engineering.

Tests verify:
- Correct feature count (14)
- Each feature computed correctly
- Edge cases (zero balances, different types)
- Batch function consistency with single function
"""
import pytest
import numpy as np
import pandas as pd

from app.core.feature_engineer import (
    FEATURE_COLUMNS,
    engineer_features,
    engineer_features_batch,
)


def make_transaction(**overrides) -> dict:
    """Base transaction — legitimate TRANSFER."""
    base = {
        "step": 10,
        "type": "TRANSFER",
        "amount": 100_000.0,
        "oldbalanceOrg": 200_000.0,
        "newbalanceOrig": 100_000.0,
        "oldbalanceDest": 50_000.0,
        "newbalanceDest": 150_000.0,
    }
    base.update(overrides)
    return base


class TestFeatureColumns:
    def test_exactly_14_features(self):
        assert len(FEATURE_COLUMNS) == 14

    def test_excluded_features_not_present(self):
        assert "error_balance_orig" not in FEATURE_COLUMNS
        assert "error_balance_dest" not in FEATURE_COLUMNS

    def test_all_expected_features_present(self):
        expected = [
            "amount", "oldbalanceOrg", "newbalanceOrig",
            "oldbalanceDest", "newbalanceDest", "hour_of_day",
            "is_transfer", "is_cashout", "balance_diff_orig",
            "balance_diff_dest", "amount_ratio_orig",
            "dest_balance_zero_before", "dest_balance_zero_after",
            "orig_balance_zeroed",
        ]
        assert FEATURE_COLUMNS == expected


class TestEngineerFeatures:
    def test_returns_all_feature_columns(self):
        features = engineer_features(make_transaction())
        for col in FEATURE_COLUMNS:
            assert col in features, f"Missing feature: {col}"

    def test_returns_exactly_14_keys(self):
        features = engineer_features(make_transaction())
        assert len(features) == 14

    def test_hour_of_day_from_step(self):
        f = engineer_features(make_transaction(step=25))
        assert f["hour_of_day"] == 1  # 25 % 24 = 1

    def test_hour_of_day_midnight(self):
        f = engineer_features(make_transaction(step=24))
        assert f["hour_of_day"] == 0  # 24 % 24 = 0

    def test_transfer_flag_set(self):
        f = engineer_features(make_transaction(type="TRANSFER"))
        assert f["is_transfer"] == 1
        assert f["is_cashout"] == 0

    def test_cashout_flag_set(self):
        f = engineer_features(make_transaction(type="CASH_OUT"))
        assert f["is_transfer"] == 0
        assert f["is_cashout"] == 1

    def test_payment_both_flags_zero(self):
        f = engineer_features(make_transaction(type="PAYMENT"))
        assert f["is_transfer"] == 0
        assert f["is_cashout"] == 0

    def test_balance_diff_orig(self):
        f = engineer_features(make_transaction(
            oldbalanceOrg=200_000, newbalanceOrig=100_000
        ))
        assert f["balance_diff_orig"] == 100_000.0

    def test_balance_diff_dest(self):
        f = engineer_features(make_transaction(
            oldbalanceDest=50_000, newbalanceDest=150_000
        ))
        assert f["balance_diff_dest"] == 100_000.0

    def test_amount_ratio_full_drain(self):
        f = engineer_features(make_transaction(
            amount=200_000, oldbalanceOrg=200_000
        ))
        # 200000 / (200000 + 1) ≈ 0.999
        assert f["amount_ratio_orig"] > 0.99

    def test_amount_ratio_small_transaction(self):
        f = engineer_features(make_transaction(
            amount=10_000, oldbalanceOrg=1_000_000
        ))
        assert f["amount_ratio_orig"] < 0.02

    def test_dest_balance_zero_before(self):
        f = engineer_features(make_transaction(oldbalanceDest=0.0))
        assert f["dest_balance_zero_before"] == 1

    def test_dest_balance_not_zero_before(self):
        f = engineer_features(make_transaction(oldbalanceDest=50_000))
        assert f["dest_balance_zero_before"] == 0

    def test_dest_balance_zero_after(self):
        f = engineer_features(make_transaction(newbalanceDest=0.0))
        assert f["dest_balance_zero_after"] == 1

    def test_orig_balance_zeroed(self):
        f = engineer_features(make_transaction(newbalanceOrig=0.0))
        assert f["orig_balance_zeroed"] == 1

    def test_orig_balance_not_zeroed(self):
        f = engineer_features(make_transaction(newbalanceOrig=100_000))
        assert f["orig_balance_zeroed"] == 0

    def test_fraud_pattern_all_flags_set(self):
        """Account drain with mule destination — all flags should fire."""
        f = engineer_features(make_transaction(
            type="TRANSFER",
            amount=500_000,
            oldbalanceOrg=500_000,
            newbalanceOrig=0.0,       # full drain
            oldbalanceDest=0.0,       # mule account
            newbalanceDest=0.0,       # immediately emptied
        ))
        assert f["orig_balance_zeroed"] == 1
        assert f["dest_balance_zero_before"] == 1
        assert f["dest_balance_zero_after"] == 1
        assert f["amount_ratio_orig"] > 0.99

    def test_division_by_zero_safe(self):
        """Zero balance sender should not cause division error."""
        f = engineer_features(make_transaction(
            amount=100, oldbalanceOrg=0.0
        ))
        assert np.isfinite(f["amount_ratio_orig"])


class TestBatchFunction:
    def test_batch_matches_single(self):
        """Batch and single functions must produce identical results."""
        tx = make_transaction()
        single = engineer_features(tx)

        df = pd.DataFrame([{
            "step": tx["step"],
            "type": tx["type"],
            "amount": tx["amount"],
            "oldbalanceOrg": tx["oldbalanceOrg"],
            "newbalanceOrig": tx["newbalanceOrig"],
            "oldbalanceDest": tx["oldbalanceDest"],
            "newbalanceDest": tx["newbalanceDest"],
        }])
        batch = engineer_features_batch(df)

        for col in FEATURE_COLUMNS:
            assert single[col] == pytest.approx(
                batch[col].iloc[0], rel=1e-6
            ), f"Mismatch on {col}"

    def test_batch_returns_correct_shape(self):
        rows = [make_transaction(step=i) for i in range(10)]
        df = pd.DataFrame(rows)
        result = engineer_features_batch(df)
        assert result.shape == (10, 14)

    def test_batch_column_order(self):
        df = pd.DataFrame([make_transaction()])
        result = engineer_features_batch(df)
        assert list(result.columns) == FEATURE_COLUMNS