# app/core/audit_logger.py
"""
Immutable audit log for all fraud decisions.

Every APPROVE, REVIEW, and BLOCK decision is written here.
Records are inserted only — never updated or deleted.

Satisfies:
- GDPR Article 22: automated decision audit trail
- CBN Consumer Protection Framework: AI decision records
- NFIU requirements: transaction monitoring records

SQLite is sufficient for portfolio scale.
Production: PostgreSQL with connection pooling.
"""
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("app/audit.db")


def initialise_audit_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fraud_audit (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id   TEXT NOT NULL,
                tx_type          TEXT,
                amount           REAL,
                fraud_probability REAL,
                decision         TEXT,
                risk_level       TEXT,
                is_flagged       INTEGER,
                aml_flag_count   INTEGER DEFAULT 0,
                requires_sar     INTEGER DEFAULT 0,
                triggered_rules  TEXT,
                top_reasons      TEXT,
                processing_ms    REAL,
                scored_at        TEXT NOT NULL,
                created_at       TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tx_id "
            "ON fraud_audit(transaction_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_decision "
            "ON fraud_audit(decision)"
        )
        conn.commit()
    logger.info(f"Audit database ready: {DB_PATH}")


def log_decision(assessment: dict) -> None:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO fraud_audit (
                    transaction_id, tx_type, amount,
                    fraud_probability, decision, risk_level,
                    is_flagged, aml_flag_count, requires_sar,
                    triggered_rules, top_reasons,
                    processing_ms, scored_at, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                assessment.get("transaction_id"),
                assessment.get("transaction", {}).get("type"),
                assessment.get("transaction", {}).get("amount"),
                assessment.get("fraud_probability"),
                assessment.get("decision"),
                assessment.get("risk_level"),
                1 if assessment.get("is_flagged") else 0,
                assessment.get("aml_flag_count", 0),
                1 if assessment.get("requires_sar") else 0,
                json.dumps(assessment.get("triggered_rules", [])),
                json.dumps(assessment.get("top_reasons", [])),
                assessment.get("processing_ms"),
                assessment.get("scored_at"),
                datetime.now(timezone.utc).isoformat(),
            ))
            conn.commit()
    except Exception as e:
        logger.error(f"Audit log write failed: {e}")


def get_stats() -> dict:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            total    = conn.execute("SELECT COUNT(*) FROM fraud_audit").fetchone()[0]
            blocked  = conn.execute("SELECT COUNT(*) FROM fraud_audit WHERE decision='BLOCK'").fetchone()[0]
            reviewed = conn.execute("SELECT COUNT(*) FROM fraud_audit WHERE decision='REVIEW'").fetchone()[0]
            sars     = conn.execute("SELECT COUNT(*) FROM fraud_audit WHERE requires_sar=1").fetchone()[0]
            avg_ms   = conn.execute("SELECT AVG(processing_ms) FROM fraud_audit").fetchone()[0] or 0
            return {
                "total": total,
                "blocked": blocked,
                "reviewed": reviewed,
                "approved": total - blocked - reviewed,
                "sar_count": sars,
                "avg_processing_ms": round(avg_ms, 2),
            }
    except Exception:
        return {}