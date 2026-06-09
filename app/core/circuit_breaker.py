# app/core/circuit_breaker.py
"""
Circuit breaker for ML model resilience.

States: CLOSED (normal) → OPEN (failed) → HALF_OPEN (testing recovery)

If ML fails 5 times consecutively, the circuit trips.
All scoring routes to a simple rule fallback immediately.
After 30 seconds, the circuit tests recovery automatically.

The customer never sees a service disruption — they receive a
decision from rules rather than from ML, without knowing the difference.
"""
import logging
import time
import threading

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout:  float = 30.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self._failures         = 0
        self._last_failure     = 0.0
        self._open             = False
        self._lock             = threading.Lock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            if self._open:
                if time.time() - self._last_failure > self.recovery_timeout:
                    self._open    = False
                    self._failures = 0
                    logger.info("Circuit breaker: OPEN → CLOSED (recovered)")
            return self._open

    def record_success(self):
        with self._lock:
            self._failures = 0

    def record_failure(self):
        with self._lock:
            self._failures     += 1
            self._last_failure  = time.time()
            if self._failures >= self.failure_threshold:
                if not self._open:
                    logger.warning(
                        f"Circuit breaker OPEN after {self._failures} failures"
                    )
                self._open = True

    def status(self) -> dict:
        return {
            "state":    "OPEN" if self._open else "CLOSED",
            "failures": self._failures,
        }


fraud_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)


def rule_fallback(features: dict, amount: float) -> dict:
    """
    Hardcoded rule-based scoring when ML is unavailable.
    Fast, deterministic, auditable — no ML required.
    """
    score = 0
    rules = []

    if amount >= 1_000_000:
        score += 40
        rules.append("Amount >= ₦1,000,000")
    if features.get("orig_balance_zeroed", 0):
        score += 35
        rules.append("Sender account completely drained")
    if features.get("dest_balance_zero_before", 0):
        score += 25
        rules.append("Recipient had zero balance (mule account pattern)")
    if features.get("amount_ratio_orig", 0) > 0.95:
        score += 20
        rules.append("Amount > 95% of sender balance")

    if score >= 70:
        decision = "BLOCK"
    elif score >= 35:
        decision = "REVIEW"
    else:
        decision = "APPROVE"

    return {
        "fraud_probability": min(score / 100, 0.99),
        "decision":          decision,
        "risk_level":        "FALLBACK",
        "model_available":   False,
        "fallback_rules":    rules,
    }