# SWM-0W scalar compatibility precursor — confirmatory result

- Date: 2026-08-20 UTC
- Evidence verdict: **`PASS`**
- Bounded scientific status: **`SUPPORTED_NARROW`**
- Scope: learned scalar compatibility over exactly three singleton incidence roles
- Whole-HSWM scientific status: **`UNJUDGED`**
- Next gate: multi-member, recipient-specific set-to-set `W`

## What was tested

SWM-0W asks one bounded question before recurrence, LLM calls, outcome learning,
topology mutation, or distributed composition are added:

> On fixed-arity synthetic worlds with three singleton incidence roles, can a
> learned role-conditioned third-order scalar operator generalize to held-out
> shift cuts, beat registered lower-order and role-erased controls, remain
> non-inferior to strong information-complete controls, and lose its advantage
> when its learned n-ary channel is removed?

Each of 20 externally seeded tasks contains `5,625 / 5,000 / 5,000`
train/dev/test worlds over disjoint `9 / 8 / 8` shift cuts. Unary and pairwise
marginals are matched. The frozen protocol evaluates nine arms, independent
typed-star compilation, one fixed role-cycle intervention, and all seven
nonempty removals of the three learned heads. Every task receipt binds its
seed-derived task UID, task bytes, exact variance, optimizer template, model
states, predictions, scores, and remove/restore checks.

This is a scalar precursor, not the canonical Semantic Weight Map. Each role
has one member and the model emits one compatibility number. It does not yet
implement multi-member aggregation, recipient-conditioned set-to-set transport,
recurrent depth, causal `ΔW`, or topology learning.

## Frozen chronology and authority

Source commit A `130d2265befeeb0bb6542bdec1eb962b48c6c346` froze the
tracked source, protocol, workflow, dependency lock, and tests. Its direct child
registration commit B `ec19a74cbcde409add819c8b566627c49582ea9a` added only
the preregistration for Quicknet round `31484160`. GitHub Actions run
[`32406084883`](https://github.com/gj3447/HSWM/actions/runs/32406084883),
attempt `1`, executed the frozen `register -> confirm -> adjudicate` chain.

The confirm job emitted only `CANDIDATE_PASS_AWAITING_BUNDLE`. That candidate is
deliberately **non-authoritative**. The separate adjudicator promoted it to
`PASS` only after rechecking the source/preregistration bindings, the sole
surviving matching GitHub run, confirm-job chronology, exact candidate artifact
ID and server digest, pinned-Node offline BLS replay, all 20 beacon-derived task
identities, every task receipt, and the frozen reducer. Reason code:
`CANDIDATE_ALL_ESSENTIAL_GATES_PASS`.

| bound object | identifier / SHA-256 |
|---|---|
| preregistration | `a365ef47f47f1cb2ab0d540c819c6ec80b249f74d144a7f9757e1e039161a00e` |
| future-round commitment | `58724d8bb96a7b3ac4015fd81a3cd0b5c3fcc279d9c04fc56f1a6675a968aa33` |
| registration GitHub artifact | ID `9420313629`; archive `6162a7a6df8d7c1ead127adb35ee8f72462232c5a3c127e65cd562b39403a30c` |
| candidate GitHub artifact | ID `9422794644`; archive `9b0072ec6a8eb553e1190b8c5d2e152919becdd0b853974a18339ea0d561b249` |
| checked-in candidate member | `52478e8fc0e5ea2a74f9103068860474318776668142cd46588e068c947fdbf7` |
| candidate protocol receipt | `0ec1428a0ea59db3449fb27c5bd9cc34c65f23789a3f6f71aea01c4edf3829d0` |
| adjudication archival artifact | ID `9422819218`; archive `c94f08c450008036658e4870325789c8008964266542c340241bb6e8428716c4` |
| checked-in adjudication member | `4fabe3c74c059ce36b2b90f692c40c640ecba8ea8324268222cbf1d4f65c4744` |
| adjudication receipt | `4333ef0bcf06c96600309d884877cafcffdca26d206c3961db8e5dd346a6cdf6` |

The adjudication is operational evidence, not an absolute cryptographic
timestamp. It trusts GitHub's hosted runner/control plane and TLS, the local
validation Python, and that the repository owner did not delete another
matching workflow run. A copied self-hashed receipt alone is not fresh external
authority: an independent reader must requery GitHub and redownload the exact
bound artifact, or use equivalent authenticated external evidence.
The adjudication artifact is an archival carrier for the receipt, not a new
noncyclic authority source.

## Registered measurements

The table reports the task mean and the shared task-bootstrap `5%`/`95%`
quantiles from 10,000 PCG64 resamples. The decision column compares the lower
bound with the preregistered threshold.

| metric | point | 5% lower | 95% upper | registered decision |
|---|---:|---:|---:|---|
| `Q` target test R-squared | `0.868449500` | `0.854302611` | `0.882971332` | `>= 0.80` pass |
| `L` over strongest lower-order/roleless control | `0.880713180` | `0.867089732` | `0.894490293` | `>= 0.10` pass |
| `C` over strongest information-complete control | `0.014327709` | `-0.002010788` | `0.030021271` | `>= -0.02` pass |
| `H` triple-head removal damage | `4.091766231` | `3.393240947` | `4.870622710` | `>= 0.10` pass |
| `S` triple-specific damage beyond unary/pair removals | `2.171953116` | `1.906581137` | `2.456445133` | `> 0.00` pass |
| `R` fixed-role-cycle damage | `1.398102454` | `1.251359582` | `1.545381005` | `>= 0.10` pass |
| `K` over nominal-capacity controls | `0.877194218` | `0.863104413` | `0.891450120` | wording gate `>= 0.10` pass |

`K` was not an essential PASS gate. Its lower bound permits only the protocol's
narrow “capacity-independent” phrase under the frozen nominal-capacity controls;
it does not establish architecture-independent, compute-matched, or universal
superiority.

## Interpretation

The admissible result supports one proposition: in this fixed synthetic family,
a learned role-conditioned scalar mechanism over exactly three singleton roles
captured a third-order compatibility signal that survived held-out cuts and the
registered controls, while exact interventions localized the gain to the
learned n-ary channel. The appropriate scientific status for that proposition
is **`SUPPORTED_NARROW`**.

It does **not** establish the full HSWM thesis. In particular, it is not evidence
for canonical recipient-specific, multi-member set-to-set `W`; recurrent or
deep HSWM dynamics; token/LLM cognition; causal outcome-bound `ΔW` or
`ΔH`; real-world semantic utility; distributed composition; consciousness;
or the Human Universal Body. The integrated HSWM programme therefore remains
**`UNJUDGED`**. The result opens only the next experiment: implement and freeze
a multi-member recipient-specific set-to-set operator under matched controls.

## Checked-in artifacts

- [preregistration](../prereg/PREREG_SWM0W_SCALAR_GATE_V1.json)
- [candidate bundle — candidate-only, non-authoritative](raw/swm0w_scalar_gate_candidate_2026-08-20.json)
- [adjudication receipt](../evidence/EVIDENCE_SWM0W_SCALAR_GATE_ADJUDICATION_2026-08-20.json)
- [confirmatory runner](../src/hswm/experiments/swm0w_confirmatory.py)
- [frozen protocol](../src/hswm/experiments/swm0w_protocol.py)
- [GitHub workflow](../.github/workflows/swm0w-confirmatory.yml)
