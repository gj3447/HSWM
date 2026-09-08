# Actual LLM baseline calibration over native USL observations

Status: `IMPLEMENTED_AWAITING_MODEL_CONFIGURATION`. Actual LLM calls recorded
for this development task: **0**. Transport fixtures are engineering checks.
This is an authored calibration probe before an independently grounded HSWM
comparison. It has **no HSWM efficacy arm**, canonical admission or G0/G1 verdict.

Read the [frozen protocol template](protocol.v1.json) and
[research decision](../../../docs/research/HSWM_RELATION_LLM_CALIBRATION_PROTOCOL_2026-09-08.md).
The template is not a completed model/configuration preregistration. Each run
seals the exact protocol, source files and supplied model configuration before
its first request. These are local chronology records, not independent custody.

Three controls receive the same eight authored training examples:

- `ALL_TRAINING_HISTORY`: the model reads every training example at inference.
- `CONSOLIDATED_TEXT_LESSON`: one model call creates a lesson, frozen to disk and
  read back before inference.
- `EXECUTABLE_PROGRAM_LIBRARY`: one model call creates a bounded JSON AST, frozen
  and read back before inference.

All inference arms receive identical grammar/tool instructions and can return
either a UID set or a program. Programs run through a separately implemented
bounded interpreter; arbitrary model code is never executed. This is a local
mechanism comparison, not a reproduction of ExpeL, Voyager, SpeedRunner or RAG.
The same available budget allows up to seven calls per arm. Actual costs differ:
history uses six calls and consolidated arms use seven. No equal-cost inference
is licensed by equal caps. All input/output usage, missing usage and wall times
are retained. No target label or score is fed into subsequent model requests.

The USL bridge uses `connectUsl` against owner fixtures. Each task is read once,
and that observation is shared across arms. Complete native source/identity
bindings remain in the snapshot. As in predecessor profile v3, original role
array order needs the same-read owner metadata; USL alone canonicalizes it.
All 34 USL source pins from predecessor v4 must match an authorized local source
copy. No USL database, live KG setting, final ALFWorld holdout or Python runtime
is used in this runner. Stored actor inputs are experiment evidence, not a
replacement owner database.

## Prepare without a model

Use the existing exact pinned USL source and installed launcher. A current
sibling checkout may have changed; source drift rejects. No dependency install
is needed. Existing output paths always reject.

```bash
USL_STUDY_ROOT=/path/to/exact-pinned-usl-source
"$USL_STUDY_ROOT/node_modules/.bin/tsx" \
  _research/causal_composition/relation_llm_comparison_v1/run.mts \
  --usl-root "$USL_STUDY_ROOT" \
  --output /tmp/hswm-relation-llm-prepare-01.json
```

This produces `PREPARED_NO_MODEL_CALLS`, a hash-chained event journal and actor
inputs. It validates 8 training plus 6 public calibration observations. These
six cases are authored calibration data, not an independently sealed test set.

## Execute with a supplied model endpoint

The current native runner supports an OpenAI-compatible Chat Completions POST
surface. Supply configuration outside the public repository, using an existing
credential **environment name**, not the secret value. For example:

```json
{
  "endpoint": "https://model.example.invalid",
  "modelId": "exact-served-model-id",
  "apiKeyEnv": "HSWM_LLM_API_KEY",
  "tokenLimit": {"field": "max_tokens", "value": 2048},
  "timeoutMs": 60000,
  "decoding": {"temperature": 0, "topP": 1, "seed": 13},
  "identityProof": {"level": "PROVIDER_REPORTED_ID_ONLY"},
  "researchMode": "EXPLORATORY_PROVIDER_IDENTITY_ONLY",
  "preflight": "NONE",
  "expectedProviderVersion": null
}
```

Select the supported token-limit field explicitly (`max_tokens` or
`max_completion_tokens`) and compatible decoding parameters. The model/config
must be chosen before execution; the runner does not adapt them on error.
No native default model, endpoint, credential, retry or automatic CLI fallback
exists. Exact response model-ID mismatch stops and preserves the occurrence.

```bash
"$USL_STUDY_ROOT/node_modules/.bin/tsx" \
  _research/causal_composition/relation_llm_comparison_v1/run.mts \
  --usl-root "$USL_STUDY_ROOT" \
  --run --config /private/path/model-config.json \
  --output /private/path/hswm-relation-llm-attempt-01.json
```

This allows at most **20 generation calls / 40,960 output-token cap** in total,
with a 60-second maximum per request. The fixture full-history preview is about
34 KB; byte bounds do not attest tokenizer/context capacity. All actual usage
is reported separately; missing/invalid usage stays unknown. Human time and
monetary cost are unmeasured, not zero.

Provider-reported IDs, seeds, fingerprints and a model list do not prove fixed
weights or deterministic results. The reusable service additionally supports
declared deployment hashes and an injected verifier for endpoint-bound hashes.
The native CLI wrapper implements neither GET preflight nor that verifier, and
rejects those settings before calling. Identity-only results remain exploratory.
Logged-in Codex CLI is not an automatic substitute: its soft tool isolation and
unenforced decoding/model-identity settings do not meet this transport contract.

Output, journal, actor-input and memory files are created with mode 0600. The
journal records exact request bodies before POST and response bytes as base64,
omitting authentication headers. Failures retain dispatch/unknown-usage counts
and after-run source integrity. Do not publish private provider traces blindly.

`--transport-fixture` is only for a loopback server with reserved model ID
`transport-fixture`. It emits `COMPLETED_TRANSPORT_FIXTURE_NO_LLM` and never a
calibration decision. A fixture score is not a model score.

## Verification

```bash
src/hswm/effect-runtime/node_modules/.bin/tsc \
  -p _research/causal_composition/relation_llm_comparison_v1/tsconfig.json
```

The focused tests are
`tests/effect-runtime/research-pinned-chat.test.ts` and
`tests/effect-runtime/research-relation-comparison.test.ts`. They cover malformed
configuration, identity mismatch, mutation after request sealing, strict response
parsing, common tool instructions, target-label exclusion and independent program
execution. They establish engineering behavior, not learning efficacy.
