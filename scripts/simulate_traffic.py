# scripts/simulate_traffic.py
"""
Simulate realistic transaction traffic into Kafka.

Generates a mix of legitimate and fraudulent transactions at a
configurable rate. Fraud is injected at approximately 2% of
TRANSFER/CASH_OUT transactions — higher than real world (0.3%)
to make the dashboard more interesting for demos.

Usage:
    python scripts/simulate_traffic.py                 # 5 tx/s, 60 seconds
    python scripts/simulate_traffic.py --rate 20       # 20 tx/s
    python scripts/simulate_traffic.py --duration 0    # run forever
"""
import argparse
import json
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from confluent_kafka import Producer

BOOTSTRAP = "localhost:9092"
TOPIC     = "raw-transactions"

TYPES    = ["TRANSFER", "CASH_OUT", "PAYMENT", "CASH_IN"]
WEIGHTS  = [0.30,       0.20,       0.40,      0.10]


def fraud_transaction(step: int) -> dict:
    """Classic account drain — high fraud probability."""
    amount = round(random.uniform(200_000, 2_000_000), 2)
    return {
        "transaction_id": f"TXN-F-{uuid.uuid4().hex[:10].upper()}",
        "step":           step,
        "type":           random.choice(["TRANSFER", "CASH_OUT"]),
        "amount":         amount,
        "name_orig":      f"C{random.randint(10**9, 10**10 - 1)}",
        "oldbalance_org": amount,       # exact balance — account drain
        "newbalance_orig": 0.0,         # zeroed
        "name_dest":      f"C{random.randint(10**9, 10**10 - 1)}",
        "oldbalance_dest": 0.0,         # mule account
        "newbalance_dest": 0.0,         # immediately emptied
    }


def legit_transaction(step: int) -> dict:
    """Realistic legitimate transaction."""
    tx_type = random.choices(TYPES, weights=WEIGHTS)[0]
    amount  = round(random.uniform(1_000, 300_000), 2)
    balance = round(random.uniform(amount * 1.5, amount * 20), 2)
    dest_before = round(random.uniform(0, 2_000_000), 2)

    return {
        "transaction_id":  f"TXN-L-{uuid.uuid4().hex[:10].upper()}",
        "step":            step,
        "type":            tx_type,
        "amount":          amount,
        "name_orig":       f"C{random.randint(10**9, 10**10 - 1)}",
        "oldbalance_org":  balance,
        "newbalance_orig": round(balance - amount, 2),
        "name_dest":       f"C{random.randint(10**9, 10**10 - 1)}",
        "oldbalance_dest": dest_before,
        "newbalance_dest": round(dest_before + amount, 2),
    }


def simulate(rate: float, duration: float):
    producer = Producer({"bootstrap.servers": BOOTSTRAP})
    interval = 1.0 / rate
    step     = 1
    sent = fraud_count = 0
    end  = time.time() + duration if duration > 0 else float("inf")

    print(f"Simulating {rate} tx/s | "
          f"Duration: {'∞' if duration == 0 else f'{duration}s'} | "
          f"Ctrl+C to stop\n")

    try:
        while time.time() < end:
            tick = time.time()

            # Inject fraud at ~2% for TRANSFER/CASH_OUT
            is_fraud = (
                random.random() < 0.02 and
                random.random() < 0.5   # only half of random are fraud-type
            )
            tx = fraud_transaction(step) if is_fraud else legit_transaction(step)

            producer.produce(
                TOPIC,
                key   = tx["transaction_id"].encode(),
                value = json.dumps({
                    "data":         tx,
                    "published_at": datetime.now(timezone.utc).isoformat(),
                }).encode("utf-8"),
            )
            producer.poll(0)

            sent += 1
            if is_fraud:
                fraud_count += 1

            if sent % 50 == 0:
                print(
                    f"  Sent: {sent:>6,} | "
                    f"Fraud: {fraud_count:>4} ({fraud_count/sent*100:.1f}%) | "
                    f"Step: {step}"
                )

            step += 1
            elapsed = time.time() - tick
            wait    = interval - elapsed
            if wait > 0:
                time.sleep(wait)

    except KeyboardInterrupt:
        print(f"\nStopped. Sent {sent:,} transactions ({fraud_count} fraud injected)")
    finally:
        producer.flush(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate",     type=float, default=5)
    parser.add_argument("--duration", type=float, default=60)
    args = parser.parse_args()
    simulate(args.rate, args.duration)