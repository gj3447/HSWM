# GAME·수풀림 개발에서 HSWM 사용하기

개발 체크를 선택·실행하고 작업별 피드백을 다음 선택에 반영하는 로컬 실사용 경로다.
가벼운 검사부터 사용하며 프로젝트의 필수 검증이나 제품 판단은 그대로 따른다.
현재 수풀림 코드는 `SYMPOSIUM`의 연구 기록에서 분리된 형제 저장소 `SUPULLIM`에 있다.
사용자가 활발히 개발 중이라고 지정한 **메이플리니지와 버엑시**를 GAME 쪽 우선 대상으로 둔다.
버엑시는 `GAMES/the-excel-tycoon`이며 기존 `game` profile 이름을 이어 쓴다. 2026-09-08부터 버엑시의
개발 루트는 독립 레포 `~/CD/virtual-excel-simulator`이고 profile은 v2다(아래 ‘2026-09-08 갱신’).
메이플리니지는 `GAMES/maplelineage` 전용 profile과 별도 상태 파일을 사용한다.

## 시작

HSWM, GAME, SUPULLIM이 같은 상위 디렉터리에 있는 checkout 기준이다.
프로젝트 루트에서 실행하면 그 workspace에 맞는 상태 파일을 계속 사용한다.
설치된 프로젝트 도구를 사용하며 프로젝트 의존성이 준비된 checkout을 전제로 한다.

GAME 루트:

```bash
uv run --locked --project ../HSWM hswm-dev maplelineage run \
  --focus combat --task '메이플리니지 전투 변경사항의 가벼운 개발 검사'
uv run --locked --project ../HSWM hswm-dev maplelineage status
uv run --locked --project ../HSWM hswm-dev 버엑시 run \
  --focus session --task '방송 세션 변경사항의 가벼운 개발 검사'
uv run --locked --project ../HSWM hswm-dev 버엑시 status
```

SUPULLIM 루트:

```bash
uv run --locked --project ../HSWM hswm-dev supullim run \
  --focus soop --task 'SOOP 연동 변경사항의 가벼운 개발 검사'
uv run --locked --project ../HSWM hswm-dev supullim status
```

다른 디렉터리에서는 `--project`를 HSWM checkout 경로로 지정하고 action 뒤에
`--workspace /실제/프로젝트/루트`를 추가한다. CLI는 이 HSWM checkout의 profile을 사용한다.
`game`, `the-excel-tycoon`, `버엑시`는 같은 profile·DB를 사용하는 이름이다.
`maplelineage`와 `메이플리니지`도 같은 이름으로 처리하며 버엑시와 이력을 섞지 않는다.
GAME의 동시 개발 worktree를 쓰는 경우 해당 GAME worktree 루트를 `--workspace`로 지정한다.

| 프로젝트·focus | 기본 실행 | 확인 범위 |
| --- | --- | --- |
| 메이플리니지 `combat` | server에 설치된 `tsx --test`로 `server/test/combat.test.ts` 실행 | 전투 명령·tick·stamina·방어·replay·경계값 |
| 메이플리니지 `encounter` | 같은 runner로 `server/test/encounter-mailbox-v2.test.ts` 실행 | 메모리 내 encounter 입력 대기열과 scheduler frame |
| 버엑시 `session` | `pnpm --dir GAMES/the-excel-tycoon run test:session` | 방송 세션 상태 전이·이벤트·replay 등의 로컬 fixture |
| 버엑시 `bridge` | `python3 GAMES/the-excel-tycoon/engineering/verify_soopoolim_creator_bridge_v1.py` | 수풀림 연결 자료의 경로·고정 hash·참조 완전성 |
| 버엑시 `career` | `pnpm --dir GAMES/the-excel-tycoon run test:career` | Studio 커리어·저장·HTTP·리허설·장면·v3/v4 저널 재생 |
| 버엑시 `graph` | `python3 -B scripts/verify_repository_graph.py` | 독립 레포 그래프·잠금·독립성 검증 |
| 버엑시 `check` | `corepack pnpm run check` (`--budget 900` 필요) | 루트 전체 게이트. 커밋 전 검사 |
| SUPULLIM `soop` | `npm run test:soop` | fake fetch·임시 SQLite를 이용한 SOOP 연동·검토자 처리 |
| SUPULLIM `creator` | `npm run check:creator-research` | 공유 조사 자료의 고정 hash·등록·참조 완전성 |

각 focus에는 기본 검사와 보조 검사까지 수행하는 extended 관계가 있다.
선택은 해당 focus 안에서만 이루어지므로 다른 기능의 쉬운 검사로 요청을 대체하지 않는다.
`plan`으로 실행 전 선택을 확인하고, `--route session-extended` 같은 옵션으로 허용된 관계를
명시 선택할 수 있다. `--stage development|regression`도 문맥에 기록한다.
기본 시간 한도는 60초이며 `--budget`으로 조절한다.

## 피드백을 남기는 방법

이 개발 profile들은 명령의 exit code·출력을 기록하되, 검사 통과를 개발 유용성 보상으로
자동 변환하지 않는다. 그래서 실행 직후 `status`의 `pending_feedback`에 episode가 나타난다.
버그를 찾은 실패한 검사도 유용했을 수 있다. 사용자가 실제 결과를 보고 판단한다.

```bash
uv run --locked --project ../HSWM hswm-dev game feedback \
  --episode 실제_작업_ID --success true \
  --source 'user: 회귀 원인을 바로 확인하는 데 도움이 됨'
```

메이플리니지는 `game`을 `maplelineage`, 수풀림은 `supullim`으로 바꾼다.
도움이 안 됐다면 `false`와 짧은 이유를 사용한다.
현재 source 길이 한도는 256자다. 이 대화에서 episode와 함께 **도움됨/도움 안 됨 + 이유**를
알려줘도 해당 작업의 명시 피드백으로 기록할 수 있다. 아직 받지 않은 의견을 만들어 기록하지 않는다.

피드백은 그 작업에서 선택한 관계의 문맥 계수와 관측 수를 갱신한다. 이 profile에서
`predicted_success`는 해당 피드백 label의 모델 예측이며 테스트 통과율이나 제품 성능 지표가 아니다.
같은 episode의 동일 피드백을 다시 보내도 중복 학습하지 않는다. `--frozen` 실행은 데이터와
피드백을 보존하되 학습 계수를 갱신하지 않는다. 중단·timeout은 자동 재실행하지 않는다.

상태는 HSWM checkout 아래 `.hswm-local/projects/`에 project와 workspace hash별 SQLite로
저장된다. `--state`로 별도 파일을 사용할 수 있다. 입력·출력·피드백은 로컬 개발 자료이며
Git에서 제외한다. GAME 제품 상태, SUPULLIM 공개 KG·회원·vault나 배포 경로에는 연결하지 않는다.
현재 세션의 편집·대화 전체를 자동 수집하지 않으며, `hswm-dev`로 실행하거나 명시적으로
제공한 피드백만 기록한다.

## 운영 범위

이 연결은 기존 HSWM 실행기를 사용하는 얇은 CLI와 세 개의 manifest다.
GAME과 SUPULLIM의 소스·package script·사용자 변경에는 새 수정이 필요하지 않다.
개발 데이터는 개선 방향을 찾는 데 사용하고, 별도의 미관측 과제 성능 증명으로 사용하지 않는다.
HSWM 전체 이론이나 게임 재미·실서비스 품질의 판정 범위도 아니다.

- CLI: `src/hswm/infrastructure/development_cli.py`
- 버엑시 profile: `_research/causal_composition/examples/adaptive_game_development.v1.json`
- 메이플리니지 profile: `_research/causal_composition/examples/adaptive_maplelineage_development.v1.json`
- 수풀림 profile: `_research/causal_composition/examples/adaptive_supullim_development.v1.json`
- 실행·학습 의미: [적응 하이퍼그래프 런타임](../research/HSWM_ADAPTIVE_HYPERGRAPH_RUNTIME_2026-09-07.md)

2026-09-07 첫 로컬 실행에서 GAME 방송 세션 검사 40개와 SUPULLIM SOOP 검사 23개가 통과했다.
episode는 각각 `game-session-smoke-20260907-1`, `supullim-soop-smoke-20260907-1`이다.
HSWM 실행·CLI 기본 검사 9개와 새 wrapper 검사 3개도 통과했다.
두 프로젝트 실행은 별도 프로세스의 `status`에서 재조회되며 사용자 피드백 대기 상태다.
실제 사용자 유용성 의견은 아직 받지 않았으므로 이 두 profile의 학습 관측 수는 0이다.

같은 날 메이플리니지 전투 검사 19개를 HSWM으로 실행해 통과했다.
episode는 `maplelineage-combat-smoke-20260907-1`이며 사용자 피드백 대기 상태다.
CLI 회귀 4개와 실제 `버엑시 status`로 이전 GAME episode가 보존되는 것도 확인했다.
게임 소스에 새 수정 없이 HSWM의 실행 대상만 확장했다.

## 2026-09-08 갱신: 버엑시 독립 레포 연결

버엑시 개발이 `GAME` 스냅샷에서 독립 레포 `~/CD/virtual-excel-simulator`로 옮겨졌다.
그 루트에서 `--project ../HSWM`으로 실행하면 workspace hash가 달라 새 상태 파일을 쓴다.
같은 날 그 workspace의 v1 profile 상태에 세션 검사 episode 2개와 에이전트 라벨 피드백 2개를
남겼다. 이후 `career`·`graph`·`check` focus를 더한 **profile v2**
(`adaptive_game_development.v2.json`, graph id `hswm-game-development-feedback-v2`)로 바꿨다.
저장소는 manifest digest를 graph id별로 고정하므로 v1을 제자리에서 바꾸지 않았다.
v1 episode·피드백은 같은 SQLite 파일의 v1 graph에 남고 `status`는 v2 graph만 보여 준다.
v1 relation 4개는 v2에서도 같은 순서·정의로 유지된다. `check`는 cost 240이므로 기본
budget 60에서는 선택되지 않으며 `--budget 900`을 명시한다.

에이전트 연결은 대상 레포 쪽에 있다. `virtual-excel-simulator/AGENTS.md`의 HSWM 절과
`.claude/skills/hswm-dev/SKILL.md`가 focus 선택, 실행, 피드백 기록 규칙을 정한다.
피드백 `--source`는 사용자 판정과 `agent(claude-code): ...`처럼 표시한 에이전트 판정을 구분한다.
에이전트 판정은 사용자 판정으로 승격하지 않는다. HSWM 실행은 대상 프로젝트의 필수 검증을
대체하지 않고, 통과가 완료 판정도 아니다. 이 연결로 얻는 데이터는 여전히 명시적 CLI 실행과
피드백뿐이며 대화·편집 전체의 자동 수집이 아니다. 메이플리니지·수풀림 레포의 지침은 아직 없다.
