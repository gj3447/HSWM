# H3-B3 V5 development certificate refusal — 2026-07-20

Status: **EFFICACY REFUSED; FRESH NOT OPENED**.

This is the first admissible efficacy result for the H3-B3 confirmatory track.
It is not a harness refusal.  The V5 evidence-production harness completed,
both development certificates ran under the frozen policy, and both refused.

The tested claim was deliberately narrow:

> B3 K2 retrieves gold evidence because two evidence-bound typed relations
> compose, beyond what the matched B3 K1 readout can retrieve.

That claim is not supported on either development certificate split.

## Frozen evidence chain

- V5 manifest SHA-256:
  `9e323caa20cdcedcdb7d400889801a59dd0b0603a8ccb8eb161f2da326d6f144`.
- Development extraction JSONL SHA-256:
  `7cb1dcf65548ac9aeace33277478e0cda0dc540cfc0ae77933921a1e06899192`.
- Extraction CLOSE receipt SHA-256:
  `ad5c7529d2bc1958fee11a67525fbc4c5eda4616a36d0633b2bacf65fd7c1421`.
- Development embedding NPZ SHA-256:
  `f0410cd2637233a04c126088d9772b35cd8278a0900ff025379832676956d291`.
- Embedding CLOSE receipt SHA-256:
  `3dd61832afe5fcc95affd3cdc94a5245204450b170c633331060dae0696607e6`.
- Development report SHA-256:
  `8cc7b3b04295ceee26f210dc15201d325e258a4f415a1d1a09a2c5381f748896`.

The extraction ran once over all 3,599 sources: 3,599 STARTs, 3,599
FINALIZEs, 3,599 endpoint calls, zero unmatched STARTs, zero ERRORs, zero
retries, and zero attempt-cap terminals.  Terminal outcomes were 1,671
`success`, 1,392 `partial`, and 536 `quarantined`.  The guarded BGE-M3 run
produced 3,999 finite normalized 1,024-dimensional vectors; maximum norm error
was `5.959501e-08`.

## Development certificate result

Each certificate contains 100 queries and uses relation/evidence components as
the inference unit.  The frozen primary margins were `+0.02` nDCG@10 and
`+0.03` ASR@10 with cluster-CI lower bound strictly above zero.

| dataset | B3 K2 - matched B3 K1 nDCG@10 | B3 K2 - matched B3 K1 ASR@10 | depth-2 first-gold queries | safety | verdict |
|---|---:|---:|---:|---|---|
| MuSiQue | `0.000000`, CI `[0, 0]` | `0.000000`, CI `[0, 0]` | `0 / 10 required` | PASS | REFUSED |
| 2Wiki | `0.000000`, CI `[0, 0]` | `0.000000`, CI `[0, 0]` | `0 / 10 required` | PASS | REFUSED |

The equality is stronger than a metric tie: for both datasets the B3 K2 and
matched B3 K1 score-array SHA-256 digests are bit-identical.

- MuSiQue K1/K2 digest:
  `e3b2fed36b14313c799b2ac510cfa273158931f86387452ec6dc0c4b53c437f4`.
- 2Wiki K1/K2 digest:
  `0fbf6c9b9d10d4dd4e809b2aa5e1fa9af8de60d82fcfbc27de55f9313284f96f`.

No promoted depth-two path was observed, no wrong depth-two path was observed,
and no receipt violation occurred.  The result is therefore not a noisy miss
around the threshold; the proposed second hop contributed exactly nothing on
the certificate queries.

## Comparator and mechanism diagnostics

### MuSiQue

- B3 K2: nDCG@10 `0.584147`, ASR@10 `0.16`.
- Against B1 K2: nDCG `-0.008904`, ASR `-0.04`.
- Against strongest static cosine: nDCG `0.000000`, ASR `0.000000`.
- B3 apply coverage: `0.05`; fallback rate: `0.95`.
- Typed arcs: 81 from 4,254 verified n-ary observations; 913 title-fallback
  arcs were correctly excluded from the typed kernel.

### 2Wiki

- B3 K2: nDCG@10 `0.726541`, ASR@10 `0.15`.
- Against B1 K2: nDCG `-0.081181`, ASR `-0.06`.
- Against strongest static cosine: nDCG `+0.047829`, ASR `+0.06`, but both
  cluster CIs have lower bound exactly zero.
- B3 apply coverage: `0.535`; fallback rate: `0.465`.
- Typed arcs: 308 from 3,100 verified n-ary observations; 838 title-fallback
  arcs were correctly excluded from the typed kernel.

The positive 2Wiki contrast against cosine is real as a point estimate, but it
cannot support the composition claim: B3 K1 has the exact same scores.  At
most it is evidence for a dataset-specific one-hop typed reweighting effect.

Both graph safety gates passed.  Maximum admitted shared-join document
frequency was 5, largest weak-component fractions were `0.004298` and
`0.003987`, and no fanout or join-hub trip leaked a non-static score.  The
safety engineering therefore did its job while the efficacy mechanism failed.

## Decision

The preregistered kill condition applies:

> K2 does not beat matched K1: the composition claim dies even if B3 beats
> cosine.

No certificate transition was written.  The fresh directory and fresh
artifacts remain absent and unauthorized.  The deployed development policy is
the static floor (`mu=0`) for both datasets.

This refusal does **not** erase the previously measured value of HSWM as an
evidence-preserving World Compiler, auditable graded supersession substrate, or
certified fail-closed readout harness.  It does rule out calling the current
B3 readout an empirically demonstrated two-hop "smart hypergraph."

Any successor must be a new preregistered experiment.  The legitimate next
step is development-only mechanism diagnosis of why `h3_local_pass_queries=0`
and why K2/K1 are bit-identical: distinguish compiler graph sparsity, claim-
continuity reachability, and query-compatibility gating before changing the
extractor, ontology, or traversal kernel.  V5 itself must not be tuned or
rerun, and its fresh holdout must remain sealed.
