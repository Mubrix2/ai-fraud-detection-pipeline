# app/core/destination_velocity.py
"""
Destination-level velocity tracking.

Answers: "Are many different customers sending to the same destination
in a short time window?" — the cross-customer signal that per-customer
velocity engines cannot see.

Per-customer velocity catches this:
  Customer C1111 sends 10 transactions in 10 minutes → HIGH_VELOCITY_10MIN

Destination velocity catches this:
  Customer C1111 → Destination M9876 (looks clean individually)
  Customer C2222 → Destination M9876 (looks clean individually)
  Customer C3333 → Destination M9876 (looks clean individually)
  ...repeated 5,000 times — each sender looks normal, the destination is the signal

This is the card testing / distributed micro-fraud pattern described
in the project's LinkedIn post and scaling roadmap.

Production equivalent: Stripe Radar tracks this across their global
merchant network. This implementation does the same thing scoped
to the transactions processed by this API instance.
"""
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone

_lock        = threading.Lock()
_dest_history: dict[str, list] = defaultdict(list)

WINDOWS = {
    "10min":  timedelta(minutes=10),
    "1hour":  timedelta(hours=1),
    "24hour": timedelta(hours=24),
}


def record_destination(dest_id: str, amount: float, sender_id: str) -> None:
    """
    Record a transaction arriving at dest_id from sender_id.
    Call BEFORE get_destination_features — same convention as velocity_engine.
    """
    with _lock:
        now = datetime.now(timezone.utc)
        _dest_history[dest_id].append({
            "timestamp": now,
            "amount":    amount,
            "sender_id": sender_id,
        })
        # Prune entries older than 24h — keeps memory bounded
        cutoff = now - WINDOWS["24hour"]
        _dest_history[dest_id] = [
            e for e in _dest_history[dest_id] if e["timestamp"] > cutoff
        ]


def get_destination_features(dest_id: str) -> dict:
    """
    Compute cross-customer destination risk features.

    Key signal: high unique_senders + low average_amount = micro-fraud.
    A legitimate recipient sees a stable set of known senders.
    A card-testing aggregation point sees many first-time senders rapidly.
    """
    with _lock:
        now     = datetime.now(timezone.utc)
        history = _dest_history.get(dest_id, [])

        features = {}
        for window_name, delta in WINDOWS.items():
            cutoff  = now - delta
            window  = [e for e in history if e["timestamp"] > cutoff]

            unique_senders = len(set(e["sender_id"] for e in window))
            total_inflow   = sum(e["amount"] for e in window)
            avg_amount     = total_inflow / len(window) if window else 0.0

            features[f"dest_unique_senders_{window_name}"] = unique_senders
            features[f"dest_total_inflow_{window_name}"]   = round(total_inflow, 2)
            features[f"dest_avg_amount_{window_name}"]     = round(avg_amount, 2)

        return features