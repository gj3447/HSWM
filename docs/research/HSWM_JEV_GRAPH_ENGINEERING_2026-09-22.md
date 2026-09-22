# Jev 연구를 잇는 HSWM 표준 그래프 엔지니어링

2026-09-22 · `SECONDARY_AI_ENGINEERING_PROPOSAL` · `NO_HSWM_EFFICACY_OR_CR_FCL_PROMOTION`

**Jev에서 가져온 결정 출력 계약을 HSWM의 관계 버전·국소 실행·관측 결과·의미 수정 계보에 연결한다.** 기존 RDF 1.1·PROV-O·SHACL·SPARQL 도구로 이 연구 구조를 조회하고 검증한다. 이번 산출물은 연구 조직 문서와 출처 결속 KG이며, 새로운 모델 실험이나 runtime schema 변경은 아니다.

HSWM은 **하나의 큰 AI, 하이퍼그래프 신경망 조직, LLM 함수라는 기본 계산 단위, 하이퍼그래프 Semantic Weight를 통한 작동**을 함께 목표로 한다. 큰 의미 하이퍼그래프가 AI 상태 자체이며 LLM은 작은 국소 입력을 받는 내부 연산자다. 그 동일한 상태가 living harness·world model·continuous learner 역할을 한다. [정체성](../canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md), [상태·연산자 정의](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md), [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)을 유지한다.

**개념적 변화:** 기존 P1–P6을 나열하는 데서, 각 원리가 어떤 그래프 객체·버전·검사·후속 연구에 해당하는지 명시한다. 그래프 저장·검증의 성공, 국소 의미 실행의 성공, outcome에 의한 학습 개선을 각각 판단한다. 연구 KG의 owner는 자료의 책임 주소이며 runtime atom의 owner나 실행 허가를 대신하지 않는다.

## 1. 이미 가져온 자료와 현재 증거

| 기록 | 이어받는 내용 | 권위와 범위 |
|---|---|---|
| [9월 20일 연구 통합](HSWM_RESEARCH_INTEGRATION_2026-09-20.md) | TypeSafe/Jev 공개 설명, Choice·Score·Noul, RLCD와 관련 문헌의 구별 | vendor 설명과 SECONDARY_AI 적용 해석 |
| [9월 21일 원리별 적용](HSWM_JEV_PRINCIPLES_2026-09-21.md) | P1–P3 공개 원리, P4 HSWM 확장, P5–P6 기존 HSWM 의무 | 구현·설계·가설의 상태를 개별 보존 |
| [9월 21일 DGX 결과](../../results/HSWM_JEV_PRINCIPLES_2026-09-21.md) | 같은 Qwen3-4B의 직접 이진 logprob 읽기와 JSON 생성 비교 | 네 synthetic 관계족의 관측; Jev/RLCD 실행·재현 아님 |

공식 [AI primer](https://docs.typesafe.ai/introduction/machine-learning-primer)와 [primitive 문서](https://docs.typesafe.ai/primitives)를 9월 22일 다시 확인했다. 공개 계약은 typed 결정과 확률, 동일 state를 읽는 여러 질문이다. 이 확인은 비공개 학습법의 재현 가능성이나 실제 보정 성능의 독립 검증을 추가하지 않는다. 질문들의 실행 독립성에서 세계 변수들의 통계적 독립성을 도출하지 않는다.

후속 설계가 반드시 보존할 관측은 다음과 같다.

| 고정된 관측 | 그래프에 남길 해석 | 다음 과제 |
|---|---|---|
| direct 480/480 유효, JSON 389/480 유효; 평균 71.95ms / 970.71ms | 이 서버·출력 계약의 안정성 및 지연 관측. 공유 trunk나 동등 품질당 우위 아님 | P1 측정 도구는 유지 |
| oracle direct 27/48, frozen 29/48, learned 26/48 | 정확한 관계를 준 국소 실행에도 병목. 조건들은 같은 test 48건을 공유 | W1 국소 의미 실행 |
| 네 revision commit, 의미 관련 필드 변화 0건 | 저장 성공과 의미 변경을 구분. learned/evidence-only 요청 bytes 동일 | W2 실제 의미 변경 진단 |
| direct 모든 arm의 보정 후 NLL·Brier가 항상 0.5 기준보다 나쁨 | 확률 보정의 유용성 미확인. T는 분석 artifact이며 canonical 학습 아님 | W1 확률 품질·거부 포함 평가 |

원래 [관측](artifacts/hswm_jev_principles_2026-09-21/observations.v1.json)과 [감사](artifacts/hswm_jev_principles_2026-09-21/audit.v1.json)를 그대로 참조한다. 동일 요청의 응답 변동도 관측됐으므로, canonical hash 복원을 응답 재현으로 바꾸어 적지 않는다. 이번 정리는 새 과학적 결과를 추가하지 않는다.

## 2. 사용할 표준과 기존 구현

| 역할 | 선택한 공식 문서 | HSWM에서의 경계 |
|---|---|---|
| 데이터 교환 | [RDF 1.1 Concepts, 2014 Recommendation](https://www.w3.org/TR/2014/REC-rdf11-concepts-20140225/) | 기존 named-graph N-Quads projection 재사용 |
| 출처 표현 | [PROV-O, 2013 Recommendation](https://www.w3.org/TR/2013/REC-prov-o-20130430/) | 현재 adapter는 source entity → projection activity → view entity를 표현. 아래 runtime 실행 계보 전체를 자동 변환하지 않음 |
| 구조 검사 | [SHACL, 2017 Recommendation](https://www.w3.org/TR/2017/REC-shacl-20170720/) | 선언한 shape에 대한 구조 검사. 진실성·LLM 이해·효능 판정 아님 |
| 조회 | [SPARQL 1.1 Query, 2013 Recommendation](https://www.w3.org/TR/2013/REC-sparql11-query-20130321/) | 기존 로컬 SELECT/ASK 범위. canonical write-back 없음 |
| 다자 관계 표현 참고 | [N-ary Relations, 2006 Working Group Note](https://www.w3.org/TR/2006/NOTE-swbp-n-aryRelations-20060412/) | 관계 인스턴스와 참여 역할을 객체화하는 패턴; Recommendation 아님 |

9월 22일 확인한 [RDF 1.2 Concepts](https://www.w3.org/TR/rdf12-concepts/)는 2026-04-07 Candidate Recommendation Snapshot이다. 이 작업의 안정 경로는 RDF 1.1로 유지한다. HSWM의 `DERIVED_FROM`, `ABOUT`, `DEPENDS_ON` 같은 local vocabulary와 아래 객체명은 W3C가 의미를 승인한 어휘가 아니다.

기존 [그래프 구현 경계](../operations/HSWM_FULL_STACK_GRAPH_ENGINEERING_2026-09-02.md)와 [잠금 manifest](../../_research/graph_standards/HSWM_GRAPH_STANDARDS_ACCEPTANCE.v1.json)의 도구를 재사용한다. 새 DB·SDK·패키지를 선택하거나 설치하지 않는다. 기존 독립 구현의 한정된 conformance 기록을 전체 표준 준수로 확대하지 않는다.

## 3. 관계·결정·학습을 위한 데이터 사전

아래는 **기존 canonical atom/typed reference 위에 대응할 설계 계약**이다. 모든 항목이 현재 schema나 runtime에 구현됐다는 뜻은 아니다. 영속·수정·복구되는 relation과 incidence에는 schema-relative owner 하나와 자체 revision 계보가 필요하다.

| 객체 또는 참조 | 최소 보존 정보 | 구분할 대상 |
|---|---|---|
| RelationVersion | schema·lineage·atom UID·revision, owner, semanticText, disposition, exception/evidence 참조 | 저장된 의미와 실행된 전이 성향 |
| RoleParticipation | relation version, 참여 atom의 정확한 version, 역할·reference type·slot/ordinal | 역할 교환과 같은 역할 내부 열거 순서 변경 |
| ReadFrame | source snapshot, 실제 read-set 및 payload hash, context, 빠진/추가 요청 정보 | 작은 입력이라는 크기와 의미적 충분성 |
| DecisionContract / CandidateSet | 출력 타입, 후보와 순서, 계약 version, 후보 범위 및 `other/expand` 의미 | 후보 내 정규화와 후보 누락 |
| Execution / Prediction | 별도 execution ID, frame·model/config·계약·요청 bytes, 예측·확률·거부·비용 | 반복 호출 occurrence와 동일한 내용 hash |
| Outcome | prediction/trace 참조, 관측 source, 사건·기록 시점, 평가 모집단 | 예측·자기 설명과 관측 결과 |
| CalibrationArtifact | fit 표본·split, model/relation/계약 version, 방법·T·평가 범위 | 보정 파라미터와 의미 수정·인과 credit |
| RevisionProposal / CommittedRevision | parent version, bound trace/outcome, 제안·검사·commit 결과, semantic/evidence 변경 내역 | 제안됨·저장됨·실제 의미가 바뀜·효용이 개선됨 |

형태는 `RelationVersion → RoleParticipation → ParticipantVersion`이다. 같은 참여자가 여러 slot에 나타나거나 같은 참여자 묶음에 여러 관계가 존재해도 합치지 않는다. 예를 들어 문·열쇠·권한·수신자를 하나의 관계 버전에 결속하고, “파손된 열쇠” 예외는 해당 version의 참조로 남긴다. `문—열쇠` 유사성 edge 하나로 이 결속을 대체할 수 없다.

[표현 연구](HSWM_SEMANTIC_WEIGHT_DEFINITION_AND_HYPERGRAPH_2026-09-14.md)의 tagged incidence 보존은 이런 저장 선택을 허용한다. 단순 clique projection의 손실은 모든 이항 그래프·비선형 pairwise 계산의 불가능성 주장이 아니다. 새 저장 adapter를 만들 때는 relation identity·역할·중복 slot·payload·revision·owner·복구의 round trip을 해당 구현에서 별도로 검증해야 한다.

Semantic Weight는 역할·문맥 조건부 **공동 전이 성향**이다. routing score, 후보 내 예측 확률, evidence mass, calibration, causal estimand를 하나의 `weight` 필드로 합치지 않는다. 이번 KG에서 이 구별을 기록하는 것과 실행 중 HSWM이 이 계약을 실현하는 것은 별도다.

## 4. P1–P6의 그래프 계약과 실행 순서

| 원리 | 그래프 엔지니어링 대응 | 현재 판단 |
|---|---|---|
| P1 typed 결정 | relation/frame/contract version에 묶인 Prediction; 후보 누락·판정/확률 모순 명시 | 기존 측정 구현 유지, 의미 정확성 별도 |
| P2 outcome 보정 | Prediction–Outcome join, 별도 CalibrationArtifact와 test population | 분석 구현 있음; canonical 학습·신뢰 확률 채택 보류 |
| P3 같은 state 공유 | 동일 snapshot read와 질문 간 의존성 DAG; dependent 질문은 다음 단계 | 설계. 실제 공유 계산·병렬 성능 미측정 |
| P4 후보·읽기 구성 | versioned CandidateSet, 허용된 추가 ReadFrame, 후보 recall | HSWM 확장. 자율적 후보/토폴로지 발견 미구현 |
| P5 공동 법칙 | joint candidate/factor 또는 명시적 conditional factorization, role incidence | HSWM 의무. 주변확률 곱으로 대체 불가 |
| P6 재귀 합성 | 하위·상위의 같은 typed Step/Learn와 lineage·예외·불확실성 참조 | HSWM 전이 가설. nested graph만으로 FCL 성립 안 함 |

실행 계약은 `snapshot 읽기 → 국소 LLM 실행 → outcome 전 trace 고정 → 관측 결속 → revision 제안 → 기존 검증/권한/충돌 검사 → commit → 다음 실행의 새 version 읽기`다. owner는 책임 주소이고 permission을 자동 부여하지 않는다. 공유 snapshot의 독립 read를 batch할 수 있다는 설계는 동시 write나 stale revision의 commit을 허용하는 근거가 아니다.

감사는 세 변화량을 따로 기록해야 한다. 첫째 canonical version/bytes 변화, 둘째 의미 본문·disposition·역할·예외 등 의미 관련 표현의 변화, 셋째 새 사례에서 전이·효용의 변화다. 표현 hash 차이는 의미 차이의 충분조건이 아니고, evidence 추가만으로도 전체 hash와 LLM 입력은 달라질 수 있다. 동일 의미의 재서술, evidence-only, sham, remove/restore 대조와 반복 측정을 남긴다.

확률의 대상도 명시한다. “후보 행동을 선택할 확률”과 “그 행동의 성공을 예측한 확률”은 다른 값이다. 보정 결과를 향후 실행에 지속 적용하려면 model·relation·출력 계약·fit population의 적용 범위와 변경 시 재검증/무효화 정책부터 구현해야 한다. 9월 21일의 T는 그 구현이 아니다.

## 5. 다음 연구: 관측에서 선행 과제를 정한다

아래 W1–W5는 `PLANNED` 연구 작업이며 새 성공 기준이나 새 FCL gate가 아니다. 숫자 기준·표본·budget·holdout·stopping rule을 고정한 실행 프로토콜은 아직 작성·실행하지 않았다. 기존 RED와 CR/FCL 성공 조건을 유지한 채, 각 실험 전에 구체화한다. W1–W3의 원인 진단은 병행 가능하지만 W4/W5의 결과로 선행 실패를 구제하지 않는다.

| 작업 | 직접 근거와 필요한 산출물 | 의존성·실패 시 처리 | 연결 의무 |
|---|---|---|---|
| W1 국소 의미 실행 | oracle 27/48 병목. oracle/frozen, 의미 제거·역할/예외 개입, 같은 정보·모델·비용의 계약 비교. 거부 포함 정확도와 확률 품질을 별도 측정 | 우선 과제. oracle에서도 실패하면 정보/encoding/모델 realization을 바꾸어 새 프로토콜로 시험; downstream scale 확대 보류 | CR-0/5, FCL-6 |
| W2 outcome에 의한 의미 수정 | 의미 변화 0건. semantic delta·evidence delta·request delta를 구별하고 evidence-only/sham/remove/restore 및 fresh-process 재사용 확인 | 학습 효능 판단은 W1의 실행 가능한 조건에 의존. no-op이면 no-op으로 기록; byte 변경만으로 성공 처리하지 않음 | CR-1/2, FCL-1/7 |
| W3 국소 읽기·후보 충분성 | 같은 read로 구별 못 하는 상태, 정답 후보 누락을 확인. full-context/fixed-read/adaptive-read와 후보 recall·추가 읽기 비용 비교 | 진단은 W1과 병행. hidden outcome을 읽게 하지 않음; 정보 손실이면 read/candidate 계약을 교정 | CR-4/5, FCL-3/5/6 |
| W4 공동 출력·동일 snapshot 실행 | 허용 joint transition, 배타/상보/삼중 제약, serial/batch/실제 공유 연산의 비용·위반·stale revision 비교 | W1–W3의 필요한 조건 이후. 주변분포만 같거나 batch만 빠르면 joint law/shared-compute 성립으로 기록하지 않음 | CR-3/6, FCL-2/4 |
| W5 두 scale에서 실행·학습 보존 | 하위/상위 모두 outcome→revision→다음 행동과 예외·불확실성·권한·exit·lineage·복원 확인 | W4 및 국소 학습 근거 이후. 요약이 Learn/개입을 잃으면 합성 방식을 수정하고 실패 계보 보존 | CR-6/7, FCL-2/8 |

**OpenCog Hyperon은 전 과정의 필수 핵심 비교 대상**이다. [직접 선행 감사](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)에 고정한 MeTTa `0.2.10`, commit `3f76dc460da6961f57f69f6c3e550c59c74ada83`와 persistent metagraph·neural bridge의 구현/prototype/설계 수준을 이어받는다. 이는 현재 최신 버전이라는 주장이 아니다. 실험 baseline은 정확한 component·commit·configuration·동일 정보/모델 접근·비용을 다시 고정해야 한다. 실행하지 못한 비교 항목은 미평가로 남긴다. 이번에 Hyperon이나 Jev API를 실행하거나 backend로 채택하지 않았다.

[적응 연구 전략](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)에 따라 방법·모델·backend는 교체할 수 있다. [FCL-1..8](HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md)의 인지 능력을 가진 HSWM들의 재귀적 합성 목표와 `SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED` 경계는 그대로다. [CR-0..7](HSWM_CONSTRUCTIVE_REALIZABILITY_PROGRAM_2026-09-10.md) 중 어느 의무도 이번 구조 정리로 완료되지 않는다.

## 6. 조회·검증과 이번 변경의 범위

[새 KG snapshot](../../ontology/development/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.v1.json)은 기존 P1–P6·실패 관측을 source-bound reference로 연결하고 그래프 계약과 W1–W5의 의존성을 기록한다. 이전 snapshot을 덮어쓰거나 같은 UID에 새 권위를 부여하지 않는다. [SPARQL 조회와 재생성 안내](../../ontology/queries/hswm_jev_graph_engineering_2026-09-22/README.md)에서 원리별 대응, 실패 근거, 다음 작업과 출처 누락을 확인한다.

구조 검증은 기존 native bundle decoder·RDF projection·SHACL·SPARQL과 정확한 로컬 source hash 대조를 사용한다. 외부 URL의 위치 digest는 문서 내용 hash가 아니며, 공식 문서의 읽은 범위와 날짜는 [공식 출처 확인](artifacts/hswm_jev_graph_engineering_2026-09-22/source-review.v1.json)에 기록한다. [검증 기록](artifacts/hswm_jev_graph_engineering_2026-09-22/validation.v1.json)은 이 작업의 구조·조회 결과이며 새로운 실험 receipt가 아니다.

이번에는 checked-in 연구 projection을 정리한다. runtime atom admission, 모델/그래프 의미 학습, live KG 게시, CR/FCL 승격을 수행한 기록이 아니다. 다음 실제 연구의 질문은 **“outcome이 관계의 의미를 바꾸고, 그 새 관계를 읽은 국소 LLM이 새 사례에서 더 유용하게 작동하는가”**다.
