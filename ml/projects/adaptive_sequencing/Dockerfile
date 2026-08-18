# Adaptive sequencing model server — exposes /predict and /health
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY ml/pyproject.toml ml/README.md /app/ml/
COPY ml/src /app/ml/src
RUN pip install --no-cache-dir /app/ml fastapi "uvicorn[standard]"

ARG MODEL_ARTIFACT_DIR=/models/adaptive_sequencing
ENV MODEL_KIND=adaptive_sequencing \
    MODEL_ARTIFACT_DIR=${MODEL_ARTIFACT_DIR} \
    PORT=8080

COPY artifacts/adaptive_sequencing ${MODEL_ARTIFACT_DIR}

EXPOSE 8080
CMD ["sh", "-c", "uvicorn asiwdp_ml.serving.main:app --host 0.0.0.0 --port ${PORT}"]
