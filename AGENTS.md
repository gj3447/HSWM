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
- For research strategy, failed mechanisms, or route changes, next read
  `docs/canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md` and its KG
  projection
  `ontology/identity/hswm_core/HSWM_ADAPTIVE_RESEARCH_STRATEGY_ONTOLOGY.v1.json`
  (bundle UID
  `sym:AbstractNode:hswm-adaptive-research-strategy-ontology-2026-08-30`).
  The USER_PRIMARY commitment preserves the final fractal HSWM target and the
  importance of the user's eight stated research questions. Preserve the
  existing FCL-1..8 operational contracts and claim ceilings as SECONDARY_AI
  formalizations while allowing algorithms, methods, backends, testbeds, and
  the active research path to be replaced. A valid negative result retires or reroutes its exact
  mechanism family with evidence lineage intact; it neither shrinks the target
  nor counts as support for it. Never weaken a success criterion, delete a RED
  path, rename failure, or use downstream scale to rescue an upstream failure.
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

## Standard-first external tooling

- For graph interoperability, MCP, Skills, observability, and other external
  tooling, search the current official source before selecting an artifact.
  Prefer published standards, official SDKs, and official conformance suites.
  Keep candidate and draft standards in an explicitly non-promoting
  experimental lane.
- Prefer OpenAI system or curated Skills when one matches the task. Install a
  curated Skill only for a concrete use, at an immutable source revision. Do
  not install a community Skill merely because it appears in a catalog.
- Pin every downloaded package, repository, binary, or image by the applicable
  exact version, source commit, package integrity or artifact digest, and
  lockfile. Record its license and authority class. If an official SDK does not
  exist, label the selected independent implementation and qualify it against
  the official suite; do not present it as the standard authority.
- Use MCP for bounded live data, action, and authentication surfaces. Use
  Skills for reusable workflow instructions and supporting resources. An HSWM
  MCP must expose an exact capability allowlist and must not become a generic
  canonical-write, Permit, causal-admission, or learning path.
- Keep HSWM-owned adapters thin, typed, provenance-bound, and explicit about
  mapping loss and claim ceiling. Add one only where a suitable standard or
  vendor surface does not meet the required boundary.
- Treat the official MCP Registry as discovery metadata only. Never auto-trust,
  auto-install, or auto-run an entry; independently verify publisher, source
  revision, package or image digest, license, authentication, capabilities, and
  an isolated smoke test first.

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
- Before publishing or rendering Markdown math, use the portable subset
  (`\\mathrm{Name}` rather than `\\operatorname{Name}` and fenced `math`
  blocks rather than `\\[...\\]`) and run
  `uv run python scripts/compile_portable_markdown_math.py README.md INDEX.md docs/canon docs/research ontology`.
  Compile a derived projection for legacy or hash-bound sources; do not rewrite
  their recorded bytes solely for renderer compatibility.
