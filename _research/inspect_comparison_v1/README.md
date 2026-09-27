# Inspect paired saved-output comparison

This isolated Python research tool uses [Inspect AI](https://inspect.aisi.org.uk/)
tasks, in-memory datasets, a no-model solver, and an exact-match scorer to
score two already-recorded output arms against the same target. It creates
ordinary Inspect `.eval` logs. It does not execute an HSWM transition, call a
model, or establish model improvement.

The strict input contract is JSONL, one object per sample with exactly these
non-empty string fields:

```json
{"id":"case-1","input":"case description","target":"expected output","baseline":"saved baseline output","candidate":"saved candidate output"}
```

Duplicate IDs, blank lines, unknown fields, and missing arms fail before an
evaluation starts. `semantic_locality_adapter.py` is an optional, source-specific
converter; it fails if either selected arm is absent, duplicated, or has a
different target for an ID.

## Run

```bash
cd _research/inspect_comparison_v1
uv sync --locked --group dev
uv run --locked python semantic_locality_adapter.py \
  ../semantic_locality_dgx_v1/observations.jsonl \
  ../../.hswm-local/inspect-comparison/semantic-locality-full-vs-role-swap.jsonl
uv run --locked python paired_eval.py \
  ../../.hswm-local/inspect-comparison/semantic-locality-full-vs-role-swap.jsonl \
  --log-dir ../../.hswm-local/inspect-comparison/eval-logs
```

The default output is the checkout's `.hswm-local/inspect-comparison`, which the
repository ignores. View the resulting logs with `uv run --locked inspect view --log-dir ../../.hswm-local/inspect-comparison/eval-logs`.

## Pin and provenance

`uv.lock` resolves this standalone environment. It pins `inspect-ai==0.3.260`
from the official PyPI release: MIT license, source archive SHA-256
`5f6fbd7bc1fae0a770dc04e208daa9275de71f6d6b85b5fb68c162a1c4e0496f`, and
official source revision `3f294e61b823d6bad5fc16706fc5825ea980c8ee`
(`0.3.260` tag). Inspect's official documentation defines an evaluation as a
Task combining a dataset, solver, and scorer; this adapter uses those interfaces
with a `mockllm/model` identifier solely because Inspect requires a model field.
The solver never invokes it.

The included semantic-locality command compares the pre-existing `full` and
`role_swap` observations as saved decisions. `role_swap` deliberately changes
the input relation roles, so this is a changed-input diagnostic, never a
same-prompt candidate improvement. See the original
[analysis](../semantic_locality_dgx_v1/analysis.v1.json). Its numbers only
re-score stored observations; they are not a new inference, a real-LLM rerun,
or HSWM efficacy evidence. Invalid or empty saved decisions are retained as
deterministic scoring failures rather than omitted.

## Live W1 relation-text comparison

`live_eval.py` evaluates the existing W1 E1 typed local-semantic input through
`hswm_bridge.mts`. For every case, it replaces only
`input.relation.semanticText`; ordered roles, fields, context, exceptions, and
the fixed execution configuration stay the same. This is an isolated
relation-text execution diagnostic, not a durable canonical revision or a
canonical learning loop. The target, split, case ID, and arm label remain with
the evaluator and are never sent to the bridge.

Prepare a new private fixture directory; the destination must not already
exist. The fixture uses the existing historical family/seed split and replaces
the W1 oracle relation text with its provisional baseline before either train
or heldout file is written.

```bash
cd _research/inspect_comparison_v1
node prepare_fixture.mts /absolute/private/hswm-w1-fixture 0 0
```

After the host-side model preflight has succeeded, compare a candidate relation
text file on the heldout data. The default `--limit 4` is a smoke run, not the
20-case heldout comparison; increase it deliberately only within the declared
128 total arm-attempt budget.

```bash
uv run --locked python live_eval.py \
  /absolute/private/hswm-w1-fixture/heldout.jsonl \
  --baseline-relation /absolute/private/hswm-w1-fixture/baseline.txt \
  --candidate-relation /absolute/private/candidate-relation.txt \
  --base-url http://127.0.0.1:8001 --model qwen3-4b-real \
  --max-tokens 32 --timeout-seconds 30 --seed 0 --limit 4
```

Inspect records this bridge-only evaluation as `none/none` because its provider
is not called directly. Each sample's `hswm_bridge` metadata binds the actual
served model name, request/response hashes, usage when reported, latency, and
the local execution boundary. Invalid model output and HTTP failures remain
scored failures. A Python-side bridge timeout records at most one possible
request attempt rather than claiming a confirmed model call. Live `.eval` logs
default to the ignored checkout `.hswm-local/inspect-live-eval/` directory.
