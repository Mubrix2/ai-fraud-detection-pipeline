# app/core/aml_detector.py
"""
Anti-Money Laundering detection.

Detects three AML typologies from transaction data:
1. Structuring (smurfing) — multiple transactions just below CTR threshold
2. Rapid layering — funds moving quickly through an account
3. Large single transaction — meets or exceeds CTR threshold

Regulatory context (Nigeria):
  - NFIU requires Currency Transaction Reports (CTR) for transactions
    >= ₦5,000,000 under Money Laundering (Prohibition) Act 2022
  - Suspicious Activity Reports (SAR) must be filed within 24 hours
    of detecting structuring or layering
"""
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.config import AML_CTR_THRESHOLD

_lock    = threading.Lock()
_history: dict[str, list] = defaultdict(list)

STRUCTURING_WINDOW_HOURS = 24
STRUCTURING_MIN_TXNS     = 3
STRUCTURING_THRESHOLD    = AML_CTR_THRESHOLD * 0.9   # 90% of CTR = ₦4.5M
LAYERING_WINDOW_HOURS    = 1
LAYERING_MIN_TXNS        = 5


def record_for_aml(customer_id: str, amount: float, tx_type: str) -> None:
    with _lock:
        now = datetime.now(timezone.utc)
        _history[customer_id].append({
            "timestamp": now,
            "amount":    amount,
            "type":      tx_type,
        })
        # Keep 30 days for AML (longer horizon than fraud velocity)
        cutoff = now - timedelta(days=30)
        _history[customer_id] = [
            h for h in _history[customer_id]
            if h["timestamp"] > cutoff
        ]


def detect(customer_id: str, amount: float, tx_type: str) -> dict:
    """
    Run all AML checks for a transaction.

    Returns:
        aml_flags:     list of triggered typologies
        requires_sar:  bool — SAR must be filed with NFIU within 24h
        requires_ctr:  bool — CTR mandatory for this transaction amount
        aml_score:     0–100 risk contribution from AML signals
        aml_note:      plain text summary for compliance
    """
    with _lock:
        history = _history.get(customer_id, [])
        now     = datetime.now(timezone.utc)

    flags = []

    # ── Check 1: CTR threshold ─────────────────────────────────────
    requires_ctr = amount >= AML_CTR_THRESHOLD
    if requires_ctr:
        flags.append({
            "typology":    "CTR_THRESHOLD",
            "description": (
                f"Transaction of ₦{amount:,.0f} meets the "
                f"₦{AML_CTR_THRESHOLD:,.0f} CTR reporting threshold. "
                f"Automatic NFIU report required."
            ),
        })

    # ── Check 2: Structuring ───────────────────────────────────────
    cutoff_24h = now - timedelta(hours=STRUCTURING_WINDOW_HOURS)
    recent_large = [
        h for h in history
        if h["timestamp"] > cutoff_24h
        and h["amount"] >= STRUCTURING_THRESHOLD
    ]
    if len(recent_large) >= STRUCTURING_MIN_TXNS:
        total = sum(h["amount"] for h in recent_large)
        flags.append({
            "typology":    "STRUCTURING",
            "description": (
                f"{len(recent_large)} transactions of "
                f"₦{STRUCTURING_THRESHOLD:,.0f}+ in 24 hours "
                f"(total ₦{total:,.0f}). "
                f"Pattern consistent with structuring to avoid CTR."
            ),
        })

    # ── Check 3: Rapid layering ────────────────────────────────────
    cutoff_1h = now - timedelta(hours=LAYERING_WINDOW_HOURS)
    recent_outbound = [
        h for h in history
        if h["timestamp"] > cutoff_1h
        and h["type"] in ("TRANSFER", "CASH_OUT")
    ]
    if len(recent_outbound) >= LAYERING_MIN_TXNS:
        flags.append({
            "typology":    "RAPID_LAYERING",
            "description": (
                f"{len(recent_outbound)} outbound transfers in 1 hour. "
                f"Rapid fund movement consistent with layering."
            ),
        })

    requires_sar = any(
        f["typology"] in ("STRUCTURING", "RAPID_LAYERING") for f in flags
    )

    aml_score = 0
    for flag in flags:
        if flag["typology"] == "CTR_THRESHOLD":
            aml_score += 20
        elif flag["typology"] == "STRUCTURING":
            aml_score += 40
        elif flag["typology"] == "RAPID_LAYERING":
            aml_score += 30

    if flags:
        note = "AML flags detected:\n" + "\n".join(
            f"• {f['description']}" for f in flags
        )
        if requires_sar:
            note += "\n\nSAR REQUIRED: File with NFIU within 24 hours."
        if requires_ctr:
            note += "\n\nCTR REQUIRED: Automatic NFIU report."
    else:
        note = "No AML patterns detected."

    return {
        "aml_flags":    flags,
        "aml_flag_count": len(flags),
        "requires_sar": requires_sar,
        "requires_ctr": requires_ctr,
        "aml_score":    min(aml_score, 100),
        "aml_note":     note,
    }