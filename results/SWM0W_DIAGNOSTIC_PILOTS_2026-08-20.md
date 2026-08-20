# SWM-0W scalar operator — disclosed diagnostic pilots

- Date: 2026-08-20 UTC
- Implementation status: `IMPLEMENTED` for the bounded scalar precursor
- Scientific status: **`UNJUDGED`**
- Verdict: **none — diagnostic runs cannot emit `PASS` or `KILL`**
- Next admissible measurement: one preregistered future-drand, 20-task run

## What these pilots tested

SWM-0W isolates one claim before recurrence, LLM calls, graph mutation, or
federation are added:

> On fixed-arity worlds with three singleton incidence roles, can a learned
> role-conditioned third-order scalar operator generalize to held-out shift
> cuts, use its n-ary channel, and outperform registered lower-order controls?

Each task is a deterministic finite world generated from one external seed. It
contains `5,625 / 5,000 / 5,000` train/dev/test worlds over disjoint `9 / 8 / 8`
shift cuts. Unary and every role-pair marginal are matched. The evaluator target
is a centered, dyadic, rank-17 three-way tensor; an exact nonzero modular minor
certifies the registered construction. The model sees only three role-tagged
two-scalar inputs, never the target, task UID, split, or evaluator envelope.

The three disclosed pilot seeds were:

```text
SHA256(ASCII("HSWM-SWM0W-PILOT-v1:{i}")), i in {0,1,2}
```

Every arm within a task used the same optimizer seed:

```text
uint64_be(SHA256(
  b"hswm-swm0w-optimizer-seed/v1\0" + task_uid.encode("ascii")
)[:8])
```

No confirmatory seed, future pulse, preregistration, or result artifact was
created by these runs.

## Registered diagnostic measurements

For target `T`, lower-order controls `P/A/R`, information-complete controls
`F/D`, and capacity probes `P17/A21/R64`:

```text
Q = R²(T)
L = R²(T) - max(R²(P), R²(A), R²(R))
C = R²(T) - max(R²(F), R²(D))
H = R²(T) - R²(T with the triple head removed)
S = H - max(damage from each of 3 unary and 3 pair heads)
R = R²(T) - R²(T under one fixed role cycle)
K = R²(T) - max(R²(P17), R²(A21), R²(R64))
```

`K` is a non-gating wording check. It cannot create a scientific `PASS`.

## First disclosed run — 200 epochs

Only the maximum epoch count is later changed; patience is `25` in both runs.

| task | `Q` | `L` | `C` | `H` | `S` | `R` | `K` |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.782797 | 0.784217 | -0.057505 | 5.936008 | 2.621622 | 1.691101 | 0.786181 |
| 1 | 0.923350 | 0.932164 | 0.025955 | 2.784283 | 1.593435 | 2.360988 | 0.930654 |
| 2 | 0.892996 | 0.908785 | 0.049306 | 3.727878 | 1.997361 | 0.458077 | 0.905071 |
| **mean** | **0.866381** | **0.875055** | **0.005919** | **4.149389** | **2.070806** | **1.503389** | **0.873969** |

Target `T` reached the epoch boundary on task 1 and nearly reached it on task
2. That censoring was declared before one and only one cap-extension diagnostic.

## Cap-extension run — 300 epochs

Only `epochs=200 -> 300` changed. No further extension or automatic rerun is
allowed.

| task | `Q` | `L` | `C` | `H` | `S` | `R` | `K` |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.782797 | 0.784217 | -0.066157 | 5.936008 | 2.621622 | 1.691101 | 0.786181 |
| 1 | 0.940706 | 0.949520 | 0.036096 | 2.209911 | 1.496662 | 2.427856 | 0.948009 |
| 2 | 0.924422 | 0.940210 | 0.080731 | 3.816598 | 1.655297 | 0.554374 | 0.936496 |
| **mean** | **0.882641** | **0.891316** | **0.016890** | **3.987505** | **1.924527** | **1.557777** | **0.890229** |

Task 1 and 2 target models improved by `+0.017355` and `+0.031425` R².
Task 0 did not improve at all; its information-complete flat MLP remained
better by `0.066157`. Several target and information-complete arms still ended
near the 300-epoch boundary, so this run does not establish optimizer
convergence. The contract is nevertheless stopped here to avoid adapting until
the desired result appears.

## Integrity observations

Across both disclosed runs:

- all `27` fits per run were finite and had zero clipped updates;
- all seven equal-width head removals per task restored model state and all
  `5,000` test predictions bit-exactly (`21/21` per run);
- native and independently compiled typed-star paths matched on all `5,000`
  test worlds per task;
- the same task-derived optimizer seed was used by all nine arms;
- no model restart, seed selection, multistart, or post-result arm selection
  was used.

## Frozen direction for the confirmatory protocol

The diagnostic phase fixes `epochs=300`, `patience=25`, and these task-level
population gates before a future pulse is selected:

| metric | proposed confirmatory gate |
|---|---:|
| `Q` | one-sided 95% task-bootstrap LCB `>= 0.80` |
| `L` | LCB `>= 0.10` |
| `C` | LCB `>= -0.02` |
| `H` | LCB `>= 0.10` |
| `S` | LCB `> 0.00` |
| `R` | LCB `>= 0.10` |
| `K` | LCB `>= 0.10` only permits capacity-independent wording |

`Q=0.80` is an interpretable minimum of explaining at least 80% of held-out
target variance. It is not the observed pilot minimum. The exact contract is
not a preregistration until its source, workflow, thresholds, future-round
commitment, and operational chronology receipt are frozen and validated.

## Claim boundary

Positive pilot values show that the bounded mechanism is worth a fresh test.
They are not evidence from an untouched task population. The target family,
three pilot seeds, optimizer behavior, and metrics have all been inspected.

Even a future confirmatory `PASS` would support only a synthetic,
fixed-three-singleton-role **scalar compatibility precursor**. It would not by
itself establish multi-member set transport, recipient-conditioned set-to-set
`W`, recurrence, LLM cognition, causal outcome learning, topology learning,
distributed HSWM, or the Human Universal Body.
