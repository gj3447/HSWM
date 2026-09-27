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
