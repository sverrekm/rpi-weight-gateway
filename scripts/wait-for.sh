#!/usr/bin/env sh
# wait-for host:port with timeout
set -e
HOSTPORT=$1
TIMEOUT=${2:-30}
START=$(date +%s)
while :; do
  nc -z ${HOSTPORT%:*} ${HOSTPORT#*:} && exit 0 || true
  NOW=$(date +%s)
  [ $((NOW-START)) -ge $TIMEOUT ] && exit 1
  sleep 1
done
