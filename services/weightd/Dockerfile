# --- Stage 1: runtime (Raspberry Pi arm64 kernel / Python 3.9 Bookworm) ---
FROM python:3.9-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_NO_BUILD_ISOLATION=1 \
    DATA_DIR=/data

# Create app dir
WORKDIR /app

## Install build dependencies (prefer gz indices for robustness)
RUN echo 'Acquire::CompressionTypes::Order:: "gz";' > /etc/apt/apt.conf.d/99force-gz \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential python3-dev git libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy backend
COPY services/weightd/requirements.txt /app/requirements.txt
## Upgrade pip tooling separately for clearer logs, then install deps preferring wheels
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip debug --verbose \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy pre-built static files from webui into the Python package directory
# main.py expects STATIC_DIR relative to the "app" package directory
COPY services/webui/dist /app/app/static

COPY services/weightd /app

# Create data dir
VOLUME ["/data"]

EXPOSE 8000
# Ensure Python sees /app on sys.path and run uvicorn with verbose logging
ENV PYTHONPATH=/app
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug"]
