# HSWM 최적화 6원칙과 7군단장의 연결

2026-10-07 · 사용자 발화는 `USER_PRIMARY` 귀속, 여섯 명칭·작업환경 구체화·역사 대응은
`SECONDARY_AI`. 사용자의 적용 요청에 따라 HSWM의 작업별 규칙으로 구현한다.

## 원문과 적용 범위

- [동일한 크기의 CHU와 웨이트 최적화](sources/USER_PRIMARY_HSWM_SAME_SIZE_WEIGHT_OPTIMIZATION_2026-10-07.txt)
- [규칙 활성화·CLI·분할·연결·병합 발화 전체](sources/USER_PRIMARY_HSWM_GRAPH_OPTIMIZATION_RULES_2026-10-07.txt)
- [HSWM 적용과 인터넷 검색·적대적 검증 제외 요청](sources/USER_PRIMARY_HSWM_OPTIMIZATION_RULES_APPLY_2026-10-07.txt)

원문 문자열을 마지막 LF가 있는 UTF-8로 보존한다. 기록일과 실제 발화 시각을 구분한다.
사용자가 직접 여섯 번호나 이름을 정한 것으로 소급하지 않는다. 독립적으로 점검할 항목으로
나눈 여섯 원칙은 아래와 같다. 원칙의 실행 본문은 [OPTIMIZATION.md](../agent-rules/OPTIMIZATION.md)의
개별 섹션에 있고, [작업 라우팅 그래프](../agent-rules/routes.json)가 필요한 섹션만 선택한다.

| ID | 원칙 | 실제 활성화 |
|---|---|---|
| R1 | 작업 조건부 규칙 활성화 | graph·instructions → hswm-rule-context |
| R2 | CLI 중심 실행 | cli → hswm-rule-cli |
| R3 | CLI 사용법의 그래프 결속 | cli → hswm-rule-cli |
| R4 | 컨텍스트에 맞는 노드 분할 | graph·instructions → hswm-rule-context |
| R5 | 선택적·느슨한 연결 | graph·instructions → hswm-rule-context |
| R6 | 의미 기여에 따른 재구성 | graph·instructions → hswm-rule-context |

공유 라우터의 기존 상속도 유지한다. 예를 들어 instructions는 이미 cli를 포함하므로
결과적으로 여섯 규칙을 선택한다. 일반 base·문서 편집·KG 조회는 이 여섯 규칙을 자동으로
전부 읽지 않는다. 단순 조회와 그래프 설계의 효과를 구분해 task를 선택한다.

`AGENTS.md`에 여섯 본문을 추가하지 않는다. 기존 CLI Source는 README 전체에서
[CLI 진입 섹션](../agent-rules/CLI.md)으로 바꾸고, 선택한 명령에서 실제 사용 섹션과
소유한 runbook으로 내려가게 한다. 선택된 본문은 끝까지 읽는다. 이것은 지침 선택 경로의
구현이며, LLM이 웨이트를 스스로 학습해 규칙을 선택한다는 관측은 아니다.

## 동일 규모와 재구성

사용자의 전체 전제는 동일한 지능과 같은 크기의 CHU에서 웨이트를 바꾸며 극도로
최적화한다는 것이다. ‘크기’가 물리 자원·상태 용량·노드 수 중 무엇을 뜻하는지는 아직
구체적으로 정해지지 않았다. 이번 표현 노드의 분할·병합을 곧바로 CHU 규모 증감으로
간주하지 않는다. 비교 시 동일성·규모·문맥 예산을 무엇으로 유지했는지 선언해야 한다.

분할이 정보 손실을 만들면 개선이 아니며, 불필요한 분할의 병합은 의미를 보존하면서
읽기 비용을 줄일 수 있다. 의미를 바꾸려는 웨이트/연결 수정과 표현만 정리하는 변경을
구분한다. 기존 원문·권위·예외·책임·계보와 [CHU 존재·HSWM 구조 구분](USER_PRIMARY_CHU_BEING_HSWM_STRUCTURE_2026-10-07.md)을 유지한다.

## 비행기맨 7군단장과의 역사 대응

기존 [7군단장 HSWM 초안 §5](../research/HARNESS_7COMMANDER_HSWM_SUBSTRATE_2026-07-21.md)의
2026-07-23 기록은 네 항목을 **사용자 주장**, 나머지 셋을 **AI 제안**으로 구분한다.
이 원칙들과 연결했다는 이유로 과거 초안의 상태나 측정 결과를 현재 정전·효능으로 바꾸지 않는다.
KG의 관련 ADR·사용자 주장 항목에는 지원되는 본문이 없어 이 로컬 출처까지 내려가 확인했다.

| 군단장 | 당시 동사·지위 | 이번 대응 — AI 해석 |
|---|---|---|
| 롱기누스 | 연결 · AI 제안 | R3·R5: 안정된 명령/자료 ID, 사용법과 중간 참조의 결속 |
| 재배맨 | 계획·LLM 슬롯 배치 · 사용자 주장 | R1·R4·R5: 작업별 활성화와 조합 가능한 문맥 단위 배치 |
| 오캄 | 정리·웨이트 조정 · 사용자 주장 | R4·R6: 과한 덩어리·분할을 재구성하고 이력을 보존하는 정리 |
| 유레카 | 발견·창조·새 HSWM 생성 · 사용자 주장 | R4·R5·R6: 조합의 의미가 생기는 단위·중간 구조의 제안 |
| 하네스=하데스 | 실현 · AI 제안 | R2·R3: 추상 작업을 사용법이 연결된 실행 인터페이스로 실현 |
| 프로메테우스 | 획득·인터넷 캐싱 · 사용자 주장 | 이번 적용에서 인터넷 검색 역할 제외 |
| 나생문 | 검증·적대 검증 · AI 제안 | 이번 적용에서 적대적 검증 역할 제외 |

이는 고정된 일곱 단계나 일곱 에이전트 실행 파이프라인을 복원하지 않는다. 역사적 역할을
현재 규칙과 비교하는 대응이다. 제외는 이번 적용 범위이며 과거 기록의 삭제나 일반적인
출처·타입·구조·회귀 검사의 폐지가 아니다. 이번에는 인터넷 검색과 적대적 검증을 실행하지 않는다.

## 표준 그래프와 현재 도구

[원문 결속 번들](../../ontology/identity/hswm_core/HSWM_OPTIMIZATION_RULES_ONTOLOGY.v1.json)은
원문·규칙 섹션·활성화 그룹·CLI/사용법·역사적 역할·제외 범위를 구분한다.
기존 RDF v2·PROV-O·SPARQL·SHACL 도구를 사용한다. 로컬 relation 어휘의 의미는
[관계 계약](artifacts/hswm_optimization_rules_2026-10-07/graph-contract.v1.json)에 둔다.

```sh
src/hswm/effect-runtime/bin/hswm-workspace show optimization-rules
src/hswm/effect-runtime/bin/hswm-workspace query optimization-rules rules
src/hswm/effect-runtime/bin/hswm-workspace query optimization-rules activation
src/hswm/effect-runtime/bin/hswm-workspace query optimization-rules cli
src/hswm/effect-runtime/bin/hswm-workspace query optimization-rules legion
src/hswm/effect-runtime/bin/hswm-workspace validate optimization-rules
```

공유 instruction router에서 graph·cli·instructions·base를 직접 선택해 활성/비활성
섹션과 읽기 완료를 확인하고, Codex·Claude·Grok 진입도 비교한다. 선택된 문자 수는
문서 읽기량의 관측값이며 토큰 수나 지능 향상의 측정값이 아니다. [라우팅 비교](artifacts/hswm_optimization_rules_2026-10-07/routing-observation.v1.json)에
적용 전후 범위를 기록한다. 이 기록은 실행 권한이나 learned dispatch를 주장하지 않는다.
