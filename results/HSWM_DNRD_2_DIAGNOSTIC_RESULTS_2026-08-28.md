# HSWM-DNRD-2 diagnostic result: JUDGMENT_REFUSED

- Date: 2026-08-28
- Experiment: `HSWM-DNRD-2`
- Frozen family: `REPEATED_CONTEXT_TABULAR_ROUTING_MECHANICS_V1`
- Frozen adjudicator status: `JUDGMENT_REFUSED` (exit `2`)
- Preregistered terminal emitted: no
- Scientific status: `UNJUDGED`
- Calls conservatively completed before termination: `3`
- Retry, resume, replacement, or second pulse: forbidden

## Result first

The sole preregistered DNRD-2 occurrence did not reach a mechanics result. The
fixed deployment preflight succeeded, and the first two training calls returned
valid exact response tokens. The third training call returned HTTP `200` but
ended with `finish_reason="length"` at the frozen `64`-token output limit. Its
352-byte content violated the required exact 26-byte response-token contract,
so the live boundary correctly recorded `FINISH_REASON_NOT_STOP` and the runner
formed a three-call inconclusive result in memory.

The executor then hit a deterministic production-path defect while comparing
the durable model-event ledger: it called `.read_bytes()` on the `None` return
value of a validation-only helper. It exited `1` before writing either
`inconclusive.json` or `bundle_index.json`. The original occurrence is therefore
not a complete evidence bundle. Both the active frozen judge and its copied
Source-A closure returned the same `JUDGMENT_REFUSED` result:

```text
bundle is missing required artifact 'candidate.json'
```

This is not a GO, NO-GO, admitted inconclusive, or judge-emitted
`VOID_PROTOCOL` terminal. The singleton is nevertheless permanently consumed
by its durable attempt marker and is operationally closed. It cannot establish
routing persistence, recovery, rollback, derangement sensitivity, replay
fidelity, LLM learning, unseen-context generalization, utility, canonical
Permit, or HSWM efficacy.

## Canonical role and conceptual delta

HSWM's target identity remains one token-native LLM-function macro-neural
network whose evolving hypergraph jointly serves as living harness, world
model, and continuous learner. DNRD-2 was only a bounded projection of one
schema-approved durable integer-routing seam. It was not a separate cognition,
routing, or learning subsystem and was never an HSWM efficacy test.

Relative to DNRD-1, the intended scientific delta was narrow: preserve the
failed raw model response, require a 26-byte token, raise the output ceiling
from 16 to 64 tokens, use exact `finish_reason="stop"`, durably fsync every
model observation, repair real-closure bundle ordering, and then test the same
outcome-bound mechanics under rollback, binding derangement, and fixed-rule
numeric replay. DNRD-2 demonstrated that the first two calls could cross the
stricter live boundary, but it did not complete even one eight-update stream or
any held-out arm comparison. The intended mechanics delta remains unmeasured.

## Frozen identity and chronology

| Binding | Exact value |
|---|---|
| Source A | `0881d92da377ba0b64e8247aa0719d4ad7a97cd0` |
| Source A tree | `6e8b5168b00726a28302d766f4b68634eb901330` |
| Source manifest SHA-256 | `0ba82ba0311dcf6d9e1dc624066545056738ed7465f0a4c0aaec002116c18fbf` |
| Direct-child preregistration B | `3b4d424a3ae0e12d8c77f01315f7b987ec24d44d` |
| Preregistration SHA-256 | `94b376fd1aa07516a3c8e3992228c5aadb25ae03b5e2f71edcb074be53c8ebc2` |
| Ratification statement SHA-256 | `039a4d6e930506f0ed2cdca32ac338da1e3559f8e9f8590c32b2d266dc7021ab` |
| Ratification time | `1787878695` |
| First eligible Quicknet round | `31692077` |
| Round time | `1787879595` |
| Pulse binding self-receipt | `bc643acb4e269f6dce4adb6f9e8836e420672a3010cd652a3ca978c3afe6507d` |
| Attempt marker self-receipt | `80bc6b29713d2c349658f99d96b12197acc21478a776faefe9adc46189dc47c0` |

The user supplied the exact preregistration hash and statement template with
display line wrapping. The external receipt records the same conservative
DNRD-1 interpretation,
`USER_EXPLICIT_RATIFICATION_INTENT_CANONICAL_TEMPLATE_WHITESPACE_NORMALIZED`,
and does not claim byte-exact attestation of the displayed multiline message.
The pinned verifier fetched and cryptographically verified the first eligible
Quicknet round after the 900-second gate. The marker was fsynced before test
material generation and remains the single consumed occurrence.

## Observed execution

The frozen three-call non-generation preflight retained:

- served model `qwen3.6-35b-a3b`;
- model root `Qwen/Qwen3.6-35B-A3B-FP8`;
- maximum model length `32768`;
- vLLM `0.25.1`;
- exactly three non-generation HTTP calls and zero generation calls in the
  deployment receipt; and
- tokenizer count `5` for `token-ffffffffffffffffffff`.

The durable model ledger contains six rows over ordinals 1 through 3:

| Ordinal | Observed | Accepted | Rejected | Result |
|---:|---:|---:|---:|---|
| 1 | 1 | 1 | 0 | exact token accepted; 160 input / 22 output tokens |
| 2 | 1 | 1 | 0 | exact token accepted; 161 input / 22 output tokens |
| 3 | 1 | 0 | 1 | HTTP 200; `finish_reason=length`; 168 input / 64 output tokens |

The third raw response is retained as 986 bytes with SHA-256
`3158022dcae6dbf6b4fd2cc6f6c0c93a993e6f4e17eb57791ecbe4d5ca0d1c61`.
The runner ledger contains the two accepted prefixes and has SHA-256
`5d377865ed297521d9404608f614914fffc842a316e8076c518f0aaea3b4d73f`;
the six-row model ledger SHA-256 is
`b16f1c9b3aeed04ed618209c7e95bab40c6e272cba3b7ef43e3f90aee4321d31`.
There were no retries and no client cache hits.

The two retained runner rows include local scorer observations and structural
credit receipts, but the incomplete, unindexed occurrence does not admit them
as evidence of the preregistered durable mechanics. No full training stream,
fresh W1 recovery comparison, W0 rollback, four-arm held-out evaluation,
binding derangement, or fixed-rule replay completed.

## Deterministic executor failure

The frozen production path writes and fsyncs each model event directly to
`model_events.jsonl`. After the runner returned, the executor intended to
validate that durable file and compare its bytes with the in-memory sequence.
The relevant code instead evaluated:

```python
retained_model_bytes = _plain_file(...).read_bytes()
```

`_plain_file` is a validator with return type `None`; it does not return the
path. Consequently every production occurrence that reaches this line raises:

```text
AttributeError: 'NoneType' object has no attribute 'read_bytes'
```

The defect was introduced in Source-A ancestor `17be139d...`. Existing tests
exercised the `model_event_ledger_path=None` dependency-injection branch and the
durable ledger in isolation, but not the production-style branch through final
artifact serialization. This is another direct example of why more harness
tests are not scientific progress unless they cover the actual evidence path.

## Frozen-judge refusal and second schema defect

The original tree has neither `candidate.json` nor `inconclusive.json`; the
judge therefore refuses before it can emit a preregistered terminal. The two
independent invocations used byte-identical judge source
`722aebe1da731a2845e5967b6e59189a35c5f69635c78710d6953911ed25de08`
and byte-identical output. Exit `2` means refusal, not a valid negative result.

The lost in-memory runner value is deterministically reconstructible from the
retained ledgers as a three-call `LiveBoundaryError` inconclusive object with
SHA-256 `a4d44e52ba7e2f3360858995d8cc9db96fcbe5903cb20a48781b9d54a67cb554`.
It was not written to the original occurrence and is not an admitted artifact.
Moreover, a second frozen mismatch blocks even a copied forensic replay from
becoming an official inconclusive bundle: `live.py` omits `chat_config` from
accepted events, while the frozen judge requires it. Both accepted rows exhibit
that mismatch. Adding fields, a terminal object, or an index after observation
would be a prohibited repair or replacement.

## Preservation and data-quality audit

The untouched incomplete occurrence contains 4,114 regular files in 443
directories, totaling 58,095,230 file bytes. It contains no symlinks or special
files. A DNRD-1-style canonical file-row commitment over the actual tree is
`c9fe2253bd16ab58011d535b4cae672d553675c3852c69291d1f0733a62a8fc9`.
This records the failed tree and is explicitly not a replacement bundle index.

A separate external non-repair projection contains only the reconstructible
lost runner object and a content-addressed forensic receipt. Its directory is:

```text
/home/lagyeongjun/.local/share/hswm/dnrd/HSWM-DNRD-2/occurrence-1-non-repair-forensic-projection
```

The projection receipt self-hash is
`cf38724e945df1a348bb9b3bfae60ca86cffb491c94d121e7414b9b5502177cf`
and its file SHA-256 is
`7975a8b4641d899753e2889bf2f1b500242821142793d0156c5616d9c17584c0`.
It does not copy, complete, index, or repair the original occurrence.

## Scientific interpretation

DNRD-2 is a material negative instrument-readiness result, not a result about
the proposed routing mechanics. Raising the output ceiling from 16 to 64
allowed two exact completions but did not make unconstrained token echo reliable:
the third response consumed the entire ceiling. The separate serialization and
judge-schema failures show that the tested end-to-end evidence path was still
not closed despite the large test suite.

The strongest defensible statement is therefore: one correctly ratified and
future-pulse-bound singleton reached three generation requests, retained two
accepted training prefixes and one exact non-stop rejection, then became
unjudgeable because the frozen instrument failed before terminal sealing. The
scientific question remains unanswered.

## Required successor gate

DNRD-2 is closed. A successor must be separately frozen and ratified; it cannot
be called a retry, resume, repair, or replacement. Before another live singleton:

1. fix the durable-ledger path validation/read bug and execute that exact branch
   through terminal write, full real-closure index, and frozen-judge admission;
2. make live-event producer and judge schemas identical for observed, accepted,
   rejected, and ambiguous events, with accepted-prefix inconclusive coverage;
3. run a production-shaped, no-network replay that includes the actual 4,050-file
   closure and every finalization branch rather than reduced fixtures alone;
4. replace unconstrained token echo with a preregistered server-enforced exact
   response grammar or an equally explicit nuisance-control design, and qualify
   it on disjoint prompts before freezing measurement;
5. make absence of both terminal artifacts produce one content-addressed
   conservative adjudication record instead of an unreceipted refusal; and
6. keep the mechanics question and all nonclaims unchanged unless a new design
   explicitly preregisters a different scientific target.

Only after those gates pass can a new singleton evaluate persistence,
actuation, recovery, rollback, derangement, and replay. Even a later mechanics
GO would remain below LLM learning, unseen-context generalization, utility, and
HSWM continuous-learning efficacy.

## Artifacts

- Raw frozen-judge refusal: [`dnrd_2_judgment_2026-08-28.json`](raw/dnrd_2_judgment_2026-08-28.json)
- Evidence receipt: [`EVIDENCE_HSWM_DNRD_2_ADJUDICATION_REFUSAL_2026-08-28.json`](../evidence/EVIDENCE_HSWM_DNRD_2_ADJUDICATION_REFUSAL_2026-08-28.json)
- External original occurrence:
  `/home/lagyeongjun/.local/share/hswm/dnrd/HSWM-DNRD-2/occurrence-1-evidence`
- External non-repair projection:
  `/home/lagyeongjun/.local/share/hswm/dnrd/HSWM-DNRD-2/occurrence-1-non-repair-forensic-projection`
