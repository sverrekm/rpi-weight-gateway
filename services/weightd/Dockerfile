# First stage: Build frontend - use explicit ARMv7 image
FROM --platform=linux/arm/v7 node:18-bullseye-slim AS frontend-builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y python3 make g++

# Copy frontend files
COPY services/webui /app

# Install dependencies and build with node-gyp
RUN npm install --force --build-from-source && \
    npm run build

# Second stage: Build backend
FROM arm32v7/python:3.9-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_NO_BUILD_ISOLATION=1 \
    DATA_DIR=/data

# Create app dir
WORKDIR /app

## Install build dependencies (prefer gz indices for robustness)
# Install WiFi AP and network management tools
RUN apt-get update && apt-get install -y \
    hostapd \
    dnsmasq \
    iptables \
    wireless-tools \
    wpasupplicant \
    net-tools \
    network-manager \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy AP setup script and configs
COPY app/setup_ap.sh /usr/local/bin/setup_ap.sh
COPY app/dnsmasq.conf /etc/dnsmasq.conf
RUN chmod +x /usr/local/bin/setup_ap.sh && \
    # Enable dnsmasq
    systemctl enable dnsmasq

# Install required system packages
RUN echo 'Acquire::CompressionTypes::Order:: "gz";' > /etc/apt/apt.conf.d/99force-gz \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       python3-dev \
       git \
       libffi-dev \
       libssl-dev \
       curl \
       network-manager \
       wireless-tools \
       wpasupplicant \
       python3-setuptools \
    && rm -rf /var/lib/apt/lists/* \
    # Install docker-compose separately to avoid conflicts
    && curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s | tr '[:upper:]' '[:lower:]')-$(uname -m)" -o /usr/local/bin/docker-compose \
    && chmod +x /usr/local/bin/docker-compose

# Create required directories
RUN mkdir -p /etc/hostapd /etc/iptables /var/run/hostapd /var/lib/misc

# Set up hostapd to run in the container
RUN systemctl enable hostapd

# Create a service to initialize the AP mode if needed
RUN echo '[Unit]\n\
Description=Setup Access Point\n\
After=network.target\n\n[Service]\n\
Type=oneshot\n\
ExecStart=/usr/local/bin/setup_ap.sh\n\nRemainAfterExit=yes\n\n[Install]\n\
WantedBy=multi-user.target\n' > /etc/systemd/system/setup-ap.service

RUN systemctl enable setup-ap.service

# Copy backend
COPY services/weightd/requirements.txt /app/requirements.txt
## Upgrade pip tooling separately for clearer logs, then install deps preferring wheels
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy backend source
COPY services/weightd /app

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/dist/ /app/app/static/

# Copy project logo into static web root
COPY static/IMG_4293.jpg /app/app/static/logo.jpg
COPY static/IMG_4293.jpg /app/app/static/logo.png

# Return to app directory
WORKDIR /app

# Create data dir and ensure proper permissions
RUN mkdir -p /data \
    && chmod 777 /data \
    && mkdir -p /dev/shm/display \
    && chmod 777 /dev/shm/display

VOLUME ["/data"]

# Allow access to serial ports
ENV PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_NO_BUILD_ISOLATION=1 \
    DATA_DIR=/data \
    # Enable Python's fork server for faster process startup
    PYTHON_USE_FORK_SAFE=1

# Add udev rules for serial devices if needed
RUN mkdir -p /etc/udev/rules.d/ && \
    echo 'KERNEL=="tty[A-Z]*[0-9]*", MODE="0666"' > /etc/udev/rules.d/99-serial.rules

# Ensure the display FIFO directory exists
RUN mkdir -p /tmp/display_fifo && chmod 777 /tmp/display_fifo

EXPOSE 8000
# Ensure Python sees /app on sys.path and run uvicorn with verbose logging
ENV PYTHONPATH=/app
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug"]
