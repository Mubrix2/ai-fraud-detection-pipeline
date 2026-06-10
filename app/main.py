# app/main.py
"""
FastAPI application entry point.

The consumer thread starts here during lifespan startup.
It is a daemon thread — automatically killed when the process exits.

Startup sequence:
1. Initialise audit database (creates SQLite tables if not present)
2. Load ML models (XGBoost + Isolation Forest + SHAP explainer)
3. Initialise Kafka producer
4. Start consumer daemon thread

All four must succeed for the service to be healthy.
If models are missing, the circuit breaker routes to rule fallback.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, transactions
from app.config import APP_ENV
from app.core.anomaly_detector import load_model as load_anomaly
from app.core.audit_logger import initialise_audit_db
from app.core.fraud_scorer import load_model as load_fraud
from app.streaming.consumer import start_consumer, stop_consumer
from app.streaming.producer import initialise_producer, shutdown_producer

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting Fraud Detection Service | env={APP_ENV}")

    # 1. Audit database
    initialise_audit_db()
    logger.info("✅ Audit database ready")

    # 2. ML models
    fraud_ok   = load_fraud()
    anomaly_ok = load_anomaly()
    logger.info(
        f"{'✅' if fraud_ok   else '⚠️ '} Fraud model "
        f"{'loaded' if fraud_ok else 'not found — circuit breaker will use fallback'}"
    )
    logger.info(
        f"{'✅' if anomaly_ok else '⚠️ '} Anomaly model "
        f"{'loaded' if anomaly_ok else 'not found — anomaly scoring disabled'}"
    )

    # 3. Kafka producer
    kafka_ok = initialise_producer()
    logger.info(
        f"{'✅' if kafka_ok else '⚠️ '} Kafka producer "
        f"{'ready' if kafka_ok else 'unavailable — transactions will not be streamed'}"
    )

    # 4. Consumer thread
    consumer_ok = start_consumer()
    logger.info(
        f"{'✅' if consumer_ok else '❌'} Consumer thread "
        f"{'running' if consumer_ok else 'failed to start'}"
    )

    logger.info("🚀 Fraud Detection Service ready")
    yield

    logger.info("Shutting down...")
    stop_consumer()
    shutdown_producer()
    logger.info("Shutdown complete")


app = FastAPI(
    title       = "Real-Time Fraud Detection Pipeline",
    description = (
        "Event-driven fraud detection with XGBoost, Isolation Forest, "
        "AML detection, SHAP explainability, and AI investigation agent."
    ),
    version  = "1.0.0",
    docs_url = "/docs",
    lifespan = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(health.router)
app.include_router(transactions.router, prefix="/api/v1")