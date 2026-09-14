# HSWM의 상태와 국소 신경 연산자 — Hyperon 핵심 비교 원칙

**기록일:** 2026-09-14

**권위:** 사용자 정체성·비교 방향은 `USER_PRIMARY`, 아래 해석·비교 방법은 `SECONDARY_AI`.

**원문:** [사용자 발화 전체](sources/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.txt)

## 1. 그대로 보존하는 문장

> 거대한 시멘틱 웨이트 하이퍼 그래프 가 ai 상태 자체이고 llm 은 작은 국소 입력을 받아 그 내부 신경 연산자로 움직인다.

가독성을 위한 정리: **거대한 Semantic Weight 하이퍼그래프가 AI의 상태 자체이고, LLM은 작은 국소 입력을 받아 그 내부의 신경 연산자로 작동한다.** 이 정리의 문구는 AI의 충실한 재서술이며, 바로 위 문장이 사용자 원문이다.

함께 보존하는 연구 방향은 **OpenCog Hyperon을 HSWM의 필수 핵심 비교 대상으로 둔다**는 것이다. 이는 `MANDATORY_CORE_COMPARATOR`이며, 채택할 backend나 제품 의존성의 결정과 구분한다.

이번 개념적 추가는 [직전 기본 정체성](USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md)에 **상태 자체인 그래프 / 작은 국소 입력 / 내부 LLM 연산자**의 관계를 명시하고, 기존 Hyperon 선행연구를 필수 비교 원칙으로 연결한 것이다. [헌법](HSWM_CONSTITUTION_2026-08-20.md)의 같은 evolving hypergraph와 outcome-bound learning을 구체화하는 사용자 방향으로 보존한다.

## 2. 다음 작업에서 이어받을 의미

이 절은 기존 정전과 연결한 `SECONDARY_AI` 해석이다.

- **상태:** 개념·관계·역할·Semantic Weight·경험·revision 계보가 지속되는 하나의 AI 상태를 이룬다. living harness, world/self model, continuous learner는 이 상태와 동역학의 기능적 관점이다. 저장소나 문서 KG만으로 이 인지적 상태의 실현을 판정하지 않는다.
- **국소 입력:** 각 연산에는 해당 전이에 필요한 관계 의미, 참여자의 역할, 문맥, 예외와 근거를 선택적으로 전달한다. “작다”의 정확한 token budget, 접근 범위, read-set 선정과 다단계 정보 전달 방법은 앞으로 정할 연구 변수다. 그래프 전체 크기와 한 번의 LLM 입력 크기를 구분한다.
- **내부 신경 연산자:** LLM의 의미 해석과 생성이 네트워크 안의 국소 전이를 실현하고, 그 결과가 이후 그래프 상태와 다른 연산을 조건화한다. 논리적 내부 역할은 로컬 배포나 특정 API·checkpoint를 강제하지 않는다. 실행에 영향을 주는 모델 버전·입력·전이·관측의 연결은 추적해야 한다.
- **Semantic Weight:** [역할·문맥 조건부 전이 성향](../research/HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md)을 유지한다. scalar relevance, attention activation, evidence, 식별된 causal effect는 구별해서 기록한다.
- **학습과 합성:** 국소 예측 뒤 외부 결과를 대조하고, 관계의 의미·구조 revision이 다음 국소 연산을 바꾸어야 한다. 필요한 예외·불확실성을 국소 입력이나 상위 요약이 소거하지 않는지 검증한다. 기존 [FCL-1..8](../research/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md)과 CR-0..7 의무를 그대로 이어받는다.

이는 구현 방향이다. 국소 입력의 충분성, 전체 상태의 동역학적 폐쇄성, 실제 LLM의 지속 학습과 합성 능력은 이 문장만으로 증명되지 않는다. [현재 구현·Lean 근거](../research/HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.md)의 범위를 유지한다.

## 3. Hyperon은 필수 핵심 비교 대상이다

[기존 2026 직접 선행 조사](../research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)는 이미 Hyperon을 조사 범위에서 가장 가까운 직접 아키텍처 선행으로 기록했다. 이번 사용자 방향은 이를 향후 아키텍처·독창성·실험 설계의 필수 비교 대상으로 명시한다. [재사용 우선 설계](../research/HSWM_REUSE_FIRST_ARCHITECTURE_2026-08-30.md)의 backend 후보 역할과 함께 유지하되, 비교를 adapter 선택만으로 축소하지 않는다.

2026-09-14에 다시 읽은 [공식 July 2026 백서](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf)는 기존 조사와 동일한 SHA-256 `bdb3efb266a35f10fe07addc34c9def68708b4fb123480163c724d8ceec3b5f2`다. §2의 지속 metagraph, §10.1의 외부·bridge·native neural 경로, §10.3의 선택적 graph read/candidate write는 이번 HSWM 개념과 직접 비교할 내용이다. §1.9는 구현, prototype, 설계, 연구 가설과 외부 검증을 구분한다.

[공식 MeTTa 저장소 README](https://github.com/trueagi-io/hyperon-experimental/blob/3f76dc460da6961f57f69f6c3e550c59c74ada83/README.md)도 별도로 확인했다. 이는 해당 interpreter의 공개 코드·개발 범위를 보여준다. 그 코드의 존재를 백서 전체 통합이나 인지 효능의 증거로 확대하지 않는다. 이번 재확인은 문서와 README 범위이며 새 실행·benchmark·전체 코드 감사가 아니다.

다음 표는 `SECONDARY_AI` 비교 설계이며, 이미 입증된 HSWM 차별점 목록이 아니다.

| 비교 축 | Hyperon에서 대조할 대상 | HSWM에서 검증할 질문 |
|---|---|---|
| 상태와 실행 | Atomspace·MeTTa·MORK의 metagraph와 graph transformation | 지속 상태가 다음 국소 연산을 실제로 조건화하는가 |
| 국소 LLM 연산 | neural kernel, symbolic-head read/write, Module Space | 입력 범위·역할·예외를 추적하며 의미 연산이 결속되는가 |
| 가중치의 의미 | truth/evidence, attention, compute fuel, neural learning | Semantic Weight의 전이 성향과 인과 효과를 각각 측정하는가 |
| 경험의 교정 | prediction, predictive coding, provenance, causal audit | 잘못된 관계를 outcome으로 교정해 후속 행동이 달라지는가 |
| 합성과 지속성 | private/shared Atomspaces, OmegaHive와 계보 | 작은 HSWM의 불확실성과 학습이 상위에서도 보존되는가 |
| 효능과 성숙도 | 해당 버전의 구현·prototype·설계별 근거 | 같은 과제·모델 접근·계산 예산에서 차이가 재현되는가 |

비교 실험을 만들 때는 Hyperon의 정확한 component·commit·configuration·사용 가능한 모델 접근을 선언하고, 백서 설계와 실행 가능한 baseline을 각각 표시한다. 대응 구현을 확보하지 못한 항목은 미평가로 남긴다. HSWM에도 같은 증거 기준을 적용하고, 관계 제거·복원과 독립 outcome으로 기전 기여를 확인한다. 두 체계의 개념적 중첩을 먼저 인정하고, 차이·우위·최초성은 별도 근거가 있을 때만 주장한다. LLM의 sequence token과 TECAN의 compute fuel도 별개로 취급한다.

## 4. 출처 결속 KG

[KG snapshot](../../ontology/identity/hswm_core/HSWM_STATE_LOCAL_OPERATOR_HYPERON_ONTOLOGY.v1.json)은 원문, 세 정체성 항목, 필수 비교 원칙, AI의 해석, 공식 자료 확인과 기존 선행 개념을 typed relation으로 연결한다. [source map](artifacts/hswm_state_local_operator_hyperon_2026-09-14/source-map.v1.json)에 원문·문서·외부 anchor의 SHA-256과 공식 자료의 확인 범위를 둔다.

[SPARQL 조회](../../ontology/queries/hswm_state_local_operator_hyperon_2026-09-14/README.md)로 사용자 정체성 세 항목과 필수 비교 대상을 각각 찾을 수 있다. 검증은 기존 RDF 1.1 projection·SHACL·SPARQL 도구를 사용한다. 로컬 관계 어휘는 HSWM 소유이며 RDF 자체의 표준 어휘라고 주장하지 않는다. 이 snapshot은 저장소의 지식 projection이고, 현재 과학적 판정이나 실행 중인 HSWM의 학습 상태를 승격하지 않는다.
