#!/usr/bin/env bash
set -euo pipefail
: "${HSWM_OUTPUT_ROOT:?Use the documented DGX hswm-run wrapper}"
: "${HSWM_RESEARCH_RUNTIME_DIST:?Use an isolated source-pinned runtime build}"
: "${W1_SERVING_ATTESTATION:?Provide a private source-bound serving attestation}"
node _research/local_semantic_execution_v1/runner.mts prepare "$HSWM_OUTPUT_ROOT"
node _research/local_semantic_execution_v1/runner.mts run "$HSWM_OUTPUT_ROOT" "$W1_SERVING_ATTESTATION"
