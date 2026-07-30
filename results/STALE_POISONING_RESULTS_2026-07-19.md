# T4 — stale-poisoning falsifier results (corrected S0, 2026-07-20)

> `stale_poisoning.py` on the T4.5 real worlds (musique/2wiki, bge-m3 cached,
> fully offline). n=200 poisoned queries per dataset; stale twin of the MOST
> retrievable gold, cosine-matched ±0.0028 (≤ prereg tol 0.02); doses 0.5/0.25/0.1.
> Arms: (a) pointwise deployed / (b) bi-temporal hard filter (Zep-faithful,
> audit=1.0 by construction) / (c) κ=0 probe / (d) κ=1 probe / (e)
> separated-graded external revision metadata. S0 reran both real datasets from
> cache through the actual `readouts.supersede()` path and emitted write/trip
> receipts. The 2026-07-19 arm-(e)-deferred interpretation is superseded here.
> Preregistered current-fact recall and H-T3b use **hop 2–3 only**; all-hop
> values are retained separately. MuSiQue: primary n=134 (67 hop-2 + 67
> hop-3), all n=200 (+66 hop-4). 2Wiki: primary n=100 (hop-2), all n=200
> (+100 hop-4).

## Headline — kill (iii) fires; the storage-boundary novelty is gone

| | musique | 2wiki |
|---|---|---|
| stale threat @ b=0.5 (arm a, top-10 rate) | 0.565 | 0.850 |
| after full dose 0.1 | **0.000** | **0.000** |
| arm (a) current recall **hop2–3 primary**, b=.5→.25→.1 | 0.6182→0.6306→0.6306 | 0.775→0.775→0.780 |
| primary delta vs hard filter, b=.5 | **−0.0124** | **−0.0050** |
| arm (a) current recall **all-hop**, b=.5→.25→.1 | 0.5367→0.5475→0.5475 | 0.6338→0.6375→0.6400 |
| all-hop delta vs hard filter, b=.5 | −0.0108 | −0.0062 |
| midrank Spearman ρ (a / d / e / b) | −0.9853 / −0.8748 / **−0.9853** / 0 | −0.9233 / −0.8515 / **−0.9233** / 0 |
| **kill (i)** — (d) vs (c) | **FIRED** (0.000 ≤ 0.000) | **FIRED** (0.005 ≤ 2SE 0.010) |
| **kill (ii)** — filter catches up on all 3 | not fired | not fired |
| **kill (iii)** — vs separated-graded (e) | **FIRED** | **FIRED** |
| arm (a) vs (e), all doses/current+audit | **bit-exact, max_abs=0** | **bit-exact, max_abs=0** |
| H-T3b **hop2–3 primary** (wrong supersede, b=.1) | 0.6306→0.5037 (−12.69pt) | 0.780→0.470 (−31.0pt) |
| H-T3b all-hop, b=.1 | 0.5475→0.4625 (−8.5pt) | 0.640→0.480 (−16.0pt) |

The previous "current recall through all doses = lossless" wording was false.
At b=0.5 the stale twin still occupies top-10 often enough to cost 1.24pt on
MuSiQue and 0.50pt on 2Wiki in the prereg primary population (all-hop:
1.08pt / 0.62pt). Loss becomes zero only at b=0.1 on these primary runs;
2Wiki also loses 0.50pt at b=0.25 (all-hop 0.25pt).

## What survived

**The pointwise conjunction**: one non-destructive `supersede()` write sinks a
maximally-confusable stale fact from 56–85% top-10 presence to **zero** with a
near-perfect tie-correct dose-response curve (ρ −0.9233…−0.9853), reaches zero stale support at
b=0.1 without current-recall loss at that dose, and keeps the stale fact
reachable for audit. The bi-temporal hard
filter matches or exceeds current-recall and wins audit@10 (1.0 by
construction) but is
**structurally incapable of dose-response** (ρ≡0: rank is dose-invariant) —
graded supersession keeps a capability the binary filter cannot express, so
kill (ii) does not fire. This capability is **not unique to one-field storage**.

## What died

**kill (i) fired on both datasets**: κ=1 vs κ=0 traversal probes do not
clear the prereg `>2*SE` threshold. MuSiQue is exactly 0.000; 2Wiki is
0.005 with `2*SE=0.010` — small, but not zero. Supersession-in-
PROPAGATION adds nothing here, for two visible reasons: (1) traversal probes
abstain ~90% (T5 trip rates), and (2) the seed already carries b algebraically
(spec §2.3: exp(W/τ) = exp(α/τ)·b^{λ_b/τ}) — the conductance leg is redundant
where the seed does the work. Combined with T5 (traversal refused on both
worlds), **the §4 novelty sentence must drop its multi-hop clause**:

> 허용 가능한 주장 (수정): "한 번의 비파괴 supersede write가 동일 snapshot의 선택
> 분포를 dose-graded로 재라우팅하며(binary filter가 구조적으로 표현 불가한
> dose-response 보존), superseded 사실은 도달가능·감사가능 상태로 남는다."
> — multi-hop 전파 재라우팅 절은 kill (i)로 사망.

**kill (iii) also fired on both datasets.** Arm (e) stores immutable graded
revision records and current pointers outside Hypergraph/WeightField, then
applies the same `lambda_b * log(strength)` at readout. It is bit-identical to
arm (a) for every current and audit score at every dose (`max_abs=0.0`), while
arm (d) beats it on none of stale suppression, current recall, historical audit
recall, or dose response by `>2*SE`. Therefore:

> Retract: "dose-graded pointwise retrieval requires one-field revision state."
> Retain: "a graded revision policy can reroute a selection distribution while
> preserving the superseded evidence for audit." The defensible systems work
> moves to atomic snapshots, replay/as-of, provenance and certified refusal.

## Honest costs (co-published, spec 의무)

- **H-T3b primary (hop 2–3)**: one WRONG supersede at full dose costs
  **−12.69pt (MuSiQue) / −31.0pt (2Wiki)** current recall. The retained
  all-hop values are −8.5pt / −16pt. "one write, three effects"의 쌍대는 "one wrong
  write, three corruptions". MemStrata AUROC 0.59 says supersession judgments
  WILL be noisy; deployment needs the wrong-write cost next to the right-write
  benefit.
- Traversal arm (d) audit@10 is dose-dependent (0.63–0.94 vs filter's constant
  1.0); pointwise arms (a/e) are 0.99–1.0. Reachability holds
  (Eilu-va-Eilu), but top-10 auditability can degrade with dose/readout.
- b=0.5 is not a harmless "light" write: besides incomplete stale suppression,
  it costs 1.24pt / 0.50pt primary current recall (all-hop 1.08pt / 0.62pt).

## Safety receipts added in S0

- Every injected and wrong-bridge mutation went through
  `readouts.supersede()`; 200 writes x 3 doses x 2 scopes per dataset were
  exact (`after == before * decay`). JSON includes deterministic SHA-256
  summaries for each receipt set.
- Forced traversal current-mode trip rates were 91.0–92.5% on MuSiQue and
  93.5–94.5% on 2Wiki. Results publish per-dose/per-arm current+audit trip
  counts, reasons, mean measured `n_eff`, and greedy-path receipt counts.
- The synthetic collateral loop directly restores b after each isolated trial;
  the report labels this reset as fixture hygiene, not a production write.

## Bug ledger (caught before landing)

1. argmin-cos injection = strawman (stale born at the bottom; nothing to sink)
   → argmax-cos threat model. 2. kill (ii) sign inversion (the better the
   graded arm expressed dose-response, the harder it "died") — caught on the
   live ρ values. 3. audit ≠ top-10 (reachability metric split from audit@10).
   4. `argsort(argsort)` broke Spearman ties by input order → midranks.
   5. prereg hop2–3 current/H-T3b had been averaged over hop-4 → primary/all-hop
   populations and n/composition now reported separately.

Files: `stale_poisoning_{musique,2wiki}_result.json`. Focused S0 tests:
`13 passed` (`test_stale_poisoning.py` + `test_readout_identity.py`).
