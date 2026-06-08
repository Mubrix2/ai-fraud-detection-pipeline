# app/config.py
"""
Single source of truth for all configuration.

All values come from environment variables.
This is Twelve-Factor App principle III — Config.

Required variables raise EnvironmentError immediately on startup
so the application fails fast with a clear message rather than
crashing later with a confusing error.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _require(key: str) -> str:
    """Raise immediately if a required variable is missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Check your .env file."
        )
    return value


# ── LLM ───────────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = _require("GROQ_API_KEY")
LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

# ── Kafka ──────────────────────────────────────────────────────────────────────
# Local development: localhost:9092 (WSL2 broker)
# Docker Compose:    kafka:9092     (service name resolution)
KAFKA_BOOTSTRAP_SERVERS: str = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
)
KAFKA_TRANSACTIONS_TOPIC: str = os.getenv(
    "KAFKA_TRANSACTIONS_TOPIC", "raw-transactions"
)
KAFKA_RESULTS_TOPIC: str = os.getenv(
    "KAFKA_RESULTS_TOPIC", "fraud-results"
)
KAFKA_CONSUMER_GROUP: str = os.getenv(
    "KAFKA_CONSUMER_GROUP", "fraud-detection-group"
)

# ── ML Model Paths ─────────────────────────────────────────────────────────────
FRAUD_MODEL_PATH: Path = BASE_DIR / os.getenv(
    "FRAUD_MODEL_PATH", "app/models/fraud_model.pkl"
)
ANOMALY_MODEL_PATH: Path = BASE_DIR / os.getenv(
    "ANOMALY_MODEL_PATH", "app/models/anomaly_model.pkl"
)
SCALER_PATH: Path = BASE_DIR / os.getenv(
    "SCALER_PATH", "app/models/scaler.pkl"
)

# ── Decision Thresholds ────────────────────────────────────────────────────────
# These are business decisions — adjust based on fraud/customer experience tradeoff
FRAUD_THRESHOLD: float = float(os.getenv("FRAUD_THRESHOLD", "0.85"))
ANOMALY_THRESHOLD: float = float(os.getenv("ANOMALY_THRESHOLD", "-0.1"))

# ── AML Thresholds ─────────────────────────────────────────────────────────────
# Nigeria NFIU Currency Transaction Report threshold: ₦5,000,000
AML_CTR_THRESHOLD: float = float(
    os.getenv("AML_CTR_THRESHOLD", "5000000")
)

# ── App ────────────────────────────────────────────────────────────────────────
APP_ENV: str = os.getenv("APP_ENV", "development")