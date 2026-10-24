# 1–3조: 정체성·상태·관계

[통합 헌법](../HSWM_CONSTITUTION.md)의 선택 가능한 한 부분이다. 아래 조항의 표현과
공학적 귀결은 `SECONDARY_AI`; 사용자 방향은 각 원문 링크에서 확인한다.

## 1. 하나의 AI와 그 지속 상태

HSWM은 LLM을 기본 인지 계산으로 하는 하이퍼그래프 AI 구조다. 거대한 Semantic Weight
하이퍼그래프가 상태 자체이고 LLM은 작은 국소 입력에 작용하는 내부 연산자다.
세계모델·자기모델·하네스·학습은 같은 지속 상태와 전이가 맡는 역할이다.
LLM 호출 횟수·에이전트 수·DB 크기를 그 정체성의 기준으로 삼지 않는다.

근거: [하나의 하이퍼그래프 AI](../USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md),
[상태와 국소 연산자](../USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md),
[token-hypergraph 중심축](../USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md).

LLM checkpoint, 호출 중의 일시 문맥, 그래프의 지속 상태, 사람에게 보여 주는 문서는
서로 다른 표현·수명·수정 경로를 가진다. Markdown과 KG projection은 가독 view로
사용하며, 문서를 편집한 사실을 native state 학습으로 기록하지 않는다.

## 2. 원자·schema·책임·계보

승인된 canonical atom version은 versioned schema 아래 하나의 책임 owner를 가진다.
고정 H/W/A/F/Π 분해는 폐기됐다. 하나의 owner는 모든 의미·저장·작성·실행 권한을
독점한다는 뜻이 아니다. 책임, authorizer, proposer, executor, custodian을 구별한다.

원자의 식별에는 schema, lineage, atom UID, revision을 보존한다. 원문·관측·주장·관계·
프로그램·결과가 서로 참조할 수 있지만, 해석이나 관측 하나가 다른 지위로 자동 승격되지 않는다.
수정은 선행 revision과 근거를 남기며, fork·merge·retire·restore가 원래 계보를 지우지 않는다.

근거: [single-owner 사용자 교정](../USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.md),
[8월 헌법의 schema·owner 계약](../HSWM_CONSTITUTION_2026-08-20.md#2-헌법적-객체--schema와-canonical-atom-model).
구현 위치: `canonical-atom-v2-schema.ts`, `canonical-atom-v2-durable-runtime.ts`.

## 3. 관계의 의미와 Semantic Weight

관계는 연결 유무만이 아니라 참여자·역할·순서·반복 참여·문맥·예외를 포함한다.
n항 관계를 pair edge로 투사하면 어떤 정보가 보존되고 사라지는지 밝힌다.
내용의 유사성, 같은 대상이라는 동일성, 실행 의존성, 인과 기여는 다른 관계다.

Semantic Weight는 역할·문맥 아래 어떤 해석·전달·전이가 일어나는지의 성향으로 다룬다.
관련성 점수, 신뢰도, 이번 실행의 활성, 보상, 인과 credit을 하나의 숫자로 합치지 않는다.
scalar 계수·규칙 본문·전이 프로그램·연결 구조는 특정 구현의 표현이며 정체성 전체를
대체하지 않는다. 한 표현의 수정이 실제 선택·출력에 주는 차이를 관측해야 한다.

근거: [Semantic Weight 정의](../../research/HSWM_SEMANTIC_WEIGHT_DEFINITION_AND_HYPERGRAPH_2026-09-14.md),
[이론적 전제](../../research/HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md).
다음 읽기: 선택 조건은 [4–6조](activation.md), 결과에 따른 수정은 [7–9조](learning.md).
