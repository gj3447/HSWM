# HSWM next-research harness and programme feedback — 2026-07-24

## Outcome first

The next programme is now an executable dependency graph rather than a prose
list.  [`hswm_next_research_harness.py`](hswm_next_research_harness.py) verifies
the receipts that constrain each branch and refuses to open a downstream gate
when its prerequisite is absent, altered, or merely self-asserted.

The current truthful runnable frontier is two-lane:

1. build and accept the **real B2.2 Gate-0 component packs**; and
2. implement the **F1 multi-role LLM function network** under an equal-budget
   comparison.

P1v5 three-factor bond plasticity remains blocked until Gate-0 acceptance.  P2
Agent-A-to-frozen-B transfer waits for both P1v5 and F1.  A learned topology
operation and long-horizon consolidation remain later gates.

## Why the order changed

The older plasticity design called B2.1 the next rung, but that experiment has
already run.  Its shared ridge/conformal router over frozen `A / B / MERGED`
arms failed all 54 standard cells and collapsed to `ABSTAIN -> MERGED`.  The
post-result oracle ceiling was below the registered primary target, so relaxing
the abstention threshold or fitting another equivalent ridge router is not an
admissible next experiment.

P1v3 and P1v4 then established a different, narrow fact: a training-derived
typed source policy can change a frozen LLM answer and the effect replicated on
a fresh six-case cut.  P1v4 is replay-verified by LakatoTree, but it is still L0
answer-interface actuation.  It does not establish a generally learned policy
compiler or a durable semantic weight update.

The two lines meet at B2.2:

```text
outcome
  -> used-bond eligibility
  -> query-conditioned fast bond candidate
  -> fresh + retention + canary evaluation
  -> repeated-effect slow Delta-ell candidate
  -> CAS promotion
  -> changed later frozen behavior
  -> removal ablation must erase the gain
```

This is not a retry of the failed P1 scalar belt.  The old update assigned one
global exact-answer scalar across winning retrieval edges and never changed a
top-10 rank.  The new first actuator is a query-conditioned fine bond potential;
only effects that repeat across independent components may be distilled into a
durable, query-independent slow weight.

## Encoded gate order

The machine-readable plan is
[`_research/next_gate_harness/plan.v1.json`](_research/next_gate_harness/plan.v1.json).
It freezes the following order:

1. preserve P1v4 L0 actuation and its L2 replay boundary;
2. preserve B2.1 router-only falsification;
3. preserve B2.2 readout/Gate-0 engineering groundwork;
4. build three real Gate-0 packs and obtain the acceptance receipt;
5. run P1v5 fast-to-slow three-factor bond plasticity with static-update,
   random-credit, shuffled-eligibility, no-promotion, and removal controls;
6. independently build F1 with at least three typed LLM function roles;
7. measure Agent-A write to frozen-Agent-B unseen transfer;
8. open one typed topology operation only after transfer;
9. measure homeostasis, forgetting, collapse, recursion, cost, replay drift,
   rollback, and consolidation over long horizons.

The plan deliberately permits Gate-0 and F1 to proceed as separate lanes.  It
does not permit P2, P3, or P4 to leapfrog their scientific prerequisites.

## Harness behavior

Generate the current status receipt:

```bash
python3 hswm_next_research_harness.py status \
  --repo-root . \
  --recorded-at 2026-07-24T05:00:00+00:00 \
  --output receipts/HSWM_NEXT_GATE_STATUS_20260724.json
```

Once a real B2.2 Gate-0 acceptance receipt exists, re-run with:

```bash
python3 hswm_next_research_harness.py status \
  --repo-root . \
  --gate0-acceptance /absolute/path/to/gate0-acceptance.json \
  --output /new/write-once/status.json
```

The supplied acceptance receipt is not trusted by shape alone.  The existing
Gate-0 validator reopens its lock, reconstructs the three role entries, verifies
their packs and frozen replay bindings, and only then marks Gate-0 satisfied.

Build the non-scientific LakatoTree registration packet:

```bash
python3 hswm_next_research_harness.py lakatotree-packet \
  --repo-root . \
  --status receipts/HSWM_NEXT_GATE_STATUS_20260724.json \
  --result-path /opt/lakatotree/.runtime/research-current/HSWM/receipts/HSWM_NEXT_GATE_STATUS_20260724.json \
  --output receipts/HSWM_NEXT_GATE_LAKATOTREE_PACKET_20260724.json
```

The packet can create only a DRAFT engineering node, open frontier questions,
and attach evidence events.  It contains neither a prediction registration nor
a scientific result submission.

## Programme feedback

- Keep P1v4: it is the first replicated causal LLM behavior actuation in this
  programme.  Keep its claim narrow because the sample is six and the policy
  class is one source-conflict mechanism.
- Do not repeat B2.1 by threshold tuning.  The action-space oracle itself was
  below the preregistered primary target.
- Treat the missing real Gate-0 packs as the immediate weight-lane blocker.  A
  learner trained on truncated top-20 packs can silently mis-score suppressed
  candidates and is not admissible.
- Keep fast attention, slow memory, and topology separate.  A frequently chosen
  route is not specialization, and a low weight is not structural separation.
- Make F1 falsifiable: at least three roles, exact call/token parity, role
  removal, role shuffle, and a single-LLM workflow baseline.  Merely wrapping
  one answerer in several prompts is not a function network result.
- Do not call an A-to-B result transfer if B sees A's transcript, updates its
  parameters, or receives an exact-query cache hit.
- Keep LakatoTree as the independent registration/replay/verdict plane.  This
  harness reports readiness only and cannot judge its own scientific success.
