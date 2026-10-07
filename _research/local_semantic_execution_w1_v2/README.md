# Full W1 instrument v2

This version implements the six-variant and repeated-sentinel schedule proposed
in the [existing W1 design](../hswm_deep_research_v1/protocol.v1.json). It preserves
the original [128-case/384-request instrument](../local_semantic_execution_v1/README.md)
unchanged. Its implementation and fixture checks do not establish actual model
readiness, learning efficacy, or any CR/FCL completion. The previous negative
model findings remain unchanged.

Each of E0/E1/E2 receives 128 cases × six variants and eight original sentinels
×20 additional repetitions: **928 requests per arm, 2,784 overall**. E3 is an
independent deterministic reference, excluded from model request counts. No
case, transform, or repeat counts as an independent sampled task-world.

The six variants are original, two separately authored paraphrases, consistent
bijective role/field renaming, object-key and role-list reordering, and a
meaning-changing value-binding exchange between `subject.dax` and `context.pel`.
The latter keeps names, role ontology and relation text; its expected table is
recomputed. It is not an invariance test. Both the whole 128-case denominator
and changed-input/answer/intermediate subsets matter; symmetric cases are retained.
The other five variants preserve the authored answers and intermediate labels.

Original frame bytes and mode instructions remain byte-for-byte equal to v1.
The rename variant uses its renamed identifiers in instructions as well as the
relation and frame. Enumeration order changes preserve the explicit role/ordinal
bindings; the ordinal defines semantic order, while array position is presentation.
Labels live in a separate evaluator reference; they never enter model
messages. The pilot stopping rule alone uses evaluator-side expected answers.

Exact transformation bytes, the seed `20261007`, case order, rotated arm order,
sentinel IDs and all request hashes are fixed by the compiled domain and frozen
in `plan.json`. The original block comes first; remaining variant blocks and
within-block cases are deterministically shuffled. The sentinel block follows.
Sentinels are original cases 0/1, 0/4, 0/3, 0/3 for families 0/1/2/3 respectively.
Twenty repeats per arm are compared with their identical original request.
Incorrect but stable sentinels fail readiness; missing/invalid outputs do not
establish stability. E0 probability variation is reported separately. E2's
observable intermediate truth and XOR consistency remain separate from final-bit
accuracy and do not reveal hidden model reasoning.

After the first 384 requests, at least one arm must have 128 valid correct final
answers or execution stops with `ORIGINAL_PILOT_FAILED`. All 2,784 scheduled
entries stay in analysis denominators. This is an explicitly frozen v2 stopping
rule; it does not modify the old original-only protocol. Full readiness requires
one observed-model arm to have 928 valid correct answers, a terminal receipt,
and no sentinel or meaning-preserving-variant bit instability. A fixture run
cannot produce model readiness. Generation is serial, with no retries or repairs;
30 seconds per request and 14,400 seconds for the full block are maximums, not a
promise that every real run will finish. Actual unequal costs remain visible.

## Local preparation and engineering validation

```sh
npm --prefix src/hswm/effect-runtime run build
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime test -- local-semantic-w1-full-domain.test.ts --maxWorkers=1
node --test tests/research/local-semantic-w1-full-analysis.test.mts tests/research/local-semantic-w1-full-instrument.test.mts
node _research/local_semantic_execution_w1_v2/runner.mts prepare /absolute/private/new-w1-full-plan
```

Preparation makes no network or model request. Plan verification pins source
files, compiled modules, lockfile, and actual Node/Effect versions. The published
v1 protocol and deep-research design are inherited by exact hashes. Existing
plans and started/failed runs cannot be overwritten or resumed; preparation requires
a new or empty directory. Execution reserves receipt files before the first HTTP
probe and refuses pre-existing sinks. Use a fresh directory after changes.
Raw responses, serving paths, reference labels and
analysis observations stay in private directories. The HTTP tests use explicit
loopback fixture servers and label their results `FIXTURE_ONLY`.

## Actual model execution prerequisites

The historical Qwen3-4B target and vLLM 0.25.1 wire contract are inherited without
claiming a currently loaded service. Use the existing owner-approved USL project
mapping/transport and DGX wrapper. The missing serving attestation/transport
cannot be inferred from a past receipt or a passing fixture. No real-model call
has been performed by this implementation work.

The original [serving attestation contract](../local_semantic_execution_v1/README.md)
and full validator are reused: checkpoint shards, tokenizer, chat template,
server config/runtime hashes, declared live-engine association, precision and
license, actual Node/Effect versions, served alias and token IDs. The raw artifact
hashes are checked before `/v1/models` and `/tokenize`; no credentials are
accepted in the loopback endpoint. Artifact-to-engine association remains an
operator declaration. No new dependency or external protocol is introduced.

Once that existing execution path is ready:

```sh
HSWM_RESEARCH_RUNTIME_DIST=/absolute/pinned/runtime-dist \
W1_SERVING_ATTESTATION=/absolute/private/serving-attestation.json \
  ~/bin/hswm-run exec NEW_W1_FULL_RUN_ID --profile hswm -- \
  bash _research/local_semantic_execution_w1_v2/launch.sh
node _research/local_semantic_execution_w1_v2/analyze.mts /absolute/private/run /absolute/private/new-analysis.json
```

A model/readout failure directs diagnosis back to W1. W2–W5 cannot use topology,
scale, or more tests as evidence that the original semantic-execution bottleneck
has disappeared. Missing serving setup is an execution dependency; local fixture
qualification only establishes that this diagnostic is ready to receive evidence.
