#!/usr/bin/env python3
"""Build the bounded HSWM Effect-runtime functional-boundary KG projection (v1).

The projection records what the 2026-09-05 TypeScript/Effect completeness audit
established (six migration gates, none closed; the decisive loop not in
TypeScript), the six functional-programming shortfalls it named, the refactor
packages that closed or narrowed them, the Effect services those packages
introduced, the five lint rules that now enforce the boundary, and the six
explicit exemption lanes that still carry imperative code with a stated reason.
Every count comes from the checked-in lint report and allowlist, which the
bundle hash-binds.  It is a bounded engineering-status projection.  It is not
HSWM cognition, learning, canonical state, a Permit, a migration-gate pass, a
G0/G1 pass, or a scientific result.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = Path("ontology/identity/hswm_core/HSWM_EFFECT_RUNTIME_FP_BOUNDARY_ONTOLOGY.v1.json")
BOUNDARY_DOC_PATH = Path("docs/operations/HSWM_EFFECT_RUNTIME_FUNCTIONAL_BOUNDARY_2026-09-06.md")
GATE_DOC_PATH = Path("docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md")
LINT_PATH = Path("src/hswm/effect-runtime/scripts/lint-effect-boundary.mjs")
ALLOWLIST_PATH = Path("src/hswm/effect-runtime/scripts/effect-boundary-allowlist.json")
LINT_REPORT_PATH = Path("src/hswm/effect-runtime/scripts/effect-boundary-lint-report.json")
SOURCE_BINDING_PATHS: tuple[Path, ...] = (
    BOUNDARY_DOC_PATH,
    GATE_DOC_PATH,
    LINT_PATH,
    ALLOWLIST_PATH,
    LINT_REPORT_PATH,
)

SCHEMA_VERSION = "hswm-effect-runtime-fp-boundary-ontology/v1"
RELEASE = "2026-09-06"
TAG = "2026-09-06"
AUDIT_COMMIT = "4dcba752a661de23066b3b33381bfdfc34879a57"
BASELINE_COMMIT = "d9e5c1a11d20181f7dcf9a8e0d23f687e8ecabbd"
STATUS = (
    "EFFECT_BOUNDARY_LINT_ENFORCED_SEVEN_LANES_EXEMPT_TS_MIGRATION_GATES_NOT_CLOSED_"
    "DECISIVE_LOOP_NOT_IN_TYPESCRIPT_G0_NOT_PASSED_G1_LOCKED"
)
NONCLAIM = (
    "EFFECT_RUNTIME_BOUNDARY_KG_PROJECTION_ONLY_NOT_HSWM_COGNITION_LEARNING_"
    "EFFICACY_MIGRATION_GATE_PASS_G0_G1_PASS_OR_SCIENTIFIC_RESULT"
)
CLAIM_CEILING = "SELF_ATTESTED_AI_CODE_AUDIT_AND_LOCAL_TEST_RUN_NOT_INDEPENDENTLY_QUALIFIED"
LINT_RULES_ORDER = ("R1", "R2", "R3", "R4", "R5")

# The lint baseline measured on the BASELINE_COMMIT tree with the corrected
# statement-throw regex (the first run under-counted `if (...) throw`).
BASELINE_COUNTS = {"R1": 3, "R2": 13, "R3": 602, "R4": 44, "R5": 149}
BASELINE_FILES_WITH_HITS = 56
BASELINE_FILES = 128
BASELINE_PER_FILE: dict[str, dict[str, int]] = {
    "canonical-atom-v2-routing-diagnostic-process.ts": {"R2": 6, "R3": 137, "R5": 26},
    "canonical-atom-v2-state-journal-file.ts": {"R3": 48, "R4": 1, "R5": 12},
    "canonical-atom-v2-content-file.ts": {"R2": 2, "R3": 40, "R5": 11},
    "canonical-atom-v2-graph-loop-job-process.ts": {"R2": 1, "R3": 19, "R5": 3},
    "canonical-atom-v2-graph-loop-engineering.ts": {"R3": 14, "R5": 4},
    "hypergraph-projection-process.ts": {"R2": 2, "R3": 10, "R5": 1},
    "canonical-atom-v2-hypergraph-projection.ts": {"R3": 10},
    "canonical-atom-v2-content.ts": {"R3": 7},
    "swm0-role-aware-core.ts": {"R3": 2, "R4": 2},
    "canonical-atom-v2-durable-runtime.ts": {"R4": 3},
    "canonical-atom-v2-current-state-permit.ts": {"R4": 1},
    "canonical-atom-v2-durable-rdf-projection.ts": {"R4": 1},
    "canonical-atom-v2-graph-loop-research-job.ts": {"R5": 1},
    "canonical-atom-v2-local-permit-commit.ts": {"R3": 1},
    "canonical-atom-v2-verified-admission-gateway.ts": {"R4": 1},
    "g0-occurrence-phase-kernel.ts": {"R4": 1},
    "g0-occurrence-temporal-domain.ts": {"R4": 1},
    "hypergraph-projection-rehearsal.ts": {"R3": 1},
    "open-connectivity-rehearsal.ts": {"R3": 1},
    "hypergraph-projection-receipt.ts": {},
    # Converted in the foundation package before the baseline was measured.
    "canonical-atom-v2-local-permit-commit-process.ts": {},
    "effect-posix-services.ts": {"R3": 4, "R5": 6},
    "effect-process-main.ts": {},
    # Split out of effect-posix-services.ts after the baseline; the adapter lane hits moved with the code.
    "effect-posix-filesystem.ts": {},
    "effect-bounded-subprocess.ts": {},
}

BUNDLE_UID = f"sym:AbstractNode:hswm-effect-fp-boundary-ontology-{TAG}"
PROGRAM_UID = f"sym:ResearchProgram:hswm-effect-fp-boundary-{TAG}"
AUDIT_RUN_UID = f"sym:AbstractNode:hswm-effect-fp-completeness-audit-run-{TAG}"
VERIFICATION_RUN_UID = f"sym:AbstractNode:hswm-effect-fp-refactor-verification-run-{TAG}"
LINT_MODULE_UID = f"sym:Concept:hswm-effect-fp-boundary-lint-{TAG}"
SR4_DEVIATION_UID = f"sym:Concept:hswm-effect-fp-sr-4-deviation-record-{TAG}"

# Anchors: MATCH-only nodes that already exist in the live KG.  Names were
# read back from the live graph on 2026-09-06 and are asserted at publish time.
HSWM_UID = "sym:Concept:hswm"
GRAPH_LOOP_PROGRAM_UID = "sym:ResearchProgram:hswm-graph-and-loop-engineering-2026-09-02-v6"
CELL_EVENT_RUNTIME_UID = "sym:AbstractNode:hswm-graph-loop-current-cell-event-runtime-2026-09-02-v6"
LOCAL_PERMIT_OCCURRENCE_UID = "sym:AbstractNode:hswm-graph-loop-current-local-permit-commit-2026-09-02-v6"
RESEARCH_JOB_RUNNER_UID = "sym:AbstractNode:hswm-graph-loop-current-research-job-runner-2026-09-02-v6"
GRAPH_LOOP_CONTROLLER_UID = "sym:AbstractNode:hswm-graph-loop-current-graph-loop-controller-2026-09-02-v6"
TS_QUALIFICATION_UID = "sym:AbstractNode:hswm-qualification-run-typescript-local-boundaries-2026-09-02-v6"
UNIVERSAL_REFINEMENT_GAP_UID = "sym:Hypothesis:hswm-graph-loop-gap-universal-source-refinement-2026-09-02-v6"
CLOSURE_BUNDLE_UID = "sym:AbstractNode:hswm-closure-plan-ontology-2026-09-05-v2"
CLOSURE_PROGRAM_UID = "sym:ResearchProgram:hswm-closure-plan-2026-09-05-v2"
CLOSURE_STEP_S2_UID = "sym:Concept:hswm-closure-step-s-2-2026-09-05-v2"
CLOSURE_D4_UID = "sym:Concept:hswm-closure-user-decision-d-4-2026-09-05-v2"
CLOSURE_BURDEN_CAP_UID = "sym:Concept:hswm-closure-burden-cap-2026-09-05-v2"
CLOSURE_SR4_UID = "sym:Concept:hswm-closure-stop-rule-sr-4-2026-09-05-v2"
CLOSURE_SR5_UID = "sym:Concept:hswm-closure-stop-rule-sr-5-2026-09-05-v2"
CLOSURE_FINDING_SUBSTRATE_UID = (
    "sym:Concept:hswm-closure-finding-core-loop-starved-by-substrate-engineering-2026-09-05-v2"
)
CLOSURE_FINDING_NO_BRIDGE_UID = (
    "sym:Concept:hswm-closure-finding-no-bridge-between-llm-instrument-and-atom-v2-permit-2026-09-05-v2"
)

ANCHORS: list[dict[str, Any]] = [
    {"uid": HSWM_UID, "name": "HSWM", "required_labels": ["Concept"]},
    {
        "uid": GRAPH_LOOP_PROGRAM_UID,
        "name": "HSWM graph and loop engineering reinforcement program [2026-09-02-v6]",
        "required_labels": ["Concept", "ResearchProgram", "ResearchArtifact"],
    },
    {
        "uid": CELL_EVENT_RUNTIME_UID,
        "name": "Cell event/effect runtime [2026-09-02-v6]",
        "required_labels": ["AbstractNode", "ResearchArtifact"],
    },
    {
        "uid": LOCAL_PERMIT_OCCURRENCE_UID,
        "name": "Local Permit issuance and POSIX commit occurrence [2026-09-02-v6]",
        "required_labels": ["AbstractNode", "ResearchArtifact"],
    },
    {
        "uid": RESEARCH_JOB_RUNNER_UID,
        "name": "LE-0 action and verifier subprocess runner [2026-09-02-v6]",
        "required_labels": ["AbstractNode", "ResearchArtifact"],
    },
    {
        "uid": GRAPH_LOOP_CONTROLLER_UID,
        "name": "GE-2 and LE-0 graph-loop engineering controller [2026-09-02-v6]",
        "required_labels": ["AbstractNode", "ResearchArtifact"],
    },
    {
        "uid": TS_QUALIFICATION_UID,
        "name": "TypeScript local gateway and Permit occurrence qualification [2026-09-02-v6]",
        "required_labels": ["AbstractNode", "ResearchArtifact"],
    },
    {
        "uid": UNIVERSAL_REFINEMENT_GAP_UID,
        "name": "Universal TypeScript/Effect-to-Lean source refinement gap [2026-09-02-v6]",
        "required_labels": ["Concept", "Hypothesis"],
    },
    {
        "uid": CLOSURE_BUNDLE_UID,
        "name": "HSWM closure plan ontology [2026-09-05-v2]",
        "required_labels": ["AbstractNode", "ResearchArtifact"],
    },
    {
        "uid": CLOSURE_PROGRAM_UID,
        "name": "HSWM closure plan [2026-09-05-v2]",
        "required_labels": ["Concept", "ResearchProgram", "ResearchArtifact"],
    },
    {
        "uid": CLOSURE_STEP_S2_UID,
        "name": "S-2 — Bridge g1_micro admission to the real local Permit commit [2026-09-05-v2]",
        "required_labels": ["Concept"],
    },
    {
        "uid": CLOSURE_D4_UID,
        "name": "D-4 — Define the finite v1 done-state and the numeric burden cap [2026-09-05-v2]",
        "required_labels": ["Concept", "Guardrail"],
    },
    {
        "uid": CLOSURE_BURDEN_CAP_UID,
        "name": "HSWM closure burden cap [2026-09-05-v2]",
        "required_labels": ["Concept", "Guardrail"],
    },
    {
        "uid": CLOSURE_SR4_UID,
        "name": "SR-4 — Freeze ontology versions and ICE episodes until the G1 verdict [2026-09-05-v2]",
        "required_labels": ["Concept", "Guardrail"],
    },
    {
        "uid": CLOSURE_SR5_UID,
        "name": "SR-5 — No exact-byte pins of live files and no dead handoff tests [2026-09-05-v2]",
        "required_labels": ["Concept", "Guardrail"],
    },
    {
        "uid": CLOSURE_FINDING_SUBSTRATE_UID,
        "name": (
            "The decisive recurrence received 5.8% of effort while ~67% went to durability, graph "
            "standards, docs and non-LLM precursors — infrastructure that has only ever processed "
            "synthetic fixtures and pre-declares it proves nothing about HSWM [2026-09-05-v2]"
        ),
        "required_labels": ["Concept", "Hypothesis"],
    },
    {
        "uid": CLOSURE_FINDING_NO_BRIDGE_UID,
        "name": (
            "The two halves of the closing loop (Python LLM instrument on DGX; TypeScript Atom v2 "
            "Permit on dev-01) were built in parallel with no join, so even a perfect G0 run cannot "
            "yield the README milestone [2026-09-05-v2]"
        ),
        "required_labels": ["Concept", "Hypothesis"],
    },
]

# --- Migration gates (docs/research/HSWM_TYPESCRIPT_EFFECT_RUNTIME_2026-08-21.md §Migration gates)
GATES: tuple[dict[str, str], ...] = (
    {
        "id": "MG-1",
        "name": "Contract gate",
        "claim": "TypeScript Schemas for state, events, errors, and replay are frozen with migration/version semantics",
        "finding": (
            "Schema ingress is pervasive (Schema.* 1,972 uses, Data.TaggedError 129 classes, decodeUnknownEither 118 "
            "vs decodeUnknownSync 0) but migration/version semantics are unimplemented: "
            "canonical-atom-v2-state-journal.ts:535 'migration is not implemented'; "
            "canonical-atom-v2-domain.ts:410-413 MIGRATION_UNSUPPORTED."
        ),
        "disposition": "UNDERDETERMINED",
        "status_word": "PARTIAL",
    },
    {
        "id": "MG-2",
        "name": "Oracle parity gate",
        "claim": "The frozen Python numeric reference is called through a typed, scoped adapter with exact fixture/receipt parity",
        "finding": (
            "A Python numeric oracle adapter and T16 parity at 5e-14 exist, but every result is TEST_ONLY_NON_AUTHORIZING "
            "with typescriptTrainingClaimed=false; fitting and gradients remain Python."
        ),
        "disposition": "UNDERDETERMINED",
        "status_word": "PARTIAL",
    },
    {
        "id": "MG-3",
        "name": "Durability gate",
        "claim": "An atomic persistent CommitStore with crash recovery, outcome-unknown reconciliation, and replay exists",
        "finding": (
            "O_EXCL+fsync+no-replace-link publication, SIGKILL crash tests, and one-winner CAS exist in the local Permit "
            "commit and state-journal files; anti-rollback is a nonclaim and the HSWM-core CommitStore is still an in-memory Ref."
        ),
        "disposition": "UNDERDETERMINED",
        "status_word": "MOSTLY_IMPLEMENTED",
    },
    {
        "id": "MG-4",
        "name": "Function-cell gate",
        "claim": "Scoped LLM/tool cell execution with bounded concurrency, timeout, cancellation, and typed provider errors exists",
        "finding": (
            "Zero LLM calls in 126 TypeScript source files; F is an identifier registry only "
            "(contracts.ts:40-42, domain.ts:289-293)."
        ),
        "disposition": "RED",
        "status_word": "ABSENT",
    },
    {
        "id": "MG-5",
        "name": "Learning gate",
        "claim": "Independently verified outcomes and causal credit bind to candidate dW/dH with retention, canary, removal, and rollback",
        "finding": (
            "canonical-atom-v2-learning-refinement.ts is an obstruction reporter that only emits the constant "
            "BLOCKED_NOT_REFINED_TO_LEAN_LEARN; no credit-to-revision binding runs in TypeScript."
        ),
        "disposition": "RED",
        "status_word": "STRUCTURE_ONLY",
    },
    {
        "id": "MG-6",
        "name": "Authority gate",
        "claim": "TypeScript is the source of truth for a migrated path after parity and replay, with Python as independent oracle",
        "finding": (
            "Temporal runs simulation only (LIVE_EXTERNAL_OPERATOR -> LIVE_ADMISSION_BLOCKED); completion authority "
            "stays in Python; PS-3 (TypeScript refines Lean) is unproved."
        ),
        "disposition": "RED",
        "status_word": "PARTIAL",
    },
)

LOOP_CLAIM = {
    "id": "LOOP-TS",
    "name": "TypeScript executes HSWM's decisive loop",
    "claim": (
        "The sealed trajectory -> outcome -> credit -> canonical revision -> held-out behavior loop runs in TypeScript"
    ),
    "finding": (
        "Every judgment step of the decisive loop is Python; TypeScript is invoked once per credited admission as a "
        "stdin/stdout subprocess to verify and sign a transition Python already decided, and the held-out probe reads "
        "Python SQLite state, not the TypeScript journal.  The functional-boundary refactor changes none of this."
    ),
    "disposition": "RED",
}

# --- Functional-programming shortfalls named by the audit and their closure status after the refactor.
FP_GAPS: tuple[dict[str, str], ...] = (
    {
        "id": "FP-GAP-1",
        "name": "I/O adapters were imperative async/Promise Node code lifted only at the edge",
        "before": "File, subprocess and HTTP adapters were async/await Node code wrapped by Effect.tryPromise (60 sites); no @effect/platform.",
        "after": (
            "One PosixFileSystem service (identity, bounded regular read, exclusive write, no-replace link, directory fsync) and one "
            "BoundedSubprocess service are the only Node adapters; every refactored store, journal and CLI takes the service value. "
            "@effect/platform stays out because it cannot express O_NOFOLLOW, directory fsync, no-replace hard links or detached "
            "process groups and would break the exact-pin dependency policy."
        ),
        "rules": ["R5", "R3"],
    },
    {
        "id": "FP-GAP-2",
        "name": "Process CLIs and library code used throw for refusal",
        "before": "throw new ProcessRefusal and throw <error>(...) patterns: 602 statement throws in the baseline tree.",
        "after": (
            "Executables are Effect programs run through one runProcessMain/runArgvProcessMain boundary that maps typed failures "
            "to the same stderr text and exit codes; refusals are ProcessRefusal values; library failures are Effect.fail/Either.left."
        ),
        "rules": ["R3", "R2"],
    },
    {
        "id": "FP-GAP-3",
        "name": "A library function started its own Effect runtime",
        "before": "canonical-atom-v2-content-file.ts:275,316 called get(...).pipe(Effect.runPromise) inside bindSchema/resolveSchema.",
        "after": "The content store yields the inner effect; Effect.run* is confined to effect-process-main.ts and executable guards.",
        "rules": ["R2"],
    },
    {
        "id": "FP-GAP-4",
        "name": "Module-level mutable state",
        "before": "21 module-level Map/Set/WeakMap/WeakSet across 15 files, three module-level let, and a WeakSet brand inside the G0 phase kernel.",
        "after": (
            "Brands are private class fields (#issued), runtime seams are private fields read through static accessors, the "
            "verified-admission root semaphores live in a ProtectedRootLocks service, and remaining constant sets are typed ReadonlySet."
        ),
        "rules": ["R1", "R4"],
    },
    {
        "id": "FP-GAP-5",
        "name": "The local Permit commit store was a plain factory, not a service",
        "before": "makeLocalPermitCommitStore returned a frozen object; nothing could provide or replace it as a Layer.",
        "after": "LocalPermitCommitStoreService (Context.Tag) with makeLocalPermitCommitStoreLayer requiring PosixFileSystem; factories retained for callers.",
        "rules": ["R5"],
    },
    {
        "id": "FP-GAP-6",
        "name": "No lint enforced immutability or the Effect boundary",
        "before": "No eslint/biome; the functional-core/Effect-shell split relied on convention and the compiler.",
        "after": "scripts/lint-effect-boundary.mjs enforces R1-R5 with a shrinking-only lane allowlist, wired into npm run check and CI.",
        "rules": ["R1", "R2", "R3", "R4", "R5"],
    },
)

LINT_RULES: tuple[dict[str, str], ...] = (
    {"id": "R1", "name": "No module-level let", "pattern": "^let\\s at column 0"},
    {
        "id": "R2",
        "name": "No Effect.run* outside the process boundary",
        "pattern": "Effect.run(Promise|Sync|PromiseExit|SyncExit|Fork|Callback) outside effect-process-main.ts or below the import.meta.url guard of *-process.ts / *-cli.ts",
    },
    {"id": "R3", "name": "No throw statements", "pattern": "statement-position throw outside allowlisted lanes"},
    {
        "id": "R4",
        "name": "No module-level mutable Map/Set",
        "pattern": "module-level const = new (Weak)?(Map|Set) unless typed ReadonlyMap/ReadonlySet",
    },
    {"id": "R5", "name": "No async functions", "pattern": "async keyword outside the POSIX adapter lane"},
)

# --- Effect services introduced or promoted by the refactor.
SERVICES: tuple[dict[str, Any], ...] = (
    {
        "id": "PosixFileSystem",
        "file": "effect-posix-filesystem.ts",
        "tag": "hswm/PosixFileSystem",
        "description": "identity, listDirectory, realpath, makeDirectory, syncDirectory, readRegularBounded, writeExclusive, linkNoReplace, chmod, unlinkIfPresent; NodePosixFileSystem value and NodePosixFileSystemLive layer; failures are PosixIoError values.",
        "provided_by": "P-0",
    },
    {
        "id": "BoundedSubprocess",
        "file": "effect-bounded-subprocess.ts",
        "tag": "hswm/BoundedSubprocess",
        "description": "observe(argv, cwd, environment, timeoutMs, maximumOutputBytes, stdin) with SIGTERM then SIGKILL, output truncation and timeout, implemented once with Effect.async.",
        "provided_by": "P-0",
    },
    {
        "id": "ProcessMainBoundary",
        "file": "effect-process-main.ts",
        "tag": "runProcessMain / runArgvProcessMain",
        "description": "The single Effect.runPromiseExit boundary for executables: reads bounded stdin or argv, runs one Effect program under NodePosixServicesLive, exit 0 on success, 2 with '<prefix>: <line>' on a typed failure, 3 on a defect.",
        "provided_by": "P-0",
    },
    {
        "id": "LocalPermitCommitStoreService",
        "file": "canonical-atom-v2-local-permit-commit.ts",
        "tag": "LocalPermitCommitStoreService",
        "description": "Context.Tag for the local Permit commit store with makeLocalPermitCommitStoreLayer(rootPath, verifier, clock) requiring PosixFileSystem; the plain factories remain as compatibility entry points.",
        "provided_by": "P-0",
    },
    {
        "id": "ProtectedRootLocks",
        "file": "canonical-atom-v2-verified-admission-gateway.ts",
        "tag": "ProtectedRootLocks",
        "description": "Service holding the per-root Effect.Semaphore map that was a module-level Map, with ProtectedRootLocksLive; the gateway factories keep their signatures.",
        "provided_by": "P-3",
    },
)

# --- Refactor packages: one commit each, in the order they were merged into main.
PACKAGES: tuple[dict[str, Any], ...] = (
    {
        "id": "P-0",
        "name": "Effect-native POSIX services and local Permit commit",
        "commit": "d9e5c1a11d20181f7dcf9a8e0d23f687e8ecabbd",
        "files": [
            "effect-posix-services.ts",
            "effect-process-main.ts",
            "canonical-atom-v2-local-permit-commit.ts",
            "canonical-atom-v2-local-permit-commit-process.ts",
        ],
        "closes": ["FP-GAP-5"],
        "narrows": ["FP-GAP-1", "FP-GAP-2"],
        "refines": [LOCAL_PERMIT_OCCURRENCE_UID],
        "preserves": [CLOSURE_STEP_S2_UID],
        "tests": [
            "test/canonical-atom-v2-local-permit-commit.test.ts",
            "test/canonical-atom-v2-local-permit-commit-process.test.ts",
            "test/canonical-atom-v2-local-permit-commit-process-crash.test.ts",
            "tests/test_hswm_atom_v2_permit_bridge.py",
        ],
    },
    {
        "id": "P-1",
        "name": "Content file store on PosixFileSystem",
        "commit": "ab211af9c61ce64a6da3037a09dc6ac9bd706f1d",
        "files": ["canonical-atom-v2-content-file.ts"],
        "closes": ["FP-GAP-3"],
        "narrows": ["FP-GAP-1", "FP-GAP-2"],
        "refines": [CELL_EVENT_RUNTIME_UID],
        "preserves": [],
        "tests": [
            "test/canonical-atom-v2-content-file.test.ts",
            "test/canonical-atom-v2-content-runtime.test.ts",
            "test/canonical-atom-v2-durable-runtime.test.ts",
        ],
    },
    {
        "id": "P-1b",
        "name": "POSIX adapter split so the DNRD-5 closure excludes child_process",
        "commit": "edee9d3becfbd9d1c4be65ad2ad80eba789ba270",
        "files": ["effect-posix-services.ts", "effect-posix-filesystem.ts", "effect-bounded-subprocess.ts"],
        "closes": [],
        "narrows": ["FP-GAP-1"],
        "refines": [],
        "preserves": [],
        "tests": ["test/dnrd5-source-closure.test.ts", "test/canonical-atom-v2-content-file.test.ts", "test/canonical-atom-v2-local-permit-commit.test.ts"],
    },
    {
        "id": "P-2",
        "name": "Bounded subprocess runner and Effect-program CLIs",
        "commit": "dad5d2139918e2dff3f16b76a13ae4fe7352e845",
        "files": [
            "canonical-atom-v2-graph-loop-research-job.ts",
            "canonical-atom-v2-graph-loop-job-process.ts",
            "hypergraph-projection-process.ts",
            "effect-process-main.ts",
        ],
        "closes": [],
        "narrows": ["FP-GAP-1", "FP-GAP-2"],
        "refines": [RESEARCH_JOB_RUNNER_UID],
        "preserves": [],
        "tests": [
            "test/canonical-atom-v2-graph-loop-research-job.test.ts",
            "test/canonical-atom-v2-graph-loop-enforcement-boundary.test.ts",
            "tests/effect-runtime/*.test.ts",
        ],
    },
    {
        "id": "P-3",
        "name": "Module-level state into private fields and a lock service",
        "commit": "68513d95c0c4753430fb467d8aad5f3d3a2bc59f",
        "files": [
            "g0-occurrence-phase-kernel.ts",
            "g0-occurrence-temporal-domain.ts",
            "canonical-atom-v2-durable-runtime.ts",
            "canonical-atom-v2-durable-rdf-projection.ts",
            "swm0-role-aware-core.ts",
            "canonical-atom-v2-verified-admission-gateway.ts",
        ],
        "closes": ["FP-GAP-4"],
        "narrows": [],
        "refines": [CELL_EVENT_RUNTIME_UID],
        "preserves": [],
        "tests": [
            "test/g0-occurrence-phase-kernel.test.ts",
            "test/canonical-atom-v2-durable-runtime.test.ts",
            "test/canonical-atom-v2-durable-rdf-projection.test.ts",
            "test/dnrd5-source-closure.test.ts",
            "test/swm0-role-aware-core.test.ts",
            "test/canonical-atom-v2-verified-admission-gateway.test.ts",
            "test/canonical-atom-v2-verified-admission-gateway-v2.test.ts",
        ],
    },
    {
        "id": "P-4",
        "name": "State journal file on PosixFileSystem with the same fault and checkpoint seams",
        "commit": "e00bd0f3c97c8cc0fddadc91ff90d8e963f59b79",
        "files": ["canonical-atom-v2-state-journal-file.ts"],
        "closes": [],
        "narrows": ["FP-GAP-1", "FP-GAP-2", "FP-GAP-4"],
        "refines": [CELL_EVENT_RUNTIME_UID],
        "preserves": [],
        "tests": [
            "test/canonical-atom-v2-state-journal-file.test.ts",
            "test/canonical-atom-v2-state-journal-file-process.test.ts",
            "test/canonical-atom-v2-state-journal-store.test.ts",
            "test/canonical-atom-v2-dnrd5-v2-two-cas-process.test.ts",
        ],
    },
    {
        "id": "P-5",
        "name": "Graph-loop control journal on PosixFileSystem and Either-returning pure cores",
        "commit": "8ee390b12dae6ce01d171ab9fc86e8e4244225a3",
        "files": [
            "canonical-atom-v2-graph-loop-engineering.ts",
            "canonical-atom-v2-content.ts",
            "canonical-atom-v2-hypergraph-projection.ts",
            "canonical-atom-v2-current-state-permit.ts",
        ],
        "closes": [],
        "narrows": ["FP-GAP-1", "FP-GAP-2", "FP-GAP-4"],
        "refines": [GRAPH_LOOP_CONTROLLER_UID],
        "preserves": [],
        "tests": [
            "test/canonical-atom-v2-graph-loop-engineering.test.ts",
            "test/canonical-atom-v2-content.test.ts",
            "test/canonical-atom-v2-current-state-permit.test.ts",
            "tests/effect-runtime/canonical-atom-v2-hypergraph-projection.test.ts",
        ],
    },
    {
        "id": "P-5b",
        "name": "Projection receipt verifies graph digests through the Either core",
        "commit": "1d44bc69f7e932d23a72ed5c3332b835353b6ea2",
        "files": ["hypergraph-projection-receipt.ts"],
        "closes": [],
        "narrows": ["FP-GAP-2"],
        "refines": [],
        "preserves": [],
        "tests": ["tests/effect-runtime/hypergraph-projection-receipt.test.ts", "tests/effect-runtime/canonical-atom-v2-hypergraph-projection.test.ts"],
    },
    {
        "id": "P-6",
        "name": "DNRD routing-diagnostic process as one Effect program",
        "commit": "547b02fa58b3b0befbd110b48b7dfa1c695503d7",
        "files": ["canonical-atom-v2-routing-diagnostic-process.ts"],
        "closes": [],
        "narrows": ["FP-GAP-1", "FP-GAP-2"],
        "refines": [CELL_EVENT_RUNTIME_UID],
        "preserves": [],
        "tests": [
            "test/canonical-atom-v2-routing-diagnostic-process.test.ts",
            "test/dnrd5-source-closure.test.ts",
            "tests/test_hswm_dnrd_execute.py",
        ],
    },
    {
        "id": "P-7",
        "name": "Rehearsal fixtures without throw",
        "commit": "fdc4c9d9a92e6e10dcfa3681ebbaedfd72534ac4",
        "files": ["hypergraph-projection-rehearsal.ts", "open-connectivity-rehearsal.ts"],
        "closes": [],
        "narrows": ["FP-GAP-2"],
        "refines": [],
        "preserves": [],
        "tests": ["tests/effect-runtime/open-connectivity-rehearsal.test.ts", "tests/effect-runtime/hypergraph-projection-receipt.test.ts"],
    },
    {
        "id": "P-8",
        "name": "Effect boundary lint enforced in check and CI",
        "commit": "1feb30ce64b281b63ec86734599a02bcc70e124a",
        "files": [],
        "closes": ["FP-GAP-6"],
        "narrows": [],
        "refines": [],
        "preserves": [CLOSURE_SR5_UID],
        "tests": ["npm run lint:boundary", "npm run check"],
    },
)

SAFE_UID = re.compile(r"sym:[A-Za-z][A-Za-z0-9_]*:[A-Za-z0-9][A-Za-z0-9._-]*\Z")
MAX_TEXT = 700


def _clip(value: str, limit: int = MAX_TEXT) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _file_sha(path: Path) -> str:
    return sha256((ROOT / path).read_bytes()).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _common(
    *,
    name: str,
    description: str,
    authority: str,
    scope: str,
    kind: str,
    plane: str,
    state: str,
    owner: str,
    roles: list[str],
    boundary: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": _clip(description),
        "authority_class": authority,
        "canonical_scope": scope,
        "ontology_kind": kind,
        "ontology_plane": plane,
        "epistemic_state": state,
        "responsibility_owner": owner,
        "claim_boundary": boundary,
        "projection_nonclaim": NONCLAIM,
        "ontology_domain": "AI",
        "record_lifecycle": "ACTIVE",
        "review_required": True,
        "semantic_roles": roles,
    }


def _node(uid: str, labels: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {"uid": uid, "labels": labels, "properties": properties}


def _relation(
    from_uid: str,
    relation_type: str,
    to_uid: str,
    scope: str,
    status: str,
    authority: str = "SECONDARY_AI",
) -> dict[str, str]:
    return {
        "from_uid": from_uid,
        "type": relation_type,
        "to_uid": to_uid,
        "authority_class": authority,
        "scope": scope,
        "status": status,
    }


def source_uid(path: Path) -> str:
    return f"sym:AbstractNode:hswm-effect-fp-source-{_slug(path.stem)}-{TAG}"


def gate_claim_uid(gate_id: str) -> str:
    return f"sym:Concept:hswm-effect-fp-gate-claim-{gate_id.lower()}-{TAG}"


def gate_decision_uid(gate_id: str) -> str:
    return f"sym:Concept:hswm-effect-fp-gate-decision-{gate_id.lower()}-{TAG}"


def gap_uid(gap_id: str) -> str:
    return f"sym:Hypothesis:hswm-effect-fp-gap-{gap_id.lower()}-{TAG}"


def package_uid(package_id: str) -> str:
    return f"sym:Concept:hswm-effect-fp-package-{package_id.lower()}-{TAG}"


def service_uid(service_id: str) -> str:
    return f"sym:Concept:hswm-effect-fp-service-{_slug(service_id)}-{TAG}"


def rule_uid(rule_id: str) -> str:
    return f"sym:Concept:hswm-effect-fp-lint-rule-{rule_id.lower()}-{TAG}"


def lane_uid(lane_id: str) -> str:
    return f"sym:Concept:hswm-effect-fp-lane-{_slug(lane_id)}-{TAG}"


def file_uid(file_name: str) -> str:
    return f"sym:AbstractNode:hswm-effect-fp-file-{_slug(file_name.removesuffix('.ts'))}-{TAG}"


def load_allowlist() -> dict[str, Any]:
    return json.loads((ROOT / ALLOWLIST_PATH).read_text(encoding="utf-8"))


def load_lint_report() -> dict[str, Any]:
    report = json.loads((ROOT / LINT_REPORT_PATH).read_text(encoding="utf-8"))
    if report.get("schema_version") != "hswm-effect-boundary-lint/v1":
        raise ValueError("lint report schema drifted")
    return report


def _counts_for(per_file: dict[str, dict[str, int]], files: list[str]) -> dict[str, int]:
    totals = {rule: 0 for rule in LINT_RULES_ORDER}
    for name in files:
        for rule in LINT_RULES_ORDER:
            totals[rule] += int(per_file.get(name, {}).get(rule, 0))
    return totals


def _hits(counts: dict[str, int]) -> int:
    return sum(counts.values())


def build_data() -> dict[str, Any]:
    allowlist = load_allowlist()
    report = load_lint_report()
    per_file: dict[str, dict[str, int]] = report["per_file"]
    bindings = [{"path": path.as_posix(), "sha256": _file_sha(path)} for path in SOURCE_BINDING_PATHS]
    binding_sha = {row["path"]: row["sha256"] for row in bindings}
    lint_green = report["violations"] == 0 and report["stale_allowlist_entries"] == 0
    lanes = allowlist["lanes"]
    lane_files: dict[str, list[str]] = {lane: [] for lane in lanes}
    for file_name, entry in allowlist["files"].items():
        lane_files[entry["lane"]].append(file_name)
    refactored_files = sorted({name for package in PACKAGES for name in package["files"]})
    for name in refactored_files:
        if name not in BASELINE_PER_FILE:
            raise ValueError(f"refactored file without baseline: {name}")
    for package in PACKAGES:
        if not re.fullmatch(r"[0-9a-f]{40}", package["commit"]):
            raise ValueError(f"package {package['id']} has no bound commit")

    nodes: list[dict[str, Any]] = []
    relations: list[dict[str, str]] = []
    boundary = (
        "This projection records engineering status of the TypeScript/Effect runtime at one commit; it is not "
        "canonical HSWM state, cognition, learning, permission, a migration-gate pass, a G0/G1 pass, or a scientific result."
    )

    nodes.append(
        _node(
            BUNDLE_UID,
            ["AbstractNode", "ResearchArtifact"],
            {
                **_common(
                    name=f"HSWM Effect runtime functional boundary ontology [{TAG}]",
                    description=(
                        "Bounded KG projection of the TypeScript/Effect completeness audit (six migration gates, none closed; "
                        "the decisive loop not in TypeScript), six functional-programming shortfalls, the refactor packages that "
                        "closed or narrowed them, the Effect services they introduced, five lint rules, and six exemption lanes."
                    ),
                    authority="SYSTEM_DERIVED",
                    scope="BOUNDED_ENGINEERING_STATUS_PROJECTION",
                    kind="ARTIFACT",
                    plane="INQUIRY",
                    state="LINT_ENFORCED_LOCAL_TESTS_GREEN_SELF_ATTESTED" if lint_green else "LINT_RED_SELF_ATTESTED",
                    owner="effect_fp_boundary_projection_custodian",
                    roles=["RESEARCH_BUNDLE", "ENGINEERING_STATUS", "CLAIM_EVIDENCE_GAP_STATUS"],
                    boundary=boundary,
                ),
                "schema_version": SCHEMA_VERSION,
                "release": RELEASE,
                "audit_commit": AUDIT_COMMIT,
                "baseline_commit": BASELINE_COMMIT,
                "artifact_binding_paths": [row["path"] for row in bindings],
                "artifact_binding_sha256": [row["sha256"] for row in bindings],
                "lint_files": int(report["files"]),
                "lint_clean_files": int(report["clean_files"]),
                "lint_violations_outside_lanes": int(report["violations"]),
                "lint_allowlisted_files": int(report["allowlisted_files"]),
                "baseline_files_with_hits": BASELINE_FILES_WITH_HITS,
                "event_version_rule": (
                    "A new version of this bundle is produced only when a lane is emptied, a gate decision changes, or the "
                    "lint rule set changes; per-commit counts are re-read from the bound lint report."
                ),
                "sr_4_deviation": (
                    "This is a new ontology JSON version created before the G1 verdict on the user's explicit 2026-09-06 "
                    "instruction to connect the Effect-boundary work to the KG; the deviation is recorded, not hidden."
                ),
            },
        )
    )
    relations.append(_relation(BUNDLE_UID, "DEPENDS_ON", CLOSURE_BUNDLE_UID, "PREDECESSOR_GOVERNANCE_BUNDLE", "ACTIVE"))
    relations.append(_relation(BUNDLE_UID, "DEPENDS_ON", GRAPH_LOOP_PROGRAM_UID, "PREDECESSOR_ENGINEERING_BUNDLE", "ACTIVE"))
    relations.append(_relation(BUNDLE_UID, "HAS_CONCEPT", PROGRAM_UID, "BUNDLE_ROOT", "ACTIVE"))

    nodes.append(
        _node(
            PROGRAM_UID,
            ["Concept", "ResearchProgram", "ResearchArtifact"],
            {
                **_common(
                    name=f"HSWM Effect runtime functional boundary program [{TAG}]",
                    description=(
                        "Make the TypeScript/Effect runtime maximally functional: one POSIX/subprocess adapter, one process "
                        "boundary, typed failures everywhere else, no module-level mutable state, and a lint that keeps it so. "
                        "The programme does not move the decisive HSWM loop into TypeScript."
                    ),
                    authority="SECONDARY_AI",
                    scope="ENGINEERING_PROGRAMME_NOT_SCIENTIFIC_RESULT",
                    kind="PLAN",
                    plane="INQUIRY",
                    state="EXECUTED_AT_BOUND_COMMITS",
                    owner="effect_fp_boundary_programme_custodian",
                    roles=["RESEARCH_PROGRAM", "ENGINEERING_STATUS"],
                    boundary="The programme orders refactor work; it does not pass any gate or promote any claim.",
                ),
                "package_ids": [package["id"] for package in PACKAGES],
                "gap_ids": [gap["id"] for gap in FP_GAPS],
                "gate_ids": [gate["id"] for gate in GATES],
                "lane_ids": list(lanes),
                "lint_rule_ids": [rule["id"] for rule in LINT_RULES],
                "user_request": "2026-09-06 USER_PRIMARY instruction: make the named shortfalls maximally TypeScript/Effect functional, organise the result graph-engineering style, and connect it to the KG",
            },
        )
    )
    relations.append(_relation(PROGRAM_UID, "EXTENDS", GRAPH_LOOP_PROGRAM_UID, "ENGINEERING_LINEAGE", "ACTIVE"))
    relations.append(_relation(PROGRAM_UID, "TARGETS", HSWM_UID, "RUNTIME_SUBSTRATE_ONLY", "ACTIVE"))
    relations.append(
        _relation(PROGRAM_UID, "DEPENDS_ON", CLOSURE_BURDEN_CAP_UID, "COMMITS_COUNTED_IN_BURDEN_WINDOW", "ACTIVE")
    )
    relations.append(_relation(PROGRAM_UID, "PRESERVES", CLOSURE_D4_UID, "FINITE_DONE_STATE_UNCHANGED", "ACTIVE"))
    relations.append(_relation(PROGRAM_UID, "PRESERVES", CLOSURE_PROGRAM_UID, "CLOSURE_STEP_ORDER_UNCHANGED", "ACTIVE"))

    for path in SOURCE_BINDING_PATHS:
        nodes.append(
            _node(
                source_uid(path),
                ["AbstractNode", "SourceDocument", "ResearchArtifact"],
                {
                    **_common(
                        name=f"{path.name} [{TAG}]",
                        description=f"Hash-bound source {path.as_posix()} for the Effect functional-boundary projection.",
                        authority="SYSTEM_DERIVED",
                        scope="BOUND_SOURCE_RECORD",
                        kind="ARTIFACT",
                        plane="EVIDENCE",
                        state="HASH_BOUND",
                        owner="effect_fp_boundary_projection_custodian",
                        roles=["EVIDENCE_ARTIFACT"],
                        boundary="A bound source proves what text existed at the bound digest, nothing more.",
                    ),
                    "standard_graph_role": "EVIDENCE_ARTIFACT",
                    "source_path": path.as_posix(),
                    "source_sha256": binding_sha[path.as_posix()],
                },
            )
        )
        relations.append(_relation(source_uid(path), "PART_OF", BUNDLE_UID, "BOUND_SOURCE", "ACTIVE"))

    nodes.append(
        _node(
            AUDIT_RUN_UID,
            ["AbstractNode", "ResearchArtifact"],
            {
                **_common(
                    name=f"TypeScript/Effect completeness audit run [{TAG}]",
                    description=(
                        "2026-09-05 code-level audit at the audited commit: 15 AI agents (inventory, six gate checks, "
                        "functional-convention audit) with skeptic re-verification of each finding; measured Schema/TaggedError/"
                        "decodeUnknownEither/Object.freeze/readonly/var/let/throw/async/Map counts across 126 source files."
                    ),
                    authority="SECONDARY_AI_SELF_ATTESTED_AUDIT",
                    scope="RUNTIME_COMPLETENESS_AUDIT_AT_ONE_COMMIT",
                    kind="QUALIFICATION_RUN",
                    plane="EVIDENCE",
                    state="SELF_ATTESTED_AI_AUDIT_NOT_INDEPENDENTLY_QUALIFIED",
                    owner="effect_fp_audit_run_custodian",
                    roles=["QUALIFICATION_RUN", "CODE_AUDIT"],
                    boundary="The audit qualifies engineering claims about one commit; it is not evidence about HSWM cognition, learning, or efficacy.",
                ),
                "standard_graph_role": "QUALIFICATION_RUN",
                "attestation_level": "SELF_ATTESTED_AI",
                "qualification_status": "COMPLETED_SKEPTIC_REVERIFIED",
                "executed_on": "2026-09-05",
                "audited_commit": AUDIT_COMMIT,
                "agent_count": 15,
            },
        )
    )
    relations.append(_relation(AUDIT_RUN_UID, "AUDITS", PROGRAM_UID, "PROGRAMME_ORIGIN", "ACTIVE"))
    relations.append(_relation(AUDIT_RUN_UID, "HAS_SOURCE", source_uid(GATE_DOC_PATH), "GATE_DEFINITIONS", "ACTIVE"))
    relations.append(_relation(AUDIT_RUN_UID, "EXTENDS", TS_QUALIFICATION_UID, "QUALIFICATION_LINEAGE", "ACTIVE"))

    verification_status = (
        "LINT_GREEN_OUTSIDE_LANES_TSC_VITEST_PYTEST_GREEN" if lint_green else "LINT_RED_OUTSIDE_LANES"
    )
    nodes.append(
        _node(
            VERIFICATION_RUN_UID,
            ["AbstractNode", "ResearchArtifact"],
            {
                **_common(
                    name=f"Effect boundary refactor verification run [{TAG}]",
                    description=(
                        "Local verification of every refactor package: tsc --noEmit for both tsconfigs, the named vitest files, "
                        "the Python bridge/DNRD tests, and the Effect boundary lint against the bound allowlist."
                    ),
                    authority="SECONDARY_AI_SELF_ATTESTED_LOCAL_RUN",
                    scope="LOCAL_VERIFICATION_AT_BOUND_COMMITS",
                    kind="QUALIFICATION_RUN",
                    plane="EVIDENCE",
                    state="SELF_ATTESTED_LOCAL_RUN_NOT_INDEPENDENTLY_QUALIFIED",
                    owner="effect_fp_verification_run_custodian",
                    roles=["QUALIFICATION_RUN", "LOCAL_TEST_RUN"],
                    boundary="A green local run shows the bound tree type-checks, passes the named tests, and satisfies the lint; it proves nothing about HSWM.",
                ),
                "standard_graph_role": "QUALIFICATION_RUN",
                "attestation_level": "SELF_ATTESTED_LOCAL_TSC_VITEST_PYTEST",
                "qualification_status": verification_status,
                "executed_on": RELEASE,
                "lint_counts_baseline": [f"{rule}={BASELINE_COUNTS[rule]}" for rule in LINT_RULES_ORDER],
                "lint_counts_current": [f"{rule}={int(report['counts'][rule])}" for rule in LINT_RULES_ORDER],
                "lint_violations_outside_lanes": int(report["violations"]),
                "lint_stale_allowlist_entries": int(report["stale_allowlist_entries"]),
            },
        )
    )
    relations.append(_relation(VERIFICATION_RUN_UID, "HAS_SOURCE", source_uid(LINT_REPORT_PATH), "LINT_REPORT", "ACTIVE"))
    relations.append(_relation(VERIFICATION_RUN_UID, "HAS_SOURCE", source_uid(ALLOWLIST_PATH), "LANE_ALLOWLIST", "ACTIVE"))
    relations.append(_relation(VERIFICATION_RUN_UID, "EXTENDS", TS_QUALIFICATION_UID, "QUALIFICATION_LINEAGE", "ACTIVE"))
    for package in PACKAGES:
        relations.append(_relation(VERIFICATION_RUN_UID, "VERIFIES", package_uid(package["id"]), "PACKAGE_TESTS", "ACTIVE"))

    # Migration gates and the loop-authority claim: Claim -> Decision.
    for gate in GATES + (dict(LOOP_CLAIM, status_word="ABSENT", name=LOOP_CLAIM["name"]),):
        claim = gate_claim_uid(gate["id"])
        decision = gate_decision_uid(gate["id"])
        nodes.append(
            _node(
                claim,
                ["Concept", "Hypothesis"],
                {
                    **_common(
                        name=f"{gate['id']} — {gate['name']} [{TAG}]",
                        description=gate["claim"],
                        authority="SECONDARY_AI",
                        scope="TS_EFFECT_MIGRATION_GATE_CLAIM",
                        kind="CLAIM",
                        plane="INQUIRY",
                        state="ASSESSED_AT_AUDIT_COMMIT",
                        owner="effect_fp_gate_claim_custodian",
                        roles=["CLAIM", "MIGRATION_GATE"],
                        boundary="A gate claim is assessed against code at one commit; it is not a gate pass.",
                    ),
                    "standard_graph_role": "CLAIM",
                    "gate_id": gate["id"],
                    "gate_status_word": gate["status_word"],
                    "current_decision_uid": decision,
                },
            )
        )
        nodes.append(
            _node(
                decision,
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"{gate['id']} current decision [{TAG}]",
                        description=gate["finding"],
                        authority="SECONDARY_AI",
                        scope="TS_EFFECT_MIGRATION_GATE_DECISION",
                        kind="DECISION",
                        plane="MODEL",
                        state="CURRENT",
                        owner="effect_fp_gate_decision_custodian",
                        roles=["DECISION", "MIGRATION_GATE"],
                        boundary="The decision records the audit's disposition; a future audit may replace it without rewriting this record.",
                    ),
                    "standard_graph_role": "DECISION",
                    "assesses_claim_uid": claim,
                    "evidence_disposition": gate["disposition"],
                    "claim_ceiling": CLAIM_CEILING,
                    "decided_on": "2026-09-05",
                },
            )
        )
        relations.append(_relation(claim, "HAS_CONCEPT", decision, "CURRENT_DECISION", "ACTIVE"))
        relations.append(_relation(claim, "HAS_SOURCE", AUDIT_RUN_UID, "AUDIT_EVIDENCE", "ACTIVE"))
        relations.append(_relation(claim, "HAS_SOURCE", source_uid(GATE_DOC_PATH), "GATE_DEFINITION", "ACTIVE"))
        relations.append(_relation(decision, "CONSTRAINS", claim, "DISPOSITION", "ACTIVE"))
        relations.append(_relation(decision, "HAS_SOURCE", AUDIT_RUN_UID, "AUDIT_EVIDENCE", "ACTIVE"))
        relations.append(_relation(claim, "PART_OF", PROGRAM_UID, "GATE_TABLE", "ACTIVE"))
    loop_decision = gate_decision_uid(LOOP_CLAIM["id"])
    relations.append(_relation(loop_decision, "PRESERVES", CLOSURE_FINDING_SUBSTRATE_UID, "FINDING_STILL_STANDS", "ACTIVE"))
    relations.append(_relation(loop_decision, "PRESERVES", CLOSURE_FINDING_NO_BRIDGE_UID, "FINDING_STILL_STANDS", "ACTIVE"))
    relations.append(_relation(loop_decision, "PRESERVES", UNIVERSAL_REFINEMENT_GAP_UID, "LEAN_REFINEMENT_UNCHANGED", "ACTIVE"))

    # Shortfall gaps.
    closed_by: dict[str, list[str]] = {gap["id"]: [] for gap in FP_GAPS}
    narrowed_by: dict[str, list[str]] = {gap["id"]: [] for gap in FP_GAPS}
    for package in PACKAGES:
        for gap_id in package["closes"]:
            closed_by[gap_id].append(package["id"])
        for gap_id in package["narrows"]:
            narrowed_by[gap_id].append(package["id"])
    for gap in FP_GAPS:
        rule_hits_in_lanes = _counts_for(per_file, list(allowlist["files"]))
        remaining_in_lanes = sum(rule_hits_in_lanes[rule] for rule in gap["rules"])
        if closed_by[gap["id"]] and remaining_in_lanes == 0:
            closure_status = "CLOSED"
        elif lint_green:
            closure_status = "CLOSED_OUTSIDE_EXEMPT_LANES"
        else:
            closure_status = "OPEN"
        nodes.append(
            _node(
                gap_uid(gap["id"]),
                ["Concept", "Hypothesis"],
                {
                    **_common(
                        name=f"{gap['id']} — {gap['name']} [{TAG}]",
                        description=f"Before: {gap['before']} After: {gap['after']}",
                        authority="SECONDARY_AI",
                        scope="FUNCTIONAL_PROGRAMMING_SHORTFALL",
                        kind="GAP",
                        plane="INQUIRY",
                        state=closure_status,
                        owner="effect_fp_gap_custodian",
                        roles=["GAP", "ENGINEERING_STATUS"],
                        boundary="A shortfall gap is about code shape; closing it changes no scientific status.",
                    ),
                    "standard_graph_role": "GAP",
                    "gap_id": gap["id"],
                    "lint_rule_ids": gap["rules"],
                    "closure_status": closure_status,
                    "closed_by_package_ids": closed_by[gap["id"]],
                    "narrowed_by_package_ids": narrowed_by[gap["id"]],
                    "remaining_hits_in_exempt_lanes": remaining_in_lanes,
                },
            )
        )
        relations.append(_relation(gap_uid(gap["id"]), "HAS_SOURCE", AUDIT_RUN_UID, "AUDIT_EVIDENCE", "ACTIVE"))
        relations.append(_relation(gap_uid(gap["id"]), "PART_OF", PROGRAM_UID, "SHORTFALL_TABLE", "ACTIVE"))
        for rule in gap["rules"]:
            relations.append(_relation(gap_uid(gap["id"]), "MEASURES", rule_uid(rule), "LINT_RULE_MEASURES_GAP", "ACTIVE"))

    # Refactor packages.
    for package in PACKAGES:
        uid = package_uid(package["id"])
        before = _counts_for(BASELINE_PER_FILE, package["files"])
        after = _counts_for(per_file, package["files"])
        nodes.append(
            _node(
                uid,
                ["Concept"],
                {
                    **_common(
                        name=f"{package['id']} — {package['name']} [{TAG}]",
                        description=(
                            f"Files: {', '.join(package['files']) or 'scripts, package.json, CI'}; tests: {', '.join(package['tests'])}."
                        ),
                        authority="SECONDARY_AI",
                        scope="REFACTOR_PACKAGE_ONE_COMMIT",
                        kind="TASK",
                        plane="INQUIRY",
                        state="MERGED_TO_MAIN",
                        owner="effect_fp_package_custodian",
                        roles=["REFACTOR_PACKAGE", "TECHNICAL_WORK"],
                        boundary="A package is one commit on main; its tests are its only completion evidence.",
                    ),
                    "package_id": package["id"],
                    "commit": package["commit"],
                    "files": package["files"],
                    "tests": package["tests"],
                    "lint_hits_before": _hits(before),
                    "lint_hits_after": _hits(after),
                    "lint_counts_before": [f"{rule}={before[rule]}" for rule in LINT_RULES_ORDER],
                    "lint_counts_after": [f"{rule}={after[rule]}" for rule in LINT_RULES_ORDER],
                },
            )
        )
        relations.append(_relation(uid, "PART_OF", PROGRAM_UID, "PACKAGE_ORDER", "ACTIVE"))
        for gap_id in package["closes"]:
            relations.append(_relation(uid, "CLOSES", gap_uid(gap_id), "SHORTFALL_CLOSED", "ACTIVE"))
        for gap_id in package["narrows"]:
            relations.append(_relation(uid, "NARROWS", gap_uid(gap_id), "SHORTFALL_NARROWED", "ACTIVE"))
        for anchor in package["refines"]:
            relations.append(_relation(uid, "REFINES", anchor, "SAME_CONTRACT_EFFECT_NATIVE", "ACTIVE"))
        for anchor in package["preserves"]:
            relations.append(_relation(uid, "PRESERVES", anchor, "CONTRACT_UNCHANGED", "ACTIVE"))
        for name in package["files"]:
            relations.append(_relation(uid, "REFACTORS", file_uid(name), "FILE_IN_PACKAGE", "ACTIVE"))
        for service in SERVICES:
            if service["provided_by"] == package["id"]:
                relations.append(_relation(uid, "PROVIDES", service_uid(service["id"]), "SERVICE_INTRODUCED", "ACTIVE"))
            elif service["provided_by"] == "P-0" and package["id"] not in {"P-0", "P-8"} and service["id"] != "LocalPermitCommitStoreService":
                relations.append(_relation(uid, "USES", service_uid(service["id"]), "SERVICE_CONSUMED", "ACTIVE"))

    # Refactored files with before/after counts.
    for name in refactored_files:
        before = _counts_for(BASELINE_PER_FILE, [name])
        after = _counts_for(per_file, [name])
        nodes.append(
            _node(
                file_uid(name),
                ["AbstractNode", "SourceDocument", "ResearchArtifact"],
                {
                    **_common(
                        name=f"{name} [{TAG}]",
                        description=f"src/hswm/effect-runtime/src/{name}: lint hits {_hits(before)} at the baseline commit, {_hits(after)} at the bound report.",
                        authority="SYSTEM_DERIVED",
                        scope="REFACTORED_SOURCE_FILE",
                        kind="ARTIFACT",
                        plane="EVIDENCE",
                        state="REFACTORED",
                        owner="effect_fp_boundary_projection_custodian",
                        roles=["SOURCE_FILE", "ENGINEERING_STATUS"],
                        boundary="A file record carries lint counts only; it is not a correctness claim.",
                    ),
                    "source_path": f"src/hswm/effect-runtime/src/{name}",
                    "lint_counts_before": [f"{rule}={before[rule]}" for rule in LINT_RULES_ORDER],
                    "lint_counts_after": [f"{rule}={after[rule]}" for rule in LINT_RULES_ORDER],
                    "in_exempt_lane": name in allowlist["files"],
                },
            )
        )
        relations.append(_relation(file_uid(name), "PART_OF", PROGRAM_UID, "REFACTORED_FILE", "ACTIVE"))

    # Services.
    for service in SERVICES:
        nodes.append(
            _node(
                service_uid(service["id"]),
                ["Concept", "Service"],
                {
                    **_common(
                        name=f"{service['id']} service [{TAG}]",
                        description=service["description"],
                        authority="SECONDARY_AI",
                        scope="EFFECT_CONTEXT_SERVICE",
                        kind="COMPONENT",
                        plane="MODEL",
                        state="IMPLEMENTED",
                        owner="effect_fp_service_custodian",
                        roles=["EFFECT_SERVICE", "ADAPTER_BOUNDARY"],
                        boundary="A service is a typed capability port; providing it proves nothing about the data it moves.",
                    ),
                    "service_id": service["id"],
                    "source_file": f"src/hswm/effect-runtime/src/{service['file']}",
                    "context_tag": service["tag"],
                    "provided_by_package_id": service["provided_by"],
                },
            )
        )
        relations.append(_relation(service_uid(service["id"]), "PART_OF", PROGRAM_UID, "SERVICE_TABLE", "ACTIVE"))
        if service["id"] in {"PosixFileSystem", "BoundedSubprocess"}:
            relations.append(_relation(service_uid(service["id"]), "REFINES", CELL_EVENT_RUNTIME_UID, "ADAPTER_BOUNDARY", "ACTIVE"))

    # Lint module and rules.
    nodes.append(
        _node(
            LINT_MODULE_UID,
            ["Concept", "CodeModule"],
            {
                **_common(
                    name=f"Effect boundary lint [{TAG}]",
                    description=(
                        "scripts/lint-effect-boundary.mjs: dependency-free scan of src/*.ts for R1-R5 with a --json report, "
                        "a shrinking-only lane allowlist whose stale entries fail the run, wired into npm run check and CI."
                    ),
                    authority="SECONDARY_AI",
                    scope="STATIC_BOUNDARY_ENFORCEMENT",
                    kind="COMPONENT",
                    plane="MODEL",
                    state="ENFORCED_IN_CHECK_AND_CI" if lint_green else "REPORT_ONLY",
                    owner="effect_fp_lint_custodian",
                    roles=["GUARDRAIL", "STATIC_CHECK"],
                    boundary="A regex lint enforces shape, not semantics; it cannot prove purity or correctness.",
                ),
                "source_path": LINT_PATH.as_posix(),
                "rule_ids": [rule["id"] for rule in LINT_RULES],
                "lane_ids": list(lanes),
            },
        )
    )
    relations.append(_relation(LINT_MODULE_UID, "HAS_SOURCE", source_uid(LINT_PATH), "LINT_SOURCE", "ACTIVE"))
    relations.append(_relation(LINT_MODULE_UID, "GUARDS", PROGRAM_UID, "BOUNDARY_ENFORCEMENT", "ACTIVE"))
    relations.append(_relation(LINT_MODULE_UID, "PRESERVES", CLOSURE_SR5_UID, "NO_EXACT_BYTE_PINS_COUNTS_ONLY", "ACTIVE"))
    for rule in LINT_RULES:
        nodes.append(
            _node(
                rule_uid(rule["id"]),
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"{rule['id']} — {rule['name']} [{TAG}]",
                        description=rule["pattern"],
                        authority="SECONDARY_AI",
                        scope="EFFECT_BOUNDARY_LINT_RULE",
                        kind="GUARDRAIL",
                        plane="MODEL",
                        state="ENFORCED",
                        owner="effect_fp_lint_custodian",
                        roles=["LINT_RULE", "GUARDRAIL"],
                        boundary="A rule forbids a syntactic construct outside its lanes; it does not certify the code it admits.",
                    ),
                    "rule_id": rule["id"],
                    "baseline_hits": BASELINE_COUNTS[rule["id"]],
                    "current_hits_total": int(report["counts"][rule["id"]]),
                    "current_hits_in_exempt_lanes": _counts_for(per_file, list(allowlist["files"]))[rule["id"]],
                },
            )
        )
        relations.append(_relation(LINT_MODULE_UID, "ENFORCES", rule_uid(rule["id"]), "RULE", "ACTIVE"))
        relations.append(_relation(rule_uid(rule["id"]), "CONSTRAINS", PROGRAM_UID, "BOUNDARY_RULE", "ACTIVE"))

    # Exemption lanes.
    for lane_id, reason in lanes.items():
        files = sorted(lane_files[lane_id])
        counts = _counts_for(per_file, files)
        rules_present = [rule for rule in LINT_RULES_ORDER if counts[rule] > 0]
        nodes.append(
            _node(
                lane_uid(lane_id),
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"{lane_id} exemption lane [{TAG}]",
                        description=reason,
                        authority="SECONDARY_AI",
                        scope="EFFECT_BOUNDARY_EXEMPTION_LANE",
                        kind="GUARDRAIL",
                        plane="MODEL",
                        state="EXEMPT_WITH_REASON",
                        owner="effect_fp_lane_custodian",
                        roles=["EXEMPTION_LANE", "GUARDRAIL"],
                        boundary="A lane names imperative code that is deliberately retained; the allowlist may only shrink.",
                    ),
                    "lane_id": lane_id,
                    "files": files,
                    "file_count": len(files),
                    "lint_counts": [f"{rule}={counts[rule]}" for rule in LINT_RULES_ORDER],
                    "lint_hits": _hits(counts),
                },
            )
        )
        relations.append(_relation(lane_uid(lane_id), "HAS_SOURCE", source_uid(ALLOWLIST_PATH), "LANE_ALLOWLIST", "ACTIVE"))
        relations.append(_relation(lane_uid(lane_id), "NARROWS", LINT_MODULE_UID, "LANE_EXEMPTION", "ACTIVE"))
        for gap in FP_GAPS:
            if gap["id"] in {"FP-GAP-3", "FP-GAP-5", "FP-GAP-6"}:
                continue
            if any(rule in rules_present for rule in gap["rules"]):
                relations.append(_relation(lane_uid(lane_id), "NARROWS", gap_uid(gap["id"]), "GAP_REMAINS_INSIDE_LANE", "ACTIVE"))
        if lane_id in {"HISTORICAL_S2S", "DNRD5_PROTOCOL"}:
            relations.append(_relation(lane_uid(lane_id), "PRESERVES", CLOSURE_SR4_UID, "FROZEN_UNTIL_G1_VERDICT", "ACTIVE"))

    nodes.append(
        _node(
            SR4_DEVIATION_UID,
            ["Concept", "Guardrail"],
            {
                **_common(
                    name=f"SR-4 deviation record for this bundle [{TAG}]",
                    description=(
                        "SR-4 (PROPOSED, not ratified) freezes new ontology JSON versions until the G1 verdict.  This bundle is a new "
                        "version created on the user's explicit 2026-09-06 instruction to connect the Effect-boundary work to the KG.  "
                        "The record exists so the deviation is visible in the graph rather than silent."
                    ),
                    authority="SECONDARY_AI",
                    scope="STOP_RULE_DEVIATION_RECORD",
                    kind="GUARDRAIL",
                    plane="MODEL",
                    state="RECORDED",
                    owner="effect_fp_boundary_projection_custodian",
                    roles=["DEVIATION_RECORD", "GUARDRAIL"],
                    boundary="Recording a deviation does not ratify or weaken the stop rule.",
                ),
                "deviating_bundle_uid": BUNDLE_UID,
                "instruction_date": "2026-09-06",
            },
        )
    )
    relations.append(_relation(SR4_DEVIATION_UID, "ADDRESSES", CLOSURE_SR4_UID, "USER_INSTRUCTED_NEW_VERSION", "ACTIVE"))
    relations.append(_relation(SR4_DEVIATION_UID, "PART_OF", BUNDLE_UID, "DEVIATION_RECORD", "ACTIVE"))

    relations.sort(key=lambda row: (row["from_uid"], row["type"], row["to_uid"]))
    counts = {
        "anchors": len(ANCHORS),
        "nodes": len(nodes),
        "relations": len(relations),
        "source_records": len(SOURCE_BINDING_PATHS),
        "qualification_runs": 2,
        "gate_claims": len(GATES) + 1,
        "gate_decisions": len(GATES) + 1,
        "fp_gaps": len(FP_GAPS),
        "packages": len(PACKAGES),
        "refactored_files": len(refactored_files),
        "services": len(SERVICES),
        "lint_rules": len(LINT_RULES),
        "lanes": len(lanes),
        "lane_files": len(allowlist["files"]),
        "lint_violations_outside_lanes": int(report["violations"]),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_uid": BUNDLE_UID,
        "status": STATUS,
        "nonclaim": NONCLAIM,
        "authority_boundary": (
            "Every node is a SECONDARY_AI engineering-status record or a SYSTEM_DERIVED hash-bound source.  The refactor "
            "changes code shape only: the six TypeScript/Effect migration gates stay unclosed, the decisive HSWM loop stays "
            "in Python, and nothing here passes G0 or G1 or promotes any scientific claim."
        ),
        "source_accessed_on": RELEASE,
        "artifact_bindings": bindings,
        "expected_counts": counts,
        "anchors": ANCHORS,
        "nodes": nodes,
        "relations": relations,
    }


def validate_data(data: dict[str, Any]) -> None:
    """Fail closed on graph-shape, identity, or property-type drift."""

    expected_keys = {
        "schema_version", "bundle_uid", "status", "nonclaim", "authority_boundary",
        "source_accessed_on", "artifact_bindings", "expected_counts", "anchors", "nodes", "relations",
    }
    if set(data) != expected_keys:
        raise ValueError("effect fp-boundary ontology top-level shape drifted")
    if data["schema_version"] != SCHEMA_VERSION or data["bundle_uid"] != BUNDLE_UID:
        raise ValueError("effect fp-boundary ontology identity drifted")
    if data["status"] != STATUS or data["nonclaim"] != NONCLAIM:
        raise ValueError("effect fp-boundary status or nonclaim drifted")
    nodes = data["nodes"]
    anchors = data["anchors"]
    relations = data["relations"]
    uids = [row["uid"] for row in nodes] + [row["uid"] for row in anchors]
    duplicates = {uid: count for uid, count in Counter(uids).items() if count > 1}
    if duplicates:
        raise ValueError(f"duplicate uid: {duplicates}")
    for row in nodes:
        if set(row) != {"uid", "labels", "properties"} or not SAFE_UID.fullmatch(row["uid"]):
            raise ValueError(f"unsafe node: {row.get('uid')}")
        if not row["labels"] or len(row["labels"]) != len(set(row["labels"])):
            raise ValueError(f"invalid labels: {row['uid']}")
        properties = row["properties"]
        for key, value in properties.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
                raise ValueError(f"unsafe property key {key} on {row['uid']}")
            if not (
                isinstance(value, (str, bool, int, float))
                or (isinstance(value, list) and all(isinstance(item, (str, bool, int, float)) for item in value))
            ):
                raise ValueError(f"non-scalar property {key} on {row['uid']}")
        for key in ("name", "description", "authority_class", "claim_boundary", "semantic_roles"):
            if not properties.get(key):
                raise ValueError(f"missing {key} on {row['uid']}")
        if properties.get("projection_nonclaim") != NONCLAIM:
            raise ValueError(f"nonclaim drifted on {row['uid']}")
        role = properties.get("standard_graph_role")
        if role == "CLAIM" and not properties.get("current_decision_uid"):
            raise ValueError(f"claim without decision: {row['uid']}")
        if role == "DECISION":
            if not properties.get("assesses_claim_uid"):
                raise ValueError(f"decision without claim: {row['uid']}")
            if properties["evidence_disposition"] not in {"NOT_EVALUATED", "SUPPORTED_IN_SCOPE", "RED", "UNDERDETERMINED"}:
                raise ValueError(f"invalid disposition: {row['uid']}")
        if role == "EVIDENCE_ARTIFACT" and not re.fullmatch(r"[0-9a-f]{64}", properties.get("source_sha256", "")):
            raise ValueError(f"evidence artifact without digest: {row['uid']}")
        if role == "QUALIFICATION_RUN" and not (properties.get("attestation_level") and properties.get("qualification_status")):
            raise ValueError(f"qualification run without attestation: {row['uid']}")
        if "REFACTOR_PACKAGE" in properties["semantic_roles"] and not re.fullmatch(r"[0-9a-f]{40}", properties.get("commit", "")):
            raise ValueError(f"package without bound commit: {row['uid']}")
    all_uids = set(uids)
    seen: set[tuple[str, str, str]] = set()
    for row in relations:
        if set(row) != {"from_uid", "type", "to_uid", "authority_class", "scope", "status"}:
            raise ValueError("relation shape drifted")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", row["type"]):
            raise ValueError(f"unsafe relation type: {row['type']}")
        if row["from_uid"] not in all_uids or row["to_uid"] not in all_uids:
            raise ValueError(f"dangling relation: {row}")
        key = (row["from_uid"], row["type"], row["to_uid"])
        if key in seen:
            raise ValueError(f"duplicate relation: {key}")
        seen.add(key)
    node_uids = {row["uid"] for row in nodes}
    for row in relations:
        if row["from_uid"] not in node_uids:
            raise ValueError(f"relation must originate from an owned node: {row}")
    if sorted(relations, key=lambda row: (row["from_uid"], row["type"], row["to_uid"])) != relations:
        raise ValueError("relations are not canonically ordered")
    counts = data["expected_counts"]
    if counts["nodes"] != len(nodes) or counts["anchors"] != len(anchors) or counts["relations"] != len(relations):
        raise ValueError("expected counts drifted")
    roles = Counter(row["properties"].get("standard_graph_role") for row in nodes)
    semantic = Counter(role for row in nodes for role in row["properties"]["semantic_roles"])
    if roles["CLAIM"] != counts["gate_claims"] or roles["DECISION"] != counts["gate_decisions"]:
        raise ValueError("gate claim or decision counts drifted")
    if roles["GAP"] != counts["fp_gaps"] or roles["QUALIFICATION_RUN"] != counts["qualification_runs"]:
        raise ValueError("gap or qualification-run counts drifted")
    if roles["EVIDENCE_ARTIFACT"] != counts["source_records"]:
        raise ValueError("source record counts drifted")
    if semantic["REFACTOR_PACKAGE"] != counts["packages"] or semantic["EFFECT_SERVICE"] != counts["services"]:
        raise ValueError("package or service counts drifted")
    if semantic["LINT_RULE"] != counts["lint_rules"] or semantic["EXEMPTION_LANE"] != counts["lanes"]:
        raise ValueError("lint rule or lane counts drifted")
    if semantic["SOURCE_FILE"] != counts["refactored_files"]:
        raise ValueError("refactored file counts drifted")


def encoded_data(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(payload).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--digests", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / ONTOLOGY_PATH)
    args = parser.parse_args()
    data = build_data()
    validate_data(data)
    payload = encoded_data(data)
    if args.digests:
        print(
            json.dumps(
                {
                    "anchors_sha256": canonical_sha(data["anchors"]),
                    "file_sha256": sha256(payload).hexdigest(),
                    "nodes_sha256": canonical_sha(data["nodes"]),
                    "projection_sha256": canonical_sha(data),
                    "relations_sha256": canonical_sha(data["relations"]),
                    "expected_counts": data["expected_counts"],
                },
                sort_keys=True,
            )
        )
        return
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != payload:
            raise SystemExit("effect fp-boundary ontology projection drifted")
        print(json.dumps({"status": "MATCH", "path": str(args.output)}, sort_keys=True))
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(json.dumps({"status": "BUILT", "path": str(args.output), "sha256": sha256(payload).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
