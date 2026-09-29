# HSWM — agent entry

Keep human canon, graph-resident AI state, interpreter code and measured evidence distinct. Preserve negative results and other writers.

Detailed owner rules: [OWNER.md](docs/agent-rules/OWNER.md).
Task/source graph: [routes.json](docs/agent-rules/routes.json).

Use the shared `instruction-routing` skill: call `instruction_routes` for this
repository, applicable tasks and target paths, then `instruction_read` until all
selected sections are complete. `edit` applies before any file change; add
`docs`, `code`, `kg`, `research`, `cli`, `infra`, `deploy` or `hswm` as applicable.
Load specialized skills only when their task is active. Reroute on scope changes.

Without the shared tool, follow the local graph's `REQUIRES`/`EXTENDS` edges and
read those sections directly. Never truncate selected rules. Nested instructions
and explicit user decisions retain precedence. Routes do not grant permission.
Inline paths/commands in OWNER.md are relative to this repository root.
