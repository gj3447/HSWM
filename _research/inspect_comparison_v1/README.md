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

## Single-case initial-versus-oracle diagnostic

`prepare_oracle_diagnostic.mts` and `oracle_single_diagnostic.py` reuse the
existing E1 bridge and paired Inspect evaluator. They prepare four historical
W1 families, selecting one case for every `(target, pel, nub)` stratum: eight
cases per family, 32 cases total, and at most 64 request attempts across the
initial and oracle relation texts. These are **development-exposed synthetic
cases**, not a fresh final holdout. `train` is the existing loader's split name;
this diagnostic does not train a model or provide examples to GEPA.

The evaluator keeps labels, case IDs and oracle-selection metadata out of model
requests. It measures environmental correctness separately from consistency
with the initial relation's own rule. The initial rule ignores `pel`, so perfect
execution of that rule need not produce the environment's correct answer.
HTTP, timeout and invalid-output failures remain in the declared cohort.

Preparation and plan verification make no model requests. From the checkout
root, use a new private destination:

```sh
node _research/inspect_comparison_v1/prepare_oracle_diagnostic.mts \
  .hswm-local/oracle-diagnostic-2026-10-10-v1
_research/inspect_comparison_v1/.venv/bin/python \
  _research/inspect_comparison_v1/oracle_single_diagnostic.py plan \
  .hswm-local/oracle-diagnostic-2026-10-10-v1 \
  --out .hswm-local/oracle-diagnostic-2026-10-10-v1-plan.json
```

The existing isolated environment pins Inspect `0.3.260`; use the locked uv
environment if it is not already prepared. Source and fixture hashes are checked
before execution. Both fixture and result destinations refuse overwrite.

After the existing project access, transport and host-side preflight requirements
are satisfied, `run` requires an explicit current endpoint and served model ID:

```sh
_research/inspect_comparison_v1/.venv/bin/python \
  _research/inspect_comparison_v1/oracle_single_diagnostic.py run \
  .hswm-local/oracle-diagnostic-2026-10-10-v1 \
  --out .hswm-local/oracle-diagnostic-2026-10-10-v1-run \
  --base-url "$HSWM_APPROVED_MODEL_BASE_URL" --model "$HSWM_APPROVED_MODEL_ID"
```

The historical endpoint/model in `execution.json` is not a readiness attestation.
The actual explicit run configuration must be recorded with the result.
There are no retries or automatic service starts.

The manifest fixes a **development screening decision** before any outputs:
oracle environmental correctness at least 30/32, initial-rule consistency at
least 30/32, oracle correctness at least 7/8 in every family, all 64 outputs valid,
and all exception cases retained. Passing permits a next diagnostic; it does not
establish HSWM efficacy, a population effect, or a learned graph update. A future
final comparison requires unexposed task families. Batch size and output format
are unchanged here, so differences from older experiments cannot be attributed
to either factor.

Validation on 2026-10-10: the existing and diagnostic Python tests passed
(18 tests), the native fixture/bridge tests passed (4 tests), and the fixture
generator passed strict TypeScript checking. These use local fixtures and
loopback responses; they do not measure model efficacy. The offline plan was
generated from the final source-pinned fixture above. No real-model diagnostic
had been run at that point.

On 2026-10-11, the first real-model diagnostic completed on the existing DGX.
The operator's `ssh dgx` alias reaches the remote `~/bin/hswm-run`; absence of a
local wrapper does not indicate that the remote wrapper is unavailable:

```sh
ssh dgx '~/bin/hswm-run --help'
ssh dgx '~/bin/hswm-run preflight'
```

The remote noninteractive PATH may omit `~/.local/bin`, which contains Node and
uv. Use the existing executables after checking their versions. A remote checkout
may predate this diagnostic: stage an exact, hashed source/fixture/lockfile bundle
and use `hswm-run exec NEW_RUN_ID --profile hswm -- COMMAND`; do not assume the
remote checkout matches the local source. Keep its isolated environment in wrapper
scratch and its selected inputs/results under `HSWM_OUTPUT_ROOT` for durable
publication to the user's data-01 storage.

Run `oracle-e1-20261011T022429Z` completed 64 requests against `qwen3-4b-real`:
64/64 valid outputs, oracle environmental correctness 17/32, initial-rule
consistency 22/32, and initial environmental correctness 18/32. The frozen screen
returned `REVISE_LOCAL_EXECUTION`; the wrapper's successful process exit is not
a scientific pass. Existing plan/source snapshots were preserved.
