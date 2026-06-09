# ai-fraud-detection-pipeline
# Real-Time Fraud Detection & Risk Management Pipeline

A production-grade, event-driven fraud detection and risk management
system for financial transactions. Every transaction is scored by two
independent AI models, checked for money laundering patterns, assigned
a composite risk score, evaluated by a configurable rules engine,
and given an explainable compliance-ready decision — all in real time.

**Live Demo:** [your-dashboard.vercel.app](#)  
**API Docs:**  [your-api.onrender.com/docs](#)

---

## The Pipeline
Transaction submitted
↓
Kafka Stream (event-driven, durable)
↓
Feature Engineering (14 features + velocity behavioural features)
↓
Dual ML Scoring
XGBoost (supervised, 98.7% recall)
Isolation Forest (unsupervised, novel patterns)
↓
AML Detection (structuring, layering, CTR/SAR generation)
↓
Composite Risk Score (0–100)
↓
Rules Engine (configurable business rules)
↓
Circuit Breaker → Rule Fallback (resilience layer)
↓
Tiered Decision: APPROVE / FLAG / CHALLENGE / BLOCK
↓
SHAP Explainability (compliance-ready, exact feature attributions)
↓
Immutable Audit Log
↓
React Investigation Dashboard + AI Agent

## Architecture
┌─────────────────────────────────────────────────────┐
│  FastAPI Service                                      │
│                                                       │
│  Main Thread (uvicorn)                               │
│  ├── POST /api/v1/transactions/submit                │
│  ├── GET  /api/v1/transactions/results/{id}          │
│  ├── GET  /api/v1/transactions/recent                │
│  ├── GET  /api/v1/transactions/stats                 │
│  ├── POST /api/v1/transactions/investigate           │
│  └── GET  /health                                    │
│                                                       │
│  Consumer Thread (daemon)                            │
│  ├── Polls Kafka raw-transactions every 1s           │
│  ├── Runs full ML + AML + risk pipeline              │
│  └── Stores results in thread-safe dict              │
└──────────────────┬──────────────────────────────────┘
│
Apache Kafka (KRaft mode)
├── Topic: raw-transactions (3 partitions)
└── Topic: fraud-results    (3 partitions)

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Streaming | Apache Kafka 3.8.1 (KRaft) | Event-driven transaction pipeline |
| ML — Supervised | XGBoost | Fraud classification |
| ML — Unsupervised | Isolation Forest | Novel anomaly detection |
| Explainability | SHAP TreeExplainer | Compliance-ready explanations |
| Feature Store | In-memory velocity engine | Customer behavioral context |
| AML | Custom rule engine | Structuring, layering, SAR/CTR |
| Risk Score | Composite scorer | 0–100 unified risk metric |
| Rules Engine | Configurable rules | Business override/supplement |
| Backend | FastAPI + Pydantic v2 | High-performance async API |
| Frontend | React + Vite + Recharts | Investigation dashboard |
| Audit | SQLite append-only | Immutable compliance log |
| AI Agent | LangGraph + Groq | Fraud investigation assistant |
| Containers | Docker + Docker Compose | Full system orchestration |
| Deployment | Render + Vercel | Cloud hosting |

## Running Locally

### Prerequisites
- Python 3.12.3
- Node.js 20+
- Java 17+ (for Kafka)
- Kafka 3.8.1 installed in WSL2

### Start Without Docker

```bash
# Terminal 1 — Kafka
kafka-server-start.sh ~/kafka/config/kraft/server.properties

# Terminal 2 — API (consumer thread starts automatically)
source venv-linux/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3 — React
cd frontend && npm run dev
```

### Start With Docker Compose

```bash
docker compose up --build
```

- API + Consumer: http://localhost:8000/docs
- Dashboard:      http://localhost:80

## Model Performance

Evaluated on 554,082 held-out transactions (real-world 0.297% fraud rate):

| Metric | XGBoost | Isolation Forest |
|---|---|---|
| Fraud Recall | 98.7% | 71.4% |
| Fraud Precision | 63.5% | 8.3% |
| F1 Score | 0.773 | 0.153 |
| ROC-AUC | 0.998 | — |

Combined strategy (either model flags): **98.9% recall**.

## Project Structure
realtime-fraud-detection-pipeline/
├── app/
│   ├── main.py                    # FastAPI + consumer thread
│   ├── config.py                  # All env-based configuration
│   ├── api/
│   │   ├── schemas.py             # Pydantic v2 request/response models
│   │   └── routes/
│   │       ├── transactions.py    # Core fraud detection endpoints
│   │       └── health.py          # Health check
│   ├── core/
│   │   ├── feature_engineer.py    # 14 features + velocity
│   │   ├── fraud_scorer.py        # XGBoost inference
│   │   ├── anomaly_detector.py    # Isolation Forest inference
│   │   ├── explainer.py           # SHAP TreeExplainer
│   │   ├── velocity_engine.py     # Sliding window behavioral features
│   │   ├── aml_detector.py        # AML patterns + SAR generation
│   │   ├── risk_scorer.py         # Composite 0–100 risk score
│   │   ├── rules_engine.py        # Configurable business rules
│   │   ├── circuit_breaker.py     # ML fallback resilience
│   │   └── audit_logger.py        # Immutable SQLite audit trail
│   ├── services/
│   │   └── detection_service.py   # Full pipeline orchestration
│   └── streaming/
│       ├── producer.py            # Kafka producer
│       └── consumer.py            # Thread-based Kafka consumer
├── scripts/                       # Training and utility scripts
├── tests/                         # Unit tests for every module
├── notebooks/                     # Data exploration
├── frontend/                      # React investigation dashboard
├── docker-compose.yml
└── Dockerfile

## Author

Mubarak Olalekan Oladipo  
AI Engineer — Fintech & Fraud Detection Specialist  
[GitHub](https://github.com/Mubrix2) · [LinkedIn](#)