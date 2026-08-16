#!/usr/bin/env bash
# F3v2 slice-2 arms smoke — preflight + runner (dev, DEVELOPMENT_ONLY).
#
# Run this when the vLLM box (192.168.219.102) is back online. It:
#   1. checks the donor endpoint  :8000 (/v1/models)
#   2. checks the receiver endpoint :8001, starting the receiver container
#      via ssh if it is down
#   3. prints the served model ids on both endpoints (identity check)
#   4. runs the <=20-new-live-call arms smoke, strictly sequential
#      (the box may be busy with other sealed runs — this script never
#      parallelizes and inherits the harness's bounded-retry timeouts)
#
# Usage: ./scripts/f3v2_smoke_preflight.sh [extra _research.f_series.f3v2_arms flags]
set -euo pipefail
cd "$(dirname "$0")/.."

DONOR=http://192.168.219.102:8000
RECV=http://192.168.219.102:8001
SSH_HOST=metahumotonic27@192.168.219.102
RECV_CONTAINER=vllm-receiver

check() { curl -sf -m 10 "$1/v1/models" >/dev/null 2>&1; }

echo "[1/4] donor $DONOR/v1/models ..."
if check "$DONOR"; then
  echo "      ok"
else
  echo "      DONOR ENDPOINT DOWN — the box itself may be offline; start the"
  echo "      donor vLLM before running this smoke. Aborting."
  exit 1
fi

echo "[2/4] receiver $RECV/v1/models ..."
if ! check "$RECV"; then
  echo "      receiver down — starting container $RECV_CONTAINER via ssh"
  ssh "$SSH_HOST" "docker start $RECV_CONTAINER"
  for _ in $(seq 1 30); do
    check "$RECV" && break
    sleep 10
  done
fi
if check "$RECV"; then
  echo "      ok"
else
  echo "      RECEIVER STILL DOWN after container start — aborting."
  exit 1
fi

echo "[3/4] served model ids (verify qwen3.6-27b / qwen3-4b-real):"
echo -n "      donor:    "
curl -s -m 10 "$DONOR/v1/models" | python3 -c 'import json,sys; print([m["id"] for m in json.load(sys.stdin)["data"]])'
echo -n "      receiver: "
curl -s -m 10 "$RECV/v1/models" | python3 -c 'import json,sys; print([m["id"] for m in json.load(sys.stdin)["data"]])'

echo "[4/4] arms smoke (planned new live calls: 16 <= 20, sequential) ..."
exec .venv/bin/python -m _research.f_series.f3v2_arms --smoke \
  --endpoint "$DONOR" --donor-model qwen3.6-27b \
  --receiver-endpoint "$RECV" --receiver-model qwen3-4b-real \
  "$@"
