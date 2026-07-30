# OOPTDD Chain "Incident" — 2026-07-28 (postmortem + ERRATA)

> **Status (2026-07-28, errata by kimi-code): MISDIAGNOSIS — retracted as a chain
> incident. The canonical chain (맥미니 GIT/HSWM) was never corrupted. What
> stands: the append() race fix (flock) and the repairs skiplist verb — both
> shipped below and worth keeping. What falls: the 4-record corruption claim,
> "original bodies unrecoverable", and "35-char hash points at the writer".**
>
> Kept in full for the record (Eilu-va-Eilu: history is documented, never
> rewritten — including our own false alarms).

## Errata (kimi-code, 2026-07-28, second review)

Direct `record_hash` recomputation over the canonical chain
(`/Users/lagyeongjun/CD/SYMPOSIUM/GIT/HSWM/receipts/receipt_log.jsonl`) shows
**all four listed records hash-match their stored hashes** (spot-verified:
seq 14 `dcefcc94…`, seq 22 `fe89ec33…`, seq 25 `5215296e…` full 64-hex,
seq 26 `e5a9a473…`). The canonical file was untouched between 01:41 UTC
(seq 65's `append()` — which itself re-verifies the whole chain — succeeded)
and the errata review.

What actually happened: the "corrupted" bodies existed **only in a local
transcription copy** of the canonical log, made by kimi-code's session via a
remote-read channel. That channel provably lost/altered bytes in exactly
those four lines (visible hex-string errors: `…e633…`→`…c633…`, a 64-hex hash
→ 48 chars, `…2cc3cc83…`→`…2cc83…`; plus a 1-byte invisible whitespace/unicode
loss in `weight_field.py`, detected later by sha mismatch 5800→5801 bytes).
The "bulk import bypassing `append()`" that the original diagnosis detected
was simply that wholesale file-write of the flawed transcription — a
**detection true-positive on a local artifact, misattributed to the
canonical chain**. "Original bodies unrecoverable" was wrong: the originals
were always in the canonical repo, one re-read away.

Lessons added by the errata:

1. **Before diagnosing chain corruption, recompute against the canonical
   source** — a hash mismatch in a *copy* indicts the copy first.
2. Transcription-style file transfer (read→re-emit) is not byte-safe for
   hash-bound artifacts; verify sha after every transfer, or don't hand it
   to `verify()` as if it were evidence about the original.
3. The race the original doc worried about was nevertheless **real and
   observed the same day** (two agent sessions appended concurrently at
   05:26/05:30/05:31 UTC): the flock fix below was the right call on the
   merits, and the misdiagnosis does not change that.
4. The repairs skiplist shipped below remains a useful verb for *future*
   genuine incidents; the 2026-07-28 entries themselves are withdrawn
   (see `receipt_log.jsonl.repairs.json` note) because the listed records
   verify clean without any skiplist.

---

## Original text (misdiagnosis, preserved verbatim)

> Status: contained. Chain verifies (`ok: True`) with 4 documented repairs.
> Repair mechanism + concurrency fix shipped in `ooptdd/receipt_log.py` (v2.8)
> with regression tests in `tests/test_repair_and_locking.py`.

## What happened

Between 13:53 and ~14:30 KST on 2026-07-28, the chain grew from 5 records
(seq 0–4) to 66 (seq 0–65). The 61 new records were `kind=harvest` records
(one per test module) carrying **timestamps of 2026-07-24T01:55 UTC** — i.e. a
bulk import of historical harvest results, written by a parallel agent session,
**bypassing `receipt_log.append()`**.

Four of the imported records fail verification:

| seq | receipt_id | defect |
|---|---|---|
| 14 | test_entity_binding | body does not match stored hash |
| 22 | test_h3_b3_end_to_end | body does not match stored hash |
| 25 | test_h3_b3_manifest | stored hash is **35 hex chars** (truncated) |
| 26 | test_h3_b3_preflight | body does not match stored hash |

Detection: `run_receipt` refused to chain a new receipt —
`refusing to append to corrupt chain` (fail-closed worked as designed).

## Diagnosis (evidence)

- **seq/prev_hash linkage is intact end-to-end** (no gaps, no reorders, no
  duplicates) — the importer linked the chain correctly but wrote bodies that
  do not hash to their stored `hash` values.
- **Not a canonicalization drift**: `canonical()` has been
  `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False)` since
  v2; no serialization variant (ascii/compact/sorted/unsorted/field-exclusion)
  reproduces any of the 4 stored hashes over current bodies.
- **Not recoverable from an archive**: no copy of the pre-import chain exists
  anywhere in the workspace (searched `find . -name 'receipt_log*.jsonl*'`).
- Brute-force over plausible field edits (tests counts, single-field
  exclusions) does not reproduce the stored hashes. The original bodies are
  cryptographically unrecoverable.
- Conclusion: importer tooling defect (body/hash write race or field mangling;
  seq=25's truncated 35-char hash points at the writer), **not adversarial
  tampering** — but the chain cannot prove intent either way, hence repairs
  are attested by name.

## Root cause class

1. A writer **bypassed `append()`** (the only path that re-verifies + hashes
   + links atomically).
2. `append()` itself was **not concurrency-atomic**: verify→write as separate
   steps could interleave under two racing harness processes.

## Fix (v2.8)

- `receipt_log.append()` now takes an **exclusive flock** and re-verifies
  *under* the lock (POSIX fcntl; no-op fallback elsewhere).
- New **repairs skiplist**: `<log>.repairs.json` — `{seq, receipt_id,
  stored_hash, reason, attested_by, attested_at}` entries make a documented,
  attested exception verify as intact. Wrong/stale entries change nothing;
  unlisted tampering is still detected (test-pinned).
  Same culture as lakatotree R6 fsck skiplists and transparency-log
  witnessed exceptions: **history is documented, never rewritten.**
- The 4 records are listed in `receipts/receipt_log.jsonl.repairs.json`,
  attested by `kimi-k2.5` (diagnosing auditor).

## Verification after repair

- `verify('receipts/receipt_log.jsonl')` → `(True, [])` (69 records, seq 0–68)
- Concurrent append stress: 8 threads × 5 appends → valid chain, contiguous seq
- Fire drill: unlisted verdict-tamper and deletion still DETECTED
- 25/25 ooptdd tests pass

## Lessons / follow-ups

- The 2026-07-28 incident is the fire drill happening for real: detection
  worked; the missing piece was a *repair verb*. Now shipped.
- All future bulk imports must go through `append()` (it is now
  concurrency-safe) or be re-chained, never patched in place.
- Consider: verify() should also reject malformed `hash` lengths (seq=25's
  35-char hash) at append time — cheap schema gate, not yet implemented.
