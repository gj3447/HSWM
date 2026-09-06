#!/usr/bin/env python3
"""Build the HSWM session ledger KG projection for 2026-09-06 (event version v1).

The ledger is a bounded, deterministic record of one working session: every
commit in the closure burden window as of the ledger head, grouped into work
streams, joined to the closure-plan steps, receipts, decisions and cap it
touched, together with the open items, the burden reading, the verification
readings and the working-tree observations taken at the ledger head.  It is an
effort ledger and an orientation aid.  It is not a research result, not a gate
pass, not a user ratification, and it promotes no scientific claim.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RELEASE = "2026-09-06"
TAG = "2026-09-06-v1"
SCHEMA_VERSION = "hswm-session-ledger/v1"
BUNDLE_UID = f"sym:AbstractNode:hswm-session-ledger-{TAG}"
ONTOLOGY_PATH = "ontology/identity/hswm_core/HSWM_SESSION_LEDGER_2026-09-06.v1.json"
CLOSURE_TAG = "2026-09-05-v5"
CLOSURE_BUNDLE_UID = f"sym:AbstractNode:hswm-closure-plan-ontology-{CLOSURE_TAG}"
CLOSURE_PROGRAM_UID = f"sym:ResearchProgram:hswm-closure-plan-{CLOSURE_TAG}"
EFFECT_FP_BUNDLE_UID = "sym:AbstractNode:hswm-effect-fp-boundary-ontology-2026-09-06"
WINDOW_START_COMMIT = "4dcba752a661de23066b3b33381bfdfc34879a57"
LEDGER_HEAD_COMMIT = "244bf4f"
STATUS = "SESSION_LEDGER_2026-09-06_48_COMMITS_23_CORE_BELOW_SHARE_S2_S3_S4_COMPLETE_S1_S5_S6_OPEN_G0_NOT_PASSED_G1_LOCKED"
NONCLAIM = (
    "SESSION_EFFORT_LEDGER_KG_PROJECTION_ONLY_NOT_HSWM_COGNITION_LEARNING_EFFICACY_GATE_PASS_"
    "USER_RATIFICATION_OR_SCIENTIFIC_RESULT"
)
MAX_TEXT = 900

SOURCE_BINDING_PATHS = (
    ROOT / "results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_RESULTS_2026-09-06.md",
    ROOT / "results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V4_RESULTS_2026-09-06.md",
    ROOT / "results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V5_RESULTS_2026-09-06.md",
    ROOT / "evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V3_2026-09-06.json",
    ROOT / "evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V4_2026-09-06.json",
    ROOT / "evidence/EVIDENCE_HSWM_G1_OPAQUE_IDENTIFIABILITY_V5_2026-09-06.json",
    ROOT / "docs/canon/sources/USER_PRIMARY_HSWM_CLOSURE_DECISIONS_2026-09-06.txt",
    ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v5.json",
    ROOT / "ontology/identity/hswm_core/HSWM_EFFECT_RUNTIME_FP_BOUNDARY_ONTOLOGY.v1.json",
    ROOT / "docs/operations/HSWM_EFFECT_RUNTIME_FUNCTIONAL_BOUNDARY_2026-09-06.md",
)

CORE_PATH_PREFIXES = (
    "src/hswm/experiments/g1_micro",
    "src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit",
    "_research/causal_composition/preregistrations/",
    "results/",
    "evidence/",
    "F1_R8_RESULTS_LOG.md",
)

COMMITS: tuple[dict[str, Any], ...] = (
    {"position": 1, "short": "95eca6f", "sha": "95eca6fed10ec5b847a88b92e98fd2781d933189", "authored_at": "2026-09-05T14:07:01Z", "subject": "research: record adversarial audit and closure plan KG projection", "files_changed": 15, "core": False, "stream": "audit_and_plan"},
    {"position": 2, "short": "e677cb2", "sha": "e677cb25ab6c45a48a00cb94d8b37ef830f63647", "authored_at": "2026-09-05T14:13:11Z", "subject": "canon: ratify D-1 and D-4 and publish closure plan v2", "files_changed": 10, "core": False, "stream": "audit_and_plan"},
    {"position": 3, "short": "0463f6c", "sha": "0463f6c058ed2bae37efd0f22f6a9f569fa7fac3", "authored_at": "2026-09-05T15:24:25Z", "subject": "research: enforce the ratified closure burden cap", "files_changed": 2, "core": True, "stream": "audit_and_plan"},
    {"position": 4, "short": "51f631b", "sha": "51f631b4e15bdd3ca48219c8df66bd3fa165ccb8", "authored_at": "2026-09-05T15:38:53Z", "subject": "feat: admit the G1 instrument through the Atom v2 local Permit commit", "files_changed": 10, "core": True, "stream": "s2_permit_bridge_and_evaluator"},
    {"position": 5, "short": "8c3f56d", "sha": "8c3f56d3b5de471761e17ef84dc92206bb00763a", "authored_at": "2026-09-05T15:42:03Z", "subject": "feat: add the separate-process salt-keyed opaque G1 evaluator", "files_changed": 2, "core": False, "stream": "s2_permit_bridge_and_evaluator"},
    {"position": 6, "short": "13780ff", "sha": "13780ff9a14dfd737566146f8664b38811902c72", "authored_at": "2026-09-05T15:57:51Z", "subject": "feat: add the opaque v3 G0-local instrument and its draft preregistration", "files_changed": 6, "core": True, "stream": "s3_instrument_and_dgx_tooling"},
    {"position": 7, "short": "1b20e3c", "sha": "1b20e3c8b8139beb07c29a9cc630e1816b8d8a14", "authored_at": "2026-09-05T16:12:54Z", "subject": "test: retain graph-and-loop v6 as the published 2026-09-02 snapshot", "files_changed": 2, "core": False, "stream": "test_hygiene"},
    {"position": 8, "short": "d9e5c1a", "sha": "d9e5c1a11d20181f7dcf9a8e0d23f687e8ecabbd", "authored_at": "2026-09-06T03:05:34Z", "subject": "refactor(effect): Effect-native POSIX services and local Permit commit", "files_changed": 6, "core": True, "stream": "effect_fp_boundary"},
    {"position": 9, "short": "75fdf15", "sha": "75fdf15b4692f690ca4b1699f6e208854e580c56", "authored_at": "2026-09-06T03:17:11Z", "subject": "chore(effect): add the Effect boundary lint with lane allowlist (report-only baseline)", "files_changed": 4, "core": True, "stream": "effect_fp_boundary"},
    {"position": 10, "short": "ab211af", "sha": "ab211af9c61ce64a6da3037a09dc6ac9bd706f1d", "authored_at": "2026-09-06T03:21:02Z", "subject": "refactor(effect): rebuild Atom v2 content file store on PosixFileSystem", "files_changed": 1, "core": False, "stream": "effect_fp_boundary"},
    {"position": 11, "short": "edee9d3", "sha": "edee9d3becfbd9d1c4be65ad2ad80eba789ba270", "authored_at": "2026-09-06T03:29:05Z", "subject": "refactor(effect): split the POSIX adapter so the DNRD-5 closure excludes child_process", "files_changed": 6, "core": True, "stream": "effect_fp_boundary"},
    {"position": 12, "short": "68513d9", "sha": "68513d95c0c4753430fb467d8aad5f3d3a2bc59f", "authored_at": "2026-09-06T03:24:47Z", "subject": "refactor(effect): replace module-level brands and lock table with private-field handles and a ProtectedRootLocks service", "files_changed": 6, "core": False, "stream": "effect_fp_boundary"},
    {"position": 13, "short": "8ee390b", "sha": "8ee390b12dae6ce01d171ab9fc86e8e4244225a3", "authored_at": "2026-09-06T03:29:16Z", "subject": "refactor: rebuild graph-loop journal on PosixFileSystem and remove throws from content, hypergraph projection", "files_changed": 4, "core": False, "stream": "effect_fp_boundary"},
    {"position": 14, "short": "1d44bc6", "sha": "1d44bc69f7e932d23a72ed5c3332b835353b6ea2", "authored_at": "2026-09-06T03:32:09Z", "subject": "refactor(effect): projection receipt verifies graph digests through the Either core", "files_changed": 1, "core": False, "stream": "effect_fp_boundary"},
    {"position": 15, "short": "dad5d21", "sha": "dad5d2139918e2dff3f16b76a13ae4fe7352e845", "authored_at": "2026-09-06T03:31:28Z", "subject": "refactor(effect): graph-loop job and hypergraph projection as Effect programs", "files_changed": 5, "core": False, "stream": "effect_fp_boundary"},
    {"position": 16, "short": "fdc4c9d", "sha": "fdc4c9d9a92e6e10dcfa3681ebbaedfd72534ac4", "authored_at": "2026-09-06T03:36:49Z", "subject": "refactor(effect): rehearsal fixtures return Either instead of throwing", "files_changed": 8, "core": False, "stream": "effect_fp_boundary"},
    {"position": 17, "short": "e00bd0f", "sha": "e00bd0f3c97c8cc0fddadc91ff90d8e963f59b79", "authored_at": "2026-09-06T03:36:08Z", "subject": "refactor(effect): rebuild Atom v2 state journal file store on PosixFileSystem", "files_changed": 1, "core": False, "stream": "effect_fp_boundary"},
    {"position": 18, "short": "547b02f", "sha": "547b02fa58b3b0befbd110b48b7dfa1c695503d7", "authored_at": "2026-09-06T03:43:15Z", "subject": "refactor(effect): rewrite DNRD routing-diagnostic process as one Effect program", "files_changed": 3, "core": False, "stream": "effect_fp_boundary"},
    {"position": 19, "short": "1feb30c", "sha": "1feb30ce64b281b63ec86734599a02bcc70e124a", "authored_at": "2026-09-06T03:47:06Z", "subject": "chore(effect): enforce the Effect boundary lint in npm run check", "files_changed": 3, "core": False, "stream": "effect_fp_boundary"},
    {"position": 20, "short": "2edf60e", "sha": "2edf60e044c2b7e417538eeba522d0289ef50c36", "authored_at": "2026-09-06T03:51:00Z", "subject": "research: record the Effect functional boundary and publish its KG projection", "files_changed": 9, "core": False, "stream": "effect_fp_boundary"},
    {"position": 21, "short": "01dce38", "sha": "01dce38ab7fdf3e5a829d4bde1bf7dcbbc638e53", "authored_at": "2026-09-06T07:11:51Z", "subject": "fix: stop pinning live files byte-exactly in the S2S numeric closure and the FP boundary test", "files_changed": 3, "core": False, "stream": "test_hygiene"},
    {"position": 22, "short": "0272c5b", "sha": "0272c5ba62bff087f1f3cb6fb9fdbd806331957b", "authored_at": "2026-09-06T07:14:27Z", "subject": "refactor(effect): retire the throwing digest wrapper and keep the Neo4j driver bracket in the adapter lane", "files_changed": 26, "core": False, "stream": "effect_fp_boundary"},
    {"position": 23, "short": "388f40d", "sha": "388f40d95b6871fe952d82ec653127fa93a18d1a", "authored_at": "2026-09-06T07:14:27Z", "subject": "refactor(effect): the state journal's process-race seam is an Effect, not a Promise thunk", "files_changed": 6, "core": False, "stream": "effect_fp_boundary"},
    {"position": 24, "short": "6ebc181", "sha": "6ebc181d0dc31716a536b98a2824db8e9fa6cd18", "authored_at": "2026-09-06T07:14:39Z", "subject": "test: retire the 23 dead per-version S2S handoff tests for one retained-snapshot test", "files_changed": 2, "core": False, "stream": "test_hygiene"},
    {"position": 25, "short": "0ddf2e0", "sha": "0ddf2e0719fc6964e8e5269278180a9167dae757", "authored_at": "2026-09-06T07:14:39Z", "subject": "research: prepare the D-3 G1 estimand binding decision (S-4)", "files_changed": 1, "core": True, "stream": "s4_estimand_binding"},
    {"position": 26, "short": "cf7595a", "sha": "cf7595ad53b2684be1e1ec992efdda59abfff422", "authored_at": "2026-09-06T07:15:04Z", "subject": "docs(effect): note the closed boundary residues in the runtime README", "files_changed": 1, "core": False, "stream": "effect_fp_boundary"},
    {"position": 27, "short": "b6b945e", "sha": "b6b945edfdee298f4eb62507ebc515d0a3bb4bd8", "authored_at": "2026-09-06T07:24:49Z", "subject": "test: follow the runtime closure growth and declare the v6 drift of the boundary refactor", "files_changed": 2, "core": False, "stream": "test_hygiene"},
    {"position": 28, "short": "ddf68c2", "sha": "ddf68c23e2eadf0d91ddc40f56bdd008bc8e63b7", "authored_at": "2026-09-06T07:50:31Z", "subject": "research: run the opaque v3 (G0-local) occurrence through the fresh-DGX lease (S-3 tooling)", "files_changed": 5, "core": True, "stream": "s3_instrument_and_dgx_tooling"},
    {"position": 29, "short": "d689def", "sha": "d689defaec5d128a355c24f086309f0c5c3618b2", "authored_at": "2026-09-06T08:11:30Z", "subject": "research: v3 code pool with equal-token-count selection, seal marker, and after-seal reveal publication", "files_changed": 5, "core": True, "stream": "s3_instrument_and_dgx_tooling"},
    {"position": 30, "short": "a9e9099", "sha": "a9e9099838924a22efb2d62c135567554a0924e4", "authored_at": "2026-09-06T17:12:32+09:00", "subject": "research: freeze the opaque v3 (G0-local) protocol for the 2026-09-06 occurrence", "files_changed": 1, "core": True, "stream": "protocol_freezes"},
    {"position": 31, "short": "13b18ba", "sha": "13b18bad548fbba166b1ecc8789bb55e0f159110", "authored_at": "2026-09-06T08:32:53Z", "subject": "fix: the DGX runtime-binding validator accepts the dated v3 protocol file", "files_changed": 2, "core": True, "stream": "s3_instrument_and_dgx_tooling"},
    {"position": 32, "short": "fd41b5d", "sha": "fd41b5d0739bee5942409968236eede37d7b03a8", "authored_at": "2026-09-06T08:49:16Z", "subject": "fix: the v3 actor never stats the evaluator's private ledger; SR-3 rerun suffix", "files_changed": 4, "core": True, "stream": "s3_instrument_and_dgx_tooling"},
    {"position": 33, "short": "647fcde", "sha": "647fcdec53997e863a8907f40644d13b1370ab47", "authored_at": "2026-09-06T17:49:27+09:00", "subject": "research: freeze the opaque v3 repaired rerun protocol (2026-09-06-r2, SR-3)", "files_changed": 1, "core": True, "stream": "protocol_freezes"},
    {"position": 34, "short": "b7aee99", "sha": "b7aee996d4cf3c791363ce39185b1b9fd70618c7", "authored_at": "2026-09-06T09:05:02Z", "subject": "research: public projection, verification join, and evidence record for a completed v3 occurrence", "files_changed": 1, "core": False, "stream": "s3_instrument_and_dgx_tooling"},
    {"position": 35, "short": "98aa571", "sha": "98aa5713d55ef3412c2676cfe2bc39182aac5dcf", "authored_at": "2026-09-06T18:05:30+09:00", "subject": "research: publish the opaque v3 (G0-local) 2026-09-06-r2 occurrence projection, verification join, and evidence record", "files_changed": 3, "core": True, "stream": "occurrence_publications"},
    {"position": 36, "short": "e926e1f", "sha": "e926e1fcbdef3c6da41a92995346df934289180b", "authored_at": "2026-09-06T09:09:06Z", "subject": "results: opaque v3 (G0-local) 2026-09-06 occurrence — S-3 run complete, rule not met", "files_changed": 5, "core": True, "stream": "occurrence_publications"},
    {"position": 37, "short": "3a751dd", "sha": "3a751ddcba5cf50eadfa0bd0f19314c7f024dfb1", "authored_at": "2026-09-06T09:16:12Z", "subject": "canon: closure plan event version v3 at the opaque v3 receipt, published to the live KG", "files_changed": 7, "core": False, "stream": "closure_events"},
    {"position": 38, "short": "ce34364", "sha": "ce34364d168b9dfd1e095629062fdf77c19b7a3a", "authored_at": "2026-09-06T09:30:17Z", "subject": "research: v4 design revision (independent, stratum-balanced no-state orders) and the delegated 2026-09-06 decision source", "files_changed": 7, "core": True, "stream": "design_revisions_and_delegated_decision"},
    {"position": 39, "short": "231ee05", "sha": "231ee05681a46d1637d1a80f65554600abfc7ee7", "authored_at": "2026-09-06T18:30:29+09:00", "subject": "research: freeze the opaque v4 (G0-local, independent no-state orders) protocol for the 2026-09-06 occurrence", "files_changed": 1, "core": True, "stream": "protocol_freezes"},
    {"position": 40, "short": "45b81d7", "sha": "45b81d753e666a1f66810ca54bb821b587a94667", "authored_at": "2026-09-06T18:43:47+09:00", "subject": "research: publish the opaque v4 (G0-local, independent no-state orders) 2026-09-06 occurrence projection, verification join, and evidence record", "files_changed": 3, "core": True, "stream": "occurrence_publications"},
    {"position": 41, "short": "4c924d2", "sha": "4c924d2e075ce7065e3698dfbb08ba209f0a2ed3", "authored_at": "2026-09-06T09:46:07Z", "subject": "results: opaque v4 (G0-local, independent no-state orders) 2026-09-06 occurrence — rule not met, control clause shown unsatisfiable", "files_changed": 4, "core": True, "stream": "occurrence_publications"},
    {"position": 42, "short": "4b4411c", "sha": "4b4411cd2d6bf6ae5671ce4fdfd56e1c082d03a9", "authored_at": "2026-09-06T09:48:30Z", "subject": "research: v5 rule revision — stateful per-stratum floors, pooled control ceilings, own-position pattern reported", "files_changed": 4, "core": True, "stream": "design_revisions_and_delegated_decision"},
    {"position": 43, "short": "d3c2a9b", "sha": "d3c2a9bd4b444c866f037c7386cacc6c12751b98", "authored_at": "2026-09-06T18:48:42+09:00", "subject": "research: freeze the opaque v5 (G0-local, corrected control clause) protocol for the 2026-09-06 occurrence", "files_changed": 1, "core": True, "stream": "protocol_freezes"},
    {"position": 44, "short": "62e2d7e", "sha": "62e2d7eef03cb87738a6174bc0a3b3c779232037", "authored_at": "2026-09-06T10:04:12Z", "subject": "research: the public projection carries the per-stateful-stratum counts and the protocol's own rule", "files_changed": 1, "core": False, "stream": "s3_instrument_and_dgx_tooling"},
    {"position": 45, "short": "7ff7766", "sha": "7ff7766dab26ce5f13b27cede0e39dc7fdd7eac3", "authored_at": "2026-09-06T19:04:14+09:00", "subject": "research: publish the opaque v5 (G0-local, corrected control clause) 2026-09-06 occurrence projection, verification join, and evidence record", "files_changed": 3, "core": True, "stream": "occurrence_publications"},
    {"position": 46, "short": "d3af76a", "sha": "d3af76a0a7c5741e5dbff53b00c294f1075abf2d", "authored_at": "2026-09-06T10:07:39Z", "subject": "results: opaque v5 (G0-local, corrected control clause) 2026-09-06 occurrence — every frozen clause held", "files_changed": 7, "core": True, "stream": "occurrence_publications"},
    {"position": 47, "short": "d71f977", "sha": "d71f97780c2709fad993f71a9c593ee72ec73d0b", "authored_at": "2026-09-06T10:12:10Z", "subject": "canon: closure plan event version v4 — D-3 ratified by delegated choice, S-4 complete, v3/v4/v5 receipts, published to the live KG", "files_changed": 7, "core": False, "stream": "closure_events"},
    {"position": 48, "short": "244bf4f", "sha": "244bf4f9a05fc9d8bbdf4ed20c409f714fa7b1cb", "authored_at": "2026-09-06T12:46:28Z", "subject": "canon: closure plan event version v5 — D-4 done-state judged SEGMENT_OBSERVED_NOT_REACHED, S-1/S-5/S-6 progress readings, published to the live KG", "files_changed": 7, "core": False, "stream": "closure_events"},
)

STREAMS: dict[str, dict[str, Any]] = {
    "audit_and_plan": {
        "name": "Adversarial audit and closure plan record",
        "outcome": "The 2026-09-05 adversarial programme audit, its closure plan, the first KG projection, the D-1/D-4 ratification event (v2) and the numeric burden-cap checker were recorded.",
        "steps": ["S-1"],
    },
    "s2_permit_bridge_and_evaluator": {
        "name": "S-2: Atom v2 local Permit bridge and separate-process evaluator",
        "outcome": "g1_micro admissions go through the real Atom v2 local Permit commit (node process) and outcomes are scored by a separate-process, salt-keyed evaluator; S-2 completed at 51f631b.",
        "steps": ["S-2"],
    },
    "s3_instrument_and_dgx_tooling": {
        "name": "S-3: opaque v3 instrument and fresh-DGX lease tooling",
        "outcome": "The 32-episode opaque v3 (G0-local) instrument, the digest-pinned loopback vLLM lease with runtime binding and final attestation, code pool with equal-token-count selection, seal marker with bounded reveal wait, after-seal reveal publication by the evaluator OS user, and the two defect fixes found by the VOID first attempt (validator path acceptance; actor never stats the evaluator ledger, SR-3 rerun suffix).",
        "steps": ["S-3"],
    },
    "effect_fp_boundary": {
        "name": "Effect runtime functional boundary refactor",
        "outcome": "PosixFileSystem and BoundedSubprocess adapters, runProcessMain, Either-returning cores, the R1-R5 boundary lint with a seven-lane allowlist wired into npm run check, and the published functional-boundary KG bundle (84 nodes / 279 relations); no throwing digest wrapper, no Promise seams in the state journal.",
        "steps": [],
    },
    "test_hygiene": {
        "name": "Test hygiene and lint residues",
        "outcome": "Retired 23 dead per-version handoff tests for one retained-snapshot test, stopped byte-pinning live files in the S2S numeric closure and the FP-boundary test, followed the runtime closure growth (76 files) and declared the v6 drift of the boundary refactor.",
        "steps": [],
    },
    "s4_estimand_binding": {
        "name": "S-4: D-3 G1 estimand binding proposal",
        "outcome": "The D-3 proposal (option A recommended: the project.v1.json pass_rule as binding G1 estimand; B0/B2 as secondary ceilings) was prepared for the user's decision.",
        "steps": ["S-4"],
    },
    "design_revisions_and_delegated_decision": {
        "name": "v4/v5 design and rule revisions under the delegated decision",
        "outcome": "The user's verbatim delegation was hash-bound (D-3 RATIFIED option A, DELEGATED_CHOICE_RECORDED_VERBATIM); v4 made the no-state orders seed-independent and stratum-balanced; v5 replaced the unsatisfiable own-position control clause with stateful per-stratum floors and pooled control ceilings.  Each is a new preregistration (RG-4); sealed terminals were not rescored.",
        "steps": ["S-3", "S-4"],
    },
    "protocol_freezes": {
        "name": "Frozen protocols",
        "outcome": "Four protocols frozen with offline tokenizer receipts: v3 2026-09-06 (VOID attempt, canonical 4d049c7b…), v3 2026-09-06-r2 (2363815e…), v4 2026-09-06 (052f5198…), v5 2026-09-06 (180f7e5f…).",
        "steps": ["S-3"],
    },
    "occurrence_publications": {
        "name": "Occurrence projections, verification joins, evidence and result files",
        "outcome": "Three sealed occurrences published: v3-r2 NO_SEPARATION (ACTIVE 32/32, RESTORE 32/32, FORCED 0/32, SHAM 20/32, NO_UPDATE 16/32, REMOVE 16/32, delta 0.594), v4 NO_SEPARATION (32/32/0/14/16/16, delta 0.641, control clause shown unsatisfiable), v5 G0_LOCAL_IDENTIFIABILITY_OBSERVED (32/32/0/16/16/16, delta 0.625, claim ceiling MEASUREMENT_READY_SINGLE_OWNER_UNDER_DECLARED_OPAQUE_TASK).  G0 NOT_PASSED, G1 NOT_EVALUATED, no efficacy inference.",
        "steps": ["S-3"],
    },
    "closure_events": {
        "name": "Closure plan event versions v3, v4, v5",
        "outcome": "v3 at the first v3 receipt; v4 with D-3 ratified by delegated choice, S-4 complete and three receipts; v5 with the D-4 done-state judged SEGMENT_OBSERVED_BY_V5_RECEIPT_NOT_REACHED and zero-POST progress readings for S-1, S-5, S-6.  Each was published to the live KG and read back exactly; predecessors retained unchanged.",
        "steps": ["S-4", "S-6"],
    },
}

RESULT_COMMIT_TO_RECEIPT = {
    "e926e1f": f"sym:AbstractNode:hswm-closure-v3-receipt-{CLOSURE_TAG}",
    "4c924d2": f"sym:AbstractNode:hswm-closure-v4-receipt-{CLOSURE_TAG}",
    "d3af76a": f"sym:AbstractNode:hswm-closure-v5-receipt-{CLOSURE_TAG}",
}

OPEN_ITEMS: tuple[dict[str, Any], ...] = (
    {
        "id": "OI-1",
        "name": "D-2 needs the user's words",
        "reading": "D-2 (narrow the never-weaken rule to post-outcome contract modification) was neither named nor asked in the 2026-09-06 delegation and remains PROPOSED; S-1 cannot close without it.",
        "owner": "USER_PRIMARY",
        "blocks": [f"sym:Concept:hswm-closure-step-s-1-{CLOSURE_TAG}"],
        "constrains": [],
        "status": "BLOCKED_ON_USER_WORDS",
    },
    {
        "id": "OI-2",
        "name": "Second-party line for S-6",
        "reading": "S-6 deliverable (b), one line naming a second-party recruiting date or an explicit non-start, requires the user's own words.  The zero-network G0-occurrence preflight reads BLOCKED_EXTERNAL on the workstation and on the DGX with all 22 external bindings missing; G0-external is not executable by one person (SR-2).",
        "owner": "USER_PRIMARY",
        "blocks": [f"sym:Concept:hswm-closure-step-s-6-{CLOSURE_TAG}"],
        "constrains": [],
        "status": "BLOCKED_ON_USER_WORDS",
    },
    {
        "id": "OI-3",
        "name": "B0 comparator successor occurrence",
        "reading": "The only B0 consumption occurrence (2026-08-30) failed before any model call: ModuleNotFoundError for alfworld inside the bwrap sandbox (DGX host diagnostics 2026-09-06 -006 reproduced it, -007 imported after a PYTHONPATH change).  The fix is an uncommitted edit to the protocol-bound alfworld_text_runtime.py, so a valid B0 needs a sixth prospective amendment or a v2 protocol, a new dated selection manifest (the sealed selection binds the protocol digest), code and test pin updates, a fresh zero-POST DGX qualification, then one 36000 s-ceiling occurrence: about 540 minutes of one-person work, not feasible on 2026-09-06.",
        "owner": "SECONDARY_AI",
        "blocks": [f"sym:Concept:hswm-closure-step-s-5-{CLOSURE_TAG}"],
        "constrains": [],
        "status": "NOT_FEASIBLE_TODAY_ROOT_CAUSE_KNOWN",
    },
    {
        "id": "OI-4",
        "name": "B2 text-lesson comparator preregistration",
        "reading": "Only a DRAFT_NOT_PREREGISTERED_NOT_FROZEN_NOT_RUN design and a lesson-state core exist; nine of eighteen bindings are pending and the selector, transport, ALFWorld execution, scorer, sealed runner and projector are missing.  Multi-day effort; depends on the repaired B0 sandbox.",
        "owner": "SECONDARY_AI",
        "blocks": [f"sym:Concept:hswm-closure-step-s-5-{CLOSURE_TAG}"],
        "constrains": [],
        "status": "NOT_FEASIBLE_TODAY_DRAFT_ONLY",
    },
    {
        "id": "OI-5",
        "name": "D-4 canonical-revision and held-out successor",
        "reading": "The v5 receipt supplies the credit-to-Permit-to-state-readout segment only; a done-state run needs a study-local canonical revision plane (owner-bound OutcomeRecord, CreditRecord, RevisionProposal, DispositionRevision, PermitCommitReceipt, CanonicalStateHead, InterventionReceipt) and a precommitted train/held-out partition on a non-numeric persistent task.  A prospective contract exists as the uncommitted d4_v1_canonical_heldout_DRAFT README prepared by a parallel agent session.",
        "owner": "SECONDARY_AI",
        "blocks": [f"sym:Concept:hswm-closure-v1-done-state-{CLOSURE_TAG}"],
        "constrains": [],
        "status": "SUCCESSOR_CONTRACT_DRAFTED_NOT_PREREGISTERED",
    },
    {
        "id": "OI-6",
        "name": "Burden cap trajectory",
        "reading": "At the ledger head 48 commits sit in the 100-commit window after 4dcba75, 23 on core paths (0.4792 < 0.5, WINDOW_OPEN_BELOW_SHARE).  The cap can only be violated when the window is full, so at least 28 of the remaining 52 commits must touch a core path; the ledger commit itself is not a core-path commit.",
        "owner": "SECONDARY_AI",
        "blocks": [],
        "constrains": [f"sym:Concept:hswm-closure-step-s-6-{CLOSURE_TAG}"],
        "status": "WINDOW_OPEN_BELOW_SHARE",
    },
    {
        "id": "OI-7",
        "name": "DGX checkout lag",
        "reading": "The DGX checkout ~/hswm-source was at 7ff7766 when the ledger was taken, behind the workstation head; code ships by git bundle (no GitHub push).  Every occurrence lease refuses a dirty or divergent tree, so the bundle must be shipped before any further DGX run.",
        "owner": "SECONDARY_AI",
        "blocks": [],
        "constrains": [f"sym:Concept:hswm-closure-step-s-5-{CLOSURE_TAG}"],
        "status": "SHIP_BUNDLE_BEFORE_NEXT_RUN",
    },
    {
        "id": "OI-8",
        "name": "Parallel agent session sharing the working tree",
        "reading": "An OpenAI Codex CLI session with the same working directory wrote, uncommitted and unreviewed by this session: the recovered B0 2026-08-30 result, evidence and raw receipts; expel_b2_text_lesson.py and its test; test_hswm_alfworld_b0_publication.py; the B2 and D-4 successor DRAFT READMEs; the alfworld_text_runtime.py PYTHONPATH fix and its test; one F1_R8_RESULTS_LOG.md row.  Their 31 tests pass locally.  This session committed only its own paths and left those files untracked; nothing here is cited as committed work.",
        "owner": "USER_PRIMARY",
        "blocks": [],
        "constrains": [f"sym:Concept:hswm-closure-step-s-5-{CLOSURE_TAG}"],
        "status": "OBSERVED_UNCOMMITTED_THIRD_WRITER",
    },
)

READINGS: tuple[dict[str, Any], ...] = (
    {
        "id": "R-BURDEN",
        "roles": ["BURDEN_READING"],
        "name": "Burden reading at the ledger head",
        "reading": "scripts/check_hswm_closure_burden_cap.py: commits_observed 48, core_commits 23, core_share 0.4792, min_core_share 0.5, window 100 from 4dcba75, status WINDOW_OPEN_BELOW_SHARE, disposition INSTRUMENT_RED_ROW_IN_F1_R8_NO_SCOPE_EXPANSION on violation.",
        "assesses": [f"sym:Concept:hswm-closure-burden-cap-{CLOSURE_TAG}"],
    },
    {
        "id": "R-VERIFY",
        "roles": ["VERIFICATION_READING"],
        "name": "Verification readings on 2026-09-06",
        "reading": "Effect runtime at 244bf4f: npm run check clean (tsc, temporal tsc, boundary lint over 130 files with 0 violations and 0 stale allowlist entries); vitest 870 passed, 7 skipped, and 2 filesystem-heavy tests (two-CAS resume, S2S preregistration snapshot) timed out at 5000 ms while the Python suite ran concurrently and passed in isolation (29/29).  Closure-plan tests 11 passed and graph-view SHACL/SPARQL 14 passed at 244bf4f; the parallel session's 31 untracked tests pass.  Python suite at 244bf4f with the parallel session's untracked tests present: 3649 passed, 3 skipped (17 min 15 s).  DGX: every occurrence lease restored the shared vllm, vllm-receiver and comfyui-10eros containers; 30 leftover /tmp/hswm-v* files were removed after the last run.",
        "assesses": [],
    },
    {
        "id": "R-DAY",
        "roles": ["SESSION_OUTCOME_READING"],
        "name": "What the day established and what it did not",
        "reading": "Established: the whole G0-local instrument chain runs end-to-end on the DGX under a fresh digest-pinned lease with OS-user custody, and under a satisfiable control clause the compiled local disposition mediates the model's opaque-action choice (stateful 96/96 vs forced-opposite 0/96 vs no-state 48/96 across v3, v4, v5).  Not established: canonical HSWM admission, held-out generalization, reuse-first comparators, G0-external, G1, efficacy; the D-4 v1 done-state is not reached.  Decisions ratified today: D-3 (delegated, option A).  Still PROPOSED: D-2.",
        "assesses": [],
    },
)

ANCHORS: tuple[dict[str, Any], ...] = (
    {"uid": "sym:Concept:hswm", "name": "HSWM", "required_labels": ["Concept"]},
    {"uid": CLOSURE_BUNDLE_UID, "name": f"HSWM closure plan ontology [{CLOSURE_TAG}]", "required_labels": ["AbstractNode", "ResearchArtifact"]},
    {"uid": CLOSURE_PROGRAM_UID, "name": f"HSWM closure plan [{CLOSURE_TAG}]", "required_labels": ["ResearchProgram"]},
    {"uid": EFFECT_FP_BUNDLE_UID, "name": "HSWM Effect runtime functional boundary ontology [2026-09-06]", "required_labels": ["AbstractNode", "ResearchArtifact"]},
    {"uid": f"sym:Concept:hswm-closure-step-s-1-{CLOSURE_TAG}", "name": f"S-1 — Ratify D-1, D-2, D-4 and record them as USER_PRIMARY [{CLOSURE_TAG}]", "required_labels": ["Concept"]},
    {"uid": f"sym:Concept:hswm-closure-step-s-2-{CLOSURE_TAG}", "name": f"S-2 — Bridge g1_micro admission to the real local Permit commit [{CLOSURE_TAG}]", "required_labels": ["Concept"]},
    {"uid": f"sym:Concept:hswm-closure-step-s-3-{CLOSURE_TAG}", "name": None, "required_labels": ["Concept"]},
    {"uid": f"sym:Concept:hswm-closure-step-s-4-{CLOSURE_TAG}", "name": None, "required_labels": ["Concept"]},
    {"uid": f"sym:Concept:hswm-closure-step-s-5-{CLOSURE_TAG}", "name": f"S-5 — Produce the first B0 and B2 comparator result files [{CLOSURE_TAG}]", "required_labels": ["Concept"]},
    {"uid": f"sym:Concept:hswm-closure-step-s-6-{CLOSURE_TAG}", "name": f"S-6 — Enforce the burden cap and settle the second-party question [{CLOSURE_TAG}]", "required_labels": ["Concept"]},
    {"uid": f"sym:AbstractNode:hswm-closure-v3-receipt-{CLOSURE_TAG}", "name": f"Opaque v3 (G0-local) occurrence receipt 2026-09-06 [{CLOSURE_TAG}]", "required_labels": ["AbstractNode", "ResearchArtifact"]},
    {"uid": f"sym:AbstractNode:hswm-closure-v4-receipt-{CLOSURE_TAG}", "name": f"Opaque v4 (G0-local, independent no-state orders) occurrence receipt 2026-09-06 [{CLOSURE_TAG}]", "required_labels": ["AbstractNode", "ResearchArtifact"]},
    {"uid": f"sym:AbstractNode:hswm-closure-v5-receipt-{CLOSURE_TAG}", "name": f"Opaque v5 (G0-local, corrected control clause) occurrence receipt 2026-09-06 [{CLOSURE_TAG}]", "required_labels": ["AbstractNode", "ResearchArtifact"]},
    {"uid": f"sym:Concept:hswm-closure-user-decision-d-2-{CLOSURE_TAG}", "name": f"D-2 — Narrow the never-weaken rule to post-outcome contract modification [{CLOSURE_TAG}]", "required_labels": ["Concept", "Guardrail"]},
    {"uid": f"sym:Concept:hswm-closure-user-decision-d-3-{CLOSURE_TAG}", "name": f"D-3 — Bind the G1 estimand [{CLOSURE_TAG}]", "required_labels": ["Concept", "Guardrail"]},
    {"uid": f"sym:Concept:hswm-closure-v1-done-state-{CLOSURE_TAG}", "name": None, "required_labels": ["Concept", "Guardrail"]},
    {"uid": f"sym:Concept:hswm-closure-burden-cap-{CLOSURE_TAG}", "name": f"HSWM closure burden cap [{CLOSURE_TAG}]", "required_labels": ["Concept", "Guardrail"]},
)


def _closure_names() -> dict[str, str]:
    path = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v5.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {row["uid"]: row["properties"]["name"] for row in data["nodes"]}


def anchors() -> list[dict[str, Any]]:
    names = _closure_names()
    rows = []
    for row in ANCHORS:
        name = row["name"] if row["name"] is not None else names[row["uid"]]
        if row["uid"] in names and names[row["uid"]] != name:
            raise ValueError(f"anchor name drifted from the bound closure bundle: {row['uid']}")
        rows.append({"uid": row["uid"], "name": name, "required_labels": list(row["required_labels"])})
    return rows


def _clip(value: str, limit: int = MAX_TEXT) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _common(*, name: str, description: str, authority: str, scope: str, kind: str, plane: str, state: str, owner: str, roles: list[str], boundary: str) -> dict[str, Any]:
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


def _relation(from_uid: str, relation_type: str, to_uid: str, scope: str, status: str, authority: str = "SECONDARY_AI") -> dict[str, str]:
    return {"from_uid": from_uid, "type": relation_type, "to_uid": to_uid, "authority_class": authority, "scope": scope, "status": status}


def stream_uid(stream_id: str) -> str:
    return f"sym:Concept:hswm-session-stream-{stream_id.replace('_', '-')}-{TAG}"


def commit_uid(short: str) -> str:
    return f"sym:AbstractNode:hswm-session-commit-{short}-{TAG}"


def open_item_uid(item_id: str) -> str:
    return f"sym:Concept:hswm-session-open-item-{item_id.lower()}-{TAG}"


def reading_uid(reading_id: str) -> str:
    return f"sym:Concept:hswm-session-reading-{reading_id.lower()}-{TAG}"


def step_uid(step_id: str) -> str:
    return f"sym:Concept:hswm-closure-step-{step_id.lower()}-{CLOSURE_TAG}"


def build_data() -> dict[str, Any]:
    bindings = [{"path": path.relative_to(ROOT).as_posix(), "sha256": _file_sha(path)} for path in SOURCE_BINDING_PATHS]
    anchor_rows = anchors()
    anchor_uids = {row["uid"] for row in anchor_rows}
    nodes: list[dict[str, Any]] = []
    relations: list[dict[str, str]] = []
    owned: set[str] = set()

    def own(node: dict[str, Any]) -> None:
        if node["uid"] in owned or node["uid"] in anchor_uids:
            raise ValueError(f"duplicate or anchor-colliding uid: {node['uid']}")
        owned.add(node["uid"])
        nodes.append(node)

    by_stream: dict[str, list[dict[str, Any]]] = {key: [] for key in STREAMS}
    for row in COMMITS:
        by_stream[row["stream"]].append(row)
    if any(not rows for rows in by_stream.values()):
        raise ValueError("every declared stream must own at least one commit")
    core_total = sum(1 for row in COMMITS if row["core"])

    own(_node(BUNDLE_UID, ["AbstractNode", "ResearchArtifact"], {
        **_common(
            name=f"HSWM session ledger [{TAG}]",
            description=(
                f"Bounded KG projection of the 2026-09-05/06 working session: {len(COMMITS)} commits in the closure burden window "
                f"after {WINDOW_START_COMMIT[:7]} up to {LEDGER_HEAD_COMMIT}, {core_total} on core paths, grouped into {len(STREAMS)} work streams, "
                f"joined to the closure-plan steps, receipts, decisions and cap they touched, with {len(OPEN_ITEMS)} open items and {len(READINGS)} readings."
            ),
            authority="SYSTEM_DERIVED", scope="BOUNDED_SESSION_EFFORT_LEDGER", kind="ARTIFACT", plane="INQUIRY",
            state="EFFORT_LEDGER_RECORDED", owner="session_ledger_custodian", roles=["SESSION_LEDGER", "PROJECTION_ROOT"],
            boundary="An effort ledger orders what was done and what stays open; it passes no gate, ratifies nothing, and promotes no claim.",
        ),
        "session_date": RELEASE,
        "window_start_commit": WINDOW_START_COMMIT,
        "ledger_head_commit": LEDGER_HEAD_COMMIT,
        "commit_count": len(COMMITS),
        "core_commit_count": core_total,
        "core_share": round(core_total / len(COMMITS), 4),
        "core_path_prefixes": list(CORE_PATH_PREFIXES),
        "closure_bundle_uid": CLOSURE_BUNDLE_UID,
        "effect_fp_bundle_uid": EFFECT_FP_BUNDLE_UID,
        "stream_ids": list(STREAMS),
    }))
    relations.append(_relation(BUNDLE_UID, "DEPENDS_ON", CLOSURE_BUNDLE_UID, "LEDGER_JOINS_CLOSURE_EVENT_V5", "BOUND"))
    relations.append(_relation(BUNDLE_UID, "DEPENDS_ON", EFFECT_FP_BUNDLE_UID, "LEDGER_JOINS_EFFECT_FP_BUNDLE", "BOUND"))
    relations.append(_relation(BUNDLE_UID, "TARGETS", CLOSURE_PROGRAM_UID, "SESSION_EFFORT_UNDER_PROGRAM", "RECORDED"))
    relations.append(_relation(BUNDLE_UID, "HAS_CONCEPT", "sym:Concept:hswm", "SUBJECT", "RECORDED"))

    for stream_id, spec in STREAMS.items():
        rows = by_stream[stream_id]
        s_uid = stream_uid(stream_id)
        own(_node(s_uid, ["Concept"], {
            **_common(
                name=f"{spec['name']} [{TAG}]", description=spec["outcome"],
                authority="SECONDARY_AI", scope="SESSION_WORK_STREAM", kind="TASK", plane="INQUIRY",
                state="RECORDED", owner="session_ledger_custodian", roles=["SESSION_WORK_STREAM"],
                boundary="A work stream groups commits by purpose; its outcome sentence is descriptive, not a result.",
            ),
            "stream_id": stream_id,
            "commit_count": len(rows),
            "core_commit_count": sum(1 for row in rows if row["core"]),
            "first_commit": rows[0]["short"],
            "last_commit": rows[-1]["short"],
            "closure_step_ids": list(spec["steps"]),
        }))
        relations.append(_relation(BUNDLE_UID, "HAS_CONCEPT", s_uid, "WORK_STREAM", "RECORDED"))
        for step_id in spec["steps"]:
            relations.append(_relation(s_uid, "ADDRESSES", step_uid(step_id), "WORK_STREAM_ADVANCES_STEP", "RECORDED"))
    relations.append(_relation(stream_uid("effect_fp_boundary"), "TARGETS", EFFECT_FP_BUNDLE_UID, "PROJECTED_AS", "PUBLISHED"))
    relations.append(_relation(stream_uid("closure_events"), "TARGETS", CLOSURE_BUNDLE_UID, "LATEST_EVENT_VERSION", "PUBLISHED"))
    relations.append(_relation(stream_uid("design_revisions_and_delegated_decision"), "TARGETS", f"sym:Concept:hswm-closure-user-decision-d-3-{CLOSURE_TAG}", "DELEGATED_RATIFICATION_SOURCE", "RATIFIED"))

    previous: str | None = None
    for row in COMMITS:
        c_uid = commit_uid(row["short"])
        own(_node(c_uid, ["AbstractNode", "ResearchArtifact"], {
            **_common(
                name=f"{row['short']} {row['subject']} [{TAG}]", description=row["subject"],
                authority="SECONDARY_AI", scope="SESSION_COMMIT", kind="ARTIFACT", plane="INQUIRY",
                state="COMMITTED", owner="session_ledger_custodian", roles=["SESSION_COMMIT", "CORE_PATH_COMMIT" if row["core"] else "NON_CORE_COMMIT"],
                boundary="A commit is a unit of checked-in work; its subject line is not a claim.",
            ),
            "commit_sha": row["sha"],
            "commit_short": row["short"],
            "authored_at": row["authored_at"],
            "files_changed": row["files_changed"],
            "core_path_commit": row["core"],
            "window_position": row["position"],
            "stream_id": row["stream"],
        }))
        relations.append(_relation(stream_uid(row["stream"]), "HAS_CONCEPT", c_uid, "STREAM_COMMIT", "COMMITTED"))
        if previous is not None:
            relations.append(_relation(previous, "PRECEDES", c_uid, "WINDOW_ORDER", "COMMITTED"))
        previous = c_uid
        if row["short"] in RESULT_COMMIT_TO_RECEIPT:
            relations.append(_relation(c_uid, "TARGETS", RESULT_COMMIT_TO_RECEIPT[row["short"]], "RESULT_FILE_FOR_RECEIPT", "SEALED"))

    for item in OPEN_ITEMS:
        o_uid = open_item_uid(item["id"])
        own(_node(o_uid, ["Concept"], {
            **_common(
                name=f"{item['id']} — {item['name']} [{TAG}]", description=item["reading"],
                authority="SECONDARY_AI" if item["owner"] == "SECONDARY_AI" else "SECONDARY_AI_PROPOSAL_FOR_USER_PRIMARY",
                scope="SESSION_OPEN_ITEM", kind="TASK", plane="INQUIRY", state=item["status"],
                owner="user" if item["owner"] == "USER_PRIMARY" else "session_ledger_custodian",
                roles=["SESSION_OPEN_ITEM"],
                boundary="An open item names what is missing and who owns it; recording it does not start or authorize any run.",
            ),
            "open_item_id": item["id"],
            "open_item_owner": item["owner"],
            "open_item_status": item["status"],
        }))
        relations.append(_relation(BUNDLE_UID, "HAS_CONCEPT", o_uid, "OPEN_ITEM", item["status"]))
        for target in item["blocks"]:
            relations.append(_relation(o_uid, "BLOCKS", target, "OPEN_ITEM_BLOCKS", item["status"]))
        for target in item["constrains"]:
            relations.append(_relation(o_uid, "CONSTRAINS", target, "OPEN_ITEM_CONSTRAINS", item["status"]))

    for reading in READINGS:
        r_uid = reading_uid(reading["id"])
        own(_node(r_uid, ["Concept"], {
            **_common(
                name=f"{reading['name']} [{TAG}]", description=reading["reading"],
                authority="SECONDARY_AI", scope="SESSION_READING", kind="OBSERVATION", plane="INQUIRY",
                state="RECORDED", owner="session_ledger_custodian", roles=list(reading["roles"]),
                boundary="A reading reports an observed number or state on the ledger date; it is not a result and expires with the next commit.",
            ),
            "reading_id": reading["id"],
            "read_on": RELEASE,
        }))
        relations.append(_relation(BUNDLE_UID, "HAS_CONCEPT", r_uid, "READING", "RECORDED"))
        for target in reading["assesses"]:
            relations.append(_relation(r_uid, "ASSESSES", target, "READING_ASSESSES", "RECORDED"))

    known = owned | anchor_uids
    for row in relations:
        if row["from_uid"] not in known or row["to_uid"] not in known:
            raise ValueError(f"dangling relation: {row}")
    nodes.sort(key=lambda row: row["uid"])
    relations.sort(key=lambda row: (row["from_uid"], row["type"], row["to_uid"]))
    data = {
        "schema_version": SCHEMA_VERSION,
        "bundle_uid": BUNDLE_UID,
        "status": STATUS,
        "nonclaim": NONCLAIM,
        "authority_boundary": (
            "Commits, streams, readings and open items are SECONDARY_AI records of effort.  Open items marked USER_PRIMARY "
            "wait on the user's own words and are not decided here.  Nothing in this ledger passes G0 or G1, reaches the "
            "D-4 done-state, or promotes any scientific claim."
        ),
        "source_accessed_on": RELEASE,
        "artifact_bindings": bindings,
        "expected_counts": {
            "nodes": len(nodes),
            "anchors": len(anchor_rows),
            "relations": len(relations),
            "commits": len(COMMITS),
            "core_commits": core_total,
            "streams": len(STREAMS),
            "open_items": len(OPEN_ITEMS),
            "readings": len(READINGS),
        },
        "anchors": anchor_rows,
        "nodes": nodes,
        "relations": relations,
    }
    validate_data(data)
    return data


def validate_data(data: dict[str, Any]) -> None:
    if data["schema_version"] != SCHEMA_VERSION or data["bundle_uid"] != BUNDLE_UID:
        raise ValueError("session ledger identity drifted")
    if data["status"] != STATUS or data["nonclaim"] != NONCLAIM:
        raise ValueError("session ledger status or nonclaim drifted")
    uids = [row["uid"] for row in data["nodes"]]
    if len(uids) != len(set(uids)):
        raise ValueError("duplicate node uids")
    anchor_uids = {row["uid"] for row in data["anchors"]}
    if anchor_uids & set(uids):
        raise ValueError("anchor collides with an owned node")
    known = anchor_uids | set(uids)
    for row in data["relations"]:
        if row["from_uid"] not in known or row["to_uid"] not in known:
            raise ValueError(f"dangling relation: {row}")
    for row in data["nodes"]:
        if row["properties"].get("projection_nonclaim") != NONCLAIM:
            raise ValueError(f"nonclaim drifted on {row['uid']}")
    counts = data["expected_counts"]
    if counts["nodes"] != len(data["nodes"]) or counts["relations"] != len(data["relations"]) or counts["anchors"] != len(data["anchors"]):
        raise ValueError("expected_counts drifted")
    commits = [row for row in data["nodes"] if "commit_sha" in row["properties"]]
    if counts["commits"] != len(commits) or counts["core_commits"] != sum(1 for row in commits if row["properties"]["core_path_commit"]):
        raise ValueError("commit counts drifted")


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
        print(json.dumps({
            "file_sha256": sha256(payload).hexdigest(),
            "projection_sha256": canonical_sha(data),
            "expected_counts": data["expected_counts"],
        }, sort_keys=True))
        return
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != payload:
            raise SystemExit("session ledger projection drifted")
        print(json.dumps({"status": "MATCH", "path": str(args.output)}, sort_keys=True))
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(json.dumps({"status": "BUILT", "path": str(args.output), "sha256": sha256(payload).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
