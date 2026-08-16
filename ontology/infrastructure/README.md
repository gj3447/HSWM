# Repository infrastructure

Packaging, CI, documentation, schemas, and maintenance scripts make the
research repository reproducible. They support the HSWM program but are not
part of its learned cognitive topology.

This separation prevents repository organization from being mistaken for the
AI behavior rules that HSWM is intended to learn.

[`legacy_replay.py`](../../src/hswm/infrastructure/legacy_replay.py) is the
historical path boundary. It resolves only ontology-selected migration rows and
materializes their complete source commit into a new detached standalone clone;
it never copies an old module back into the live root.
