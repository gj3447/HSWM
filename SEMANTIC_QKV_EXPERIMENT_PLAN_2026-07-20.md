# HSWM semantic-layer QKV experiment plan — 2026-07-20

Status: development-only mechanism protocol freeze, with a pre-exhaustive-run
causal-audit amendment. This is not a fresh confirmatory preregistration. Before
the first freeze, feasibility inspection had already counted the eligible
2Wiki development question types and checked that their date strings were
parseable. No semantic-layer execution outcome had been computed at that first
freeze. Core unit tests later ran before the control audit below was completed;
the 128-case registered falsifier had not yet run. This history is another
reason to treat the result as development evidence only.

## Canonical correction

The hypothesis is not "make the previous layer deeper". The user's correction
is the experiment's independent variable:

> 단순 겹겹이가 아니라 시멘틱한 겹겹. 그냥 무식하게 겹겹이 쌓으니까 그렇지.

The failed B1-QKV probe repeatedly updated one paragraph-vector state in one
embedding space. It did not test layers whose semantic type, cardinality, and
operator change. The corrected minimal stack is:

```text
Person
  --EXPAND(child)-->
BranchSet[Person]
  --MAP_ONE(birth_date), preserving branch lineage-->
BranchSet[Pair[Person, Date]]
  --REDUCE_SELECT(ARGMIN or ARGMAX; Date is K, bound Person is V)-->
Selected[Person]
  --LOOKUP_ONE(birthplace)-->
City
```

This is a typed evidence-bound operator experiment. It is not a claim that HSWM
is a neural network, that the operators are learned attention, or that semantic
types alone create general reasoning ability.

The treatment is the joint package of hard semantic-type gates, explicit
branch lineage, arity-changing state, and operator-specific transitions.
Experiment A identifies that package against registered controls; it does not
separately estimate the causal contribution of type tags, branching, reduction,
or layer order. The mutations below are conformance teeth, not independent
empirical treatment-effect estimates.

## Mechanism contract

Each layer has a hard input-state type and output-state type. Types are gates,
not soft score features. `EXPAND` admits one-to-many evidence matches and creates
content-addressed branches. `MAP_ONE` must find exactly one typed value per
branch and preserve branch identity. `REDUCE_SELECT` must consume at least two
complete branches and select a Value that remains bound to its comparison Key.
`LOOKUP_ONE` may read only from the selected entity.

The synthetic program, including `ARGMIN` versus `ARGMAX`, is supplied directly;
no natural-language program induction is tested in Experiment A. Expected
terminal IDs are literal fields in a separately hashed fixture manifest frozen
before the exhaustive run. Neither the treatment runner nor a mutation runner
may derive its expected terminal by calling the reducer implementation under
test.

The core program contains no answer, gold, support, hop, decomposition, or
evaluator fields. Every fact has exact evidence selectors. Every successful
layer receipt records the typed Q/K/V digests, before/after state roots, branch
lineage, evidence IDs, and the previous receipt root. Input order and repeat
execution must be bit-deterministic.

Any missing, ambiguous, mistyped, or out-of-order transition refuses the whole
query. Refusal returns the caller's static payload byte-identically, with no
externally visible partial state or successful-layer receipt.

## Experiment A — synthetic heterogeneous semantic stack

Each isomorphic world contains two children, their distinct birth dates, and
their distinct birthplaces. Two reducer programs ask for the older and younger
child's birthplace. A paired world exchanges only the two date Values while
preserving the relation/key/value multisets once branch association is erased.

```text
32 base worlds × 2 date assignments × 2 reducers = 128 cases
```

Frozen primary gates:

- full typed terminal exactness is `128/128`;
- every successful route proves the four hard type transitions and unbroken
  branch lineage;
- every Value selected by the reducer is still paired with the Date used as its
  Key;
- receipt-chain violations, static-payload refusal violations, repeat drift,
  and reversed-memory-order drift are all zero;
- tied reducers, incomplete branches, ambiguous single-value reads, and invalid
  layer order all refuse query-atomically.

Frozen matched controls:

- `SINGLE_FRONTIER_EXACT` applies the current exact-one-key routing contract.
  Its prediction is `AMBIGUOUS_KEY_MATCH` at the one-to-many child layer in
  `128/128` cases. This is an arity diagnostic, not the primary homogeneous
  comparator.
- `HOMOGENEOUS_REPEAT` preserves the supplied program, including its reducer
  token, but uses one fixed state shape and one repeated association-erasing
  transition. Its state contains only the typed value multiset and remaining
  program tokens; it carries no typed state variants, branch IDs, or Person-Date
  bindings. For a fixed reducer, the two paired date-assignment worlds must
  have the same control signature. Their terminals differ, so a deterministic
  signature-only policy has exactness at most `64/128`.
- `BRANCH_ERASURE` runs the same typed program through `MAP_ONE` and preserves
  reducer, fact types, relation keys, and value multiset, but removes branch IDs
  and Person-Date pairing immediately before `REDUCE_SELECT`. It must refuse
  `128/128` with `MISSING_BRANCH_ASSOCIATION`; it may not invent a caller-order
  pairing.

The exact canonical payload retained and erased by both controls, their refusal
policy, and their schema versions are frozen before the exhaustive run.
"Either refusal or collision" is not an admissible post-outcome definition.

Frozen conformance mutations:

- `TYPE_MUTATION` changes one birth-date target type while preserving its
  payload; the query must refuse with a type mismatch;
- `KEY_MUTATION` exchanges birth-date and birthplace predicates while
  preserving evidence/value bundles; it must not reproduce the original
  frozen terminal;
- `VALUE_BINDING_MUTATION` exchanges same-type Date Values between branches
  while preserving keys, types, and branch count; it must not reproduce the
  original frozen terminal;
- `REDUCER_MUTATION` exchanges `ARGMIN` and `ARGMAX`; it must select the opposite
  branch on the distinct-date fixture. This proves reducer-token sensitivity,
  not treatment superiority;
- `LAYER_ORDER_MUTATION` exchanges map/reduce or reduce/lookup and must refuse
  before executing a layer;
- evidence corruption must be rejected before a typed Value enters state.

Because several mutations deliberately change the meaning of the program or
memory, their zero original-terminal count is implementation conformance, not
causal evidence that heterogeneous execution outperforms another reasoner.

Passing Experiment A permits only this claim:

> On the frozen synthetic two-branch child/date/birthplace fixtures, this
> implementation deterministically executed a supplied heterogeneous typed
> program with branch-preserving map, typed reduction, value-bound lookup,
> evidence receipts, and query-atomic refusal.

It does not establish natural-language program induction, learning, real-data
retrieval or answer uplift, general semantic-layer capability outside the
frozen operator family, cognitive uplift, or an impossibility theorem for
arbitrary homogeneous or learned QKV systems.

## Experiment B — 2Wiki evaluator-supplied-memory executor coverage probe

Feasibility inspection selected 132 of the 200 already-open 2Wiki
development-v4 rows after inspecting question type and date parseability:

- 32 `comparison` rows;
- 100 `bridge_comparison` rows.

The runner selects and seals the exact 132 qids, raw-row hashes, eligibility
rule, and one exclusion reason for each remaining row in the same development
run. This is not an independently pre-sealed cohort or preregistered root.
Accuracy on 132 rows is conditional on this post-inspection cohort; all 200
rows are also reported with exclusions counted as refusals.

Typed facts and branch/path schema are assembled from evaluator evidence
triples. Those triples may directly contain the benchmark answer or an
answer-identifying value. Withholding the explicit answer field until after the
receipt is sealed is an ordering and implementation-separation check; it is
not answer-information isolation. This is not retrieval, label-blind reasoning,
or end-to-end QA.

Experiment B uses a dataset-specific executor, not the synthetic
`semantic_layer_routing.py` kernel. Its evidence binding is a canonical hash of
the evaluator triple, not an exact selector into the source paragraph. Its
entity/country resolver was inspected and tuned on this development artifact.
Those differences forbid using B as real-data validation of the common kernel,
held-out resolver generalization, or HSWM's document-evidence path.

Only the reducer family is selected from raw question text. Branch structure,
relation path, property slots, and typed facts are oracle-supplied by evaluator
triples and recorded as such. The separately hashed reducer parser uses exact
NFKC-casefold/token-boundary rules:

- `first`, `earlier`, `older` -> `ARGMIN_DATE`;
- `recent`, `later`, `younger` -> `ARGMAX_DATE`;
- `same` -> `NONEMPTY_SET_OVERLAP`;
- `longer` -> `ARGMAX_LIFESPAN`.

Exactly one operator family must match. Zero or multiple matches refuse without
using dataset type, answer, gold, or support labels to resolve the ambiguity.
The inspected cohort contains 75 minimum-date, 30 maximum-date, 25 set-overlap,
and 2 lifespan programs; results are reported separately for all four shapes.

Direct comparison uses two candidate branches. Bridge comparison first maps
each candidate through its director branch and then reads the compared typed
property. Multiple citizenship Values remain typed sets for overlap; they may
not be collapsed to a caller-ordered scalar. Unsupported parse or schema cases
must be reported as refusals, never silently repaired with the answer.

This arm reports eligibility over all 200 rows, exclusion reasons for the 68
out-of-scope chain rows, refusal-counted-as-incorrect accuracy over all 200,
conditional accuracy over 132, per-operator accuracy, type/branch/evidence/
receipt integrity, explicit-answer ordering receipts, and registered control
and mutation diagnostics. The association-erased diagnostic preserves reducer
and program shape and erases only branch identity/cross-branch bindings.

No uplift or upper-bound gate is attached because evaluator evidence constructs
both memory and path schema. The maximum Experiment B claim is:

> executor coverage and conditional terminal accuracy on a post-inspection
> 2Wiki development cohort using evaluator-supplied typed facts and path schema.

It cannot support retrieval uplift, evidence discovery, label-blind reasoning,
natural-language program induction, fresh generalization, or HSWM cognitive
uplift.

## Deployment boundary

The current B3 cache is incomplete, so no deployable raw-query plus extracted
claim-memory efficacy run is authorized here. A future deployable test requires:

1. complete development B3 claim extraction built without evaluator triples;
2. a separately frozen raw-question program compiler;
3. answer/support isolation until the execution receipt is sealed;
4. matched static, homogeneous, typed, and null arms;
5. a new sealed fresh protocol before any confirmatory efficacy claim.

Fresh H3-B3 segments, manifests, labels, and gates remain out of scope and must
not be modified or inspected further by this experiment.

### Fresh-boundary contamination disclosure

During parallel feasibility inventory, one read-only check accidentally loaded
the fresh-v4 paragraph `source_id` set to measure cache intersection. It did not
load or use fresh questions, answers, gold IDs, or evaluation rows, and none of
the development results in this experiment use that set. Nevertheless, the
affected fresh artifact is no longer eligible for a claim of completely blind
prospective evaluation. A future confirmatory run needs a newly sealed fresh
artifact. This disclosure was added before semantic execution outcomes were
sealed by the registered 128-case falsifier or the 132-row development runner.
