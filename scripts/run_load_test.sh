#!/bin/sh
# Run Locust load test against the Docker Compose app stack.
#
# Usage:
#   ./scripts/run_load_test.sh              # full mixed workload (500 users)
#   ./scripts/run_load_test.sh redirect     # cache-heavy redirect benchmark

set -e

MODE="${1:-mixed}"

docker-compose exec redis redis-cli FLUSHDB

mkdir -p results

if [ "$MODE" = "redirect" ]; then
  export LOCUST_USER_CLASS=RedirectUser
  export LOCUST_USERS=100
  export LOCUST_SPAWN_RATE=25
  export LOCUST_RUN_TIME=30s
  export LOCUST_CSV_PREFIX=results/load_test_redirect
else
  export LOCUST_USER_CLASS=
  export LOCUST_USERS=500
  export LOCUST_SPAWN_RATE=50
  export LOCUST_RUN_TIME=60s
  export LOCUST_CSV_PREFIX=results/load_test
fi

docker-compose --profile loadtest run --rm loadtest

echo "Results written to ${LOCUST_CSV_PREFIX}_stats.csv"