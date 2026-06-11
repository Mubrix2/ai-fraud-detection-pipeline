# Real-Time Fraud Detection & Risk Management Pipeline

A production-grade, event-driven fraud detection system for financial
transactions. Every transaction flows through a Kafka streaming pipeline,
two independent ML models, AML pattern detection, a configurable rules
engine, and SHAP explainability — producing a compliance-ready decision
in under 500 milliseconds.

**Live Demo:** [ai-fraud-detection-pipeline.vercel.app](https://ai-fraud-detection-pipeline.vercel.app)  
**API Docs:**  [ai-fraud-detection-pipeline.onrender.com/docs](https://ai-fraud-detection-pipeline.onrender.com/docs)

---

## Demo

![Demo](demo.gif)

---

## The Pipeline

```
Transaction submitted via REST API
          │
          ▼
Kafka Stream ─── raw-transactions topic (3 partitions)
          │
          ▼
Feature Engineering ─── 14 features from transaction fields
          │
          ├── Velocity Engine (per-customer sliding window behavioural context)
          │
          ▼
Dual ML Scoring
    XGBoost Classifier      → fraud probability 0–1  (supervised)
    Isolation Forest        → anomaly score           (unsupervised)
          │
          ▼
AML Detection
    Structuring / Smurfing  → CTR/SAR generation
    Rapid Layering          → NFIU reporting flag
          │
          ▼
Rules Engine ─── configurable business rules overlay
          │
          ├── Circuit Breaker → Rule Fallback (if ML unavailable)
          │
          ▼
3-Tier Decision
    APPROVE  (fraud_prob < 0.60)
    REVIEW   (fraud_prob ≥ 0.60  OR  AML flag  OR  rules escalate)
    BLOCK    (fraud_prob ≥ 0.85)
          │
          ▼
SHAP Explanation ─── exact TreeExplainer attributions (compliance)
          │
          ▼
Immutable Audit Log ─── SQLite append-only
          │
          ▼
React Dashboard + AI Investigation Agent (LangGraph)
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  FastAPI Service  (single process)                            │
│                                                               │
│  Main Thread (uvicorn)          Consumer Thread (daemon)      │
│  ┌────────────────────┐        ┌─────────────────────────┐   │
│  │ POST /submit        │        │ polls Kafka every 1s    │   │
│  │   → assess_txn()   │        │ → assess_txn()          │   │
│  │   → store result   │        │ → store result          │   │
│  │   → publish Kafka  │        │ → publish fraud-results │   │
│  │ GET  /recent        │        └─────────────────────────┘   │
│  │ GET  /stats         │                                       │
│  │ POST /investigate   │   shared: _results_store (locked)    │
│  └────────────────────┘                                       │
└──────────────────────────────┬───────────────────────────────┘
                               │
                    Apache Kafka (KRaft)
                    ├── raw-transactions  (3 partitions)
                    └── fraud-results     (3 partitions)
```

The consumer thread and HTTP endpoints share `_results_store` — a
thread-safe in-memory dict protected by a lock. The HTTP `/submit`
endpoint scores synchronously so results are immediately available.
The consumer thread provides the Kafka streaming architecture.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Streaming | Apache Kafka 4.x (KRaft) | Durable, replayable, horizontally scalable |
| ML — Supervised | XGBoost | Best-in-class for tabular fraud data |
| ML — Unsupervised | Isolation Forest | Novel pattern detection without labels |
| Explainability | SHAP TreeExplainer | Exact attributions — regulatory requirement |
| Feature Context | Velocity Engine | Per-customer behavioural baseline |
| AML | Custom rule engine | Structuring, layering, NFIU CTR/SAR |
| Rules Engine | Python rules | Business policy overlay on ML output |
| Resilience | Circuit Breaker | Rule fallback if ML unavailable |
| Audit | SQLite append-only | Immutable compliance trail |
| Backend | FastAPI + Pydantic v2 | Fast, validated, async |
| Frontend | React + Vite + Recharts | Live investigation dashboard |
| AI Agent | LangGraph + Groq | Conversational fraud investigation |
| Containers | Docker + Docker Compose | Full system orchestration |

---

## Decision Logic

```python
# Clean, auditable, standard
if fraud_prob >= 0.85:
    decision = "BLOCK"
elif fraud_prob >= 0.60:
    decision = "REVIEW"
else:
    decision = "APPROVE"

# Rules and AML can escalate APPROVE → REVIEW
# Anomaly can escalate APPROVE → REVIEW
# Nothing can de-escalate (only increases risk)
```

---

## Model Performance

Evaluated on 554,082 held-out transactions (real-world 0.297% fraud rate):

| Metric | XGBoost | Isolation Forest |
|---|---|---|
| Fraud Recall | 98.7% | 71.4% |
| Fraud Precision | 63.5% | 8.3% |
| F1 Score | 0.773 | — |
| ROC-AUC | 0.998 | — |

**Combined strategy (REVIEW/BLOCK if either flags): 98.9% recall.**

Dataset: PaySim (synthetic mobile money, 6.3M transactions).  
Note: Isolation Forest precision is low by design — it flags unusual
transactions regardless of whether that pattern is labelled fraud.
Its value is catching novel patterns XGBoost has never trained on.

---

## Running Locally

### Prerequisites

- Python 3.12.3
- Node.js 20+
- Java 17+ (for Kafka)
- Kafka 4.x installed in WSL2 or Linux

### Quick Start — Docker Compose (recommended)

```bash
# 1. Train models first (one-time, ~10 minutes)
python scripts/prepare_data.py
python scripts/train_fraud_model.py
python scripts/train_anomaly_model.py

# 2. Start all services
docker compose up --build
```

| Service | URL |
|---|---|
| API + Docs | http://localhost:8000/docs |
| Dashboard | http://localhost:80 |
| Kafka | localhost:9092 (internal) / 29092 (host) |

### Manual Start — Three Terminals

```bash
# Terminal 1 — Kafka
kafka-server-start.sh ~/kafka/config/kraft/server.properties

# Terminal 2 — API (consumer thread starts automatically)
source venv-linux/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3 — React dashboard
cd frontend && npm run dev
# Dashboard: http://localhost:5173
```

### Generate Demo Traffic

```bash
# 10 transactions/second for 60 seconds (2% fraud injection)
python scripts/simulate_traffic.py --rate 10 --duration 60

# Continuous stream
python scripts/simulate_traffic.py --rate 5 --duration 0
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/transactions/submit` | Submit transaction for screening |
| `GET` | `/api/v1/transactions/results/{id}` | Get result for a transaction |
| `GET` | `/api/v1/transactions/recent` | Recent transactions for dashboard |
| `GET` | `/api/v1/transactions/stats` | System statistics |
| `POST` | `/api/v1/transactions/investigate` | AI investigation agent |
| `GET` | `/health` | Service health check |

**Submit a suspicious transaction:**
```bash
curl -X POST http://localhost:8000/api/v1/transactions/submit \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "TXN-001",
    "step": 3, "type": "TRANSFER", "amount": 750000,
    "name_orig": "C1234567890",
    "oldbalance_org": 750000, "newbalance_orig": 0,
    "name_dest": "C9876543210",
    "oldbalance_dest": 0, "newbalance_dest": 0
  }'
```

**Ask the investigation agent:**
```bash
curl -X POST http://localhost:8000/api/v1/transactions/investigate \
  -H "Content-Type: application/json" \
  -d '{"question": "Why was TXN-001 flagged?"}'
```

---

## Project Structure

```
realtime-fraud-detection-pipeline/
├── app/
│   ├── main.py                   # FastAPI + consumer daemon thread
│   ├── config.py                 # All configuration from env vars
│   ├── api/
│   │   ├── schemas.py            # Pydantic v2 models (extra=forbid)
│   │   └── routes/
│   │       ├── transactions.py   # Core fraud detection endpoints
│   │       └── health.py
│   ├── core/
│   │   ├── feature_engineer.py   # 14 engineered features
│   │   ├── fraud_scorer.py       # XGBoost inference + 3-tier decision
│   │   ├── anomaly_detector.py   # Isolation Forest inference
│   │   ├── explainer.py          # SHAP TreeExplainer
│   │   ├── velocity_engine.py    # Per-customer sliding window features
│   │   ├── aml_detector.py       # Structuring/layering + SAR/CTR
│   │   ├── rules_engine.py       # Configurable business rules
│   │   ├── circuit_breaker.py    # ML fallback resilience
│   │   ├── audit_logger.py       # Immutable SQLite audit trail
│   │   └── investigation_agent.py # LangGraph analyst agent
│   ├── services/
│   │   └── detection_service.py  # 9-step pipeline orchestration
│   └── streaming/
│       ├── producer.py           # Kafka producer
│       └── consumer.py           # Daemon thread consumer
├── scripts/
│   ├── prepare_data.py           # SMOTE, scaling, train/test split
│   ├── train_fraud_model.py      # XGBoost training + threshold search
│   ├── train_anomaly_model.py    # Isolation Forest training
│   ├── evaluate_models.py        # Combined model evaluation
│   ├── simulate_traffic.py       # Demo traffic generator
│   └── test_kafka_connection.py  # Kafka health check
├── tests/                        # Unit tests for every module
├── notebooks/
│   └── 01_data_exploration.ipynb # 7-cell analysis driving design
├── frontend/                     # React investigation dashboard
├── Dockerfile                    # API image
├── Dockerfile.frontend           # React multi-stage image
├── docker-compose.yml            # Full system orchestration
└── nginx.conf                    # SPA routing config
```

---

## Deployment

```
Render (API)          Vercel (Frontend)
     ↓                      ↓
FastAPI + consumer    React dashboard
synchronous scoring   polls Render API
     ↑
No Kafka in cloud — synchronous scoring path handles all functionality.
Kafka streaming architecture demonstrated via Docker Compose locally.
```

| Service | Platform | Cost |
|---|---|---|
| API | Render Web Service (free) | $0 |
| Frontend | Vercel (free) | $0 |

---

## AML Compliance

The pipeline detects three Anti-Money Laundering typologies:

**Structuring (Smurfing):** Multiple transactions of ₦4,500,000+
within 24 hours — structured to avoid the ₦5,000,000 CTR threshold.

**Rapid Layering:** 5+ outbound transfers within 1 hour — funds
moving quickly through an account to obscure origin.

**CTR Threshold:** Single transaction at or above ₦5,000,000 —
automatic Currency Transaction Report required under Nigeria's
Money Laundering (Prohibition) Act 2022.

Suspicious Activity Reports (SAR) are generated for structuring
and layering, with NFIU filing obligation flagged within 24 hours.

---

## Engineering Decisions

**Why consumer as a thread?**  
Keeps deployment simple — one process, one container. The same
architecture separation (producer/consumer) is demonstrated without
the operational complexity of a second service.

**Why 3-tier (APPROVE/REVIEW/BLOCK) not 4-tier?**  
Maps directly to how fraud operations teams work. REVIEW routes to
the analyst queue. BLOCK declines the transaction. Simple, auditable,
standard across production fintechs.

**Why SMOTE only on training data?**  
The test set retains the real fraud rate (0.297%) to give honest
evaluation metrics. Applying SMOTE to test data inflates recall
artificially — you'd be testing on synthetic easy examples.

**Why PaySim?**  
Only freely available, appropriately licensed mobile-money fraud
dataset. The IEEE-CIS Kaggle dataset is closer to production data
(real features: device fingerprints, email domains) and would be
the next step for a more realistic model.

---

## Scaling Roadmap

This system is built to handle a portfolio demo and early-stage
production traffic (hundreds to low thousands of transactions per day).
Below is what changes — and why — as transaction volume grows.

### Current Capacity (as built)

| Component | Current Limit | Bottleneck |
|---|---|---|
| API | ~50-100 req/s | Single process, single core |
| Consumer | 1 thread, 3 partitions | Only 1 of 3 partitions used |
| Results store | 1,000 entries, in-memory | Lost on restart, not shared |
| Velocity/AML history | In-memory dict | Lost on restart, single process |
| Audit log | SQLite | File-level locking |
| Kafka | Single broker | No replication, single point of failure |

---

### Stage 1: 1,000 → 50,000 transactions/day

**Add Redis for shared state**
Replace in-memory `_results_store`, velocity history, and AML history
with Redis. This allows multiple API instances to share state and
survive restarts without losing customer behavioural history.

**Add rate limiting at the gateway**
nginx `limit_req_zone` prevents a single client from overwhelming
the API — protects against both abuse and runaway integration bugs.

**Horizontal scale the API**
Run 2-3 API instances behind a load balancer. Each instance reads/writes
shared Redis state. Render/Railway support this with a "scale" setting —
no code changes if Redis is in place.

---

### Stage 2: 50,000 → 1,000,000 transactions/day

**Separate the consumer into its own service**
Run 3 consumer instances — one per Kafka partition — as independent
deployments. Each consumes one partition exclusively (Kafka guarantees
this within a consumer group).

**Move audit log to PostgreSQL**
SQLite's file locking becomes a bottleneck above ~1,000 writes/second.
PostgreSQL with connection pooling (PgBouncer) handles this comfortably.

**Add a feature store**
Velocity and AML history move from Redis dicts to a proper feature
store (Feast, or Redis with structured TTL keys) — enables feature
reuse across fraud, AML, and future credit risk models.

**Multi-broker Kafka (3 brokers, replication factor 3)**
Single broker = single point of failure. 3 brokers with RF=3 means
the system survives any single broker going down with zero data loss.

---

### Stage 3: 1,000,000+ transactions/day

**Dead Letter Queue (DLQ)**
Messages that fail processing 3 times go to `fraud-dlq` instead of
being dropped or retried forever. A separate process reviews DLQ
messages — usually malformed payloads or model timeout edge cases.

**Idempotency layer**
At this volume, network retries WILL cause duplicate submissions.
Redis-based idempotency keys (hash of transaction_id) prevent
double-scoring the same transaction.

**Observability stack**
Prometheus + Grafana for metrics (request rate, latency percentiles,
model inference time, Kafka consumer lag). Without this, you are
blind to degradation until customers complain.

**Model serving separation**
ML inference moves to a dedicated service (or ONNX Runtime for
sub-10ms inference) so model updates don't require redeploying the
whole API.

---

### What Does NOT Change

The core detection pipeline — feature engineering, the 14 features,
the 9-step assess_transaction() flow, the SHAP explainability, the
AML typologies, the 3-tier decision logic — remains identical at
every scale. Scaling changes *infrastructure*, not *fraud logic*.
This separation (business logic vs infrastructure) is why the
architecture can grow without a rewrite.

---

## Author

**Mubarak Olalekan Oladipo**  
AI Engineer — Fraud Detection & Risk Management  
Ibadan, Nigeria · Open to remote  
[GitHub](https://github.com/Mubrix2) · [LinkedIn](https://www.linkedin.com/in/mubarak-oladipo/) · +234 814 353 0951