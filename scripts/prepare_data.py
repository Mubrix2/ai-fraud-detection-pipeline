# scripts/prepare_data.py
"""
Prepare PaySim data for model training.

Pipeline:
1. Load raw PaySim CSV
2. Filter to TRANSFER and CASH_OUT (only fraud-relevant types)
3. Engineer 14 features
4. Stratified 80/20 train/test split
5. Fit StandardScaler on training data, apply to both splits
6. Apply SMOTE to training data only (test keeps real distribution)
7. Save processed arrays to data/processed/

Why SMOTE only on training:
   The test set must reflect real-world fraud rates (0.477%)
   to give honest evaluation metrics. Applying SMOTE to test
   data would inflate recall artificially.

Why StandardScaler before SMOTE:
   SMOTE interpolates between samples — scaling first ensures
   interpolation happens in a normalised space.

Usage:
    python scripts/prepare_data.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.feature_engineer import FEATURE_COLUMNS, engineer_features_batch

RAW_PATH       = Path("data/raw/paysim.csv")
PROCESSED_DIR  = Path("data/processed")
MODELS_DIR     = Path("app/models")

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE   = 42
TEST_SIZE      = 0.20
SMOTE_SAMPLING = "auto"


def main():
    print("=" * 55)
    print(" PaySim Data Preparation")
    print("=" * 55)

    # ── 1. Load raw data ───────────────────────────────────────────
    print("\n[1/6] Loading raw data...")
    df = pd.read_csv(RAW_PATH)
    print(f"      Loaded: {len(df):,} rows × {len(df.columns)} columns")
    print(f"      Fraud rate: {df['isFraud'].mean()*100:.3f}%")

    # ── 2. Filter to fraud-relevant transaction types ──────────────
    print("\n[2/6] Filtering to TRANSFER and CASH_OUT...")
    df = df[df["type"].isin(["TRANSFER", "CASH_OUT"])].copy()
    print(f"      After filter: {len(df):,} rows")
    print(f"      Fraud rate:   {df['isFraud'].mean()*100:.3f}%")

    # ── 3. Feature engineering ──────────────────────────────────────
    print("\n[3/6] Engineering features...")
    X = engineer_features_batch(df)
    y = df["isFraud"].values
    print(f"      Feature matrix: {X.shape}")
    print(f"      Features: {list(X.columns)}")
    assert X.shape[1] == len(FEATURE_COLUMNS), (
        f"Expected {len(FEATURE_COLUMNS)} features, got {X.shape[1]}"
    )

    # ── 4. Train/test split ────────────────────────────────────────
    print("\n[4/6] Splitting train/test (80/20, stratified)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )
    print(f"      Train: {len(X_train):,} rows | "
          f"Fraud rate: {y_train.mean()*100:.3f}%")
    print(f"      Test:  {len(X_test):,} rows  | "
          f"Fraud rate: {y_test.mean()*100:.3f}%")

    # ── 5. Scale features ──────────────────────────────────────────
    print("\n[5/6] Scaling features (StandardScaler)...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)

    scaler_path = MODELS_DIR / "scaler.pkl"
    joblib.dump(scaler, scaler_path)
    print(f"      Scaler saved → {scaler_path}")

    # ── 6. SMOTE on training data only ─────────────────────────────
    print("\n[6/6] Applying SMOTE to training data...")
    fraud_before = y_train.sum()
    legit_before = (y_train == 0).sum()
    print(f"      Before SMOTE — fraud: {fraud_before:,} | "
          f"legit: {legit_before:,}")

    smote = SMOTE(random_state=RANDOM_STATE, sampling_strategy=SMOTE_SAMPLING)
    X_train_resampled, y_train_resampled = smote.fit_resample(
        X_train_scaled, y_train
    )
    fraud_after = y_train_resampled.sum()
    legit_after = (y_train_resampled == 0).sum()
    print(f"      After SMOTE  — fraud: {fraud_after:,} | "
          f"legit: {legit_after:,}")

    # ── Save processed arrays ──────────────────────────────────────
    np.save(PROCESSED_DIR / "X_train.npy", X_train_resampled)
    np.save(PROCESSED_DIR / "y_train.npy", y_train_resampled)
    np.save(PROCESSED_DIR / "X_test.npy",  X_test_scaled)
    np.save(PROCESSED_DIR / "y_test.npy",  y_test)

    # Save raw test set (unscaled) for inspection
    X_test.to_csv(PROCESSED_DIR / "X_test_raw.csv", index=False)

    print(f"\n      X_train shape: {X_train_resampled.shape}")
    print(f"      X_test  shape: {X_test_scaled.shape}")
    print(f"\n✅ Data preparation complete")
    print(f"   Saved to: {PROCESSED_DIR}/")


if __name__ == "__main__":
    main()