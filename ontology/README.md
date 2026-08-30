# HSWM repository ontology

This directory is the semantic front door to the repository. The filesystem
still has one physical location per file, but an ontology can give the same
file several meanings and connect it to several neighboring concepts.

The repository therefore uses two compatible views:

- the **physical view** preserves imports, packages, and path/SHA-bound research
  evidence;
- the **ontology view** says what each path means and how it participates in
  HSWM, without copying it or pretending that a folder tree is the cognitive
  system itself.

New Python implementation belongs under [`src/hswm/`](../src/hswm/). The root
contains only public entry files. The final 93 root-era compatibility sources
live together in the closed
[`_research/root_compat/`](../_research/root_compat/) cluster so flat imports and
same-directory bindings remain intact. Their reasons are frozen in
[`ROOT_COMPATIBILITY_BASELINE.v1.json`](history/ROOT_COMPATIBILITY_BASELINE.v1.json).
Their canonical destinations are source-pinned by the final
[`Python`](history/PYTHON_ROOT_MIGRATIONS.FINAL.v2.json) and
[`asset`](history/ROOT_ASSET_MIGRATIONS.FINAL.v1.json) manifests. Published old
commands can be recovered without polluting the active checkout with
`uv run hswm-legacy-replay materialize OLD_ROOT_FILE /tmp/hswm-replay`.

## Concept map

| concept | question it answers |
|---|---|
| [`identity/`](identity/) | What is HSWM and why does it exist? |
| [`substrate/`](substrate/) | What durable world and provenance can it remember? |
| [`field/`](field/) | What are `H`, `W`, `A`, topology, and the optional sheaf lens? |
| [`cells/`](cells/) | How do local LLM functions communicate through ports? |
| [`learning/`](learning/) | When do trajectories become durable learned coordination? |
| [`boundary/`](boundary/) | Which thin deterministic constraints remain fixed? |
| [`evaluation/`](evaluation/) | How are claims falsified and behavior changes measured? |
| [`evidence/`](evidence/) | Where are preregistrations, manifests, results, and receipts? |
| [`infrastructure/`](infrastructure/) | What builds, validates, packages, and documents the repository? |
| [`history/`](history/) | How are root-era paths, digests, and detached replay preserved? |

The machine-readable concept graph is
[`HSWM_REPOSITORY_ONTOLOGY.v1.json`](HSWM_REPOSITORY_ONTOLOGY.v1.json). It
defines concepts and relationships; the filesystem and typed-directory
conventions remain the source of truth for current paths. A checked-in catalog
of every repository path is intentionally not part of this navigation layer.

The cross-cutting research rule is defined by the
[`adaptive research strategy canon`](../docs/canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)
and its
[`typed KG projection`](identity/hswm_core/HSWM_ADAPTIVE_RESEARCH_STRATEGY_ONTOLOGY.v1.json):
the USER_PRIMARY final fractal target and eight stated research questions stay
in scope. Existing FCL-1..8 operational contracts and claim ceilings remain
SECONDARY_AI formalizations and stay unchanged or stronger, while concrete
algorithms, methods, models, backends, testbeds, and paths remain replaceable.
RED evidence is preserved and successor routes keep the same or stronger controls. This
crosses identity, learning, evaluation, and evidence without turning every
repository file into a KG node.

## Important boundary

This ontology organizes source and evidence; it is not a hand-written AI
behavior rulebook. HSWM behavior is intended to be learned from outcome-bound
token/action/tool trajectories through durable `W`, routing, and `H` changes.
Turning these folders into another growing set of mandatory cognitive rules
would reproduce LX3 Ragnarok rather than solve it.
