# HSWM 실사용 적응 하이퍼그래프 런타임

상태: `EXPERIMENTAL_LOCAL_ADAPTATION / SCIENTIFICALLY_UNJUDGED`.
개념 기준: [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md),
[관계 동역학 계획](HSWM_WOLFRAM_RELATIONAL_CAPABILITY_RESEARCH_PLAN_2026-09-06.md),
[프랙탈 연결](HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md).

## 구현 전에 고정한 변화

한 schema 아래 cell·context field·조건·역할 있는 n-ary relation·trajectory·outcome을
서로 참조하는 atom으로 표현한다. 각 atom에는 하나의 owner와 immutable revision이 있다.
관계의 적용 조건, 입력 read-set, 참여 cell들과 학습 계수가 같은 실행 관계를 구성한다.
local rewrite는 읽은 revision을 소비 참조로 남기고 새 revision을 원자 저장한다.

학습은 실제 작업의 성공·실패로 관계별 문맥 feature와 pair interaction의 logistic 계수를
갱신한다. 소요 시간은 선택 비용으로 학습한다. 충분한 혼합 결과가 있으면 기존 유한 AST
합성기로 조건부 관계를 제안해 국소 분화를 시도한다. 재귀 호출에서 부모는 합성 관계의
관측된 결과를, 자식은 자기 관계의 결과를 학습한다. 이것은 관측 기반 적응이며 개별
참여자의 인과적 기여를 식별했다는 뜻이 아니다.

CLI 실행은 학습 가중치로 허용된 관계를 선택하고 실제 command/LLM cell을 호출한다.
LLM의 정상 응답 자체를 성공으로 보상하지 않는다. 선언된 작업 checker나 명시적 후속
feedback이 필요하다. 작업 실행 전 trajectory를 저장하고, 결과와 학습 revision을 결속한다.
결과가 불명확하거나 프로세스가 중단되면 같은 episode를 자동 재실행하지 않는다.

이것은 Wolfram의 국소 hypergraph updating과 사건 의존성에서 가져온 공학적 연결이다.
학습 알고리즘·문맥·과제 성공 정의는 HSWM의 별도 가설이며 물리학에서 도출되지 않는다.
임의 순서의 동치성, causal invariance, 의식·인지 합성의 실현을 주장하지 않는다.
[Wolfram 원문](https://www.wolframphysics.org/technical-introduction/the-updating-process-in-our-models/updating-events-and-causal-dependence/).

새 경로의 schema는 로컬 prototype 범위다. 기존 Atom-v2 admission의 qualification이나
G0/G1/FCL 판정을 자동 승계하지 않는다. P1의 기존 RED를 고치지 않으며 새 경로의 효능도
미판정이다. 사용자 요청대로 실행에 필요한 타입·권한·복원과 핵심 회귀 검사만 유지한다.

## 바로 실행

저장소 루트의 일반 Linux checkout에서 다음을 실행한다. 이미 설치된 `uv`와 기존 lockfile을
사용하며 서버·MCP·별도 그래프 DB 설치는 필요하지 않다.

```bash
hswm_program=_research/causal_composition/examples/adaptive_developer.v1.json
uv run --locked hswm-live --program "$hswm_program" run \
  --context '{"area":"cells","stage":"development"}' \
  --task '현재 적응 런타임의 개발 검사를 실행한다'
uv run --locked hswm-live --program "$hswm_program" status
uv run --locked hswm-live --program "$hswm_program" plan \
  --cell checks --context '{"area":"cells","stage":"development"}'
```

예제는 `developer → [syntax, checks]`, `checks → [선택된 검사 cell]`을 실행한다.
하나의 관계에 source와 순서 있는 복수 member가 참여하며, router 자체가 다시 member가
될 수 있다. Python 문법 검사 뒤 학습 점수로 focused/compatibility pytest 묶음을 선택한다.
이는 개발 검사 성공률·소요 시간에 대한 관측이지 코드 품질 전체의 점수가 아니다.
더 넓은 회귀가 필수인 작업은 그 검사만 허용하는 manifest/allowlist를 사용한다.

기본 상태 파일은 workspace 아래 `.hswm-local/runtime.sqlite3`이며 Git에서 제외된다.
episode 입력·출력·문맥·결과, 관계 계수와 revision, rewrite 사건을 저장한다.
다음 호출은 같은 DB의 최신 관계를 읽는다. `--state`로 다른 DB를 지정할 수 있으며,
manifest를 수정하면 새 `graph_id` 또는 별도 DB를 사용한다. 같은 graph의 manifest hash
불일치는 거부한다. workspace의 전체 파일 내용을 봉인하는 기능은 포함하지 않는다.

`run`의 `--episode`를 생략하면 새 ID를 만든다. 동일 ID·동일 입력은 저장된 결과를
반환하며 명령이나 학습을 반복하지 않는다. 다른 입력에 같은 ID를 쓰면 거부한다.
`--frozen`은 실행·결과를 기록하되 관계 학습을 멈춘다. `plan`은 선택만 계산하고,
`--route`는 현재 허용되는 root 관계를 명시 선택한다. `--allow`는 허용할 cell ID마다
반복하며 root와 중간 router도 포함한다.

`graph`는 role reference를 포함한 현재 atom과 과거 rewrite의 consumed/produced revision을
JSON으로 출력한다. 물리 저장은 SQLite이고, 하이퍼그래프 의미는 복수 참여자·역할·참조를
가진 관계 atom이 담당한다. 기존 문헌 온톨로지 KG와는 별도인 실행 상태다.

## 학습·조건 생성·복원

1. 허용된 관계 중 guard가 현재 문맥에서 참인 관계를 찾는다.
2. 관계별 logistic 계수로 문맥의 성공 성향을 계산하고 관측 평균 비용과 작은 탐색 보너스를
   반영해 선택한다. 초기 계수는 0이며 첫 선택에는 사전 비용과 UID tie-break가 작용한다.
3. 실제 명령 또는 typed LLM port를 호출한다. 명시한 checker 결과가 있으면 새로운 outcome과
   관계 revision을 같은 transaction에 저장한다. 부모와 자식 router는 각각 자신의 관측을
   갱신한다. 부모 결과가 개별 자식의 인과적 기여라는 가정은 하지 않는다.
4. 서로 다른 공개 문맥이 최소 4개이고 성공·실패가 섞이면 유한 조건식 문법에서 일관된
   비상수 guard를 합성한다. base 관계당 최대 한 개의 국소 분화 관계를 만들며 추가 field를
   read-set에 연결할 수 있다. 새 관계는 같은 member와 초기 계수로 시작해 이후 실행에서
   선택·학습할 수 있다. 후보가 실제 효능 검증을 통과했다는 뜻은 아니다.

조건 atom의 `PROPOSED_NOT_ADMITTED`는 기존 canonical admission에 대한 상태다.
이 명령으로 명시적으로 시작한 local prototype에서는 그 후보를 실험적 관계로 사용할 수
있다. 후보의 공개 결과 provenance와 parent relation을 보존하며, 새로운 명령이나 endpoint를
합성하거나 manifest의 실행 권한을 확대하지 않는다.

각 모델은 최대 64 feature와 64 문맥, 관계별 최근 64개 사례를 사용한다. 한도를 넘으면
결과를 보존하고 해당 가중치 갱신을 `DEFERRED`로 기록한다. 호출은 기본 60초·leaf 16회,
재귀 깊이 최대 8이며 순환 호출을 중단한다. 무한 지속 학습·장기 망각·자유로운 구조 재조직은
후속 구현 범위다. 초기 값·feature 문법·탐색 계수는 아직 연구자가 정한 부분이다.

`restore --relation RELATION_ID --revision N`은 과거 관계 내용을 새로운 revision으로 복원한다.
이는 그 관계의 복원이다. 생성된 자식 관계나 외부 명령의 파일 변경을 되돌리지는 않는다.
단일 로컬 writer lock과 DB CAS를 함께 사용하며, 중단되어 결과가 불명확한 episode는 다른
실행을 막고 명시적인 확인을 기다린다. 현재 실행 중에는 feedback/restore도 거부한다.

## 작업 cell 연결

program은 `schema_version`, `graph_id`, `root`, `context_domain`, `cells`, `relations`를 가진다.
cell은 `cell_id`, `kind`, `owner`, `input_type`, `output_type`을 선언한다.
관계는 `uid`, `source`, 순서 있는 `members`, `reads`, 초 단위 `cost_hint`, 선택적 `guard`다.
문맥은 최대 8개 field의 유한 JSON scalar enum이며 입력·출력 port type은 합성 경계에서 맞아야 한다.

- `command`: literal `argv`를 실행한다. task·prompt·선택된 context·episode/call ID가 JSON stdin으로
  전달된다. 앞선 member 출력은 `previous_output`에 들어간다. 기본 반환은 실행 상태이고 보상이
  아니다. 검사 명령에만 `"outcome":"exit_code"`를 선언하여 exit 0/비0을 관측 성공/실패로 사용한다.
- `llm`: 기존 typed `CellPort` 또는 OpenAI-compatible endpoint의 `base_url`, `model`, 선택적
  `api_key_env`, `max_tokens`를 사용한다. 키는 환경변수로 읽으며 manifest에 저장하지 않는다.
  정상 응답은 작업 성공을 뜻하지 않는다. 다음 member가 출력을 검사하거나 사용자가 feedback을
  제공한다. 이번 구현의 LLM 경로는 injected port로 검증했고 실제 유료 모델 호출은 하지 않았다.
- `router`: 같은 선택·실행 절차로 관계를 호출한다. 이 재귀 실행은 구조적 합성이며 상위 인지나
  FCL 전체의 실현을 증명하지 않는다.

명시적 checker가 없거나 timeout/중단으로 결과가 불명확할 때, 사용자가 실제 결과를 확인한 후
`feedback --episode EPISODE_ID --success true --source '확인 근거'`를 사용할 수 있다.
`false`도 가능하다. 이 피드백은 root 관계에만 적용하며 하위 member의 성공을 만들어내지 않는다.
같은 피드백의 재전송은 다시 학습하지 않는다. 이미 checker 결과가 있는 episode를 덮어쓰지 않는다.

`run` exit code는 성공적 실행 0, 실패한 실행 1, 입력/상태 오류 2, 결과 불명확 3,
실행 보류 4, 진행 중인 과거 episode 조회 5다. 코드 0도 checker/feedback이 없으면 보상은 없다.
JSON에는 제한된 출력, 출력 digest, 선택 revision과 결과가 포함된다.

## 구현과 가벼운 확인

- 실행 관계·재귀·outcome 결속: `src/hswm/cells/adaptive_runtime.py`
- 문맥 계수와 조건 후보 생성: `src/hswm/cells/adaptive_learning.py`
- immutable atom·CAS rewrite: `src/hswm/cells/adaptive_store.py`
- 실제 command/typed LLM 호출: `src/hswm/cells/adaptive_executor.py`
- CLI: `src/hswm/infrastructure/adaptive_cli.py`

`tests/test_adaptive_*.py` 중 store/learning/executor/runtime/cli/lifecycle 검사는 실제 subprocess
결과에 따른 선택 변화, 재시작 후 유지, 동일 episode 비재실행, 새 관계의 추가 field 전달,
순서 있는 재귀 합성, frozen/restore, 명시적 feedback, timeout과 동시 실행 경계를 확인한다.
공개 authored 예시에서 확인하는 구현 회귀이며 새로운 과제에서의 성능 우위 측정은 아니다.

2026-09-07 개발 확인에서는 이 CLI가 문법 검사와 새 회귀 28개를 실제 실행해 통과했다.
상위 `development-cycle`과 하위 `focused` 관계는 관측 수 0→1, revision 1→2가 되었고,
별도 CLI 프로세스의 `plan`이 갱신된 모델을 읽었다. 기존 conditional capability/probe/task CLI
회귀 45개도 통과했다. 이 개발 기록은 Git 제외 경로
`.hswm-local/development-20260907.sqlite3`에 있다. 해당 이력을 이어 쓰려면 위 명령에
`--state .hswm-local/development-20260907.sqlite3`를 subcommand 앞에 추가한다.
