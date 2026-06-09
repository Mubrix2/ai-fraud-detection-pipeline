# app/core/anomaly_detector.py
"""
Isolation Forest anomaly detection module.

Trained on legitimate transactions only. Detects novel patterns
that the supervised XGBoost model has never seen.

Score interpretation:
  More negative = more anomalous = farther from normal transactions
  The offset_ threshold separates normal from anomalous.
"""
import logging
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from app.config import ANOMALY_MODEL_PATH, ANOMALY_THRESHOLD, SCALER_PATH
from app.core.feature_engineer import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

_model  = None
_scaler = None


def load_model() -> bool:
    global _model, _scaler

    if not ANOMALY_MODEL_PATH.exists():
        logger.warning(f"Anomaly model not found: {ANOMALY_MODEL_PATH}")
        logger.warning("Run: python scripts/train_anomaly_model.py")
        return False

    _model = joblib.load(ANOMALY_MODEL_PATH)

    if SCALER_PATH.exists() and _scaler is None:
        _scaler = joblib.load(SCALER_PATH)

    logger.info(f"Anomaly model loaded | threshold={ANOMALY_THRESHOLD}")
    return True


def score_transaction(features: dict) -> dict:
    if _model is None:
        return {
            "anomaly_score":    0.0,
            "is_anomalous":     False,
            "anomaly_label":    "UNKNOWN",
            "model_available":  False,
        }

    feature_df = pd.DataFrame(
        [[features.get(col, 0.0) for col in FEATURE_COLUMNS]],
        columns=FEATURE_COLUMNS,
    )

    if _scaler is not None:
        feature_array = _scaler.transform(feature_df)
    else:
        feature_array = feature_df.values

    score = float(_model.score_samples(feature_array)[0])
    is_anomalous = score < ANOMALY_THRESHOLD

    label = "ANOMALOUS" if score < ANOMALY_THRESHOLD - 0.05 else (
        "SUSPICIOUS" if is_anomalous else "NORMAL"
    )

    return {
        "anomaly_score":   round(score, 6),
        "is_anomalous":    is_anomalous,
        "anomaly_label":   label,
        "model_available": True,
    }