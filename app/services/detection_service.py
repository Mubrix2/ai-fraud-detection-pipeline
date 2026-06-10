# app/services/detection_service.py
"""
Main fraud detection pipeline orchestrator.

Every transaction flows through this function exactly once.
The pipeline runs in this sequence:

1. Type guard     — PAYMENT/CASH_IN/DEBIT auto-approve (out of model scope)
2. Feature eng    — 14 base features
3. Velocity       — per-customer behavioral context
4. AML detection  — structuring, layering, CTR/SAR
5. ML scoring     — XGBoost fraud probability
6. Anomaly check  — Isolation Forest
7. Rules engine   — business rules overlay
8. SHAP           — compliance explanation
9. Audit log      — immutable record

Decision logic (clear and auditable):
    BLOCK  if fraud_prob >= 0.85
    REVIEW if fraud_prob >= 0.60 OR rules escalate OR AML flags
    APPROVE otherwise
"""
import logging
import time
from datetime import datetime, timezone

from app.core.anomaly_detector import score_transaction as anomaly_score
from app.core.audit_logger import log_decision
from app.core.circuit_breaker import fraud_breaker, rule_fallback
from app.core.explainer import explain_transaction
from app.core.feature_engineer import engineer_features
from app.core.fraud_scorer import score_transaction as fraud_score
from app.core.rules_engine import apply_rules
from app.core.velocity_engine import get_velocity_features, record_transaction
from app.core import aml_detector

logger = logging.getLogger(__name__)

# Transaction types the ML model was trained on
# All others are auto-approved — model has no reference for them
SCOREABLE_TYPES = {"TRANSFER", "CASH_OUT"}


def assess_transaction(
    transaction_id: str,
    transaction_data: dict,
) -> dict:
    """
    Run a transaction through the full fraud detection pipeline.

    Args:
        transaction_id:   Unique identifier for this transaction
        transaction_data: Raw transaction fields (type, amount, balances, etc.)

    Returns:
        Complete assessment dict with decision, risk score, SHAP explanation,
        AML flags, velocity context, and audit fields.
    """
    start = time.perf_counter()

    tx_type = str(transaction_data.get("type", "")).upper()
    amount  = float(transaction_data.get("amount", 0))
    name_orig = str(transaction_data.get("name_orig", "UNKNOWN"))
    name_dest = str(transaction_data.get("name_dest", "UNKNOWN"))

    # ── 1. Type guard ──────────────────────────────────────────────
    # The model was trained on TRANSFER and CASH_OUT only.
    # Other types produce out-of-distribution predictions (garbage).
    if tx_type not in SCOREABLE_TYPES:
        elapsed = (time.perf_counter() - start) * 1000
        assessment = _build_assessment(
            transaction_id   = transaction_id,
            transaction_data = transaction_data,
            fraud_probability = 0.0,
            decision         = "APPROVE",
            risk_level       = "LOW",
            is_flagged       = False,
            anomaly_label    = "N/A",
            velocity         = {},
            aml              = {"aml_flags": [], "aml_flag_count": 0,
                                 "requires_sar": False, "requires_ctr": False,
                                 "aml_score": 0, "aml_note": "Type outside model scope."},
            rules            = {"triggered_rules": [], "rules_applied": 0},
            explanation      = {"top_reasons": [],
                                 "explanation_text": f"{tx_type} is outside the model scope — auto-approved.",
                                 "explanation_available": False},
            processing_ms    = elapsed,
            note             = f"Auto-approved: {tx_type} not in training scope",
        )
        log_decision(assessment)
        logger.info(f"AUTO-APPROVED | {transaction_id} | type={tx_type} | {elapsed:.1f}ms")
        return assessment

    # ── 2. Feature engineering ─────────────────────────────────────
    internal = {
        "step":           transaction_data.get("step", 0),
        "type":           tx_type,
        "amount":         amount,
        "oldbalanceOrg":  float(transaction_data.get("oldbalance_org", 0)),
        "newbalanceOrig": float(transaction_data.get("newbalance_orig", 0)),
        "oldbalanceDest": float(transaction_data.get("oldbalance_dest", 0)),
        "newbalanceDest": float(transaction_data.get("newbalance_dest", 0)),
    }
    features = engineer_features(internal)

    # ── 3. Velocity features ───────────────────────────────────────
    record_transaction(name_orig, amount)
    velocity = get_velocity_features(name_orig, amount)

    # ── 4. AML detection ───────────────────────────────────────────
    aml_detector.record_for_aml(name_orig, amount, tx_type)
    aml = aml_detector.detect(name_orig, amount, tx_type)

    # ── 5. ML scoring (with circuit breaker protection) ────────────
    if fraud_breaker.is_open:
        logger.warning("Circuit breaker OPEN — using rule fallback")
        fraud_result = rule_fallback(features, amount)
    else:
        try:
            fraud_result = fraud_score(features)
            fraud_breaker.record_success()
        except Exception as e:
            fraud_breaker.record_failure()
            logger.error(f"ML scoring failed: {e} — using fallback")
            fraud_result = rule_fallback(features, amount)

    fraud_prob = fraud_result["fraud_probability"]
    decision   = fraud_result["decision"]
    risk_level = fraud_result["risk_level"]

    # ── 6. Anomaly detection ───────────────────────────────────────
    anomaly = anomaly_score(features)

    # Anomaly can escalate APPROVE → REVIEW (never de-escalates)
    if (
    anomaly["is_anomalous"]
    and anomaly["anomaly_label"] == "ANOMALOUS" 
    and decision == "APPROVE"
):
        decision   = "REVIEW"
        risk_level = "MEDIUM"

    # ── 7. Rules engine ────────────────────────────────────────────
    # AML flags can also force REVIEW
    rules = apply_rules(features, decision, velocity, transaction_data)
    decision = rules["final_decision"]

    # AML flag escalation
    if aml["aml_flag_count"] > 0 and decision == "APPROVE":
        decision   = "REVIEW"
        risk_level = "HIGH"

    is_flagged = decision in ("REVIEW", "BLOCK")

    # ── 8. SHAP explanation ────────────────────────────────────────
    explanation = explain_transaction(features)

    # ── 9. Build assessment and audit ─────────────────────────────
    elapsed = (time.perf_counter() - start) * 1000

    assessment = _build_assessment(
        transaction_id    = transaction_id,
        transaction_data  = transaction_data,
        fraud_probability = fraud_prob,
        decision          = decision,
        risk_level        = risk_level,
        is_flagged        = is_flagged,
        anomaly_label     = anomaly["anomaly_label"],
        velocity          = velocity,
        aml               = aml,
        rules             = rules,
        explanation       = explanation,
        processing_ms     = elapsed,
    )

    log_decision(assessment)

    log_level = logging.WARNING if is_flagged else logging.INFO
    logger.log(
        log_level,
        f"{'🚨' if is_flagged else '✅'} {decision} | "
        f"{transaction_id} | "
        f"fraud={fraud_prob:.3f} | "
        f"anomaly={anomaly['anomaly_label']} | "
        f"aml={aml['aml_flag_count']} flags | "
        f"{elapsed:.1f}ms"
    )

    return assessment


def _build_assessment(
    transaction_id, transaction_data, fraud_probability,
    decision, risk_level, is_flagged, anomaly_label,
    velocity, aml, rules, explanation, processing_ms, note=None,
) -> dict:
    return {
        "transaction_id":    transaction_id,
        "transaction": {
            "type":   transaction_data.get("type"),
            "amount": transaction_data.get("amount"),
            "step":   transaction_data.get("step"),
        },
        "fraud_probability": round(fraud_probability, 6),
        "decision":          decision,
        "risk_level":        risk_level,
        "is_flagged":        is_flagged,
        "anomaly_label":     anomaly_label,
        "aml_flag_count":    aml.get("aml_flag_count", 0),
        "aml_flags":         aml.get("aml_flags", []),
        "requires_sar":      aml.get("requires_sar", False),
        "requires_ctr":      aml.get("requires_ctr", False),
        "aml_note":          aml.get("aml_note", ""),
        "triggered_rules":   rules.get("triggered_rules", []),
        "velocity":          velocity,
        "top_reasons":       explanation.get("top_reasons", []),
        "explanation_text":  explanation.get("explanation_text", ""),
        "explanation_available": explanation.get("explanation_available", False),
        "scored_at":         datetime.now(timezone.utc).isoformat(),
        "processing_ms":     round(processing_ms, 2),
        **({"note": note} if note else {}),
    }