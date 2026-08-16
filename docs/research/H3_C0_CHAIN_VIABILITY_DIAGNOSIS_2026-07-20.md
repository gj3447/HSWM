# H3-C0 evidence-bound chain viability diagnosis — 2026-07-20

Status: development-only post-refusal diagnosis.  No model call, certificate
rerun, source-code edit, transition write, or fresh access was performed.

Inputs were the closed V5 development artifacts:

- manifest SHA-256
  `9e323caa20cdcedcdb7d400889801a59dd0b0603a8ccb8eb161f2da326d6f144`;
- extraction CLOSE SHA-256
  `ad5c7529d2bc1958fee11a67525fbc4c5eda4616a36d0633b2bacf65fd7c1421`;
- embedding CLOSE SHA-256
  `3dd61832afe5fcc95affd3cdc94a5245204450b170c633331060dae0696607e6`;
- development report SHA-256
  `8cc7b3b04295ceee26f210dc15201d325e258a4f415a1d1a09a2c5381f748896`.

## Conclusion

`B3 K2 == B3 K1` is forced by the compiled topology.  Before query matching,
scoring, `mu`, or safety gates matter, neither development graph contains one
legal non-cyclic claim-continuous two-edge path.

| dataset | typed arcs | nonterminal shared / terminal title | paragraph-only simple pairs | exact claim-continuity pairs | admissible two-edge chains | B1 simple pairs |
|---|---:|---:|---:|---:|---:|---:|
| MuSiQue | 81 | 36 / 45 | 3 | 0 | 0 | 446 |
| 2Wiki | 308 | 39 / 269 | 28 | 2 | 0 | 945 |

The two exact 2Wiki pairs are immediate backtracks and are correctly rejected:

- `Queen Hogu -> Geojilmi of Geumgwan Gaya -> Queen Hogu`;
- `John, Count Palatine... -> Catherine of Pomerania... -> John, Count Palatine...`.

Thus the traversal implementation is not generally inert: B1 has hundreds of
simple two-edge paths and distinct K1/K2 score digests.  The evidence-bound B3
material is what terminates before a legal second hop.

## Gate waterfall

The exclusive full-development query waterfall under each selected top-3
policy was:

| outcome | MuSiQue, n=200 | 2Wiki, n=200 |
|---|---:|---:|
| no outgoing typed arc from a cosine seed | 172 | 61 |
| outgoing arc, but source predicate mismatch | 17 | 30 |
| predicate passes, relation quality/role shortfall | 1 | 2 |
| at least one one-hop typed application | 10 | 107 |
| one-hop application includes a nonterminal edge | 4 | 18 |
| legal claim-continuous second hop | 0 | 0 |

On the 100-query certificate halves the corresponding counts were:

| outcome | MuSiQue | 2Wiki |
|---|---:|---:|
| no seed outgoing arc | 85 | 10 |
| predicate mismatch | 9 | 4 |
| quality/role shortfall | 1 | 0 |
| one-hop applied | 5 | 86 |
| nonterminal first edge | 1 | 15 |
| legal second hop | 0 | 0 |

Removing predicate and role admission entirely does not rescue K2: the untyped
diagnostic reaches one hop for 28/200 MuSiQue and 139/200 2Wiki queries, but
still has zero depth-two path because the claim-continuity frontier is empty.
Fanout and join-hub trips were zero.  Positive seed score and safety fallback
are therefore not the cause.

## Where the material disappears

The extractor/compiler preserved many exact observations but very few claims
participate as an outgoing typed arc.

| material | MuSiQue | 2Wiki |
|---|---:|---:|
| paragraphs | 2,094 | 1,505 |
| admitted exact-span n-ary claims | 4,254 | 3,100 |
| unique typed-arc source claims | 64 (1.5%) | 276 (8.9%) |
| licensed shared pairs / all shared candidates | 36 / 2,684 (1.34%) | 39 / 2,701 (1.44%) |
| records with at least one quote quarantine | 1,285 | 643 |
| quote-quarantine items | 2,813 | 1,252 |
| ambiguous-quote items | 2,380 | 1,005 |
| deterministic title fallbacks excluded from typed kernel | 913 | 838 |

The exclusions are not silent loss.  Every rejected shared surface retains a
reason such as homonym risk, non-name surface, role-direction mismatch,
ambiguous title continuation, or missing continuation subject.  This preserves
evidence integrity, but it also leaves only 36/39 carrier arcs capable of
holding a target claim.

One-hop relevance is alive.  On the certificate split, 18/100 MuSiQue and
89/100 2Wiki queries have a typed gold-to-gold edge.  This explains why 2Wiki
B3 can beat cosine pointwise while K2 contributes nothing.

## Exact title-to-claim counterfactual

A safe local improvement is possible in principle: a title-terminal landing
can branch into target claims whose subject is exactly the same normalized
title, provided both title and body-subject selectors remain in the receipt.
No arbitrary paragraph-local claim switch is allowed.

- MuSiQue: 7/45 terminal arcs have such an exact target-subject claim, but none
  of those claims has a legal outgoing typed arc; added simple chains: 0.
- 2Wiki: 151/269 terminal arcs have an exact target-subject claim; 27 candidate
  claims have an outgoing typed arc, yielding 15 non-cyclic structural chains.
  Certificate top-3 seeds reach three such chain entrances, but the first
  predicate matches the query in zero cases.

Therefore exact title-subject binding is worth implementing as an auditable
arm, but it is not by itself an evidenced fix for the current failure.

## Root-cause classification

1. **Kernel arithmetic/state transition: not defective.**  Exact claim-ID
   continuity, title-terminal stopping, join reuse prevention, and cycle
   rejection all behave according to the frozen safety contract.
2. **Builder material: insufficient for composition.**  Alias fragmentation,
   absent canonical entity identity, ambiguous quote selectors, and missing
   subject-to-next-argument continuity prevent three-node claim chains.
3. **Query matcher: a secondary bottleneck.**  It removes some one-hop
   opportunities, but even an untyped run cannot create a second hop from a
   graph with no legal chain.
4. **Harness: real-world non-vacuity gate missing.**  The preflight proves the
   code on synthetic chains, while `compile_segment()` only requires one new
   shared adjacency.  Neither requires the compiled real graph to contain an
   admissible depth-two chain before expensive embedding/certification.

The V5 refusal remains valid for the current compiler/readout.  The diagnostic
does narrow its interpretation: it is a treatment-viability failure, not a
general disproof that evidence-bound relational composition can exist.

## Successor: H3-C0 builder factorial

Any successor must be newly preregistered and development-only first.  Keep the
query matcher, embeddings, scorer, and traversal policy fixed so the builder
effect is identifiable.

Recommended arms:

1. `C0`: current exact-surface compiler.
2. `C1`: exact title-to-claim subject weave with both exact selectors and no
   arbitrary claim switch.
3. `C2`: provenance-bound canonical entity nodes.  A Wikidata QID/SKOS mapping
   or a local canonical ID is admissible only with alias-to-span provenance,
   confidence, and reversible audit evidence.
4. `C3`: `C2` plus explicit intra-paragraph claim weave/coreference receipts;
   every handoff must bind the landed entity to the next claim subject.

The real-material gate must run after extraction/compiler and before embedding
or efficacy evaluation.  It should publish an immutable chain ledger and stop
at the first failed rung:

```text
T0  A.target == B.source
    A.target_claim_id == B.source_claim_id
    A.join_entity_id != B.join_entity_id
    B.target not in {A.source, A.target}
    fanout and join bounds pass

T1  a frozen query seed reaches the T0 chain entrance
T2  both source predicates are query-compatible
T3  K2 changes the matched K1 score digest and a second-edge null kills it
```

The successor preregistration should set nonzero per-dataset minima before the
arm outputs are inspected; the existing certificate requirement of at least 10
depth-two first-gold queries is the natural upper gate.  If T0 is zero, the
system must emit `PRECOMPUTE_NOOP_DEPTH2` and spend no embedding or certificate
budget.

The engineering direction is consequently precise: make the World Compiler
better at canonical, evidence-bound entity and claim continuity.  Do not relax
to paragraph-level traversal merely to manufacture a positive K2 result.
