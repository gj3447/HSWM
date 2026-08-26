# HSWM canonical-atom v2 content-bound runtime

> **Date:** 2026-08-26
>
> **Status:** `IMPLEMENTED_LOCAL_CONTENT_DURABILITY / STATE_JOURNAL_NON_DURABLE / SCIENTIFIC_UNJUDGED`
>
> **Authority:** bounded engineering continuation of the canonical-atom v2
> reference kernel. It strengthens byte identity and retrieval integrity; it
> does not add a philosophical, authorization, learning, or efficacy claim.

## 1. Canonical role and conceptual delta

The target identity remains one schema-relative canonical atom model inside
one evolving HSWM. This phase does not introduce a content subsystem that is
itself cognition. It supplies the byte-identity condition needed for a
canonical schema and atom to remain inspectable rather than existing only as
ephemeral JavaScript objects.

The phase-1 reference kernel bound atom payloads only by a caller-supplied
descriptor and bound the active schema only by `schemaVersion`. The new
content-bound facade adds three independent byte domains:

```text
raw payload bytes
  -- SHA-256(raw bytes) --> payload descriptor

strictly decoded schema
  -- hswm-canonical-json/v1 --> schema bytes --> schema content descriptor

strict canonical atom metadata
  -- hswm-canonical-json/v1 --> atom-envelope bytes --> envelope descriptor
```

The atom envelope contains the key, kind, single responsibility owner, payload
descriptor, provenance, lifecycle and typed references. Its digest therefore
changes when accountability or relational metadata changes even if the payload
bytes remain the same.

These digests establish byte equality and retrieval integrity only. They do
not establish truth, sufficient provenance, current permission, causal credit,
semantic equivalence or collision impossibility.

## 2. Bounded canonical JSON

[`canonical-atom-v2-json.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-json.ts)
defines `hswm-canonical-json/v1`:

- duplicate object keys are rejected before object materialization;
- input and output are bounded to 1 MiB, depth 128 and 100,000 nodes;
- only null, booleans, strings, safe integers, arrays and plain objects exist
  in this domain;
- floats, exponent notation, `-0`, unsafe integers, lone surrogates, cycles,
  sparse arrays, accessors, symbols and non-plain objects are rejected;
- object keys use deterministic UTF-16 lexical order;
- output is UTF-8 without whitespace or a terminal newline;
- Unicode normalization is not performed.

Schema ingress accepts duplicate-free JSON with arbitrary insignificant
whitespace or object-key order, then hashes the decoded schema's canonical
encoding. Array order and exact Unicode code points remain identity-bearing.
This is a named HSWM encoding contract, not an assertion of RFC 8785
conformance and not the historical S2S control-JSON hash domain.

## 3. Content store and schema binding

[`canonical-atom-v2-content.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-content.ts)
defines the Effect content-store port. Payload SHA-256 is always computed from
the exact supplied bytes; media type is separately retained in the descriptor
and is not concatenated into the digest preimage. `put`, `get` and `verify`
defensively copy and recheck byte length and digest. A schema version can be
bound once to one exact schema content descriptor. A later different binding
fails closed rather than overwriting the first. This reference port bounds one
payload at 16 MiB.

The package-root facade does not export the raw store or raw schema-binding
mutation capability. Callers stage and read content through the narrower
content runtime.

[`canonical-atom-v2-content-file.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-content-file.ts)
implements a local POSIX/Linux adapter:

1. require an absolute, non-symlink, private `0700` root whose immediate parent
   already exists, then fsync the root entry and child-directory provisioning;
2. derive every final filename from a validated lowercase SHA-256 digest;
3. write a same-directory `O_EXCL | O_NOFOLLOW` temporary file;
4. change it to `0400`, fsync the file, hard-link create-only to the final
   name, fsync the directory and exact-read the result;
5. treat identical publication as idempotent and never overwrite different or
   corrupt final bytes;
6. reject symlink/non-regular entries, changed directory identity, size drift,
   digest drift and unsafe permissions.

This adapter assumes the root and its parents are controlled by the runner.
Node does not expose `openat2`; hostile parent replacement, network filesystem
semantics, Windows, remote replication, encryption and multi-host consensus are
outside its claim.

## 4. Content-first admission boundary

[`canonical-atom-v2-content-runtime.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-content-runtime.ts)
keeps the original pure reducer unchanged and wraps it with a stricter Effect
boundary:

```text
strict content-bound command decode
  -> exact schema-digest grant match
  -> active schema bytes verification
  -> pure domain candidate validation
  -> prior bound-content verification
  -> all proposed payload verification
  -> create-only atom-envelope publication
  -> Ref.modify state + one content-bound receipt
```

The command's write bindings must form an exact bijection over its write set.
Each binding contains the atom key, exact payload descriptor and exact metadata
envelope descriptor. The accepted receipt retains the active schema binding and
those sorted write bindings without embedding payload bytes.

No content is written for an authorization or pure-domain rejection. A store
failure never changes state or history. Two concurrent commands may both
publish valid immutable envelope bytes before one loses the state revision
compare-and-set; that losing envelope is an unreferenced orphan, not an admitted
atom or receipt. Deletion and garbage collection are deliberately absent until
a durable state journal can prove reachability.

## 5. Exact durability boundary

The file-backed facade makes schema, payload and atom-envelope bytes durable to
the local adapter's stated fsync boundary. It does **not** make
`CanonicalAtomV2State` or the receipt journal durable. A fresh runtime process
therefore starts with an empty reference state even though previously staged
bytes and the immutable schema binding remain present. It must not be described
as canonical-state recovery, exactly-once commit or durable learning.

The in-memory facade proves the same content-binding invariants without any
restart durability. Both facades retain the phase-1 reference grant label; a
schema digest does not add expiry, revocation, consent or canonical permit
semantics.

A later, separate
[`durable journal runtime`](HSWM_CANONICAL_ATOM_V2_DURABLE_JOURNAL_RUNTIME_2026-08-26.md)
now composes these content guarantees with an explicit revision-zero genesis
and immutable predecessor-bound state/receipt records. That continuation does
not retroactively change this facade's `STATE_JOURNAL_NON_DURABLE` contract.

## 6. Verification and next order

Tests cover duplicate keys and hostile runtime values, canonical digest
stability, exact raw-byte descriptors, defensive copies, restart retrieval,
schema-version conflict, corrupt and unsafe files, schema/grant/command digest
drift, missing payloads, forged envelopes, preflight no-write behavior and
concurrent one-winner state admission.

The durable-journal continuation completed the former first two steps for one
bounded observed local linear prefix, without an external anti-rollback
witness. The next implementation order is now:

1. represent authorization decisions, expiry/revocation evidence, sealed
   trajectories, outcomes and provenance evidence as typed canonical atoms;
2. add quarantine/rejection receipts, migration, fork/merge and compensating
   restore;
3. add loss-declared projections and only then outcome-bound learning
   proposals.

No research receipt or results-log entry is created because this is engineering
closure, not a material scientific result.
