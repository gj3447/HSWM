# HSWM Jev context selection

2026-10-09 · `SECONDARY_AI_ENGINEERING_IMPLEMENTATION`

작업에 필요한 **관계 묶음**을 Jev가 제안하고, HSWM이 정확한 버전의 역할·문맥·근거·예외를
읽어 국소 LLM 입력으로 조립한다. 기존 canonical atom v2 저장소, `readLlmSemanticFrame`,
Effect 3.22.1, native RDF v2·SPARQL·SHACL·PROV-O 구현을 사용한다.
새 DB, 모델 설치, instruction router 교체는 없다.

현재 연결한 추론 어댑터는 기존 `jev-dgx`의 **Kotoba open-jev**이다. TypeSafe 공식 Jev
가중치나 Claude Code Typeahead mod를 실행한 것이 아니다. Typeahead는 적용 아이디어의
출처이며, 공식 API와 이 어댑터의 응답 형식을 섞지 않는다.

## Implemented path

1. 호출자가 작업, 작은 후보 목록, 필수 관계, byte 예산과 선택 기준을 명시한다.
2. 후보의 현재 관계 버전과 정확한 참여자 참조를 snapshot에 결속한다. Jev 입력에는
   작업·짧은 후보 설명·plan hash를 넣는다. 후보 설명은 호출자가 작성한 MAP이며 의미적
   충분성이 검증된 요약이라고 주장하지 않는다.
3. Jev의 응답을 요청 hash, 후보 전체, 확률 합, 선택값, confidence, margin에 대해 검사한다.
   `NONE`, `NEED_MORE`, 입력 한도 초과를 보존한다. 전송 실패를 `NONE`으로 바꾸지 않는다.
4. 선택된 후보의 모든 관계와 필수 관계를 함께 읽는다. 관계의 모든 비-supersedes 역할,
   source revision, 중복 참여와 순서, exceptionRefs를 보존한다. 필수·선택 관계가 겹치면
   같은 root를 한 번 읽되, 관계 내부의 참여 slot은 합치지 않는다.
5. 완전한 JSON 요청 payload가 예산 안에 있을 때만 한 번 LLM을 호출한다. 버전은 조립
   전후와 호출 전후에 대조한다. 과거 선택을 새 graph에 적용하거나 잘라서 맞추지 않는다.
6. 선택 → 조립 → 실행 trace → 호출자 관측을 content hash로 연결해 기존 immutable
   content store에 stage한다. canonical atom commit, W 변경, 독립 결과 검증은 수행하지 않는다.

후보는 1–8개, 후보당 root 1–8개, 필수 root 최대 8개다. 대규모 graph의 자율 탐색·후보
발견은 이번 범위가 아니다. 초기에 후보에 없는 정답을 Jev가 복구할 수 없으므로
`NEED_MORE` 뒤의 후보 확장/원문 선택은 다음 명시적 호출로 남는다.

prepare는 후보 본문을 `readContent`로 직접 읽지 않는다. 기존 durable snapshot 복구는
저장소의 무결성 확인을 위해 payload를 검증할 수 있다. 따라서 전체 disk I/O 감소나
전체 graph 크기에 독립적인 준비 비용을 주장하지 않는다.

## CLI usage

저장소 루트에서 build 후 실행한다. `hswm-context`는 JSON 한 개를 stdin에서 받고
JSON 한 개를 stdout에 쓴다. 옵션은 `--help`뿐이다.
선택 확률은 유한 소수를 허용하는 기존 general JSON 경계를 사용한다. canonical atom의
정수 전용 JSON 규약은 변경하지 않는다. stdin은 1 MiB이며 중복 키를 거부한다.

```sh
npm --prefix src/hswm/effect-runtime run build
src/hswm/effect-runtime/bin/hswm-context --help
src/hswm/effect-runtime/bin/hswm-context < prepare.json > plan.json
```

입력 공통 필드:

| 필드 | 의미 |
|---|---|
| `contract` | `hswm-semantic-context-cli/v1` |
| `action` | 아래 단계 중 하나 |
| `durableRoot` | 이미 존재하는 로컬 private POSIX store의 절대 경로; 공개 graph에 넣지 않음 |
| `journalLineageId` | 해당 저장소의 journal lineage |
| `schema` | 저장소에 결속된 완전한 canonical atom v2 schema JSON |

기존 소유자의 schema·journal·등록된 실행 경로를 사용한다. 비어 있는 디렉터리는 후보를
제공하지 못한다. store layer가 schema/journal 초기화를 수행할 수 있으므로 임의의 경로를
조회용으로 열지 않는다. 이 CLI는 seed/권한 생성 기능을 제공하지 않는다.

| action | 추가 입력 | 효과 |
|---|---|---|
| `prepare` | `spec` | snapshot 기반 plan, Jev 요청, 각 hash 반환. 모델 호출 없음 |
| `decide` | `spec`, `expectedPlanSha256` | `jev-dgx decide -`를 한 번 호출. 응답/selection 반환 |
| `assemble` | `spec`, `expectedPlanSha256`, `decision` | 정확한 원문 문맥 조립. 모델 호출 없음 |
| `execute` | assemble 입력 + `cell` | LLM 한 번 호출, immutable 요청·응답·trace stage |
| `observe` | `outcome: {traceContent, observed, source}` | 저장된 trace를 읽고 호출자 관측 stage |
| `project` | assemble 입력 + `assemblySourcePath` | 저장한 assemble JSON을 현재 조립 결과와 대조한 뒤 native KG bundle 반환 |

`decision`은 기존 Jev worker의 `jev-result/v1` 전체 응답이다. receipt의 hash는 worker가
실제로 쓰는 `JSON.stringify(정규화된 jev-request/v1)` UTF-8 bytes와 일치해야 한다.
외부 파일로 가져온 receipt는 `CALLER_SUPPLIED_RECEIPT_NOT_MODEL_ATTESTATION`이다.
형식 일치만으로 실제 모델이 실행됐다고 인증하지 않는다.

`cell`은 `{base_url, model, max_tokens, api_key_env?}`다. URL에 credential을 넣지 않는다.
Jev 모델 호출과 LLM 호출은 명시적 별도 단계이고 자동 재시도는 없다. 기존 원격 실행의
USL mapping·승인 범위·도달성 전제가 충족된 경로에서만 `decide`/원격 `execute`를 사용한다.
prepare/assemble/project가 그 전제를 대신하거나 원격 호출을 몰래 수행하지 않는다.

spec 예시 — UID는 실제 저장소의 값으로 바꾼다:

```json
{
  "contract": "hswm-semantic-context-spec/v1",
  "event": "문을 열 수 있는지 예외까지 확인해",
  "mandatoryRelationUids": ["relation:mandatory"],
  "candidates": [
    {"id": "door", "summary": "문 열기: 열쇠와 권한, 파손 예외", "relationUids": ["relation:door", "relation:companion"]},
    {"id": "calendar", "summary": "일정 날짜 계산", "relationUids": ["relation:calendar"]}
  ],
  "maximumContextBytes": 65536,
  "minimumConfidence": 0.5,
  "minimumMargin": 0.1
}
```

예시 threshold는 효능·calibration 결과가 아니다. local open-jev의 state 256 / 전체
512 tokenizer-token 제한을 byte 수로 추정하지 않는다. worker의 `needs_original_selection`을
그대로 받아 다음 source 선택으로 돌린다. 출력이 동률이면 `NEED_MORE`다.

`maximumContextBytes`는 최종 `payload` JSON의 UTF-8 크기다. HTTP 봉투, LLM token,
모델 메모리, 대기시간 또는 총 CHU 자원을 뜻하지 않는다. Jev timeout은 240초,
stdout/stderr 합은 128 KiB, LLM 실행 timeout은 기존 120초다. 실패·중단·초과 출력은
다시 실행하지 않는다. CLI exit 0은 완료된 관측이며 abstention도 포함한다. typed refusal은
2, defect는 3이다.

## Standard graph

project는 repo-relative `assemblySourcePath`의 실제 bytes를 SHA-256에 결속한다.
파일은 `assemble`의 stdout 원문이어야 한다. 다른 receipt·plan·snapshot의 파일은 거부한다.

```sh
src/hswm/effect-runtime/bin/hswm-context < assemble.json > selected-context.json
# project.json: 같은 입력에서 action="project", assemblySourcePath="selected-context.json"
src/hswm/effect-runtime/bin/hswm-context < project.json > context-bundle.json
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source context=context-bundle.json --profile v2 --query ontology/queries/hswm_jev_context_2026-10-09/roles.rq
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source context=context-bundle.json --profile v2 --shapes ontology/queries/hswm_jev_context_2026-10-09/shapes.ttl
```

실제 작업의 context/receipt에는 private 원문이 들어갈 수 있다. 예시는 작업자가 선택한
private 출력 경로에서 실행하며 자동 공개·KG 게시를 하지 않는다.

형태는 `Plan → Selection → Candidate/Assembly → Frame → RoleOccurrence → Participant`다.
각 Frame에는 관계의 정확한 key·owner·semantic JSON·frame hash·조립 내 ordinal이 있고,
RoleOccurrence에는 역할·reference type·원래 순서가 있다. 동일 participant가 두 역할에
나타나도 occurrence는 두 개다. [관계 계약](artifacts/jev_context_2026-10-09/graph-contract.v1.json)에
scope·domain/range·cardinality·손실 범위를 둔다. 기존 RDF v2 exporter의 reified relation과
PROV-O source derivation을 재사용한다. JSON-LD/N-Quads는 그 exporter의 파생 출력이다.

기술 안내와 검증용 fixture는 `hswm-workspace show jev-context`에서 찾는다.
`contracts`, `cli`는 구현 계약, `selection`, `roles`는 **SCRIPTED fixture** 조회다.
이 fixture를 실제 Jev 예측이나 성능 결과로 읽지 않는다. 실행 trace/outcome은 별도
content-store 기록으로 연결되며 현재 RDF view는 선택·조립까지 투영한다.

## Evidence and remaining measurements

2026-10-09 로컬 검증: 신규 context 검사 13개와 기존 semantic runtime·workspace 회귀
21개, 합계 **34개 통과**. TypeScript·Effect 경계 검사와 build도 통과했다.
실제 RDF 투영에서 공통 v2 SHACL과 context SHACL을 모두 실행했고, 연결이 빠진
부정 fixture의 거부도 확인했다. workspace 질의는 계약 6개, CLI 1개, 선택 1개,
역할 12개를 반환한다. scripted 예제는 필수 관계와 선택된 두 관계를 함께 읽으며
최종 payload는 6,060 UTF-8 bytes다. 이는 해당 예제의 크기이지 성능 비교가 아니다.

파일 fixture의 첫 NFS 실행은 immutable 파일 hard-link에서 `EPERM`으로 실패했다.
기존 file adapter가 요구하는 로컬 POSIX 의미를 확인하기 위해 명시적 RAM filesystem의
작은 임시 저장소에서 재검증했다. NFS 지원이나 전원 손실 내구성을 검증한 결과는 아니다.

재검증 명령은 아래와 같다. 임시 파일은 `TMPDIR`을 따르며 소유한 fixture만 정리한다.

```sh
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime run build
npm --prefix src/hswm/effect-runtime run test -- ../../../tests/effect-runtime/semantic-context.test.ts ../../../tests/effect-runtime/canonical-atom-v2-llm-semantic-runtime.test.ts ../../../tests/effect-runtime/workspace-cli.test.ts test/workspace-composite.test.ts --maxWorkers=1
src/hswm/effect-runtime/bin/hswm-workspace validate jev-context
src/hswm/effect-runtime/bin/hswm-workspace bindings jev-context
```

일반 계약·회귀 검사로 선택, abstention, 원문 보존, 버전 변경, 입력/출력 한도, 파일 저장소,
CLI, SPARQL/SHACL과 실행-관측 결속을 확인한다. 실제 Jev/LLM 추론과 토큰 사용량은
측정하지 않았다. `modelUsage=UNREPORTED_BY_THIS_ADAPTER`를 0으로 해석하지 않는다.

다음 비교는 같은 기반 LLM·작업·허용 정보·총 예산에서 fixed context와 이 선택기를
대조해야 한다. 후보 recall, 잘못된 생략, NONE/NEED_MORE, 한국어, 옵션 순서, 조합 효과,
실제 성공률·비용·end-to-end 지연을 함께 본다. Typeahead의 호출 예측, 후보 확률,
작업 성공률, Semantic Weight를 분리한다. W 갱신은 기존 outcome/admission 경로와
별도의 근거를 필요로 하며 이번 adapter가 허가하지 않는다. T7 읽기 선택 효용과
초지능 주장은 아직 입증되지 않았다.

출처와 연결:

- [기존 Jev 후보·국소 읽기 연구](../research/HSWM_JEV_PRINCIPLES_2026-09-21.md)
- [ReadFrame·역할·결과 계보 계약](../research/HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.md)
- [최적화 6원칙](../canon/USER_PRIMARY_HSWM_OPTIMIZATION_RULES_2026-10-07.md)
- [Typeahead 원본 설명](https://github.com/davila7/claude-code-templates/blob/main/cli-tool/components/mods/productivity/jev-skill-typeahead/README.md), 2026-10-09 확인: preview와 keyword score, provider, attach의 범위를 구분한다.
- [TypeSafe skill-suggestion cookbook](https://docs.typesafe.ai/cookbooks/skill_suggestion): 후보의 적합성·기권·추가 근거를 다루는 아이디어의 출처. 이 구현의 성능 근거는 아니다.

되돌리기는 신규 context 파일, workspace entry와 안내 링크만 제거한다. 기존 규칙·runtime
canonical state·과거 실험의 hash는 수정하지 않는다. stage된 실행 원문은 해당 store 소유자의
보존 정책을 따르며 canonical rollback을 가장해 삭제하지 않는다.
