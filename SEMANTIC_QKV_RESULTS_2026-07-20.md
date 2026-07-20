# HSWM semantic-layer QKV results — 2026-07-20

## Bottom line

The user's correction survived its narrow mechanism test:

> 단순 겹겹이가 아니라 시멘틱한 겹겹. 그냥 무식하게 겹겹이 쌓으니까 그렇지.

The failed B1-QKV experiment repeatedly updated one paragraph-vector state. It
did not test a stack whose unresolved state changes semantic type, arity, and
operator. The new evidence-bound synthetic kernel executes:

```text
Person
  -> BranchSet[Person]
  -> BranchSet[Pair[Person, Date]]
  -> Selected[Person]
  -> City
```

On the frozen fixtures, the supplied heterogeneous program passes every
registered gate. This is a real correction to the experiment design. It is not
yet evidence that HSWM induces such programs from language, retrieves their
facts from documents, learns the operators, or improves cognitive ability.

The exact current verdict is:

> HSWM is not a pathetic or empty theory. It is already a useful
> evidence-preserving substrate, and heterogeneous semantic layering is now a
> working narrow mechanism. The ambitious claim that HSWM structure itself
> creates deployable reasoning intelligence remains unproved.

## A. Synthetic common-kernel result

The registered matrix contains four unique semantic templates—two Date
assignments times two reducers—replicated into 32 content-addressed namespaces.
It is therefore 128 deterministic cases, not 128 structurally diverse tasks.

| arm or tooth | result | interpretation |
|---|---:|---|
| heterogeneous typed program | **128/128** | exact frozen terminal |
| fixed-state association-erased control | **64/128** | chance ceiling on paired assignments |
| fixed-reducer paired-world signature collisions | **64/64** | erased state cannot retain Date-to-Person association |
| exact single-frontier router | **0/128**, 128 refusals | exact-one router cannot represent one-to-many branch |
| actual branch-erasure control | **128/128 refusals** | typed map runs; unbound Date/Person bags reach the same reducer and fail closed |
| type mutation | **128/128 refusals** | hard type gate has teeth |
| key/value/reducer mutations | **0/128 original terminals** | implementation is sensitive to each frozen semantic binding |
| layer order mutation | **128/128 refusals** | state-type protocol is enforced |
| missing/ambiguous/tied cases | **128/128 refusals each** | no caller-order repair |
| repeat and reversed memory order | **128/128 identical** | deterministic execution and receipt |
| receipt envelope hash chain | **128/128 valid** | step and final envelope hashes independently recompute |

The branch-erasure arm is not a constant refusal shim. The common kernel first
executes `EXPAND` and `MAP_ONE`, constructs and hashes an explicit
`BRANCH_SET_PERSON_DATE_ERASED` state containing the typed Date and Person bags
but no pairings, and passes it into the same reducer used by the full arm. The
reducer returns `MISSING_BRANCH_ASSOCIATION`; query atomicity removes the
successful internal partial steps from the public receipt.

The homogeneous control preserves the reducer token, relation program, types,
and complete Value multiset. It removes typed state variants, branch IDs, and
Person-Date associations. Its prediction consumes exactly the canonical state
whose digest is reported. Thus the 64/128 comparison does not obtain its effect
by deleting `ARGMIN` versus `ARGMAX` from Q.

This experiment identifies the joint package of hard type gates, changing
arity/state shape, branch lineage, and operator-specific transitions. The
mutation teeth do not separately estimate a causal effect for each component.

Allowed claim:

> On the frozen synthetic two-branch child/date/birthplace fixtures, this
> implementation deterministically executed a supplied heterogeneous typed
> program with branch-preserving map, typed reduction, value-bound lookup,
> evidence receipts, and query-atomic refusal.

Source: `semantic_layer_result.json`, result SHA-256
`09e91ef6e4030c676074aaa4a59baf2e3acf86f1d5e63f8b3330202469d53b29`.

## B. 2Wiki evaluator-supplied-memory probe

The development probe covers comparison shapes selected after inspecting the
already-open development artifact:

| operator family | supported / exact |
|---|---:|
| `ARGMIN_DATE` | 75/75 |
| `ARGMAX_DATE` | 30/30 |
| `SET_OVERLAP_BOOL` | 25/25 |
| `LIFESPAN_ARGMAX` | 2/2 |
| conditional selected cohort | **132/132** |
| full development, exclusions counted as refusal | **132/200 = 66%** |

The 68 excluded rows are 52 compositional and 16 inference questions outside
this comparison operator family. The exact cohort and row hashes are selected
and sealed in the same run, not by an independent pre-run cohort manifest.

The controls have useful development teeth:

| control | exact / supported | interpretation |
|---|---:|---|
| reducer inversion | **0/132** | reducer token changes every terminal |
| same-type Value swap, ordered reducers | **0/107** | branch-bound operand matters |
| same-type Value swap, set equality | 25/25 | intentionally symmetric; no null tooth |
| type-erased string executor | **80/132**, 2 refused | typed Date/Duration/Country operators matter on this artifact |
| strict resolver only | **109/132**, 23 refused | development-tuned semantic entity resolution supplies 23 cases |
| type-tag mutation | 132 refusals | actual mutation plus hard validation |
| evidence-digest mutation | 132 refusals | actual mutation plus integrity validation |
| repeat / reversed fact order | 132/132 identical | deterministic sealed terminals |

This result is nearly oracle execution by construction:

- evaluator evidence triples supply the facts and relation/path schema;
- those triples can contain the answer or an answer-identifying value;
- only the reducer family is parsed from raw question text;
- the explicit answer field is read after terminal sealing, which proves API
  ordering but not information isolation;
- `semantic_2wiki_oracle.py` is a dataset-specific executor, not the common
  `semantic_layer_routing.py` kernel;
- evidence is bound to the evaluator triple hash, not to an exact selector in
  the source paragraph;
- the entity/country resolver was developed against this development artifact;
  it has no held-out generalization result;
- normalized exact is NFKC/casefold lexical exact, not byte identity.

The 132/132 result therefore establishes only this:

> A bespoke typed executor can reproduce the selected 2Wiki development
> comparison terminals when evaluator annotations supply its fact memory and
> path schema.

It is not HSWM retrieval, evidence discovery, label-blind reasoning, raw-language
program induction, common-kernel real-data validation, or cognitive uplift.

Source: `semantic_2wiki_oracle_result.json`, result SHA-256
`2f62a2926614f8bde4c0e5a9a467084fc8a07853b29ecd8b2682d22d16332500`.

## What changed in the theory verdict

Before this experiment, the observed failure could be read too broadly as
"stacked HSWM does not reason." The evidence now supports a narrower diagnosis:

1. Homogeneous recurrence over the available B1 paragraph reads does not help.
2. An explicitly supplied heterogeneous semantic program can perform
   branch-preserving map/reduce/lookup with evidence receipts.
3. Real benchmark relation shapes are representable by typed operators under
   evaluator-supplied memory.
4. What remains missing is the hard part: compiling the semantic program from
   the raw question and populating its typed, exact-source-bound memory without
   evaluator help.

So the Q/K/V analogy is useful only at the operator level:

```text
Q = typed unresolved goal and bound frontier
K = typed evidence address or reducer key
V = evidence-bound filler, branch-bound entity, or derived typed output
next Q = a new semantic state, not the old vector plus another read
```

Calling this a neural network would still be premature. It is presently a
deterministic typed symbolic runtime with Q/K/V-shaped interfaces.

## Next decisive experiment

The next valid efficacy step is not another synthetic layer. It requires:

1. a complete development B3 extraction produced under a current manifest,
   without evaluator evidence triples;
2. exact document selectors and typed claims admitted into the common semantic
   runtime;
3. a separately frozen raw-question program compiler;
4. answer/support isolation until after receipt sealing;
5. matched static, fixed-state homogeneous, heterogeneous typed, and mutation
   arms on the full finite development cohort;
6. a newly sealed fresh artifact if development gates pass.

The historical partial B3 cache has zero development queries with all required
gold facts usable, so a cherry-picked no-label subset is forbidden. The earlier
fresh-v4 paragraph-source-ID metadata read also means the affected fresh
artifact cannot be called completely blind; a confirmatory run needs a new
seal.

## Validation

Focused checks at result freeze:

```text
tests/test_semantic_layer_routing.py
tests/test_semantic_layer_falsifier.py
tests/test_semantic_2wiki_oracle.py
tests/test_verify_efficacy_claims.py

20 synthetic semantic tests passed
4 2Wiki oracle tests passed
2 efficacy-ledger tests passed
```

Full source-tree validation: **399 passed in 30.48s**.
