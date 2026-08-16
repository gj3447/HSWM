# HSWM working rules

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
