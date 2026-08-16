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

New Python implementation belongs under [`src/hswm/`](../src/hswm/). Root
Python modules are a shrinking, explicitly frozen compatibility surface; each
completed move is source-pinned by the manifests in [`history/`](history/).
Every remaining root module has exactly one reason class in
[`PYTHON_ROOT_CLASSIFICATION.v1.json`](history/PYTHON_ROOT_CLASSIFICATION.v1.json).

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
| [`history/`](history/) | Why do some legacy root paths remain frozen? |

The machine-readable graph is
[`HSWM_REPOSITORY_ONTOLOGY.v1.json`](HSWM_REPOSITORY_ONTOLOGY.v1.json). Its
generated path projection is
[`HSWM_PATH_CATALOG.v1.json`](HSWM_PATH_CATALOG.v1.json). Validate both with:

```bash
uv run --locked python scripts/validate_repository_ontology.py
```

## Important boundary

This ontology organizes source and evidence; it is not a hand-written AI
behavior rulebook. HSWM behavior is intended to be learned from outcome-bound
token/action/tool trajectories through durable `W`, routing, and `H` changes.
Turning these folders into another growing set of mandatory cognitive rules
would reproduce LX3 Ragnarok rather than solve it.
