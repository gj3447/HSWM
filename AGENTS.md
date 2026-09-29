# HSWM working rules

Keep work proportional to the request. The default is: inspect the relevant
files, make the change, run focused checks, and record the result in Git.
The [research workflow](docs/operations/HSWM_RESEARCH_WORKFLOW.md) is the current
engineering entrypoint; it supersedes older mandatory development ceremonies.

The user has already supplied HSWM's target and philosophy. Resolve research
and implementation unknowns through source review, search, and bounded work;
do not ask the user to restate the direction or stop at an unfinished-status
report when the next authorized step can be carried out.

## Research identity

- HSWM targets one large AI organized as a hypergraph neural network, with LLM
  functions as its basic computation and hypergraph Semantic Weight as its
  operating mechanism. The graph is the AI state; LLMs act on local inputs.
  Living harness, world model, and continuous learner are roles of this one AI.
- Learning revises canonical graph state and graph-resident programs. TS/Effect
  is the versioned interpreter and I/O implementation; routine learning does not
  edit its source. Preserve this distinction when designing query/tool interfaces.
- For identity or architecture changes, start with the
  [constitution](docs/canon/HSWM_CONSTITUTION_2026-08-20.md),
  [user definition](docs/canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md),
  and [state/operator definition](docs/canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md).
  Otherwise read only the topic-specific sources needed for the task, linked
  from the research workflow. Routine fixes do not require a canon read-through.
- Preserve the fractal HSWM target, CR-0..7/FCL-1..8 research obligations, and
  negative results. Methods and backends may change; success criteria and past
  failures must not be rewritten to claim success. Distinguish user direction,
  AI interpretation, formal assumptions, and measured evidence.
- Include OpenCog Hyperon in architecture, novelty, and empirical comparisons,
  at explicit component versions and maturity. This does not require adopting it.
  Tests, repository KG, and MCP interfaces alone do not establish HSWM efficacy.

## Graph engineering

- Reuse the existing RDF 1.1, SHACL 1.0, SPARQL 1.1, JSON-LD 1.1, and PROV-O
  tooling for graph exchange, validation, queries, and provenance. Check official
  documentation when selecting or changing a standard or external dependency.
- Use stable identifiers, explicit types, versioned schemas, and source links.
  Preserve n-ary relation identity, participant roles, order, context, and
  exceptions through incidence/relation nodes; document any projection loss.
  A graph projection is a view, not an implicit canonical-state write path.
- Canonical runtime changes follow the existing schema, single responsibility
  owner per atom version, revision lineage, and outcome-bound learning model.
  Do not reintroduce the retired fixed `H/W/A/F/Π` decomposition.
- Prefer existing libraries and thin adapters. Lock adopted dependencies and
  record their source and license in the existing manifests. Run full standards
  qualification when its implementation/profile changes, not for routine edits.
  MCP tools keep explicit capabilities and authentication; registry listings are
  discovery metadata, not permission to install or execute.

## Development

- New runtime code uses pure immutable TypeScript domain functions and Effect
  services for I/O under `src/hswm/`. Use existing test locations, `_research/`
  for experiments, and typed document/artifact directories; keep generated files
  out of the repository root.
- Run checks relevant to the changed behavior, schema, query, or document.
  Follow the applicable CI checks; a wrapper's selected profile is not a ceiling.
  Local development does not require a graph server, full-suite replay, or GPU.
- `hswm-dev hswm plan/run/status/feedback` is optional for studying or using the
  adaptive development workflow. Direct npm/uv commands are supported. If used,
  keep state private and label agent judgments `agent(<tool>):...`; a passing
  check is not automatically useful feedback or causal credit.
- Use Git and a concise validation note for routine code/docs/environment work.
  Add source-bound KG snapshots and content-addressed research receipts when
  publishing material research results; preserve their predecessors and record
  those results in `F1_R8_RESULTS_LOG.md`. Do not add approval gates or ledgers.
- Preserve unrelated changes, public compatibility, historical evidence, and
  private data. Do not refresh old hashes to hide drift. Moving a path listed in
  `ontology/history/ROOT_COMPATIBILITY_BASELINE.v1.json` requires its source-pinned
  compatibility manifest. Maintainer work normally verifies, commits, and pushes
  to the current canonical branch; respect the active contributor/PR workflow.
- Use the documented local npm/uv environment. Mac/DGX heavy runs use
  `~/bin/hswm-run`; DGX is scratch, data-01 durable, and `/Volumes/GM` read-only.
  Keep credentials, private datasets, and model artifacts out of public commits.
- For Markdown math, use `\\mathrm{Name}` and fenced `math` blocks. Compile the
  changed documents with `scripts/compile_portable_markdown_math.py`; use derived
  projections for hash-bound sources instead of changing historical bytes.
