# HSWM — public repository index

> HSWM = Hypergraph Semantic Weight Map. 지향 정체성은 함수 단위가 LLM으로 실행되는 하이퍼그래프 시멘틱 신경망이며(가소성 학습 루프는 아직 미실행), 현재 측정으로 방어 가능한 범위는 **evidence-preserving memory substrate**까지다. 이 인덱스는 공개 저장소의 코드·설계·실험
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

목표 아키텍처의 범주도 고정했다. **HSWM = Hypergraph Semantic Weight Map**이며, 신경망적
함수 단위가 LLM으로 동작하는 하이퍼그래프 기반의 거대 시멘틱 신경망이다. hypergraph \(H\)가
함수·상태의 n-ary 연결 구조를, Semantic Weight Map \(W\)가 그 사이의 거시 가중치·활성·
routing을 이룬다. HSWM 전체가 persistent recurrent state, credit, acceptance,
weight/topology rewrite를 소유한다. 이는 목표 정체성이며 현재 효능 주장이 아니다.
정본은
[`CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`](CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md)다.
함수 계약, 실행 cycle, 코드 대응, 구현 가능성, 실패 모드와 결정적 실험은
[`HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md`](HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md)에 고정했다.

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
- 결정적 비교 설계 lock: [`_research/shared_field_hypothesis/`](_research/shared_field_hypothesis/) — shared field 대 separate heads에서 비교할 예산 차원·카운터 계약과 독립 selection·revision·감사 지표를 잠금. 현재 `DESIGN_LOCKED_NOT_PREREGISTERED`이며 v1은 모든 run을 거부한다
- 경계: 설계 수식은 `SECONDARY_AI_RESEARCH_AND_DESIGN`; B2.1 수치는 별도 prereg·실측·감사·LakatoTree receipt에 근거한다.

### P0–P4 전환 상태와 최신 falsifier

| 단계/실험 | 현재 판정 | 산출물 |
|---|---|---|
| P0 identity/metric | 목표 정체성 고정. 함수/agent process가 LLM으로 실행되고 `H,W`가 그 거시 신경망을 구성 | [canon](CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md) |
| P1 closed learning loop | 사전등록 완료, `eligibility_tag`/`M_commit`/loop harness 미구현·미실행 | [prereg](PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json) |
| B2 routing signal | 최선 slice oracle +9.92pp, tie 75%; pooled 분포는 tie kill. 얇은 oracle signal이지 learned 성공 아님 | [result](B2_ROUTING_SIGNAL_RESULTS_2026-07-23.md) · [evidence](EVIDENCE_B2_ROUTING_SIGNAL_2026-07-23.json) |
| E1 conditional traversal | bridge −13.89pp, factoid −7.27pp. 전면 OFF 유지 | [result](E1_CONDITIONAL_TRAVERSAL_RESULTS_2026-07-23.md) · [evidence](EVIDENCE_E1_CONDITIONAL_TRAVERSAL_2026-07-23.json) |
| P3 shadow topology absorption | 0/3 수용, canary 100%, sealed Δ0. 안전하지만 후보가 무득 | [result](SHADOW_GATED_ABSORPTION_RESULTS_2026-07-23.md) · [evidence](prom_search_hswm/evidence/EVIDENCE_shadow_gated_absorption_20260723.json) |
| prior-art tribunal | generic graph three-factor+sleep novelty는 사망; n-ary credit/LLM verdict/topology/shared persistent field 슬롯 생존 | [tribunal](TRIBUNAL_PHASOR_AGENTS_PRIOR_ART_2026-07-23.md) |

## 2026-07-23 paper–code absorption gate

11개 외부 시스템을 이름이 아니라 paper–code pair로 고정했다. 현재 상태는
`SOURCE-LOCKED / NOT ACTIVATED`이며, 외부 성능 수치를 HSWM 성과로 간주하지 않는다.

- 배포 경계: [`ABSORB_CONTRACT_v1.md`](ABSORB_CONTRACT_v1.md)
- 흡수 판단·우선순위·falsifier: [`PAPER_CODE_ABSORPTION_LEDGER_2026-07-23.md`](PAPER_CODE_ABSORPTION_LEDGER_2026-07-23.md)
- 기계 판독 게이트: [`manifest.v1.json`](_research/competitor_absorption/manifest.v1.json) · [`verify_sources.py`](_research/competitor_absorption/verify_sources.py)
- 재현 provenance: [`source_locks/`](_research/competitor_absorption/source_locks/)

제3자 clone·PDF·추출문은 저장소에 vendor하지 않는다. 공개 저장소에는 upstream commit,
paper URL/SHA-256, license route, code anchor와 default-off disposition만 둔다.

## 복구된 미게시 연구 묶음

최신 `main`보다 뒤처진 별도 작업 미러에서 아래 묶음을 원래 provenance와 함께 복구했다.
기존 `main`을 미러로 덮지 않고, 현재 정본 위에 독립 산출물로 이식했다.

| 묶음 | 공개 경계 | 산출물 |
|---|---|---|
| H3-B3 V5 재현성 | 이미 공개된 V5 run manifest가 고정한 source/prereg/test를 복구. 기존 refusal·효능 판정은 변경하지 않음 | [V5 prereg](H3_B3_V5_RESTART_PREREG_2026-07-20.md) · [C0 diagnosis](H3_C0_CHAIN_VIABILITY_DIAGNOSIS_2026-07-20.md) |
| World Compiler S4.0 | 가역적 entity binding 수직 slice와 OSS 비교. `claim_weave`·`chain_viability`는 미구현 | [receipt](S4_0_REVERSIBLE_ENTITY_BINDING_2026-07-21.md) · [PROM](WORLD_COMPILER_V2_OSS_PROM_2026-07-21.md) |
| R3 walk-regime density dial | PhantomWiki regime-swap 사전등록과 실행 코드. 결과·성능 주장은 아직 없음 | [prereg](PREREG_R3_WALK_REGIME_2026-07-23.json) · [`r3_walk_regime.py`](r3_walk_regime.py) |

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
| [`_research/competitor_absorption/`](_research/competitor_absorption/) | 외부 paper–code source lock, license gate, default-off absorption manifest |
| [`_research/shared_field_hypothesis/`](_research/shared_field_hypothesis/) | shared field 대 separate heads의 fail-closed 동등예산 실험 계약 |

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

1. shared-field v2에 artifact-derived event/parameter counter, 외부 LakatoTree prediction receipt, neutral replay/full-candidate score-pack, frozen input, 수치 cap, 통계 설계를 함께 바인딩한 뒤에만 `PREREGISTERED_UNRUN`으로 승격
2. B2.2 full score-component pack + fast query-bond learner; 반복된 효과만 slow `Delta ell`로 증류
3. 독립 selection action과 evolving-knowledge cohort 구현
4. relation/type/role compatibility와 adapter registry
5. cyclic connector graph의 budgeted readout
6. `hswm_plasticity_loop.v1.json`의 durable reducer·event log·typed proposal compiler 구현
7. 두 번째 benchmark 및 Agent-A-write → Agent-B transfer
8. fresh-clone 기본 명령 `uv run --extra dev pytest -q`를 재생하는 server-owned certification

## 공개 경계

- `prom_search_hswm/data/gold_badiou24.json`만 Tier-1 구조 테스트용으로 provenance와
  SHA-256을 고정해 공개한다. 나머지 로컬 gold/source·외부 benchmark 입력은 계속 ignore하며,
  공개 전 별도 privacy/license 검토가 필요하다.
- 문서 속 USER 원문은 canonical user direction이다. 수식·타입·API와 연구 해석은
  SECONDARY_AI이며, 사용자가 별도로 승인하지 않은 성능 주장을 canon으로 승격하지 않는다.
