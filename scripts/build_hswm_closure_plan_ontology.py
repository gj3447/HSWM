#!/usr/bin/env python3
"""Build the bounded HSWM closure-plan KG projection (event version v2).

The projection records one adversarial programme audit (14 verified findings),
the open closure gaps, four USER_PRIMARY decisions that are only PROPOSED until
the user's own words are hash-bound, two proposed G0 sub-gates, one finite v1
done-state, six ordered closure steps, five stop rules, and one numeric burden
cap.  It is a bounded research-governance projection.  It is not HSWM
cognition, learning, canonical state, a Permit, a gate pass, a user
ratification, or a scientific result.
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
ONTOLOGY_PATH = Path("ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v3.json")
CLOSURE_DOC_PATH = Path(
    "docs/research/HSWM_ADVERSARIAL_AUDIT_AND_CLOSURE_PLAN_2026-09-05.md"
)
FINDINGS_PATH = Path(
    "_research/causal_composition/audits/HSWM_ADVERSARIAL_AUDIT_FINDINGS_2026-09-05.json"
)
# Event version v2: the user's verbatim ratification of D-1 and D-4.
RATIFICATION_SOURCE_PATH: Path | None = Path(
    "docs/canon/sources/USER_PRIMARY_HSWM_CLOSURE_DECISIONS_2026-09-05.txt"
)
RATIFIED_DECISIONS: tuple[str, ...] = ("D-1", "D-4")
RATIFIED_ON = "2026-09-05"
# Event version v3: the opaque v3 (G0-local) receipt of 2026-09-06 (S-3 run
# complete, preregistered rule not met) and the S-2 Permit bridge it used.
V3_RESULTS_PATH = Path("results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_RESULTS_2026-09-06.md")
V3_EVIDENCE_PATH = Path("evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_2026-09-06.json")
V3_PROTOCOL_PATH = Path(
    "_research/causal_composition/preregistrations/g1_opaque_identifiability_v3_2026-09-06-r2/protocol.v1.json"
)
SOURCE_BINDING_PATHS: tuple[Path, ...] = tuple(
    path
    for path in (CLOSURE_DOC_PATH, FINDINGS_PATH, RATIFICATION_SOURCE_PATH, V3_RESULTS_PATH, V3_EVIDENCE_PATH, V3_PROTOCOL_PATH)
    if path
)

SCHEMA_VERSION = "hswm-closure-plan-ontology/v3"
RELEASE = "2026-09-06"
TAG = "2026-09-05-v3"
PREDECESSOR_TAG = "2026-09-05-v2"
AUDITED_COMMIT = "4dcba752a661de23066b3b33381bfdfc34879a57"
STATUS = (
    "ADVERSARIAL_AUDIT_VERIFIED_CLOSURE_PLAN_D1_D4_USER_RATIFIED_D2_D3_PROPOSED_"
    "S2_S3_COMPLETE_V3_RULE_NOT_MET_G0_NOT_PASSED_G1_LOCKED"
)
V3_STUDY_UID = "sym:ExploratoryStudy:hswm-g1-opaque-identifiability-v3-2026-09-06-r2"
V3_TERMINAL = "V3_COMPLETE_NO_SEPARATION_NO_EFFICACY_INFERENCE"
V3_PROTOCOL_CANONICAL_SHA256 = "2363815ecfc575857f812931566d6f8f8132bfa6ab480d35655827f68cd96fc6"
V3_BUNDLE_SHA256 = "69d8d7846035eb3060caade0002ee58327200848ccc05589598b134790e44584"
V3_ABORTED_PROTOCOL_CANONICAL_SHA256 = "4d049c7bfeabbbbb969cec8e9c77a7c06e4a193e880d70dd3a28551cdd534e6d"
COMPLETED_STEPS: dict[str, dict[str, Any]] = {
    "S-2": {
        "completed_on": "2026-09-05",
        "commit": "51f631b4e15bdd3ca48219c8df66bd3fa165ccb8",
        "outcome": "PERMIT_BRIDGE_IMPLEMENTED_AND_EXERCISED_BY_96_V3_COMMITS",
    },
    "S-3": {
        "completed_on": "2026-09-06",
        "commit": "e926e1fcbdef3c6da41a92995346df934289180b",
        "outcome": "RUN_COMPLETE_PREREGISTERED_RULE_NOT_MET",
    },
}
# Burden-cap reading at the S-3 results commit (scripts/check_hswm_closure_burden_cap.py).
BURDEN_READING = {
    "reading_commit": "e926e1fcbdef3c6da41a92995346df934289180b",
    "reading_commits_observed": 36,
    "reading_core_commits": 15,
    "reading_core_share": 0.4167,
    "reading_status": "WINDOW_OPEN_BELOW_SHARE",
}
NONCLAIM = (
    "AUDIT_AND_CLOSURE_PLAN_KG_PROJECTION_ONLY_NOT_HSWM_COGNITION_LEARNING_"
    "EFFICACY_GATE_PASS_USER_RATIFICATION_OR_SCIENTIFIC_RESULT"
)
PROPOSED = "PROPOSED_AWAITING_USER_PRIMARY"
AUDIT_CEILING = "SELF_ATTESTED_AI_ADVERSARIAL_AUDIT_NOT_INDEPENDENTLY_QUALIFIED"

BUNDLE_UID = f"sym:AbstractNode:hswm-closure-plan-ontology-{TAG}"
PROGRAM_UID = f"sym:ResearchProgram:hswm-closure-plan-{TAG}"
AUDIT_RUN_UID = f"sym:AbstractNode:hswm-closure-audit-run-{TAG}"
CLOSURE_DOC_UID = f"sym:AbstractNode:hswm-closure-source-audit-and-closure-plan-doc-{TAG}"
FINDINGS_UID = f"sym:AbstractNode:hswm-closure-source-audit-findings-json-{TAG}"
DONE_STATE_UID = f"sym:Concept:hswm-closure-v1-done-state-{TAG}"
BURDEN_CAP_UID = f"sym:Concept:hswm-closure-burden-cap-{TAG}"
RATIFICATION_SOURCE_UID = f"sym:AbstractNode:hswm-closure-source-user-primary-closure-decisions-{TAG}"
V3_RECEIPT_UID = f"sym:AbstractNode:hswm-closure-v3-receipt-{TAG}"
V3_RESULTS_UID = f"sym:AbstractNode:hswm-closure-source-v3-results-doc-{TAG}"
V3_EVIDENCE_UID = f"sym:AbstractNode:hswm-closure-source-v3-evidence-json-{TAG}"
V3_PROTOCOL_UID = f"sym:AbstractNode:hswm-closure-source-v3-frozen-protocol-{TAG}"
EFFECT_FP_BUNDLE_UID = "sym:AbstractNode:hswm-effect-fp-boundary-ontology-2026-09-06"
PREDECESSOR_BUNDLE_UID = f"sym:AbstractNode:hswm-closure-plan-ontology-{PREDECESSOR_TAG}"
PREDECESSOR_PROGRAM_UID = f"sym:ResearchProgram:hswm-closure-plan-{PREDECESSOR_TAG}"

# Anchors: MATCH-only nodes that already exist in the live KG.  Names are
# copied from the live readback of 2026-09-05 and are asserted at publish time.
HSWM_UID = "sym:Concept:hswm"
CAUSAL_PROGRAM_UID = "sym:ResearchProgram:hswm-causal-composition-research-2026-08-29"
G0_UID = "sym:Hypothesis:hswm-meta-g0-measurement-integrity"
G1_UID = "sym:Hypothesis:hswm-meta-g1-local-causal-rung"
PS5_UID = "sym:Concept:hswm-proof-status-claim-outcome-truth-causal-credit-2026-09-02-v6"
PS6_UID = "sym:Concept:hswm-proof-status-claim-revision-real-llm-efficacy-2026-09-02-v6"
ADAPTIVE_BUNDLE_UID = "sym:AbstractNode:hswm-adaptive-research-strategy-ontology-2026-08-30"
RG4_UID = "sym:Concept:hswm-adaptive-guard-no-immunization"
RG6_UID = "sym:Concept:hswm-adaptive-guard-anti-ragnarok"
GRAPH_LOOP_PROGRAM_UID = "sym:ResearchProgram:hswm-graph-and-loop-engineering-2026-09-02-v6"
GATE_UIDS = {"G0": G0_UID, "G1": G1_UID}
PROOF_CLAIM_UIDS = {"PS-5": PS5_UID, "PS-6": PS6_UID}

ANCHORS: list[dict[str, Any]] = [
    {"uid": HSWM_UID, "name": "HSWM", "required_labels": ["Concept"]},
    {
        "uid": CAUSAL_PROGRAM_UID,
        "name": "HSWM causal-composition research program",
        "required_labels": ["Concept", "ResearchProgram", "ResearchArtifact"],
    },
    {"uid": G0_UID, "name": "G0 — Measurement integrity", "required_labels": ["Concept", "Hypothesis"]},
    {
        "uid": G1_UID,
        "name": "G1 — Minimal outcome-bound causal rung",
        "required_labels": ["Concept", "Hypothesis"],
    },
    {
        "uid": PS5_UID,
        "name": "External outcome truth and independent causal credit [2026-09-02-v6]",
        "required_labels": ["Concept"],
    },
    {
        "uid": PS6_UID,
        "name": "Revision-caused improvement in real LLM behavior [2026-09-02-v6]",
        "required_labels": ["Concept"],
    },
    {
        "uid": ADAPTIVE_BUNDLE_UID,
        "name": "HSWM adaptive research strategy ontology",
        "required_labels": ["AbstractNode", "ResearchArtifact"],
    },
    {"uid": RG4_UID, "name": "RG-4 — No post-hoc immunization", "required_labels": ["Concept", "Guardrail"]},
    {
        "uid": RG6_UID,
        "name": "RG-6 — Anti-Ragnarok burden discipline",
        "required_labels": ["Concept", "Guardrail"],
    },
    {
        "uid": GRAPH_LOOP_PROGRAM_UID,
        "name": "HSWM graph and loop engineering reinforcement program [2026-09-02-v6]",
        "required_labels": ["Concept", "ResearchProgram", "ResearchArtifact"],
    },
    {
        "uid": PREDECESSOR_BUNDLE_UID,
        "name": f"HSWM closure plan ontology [{PREDECESSOR_TAG}]",
        "required_labels": ["AbstractNode", "ResearchArtifact"],
    },
    {
        "uid": PREDECESSOR_PROGRAM_UID,
        "name": f"HSWM closure plan [{PREDECESSOR_TAG}]",
        "required_labels": ["Concept", "ResearchProgram", "ResearchArtifact"],
    },
    {
        "uid": EFFECT_FP_BUNDLE_UID,
        "name": "HSWM Effect runtime functional boundary ontology [2026-09-06]",
        "required_labels": ["AbstractNode", "ResearchArtifact"],
    },
]

SEVERITY_ORDER = {"NONE": 0, "MINOR": 1, "MAJOR": 2, "FATAL": 3}
LENSES = (
    "gate-satisfiability",
    "mechanism-underspecified",
    "effort-allocation",
    "lean-vacuity",
    "code-vs-docs",
    "scientific-coherence",
    "process-pathology",
    "minimal-closing-experiment",
)
REFUTERS = ("evidence-skeptic", "steelman-maintainer")
MAX_EVIDENCE_REFS = 12
MAX_TEXT = 700


def _clip(value: str, limit: int = MAX_TEXT) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# finding key -> (gap ids, blocked gates, assessed proof claims)
FINDING_LINKS: dict[str, dict[str, list[str]]] = {
    "g0-requires-nine-independent-roles-with-no-plan": {
        "gaps": ["GAP-1"], "blocks": ["G0"], "assesses": ["PS-5"],
    },
    "hswm-delta-is-governance-not-behavior": {
        "gaps": ["GAP-4"], "blocks": ["G1"], "assesses": ["PS-6"],
    },
    "core-loop-starved-by-substrate-engineering": {
        "gaps": ["GAP-2", "GAP-6"], "blocks": ["G0"], "assesses": ["PS-6"],
    },
    "loop-degenerates-to-one-bit-copy-register": {
        "gaps": ["GAP-3", "GAP-4"], "blocks": ["G1"], "assesses": ["PS-6"],
    },
    "target-closed-as-civilizational-horizon-no-done-state": {
        "gaps": ["GAP-5"], "blocks": [], "assesses": [],
    },
    "g0-requirement-accretion-and-circular-qualification": {
        "gaps": ["GAP-1", "GAP-6"], "blocks": ["G0"], "assesses": ["PS-5"],
    },
    "monotone-ratchet-no-termination-rule": {
        "gaps": ["GAP-5", "GAP-6"], "blocks": [], "assesses": [],
    },
    "void-driven-instrument-fanout-without-closure": {
        "gaps": ["GAP-3", "GAP-7"], "blocks": ["G0"], "assesses": ["PS-5"],
    },
    "handoff-projection-ceremony-as-unit-of-work": {
        "gaps": ["GAP-6"], "blocks": [], "assesses": [],
    },
    "semantic-weight-has-no-executable-definition": {
        "gaps": ["GAP-4"], "blocks": [], "assesses": [],
    },
    "bridge-theorems-satisfied-by-trivial-interpretation": {
        "gaps": [], "blocks": [], "assesses": [],
    },
    "proof-burst-formalizes-unrun-dnrd5-off-critical-path": {
        "gaps": ["GAP-6"], "blocks": [], "assesses": [],
    },
    "no-bridge-between-llm-instrument-and-atom-v2-permit": {
        "gaps": ["GAP-2"], "blocks": ["G1"], "assesses": ["PS-6"],
    },
    "ts-lean-link-is-caller-asserted-booleans": {
        "gaps": [], "blocks": [], "assesses": [],
    },
}

GAPS: dict[str, tuple[str, str]] = {
    "GAP-1": (
        "G0-external roles have no designated second party",
        "No named custodian, evaluator-B, WORM administrator, or external auditor exists for the nine pairwise-distinct roles that the 2026-09-03 occurrence-integrity profile requires; the preflight returns BLOCKED_EXTERNAL with 22 missing bindings.",
    ),
    "GAP-2": (
        "No bridge between the Python LLM instrument and the Atom v2 Permit path",
        "g1_micro.py issues an experiment-local grant and never calls the TypeScript local Permit commit; the Effect runtime makes no LLM call. The decisive recurrence has never crossed the real owner/Permit admission path.",
    ),
    "GAP-3": (
        "No G0-local rerun with randomized candidate position, sham arm, and separate-process evaluator",
        "The 2026-08-30 v2 occurrence showed a first-candidate position bias and used a same-process evaluator; do_not_rerun_this_occurrence is true and no v3 preregistration exists.",
    ),
    "GAP-4": (
        "G1 estimand is contradictory across documents and no H1-over-B2 mechanism paragraph exists",
        "project.v1.json binds a mediation-only pass rule while the viability assessment demands beating a text-lesson baseline; no document states why an owner-valid canonical revision should outperform an information-matched text lesson.",
    ),
    "GAP-5": (
        "No finite v1 done-state in canon",
        "The adaptive strategy and methodology describe an exploration programme without a terminal positive state; the only finite positive is a candidate that requires independent replication before it counts.",
    ),
    "GAP-6": (
        "Burden cap is declared but has no number, date, or check",
        "The viability assessment names a burden cap once; no threshold, window, command, or violation disposition exists, and the same-shaped sprawl recurred within a week of the 2026-08-23 cleanup.",
    ),
    "GAP-7": (
        "Reuse-first comparators B0 and B2 have never produced a result file",
        "The sealed ALFWorld B0 selection is NOT_RUN and the ExpeL B2 adapter has only a parity manifest, so no comparator ceiling exists for a later G1 verdict.",
    ),
}

USER_DECISIONS: dict[str, dict[str, Any]] = {
    "D-1": {
        "name": "D-1 — Split G0 into G0-local and G0-external",
        "proposed_text": (
            "G0를 G0-local과 G0-external로 나눈다. G0-local은 별도 프로세스, "
            "별도 OS 사용자, 별도 키의 evaluator, 사전 커밋된 reveal, "
            "후보 위치 랜덤화, outcome-independent sham으로 통과할 수 있고 "
            "claim ceiling은 MEASUREMENT_READY_SINGLE_OWNER다. OSF, Sigstore, WORM, 9역할 등 "
            "외부 공증은 G0-external로 옮기고, 제2자가 이름과 날짜로 "
            "지정되기 전까지 미개시한다."
        ),
        "affects": "G0 gate contract, docs/research/HSWM_G0_OCCURRENCE_INTEGRITY_PROFILE_2026-09-03.md status line",
    },
    "D-2": {
        "name": "D-2 — Narrow the never-weaken rule to post-outcome contract modification",
        "proposed_text": (
            "AGENTS.md의 'Never weaken a success criterion'은 'outcome을 관측한 뒤 "
            "preregistered contract를 수정하지 않는다'로 한정한다. outcome을 "
            "보기 전의 gate 분할과 요구사항 정리는 약화가 아니다."
        ),
        "affects": "AGENTS.md lines 33-34; RG-4 interpretation",
    },
    "D-3": {
        "name": "D-3 — Bind the G1 estimand",
        "proposed_text": (
            "G1의 binding estimand는 project.v1.json의 pass_rule(fresh-task gain, remove/restore, "
            "sham/shuffled credit, compiled mediation)이다. ExpeL B2와 ALFWorld B0 비교는 "
            "secondary ceiling comparator로 두고, H1이 B2보다 나아야 하는 기전 "
            "문단이 쓰여지기 전까지 primary estimand에 포함하지 않는다."
        ),
        "affects": "G1 pass rule interpretation; docs/research/HSWM_RESEARCH_VIABILITY_AND_POSITIONING_2026-08-30.md line 115 reading",
    },
    "D-4": {
        "name": "D-4 — Define the finite v1 done-state and the numeric burden cap",
        "proposed_text": (
            "v1 완료 상태는 G0-local 아래에서 outcome, credit, 실제 Atom v2 Permit "
            "경로의 durable canonical revision, changed held-out behavior가 remove/restore와 sham "
            "대조와 함께 results/에 체크인된 한 번의 run이다. burden cap은 "
            "4dcba75 이후 100 커밋 중 50% 이상이 core path를 건드리는 것이고 "
            "v3 run-by는 2026-09-15다. 위반 시 F1_R8에 INSTRUMENT_RED 행을 기록하고 "
            "범위를 확대하지 않는다."
        ),
        "affects": "F1_R8_RESULTS_LOG.md rule; RG-6 numbers; second-party recruiting line",
    },
}

SUBGATES: dict[str, dict[str, Any]] = {
    "G0-LOCAL": {
        "name": "G0-local — single-owner measurement integrity",
        "description": "Measurement-integrity sub-gate passable by one researcher: evaluator in a separate process under a separate OS user and key, precommitted reveal, randomized candidate position, outcome-independent sham arm, sealed trajectory before outcome, exact remove/restore, and an all-run manifest.",
        "claim_ceiling": "MEASUREMENT_READY_SINGLE_OWNER",
        "relation": ("NARROWS", "G0_SPLIT_PROPOSAL"),
        "pass_criteria": [
            "evaluator runs in a separate process under a separate OS user with a separate key",
            "reveal commitment is written before any behavior call",
            "candidate position is randomized per episode and stratified in analysis",
            "an outcome-independent sham arm is present",
            "trajectory is sealed before outcome observation",
            "remove returns exact genesis and restore returns exact prior bytes",
            "all runs, including VOID ones, are listed in one manifest",
        ],
    },
    "G0-EXTERNAL": {
        "name": "G0-external — externally witnessed publication gate",
        "description": "The nine-role external notarization chain (custodian, evaluator-B, WORM administrator, external auditor, OSF registration, Sigstore/Rekor, RFC3161 TSA, production Temporal) is deferred to a publication gate that starts only when a second party is named with a date.",
        "claim_ceiling": "DEFERRED_PUBLICATION_GATE",
        "relation": ("DEFERS", "EXTERNAL_NOTARIZATION_DEFERRED_UNTIL_SECOND_PARTY"),
        "pass_criteria": [
            "a second party is named with a start date",
            "the existing hswm-g0-occurrence preflight reports no missing external binding",
            "independent replay by the second party agrees with the local result",
        ],
    },
}

STEPS: dict[str, dict[str, Any]] = {
    "S-1": {
        "name": "S-1 — Ratify D-1, D-2, D-4 and record them as USER_PRIMARY",
        "kind": "RULE_RELAXATION",
        "run_by": "2026-09-08",
        "needs_user": True,
        "needs_dgx": False,
        "deliverables": [
            "docs/canon/sources/USER_PRIMARY_HSWM_CLOSURE_DECISIONS_<date>.txt",
            "AGENTS.md (lines 33-34 narrowed per D-2)",
            "docs/research/HSWM_G0_OCCURRENCE_INTEGRITY_PROFILE_2026-09-03.md (status line gains DEFERRED_PUBLICATION_GATE)",
            "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v2.json (event version: decisions RATIFIED)",
        ],
        "verification": [
            "uv run python scripts/build_hswm_closure_plan_ontology.py --check",
            "uv run pytest -q tests/test_hswm_closure_plan.py",
        ],
        "stop_rule": "If the user rejects D-1, G0-external stays the only G0 and S-3 is not started; record the rejection as a RATIFIED negative decision instead of re-arguing it in new documents.",
        "completion_evidence": "docs/canon/sources/USER_PRIMARY_HSWM_CLOSURE_DECISIONS_*.txt",
        "gaps": ["GAP-1", "GAP-5"],
        "findings": [
            "g0-requires-nine-independent-roles-with-no-plan",
            "target-closed-as-civilizational-horizon-no-done-state",
            "g0-requirement-accretion-and-circular-qualification",
            "monotone-ratchet-no-termination-rule",
        ],
        "decisions": ["D-1", "D-2", "D-4"],
    },
    "S-2": {
        "name": "S-2 — Bridge g1_micro admission to the real local Permit commit",
        "kind": "TECHNICAL_WORK",
        "run_by": "2026-09-10",
        "needs_user": False,
        "needs_dgx": False,
        "deliverables": [
            "src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit-process.ts (stdin envelope, stdout receipt)",
            "src/hswm/experiments/g1_micro.py (_admit_branch calls the subprocess; receipt digest bound into the compile_disposition readset; GPU UUID and image pin moved to protocol fields)",
            "tests/test_hswm_g1_micro.py and src/hswm/effect-runtime/test/*.test.ts additions",
        ],
        "verification": [
            "cd src/hswm/effect-runtime && npm run check && npx vitest run canonical-atom-v2-local-permit-commit",
            "uv run --locked --extra dev pytest -q tests/test_hswm_g1_micro.py",
        ],
        "stop_rule": "Do not add any effect-runtime module that carries no LLM payload through this bridge; if the bridge cannot close in two working days, record the exact blocker on GAP-2 and stop.",
        "completion_evidence": "src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit-process.ts",
        "gaps": ["GAP-2"],
        "findings": [
            "core-loop-starved-by-substrate-engineering",
            "no-bridge-between-llm-instrument-and-atom-v2-permit",
        ],
        "decisions": [],
    },
    "S-3": {
        "name": "S-3 — Preregister and run opaque v3 under G0-local",
        "kind": "TECHNICAL_WORK",
        "run_by": "2026-09-15",
        "needs_user": False,
        "needs_dgx": True,
        "deliverables": [
            "_research/causal_composition/preregistrations/g1_opaque_identifiability_v3_<date>/ (v2 + randomized position + sham arm + separate-process evaluator + S-2 Permit path, n >= 30 episodes)",
            "results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_RESULTS_<date>.md",
            "evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_<date>.json",
            "F1_R8_RESULTS_LOG.md (one row)",
        ],
        "verification": [
            "frozen independent verifier run on the DGX wrapper receipt",
            "uv run --project _research/graph_standards/runtime --locked --extra graph pytest -q tests/test_research_evidence_graph_view.py (v3 public receipt added as an exact source)",
        ],
        "stop_rule": "One occurrence only. A VOID is repaired and rerun within 24 hours under the same protocol family; no new instrument family is opened.",
        "completion_evidence": "results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_RESULTS_*.md",
        "gaps": ["GAP-3"],
        "findings": [
            "loop-degenerates-to-one-bit-copy-register",
            "void-driven-instrument-fanout-without-closure",
        ],
        "decisions": ["D-1"],
    },
    "S-4": {
        "name": "S-4 — Ratify D-3 and fix the G1 estimand",
        "kind": "RULE_RELAXATION",
        "run_by": "2026-09-08",
        "needs_user": True,
        "needs_dgx": False,
        "deliverables": [
            "docs/canon/sources/USER_PRIMARY_HSWM_CLOSURE_DECISIONS_<date>.txt (D-3 sentence)",
            "one mechanism paragraph for H1 over B2 if option B is chosen",
        ],
        "verification": [
            "uv run pytest -q tests/test_hswm_closure_plan.py",
        ],
        "stop_rule": "If no mechanism paragraph can be written, option A (mediation-only pass rule) is the binding estimand; do not build comparator infrastructure before the estimand is bound.",
        "completion_evidence": "docs/canon/sources/USER_PRIMARY_HSWM_CLOSURE_DECISIONS_*.txt",
        "gaps": ["GAP-4"],
        "findings": [
            "hswm-delta-is-governance-not-behavior",
            "loop-degenerates-to-one-bit-copy-register",
            "semantic-weight-has-no-executable-definition",
        ],
        "decisions": ["D-3"],
    },
    "S-5": {
        "name": "S-5 — Produce the first B0 and B2 comparator result files",
        "kind": "TECHNICAL_WORK",
        "run_by": "2026-09-22",
        "needs_user": False,
        "needs_dgx": True,
        "deliverables": [
            "results/HSWM_ALFWORLD_B0_CALIBRATION_RESULTS_<date>.md (sealed selection 68bd43d consumed)",
            "results/HSWM_EXPEL_B2_TEXT_LESSON_RESULTS_<date>.md",
            "F1_R8_RESULTS_LOG.md rows",
        ],
        "verification": [
            "uv run --locked --extra dev pytest -q tests/test_hswm_alfworld_b0_protocol.py tests/test_hswm_expel_b2_prior_pin.py",
        ],
        "stop_rule": "Comparators are secondary ceilings under D-3; a comparator failure does not reopen the G1 estimand.",
        "completion_evidence": "results/HSWM_ALFWORLD_B0_CALIBRATION_RESULTS_*.md",
        "gaps": ["GAP-7"],
        "findings": ["void-driven-instrument-fanout-without-closure"],
        "decisions": ["D-3"],
    },
    "S-6": {
        "name": "S-6 — Enforce the burden cap and settle the second-party question",
        "kind": "RESOURCE",
        "run_by": "2026-09-08",
        "needs_user": True,
        "needs_dgx": False,
        "deliverables": [
            "F1_R8_RESULTS_LOG.md rule paragraph naming the cap and the check command",
            "one line in the closure doc naming a second-party recruiting date or an explicit non-start",
        ],
        "verification": [
            "uv run python scripts/check_hswm_closure_burden_cap.py",
        ],
        "stop_rule": "If the cap is violated, record an INSTRUMENT_RED row in F1_R8_RESULTS_LOG.md and do not expand scope until the next core-path commit.",
        "completion_evidence": "F1_R8_RESULTS_LOG.md",
        "gaps": ["GAP-6"],
        "findings": [
            "core-loop-starved-by-substrate-engineering",
            "monotone-ratchet-no-termination-rule",
            "handoff-projection-ceremony-as-unit-of-work",
            "proof-burst-formalizes-unrun-dnrd5-off-critical-path",
        ],
        "decisions": ["D-4"],
    },
}
STEP_ORDER = ("S-1", "S-2", "S-3", "S-4", "S-5", "S-6")
STEP_PRECEDENCE = (("S-1", "S-3"), ("S-2", "S-3"), ("S-4", "S-5"), ("S-3", "S-5"), ("S-1", "S-6"))

STOP_RULES: dict[str, dict[str, Any]] = {
    "SR-1": {
        "name": "SR-1 — No new document restating G0_NOT_PASSED",
        "description": "No new profile, authority, boundary, or NEXT_SESSION document that restates G0_NOT_PASSED or G1_LOCKED until the v3 result exists; status changes are recorded as event versions of this bundle (ratification, v3 receipt) and in F1_R8_RESULTS_LOG.md.",
        "findings": [
            "g0-requirement-accretion-and-circular-qualification",
            "handoff-projection-ceremony-as-unit-of-work",
        ],
    },
    "SR-2": {
        "name": "SR-2 — No infrastructure for undesignated external operators",
        "description": "No OSF, Sigstore, WORM, or Temporal-serve infrastructure is extended until a second party is named with a date.",
        "findings": [
            "g0-requires-nine-independent-roles-with-no-plan",
            "core-loop-starved-by-substrate-engineering",
        ],
    },
    "SR-3": {
        "name": "SR-3 — Repair and rerun within 24 hours after a VOID",
        "description": "A VOID or inconclusive occurrence is repaired and rerun under the same protocol family within 24 hours; no new instrument family is opened in response to a VOID.",
        "findings": ["void-driven-instrument-fanout-without-closure"],
    },
    "SR-4": {
        "name": "SR-4 — Freeze ontology versions and ICE episodes until the G1 verdict",
        "description": "No new ICE physics episode and no new ontology JSON version, including a graph-and-loop v7, before a G1 verdict; the only exception is an event version of this bundle at ratification or at the v3 receipt.",
        "findings": [
            "core-loop-starved-by-substrate-engineering",
            "handoff-projection-ceremony-as-unit-of-work",
            "proof-burst-formalizes-unrun-dnrd5-off-critical-path",
        ],
    },
    "SR-5": {
        "name": "SR-5 — No exact-byte pins of live files and no dead handoff tests",
        "description": "Live files such as pyproject.toml, design documents, and active TypeScript sources are referenced by path and commit, never by exact-byte hash pin; the ignored handoff test corpus is removed in a separate cleanup commit.",
        "findings": [
            "handoff-projection-ceremony-as-unit-of-work",
            "ts-lean-link-is-caller-asserted-booleans",
        ],
    },
}

BURDEN_CAP: dict[str, Any] = {
    "window_start_commit": AUDITED_COMMIT,
    "window_commits": 100,
    "min_core_share": 0.5,
    "core_path_prefixes": [
        "src/hswm/experiments/g1_micro",
        "src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit",
        "_research/causal_composition/preregistrations/",
        "results/",
        "evidence/",
        "F1_R8_RESULTS_LOG.md",
    ],
    "v3_run_by": "2026-09-15",
    "violation_disposition": "INSTRUMENT_RED_ROW_IN_F1_R8_NO_SCOPE_EXPANSION",
    "check_command": "uv run python scripts/check_hswm_closure_burden_cap.py",
}

DONE_STATE: dict[str, Any] = {
    "statement": "One checked-in run under G0-local in which an independently produced outcome yields credit, the credit admits one owner-valid canonical revision through the real Atom v2 local Permit path, and the revision changes fresh held-out behavior while removal eliminates and byte-identical restoration recovers the effect and the sham arm fails to reproduce it.",
    "claim_ceiling": "LOCAL_CAUSAL_REVISION_UNDER_DECLARED_TASK_CANDIDATE_SINGLE_OWNER",
    "required_artifacts": [
        "_research/causal_composition/preregistrations/g1_opaque_identifiability_v3_*/protocol.v1.json",
        "results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_RESULTS_*.md",
        "evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_*.json",
        "F1_R8_RESULTS_LOG.md row",
    ],
    "not_included": "G0-external notarization, independent replication, FCL-2..8, HSWM-of-HSWMs, consciousness, selfhood, scale closure",
}

SAFE_UID = re.compile(r"sym:[A-Za-z][A-Za-z0-9_]*:[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def _file_sha(path: Path) -> str:
    return sha256((ROOT / path).read_bytes()).hexdigest()


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
        "description": description,
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


def finding_uid(key: str) -> str:
    return f"sym:Concept:hswm-closure-finding-{key}-{TAG}"


def decision_uid(key: str) -> str:
    return f"sym:Concept:hswm-closure-finding-decision-{key}-{TAG}"


def gap_uid(gap_id: str) -> str:
    return f"sym:Hypothesis:hswm-closure-gap-{gap_id.lower()}-{TAG}"


def user_decision_uid(decision_id: str) -> str:
    return f"sym:Concept:hswm-closure-user-decision-{decision_id.lower()}-{TAG}"


def subgate_uid(gate_id: str) -> str:
    return f"sym:Hypothesis:hswm-closure-subgate-{gate_id.lower()}-{TAG}"


def step_uid(step_id: str) -> str:
    return f"sym:Concept:hswm-closure-step-{step_id.lower()}-{TAG}"


def stop_rule_uid(rule_id: str) -> str:
    return f"sym:Concept:hswm-closure-stop-rule-{rule_id.lower()}-{TAG}"


def load_findings() -> list[dict[str, Any]]:
    raw = (ROOT / FINDINGS_PATH).read_bytes()
    document = json.loads(raw.decode("utf-8"))
    findings = document["findings"]
    if [item["key"] for item in findings] != list(FINDING_LINKS):
        raise ValueError("findings JSON key order drifted from FINDING_LINKS")
    return findings


def _revised_severity(finding: dict[str, Any]) -> str:
    severities = [vote["revised_severity"] for vote in finding["votes"]]
    return min(severities, key=lambda item: SEVERITY_ORDER[item])


def _disposition(status: str) -> str:
    return {
        "CONFIRMED": "SUPPORTED_IN_SCOPE",
        "CONTESTED": "UNDERDETERMINED",
        "REFUTED": "RED",
    }[status]


def build_data() -> dict[str, Any]:
    findings = load_findings()
    bindings = [
        {"path": path.as_posix(), "sha256": _file_sha(path)} for path in SOURCE_BINDING_PATHS
    ]
    doc_sha = _file_sha(CLOSURE_DOC_PATH)
    findings_sha = _file_sha(FINDINGS_PATH)
    if RATIFICATION_SOURCE_PATH is None:
        raise ValueError("event version v2 requires the bound ratification source")
    ratification_path = RATIFICATION_SOURCE_PATH.as_posix()
    ratification_sha = _file_sha(RATIFICATION_SOURCE_PATH)

    def is_ratified(decision_id: str) -> bool:
        return decision_id in RATIFIED_DECISIONS

    def decision_status(decision_id: str) -> str:
        return "USER_RATIFIED" if is_ratified(decision_id) else PROPOSED

    def dependency_status(decision_id: str) -> str:
        return "SATISFIED" if is_ratified(decision_id) else "PENDING"

    def prospective_state(decision_id: str) -> str:
        return (
            "USER_RATIFIED_PROSPECTIVE_SCIENTIFICALLY_UNJUDGED"
            if is_ratified(decision_id)
            else PROPOSED
        )

    nodes: list[dict[str, Any]] = []
    relations: list[dict[str, str]] = []
    owned_uids: list[str] = []

    def own(node: dict[str, Any]) -> None:
        nodes.append(node)
        owned_uids.append(node["uid"])

    own(
        _node(
            BUNDLE_UID,
            ["AbstractNode", "ResearchArtifact"],
            {
                **_common(
                    name=f"HSWM closure plan ontology [{TAG}]",
                    description=(
                        "Bounded KG projection of one adversarial programme audit, its "
                        "open closure gaps, four proposed USER_PRIMARY decisions, two "
                        "proposed G0 sub-gates, one finite v1 done-state, six ordered "
                        "closure steps, five stop rules, and one numeric burden cap."
                    ),
                    authority="SYSTEM_DERIVED",
                    scope="BOUNDED_RESEARCH_GOVERNANCE_PROJECTION",
                    kind="ARTIFACT",
                    plane="INQUIRY",
                    state="AUDIT_VERIFIED_PLAN_PROPOSED_USER_PRIMARY_PENDING",
                    owner="closure_plan_projection_custodian",
                    roles=["RESEARCH_BUNDLE", "ADVERSARIAL_AUDIT", "CLOSURE_PLAN", "CLAIM_EVIDENCE_GAP_STATUS"],
                    boundary=(
                        "This projection is research governance infrastructure; it is not "
                        "canonical HSWM state, cognition, learning, permission, a gate pass, "
                        "a user ratification, or a scientific result."
                    ),
                ),
                "audited_commit": AUDITED_COMMIT,
                "event_version_rule": (
                    "A new version of this bundle is produced only at USER_PRIMARY "
                    "ratification and at the v3 result receipt; not for routine status edits."
                ),
                "ratification_source_path": ratification_path,
                "ratification_source_sha256": ratification_sha,
                "ratified_decision_ids": list(RATIFIED_DECISIONS),
                "predecessor_bundle_uid": PREDECESSOR_BUNDLE_UID,
                "v3_receipt_uid": V3_RECEIPT_UID,
                "sr_4_exception": "event version at the v3 result receipt, as the rule itself allows",
            },
        )
    )
    own(
        _node(
            PROGRAM_UID,
            ["Concept", "ResearchProgram", "ResearchArtifact"],
            {
                **_common(
                    name=f"HSWM closure plan [{TAG}]",
                    description=(
                        "Ordered six-step programme whose only goal is one checked-in "
                        "run of outcome to credit to durable canonical revision to "
                        "changed held-out behavior under a single-owner G0-local gate."
                    ),
                    authority="SECONDARY_AI_PROPOSAL_FOR_USER_PRIMARY",
                    scope="CLOSURE_PROGRAMME_NOT_SCIENTIFIC_RESULT",
                    kind="PLAN",
                    plane="INQUIRY",
                    state=PROPOSED,
                    owner="closure_plan_programme_custodian",
                    roles=["RESEARCH_PROGRAM", "CLOSURE_PLAN"],
                    boundary=(
                        "The programme orders work; it does not promise success, pass any "
                        "gate, or reduce the final HSWM target."
                    ),
                ),
                "step_ids": list(STEP_ORDER),
                "gap_ids": list(GAPS),
                "user_decision_ids": list(USER_DECISIONS),
                "stop_rule_ids": list(STOP_RULES),
            },
        )
    )
    own(
        _node(
            AUDIT_RUN_UID,
            ["AbstractNode", "ResearchArtifact"],
            {
                **_common(
                    name=f"Adversarial programme audit run [{TAG}]",
                    description=(
                        "Eight adversarial finder lenses, one merge, two independent "
                        "refuters per finding, one synthesis; 38 AI agents; 24 raw "
                        "findings merged to 14; 11 CONFIRMED, 2 CONTESTED, 1 REFUTED."
                    ),
                    authority="SECONDARY_AI_SELF_ATTESTED_AUDIT",
                    scope="PROGRAMME_CONVERGENCE_AUDIT_AT_ONE_COMMIT",
                    kind="QUALIFICATION_RUN",
                    plane="EVIDENCE",
                    state="SELF_ATTESTED_AI_AUDIT_NOT_INDEPENDENTLY_QUALIFIED",
                    owner="closure_audit_run_custodian",
                    roles=["QUALIFICATION_RUN", "ADVERSARIAL_AUDIT"],
                    boundary=(
                        "The audit qualifies programme-governance claims about one commit; "
                        "it is not evidence about HSWM cognition, learning, or efficacy."
                    ),
                ),
                "executed_on": RELEASE,
                "audited_commit": AUDITED_COMMIT,
                "finder_lenses": list(LENSES),
                "refuter_lenses": list(REFUTERS),
                "raw_findings": 24,
                "merged_findings": len(findings),
                "status_counts": [
                    f"{status}={count}"
                    for status, count in sorted(Counter(item["status"] for item in findings).items())
                ],
                "attestation_level": "SELF_ATTESTED_AI_ONLY",
                "qualification_status": "NOT_INDEPENDENTLY_QUALIFIED",
                "raw_log_status": "FINDINGS_AND_VOTES_PERSISTED_IN_BOUND_JSON",
                "standard_graph_role": "QUALIFICATION_RUN",
            },
        )
    )
    own(
        _node(
            RATIFICATION_SOURCE_UID,
            ["AbstractNode", "SourceDocument", "UserCanonicalUtterance"],
            {
                **_common(
                    name=f"Exact USER_PRIMARY closure-decision source [{TAG}]",
                    description=(
                        "Verbatim user utterance of 2026-09-05 naming D-1 and D-4 as "
                        "ratified, ordering live KG publication and per-step commits; "
                        "D-2 and D-3 are not named and remain PROPOSED."
                    ),
                    authority="USER_PRIMARY",
                    scope="EXACT_USER_SOURCE",
                    kind="ARTIFACT",
                    plane="EVIDENCE",
                    state="SOURCE_BOUND",
                    owner="closure_plan_source_custodian",
                    roles=["EXACT_USER_SOURCE", "LOCAL_SOURCE_RECORD"],
                    boundary=(
                        "The user's words ratify governance decisions; they are not "
                        "scientific evidence, a gate pass, or HSWM efficacy."
                    ),
                ),
                "source_path": ratification_path,
                "source_sha256": ratification_sha,
                "ratified_decision_ids": list(RATIFIED_DECISIONS),
                "standard_graph_role": "EVIDENCE_ARTIFACT",
            },
        )
    )
    for uid, path, sha, name, description in (
        (
            CLOSURE_DOC_UID,
            CLOSURE_DOC_PATH,
            doc_sha,
            "HSWM adversarial audit and closure plan document",
            "Answer-first human record of the audit, gaps, plan, stop rules, burden cap, and the exact decisions requested from the user.",
        ),
        (
            FINDINGS_UID,
            FINDINGS_PATH,
            findings_sha,
            "HSWM adversarial audit findings JSON",
            "Frozen 14-finding record with evidence citations and both refuter votes per finding.",
        ),
    ):
        own(
            _node(
                uid,
                ["AbstractNode", "SourceDocument", "ResearchArtifact"],
                {
                    **_common(
                        name=name,
                        description=description,
                        authority="SECONDARY_AI",
                        scope="LOCAL_SOURCE_BINDING",
                        kind="ARTIFACT",
                        plane="EVIDENCE",
                        state="SOURCE_BOUND",
                        owner="closure_plan_source_custodian",
                        roles=["LOCAL_SOURCE_RECORD"],
                        boundary=(
                            "A source binding proves only the bytes used by this projection, "
                            "not the truth of the source."
                        ),
                    ),
                    "source_path": path.as_posix(),
                    "source_sha256": sha,
                    "standard_graph_role": "EVIDENCE_ARTIFACT",
                },
            )
        )

    for finding in findings:
        key = finding["key"]
        links = FINDING_LINKS[key]
        f_uid = finding_uid(key)
        d_uid = decision_uid(key)
        revised = _revised_severity(finding)
        own(
            _node(
                f_uid,
                ["Concept", "Hypothesis"],
                {
                    **_common(
                        name=f"{finding['title']} [{TAG}]",
                        description=_clip(finding["claim"]),
                        authority="SECONDARY_AI_AUDIT_CLAIM",
                        scope=f"PROGRAMME_STATE_AT_{AUDITED_COMMIT[:7]}",
                        kind="CLAIM",
                        plane="EVIDENCE",
                        state=finding["status"],
                        owner="closure_audit_claim_custodian",
                        roles=["AUDIT_FINDING", "CONVERGENCE_BLOCKER_CLAIM"],
                        boundary=(
                            "An audit finding describes why the programme was not converging "
                            "at one commit; it is not a scientific result about HSWM."
                        ),
                    ),
                    "finding_key": key,
                    "severity_reported": finding["severity"],
                    "severity_revised": revised,
                    "verification_status": finding["status"],
                    "source_lenses": list(finding["source_lenses"]),
                    "why_it_blocks_completion": _clip(finding["why_it_blocks_completion"]),
                    "suggested_fix": _clip(finding["suggested_fix"]),
                    "evidence_refs": [
                        _clip(item, 300) for item in finding["evidence"][:MAX_EVIDENCE_REFS]
                    ],
                    "evidence_ref_count": len(finding["evidence"]),
                    "cited_at_commit": AUDITED_COMMIT,
                    "gap_ids": list(links["gaps"]),
                    "blocked_gate_ids": list(links["blocks"]),
                    "assessed_proof_claim_ids": list(links["assesses"]),
                    "current_decision_uid": d_uid,
                    "standard_graph_role": "CLAIM",
                },
            )
        )
        own(
            _node(
                d_uid,
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"Verification decision for {key} [{TAG}]",
                        description=_clip(
                            "; ".join(
                                f"{vote['refuter']}: refuted={str(vote['refuted']).lower()} "
                                f"({vote['confidence']}, revised {vote['revised_severity']})"
                                for vote in finding["votes"]
                            )
                        ),
                        authority="SECONDARY_AI_AUDIT_DECISION",
                        scope=f"STATUS_AS_OF_{RELEASE.replace('-', '_')}",
                        kind="DECISION",
                        plane="EVIDENCE",
                        state=finding["status"],
                        owner="closure_audit_decision_custodian",
                        roles=["STATUS_DECISION", "ADVERSARIAL_VERIFICATION"],
                        boundary=(
                            "Two AI refuters attacked the finding; the decision is a "
                            "self-attested verification, not independent qualification."
                        ),
                    ),
                    "finding_key": key,
                    "assesses_claim_uid": f_uid,
                    "verification_status": finding["status"],
                    "evidence_disposition": _disposition(finding["status"]),
                    "implementation_status": "NOT_APPLICABLE",
                    "claim_ceiling": AUDIT_CEILING,
                    "severity_revised": revised,
                    "refuter_votes": [
                        f"{vote['refuter']}|refuted={str(vote['refuted']).lower()}|{vote['confidence']}|{vote['revised_severity']}"
                        for vote in finding["votes"]
                    ],
                    "what_would_change_my_mind": [
                        _clip(vote["what_would_change_my_mind"], 400) for vote in finding["votes"]
                    ],
                    "decision_relation_semantics": "CURRENT_STATUS_DECISION",
                    "standard_graph_role": "DECISION",
                },
            )
        )
        relations.append(_relation(f_uid, "HAS_SOURCE", FINDINGS_UID, "SOURCE_PROVENANCE", "BOUND", "SYSTEM_DERIVED"))
        relations.append(_relation(f_uid, "HAS_SOURCE", CLOSURE_DOC_UID, "SOURCE_PROVENANCE", "BOUND", "SYSTEM_DERIVED"))
        relations.append(_relation(f_uid, "HAS_CONCEPT", d_uid, "CURRENT_STATUS_DECISION", "ACTIVE"))
        relations.append(_relation(d_uid, "CONSTRAINS", f_uid, "AUDIT_CLAIM_CEILING", "ACTIVE"))
        relations.append(_relation(AUDIT_RUN_UID, "TESTS", f_uid, "ADVERSARIAL_VERIFICATION", "SELF_ATTESTED"))
        for gap_id in links["gaps"]:
            relations.append(_relation(f_uid, "TARGETS", gap_uid(gap_id), "CLOSURE_GAP", "OPEN"))
        if finding["status"] != "REFUTED":
            for gate_id in links["blocks"]:
                relations.append(_relation(f_uid, "BLOCKS", GATE_UIDS[gate_id], "GATE_BLOCKER_OBSERVED", "ACTIVE"))
            for claim_id in links["assesses"]:
                relations.append(_relation(f_uid, "ASSESSES", PROOF_CLAIM_UIDS[claim_id], "PROOF_STATUS_CROSS_REFERENCE", "ACTIVE"))

    for gap_id, (name, description) in GAPS.items():
        own(
            _node(
                gap_uid(gap_id),
                ["Concept", "Hypothesis"],
                {
                    **_common(
                        name=f"{gap_id} — {name} [{TAG}]",
                        description=description,
                        authority="SECONDARY_AI",
                        scope="OPEN_CLOSURE_GAP",
                        kind="GAP",
                        plane="INQUIRY",
                        state="OPEN",
                        owner="closure_gap_custodian",
                        roles=["CLOSURE_GAP"],
                        boundary="An open gap names missing work; closing it is not a scientific result.",
                    ),
                    "gap_id": gap_id,
                    "standard_graph_role": "GAP",
                },
            )
        )
        relations.append(_relation(PROGRAM_UID, "TARGETS", gap_uid(gap_id), "GAP_CLOSURE", "PLANNED"))

    for decision_id, spec in USER_DECISIONS.items():
        own(
            _node(
                user_decision_uid(decision_id),
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"{spec['name']} [{TAG}]",
                        description=spec["proposed_text"],
                        authority="USER_PRIMARY" if is_ratified(decision_id) else "SECONDARY_AI_PROPOSAL_FOR_USER_PRIMARY",
                        scope="USER_PRIMARY_DECISION" if is_ratified(decision_id) else "USER_PRIMARY_DECISION_REQUEST",
                        kind="DECISION",
                        plane="MODEL",
                        state="USER_RATIFIED_DIRECTION_SCIENTIFICALLY_UNJUDGED" if is_ratified(decision_id) else PROPOSED,
                        owner="hswm_target_direction_custodian",
                        roles=["USER_PRIMARY_DECISION", "CLOSURE_PLAN"],
                        boundary=(
                            "Until the user's own words are hash-bound, this node is a proposal; "
                            "ratification, modification, or rejection is the user's alone."
                        ),
                    ),
                    "decision_id": decision_id,
                    "proposed_text": spec["proposed_text"],
                    "affects": spec["affects"],
                    "options": ["RATIFY", "MODIFY", "REJECT"],
                    "ratification_status": "RATIFIED" if is_ratified(decision_id) else "PROPOSED",
                    "ratification_source_path": ratification_path if is_ratified(decision_id) else "",
                    "ratification_source_sha256": ratification_sha if is_ratified(decision_id) else "",
                    "ratified_on": RATIFIED_ON if is_ratified(decision_id) else "",
                    "plan_graph_role": "USER_PRIMARY_DECISION",
                },
            )
        )
        if is_ratified(decision_id):
            relations.append(_relation(user_decision_uid(decision_id), "HAS_SOURCE", RATIFICATION_SOURCE_UID, "USER_RATIFICATION", "BOUND", "USER_PRIMARY"))

    for gate_id, spec in SUBGATES.items():
        relation_type, relation_scope = spec["relation"]
        own(
            _node(
                subgate_uid(gate_id),
                ["Concept", "Hypothesis", "Guardrail"],
                {
                    **_common(
                        name=f"{spec['name']} [{TAG}]",
                        description=spec["description"],
                        authority="SECONDARY_AI_PROPOSAL_FOR_USER_PRIMARY",
                        scope="PROSPECTIVE_G0_SUBGATE",
                        kind="GATE",
                        plane="INQUIRY",
                        state=prospective_state("D-1"),
                        owner="closure_subgate_custodian",
                        roles=["PROSPECTIVE_GATE", "G0_SPLIT"],
                        boundary="A sub-gate is a measurement-validity prerequisite, not an efficacy result.",
                    ),
                    "subgate_id": gate_id,
                    "claim_ceiling": spec["claim_ceiling"],
                    "pass_criteria": list(spec["pass_criteria"]),
                    "plan_graph_role": "PROSPECTIVE_SUBGATE",
                },
            )
        )
        relations.append(_relation(subgate_uid(gate_id), relation_type, G0_UID, relation_scope, decision_status("D-1")))
        relations.append(_relation(subgate_uid(gate_id), "DEPENDS_ON", user_decision_uid("D-1"), "RATIFICATION_PREREQUISITE", dependency_status("D-1")))
        relations.append(_relation(user_decision_uid("D-1"), "PROPOSES", subgate_uid(gate_id), "G0_SPLIT", decision_status("D-1")))
        relations.append(_relation(PROGRAM_UID, "TESTS", subgate_uid(gate_id), "PROSPECTIVE_SUBGATE", decision_status("D-1")))

    own(
        _node(
            DONE_STATE_UID,
            ["Concept", "Guardrail"],
            {
                **_common(
                    name=f"HSWM v1 done-state [{TAG}]",
                    description=DONE_STATE["statement"],
                    authority="SECONDARY_AI_PROPOSAL_FOR_USER_PRIMARY",
                    scope="FINITE_V1_TERMINAL_STATE",
                    kind="MILESTONE",
                    plane="INQUIRY",
                    state=prospective_state("D-4"),
                    owner="closure_done_state_custodian",
                    roles=["DONE_STATE", "CLOSURE_PLAN"],
                    boundary="Reaching the done-state yields a candidate claim under one declared task; it is not integrated HSWM or fractal evidence.",
                ),
                "claim_ceiling": DONE_STATE["claim_ceiling"],
                "required_artifacts": list(DONE_STATE["required_artifacts"]),
                "not_included": DONE_STATE["not_included"],
                "plan_graph_role": "DONE_STATE",
            },
        )
    )
    relations.append(_relation(user_decision_uid("D-4"), "PROPOSES", DONE_STATE_UID, "DONE_STATE", decision_status("D-4")))
    relations.append(_relation(PROGRAM_UID, "TARGETS", DONE_STATE_UID, "V1_DONE_STATE", decision_status("D-4")))

    for index, step_id in enumerate(STEP_ORDER, start=1):
        spec = STEPS[step_id]
        s_uid = step_uid(step_id)
        own(
            _node(
                s_uid,
                ["Concept"],
                {
                    **_common(
                        name=f"{spec['name']} [{TAG}]",
                        description=_clip("; ".join(spec["deliverables"])),
                        authority="SECONDARY_AI_PROPOSAL_FOR_USER_PRIMARY",
                        scope="ORDERED_CLOSURE_STEP",
                        kind="TASK",
                        plane="INQUIRY",
                        state="COMPLETED" if step_id in COMPLETED_STEPS else "PLANNED",
                        owner="closure_step_custodian",
                        roles=["CLOSURE_STEP", spec["kind"]],
                        boundary="A step orders work; completing it is evidenced only by the named checked-in artifact.",
                    ),
                    "step_id": step_id,
                    "step_order": index,
                    "step_kind": spec["kind"],
                    "run_by": spec["run_by"],
                    "needs_user": spec["needs_user"],
                    "needs_dgx": spec["needs_dgx"],
                    "deliverable_paths": list(spec["deliverables"]),
                    "verification_commands": list(spec["verification"]),
                    "stop_rule": spec["stop_rule"],
                    "completion_evidence_path_pattern": spec["completion_evidence"],
                    "closure_status": (
                        "COMPLETED" if step_id in COMPLETED_STEPS
                        else "IN_PROGRESS" if step_id in {"S-1", "S-6"} else "PLANNED"
                    ),
                    **({
                        "completed_on": COMPLETED_STEPS[step_id]["completed_on"],
                        "completion_commit": COMPLETED_STEPS[step_id]["commit"],
                        "completion_outcome": COMPLETED_STEPS[step_id]["outcome"],
                    } if step_id in COMPLETED_STEPS else {}),
                    "plan_graph_role": "CLOSURE_STEP",
                },
            )
        )
        for gap_id in spec["gaps"]:
            relations.append(_relation(s_uid, "CLOSES", gap_uid(gap_id), "GAP_CLOSURE", "CLOSED" if step_id in COMPLETED_STEPS else "PLANNED"))
        for key in spec["findings"]:
            relations.append(_relation(s_uid, "ADDRESSES", finding_uid(key), "FINDING_RESPONSE", "PLANNED"))
        for decision_id in spec["decisions"]:
            relations.append(_relation(s_uid, "DEPENDS_ON", user_decision_uid(decision_id), "RATIFICATION_PREREQUISITE", dependency_status(decision_id)))
    for before, after in STEP_PRECEDENCE:
        relations.append(_relation(step_uid(before), "PRECEDES", step_uid(after), "CLOSURE_ORDER", "SATISFIED" if before in COMPLETED_STEPS else "PLANNED"))
    relations.append(_relation(step_uid("S-3"), "TARGETS", DONE_STATE_UID, "DONE_STATE_ATTEMPT", "ATTEMPTED_NOT_REACHED"))
    relations.append(_relation(step_uid("S-3"), "TESTS", subgate_uid("G0-LOCAL"), "PROSPECTIVE_SUBGATE", "TESTED_RULE_NOT_MET"))

    # Event version v3: the opaque v3 receipt and its three bound sources.
    for uid, path, name, description in (
        (V3_RESULTS_UID, V3_RESULTS_PATH, "HSWM opaque v3 (G0-local) result document", "Human record of the 2026-09-06 occurrence: sealed terminal, per-arm counts by position stratum, the failing rule clause, the VOID attempt, and the custody ceiling."),
        (V3_EVIDENCE_UID, V3_EVIDENCE_PATH, "HSWM opaque v3 evidence record", "Content-addressed evidence projection binding the frozen protocol, one-shot registry, DGX runtime receipts, and the public artifacts."),
        (V3_PROTOCOL_UID, V3_PROTOCOL_PATH, "HSWM opaque v3 frozen protocol (2026-09-06-r2)", "Frozen preregistration generated on the run host from the evaluator's seed with equal-token-count code selection and a measured tokenizer binding."),
    ):
        own(
            _node(
                uid,
                ["AbstractNode", "SourceDocument", "ResearchArtifact"],
                {
                    **_common(
                        name=f"{name} [{TAG}]",
                        description=description,
                        authority="SYSTEM_DERIVED",
                        scope="BOUND_SOURCE_RECORD",
                        kind="ARTIFACT",
                        plane="EVIDENCE",
                        state="SOURCE_BOUND",
                        owner="closure_plan_source_custodian",
                        roles=["EVIDENCE_ARTIFACT", "LOCAL_SOURCE_RECORD"],
                        boundary="A bound source proves what bytes existed at the bound digest; it is not a gate pass or efficacy evidence.",
                    ),
                    "source_path": path.as_posix(),
                    "source_sha256": _file_sha(path),
                    "standard_graph_role": "EVIDENCE_ARTIFACT",
                },
            )
        )
    own(
        _node(
            V3_RECEIPT_UID,
            ["AbstractNode", "ResearchArtifact"],
            {
                **_common(
                    name=f"Opaque v3 (G0-local) occurrence receipt 2026-09-06 [{TAG}]",
                    description=(
                        "One frozen 32-episode occurrence on the DGX with a separate-OS-user evaluator, balanced positions, an "
                        "outcome-independent sham arm, and 96 Atom v2 local Permit commits: ACTIVE 32/32, RESTORE 32/32, "
                        "FORCED_OPPOSITE 0/32, SHAM 20/32, NO_UPDATE 16/32, REMOVE 16/32, delta_state 0.594.  The no-state arms "
                        "were 16/16 in the position-1 stratum against a frozen ceiling of 12, so the sealed terminal is "
                        "NO_SEPARATION.  The first attempt of the day aborted after the seal on an instrument defect and was "
                        "rerun within 24 hours under SR-3."
                    ),
                    authority="SECONDARY_AI_SELF_ATTESTED_LOCAL_OCCURRENCE",
                    scope="ONE_SEALED_DGX_OCCURRENCE_WITH_CHECKED_IN_REPLAY",
                    kind="QUALIFICATION_RUN",
                    plane="EVIDENCE",
                    state="SEALED_RULE_NOT_MET_INSTRUMENT_VALIDATION_ONLY",
                    owner="closure_v3_receipt_custodian",
                    roles=["QUALIFICATION_RUN", "CLOSURE_STEP_RECEIPT"],
                    boundary=(
                        "The receipt records a run and its sealed terminal; it is not a G0-local pass, not G0-external, not a G1 "
                        "result, not canonical HSWM admission, and not efficacy evidence."
                    ),
                ),
                "standard_graph_role": "QUALIFICATION_RUN",
                "attestation_level": "SELF_ATTESTED_LOCAL_DGX_OCCURRENCE_WITH_CHECKED_IN_REPLAY",
                "qualification_status": V3_TERMINAL,
                "study_uid": V3_STUDY_UID,
                "protocol_canonical_sha256": V3_PROTOCOL_CANONICAL_SHA256,
                "bundle_sha256": V3_BUNDLE_SHA256,
                "branch_correct": ["ACTIVE=32", "RESTORE=32", "FORCED_OPPOSITE_FEEDBACK=0", "OUTCOME_INDEPENDENT_SHAM=20", "NO_UPDATE=16", "REMOVE=16"],
                "no_state_correct_by_position": ["NO_UPDATE=16/16,0/16", "REMOVE=16/16,0/16", "OUTCOME_INDEPENDENT_SHAM=11/16,9/16"],
                "delta_state": 0.59375,
                "failing_rule_clause": "no_state_arm_per_position_stratum_correct_max=12",
                "atom_v2_permit_commits": 96,
                "exact_remove_and_restore": 32,
                "evaluator_feedback_verified": 32,
                "evaluator_separate_os_user_episodes": 32,
                "claim_ceiling": "INSTRUMENT_VALIDATION_ONLY",
                "aborted_attempt_protocol_canonical_sha256": V3_ABORTED_PROTOCOL_CANONICAL_SHA256,
                "aborted_attempt_terminal": "INCONCLUSIVE_MEASUREMENT_NOT_READY",
                "custody_ceiling": "OS_USER_SEPARATION_NOT_PRIVILEGE_SEPARATION",
                "closure_step_id": "S-3",
            },
        )
    )
    for source_uid in (V3_RESULTS_UID, V3_EVIDENCE_UID, V3_PROTOCOL_UID):
        relations.append(_relation(V3_RECEIPT_UID, "HAS_SOURCE", source_uid, "SOURCE_PROVENANCE", "BOUND", "SYSTEM_DERIVED"))
    relations.append(_relation(V3_RECEIPT_UID, "TESTS", subgate_uid("G0-LOCAL"), "G0_LOCAL_CRITERIA_MECHANICALLY_PRESENT", "TESTED_RULE_NOT_MET"))
    relations.append(_relation(V3_RECEIPT_UID, "TARGETS", step_uid("S-3"), "STEP_COMPLETION_EVIDENCE", "COMPLETED"))
    relations.append(_relation(V3_RECEIPT_UID, "DEPENDS_ON", step_uid("S-2"), "PERMIT_BRIDGE_USED", "SATISFIED"))
    relations.append(_relation(V3_RECEIPT_UID, "DEPENDS_ON", EFFECT_FP_BUNDLE_UID, "PERMIT_PROCESS_FROM_REFACTORED_RUNTIME", "ACTIVE"))
    relations.append(_relation(V3_RECEIPT_UID, "ADDRESSES", finding_uid("no-bridge-between-llm-instrument-and-atom-v2-permit"), "BRIDGE_EXERCISED_96_COMMITS", "ADDRESSED"))
    relations.append(_relation(V3_RECEIPT_UID, "ADDRESSES", finding_uid("void-driven-instrument-fanout-without-closure"), "VOID_REPAIRED_AND_RERUN_SAME_FAMILY_SR3", "ADDRESSED"))
    relations.append(_relation(V3_RECEIPT_UID, "PRESERVES", G0_UID, "G0_NOT_PASSED", "ACTIVE"))

    for rule_id, spec in STOP_RULES.items():
        r_uid = stop_rule_uid(rule_id)
        own(
            _node(
                r_uid,
                ["Concept", "Guardrail"],
                {
                    **_common(
                        name=f"{spec['name']} [{TAG}]",
                        description=spec["description"],
                        authority="SECONDARY_AI_PROPOSAL_FOR_USER_PRIMARY",
                        scope="CLOSURE_DISCIPLINE",
                        kind="GUARDRAIL",
                        plane="MODEL",
                        state=PROPOSED,
                        owner="closure_stop_rule_custodian",
                        roles=["STOP_RULE", "CLOSURE_PLAN"],
                        boundary="A stop rule bounds work; it does not weaken any preregistered success criterion.",
                    ),
                    "stop_rule_id": rule_id,
                    "self_exemption": (
                        "This bundle's event versions at ratification and at the v3 receipt"
                        if rule_id in {"SR-1", "SR-4"}
                        else ""
                    ),
                    "plan_graph_role": "STOP_RULE",
                },
            )
        )
        relations.append(_relation(r_uid, "CONSTRAINS", PROGRAM_UID, "CLOSURE_DISCIPLINE", PROPOSED))
        for key in spec["findings"]:
            relations.append(_relation(r_uid, "MITIGATES", finding_uid(key), "SPRAWL_MITIGATION", "PROPOSED"))
    relations.append(_relation(stop_rule_uid("SR-4"), "CONSTRAINS", GRAPH_LOOP_PROGRAM_UID, "VERSION_FREEZE_UNTIL_G1_VERDICT", PROPOSED))

    own(
        _node(
            BURDEN_CAP_UID,
            ["Concept", "Guardrail"],
            {
                **_common(
                    name=f"HSWM closure burden cap [{TAG}]",
                    description=(
                        "At least half of the next one hundred commits after the audited "
                        "commit must touch a core closure path; the v3 occurrence must run "
                        "by the stated date; violation is recorded as INSTRUMENT_RED without "
                        "scope expansion."
                    ),
                    authority="SECONDARY_AI_PROPOSAL_FOR_USER_PRIMARY",
                    scope="NUMERIC_BURDEN_DISCIPLINE",
                    kind="GUARDRAIL",
                    plane="MODEL",
                    state=prospective_state("D-4"),
                    owner="closure_burden_cap_custodian",
                    roles=["BURDEN_CAP", "CLOSURE_PLAN"],
                    boundary="The cap bounds effort allocation; it is not a research result and does not lower any success criterion.",
                ),
                **BURDEN_CAP,
                **BURDEN_READING,
                "plan_graph_role": "BURDEN_CAP",
            },
        )
    )
    relations.append(_relation(BURDEN_CAP_UID, "CONSTRAINS", PROGRAM_UID, "BURDEN_DISCIPLINE", decision_status("D-4")))
    relations.append(_relation(BURDEN_CAP_UID, "DEPENDS_ON", user_decision_uid("D-4"), "RATIFICATION_PREREQUISITE", dependency_status("D-4")))
    relations.append(_relation(user_decision_uid("D-4"), "PROPOSES", BURDEN_CAP_UID, "BURDEN_CAP", decision_status("D-4")))
    relations.append(_relation(user_decision_uid("D-4"), "NARROWS", RG6_UID, "BURDEN_DISCIPLINE_NUMBERS", decision_status("D-4")))
    relations.append(_relation(user_decision_uid("D-2"), "NARROWS", RG4_UID, "NEVER_WEAKEN_NARROWING_PROPOSAL", decision_status("D-2")))
    relations.append(_relation(user_decision_uid("D-3"), "CONSTRAINS", G1_UID, "ESTIMAND_BINDING_PROPOSAL", decision_status("D-3")))
    relations.append(_relation(BUNDLE_UID, "SUPERSEDES_AS_FOLLOWUP", PREDECESSOR_BUNDLE_UID, "NON_OVERWRITING_STATUS_FOLLOWUP_WITHOUT_SCIENTIFIC_PROMOTION", "ACTIVE", "SYSTEM_DERIVED"))
    relations.append(_relation(PROGRAM_UID, "SUPERSEDES_AS_FOLLOWUP", PREDECESSOR_PROGRAM_UID, "NON_OVERWRITING_STATUS_FOLLOWUP_WITHOUT_SCIENTIFIC_PROMOTION", "ACTIVE"))

    for uid in owned_uids:
        if uid == BUNDLE_UID:
            continue
        if uid in {CLOSURE_DOC_UID, FINDINGS_UID, RATIFICATION_SOURCE_UID, V3_RESULTS_UID, V3_EVIDENCE_UID, V3_PROTOCOL_UID}:
            relations.append(_relation(BUNDLE_UID, "HAS_SOURCE", uid, "SOURCE_PROVENANCE", "BOUND", "SYSTEM_DERIVED"))
        else:
            relations.append(_relation(BUNDLE_UID, "HAS_CONCEPT", uid, "BOUNDED_PROJECTION_MEMBERSHIP", "ACTIVE", "SYSTEM_DERIVED"))
    relations.append(_relation(AUDIT_RUN_UID, "HAS_SOURCE", FINDINGS_UID, "SOURCE_PROVENANCE", "BOUND", "SYSTEM_DERIVED"))
    relations.append(_relation(BUNDLE_UID, "DOES_NOT_ENFORCE", HSWM_UID, "KG_PROJECTION_BOUNDARY", "ACTIVE", "SYSTEM_DERIVED"))
    relations.append(_relation(BUNDLE_UID, "AUDITS", CAUSAL_PROGRAM_UID, "ADVERSARIAL_PROGRAMME_AUDIT", "SELF_ATTESTED"))
    relations.append(_relation(PROGRAM_UID, "PRESERVES", CAUSAL_PROGRAM_UID, "EXISTING_G0_TO_G6_ORDER", "ACTIVE"))
    relations.append(_relation(PROGRAM_UID, "PRESERVES", ADAPTIVE_BUNDLE_UID, "TARGET_PERSISTENCE_AND_METHOD_ADAPTATION", "ACTIVE"))

    relations.sort(key=lambda row: (row["from_uid"], row["type"], row["to_uid"]))
    data = {
        "schema_version": SCHEMA_VERSION,
        "bundle_uid": BUNDLE_UID,
        "status": STATUS,
        "nonclaim": NONCLAIM,
        "authority_boundary": (
            "The audit findings, gaps, plan, stop rules, and burden cap are SECONDARY_AI "
            "formalizations. D-1 and D-4 are USER_PRIMARY because the user's own words are "
            "hash-bound as a canon source; D-2 and D-3 remain PROPOSED until named. S-2 and S-3 "
            "are COMPLETED as runs: the opaque v3 receipt of 2026-09-06 is sealed NO_SEPARATION "
            "under its frozen rule. Nothing here passes G0 or G1 or promotes any scientific claim."
        ),
        "source_accessed_on": RELEASE,
        "artifact_bindings": bindings,
        "expected_counts": {
            "nodes": len(nodes),
            "anchors": len(ANCHORS),
            "relations": len(relations),
            "findings": len(findings),
            "finding_decisions": len(findings),
            "gaps": len(GAPS),
            "user_primary_decisions": len(USER_DECISIONS),
            "g0_subgates": len(SUBGATES),
            "closure_steps": len(STEPS),
            "stop_rules": len(STOP_RULES),
            "burden_caps": 1,
            "done_states": 1,
            "audit_runs": 1,
            "source_records": len(bindings),
            "ratified_decisions": len(RATIFIED_DECISIONS),
            "completed_steps": len(COMPLETED_STEPS),
            "v3_receipts": 1,
        },
        "anchors": ANCHORS,
        "nodes": nodes,
        "relations": relations,
    }
    validate_data(data)
    return data


def validate_data(data: dict[str, Any]) -> None:
    """Fail closed on graph-shape, identity, or property-type drift."""

    expected_keys = {
        "schema_version", "bundle_uid", "status", "nonclaim", "authority_boundary",
        "source_accessed_on", "artifact_bindings", "expected_counts", "anchors", "nodes", "relations",
    }
    if set(data) != expected_keys:
        raise ValueError("closure-plan ontology top-level shape drifted")
    if data["schema_version"] != SCHEMA_VERSION or data["bundle_uid"] != BUNDLE_UID:
        raise ValueError("closure-plan ontology identity drifted")
    if data["status"] != STATUS or data["nonclaim"] != NONCLAIM:
        raise ValueError("closure-plan status or nonclaim drifted")
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
        if role == "DECISION" and not properties.get("assesses_claim_uid"):
            raise ValueError(f"decision without claim: {row['uid']}")
        if properties.get("plan_graph_role") == "CLOSURE_STEP":
            for key in ("run_by", "stop_rule", "verification_commands", "step_order", "completion_evidence_path_pattern"):
                if not properties.get(key):
                    raise ValueError(f"closure step missing {key}: {row['uid']}")
        if properties.get("plan_graph_role") == "USER_PRIMARY_DECISION":
            if properties["ratification_status"] not in {"PROPOSED", "RATIFIED", "MODIFIED", "REJECTED"}:
                raise ValueError(f"invalid ratification status: {row['uid']}")
            if properties["ratification_status"] != "PROPOSED" and not properties["ratification_source_sha256"]:
                raise ValueError(f"ratified decision without bound source: {row['uid']}")
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
    plan_roles = Counter(row["properties"].get("plan_graph_role") for row in nodes)
    if roles["CLAIM"] != counts["findings"] or roles["DECISION"] != counts["finding_decisions"]:
        raise ValueError("finding or decision counts drifted")
    if roles["GAP"] != counts["gaps"] or plan_roles["CLOSURE_STEP"] != counts["closure_steps"]:
        raise ValueError("gap or step counts drifted")
    if plan_roles["USER_PRIMARY_DECISION"] != counts["user_primary_decisions"]:
        raise ValueError("user decision counts drifted")
    if plan_roles["STOP_RULE"] != counts["stop_rules"] or plan_roles["PROSPECTIVE_SUBGATE"] != counts["g0_subgates"]:
        raise ValueError("stop rule or subgate counts drifted")
    ratified = [
        row for row in nodes
        if row["properties"].get("plan_graph_role") == "USER_PRIMARY_DECISION"
        and row["properties"]["ratification_status"] == "RATIFIED"
    ]
    if len(ratified) != counts["ratified_decisions"]:
        raise ValueError("ratified decision counts drifted")


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
            raise SystemExit("closure-plan ontology projection drifted")
        print(json.dumps({"status": "MATCH", "path": str(args.output)}, sort_keys=True))
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(json.dumps({"status": "BUILT", "path": str(args.output), "sha256": sha256(payload).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
