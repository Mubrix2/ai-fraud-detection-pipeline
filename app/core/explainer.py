# app/core/explainer.py
"""
SHAP TreeExplainer for XGBoost fraud model.

Provides exact feature attributions for every flagged transaction.
TreeExplainer is exact (not approximate) — it uses the tree structure
directly, computing precise Shapley values in milliseconds.

Initialised once after model loads. Creating TreeExplainer parses
all 500 trees (~1 second). Reused for every subsequent transaction.
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

from app.core.feature_engineer import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

_explainer = None

IMPACT_LABELS = {
    "HIGH":   lambda v: abs(v) >= 0.15,
    "MEDIUM": lambda v: abs(v) >= 0.05,
    "LOW":    lambda v: abs(v) < 0.05,
}

FEATURE_PLAIN_ENGLISH = {
    "amount":                 "Transaction amount",
    "oldbalanceOrg":          "Sender balance before transaction",
    "newbalanceOrig":         "Sender balance after transaction",
    "oldbalanceDest":         "Recipient balance before transaction",
    "newbalanceDest":         "Recipient balance after transaction",
    "hour_of_day":            "Hour of day transaction occurred",
    "is_transfer":            "Transaction is a TRANSFER type",
    "is_cashout":             "Transaction is a CASH_OUT type",
    "balance_diff_orig":      "Change in sender balance",
    "balance_diff_dest":      "Change in recipient balance",
    "amount_ratio_orig":      "Transaction amount as fraction of sender balance",
    "dest_balance_zero_before": "Recipient had zero balance before transaction",
    "dest_balance_zero_after":  "Recipient had zero balance after transaction",
    "orig_balance_zeroed":      "Sender account completely emptied",
}


def initialise_explainer(model) -> None:
    """Initialise TreeExplainer after model loads. Called once."""
    global _explainer
    try:
        import shap
        _explainer = shap.TreeExplainer(model)
        logger.info("SHAP TreeExplainer initialised")
    except Exception as e:
        logger.warning(f"SHAP explainer failed to initialise: {e}")


def explain_transaction(features: dict, top_n: int = 5) -> dict:
    """
    Generate SHAP explanation for a single transaction.

    Args:
        features: Feature dict from engineer_features()
        top_n:    Number of top features to return (default 5)

    Returns:
        Dict with top_reasons list and explanation_text string
    """
    if _explainer is None:
        return {
            "top_reasons": [],
            "explanation_text": "SHAP explainer not available.",
            "explanation_available": False,
        }

    feature_df = pd.DataFrame(
        [[features.get(col, 0.0) for col in FEATURE_COLUMNS]],
        columns=FEATURE_COLUMNS,
    )

    try:
        shap_values = _explainer.shap_values(feature_df)

        if isinstance(shap_values, list):
            values = shap_values[1][0]  # fraud class
        else:
            values = shap_values[0]

        # Rank by absolute contribution
        ranked = sorted(
            zip(FEATURE_COLUMNS, values),
            key=lambda x: abs(x[1]),
            reverse=True,
        )[:top_n]

        top_reasons = []
        for feat, shap_val in ranked:
            direction = "increased_risk" if shap_val > 0 else "decreased_risk"
            abs_val   = abs(shap_val)
            impact    = "HIGH" if abs_val >= 0.15 else (
                        "MEDIUM" if abs_val >= 0.05 else "LOW")

            top_reasons.append({
                "feature":     feat,
                "description": FEATURE_PLAIN_ENGLISH.get(feat, feat),
                "shap_value":  round(float(shap_val), 4),
                "direction":   direction,
                "impact":      impact,
            })

        lines = []
        for r in top_reasons:
            sign = "▲" if r["direction"] == "increased_risk" else "▼"
            lines.append(
                f"{sign} {r['description']} "
                f"(impact: {r['impact']}, "
                f"SHAP: {r['shap_value']:+.4f})"
            )
        explanation_text = "\n".join(lines)

        return {
            "top_reasons":          top_reasons,
            "explanation_text":     explanation_text,
            "explanation_available": True,
        }

    except Exception as e:
        logger.error(f"SHAP explanation failed: {e}")
        return {
            "top_reasons": [],
            "explanation_text": f"Explanation unavailable: {e}",
            "explanation_available": False,
        }