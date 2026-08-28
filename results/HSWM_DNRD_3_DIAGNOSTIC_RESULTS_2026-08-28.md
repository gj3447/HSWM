# HSWM-DNRD-3 diagnostic result: VOID_PROTOCOL

- Date: 2026-08-28
- Experiment: `HSWM-DNRD-3`
- Frozen family: `REPEATED_CONTEXT_TABULAR_ROUTING_MECHANICS_V2`
- Executor retained artifact: `inconclusive.json` (unadmitted)
- Independent frozen-judge terminal: `VOID_PROTOCOL` (exit `0`)
- Scientific status: `UNJUDGED`
- Model calls recorded by the live boundary: `128`
- Retry, resume, repair, replacement, or second pulse: forbidden

## Result first

The sole preregistered DNRD-3 occurrence completed all 128 planned live model
requests at the network boundary: 32 training calls and 96 heldout calls. The
durable model ledger contains 128 observed and 128 accepted events, the runner
ledger contains 128 pre-dispatch readouts and 128 completed-call events, and the
client recorded zero cache hits and no retry. This is a much later operational
reach than DNRD-1 or DNRD-2, but it did not produce a mechanics result.

After the final call, the frozen runner reread the durable model ledger and
required every accepted response content string to be byte-identical to compact
canonical JSON. All 128 responses were valid one-property JSON objects accepted
by the live schema boundary with exact `finish_reason="stop"`, but the server
serialized each object over three indented lines. The end-of-run validator
therefore raised:

```text
ValueError: completion content is not exact structured response
```

The executor retained a 128-call `inconclusive.json` and a self-addressed bundle
index. It did not create a candidate, bridge-state evidence, or raw bridge-mount
closure. The independent frozen judge then failed structural verification and
emitted `VOID_PROTOCOL` before interpreting the terminal or ledgers because the
copied 4,050-file Node runtime closure contains one manifest-pinned zero-byte
regular file:

```text
bridge_runtime_closure/node_modules/@standard-schema/spec/dist/index.js
```

The exact file was already zero bytes in the frozen runtime source and is
committed in the runtime manifest with the SHA-256 of empty bytes. The executor
accepted and copied it exactly; the judge allowed empty indexed files only for
the two event ledgers. This is a frozen producer/consumer contract mismatch,
not evidence of post-copy truncation.

The authoritative terminal is consequently `VOID_PROTOCOL` with scientific
status `UNJUDGED`. The retained 128-call operational trace is not admitted
mechanics evidence. It establishes no persistence, recovery, rollback,
derangement sensitivity, replay fidelity, LLM learning, unseen-context
generalization, utility, HSWM efficacy, topology result, admission, or canonical
Permit.

## Canonical role and evidence boundary

HSWM's target identity remains one token-native LLM-function macro-neural
network whose evolving hypergraph jointly acts as living harness, world model,
and continuous learner. DNRD-3 was only a bounded projection of one proposed
schema-approved durable routing-disposition transition. It was not a separate
router, cognition system, learner, or world model.

The frozen projection assigned exactly one schema-relative responsibility owner
to each local atom and used typed references, provenance-bound transitions, and
response-independent scorer-outcome records. The bridge, repository ontology,
event ledgers, and judge are bounded interfaces and evidence instruments. Their
growth, test count, or operational reach is not itself HSWM progress.

Target identity and current evidence therefore remain sharply separated:

- target: an outcome-bound canonical revision must causally change a later
  token-native traversal or transition inside the one evolving HSWM;
- DNRD-3 question: whether one finite integer-routing projection persisted,
  actuated pre-model route selection, survived rollback/recovery, changed under
  binding derangement, and replayed from retained update records; and
- current evidence: the occurrence failed instrument admission before the
  frozen judge could evaluate any of those contrasts.

## Intended conceptual delta

Relative to DNRD-1 and DNRD-2, DNRD-3 moved the proposed cause upstream of the
model response. It bound each numeric update to a locally declared scorer
outcome, recorded heldout route selection before model dispatch, compared FULL
against exact W0 rollback and a matched context-binding derangement, and made a
no-model fixed-rule replay of the same retained update records an admission
gate. The model response was intended only as a post-route provenance/nuisance
channel.

The fixed finite rule required every one of four streams to show FULL positive
reward on 8/8 probes, W0 on 4/8, DERANGED on at most 4/8, FULL differing from W0
on exactly 4/8 and from DERANGED on at least 4/8, together with recovery,
rollback, replay, parity, leakage, and evidence-closure gates. That rule was not
adjudicated. No result count is reconstructed from the partial artifacts.

## Frozen identity and chronology

| Binding | Exact value |
|---|---|
| Source A | `788f4d670507c078e053a1275bb1c0652a1ec07d` |
| Source A tree | `f396bd6015679080351937505c6c4c06ca43335a` |
| Source freeze time | `1787884945` |
| Source manifest SHA-256 | `655ea553bcb0a1e502952e360274ee2a39761e4838c7dd5d5e96549c476022bb` |
| Source-A CI run | `33136718466` (`success`) |
| Source-A CI receipt self-hash | `426c7d8fae598ba9b2c258eaf4f9b59330ccf2f4c4e213a4934e86ccc3b7789c` |
| Direct-child preregistration B | `5ca0bf0c2cba86812ef017100cbcc698affe3b23` |
| Preregistration SHA-256 | `2bcbe110cac8b69b3889761c05635a8af62b09a443e2a10a2a4a62aad0791226` |
| Ratification statement SHA-256 | `2785253d1700bc91b07a476487ef59ee4188c00aad815ced950b541236d46820` |
| Ratification time | `1787890314` |
| Minimum eligible pulse time | `1787891214` |
| First eligible Quicknet round | `31695950` |
| Quicknet round time | `1787891214` |
| Pulse verified time | `1787891239` |
| Pulse binding self-receipt | `7652742294bd928ec2de465d3afbf84582c28e134b4d3877710719cd75d10986` |
| Attempt marker self-receipt | `92dcce41f6df4c5695f282ef3ab6769dbf0a54639bd787900ae3d80cc0642f47` |
| Runtime configuration SHA-256 | `8700134a6d397dfc6fe4011523c165d8166fe26401a7aba06aac874296b2ce4a` |

The user supplied the exact preregistration hash and statement template with
display line wrapping. The external receipt records
`USER_EXPLICIT_RATIFICATION_INTENT_CANONICAL_TEMPLATE_WHITESPACE_NORMALIZED`;
it does not claim byte-exact attestation of the displayed multiline message.
The pinned verifier fetched and cryptographically verified the first eligible
Quicknet round at the exact 900-second threshold. The durable marker was written
before generation and permanently consumes this occurrence.

## Model and call boundary

The fixed deployment preflight retained:

- served model `qwen3.6-35b-a3b`;
- model root `Qwen/Qwen3.6-35B-A3B-FP8`;
- model maximum length `32768`;
- vLLM `0.25.1`;
- exactly three non-generation HTTP calls and zero generation calls in the
  preflight receipt; and
- tokenizer count `10` for the fixed preflight prompt.

The served ID and root do not attest exact weight bytes, backend determinism, or
provider-cache independence. The occurrence's generation calls are evidenced
separately by the two durable ledgers:

| Ledger fact | Count |
|---|---:|
| Training ordinals | 32 |
| Heldout ordinals | 96 |
| Logical/dispatched ordinals | 128 |
| Runner `PRE_DISPATCH_READOUT` rows | 128 |
| Runner `COMPLETED_CALL` rows | 128 |
| Model `CHAT_COMPLETION_OBSERVED` rows | 128 |
| Model `CHAT_COMPLETION_ACCEPTED` rows | 128 |
| Accepted responses with `finish_reason="stop"` | 128 |
| Client cache hits | 0 |
| Accepted prompt tokens | 17,515 |
| Accepted completion tokens | 4,027 |

Every accepted content string was 52 UTF-8 bytes and parsed as one
`response_token` object whose token passed the live dynamic-enum/schema check.
None was the frozen compact canonical serialization; each used newline and
indentation whitespace. Server-enforced JSON Schema constrained the data model,
not its lexical byte representation. The disjoint three-call qualification had
tested semantic structured-output compatibility, but it had not established
compact canonical serialization. Its exact summary SHA-256 is
`19bfbeaecf8d9275f31a04d28601c37f58d8832f58a4da084deb85dc5b056301`.

The runner ledger is 606,516 bytes with SHA-256
`1f6aaa5e473a9f1c90f5bd0df0c29f5e2bff457c82e917f32ec1eb357f3b2c5a`.
The model ledger is 426,856 bytes with SHA-256
`f3f69a66a62847a9a106c7eb93f6f40de0d4d83a440dc3ddb40910931cbb9503`.
These are provenance-bound operational artifacts, not admitted causal results.

## Deterministic runner failure

Frozen runner source SHA-256
`b56790b3cf67a7f2597f5e1e1d9637fd9f9838a7f9aa6fe8269e8f4357e16350`
validated the durable model ledger after all calls. At source line 1422 it
compared the original content with `canonical_json(structured)`, and line 1424
raised the exact `ValueError` above. The canonical error envelope

```json
{"message":"completion content is not exact structured response","type":"ValueError"}
```

has SHA-256
`60a4e159eb6a2158f48808fb618a7c69bc339c1d57e46bc075cda46d0488daf6`,
exactly matching the retained terminal's `failure_digest`. The executor then
wrote `inconclusive.json` (266 bytes, SHA-256
`5288e40501acf417d7aea031224532a818aa9fa98a78f0ec48ab64ac62b33f94`)
and `bundle_index.json` before exiting `0`.

The runner failure occurred before candidate construction and before export of
`bridge_state_evidence.json` and `bridge_mount_closure.json`. The mutable bridge
state directory and completed runner rows remain outside the missing frozen
candidate closure. Post-hoc route aggregation would bypass the preregistered
construction and judgment path, so it is intentionally not promoted.

## Independent structural VOID

The preservation record reports one independent frozen-judge invocation. Frozen
judge source SHA-256
`0d5bbde0c4b0af1e2934f91251fe99e662018661b4f011b1fbb84a4e6fa57fc7`
returned exit `0` with terminal `VOID_PROTOCOL`, authority
`INCOMPLETE_OR_INVALID_EVIDENCE_BUNDLE_NOT_VERIFIED`, and this exact reason:

```text
bundle artifact 'bridge_runtime_closure/node_modules/@standard-schema/spec/dist/index.js' is empty
```

The runtime manifest has 56 compiled files and 3,994 external-package files.
The Source-A runtime and copied closure each contain all 4,050 files totaling
55,496,654 bytes, with owner-read-only file mode `0400`. Their only empty file
is the same `@standard-schema/spec` v1.1.0 path, committed as:

```text
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

The executor's manifest validator required a nonempty file list, safe paths,
valid hashes, exact source hashes, and exact copied hashes, but it did not
forbid an individual empty regular file. Its bundle index therefore contains
4,118 artifact rows totaling 59,222,786 bytes and has self-receipt
`ab2e3b67aa8651e585764da1499813888c5500777850aab03b554a31bfa682f5`.
The evidence tree contains 4,119 regular files including the unindexed index
itself, 443 descendant directories, no symlinks or special files, and exactly
one zero-byte file.

The judge's generic bundle-file validator instead allowed empty bytes only for
`runner_events.jsonl` and `model_events.jsonl`. It failed while validating the
index and never reached the retained inconclusive-ledger semantics. The raw
index's existence, coverage, and self-hash cannot override that frozen
admission failure. No post-observation repair, removal, reindex, or replacement
was performed or is claimed. Same-UID adversarial immutability is not proven by
the retained tree.

## Scientific interpretation

DNRD-3 is a material negative instrument-readiness result, not a result about
the proposed causal routing mechanics. It falsified two assumptions in the
frozen end-to-end evidence path:

1. strict JSON Schema compatibility does not imply a unique compact JSON byte
   serialization; and
2. a runtime producer that admits hash-pinned empty regular files is
   incompatible with a consumer that rejects every such artifact.

The strongest defensible statement is therefore: one correctly frozen,
exact-hash-ratified, future-pulse-bound singleton recorded all 128 planned
network calls without a client retry, then produced an unverified inconclusive
artifact and was conservatively judged `VOID_PROTOCOL` because the evidence
contracts were inconsistent. The scientific question remains unanswered.

The fact that more operational scaffolding survived than in DNRD-1/2 is not a
positive HSWM result. It only localizes the remaining defects later in the
measurement path.

## Required successor gate

DNRD-3 is closed and cannot be rehabilitated. A successor must be a new design,
not a retry, repair, resume, replacement, or second pulse. Before any new live
singleton it must:

1. commit both raw response bytes and a separately canonicalized parsed object,
   validating semantic schema/candidate membership without assuming server
   whitespace; or preregister and qualify a genuinely byte-canonical server
   contract;
2. define one shared producer/judge rule for manifest-pinned zero-byte regular
   files, then exercise the actual 4,050-file closure including this path;
3. replay the complete production finalization path with 128 pretty-serialized
   accepted responses, including candidate, inconclusive, and structural-void
   branches, before source freeze;
4. preserve raw bridge-state evidence and terminal semantics in a transaction
   whose failure cannot silently turn bounded operational bytes into a causal
   result;
5. keep the same outcome-independence, W0/FULL/DERANGED, no-model replay, leakage,
   call-accounting, and no-promotion boundaries unless a new preregistration
   explicitly changes the scientific question; and
6. obtain a fresh public pre-observation chronology and use a newly generated
   singleton identity. DNRD-3's retained bytes remain immutable and consumed.

Only after those gates pass may a successor adjudicate persistence, actuation,
recovery, rollback, derangement, and replay. Even a later mechanics GO remains
strictly below LLM learning, unseen-context generalization, utility, and HSWM
continuous-learning efficacy.

## Artifacts

- Canonicalized raw frozen judgment:
  [`dnrd_3_judgment_2026-08-28.json`](raw/dnrd_3_judgment_2026-08-28.json)
- Content-addressed evidence projection:
  [`EVIDENCE_HSWM_DNRD_3_ADJUDICATION_2026-08-28.json`](../evidence/EVIDENCE_HSWM_DNRD_3_ADJUDICATION_2026-08-28.json)
- External preserved occurrence (no post-observation repair asserted or
  performed):
  `/home/lagyeongjun/.local/share/hswm/dnrd/HSWM-DNRD-3/occurrence-1-evidence`
- External frozen-judge output:
  `/home/lagyeongjun/.local/share/hswm/dnrd/HSWM-DNRD-3/occurrence-1-judgment.json`

No model response body, private fixture, mutable bridge state, credential, or
unlicensed runtime dependency is copied into the repository by this result
record.
