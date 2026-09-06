# B2 external text-lesson comparator — frozen prospective v2

[Protocol v2](protocol.v2.json), SHA-256
`5ef3784f54c7fed7bb5bc682b982ef9220513782764d9afed19104c7a1722680`,
is a new occurrence and selection. It preserves the v1 algorithm, 8 train +
4 descriptive `valid_seen` groups, 20-action horizon, 240 + 8 per-phase POST
caps, outcome-gated reflection, evaluation freeze, stop conditions, and claim
ceiling. No B2 task, model request, or outcome has been inspected for v2 at
registration.

The [v1 result](../../../../results/HSWM_EXPEL_B2_TEXT_LESSON_V1_RESULTS_2026-09-06.md)
was `VOID_PROTOCOL_OR_EVIDENCE_BINDING_BREACH` before its start marker because
the caller supplied an incorrect asset root. It is preserved, not retried.
The earlier `python -m` command merely imported the module and returned; it
made no scientific start marker and is separately retained as a launcher
no-op. The actual v1 call invoked the already frozen `main()` and returned
the VOID terminal.

V2 corrects the caller's locator-relative asset root, adds the missing module
entrypoint, and validates every selected file's SHA/length/path through
`LocalSandboxSpec.validate()` before a start marker. Private prelease errors
now retain a bounded diagnostic and stage. A read-only diagnostic at the v1
source commit checked all 12 previously selected file bindings with the
correct root, without starting an environment, model, lease, or marker. V2
still selects new groups through its new protocol/occurrence hash.

The same qualified model snapshot, vLLM digest, ARM64 PDDL-only runtime, GPU,
and source archive are used. No artifact download or changed model service
configuration is required. The live module is invoked through `hswm-run`
with explicit paths, using `python -m hswm.experiments.expel_b2_live`.

This is a lesson-only external comparator, not direct ExpeL, canonical HSWM
learning/admission, independent custody, G0 passage, G1, or efficacy evidence.
The historical B0 still supplies no success rate; B0/B2 numerical comparison
remains unavailable without a separate B0 successor. All other interpretation
and privacy boundaries are recorded in the [v1 design](README.md) and are
fixed explicitly in the v2 JSON.
