#!/usr/bin/env sh
# wait-for host:port with timeout
set -e
HOSTPORT=$1
TIMEOUT=${2:-30}
START=$(date +%s)
while :; do
  # Try multiple netcat variants
  if command -v nc >/dev/null 2>&1; then
    nc -z ${HOSTPORT%:*} ${HOSTPORT#*:} && exit 0 || true
  elif command -v netcat >/dev/null 2>&1; then
    netcat -z ${HOSTPORT%:*} ${HOSTPORT#*:} && exit 0 || true
  else
    # Fallback using /dev/tcp
    (echo >/dev/tcp/${HOSTPORT%:*}/${HOSTPORT#*:}) >/dev/null 2>&1 && exit 0 || true
  fi
  NOW=$(date +%s)
  [ $((NOW-START)) -ge $TIMEOUT ] && exit 1
  sleep 1
done
