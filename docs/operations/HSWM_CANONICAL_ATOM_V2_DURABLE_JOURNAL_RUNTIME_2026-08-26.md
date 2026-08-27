# HSWM canonical-atom v2 durable journal runtime

> **Date:** 2026-08-26
>
> **Status:** `IMPLEMENTED_LOCAL_PREDECESSOR_BOUND_DURABILITY_REFERENCE_SCOPE / NOT_CANONICAL_PERMIT / NOT_LEARNING / SCIENTIFIC_UNJUDGED`
>
> **Authority:** bounded engineering continuation for canonical-atom v2 phase
> 3. It implements recoverable local state continuity, not a new HSWM ontology or a
> result about intelligence, learning, or authorization.

## 1. Canonical role and conceptual delta

The constitutional target remains one evolving hypergraph of schema-admitted
canonical atoms and typed references. The living harness/world-model role
requires more than retaining process memory: a later runtime must be able to
test whether a proposed current state is the causally continuous successor of
an exact prior state. This phase supplies a narrow, replayable evidence path
for that continuity.

It does not make the journal a second cognition, a replacement world model, or
an external controller. The journal is a bounded persistence substrate for the
same canonical transition model:

```text
canonical schema bytes + revision-0 genesis
  -> immutable predecessor-bound commit records
  -> exact receipt + payload/envelope bindings
  -> deterministic replay and state commitment verification
  -> reconstructed canonical state used by the next transition
```

The former fixed `H/W/A/F/Π` decomposition remains retired. For historical
comparison only, this phase persists and replays the admitted relational state
that older notes might project as `H`, and re-executes the deterministic
transition realization that they might project as `F`. It does not create a
separate `H` or `F` owner/component; it changes no learned `W`, supplies no
canonical authorization `A`, and compiles no projection `Π`.

In the constitutional causal-learning loop, this is only state-continuity and
receipt infrastructure around a bounded `Step_σ` realization. There is no
sealed typed trajectory, external outcome, causal credit, owner-valid learned
revision, changed traversal disposition, or admitted `Learn_σ` transition.
Replay is therefore a prerequisite evidence mechanism, not continuous
learning.

`journalLineageId` names this journal continuity domain. It is deliberately
separate from an atom's `lineageId`, atom UID, revision identity, provenance,
or evidence of identity of an HSWM instance. It scopes a local journal and its
fixed publication slots; it neither proves an atom's identity nor turns a
journal writer, file custodian, executor, validator, or authorizer into that
atom's schema-relative responsibility owner. Each admitted atom still has
exactly one owner only as declared by the active schema.
`journalLineageId` is also not a globally exclusive registry: independent
roots can reuse it and form separate observed prefixes unless a later external
coordination or witness contract prevents that.

## 2. Exact record model

The record codec is `hswm-canonical-atom-v2-state-journal/v1` over exact
`hswm-canonical-json/v1` UTF-8 bytes. Parsing rejects duplicate keys before
object materialization; accepted on-disk record bytes must already equal the
codec's canonical bytes. Re-encoding permissive JSON before calculating a
digest is not recovery.

The immutable genesis is the only record at state revision `0`:

- it has a valid `journalLineageId`, the exact active schema content descriptor,
  `bootstrapClosed: false`, and `predecessor: null`;
- its state commitment is the SHA-256 of the deterministic empty v2 state for
  that exact schema version; and
- it has no receipt or atom write bindings.

Every later record has a strictly next state revision and contains:

- the same journal lineage and schema content binding;
- an immutable descriptor of its *immediate* predecessor record (media type,
  length and SHA-256);
- the exact accepted reference-kernel receipt;
- a one-to-one, sorted set of write bindings for atom key, payload descriptor,
  and canonical metadata-envelope descriptor;
- commitment digests for both the immediately previous and the deterministically
  resulting state; and
- the explicit label
  `LOCAL_PREDECESSOR_BOUND_JOURNAL_V1_NOT_CANONICAL_PERMIT_NOT_LEARNING`.

The predecessor descriptor chain, revision adjacency, schema binding and state
commitments are all independently checked. A matching hash alone is not enough:
the record is decoded strictly, the referenced envelope is canonical and
key/payload-bound, the receipt is reconstructed deterministically, and the pure
transition reducer must produce the committed successor state.

## 3. Replay is the truth source

Recovery begins at the unique revision-0 genesis and applies every following
record in slot order. For each commit it verifies, before exposing a successor:

1. exact canonical record bytes and record descriptor;
2. immediate predecessor descriptor, journal lineage, contiguous revision and
   unchanged schema-content binding;
3. the schema blob's exact bytes and descriptor;
4. every payload and atom-envelope blob's existence, byte length, SHA-256,
   media type, canonical JSON form, atom key and write-binding bijection;
5. the deterministic receipt and pure domain transition; and
6. previous and resulting state commitments.

Thus a mutable in-memory state, receipt cache, file listing, or content object
is never the source of canonical state by itself. Such values are derived
snapshots only and may be discarded and reconstructed from the verified record
prefix. Returned record, receipt, descriptor and state snapshots remain
defensively immutable.

The recovery stance is fail closed. A gap, malformed entry, duplicate JSON key,
noncanonical bytes, invalid descriptor, altered predecessor, forked slot,
schema drift, missing/corrupt content, receipt mismatch, or state-commitment
mismatch rejects recovery. It must not silently select a longest valid prefix.
Only the absence of the *next* fixed slot is an ordinary end of the journal.

This also fixes the exact completeness boundary: without a separately trusted
monotonic head witness, deletion of one or more complete trailing slots is
indistinguishable from a journal that legitimately ended at the remaining
prefix. The hash chain proves integrity and causal order *within the observed
prefix*; it does not prove that the observed head is the highest head ever
published. This phase therefore makes no anti-rollback or fresh-root
completeness claim.

## 4. Local POSIX publication, crashes, and races

The reference file adapter uses a private absolute `0700` root with distinct
object and fixed-slot directories. It validates path/dir identity and
permissions, derives final names from validated hashes, rejects nonregular and
symlinked entries, bounds reads, and uses `O_NOFOLLOW` where Node permits it.
Root creation is nonrecursive: the immediate controlled parent must already
exist. Initialization rejects a symlink supplied as the root, fsyncs the actual
parent after provisioning the root, and fsyncs the root after provisioning the
object and slot directories.
Node lacks `openat2`; therefore controlled parents and the adapter's stated
local POSIX assumptions remain required.

Publication is ordered as follows:

```text
canonical journal record bytes
  -> immutable content-addressed object: temp O_EXCL/no-follow write
     -> chmod 0400 -> file fsync -> create-only hard-link -> directory fsync
  -> one deterministic revision slot: create-only hard-link to that object
     -> slot directory fsync -> exact readback/recovery
```

The fixed slot name binds `journalLineageId`, active schema digest and state
revision. It is a local compare-and-set anchor: two writers contending for the
same fixed slot in one local root incarnation, with the same complete
predecessor descriptor (media type, byte length and SHA-256) but different
successor bytes, have at most one winner while that observed slot entry remains
intact; the loser gets a conflict/stale-predecessor result and no committed
receipt. Retrying the same exact bytes for an occupied slot is idempotent,
re-fsyncs the object and slot directories, and reports the already committed
recovery prefix. This is one-winner concurrency within a retained slot
incarnation, not global or lifetime uniqueness after root cloning or external
deletion.

A failure before slot publication may leave a content-addressed journal object
or temporary file. This is an unclaimed orphan, not a committed atom, receipt,
or state transition. A visible final slot must point to exactly the same inode
and bytes as its immutable object, then pass complete replay. A directory-sync
ambiguity is reported as an unknown publication outcome until exact recovery
can establish the winner; it is not converted into success by assumption.
Garbage collection of orphan content is intentionally deferred until a
reachability policy is specified from the durable journal.

## 5. Narrow durability claim and explicit nonclaims

Within the stated local POSIX adapter assumptions, a successfully published,
read-back immutable record can be recovered as a contiguous predecessor-bound
prefix and replayed against its referenced content. This is a local durable
state-and-receipt journal reference scope. It is not evidence of universal
power-loss behavior, filesystem-independent durability, or distributed
agreement.

In particular, this phase does **not** provide:

- canonical `Permit` verification, expiry/revocation/consent semantics, or an
  inference from receipt, owner, custodian, or journal writer to permission;
- sealed trajectories, outcomes, causal credit, outcome-bound continuous
  learning, or a claim that replay itself changes future dispositions;
- replication, quorum, consensus, CRDT conflict resolution, or a distributed
  fork-choice rule;
- a power-loss proof for every OS, device, filesystem, network filesystem, or
  hostile-parent-path environment;
- schema migration, atom/journal fork or merge, rollback/compensation, or a
  cross-version identity proof;
- external-effect exactly-once delivery. The journal records a local accepted
  state transition, not completion of an arbitrary external action;
- an externally witnessed monotonic head, anti-rollback protection, or proof
  that a freshly opened valid prefix has not lost a complete trailing suffix.

The reference grant receipt label remains
`REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT`; durable storage does not
strengthen it. The phase remains `SCIENTIFIC_UNJUDGED`.

## 6. Verification

The checked-in deterministic suite covers the exact record codec, canonical
genesis, two-step pure replay, receipt/binding/state/envelope tamper rejection,
memory-store contiguity, file restart, exact retry, stale predecessor and
independent-writer races, runtime restart through two revisions, finalized-slot
permission drift, complete-descriptor CAS mismatch, unsafe root symlinks,
missing reachable payload content, frozen results, and failed proposal prefix
invariance. It now also interrupts every ordinary commit at 14 exact
before/after checkpoints spanning object file fsync, object link,
object-directory fsync, object readback, slot link, slot-directory fsync and
final journal readback, plus genesis at representative pre-slot and post-slot
checkpoints. Every case opens a fresh Layer and observes only the old exact
prefix or the old prefix plus the exact new record. Non-tail gaps, hard-linked
record truncation, and missing journal objects fail closed. Fresh
durable-runtime reopening separately demonstrates that a non-tail gap and a
missing referenced object fail closed, while complete tail deletion can expose
an intact shorter prefix and therefore remains an explicit anti-rollback
nonclaim. A re-addressed `{}` journal object also demonstrates the boundary
between the raw store and the runtime: structural hard-link recovery succeeds,
but strict canonical replay rejects the record as `RECORD_INVALID`.

The interruption seam throws a tagged exception inside a still-running test
process; JavaScript cleanup may therefore run. It demonstrates fresh-replay
exposure invariants, not physical power loss, kernel writeback behavior, device
flush behavior, or universal crash durability.

A separate Layer-local fault plan now throws raw native-like `Error{code}`
values immediately before or after selected adapter calls. It exercises the
actual link/fsync catch paths and bounded readback normalization without a
global toggle, environment switch, or package-root export. One-shot object/slot
fsync errors must resynchronize; repeated exact-retry resync errors remain typed as
`PUBLICATION_OUTCOME_UNKNOWN`. Once a slot may be visible, persistent slot
fsync failure or final readback `EIO` is also classified as outcome-unknown,
and a fresh fault-free Layer independently determines the exact visible
prefix. Before-slot link/readback failures retain the old prefix. Synthetic
native-like errors validate adapter control flow, not actual kernel or device
fault semantics.

The live-process suite additionally coordinates two distinct PIDs at the
pre-slot-link boundary after both observed the same empty prefix. This creates
a deterministic stale-prefix hard-link CAS competition without claiming
simultaneous kernel scheduling. One different-byte round yields exactly one
`Committed` record and one typed
conflict; an identical-byte round yields one `Committed` and one
`AlreadyCommitted`. A third fresh observer process recovers one exact record,
and the winning slot and content-addressed object have the same device/inode.
This is bounded evidence for the pinned Node/vite-node toolchain on a local
POSIX filesystem, not NFS/SMB behavior, distributed exclusion, prolonged load,
or crash/power-cut durability.

Implementation and review must retain at least these categories:

| Category | Required evidence |
| --- | --- |
| Genesis/restart | exact revision-0 genesis, multi-revision fresh-runtime replay, and replay idempotence |
| Canonical ingress | duplicate-key, malformed, non-UTF-8/bounded, and noncanonical-record rejection |
| Chain integrity | predecessor/hash/state-commitment tamper, gap, reorder, duplicate slot, fork, and truncated record bytes fail closed; complete trailing-slot deletion remains an explicit anti-rollback nonclaim |
| Content integrity | missing or changed schema/payload/envelope bytes and descriptor/schema drift reject replay |
| Publication/interruption | package-root-private, internal test-only deterministic interruptions before/after object fsync/link/readback and slot link/fsync/final readback yield either no claimed slot or one wholly replayable record; unclaimed orphans are allowed |
| Native-like I/O faults | Layer-local raw `EIO` and unsupported-link errors exercise actual adapter catch branches; persistent post-slot failures are outcome-unknown and fresh replay decides visibility |
| Concurrency | in-process writers and barrier-coordinated independent PIDs have one fixed-slot winner; stale predecessor fails; exact winner retry is idempotent; different bytes conflict |
| Snapshot/failure | receipt/state nested snapshots cannot mutate future reads; rejected domain/permission/store paths leave committed prefix unchanged |
| Public boundary | package root exposes no raw slot overwrite, journal bypass, mutable cache, or unsafe receipt-construction path |

These tests are executable invariant evidence, not proof of HSWM cognition,
scientific efficacy, or a natural unique atomization.

## 7. Implemented boundary and next order

`canonical-atom-v2-durable-runtime.ts` now performs the former integration
steps: initialization publishes or reconciles the exact genesis, every state or
history read replays the current journal, submit preflights before content
publication, the fixed slot is the commit point, and the returned state and
receipt come from a fresh verified replay. No process-local state cache is
accepted as recovery truth.

The file adapter now has package-root-private, internal test-only factories for
the 14 logical interruption checkpoints, a sequential native-like I/O fault
plan, and a pre-slot-link process barrier. They are compiled into the internal
module but production fixes interruption/fault/hook inputs to
`null`/empty/`null`; none is exposed as a runtime command, environment variable,
or public mutation capability. These are evidence instruments for the existing
transition contract, not HSWM state components or a learning advance.

The next implementation order is:

1. Add a platform fault harness outside the process for actual filesystem
   failure semantics, then expand process count, duration, filesystems and
   supported-OS coverage. Keep physical power-cut testing as a separate
   platform claim.
2. Specify typed canonical authorization, trace, provenance, outcome and
   rejection/quarantine evidence without treating them as automatically
   authorized or learned.
3. Specify an external monotonic-head witness before making any completeness or
   rollback-resistance claim; only after that, specify migration, fork/merge,
   compensating restore, loss-declared projections, and outcome-bound learning
   proposals.

No research receipt or results-log entry accompanies this document: it is an
operations and engineering handoff, not a material scientific result.
