#!/usr/bin/env bash
set -euo pipefail

tool_root=/data/kjra/TOOLS/hswm-phantomwiki-1.0.3
micro_bin="$tool_root/bin/micromamba"
env_root="$tool_root/env"
project_root=/data/kjra/PROJECT/HSWM_P1V4_20260724_FROZEN_DATA
final_root="$project_root/phantomwiki_seed4/sparse_t200_fk1"
staging_root="$project_root/.staging-phantomwiki-seed4-sparse-t200-fk1"

if [[ -e "$final_root" ]]; then
  echo "refusing to overwrite frozen dataset: $final_root" >&2
  exit 41
fi
if [[ -e "$staging_root" ]]; then
  echo "refusing pre-existing staging path: $staging_root" >&2
  exit 42
fi

test -x "$micro_bin"
test -x "$env_root/bin/python"
test -x "$env_root/bin/swipl"
"$env_root/bin/python" -c \
  'import importlib.metadata as m; assert m.version("phantom-wiki") == "1.0.3"'

mkdir -p "$project_root/phantomwiki_seed4"
PATH="$env_root/bin:$PATH" "$env_root/bin/pw-generate" \
  -od "$staging_root" \
  --num-family-trees 200 \
  --friendship-k 1 \
  --num-questions-per-type 30 \
  --question-depth 10 \
  --seed 4 \
  --friendship-seed 4 \
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
if not isinstance(questions, list) or len(questions) != 600:
    raise SystemExit("combined question output is not the frozen 600-row cut")
by_type = {}
for row in questions:
    if not isinstance(row, dict) or not isinstance(row.get("type"), int):
        raise SystemExit("question schema drift")
    by_type.setdefault(row["type"], []).append(row)
if set(by_type) != set(range(20)) or any(len(rows) != 30 for rows in by_type.values()):
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

"$env_root/bin/python" - "$final_root" "$project_root/generation_receipt_seed4.json" <<'PY'
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
        "num_questions_per_type": 30,
        "question_depth": 10,
        "seed": 4,
        "friendship_seed": 4,
        "article_format": "json",
        "question_format": "json",
    },
    "universe": "sparse_t200_fk1_seed4",
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
