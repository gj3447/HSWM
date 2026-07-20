# H3-B3 preregistration — evidence-bound relation composition

Status: frozen before the fresh B3 extraction/evaluation run.

This experiment tests the narrow claim the user called HSWM's third kind of
intelligence: **retrieval that succeeds because two evidence-bound relations
compose, rather than because a paragraph is already semantically similar to
the query**.  It does not test general reasoning or answer generation.

Longinus ReferenceSite: `HSWM/PROM_16_WORLD_COMPILER_CERTIFIED_READOUT_ENVELOPE_2026-07-20.md`
sections 12.2, 13, 15/S6-S7, and 17.

## 1. Treatment and frozen boundary

- B1: deterministic exact-title anchors.
- B3: recorded LLM n-ary observations compiled only after every
  subject/predicate/argument is rebound to an exact paragraph span.
- B3 may add a paragraph arc only through an admitted exact shared role entity
  or an exact title target.  A shared continuation is directed
  `source argument -> target subject`; subject-subject, argument-argument, and
  an unevidenced reverse are forbidden.  The arc retains both endpoint
  selectors, roles, predicates, claim IDs, and the join entity ID.
- Path depth counts **applied source-claim predicates**, not paragraph links.
  At one hop the kernel may score only the outgoing claim's predicate and
  source role.  A target claim predicate is receipt/continuation evidence and
  cannot affect the score until it becomes the source claim of the next hop.
- Claim continuity is mandatory: after an arc lands on `target_claim_id`, the
  next arc's `source_claim_id` must be exactly that ID.  Landing on a title-only
  target with no target claim terminates the path.  Switching to an unrelated
  claim merely because it shares the same paragraph is forbidden.
- The compiler input is exactly `(source_id, title, text)`.  Question, answer,
  support, hop, decomposition, evidence triples, and gold IDs are evaluator
  sidecars and must fail closed at the compiler boundary.
- Candidate paragraphs, paragraph/query embedding model and revision, static
  scores, reader, and top-k are held fixed between arms.
- The extractor is stochastic infrastructure outside the trusted compiler.
  Raw response, producer/model revision, prompt/config/output hashes, token
  usage, latency, and every quarantine are preserved.
- Confirmatory extraction uses `batch_size=1`: one paragraph is the model's
  complete context.  Parallelism may change wall time but never request
  membership or relation interpretation context.
- Exact surface equality proves a string match, not entity identity.  A
  separate query-label-blind identity audit is an admission gate (§5).

## 2. Fresh holdout

Seed:

```text
HSWM-H3-B3-CONFIRM-2026-07-20-v1
```

Ordering is `sha256(seed | dataset | qid), qid`.  Every prior B1 query ID,
relation-template ID, and exact evidence-content ID is excluded before quota
selection.

| dataset | quota | source receipt |
|---|---:|---|
| MuSiQue | 2-hop 160, 3-hop 80, 4-hop 60 | raw canonical SHA `8a2bf53b77f4e322d34fbca6e40bd10ec98ab2688dc745f1cd3681943c83253d` |
| 2WikiMultihopQA | 2-hop 150, 4-hop 100 | parquet SHA `408e2dbb28edc6c8b9ca3ba0c94d4fc7bf17ffb923766593a3a7f546ab4cba59` |

The previously measured 200-row B1 corpus per dataset is development-only:
its existing relation/evidence-disjoint validation half is the tune group and
its test half is the certificate group.  The entire newly selected set above
is the untouched confirmatory test.  The fresh exclusion rule guarantees that
no query ID, relation-template ID, or exact evidence-content ID from either
development half enters that confirmatory test.  Thus no fresh result is used
to choose or admit a policy.

## 3. Precompute no-op gate

No full extraction/embedding run is allowed unless all hold:

1. a non-title exact shared entity makes B3 adjacency differ from B1;
2. role/predicate-aware B3 scores differ from the B1 untyped kernel;
3. a synthetic target first reached at depth two is promoted by K2 but not K1;
4. breaking only the second edge destroys that promotion;
5. `mu=0` is bit-identical to the static score vector;
6. every promoted two-hop receipt contains two exact selectors and an
   intermediate target/join identity;
7. a two-claim intermediate paragraph cannot be used to switch claims;
8. target-predicate words alone cannot make the current hop eligible;
9. any fanout or join-hub trip returns the static floor for that query.

## 4. Policy and comparisons

The tune surface is deliberately small:

```text
seed_k       in {3, 10}
mu           in {0.025, 0.05, 0.1}
direction    = evidence direction only (shared-role joins are explicitly paired)
path depth   K = 2
```

The selected K2 policy is compared with the matched K1 policy using the same
`seed_k`, `mu`, graph, and typed arc scoring.  A policy that does
not beat K1 on the old-corpus certificate group is refused and deploys
`mu=0`.  No policy is reselected on the fresh test.

Frozen comparators:

- cosine, BM25, and RRF;
- B1 title-anchor K1 and K2;
- B3 typed K1 and K2;
- directed degree-preserving topology shuffles;
- topology-fixed predicate/role shuffles;
- second-edge-only shuffles for the K2 causal test.

All policy selection and multiplicity adjustment are grouped by relation/
evidence component, never query-IID.

Tune objective and tie-break are fixed: mean nDCG@10, then ASR@10, then lower
`mu`, then lower `seed_k`.  The development certificate uses the same
`+0.02 nDCG`, `+0.03 ASR`, and cluster-CI-lower-`>0` margins as fresh test.
The strongest static baseline is chosen on tune and then frozen.

## 5. Primary metrics and PASS gate

Primary retrieval metrics are nDCG@10 and all-support recall@10 (ASR@10).
Support recall@10 and downstream answer F1 are secondary/open respectively.

A dataset passes only if all conditions hold on its untouched test split:

1. `B3 K2 - matched B3 K1 >= +0.02 nDCG@10` and cluster CI lower bound `> 0`;
2. `B3 K2 - matched B3 K1 >= +0.03 ASR@10` and cluster CI lower bound `> 0`;
3. B3 K2 clears the same two thresholds against B1 K2 and the strongest
   static baseline;
4. at least `max(10, 5% of test queries)` have a gold paragraph first reached
   at depth two, and this cohort has positive K2-minus-K1 gain;
5. real K2 beats every topology, role/predicate, and second-edge null on both
   primary metrics;
6. apply coverage is at least 0.50;
7. false-link, hub/percolation, quarantine, fallback, trip, build-call, token,
   latency, and wrong-path statistics are all reported.

Safety co-primary admission additionally requires:

- every shared join has compiler document frequency `<= 8`;
- the largest weak paragraph component is `<= 25%` of targets;
- no query with a fanout or join-hub trip receives a non-static score;
- a deterministic, query-label-blind sample of up to 100 unique shared joins
  (`HSWM-H3-B3-ARC-AUDIT-2026-07-20-v1`) is adjudicated from only its two local
  exact contexts by Qwen3.6-27B revision
  `6a9e13bd6fc8f0983b9b99948120bc37f49c13e9`; `UNCLEAR` counts as incorrect;
  entity-identity precision must be `>= 0.95` and its 95% Wilson lower bound
  `>= 0.90`.  Missing adjudication means `REFUSED`, never presumed precision.

The primary estimand is query-weighted.  Relation/evidence components are the
resampling unit.  Percentile cluster bootstrap uses 10,000 draws with seed
`20260720`; one-sided cluster sign-flip uses 100,000 draws (or exact enumeration
when smaller).  Alpha is 0.05.  Benjamini-Hochberg covers the family
`2 datasets x 2 primary metrics x 3 primary comparisons` (K2-K1, B3-B1,
B3-strongest-static).

Topology and relation-role nulls use seeds `0,1,2,3,4`.  The query-specific
second-step null may be reported only when it changes the real K2 second step,
creates no self-loop/duplicate, and leaves the matched K1 score digest exactly
unchanged; otherwise that null is `NULL_INVALID` and the dataset cannot PASS.
Real-minus-null must have cluster-CI lower `>0` on both primary metrics for
every valid frozen null.

Both datasets passing permits the phrase **evidence-bound relational
composition retrieval intelligence**.  One passing is dataset-specific
evidence.  Neither passing refutes or leaves H3 inconclusive.  Even a full pass
does not permit `general reasoner`, `answer reasoning`, or deployment claims;
paired downstream answer F1 and CRE admission remain separate gates.

## 6. Kill conditions

- B3 adjacency equals B1 after exact-span admission: precompute no-op, stop.
- K2 does not beat matched K1: composition claim dies even if B3 beats cosine.
- Second-edge shuffle does not kill the effect: the gain is not attributed to
  relation composition.
- Role/predicate shuffle does not kill the effect: typed semantics are not the
  cause; report topology-only retrieval.
- Exact-span quarantine removes the gain: report extractor leakage/artifact.
- Hub/component budgets trip: refuse even if utility rises.
- MuSiQue and 2Wiki disagree: no general H3 claim.

## 7. Pre-outcome integrity addendum

This addendum was fixed before any development-certificate or fresh retrieval
metric was computed.  It changes no arm, threshold, sample, or statistical
budget.  It closes evidence-production ambiguities discovered while turning
the preregistration into an executable harness.

1. **Implementation identity.**  The nine precompute gates issue a first-write
   v2 receipt that also binds the exact per-file SHA-256 map and canonical code
   root of every imported H3 implementation module.  The run manifest must
   bind the identical set and root; a post-gate code change invalidates the
   receipt.
2. **Physical phase separation.**  Development and fresh extraction logs and
   embedding bundles have different precommitted paths.  Each producer has an
   `OPEN` receipt created while its output is nonexistent and a `CLOSE` receipt
   over the same reserved inode or exclusive directory.  A fresh `OPEN`
   additionally requires the first-write certificate-transition hash from
   both passing development datasets.
3. **No circular PRE_RUN hashes.**  The PRE_RUN manifest commits inputs,
   configs, deployment identities, and future paths, but not hashes of outputs
   that do not yet exist.  Development output hashes enter the certificate
   transition; fresh output hashes enter the fresh-artifact seal.
4. **Model identity.**  Embedding and OpenAI-compatible model receipts bind an
   immutable local snapshot, relevant weight/config/tokenizer hashes, exact
   runtime configuration, and producer code.  The Qwen27 audit deployment is
   a future-path commitment at PRE_RUN because it shares a GPU sequentially
   with the extractor; its live receipt is created and hash-bound before the
   packet seal and before any audit endpoint call.
5. **Label order.**  Fresh compiler artifacts and the query-label-blind join
   packet are sealed before fresh evaluator labels are opened.  Fresh scoring
   is forbidden until extraction, embedding, packet, and adjudication close
   receipts all validate.
6. **Second-edge estimand.**  The query-specific second-edge control is
   query-weighted over the full evaluation set: queries without an admissible
   second-edge intervention contribute a zero paired delta.  An intervention
   is invalid if it creates any self-loop or duplicate, including collisions
   between two rewired edges, or changes the matched K1 digest.
7. **Identity-audit estimand.**  The audit population is every unique emitted
   `(join identity, source claim, target claim, source document, target
   document)` pair.  It is reported as **shared-join identity precision**, not
   as typed-predicate or full-arc semantic precision.  Reverse duplicates are
   collapsed; distinct source/target pairs sharing one surface are retained.
8. **Single committed outcome.**  The audit uses a sealed packet, an
   exclusively empty append ledger, one durable endpoint outcome per item,
   and a first-write adjudication close.  `finish_reason != stop`, missing
   items, duplicates, or deployment/config drift force refusal.
9. **Report publication.**  Development reports, the certificate transition,
   the fresh-artifact seal, and the final report are first-write artifacts.
   A failed development certificate produces a refusal and cannot authorize a
   fresh producer.
