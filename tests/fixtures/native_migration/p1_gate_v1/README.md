# Native P1 original engineering contracts

These are synthetic implementation-comparison fixtures, not research outcomes.
The three frozen 390-question universes exercise zero, positive (+1), and negative
(-1) fresh-gate deltas. Original Python wrote the complete expected diagnostic
and summary. Native replay reconstructs all five exact input files from base64,
checks their SHA-256 digests, and compares every output byte and stdout byte.
SQLite and NPZ bytes are synthetic local fixtures, without private data.

The original diagnostic source is `src/hswm/diagnostics/p1_gate.py`, SHA-256
`e4b401bdaa92eedb3cdc0792f8a2a5913c70413ec97cb6373f86f0452b6d9ac0`.
`bootstrap.original.v1.json` contains 72 original MT19937/bootstrap cases,
including powers-of-two lengths and signed/large integer seeds.

This qualification covers frozen float64 cached embeddings. Missing-cache model
loading/embedding generation is still a separate unfinished native dependency;
`--embedding-cache-folder` preserves the original argument surface without
implicitly downloading or regenerating a model. It does not establish parity
for all possible Unicode datasets, floating-point backends, or malformed inputs.
