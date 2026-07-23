# B2.2 Gate 0 — full-candidate exact-replay harness

Status: **ENGINEERING HARNESS / NO EFFICACY CLAIM**
Lane: HSWM engineering research
Programme: `LakatosTree_PromSearchHSWM_20260721`
Parent: `B2.2-query-bond-weight-groundwork`

## Decision

B2.2 must not fit a learner from the existing B2.1 top-20 scorepacks. A slow or
fast suppression can promote a candidate from below rank 20, while the current
packs retain only the final top-20 IDs and scores. The first executable rung is
therefore a fail-closed harness that freezes **every query x every candidate**
component and proves that neutral bond weights replay frozen B2 exactly.

This is an experiment harness inside an `L_IDE` engineering workflow. It is not
an `L_RT` agent runtime and does not own retries, scheduling, activation,
topology mutation, learning, or scientific judgment.

A single pack can reach only `PACK_SELF_CHECK_PASS` and always carries
`learner_allowed=false`. The sole learner unlock is a separate, hash-bound
`GATE0_ACCEPTED` receipt over all three required roles:

1. 2Wiki `b2_reproduction400`, including frozen row-wise B2 and pinned B2.1;
2. 2Wiki `full_closed_corpus`, including pinned B2.1 top-20 continuity;
3. MuSiQue `full_closed_corpus`, including pinned B2.1 top-20 continuity.

Their fixed `(Q,E)` identities are respectively `(400,2753)`, `(500,3452)`,
and `(800,8893)`; a self-consistent smaller cohort cannot satisfy acceptance.

The acceptance lock freezes each pack root, complete identity/count/digest
tuple, producer/data/model provenance, compile-receipt hash, and compressed plus
decompressed B2.1 reference hashes before the acceptance pass.

## PROM synthesis

The immediate problem has four independent parts:

1. **Identity:** freeze raw query bytes, candidate identities, field partition,
   incidence/seams, model snapshot, producer code, and scoring constants.
2. **Observability:** retain the full edge-cosine, vertex, no-seam bridge,
   merged bridge, and both reconstructed base-score matrices in `float64`.
3. **Independent replay:** compare the component compiler with the original
   row-wise B2 scorer, then pass the complete MERGED base vector through the
   neutral `rank_bonds()` boundary.
4. **Leakage separation:** keep gold IDs, class labels, and later split metadata
   in a hash-bound supervision sidecar, outside the feature-array interface.

The next mechanism after Gate 0 is a small A/B-renaming-invariant,
query-conditioned bond residual. It remains a hypothesis. Gate 0 cannot report
retrieval improvement and cannot activate either fast or slow weights.

## Harness axes

| Axis | Concrete control |
|---|---|
| Inform | manifest binds dataset, cohort, candidate/query identities, formula, model and producer hashes |
| Constrain | exact global candidate coverage, fixed axes/dtypes, no top-k pack, no overwrite, no gold in feature arrays |
| Verify | component algebra, frozen-B2 full-ranking replay, neutral `rank_bonds()` replay, deterministic content hashes |
| Correct | typed fail-closed diagnostics identify stale identity, corruption, truncation, drift, or replay mismatch; packs remain unaccepted data until a separate locked receipt is published |

## Artifact shape

The pack is a directory rather than one giant JSON value. Numeric matrices are
separate non-pickle NumPy arrays so trusted ingestion can read, hash, and parse
one exact byte snapshot without re-embedding. The learner receives detached,
owning, read-only `ndarray` copies rather than memory maps or live file handles.

```text
<pack>/
  manifest.json
  edges.json
  queries.json
  supervision.json
  edge_cosine.npy
  vertex_channel.npy
  bridge_no_seam.npy
  bridge_merged.npy
  base_no_seam.npy
  base_merged.npy
```

All matrices have one declared axis order, `query,edge`, and dtype `float64`.
`edges.json` uses canonical edge-ID order and includes field labels plus static
structural counts/digests. `queries.json` contains only query identity digests
and observable query counts. `supervision.json` contains gold/class metadata and
is hash-bound to the same pack but is not returned by the feature-array API.

The public learner view contains only a path-free manifest projection, feature
edges, feature queries, detached arrays, and the accepted role/root binding. It
does not expose `supervision.json`, the manifest file inventory, filesystem
paths, file names, gold IDs, or the supervision `class` field. This is a trusted
ingestion boundary: the verifier has filesystem access and hands an already
detached value to learner code. It is not, and does not claim to be, a sandbox
against learner code that independently obtains arbitrary filesystem access.

The manifest records, at minimum:

- schema, development-only claim boundary, dataset, cohort, condition and salt;
- query/candidate counts, axis order, formula version, `lambda_v=0.10`, and
  `lambda_b=0.30`;
- dataset, model-snapshot, producer-module, candidate-set, query-set,
  incidence, seam and locked-parameter hashes;
- every file's byte hash, size, dtype and shape;
- a canonical manifest-payload hash.

## Gate contract

### G0.1 — complete identity

- Each query sees the same complete edge set exactly once.
- Edge IDs and query identity digests are non-empty and unique.
- A/B field labels, incidence digests, and structural counts cover every edge.
- A changed raw question byte, dataset, model snapshot, producer, coefficient,
  or candidate order changes a bound digest.
- Model provenance accepts only a real, non-symlinked snapshot directory with
  no nested file or directory symlinks. Compilation hashes it before embedding
  and recomputes the complete strict manifest before pack publication; lock
  validation repeats the same strict check.

### G0.2 — component algebra

For every `(q,e)`:

```text
base_no_seam = edge_cosine + 0.10 * vertex_channel
                              + 0.30 * bridge_no_seam
base_merged  = edge_cosine + 0.10 * vertex_channel
                              + 0.30 * bridge_merged
```

All arrays must be finite `float64`; maximum absolute reconstruction error is
`<= 1e-12`.

### G0.3 — frozen B2 replay

Against the original row-wise B2 scorer, all four arms must agree:

- `A`: `base_no_seam`, restricted to field A;
- `B`: `base_no_seam`, restricted to field B;
- `MERGED`: `base_merged`, all candidates;
- `NO_SEAM`: `base_no_seam`, all candidates.

Complete edge-ID order must be identical under `score DESC, edge_id ASC`; the
maximum absolute score error must be `<= 1e-9`. Top-k agreement alone is not a
pass.

### G0.4 — neutral bond binding

The complete MERGED ranking and score vector must remain identical under all
three neutral forms:

1. dense slow `ell(e)=0`, omitted query plane;
2. constant raw query logits, normalized to all-zero relative potentials;
3. arbitrary valid non-positive potentials with `lambda_s=lambda_q=0`.

Candidate coverage is exact; silent default weights are forbidden.

### G0.5 — state non-interference

Compilation and replay must not mutate embeddings, incidence, seam arcs,
provenance, topology, candidate identities, or durable semantic weights.

### G0.6 — deterministic receipt

Repeated compilation from the same frozen embedding table must produce the same
semantic file and ranking digests. Intrinsic verification emits only
`PACK_SELF_CHECK_PASS` with `learner_allowed=false`; failure exits non-zero and
emits no metric or efficacy verdict.

The real `compile` command performs the component compilation twice through one
cached embedding table, stores the embedding-table digest in the pack, and
requires identical primary/repeated semantic digests before publication. This
is an operational gate, not only a synthetic unit test.

### G0.7 — locked bundle acceptance

- `verify` requires an out-of-band expected pack root.
- Each B2.1 reference must be the pinned deterministic gzip and payload bytes,
  use `top_k=20`, and match cohort/model/coefficients, Q/E counts, full edge-axis
  digest, question digests, and dataset/model provenance.
- The 400-query role must additionally contain a finite, zero-mismatch frozen
  B2 full-ranking replay for all four arms. The complete original row-wise
  ranking is preserved as a deterministic gzip; lock/accept reloads it and
  reruns the comparison rather than trusting the compile receipt's summary.
- The two full-corpus roles and reproduction role must all be present in the
  frozen lock. A missing role, changed pack/receipt/reference byte, stale source,
  or non-finite comparison rejects the entire bundle.
- Only the final acceptance receipt may carry `learner_allowed=true`. The public
  feature loader requires that receipt, re-verifies component and neutral
  semantics against its root, and never returns the supervision sidecar.
- The acceptance receipt carries exactly the engineering-only claim
  `mechanical full-candidate replay only; no retrieval-gain claim` and a
  UTC-offset ISO-8601 `accepted_at`; either field drifting invalidates learner
  authorization.
- Compile receipts and frozen-B2 references may not overlap the pack output or
  model snapshot. Lock and acceptance receipts may not equal or descend from
  any member pack. Lexical siblings remain valid outputs.

### G0.8 — exact B2.1 cache prefix through each target

The frozen B2.1 scorepacks were produced by one shared cached encoder, not by
three independent dataset runs. The repository already records one rejected
run where a changed cache key and GPU batch changed scores at float32 scale in
[`INVALIDATED_b21_preflight_numeric_equivalence_20260723.json`](../evidence/INVALIDATED_b21_preflight_numeric_equivalence_20260723.json).
That makes the encoder-call prefix part of provenance. Exploratory standalone
comparisons without a durable receipt are deliberately not quoted as evidence
here.

The sealed scope is `prefix_through_role_target`: every B2.1 encoder request
from an empty cache through the role's first target request, inclusive. Calls
after that target belong to the determinism or frozen-reference verification
suffix and are not misrepresented as part of this prefix. The exact plans are:

1. reproduction: the 400-query 2Wiki base/legacy target;
2. full 2Wiki: reproduction base/legacy, reproduction frozen-reference
   cache hit, then the full base/legacy target;
3. full MuSiQue: reproduction base/legacy, reproduction frozen-reference,
   2Wiki full base under legacy and both alternate salts, 2Wiki full
   private-entity/legacy, then the MuSiQue base/legacy target.

The compiler executes and observes every sealed-prefix call, including the
zero-miss frozen-reference and alternate-salt calls. Each step binds ordered
requested, missing, and cumulative-cache counts plus text-digest sequences.
The compile receipt also binds the prefix profile/scope, 2Wiki source path/hash,
model snapshot, `device=cuda`, `batch_size=128`, and normalization mode. The
target embedding-table digest is explicitly a
`producer_attested_manifest_binding`; it is not claimed to be independently
re-derived by the model-free lock verifier. B2.1 score continuity and frozen-B2
replay remain the independent output checks.

Lock creation reconstructs the exact prefix from the pinned datasets and
requires all three roles to share the reproduction 2Wiki hash. Acceptance
copies this summary and rebuilds it again before learner access. MuSiQue
compilation consequently requires
`--b21-history-2wiki-data <pinned-2wiki.json>`.

The pinned B2.1 scorepack must also bind its producing
`prom_b21_learned_router.py` SHA and the exact B2.1 frozen-module SHA map to the
producer hashes sealed in the candidate pack. A missing, extra, or stale module
entry rejects continuity even when ranked outputs happen to remain unchanged.

## Required injected negatives

Verification must reject:

- a missing, extra, duplicate, truncated, or reordered candidate;
- a missing/extra file, symlink, byte-tampered array, or stale manifest hash;
- `float32`, transposed/wrong-shaped, NaN, or infinite matrices;
- changed question bytes or duplicate query identity;
- a perturbed formula coefficient or component value, even if file hashes were
  recomputed;
- a different tie rule or top-k-only representation;
- supervision fields exposed through the feature-array API.
- a self-check receipt presented as learner authorization;
- a `top_k=1`, wrong-cohort/model/provenance, changed-question, or non-finite
  B2.1/frozen-B2 reference;
- a compile receipt, input byte, model snapshot, producer source, or pack changed
  after the acceptance lock;
- a top-level pack-directory symlink, symlinked pack output, top-level model
  symlink, or nested model file/directory symlink;
- a sidecar or array changed after file-set inspection but before parsing;
- a lock/acceptance output placed at or below any pack, or a compile
  receipt/frozen reference placed below a pack or model snapshot;
- an altered acceptance claim boundary or a missing/non-string/non-UTC
  `accepted_at` value;
- an absent, reordered, extra, or mutated B2.1 sealed-prefix step;
- a changed cache-prefix 2Wiki source, target text table, model, device,
  batch size, normalization mode, or embedding-table digest.

## Operational boundary

Unit and synthetic replay tests are lightweight and may run locally. Building
the real full-candidate matrices is a heavy one-time embedding job and must use
the guarded Dell path when the Mac resource preflight fails. The runtime pack is
data/evidence, not a source file and must not be committed to Git.

Operational order is `compile` for all three roles, `lock` over their pack and
compile-receipt paths, then `accept`. A compile-receipt write failure may leave
an orphan pack, but that directory is deliberately inert: without the later
acceptance receipt the learner-facing loader refuses it.

Pack verification first freezes the self-hashed manifest, checks the exact file
set, then opens each declared payload without following symlinks and hashes the
same in-memory bytes that JSON/NumPy parses. Arrays are loaded from `BytesIO`
and copied into owning read-only values; neither verification nor learner
ingestion returns a filename-bearing memory map.

The reproduction compile additionally requires `--frozen-b2-reference`; the
two full-corpus compiles must omit it. The MuSiQue compile additionally requires
`--b21-history-2wiki-data`. Lock creation reopens the pinned B2.1 and frozen-B2
gzip bytes, verifies compressed and payload hashes, reconstructs the sealed
cache prefix, and directly replays the references against the candidate
matrices.

## Next falsifier after Gate 0

Only after all gates pass may development fit a low-capacity fast potential
over observable score/structure components. Required controls remain frozen
MERGED, score-only linear, shuffled target, private-entity/answer-surface,
`lambda_q=0`, rejected B2.1 routing, and equal-budget flat/vector reranking.
Repeated fast effects may propose a slow `Delta ell`; they do not automatically
become durable memory or topology.
