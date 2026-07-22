# B2.1 learned router — multi-case result

> Date: 2026-07-23 KST
>
> Scientific result: **REJECTED**
>
> LakatoTree result: **metric equivalent / degenerating**, node `REJECTED`
>
> Scope: frozen `A / B / MERGED` arms plus a learned router. This is not a test of
> semantic-edge-weight learning or topology learning.

## Conclusion first

The learned router did not solve B2's interference problem. All 54 standard cells
selected `ABSTAIN` for every test query, so execution reduced exactly to the
`MERGED` baseline. The primary improvement over `MERGED` was `0.0` on both 2Wiki
and MuSiQue, while the preregistered success condition was a minimum improvement
strictly greater than `+0.02`.

This is not merely an over-conservative threshold accident. A post-result oracle
diagnostic shows that, on the two frozen primary cohorts, even a router that knows
the gold answer and chooses the best of `A`, `B`, and `MERGED` per query has only
`+0.010870` minimum headroom. Thus no possible router over these three frozen arms
can satisfy the registered `> +0.02` primary prediction.

The narrow conclusion is therefore:

> **Reject the router-only action space, not the larger HSWM learning hypothesis.**
> The next learnable object must reach inside the HSWM: semantic weights and then
> bounded `CONNECT / SEPARATE / SPECIALIZE` topology edits.

## What was actually learned

The learned variable in B2.1 was the router parameter `phi`:

```text
g_phi(query, observable score/provenance features) -> A | B | ABSTAIN
ABSTAIN -> execute MERGED
```

It was a shared A/B-equivariant ridge utility model with 53 observable features and
component-worst conformal abstention. Gold labels were used only to fit and evaluate
the router on component-disjoint splits.

B2.1 did **not** change:

- embedding parameters `X`;
- semantic edge weights `ell` inside either HSWM;
- ports, connectors, membership, or hypergraph topology;
- the frozen `A`, `B`, `MERGED`, and no-seam rankers.

So, in the user's terms, this experiment learned **which existing map to execute**;
it did not yet learn **the HSWM weights themselves**. “HSWM 학습 = 웨이트 조절” is
partly right, but the full state has three distinct learnable planes:

1. `weight`: how strongly an existing semantic bond contributes;
2. `routing`: which HSWM or expert coalition is active for this query;
3. `topology`: which ports/hyperedges should connect, separate, or specialize.

Query activation is transient state and is not counted as durable learning.

## Frozen evaluation matrix

The standard matrix was:

```text
2 datasets (2Wiki, MuSiQue)
x 3 field partitions (legacy, b21-field-v1, b21-field-v2)
x 3 retrieval cutoffs (k=5, 10, 20)
x 3 router seeds (7332, 7333, 7334)
= 54 standard cells
```

Every standard cell also included a capacity-matched shuffled-target negative.
Six additional private-entity-surface cells tested whether lexical entity names
were carrying the decision. Train/calibration/test were disjoint by gold-component,
so MuSiQue duplicate rows could not leak a shared component across splits.

The scorer and embeddings were run on the Dell host because the Mac failed the
resource headroom check. The frozen model was
`sentence-transformers/all-MiniLM-L6-v2`, snapshot SHA-256
`a505d33be7223cfc86d31cf5f26914d756ec21448b6ca202da5dc50d74a9bc96`.

## Primary results

| Dataset | Test queries | Independent components | Actions A/B/ABSTAIN | Router - MERGED | Cross - best single | In-field - best single | Radius |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2Wiki | 92 | 92 | 0 / 0 / 92 | `0.000000` | `+0.245690` | `-0.029412` | `0.367285` |
| MuSiQue | 140 | 54 | 0 / 0 / 140 | `0.000000` | `+0.168675` | `-0.035088` | `0.472949` |

The positive cross-field numbers in this table are inherited from executing
`MERGED`; they are not gains created by the router. The router abstained everywhere.

Registered primary metric:

```text
min_dataset(router recall@10 - MERGED recall@10) = 0.0
required                                             > +0.02
result                                               FAIL
```

Registered novel/no-harm metric:

```text
min_dataset(in-field router - best single) = -0.035088
required                                    >= -0.02
result                                      FAIL
```

## Matrix-wide and negative-control results

| Check | Result |
|---|---:|
| Standard joint pass | `0 / 54` |
| 2Wiki joint pass | `0 / 27` |
| MuSiQue joint pass | `0 / 27` |
| Shuffled-target joint pass | `0 / 54` |
| Private-entity joint pass | `0 / 6` |
| Standard accepted single-field actions | `0 / 6,264` repeated query exposures |
| Standard overall delta range | `[0.0, 0.0]` |

Gate counts across the 54 standard cells were:

| Gate | Passed |
|---|---:|
| Cross gain over best single | `54 / 54` |
| Cross preserved versus MERGED | `54 / 54` |
| In-field no-harm versus best single | `3 / 54` |
| In-field recovery versus MERGED | `0 / 54` |
| Overall paired CI lower bound above zero | `0 / 54` |
| Nontrivial router acceptance | `0 / 54` |
| Joint gate | `0 / 54` |

The shuffled negative passed its literal safety requirement (“must not pass”), but
because both real and shuffled routers abstained everywhere it supplies no positive
capacity evidence. The private-entity primary cases were no worse than their
private `MERGED` baselines, but also failed the joint gate; this is abstention safety,
not learned specialization.

## Exact B2 continuity check

Before evaluating B2.1, the new vectorized scorer had to reproduce frozen B2:

- 400 queries, 1,600 arm rankings, 32,000 score comparisons;
- zero QID mismatches and zero ranked-ID-list mismatches;
- maximum absolute score error `3.552713678800501e-15 <= 1e-9`;
- vectorized and frozen digest both
  `9303687dbd17c4bf21a428328fd2dd5dae9d9899ab0caac7af3bad4794cae3bf`;
- aggregate continuity: cross `+0.213675`, in-field `-0.064759`, seam `+0.034188`.

The first attempt was invalidated before any router measurement because an adapter
trimmed trailing whitespace from three 2Wiki questions. Ranked IDs still matched,
but maximum numeric drift `1.7797851370460194e-07` exceeded the locked `1e-9`
tolerance. The invalidated receipt is preserved; the repair changed only byte
preservation and was preregistered before the successful rerun. The tolerance and
scientific criteria were not relaxed.

## Post-result headroom diagnosis

This section is explicitly `DIAGNOSTIC_NO_CLAIM`; it was not preregistered and does
not replace the official result.

| Dataset | MERGED recall | Gold oracle over A/B/MERGED | Oracle headroom |
|---|---:|---:|---:|
| 2Wiki | `0.758152` | `0.769022` | `+0.010870` |
| MuSiQue | `0.673810` | `0.693452` | `+0.019642` |

The registered metric takes the minimum over datasets, so its oracle ceiling is
`+0.010870`, below the required `> +0.02`. Across all non-primary matrix cells,
oracle headroom ranged from `+0.002718` to `+0.059524`, and 42/54 happened to exceed
`+0.02`; that does not rescue the frozen primary prediction.

Removing the conformal radius also did not help:

- 2Wiki accepted 13 single-field actions, all 13 true recall ties; delta `0.0`.
- MuSiQue accepted 15, comprising 1 positive, 1 negative, and 13 ties; delta `0.0`.
- forcing a single-field choice was harmful: `-0.179348` on 2Wiki and `-0.117262`
  on MuSiQue.

Therefore lowering the abstention threshold is not the next experiment. The utility
signal and, more decisively, the frozen action space are insufficient.

## Architectural consequence

The simplest reusable formulation is not a fixed stack of layers. Let every object
remain an HSWM and let learning emit a sparse, typed delta over the same algebra:

```text
H_t = NF(M, P, C, X, ell, Pi)

proposal_t = agent_phi(query, H_t)
           = (Delta ell, Delta C, Delta Pi)

H_candidate = apply(H_t, proposal_t)
H_(t+1)     = CAS_activate(H_candidate) only after replay/no-harm gates
```

Here `Delta ell` changes semantic weights, `Delta C` changes n-ary connectors, and
`Delta Pi` changes specialization/routing policy. The agent does not mutate the
active network directly: it proposes an immutable candidate, evaluates it on fresh
component-disjoint data, checks retention/canary/replay, and activates it atomically.

A compact objective for the next branch is:

```text
task loss
+ lambda_sparse * number_or_magnitude_of_edits
+ lambda_interference * retained-domain harm
+ lambda_uncertainty * proposal uncertainty
```

subject to typed-port compatibility, evidence provenance, edit budgets, idempotent
event replay, and an explicit `ABSTAIN / NO_CHANGE` action. This gives the desired
Transformer-like elegance: one self-similar object type, one sparse edit algebra,
and one safety-preserving activation rule—without pretending that arbitrary depth
or arbitrary rewiring is automatically useful.

### Next falsifiable rung: B2.2

1. Freeze embeddings and the B2 scorer again.
2. Add a sparse `Delta ell` action that may reweight evidence-bearing seam and
   in-field hyperedges; do not yet add unrestricted topology creation.
3. Compare `MERGED`, the rejected B2.1 router, learned `Delta ell`, shuffled-target
   `Delta ell`, and a gold-oracle diagnostic under equal compute.
4. Require positive overall CI, cross-field retention, in-field no-harm, sparse edit
   budget, private-entity robustness, two datasets, three seeds, and exact replay.
5. Only if weight learning leaves irreducible cases, unlock bounded typed
   `CONNECT / SEPARATE / SPECIALIZE` proposals as the following rung.

This ordering tests the smallest internal change first while preserving the user's
larger target: an agent-completed semantic neural network whose maps can be combined,
detached, and specialized without a privileged “first layer.”

## LakatoTree disposition

Tree `LakatosTree_PromSearchHSWM_20260721`, node
`B2.1r1-query-byte-equivalence-repair`:

- official scripted verdict: `degenerating`;
- metric verdict: `equivalent` (`delta=0.0`);
- node state: `REJECTED`;
- question `Q-b21-learned-router-interference-control`: remains `OPEN`, because
  this ridge router failed but learned routing in general was not disproved;
- prediction receipt:
  `27fb71d548ca91a757ce524b94b9cfdba90453333f40bbd0ddcbe25085a6d1ee`;
- result receipt:
  `5843898b353b6b388acf61640bba8d7ea8ac47b120835db014c94776ea5fd7b7`;
- `verify_verdict`: `ok=true`, receipt re-derivation agrees;
- certificate: `certified=false`.

Certification remains false because the server replay template invoked the harness
without its required dataset/model arguments, yielding `replay_refuted`; measurement
therefore remained `client_asserted`. The certificate also reports calibration ECE
`0.1771 > 0.1` and missing reproducible lineage. These assurance failures do not
change the locally audited scientific failure, but they prohibit claiming a
server-owned certified result.

## Reproducibility artifacts

- harness: `../prom_b21_learned_router.py`
- tests: `../test_hswm_b21_learned_router.py`
- evidence: `../evidence/EVIDENCE_b21_learned_router_20260723.json`
- independent arithmetic/provenance audit:
  `../evidence/AUDIT_b21_learned_router_20260723.json`
- posthoc oracle/threshold diagnostic:
  `../evidence/DIAG_b21_router_headroom_20260723.json`
- invalidated preflight:
  `../evidence/INVALIDATED_b21_preflight_numeric_equivalence_20260723.json`
- repair preregistration:
  `../evidence/PREREG_b21r1_query_byte_repair_20260723.json`
- LakatoTree packet: `../judgments/B21_learned_router/`

The full relevant regression suite passed `113` tests. All 9 compressed scorepacks
and their payload hashes matched the evidence manifest; the large scorepacks remain
in the ignored local cache rather than Git.
