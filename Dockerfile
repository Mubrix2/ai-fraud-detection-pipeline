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

FROM python:3.12-slim

WORKDIR /app

# Build tools needed for confluent-kafka (librdkafka) and XGBoost (gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python dependencies first — Docker layer caching
# This layer only rebuilds when requirements.txt changes,
# not when source code changes
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/ scripts/check_models.py

# Verify models exist — fail fast at build time, not at runtime
# Gives a clear error message if training was skipped
RUN python scripts/check_models.py


EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]