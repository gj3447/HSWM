#!/usr/bin/env bash
set -euo pipefail

expected_commit=4b0dbdd192a717a56abccee481dbad50b2a94d65
code_root=/data/kjra/PROJECT/HSWM_P1V3_20260724_CODE_4b0dbdd
data_root=/data/kjra/PROJECT/HSWM_P1V3_20260724_FROZEN_DATA
development_sidecar="$data_root/sealed/p1v3_policy_seed3_development_r2.json"
heldout_sidecar="$data_root/sealed/p1v3_policy_seed3_heldout_r2.json"
run_root="$data_root/heldout/measurement_seed3_r1"
answer_db="$run_root/answers.sqlite3"
evidence_output="$run_root/evidence.json"
judge_output="$run_root/judge_receipt.json"
tokenizer_snapshot=/data/kjra/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/95a723d08a9490559dae23d0cff1d9466213d989
python_bin=/data/kjra/PROJECT/PI/_serve/vllm-venv/bin/python

for target in "$code_root" "$run_root"; do
  if [[ -e "$target" ]]; then
    echo "refusing to overwrite heldout measurement target: $target" >&2
    exit 41
  fi
done
test -s "$development_sidecar"
test -s "$heldout_sidecar"
test -d "$tokenizer_snapshot"

git clone --quiet https://github.com/gj3447/HSWM.git "$code_root"
git -C "$code_root" checkout --quiet --detach "$expected_commit"
actual_commit="$(git -C "$code_root" rev-parse HEAD)"
if [[ "$actual_commit" != "$expected_commit" ]]; then
  echo "checkout commit mismatch: $actual_commit" >&2
  exit 42
fi
mkdir -p "$run_root"

cd "$code_root"
"$python_bin" p1v3_heldout_measure.py \
  --preregistration PREREG_P1V3_POLICY_ACTUATION_2026-07-24.json \
  --prediction-receipt receipts/p1v3_policy_prediction_receipt_seed3_20260724.json \
  --public-manifest receipts/p1v3_policy_public_manifest_seed3_20260724.json \
  --development-sidecar "$development_sidecar" \
  --heldout-sidecar "$heldout_sidecar" \
  --sidecar-separation-receipt receipts/p1v3_policy_sidecar_separation_seed3_20260724.json \
  --calibration-evidence receipts/p1v3_policy_calibration_evidence_seed3_20260724.json \
  --deployment-receipt receipts/p1v2_qwen35_deployment_20260724.json \
  --budget-manifest receipts/p1v3_policy_heldout_budget_seed3_20260724.json \
  --tokenizer-snapshot "$tokenizer_snapshot" \
  --answer-db "$answer_db" \
  --evidence-output "$evidence_output"

"$python_bin" p1v3_heldout_judge.py \
  --evidence "$evidence_output" \
  --budget receipts/p1v3_policy_heldout_budget_seed3_20260724.json \
  --output "$judge_output"

"$python_bin" - "$answer_db" "$evidence_output" "$judge_output" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


answer_db, evidence_path, judge_path = map(Path, sys.argv[1:4])
evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
judge = json.loads(judge_path.read_text(encoding="utf-8"))
with sqlite3.connect(answer_db) as connection:
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
if states != {"COMPLETE": 24}:
    raise SystemExit(f"unexpected answer DB states: {states}")
if exact_verdict_key_count != 0:
    raise SystemExit("measurement evidence contains a verdict key")
print(json.dumps({
    "answer_db_states": states,
    "evidence_file_sha256": file_sha256(evidence_path),
    "evidence_sha256": evidence["evidence_sha256"],
    "exact_verdict_key_count": exact_verdict_key_count,
    "judge_file_sha256": file_sha256(judge_path),
    "judge_receipt_sha256": judge["judge_receipt_sha256"],
    "judge_script_sha256": judge["judge_script_sha256"],
    "metrics": judge["metrics"],
    "value": judge["value"],
    "verdict": judge["verdict"],
}, sort_keys=True))
PY
