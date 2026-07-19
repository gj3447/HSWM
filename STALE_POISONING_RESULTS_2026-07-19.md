# T4 — stale-poisoning falsifier results (2026-07-19)

> `stale_poisoning.py` on the T4.5 real worlds (musique/2wiki, bge-m3 cached,
> fully offline). n=200 poisoned queries per dataset; stale twin of the MOST
> retrievable gold, cosine-matched ±0.0028 (≤ prereg tol 0.02); doses 0.5/0.25/0.1.
> Arms: (a) pointwise deployed / (b) bi-temporal hard filter (Zep-faithful,
> audit=1.0 by construction) / (c) κ=0 probe / (d) κ=1 probe. Arm (e) DEFERRED.

## Headline — the claim SHRINKS to its pointwise core, and that core is strong

| | musique | 2wiki |
|---|---|---|
| stale threat @ b=0.5 (arm a, top-10 rate) | 0.565 | 0.850 |
| after full dose 0.1 | **0.000** | **0.000** |
| current recall through all doses | 0.547 (무손상) | 0.640 (무손상) |
| dose-response ρ (a / d / b) | −0.99 / −0.88 / **0 (구조적 불가)** | −0.93 / −0.86 / **0** |
| **kill (i)** — (d) vs (c) | **FIRED** (diff 0.0) | **FIRED** (diff 0.0) |
| **kill (ii)** — filter catches up on all 3 | not fired | not fired |
| kill (iii) — vs separated-graded (e) | DEFERRED | DEFERRED |
| H-T3b collateral (wrong supersede, dose .1) | cur 0.547→0.4625 | 0.640→0.480 |

## What survived (and is now measured, not asserted)

**The pointwise conjunction**: one non-destructive `supersede()` write sinks a
maximally-confusable stale fact from 56–85% top-10 presence to **zero** with a
near-perfect dose-response curve (ρ −0.93…−0.99), leaves current-fact recall
untouched, and keeps the stale fact reachable for audit. The bi-temporal hard
filter matches current-recall and wins audit@10 (1.0 by construction) but is
**structurally incapable of dose-response** (ρ≡0: rank is dose-invariant) —
graded one-field supersession keeps a capability the filter cannot express, so
kill (ii) does not fire.

## What died

**kill (i) fired on both datasets**: κ=1 vs κ=0 traversal probes are
indistinguishable (stale-suppression diff exactly 0.0). Supersession-in-
PROPAGATION adds nothing here, for two visible reasons: (1) traversal probes
abstain ~90% (T5 trip rates), and (2) the seed already carries b algebraically
(spec §2.3: exp(W/τ) = exp(α/τ)·b^{λ_b/τ}) — the conductance leg is redundant
where the seed does the work. Combined with T5 (traversal refused on both
worlds), **the §4 novelty sentence must drop its multi-hop clause**:

> 허용 가능한 주장 (수정): "한 번의 비파괴 supersede write가 같은 場의 검색·plan
> 분포를 dose-graded로 재라우팅하며(binary filter가 구조적으로 표현 불가한
> dose-response 보존), superseded 사실은 도달가능·감사가능 상태로 남는다."
> — multi-hop 전파 재라우팅 절은 kill (i)로 사망. kill (iii)는 OPEN.

## Honest costs (co-published, spec 의무)

- **H-T3b**: one WRONG supersede at full dose costs −8.5pt (musique) / −16pt
  (2wiki) current recall — "one write, three effects"의 쌍대는 "one wrong
  write, three corruptions". MemStrata AUROC 0.59 says supersession judgments
  WILL be noisy; deployment needs the wrong-write cost next to the right-write
  benefit.
- Graded audit@10 is dose-dependent (0.63–0.94 vs filter's constant 1.0) —
  reachability holds (Eilu-va-Eilu) but top-10 auditability degrades with dose.
- Kill (iii) (vs Kumiho-style separated-graded) remains OPEN — arm (e) not built.

## Bug ledger (caught before landing)

1. argmin-cos injection = strawman (stale born at the bottom; nothing to sink)
   → argmax-cos threat model. 2. kill (ii) sign inversion (the better the
   graded arm expressed dose-response, the harder it "died") — caught on the
   live ρ values. 3. audit ≠ top-10 (reachability metric split from audit@10).

Files: `stale_poisoning_{musique,2wiki}_result.json`. 59/59 tests.
