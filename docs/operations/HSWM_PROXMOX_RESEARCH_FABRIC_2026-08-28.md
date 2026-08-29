# HSWM Proxmox research fabric — 2026-08-28

> Status: `IMPLEMENTED_DEVELOPMENT_INFRASTRUCTURE / BOUNDED_PROJECTION`
>
> Claim boundary: this fabric improves execution, observation, replay, and
> agent legibility. It is **not** HSWM cognition, canonical atom authority,
> causal credit, continuous learning, or evidence that HSWM works.

## Canonical role and conceptual delta

HSWM remains one token-native LLM-function macro-neural network whose evolving
hypergraph is simultaneously living harness, world model, and continuous
learner. This deployment does not split that identity into harness, loop, and
graph subsystems and does not restore the retired fixed `H/W/A/F/Π` model.

The conceptual delta is narrower: the existing Proxmox fabric gains two
development projections that make token/tool trajectories and long-running
workflow execution easier to inspect and replay. An HSWM transition becomes a
canonical change only through the repository's schema-relative owner,
typed-reference, provenance, `Inv/Permit`, outcome, validation, and admission
contracts. A Phoenix trace, Temporal history, OpenObserve event, or Neo4j node
does not cross that boundary by existing.

| Surface | One bounded responsibility | Explicit non-claim |
|---|---|---|
| repository, `AGENTS.md`, CI | agent-legible harness projection and mechanical boundaries | not the living HSWM state by itself |
| Temporal development server | durable workflow-history and retry carrier for development loops | not outcome, causal credit, or `Learn_σ` |
| Phoenix | LLM/tool trajectory, dataset, experiment, and evaluation projection | not a sealed canonical trajectory or truth judge |
| OpenObserve CT302 | generic operational logs and traces | not HSWM memory or learning |
| canonical Neo4j on data-01 | bounded KG read/write projection | not HSWM cognition or canonical atom authority |
| code Neo4j CT300 | bounded source/code graph projection | not schema ownership or routing cognition |

This follows the practical harness-engineering lesson that agent-relevant
knowledge should be repository-local, versioned, discoverable, and backed by
mechanical boundaries ([OpenAI, *Harness engineering*](https://openai.com/index/harness-engineering/)).

## Current measured topology

The 2026-08-28 observation was made from `dev-01`, Proxmox CT307.

| Asset | Endpoint | Observed role/status |
|---|---|---|
| `dev-01` CT307 | `192.168.0.32` | HSWM checkout and development runtime |
| `openobserve-01` CT302 | `192.168.0.27:5081` | `/healthz` returned 200; generic observability authority |
| canonical Neo4j, data-01 VM200 | `192.168.0.25:7687` | TCP reachable; existing bounded KG projection |
| code Neo4j, CT300 | `192.168.0.19:7687` | TCP reachable; code graph projection |
| `grafana-mcp-01` CT304 | `192.168.0.29:9090` | TCP reachable; query interface |
| `ci-runner-01` CT303 | `192.168.0.28` | existing runner guest; not registered to this public repository at observation time |

The repository's ordinary and confirmatory GitHub workflows remain on
GitHub-hosted runners. A public repository must not send untrusted pull-request
code to a persistent self-hosted home-lab runner without a separate trust gate.

The canonical Neo4j HTTP discovery endpoint reports Community `2026.02.3`.
There is no graph-engineering reason to install a competing database beside it.
Projectors should use fork-safe identity properties and uniqueness constraints,
then keep schema admission and richer invariants in HSWM's application boundary.
Neo4j documents that Community supports property uniqueness but several
existence/type/key constraints are Enterprise-only
([Cypher constraints](https://neo4j.com/docs/cypher-manual/current/schema/constraints/)).
It also limits Community to offline database backup while online backup is an
Enterprise capability
([Neo4j backup and restore](https://neo4j.com/docs/operations-manual/current/backup-restore/)).
That makes the existing independent-backup gap an operations gate, not a reason
to mistake a second graph database for redundancy.

## Installed development services

Both new services run as the unprivileged `lagyeongjun` user inside CT307 and
inherit a small environment allowlist; session and model-provider credentials
are not inherited. Temporal and Phoenix HTTP bind only to loopback. Phoenix
20.4.0's gRPC collector binds its port on all interfaces upstream, so Phoenix
authentication is enabled and a generated admin bearer secret protects both
collectors. HTTP/OTLP on loopback remains the preferred ingestion path.

| Service | Pinned version | Local endpoints | Persistent state |
|---|---|---|---|
| Temporal CLI | `1.8.2` (embedded server `1.31.2`, UI `2.50.1`) | gRPC `127.0.0.1:7233`, HTTP `:7243`, UI `:8233`, metrics `:9464` | `~/.local/state/hswm-research-fabric/temporal/temporal.db` |
| Arize Phoenix | `20.4.0` | UI and OTLP/HTTP `127.0.0.1:6006`, OTLP/gRPC `:4317` | `~/.local/state/hswm-research-fabric/phoenix/` |

Temporal documents durable execution as resuming work after failures, but its
local `start-dev` server explicitly is not a production deployment
([Temporal documentation](https://docs.temporal.io/)). Phoenix supports
OpenTelemetry/OpenInference tracing, evaluations, datasets, and experiments
([Phoenix overview](https://arize.com/docs/phoenix/)); its official deployment
guidance classifies SQLite as local/single-user and PostgreSQL as the production
backend ([Phoenix self-hosting architecture](https://arize.com/docs/phoenix/self-hosting/architecture)).

Phoenix defaults used here:

- `PHOENIX_HOST=127.0.0.1`
- `PHOENIX_WORKING_DIR=~/.local/state/hswm-research-fabric/phoenix`
- `PHOENIX_ENABLE_AUTH=true`
- `PHOENIX_TELEMETRY_ENABLED=false`
- `PHOENIX_ALLOW_EXTERNAL_RESOURCES=false`
- `PHOENIX_ALLOWED_PROVIDERS=NONE`
- `PHOENIX_ENABLE_MCP_SERVER=true`
- `PHOENIX_ENABLE_MCP_CODE_MODE=false`
- `PHOENIX_ENABLE_OAUTH2_AUTHORIZATION_SERVER=false`
- `PHOENIX_OAUTH2_DYNAMIC_CLIENT_REGISTRATION=disabled`

The privacy settings keep the UI from sending analytics, loading external
resources, or initiating model-provider calls. The MCP settings expose the
authenticated Streamable HTTP endpoint without a model-visible code executor
or an interactive OAuth registration surface. Phoenix documents both the
telemetry opt-out and air-gapped controls in its
[privacy guidance](https://arize.com/docs/phoenix/self-hosting/security/privacy).

## Operation

From the HSWM checkout:

```bash
uv run --locked hswm-research-fabric start
uv run --locked hswm-research-fabric status
uv run --locked hswm-research-fabric doctor
uv run --locked hswm-research-fabric stop
```

The same launcher is installed and enabled as the lingering user unit
`hswm-research-fabric.service`, so the development fabric returns after CT307
reboots. Inspect or restart it with:

```bash
systemctl --user status hswm-research-fabric.service
systemctl --user restart hswm-research-fabric.service
```

The launcher refuses to replace an untracked listener, binds the process record
to PID start time and executable SHA-256, rejects pinned-version drift, and
signals only the tracked process group. Logs and process records live below
`~/.local/state/hswm-research-fabric/`.
The generated Phoenix JWT/admin secrets live only in
`~/.local/state/hswm-research-fabric/secrets/phoenix.json` with mode `0600`;
the process receipt, logs, repository, and smoke output do not contain them.

## AI-native research tools applied on 2026-08-29

### Phoenix VIEWER MCP for Codex

Phoenix has one dedicated local `VIEWER` identity for Codex. Its API key and
rotation password live only in
`~/.local/state/hswm-research-fabric/secrets/phoenix-mcp-viewer.json` with mode
`0600`. The Codex configuration contains no token. Instead, the mode-`0700`
stdio launcher `~/.local/libexec/hswm-phoenix-viewer-mcp` reads that secret and
proxies to `http://127.0.0.1:6006/mcp`. The launcher verifies the SHA-256 of a
reviewed installed module copy before executing it inside Phoenix `20.4.0`'s
installed environment; that module also fails closed unless the observed
`fastmcp-slim` version is exactly `3.4.7`.

The trusted project config `.codex/config.toml` registers the optional Codex
server `hswm_phoenix_ro`. Its client allowlist is:

```text
describeSqlSchema
executeSql
getProjects
getProject
```

`executeSql` is Phoenix's analytics-only SQL tool: it admits read-only `SELECT`
against an allowlisted telemetry/dataset/experiment schema and applies row,
response-byte, and statement-time bounds. Defense is layered:

1. Phoenix authenticates the dedicated principal as `VIEWER` and rejects REST
   mutation probes with HTTP 403.
2. Phoenix MCP code mode is disabled, so there is no general `execute` sandbox.
3. The stdio server itself registers exactly the four read tools above; project
   create/update/delete and progressive disclosure tools do not exist on that
   server surface.
4. Codex repeats the same four-name allowlist as defense in depth.
5. The token is absent from argv, repository files, process receipts, and Codex
   TOML.

Provisioning and non-secret validation are repeatable:

```bash
uv run python -m hswm.infrastructure.phoenix_mcp_viewer provision
uv run python -m hswm.infrastructure.phoenix_mcp_viewer validate
uv run --locked --script \
  _research/infrastructure_smoke/phoenix_viewer_mcp_smoke.py
codex mcp get hswm_phoenix_ro
```

Codex loads MCP inventory at session start, so an already-running session does
not gain this tool dynamically; start a new Codex session after registration.
The stdio proxy is intentional: Codex supports both local stdio and Streamable
HTTP MCP servers, while the proxy keeps bearer material out of client config
([OpenAI MCP documentation](https://developers.openai.com/codex/mcp/)). Phoenix
documents the `VIEWER` role as read-only for ordinary API mutation routes and
supports API-key authentication for integrations
([Phoenix authentication](https://arize.com/docs/phoenix/self-hosting/security/authentication)).

### Inspect AI as an outer evaluator

`~/.local/bin/hswm-inspect-outer` launches a direct-version-pinned
`inspect-ai==0.3.260` no-model preflight through `uvx`; it does not expose a
generic `inspect eval` pass-through or add Inspect's dependency graph to the
historically bound repository `uv.lock`. The preflight uses a
credential-minimal environment and records hashes rather than CLI output. The
host launcher also verifies the SHA-256 of its reviewed installed module copy
before execution:

```bash
uv run python -m hswm.evaluation.inspect_outer_runner
hswm-inspect-outer
```

An actual Inspect evaluation is intentionally not authorized by this launcher.
A later protocol may use Inspect only for a frozen task or already closed
immutable logs under a distinct analysis-run identity; it must explicitly bind
its credential and model surface and forbid DNRD wrapping, source-run
retry/resume, HSWM provider dispatch, and score-to-admission conversion.
Inspect's task, solver, scorer, log, and eval-set concepts are documented in the
[Inspect AI documentation](https://inspect.aisi.org.uk/).

### Neo4j MCP decision

The canonical database was re-probed as Neo4j Community `2026.02.3`. Community
does not provide the role/privilege commands needed to give a general Cypher
MCP a database-enforced reader identity. Consequently, the existing
`ontology` MCP remains the only Codex canonical-KG interface, with its four
predeclared and sensitivity-filtered read tools:

```text
ontology_search
ontology_get
ontology_neighbors
ontology_claim_history
```

The official Neo4j MCP's read-only classifier was tested separately with an
exact pin, including rejection of `CREATE`, but it was deliberately not
registered against canonical data because the underlying credential would
still retain publisher power. General `read-cypher` remains gated on a
database-enforced reader, a read replica, or another independently bounded
projection. This follows the server's own defense-in-depth guidance rather than
treating a query classifier as a substitute for database authorization
([Neo4j MCP tools](https://neo4j.com/docs/mcp/current/tools/),
[Neo4j MCP configuration](https://neo4j.com/docs/mcp/current/configuration/)).

To see the UIs from another machine, use an SSH tunnel rather than opening the
unauthenticated development ports to the LAN:

```bash
ssh -L 6006:127.0.0.1:6006 -L 8233:127.0.0.1:8233 dev
```

Then open `http://127.0.0.1:6006` and `http://127.0.0.1:8233` locally.

Run one no-secret infrastructure smoke:

```bash
uv run --locked --script \
  _research/infrastructure_smoke/research_fabric_smoke.py
```

The smoke starts one Temporal workflow/activity and emits one Phoenix span. Its
payload contains only a generated run ID, bounded status, and content hash. It
does not record prompts, completions, credentials, private data, an HSWM
outcome, or a canonical revision. Phoenix's OTEL integration is documented at
[Setup OTEL](https://www.arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel).
Its PEP 723 dependencies and adjacent script lock are intentionally isolated
from the repository root `uv.lock`, whose historical SWM-0W evidence binding
must remain byte-exact.

## Instrumentation contract for later HSWM work

Use one root span per bounded run and preserve correlation across workflow,
messages, model/tool spans, external outcome, and any later admission proposal.
OpenTelemetry's current GenAI conventions remain in motion, so pin emitted
convention versions and do not silently rename fields; message producer and
consumer traces should propagate or link their creation context
([OpenTelemetry messaging spans](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/)).

Minimum low-cardinality correlation fields:

```text
hswm.run.id
hswm.schema.version
hswm.trajectory.uid
hswm.atom.uid                 # only when an admitted atom actually exists
hswm.owner.responsibility     # responsibility address, not authorization
hswm.outcome.ref              # reference only; never infer PASS from trace status
hswm.effect.receipt.ref
hswm.projection.kind
service.name / service.version / deployment.environment.name
```

Prompt, completion, raw tool output, datasets, secrets, and personal data are
opt-in fields. A span status of `OK`, a completed Temporal workflow, or a passing
evaluator is operational evidence only. It cannot synthesize current permission,
seal a trajectory retroactively, or admit a canonical revision.

## Production promotion gates

Do not call the current pair production. Promotion requires a separate
operator-authorized Proxmox change with at least:

1. dedicated guest ownership rather than co-location in CT307;
2. authenticated TLS endpoints and explicit ingress policy;
3. PostgreSQL-backed Phoenix and a supported multi-service Temporal deployment;
4. backup and tested restore on independent physical storage;
5. retention, capacity, secret rotation, and upgrade/rollback contracts;
6. immutable desired-state manifest versus live observation receipts;
7. explicit mapping from histories/traces to schema-approved atom kinds,
   exactly one schema-relative responsibility owner, typed references, and a
   separately validated outcome/admission transition.

No remote Neo4j write, OpenObserve cutover, CI-runner registration, public
ingress change, or research-result receipt was performed in this installation.

## As-built validation

The 2026-08-28 installation closed with these bounded observations:

- launcher unit tests: `4 passed`;
- Phoenix `20.4.0` and Temporal CLI `1.8.2` version checks matched;
- Temporal executable SHA-256 matched the pinned installed binary;
- `doctor`: both new services and all four existing dependency endpoints ready;
- one Temporal workflow/activity completed and remained queryable after restart;
- one Phoenix span remained queryable after restart;
- an unauthenticated OTLP/gRPC request to the wildcard collector was rejected as
  `UNAUTHENTICATED`;
- the lingering user systemd unit was enabled and its process cgroup contained
  only the tracked Phoenix and Temporal processes.

These are infrastructure checks, not material HSWM research results, so no
content-addressed research receipt or `F1_R8_RESULTS_LOG.md` entry was created.

The 2026-08-29 AI-native extension additionally closed with:

- dedicated Phoenix `VIEWER`: read probe 200 and mutation probe 403;
- Phoenix MCP code mode disabled and OAuth authorization server disabled;
- authenticated Streamable HTTP and secret-free stdio-proxy handshakes passed;
- analytics `SELECT 1` returned one row through both transports;
- analytics `CREATE TABLE` was refused as unsupported syntax before execution;
- Codex reported the exact four-tool Phoenix allowlist;
- Inspect `0.3.260` no-model preflight and direct-version-pinned launcher passed;
- canonical Neo4j remained unchanged and no general Cypher MCP was registered.
