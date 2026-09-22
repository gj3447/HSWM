# W1: original 128-case local semantic execution instrument

**Status on 2026-09-22: offline-qualified execution instrument; zero new real-model requests.**
This advances the E01/E02 instrument, not E03 readiness, learning efficacy or CR/FCL closure.
HSWM remains one AI whose Semantic Weight hypergraph is its state and whose local LLM
functions perform computation. This research driver supplies a fixed local relation frame;
it does not implement a new subsystem or claim that a fixture is a cognition-bearing graph.

Engineering verification passed: native build, full type/boundary checks, five focused
domain tests and three HTTP fixture integration tests. The HSWM development workflow also
selected and passed 55 existing adaptive-runtime tests; those checks do not test this new
instrument by themselves. The integration checks inject missing logprobs, malformed values,
HTTP/transport failures, absent usage, terminal-record loss and changed request/response bytes.
The actual local Node version is 24.20.0 versus the package declaration 24.13.0; each prepared
plan records the actual version rather than claiming equality.

The conceptual change from the [2026-09-21 Jev experiment](../../results/HSWM_JEV_PRINCIPLES_2026-09-21.md)
is to isolate correct-relation execution before trying another learner. All four original
families and all 32 bit patterns are tested in each of three modes. The previous 27/48
oracle-direct result, zero semantic-field changes in four revisions, and equal learned /
evidence-only request bytes remain negative findings with their original scope.

| Mode | Output | Scoring |
| --- | --- | --- |
| E0 | One token; candidate logprobs | Existing strict binary readout; missing candidate is a refusal |
| E1 | `{"answer":0}` | Final bit; no requested probability or confidence-consistency gate |
| E2 | `{"base":0,"context_flip":0,"exception_flip":0,"answer":0}` | Final bit, intermediate truth and XOR consistency reported separately |

An identical relation, ordered typed roles, empty prior-evidence collection, and input
fields go to all three arms. Only output instructions/schema/cap differ. The field meanings
and precise oracle text are inherited from the old authored fixture; its context effect is
fully specified here. Gold answers are evaluator-only, outside model-visible messages.
Case identifiers are not sent. No parser repair, retry, answer extraction or successful-only
denominator is allowed. A complete block has **384 generation requests**. This is an
original-serialization diagnostic: the six transforms and sentinel repetitions required by
the [full W1 protocol](../hswm_deep_research_v1/protocol.v1.json) still total **2,784 requests**
and are not implemented by this block. Even 384/384 correct would not discharge E03.

The historical target is `Qwen/Qwen3-4B@1cfa9a7208912126459214e8b04321603b3df60c`,
served as `qwen3-4b-real`. Its old tokenizer and 4B server artifact digests were not separately
attested. Fresh serving/artifact evidence is required before a real run. On the current
checkout host, local port 8001 refused connection, no local GPU/model service or `hswm-run`
was found, and a bounded noninteractive SSH probe to documented alias `dgx` timed out before
authentication. Remote availability is **unverified**. An old successful receipt does not
establish current availability. No download, server launch or real-model request occurred.
Installed `hf` 1.29.0 returned the exact target revision through a read-only metadata request;
its requested card metadata was empty. This confirms the Hub revision, not local tensor
availability, model license verification, or loaded-engine identity.

## Files and execution

- Pure fixture/parser: `src/hswm/effect-runtime/src/local-semantic-execution-domain.ts`.
- `protocol.v1.json`: population, modes, budgets, model target and analysis policy.
- `runner.mts`: prepare exact requests, verify source/compiled bytes, preflight, append HTTP records.
- `analyze.mts`: replay raw bytes, enforce hashes/coverage and produce private descriptive analysis.
- `graph.mts`: source-bound engineering KG projection; contains no observed model records.

Build and qualify locally, without a model:

```sh
npm --prefix src/hswm/effect-runtime run build
npm --prefix src/hswm/effect-runtime run test -- ../../../tests/effect-runtime/local-semantic-execution-domain.test.ts --maxWorkers=1
node --test tests/research/local-semantic-execution-instrument.test.mts
```

Use a private, absolute new output directory for an offline request compilation:

```sh
node _research/local_semantic_execution_v1/runner.mts prepare /absolute/private/w1-plan
```

`plan.json` binds 128 frames, 384 exact request bodies, expected-table digest, source files,
compiled modules, lockfile, actual Node and Effect versions. `reference.json` is separate
evaluator custody. `prepare` does not contact a server. The generated plan is not a complete
model execution freeze until serving preflight succeeds. Source drift requires a fresh
directory; existing records cannot be overwritten or resumed as though uninterrupted.

On an accessible DGX, use the documented wrapper and the exact isolated runtime build:

```sh
HSWM_RESEARCH_RUNTIME_DIST=/absolute/pinned/runtime-dist \
W1_SERVING_ATTESTATION=/absolute/private/serving-attestation.json \
  ~/bin/hswm-run exec NEW_W1_RUN_ID --profile hswm -- \
  bash _research/local_semantic_execution_v1/launch.sh
```

Do not invent `HSWM_EXECUTION_TIER` or bypass missing wrapper preflight. The launcher prepares
inside the wrapper's output root, then checks a local serving attestation, `/v1/models`, and
`/tokenize` for both candidate IDs. It persists a freeze before generation, caps each call
at 30 seconds and the serial generation block at 1,800 seconds, and makes no retries.
Preflight requests/time are recorded separately. A failed preflight cannot become model
evidence. A new run requires a new run ID/directory.

The private serving-attestation JSON has these fields:

```json
{
  "schema_version": "hswm-local-semantic-serving-attestation/v1",
  "authority_class": "LOCAL_OPERATOR_DECLARATION",
  "base_url": "http://127.0.0.1:8001",
  "repository": "Qwen/Qwen3-4B",
  "revision": "1cfa9a7208912126459214e8b04321603b3df60c",
  "served_name": "qwen3-4b-real",
  "vllm_version": "0.25.1",
  "node_version": "REPLACE_WITH_ACTUAL_PINNED_VERSION",
  "effect_version": "3.22.1",
  "precision": "REPLACE_WITH_ACTUAL_LOADED_PRECISION",
  "model_license": "REPLACE_WITH_VERIFIED_LICENSE",
  "serving_evidence_note": "REPLACE_WITH_SOURCE_OF_ACTIVE_ENGINE_AND_CONFIG_ASSOCIATION",
  "checkpoint_set_complete": true,
  "artifacts": []
}
```

The example is intentionally incomplete. `artifacts` must contain `{role,path,sha256}`
for every checkpoint shard and applicable tokenizer file, the actual chat template,
server configuration and server-runtime artifact/manifest. Required roles are `checkpoint`,
`tokenizer`, `chat_template`, `server_config`, `server_runtime`; paths must be absolute and
every digest is checked by streaming the local file. A checkpoint revision alone is not a
tensor-byte verification. The complete shard set and live-engine association remain explicit
operator declarations; this is not hardware attestation or proof that a served name uniquely
identifies loaded weights. Mid-run hot reload/configuration drift is not independently
detected. No secrets belong in the configuration record or published KG.
The dependency pin covers the lockfile, compiled modules and actual Effect/Node versions,
not every installed dependency byte. Do not label that stronger reproducibility claim proved.

Analyze saved evidence without a model call:

```sh
node _research/local_semantic_execution_v1/analyze.mts \
  /absolute/private/w1-run /absolute/private/w1-analysis.json
```

Every arm retains 128 scheduled cases even after wall-time termination or a crash. The
analysis requires a matching terminal receipt to call the census complete and distinguishes
unattempted cases, persisted intents with no completion, transport
failures, HTTP errors, refusals, and valid wrong answers. Intents are recorded before send;
a crash between those operations makes actual server receipt unknown. Usage missing from
the server remains `UNREPORTED`, including reasoning tokens when absent. Read tokens are
an uninstrumented part of prompt tokens. No update or retry calls exist in this protocol.
Latency includes cache/scheduling effects; no energy attribution, repeatability, calibration
or equal-cost superiority claim follows. E0 reports disagreement between emitted token and
conditional-logprob readout separately. E2 is an observable output contract, not hidden
model reasoning.

The raw traces, detailed analysis and serving paths stay private. Review aggregates before
making a dated research result and content-addressed receipt. Current fixture transport tests
are engineering evidence only and do not need an F1_R8 research-result entry.

## Official protocol reference

The HTTP adapter uses the exact official vLLM v0.25.1
[chat-completion protocol](https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/entrypoints/openai/chat_completion/protocol.py)
and [tokenization protocol](https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/entrypoints/serve/tokenize/protocol.py)
(Apache-2.0), reviewed 2026-09-22. `allowed_token_ids` and template kwargs are vendor
extensions; they are not a graph standard. No new package or model was installed.
The existing validation graph remains a structural record contract, and this instrument's
engineering KG snapshot must not be mistaken for populated observed validation records.
