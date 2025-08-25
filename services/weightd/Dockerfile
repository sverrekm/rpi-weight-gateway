# --- Stage 1: build web UI ---
FROM --platform=$BUILDPLATFORM node:20-alpine AS webui
WORKDIR /app
COPY services/webui/package.json ./
RUN npm install
COPY services/webui ./
RUN npm run build

# --- Stage 2: python runtime ---
FROM --platform=$TARGETPLATFORM python:3.9-slim-bullseye
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Create app dir
WORKDIR /app

# Copy backend
COPY services/weightd/requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip==23.2.1 setuptools==68.2.2 wheel==0.41.2
RUN pip install --no-binary=:all: fastapi==0.103.2
RUN pip install --no-binary=:all: uvicorn==0.23.2
RUN pip install --no-binary=:all: pydantic==1.10.13
RUN pip install --no-binary=:all: paho-mqtt==1.6.1
RUN pip install --no-binary=:all: python-multipart==0.0.9
COPY services/weightd/app /app/app

# Copy built web UI to static
COPY --from=webui /app/dist /app/app/static

# Create data dir
VOLUME ["/data"]
ENV DATA_DIR=/data

EXPOSE 8080
CMD ["python", "-m", "app.main"]
