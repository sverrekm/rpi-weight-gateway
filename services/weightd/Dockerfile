# Allow overriding base image for architecture compatibility (e.g., arm32v7/ or arm64v8/)
ARG BASE_IMAGE=python:3.9-bookworm
FROM ${BASE_IMAGE}
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
       docker.io curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose \
    && chmod +x /usr/local/bin/docker-compose

# Copy backend
COPY services/weightd/requirements.txt /app/requirements.txt
## Upgrade pip tooling separately for clearer logs, then install deps preferring wheels
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip debug --verbose \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy backend source including static files
COPY services/weightd /app

# Copy project logo into static web root
COPY static/IMG_4293.jpg /app/app/static/logo.jpg
COPY static/IMG_4293.jpg /app/app/static/logo.png

# Create data dir
VOLUME ["/data"]

EXPOSE 8000
# Ensure Python sees /app on sys.path and run uvicorn with verbose logging
ENV PYTHONPATH=/app
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug"]
