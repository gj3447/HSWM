# HSWM working rules

## HSWM identity and research order

- Read `docs/canon/HSWM_CONSTITUTION_2026-08-20.md` as the target-identity
  entrypoint. HSWM is one token-native LLM-function macro-neural network whose
  evolving hypergraph plays the roles of living harness, world model, and
  continuous learner; these are not separate subsystems.
- For fractal, multiscale, hypergraph, or HSWM-of-HSWMs work, next read
  `docs/research/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md` and its
  checked-in/live-KG projection
  `ontology/identity/human_universal_body/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_ONTOLOGY.v1.json`
  (bundle UID
  `sym:AbstractNode:hswm-fractal-scientific-connections-ontology-2026-08-28`).
  Preserve the eight FCL laws and the core invariant: a cognition-bearing HSWM
  is a composable cell, and HSWMs may recursively form larger cognition-bearing
  HSWMs under the same typed, outcome-bound dynamics. The scientific status is
  `SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`: the cited theories
  establish typed connections and falsifiable bridges, not evidence that HSWM
  already realizes consciousness, selfhood, or scale-invariant causal closure.
- For philosophy, research direction, or architecture work, establish the
  canonical role, separate target identity from current evidence, and state the
  conceptual delta before implementing. Do not default to code or tests.
- Do not map implementation to the retired fixed `H/W/A/F/Π` decomposition.
  Map it instead to schema-approved canonical atoms, exactly one
  schema-relative responsibility owner per atom, typed references,
  provenance-bound transitions, and the outcome-bound causal-learning loop.
  Tests are evidence instruments, not HSWM progress by themselves.
- Treat repository ontology and MCPs as bounded projections and interfaces, not
  as HSWM cognition, routing, or learning.

- Put new implementation in `src/hswm/`, tests in `tests/`, research programs in
  `_research/`, and documents or artifacts in their typed directories. Do not add
  new implementation or generated artifacts to the repository root. Move ordinary
  unbound files with standard Git operations; moving a compatibility path listed
  in `ontology/history/ROOT_COMPATIBILITY_BASELINE.v1.json` under `paths`
  requires one source-pinned manifest before its canonical copy can change.
- Preserve unrelated user changes, public compatibility, and checked-in scientific
  evidence. Do not rewrite hash-bound historical records merely to modernize paths.
- Validate in proportion to the change. On an ordinary Linux checkout, use the
  documented `uv` and pytest workflow. In the maintainer Mac/DGX setup, launch
  Python, pytest, embeddings, and heavy runs through `~/bin/hswm-run`; if its
  preflight is unavailable, use static checks and CI. DGX is scratch, data-01 is
  durable storage, and `/Volumes/GM` remains read-only.
- Add a content-addressed receipt and an entry in `F1_R8_RESULTS_LOG.md` only for a
  material research result. Routine code, documentation, and repository cleanup do
  not need research ceremony.
- Follow the active Git workflow. Maintainer work is normally verified, committed,
  and pushed to the current canonical branch unless the user says otherwise; do not
  impose a special branch topology on contributors or PRs.
- Keep the retired personal governance toolchains deleted. Do not restore their
  gates, ledgers, judgment packets, or canonical-write MCP paths without an explicit
  user request.
- Keep public claims within checked-in evidence, and do not commit private datasets,
  ignored model artifacts, credentials, or unlicensed third-party material.
