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

The last three settings keep the UI from sending analytics, loading external
resources, or initiating model-provider calls. Phoenix documents both the
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

To see the UIs from another machine, use an SSH tunnel rather than opening the
unauthenticated development ports to the LAN:

```bash
ssh -L 6006:127.0.0.1:6006 -L 8233:127.0.0.1:8233 dev
```

Then open `http://127.0.0.1:6006` and `http://127.0.0.1:8233` locally.

Run one no-secret infrastructure smoke:

```bash
uv run --locked --extra research-infra \
  python _research/infrastructure_smoke/research_fabric_smoke.py
```

The smoke starts one Temporal workflow/activity and emits one Phoenix span. Its
payload contains only a generated run ID, bounded status, and content hash. It
does not record prompts, completions, credentials, private data, an HSWM
outcome, or a canonical revision. Phoenix's OTEL integration is documented at
[Setup OTEL](https://www.arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel).

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
