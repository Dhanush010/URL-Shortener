#!/bin/sh
# Invoked inside the loadtest container.

set -e

pip install -q --trusted-host pypi.org --trusted-host files.pythonhosted.org locust httpx
mkdir -p results

python scripts/seed_urls.py http://app:8000 50

USER_CLASS="${LOCUST_USER_CLASS:-}"
USERS="${LOCUST_USERS:-500}"
SPAWN_RATE="${LOCUST_SPAWN_RATE:-50}"
RUN_TIME="${LOCUST_RUN_TIME:-60s}"
CSV_PREFIX="${LOCUST_CSV_PREFIX:-results/load_test}"

if [ -n "$USER_CLASS" ]; then
  exec locust -f locustfile.py --host=http://app:8000 "$USER_CLASS" \
    --users="$USERS" \
    --spawn-rate="$SPAWN_RATE" \
    --run-time="$RUN_TIME" \
    --headless \
    --csv="$CSV_PREFIX"
fi

exec locust -f locustfile.py --host=http://app:8000 \
  --users="$USERS" \
  --spawn-rate="$SPAWN_RATE" \
  --run-time="$RUN_TIME" \
  --headless \
  --csv="$CSV_PREFIX"
