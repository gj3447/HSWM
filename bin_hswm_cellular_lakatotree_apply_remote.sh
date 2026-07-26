#!/usr/bin/env bash
# Apply the sealed HSWM cellular packet through the canonical Proxmox host and
# copy the exact readback receipt back to this Git working tree.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")" && pwd)
symposium_root=/Users/lagyeongjun/CD/SYMPOSIUM
sync_script="$symposium_root/bin/lakatotree-sync-now.sh"
remote_host=${LAKATOTREE_SSH_HOST:-root@192.168.0.26}
remote_repo=/Users/lagyeongjun/CD/SYMPOSIUM/GIT/HSWM
receipt_name=HSWM_CELLULAR_LAKATOTREE_READBACK_20260726.json
remote_receipt="/tmp/$receipt_name"
local_receipt="$repo_root/receipts/$receipt_name"
ssh_opts=(-o BatchMode=yes -o ConnectTimeout=5)

if ! ssh "${ssh_opts[@]}" "$remote_host" "curl -fsS --max-time 5 http://127.0.0.1:55170/healthz >/dev/null"; then
  echo "REFUSED: canonical LakatoTree host or service is unavailable: $remote_host" >&2
  exit 2
fi

if [[ ! -x "$sync_script" ]]; then
  echo "REFUSED: canonical sync script missing or not executable: $sync_script" >&2
  exit 2
fi

"$sync_script"

ssh "${ssh_opts[@]}" "$remote_host" \
  "set -a; . /opt/lakatotree/server.env; set +a; cd '$remote_repo'; /opt/lakatotree/.venv/bin/python bin_hswm_cellular_lakatotree_upload.py --url http://127.0.0.1:55170 --receipt '$remote_receipt'"

scp "${ssh_opts[@]}" "$remote_host:$remote_receipt" "$local_receipt"

python3 - "$local_receipt" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
receipt = json.loads(path.read_text(encoding="utf-8"))
if receipt.get("status") != "APPLIED_AND_EXACT_READBACK_PASS":
    raise SystemExit(f"REFUSED: unexpected receipt status: {receipt.get('status')!r}")
if receipt.get("scientific_status") != "UNJUDGED":
    raise SystemExit("REFUSED: upload changed scientific status")
if receipt.get("verdict_mutation_performed") is not False:
    raise SystemExit("REFUSED: upload claims a verdict mutation")
print(f"PASS: exact LakatoTree readback copied to {path}")
PY
