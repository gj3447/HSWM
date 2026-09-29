# 규칙의 HSWM적 구성: 온톨로지와 평가 v1

2026-09-29 · `SECONDARY_AI / PROPOSED` · `agent:codex`.
이 문서는 사용자 방향의 공학적 해석이다. 원문은 [별도 보존](../canon/sources/USER_PRIMARY_HSWM_LIKE_DISTRIBUTED_ACTIVATION_2026-09-29.txt)한다.
현재 작업은 개념·데이터 계약·평가 도구이며 실제 HSWM 학습 효능을 측정한 연구 결과가 아니다.

## 1. 정의와 기존 정전

**규칙 체계가 HSWM적이라는 것은, 원문과 그 원문에 결속된 여러 해상도의 의미 지도가
역할·문맥을 가진 관계 구조로 조직되어, 의미적 전이 성향에 따라 필요한 국소 부분을
찾고 활성화하며, 그 위치·연결·성향을 원문과 분리하여 제한된 범위에서 수정할 수 있다는 뜻이다.**

이는 이번 발화에 대한 조작적 정의 제안이다. 문서에 링크가 많거나 embedding이 있다는
사실만으로 충족되지 않는다. 역으로 하이퍼그래프 전용 DB를 써야만 충족되는 것도 아니다.
관계와 참여 역할을 보존하는 표준 그래프 표현도 가능하다.

[헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 HSWM은 큰 그래프 자체를 상태로 삼는 하나의
LLM 기반 AI다. 여기서 정의하는 **HSWM적 구성**은 규칙·메모리·검색 표현에 적용하는 부분적
설계 성질이다. 이 성질이 높아도 continuous learning, 신경망적 효능, 전체 HSWM 실현을
입증하지 않는다. [CHU 범위](../canon/USER_PRIMARY_CHU_HSWM_SOFTWARE_SCOPE_2026-09-27.md)는
HSWM보다 넓다. 이 프로파일은 CHU 전체를 규칙 검색기로 축소하지 않는다.

Semantic Weight는 [기존 이론](HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md)의
**역할·문맥별 전이 성향**을 이어받는다. 저장된 관계 설명과 파라미터를 versioned interpreter가
해석하는 성향이지, 임의의 실수 하나를 새로 붙인 이름이 아니다. 다음을 별도로 저장한다.

| 항목 | 의미 | 자동으로 뜻하지 않는 것 |
| --- | --- | --- |
| Semantic Weight / disposition | 관계를 읽었을 때 가능한 공동 전이의 성향 | 인과 효능이 이미 검증됨 |
| selection score | 이번 작업에서 후보 관계를 고르는 수치 | 진실, 권한, 사용자 우선순위 |
| activation | 실제로 읽거나 실행한 국소 경로 | 영속적 학습 갱신 |
| evidence / uncertainty | 주장·추정의 출처와 불확실성 | 활성화량 또는 의미 자체 |
| HSWM-like score | 이 평가 프로파일에 대한 증거 수준 | 위 네 값을 대체하는 통합 가중치 |

기존 KG `sym:Concept:hswm`에는 폐기된 H/W/A/F/Π 분해가 남아 있다. 이를 이번 정의의 정본으로
재사용하지 않는다. 해당 노드는 수정하지 않고, 현재 schema-relative 헌법과 후속 정의를
연결한 제안으로 기록한다. 선행 KG `sym:Note:chatgpt-hswm-literature-synthesis-roadmap-2026-09-17`,
`sym:Note:chatgpt-chu-hswm-scope-20260927`의 AI 제안 상태도 유지한다.

## 2. 온톨로지는 무엇을 담당하는가

온톨로지는 대상의 식별자·타입·역할·관계 의미·유효 범위·출처를 정한다. 검색 지도는 그 위의
관측·내비게이션 view이고, 활성화 정책은 그 view를 사용하는 실행 계약이다. 세 책임은
분리하되 서로의 revision을 참조한다. ontology가 있다고 좋은 routing이 자동으로 생기지 않는다.

| 타입 | 필수 의미와 분리 기준 |
| --- | --- |
| SourceArtifact | 원문 bytes, revision, digest, 작성자, 출처. AI 요약으로 덮어쓰지 않음 |
| RuleUnit | 적용 조건·행동·예외가 함께 해석되는 단위. 무조건 한 문장으로 쪼개지 않음 |
| MapView / MapBinding | 해상도·요약·원문 범위·손실·source revision·복원 경로 |
| HyperRelation / Participation | 관계 ID와 참여자의 역할·필요한 순서·공동 조건·문맥 |
| SemanticDisposition | 해석 계약·revision·역할/문맥별 전이 성향. scalar score와 분리 |
| Context / Placement | 작업·대상·행동·scope와 의미적 이웃. 물리 폴더와 동일시하지 않음 |
| ActivationPolicy / Episode | 후보 선택·예산·필수 규칙 closure와 실제 읽은 기록 |
| LocalPatch | 대상 revision, read/write set, 변경 근거, 기존 owner의 admission, rollback |
| Assessment / Evidence | 평가 대상 revision·작업 분포·각 축의 근거·미평가·프로파일 버전 |

단위는 source의 byte offset 또는 안정적인 section ID를 가리킨다. 부분 읽기의 완전성은
조건·예외·상위 규칙까지 포함하는 dependency closure로 확인한다. 요약에는 적용 범위와
누락된 조건을 표시하고, 실행 전 선택된 규칙 원문 전체를 끝까지 읽는다. source hash가 바뀌면
요약을 오래된 view로 표시하고 재생성한다. `related`/유사도는 `requires`나 `sameAs`가 아니다.

역할 있는 n항 관계를 일반 그래프에 옮길 때 `relation → participation → target`으로 둔다.
각 participation은 role, ordinal, revision을 가진다. unordered 역할 안의 열거 순서와
의미를 바꾸는 시간·입출력 순서를 구분한다. conjunction을 pairwise clique로 바꾸면서
관계 ID·조건·예외를 버린 표현은 동등하다고 주장하지 않는다.

이번 [JSON 온톨로지](../../ontology/identity/hswm_core/HSWM_LIKE_RULE_ACTIVATION_ONTOLOGY.v1.json)는
기존 KG bundle 형식을 사용한다. 새 predicate의 domain/range/cardinality/meaning을
`PREDICATE_DEFINITION` 노드로 선언한다. 기존 RDF projection과 SHACL 1.0으로 검증한다.
이는 로컬 해석·교환 프로파일이며 live Neo4j의 정전 스키마를 임의로 늘리는 migration이 아니다.
프로파일 색인 노드에는 설명·문헌 링크가 모인다. 이 메타데이터 차수를 실제 rule activation
차수로 세지 않으며, `REFERENCES` 이웃을 모두 읽게 하는 실행 의미도 부여하지 않는다.

## 3. 넓게 분포하되 필요한 부분으로 찾아가기

```text
작업·대상·행동
  → 여러 의미 지도에서 관련 이웃 탐색
  → 역할·문맥·공동 조건으로 후보 좁히기
  → 적용되는 필수 규칙과 예외의 closure 계산
  → 선택한 원문을 revision 확인하며 완전히 읽기
  → 국소 실행 / 실제 activation 기록
  → 결과 근거가 있으면 제한된 patch 제안
```

여기서 단계들은 구현 인터페이스 설명이지 HSWM을 영구적인 여러 subsystem으로 분해한 것이 아니다.
선택은 단순 threshold 한 번으로 끝나지 않는다. 필수 규칙이 예산을 넘으면 page·재검색·분할
실행·명시적 budget 조정으로 처리한다. 높은 점수의 몇 개만 남기며 필수 예외를 버리지 않는다.
어떤 작업에서 요구되는 원문인지 불명확하면 `unknown applicability`로 드러내고 관련 원문을
읽어 해결한다. 알려진 참조만 닫았다는 사실로 실제 required set 전체를 알았다고 주장하지 않는다.

**CHU에서의 위치**는 stable UID가 가진 타입과 문맥별 이웃·참여 역할·view 좌표다. 동일한
규칙은 배포·저장소·보안 등 여러 지도에서 다른 위치로 나타날 수 있다. 이를 위해 원문,
의미 단위, placement, disposition, 실제 activation 기록을 서로 다른 revision 객체로 둔다.
agent는 허용된 placement/관계 후보를 국소 변경할 수 있지만 source나 사용자 권위를
조용히 바꾸지 않는다. patch는 기대 revision과 변경 범위를 검사하고 기존 owner 경로로
admit한다. 본 작업은 이 계약을 정의하며 새로운 쓰기 실행기나 자동 rewiring을 설치하지 않는다.

| 관측량 | 정확한 정의와 해석 |
| --- | --- |
| structural degree | 노드에 참여한 서로 다른 hyperrelation ID 수. 반복 role 수와 구분 |
| arity | 한 hyperrelation의 participation 수. 서로 다른 target 수와도 구분 |
| candidate fan-out | query당 검토한 후보 수. 실제 활성 단위 수와 분리 |
| active units / bytes / tokens | 실제 원문을 읽은 단위와 비용. 탐색 비용도 별도 합산 |
| required coverage | 독립적으로 판정한 required set 중 완전히 읽은 비율 |
| irrelevant activation | 활성 단위 중 독립 판정상 불필요한 비율 |
| concentration | 작업 분포별 activation share의 HHI와 effective count; 균등화 목표 아님 |
| reachability / tail cost | 올바른 원문으로 도달하는 경로·p95 비용·놓친 예외 |

```math
\mathrm{Coverage}(q)=\frac{|A(q)\cap R(q)|}{|R(q)|},\qquad
\mathrm{Waste}(q)=\frac{|A(q)\setminus R(q)|}{|A(q)|},\qquad
\mathrm{HHI}=\sum_v p_v^2,\qquad \mathrm{EffectiveCount}=1/\mathrm{HHI}.
```

`A`는 완전히 읽은 원문 단위, `R`은 평가자가 사전에 판정한 적용 규칙이다. 빈 분모는
`N/A`이며 0이나 1로 임의 채우지 않는다. `p`는 선언한 작업 묶음에서의 활성화 점유율이고,
빈 workload에는 HHI를 계산하지 않는다. 공통 필수 규칙이 자주 활성화되는 것은 정상일 수
있다. 중요한 것은 한 허브가 무관한 이웃을 매번 전부 펼치거나, 예산을 소진시키는지다.
반대로 차수를 무조건 낮추면 단절과 정보 병목이 생긴다. 보편적인 최적 연결 개수는 미정이다.
후보 fan-out·hop·예산은 workload별로 정하고 coverage와 비용의 Pareto 비교로 조정한다.

## 4. HSWM-like rule score v1

**새로운 AI 제안 지표**이며 공인 표준이나 사용자 지정 수치가 아니다. 각 규칙 또는 rule-set의
동일 revision·동일 작업 분포를 비교한다. 서로 다른 scope나 증거 수준의 점수를 순위로 섞지 않는다.
8축의 vector를 먼저 보고, 모두 평가되었을 때에만 동일 가중치의 0–100 합성점을 표시한다.

| 축 ID | 평가 질문 |
| --- | --- |
| source_fidelity | 원문·출처·권위·revision을 보존하고 실제 원문으로 돌아가는가? |
| multiscale_map | 지도 해상도와 원문 범위·손실이 명확하며 필요한 전문을 복원하는가? |
| role_composition | 역할·공동 조건·예외·필요한 순서를 보존하는가? |
| context_activation | 대상과 작업에 맞게 필요한 규칙을 빠짐없이 고르는가? |
| distributed_navigation | 무관한 폭발적 활성화를 피하면서 필요한 위치에 도달하는가? |
| local_adjustability | 원문을 보존하며 국소 위치·연결을 versioned patch로 조정하는가? |
| semantic_disposition | 의미적 전이 성향과 selection score·권위·truth를 구분하는가? |
| evaluability | 실제 활성화·결과·비용·실패를 재현 가능한 근거로 평가하는가? |

각 축의 evidence ladder: **0** 관측된 부재/위반, **1** 문서 계약,
**2** 구조·복원·정적 또는 합성 사례 검사, **3** 대표 실제 작업에서 관측,
**4** 사전에 정한 기준과 독립된 fresh 사례·적절한 대조/개입으로 확인.
4는 보편적 인과 증명이나 세계 전체의 일반화를 뜻하지 않는다. 세부 축별 판정 질문은
[rubric JSON](../../ontology/identity/hswm_core/HSWM_LIKE_RULE_SCORE.v1.json)에 있다.

```math
\mathrm{Score}_{v1}=100\frac{\sum_i w_i s_i}{4\sum_i w_i},\qquad w_i=1.
```

미측정은 `null`이고 전체 점수도 `null`이다. 판정된 0에도 관측 근거가 필요하다.
원문/권위 변조, 조건·예외 손실, 필수 원문 누락, 무단 영속 변경은 점수로 상쇄하지 않는다.
이 네 invariant가 false면 `INVALID`, unknown이면 `INCOMPLETE`다. 여기서 invariant는
평가 대상의 판정선이며 평범한 작업 전마다 새 승인 절차를 만드는 규칙이 아니다.
평가 CLI는 제출된 판정·근거 참조의 형태와 산술을 검증한다. 근거가 참인지, 규칙이 의미적으로
유용한지는 자동 판정하지 않는다. 점수로 canonical status/confidence를 변경하지 않는다.

```sh
.venv/bin/python scripts/evaluate_hswm_like_rules.py validate
.venv/bin/python scripts/evaluate_hswm_like_rules.py score ontology/identity/hswm_core/HSWM_LIKE_RULE_ASSESSMENT_TEMPLATE.v1.json
.venv/bin/python -m pytest -q tests/test_hswm_like_rules.py
```

현재 template은 실제 작업 평가를 수행하지 않은 상태이므로 `INCOMPLETE`, 점수 `null`이다.
로컬 단위검사의 합성 입력에서 나온 수치는 현 CD 규칙의 점수가 아니다.

## 5. 검색한 1차 소스와 적용 범위

2026-09-29 확인. 초록/규격의 해당 절을 근거로 삼고 성능 수치를 HSWM에 이식하지 않는다.

| 소스 | 확인한 내용과 이 설계에 쓰는 범위 | 한계 |
| --- | --- | --- |
| [W3C n-ary relations, 2006 Note](https://www.w3.org/TR/swbp-n-aryRelations/) | binary RDF에서 relation instance와 참여 역할로 다자 관계 표현 | informative Note이며 모든 clique projection의 동등성을 보증하지 않음 |
| [SHACL 1.0, 2017 Recommendation](https://www.w3.org/TR/2017/REC-shacl-20170720/) | RDF의 cardinality·type·필수값 검사 | 의미의 참이나 routing 효능 증명 아님 |
| [PROV-O, 2013 Recommendation](https://www.w3.org/TR/prov-o/) | entity/activity/agent·derivation으로 출처 연결 | provenance의 존재가 source 내용의 참을 뜻하지 않음 |
| [SKOS, 2009 Recommendation](https://www.w3.org/TR/skos-reference/) | label·concept scheme·broader/related·mapping 구분 | 탐색용 개념 연관을 논리적 동일성으로 승격하지 않음 |
| [AllSet, v4 / ICLR 2022](https://arxiv.org/abs/2106.13264v4) | hypergraph layer를 두 multiset 함수 합성으로 구성 | role/order 보존은 이 프로파일의 별도 의무 |
| [RAPTOR, v1 / 2024](https://arxiv.org/abs/2401.18059v1) | chunk와 recursive summary의 여러 해상도 검색 | 하나의 tree를 CHU의 유일 구조로 채택하지 않음 |
| [HippoRAG 2, v2 / ICML 2025](https://arxiv.org/abs/2502.14802v2) | graph association·Personalized PageRank와 passage integration | retrieval 개선이 outcome-bound HSWM 학습 증거는 아님 |
| [Switch Transformers, JMLR 2022](https://www.jmlr.org/papers/v23/21-0998.html) | 입력에 따라 다른 expert를 선택하는 sparse computation | 규칙 routing의 최적 top-k·차수를 결정하지 않음 |
| [Alon–Yahav, v4 / ICLR 2021](https://arxiv.org/abs/2006.05205v4) | 긴 경로에서 많은 정보를 고정 크기로 모으는 GNN bottleneck | 문서 과다 로딩과 같은 현상이 아님; 무조건 pruning의 반례 방향 |
| [Hyperon July 2026 whitepaper §1.9, §10.3](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf) | selected typed graph reads, candidate writes, Context Frame과 명시된 maturity 구분 | implemented·prototype·design·hypothesis를 합쳐 완성품이라 부르지 않음 |
| [Hyperon experimental README, 3f76dc4](https://github.com/trueagi-io/hyperon-experimental/blob/3f76dc460da6961f57f69f6c3e550c59c74ada83/README.md) | 해당 revision의 MeTTa/Hyperon 개발·실행 표면, pre-alpha 표기 | whitepaper 전체 구현 또는 현재 배포 전체의 maturity 판정은 아님 |

Hyperon은 필수 비교 대상이다. 이번 작업은 그 설계의 typed local read/candidate write와
성숙도 구분을 대조했고 설치나 성능 비교 실행은 하지 않았다. RDF 표준, retrieval 논문,
HSWM의 Semantic Weight를 하나의 이미 입증된 알고리즘처럼 합치지 않는다.

## 6. 검증 질문과 후속 실제 평가

로컬 graph 검사는 아래 질문의 **내용**을 검사한다. node 수는 관측 메타데이터다.

1. 원문과 AI 정의가 서로 다른 권위로 식별되고 정확한 source hash로 연결되는가?
2. 의미 지도에서 원문으로 복원 경로와 선언된 손실을 찾을 수 있는가?
3. 예시 n항 관계의 task/path/action/exception/rule 역할을 순서 정보와 함께 되찾는가?
4. predicate domain/range/cardinality, endpoint, 고립 노드, 출처 변조를 탐지하는가?
5. 모르는 score와 invariant가 거짓인 score를 높은 종합점으로 표시하지 않는가?

실제 CD 적용 평가는 동결한 규칙 revision과 작업 묶음에서 full-context, 기존 정적 router,
일반 retrieval, 이 설계의 후보를 같은 원문·자원 조건으로 비교한다. 평범한 코드 변경,
CLI 사용, graph/schema 변경, 경계 경로, scope 변경, 애매한 지시, 예외 규칙을 포함한다.
정답 required set은 후보가 고른 목록으로 대신하지 않고 별도로 판정한다. 누락·오적용,
source stale, source bytes/tokens, 탐색/전체 latency, tail cost, 사용자 작업 성공을 기록한다.
edge 추가/제거와 map 요약 유무를 분리한 ablation으로 무엇이 기여했는지 살핀다.
새 숫자나 학습 개선은 실제 결과가 나온 다음 기록한다.

이번 정의의 변경점은 원문/지도 결속, 역할 관계, 분산 탐색, 국소 patch, 평가 프로파일이다.
canonical runtime schema나 CR/FCL 판정은 변경하지 않는다. source와 interpreter 구분을
보존하며, 구조 검증과 실제 효능을 분리한다.

## 7. KG 게시와 재사용

온톨로지 전체는 로컬 JSON과 표준 RDF view로 보존한다. live KG에는 기존 Relay KG의
owner-managed draft publisher로 정의·지도/원문·연결성/조정·평가·연구 근거를 별도 기록하고
`ABOUT` / `REFERENCES` / `DERIVED_FROM`으로 연결한다. AI record는 `SECONDARY_AI`,
`PENDING_OR_PRELIMINARY`, 새 링크는 `PROPOSED`다. 사용자 원문은 원문 파일과 digest로
인용하고 draft 자체를 사용자 정전으로 가장하지 않는다. 원문 노드의 authority와 AI 제안의
authority는 local graph에서도 분리한다.

새 predicate는 로컬 bundle의 제안 vocabulary다. 이 게시로 해당 predicate가 Neo4j의
정전 스키마에 등록되거나 전용 자동 활성화 runtime이 설치되었다고 주장하지 않는다.
검색 시 `ontology_search("HSWM적", include_preliminary=true)` 또는
`ontology_search("hswm-like", include_preliminary=true)`로 찾는다.
실제 UID·내용 readback은 이 문서와 함께 생성하는
[게시 결과](artifacts/hswm_like_rules_2026-09-29/kg-publication.v1.json)에 남긴다.
