# app/core/velocity_engine.py
"""
Real-time velocity feature engine.

Tracks per-customer transaction history in memory.
Answers: "Is this transaction unusual for THIS customer?"

This is the key improvement over a raw feature-only model.
Without velocity, ₦750,000 TRANSFER looks suspicious for everyone.
With velocity, ₦750,000 is normal for a business owner who
sends ₦800,000 weekly, but suspicious for someone whose
max historical transaction was ₦50,000.

In production: Redis with TTL expiry replaces this in-memory store.
For this project: thread-safe in-memory dict with pruning.
"""
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone

_lock = threading.Lock()
_history: dict[str, list] = defaultdict(list)

WINDOWS = {
    "10min": timedelta(minutes=10),
    "1hour": timedelta(hours=1),
    "24hour": timedelta(hours=24),
}


def record_transaction(customer_id: str, amount: float) -> None:
    """Record a transaction. Called before scoring for future context."""
    with _lock:
        now = datetime.now(timezone.utc)
        _history[customer_id].append((now, amount))

        # Prune entries older than 24h to control memory
        cutoff = now - WINDOWS["24hour"]
        _history[customer_id] = [
            (ts, amt) for ts, amt in _history[customer_id]
            if ts > cutoff
        ]


def get_velocity_features(customer_id: str, current_amount: float) -> dict:
    """
    Compute velocity features for a customer.

    Returns features capturing:
    - Transaction frequency in each time window
    - Amount totals in each time window
    - Current amount vs customer's historical average
    """
    with _lock:
        now     = datetime.now(timezone.utc)
        history = _history.get(customer_id, [])

        counts = {}
        totals = {}
        for window_name, delta in WINDOWS.items():
            cutoff   = now - delta
            window   = [(ts, amt) for ts, amt in history if ts > cutoff]
            counts[window_name] = len(window)
            totals[window_name] = sum(amt for _, amt in window)

        # 24h baseline for amount anomaly
        all_amounts = [amt for _, amt in history]
        avg_24h = sum(all_amounts) / len(all_amounts) if all_amounts else current_amount
        amount_vs_avg = current_amount / (avg_24h + 1)

        return {
            "txn_count_10min":   counts["10min"],
            "txn_count_1hour":   counts["1hour"],
            "txn_count_24hour":  counts["24hour"],
            "txn_total_1hour":   totals["1hour"],
            "txn_total_24hour":  totals["24hour"],
            "amount_vs_24h_avg": round(amount_vs_avg, 4),
        }