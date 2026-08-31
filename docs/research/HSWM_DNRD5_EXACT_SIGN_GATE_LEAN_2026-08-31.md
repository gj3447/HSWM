# HSWM DNRD-5 exact paired sign gate in Lean

> **Status:** `SECONDARY_AI_FORMAL_ARITHMETIC_CONTRACT / NOT_INFERENTIAL_EVIDENCE / NO_SCIENTIFIC_RESULT`
>
> **Source arithmetic:**
> [`_research/dnrd5/analysis.py`](../../_research/dnrd5/analysis.py)
> under the
> [`DNRD-5 exactness policy`](HSWM_DNRD_5_EXACTNESS_POLICY_AMENDMENT_2026-08-28.md)
>
> **Downstream terminal boundary:**
> [`DNRD-5 four-arm efficacy terminal`](HSWM_DNRD5_FOUR_ARM_EFFICACY_LEAN_BOUNDARY_2026-08-31.md)
>
> **Formal artifact:**
> [`HSWMDnrd5ExactSignGate.lean`](../../formal/HSWMDnrd5ExactSignGate.lean)

## 1. Scope

This boundary formalizes only the finite integer arithmetic of one paired
ACTIVE-versus-control sign-test gate. DNRD-5 has three such gates. It does not
establish the randomization law, deterministic potential outcomes,
exchangeability, consistency, no interference, integrity, external truth or
causal validity that give the arithmetic its interpretation.

It also does not formalize the asymptotic normal lower confidence bound. That
layer remains separately labeled and must be positive in the downstream
terminal classifier.

## 2. Exact count semantics

For one control, each complete block contributes a paired difference in
`{-1,0,1}`. Let `w` be ACTIVE-favoring discordant blocks, `l` be
control-favoring discordant blocks, `t` be ties and `m=w+l`.

The frozen inclusive upper tail is:

```math
N_{\mathrm{tail}}(m,w)
=
\sum_{k=w}^{m}{m\choose k},
\qquad
p_{\mathrm{exact}}
=
\frac{N_{\mathrm{tail}}(m,w)}{2^m}.
```

The `k >= w` tail is inclusive. Ties remain in the 300-block descriptive
population but do not enter `m`. Conditioning on discordance does not redefine
the study population.

## 3. Integer-only Bonferroni threshold

The frozen family has three contrasts and familywise alpha `1/20`. At this
threshold the cap in `min(1, 3 p_exact)` cannot turn a failing value into a
passing one. Cross multiplication by the positive denominator gives:

```math
3\frac{N_{\mathrm{tail}}}{2^m}\leq\frac{1}{20}
\quad\Longleftrightarrow\quad
60N_{\mathrm{tail}}\leq 2^m.
```

The Lean decision uses exactly this natural-number inequality and additionally
requires `w <= m`. It performs no floating-point conversion, decimal rounding
or fraction reduction.

## 4. Machine-checked properties

The Lean module's 16 theorems prove:

- its boolean exact gate is true exactly when `w <= m` and the integer
  Bonferroni inequality holds;
- the generic cross-multiplied `3/20` fraction comparison reduces to the same
  `60 * tail <= denominator` inequality;
- changing only the tie count cannot change the exact gate;
- zero discordance and a 300-tie occurrence do not pass;
- the inclusive tail keeps the observed threshold term;
- concrete all-discordant-win edges at `m=5` and `m=6` respectively fail and
  pass the Bonferroni exact layer (`2^5 < 60 <= 2^6`); and
- projection into the downstream `ContrastGate` preserves the exact decision
  while accepting the asymptotic-LCB decision only as a separate boolean.

These are arithmetic and refinement facts, not experimental outcomes.

## 5. Frozen cross-language arithmetic witnesses

The Python implementation uses `Fraction`, `math.comb`, an inclusive
`range(active_wins, discordance + 1)`, denominator `1 << discordance`, and
three-way Bonferroni adjustment. The Lean definitions independently encode the
same mathematical contract using an in-module Pascal recursion for natural
binomial coefficients, a finite inclusive tail and natural-number comparison.

The count projections of checked-in `analysis_v1.json` are reified as Lean
constants. Kernel-checked native evaluation establishes:

| Frozen case projection | Lean exact-layer result |
| --- | --- |
| all 300 ties | fail |
| known small tail `w=2`, `l=1` | numerator `4`, denominator `8`, fail after Bonferroni |
| GO arithmetic vector `w=300`, `l=0` | pass |
| mechanism-incomplete primary `w=220`, `l=0`, `t=80` | primary exact layer passes |
| nontrivial large tail `w=180`, `l=120` | pass |
| positive-LCB/exact-p split `w=5`, `l=0`, `t=295` | exact layer fails |

The Python frozen-vector suite remains the source-language check and is run
separately. These Lean witnesses bind mathematical count values, not JSON
bytes, block IDs, Python control flow or the Decimal LCB implementation.

This is not a verified compiler or whole-program semantics proof for Python.
The checked vector agreement narrows but does not eliminate that gap; a
production judge still needs independently bound source and occurrence bytes.

## 6. Exact claim ceiling

Lean can check the arithmetic for supplied counts. It does not prove that
counts came from 300 valid sealed blocks, that ACTIVE/control labels were
randomized correctly, or that an exact-test interpretation is justified. It
does not calculate or validate the asymptotic LCB.

No checked-in observed count is introduced, no DNRD-5 terminal is emitted, and
the causal-effect status remains `NOT_EVALUATED`. This phase needs no research
receipt.
