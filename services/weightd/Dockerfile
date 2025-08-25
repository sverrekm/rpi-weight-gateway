# --- Stage 1: python runtime ---
FROM --platform=linux/arm/v7 python:3.9-buster
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

# Create app dir
WORKDIR /app

# Copy backend
COPY services/weightd/requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade --no-cache-dir pip setuptools wheel \
    && pip install --no-cache-dir --no-compile --prefer-binary -r requirements.txt

# Copy pre-built static files from webui
COPY services/webui/dist /app/static

COPY services/weightd /app

# Create data dir
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
