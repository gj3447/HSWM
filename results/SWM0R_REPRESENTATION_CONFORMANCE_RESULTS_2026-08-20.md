# SWM-0R representation conformance — confirmatory result

- Date: 2026-08-20 UTC
- Verdict: **engineering `PASS`**
- Implementation status: `IMPLEMENTED`
- Scientific status: **`UNJUDGED`**
- Next gate: `SWM-0W` — not yet implemented or passed

## What was tested

SWM-0R asks a deliberately smaller question than the full Semantic Weight Map:

> Can an immutable role-bearing n-ary representation preserve a joint relation
> that registered scalar, pairwise, role-erased, grouping-erased, flat, and
> identifier-only projections provably lose?

Each block exhausts nine worlds over `F₃`. One latent is encoded only by exact
hyperedge grouping; the other is encoded only by incidence role. The target is
their modular sum. The native path and the typed-star path use independently
implemented traversals, while every lossy representation has an exact
label-uniform Bayes ceiling of `1/3` on this fixture.

This is a constructive representation witness. The encoder knows the finite
fixture; only the final balanced ridge lookup is fitted. It is not learned
`Θ/R/W`, not semantic efficacy, and not a cognitive benchmark.

## Frozen chronology

The implementation, adversarial tests, and preregistration were committed and
pushed as `981517840e55f999a9b5cc2adee8cb39fda24af7` before confirmatory seeds
`100..119` were generated. The runner then required the preregistration and all
three runtime sources to be tracked and byte-identical to that same `HEAD`.

- Preregistration SHA-256:
  `7e8ee52b551a810f590a1c7d5da718f85e3f32b9755c9340b317cc2e4103074a`
- Raw result SHA-256:
  `d1504c47305590c47a3c92bd181ed667a13e6f61b9035d97ef574aa5b580d254`
- Internal manifest SHA-256:
  `bd06407188397f5b6ae126ec107e87d86bb278254d674bbb65b3138d38ab6f60`
- Internal result SHA-256:
  `ed93e2160c081d3802330b1ab1eb0bf01161139fa76d5359db3a68864316af41`
- A second full run was byte-identical to the first.

## Direct result

| measurement | observed |
|---|---:|
| native role-bearing n-ary accuracy | `1.0000` |
| independent typed-star accuracy | `1.0000` |
| each of seven registered lossy arms | `0.3333` |
| target − dev-frozen strongest lossy arm | `0.6667` |
| target − typed star | `0.0000` |
| targeted role-edge removal fraction | `1.0000` |
| matched irrelevant-edge accuracy change | `0.0000` |
| positive nonce/order seeds | `20 / 20` |
| integrity checks | `7 / 7` |
| registered promotion gates | `6 / 6` |

The target edge removal reduced the native result to the lossy ceiling; removing
one matched but irrelevant grouping edge did not change the prediction; exact
restore recovered the original artifact and outputs.

Both readouts contain `162` nominal padded coefficients, but that is not compute
parity. The native and typed-star encoders used respectively `9/9` effective
features and `49/89` audited structural work units. These units are neither FLOPs
nor latency measurements.

## Interpretation

The result closes one engineering prerequisite: exact n-ary grouping and
incidence roles can be represented without collapsing to the registered lossy
views, and the relevant relation can be removed and restored immutably.

It does **not** show that an operator learned this distinction. The twenty
confirmatory seeds only change opaque identifiers and order over the same nine
semantic worlds, so their point-mass bootstrap intervals are diagnostic rather
than evidence of broad population generalization. Consequently the programme's
scientific status remains `UNJUDGED`.

The only permitted promotion is to implement and preregister **SWM-0W**: a
genuinely learned role-conditioned set-hypergraph operator receiving raw
incidence features, tested against information-complete and lower-order matched
baselines. Recurrence (`SWM-1`) remains closed until that learned gate passes.

## Verification

- SWM-0R world/operator/protocol suite: `45 passed`
- Full repository regression: `1589 passed, 3 skipped`
- Wheel and source distribution: built successfully
- Confirmatory replay: byte-exact raw JSON SHA-256 match

## Artifacts

- [preregistration](../prereg/PREREG_SWM0R_REPRESENTATION_CONFORMANCE_2026-08-20.json)
- [raw canonical result](raw/swm0r_representation_conformance_2026-08-20.json)
- [evidence receipt](../evidence/EVIDENCE_SWM0R_REPRESENTATION_CONFORMANCE_2026-08-20.json)
- [world generator](../src/hswm/experiments/swm0_worlds.py)
- [constructive operator](../src/hswm/experiments/swm0_operator.py)
- [protocol](../src/hswm/experiments/swm0_protocol.py)
