# app/streaming/consumer.py
"""
Kafka consumer running as a daemon thread inside FastAPI.

Architecture:
  FastAPI process
  ├── Main thread:       uvicorn HTTP server
  └── Daemon thread:     Kafka consumer loop  ← this file

The consumer thread starts in main.py lifespan and runs for
the entire lifetime of the process. It shares memory with the
main thread — specifically _results_store — protected by a lock.

Why daemon=True:
  A daemon thread is killed automatically when the main process exits.
  Without daemon=True, Python would wait for the consumer loop to
  finish naturally — which never happens. The process would hang.

Consumer group semantics:
  All replicas of this service share KAFKA_CONSUMER_GROUP.
  Kafka assigns each partition to exactly one consumer in the group.
  With 3 partitions and 1 replica: this consumer handles all 3.
  With 3 partitions and 3 replicas: each handles 1 partition.
  Scaling horizontally requires no code changes.
"""
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from confluent_kafka import Consumer, KafkaError, Producer

from app.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CONSUMER_GROUP,
    KAFKA_RESULTS_TOPIC,
    KAFKA_TRANSACTIONS_TOPIC,
)

logger = logging.getLogger(__name__)

# ── Thread-safe results store ──────────────────────────────────────────────────
_results_store: dict[str, dict] = {}
_results_lock  = threading.Lock()

# ── Runtime stats ──────────────────────────────────────────────────────────────
_stats = {
    "consumed":  0,
    "flagged":   0,
    "failed":    0,
    "started_at": None,
}

# ── Thread control ─────────────────────────────────────────────────────────────
_stop_event:    threading.Event          = threading.Event()
_consumer_thread: Optional[threading.Thread] = None


# ── Store operations ───────────────────────────────────────────────────────────

def store_result(transaction_id: str, assessment: dict) -> None:
    with _results_lock:
        _results_store[transaction_id] = assessment
        # Cap at 1000 entries — oldest evicted first
        if len(_results_store) > 1000:
            oldest = next(iter(_results_store))
            del _results_store[oldest]


def get_result(transaction_id: str) -> Optional[dict]:
    with _results_lock:
        return _results_store.get(transaction_id)


def get_all_results() -> list[dict]:
    with _results_lock:
        return sorted(
            _results_store.values(),
            key=lambda x: x.get("scored_at", ""),
            reverse=True,
        )


def get_consumer_stats() -> dict:
    return {
        **_stats,
        "results_in_store": len(_results_store),
        "consumer_running": (
            _consumer_thread is not None
            and _consumer_thread.is_alive()
        ),
    }


# ── Internal pipeline ──────────────────────────────────────────────────────────

def _create_results_producer() -> Producer:
    return Producer({
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "acks": "1",
    })


def _process_message(msg, results_producer: Producer) -> None:
    """Process one Kafka message through the full detection pipeline."""
    try:
        raw  = json.loads(msg.value().decode("utf-8"))
        data = raw.get("data", raw)

        transaction_id = str(
            data.get("transaction_id") or
            (msg.key().decode("utf-8") if msg.key() else "unknown")
        )

        from app.services.detection_service import assess_transaction
        assessment = assess_transaction(
            transaction_id   = transaction_id,
            transaction_data = data,
        )

        store_result(transaction_id, assessment)

        # Publish scored result for downstream consumers
        results_producer.produce(
            topic = KAFKA_RESULTS_TOPIC,
            key   = transaction_id.encode("utf-8"),
            value = json.dumps(assessment, default=str).encode("utf-8"),
        )
        results_producer.poll(0)

        _stats["consumed"] += 1
        if assessment.get("is_flagged"):
            _stats["flagged"] += 1

    except json.JSONDecodeError as e:
        logger.error(f"Bad JSON in message: {e}")
        _stats["failed"] += 1
    except Exception as e:
        logger.error(f"Message processing error: {e}", exc_info=True)
        _stats["failed"] += 1


def _run_consumer() -> None:
    """
    Main consumer loop. Runs until _stop_event is set.
    Called from the background thread — never from the main thread.
    """
    logger.info(
        f"Consumer starting | "
        f"broker={KAFKA_BOOTSTRAP_SERVERS} | "
        f"topic={KAFKA_TRANSACTIONS_TOPIC} | "
        f"group={KAFKA_CONSUMER_GROUP}"
    )

    consumer = Consumer({
        "bootstrap.servers":     KAFKA_BOOTSTRAP_SERVERS,
        "group.id":              KAFKA_CONSUMER_GROUP,
        "auto.offset.reset":     "earliest",
        "enable.auto.commit":    True,
        "auto.commit.interval.ms": 5000,
        "session.timeout.ms":    30000,
    })

    results_producer = _create_results_producer()

    try:
        consumer.subscribe([KAFKA_TRANSACTIONS_TOPIC])
        _stats["started_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("✅ Consumer subscribed — polling for messages")

        while not _stop_event.is_set():
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    logger.error(f"Consumer error: {msg.error()}")
                continue

            _process_message(msg, results_producer)

    except Exception as e:
        logger.error(f"Consumer loop error: {e}", exc_info=True)
    finally:
        consumer.close()
        results_producer.flush(timeout=5)
        logger.info("Consumer shut down cleanly")


# ── Thread lifecycle ───────────────────────────────────────────────────────────

def start_consumer() -> bool:
    """Start the consumer as a background daemon thread."""
    global _consumer_thread

    _stop_event.clear()
    _consumer_thread = threading.Thread(
        target = _run_consumer,
        name   = "kafka-consumer",
        daemon = True,
    )
    _consumer_thread.start()

    import time
    time.sleep(0.5)

    if _consumer_thread.is_alive():
        logger.info("✅ Consumer thread running")
        return True

    logger.error("❌ Consumer thread failed to start")
    return False


def stop_consumer() -> None:
    """Signal the consumer to stop and wait for clean shutdown."""
    global _consumer_thread
    _stop_event.set()
    if _consumer_thread and _consumer_thread.is_alive():
        _consumer_thread.join(timeout=10)
    _consumer_thread = None
    logger.info("Consumer thread stopped")