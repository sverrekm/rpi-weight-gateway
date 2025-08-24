#!/usr/bin/env bash
set -euo pipefail

WITH_PROFILES=""
for arg in "$@"; do
  case "$arg" in
    --with-mqtt) WITH_PROFILES="$WITH_PROFILES --profile mqtt" ;;
    --with-wifi) WITH_PROFILES="$WITH_PROFILES --profile wifi" ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  usermod -aG docker "${SUDO_USER:-$USER}" || true
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Installing docker compose plugin..."
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update && apt-get install -y docker-compose-plugin
  else
    echo "Please install docker compose plugin manually for your distro." >&2
  fi
fi

# Clone or update repository
REPO_DIR="rpi-weight-gateway"
if [ -d "$REPO_DIR" ]; then
  echo "Updating existing repository..."
  cd "$REPO_DIR"
  git pull
else
  echo "Cloning repository..."
  git clone https://github.com/sverrekm/rpi-weight-gateway.git
  cd "$REPO_DIR"
fi

[ -f .env ] || cp .env.example .env

docker compose pull || true
DOCKER_DEFAULT_PLATFORM=linux/arm/v7 docker compose build
DOCKER_DEFAULT_PLATFORM=linux/arm/v7 docker compose up -d $WITH_PROFILES

echo "Done. If you were added to docker group, log out/in."
echo "Access the web UI at: http://$(hostname -I | awk '{print $1}'):8080"
