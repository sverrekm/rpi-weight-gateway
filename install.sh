#!/usr/bin/env bash
set -euo pipefail

# Idempotent installer/updater for rpi-weight-gateway
# Usage examples:
#   curl -fsSL https://raw.githubusercontent.com/sverrekm/rpi-weight-gateway/main/install.sh | sudo bash -s -- --with-mqtt --with-wifi
#   curl -fsSL https://raw.githubusercontent.com/sverrekm/rpi-weight-gateway/main/install.sh | sudo bash -s -- --rebuild

REPO_URL="https://github.com/sverrekm/rpi-weight-gateway.git"
INSTALL_DIR="/opt/rpi-weight-gateway"
BRANCH="main"
WITH_PROFILES=()
REBUILD=0

log() { echo -e "[install] $*"; }
err() { echo -e "[install][error] $*" >&2; }

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    err "This script must run as root (use sudo)."; exit 1
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --with-mqtt) WITH_PROFILES+=("--profile" "mqtt"); shift ;;
      --with-wifi) WITH_PROFILES+=("--profile" "wifi"); shift ;;
      --rebuild) REBUILD=1; shift ;;
      --branch) BRANCH="${2:-main}"; shift 2 ;;
      *) err "Unknown option: $1"; exit 1 ;;
    esac
  done
}

ensure_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker "${SUDO_USER:-$USER}" || true
  fi
  if ! docker compose version >/dev/null 2>&1; then
    log "Installing docker compose plugin..."
    if command -v apt-get >/dev/null 2>&1; then
      apt-get update && apt-get install -y docker-compose-plugin
    else
      err "Please install docker compose plugin for your distro."; exit 1
    fi
  fi
  # Try to ensure daemon is up
  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable docker || true
    systemctl start docker || true
  fi
}

sync_repo() {
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Updating repository at $INSTALL_DIR (branch $BRANCH)..."
    git -C "$INSTALL_DIR" fetch --all --prune
    git -C "$INSTALL_DIR" checkout "$BRANCH"
    git -C "$INSTALL_DIR" pull --ff-only || git -C "$INSTALL_DIR" reset --hard origin/"$BRANCH"
  else
    log "Cloning repository to $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
  fi
}

build_frontend() {
  cd "$INSTALL_DIR"
  if command -v npm >/dev/null 2>&1; then
    log "Building React frontend..."
    
    # Clean up any existing build
    rm -rf "$INSTALL_DIR/services/webui/dist"
    rm -rf "$INSTALL_DIR/services/webui/node_modules"
    cd services/webui
    
    # Clean up any existing build artifacts
    log "Cleaning up old build artifacts..."
    rm -rf node_modules/
    rm -rf dist/
    
    # Install dependencies
    log "Installing frontend dependencies..."
    npm install --force
    
    # Build the frontend
    log "Building frontend..."
    npm run build
    
    # The postbuild script will handle copying files
    
    # Verify files were built
    if [ ! -d "dist" ]; then
      log "Error: Frontend build failed - dist directory not found"
      exit 1
    fi
    
    log "Frontend build complete"
    cd "$INSTALL_DIR"
  else
    log "npm not found, skipping frontend build"
    exit 1
  fi
}

prepare_config() {
  cd "$INSTALL_DIR"
  mkdir -p data data/mosquitto
  # Ensure mosquitto.conf exists for compose mount
  if [[ ! -f data/mosquitto.conf ]]; then
    cat > data/mosquitto.conf <<'EOF'
listener 1883 0.0.0.0
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
EOF
  fi
  # Create .env from example if missing (non-interactive defaults)
  if [[ -f .env.example && ! -f .env ]]; then
    cp .env.example .env
  fi
}

compose_up() {
  cd "$INSTALL_DIR"
  if [[ $REBUILD -eq 1 ]]; then
    log "Building image (manual docker build to avoid BuildKit)..."
    # Determine project image tag (default compose project name is directory name)
    local IMAGE_TAG="rpi-weight-gateway-weightd:latest"
    # Select base image per arch
    local ARCH
    ARCH=$(uname -m)
    local BASE_IMAGE
    case "$ARCH" in
      armv7l)
        BASE_IMAGE="arm32v7/python:3.9-bullseye" # bookworm often missing for armv7
        ;;
      aarch64)
        BASE_IMAGE="python:3.9-bookworm"
        ;;
      *)
        BASE_IMAGE="python:3.9-bookworm"
        ;;
    esac
    docker build --build-arg BASE_IMAGE="$BASE_IMAGE" -f services/weightd/Dockerfile -t "$IMAGE_TAG" . || {
      log "Manual docker build failed"; exit 1; }
  fi
  log "Starting services..."
  if [[ $REBUILD -eq 1 ]]; then
    docker compose up -d --no-build "${WITH_PROFILES[@]}"
  else
    docker compose up -d "${WITH_PROFILES[@]}"
  fi
}

main() {
  require_root
  parse_args "$@"
  ensure_docker
  sync_repo
  build_frontend
  prepare_config
  compose_up
  log "Done. To manage services: cd $INSTALL_DIR && docker compose ps"
}

main "$@"
exit 0
