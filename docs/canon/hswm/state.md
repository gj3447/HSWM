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

### 1조의 이유·문제·구현

**해결하려는 문제.** 대화마다 경험이 사라지거나, 같은 대상을 문서·메모리·도구 설정이
각자 다르게 기억하면 수정 결과가 다음 행동에 이어지지 않는다. 따라서 무엇이 지속되고
어떤 연산이 그것을 바꾸는지 명확해야 한다. 장비의 좌표 변환 조건을 고쳤다면 다음 검사도
그 판본을 사용해야 한다. 이전 대화가 검색되는 것만으로는 충분하지 않다.

**문헌 근거와 적용 범위.** Packer 등, *MemGPT* (arXiv:2310.08560v2, 2024, §2)는
LLM의 주 문맥과 외부 기억을 명시적인 이동 연산으로 연결한다. 상태 수명과 문맥 조립에
참고한다. [원문](https://arxiv.org/html/2310.08560v2#S2).
Goertzel 등, *OpenCog Hyperon* (arXiv:2310.18318v1, 2023, §§3.1–3.3)은 Atomspace와
그 일부를 변환하는 MeTTa 프로그램을 설명한다. 그래프에 데이터와 프로그램을 두는 선행
구조와 비교하되 이것이 HSWM의 동일성·성능을 입증하지는 않는다.
[원문](https://arxiv.org/html/2310.18318v1#S3).

**구현 경로.** 기존 `canonical-atom-v2-durable-runtime.ts`가 저장 상태를,
`readLlmSemanticFrame`과 `executeLlmSemanticRelation`이 선택한 관계의 읽기·전이를 맡는다.
대상 UID·판본과 사건을 입력으로 받아 예측·trace·수정 후보를 연결한다. 재시작 후에는
대화 요약을 정본으로 복원하지 않고 저장된 상태와 출처를 다시 연다. LLM·토크나이저·
인터프리터의 판본은 상태 판본과 별도로 결속한다.

**현재와 후속·확인 사례.** 영속 상태와 국소 의미 실행을 재사용한다. 서로 다른 작업·도구에서
같은 의미를 유지하는 통합 효능은 별도 과제다. ‘조건 수정 후 재사용’, ‘이전 대화의 잘못된
조건 재유입’, ‘재시작 뒤 판본 복원’을 검사하고 문서 일치만으로 실행의 일치를 판정하지 않는다.

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

### 2조의 이유·문제·구현

**해결하려는 문제.** 동일한 이름의 객체, 동시 수정, 오래된 읽기, 작성자와 승인자의 혼동은
잘못된 상태를 정상 판본처럼 보이게 한다. 원자별 책임과 판본 식별은 충돌의 처리 주체와
수정 근거를 정한다. 책임 owner 하나라는 결정은 다른 참여자의 저작·보관·실행 역할을
지우는 권한 독점 규칙이 아니다.

**문헌 근거.** Lebo·Sahoo·McGuinness 편집, W3C *PROV-O* (2013-04-30 Recommendation,
§§3.1–3.3)는 Entity·Activity·Agent와 derivation·association·revision을 구분한다.
출처·변경 계보의 교환 표현에 사용한다. PROV-O가 HSWM의 single-owner 정책이나 동시성
제어를 정해 주는 것은 아니다.
[원문](https://www.w3.org/TR/2013/REC-prov-o-20130430/#description).

**구현 경로.** `CanonicalAtomV2Key`의 schemaVersion·lineageId·atomUid·revisionId와
content hash, 책임 owner, 선행 판본을 유지한다. writer는 기존 `CommitCanonicalAtomsV2`의
expectedStateRevision·readSet·writes·authorizationRef를 검사한다. 오래된 제안은 최신
상태에 덮어쓰지 않고 다시 읽어 의미를 검토한다. 복원도 후속 판본으로 남겨 중간 실패를 보존한다.

**현재와 후속·확인 사례.** schema·admission·durable journal을 재사용한다. 여러 writer의
의미적 merge는 UID 일치와 별개다. 같은 선행 판본에서 상충하는 두 수정, 다른 owner의
동일 UID, 복원, 내용이 바뀐 동일 경로를 넣어 잘못된 수락과 계보 손실을 검사한다.

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

### 3조의 이유·문제·구현

**해결하려는 문제.** ‘카메라–부품–좌표계–검사 규칙’을 이웃 목록으로만 만들면 누가 무엇을
어떤 조건에서 관측하는지가 사라진다. 같은 참여자라도 역할을 바꾸면 다른 주장이다.
비슷한 텍스트라는 이유로 같은 장비나 같은 인과관계로 병합하는 오류도 막아야 한다.

**문헌 근거와 차이.** Noy·Rector 편집, W3C *Defining N-ary Relations* (2006-04-12
Working Group Note, Pattern 1)은 관계 자체를 객체로 두어 참여자와 속성을 표현한다.
[원문](https://www.w3.org/TR/2006/NOTE-swbp-n-aryRelations-20060412/).
Chien 등, *You are AllSet* (ICLR 2022, arXiv:2106.13264v4, §§3–4, 식 5)는
노드→하이퍼에지→노드의 multiset 연산을 제시한다. 국소 연산의 비교 근거다. 순열 불변
집계에 역할 정보를 넣지 않으면 역할 차이를 보존할 수 없으므로 HSWM의 역할·순서를
생략하는 근거로 쓰지 않는다. [원문](https://arxiv.org/html/2106.13264v4#S3).

**구현 경로.** 기존 `CanonicalAtomV2Reference`와 schema의 역할 cardinality를 사용해
관계 UID, referenceType·role·target과 실제 배열 순서를 보존한다. 읽기 frame에서 조건과
예외를 본문에 함께 전달한다. 학습 대상이 수치 정책, 의미 내용, 연결 구조 중 무엇인지
구분하고 변경을 실제 결과에 연결한다. 표현이 다른 W를 단일 점수로 합치지 않는다.

**현재와 후속·확인 사례.** 역할 있는 frame과 의미 수정, 활성화 정책, 제한된 topology
연산은 기존 경로를 사용한다. 일반적인 의미 동등성 판정과 개별 연결의 인과 기여는 후속
연구다. 역할 교환·반복 참여·예외 제거·유사하지만 다른 대상의 병합을 반례로 검사한다.

문헌 확인: 2026-10-24. 구현 설계·확인 사례는 AI의 공학적 적용이며 논문의 직접 결론과 구분한다.
