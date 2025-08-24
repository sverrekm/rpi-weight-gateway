# --- Stage 1: build web UI ---
FROM --platform=$BUILDPLATFORM node:20-alpine AS webui
WORKDIR /app
COPY services/webui/package.json ./
RUN npm install
COPY services/webui ./
RUN npm run build

# --- Stage 2: python runtime ---
FROM --platform=$TARGETPLATFORM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Create app dir
WORKDIR /app

# Copy backend
COPY services/weightd/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY services/weightd/app /app/app

# Copy built web UI to static
COPY --from=webui /app/dist /app/app/static

# Create data dir
VOLUME ["/data"]
ENV DATA_DIR=/data

EXPOSE 8080
CMD ["python", "-m", "app.main"]
