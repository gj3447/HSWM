#!/usr/bin/env bash
set -euo pipefail

expected_commit=0ea945321b3d07143b17a2626ef3881d3f368146
code_root=/data/kjra/PROJECT/HSWM_P1V4R2_20260724_CALIBRATION_CODE_0ea9453
data_root=/data/kjra/PROJECT/HSWM_P1V4R2_20260724_FROZEN_DATA
calibration_root="$data_root/calibration"
development_sidecar="$data_root/sealed/p1v4_policy_seed5_development_r2.json"
public_manifest="$data_root/p1v4_policy_public_manifest_seed5_r2.json"
deployment_receipt="$code_root/receipts/p1v2_qwen35_deployment_20260724.json"
tokenizer_snapshot=/data/kjra/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/95a723d08a9490559dae23d0cff1d9466213d989
budget_output="$calibration_root/p1v4_policy_calibration_budget_seed5_r2.json"
answer_db="$calibration_root/p1v4_policy_calibration_answers_seed5_r2.sqlite3"
evidence_output="$calibration_root/p1v4_policy_calibration_evidence_seed5_r2.json"
python_bin=/data/kjra/PROJECT/PI/_serve/vllm-venv/bin/python

for target in "$code_root" "$budget_output" "$answer_db" "$evidence_output"; do
  if [[ -e "$target" ]]; then
    echo "refusing to overwrite calibration target: $target" >&2
    exit 41
  fi
done
test -s "$development_sidecar"
test -s "$public_manifest"
test -d "$tokenizer_snapshot"

git clone --quiet https://github.com/gj3447/HSWM.git "$code_root"
git -C "$code_root" checkout --quiet --detach "$expected_commit"
actual_commit="$(git -C "$code_root" rev-parse HEAD)"
if [[ "$actual_commit" != "$expected_commit" ]]; then
  echo "checkout commit mismatch: $actual_commit" >&2
  exit 42
fi
mkdir -p "$calibration_root"

cd "$code_root"
"$python_bin" p1v3_calibration_preflight.py \
  --public-manifest "$public_manifest" \
  --development-sidecar "$development_sidecar" \
  --deployment-receipt "$deployment_receipt" \
  --tokenizer-snapshot "$tokenizer_snapshot" \
  --output "$budget_output"

"$python_bin" p1v3_calibration_measure.py \
  --public-manifest "$public_manifest" \
  --development-sidecar "$development_sidecar" \
  --deployment-receipt "$deployment_receipt" \
  --budget-manifest "$budget_output" \
  --tokenizer-snapshot "$tokenizer_snapshot" \
  --answer-db "$answer_db" \
  --evidence-output "$evidence_output"

"$python_bin" - "$budget_output" "$answer_db" "$evidence_output" <<'PY'
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


budget_path, answer_db_path, evidence_path = map(Path, sys.argv[1:4])
budget = json.loads(budget_path.read_text(encoding="utf-8"))
evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
with sqlite3.connect(answer_db_path) as connection:
    states = dict(connection.execute(
        "SELECT status, COUNT(*) FROM p1v2_answer_requests GROUP BY status"
    ))


def recursive_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key).casefold()
            yield from recursive_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from recursive_keys(item)


exact_verdict_key_count = sum(key == "verdict" for key in recursive_keys(evidence))
if exact_verdict_key_count:
    raise SystemExit("calibration evidence contains a scientific verdict key")
if states != {"COMPLETE": 12}:
    raise SystemExit(f"unexpected answer DB states: {states}")
if budget["data"]["heldout_sidecar_loaded"] is not False:
    raise SystemExit("budget reports heldout sidecar access")
if evidence["data_boundary"]["heldout_sidecar_loaded"] is not False:
    raise SystemExit("evidence reports heldout sidecar access")

gate = evidence["calibration_gate"]
print(json.dumps({
    "budget_file_sha256": file_sha256(budget_path),
    "budget_manifest_sha256": budget["budget_manifest_sha256"],
    "evidence_file_sha256": file_sha256(evidence_path),
    "evidence_sha256": evidence["evidence_sha256"],
    "exact_verdict_key_count": exact_verdict_key_count,
    "answer_db_states": states,
    "gate_status": gate["gate_status"],
    "heldout_freeze_authorized": gate["heldout_freeze_authorized"],
    "heldout_sidecar_loaded": False,
    "metrics": gate["metrics"],
    "reasons": gate["reasons"],
}, sort_keys=True))
PY
