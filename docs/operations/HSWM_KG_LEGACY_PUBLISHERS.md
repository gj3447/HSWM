# Historical KG publisher verification

The explicitly invoked Human Universal Body and Sheaf Python loaders share
`hswm.infrastructure.kg_legacy_projection`. This is a bounded compatibility
path for their existing projections. The active TypeScript/Effect runtime and
its canonical admission/learning interfaces are unchanged.

Both loaders validate their intended projection before connecting. Inside the
write transaction they require UID uniqueness on at least one declared label
per owned node and on `SchemaRegistry`, take the existing registry lock, then
resolve node and relationship identities. Missing constraints, duplicate
identities, other-bundle ownership and unregistered tokens fail before content
writes. They do not create constraints or register schema tokens automatically.

The label rule preserves the historical Sheaf binding: a `sym:ResearchSource:`
UID has declared `AbstractNode` / `SourceDocument` labels. No label is invented
from that UID. This compatibility check does not weaken the separate UID-kind
contract of newer bundle publishers or establish global UID uniqueness for
unrelated writers.

Readback checks every intended node property/label and every relationship's
direction, endpoints, type and intended properties. Unexpected bundle-owned
edges fail the transaction. Unrelated properties/labels survive. Repeating an
identical projection leaves content and timestamps unchanged. An explicitly
changed legacy input still updates its intended fields; these are historical
upsert APIs, not immutable receipt-based revision APIs.

The Sheaf alias projection retains its original pair-edge coalescing. The full
semantic relation names remain in the source JSON. The Human Universal Body
loader retains its original authority fields and source-hash requirements;
source drift is still rejected. Historical source hashes must not be refreshed
merely to make an old bundle publishable.

## Focused checks

Run from this repository with its Python environment:

```sh
PYTHONPATH=src uv run --no-project --with pytest python -B -m pytest -q \
  -p no:cacheprovider tests/test_kg_legacy_projection.py \
  tests/test_kg_publication_integrity.py tests/test_kg_bundle_semantics.py \
  tests/test_hswm_sheaf_ontology.py tests/test_hswm_fractal_cognitive_composition.py
```

The opt-in integration suite requires a separate **empty disposable Neo4j**.
Its private JSON config contains `uri`, `user`, `password`, `database`. There is
no production-config fallback. The suite creates test constraints, commits
fixtures and abruptly terminates test clients. It removes its nodes; destroy
the disposable instance afterward to remove test schema and credentials.

```sh
HSWM_LEGACY_DISPOSABLE_TEST=1 \
HSWM_LEGACY_DISPOSABLE_CONFIG=/private/disposable.json \
PYTHONPATH=src uv run --no-project --with pytest --with neo4j python -B -m pytest -q \
  -p no:cacheprovider tests/test_kg_legacy_projection_integration.py
```

The integration suite compares both complete legacy projections with the
publisher implementations pinned at `8043a83841bf3e89dc4e089adbab012475839fc8`.
That Git object is required. It checks exact content apart from timestamps,
unchanged retry timestamps, concurrent publication, equal-count content
corruption, missing constraints, duplicate edges, foreign ownership,
preserved foreign properties/anchors, and client death before/after commit.

Client death tests use `os._exit` without a graceful driver close. They verify
rollback after connection loss before commit and content-preserving retry
after an acknowledged commit with no result returned to the parent process.
They do not simulate an ambiguous server commit acknowledgement, server/storage
failure, arbitrary production compensation, or HSWM efficacy.

## Remaining publisher entrypoints (2026-10-11)

Human fractal projection, fractal scientific connections, causal-composition
research and Ragnarok/PIDNA now use the existing typed UID validation before
connecting, require UID-kind constraints and serialize on the schema registry
inside the transaction. Their anchor checks, exact content readback, immutable
projection rules and explicit predecessor upgrade semantics remain in place.
The graph-and-loop and adaptive-research writers already use this contract;
closure-plan, Effect-boundary and session-ledger delegate to graph-and-loop.

SWM-0R/W publisher source files are themselves hashed historical evidence.
Their original bytes and bundle hashes remain unchanged. Use the new protected
entrypoint for publication; the old scripts remain historical compatibility
sources and do not gain concurrency protection retroactively:

```sh
PYTHONPATH=src python -m scripts.publish_hswm_frozen_evidence swm0r \
  --ontology ontology/identity/human_universal_body/HSWM_SWM0R_EVIDENCE_BUNDLE.v1.json
```

The default validates tracked sources and the evidence replay without opening
credentials. Explicit `--apply --source-config /private/config.json` adds the
same constraint/registry protection around the historical callback and performs
its exact post-commit readback. The private JSON has `uri`, `user`, `password`,
`database`. Replace `swm0r` and its bundle with `swm0w` for that evidence profile.
Use the repository's prepared Python environment. SWM-0W cryptographic replay
also retains its preregistered Node 24.13.0 executable hash; a newer system Node
is not an equivalent replay environment and must not be used to refresh hashes.
On managed NFS, SWM-0R's historical sparse replay may encounter Git's dubious
ownership check. Scope `safe.directory` to that job's `TMPDIR` descendants using
process-local `GIT_CONFIG_*` variables; preserve any existing indexed entries.
Do not change global Git trust or the hash-bound replay source to bypass it.

`tests/test_kg_remaining_publishers.py` exercises these six entrypoints and the
retained source projections. Its opt-in integration companion publishes all six
full projections concurrently, verifies unchanged retries and read-only anchors,
and rejects missing constraints. No production schema is created automatically.

The additional fault suite suppresses a real Bolt COMMIT SUCCESS reply before
the client receives it, and kills the disposable server before/after commit.
Only `scripts/run_kg_disposable_tests.py` supplies server process control:

```sh
proxmox-scratch run kg-publisher-checks --timeout 1200 --max-bytes 1500000000 -- \
  env PYTHONPATH=src uv run --no-project --with neo4j --with pytest \
  python -B scripts/run_kg_disposable_tests.py --artifacts /approved/evidence/path
```

This harness downloads checksum-pinned Neo4j 5.26.0 and Temurin JRE 21 into
managed scratch, binds only loopback, changes the initial password over Bolt,
and removes its private runtime on completion. It never discovers live config.
Server crash recovery is distinct from storage-media loss, external backup
restoration and historical compensation; those are not covered by this suite.
