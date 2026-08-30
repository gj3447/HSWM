# Macro-learning

The intended analogy is one level above transformer training:

| transformer training | HSWM macro-training |
|---|---|
| training corpus | token, action, tool-use, and outcome trajectories |
| model parameters | durable `W`, routing policy, and `H` topology |
| objective and optimizer | external outcome, eligibility, credit, and bounded update |
| forward pass | recurrent coalition of LLM function cells |
| held-out validation | fresh/equal-budget evaluation and removal ablation |

Tokens are observations, not learned rules by themselves. Only an
outcome-linked update that becomes durable, changes later behavior, and loses
its effect when removed counts as evidence of learning.

See the [canonical direction](../../docs/canon/USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md)
and the executable
[`token_learning_contract.py`](../../src/hswm/learning/token_learning_contract.py).

The learning target is not reduced when one update family fails. The
[`adaptive realization methodology`](../../docs/research/HSWM_ADAPTIVE_REALIZATION_METHODOLOGY_2026-08-30.md)
requires the exact mechanism to become `RED_WITHIN_SCOPE` or
`UNDERDETERMINED`, preserves its evidence, and admits a successor only through
a new prospective contract with the same or stronger causal controls.
