# HSWM 연구 작업환경

2026-09-26 갱신. 현재 작업 안내는 이 문서와 [AGENTS.md](../../AGENTS.md)를 따른다.
기본 흐름은 **관련 자료 확인 → 변경 → 필요한 검사 → Git 기록**이다.
작업마다 전체 정전 읽기, 개발 episode·feedback, KG snapshot을 만들 필요는 없다.
날짜가 붙은 이전 환경·도구 문서는 당시 구현과 재현 정보를 확인할 때 사용한다.

HSWM은 LLM을 기본 계산 단위로 삼고 Semantic Weight 하이퍼그래프로 작동하는 하나의
AI를 목표로 한다. 큰 그래프가 상태이고 LLM은 국소 연산자다. 이번 정리는 작업 절차의
단순화이며, 기존 CR/FCL 판정·연구 목표·실험 성공 기준을 변경하지 않는다.

## 준비

저장소 루트에서 필요한 환경만 준비한다. Node/npm 기준은
[package.json](../../src/hswm/effect-runtime/package.json), 의존성은 기존 lockfile을 따른다.

```sh
npm --prefix src/hswm/effect-runtime ci --ignore-scripts
npm --prefix src/hswm/effect-runtime run build
```

Python 비교 구현이나 Python graph 검사를 실행할 때만 별도 환경을 준비한다.
기존 wrapper는 core/graph 환경을 분리하고 uv 0.12.3·CPython 3.12.13을 사용한다.

```sh
src/hswm/development/bin/hswm-python sync
```

이미 준비된 환경에서는 설치를 반복하지 않는다. 기본 편집·검사에는 Docker, Neo4j,
외부 LLM, GPU가 필요 없다. 서버·모델 실험은 실제로 필요한 작업에서 설정한다.

## 그래프 작업의 기본

| 목적 | 기존 도구와 작성 원칙 |
| --- | --- |
| 데이터 교환 | [RDF 1.1](https://www.w3.org/TR/rdf11-concepts/) 기반 projection. 기존 UID를 유지하고 type과 namespace를 명시한다. |
| 구조 검사 | [SHACL](https://www.w3.org/TR/shacl/)로 해당 schema의 필수 속성·자료형·참조를 검사한다. |
| 조회 | [SPARQL 1.1](https://www.w3.org/TR/sparql11-query/)로 필요한 질문을 표현하고 예상 결과를 확인한다. 현재 도구가 지원하는 조회 범위를 따른다. |
| 출처 | [PROV-O](https://www.w3.org/TR/prov-o/)와 기존 source path·revision·digest 필드를 사용한다. 일상 수정의 이력은 Git으로 충분하다. |
| 다자 관계 | relation/incidence node로 관계 ID, 참여자 역할·순서·문맥을 보존한다. 단순 pair edge로 내보낼 때는 손실을 명시한다. |

이 표는 기존 스택의 사용 기준이다. 모든 데이터를 새 RDF 원본으로 이관하거나 그래프 DB를
추가할 필요는 없다. 원본 JSON·런타임 상태와 조회용 projection의 책임을 구분한다.
새 의존성은 공식 문서를 확인하고 기존 lockfile에 고정한다. 별도 승인 문서나 도구 계층은
실제 요구가 있을 때만 추가한다. 전체 공식 suite 재검증은 표준 구현·지원 profile을
변경할 때 수행하고, 일반 변경은 영향받는 shape·query·adapter를 검사한다.

기존 자료는 build 후 다음처럼 조회할 수 있다. `identity`를 작업 대상 ID로 바꾼다.

```sh
src/hswm/effect-runtime/bin/hswm-workspace status
src/hswm/effect-runtime/bin/hswm-workspace show identity
src/hswm/effect-runtime/bin/hswm-workspace query identity basic-identity
src/hswm/effect-runtime/bin/hswm-workspace validate identity
```

출처 비교가 필요하면 `bindings identity`, 설치 문제를 조사할 때는 `doctor`를 사용한다.
`validate`의 성공은 구조 검사 결과이며 출처 일치 여부는 `bindingSummary`로 따로 확인한다.
과거 snapshot의 hash와 현재 파일이 다르면 원래 Git revision을 확인한다. 과거 hash를
현재 값으로 덮어쓰지 않는다. CLI 상세는 [KG 탐색 안내](HSWM_KG_WORKSPACE_2026-09-22.md)에 있다.

긴 연구 문서를 찾을 때는 QMD, 저장된 모델 응답 두 군을 비교할 때는 Inspect AI를 선택해서
사용할 수 있다. 코드 심볼 탐색은 Serena, 관계 설명의 최적화 비교는 GEPA를 사용할 수 있다.
설치·검색·평가 명령은 [AI 연구 도구 안내](HSWM_AI_NATIVE_TOOLS.md)에 있다.

## 변경에 맞는 검사와 기록

아래에서 해당하는 검사만 고른다. schema나 공통 실행 경로를 바꾸면 관련 회귀 범위까지
넓히고, 최종 CI 요구사항은 [.github/workflows](../../.github/workflows/)를 따른다.

| 변경 | 확인 방법 |
| --- | --- |
| 설명·작업 규칙 | diff와 로컬 링크 확인. 수식을 바꿨다면 portable math compiler 실행. |
| ontology 데이터·shape·query | 해당 `hswm-workspace validate/query`; 공통 처리 변경이면 `npm --prefix src/hswm/effect-runtime run test:ontology`. |
| TypeScript/Effect | `npm --prefix src/hswm/effect-runtime run check`, 관련 Vitest, 실행 CLI를 바꿨다면 build. |
| Python | 준비된 `src/hswm/development/bin/hswm-python core pytest -q tests/<관련 파일>.py`; graph 의존 검사는 `core` 대신 `graph`. |
| 모델·학습 실험 | 해당 연구 protocol의 대조군·평가 데이터·비용·재현 조건과 성공/실패 기준. |

일반 변경은 commit과 검사 결과 설명으로 기록한다. 연구 결과를 공개할 때는 재현에 필요한
설정·출처·관측·실패·한계를 기존 형식의 새 snapshot/receipt로 남긴다. 구조 검사 통과와
실제 LLM 성능·인과 효과를 구별한다. 기존 실패 결과와 CR/FCL의 미해결 상태는 유지한다.

`hswm-dev hswm plan/run/status/feedback`은 적응형 검사 선택을 사용하거나 연구할 때 선택한다.
이를 거치지 않은 직접 npm/uv 실행도 정상 개발 경로다. 사용했다면 `.hswm-local/`에 기록하고
에이전트 판단은 `agent(<tool>):...`로 사용자 피드백과 구분한다. 통과만으로 유용성 피드백을
자동 생성하지 않는다. 상세 명령은 [기존 개발 도구 안내](HSWM_DEVELOPMENT_WORKFLOW_2026-09-09.md)에 있다.
그 문서의 도구 사용 예시는 일상 작업의 필수 순서가 아니다.

## 해당 연구를 할 때 찾아볼 자료

전체를 차례로 읽는 목록이 아니다. 바꾸려는 개념이나 주장에 해당하는 원문만 확인한다.
각 문서의 연결된 KG·Lean·실험 근거는 그 내용을 검증하거나 수정할 때 함께 읽는다.

| 작업 | 출발점 |
| --- | --- |
| 정체성·아키텍처 | [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md), [네 가지 정체성](../canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md), [상태·국소 연산자](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md) |
| 아키텍처·독창성·실험 비교 | [Hyperon 직접 선행 조사](../research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md); 정확한 component·버전·구현 성숙도로 비교하며 backend 채택과 구별 |
| 프랙탈·다중 규모 합성 | [과학적 연결과 FCL-1..8](../research/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md) |
| 층간 매핑·뇌 모델링·agent의 바깥 역할 | [M = Map 사용자 방향](../canon/USER_PRIMARY_HSWM_CROSS_LAYER_MAP_2026-09-27.md), [매핑의 충분성과 후속 실험](../research/HSWM_CROSS_LAYER_MAP_RESEARCH_2026-09-27.md), [문헌·기존 코드·공학 연결 설계](../research/HSWM_CROSS_LAYER_MAP_ENGINEERING_2026-09-27.md) |
| 층간 매핑 실행·RDF 조회 | [Cross-layer Map v1 실행 안내](../../_research/cross_layer_map_v1/README.md): 유한 매핑, 명시적 관측 바인딩, 의미 revision, SPARQL/SHACL |
| 하이퍼그래프의 선택 이유·최소 비용 | [사용자 가설](../canon/USER_PRIMARY_HSWM_MINIMUM_COST_HYPERGRAPH_2026-09-27.md), [주장 판정·최소 예측 상태·비용 비교·표준 그래프 매핑](../research/HSWM_MINIMUM_COST_HYPERGRAPH_HYPOTHESIS_2026-09-27.md) |
| 의미 상태의 표현 비교·MapSpec RDF 조회 | [실행 안내](../../_research/semantic_map_engineering_v1/README.md): 세 표현의 정확한 왕복, 직렬화 바이트, 명시적인 MapSpec view, 기존 revision 루프 재사용 |
| 직관·문헌·구현의 연결 KG | [표준 그래프 종합](../research/HSWM_INTUITION_STANDARD_GRAPH_SYNTHESIS_2026-09-27.md): 사용자 가설, 문헌의 제한 조건, 구현 계약과 미해결 질문의 source-bound graph |
| CHU의 넓은 범위와 LLM 전용 HSWM | [사용자 범위 정의](../canon/USER_PRIMARY_CHU_HSWM_SOFTWARE_SCOPE_2026-09-27.md), [계산 구조·원전·실행 계약](../research/CHU_HSWM_COMPUTATIONAL_ARCHITECTURE_2026-09-27.md): 세계 모델링 능력의 겹침과 조회·검증 가능한 KG |
| 현재 연구 공백·다음 실행 | [9월 27일 자기점검](../research/HSWM_RESEARCH_SELF_REVIEW_2026-09-27.md): 실제 LLM 음성 결과, 아직 연결되지 않은 적용, W1 바인딩 교환의 채점 민감도 |
| 진단의 적대적 검토·해결 설계 | [9월 27일 해결안](../research/HSWM_ADVERSARIAL_REMEDIATION_PLAN_2026-09-27.md): 복사 지름길·관측 부족·수정 no-op의 구분, 실행–관측–수정–재읽기 계약과 기존 W1–W5 연결 |
| 추가 도구·논문 본문 확인 | [9월 27일 도구·논문 검토](../research/HSWM_ADDITIONAL_TOOLS_AND_PAPER_REVIEW_2026-09-27.md): 생성 과제·문법 제한·PDF 근거 위치, 검색과 세계 모델 대조군의 전제·소스 버전·적용 순서 |
| 연구 경로 변경·실패 해석 | [적응 연구 전략](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md) |
| Semantic Weight·표현·이론 채택 | [이론 기반](../research/HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md), [정의와 하이퍼그래프](../research/HSWM_SEMANTIC_WEIGHT_DEFINITION_AND_HYPERGRAPH_2026-09-14.md) |
| 실현 가능성·성능 증명 | [구성적 증명](../research/HSWM_SEMANTIC_WEIGHT_CONSTRUCTIVE_PROOF_2026-09-14.md), [문헌에서 성능으로](../research/HSWM_LITERATURE_TO_PERFORMANCE_PROOF_2026-09-14.md), [bounded 확장](../research/HSWM_SEMANTIC_FRONTIER_PROOFS_2026-09-14.md) |
| LLM 의미 실행·그래프 수정 | [의미 엔진 연구](../research/HSWM_LLM_SEMANTIC_ENGINE_RESEARCH_2026-09-14.md), [구현과 근거](../research/HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.md), [사용자 원문](../canon/sources/USER_PRIMARY_HSWM_SEMANTIC_GRAPH_ENGINE_2026-09-14.txt) |
| 표준 adapter·conformance 변경 | [기존 표준 profile과 근거](HSWM_STANDARD_TOOLCHAIN_POLICY_2026-09-02.md), [graph 구현 경계](HSWM_FULL_STACK_GRAPH_ENGINEERING_2026-09-02.md) |

이전 문서의 필독 순서·매 작업 기록 의무는 위의 작업별 선택 원칙으로 대체한다.
특정 실험의 통계적·인과적 판정 조건과 실제 runtime schema 제약은 해당 작업에 계속 적용된다.
