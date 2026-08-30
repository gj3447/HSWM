# ALFWorld text G1 candidate source/data audit

This is a bounded source and data audit for a potential text-only ALFWorld
environment. The selected conditional slice is
`pick_clean_then_place_in_recep`; it is not installed, downloaded, run, or
qualified here.

The audit status is exactly
`CANDIDATE_SELECTED_LOCAL_RESEARCH_AUTHORIZED_UPSTREAM_LICENSE_SCOPE_UNRESOLVED_NO_REDISTRIBUTION`.
The bound [`local_use_authorization.v1.json`](local_use_authorization.v1.json)
records the workspace owner's authorization to fetch, verify, unpack, and run
the pinned public bytes for local non-redistributive research. It is not an
upstream license grant. The official ALFWorld code is MIT licensed, but that
code license does **not** establish
permission for downloaded game data, human annotations, ALFRED-derived
trajectories, PDDL files, or release assets. Redistribution and asset-content
publication remain blocked until an authoritative permission source is pinned
and reviewed.

[`source_audit.v1.json`](source_audit.v1.json) pins the official paper, code
commit/tree/tarball, code license, five minimal source bytes, and three release
assets observed by streaming official release bytes on 2026-08-30. GitHub API
digest fields for those assets were null; the recorded SHA-256 values are
observations, not an assertion of source-controlled data licensing.

Local execution does not open G0 or G1. The actor must not see admissible
commands, expert plans/traces, hidden PDDL, or final-holdout retrieval. A
separately identified evaluator, fresh unseen validation, retention
measurement, B2/H1 equal budgets, and isolated B2 lesson/retrieval state remain
mandatory. This audit makes no HSWM, FCL, or efficacy claim.

The checked-in aggregate-only
[`HSWM_ALFWORLD_TEXT_CLEAN_POOL_2026-08-30.json`](../../../../manifests/HSWM_ALFWORLD_TEXT_CLEAN_POOL_2026-08-30.json)
records archive-to-extraction verification without publishing the local game
locator. It contains 650 train, 27 valid-seen, and 31 valid-unseen usable games.
Task grouping excludes the official split label and trial identifier: 25 of 27
valid-seen groups overlap train, while valid-unseen has 11 groups and zero
train overlap. This makes valid-seen suitable only for an explicit
contamination-sensitivity probe; it must not serve as the lineage-disjoint
final holdout. The
[public runtime qualification](../../../../manifests/HSWM_ALFWORLD_TEXT_RUNTIME_QUALIFICATION_2026-08-30.json)
binds one sealed fixed-action run to the exact pool, local private receipt,
runtime source, interpreter, packages, and bubblewrap binary. Its status is
`ENGINEERING_INSTRUMENT_QUALIFIED_G0_NOT_PASSED`: the local runtime boundary is
an engineering G0 instrument, not an independently owned evaluator, an agent
efficacy result, or a G0 decision.
