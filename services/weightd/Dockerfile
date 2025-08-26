# --- Stage 1: python runtime (Variant B: ARMv7 / Python 3.9 Bullseye) ---
FROM python:3.9-bullseye
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_NO_BUILD_ISOLATION=1 \
    DATA_DIR=/data

# Create app dir
WORKDIR /app

## Install build dependencies to allow source builds when ARM wheels are missing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential python3-dev git libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy backend
COPY services/weightd/requirements.txt /app/requirements.txt
## Upgrade pip tooling separately for clearer logs, then install deps preferring wheels
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip debug --verbose \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy pre-built static files from webui
COPY services/webui/dist /app/static

COPY services/weightd /app

# Create data dir
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
