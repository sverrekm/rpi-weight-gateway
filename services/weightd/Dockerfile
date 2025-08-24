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
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY services/weightd/app /app/app

# Copy built web UI to static
COPY --from=webui /app/dist /app/app/static

# Create data dir
VOLUME ["/data"]
ENV DATA_DIR=/data

EXPOSE 8080
CMD ["python", "-m", "app.main"]
