# --- Stage 1: python runtime ---
FROM arm32v7/python:3.9-bullseye
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_NO_BUILD_ISOLATION=1 \
    DATA_DIR=/data

# Create app dir
WORKDIR /app

# Copy backend
COPY services/weightd/requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir \
        'pip<24.1' 'setuptools<69' 'wheel<0.42' \
    && pip install -vv --no-cache-dir --only-binary=:all: -r requirements.txt

# Copy pre-built static files from webui
COPY services/webui/dist /app/static

COPY services/weightd /app

# Create data dir
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
