# HSWM-DNRD-5 one-block actual-byte corpus

- Date: 2026-08-28
- Corpus contract: `hswm-dnrd5-one-block-actual-byte-corpus/v1`
- Judge contract: `hswm-dnrd5-independent-actual-byte-judge/v2`
- Intended success terminal:
  `FIXTURE_BYTE_CLOSURE_VALIDATED_NOT_PROVIDER_OCCURRENCE_OR_SCIENTIFIC_RESULT`
- Provider/model calls authorized by this design: `0`
- Status: `FIXTURE BYTE CLOSURE VALIDATED / SOURCE-A BLOCKED`

## Validation outcome

The deterministic fixture producer and the separately implemented judge now
close one complete block under this contract.  Two consecutive clean
regenerations produced the same canonical root SHA-256:
`ccf11bb67b406e226da7efc4b76c9512e7d581a54af109a650a914dbf8775271`.
The judge independently rederived 390 unique indexed blobs, 87 admitted atoms,
78 journal listings (one genesis plus 77 commits), all 59 lifecycle adapter
rows, nine fixture receipts, ninety receipt-bound raw content roles, and the
99 logical provider bindings.

The mutation suite and independent read-only falsification covered missing and
extra blobs, descriptor substitution, lifecycle same-kind arm swaps, journal
predecessor and listing mutations, effect/write-set mutation, provider order,
projection substitution, hidden-field leakage, evidence-source substitution,
counter drift, terminal-order drift, filesystem aliasing, and root-identity
drift.  Initially passing same-kind lifecycle and journal-schedule swaps were
treated as false positives; the v2 judge now requires exact ordered atom, arm,
slot, derived transition, canonical admission schedule, audit, receipt, and
terminal key equality.  Later fresh mutation rounds confirmed those attacks
now fail closed.

The judge validates structurally conforming candidate corpora and returns each
candidate's independently derived root; it does not make one known hash the
definition of validity.  The `ccf11b...5271` root above is the checked-in known
answer and is pinned by its regression test.  A fully resealed candidate may
use different otherwise-valid nonreceipt atom identifiers and therefore have a
different root; this is intentional.  Receipt UIDs, by contrast, remain
cryptographically bound to their postcommit identities.

This validates only the deterministic fixture's byte coherence and the tested
falsifiers.  The four source/tree/build/import evidence roles remain explicitly
typed placeholders, the fixture transport vocabulary is not a provider
receipt, and no model or provider call occurred.  Source/build/import closure,
the sole Permit/provider dispatcher, authenticated authority/time/custody, and
all occurrence and efficacy evidence remain open.

## Canonical role, present evidence, and conceptual delta

HSWM's target remains one token-native LLM-function macro-neural network whose
schema-admitted evolving hypergraph is simultaneously its living harness,
world model, and continuous learner.  A corpus, repository KG, lifecycle
projection, or judge is only bounded evidence about that state.  None is a
separate cognition or learning subsystem.

The present DNRD-5 evidence now includes one deterministic, production-shaped
fixture block whose instrument bytes are closed under one manifest and replayed
by a separately implemented judge.  That closes the earlier integration gap
between the task, randomization, lifecycle, provider vocabulary, Permit,
successor-schema, transaction, main-effect, and postcommit-receipt instruments.
It does not establish that a provider occurrence happened or that the modeled
block learned anything.

The next conceptual delta is to replace the fixture's typed source, build, and
import placeholders with locally rederived no-call closure, then enforce one
Permit-mediated dispatcher before any Source-A freeze can be considered.  This
remains instrument qualification, not another scientific arm, pilot
observation, or unregistered model run.

## Closed corpus object

The corpus is one exact canonical object plus a content-addressed blob map.  Its
root manifest must bind every blob by media type, byte length, and SHA-256.  The
judge rejects missing and extra descriptors, duplicate logical identities,
unindexed blobs, descriptors whose bytes do not hash back, and any root hash
that is not independently rederived.

The object must close these sets for exactly one block:

1. The preserved lifecycle and lifecycle-alignment bytes, the exact v2 schema
   bytes, their pinned identities, all 15 ordered events, and all 59 row
   adapters.  The four assignment rows resolve to one assignment atom and four
   distinct fork atoms.  Every previously opaque structural handle resolves to
   one schema-approved canonical atom key of the required kind.
2. Every admitted canonical atom's raw payload bytes, content descriptor,
   canonical envelope bytes, typed references, responsibility owner, and
   provenance source.  Atom keys are unique, all external references resolve,
   and every atom kind has exactly its schema-relative owner.
3. One genesis plus the complete ordered journal lineage.  The v2 judge
   independently rebuilds the canonical stable topological schedule from atom
   references, provenance, core atom order, and the frozen special-group
   priority.  For this 87-atom corpus that schedule is exactly 77 commits: 67
   singleton support/decision commits and ten two-atom effect, receipt, audit,
   or terminal commits.  It contains exactly three ADMIT main-effect records,
   one RESTORE main-effect record, three revision receipt-seal records, one
   rollback receipt-seal record, one delayed audit-release seal, and one
   terminal manifest/block-seal record.  ACTIVE, SHAM, EXACT, and rollback
   occur in that order, and each main effect is immediately followed by its
   matching receipt seal before a later state effect or probe may depend on it.
4. The exact block, assignment, W0/four-fork, proposal, validation, credit,
   decision, projection, trajectory, blind-probe, hidden-outcome, placebo,
   escrow, rollback, audit-release, evidence-manifest, and block-seal closures.
   The manifest derives its exact atom, payload, envelope, and journal sets from
   the corpus; it may not accept a caller-selected subset.
5. The exact fixture nine-call grammar: one `PRE_OUTCOME_TRAJECTORY`, four
   `REVISION_PROPOSAL`, and four `FRESH_PROBE` calls.  There are exactly nine
   canonical START records and nine successful terminal records in one
   hash-chained fixture ledger.  Call IDs, session IDs, worker IDs, private
   bindings, request nonces, and RNG descriptors are unique in the block and
   are bound to their declared opaque slot.
6. For every call, the exact fixture receipt plus its ten raw content roles:
   request projection, transmitted request, observed response, RNG, model
   identity, runtime identity, isolation statement, instruction, model input,
   and response schema.  This is 99 logical content bindings: nine receipts and
   ninety receipt-bound roles.  The content-addressed store's unique-blob count
   is independently derived because equal immutable bytes may deduplicate; it
   is never assumed to equal 99.
7. Exact evaluator input/output, genuine and placebo commitment/opening,
   assignment/randomness receipt, Permit input/resolution, authorization,
   revocation, trusted-time placeholder, source/tree, selected build,
   allowed-import graph, runtime, and custody/isolation statement bytes.  A
   placeholder or declaration remains explicitly typed as such and cannot be
   promoted to authenticated evidence by inclusion in the corpus.

## Normative TypeScript-to-Python byte-replay bridge

The corpus shares bytes, never a TypeScript validator result.  The independent
judge implements this frozen replay grammar directly:

- All schema, atom-envelope, state, journal, manifest, and fixture-ledger JSON
  uses `hswm-canonical-json/v1`: strict UTF-8, duplicate-key rejection, compact
  encoding, safe integers other than negative zero, no trailing bytes, UTF-16
  object-key order, a 1 MiB object bound, depth 128, and 100,000 nodes.
- A canonical atom key ID is exactly
  `schemaVersion|lineageId|atomUid|revisionId`.  State atoms and journal write
  bindings are strictly sorted by that text ID.  Every key component uses the
  Canonical Atom V2 ASCII Identifier domain and the revision is a safe
  nonnegative integer.  Atom envelope bytes are the
  exact canonical atom object and use
  `application/vnd.hswm.canonical-atom-v2+json`.
- The initial state is exactly `{schemaVersion, revision: 0,
  bootstrapClosed: false, atoms: [], acceptedTransitionIds: []}`.  A successful
  commit increments the revision once, permanently closes bootstrap, appends
  the transition ID, and adds immutable writes before sorting all atoms by key
  ID.  No transition ID or canonical/logical atom identity may repeat.
- The state SHA-256 is computed from the canonical bytes of the exact state
  object.  A commit's `previousStateSha256` and `resultingStateSha256` must equal
  the independently reconstructed states; no supplied state projection is
  authoritative.
- Genesis and commit records use
  `hswm-canonical-atom-v2-state-journal/v1` and media type
  `application/vnd.hswm.canonical-atom-v2-state-journal+json`.  Each descriptor
  is recomputed from exact record bytes.  Every commit names the immediately
  prior descriptor, same journal lineage and exact schema-content binding, and
  state revision `prior + 1`.
- The corpus root is a regular directory containing exactly one regular
  `manifest.json` and one regular `blobs/` directory.  Symlinked roots,
  manifests, blob directories, or blobs and any unbound top-level entry are
  rejected; content hashing is not used to disguise filesystem aliasing.
- A commit's accepted receipt reconstructs its command.  Its read set must be
  duplicate-free and present in prior state; writes must be new, schema-valid,
  owner-valid, and content/envelope-bound.  Each external typed/provenance
  source must be both in prior state and in the read set; same-batch sources
  must form an acyclic dependency graph.  The first commit alone may introduce
  bootstrap provenance.
- The exact v2 schema bytes, not a separately maintained Python kind table,
  supply allowed kinds, one owner per kind, reference target kinds, and role
  cardinalities.  DNRD-5 decision/effect/receipt/audit/manifest semantic
  equalities are additional judge rules and cannot be inferred from
  kind-correct references alone.

These rules are a cross-language contract, not a claim that the Python judge
is another HSWM state owner.  Any ambiguity discovered while implementing them
fails the fixture rather than being filled with a caller assertion.

## Fixture transport and provider-byte rule

The transmitted-request fixture and request projection are deliberately
different byte strings with different media types and descriptors.  The
projection binds private call/session/custody fields that transmitted bytes
must not reveal.  The actual-byte judge must reconstruct and compare each
object according to its own contract; it must not reuse the older TypeScript
nine-call helper that requires request bytes to equal projection bytes.

No network or model provider is called to build this corpus.  It therefore
must not mint the production gateway's client-observed transport receipt.  The
fixture instead uses the separate frozen vocabulary
`hswm-dnrd5-fixture-transport-receipt/v1`, and every receipt and START/terminal
record carries
`DETERMINISTIC_FIXTURE_NOT_TRANSPORT_OR_PROVIDER_OBSERVATION`.  Deterministic
responses exercise the same ten-role byte grammar but are only fixture bytes.
A valid corpus establishes neither provider identity, TLS, dispatch,
provider-side exactly-once behavior, nor occurrence.  Equivalence between this
fixture grammar and the selected production gateway build remains a later
source/build/import qualification obligation.

## Independent judge

The judge is implemented outside the producer and must not import the corpus
producer, the TypeScript validators, or their local success projections.  It
may consume the frozen contract and standard cryptographic/JSON primitives,
but it independently:

- rejects noncanonical, duplicate-key, alternate, oversized, or unindexed
  bytes;
- rederives the root descriptor index and exact logical/unique blob closures;
- reconstructs all 59 lifecycle bindings and v2 kind/owner/reference closure;
- replays the complete journal predecessor, revision, state-hash, envelope,
  effect, receipt, audit, and terminal-seal chain;
- checks exact three-revision/one-rollback receipt cardinality and decision,
  consumption, effect, evidence-purpose, lineage, and descriptor equality;
- reconstructs the 18-record fixture ledger, nine receipts, ten per-call
  content roles, call grammar, unique private bindings/nonces/RNG, and the
  distinct projection/request bytes;
- rederives the manifest and block root from exact sets, rejecting a selected
  subset, extra descriptor, arm/fork swap, or valid graph paired with another
  provider or journal record; and
- returns only the frozen fixture terminal and boolean evidence boundaries.

The producer and judge share known-answer corpus bytes, not validation code.
Mutation tests must independently cover at least one omission, addition,
byte-preserving descriptor swap, arm/fork swap, journal predecessor change,
decision/effect cross-wire, receipt cardinality change, provider call-class
reorder, request/projection substitution, hidden-field leak, and root-manifest
change.

## Scientific boundary and next decision

This passing one-block fixture shows that the evidence instruments describe one
byte-coherent deterministic candidate and that the tested substitution attacks
fail.  It cannot
show that a provider call occurred, that hidden/placebo entropy was fair or
conditionally independent, that isolation declarations were true, that the
model learned, or that any arm improved a fresh probe.  It produces no effect
estimate, confidence interval, exact test, research-result receipt, or
`F1_R8_RESULTS_LOG.md` entry.

Only after this corpus and judge pass independent adversarial review may the
source/build/import closure and sole Permit/provider dispatcher be qualified.
Only a later no-call Source-A audit can decide whether a preregistered empirical
run is eligible.  No manual user hash echo is part of this preparation.
