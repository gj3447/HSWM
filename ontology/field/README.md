# Semantic field

The field is the coupled state `(H, W, A)`: mutable n-ary connectivity, durable
semantic coupling, and run-local activation. Its topology is the concrete core;
sheaf theory is an optional lens for observing compatibility across unlike
local states.

- [`sheaf/`](sheaf/) contains the source-backed sheaf research bundle.
- [`prom_search_hswm/`](../../prom_search_hswm/) contains field algebra,
  routing, retrieval, and plasticity experiments.
- [`hswm.substrate.hypergraph`](../../src/hswm/substrate/hypergraph.py) is the
  canonical exact-byte implementation of the mutable n-ary topology.
- [`hswm.substrate.field_snapshot`](../../src/hswm/substrate/field_snapshot.py)
  binds immutable field cuts and the installed static-kernel identity.
