# HSWM 연결성 지도 — E2E 신경망 대체 테제의 8개 연결 (2026-08-03)

> **status**: `CONNECTIVITY_MAP — synthesis 사용자 ratify 완료 (2026-08-03, C2~C5·C7·C8)`
> **date**: 2026-08-03
> **authority**: USER_CANON 발화(2026-07-30 PROM-17 원천 대화, 2026-08-03 재확인 발화)에서 출발한 SECONDARY_AI 연결 합성. 이 문서는 **연결성 지도**이며 새 측정·효능 주장이 아니다.
> **purpose**: PROM-17이 두 축(축 1 glue 붕괴 / 축 2 LLM 활성화 함수)을 선언했다면, 이 문서는 그 축이 SYMPOSIUM 스택의 기존 정전·문서·장치와 **어디에 잇닿는지**를 잇는다. 각 연결은 (a) **이미 해설된 곳** — 검증된 문서 앵커, (b) **이 문서가 새로 잇는 부분** — synthesis, 으로 명시 분리한다.
> **canon 분리**: 인용된 사용자 발화만 USER_PRIMARY. 연결의 출처는 AI synthesis(2차 소스)이며, C2~C5·C7·C8의 synthesis 부분은 2026-08-03 사용자 verdict로 ratify됐다 (KG `user-ratify-hswm-connectivity-map-synthesis-c2-c8-2026-08-03`). 효능 non-claim은 유지.
> **relation**: PROM-17(동기 정식)의 후방 연결 문서. PROM-17 §8의 관계 문서 체계와 `INDEX.md`의 정체성 정의를 변경하지 않는다.

## 0. 정체 테제 (사용자 발화)

> "테슬라가 자율주행에 하드코딩을 빼고 신경망으로 싹다 대체했듯이, AI끼리 멀티에이전트 체계와 룰에 하드코딩을 빼고 신경망으로 대체하는 것이 HSWM."
> — USER 2026-08-03 (원문 타이포만 정규화, 취지 불변)

한 줄 정식: **HSWM = 멀티에이전트 조정 직물(coordination glue)의 End-to-End 신경망화. LLM은 주체가 아니라 거시 신경망의 의미적 활성화 함수 `f_i`다** (주객전도, PROM-17 §3).

## 1. 연결 그물 — 8개 연결

### C1. Bitter Lesson → glue 붕괴

- **명제**: 규칙 *방식* 자체가 (에이전트 수 × 도구 수 × 맥락) 조합 폭발에 패배한다. 현재 에이전트·MCP·CLI 생태계는 자율주행 초기 rule-based C++ 스택과 같은 물질이다.
- **이미 해설된 곳**: PROM-17 §1 전체 (Sutton *Bitter Lesson* 인용, if-else 라우터 코드 예시, §1.3 HSWM의 답).
- **새로 잇는 부분**: 없음 — PROM-17이 완결. 이 문서는 후방 연결만 담당.
- **상태**: 동기 선언 (`MOTIVATION_CANON_CANDIDATE`).

### C2. 7군단장 = 이 생태계의 C++ 스택; 2026-05-30 reframe = proto-HSWM

- **명제**: 고정 동사 7개(획득/발견·창조/연결/정리/검증/계획/실현)·AGENTS.md 규약·phase gate·hook 체인은 손으로 쓴 coordination 규칙 덩어리 — 이 생태계의 glue다. `HARNESS_7COMMANDER` 초안은 이들을 場 위 operator로 환원하는 용해 문서다.
- **이미 해설된 곳**: `HARNESS_7COMMANDER_HSWM_SUBSTRATE_2026-07-21.md` (7 operator 표, 롱기누스=`field_id` indirection, 오캄=`supersede_state` dose-graded, PROM=프로메테우스 인스턴스; 사용자 ratify 대기). AGENTS.md 정전 `7cmd-measurement-driven-conditional-dispatch-2026-05-30` (고정 USES 관계 retract → 각 commander 자체 metric 측정 후 threshold 초과 시 conditional invocation).
- **새로 잇는 부분**: **2026-05-30 reframe을 HSWM의 계보상 proto-move로 명시** — compile-time wiring을 runtime 측정 해결로 바꾼 첫 이탈이며, HSWM은 이를 dispatch 너머 coordination 전체(누구와 협력할지/어떤 도구를 부를지/맥락을 어디에 둘지)로 일반화하는 것이다. 이 계보 연결은 기존 어느 문서에도 없었다.
- **상태**: synthesis (사용자 ratify 2026-08-03). 군단장의 場 위 동작 자체는 `user-canon-legioncommanders-operate-on-hswm-neural-net-2026-07-23` (VerdictPending) — 미확정으로 유지.

### C3. 계약 = 하드코딩의 잔여이자 헌법

- **명제**: 하드코딩은 제로가 아니라 **제약**(포트 계약·타입 검증·보안 헌법·CAS/CRDT 제어 평면)으로 격하된다. 신경망은 제약이 허용하는 실행 가능 집합 안에서만 동작한다 — FSD의 rule-based safety envelope와 동형.
- **이미 해설된 곳**: PROM-17 §6.1 (정제 테제).
- **새로 잇는 부분**: `apt-contract-root-axiom-2026-05-27` — 계약은 항상 present하며 coupling=0이면 대수 항등원(emp/Id/ε)으로 degenerate, coupling>0에서만 non-trivial — 과의 대응. PROM-17의 "제약으로의 격하"는 root axiom의 "coupling>0에서만 non-trivial 계약"을 실행 층에 옮긴 것이다. **계약은 신경망의 대척점이 아니라 신경망이 그 안에서만 동작하는 실행 가능 집합의 경계**다.
- **상태**: synthesis (사용자 ratify 2026-08-03; root axiom은 정전, 이 대응 관계 ratify됨).

### C4. 영수증 = 그래디언트 대체 — 방법론 = 학습 인프라

- **명제**: LLM은 미분 불가라 거시망에 역전파가 통하지 않는다(프랙탈 구조의 귀결). 따라서 영수증 기반 Hebbian/Fast-Weight 국소 학습은 선택이 아니라 **구조적 필연**이며, 영수증은 단순 로그가 아니라 희소·지연 보상을 조밀하게 바꾸는 **credit assignment 장치**다.
- **이미 해설된 곳**: PROM-17 §2.1, §2.2, §4.
- **새로 잇는 부분**: 이 레포의 outcome trace·로컬 prereg·음성대조·replay를 **거시 신경망의 학습 신호 인프라**로 재해석한다. F2(ΔW credit, ρ=0.8857, kill 3종 미발동)는 이 인프라 위에서 "결과→신용→ΔW" claim의 첫 측정등급 통과 후보다.
- **상태**: synthesis (사용자 ratify 2026-08-03; 기제는 PROM-17 정전 후보, "인프라 전체 = 학습 신호" 해석 ratify — 효능 non-claim 유지).

### C5. 합의 = 프로토콜이 아니라 동역학

- **명제**: "합의를 포함하는 더 큰 AI"(사용자 정전 2026-07-23)의 유일한 공학 경로는 Phase B **"한 대수 두 스케일"** — fact-level ADD/SPLIT/MERGE/SUPERSEDE ≡ field-level 망 연산. L5 no-harm이 이 대수의 유일한 경험 법칙이다.
- **이미 해설된 곳**: `DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md`; B2 결과 (cross-field merge +0.214, 첫 완전 progressive, 단 L5 위반 in-field −0.065 → lemma_incorporation); 헌장 HC-08 (합의의 헌법적 제한 — electorate·agenda·집계 규칙 안의 제한적 절차로서의 합의).
- **새로 잇는 부분**: "프로토콜(투표·쿼럼 = 더 많은 glue) → 場 merge 동역학"이라는 재프레임 자체. 단, 헌장 HC-08의 절차적 합의 정의와의 관계는 미해결로 남긴다 — 동역학으로 떨어지는 합의도 electorate·비가역선·집계 규칙의 제약 안에 들어가야 하며, 이는 C3의 계약층 문제로 환원된다.
- **상태**: synthesis (사용자 ratify 2026-08-03) + 측정 최전선 (B2의 L5 위반이 현 블로커).

### C6. Fast/Slow W = 비정상성 대응 (안정성-가소성 딜레마)

- **명제**: API는 deprecate되고 모델은 업데이트된다 — 학습된 가중치가 계속 낡아가는 환경. `W_slow`(장기 협력 사전분포) + `W_fast`(세션 내 즉응 적응) 이중 구조가 답. 모델 스왑은 학습 도중 활성화 함수를 교체하는 것과 같아 `ρ_i`(포트 계약)는 가중치 보존 정규화층이어야 한다.
- **이미 해설된 곳**: PROM-17 §2.3, §5.2; `HSWM_MATH_DEFINITION_UNIFIED_2026-07-26.md` (W = W_slow(ℓ≤0,b) + W_fast(j≥0) 층별화, 코드 선례 bond readout 2평면).
- **새로 잇는 부분**: 없음.
- **상태**: 설계 정전 후보.

### C7. field_id/current_locator = 정체성 문제의 수렴

- **명제**: "LLM은 교체 가능한 소자이고 기억·가중치·인지 동역학은 거시망에 귀속"이라는 명제가 성립하려면 정체성이 기판(substrate)에서 떠 있어야 한다 → 안정 `field_id`(불변) ↔ 휘발 `current_locator`(가변) 분리.
- **이미 해설된 곳**: `HARNESS_7COMMANDER_HSWM_SUBSTRATE_2026-07-21.md` (사용자 2문제 → 하나의 뿌리 진단); `DESIGN_HARNESS_DOC_HSWM_LENS_DUALITY_2026-07-21.md` (치환이 보존하는 것 = shared-spine 위 consistency relation R = 참조 field_id 집합 동일성 + per-cell sha256).
- **새로 잇는 부분**: 이것이 **동일 문제의 네 번째 인스턴스**라는 수렴 진단 — 롱기누스 ReferenceSite(code↔KG 바인딩, 주소가 바뀌어도 참조가 살아있음) / p333 DID==PeerId(Ed25519 키=정체성, 위치·전송과 무관) / KG `:LATEST_CANONICAL` materialized view(가변 이력 위의 안정 포인터) / HSWM `field_id`. 스택 전체가 "위치·상태가 바뀌어도 정체성이 유지되는 층"을 각개로 풀고 있으며, HSWM 場 스키마는 그 일반형의 신경망 버전이다.
- **상태**: synthesis (사용자 ratify 2026-08-03; 각 인스턴스는 정전·실재, 수렴 진단 ratify됨).

### C8. 비유가 깨지는 지점 = 연구 과제 (+ 4번째 파열점: 합의의 적대성)

- **명제**: FSD 비유는 출발점이지 완성이 아니다 — 성공 조건이 다르고, 그 차이가 HSWM의 실제 연구 과제를 결정한다.
- **이미 해설된 곳**: PROM-17 §2의 3개 파열점 — 이산 선택(그래디언트 無 → 영수증 국소 학습), 희소·지연 보상(→ 조밀 credit), 비정상성(→ Fast/Slow).
- **새로 잇는 부분**: **4번째 파열점 — 적대성**. 운전 환경은 비적대적이지만, 합의·전이 채널은 적대 가능하다: LLM-to-LLM prompt infection(arXiv:2505.23847), 메모리 추출 공격 MEXTRA(arXiv:2502.13172), 공유 prior가 만장일치 오합의로 위장한 사례(80+ 에이전트, arXiv:2604.19049) — 전부 `PROM_16_UNPROVEN_B_AGENT_AB_TRANSFER_2026-07-25.md`가 실증한 위험. Byzantine 조건의 존재가 L5 no-harm을 "유일한 경험 법칙"으로 세운 설계 직관의 정당화다.
- **상태**: synthesis (사용자 ratify 2026-08-03; 3개 파열점은 PROM-17, 4번째는 이 문서의 추가).

## 2. 정체성 3층과 측정 층 (분리 유지)

- **정체 = 대체 프로그램**(§0–1). **측정 = 프로그램의 현재 좌표**. 두 층의 혼동 금지 (PROM-17 §7 non-claim 계승).
- **L0 메모리 substrate — CONFIRMED** (HSWM F1 0.541 vs cosine 0.469, +0.073, p<0.0001, n=300, 추론 LLM콜 0). 자율주행 비유로는 perception stack이 먼저 검증된 단계.
- **L1 LLM-함수 신경망 — TARGET**. PROM-17 §6.2의 세 falsifiable 질문(경험-품질 곡선 단조 향상 / 계열 A→B 전이 / 가중치 장 절제 시 하드코딩 라우터로 퇴화)이 F1~F5 게이트·장부로 사전등록돼 있다. 현 최전선 = F1 r8/try3 (`FINDINGS/hswm-f1-r8-try3-2026-07-28/REPORT.md` — 모델콜 0, B22 LOCKED, fail-closed 재시작 준비).
- **L3 합의 포함 더 큰 AI — OPEN**. C5의 merge 대수가 유일 공학 경로이고 L5 위반이 현 블로커.
- 프로그램 전체 `scientific_status` = **UNJUDGED**. 현재 주장은 [`EFFICACY.md`](../../EFFICACY.md)의 체크인 직접 측정 경계를 따른다.

## 3. Claims and Non-claims

- **Claim (connectivity)**: C1–C8 연결 지도. 각 항목의 "이미 해설된 곳"은 검증된 앵커이고, "새로 잇는 부분"은 SECONDARY_AI synthesis다.
- **Non-claim (efficacy)**: 효능 주장 없음. 모든 측정 인용은 기존 receipt·INDEX의 재인용이다.
- **Non-claim (canon)**: §0의 사용자 발화 인용 외 어떤 명제도 USER_PRIMARY 정전이 아니다. C2·C3·C4·C5·C7·C8의 synthesis 부분은 2026-08-03 사용자 verdict로 ratify된 해석이다 (출처는 2차 소스로 유지).
- **Non-claim (uniqueness)**: MoE·NTM·DNC·AriGraph·GPTSwarm 등 선행과의 정량 대조는 PROM-17 §7과 tribunal 문서의 과제로 유지한다.

## 4. 관계 문서

- **PROM-17 (전방)**: [`PROM_17_HSWM_WHY_GLUE_CODE_NEURAL_TOPOLOGY_LLM_ACTIVATION_2026-07-30.md`](../research/PROM_17_HSWM_WHY_GLUE_CODE_NEURAL_TOPOLOGY_LLM_ACTIVATION_2026-07-30.md)
- **PROM-17 §8 관계 문서**: [`CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`](../../_research/root_compat/CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md) (정체성 정전) / [`PROM_9_HSWM_LLM_FUNCTION_SEMANTIC_NEURAL_NETWORK_2026-07-24.md`](../research/PROM_9_HSWM_LLM_FUNCTION_SEMANTIC_NEURAL_NETWORK_2026-07-24.md) (최소 구현 계약) / [`PROM_16_HSWM_HOLISTIC_SCIENTIFIC_ARCHITECTURE_2026-07-26.md`](../research/PROM_16_HSWM_HOLISTIC_SCIENTIFIC_ARCHITECTURE_2026-07-26.md) (총체 과학 구조)
- **HSWM/ 카탈로그**: HARNESS_7COMMANDER (C2·C7) / LENS_DUALITY (C7) / PHASE_B (C5) / MATH_DEFINITION_UNIFIED (C6) / 헌장 HC-08 (C5) / B2 결과 (C5) / PROM_16_UNPROVEN_B (C8)
- **AGENTS.md 정전**: `7cmd-measurement-driven-conditional-dispatch-2026-05-30` (C2) / `apt-contract-root-axiom-2026-05-27` (C3)
- **KG**: `user-canon-hswm-is-the-larger-ai-containing-consensus-2026-07-23` / `user-canon-hswm-functions-are-llm-executed-neural-net-2026-07-23` / `user-canon-legioncommanders-operate-on-hswm-neural-net-2026-07-23` (VerdictPending) / `commander-hswm-omc-2026-07-19`
