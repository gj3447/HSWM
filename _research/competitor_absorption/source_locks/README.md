# Competitor source locks

This directory publishes the compact provenance needed by HSWM's paper/code
absorption gate. It intentionally does **not** vendor third-party repositories,
paper PDFs, extracted text, models, datasets, or generated outputs.

- [`repos.lock.tsv`](repos.lock.tsv) pins 11 upstream repositories to full Git
  commits and records the branch used for the original shallow checkout.
- [`papers.lock.tsv`](papers.lock.tsv) pins 11 primary papers by source URL,
  identifier, page count, and SHA-256. HippoRAG has two lineage papers; the
  Graphiti and Zep repositories share the Zep temporal-KG paper.

The original read-only bundle was collected on 2026-07-23. Each repository was
a clean `--depth 1 --single-branch --no-tags --filter=blob:none` checkout at the
recorded commit. All PDFs parsed, produced non-empty text, and had their first
page rendered for identity review. No dependency, model, dataset, or service was
installed as part of source locking.

For a full local replay, construct a bundle directory with each code checkout at
`<bundle>/<name>/`, and papers at the `local_pdf` and `local_text` paths beneath
`<bundle>/papers/`. Then run:

```bash
python3 _research/competitor_absorption/verify_sources.py \
  --bundle-root /absolute/path/to/HSWM_COMPETITORS
```

Without `--bundle-root`, the validator still checks the committed manifest,
lock-table coverage, baseline ancestry, licensing policy, and inactive deployment
defaults. Supplying a missing or incomplete bundle fails closed.

Absence of a license file is not permission to reuse code. HGRAG and T-GRAG are
reference-only clean-room inputs; SiReRAG is CC BY-NC 4.0 and is likewise never
copied into HSWM. See the
[`PAPER_CODE_ABSORPTION_LEDGER_2026-07-23.md`](../../../PAPER_CODE_ABSORPTION_LEDGER_2026-07-23.md)
for the per-candidate disposition and falsifier.
