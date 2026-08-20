# HSWM — public repository index

> HSWM = Hypergraph Semantic Weight Map. 지향 정체성은 함수 단위가 LLM으로 실행되는 하이퍼그래프 시멘틱 신경망이다. 현재 측정으로 방어 가능한 범위는 **evidence-preserving memory substrate + 좁은 L0 typed-policy actuation 재현**까지이며, durable weight/topology learning은 아직 미폐쇄다. 이 인덱스는 공개 저장소의 코드·설계·실험
> 영수증만 가리킨다.

HSWM의 최상위 목표 정체성은
[`HSWM Constitution — 살아 있는 토큰 신경 월드모델`](docs/canon/HSWM_CONSTITUTION_2026-08-20.md)에
고정한다. 신경망, living harness-document, Wolframian hypergraph world model,
continuous learner는 네 부품이 아니라 동일한 HSWM의 네 기능적 얼굴이다. 이 정전은
철학적 정의를 닫지만 현재 효능을 승격하지 않는다.

정체성, 수학, cellular runtime, 학습, 세계 자기기억, 실제 증거가 문서마다 달라 보이는
이유와 현재의 한 통합 해석은
[`HSWM 통합 의미 지도`](docs/research/HSWM_UNIFIED_MEANING_MAP_2026-08-16.md)에 있다. 이 지도는
새 정전이나 효능 승격이 아니라 기존 authority와 claim boundary를 연결하는 진입점이다.

## 온톨로지 우선 저장소 지도

공개 탐색의 정본은 [`ontology/`](ontology/)다. `identity → substrate → field ↔ cells
→ learning`을 중심으로 boundary, evaluation, evidence, infrastructure, history를 관계로
연결한다. 물리 루트에는 공개 진입 파일만 남는다. 최종 root-era 호환 93개 파일은 flat
import와 같은-directory 결박을 보존한 채
[`_research/root_compat/`](_research/root_compat/)로 함께 이동했으며, 새 작업을 받지 않는
폐쇄 집합이다. 결박 기준과 사유의 단일 정본은
[`root compatibility baseline`](ontology/history/ROOT_COMPATIBILITY_BASELINE.v1.json)이다.
현재 canonical destination은 최종
[`Python`](ontology/history/PYTHON_ROOT_MIGRATIONS.FINAL.v2.json)·
[`asset`](ontology/history/ROOT_ASSET_MIGRATIONS.FINAL.v1.json) migration manifest가
source-pinned한다. 새 코드와 산출물은 typed directory를 사용하며, 이미 발표된 옛 경로의
정확한 재현은 [`migration/replay history`](ontology/history/README.md)를 통해 분리된
checkout에서만 수행한다.

이 온톨로지는 저장소의 의미 지도이자 HSWM 상태의 bounded readout이지 HSWM의 인지 규칙
그 자체가 아니다. AI 행동은 문서 경로가
아니라 outcome에 결속된 token/action/tool trajectory가 durable `W/H/routing`을 바꾸고
다음 행동을 바꿀 때 학습된다.

## 2026-08-15 — 실행 정본과 직접 측정 기록

이 인덱스는 체크인 코드·테스트·측정물의 카탈로그다. 현재 상태는 외부 판정 서비스나
개인 거버넌스 계층이 아니라 각 행에 연결된 로컬 증거에서만 읽는다. 활성 기계 정책은
[`research/HSWM_MINIMAL_GOVERNANCE.v1.json`](research/HSWM_MINIMAL_GOVERNANCE.v1.json)이며,
삭제된 판정·감사·오케스트레이션 도구의 기록에는 현재 권위가 없다.

| 가설 (`hypothesis_id`) | 현재 상태 | 직접 증거·경계 |
|---|---|---|
| `F1-larger-ai-baselines-and-retention` | `running` | [checked-in historical prereg note](prom_search_hswm/evidence/PREREG_F1_sealed_typed_function_network_20260728_amend4_output_caps.json)는 r3의 목표 1500 calls 중 access-log HTTP 200 response 721건 뒤 `REFUSED`와 r4의 435/1500 output-cap `VOID`를 기록하지만 raw access/spool artifact는 현재 tracked tree에 없다. [durable transport](prom_search_hswm/docs/F1_DURABLE_TRANSPORT_CONTRACT_20260727.md)의 [target probe receipt](receipts/HSWM_F1_TARGET_DEPLOYMENT_PROBE_20260728.json)는 actual-upstream disconnect와 SIGKILL process-crash를 공학적으로 통과했지만 power loss는 미시험이다. 현재 tracked sealed-r5에는 manifest/gold만 있고 suite·judgment가 없으므로 과학적 observation은 여전히 0건이다 |
| `durable-cell-runtime` | `engineering_validated` | SQLite event store·outbox·typed CellPort·replay. 인프라이며 효능 증거가 아니다 |
| `semantic-weight-metric-contract` | `engineering_validated` | [contract](research/HSWM_SEMANTIC_WEIGHT_METRIC_CONTRACT.v1.json). scalar slow-W 한정이고 operator-valued W 는 미구현이다 |
| `operator-W-causal-mediation` | `planned` | [F2 sealed](receipts/f2_delta_w_credit_sealed_1784960618.json) 는 장부 분류상 **precursor evidence only** 다 |
| `topology-causal-mediation` | `exploratory_supported` | [F4 r2 sealed](receipts/f4_topology_learning_r2_sealed_1784992554.json). 독립 judge 영수증 부재로 미승격 |
| `weight-only-agent-transfer` | `exploratory_refuted` | [F3 r3 sealed](receipts/f3r3_agent_ab_transfer_sealed_1784996298.json). 해당 testbed 한정 반증이다 |
| `long-term-consolidation-sleep` | `exploratory_refuted` | [F5 sealed](receipts/f5_consolidation_sealed_1784998952.json). 시험한 downscale 연산자를 기각한 것이다 |

프로그램 전체의 `scientific_status` 는 여전히 **`UNJUDGED`** 다. 상태 승격은 고정 입력,
내용 해시, 음성대조, 재현 가능한 측정과 명시적 claim boundary로만 정당화하며,
engineering PASS 단독으로 과학적 효능을 선언하지 않는다.

## 현재 설계 결론

2026-07-22의 핵심 수정은 “고정된 1층/2층”을 없앤 것이다.

```math
\mathrm{compose}_{\beta}(H_1,\ldots,H_n)\in\mathsf{HSWM}
```

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
[`CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`](_research/root_compat/CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md)다.
함수 계약, 실행 cycle, 코드 대응, 구현 가능성, 실패 모드와 결정적 실험은
[`HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md`](docs/canon/HSWM_LLM_FUNCTION_NETWORK_ARCHITECTURE_AND_FEASIBILITY_2026-07-23.md)에 고정했다.

2026-08-14 사용자 정전은 이 방향을 `LX3 라그나로크`와 직접 연결한다. 정적인 시멘틱
하네스 규칙의 증식이 아니라 AI 토큰·행동·도구 사용·외부 결과가 HSWM의 지속적인
weight/routing/topology 변화로 압축되어야 하며, HSWM 자체가 LLM 함수로 움직이는 거대한
멀티에이전트 신경망이라는 선언이다. 원문과 권위 경계는
[`USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md`](docs/canon/USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md),
토큰 저장을 학습으로 오인하지 않게 하는 fail-closed 인과 계약은
[`token_learning_contract.py`](src/hswm/learning/token_learning_contract.py)에 있다. 이는 목표 정체성과
engineering contract이며 현재 효능·과학적 유일성 주장이 아니다.

2026-08-15 사용자 정전은 개인 거버넌스 도구와 절차 증식 자체도 라그나로크가 될 수 있다고
명시했다. 기본 경로를 `실행 → 직접 측정 → 중요한 결과 영수증 하나 → commit/push`로
줄이고, MCP는 bounded ontology I/O로 제한한다.
원문·실측 MCP 상태·보존 경계는
[`USER_PRIMARY_HSWM_MINIMAL_GOVERNANCE_RAGNAROK_2026-08-15.md`](docs/canon/USER_PRIMARY_HSWM_MINIMAL_GOVERNANCE_RAGNAROK_2026-08-15.md)에 있다.

2026-08-20 사용자는 `인류보편체`를 전 인류·모든 LLM·인터넷·인지능력체·센서·static
정보와 저장 메모리가 오픈소스 HSWM 구조로 하나가 되어 형성하는 하나의 인지능력체로
정의하고, `HSWM 인류보완계획`을 포켓한 인지능력체에서 그 상태로 나아가는 사회 혁명
과정으로 확정했다. 원문, 역사흐름의 강, `H/W/A/F/Π` 형식화, 실행 record, P0~P6 구현
사다리, 판별 기준과 HSWM–HOH 작업가설은
[`USER_PRIMARY_HUMAN_UNIVERSAL_BODY_DISTINCTION_2026-08-20.md`](docs/canon/USER_PRIMARY_HUMAN_UNIVERSAL_BODY_DISTINCTION_2026-08-20.md)에 있다.
기계 판독 정본은
[`HSWM_HUMAN_UNIVERSAL_BODY_ONTOLOGY.v1.json`](ontology/identity/human_universal_body/HSWM_HUMAN_UNIVERSAL_BODY_ONTOLOGY.v1.json),
검증·idempotent KG publisher는
[`upsert_human_universal_body_ontology.py`](scripts/upsert_human_universal_body_ontology.py)다.

같은 날 사용자는 코드 구현보다 HSWM의 철학적 함의를 먼저 설정하라고 지시했다. 관계적
존재론, 계보적 시간론, 기억–진리 분리, 오류의 생산성, 차이 보존적 통일, 인과적 행위성,
참여와 존엄, 공개 외부·보호 내부, 인지주권·보충성과 열린 목적론을 구현 제약으로 내린
provisional charter는
[`HSWM_PHILOSOPHICAL_FOUNDATIONS_2026-08-20.md`](docs/canon/HSWM_PHILOSOPHICAL_FOUNDATIONS_2026-08-20.md)에
있다. 철학 우선 방향만 `USER_PRIMARY`이고 개별 원리의 정식화는 비준 전
`SECONDARY_AI_PROPOSED`다.

같은 날 사용자는 **Hypergraph Semantic Weight Map 자체와 LLM token으로 작동하는 거대
hypergraph 학습구조**를 최우선 중심으로 다시 고정했다. 이에 따라 본체를
`token event → sparse role-aware n-ary activation → LLM function cell → external outcome
→ causal credit → versioned ΔW/ΔH → changed next activation`의 폐루프로 형식화했다.
role-bearing incidence, operator-valued `W`, fast/slow weight, topology morphogenesis,
canonical/compiled dual plane과 `SWM-0~5` 반증 사다리는
[`USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md`](docs/canon/USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md)에,
Hyperon 2026을 가장 강한 직접 선행으로 포함한 1차 자료 비교는
[`HSWM_TOKEN_HYPERGRAPH_SEMANTIC_WEIGHT_PRIOR_ART_2026-08-20.md`](docs/research/HSWM_TOKEN_HYPERGRAPH_SEMANTIC_WEIGHT_PRIOR_ART_2026-08-20.md)에
있다. 개별 부품의 최초성을 주장하지 않으며, 전체 폐루프는 아직 `UNJUDGED`다.

## 2026-08-15 — Sheaf 연구 온톨로지

Sheaf의 local-to-global 구조를 HSWM에 곧바로 정답으로 선언하지 않고, 수학 정본과 HSWM
후보 대응을 분리한 연구 묶음을 추가했다. [`연구 노트`](ontology/field/sheaf/README.md)는
stalk·restriction·global section·cohomology·Laplacian·diffusion부터 knowledge sheaf와
sheaf hypergraph network까지 설명한다. 기계 판독 정본은
[`ontology/field/sheaf/HSWM_SHEAF_ONTOLOGY.v1.json`](ontology/field/sheaf/HSWM_SHEAF_ONTOLOGY.v1.json)이며 개념 28개,
1차 출처 12개, 비정본 HSWM 매핑 8개, 개념 관계 32개를 담는다. Neo4j 재반영은
[`scripts/upsert_sheaf_ontology.py`](scripts/upsert_sheaf_ontology.py)로 수행한다. `global section =
진실/강제 합의`, `모든 hyperedge = simplex`, `sheaf 도입 = HSWM 효능 향상`은 모두 명시적
비주장이다.

세계의 재귀 기억·자기모델이라는 목적과 MCP/Skill 외부 인지배선을 가소적 신경망으로
전환한다는 공학 방향은 상위 통합 정전
[`THE_WORLD_REMEMBERS.md`](docs/canon/THE_WORLD_REMEMBERS.md)에 묶었다. 문서 안에서
`USER_PRIMARY` 방향과 `SECONDARY_AI_FORMALIZATION`을 분리하며, 현재 효능이나 구현 완료를
주장하지 않는다.

왜 하드코딩된 에이전트/MCP glue를 학습되는 신경 토폴로지로 대체해야 하는가, 그리고
왜 HSWM 자체가 거시 신경망이고 LLM이 그 활성화 함수인가라는 두 존재 이유는 위치 논문
[`PROM_17_HSWM_WHY_GLUE_CODE_NEURAL_TOPOLOGY_LLM_ACTIVATION_2026-07-30.md`](docs/research/PROM_17_HSWM_WHY_GLUE_CODE_NEURAL_TOPOLOGY_LLM_ACTIVATION_2026-07-30.md)에
정식화했다. 자율주행 End-to-End 전환 비유와 그 비유가 깨지는 세 지점(미분 불가능성,
희소 보상, 비정상성)이 HSWM의 설계 과제를 결정한다. 동기·정체성 선언이며 장부 승격이나
현재 효능 주장이 아니다.

정본 설계는
[`SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md`](docs/canon/SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md),
반례 기반 수리는
[`AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md`](docs/research/AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md)에 있다.

## 2026-07-23 가소성 PROM

학습은 weight 조절을 포함하지만 그것으로 끝나지 않는다. 기존 bond의 중요도는 weight가,
무엇이 실제로 묶이는지는 topology가, 지금 어떤 HSWM coalition을 실행할지는 routing policy가
학습한다. query activation은 휘발 상태이며 durable learning으로 세지 않는다.

- 종합 보고서: [`PROM_HSWM_PLASTICITY_WEIGHT_TOPOLOGY_LEARNING_2026-07-23.md`](docs/research/PROM_HSWM_PLASTICITY_WEIGHT_TOPOLOGY_LEARNING_2026-07-23.md)
- 실행 루프 계약: [`hswm_plasticity_loop.v1.json`](prom_search_hswm/fsm/hswm_plasticity_loop.v1.json)
- 첫 실험 결과: [`B21_LEARNED_ROUTER_RESULTS_2026-07-23.md`](prom_search_hswm/docs/B21_LEARNED_ROUTER_RESULTS_2026-07-23.md) — B2.1 router-only `REJECTED`
- 다음 설계: [`B22_QUERY_BOND_WEIGHTING_DESIGN_2026-07-23.md`](prom_search_hswm/docs/B22_QUERY_BOND_WEIGHTING_DESIGN_2026-07-23.md) — fast query-bond attention을 먼저 검증하고 반복 효과만 slow `Delta ell`로 증류
- 결정적 비교 설계 lock: [`_research/shared_field_hypothesis/`](_research/shared_field_hypothesis/) — shared field 대 separate heads에서 비교할 예산 차원·카운터 계약과 독립 selection·revision·감사 지표를 잠금. 현재 `DESIGN_LOCKED_NOT_PREREGISTERED`이며 v1은 모든 run을 거부한다
- 경계: 설계 수식은 `SECONDARY_AI_RESEARCH_AND_DESIGN`; B2.1 수치는 체크인 prereg와 직접 측정에 근거한다.

### P0–P4 전환 상태와 최신 falsifier

| 단계/실험 | 현재 판정 | 산출물 |
|---|---|---|
| P0 identity/metric | 목표 정체성 고정. 함수/agent process가 LLM으로 실행되고 `H,W`가 그 거시 신경망을 구성. 인지체 metric(slope>0)·baseline 3종·평가 3종 잠금 초안 (ratify 대기) | [canon](_research/root_compat/CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md) · [P0 prereg](prereg/PREREG_P0_COGNITIVE_METRIC_LOCK_2026-07-24.md) |
| P1 learning actuation | scalar slow-weight P1은 **과학적 RED**(12 candidates, active 0, A1−A2=0, rank 변화 0/456). typed-policy 표현으로 이동한 P1v3은 `6/6 vs 0/6`, 독립 P1v4는 `6/6 vs 2/6`, 개선 4/6으로 재현됐다. 단 n=6 L0이며 일반 compiler·durable `Delta W`는 미확증 | [efficacy record](EFFICACY.md) · [P1v4 closeout](_research/p1v4_fresh_replication/CLOSEOUT_20260724.md) · [prereg](prereg/PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json) |
| B2 routing signal | 최선 slice oracle +9.92pp, tie 75%; pooled 분포는 tie kill. 얇은 oracle signal이지 learned 성공 아님 | [result](results/B2_ROUTING_SIGNAL_RESULTS_2026-07-23.md) · [evidence](evidence/EVIDENCE_B2_ROUTING_SIGNAL_2026-07-23.json) |
| E1 conditional traversal | bridge −13.89pp, factoid −7.27pp. 전면 OFF 유지 | [result](results/E1_CONDITIONAL_TRAVERSAL_RESULTS_2026-07-23.md) · [evidence](evidence/EVIDENCE_E1_CONDITIONAL_TRAVERSAL_2026-07-23.json) |
| P3 shadow topology absorption | 0/3 수용, canary 100%, sealed Δ0. 안전하지만 후보가 무득 | [result](results/SHADOW_GATED_ABSORPTION_RESULTS_2026-07-23.md) · [evidence](prom_search_hswm/evidence/EVIDENCE_shadow_gated_absorption_20260723.json) |
| prior-art tribunal | generic graph three-factor+sleep novelty는 사망; n-ary credit/LLM verdict/topology/shared persistent field 슬롯 생존 | [tribunal](_research/root_compat/TRIBUNAL_PHASOR_AGENTS_PRIOR_ART_2026-07-23.md) |

## 2026-07-23 paper–code absorption gate

11개 외부 시스템을 이름이 아니라 paper–code pair로 고정했다. 현재 상태는
`SOURCE-LOCKED / NOT ACTIVATED`이며, 외부 성능 수치를 HSWM 성과로 간주하지 않는다.

- 배포 경계: [`ABSORB_CONTRACT_v1.md`](docs/research/ABSORB_CONTRACT_v1.md)
- 흡수 판단·우선순위·falsifier: [`PAPER_CODE_ABSORPTION_LEDGER_2026-07-23.md`](docs/research/PAPER_CODE_ABSORPTION_LEDGER_2026-07-23.md)
- 기계 판독 게이트: [`manifest.v1.json`](_research/competitor_absorption/manifest.v1.json) · [`verify_sources.py`](_research/competitor_absorption/verify_sources.py)
- 재현 provenance: [`source_locks/`](_research/competitor_absorption/source_locks/)

제3자 clone·PDF·추출문은 저장소에 vendor하지 않는다. 공개 저장소에는 upstream commit,
paper URL/SHA-256, license route, code anchor와 default-off disposition만 둔다.

## 복구된 미게시 연구 묶음

최신 `main`보다 뒤처진 별도 작업 미러에서 아래 묶음을 원래 provenance와 함께 복구했다.
기존 `main`을 미러로 덮지 않고, 현재 정본 위에 독립 산출물로 이식했다.

| 묶음 | 공개 경계 | 산출물 |
|---|---|---|
| H3-B3 V5 재현성 | 이미 공개된 V5 run manifest가 고정한 source/prereg/test를 복구. 기존 refusal·효능 판정은 변경하지 않음 | [V5 prereg](_research/root_compat/H3_B3_V5_RESTART_PREREG_2026-07-20.md) · [C0 diagnosis](docs/research/H3_C0_CHAIN_VIABILITY_DIAGNOSIS_2026-07-20.md) |
| World Compiler S4.0 | 가역적 entity binding 수직 slice와 OSS 비교. `claim_weave`·`chain_viability`는 미구현 | [receipt](docs/research/S4_0_REVERSIBLE_ENTITY_BINDING_2026-07-21.md) · [PROM](docs/research/WORLD_COMPILER_V2_OSS_PROM_2026-07-21.md) |
| R3 walk-regime density dial | PhantomWiki large+sparse hard-hop에서 walk−flat `+0.0111`, LCB `+0.00085`; dense에서는 `-0.0048`. synthetic retrieval-side regime 관측이며 real-data answer uplift가 아니다 | [prereg](prereg/PREREG_R3_WALK_REGIME_2026-07-23.json) · [result](results/R3_WALK_REGIME_RESULTS_2026-07-24.md) · [`r3_walk_regime.py`](_research/f_series/r3_walk_regime.py) |

## 2026-07-22 연구 장부

| 갈래 | 결과 | 산출물 |
|---|---|---|
| shared semantic hypergraph NN | 사용자 방향과 AI 형식화를 분리해 W/graph/agent-transfer 경계를 고정. 이론 lock이며 성능 판정 아님 | [spec](docs/canon/SPEC_SHARED_HYPERGRAPH_NN_SEMANTIC_WEIGHT_2026-07-22.md) |
| P1 binding density | semantic 0.2121, lexical CONTAINS 0.0, MC-null z 6.56, `progressive` | [PROM mirror](prom_search_hswm/INDEX.md) |
| P4 equal-compute | semantic−control 0.0303, novel 미달, `partial / degenerating`; 1-pass Jaccard 0.4242가 semantic 0.2121보다 높음 | [PROM mirror](prom_search_hswm/README.md) |
| P5 fixed multi-view routing | hard-4 Δ0, full-chain −0.0125, `REJECTED / degenerating` | [report](docs/research/PROM_P5_MULTIVIEW_HARDHOP_2026-07-22.md) |
| P6 semantic-residual absorption | fresh unseen 3회 모두 손해라 FSM이 3/3 거부; sealed Δ0, `equivalent / degenerating` | [report](docs/research/PROM_P6_CONTINUAL_ABSORPTION_FSM_2026-07-22.md) |
| Phase B field algebra | immutable content-addressed Field, merge/split/compose, L1–L4 10/10 | [design](docs/research/DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md) |
| B1 identity material | MuSiQue legal chain 0→6, 2Wiki 0→25; 후속 T1/T2 공통 성공은 미달 | [B1](results/B1_IDENTITY_UNLOCK_RESULTS_2026-07-22.md) · [T1](results/T1_ENTRANCE_REACH_RESULTS_2026-07-22.md) |
| B2 federated merge | cross-field +0.2137, seam +0.0342, `progressive`; in-field −0.0648로 no-harm 위반 | [result](prom_search_hswm/docs/B2_CROSSFIELD_MERGE_RESULTS_2026-07-22.md) |
| B2.1 learned router | 2벤치 × 3 partition × 3 k × 3 seed = 54셀 전부 abstain; primary Δ0, oracle ceiling min +0.01087로 router-only `REJECTED / degenerating` | [result](prom_search_hswm/docs/B21_LEARNED_ROUTER_RESULTS_2026-07-23.md) |
| B2.2 bond weighting 진단 | fine top-20 oracle +0.0489/+0.0833; train-only static sparse patch는 6/6 calibration·test Δ0. query-bond 쪽 room만 확인, confirmatory claim 아님 | [design](prom_search_hswm/docs/B22_QUERY_BOND_WEIGHTING_DESIGN_2026-07-23.md) · [diagnostic](prom_search_hswm/evidence/DIAG_b22_fine_bond_action_headroom_20260723.json) |
| PROM-8 / R1 | dynamic two-lane 처방. R1 T1 minimum 0→2, 2Wiki depth-2 0→4, MuSiQue 0 | [PROM-8](docs/research/PROM_8_DYNAMIC_TWO_LANES_2026-07-22.md) · [R1](results/R1_T1_RETRY_RESULTS_2026-07-22.md) |
| open composition v2r3 | target 59/59, expanded 78/78, injected negative 2/2. 로컬 구조 closure만 통과했으며 과학적 효능은 미판정 | [amendment](docs/research/AMENDMENT_OPEN_HSWM_KERNEL_V2_2026-07-22.md) |

## 저장소 지도

| 경로 | 역할 |
|---|---|
| [`README.md`](README.md) | 공개 구현의 현재 claim boundary와 실행법 |
| [`EFFICACY.md`](EFFICACY.md) | 효능 주장과 반증 결과의 장부 |
| [`_research/root_compat/`](_research/root_compat/) | source-pinned root-era flat compatibility source; 새 작업 금지 |
| [`world_ir.py`](_research/root_compat/world_ir.py), [`world_compiler.py`](_research/root_compat/world_compiler.py) | evidence-preserving world compiler의 flat 호환 모듈 |
| [`doc_builder.py`](src/hswm/substrate/doc_builder.py), [`world_builder.py`](src/hswm/substrate/world_builder.py) | deterministic document/corpus hypergraph builders |
| [`field_snapshot.py`](src/hswm/substrate/field_snapshot.py), [`certified_readout.py`](src/hswm/substrate/certified_readout.py) | immutable field cut와 fail-closed readout |
| [`prom_search_hswm/`](prom_search_hswm/) | PROM→HSWM, field algebra, federated merge, open-composition 연구 코드와 영수증 |
| [`prom_search_hswm/hswm_open_kernel.py`](prom_search_hswm/hswm_open_kernel.py) | v2r3 open self-similar deterministic kernel |
| [`prom_search_hswm/test_hswm_open_kernel.py`](prom_search_hswm/test_hswm_open_kernel.py) | v2r3 반례·불변식 테스트 |
| [`prom_search_hswm/prom_b21_learned_router.py`](prom_search_hswm/prom_b21_learned_router.py) | frozen HSWM arm 위 B2.1 learned router·conformal abstention harness |
| [`prom_search_hswm/hswm_bond_readout.py`](prom_search_hswm/hswm_bond_readout.py) | slow `ell`과 volatile query-bond potential을 분리 적용하는 pure deterministic module |
| [`prom_search_hswm/test_hswm_bond_readout.py`](prom_search_hswm/test_hswm_bond_readout.py) | neutral parity·coverage·monotonic suppression·shift invariance 19 tests |
| [`prom_search_hswm/fsm/hswm_plasticity_loop.v1.json`](prom_search_hswm/fsm/hswm_plasticity_loop.v1.json) | weight→routing→topology 후보의 bounded proposal/evaluation/activation 계약 |
| [`PROM_9_HSWM_LLM_FUNCTION_SEMANTIC_NEURAL_NETWORK_2026-07-24.md`](docs/research/PROM_9_HSWM_LLM_FUNCTION_SEMANTIC_NEURAL_NETWORK_2026-07-24.md) / [`prom9_semantic_neural_network.v1.json`](prom_search_hswm/prom9_semantic_neural_network.v1.json) / [`prom9_protocol.py`](prom_search_hswm/prom9_protocol.py) | LLM 3-role typed 함수망→외부 outcome→eligibility→fast bond→slow weight 승격을 동등예산 대조군과 함께 고정한 PROM-9 |
| [`token_learning_contract.py`](src/hswm/learning/token_learning_contract.py) / [`USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md`](docs/canon/USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md) | 최소 token/action trajectory를 eligibility→outcome→activated candidate에 결속하고 단일 causal-test receipt 전에는 학습 규칙 주장을 막는 계약과 사용자 정전 |
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

이 회귀는 구조·불변식의 로컬 closure만 증명한다. 성능과 과학적 효능은 각 직접 측정과
claim boundary를 따로 확인해야 한다.

## 다음 frontier

1. Dell guarded path에서 B2.2 reproduction/full-2Wiki/full-MuSiQue pack을 만들고 lock→accept하여 실 Gate-0 receipt를 확보
2. Gate-0 뒤에만 P1v5 query×bond fast learner를 동결하고 outcome→eligibility→fast candidate→slow `Delta ell` 승격을 static/random/shuffle/no-promotion/removal/equal-budget controls로 시험
3. 독립 축으로 PROM-9의 QF/BF/AF typed port·function registry·call receipt를 구현하고 single-LLM workflow/vector memory와 exact call·token parity, role-removal/shuffle 비교
4. P1v5+F1 뒤 Agent-A write → frozen Agent-B unseen transfer; transcript·exact-cache·B-update 금지
5. 전이 뒤에만 typed `CONNECT` 한 종류를 열고 weight-only/router-only/flat-memory 및 removal ablation과 비교
6. 그 뒤 homeostasis·forgetting·collapse·recursion·cost·rollback·sleep/consolidation 장기판
7. shared-field v2의 독립 selection/evolving-knowledge cohort와 재현 가능한 fresh-clone 검증을 공통 기반으로 구현

## 공개 경계

- `prom_search_hswm/data/gold_badiou24.json`만 Tier-1 구조 테스트용으로 provenance와
  SHA-256을 고정해 공개한다. 나머지 로컬 gold/source·외부 benchmark 입력은 계속 ignore하며,
  공개 전 별도 privacy/license 검토가 필요하다.
- 문서 속 USER 원문은 canonical user direction이다. 수식·타입·API와 연구 해석은
  SECONDARY_AI이며, 사용자가 별도로 승인하지 않은 성능 주장을 canon으로 승격하지 않는다.
