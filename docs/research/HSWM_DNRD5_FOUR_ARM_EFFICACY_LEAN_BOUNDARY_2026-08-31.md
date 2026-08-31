# HSWM DNRD-5 four-arm efficacy terminal Lean boundary

> **Status:** `SECONDARY_AI_FORMAL_EXPERIMENTAL_CONTRACT / CURRENT_EFFICACY_NOT_EVALUATED / NO_SCIENTIFIC_RESULT`
>
> **Mechanism scope:** DNRD-5 only; replaceable under the
> [`adaptive research strategy`](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)
>
> **Design authority:**
> [`DNRD-5 causal macroplasticity design`](HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md),
> [`scientific-boundary review`](HSWM_DNRD_5_SCIENTIFIC_BOUNDARY_REVIEW_2026-08-28.md),
> and the
> [`exactness policy amendment`](HSWM_DNRD_5_EXACTNESS_POLICY_AMENDMENT_2026-08-28.md)
>
> **Formal artifact:**
> [`HSWMDnrd5EfficacyBoundary.lean`](../../formal/HSWMDnrd5EfficacyBoundary.lean)

## 1. Canonical role and mechanism scope

HSWM's USER_PRIMARY target remains one token-native LLM-function macro-neural
network with an outcome-to-credit-to-revision-to-fresh-behavior loop. DNRD-5 is
one bounded experimental route for testing one candidate causal mechanism
inside that target. Its four arms, block count and statistical rule are not the
definition of HSWM and must not become permanent architecture.

A valid DNRD-5 negative result retires or reroutes the exact tested mechanism
family with its evidence lineage intact. It does not shrink the HSWM target,
rename failure, weaken a criterion, delete a RED path or become support merely
because a later system is larger.

## 2. Target identity versus current evidence

The design declares 300 independent complete block-clusters. Every block has
exactly these four typed arms:

- `ACTIVE` — genuine outcome-bound admitted successor;
- `OUTCOME_INDEPENDENT_SHAM` — matched admitted rewrite driven by a
  distribution-matched but locally outcome-independent placebo;
- `DELAYED_NO_CREDIT` — no admission before probes and genuine outcome held in
  escrow until every response seal;
- `EXACT_W0_ROLLBACK` — active-style staging admission followed by exact
  behavioral W0 restoration before its probe.

Current checked-in evidence remains `NOT_EVALUATED` for DNRD-5 causal efficacy.
Content/trace or instrument qualification does not provide a preregistered
marked occurrence, 300 sealed four-arm outcomes or an independent scientific
terminal.

## 3. Integrity and completeness before statistics

The formal boundary represents an occurrence-integrity record with explicit
conditions for frozen source/preregistration, the exact block universe and arm
assignment, nine-call accounting, active/sham matching, delayed no-credit
escrow, exact W0 restoration, exclusion/no leakage, blind evaluation,
independent judgment, and the Permit/Inv/admission path.

Operational completeness separately requires all 300 blocks, all four sealed
arm outcomes in each block, and no missing probe/evaluator receipt. Integrity
failure and missingness are not unfavorable scores and cannot enter efficacy
arithmetic:

```text
pre-marker refusal                 -> PREMARKER_REFUSAL
post-marker integrity failure      -> VOID_PROTOCOL
validly sealed operational missing -> INCONCLUSIVE_OCCURRENCE
```

There is no complete-case analysis, replacement block, retry, resume, second
pulse or rerun.

## 4. Frozen three-contrast gate

The primary contrast is ACTIVE against `OUTCOME_INDEPENDENT_SHAM`. The two
required mechanism contrasts are ACTIVE against `DELAYED_NO_CREDIT` and
`EXACT_W0_ROLLBACK`.

Each contrast gate contains two separately labeled decisions:

1. the Bonferroni-adjusted one-sided exact conditional sign-test p-value is at
   most `.05` under the frozen sharp-null label-swap law; and
2. the separately asymptotic one-sided simultaneous lower confidence bound is
   strictly positive.

The formal terminal classifier consumes only these already judged booleans; it
does not recompute p-values or pretend that the asymptotic bound is exact. A
contrast passes only when both layers pass.

The subsequent
[`exact paired sign gate`](HSWM_DNRD5_EXACT_SIGN_GATE_LEAN_2026-08-31.md)
refines the exact-p boolean from natural-number counts without changing the
separate asymptotic-LCB input.

```math
\mathrm{ContrastPass}_j
=
(p^{\mathrm{adjusted}}_j\leq .05)
\;\land\;
(\mathrm{LCB}_j>0).
```

For a complete integrity-valid marked occurrence:

- all three contrast gates pass: `CAUSAL_MACROPLASTICITY_GO`;
- primary passes and both mechanism contrasts fail:
  `PRIMARY_SIGNAL_MECHANISM_INCOMPLETE`;
- every other non-GO pattern: `VALID_CAUSAL_NO_GO`.

The planning alternative `.15` is not part of the observed pass rule.

## 5. Machine-checked terminal properties

The Lean module defines a total fail-closed terminal classifier. Its 21
theorems prove:

- the four arm constructors are distinct and the declared arm universe has
  exactly four members;
- pre-marker refusal cannot produce GO;
- any marked integrity failure produces `VOID_PROTOCOL` regardless of
  favorable-looking contrast flags;
- integrity-valid operational incompleteness produces
  `INCONCLUSIVE_OCCURRENCE` regardless of contrast flags;
- GO requires a marked, integrity-valid, operationally complete occurrence and
  both statistical layers for all three contrasts;
- failure of either statistical layer in any contrast prevents GO;
- the exact primary-only pattern yields
  `PRIMARY_SIGNAL_MECHANISM_INCOMPLETE`;
- complete valid non-GO patterns outside primary-only yield
  `VALID_CAUSAL_NO_GO`; and
- the exact checked-in readiness profile cannot support a scientific terminal
  because no preregistered efficacy occurrence, four-arm outcome set or
  independent efficacy judgment is present.

## 6. Exact claim ceiling

Lean proves the classifier's consequences assuming its boolean evidence fields
are correctly supplied. It does not validate actual source, randomization,
calls, model isolation, outcomes, p-values, confidence bounds, external truth,
causal assumptions or judge independence. An all-true symbolic input would be
a test vector, not observed evidence.

This boundary emits no actual terminal, changes no current DNRD-5 status and
creates no research receipt. DNRD-5 causal efficacy remains `NOT_EVALUATED`;
HSWM efficacy, G0/G1, FCL laws, cognition and complete realization remain
`UNJUDGED`.
