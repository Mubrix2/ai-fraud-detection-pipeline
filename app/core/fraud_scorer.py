# app/core/fraud_scorer.py
"""
XGBoost fraud scoring module.

Singleton pattern: model loads once at startup, reused for every transaction.
Creating an XGBClassifier from a .pkl file takes ~500ms — unacceptable per-request.

Decision: 3-tier threshold
    BLOCK  (fraud_prob >= 0.85): high confidence fraud, decline
    REVIEW (fraud_prob >= 0.60): moderate risk, flag for analyst
    APPROVE(fraud_prob < 0.60):  low risk, proceed
"""
import json
import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

from app.config import (
    FRAUD_MODEL_PATH,
    SCALER_PATH,
    THRESHOLD_BLOCK,
    THRESHOLD_REVIEW,
)
from app.core.feature_engineer import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

_model  = None
_scaler = None


def load_model() -> bool:
    """Load XGBoost model and scaler at startup. Returns True on success."""
    global _model, _scaler

    if not FRAUD_MODEL_PATH.exists():
        logger.warning(f"Fraud model not found: {FRAUD_MODEL_PATH}")
        logger.warning("Run: python scripts/train_fraud_model.py")
        return False

    _model = joblib.load(FRAUD_MODEL_PATH)

    if SCALER_PATH.exists():
        _scaler = joblib.load(SCALER_PATH)
        logger.info("Scaler loaded")

    # Load threshold from metadata if available
    meta_path = FRAUD_MODEL_PATH.parent / "fraud_model_metadata.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        logger.info(
            f"Fraud model loaded | "
            f"threshold={THRESHOLD_BLOCK} | "
            f"recall={meta.get('fraud_recall', 'N/A')}"
        )

    # Initialise SHAP explainer after model loads
    from app.core.explainer import initialise_explainer
    initialise_explainer(_model)

    return True


def score_transaction(features: dict) -> dict:
    """
    Score a single transaction using the XGBoost fraud model.

    Args:
        features: Dict with FEATURE_COLUMNS keys (from engineer_features)

    Returns:
        Dict with fraud_probability, decision, risk_level, model_available
    """
    if _model is None:
        return {
            "fraud_probability": 0.0,
            "decision":       "APPROVE",
            "risk_level":     "UNKNOWN",
            "model_available": False,
        }

    import pandas as pd
    feature_df = pd.DataFrame(
        [[features.get(col, 0.0) for col in FEATURE_COLUMNS]],
        columns=FEATURE_COLUMNS,
    )

    if _scaler is not None:
        feature_array = _scaler.transform(feature_df)
    else:
        feature_array = feature_df.values

    fraud_prob = float(_model.predict_proba(feature_array)[0][1])

    # 3-tier decision — clean and standard
    if fraud_prob >= THRESHOLD_BLOCK:
        decision   = "BLOCK"
        risk_level = "CRITICAL"
    elif fraud_prob >= THRESHOLD_REVIEW:
        decision   = "REVIEW"
        risk_level = "HIGH"
    else:
        decision   = "APPROVE"
        risk_level = "LOW"

    return {
        "fraud_probability": round(fraud_prob, 6),
        "decision":          decision,
        "risk_level":        risk_level,
        "model_available":   True,
    }