# HSWM 연구 통합 그래프 — 2026-09-20

**기존 HSWM 연구, `chatgpt-api` 연구 12건, Jev 조사와 DGX 실측을 출처 결속 온톨로지로 연결했다.** 개념적 변화는 연구 답변을 더 쌓는 데서, 주장·출처·조건·미해결 질문·실측을 함께 조회하는 구조로 옮긴 것이다. 그래프 정리는 HSWM 인지나 학습 상태의 구현·승격이 아니다.

HSWM은 하나의 큰 AI이며, 하이퍼그래프 신경망 구조를 가지고, LLM-function을 기본 계산 단위로 쓰며, 하이퍼그래프 Semantic Weight로 작동한다. 큰 의미 하이퍼그래프는 AI 상태이고 LLM은 국소 내부 연산자다. 이 네 정체성과 상태/연산자 원칙은 [사용자 정전](../canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md), [국소 연산자 정전](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md)에 남긴다. 여기의 분류와 연구 해석은 `SECONDARY_AI`다.

## 범위와 읽는 방법

| 자료 | 이번 처리 | 해석 경계 |
|---|---|---|
| 저장소 자료 244개 | 정전·연구 Markdown 149개와 ontology bundle 95개의 경로·SHA·원래 상태를 색인 | 모든 원문의 모든 주장을 새로 감사했다는 뜻이 아님 |
| 기존 live KG 기록 49개 | 원래 UID·본문 SHA·권위와 연결. R0~R8, 동역학·학습 이론·P1, 문헌 조사, Jev 포함 | 기존 노드를 덮어쓰지 않음; 초안을 사용자 확정 또는 실측으로 승격하지 않음 |
| `chatgpt-api` 연구 12건 | 원본 응답 SHA 검증, 주제별 제안·한계·다음 검증을 12개 구조화 주장으로 정리 | 원본 86,350자는 비공개 저장소에 보존; 응답 자체가 원문의 진실성 검증은 아님 |
| 외부 출처 242개 | 중복 URL을 합치고 어느 응답·주장이 인용했는지 연결 | 이번 직접 확인과 기존 AI 답변의 미재검증 인용을 구분 |
| DGX 실측 1건 | 80회 추론, 5조건의 관측·프로토콜·모델 관측·한계 연결 | 국소 합성 과제의 해석 관측. 학습·인과 효과·CR/FCL 완료 아님 |

저장소 색인은 이 통합 작업 직전의 direct `docs/canon/*.md`, `docs/research/*.md`와 `nodes`/`relations`를 가진 `ontology/**/*.json`의 명시적 범위다. 중첩 artifact·구현·raw data 전체를 망라했다고 주장하지 않는다. 95개 bundle UID 중 이번 `NORMAL` sensitivity 조회에서 기존 live anchor 14개를 해결했고 81개는 미해결로 보존했다. 미해결은 원본 부재 판정이 아니며 다른 UID로 임의 합치지 않았다.

[온톨로지](../../ontology/development/HSWM_RESEARCH_INTEGRATION_2026-09-20.v1.json)는 **677개 소유 노드, 기존 anchor 63개, 소유 관계 1,224개**다. 연구 제안 12개, 문헌 주장 9개, 기존 형식 연구 참조 14개, 실측 결과 5개와 미해결 의무 13개를 분리한다. role occurrence 51개는 주장·출처·대상·남은 의무 또는 실험·모델·프로토콜을 역할과 ordinal로 결속한다. 이것은 연구 관계 표현이며 HSWM runtime hypergraph를 대신하지 않는다.

## 기존 연구에서 이어받은 결론

9월 18일의 12개 응답은 Hyperon/Classic AtomSpace, durable TypeScript, LLM transport, 시간 기억, n항 상호운용, 외부 평가, observability, 인과 분석, optimizer, 합성, 최소 stack, qualification을 다룬다. 기존 수집 상태는 12/12 완료였고, 한 응답의 축약 URL 때문에 생긴 수집 불일치는 이전 복구 기록대로 보존했다. 이번에는 재요청하지 않고 저장된 exact response hash를 대조했다. UI의 `gpt-6-pro` 표시는 backend checkpoint 인증과 구별한다.

요지는 새 프레임워크를 한꺼번에 설치하는 것이 아니라, 기존 HSWM/Effect 기능의 부족한 계약을 확인한 뒤 필요한 부품만 검증하자는 제안이다. DBOS·AI SDK·Graphiti·Inspect·MLflow·DoWhy·GEPA 등의 우선순위는 **이전 AI 연구의 조건부 제안**이며 채택 완료나 최신 버전 보증이 아니다. 정확한 설치 pin·license·공식 원문·호환성은 실제 채택 시 다시 확인해야 한다. 이번 작업은 이들 패키지를 설치하지 않았다.

Hyperon은 backend 후보 여부와 별개로 필수 핵심 비교 대상이다. [직접 선행 감사](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)의 persistent metagraph·neural bridge와 구현/prototype/설계의 성숙도 구분을 보존한다. Classic AtomSpace 저장 기능을 Hyperon의 구현 완료로 옮겨 적지 않는다.

R0~R8와 mathematical dynamics, learning theory, closure-aware P1은 원래의 조건·반례·미해결 의무를 가진 초안으로 연결한다. 논문 결과와 가정, source-bound 근거와 인과 credit, stored meaning과 Semantic Weight disposition을 구분한다. FCL의 목표인 인지 능력을 가진 HSWM들의 재귀적 합성도 유지하며, nested graph나 도구 orchestration만으로 이를 실현했다고 보지 않는다.

## Jev와 논문 연결

Jev는 TypeSafe AI의 typed decision 모델이며 공식 소개일은 **2026-09-15**다. 9월 20일 당일 출시가 아니다. Choice·Score·Noul과 confidence 의미, vendor 결과의 경계를 분리했다. TypeSafe가 RLCD를 `Reinforcement Learning for Calibrated Decisions`라고 부르지만, 이번에 검토한 공식 자료에서는 정확한 모델 구조·base model·parameter 수·학습 데이터·loss/reward/optimizer·weights와 Jev 기술 논문을 확인하지 못했다. [공식 소개](https://typesafe.ai/blog/introducing-system-one-models-and-jev), [confidence 문서](https://docs.typesafe.ai/confidence)

관련 논문은 [RLCR v2](https://arxiv.org/html/2507.16806v2), [Guo 등의 calibration](https://proceedings.mlr.press/v70/guo17a.html), [Language Models (Mostly) Know What They Know](https://arxiv.org/abs/2207.05221v1), [InstructGPT](https://arxiv.org/abs/2203.02155v1)다. 각각 correctness confidence·보정·자기평가·연구자 배경의 연결이며, Jev의 공개되지 않은 개발 recipe라고 제시하지 않는다. RLCR과 Jev RLCD의 계보도 확인되지 않았다.

## DGX에서 새로 관측한 것

[결과 보고서](../../results/HSWM_LOCAL_SEMANTIC_PROBE_2026-09-20.md)에 상세 프로토콜·관측·receipt를 둔다. 원본/열거 순서 변경/동일 prompt 재입력은 16/16이며, 역할 사실 교환은 원래 정답 기준 14/16, 바뀐 입력의 정답 기준 16/16이다. 의미 제거는 15/16이다. 따라서 역할에 따른 국소 해석은 관측했지만, 의미 관계의 추가 효용은 아직 식별되지 않았다.

다음 우선 질문은 의미 제거 조건의 shortcut을 차단하는 사전 고정 과제, 모델 checkpoint 확인, 동등 예산, held-out outcome→durable revision→새 읽기, 정확한 제거·복원이다. 이번 `restored`는 prompt 재입력일 뿐 canonical graph 복원이 아니다. Jev나 Hyperon을 실행한 비교도 아니다. 기존 RED와 CR/FCL ceiling은 유지한다.

## 표준과 검증

[RDF 1.1](https://www.w3.org/TR/rdf11-concepts/), [PROV-O](https://www.w3.org/TR/prov-o/), [SHACL 1.0](https://www.w3.org/TR/shacl/), [SPARQL 1.1](https://www.w3.org/TR/sparql11-query/)을 기존 native TypeScript/Effect 도구로 사용한다. [W3C n-ary 관계 패턴](https://www.w3.org/TR/swbp-n-aryRelations/)은 Recommendation이 아닌 Working Group Note로 표시했다. HSWM의 로컬 role/edge 어휘를 W3C 표준 어휘라고 부르지 않는다.

source digest·소유권·기존 anchor·역할 cardinality·근거 없는 주장·미해결 의무를 검사한다. PROV derivation은 원자료의 진실성을 보증하지 않고, SHACL 통과도 과학적 효능을 판정하지 않는다. [쿼리와 재생성 방법](../../ontology/queries/hswm_research_integration_2026-09-20/README.md), [검증 기록](artifacts/hswm_research_integration_2026-09-20/validation.v1.json), [live publication 기록](artifacts/hswm_research_integration_2026-09-20/live-publication.v1.json)을 별도로 제공한다.
