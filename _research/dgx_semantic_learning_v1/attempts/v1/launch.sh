#!/usr/bin/env bash
set -euo pipefail
: "${HSWM_OUTPUT_ROOT:?Run through hswm-run}"
: "${HSWM_RESEARCH_RUNTIME_DIST:?Set the isolated, source-pinned runtime dist}"
nvidia-smi --query-gpu=timestamp,utilization.gpu,power.draw --format=csv -l 2 > "$HSWM_OUTPUT_ROOT/gpu.csv" &
telemetry_pid=$!
trap 'kill "$telemetry_pid" 2>/dev/null || true; wait "$telemetry_pid" 2>/dev/null || true' EXIT
timeout --signal=TERM --kill-after=10s 2400s /home/metahumotonic27/.local/opt/node-v24.13.0-linux-arm64/bin/node _research/dgx_semantic_learning_v1/run.mts
