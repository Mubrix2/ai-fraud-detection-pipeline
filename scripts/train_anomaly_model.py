# scripts/train_anomaly_model.py
"""
Train Isolation Forest anomaly detector on legitimate transactions.

Why train on legitimate transactions only:
   The model learns what NORMAL looks like. Any transaction
   statistically distant from normal is anomalous — including
   novel fraud patterns that XGBoost has never seen.

   If we trained on all transactions (including fraud), the model
   would learn that fraud is also "normal" and the anomaly boundary
   would shift to include known fraud patterns.

max_samples=256:
   From the original Isolation Forest paper (Liu et al. 2008).
   256 samples per tree is the theoretical sweet spot.
   Using more samples adds computation with diminishing returns.

Usage:
    python scripts/train_anomaly_model.py
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROCESSED_DIR = Path("data/processed")
MODELS_DIR    = Path("app/models")
RANDOM_STATE  = 42


def main():
    print("=" * 55)
    print(" Isolation Forest Anomaly Model Training")
    print("=" * 55)

    X_train = np.load(PROCESSED_DIR / "X_train.npy")
    y_train = np.load(PROCESSED_DIR / "y_train.npy")
    X_test  = np.load(PROCESSED_DIR / "X_test.npy")
    y_test  = np.load(PROCESSED_DIR / "y_test.npy")

    # Train on legitimate transactions only
    X_legit = X_train[y_train == 0]
    print(f"\nTraining on {len(X_legit):,} legitimate transactions only")

    fraud_rate = y_test.mean()
    print(f"Expected fraud rate: {fraud_rate:.4f} (used as contamination)")

    print("\nTraining Isolation Forest...")
    model = IsolationForest(
        n_estimators=200,
        max_samples=256,
        contamination=float(fraud_rate),
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_legit)

    # Evaluate on test set
    # Isolation Forest returns -1 (anomaly) or 1 (normal)
    raw_preds = model.predict(X_test)
    preds = (raw_preds == -1).astype(int)  # convert to 0/1

    print("\nTest set evaluation:")
    print(classification_report(y_test, preds,
                                 target_names=["Legit", "Anomaly"]))

    scores = model.score_samples(X_test)
    print(f"Score range: [{scores.min():.4f}, {scores.max():.4f}]")
    print(f"Threshold (decision_function=0): {model.offset_:.4f}")

    # Save
    model_path = MODELS_DIR / "anomaly_model.pkl"
    joblib.dump(model, model_path)

    metadata = {
        "contamination": round(float(fraud_rate), 6),
        "n_estimators": 200,
        "max_samples": 256,
        "offset": float(model.offset_),
        "train_samples": len(X_legit),
    }
    meta_path = MODELS_DIR / "anomaly_model_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n✅ Model saved → {model_path}")
    print(f"✅ Metadata → {meta_path}")


if __name__ == "__main__":
    main()