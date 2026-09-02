---
name: hswm-research-readout
description: Produce an evidence-bounded target/current/delta readout for HSWM architecture, research-direction, or scientific-status questions in this repository. Do not use for routine coding, test repair, or generic repository summaries.
---

# HSWM Research Readout

Produce a repository-grounded research readout. This Skill is a bounded
projection and procedure prior, not HSWM cognition, a certified HSWM state
readout, or evidence of continuous learning.

## Observation cut

Work read-only unless the user separately requests a mutation.

Record the UTC date, HEAD commit, branch, and `git status --short`. Treat dirty
or untracked material as preliminary. When a relevant authoritative file is
dirty, distinguish its working-tree content from the checked-in version.

## Authority and evidence

1. Read the applicable `AGENTS.md` instructions.
2. Read `docs/canon/HSWM_CONSTITUTION_2026-08-20.md` completely.
3. Locate only the task-specific canon with `rg`; do not load unrelated files.
4. For current scientific status, inspect the header, bottom line, exact claim
   table, and relevant sections of `EFFICACY.md`.
5. When empirical status matters, follow the repository runtime rules and run
   `uv run hswm-verify-efficacy --pretty`; inspect the receipts it links.
6. Treat code and tests as implementation or conformance evidence unless an
   independently measured outcome supports a stronger claim.
7. Treat ontology and MCP results as navigation or bounded projections. Prefer
   their source-pinned repository files for authority.
8. Treat operations handoffs and unadjudicated artifacts as engineering state
   or preliminary evidence, not scientific promotion.

Classify material statements as exactly one of:

- `TARGET_IDENTITY`
- `DIRECT_EVIDENCE`
- `INFERENCE`
- `OPEN_OR_UNJUDGED`

Never silently promote a statement between classes.

## Readout

Lead with one bounded verdict. Then report only the useful parts:

- canonical target role;
- current direct evidence and its observation cut;
- conceptual delta;
- mapping to schema-approved canonical atom kinds, exactly one schema-relative
  responsibility owner per atom, typed references, provenance-bound
  transitions, and the outcome-bound causal-learning loop;
- present and missing links in the outcome-bound learning loop;
- the next decisive falsifier, gate, or implementation step;
- explicit non-claims.

For a proposed Skill, MCP, agent workflow, document, or implementation, answer
the four questions in Constitution section 9 before recommending a mutation.

## Boundaries

Do not equate repository state, KG, RAG, MCP, prompts, Skills, transcripts,
passing tests, or stored telemetry with HSWM cognition or learning.

Do not claim durable learning without this complete causal chain:

```text
external attributable outcome → eligibility and causal credit
→ versioned canonical atom/relation/transition-disposition candidate delta
→ fresh/retention/canary/removal validation
→ accepted state that changes a later activation
```

Do not create a research receipt or edit `F1_R8_RESULTS_LOG.md` for an ordinary
readout or Skill validation.
