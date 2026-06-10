# app/core/feature_engineer.py
"""
Feature engineering for the fraud detection pipeline.

Transforms raw transaction fields into 14 ML-ready numeric features.
This module is the single source of truth for feature definitions.
The same function runs during training (batch) and inference (single).

FEATURE_COLUMNS must stay in sync between:
  - engineer_features() return dict
  - engineer_features_batch() return DataFrame columns
  - scripts/prepare_data.py
  - app/models/scaler.pkl (fitted column order)

Deliberately excluded features (PaySim artefacts):
  error_balance_orig = (oldbalanceOrg - newbalanceOrig) - amount
  error_balance_dest = (newbalanceDest - oldbalanceDest) - amount
  In PaySim's synthetic simulation these are always 0 for legitimate
  and always non-zero for fraud — perfectly discriminative, zero learning.
  Including them produces 100% accuracy with best_iteration=0.
  They are simulation artefacts, not real fraud signals.
"""
import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "amount",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
    "hour_of_day",
    "is_transfer",
    "is_cashout",
    "balance_diff_orig",
    "balance_diff_dest",
    "amount_ratio_orig",
    "dest_balance_zero_before",
    "dest_balance_zero_after",
    "orig_balance_zeroed",
]


def engineer_features(transaction: dict) -> dict:
    """
    Engineer features for a single transaction.
    Used at inference time in the detection pipeline.

    Args:
        transaction: Dict with raw transaction fields.
                     Keys: step, type, amount, oldbalanceOrg,
                     newbalanceOrig, oldbalanceDest, newbalanceDest

    Returns:
        Dict with exactly FEATURE_COLUMNS as keys.
    """
    step            = int(transaction.get("step", 0))
    tx_type         = str(transaction.get("type", "")).upper()
    amount          = float(transaction.get("amount", 0.0))
    old_bal_orig    = float(transaction.get("oldbalanceOrg", 0.0))
    new_bal_orig    = float(transaction.get("newbalanceOrig", 0.0))
    old_bal_dest    = float(transaction.get("oldbalanceDest", 0.0))
    new_bal_dest    = float(transaction.get("newbalanceDest", 0.0))

    return {
        # Direct fields — passed through unchanged
        "amount":          amount,
        "oldbalanceOrg":   old_bal_orig,
        "newbalanceOrig":  new_bal_orig,
        "oldbalanceDest":  old_bal_dest,
        "newbalanceDest":  new_bal_dest,

        # Time — cyclical daily pattern (0–23), not monotonic step (1–744)
        "hour_of_day":     step % 24,

        # Type encoding — binary flags instead of string categories
        # Only TRANSFER and CASH_OUT are ever scored (type guard catches others)
        "is_transfer":     1 if tx_type == "TRANSFER"  else 0,
        "is_cashout":      1 if tx_type == "CASH_OUT"  else 0,

        # Balance change signals
        "balance_diff_orig": old_bal_orig - new_bal_orig,
        "balance_diff_dest": new_bal_dest - old_bal_dest,

        # Amount as a fraction of sender's balance
        # Near 1.0 = account drain = strong fraud signal
        # +1 prevents division by zero for zero-balance accounts
        "amount_ratio_orig": amount / (old_bal_orig + 1),

        # Zero-balance flags — key indicators of fraud patterns
        # dest_balance_zero_before: recipient had no money → mule account
        # dest_balance_zero_after:  recipient emptied it immediately → layering
        # orig_balance_zeroed:      sender account fully drained → takeover
        "dest_balance_zero_before": 1 if old_bal_dest == 0.0 else 0,
        "dest_balance_zero_after":  1 if new_bal_dest == 0.0 else 0,
        "orig_balance_zeroed":      1 if new_bal_orig == 0.0 else 0,
    }


def engineer_features_batch(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features for a DataFrame of transactions.
    Used during model training in scripts/prepare_data.py.

    Args:
        df: Raw PaySim DataFrame with original column names.

    Returns:
        DataFrame with exactly FEATURE_COLUMNS as columns,
        in the same order as FEATURE_COLUMNS list.
    """
    result = pd.DataFrame()

    result["amount"]          = df["amount"].astype(float)
    result["oldbalanceOrg"]   = df["oldbalanceOrg"].astype(float)
    result["newbalanceOrig"]  = df["newbalanceOrig"].astype(float)
    result["oldbalanceDest"]  = df["oldbalanceDest"].astype(float)
    result["newbalanceDest"]  = df["newbalanceDest"].astype(float)

    result["hour_of_day"] = (df["step"] % 24).astype(int)

    result["is_transfer"] = (df["type"] == "TRANSFER").astype(int)
    result["is_cashout"]  = (df["type"] == "CASH_OUT").astype(int)

    result["balance_diff_orig"] = (
        df["oldbalanceOrg"] - df["newbalanceOrig"]
    ).astype(float)
    result["balance_diff_dest"] = (
        df["newbalanceDest"] - df["oldbalanceDest"]
    ).astype(float)

    result["amount_ratio_orig"] = (
        df["amount"] / (df["oldbalanceOrg"] + 1)
    ).astype(float)

    result["dest_balance_zero_before"] = (
        df["oldbalanceDest"] == 0.0
    ).astype(int)
    result["dest_balance_zero_after"] = (
        df["newbalanceDest"] == 0.0
    ).astype(int)
    result["orig_balance_zeroed"] = (
        df["newbalanceOrig"] == 0.0
    ).astype(int)

    return result[FEATURE_COLUMNS]