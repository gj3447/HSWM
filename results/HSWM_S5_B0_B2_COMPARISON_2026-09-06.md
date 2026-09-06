# S-5 first B0/B2 results — descriptive comparison

Both frozen successor occurrences completed all 12 episodes, and both scored
0/4 on descriptive `valid_seen`. B0 is classified
`FLOOR_OR_INSTRUMENT_REPAIR` by its preregistered rule. These observations
establish neither a useful calibrated headroom nor an effect of text lessons.

| Observed quantity | B0 successor v2 | B2 text-lesson v3 |
|---|---:|---:|
| Train successes / completed | 0/8 | 1/8 |
| `valid_seen` successes / completed | 0/4 | 0/4 |
| Completed / scheduled episodes | 12/12 | 12/12 |
| Environment actions | 240 | 225 |
| Action tokenize / completion POSTs | 240 / 240 | 225 / 225 |
| Reflection tokenize / completion POSTs | 0 / 0 | 1 / 1 |
| Total HTTP POSTs | 480 | 452 |
| Action input / output tokens | 179468 / 4265 | 192489 / 3838 |
| Reflection input / output tokens | 0 / 0 | 739 / 31 |
| Frozen retained lessons at evaluation | none (stateless) | 1 |
| `valid_unseen` selected | 0 | 0 |

The [B0 result](HSWM_ALFWORLD_B0_SUCCESSOR_RESULTS_2026-09-06.md) and
[B2 result](HSWM_EXPEL_B2_TEXT_LESSON_V3_RESULTS_2026-09-06.md) link their
frozen protocols, content-addressed evidence, public receipts and verified
private-archive aggregates. B0's missing wrapper aggregates are explicitly
reconstructed as a posthoc projection; the original receipt is preserved.
Earlier B0 and B2 failures remain in their separate result/evidence records.

The occurrences use the same pinned model, image, GB10 and qualified
PDDL-only runtime, with separately selected cohorts. B0 is stateless; B2 is
an ExpeL-inspired lesson-only external comparator, not direct ExpeL or HSWM
learning. Their selection policies and budgets differ: B0 permits 240 POSTs
per phase; B2 permits 240 action plus 8 reflection POSTs per phase. They are
unpaired and not budget-matched. No causal gain, ranking, or efficacy estimate
is inferred; `valid_seen` is not a final held-out estimate.

S-5 is complete as the closure plan's first-result-file deliverable, including
the material F1_R8 entries. This does not reopen D-3's binding G1 estimand or
close D-4. G0 is `NOT_PASSED`, G1 is `NOT_EVALUATED`, and S-6 remains open for
the second-party decision. The global claim ceiling is unchanged.
