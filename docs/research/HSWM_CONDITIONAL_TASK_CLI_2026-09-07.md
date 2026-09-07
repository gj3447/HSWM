# HSWM 조건부 과제 CLI와 실행 배치

상태: `SECONDARY_AI_IMPLEMENTATION / BOUNDED_PROPOSALS / NO_EFFICACY_INFERENCE`.
[적대적 검토](HSWM_ADVERSARIAL_REVIEW_AND_THEORY_ADOPTION_2026-09-07.md)의 A2~A4를
보완하고, 공개된 과제 조건에서 후보 예측이 갈리는 다음 확인 대상을 제안하는 경로를 연결했다.

## 1. 정본 역할과 이번 변화

[헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 HSWM은 하나의 token-native
LLM-function macro-neural network이며 evolving hypergraph가 실행 조건·월드모델·계속학습의
역할을 함께 한다. FCL-1..8, schema-relative single owner, typed reference,
outcome-bound revision과 기존 실패 판정을 유지한다.

이번 변화는 그 정체성의 축소나 새 canonical schema 도입이 아니다. 현재의 relation·disposition
**후보 projection**에 탐색 재개, 관측별 provenance, 판별 과제 제안과 CLI 입출력을 추가한다.
후보는 아직 canonical atom이 아니다. 실제 admission은 각 atom의 schema·owner·typed refs,
독립 outcome/credit·현재 Inv/Permit에 결속되어야 한다. JSON 저장과 후보 재합성은 이를 대신하지 않는다.

사용자가 과제를 준다는 느낌은 다음과 같다. 예를 들어 코드 수정 과제라면, 현재 관계가
어떤 파일과 검사를 먼저 읽을지 조건화하고, 허용된 수정·검사의 결과가 후보 관계를 바꾸며,
검증된 관계가 다음 유사 과제의 탐색과 행동을 바꾸는 방식이다. 이는 목표 사용 방식이다.
이번 CLI는 그 전체 코딩 agent가 아니라, 아래 작은 조건부 과제 경로를 실행한다.

## 2. 실행 방법

저장소 루트의 일반 Linux checkout에서 실행한다. 추가 DB, 서비스, 인증정보 또는 모델 호출이
필요하지 않으며 기존 `uv.lock`의 의존성을 사용한다.

```sh
uv run --locked hswm-task --help
uv run --locked hswm-task demo _research/causal_composition/examples/conditional_task_demo.v1.json
```

동일한 진입점의 module 실행도 지원한다.

```sh
uv run --locked python -m hswm.infrastructure.conditional_task_cli demo _research/causal_composition/examples/conditional_task_demo.v1.json --output /tmp/hswm-task-demo.json
```

[입력 예제](../../_research/causal_composition/examples/conditional_task_demo.v1.json)는 사람이 작성한
공개 episode다. CLI는 예제 전체를 볼 수 있으므로 evaluator 격리나 새 환경 실행이 아니다.
후속 결과는 후보 생성기·probe 선택기의 입력에는 전달되지 않는다.
예제의 `outcome_projection`은 Boolean 성공을 relation truth target으로 읽는 task mapping과
그 출처를 명시한다. `preview_query`는 수정·복원 전후에 쓰는 동일한 별도 query의 digest이며,
선택된 probe 조건과 반드시 같지는 않다.
기본 출력은 JSON이며 `--output`으로 저장한다. 입력 파일 대신 `-`를 주면 stdin을 읽는다. 입력은 최대 1 MiB,
중복 JSON key·비유한 수·잘못된 구조는 `REJECTED`와 exit code 2로 반환한다.

| 명령 | JSON 입력 | 결과 |
|---|---|---|
| `synthesize INPUT` | `domain`, `examples`; 선택적으로 `parent`, `search_budget`, `candidate_limit`, `resume_cursor` | 공개 예시에 일관된 관계 후보와 탐색 상태 |
| `preview INPUT` | `domain`, `relation`, `observations`, `action`, `checks` | 선택된 단일 relation의 TRUE guard에 따른 행동·관찰·보류 제안 |
| `probe INPUT` | `domain`, `candidates`, `contexts`, `allowed_reads`, `allowed_probe_ids`, `budget` | 제공된 과제 조건 중 후보의 relation prediction이 갈리는 대상 |
| `demo INPUT` | 예제의 `hswm-conditional-demo/v1` 구조 | 초기 후보 → 판별 대상 → 후속 공개 결과 → 수정 후보 → preview 변화 재생 |

`domain`은 `[{"role":"part","field":"ready","values":[0,1]}]`, observation values는
`[{"role":"part","field":"ready","value":1}]`, 읽기 참조는 `[["part","ready"]]`다.
`examples`는 `{values,outcome,source}` 행이다. `preview`의 relation은 예제의
`initial_relation`, observations는 `query`, checks는 `checks`와 같은 구조를 쓴다.
`probe`의 candidates는 `{relation_ast,source}`, contexts는 `{id,values,source,cost}` 행이다.
각 명령은 선언하지 않은 필드를 거부한다. CLI preview는 단일 조건을 위한 얇은 변환이며,
Python preview API의 최대 8개 rule 표면을 모두 직렬화한 계약 parser는 아니다.

후보 8개에서 중단됐을 때에는 같은 요청과 직전 결과를 사용해 이어서 탐색할 수 있다.

```sh
uv run --locked hswm-task synthesize /tmp/request.json --output /tmp/page1.json
uv run --locked hswm-task synthesize /tmp/request.json --resume-from /tmp/page1.json --output /tmp/page2.json
```

`resume_cursor`는 domain·history·parent·grammar와 offset에 결속된 공개 무결성 값이다.
서명·인증이나 검토 이력의 증명은 아니다. 예시가 바뀌면 새 탐색을 시작한다. 반환된 페이지는
현재 페이지의 후보만 포함하며, 과거 페이지 후보가 자동으로 admission되는 일은 없다.
`search_complete`는 공간 끝에 도달했다는 뜻이며, caller가 전달한 cursor 이전 페이지를
실제로 검토했다는 증명은 아니다.

## 3. 실제 적용한 보완과 관측

- A2: `CANDIDATE_LIMIT`, `SEARCH_BUDGET`, `SPACE_EXHAUSTED`, `CONFLICTING_EVIDENCE`를
  구분하고 재개 cursor·offset·공간 크기를 공개한다. 조합은 lazy 순회한다. 선언 domain은
  최대 64개 field·128개 equality leaf, 이력은 최대 512개 예시, 호출당 후보 평가는 최대 4096개다.
  `examined`는 현재 페이지의 후보 평가 수이며 `search_offset`·`enumeration_progress`는
  앞선 열거 위치다. 재개시 prefix 순회 비용도 있으므로 `examined`만 총비용으로 쓰면 안 된다.
- A3: 정적 `preview_uid`를 유지하면서 `step_input_digest`, 관측 record digest,
  evaluated/selected rule provenance를 추가했다. 현재 시간·scope·revision·권한·budget도
  결속한다. 입력 source는 여전히 caller assertion이며 인증된 환경 증거가 아니다.
- A4: malformed JSON, 비유한 수, 잘못된 rule/observation을 `Reject`로 정규화했다.
- A1: 완전 관측에서 같은 FALSE였던 후보 8개는 부분 관측에서 서로 다르다. 따라서 단순
  진리표 기반 중복 제거를 넣지 않았다. 새로운 의미 동등성 증명을 주장하지 않는다.
- probe: 최대 8개 후보·64개 **이미 공개된 완전 과제 조건**의 relation prediction을 비교한다.
  분리도와 선언 비용으로 선택하며 전체 domain 읽기 권한·probe allowlist·budget을 요구한다.
  선택 전에 후보별 예측과 `proposal_digest`를 만든다. 구별되는 허용 조건이 없으면 보류한다.
  미래 outcome을 만들거나 실제 intervention/causal credit을 확정하지 않는다. 관계의 TRUE를
  과제 성공으로 읽는 mapping도 과제별로 명시해야 한다.

예제에서는 초기 2개 후보 `ready`와 `ready AND clean`이 `ready=1, clean=0`에서 갈린다.
선택된 대상의 후속 공개 실패를 추가하면 후보가 1개로 줄고, 같은 query의 읽기 field 수가
1→2, 제안은 `ACTION_PROPOSAL`→`WITHHOLD`가 된다. 이전 relation을 복원하면 이전
preview가 돌아온다. 이 예제의 첫 후보 선택은 재생용이며 실제 admission 정책이 아니다.

이는 [인과 prior/식별 검토](HSWM_ADVERSARIAL_REVIEW_AND_THEORY_ADOPTION_2026-09-07.md)의
제한된 후보 판별 아이디어를 구현한 것이다. Causal ABA 전체, Narcissus의 LLM-guided search,
TheoryCoder-2의 추상화, GEPA·Nested Learning·Meta-TTL을 재현·채택 완료한 것이 아니다.
새 과제 효능과 강한 baseline 비교는 남아 있다. G0 미통과·G1 미평가·D-4 미완료도 유지한다.

## 4. MCP, graph DB, 서버와 CLI의 관계

| 구성 | 역할과 현재 상태 |
|---|---|
| CLI | 이번 `hswm-task`가 같은 Python proposal 함수를 로컬에서 호출한다. 출력 파일은 proposal record다. |
| HSWM backend 서버 | 여러 client의 장기 실행·동시성·세션이 필요할 때 같은 코드와 상태 writer를 서비스로 노출하는 배치 방식이다. 이번 CLI용 서버를 새로 띄우지는 않았다. |
| 실행 상태 저장 | 기존 [`store.py`](../../src/hswm/cells/store.py)는 SQLite cell event/state/outbox를 원자 저장하는 prototype writer다. 새 conditional CLI와의 durable admission 연결은 아직 없다. |
| 연구 KG | 기존 Neo4j/MCP의 논문·설계·증거 조회 projection이다. relation 후보의 참이나 실행 권한을 결정하지 않는다. |
| hypergraph 표현 | n-ary relation 자체를 식별 가능한 atom으로 두고 참가자와 role-bearing incidence를 연결하는 논리적 표현이다. 특정 DB 제품의 도입과 동일하지 않다. |
| MCP | 외부 과제 정보·도구를 제한된 capability로 연결하거나 HSWM의 bounded 조회/제안 표면을 노출할 수 있다. canonical write·Permit·credit/admission의 범용 우회 경로가 되어서는 안 된다. |

배치 방향은 CLI와 선택적인 서버 진입점이 같은 실행 코드를 사용하는 것이다. 연구 KG는
참조 정보를 공급하고, 과제 환경은 허용된 관측·행동과 결과를 제공하며, runtime writer는
검증된 event와 상태를 지속한다. 이 배치 요소들을 서로 독립적인 HSWM 인지기관으로 등치하지 않는다.

Neo4j는 property graph이므로 native hyperedge 대신 intermediate node로 n-ary 관계를
표현할 수 있다. HSWM에서는 이때 role·owner·version·provenance와 변환 손실을 보존해야 한다.
[Neo4j 공식 모델링 문서](https://neo4j.com/docs/getting-started/data-modeling/modeling-designs/).
MCP의 공식 transport에는 client가 시작하는 subprocess의 stdio와 Streamable HTTP가 있다.
따라서 로컬 MCP 연결에도 항상 원격 서버가 필요한 것은 아니다.
[MCP 2026-07-28 transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports).
이번 작업은 새 MCP SDK나 DB 제품을 설치하지 않았다.

## 5. 역사 기록과 검증

기존 감사 프로그램과 frontier v1 bundle은 수정 전 source hash에 결속된 역사 기록이다.
그 bytes를 새 구현에 맞춰 바꾸지 않았다. 수정 전 감사를 재실행하려면 `3b29e47` checkout을
사용한다. 현재 source를 대상으로 실행하면 원래의 hash guard가 의도대로 거부한다.

frontier v1은 새 snapshot manifest의 명시된 `6e2e49f` Git blobs로 검증한다.
기본 worktree 검증의 drift 거부는 유지하며, historical 검증을 live publication과 조합할 수 없다.
이 경로는 현재 구현의 KG 갱신을 주장하지 않는다.

```sh
uv run --locked python -m hswm.infrastructure.frontier_learning_projection --historical-snapshot
uv run --locked pytest -q tests/test_conditional_capability.py tests/test_conditional_probe.py tests/test_conditional_task_cli.py tests/test_hswm_cellular_runtime.py tests/test_frontier_learning_projection.py
```

위 검사 60개와 CLI entrypoint 실행, 역사 snapshot 검증이 통과했다. 소프트웨어 통합·공개
예제 재생이므로 새 연구 gate나 결과 장부 항목을 만들지 않는다.
