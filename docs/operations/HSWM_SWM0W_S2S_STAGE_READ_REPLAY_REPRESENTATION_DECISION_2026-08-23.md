# HSWM SWM-0W-S2S stage-read replay representation decision

Date: 2026-08-23

Status: `REPRESENTATION_AND_RESOURCE_CONTRACT_FROZEN /
BOUNDED_STRUCTURAL_REPLAY_CORE_IMPLEMENTED /
HOSTILE_MATRIX_AND_PRODUCTION_INTEGRATION_OPEN`

Authority: the strict TypeScript/Effect direction is `USER_PRIMARY`; this
bounded evidence-carrier decision is `SECONDARY_AI_PROPOSED` and remains
falsifiable by implementation, hostile validation, and resource-bound tests.

## Canonical role and delta

HSWM remains the one token-native LLM-function macro-neural network defined by
[`HSWM_CONSTITUTION_2026-08-20.md`](../canon/HSWM_CONSTITUTION_2026-08-20.md).
This decision changes only `Π`: it fixes how a future confirmatory stage can
retain and replay one predecessor artifact read without silently discarding raw
observations or duplicating a 64 MiB carrier. It does not change `H`, `W`, `A`,
or `F`, and it is not evidence of semantic-weight learning, a scientific result,
or progress through event 10.

## Decision

One `hswm-swm0w-s2s-stage-artifact-read-replay/v1` attachment is a deterministic
stored ZIP with exactly two members:

| Member | Meaning | Hard maximum |
|---|---|---:|
| `manifest.json` | one canonical ASCII JSON line, including aggregate self-hash and all compact bindings | 1,048,576 B |
| `observations.bin` | exact concatenation of the retained GitHub JSON response bodies in ledger order | 11,534,336 B |

The manifest gives every observation an ordinal, phase, kind, offset, byte
length, raw SHA-256, observation time, GitHub request ID, response ETag, and
receipt SHA-256. Offsets must start at zero, be contiguous and non-overlapping,
and end at the declared blob length. Each slice remains independently capped at
1,048,576 bytes and must reconstruct one trusted GitHub observation through the
existing validator for its kind and expected identity.

A successful lookup on poll `p in {1,2,3}` has exactly `5 + 2p` response bodies:

```text
lookup:   initial run + jobs + p * (artifacts + run) = 2 + 2p
readback: start run + exact artifact + final run     = 3
total:                                                5 + 2p
```

The downloaded predecessor carrier is deliberately not a third replay member.
Instead, the replay manifest content-addresses the exact upload attachment in a
source evidence stage:

- a registration read names the `REGISTER` envelope and
  `upload/registration_archive.zip`;
- a candidate read names the `CONFIRM` envelope and
  `upload/candidate_archive.zip`.

The reference binds the source stage, source manifest hash, source claim hash,
logical name, role, schema version, media type, byte length, and raw SHA-256.
Validation must receive the source stage from the recovered durable chain,
revalidate its envelope and claim, locate that one attachment, read the actual
bytes, and rehash them. It must then revalidate the GitHub download receipt and
the role-specific ZIP/member policy over those bytes. A digest string without
the referenced bytes is insufficient and must fail closed.

The aggregate manifest also binds the current-run evidence receipt, consumer
stage and operation, artifact role, run/head/job identity, successful poll
topology, download receipt, archive/member projection, artifact evidence,
permit evidence, and the exact operation-to-ledger entries. The two independent
candidate reads bind the same candidate fingerprint; equality is checked again
at the stage aggregate boundary.

## Exact byte accounting

The pinned stored-ZIP dialect uses two fixed ASCII member names, signed 16-byte
data descriptors, no extras or comments, and one 22-byte end record. Its exact
framing is:

```text
2 * (30-byte local header + 16-byte descriptor + 46-byte central header)
+ 2 * (len("manifest.json") + len("observations.bin"))
+ 22-byte end record
= 2 * 92 + 2 * (13 + 16) + 22
= 264 bytes
```

Therefore:

```text
manifest maximum       1,048,576 B
observation maximum   11,534,336 B
exact ZIP framing            264 B
carrier maximum       12,583,176 B
```

This is 4,194,040 bytes below the former coarse 16 MiB replay-profile cap and
54,525,688 bytes below the generic 64 MiB attachment cap. The success profile is
narrowed to the derived 12,583,176-byte carrier maximum; the generic envelope
limits remain unchanged.

With that narrower cap, maximum attachment totals are:

| Stage | Attachments | Attachment maximum total |
|---|---:|---:|
| `REGISTER` | 13 | 108,068,864 B |
| `CONFIRM` | 17 | 112,484,616 B |
| `ADJUDICATE` | 18 | 74,670,872 B |

All remain below the 268,435,456-byte envelope attachment-total cap. The
1,048,576-byte envelope manifest and 16,384-byte claim are separate bounded
content objects and are not miscounted as attachment bytes. These acceptance
limits do not claim an economical resident-heap bound; stage programs must keep
sequential acquisition and validation.

## Alternatives not adopted

- Embedding every downloaded archive would require at least 75 MiB for a
  candidate read before replay control data and ZIP framing. It contradicts the
  current 64 MiB per-attachment substrate and needlessly duplicates an already
  content-addressed predecessor object.
- Raising the generic attachment and stage limits would expand validation,
  recovery, and resident-memory exposure without adding evidence.
- Lowering the adopted 64 MiB candidate limit would be a protocol change without
  an empirical justification.
- A hash-only external reference would fit, but would not prove byte
  availability and is therefore rejected.

## Required falsification surface

The bounded structural core at code checkpoint `955beb0` now establishes the
two-member dialect and derived profile caps, reconstructs every retained raw
observation through its existing validator, revalidates the referenced source
envelope, claim, attachment bytes, download, archive, members, permit receipt,
and consumer identity, and requires candidate FIRST/REREAD to share one
current-run receipt and an exact cumulative permit-ledger prefix. Builders
accept only module-issued validated reads. The pure boundary returns `Either`;
the typed Effect wrappers defer it with `Effect.suspend`.

That implementation and its tests close the representation/resource decision,
not this entire falsification surface. In particular, recovered-chain getters
and attachment byte readers remain callable, unbranded inputs. The aggregate
hostile and every-later-phase matrix is incomplete, and no closed stage program
yet emits or commits this replay attachment. Continue to require tests for:

1. exact two-member ZIP dialect, fixed 264-byte framing, and all maximum and
   maximum-plus-one boundaries;
2. unknown-input and canonical-manifest rejection, aggregate self-hash, exact
   observation slicing, and independent reconstruction of every raw body;
3. exact poll topology, current-run/stage/operation/role binding, download and
   archive/member replay, and operation ledger mapping;
4. rejection of missing/corrupt/wrong-stage/wrong-claim predecessor content,
   including a correct hash with unavailable bytes;
5. hostile excess/accessor/proxy/cycle/alias/drifting-reader inputs and every
   nested receipt substitution or reorder;
6. candidate-first/reread fingerprint equality at the aggregate stage boundary.

Until the remaining hostile/phase checks, stage-program integration, and the
external durable-root gate close, this is a source-controlled engineering
contract plus a bounded structural implementation only. It does not claim that
any replay was produced by GitHub, emitted by a production stage, or durably
committed in production.
