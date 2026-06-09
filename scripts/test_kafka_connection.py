# scripts/test_kafka_connection.py
"""
Kafka connection verification script.

Verifies the full producer → broker → consumer round-trip.
Run this before starting any development session to confirm
Kafka is available and both topics exist.

Usage:
    python scripts/test_kafka_connection.py

Expected output:
    ✅ Producer: delivered to raw-transactions [partition] offset X
    ✅ Consumer: received TEST-CONNECT-001
    ✅ Kafka connection verified
"""
import json
import sys
import time
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from confluent_kafka import Consumer, KafkaError, Producer

BOOTSTRAP_SERVERS = "localhost:9092"
TEST_TOPIC = "raw-transactions"
TEST_TRANSACTION_ID = "TEST-CONNECT-001"


def verify_producer() -> bool:
    """Produce a test message and confirm delivery."""
    producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})

    test_message = {
        "transaction_id": TEST_TRANSACTION_ID,
        "type": "TRANSFER",
        "amount": 100000.0,
        "source": "kafka-connection-test",
    }

    delivery_result = {}

    def on_delivery(err, msg):
        if err:
            delivery_result["error"] = str(err)
            print(f"❌ Producer delivery failed: {err}")
        else:
            delivery_result["success"] = True
            print(
                f"✅ Producer: delivered to {msg.topic()} "
                f"[partition {msg.partition()}] "
                f"offset {msg.offset()}"
            )

    producer.produce(
        TEST_TOPIC,
        key=TEST_TRANSACTION_ID.encode("utf-8"),
        value=json.dumps(test_message).encode("utf-8"),
        callback=on_delivery,
    )
    producer.flush(timeout=10)
    return "success" in delivery_result


def verify_consumer() -> bool:
    """Consume messages and find the test message."""
    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": "kafka-verify-group",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    consumer.subscribe([TEST_TOPIC])

    deadline = time.time() + 10  # 10 second timeout
    found = False

    while time.time() < deadline:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() != KafkaError._PARTITION_EOF:
                print(f"❌ Consumer error: {msg.error()}")
            continue

        try:
            data = json.loads(msg.value().decode("utf-8"))
            if data.get("transaction_id") == TEST_TRANSACTION_ID:
                print(f"✅ Consumer: received {TEST_TRANSACTION_ID}")
                found = True
                break
        except json.JSONDecodeError:
            continue

    consumer.close()

    if not found:
        print(f"❌ Consumer: test message not received within 10 seconds")

    return found


def check_topics() -> bool:
    """Verify both required topics exist."""
    from confluent_kafka.admin import AdminClient

    admin = AdminClient({"bootstrap.servers": BOOTSTRAP_SERVERS})
    metadata = admin.list_topics(timeout=5)
    existing = set(metadata.topics.keys())
    required = {"raw-transactions", "fraud-results"}
    missing = required - existing

    if missing:
        print(f"❌ Missing topics: {missing}")
        print(
            "Create them with:\n"
            "  kafka-topics.sh --create --topic raw-transactions "
            "--bootstrap-server localhost:9092 --partitions 3 "
            "--replication-factor 1"
        )
        return False

    print(f"✅ Topics verified: {required}")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print(" Kafka Connection Verification")
    print("=" * 50)
    print()

    topics_ok = check_topics()
    if not topics_ok:
        sys.exit(1)

    produced = verify_producer()
    consumed = verify_consumer()

    print()
    if produced and consumed:
        print("✅ Kafka connection verified — ready for development")
        sys.exit(0)
    else:
        print("❌ Kafka verification failed")
        print("   Is Kafka running? Start with:")
        print(
            "   kafka-server-start.sh "
            "~/kafka/config/kraft/server.properties"
        )
        sys.exit(1)