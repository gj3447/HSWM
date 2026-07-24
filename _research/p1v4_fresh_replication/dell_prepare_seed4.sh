#!/usr/bin/env bash
set -euo pipefail

expected_commit=0ea945321b3d07143b17a2626ef3881d3f368146
code_root=/data/kjra/PROJECT/HSWM_P1V4_20260724_CODE_0ea9453
data_root=/data/kjra/PROJECT/HSWM_P1V4_20260724_FROZEN_DATA
universe_root="$data_root/phantomwiki_seed4/sparse_t200_fk1"
generation_receipt="$data_root/generation_receipt_seed4.json"
public_output="$data_root/p1v4_policy_public_manifest_seed4.json"
development_output="$data_root/sealed/p1v4_policy_seed4_development.json"
heldout_output="$data_root/sealed/p1v4_policy_seed4_heldout.json"
separation_output="$data_root/p1v4_policy_sidecar_separation_seed4.json"
python_bin=/data/kjra/PROJECT/PI/_serve/vllm-venv/bin/python

for target in \
  "$code_root" "$public_output" "$development_output" "$heldout_output" \
  "$separation_output"; do
  if [[ -e "$target" ]]; then
    echo "refusing to overwrite frozen target: $target" >&2
    exit 41
  fi
done

git clone --quiet https://github.com/gj3447/HSWM.git "$code_root"
git -C "$code_root" checkout --quiet --detach "$expected_commit"
actual_commit="$(git -C "$code_root" rev-parse HEAD)"
if [[ "$actual_commit" != "$expected_commit" ]]; then
  echo "checkout commit mismatch: $actual_commit" >&2
  exit 42
fi
mkdir -p "$data_root/sealed"

"$python_bin" "$code_root/p1v3_prepare.py" \
  --universe-path "$universe_root" \
  --generation-receipt "$generation_receipt" \
  --public-output "$public_output" \
  --development-output "$development_output" \
  --heldout-output "$heldout_output"

PYTHONPATH="$code_root" "$python_bin" - \
  "$public_output" "$development_output" "$heldout_output" \
  "$separation_output" "$expected_commit" <<'PY'
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

from p1v3_prepare import verify_policy_manifests


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


public_path, development_path, heldout_path, separation_path = map(
    Path, sys.argv[1:5]
)
expected_commit = sys.argv[5]
public = json.loads(public_path.read_text(encoding="utf-8"))
development = json.loads(development_path.read_text(encoding="utf-8"))
heldout = json.loads(heldout_path.read_text(encoding="utf-8"))
verify_policy_manifests(public, development, heldout)

development_ids = set(development["cases"])
heldout_ids = set(heldout["cases"])
if development_ids & heldout_ids:
    raise SystemExit("development and heldout case IDs overlap")
if {row["split"] for row in development["cases"].values()} != {
    "training", "calibration"
}:
    raise SystemExit("development sidecar contains a non-development split")
if {row["split"] for row in heldout["cases"].values()} != {"heldout"}:
    raise SystemExit("heldout sidecar contains a development split")

forbidden = {
    "expected_answers", "trusted_source_ids", "distractor_source_ids",
    "trusted_class", "distractor_class", "gold_answers", "answer", "answers",
    "solution_trace", "solution_traces",
}


def recursive_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key).casefold()
            yield from recursive_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from recursive_keys(item)


public_forbidden_keys = sorted(forbidden & set(recursive_keys(public)))
if public_forbidden_keys:
    raise SystemExit(f"public manifest leaked keys: {public_forbidden_keys}")

separation = {
    "schema_version": "hswm-p1v4-policy-sidecar-separation-receipt/v1",
    "preparation_code_commit": expected_commit,
    "completed_at": datetime.now(timezone.utc).isoformat(),
    "public": {
        "remote_path": str(public_path),
        "file_sha256": file_sha256(public_path),
        "manifest_sha256": public["public_manifest_sha256"],
        "forbidden_key_count": len(public_forbidden_keys),
    },
    "development": {
        "remote_path": str(development_path),
        "file_sha256": file_sha256(development_path),
        "sidecar_sha256": development["development_sidecar_sha256"],
        "case_count": len(development_ids),
        "splits": ["training", "calibration"],
    },
    "heldout": {
        "remote_path": str(heldout_path),
        "file_sha256": file_sha256(heldout_path),
        "sidecar_sha256": heldout["heldout_sidecar_sha256"],
        "case_count": len(heldout_ids),
        "splits": ["heldout"],
    },
    "calibration_loader_contract": {
        "allowed_sidecar_sha256": development["development_sidecar_sha256"],
        "heldout_sidecar_must_not_be_loaded": True,
    },
    "sidecar_overlap_count": len(development_ids & heldout_ids),
    "prior_outcome_reuse": False,
}
separation_path.write_text(
    json.dumps(separation, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps({
    "code_commit": expected_commit,
    "public_manifest_sha256": public["public_manifest_sha256"],
    "public_file_sha256": file_sha256(public_path),
    "development_sidecar_sha256": development["development_sidecar_sha256"],
    "development_file_sha256": file_sha256(development_path),
    "heldout_sidecar_sha256": heldout["heldout_sidecar_sha256"],
    "heldout_file_sha256": file_sha256(heldout_path),
    "development_case_count": len(development_ids),
    "heldout_case_count": len(heldout_ids),
    "sidecar_overlap_count": len(development_ids & heldout_ids),
    "public_forbidden_key_count": len(public_forbidden_keys),
    "separation_file_sha256": file_sha256(separation_path),
}, sort_keys=True))
PY
