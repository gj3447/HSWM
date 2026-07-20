# HSWM QKV structure results — 2026-07-20

## Verdict

The QKV idea is structurally meaningful, but its first real-data treatment did
not increase multi-hop retrieval ability across both datasets.

- The exact ordered router passes all 64/64 synthetic order-collision cases.
- The no-label B1-QKV treatment fails the frozen real-data development gate on
  both MuSiQue and 2Wiki.
- On 2Wiki, one evidence-linked query update is useful, but the second update
  lowers nDCG relative to matched K1.
- On MuSiQue, K2 is worse than both K1 and cosine and applies fully to only 40%
  of held development-test queries.

Therefore the current result supports **an evidence-bound ordered associative
memory mechanism**, not **HSWM reasoning uplift**.

## What changed conceptually

`typed_composition.py` already had key-like source predicates, value-like target
claims/selectors, and active claim continuity. Its query terms, however, stay
fixed across every hop. The new probes isolate the missing causal claim:

```text
selected V_t becomes part of Q_(t+1)
```

Two implementations test that claim without replacing the existing H3 arm:

1. `qkv_routing.py` performs exact ordered `(frontier, relation) -> Value`
   routing with complete endpoint receipts and atomic refusal.
2. `qkv_b1_probe.py` uses the raw-question BGE vector as Q, paragraph vectors
   as K, and only exact-title-linked target paragraph vectors as V. Each layer
   executes `q_(t+1) = normalize(q_t + gamma * value_read)`.

## A. Synthetic ordered-routing falsifier

Fixture per world:

```text
A --alpha--> B --beta--> D
A --beta----> C --alpha-> E
```

The relation bags are identical but their order changes the terminal. Thirty-two
isomorphic worlds produce 64 programs.

| gate | result |
|---|---:|
| ordered K2 exact terminal | 64 / 64 |
| matched K1 reaches a K2 terminal | 0 / 64 |
| second-step key-null survives | 0 / 64 |
| second-step value-null survives | 0 / 64 |
| unseen relation atomic refusal | 64 / 64 |
| ambiguous key atomic refusal | 64 / 64 |
| V-to-next-Q receipt chain valid | 64 / 64 |
| K1 route unchanged by second-step nulls | 64 / 64 |
| input-order/repeat determinism | 64 / 64 |
| unordered bag-control accuracy | 32 / 64 |

Result: `PASS`, receipt
`qkv_routing_result.json` (`result_sha256 =
4004a0a455a7bdff05b5e65875111718f9601b34cf458864948ff376ae6cada0`).

This proves only that the ordered address/value algebra has teeth. It does not
test raw-language decomposition or real retrieval.

## B. B1-QKV real-data development falsifier

### Boundary

- MuSiQue development-v4: 200 exact query preimages, 2,094 paragraph targets,
  958 admitted title-evidence arcs.
- 2Wiki development-v4: 198 exact query preimages, 1,505 targets, 1,100 arcs.
  Two historical trailing-space query-vector mismatches were excluded
  fail-closed.
- The scorer saw vectors and the B1 evidence graph only. Gold IDs and relation
  labels were joined after scoring.
- Policy selection used the relation/evidence-disjoint validation half. The
  numbers below are from the held development-test half: MuSiQue 100 queries,
  2Wiki 98.
- No fresh segment or B3 extraction entered this experiment.

Frozen grid: `seed_k in {3,10}`, `temperature in {.05,.10,.20}`, `gamma in
{.10,.25,.50,1.0}`, K2. Cluster bootstrap uses 10,000 draws over the existing
relation/evidence components.

### Held development-test results

| dataset | arm | nDCG@10 | ASR@10 | support recall@10 |
|---|---|---:|---:|---:|
| 2Wiki | cosine | 0.678094 | 0.091837 | 0.594388 |
| 2Wiki | QKV K1 | **0.763328** | 0.204082 | **0.719388** |
| 2Wiki | QKV K2 | 0.727862 | **0.214286** | 0.704082 |
| MuSiQue | cosine | **0.585216** | 0.160000 | 0.562500 |
| MuSiQue | QKV K1 | 0.582733 | **0.210000** | **0.584167** |
| MuSiQue | QKV K2 | 0.567494 | 0.170000 | 0.560833 |

Selected policies:

- 2Wiki: `seed_k=10, temperature=.05, gamma=.25`;
- MuSiQue: `seed_k=3, temperature=.05, gamma=.10`.

Primary K2-minus-K1 effects:

| dataset | metric | mean delta | component-bootstrap 95% CI |
|---|---|---:|---:|
| 2Wiki | nDCG@10 | **-0.035466** | [-0.040210, 0.017203] |
| 2Wiki | ASR@10 | +0.010204 | [-0.214286, 0.022556] |
| MuSiQue | nDCG@10 | **-0.015238** | [-0.035375, -0.000106] |
| MuSiQue | ASR@10 | **-0.040000** | [-0.092308, -0.008850] |

2Wiki K2 still beats cosine on nDCG by `+0.049768` with CI
`[+0.040943, +0.163923]`, and beats all five degree-preserving Value shuffles.
But matched K1 is better on nDCG, so the second recurrent layer—the proposed
reasoning mechanism—is not the cause of the strongest result. Its ASR gain over
cosine also has lower CI `0.0`, not strictly positive.

MuSiQue K2 has full-depth apply coverage `0.40`, loses to K1 and cosine, and
does not beat the five nulls. Both datasets preserve the `gamma=0` cosine floor
bit-identically.

Result: `B1_QKV_REAL_DATA_GATE_FAILED`, receipt
`qkv_b1_development_result.json` (`result_sha256 =
8c128bd1db96c7a2b00791b208c3c19a478cd6952edabcbce67b302385f0e955`).

## Interpretation

This result separates three claims that were previously conflated:

1. **Does a Q/K/V-like structure exist?** Yes. Ordered, evidence-bound Values
   can deterministically become the next Query frontier.
2. **Can one associative read help retrieval?** Sometimes. The 2Wiki K1 result
   is a real development signal worth preserving.
3. **Does stacking those reads currently create reasoning ability?** No. K2
   loses nDCG to K1 on both datasets and fails the cross-dataset gate.

The likely bottleneck is not the absence of another graph layer. B1 title links
are weak semantic keys; adding a target paragraph vector does not reliably
remove the relation already answered or isolate the next one. The query vector
therefore drifts, and second-hop error compounds. MuSiQue also contains DAG and
comparison-style programs that cannot be represented by one recurrent frontier.

## Next admissible experiment

The next serious arm is B3-QKV, not a deeper B1 stack:

- finish a valid development extraction so every candidate paragraph has
  admitted n-ary claims;
- embed only evidence-bound `predicate + argument role` preimages as Keys;
- keep Values symbolic: target claim, join entity, and both exact selectors;
- compare K2 against matched K1, the current typed K2 arm, and `rho=0` query
  residual ablation;
- require query, Key, Value, and second-edge shuffles to kill the effect;
- stop at development unless both datasets clear the existing H3 margins.

The current 434-row partial extraction cache cannot support that test. A new
sealed extraction/key artifact is required. No fresh QKV claim is authorized by
the results in this document.
