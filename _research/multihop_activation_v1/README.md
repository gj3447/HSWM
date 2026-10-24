# Multi-hop native activation integration

This is an authored five-vertex, three-hop integration example using the existing native
runtime. It is not a natural-task benchmark or an operational policy deployment.
The [source/constitution/technique/result review](../../docs/operations/HSWM_MULTIHOP_ACTIVATION_2026-10-24.md)
contains the measured scope and presentation references.

`executeActivationLoop` joins existing activation, external evaluation, owner admission and
exact readback in one use. `executeActivationTraversal` reads a native step and follows only
the selected next reference, carrying required relations and the previous actual output.
Both are in `src/hswm/effect-runtime/src/`; the example does not add another graph engine.
Real consumers provide their own admitted graph, versioned features, outcome evaluator and
existing owner callback. The source-navigation workspace is not automatically converted to
executable instructions or a globally trained policy.

Build with the existing runtime npm scripts, then read the installed script help:

```sh
node _research/multihop_activation_v1/run.mjs --help
node _research/multihop_activation_v1/run.mjs prepare NEW_PRIVATE_ROOT MODEL_ID
proxmox-scratch run hswm-multihop-live --timeout 1500 --max-bytes 268435456 -- \
  node _research/multihop_activation_v1/run.mjs run NEW_PRIVATE_ROOT
node _research/multihop_activation_v1/check.mjs NEW_PRIVATE_ROOT
```

The transport is the existing loopback endpoint documented in the owner study, capped at
42 calls and 45 minutes. Prepare requires a new directory and explicit model ID. It records
the current task's selected local scope, recipient, expiry and revocation. Each call checks
that exact scope and selected implementation pins. No service setup, remote registration,
credential scan, retries or auto-renewal occurs. Historical expired studies stay unchanged.

The native owner handles W updates during TRAIN; AUDIT never submits. Feedback is the
per-hop external authored reference, not model confidence or a causal decomposition of
terminal reward. Original request/response, execution trace, outcome, successor and traversal
receipt remain local. A failed run retains its partial evidence; do not rerun into it.

The checker calls no provider and performs no policy writes. It independently recomputes
the task outcome and 2x2 ridge statistics, checks actual wire and native content, restores
the recorded owner state, verifies fresh-process reuse, and rejects three deliberate record
mutations. Its source pins cover the listed main runtime modules, not every transitive
dependency or the model checkpoint. A passing checker is scoped integration evidence.

2026-10-24: 42 actual calls, 142,967 provider tokens, 24 native updates, entry W revision 8;
final authored evaluation 6/6 and restart 3/3. Raw evidence is ignored under
`.hswm-local/multihop-activation-2026-10-24/`. Preserve the 18/24 training outcomes and the
earlier test timeout. Snapshot/journal recovery is still global; prompt locality does not
make its storage I/O local.

Verification: 9 traversal and 3 existing activation tests passed; all 16 source-navigation
tests passed after the concurrent current-constitution v2 bindings were finalized. The first
combined run retained one source-hash mismatch during that edit. The checker independently
passed with all 398 native-store files byte-identical before and after its readback.
Strict TypeScript/Effect checks, the native build, and portable Markdown compilation also
passed. These checks establish the bounded implementation contract, not general efficacy.
