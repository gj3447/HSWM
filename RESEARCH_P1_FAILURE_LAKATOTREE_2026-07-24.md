# P1 failure analysis — LakatoTree research closeout

Date: 2026-07-24

Programme: `LakatosTree_HSWM_20260719`

Lane: `ENGINEERING + PI`
Authority boundary: this document is a repository-local research synthesis. It is
not a hand-entered LakatoTree verdict and it does not repair missing server-side
registration after the fact.

## Bottom line

P1 did not show that HSWM learning in general is impossible. It falsified a much
narrower protective-belt hypothesis:

> On the frozen PhantomWiki substrate, exact-answer set-match reward minus an
> expanding scalar baseline, distributed across normalized winning-path edge
> tags with `eta=0.05`, can change later fresh top-10 retrieval after an
> immediate promotion gate.

The runtime path itself is GREEN. The domain result for that hypothesis is RED.
The official LakatoTree kernel state is nevertheless **unjudged**, not
`rejected`, because the historical evidence generator wrote its own `FAIL` and
the run cannot be bound to a retrievable server-owned experiment tag and neutral
judge receipt. The negative measurements remain real; the procedural defect
prevents retroactively calling them a valid LakatoTree verdict.

## Three verdict layers that must not be collapsed

| layer | result | evidence |
|---|---|---|
| engineering | **GREEN** | outcome, eligibility, candidate staging, fresh gate, canary, CAS and immutable receipts executed |
| scientific protective belt | **RED** | A1-A2 paired recall@10 `0.0`, bootstrap lower `0.0`, A1 slope `-0.0270833`, 12 candidates and 0 activations |
| LakatoTree kernel | **UNJUDGED — procedural block** | measurement code emitted `verdict=FAIL`; no resolvable live experiment tag, independent judge-script receipt, or injected-negative judge receipt |

The last row is an audit finding, not a claim that the scientific result was
positive or ambiguous. A post-hoc adapter cannot recreate preregistration
chronology or judge independence.

## What failed mechanically

### 1. The tested signal was not the canonical LLM semantic judgment loop

The hard core says that HSWM learning is an LLM judgment producing an
evidence-bound lesson or semantic residual, followed by non-destructive
promotion and changed held-out behavior. P1 instead used one environment scalar:

```text
M_e = exact_set_match_e - expanding_mean(exact_set_match_<e)
Delta ell_b = 0.05 * M_e * normalized_tag_b
score = static_cosine + 0.1 * weighted_walk(exp(ell))
```

This was a legitimate minimal falsifier, but only for a scalar three-factor
edge-weight belt. It did not execute a typed LLM verdict-to-lesson compiler,
non-cosine semantic residual, multi-function network, transfer, topology
rewiring, or consolidation.

### 2. Reward and credit measured different things

`p1_eligibility_tag.py` gives the selected winning retrieval paths a total
credit mass of exactly one. `p1_phantom_environment.py` then rewards exact
answer-set match. A useful retrieval trace can therefore receive negative
modulation when the downstream answerer formats, omits, or otherwise misses the
answer. In A1 the four candidate-producing episodes had modulation
`[-0.1, -0.075, -0.025, +0.00625]`: three updates punished the paths selected
for the episode, while only the last update was weakly positive.

This violates the spirit of task-specific learning signals described by e-prop:
an eligibility trace alone is insufficient; it must be paired with a learning
signal that assigns the relevant downstream error to the relevant units. P1's
global exact-match scalar did not establish that assignment.

### 3. Credit normalization plus small `eta` diluted actuation

The A1 candidates spread L1 budgets of approximately `0.005`, `0.00375`,
`0.00125`, and `0.0003125` across 8, 6, 11, and 6 edges. Maximum absolute
per-edge log-weight changes were only `9.92e-4`, `9.39e-4`, `3.43e-4`, and
`9.11e-5`. They were exponentiated inside the traversal contribution and that
contribution was then scaled by `mu=0.1`, while the cosine score remained the
dominant additive term.

The theoretical multiplicative movement before `mu` is at most
`exp(L1)-1`; after `mu=0.1`, even the loose path-contribution upper bounds are
about `5.01e-4`, `3.76e-4`, `1.25e-4`, and `3.13e-5`. Actual changes were
smaller because only a minority of fresh queries traversed a touched edge.

### 4. Frozen rank replay proves an actuation deadband

`P1_RANK_INVARIANCE_DIAGNOSTIC_R2_2026-07-23.json` replayed the exact staged
snapshot bytes on the exact frozen fresh split. It made no LLM call and did not
create a new arm outcome.

| diagnostic | result |
|---|---:|
| candidate/query evaluations | `12 x 38 = 456` |
| queries whose selected path touched an updated edge | `21 / 456` |
| queries with any score change | `21 / 456` |
| top-10 order changes | `0` |
| top-10 membership changes | `0` |
| maximum absolute score delta | `3.2359e-5` |
| maximum delta / rank-10-to-11 boundary gap | `0.102697` |

Even the most favorable observed perturbation was only about 10% of the
boundary gap. Therefore relaxing the statistical threshold cannot rescue these
particular candidates: the discrete retrieval outcome was rank-invariant.

### 5. The immediate gate prevented accumulation, but was not the root cause

Every candidate had to exceed fresh recall delta `0.01` with bootstrap lower
bound above zero before activation. Since one candidate could not change top-10
membership, no update accumulated into a larger field change. That is an
actuation deadband. However simply lowering the gate is inadmissible: it would
publish behaviorally inert or harmful state and break the existing safety
contract. The candidate representation must change first.

### 6. The controls were censored by the same zero-activation gate

A1, shuffled-M A3, and uniform-credit A4 all generated candidates, and all were
rejected before activation. Their equal later curves establish absence of a
causal effect under the registered loop; they do **not** independently prove
that modulation order and eligibility tags contain no information. K2 and K3
are therefore secondary kill signals under common censoring, not standalone
mechanism identifications.

## Lakatos interpretation

### Hard core retained

- one evidence-bound semantic field governs retrieval, dispatch, and revision;
- semantic weight is cosine plus a judgment-derived non-cosine residual;
- learning is verdict-to-lesson feedback, not necessarily foundation-model SGD;
- revisions are immutable, gated, replayable, and non-destructive;
- efficacy means a controlled change in held-out behavior.

### Protective belt rejected

- global exact-answer scalar as the only learning signal;
- normalized credit over the currently winning retrieval path;
- query-global slow edge weights as the immediate behavior actuator;
- per-episode promotion requiring a discrete fresh top-10 jump.

### Programme status

The P1 belt is empirically degenerating: it followed earlier P6 and topology
candidate failures, and its candidates again produced no held-out movement.
The programme can remain progressive only by making the already-committed
problem shift to a typed verdict-to-lesson action space and by passing a stronger
removal/shuffle falsifier. More scalar-edge tuning is prohibited.

## Why typed lessons are the next admissible belt

The shift is grounded in mechanisms already demonstrated outside HSWM:

- Reflexion stores linguistic feedback in episodic memory and uses it to alter
  later decisions without parameter-weight updates.
- ExpeL extracts natural-language insights from experience and recalls them for
  new tasks, including transfer-oriented settings.
- Voyager grows a verified skill library from environment feedback and reuses
  those skills on new tasks.

These do not prove HSWM. They show a credible action space in which a sparse
semantic lesson can condition later behavior more directly than a tiny global
edge perturbation.

## Next falsifier ladder

The full contract is in
`PREREG_P1V2_TYPED_VERDICT_LESSON_2026-07-24.json`. It remains a local draft and
measurement is forbidden until the server tag, frozen modules, untouched split,
model deployment, budget manifest, neutral judge, and injected-negative judge
receipts all exist.

1. **L0 actuation precondition:** a valid typed lesson must change at least one
   held-out model decision under exact no-memory token/call parity. If an oracle
   lesson cannot actuate behavior, do not train a lesson compiler.
2. **L1 causal learning test:** compare typed lesson, raw transcript, no memory,
   and shuffled/removal controls on a newly generated untouched PhantomWiki
   universe.
3. **L2 transfer:** only after L1 passes both no-memory and raw-transcript
   margins may Agent A's frozen lesson artifact be exposed to a frozen Agent B.
4. **P3/P4 remain closed:** topology rewiring and consolidation do not open
   until a promoted state causes reproducible held-out behavior.

Primary success requires the minimum of typed-minus-no-memory and
typed-minus-raw-transcript to exceed `0.03`, with paired-bootstrap lower bounds
above zero. Shuffling/removing the lesson must erase at least `0.02` of the gain,
retention loss must stay within `0.02`, and exact model/call/token/split/gold
parity must hold.

If typed lessons beat no memory but not raw transcript, the result supports only
operational compression, not HSWM-specific learning. If they fail both, stop
P2/P3/P4 and retain the narrower compiler plus safe graph-memory claim.

## Provenance and reproducibility

- original prereg SHA-256:
  `136405ba5d0006195e9fe4c1a9899eb4ef098bbe22fa725599936479baa0e91d`
- original evidence SHA-256:
  `880de2841d33d04a1e615984287dbd2ab855bd8e288fc7999f19687d57233bfe`
- experiment receipt:
  `70cf72a18da617a3494b00848f349f0fd96c6dce444639413c21ace41e24f758`
- rank diagnostic: schema `hswm-p1-posthoc-rank-invariance/v1`; its internal
  `diagnostic_sha256` is checked by `verify_efficacy_claims.py`.
- Dell replay job: `hswm-p1-rank-invariance-r2b`, `rc=0`; retrieval only, no
  answer-model call.
- independent audit recomputed the 17 frozen module hashes with no mismatch and
  classified the kernel state as procedurally unjudged. No KG write occurred.

## Primary research sources

- Bellec et al., [A solution to the learning dilemma for recurrent networks of
  spiking neurons](https://www.nature.com/articles/s41467-020-17236-y), Nature
  Communications (2020).
- Shinn et al., [Reflexion: Language Agents with Verbal Reinforcement
  Learning](https://papers.nips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html), NeurIPS (2023).
- Zhao et al., [ExpeL: LLM Agents Are Experiential
  Learners](https://arxiv.org/abs/2308.10144) (2023).
- Wang et al., [Voyager: An Open-Ended Embodied Agent with Large Language
  Models](https://arxiv.org/abs/2305.16291) (2023).
