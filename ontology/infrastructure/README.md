# Repository infrastructure

Packaging, CI, documentation, schemas, and maintenance scripts make the
research repository reproducible. They support the HSWM program but are not
part of its learned cognitive topology.

This separation prevents repository organization from being mistaken for the
AI behavior rules that HSWM is intended to learn.

[`legacy_replay.py`](../../src/hswm/infrastructure/legacy_replay.py) is the
historical path boundary. It resolves only ontology-selected Python and asset
migration rows through one unique old-path index, then materializes their
complete source commit into a new detached standalone clone; it never copies an
old module or asset back into the live root.

The active flat compatibility sources are grouped under
[`_research/root_compat/`](../../_research/root_compat/), with the final Python
and asset manifests recorded in [`history/`](../history/). Packaging may expose
those legacy import names, but new implementation belongs under `src/hswm/` and
new artifacts use typed directories.
