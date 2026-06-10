# Dockerfile
# Builds the FastAPI fraud detection service.
# The Kafka consumer runs as a daemon thread inside this container.
# No separate consumer container needed.
#
# Build prerequisite: trained models must exist in app/models/
# Run before building:
#   python scripts/prepare_data.py
#   python scripts/train_fraud_model.py
#   python scripts/train_anomaly_model.py

# Dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Verify models — heredoc syntax keeps Python readable without parse errors
# docker-compose.yml context path ensures app/models/ is included
RUN python3 - <<'PYEOF'
import sys
from pathlib import Path

required = [
    "app/models/fraud_model.pkl",
    "app/models/anomaly_model.pkl",
    "app/models/scaler.pkl",
]
missing = [m for m in required if not Path(m).exists()]
if missing:
    print("ERROR: Missing model files:")
    for m in missing:
        print(f"  {m}")
    print("\nRun these before building:")
    print("  python scripts/prepare_data.py")
    print("  python scripts/train_fraud_model.py")
    print("  python scripts/train_anomaly_model.py")
    sys.exit(1)
print(f"All {len(required)} model files verified.")
PYEOF

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]