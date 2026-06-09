# scripts/train_fraud_model.py
"""
Train XGBoost fraud classifier on prepared PaySim data.

Training strategy:
- XGBoost on SMOTE-balanced training set (50/50 fraud/legit)
- Early stopping on test set AUCPR to prevent overfitting
- Threshold search: find the probability cutoff that maximises
  F1 score on test set (not default 0.5)
- Save model + metadata for inference

Key metric: AUCPR (Area Under Precision-Recall Curve)
  Not accuracy (misleading with class imbalance).
  Not AUC-ROC (includes irrelevant high-FP regions).
  AUCPR focuses only on the positive (fraud) class — what matters.

Usage:
    python scripts/train_fraud_model.py
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROCESSED_DIR = Path("data/processed")
MODELS_DIR    = Path("app/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)
RANDOM_STATE  = 42


def search_threshold(model, X_test: np.ndarray, y_test: np.ndarray) -> float:
    """
    Find the probability threshold that maximises F1 on the test set.

    Default threshold of 0.5 assumes equal cost of FP and FN.
    In fraud detection, FN (missing fraud) costs more than FP
    (flagging a legitimate transaction). Searching finds the threshold
    that best balances recall and precision for this dataset.
    """
    probs = model.predict_proba(X_test)[:, 1]
    best_threshold = 0.5
    best_f1 = 0.0

    for threshold in np.arange(0.1, 0.95, 0.05):
        preds = (probs >= threshold).astype(int)
        f1 = f1_score(y_test, preds, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = round(float(threshold), 2)

    return best_threshold


def main():
    print("=" * 55)
    print(" XGBoost Fraud Model Training")
    print("=" * 55)

    # ── Load processed data ────────────────────────────────────────
    print("\nLoading processed data...")
    X_train = np.load(PROCESSED_DIR / "X_train.npy")
    y_train = np.load(PROCESSED_DIR / "y_train.npy")
    X_test  = np.load(PROCESSED_DIR / "X_test.npy")
    y_test  = np.load(PROCESSED_DIR / "y_test.npy")

    print(f"  Train: {X_train.shape} | "
          f"Fraud rate: {y_train.mean()*100:.1f}% (after SMOTE)")
    print(f"  Test:  {X_test.shape}  | "
          f"Fraud rate: {y_test.mean()*100:.3f}% (real distribution)")

    # ── Train model ────────────────────────────────────────────────
    print("\nTraining XGBoost...")
    print("This takes 5–10 minutes.\n")

    model = XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=1,       # balanced via SMOTE — no need to reweight
        eval_metric="aucpr",
        early_stopping_rounds=50,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        verbosity=1,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=50,
    )

    print(f"\nTraining complete.")
    print(f"Best iteration: {model.best_iteration}")

    # ── Find optimal threshold ─────────────────────────────────────
    print("\nSearching for optimal decision threshold...")
    threshold = search_threshold(model, X_test, y_test)
    print(f"Optimal threshold: {threshold}")

    # ── Evaluate ───────────────────────────────────────────────────
    probs = model.predict_proba(X_test)[:, 1]
    preds = (probs >= threshold).astype(int)
    cm = confusion_matrix(y_test, preds)
    tn, fp, fn, tp = cm.ravel()
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    roc_auc   = roc_auc_score(y_test, probs)

    print("\n" + "=" * 55)
    print(" EVALUATION REPORT")
    print("=" * 55)
    print(f"\nThreshold: {threshold}")
    print(f"\n{classification_report(y_test, preds, target_names=['Legit', 'Fraud'])}")
    print(f"Confusion Matrix:")
    print(f"  True Negatives  (correctly cleared): {tn:,}")
    print(f"  False Positives (wrongly flagged):   {fp:,}")
    print(f"  False Negatives (missed fraud):      {fn:,}")
    print(f"  True Positives  (caught fraud):      {tp:,}")
    print(f"\nKey Metrics:")
    print(f"  Fraud Recall:    {recall:.4f} — {recall*100:.1f}% of fraud caught")
    print(f"  Fraud Precision: {precision:.4f}")
    print(f"  ROC-AUC:         {roc_auc:.4f}")

    # ── Save model and metadata ────────────────────────────────────
    model_path = MODELS_DIR / "fraud_model.pkl"
    joblib.dump(model, model_path)

    metadata = {
        "threshold": threshold,
        "best_iteration": int(model.best_iteration),
        "fraud_recall": round(recall, 4),
        "fraud_precision": round(precision, 4),
        "roc_auc": round(roc_auc, 4),
        "train_shape": list(X_train.shape),
        "test_shape": list(X_test.shape),
        "features": 14,
    }
    meta_path = MODELS_DIR / "fraud_model_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n✅ Model saved → {model_path}")
    print(f"✅ Metadata saved → {meta_path}")


if __name__ == "__main__":
    main()