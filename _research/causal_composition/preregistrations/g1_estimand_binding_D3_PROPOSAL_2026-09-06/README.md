# D-3 — G1 estimand binding proposal (S-4 deliverable, awaiting USER_PRIMARY)

Status: `PROPOSED_AWAITING_USER_PRIMARY / OPTION_A_RECOMMENDED / NOT_A_PREREGISTRATION`.
Closure step: S-4 of the
[closure plan](../../../../docs/research/HSWM_ADVERSARIAL_AUDIT_AND_CLOSURE_PLAN_2026-09-05.md),
run-by 2026-09-08.  Gap closed on ratification: GAP-4.

This file prepares the decision; it does not take it.  D-3 becomes binding
only when the user's own sentence is appended to a
`docs/canon/sources/USER_PRIMARY_HSWM_CLOSURE_DECISIONS_<date>.txt` source and
the closure-plan bundle records the ratification as an event version.

## 1. The contradiction to close (GAP-4)

| Document | What it requires of G1 |
|---|---|
| `_research/causal_composition/project.v1.json` (`pass_rule`) | fresh-task gain; remove eliminates; restore recovers; sham and shuffled credit fail; compiled traversal mediation |
| viability assessment, line 115 | held-out gain larger than an information-matched text lesson |
| v2 results document, line 165 | "better than the strongest inherited baseline" is not yet an executable decision rule |

The audit's finding 2 (`hswm-delta-is-governance-not-behavior`, CONTESTED)
established that the structural-impossibility claim was refuted because the
binding `pass_rule` asks for mediation, not for beating B2.  What survives is
the cross-document contradiction above and the absence of any paragraph that
says why an owner-valid canonical revision should outperform an
information-matched text lesson.

## 2. Option A (recommended): the `pass_rule` is the binding estimand

Proposed D-3 sentence (unchanged from the closure plan; the user may adopt,
modify, or reject it):

> G1의 binding estimand는 `project.v1.json`의 pass_rule(fresh-task gain,
> remove/restore, sham/shuffled credit, compiled mediation)이다. ExpeL B2와
> ALFWorld B0 비교는 secondary ceiling comparator로 두고, H1이 B2보다 나아야
> 하는 기전 문단이 쓰여지기 전까지 primary estimand에 포함하지 않는다.

Consequences if ratified:

- the viability line 115 and the v2 results line 165 are read as secondary
  ceiling statements, not as G1 pass criteria; no document is rewritten
  (hash-bound records stay), the ratification source carries the precedence;
- S-5 (first B0 and B2 result files) stays on the plan as a ceiling measurement
  with its own stop rule ("comparator failure does not reopen the estimand");
- opaque v3 (S-3) is analysed under the `pass_rule` only.

## 3. Option B: a prospective mechanism paragraph for H1 over B2

The closure plan's candidate paragraph:

> cue-indexed compiled projection은 global rule-list interference 없이 정확히 한
> disposition만 readset에 넣으므로, 규칙 수가 늘수록 text lesson의 retrieval
> 오류율보다 낮은 오적용률을 가진다.

Why it cannot be written as a prospective hypothesis today:

1. **The channel is identical.** In the current instrument the compiled
   disposition reaches the model only as prompt text (`compile_disposition`),
   exactly as a text lesson would.  The paragraph's mechanism (no rule-list
   interference) is a property of the retrieval step, and an
   information-matched text lesson with the same cue-indexed retrieval is a
   legitimate B2 configuration, so the paragraph predicts a tie against the
   matched baseline and a win only against a deliberately weakened one.
2. **No rule count varies.** v3 admits at most one disposition per episode
   (32 episodes, 10 calls); the paragraph's predicted effect grows with the
   number of rules, which the instrument holds at one.  A test of the
   paragraph needs a rule-count sweep that no preregistration defines.
3. **The estimand would become comparative before any absolute effect
   exists.** G1's `pass_rule` has never produced a PASS; making "beats B2"
   primary before a single mediated effect is observed inverts the
   closure order (finding 3, substrate before loop).

The S-4 stop rule therefore applies: if no mechanism paragraph can be written
as a prospective hypothesis, option A is binding.  Option B remains available
later as a **new** preregistered hypothesis with a rule-count sweep, after a
`pass_rule` PASS exists; nothing here forbids it.

## 4. What ratification requires from the user

One sentence, in the user's own words, either:

- "D-3 확정" with the option A sentence above (recommended), or
- a modified sentence (recorded as `MODIFIED` with the modification bound), or
- "D-3 기각" (recorded as `REJECTED`; GAP-4 stays open and S-5 is blocked by
  its own stop rule).

Verification after ratification:

```bash
uv run --locked --extra dev pytest -q tests/test_hswm_closure_plan.py
uv run --locked --extra dev python scripts/build_hswm_closure_plan_ontology.py --check
```

## 5. Claim boundary

This proposal is SECONDARY_AI analysis of existing documents.  It is not a
preregistration, not a G0 or G1 result, and not evidence about HSWM.  The v3
instrument, the comparators, and the fractal status are unchanged by it.
