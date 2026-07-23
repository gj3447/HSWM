# HSWM — public repository index

> HSWM = Hypergraph Semantic Weight Map. 현재 방어 가능한 역할은 **reasoner가 아니라
> evidence-preserving memory substrate**다. 이 인덱스는 공개 저장소의 코드·설계·실험
> 영수증만 가리킨다.

## 현재 설계 결론

2026-07-22의 핵심 수정은 “고정된 1층/2층”을 없앤 것이다.

\[
\operatorname{compose}_{\beta}(H_1,\ldots,H_n)\in\mathsf{HSWM}
\]

- HSWM은 typed ports와 evidence-bearing n-ary connectors를 가진 open weighted
  hypergraph다.
- 원자 HSWM과 합성 HSWM은 같은 타입이다. 합성체를 다시 연결·분리·전문화할 수 있다.
- 저장 정규형은 flat mount/port/connector manifest다. 재귀는 인터페이스에만 있다.
- `compose`는 구조를 연결하고, `materialize`만 legacy `Field` quotient를 만든다.
- MoE는 고정 top router가 아니라 query-time bounded expert coalition으로 해석한다.
- learned `CONNECT / SEPARATE / SPECIALIZE` 정책은 아직 구현되지 않았다. 현재 구현은
  결정론적 커널이며, 2026-07-23에 weight·routing·topology를 분리한 가소성 의미론과
  fail-closed loop 계약까지 설계됐다.
- B2.1에서 frozen `A / B / MERGED` 위 shared-ridge router를 실제 학습했지만, 표준
  54셀 전부 `ABSTAIN -> MERGED`로 붕괴해 `REJECTED`됐다. primary gold oracle의
  최소 headroom도 `+0.010870 < +0.02`라 router-only 행동공간 자체가 부족하다.
- B2.2 사전 진단에서 manifest의 `SemanticWeight`가 B2 readout에는 아직 inert였음이
  확인됐다. pure bond-readout binding을 추가했고, fine query-edge 상한은
  `+0.048913/+0.083333`이지만 static edge-ID suppression은 6/6 validation/test Δ0였다.

정본 설계는
[`SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md`](SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md),
반례 기반 수리는
[`AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md`](AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md)에 있다.

## 2026-07-23 가소성 PROM

학습은 weight 조절을 포함하지만 그것으로 끝나지 않는다. 기존 bond의 중요도는 weight가,
무엇이 실제로 묶이는지는 topology가, 지금 어떤 HSWM coalition을 실행할지는 routing policy가
학습한다. query activation은 휘발 상태이며 durable learning으로 세지 않는다.

- 종합 보고서: [`PROM_HSWM_PLASTICITY_WEIGHT_TOPOLOGY_LEARNING_2026-07-23.md`](PROM_HSWM_PLASTICITY_WEIGHT_TOPOLOGY_LEARNING_2026-07-23.md)
- 실행 루프 계약: [`hswm_plasticity_loop.v1.json`](prom_search_hswm/fsm/hswm_plasticity_loop.v1.json)
- 첫 실험 결과: [`B21_LEARNED_ROUTER_RESULTS_2026-07-23.md`](prom_search_hswm/docs/B21_LEARNED_ROUTER_RESULTS_2026-07-23.md) — B2.1 router-only `REJECTED`
- 다음 설계: [`B22_QUERY_BOND_WEIGHTING_DESIGN_2026-07-23.md`](prom_search_hswm/docs/B22_QUERY_BOND_WEIGHTING_DESIGN_2026-07-23.md) — fast query-bond attention을 먼저 검증하고 반복 효과만 slow `Delta ell`로 증류
- 경계: 설계 수식은 `SECONDARY_AI_RESEARCH_AND_DESIGN`; B2.1 수치는 별도 prereg·실측·감사·LakatoTree receipt에 근거한다.

## 2026-07-22 연구 장부

| 갈래 | 결과 | 산출물 |
|---|---|---|
| shared semantic hypergraph NN | 사용자 방향과 AI 형식화를 분리해 W/graph/agent-transfer 경계를 고정. 이론 lock이며 성능 판정 아님 | [spec](SPEC_SHARED_HYPERGRAPH_NN_SEMANTIC_WEIGHT_2026-07-22.md) |
| P1 binding density | semantic 0.2121, lexical CONTAINS 0.0, MC-null z 6.56, `progressive` | [PROM mirror](prom_search_hswm/INDEX.md) |
| P4 equal-compute | semantic−control 0.0303, novel 미달, `partial / degenerating`; 1-pass Jaccard 0.4242가 semantic 0.2121보다 높음 | [PROM mirror](prom_search_hswm/README.md) |
| P5 fixed multi-view routing | hard-4 Δ0, full-chain −0.0125, `REJECTED / degenerating` | [report](PROM_P5_MULTIVIEW_HARDHOP_2026-07-22.md) |
| P6 semantic-residual absorption | fresh unseen 3회 모두 손해라 FSM이 3/3 거부; sealed Δ0, `equivalent / degenerating` | [report](PROM_P6_CONTINUAL_ABSORPTION_FSM_2026-07-22.md) |
| Phase B field algebra | immutable content-addressed Field, merge/split/compose, L1–L4 10/10 | [design](DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md) |
| B1 identity material | MuSiQue legal chain 0→6, 2Wiki 0→25; 후속 T1/T2 공통 성공은 미달 | [B1](B1_IDENTITY_UNLOCK_RESULTS_2026-07-22.md) · [T1](T1_ENTRANCE_REACH_RESULTS_2026-07-22.md) |
| B2 federated merge | cross-field +0.2137, seam +0.0342, `progressive`; in-field −0.0648로 no-harm 위반 | [result](prom_search_hswm/docs/B2_CROSSFIELD_MERGE_RESULTS_2026-07-22.md) |
| B2.1 learned router | 2벤치 × 3 partition × 3 k × 3 seed = 54셀 전부 abstain; primary Δ0, oracle ceiling min +0.01087로 router-only `REJECTED / degenerating` | [result](prom_search_hswm/docs/B21_LEARNED_ROUTER_RESULTS_2026-07-23.md) |
| B2.2 bond weighting 진단 | fine top-20 oracle +0.0489/+0.0833; train-only static sparse patch는 6/6 calibration·test Δ0. query-bond 쪽 room만 확인, confirmatory claim 아님 | [design](prom_search_hswm/docs/B22_QUERY_BOND_WEIGHTING_DESIGN_2026-07-23.md) · [diagnostic](prom_search_hswm/evidence/DIAG_b22_fine_bond_action_headroom_20260723.json) |
| PROM-8 / R1 | dynamic two-lane 처방. R1 T1 minimum 0→2, 2Wiki depth-2 0→4, MuSiQue 0 | [PROM-8](PROM_8_DYNAMIC_TWO_LANES_2026-07-22.md) · [R1](R1_T1_RETRY_RESULTS_2026-07-22.md) |
| open composition v2r3 | target 59/59, expanded 78/78, injected negative 2/2. 구조 closure는 통과했지만 LakatoTree는 `partial`, certificate=false | [amendment](AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md) · [judgment](prom_search_hswm/judgments/OPEN_COMPOSITION_20260722/V2_JUDGMENT.md) |

## 저장소 지도

| 경로 | 역할 |
|---|---|
| [`README.md`](README.md) | 공개 구현의 현재 claim boundary와 실행법 |
| [`EFFICACY.md`](EFFICACY.md) | 효능 주장과 반증 결과의 장부 |
| [`world_ir.py`](world_ir.py), [`world_compiler.py`](world_compiler.py) | evidence-preserving world compiler |
| [`field_snapshot.py`](field_snapshot.py), [`certified_readout.py`](certified_readout.py) | immutable field cut와 fail-closed readout |
| [`prom_search_hswm/`](prom_search_hswm/) | PROM→HSWM, field algebra, federated merge, open-composition 연구 코드와 영수증 |
| [`prom_search_hswm/hswm_open_kernel.py`](prom_search_hswm/hswm_open_kernel.py) | v2r3 open self-similar deterministic kernel |
| [`prom_search_hswm/test_hswm_open_kernel.py`](prom_search_hswm/test_hswm_open_kernel.py) | v2r3 반례·불변식 테스트 |
| [`prom_search_hswm/prom_b21_learned_router.py`](prom_search_hswm/prom_b21_learned_router.py) | frozen HSWM arm 위 B2.1 learned router·conformal abstention harness |
| [`prom_search_hswm/hswm_bond_readout.py`](prom_search_hswm/hswm_bond_readout.py) | slow `ell`과 volatile query-bond potential을 분리 적용하는 pure deterministic module |
| [`prom_search_hswm/test_hswm_bond_readout.py`](prom_search_hswm/test_hswm_bond_readout.py) | neutral parity·coverage·monotonic suppression·shift invariance 19 tests |
| [`prom_search_hswm/fsm/hswm_plasticity_loop.v1.json`](prom_search_hswm/fsm/hswm_plasticity_loop.v1.json) | weight→routing→topology 후보의 bounded proposal/evaluation/activation 계약 |
| [`prom_search_hswm/evidence/`](prom_search_hswm/evidence/) | preregistration, evidence, neutral judge packet, injected negative |

## 검증·판정 경계

재현 가능한 현재 구조·가소성 관련 회귀:

```bash
python3 -m pytest \
  prom_search_hswm/test_hswm_open_kernel.py \
  prom_search_hswm/test_hswm_open_composition.py \
  prom_search_hswm/test_hswm_field_algebra.py \
  prom_search_hswm/test_hswm_b2_crossfield.py \
  prom_search_hswm/test_hswm_absorption_fsm.py \
  prom_search_hswm/test_hswm_b21_learned_router.py \
  prom_search_hswm/test_hswm_bond_readout.py \
  tests/test_additive_floor.py \
  tests/test_supersede_confluence.py \
  tests/test_field_snapshot.py -q
```

2026-07-23 재실행 결과는 `132 passed`다.
테스트 통과는 harness/불변식 closure이고, 성능 판정은 별도 evidence와 receipt를 따른다.

LakatoTree `LakatosTree_HSWM_SolidMultiAgent_20260722 /
ENG-open-composition-kernel-v2r3`의 receipt-chain verdict는 `partial`이고 receipt는
`c000bd063ded7d89b4123bb50cc34a7c38ef66a244514e9a555f3edb38e97a60`이다.
`verify_verdict`는 `ok=true`지만 server-owned measurement, calibration, reproducibility
certificate가 닫히지 않아 `certified=false`다.

## 다음 frontier

1. relation/type/role compatibility와 adapter registry
2. cyclic connector graph의 budgeted readout
3. `hswm_plasticity_loop.v1.json`의 durable reducer·event log·typed proposal compiler 구현
4. B2.2 full score-component pack + fast query-bond learner; 반복된 효과만 slow `Delta ell`로 증류
5. 두 번째 benchmark 및 Agent-A-write → Agent-B transfer
6. 올바른 `python3 -m pytest` replay를 쓰는 server-owned certification

## 공개 경계

- `prom_search_hswm/data/`의 로컬 gold/source 파일은 저장소의 일반 `data/` ignore 규칙
  때문에 공개 Git에 포함되지 않는다. 해당 입력을 공개하려면 별도 privacy/license 검토가
  필요하다.
- 문서 속 USER 원문은 canonical user direction이다. 수식·타입·API와 연구 해석은
  SECONDARY_AI이며, 사용자가 별도로 승인하지 않은 성능 주장을 canon으로 승격하지 않는다.
