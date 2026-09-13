# Native model and HTTP transport checkpoint — 2026-09-13

The native S2S route now fits actual parameters, builds the complete optimization receipt, reconstructs and archives the model, and verifies it from a file through 'hswm-s2s-model'. The one-shot F1 HTTP adapter also executes natively. Full migration remains incomplete; see [inventory v8](../../_research/native_migration_2026-09-13/inventory.v8.json) and the [active console caller audit](../../_research/native_migration_2026-09-13/active-console-callers.v1.json).

The conceptual change is executable source-bound model reconstruction. HSWM remains one token-native evolving hypergraph macro-network. Target identity, FCL-1..8, RED paths and success criteria are unchanged. Archive consistency, KG structure and engineering checks do not establish cognition, efficacy or deterministic fit replay.

The [verification record](../../_research/native_migration_2026-09-13/model-transport-verification.v1.json) binds 24 final source files to one isolated run: 1426 tests passed and 8 existing opt-in tests skipped. Historical Qwen replay was enabled. TypeScript, Effect/functional rules, build, DNRD, package dry-run and portable math passed without expanding the 38-file allowlist.

S2S reconstructs all three original zero-fit arms and a real T16 best-update-2 archive byte-for-byte. It recomputes train/dev losses from actual parameters and task data. An adversarial receipt with consistently resealed history and one-step altered best losses passes optimization parsing but is rejected at model reconstruction, just as the source does.

[NumPy's pinned pairwise reduction source](https://github.com/numpy/numpy/blob/48fecee5453aa1d31e6b79dcb3969dc1a6d1a891/numpy/_core/src/umath/loops_utils.h.src) defines the selected eight-lane, block-128 arithmetic. Independent byte-bound vectors exposed a false 8192-element chunk assumption, which was removed. All 18 reduction vectors now match exact hex. This is a qualified reference profile; it is not universal backend equivalence.

The [production qualification](../../_research/native_migration_2026-09-13/model-native-production-qualification.v1.json) ran the emitted CLI with only pinned Node and dirname on PATH. It verified four original archives, wrote zero and nonzero native fit archives as 0600 files, refused an existing output without changing bytes, and rejected crossed command flags. A separate one-time original Python parser accepted both native-emitted archives. Their native gradient/Adam trajectories are not claimed to be original-byte-identical.

From the repository checkout after the native build:

~~~sh
src/hswm/effect-runtime/bin/hswm-s2s-model verify --archive model.json
src/hswm/effect-runtime/bin/hswm-s2s-model fit --task task.json --config config.json --arm T16 --output new-model.json
~~~

Task and config inputs use the original canonical task/archive and hex-config schemas. Fit uses complete finite train/dev data. Output creation is exclusive. These commands issue a self-consistent model artifact, not a candidate PASS or a deterministic replay receipt.

F1 request bytes match the original one-shot OpenAI-compatible port. Its [pinned Node fetch surface](https://nodejs.org/download/release/v24.13.0/docs/api/globals.html#fetch) is scoped through typed Effect services. Loopback tests cover exact POST, no 503 retry, no redirect follow, deadline abort and streamed 16MiB refusal. Secrets are read each call and excluded from returned errors. Native latency is measured, not compared with historical wall time. No external model call was made.

The SQLite ledger draft remains unaccepted: a different schema, incomplete row/item audit and unreachable acceptance transition cannot replace the original authority. Six draft sources and failure findings are preserved privately with public digests; they are excluded from the native build. Original durable execution remains active. Next work is its exact ledger/spool/suite closure, S2S candidate protocol and pilot closure, F3 lifecycle, and individual compatibility/standards lanes.
