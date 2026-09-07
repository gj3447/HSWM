# HSWM 철학 ontology와 표준 그래프 연결 점검

점검 기준: `ef80df672814e7bc505140ea3e22042ad70d9af1`, 2026-09-07 live read.
상태: `ENGINEERING_AUDIT / SEMANTIC_COVERAGE_PRESENT / INTEGRATION_PARTIAL`.

**HSWM의 내용과 철학적 함의는 KG에 상당히 구체적으로 정리돼 있다. 다만 최근 연구
묶음의 정확한 정합성을 전체 철학 계보의 최신 동기화·MCP 조회·표준 RDF 통합 완료로
일반화할 수는 없다.** 이번에는 주요 live bundle 8개, 철학 P1~P10, FCL-1~8,
선택한 철학 artifact 7개의 현행 RDF compiler 호환성과 MCP 검색을 확인했다.
모든 ontology 파일·모든 그래프 client·모든 과학적 주장에 대한 전수 인증은 아니다.

[기계 판독 점검 기록](../../_research/graph_standards/results/HSWM_PHILOSOPHY_KG_AUDIT_2026-09-07.json)에
파일 digest, 비교 범위, 불일치 필드, 정확한 predecessor snapshot, 조회 결과를 남긴다.
이번 감사는 live KG를 읽었으며 기존 graph와 역사적 source bytes를 수정하지 않았다.
새 연구 결과·F1_R8 receipt·효능 판정은 아니다.

## 1. 실제로 잘 정리된 부분

| 철학·정체성 축 | 확인한 표현과 함의 |
|---|---|
| 하나의 token-native 몸 | 헌법과 adaptive TI-1/TI-2가 evolving hypergraph의 harness/world model/learner 역할을 하나의 목표 정체성으로 연결 |
| 관계·시간·오류 | P1 관계적 존재론, P2 계보적 시간론, P3 기억–진리 분리, P4 오류 가능성 각각 독립 UID와 관계를 가짐 |
| 개체성과 권리 | P5 차이 보존적 통일, P6 인과적 행위성, P7 참여·존엄, P8 공개 외부/보호 내부, P9 인지주권·보충성, P10 열린 목적론 |
| 프랙탈 합성 | FCL-1~8이 독립 노드이며 국소 학습·합성 보존·상황별 구성·다중규모 credit·형태 변화·세계/자기모델·연속성·재귀 참여를 구별 |
| 과학과 설계의 구별 | scientific-connections의 문헌 16개·reported construct·HSWM bridge hypothesis·falsification null이 다른 권위와 epistemic 상태를 가짐 |
| 실제 후속 논의 | 학습 계획과 C-1~C-3은 소유/구성원/권한, 미식별 credit, 작성된 outcome과 실측을 구별하고 이전 정본·결과에 연결 |

P1~P10은 live KG에 **10/10**, FCL은 **8/8** 존재했다. 철학 10개 노드의 연결 수는
각각 2~5로, 고립된 이름표만 있는 상태는 아니다. 이는 내용의 존재와 연결을 확인한 것이며
철학적 참·현실 효능·인지 실현의 증거는 아니다. 현재 통합 과학 상태
`SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`를 유지한다.

근거 문서와 bundle은 [인류보편체 철학 ontology](../../ontology/identity/human_universal_body/HSWM_HUMAN_UNIVERSAL_BODY_ONTOLOGY.v1.json),
[FCL projection](../../ontology/identity/human_universal_body/HSWM_HUMAN_UNIVERSAL_BODY_FRACTAL_PROJECTION.v1.json),
[과학적 연결](../../ontology/identity/human_universal_body/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_ONTOLOGY.v1.json),
[adaptive strategy](../../ontology/identity/hswm_core/HSWM_ADAPTIVE_RESEARCH_STRATEGY_ONTOLOGY.v1.json)다.

## 2. live KG와 checked-in bundle의 차이

표의 live 수는 해당 `ontology_bundle_uid`가 소유한다고 기록된 범위다. 같은 UID가 다른
역사 bundle에 있으면 구별해서 확인했다. 전용 publisher의 예상 필드로 비교했으며,
오래된 인류보편체 publisher의 동적 timestamp·추가 metadata는 전체 exact 비교에서 제외했다.

| 묶음 | repo 노드/관계 | live 소유 노드/관계 | 판단 |
|---|---:|---:|---|
| 인류보편체 v1 | 92 / 214 | 105 / 261 | 원래 UID와 관계 topology는 모두 존재. 후속 FCL 관련 13개 노드·47개 관계가 이 bundle 아래 추가돼 있고, Occam source 노드 digest 1개는 차이 |
| 별도 fractal projection v1 | 14 / 47 | 0 / 0 | 자체 bundle로는 게시되지 않은 상태. 기대 UID 13개와 관계 43개는 다른 bundle 아래 존재; projection root와 그 연결을 구별해야 함 |
| scientific-connections v1 | 54 / 150 | 54 / 150 | 전용 publisher의 노드·관계·필드와 정확히 일치 |
| adaptive strategy v1 | 35 / 170 | 34 / 161 | publisher가 인식하는 **EXACT_PREDECESSOR**. 최신 권위·출처 수정이 아직 반영되지 않음 |
| causal-composition v1 | 99 / 394 | 99 / 394 | topology는 일치. projection digest와 README source 노드 digest는 현재 repo와 다름 |
| graph-and-loop v6 | 130 / 412 | 130 / 412 | topology는 일치. projection digest·source 노드 digest 7개가 다름. 현재 checkout과 source binding 13개도 차이 |
| hypergraph learning plan | 63 / 247 | 63 / 247 | 노드·관계·전체 속성·라벨 정확히 일치 |
| workshop C-1~C-3 | 29 / 107 | 29 / 107 | 노드·관계·전체 속성·라벨 정확히 일치 |

`graph-and-loop v6`의 이후 runtime source 변화는 기존
[README](../../ontology/identity/hswm_core/README.md)에 역사 snapshot과 후속 변경으로
명시돼 있다. 현재 파일과 과거 digest가 다르다는 사실을 과학적 실패나 데이터 훼손으로
판정하지 않는다. 다만 현재 checked-in bundle과 live publication의 digest 차이까지
자동으로 해소되지는 않으므로, 정확히 어느 revision을 조회하는지 보여주는 계보가 필요하다.
인류보편체의 Occam 문서 역시 현재 파일과 옛 binding이 다른 것으로 확인했다.

### 우선 확인할 차이: adaptive strategy의 권위·출처 수정

live snapshot은 [publisher](../../scripts/upsert_hswm_adaptive_research_strategy.py)의
알려진 predecessor digest와 노드/관계 수 모두 일치한다. 부분 write나 미확인 혼합 상태로
관측된 것은 아니다. 현재 repo는 헌법 source node를 추가하고 TI-2~TI-5의 authority 표현과
출처 관계를 세분화했지만, live에는 그 이전 표현이 남아 있다.

예를 들어 TI-2의 live authority는 `USER_PRIMARY_TARGET_WITH_SECONDARY_FORMALIZATION`,
현재 repo는 `CANONICAL_TARGET_WITH_SECONDARY_FORMALIZATION`다. 이는 사용자 목표를
부정하는 변경이 아니라, 새 발화의 직접 권위와 기존 정본에서 이어받은 상세를 구분한
수정이다. 나머지 차이도 기계 기록에 남겼다. 새 계획에서 이 anchor를 참조한다는 사실만으로
anchor 내용까지 자동 동기화되지는 않는다.

## 3. KG에는 있지만 MCP에서는 찾기 어려운 철학 노드

`include_preliminary=true`로 다음 검색을 실제 수행했다.

| 검색 | MCP 응답 | direct KG 확인 |
|---|---|---|
| `P1 HSWM 관계적 존재론` | null | 해당 UID 존재 |
| `P3 HSWM 기억` | null | 해당 UID 존재 |
| `FCL-8` | null | 해당 UID 존재 |
| `HSWM fractal scientific connections` | null | 54/150 bundle 존재 |
| 최근 hypergraph learning plan 이름 | 정상 검색 | 해당 UID 존재 |

옛 인류보편체 노드 105개에는 `ontology_sensitivity_v1`이 없었다. scientific-connections
54개에는 그 필드뿐 아니라 현재 MCP가 표시하는 authority/lifecycle 계열의 versioned
metadata도 없었다. 반면 최근 두 묶음은 명시적 NORMAL 및 versioned authority를 갖는다.
MCP 도구가 **명시적으로 비밀이 아닌 active record**만 조회한다고 선언한 점과 이 차이는
검색 누락의 원인이라는 해석을 지지한다. MCP 서버 내부의 전체 filter/index 구현을
감사한 것은 아니므로, 유일한 원인으로 확정하지 않는다.

이것은 철학 내용의 부재와 다르다. 수정 시 검색의 보호 조건을 느슨하게 하거나 옛 노드를
일괄 NORMAL로 바꾸면 안 된다. 공개 source와 scope를 검토한 bounded discovery projection,
현재 metadata 규약, 정확한 legacy UID 연결로 해결할 수 있는지 먼저 정해야 한다.
옛 publisher의 exact readback과 충돌하는 임의 metadata 덧붙이기도 피해야 한다.

## 4. 표준 그래프와의 연결은 어디까지 됐는가

현행 `KgBundleSource/KgBundleGraphView`로 직접 읽은 결과는 다음과 같다.

| artifact | 직접 RDF bundle 입력 | generic SHACL |
|---|---|---|
| adaptive strategy, hypergraph learning plan, workshop C-1~C-3 | 모두 가능 | 각각 통과 |
| human-universal-body, 별도 fractal projection, scientific-connections | legacy schema라 직접 입력 불가 | 이 compiler로는 평가하지 않음 |
| retired core-responsibility v1 | 역할/primitive 중심의 별도 local schema | 이 compiler로는 평가하지 않음 |

legacy schema에는 전용 publisher·검증 경로가 있다. 최신 compiler의 형식 거부는 그
ontology의 실패 판정이 아니다. 중요한 것은 **새 bundle이 옛 JSON을 source hash로
참조하는 것과, 그 JSON 내부의 모든 철학 노드·관계를 RDF로 펼치는 것은 다르다**는 점이다.
현재는 전자가 확인됐고, 전체 철학 ontology의 통합 RDF 표현은 확인되지 않았다.

RDF는 triple 기반이며 n-ary 의미를 간접적으로 표현한다. 최근 계획의 relation instance와
역할 incidence는 이 표현에 맞고, grouping·role·ordinal·scope를 지운 flattening과 구별돼
있다. [W3C RDF 1.1](https://www.w3.org/TR/rdf11-concepts/)
참고한 [W3C n-ary 문서](https://www.w3.org/TR/swbp-n-aryRelations/)는 Working Group Note이며
HSWM 도메인 ontology 자체에 대한 표준 인증이 아니다.

[SHACL](https://www.w3.org/TR/shacl/)은 선언한 구조적 제약을 확인하고,
[PROV-O](https://www.w3.org/TR/prov-o/)는 derivation 등의 provenance를 표현하는 기반이다.
현재 적용된 검증이 철학의 참, outcome의 독립성, causal credit이나 효능을 증명하지는 않는다.
기존 [표준 acceptance 기록](../../_research/graph_standards/HSWM_GRAPH_STANDARDS_ACCEPTANCE.v1.json)의
pin된 구현·선택된 suite·명시된 제외 범위를 유지한다. RDF export의 단순 정렬을
RDFC 수행이나 전체 표준 적합성 인증으로 해석하지 않는다.

## 5. 철학적 최신 의미를 찾는 입구의 보완점

**retired fixed-role 표시:** [core-responsibility v1](../../ontology/identity/hswm_core/HSWM_CORE_RESPONSIBILITY_ONTOLOGY.v1.json)은
역사 bytes 안에 여전히 `CANONICAL_TARGET_IDENTITY`와 fixed `H/W/A/F/Pi` owner 문구를
갖고 있다. 상위 README와 [Effect runtime README](../../src/hswm/effect-runtime/README.md)는
이를 명확히 retired compatibility로 표시한다. 해당 두 local UID는 이번 live 검색에서
발견되지 않았으므로, live canonical model이 재도입됐다고 주장하지 않는다. 다만
[ontology 입구 README](../../ontology/README.md)의 field·learning 설명에는 옛 H/W/A
표기가 역사 구분 없이 남아 있어, 최신 정체성 진입점과 의미가 어긋날 수 있다.

**Wolfram 함의의 주소화:** [Wolfram 계획 문서](HSWM_WOLFRAM_RELATIONAL_CAPABILITY_RESEARCH_PLAN_2026-09-06.md)는
관계 상태·국소 변화·사건 계보라는 analogy와 물리 동일성·순서 독립성·효능의 비추론 경계를
명시한다. 그러나 최근 학습-plan bundle은 그 문서를 source로 결속할 뿐 이 대응을 직접
조회할 별도 의미 노드를 만들지는 않았다. 선택한 live HSWM Concept/AbstractNode 범위의
Wolfram 이름 조회도 0개였다. 이것은 문서의 함의가 모두 KG 질의 가능한 형태로 옮겨졌다고
말할 수 없는 구체적인 예다.

## 6. 권장 보완 순서

1. **최신 revision을 식별한다.** adaptive의 알려진 predecessor→current 수정 경로를
   검토하고, 별도 fractal projection과 기존 인류보편체에 들어간 FCL 계보를 정확히 표시한다.
   과거 source bytes와 scientific RED·claim ceiling은 보존한다.
2. **철학을 조회 가능하게 연결한다.** 공개 검토된 metadata projection으로 P1~P10·FCL·
   scientific bridge의 현재 scope와 원래 UID를 연결한다. USER_PRIMARY·SECONDARY_AI·
   문헌 보고·target·관측 상태를 합치지 않는다.
3. **선언한 의미를 보존한 표준 파생 표현을 만든다.** legacy source를 수정하는 대신
   source-bound derived RDF view와 구체적인 mapping loss를 둔다. 역할·경계·이탈·
   provenance·supersession·Wolfram 비추론 경계를 실제 질의로 확인한다.

이 순서는 발견한 연결 문제의 수리 제안이다. 새 HSWM 기전, 승인 gate 또는 효능 기준을
추가하는 계획이 아니다. 이번 감사의 완료와 위 수리의 완료는 구별한다.
