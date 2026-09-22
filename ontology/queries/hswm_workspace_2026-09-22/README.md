# Workspace snapshot queries

These queries inspect the dated workspace metadata projection. They do not merge the underlying research nodes or execute a documented workflow.

From the repository root:

```bash
src/hswm/effect-runtime/bin/hswm-kg-bundle query \
  --source workspace=ontology/development/HSWM_KG_WORKSPACE_2026-09-22.v1.json \
  --profile v2 \
  --query ontology/queries/hswm_workspace_2026-09-22/entrypoints.rq

node _research/hswm_workspace_2026-09-22/verify.mjs
```

| Query | Inspects |
|---|---|
| `entrypoints.rq` | Curated document and bundle entrypoints |
| `bundle_binding_summaries.rq` | Each captured bundle occurrence and worktree binding comparison counts |
| `duplicate_uid_occurrences.rq` | Repeated UIDs, preserving each source-bundle occurrence |
| `command_surfaces.rq` | Documented commands, writable destinations and network boundaries |
| `unresolved_drift_observations.rq` | Non-matching/unread bindings, without declaring historical corruption |

The dynamic checkout interface is `src/hswm/effect-runtime/bin/hswm-workspace`.
See the [operations guide](../../../docs/operations/HSWM_KG_WORKSPACE_2026-09-22.md) for all commands and the explicit `SOURCE_ONLY` historical profile.
