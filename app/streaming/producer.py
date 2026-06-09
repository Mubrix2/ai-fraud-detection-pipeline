# app/streaming/producer.py
"""
Kafka producer for publishing transactions to the streaming pipeline.

Single producer instance initialised at startup and reused.
Creating a new producer per request would be wasteful (~50ms overhead).

acks='all': broker confirms write to all in-sync replicas before
acknowledging. Guarantees no message is lost even if the leader
broker crashes immediately after acknowledgment.

linger.ms=5: wait 5ms to batch multiple messages together.
Improves throughput under load at the cost of 5ms added latency.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from confluent_kafka import KafkaException, Producer

from app.config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TRANSACTIONS_TOPIC

logger = logging.getLogger(__name__)

_producer: Optional[Producer] = None


def initialise_producer() -> bool:
    global _producer
    try:
        _producer = Producer({
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "acks":              "all",
            "retries":           5,
            "linger.ms":         5,
        })
        logger.info(
            f"Kafka producer ready | broker={KAFKA_BOOTSTRAP_SERVERS}"
        )
        return True
    except KafkaException as e:
        logger.error(f"Kafka producer failed: {e}")
        return False


def _on_delivery(err, msg):
    if err:
        logger.error(f"Delivery failed: {err}")
    else:
        logger.debug(
            f"Delivered → {msg.topic()} "
            f"[{msg.partition()}] offset={msg.offset()}"
        )


def publish_transaction(transaction: dict) -> bool:
    """Publish a transaction dict to raw-transactions topic."""
    if _producer is None:
        logger.warning("Producer not initialised — skipping publish")
        return False

    message = {
        "data": transaction,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        _producer.produce(
            topic    = KAFKA_TRANSACTIONS_TOPIC,
            key      = str(transaction.get("transaction_id", "")).encode(),
            value    = json.dumps(message).encode("utf-8"),
            callback = _on_delivery,
        )
        _producer.poll(0)
        return True
    except (KafkaException, BufferError) as e:
        logger.error(f"Publish failed: {e}")
        return False


def shutdown_producer() -> None:
    global _producer
    if _producer:
        logger.info("Flushing producer...")
        _producer.flush(timeout=10)
        _producer = None