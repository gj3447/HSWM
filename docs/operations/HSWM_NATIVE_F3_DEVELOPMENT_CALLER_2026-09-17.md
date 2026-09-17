# Native F3 development caller

2026-09-17 · T0 engineering · source base `5985dede4e57f3850207c753df374191433e96c4`.

The F3v2 development launcher can now explicitly select the TypeScript/Effect
PostgreSQL cache and shared call budget. The Python adapter maps its existing
chat interface to a one-request native process. Request identity, reservations,
cache admission, counters and HTTP dispatch are owned by the native runtime.
This extends the earlier [PostgreSQL checkpoint](HSWM_NATIVE_F3_POSTGRES_CACHE_2026-09-17.md)
without changing that historical snapshot.

## Selection and configuration

Build `src/hswm/effect-runtime` with the repository-pinned Node 24.13.0. The npm
package includes `hswm-f3-development` and the existing SQL migration. Apply the
migration with the database owner before using the caller; the caller performs
no schema DDL. The private JSON configuration has exactly one `connectionString`
property, is a regular mode-0600 file, and stays outside the repository.

`_research/f_series/f3v2_dev_smoke.py` requires all four flags to select this path:
`--live --dev --native-f3-run-id <stable-run-id> --native-f3-config <private-file>`.
Native selection rejects sealed manifests, including when `--dev` is also set.
Without these flags the historical launcher path remains available. The pinned
`f2_delta_w_credit.py` and `f3v2_arms.py` source bytes are unchanged.

The run configuration digest binds launcher bytes, manifest hash, actual world
hashes, endpoint/model identities, seeds, arms, token limit and budget. Reusing
the same run ID with a changed digest or maximum budget is refused. Stable
`f3v2-donor` and `f3v2-receiver` client IDs share one durable run budget; there is
no second Python budget debit. A new run ID creates a separate development
budget, not an account-wide usage limit. The cache remains run-scoped.

The source checkout adapter launches the compiled native process using
`HSWM_NODE` or `node` from PATH. It is not a Python-wheel-only deployment path.
The process consumes one canonical JSON request and returns a bounded result
with run/client/request identity, terminal and observed counters. Its timeout
is an integer number of seconds from 1 through 86400. The Python default 240.0
is serialized as 240; fractional or boolean timeouts are refused before launch.
This boundary is exercised with the actual Python serializer, not only stubs.

## Dispatch and recovery

The fetch provider uses the source-shaped request body, including seed,
temperature 0, top-p 1, JSON response format and thinking disabled. It sends
one POST, refuses redirects, bounds the response to 1 MiB and aborts at the
deadline. It introduces no provider retry. Errors after dispatch begins are
conservatively classified as unknown delivery, including HTTP errors and
invalid response JSON. The durable reservation then remains unresolved.

A later call for that same unresolved request returns `UNRESOLVED_DISPATCH`
without another POST. Completed cache entries survive process exits and are
checked before budget exhaustion. A child-process timeout, refusal or ambiguous
database result is not reported as an observed zero budget. Success and aborted
development receipts retain the public run identity; unknown usage is null.
Private configuration paths and child stderr are not included in receipts.

## Verification

- 21 native tests passed without skips, using a real PostgreSQL database in
  isolated random schemas and a local fake HTTP provider. The integration test
  traversed Python -> compiled native process -> PostgreSQL -> HTTP, then
  repeated the call after process exit to verify a cache hit. It also covered
  exhausted budget, configuration drift and no replay after socket loss.
- 50 Python tests passed for the bridge, F3v2 arms and sealed input behavior.
  They include private-path redaction and aborted-run unknown counters.
- Type checking, Effect boundary/functional checks, both build configurations
  and npm package inspection passed.
- `hswm-dev hswm run` selected `relation:runtime-focused` in episode
  `c40ca1e2-0408-4030-9f17-0a27b821a9c6` and passed 55 shared regression checks.
  Separate F3 tests were required because that profile does not select them.
  Feedback is an explicit `agent(codex)` usefulness judgment.

The initial mocked Python tests missed decimal timeout serialization. Review
identified that canonical stdin rejects 240.0; the final integration crosses
that exact real process boundary and verifies the correction.

No live model call or scientific experiment was run for this checkpoint. It
does not establish full F3 migration, cross-run Python file-cache parity,
uncertain-delivery reconciliation, real-model improvement, or 24-hour service
reliability. The Astra web relay does not supply F3's sampling/seed contract;
this bridge does not route scientific F3 calls through it. HSWM identity and
CR/FCL status are unchanged.

Source-bound projection:
`ontology/development/HSWM_NATIVE_F3_DEVELOPMENT_CALLER_2026-09-17.v1.json`.
