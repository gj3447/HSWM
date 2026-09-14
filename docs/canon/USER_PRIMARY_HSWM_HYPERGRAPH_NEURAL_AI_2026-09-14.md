# HSWM 기본 정체성 — LLM을 계산 단위로 하는 하나의 하이퍼그래프 신경망 AI

**지위:** `USER_PRIMARY_TARGET_IDENTITY_REAFFIRMATION`

**원문:** [사용자 발화](sources/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.txt)

## 1. 기본 개념

> **HSWM은 LLM을 기본 계산 단위로 사용하고, 하이퍼그래프 Semantic Weight를 통해 작동하는 하이퍼그래프 신경망이며, 전체가 하나의 거대한 AI를 이루는 것을 기본 개념으로 한다.**

이 문장은 사용자가 이번에 재확인한 대상 정체성의 정리다. 아래 네 항목을 함께 보존한다.

| 관점 | 기본 개념 | KG 관계 |
|---|---|---|
| 전체 정체성 | 하나의 거대한 AI | `HAS_UNIFIED_AI_IDENTITY` |
| 신경망 구성 | 하이퍼그래프 신경망 | `HAS_NETWORK_ARCHITECTURE` |
| 기본 계산 | LLM을 이용한 계산 | `HAS_BASIC_COMPUTATION_UNIT` |
| 작동의 중심 | 하이퍼그래프 Semantic Weight | `OPERATES_THROUGH` |

이 기본 개념은 [HSWM 헌법](HSWM_CONSTITUTION_2026-08-20.md)의 token-native LLM-function macro-neural network와 이어진다. 이번 기록은 그 정체성을 탐색하기 쉬운 출처 결속 그래프로 재확인한다. 기존 헌법의 원문과 과거 증거를 수정하지 않는다.

## 2. 기존 정의와의 의미 연결

이 절의 구체화는 `SECONDARY_AI` 해석이며, 기존 정전을 참조한다. 이번 사용자 발화에 수학적 세부 정의까지 소급하지 않는다.

**LLM 기본 계산 단위.** 네트워크 안의 함수·국소 전이를 LLM이 해석하고 실행한다. 입력 token과 문맥·관계 의미를 읽고 출력을 발생시키는 계산이 상위 신경망의 작동을 이룬다. 기본 단위는 특정 HTTP 요청 횟수나 provider 제품에 고정되지 않는다. 모델·checkpoint·배포 방식은 이 정체성을 실현할 때 선택하는 방법이다.

**하이퍼그래프 신경망.** 여러 참여자가 역할을 가진 n항 관계로 결속된다. 관계가 읽는 입력·문맥, 받는 주체와 정보 흐름은 schema와 typed reference에 따라 구분한다. 지속적으로 수정·복구되는 관계도 canonical atom으로 계보와 책임 주소를 가진다. 모든 atom이 LLM 계산 노드인 것은 아니며, 개념·근거·관계·실행 사건도 같은 상태의 typed atom으로 기록할 수 있다.

**Semantic Weight.** [기존 이론 정의](../research/HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md)의 역할·문맥에 조건화된 전이 성향을 이어받는다. 어떤 참여자들의 정보가 어떤 문맥에서 어떻게 해석·변환·전달되고 다음 반응을 바꾸는지가 핵심이다. 관련성 점수, 이미 관측된 활성, 근거의 신뢰도, 식별한 인과 효과는 각각 구분해서 표현한다.

**하나의 거대한 AI.** 개별 LLM 실행과 관계의 변화가 전체의 지속적인 추론·행동·학습으로 결속되는 대상이다. 같은 evolving hypergraph가 실행을 조직하는 living harness, 세계와 자신을 표현하는 world/self model, 경험으로 바뀌는 continuous learner의 역할을 함께 한다. 이 세 이름은 한 AI를 바라보는 기능적 관점이다. “거대함”에 특정 파라미터 수, 서버 수, 단일 checkpoint 또는 의식 판정을 부여하지 않는다.

**같은 몸의 학습.** 결과가 관계·전이 성향의 revision으로 이어지고, 바뀐 상태를 이후 계산이 다시 사용하는 방향을 보존한다. [적응 연구 전략](HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)과 [프랙탈 합성](USER_PRIMARY_HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.md)의 기존 목표도 유지한다. 작은 HSWM이 상위 HSWM의 cell로 참여하는 상세 FCL 계약은 해당 정전에서 이어받는다.

## 3. KG 기록 방식

[정체성 KG](../../ontology/identity/hswm_core/HSWM_HYPERGRAPH_NEURAL_AI_IDENTITY_ONTOLOGY.v1.json)는 사용자 원문, 이번 네 가지 정체성 진술, 기존 정의에 대한 의미 연결을 분리해 기록한다.

- 각 node에 안정된 UID, 역할, source path, source SHA-256, authority와 책임 주소를 기록한다.
- 사용자 재확인은 `USER_PRIMARY`, 상세 해석과 연결은 `SECONDARY_AI`로 표시한다.
- 기존 HSWM·Semantic Weight·fractal 개념은 소유 snapshot에 결속된 anchor로 참조한다.
- 관계에는 방향·type·authority·scope를 두며, 원문까지 거슬러 갈 수 있게 한다.
- 기존 RDF 1.1·SHACL·SPARQL 도구로 구조와 조회를 검증한다. [조회 예](../../ontology/queries/hswm_hypergraph_neural_ai_2026-09-14/README.md)에서 네 가지 기본 개념을 확인할 수 있다.

여기서 확정하는 것은 **무엇을 HSWM이라고 만들고 있는가**다. [현재 구현·증명 기록](../research/HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.md)의 범위와 CR/FCL의 과학적 판정은 기존대로 유지한다. 이 KG는 정체성을 기록하는 projection이다.
