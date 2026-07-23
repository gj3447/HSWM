#!/usr/bin/env bash
set -euo pipefail

tool_root=/data/kjra/TOOLS/hswm-phantomwiki-1.0.3
env_root="$tool_root/env"
project_root=/data/kjra/PROJECT/HSWM_P1V4R2_20260724_FROZEN_DATA
final_root="$project_root/phantomwiki_seed5/sparse_t200_fk1_q200"
staging_root="$project_root/.staging-phantomwiki-seed5-sparse-t200-fk1-q200"

if [[ -e "$final_root" || -e "$staging_root" ]]; then
  echo "refusing pre-existing seed5 target" >&2
  exit 41
fi
test -x "$env_root/bin/python"
test -x "$env_root/bin/swipl"
test -x "$env_root/bin/pw-generate"
"$env_root/bin/python" -c \
  'import importlib.metadata as m; assert m.version("phantom-wiki") == "1.0.3"'

mkdir -p "$project_root/phantomwiki_seed5"
PATH="$env_root/bin:$PATH" "$env_root/bin/pw-generate" \
  -od "$staging_root" \
  --num-family-trees 200 \
  --friendship-k 1 \
  --num-questions-per-type 200 \
  --question-depth 10 \
  --seed 5 \
  --friendship-seed 5 \
  --article-format json \
  --question-format json

"$env_root/bin/python" - "$staging_root/questions.json" "$staging_root/questions" <<'PY'
from __future__ import annotations
import json
from pathlib import Path
import sys

source = Path(sys.argv[1])
target = Path(sys.argv[2])
questions = json.loads(source.read_text(encoding="utf-8"))
if not isinstance(questions, list) or len(questions) != 4000:
    raise SystemExit("combined question output is not the frozen 4000-row cut")
by_type = {}
for row in questions:
    if not isinstance(row, dict) or not isinstance(row.get("type"), int):
        raise SystemExit("question schema drift")
    by_type.setdefault(row["type"], []).append(row)
if set(by_type) != set(range(20)) or any(len(rows) != 200 for rows in by_type.values()):
    raise SystemExit("per-type question cardinality drift")
target.mkdir(exist_ok=True)
for question_type, rows in sorted(by_type.items()):
    (target / f"type{question_type}.json").write_text(
        json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
PY

test -s "$staging_root/articles.json"
test -s "$staging_root/questions/type6.json"
mv "$staging_root" "$final_root"

"$env_root/bin/python" - "$final_root" "$project_root/generation_receipt_seed5_r2.json" <<'PY'
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
output = Path(sys.argv[2])

def digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()

receipt = {
    "schema_version": "hswm-p1v4-phantom-generation-receipt/v1",
    "generator": {
        "package": "phantom-wiki",
        "version": "1.0.3",
        "swi_prolog_version": subprocess.check_output(
            ["/data/kjra/TOOLS/hswm-phantomwiki-1.0.3/env/bin/swipl", "--version"],
            text=True,
        ).strip(),
    },
    "flags": {
        "num_family_trees": 200,
        "friendship_k": 1,
        "num_questions_per_type": 200,
        "question_depth": 10,
        "seed": 5,
        "friendship_seed": 5,
        "article_format": "json",
        "question_format": "json",
    },
    "eligibility_repair": {
        "prior_seed": 4,
        "prior_public_single_match_candidates": 3,
        "prior_gold_inspected": False,
        "change": "increase public questions per type from 30 to 200 on a new seed",
        "unchanged": "single-match eligibility, deterministic selection, split 1/3/6, scoring",
    },
    "universe": "sparse_t200_fk1_seed5_q200",
    "dataset_files": {
        "articles.json": digest(root / "articles.json"),
        "questions/type6.json": digest(root / "questions" / "type6.json"),
    },
    "overwrite_policy": "fail_if_frozen_target_exists",
}
encoded = json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
receipt["generation_receipt_sha256"] = sha256(encoded.encode("utf-8")).hexdigest()
output.write_text(
    json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(receipt, sort_keys=True))
PY
