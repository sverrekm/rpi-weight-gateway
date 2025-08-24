# --- Stage 1: build web UI ---
FROM --platform=$BUILDPLATFORM node:20-alpine AS webui
WORKDIR /app
COPY services/webui/package.json ./
RUN npm install
COPY services/webui ./
RUN npm run build

# --- Stage 2: python runtime ---
FROM --platform=$TARGETPLATFORM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create app dir
WORKDIR /app

# Copy backend
COPY services/weightd/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --no-deps fastapi==0.104.1 && \
    pip install --no-cache-dir --no-deps uvicorn==0.24.0 && \
    pip install --no-cache-dir --no-deps pydantic==2.5.0 && \
    pip install --no-cache-dir --no-deps paho-mqtt==1.6.1 && \
    pip install --no-cache-dir --no-deps python-multipart==0.0.6 && \
    pip install --no-cache-dir --no-deps orjson==3.9.10 || pip install --no-cache-dir --no-deps --no-binary=orjson orjson==3.9.10 && \
    pip install --no-cache-dir --no-deps RPi.GPIO==0.7.1 || echo "RPi.GPIO install failed - will use mock in container"
COPY services/weightd/app /app/app

# Copy built web UI to static
COPY --from=webui /app/dist /app/app/static

# Create data dir
VOLUME ["/data"]
ENV DATA_DIR=/data

EXPOSE 8080
CMD ["python", "-m", "app.main"]
