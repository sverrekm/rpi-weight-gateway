# --- Stage 1: runtime (RPi3 ARMv7 / Balena Debian Bookworm + Python 3) ---
FROM balenalib/raspberrypi3-debian:bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_NO_BUILD_ISOLATION=1 \
    DATA_DIR=/data

# Create app dir
WORKDIR /app

## Install Python and build dependencies using balena install helper (more robust on RPi3)
RUN install_packages \
      python3 python3-pip python3-dev \
      build-essential git libffi-dev libssl-dev

# Copy backend
COPY services/weightd/requirements.txt /app/requirements.txt
## Upgrade pip tooling separately for clearer logs, then install deps preferring wheels
RUN python3 -m pip install --upgrade pip setuptools wheel \
    && pip debug --verbose \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy pre-built static files from webui
COPY services/webui/dist /app/static

COPY services/weightd /app

# Create data dir
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
