# Recommendation model server — exposes /predict and /health
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY ml/pyproject.toml ml/README.md /app/ml/
COPY ml/src /app/ml/src
RUN pip install --no-cache-dir /app/ml fastapi "uvicorn[standard]"

# Artifacts are baked in at image build time or mounted at runtime.
ARG MODEL_ARTIFACT_DIR=/models/recommendation
ENV MODEL_KIND=recommendation \
    MODEL_ARTIFACT_DIR=${MODEL_ARTIFACT_DIR} \
    PORT=8080

COPY artifacts/recommendation ${MODEL_ARTIFACT_DIR}

EXPOSE 8080
CMD ["sh", "-c", "uvicorn asiwdp_ml.serving.main:app --host 0.0.0.0 --port ${PORT}"]
