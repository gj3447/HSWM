#!/usr/bin/env bash
set -euo pipefail

expected_commit=5f0ab6b949dd8fca24770e8c66b3106e0adf3cc4
code_root=/data/kjra/PROJECT/HSWM_P1V3_20260724_CODE_5f0ab6b
data_root=/data/kjra/PROJECT/HSWM_P1V3_20260724_FROZEN_DATA
development_sidecar="$data_root/sealed/p1v3_policy_seed3_development_r2.json"
heldout_root="$data_root/heldout"
budget_output="$heldout_root/p1v3_policy_heldout_budget_seed3_r1.json"
tokenizer_snapshot=/data/kjra/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/95a723d08a9490559dae23d0cff1d9466213d989
python_bin=/data/kjra/PROJECT/PI/_serve/vllm-venv/bin/python

for target in "$code_root" "$budget_output"; do
  if [[ -e "$target" ]]; then
    echo "refusing to overwrite heldout preflight target: $target" >&2
    exit 41
  fi
done
test -s "$development_sidecar"
test -d "$tokenizer_snapshot"

git clone --quiet https://github.com/gj3447/HSWM.git "$code_root"
git -C "$code_root" checkout --quiet --detach "$expected_commit"
actual_commit="$(git -C "$code_root" rev-parse HEAD)"
if [[ "$actual_commit" != "$expected_commit" ]]; then
  echo "checkout commit mismatch: $actual_commit" >&2
  exit 42
fi
mkdir -p "$heldout_root"

cd "$code_root"
"$python_bin" p1v3_heldout_preflight.py \
  --public-manifest receipts/p1v3_policy_public_manifest_seed3_20260724.json \
  --development-sidecar "$development_sidecar" \
  --sidecar-separation-receipt receipts/p1v3_policy_sidecar_separation_seed3_20260724.json \
  --calibration-evidence receipts/p1v3_policy_calibration_evidence_seed3_20260724.json \
  --deployment-receipt receipts/p1v2_qwen35_deployment_20260724.json \
  --tokenizer-snapshot "$tokenizer_snapshot" \
  --output "$budget_output"

"$python_bin" - "$budget_output" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
budget = json.loads(path.read_text(encoding="utf-8"))
digest = sha256(path.read_bytes()).hexdigest()
if budget["measurement_state"] != "FROZEN_UNRUN":
    raise SystemExit("heldout budget is not unrun")
if budget["data"]["heldout_gold_values_or_cardinality_inspected_for_planning"] is not False:
    raise SystemExit("heldout planning crossed the sealed outcome boundary")
if budget["parity"]["physical_model_calls_total"] != 24:
    raise SystemExit("heldout physical call budget drifted")
print(json.dumps({
    "budget_file_sha256": digest,
    "budget_manifest_sha256": budget["budget_manifest_sha256"],
    "heldout_cases": budget["data"]["heldout_case_count"],
    "minimum_typed_improvements_for_pass": budget["score_contract"][
        "minimum_typed_improvements_for_pass"
    ],
    "physical_model_calls_total": budget["parity"]["physical_model_calls_total"],
    "measurement_state": budget["measurement_state"],
    "heldout_outcomes_inspected_for_planning": False,
}, sort_keys=True))
PY
