# Native F3 PostgreSQL cache and budget

2026-09-17 · T0 engineering · source base `f3772f9c1e5b9982ff33b8882cc99c6042e698e4`.

The TypeScript/Effect runtime now has a durable F3 cache/budget port and a
PostgreSQL adapter. This is a partial migration checkpoint. Existing Python
launchers and scientific execution routes have not been replaced.

## Contract

- `native-f3-cache-runtime.ts` composes the existing source-bound request identity,
  response decoder, a typed persistence service and a typed provider service.
- `native-f3-pg-persistence.ts` reserves each run/request identity atomically.
  All clients share the run budget; hit/miss observations remain per client.
  A completed cache hit is checked before budget exhaustion.
- A reservation survives process loss. Unknown delivery leaves it `RESERVED`;
  another caller receives `UNRESOLVED_DISPATCH` and cannot dispatch it again.
  There is no automatic expiration or uncertain-request replay.
- A confirmed `NOT_SENT` transport failure or a received invalid response may
  close the reservation as `FAILED_KNOWN`. A later explicit acquisition may
  reserve again, consuming another miss. The prior reservation is archived and
  cannot complete the replacement reservation.
- Completion checks the reservation, request hash and response metadata hash.
  Exact repeated completion is idempotent; conflicting completion fails.
  Corrupt cached metadata does not increment counters or dispatch a request.
- Configuration drift, invalid counters and oversized documents fail closed.
  Documents are bounded to 1 MiB. Unknown database state is reported as unknown,
  never as an invented zero counter snapshot.
- A transaction uses one checked-out database client. Interrupted or failed
  transactions roll back where possible and discard that client; an ambiguous
  commit cannot cause an automatic provider replay.

The adapter uses parameterized values and validates its schema identifier.
This follows the official node-postgres contracts for
[transactions](https://node-postgres.com/features/transactions) and
[queries](https://node-postgres.com/features/queries).

## Installation and composition

Pinned dependencies: `pg@8.16.3` and `@types/pg@8.15.6` (MIT), with registry
integrities in `package-lock.json`. Runtime verification used the repository's
Node `24.13.0` requirement. The SQL migration is included in the package files.

1. Apply `src/hswm/effect-runtime/migrations/0001_native_f3_pg.sql` in a transaction
   using the dedicated database owner, before constructing the adapter.
2. Supply a node-postgres pool, validated schema name and immutable run tuple
   `{ runId, configDigest, maxCalls }` to `initializeNativeF3PgRun`.
3. Compose `makeNativeF3PgPersistence` with an explicit provider implementation
   using `makeNativeF3PersistentChat`. End the pool at application shutdown.
4. Preserve unresolved reservations for delivery reconciliation. Do not delete
   them to retry an operation whose external execution is unknown.

On data-01, a dedicated `hswm_runtime` database and non-superuser role were
provisioned. The migration created four tables in `hswm_f3`: `runs`,
`cache_entries`, `client_counters`, and `attempt_history`. Readback found zero
production runs. Private connection configuration is outside the repository at
`~/.config/hswm/f3-postgres.json` (mode 0600); it is not a public artifact.
This provisioned storage is ready for a future caller integration, not evidence
that the existing F3 launcher already uses it.

## Verification

The two new test files under `src/hswm/effect-runtime/test/` passed **14/14**
checks, with no skips, using a real PostgreSQL database and isolated random
schemas. They cover concurrent same-request acquisition, shared budget,
client counters, adapter recreation, uncertain delivery, known failure,
correlation, config drift, corrupt cache, overflow, document bounds and failed
transaction-client disposal. They do not establish crash recovery under an
actual process kill or all database/network failure schedules.

```bash
cd src/hswm/effect-runtime
HSWM_F3_PG_TEST_CONFIG="$HOME/.config/hswm/f3-postgres.json" \
  node node_modules/vitest/vitest.mjs run \
  test/native-f3-cache-runtime.test.ts \
  test/native-f3-pg-persistence.integration.test.ts --maxWorkers=1 --cache=false
```

Type checking, Effect boundary and functional checks passed. Both build
configurations passed; `npm pack --dry-run` included the compiled adapters and
SQL migration. The HSWM development workflow selected `relation:runtime-focused`
and passed 55 shared regression checks in episode
`9814fc73-e1c5-4ba7-8ba3-2ff8c1dd7ac3`. Separate F3 tests were necessary because
that profile does not select this feature's tests. Usefulness feedback is
explicitly `agent(codex)` judgment, not user feedback or efficacy evidence.

## Remaining boundary

The new cache is scoped to one durable run. Python `CACHE_DIR` can share cache
files across runs; full source parity and F3-STATE-CACHE closure are not claimed.
No filesystem cache export, existing-launcher replacement, uncertain-delivery
reconciler, provider retry policy or complete F3 lifecycle is implemented here.
F3's seeded/sampling/response-format contract is not supplied by the Astra web
relay; this change does not route scientific F3 calls through that relay.

This checkpoint changes no HSWM target identity, scientific result, CR/FCL
status or efficacy claim. Its source-bound projection is
`ontology/development/HSWM_NATIVE_F3_POSTGRES_CACHE_2026-09-17.v1.json`.
