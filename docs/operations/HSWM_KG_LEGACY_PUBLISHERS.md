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
