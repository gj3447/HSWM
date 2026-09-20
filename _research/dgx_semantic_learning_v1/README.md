# DGX native semantic revision experiment

Real model calls execute the existing TypeScript/Effect content-bound durable semantic runtime. The authored binary environment and frozen partitions are pure functions in `domain.mts`; the LLM receives typed local roles, meaning, exceptions and observed training outcomes. This is a bounded research slice with caller-owned observations and reference authorization, not the full HSWM or a learned checkpoint.

The active runner is **protocol v3**: Qwen3-4B on the existing DGX port 8001, 16 trials, six conditions, at most 128 model calls, no retries, temperature zero and JSON Schema output. `launch.sh` imposes a 2,400-second wall limit and samples GPU utilization. The script terminates only its own telemetry process.

Prior v1/v2 sources and source manifests remain under `attempts/`. `attempt-source-map.v1.json` resolves original source paths to preserved bytes where the current instrument has changed. Native source and compiled JS are bound by the manifests. The remote dependency lock differs from the local build lock; full installed-tree identity is not claimed.

Use the repository's existing dependencies:

```sh
npm --prefix src/hswm/effect-runtime run build
npm --prefix src/hswm/effect-runtime run test -- ../../../tests/effect-runtime/dgx-semantic-learning-domain.test.ts ../../../tests/effect-runtime/canonical-atom-v2-llm-semantic-runtime.test.ts --maxWorkers=1
node _research/dgx_semantic_learning_v1/run.mts --protocol
```

For a new run, preserve the new protocol/source pins before inference, stage the exact compiled runtime JS into an isolated `runtime-dist` beneath the research directory on DGX, and verify every staged hash. Use the already installed matching Effect dependency. Check port 8001 `/health` before launch; a health response is only startup readiness, not model quality. Then run on DGX from its source checkout, with a **new** run ID:

```sh
HSWM_RESEARCH_RUNTIME_DIST="$PWD/_research/dgx_semantic_learning_v1/runtime-dist" \
  ~/bin/hswm-run exec NEW_UNIQUE_RUN_ID --profile hswm -- \
  bash _research/dgx_semantic_learning_v1/launch.sh
```

`hswm-run` requires data-01 durability and its resource reserve. It publishes artifacts even after failure. Do not interpret a wrapper receipt's process status as a scientific verdict. Do not change an active runner while its fresh-process workers are still importing it.

`cp -a` preserves internal hard links needed by native journal recovery; plain Node recursive copy does not. The feedback-only condition makes a new native revision with initial meaning and retained observed evidence. `removed` reopens the frozen initial snapshot; `restored` reopens an exact learned snapshot. Canonical equality does not imply identical HTTP requests because executions have fresh IDs.

After completion, retain raw HTTP and canonical stores in the durable archive. Copy the public-safe synthetic output and original receipt into a private analysis directory and produce a new observation artifact:

```sh
node _research/dgx_semantic_learning_v1/analyze.mts PRIVATE_OUTPUT_DIRECTORY NEW_OBSERVATIONS_JSON
```

The analyzer checks every captured request for train/heldout separation and label leakage and reports malformed batches without repair. `graph.mts` builds the separate research ontology from fixed catalogs, observations and reports. It does not call a model or write live KG. The dated `publish.mts` uses a single reviewed bundle digest and the existing registry/collision/anchor/readback publisher.

The completed v3 result is **155/320 before and after semantic revision**, versus **156/320 feedback-only** and **166/320 oracle**. This exact configuration does not establish learning utility. Qualify basic semantic execution before adding optimizer complexity or scale. No recurring schedule has been enabled.
