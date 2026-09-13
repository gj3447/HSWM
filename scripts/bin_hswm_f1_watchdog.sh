#!/usr/bin/env bash
# F1 sealed-r3 watchdog: wait for runner exit, then judge automatically.
# Lives on dgx. judge is deterministic/local (bootstrap, cache-only) — no GPU.
set -u
RUNNER_PID="$1"
BASE="$HOME/hswm_f1_sealed"
RUN_DIR="$BASE/_research/prom9_runs/f1-2wiki-sealed-r3"
STATUS="$RUN_DIR/watchdog.status"

echo "watchdog start $(date -Is) runner_pid=$RUNNER_PID" > "$STATUS"

# wait for the runner to exit (poll, survives ssh detach)
while kill -0 "$RUNNER_PID" 2>/dev/null; do
  sleep 60
done
echo "runner exited $(date -Is)" >> "$STATUS"

if [ ! -f "$RUN_DIR/suite.json" ]; then
  echo "NO_SUITE — run refused or crashed; see run.log" >> "$STATUS"
  exit 1
fi

cd "$BASE" || exit 1
src/hswm/effect-runtime/bin/hswm-prom9-f1 judge \
  --suite "$RUN_DIR/suite.json" \
  --gold "$RUN_DIR/gold.separate.json" \
  --output "$RUN_DIR/judgment.json" \
  >> "$RUN_DIR/judge.log" 2>&1
rc=$?
if [ $rc -eq 0 ]; then
  verdict=$(node -p 'JSON.parse(require("node:fs").readFileSync(process.argv[1], "utf8")).verdict' "$RUN_DIR/judgment.json" 2>/dev/null)
  echo "JUDGED verdict=$verdict $(date -Is)" >> "$STATUS"
else
  echo "JUDGE_FAILED rc=$rc $(date -Is)" >> "$STATUS"
fi
exit $rc
