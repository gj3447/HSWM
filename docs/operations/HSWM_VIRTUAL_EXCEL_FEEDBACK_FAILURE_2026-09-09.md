# 버엑시 소비자 보고: 검사 성공 뒤 HSWM feedback 실패

2026-09-09 · `SECONDARY_AI / CONSUMER_BUG_REPORT / OPEN`.
보고자: `agent(codex)`, 소비자 저장소 `virtual-excel-simulator`.
사용자의 오류 전달 요청으로 HSWM 저장소에 남기는 보고다. 수정·재실행·복구 완료 보고가 아니다.

버엑시의 전체 로컬 검사는 성공했지만 HSWM의 사후 피드백 기록이 실패했다.
네이티브 TypeScript CLI는 상세 원인 없이 `error: feedback`을 반환했고, 소비자 문서에
남아 있던 Python 대체 경로는 학습 처리 중 `KeyError: 'context'`로 종료됐다.
해당 episode는 확인 당시 피드백 대기 상태였다. 사용자는 HSWM 사용을 보류했으며,
이번 오류 보고 요청은 사용 재개나 기존 episode 재시도 승인이 아니다.

## 실제 관찰

| 항목 | 기록된 값 |
| --- | --- |
| Episode | `fec2d89e-38c1-4f4b-9140-05c3b7a01f31` |
| Backend / 선택 경로 | `typescript-effect` / `relation:check-focused`, revision 21 |
| 학습 설정 | `learn: true` |
| 실행 상태 / 시간 | `SUCCEEDED` / 50.649초 |
| 검사 범위 | Lean 빌드·공리 감사, 프로젝트 그래프 18개, 새 엔진 테스트 24개, 기존 저장 호환성과 Studio 빌드 등 전체 로컬 검사 |
| Result success | `null`: 검사 실행의 성공과 제출할 유용성 피드백은 별개 |
| 출력 digest | `c9a46947b07062cfd0fd605ffc0968f7d4437eed4dabb9323f1402119240d5fa` |
| 피드백 결과 | TS exit 2; Python exit 1; 이후 상태 관찰의 `pending_feedback`에 해당 episode 존재 |

제출하려던 `success: true`는 에이전트의 로컬 검사 판단이다. 사용자의 재미 평가나
HSWM의 인과적 효능 판정이 아니며, 이번 오류 보고를 `success: false`로 기존 게임 실행에
주입해서도 안 된다. 원래 피드백 값과 보고의 역할을 구분한다.

## 당시 실행 순서

아래 종료 코드와 오류 출력은 당시 agent transcript에 기록된 관찰이다.
독립된 원본 stderr 파일은 보존되지 않았다.

소비자 저장소 루트에서 아래 검사 호출은 성공했다.

```sh
../HSWM/src/hswm/effect-runtime/bin/hswm-dev 버엑시 run --focus check --task 'Verify functional TypeScript Effect training-match FSM, Lean parity, atomic journal and graph closure' --budget 900
```

이어 다음 피드백을 제출했다. 아래 명령은 사고 당시 기록이며 보류 중 실행 지시가 아니다.

```sh
../HSWM/src/hswm/effect-runtime/bin/hswm-dev 버엑시 feedback --episode fec2d89e-38c1-4f4b-9140-05c3b7a01f31 --success true --source 'agent(codex): Full local check passed: Lean build and axiom audit, 18 project graph gates, TypeScript including 24 training-match tests and 1944-path Lean parity, existing save compatibility and Studio build. Local engine evidence only, not human fun or launch balance approval.'
```

TS stderr, exit 2:

```json
{"status":"ERROR","code":2,"error":"feedback","backend":"typescript-effect"}
```

당시 소비자 skill의 fallback에 따라 Python 경로도 한 번 시도했다.
HSWM의 현재 AGENTS는 Python 적응 모듈을 과거 비교 도구로 분류한다. 이 fallback을
앞으로 지원되는 정상 복구 경로라고 가정하면 안 된다.

```sh
uv run --locked --project ../HSWM python -m hswm.infrastructure.development_cli 버엑시 feedback --episode fec2d89e-38c1-4f4b-9140-05c3b7a01f31 --success true --source 'agent(codex): Full local check passed: Lean build and axiom audit, 18 graph gates, 24 new engine tests with actual Lean parity, existing compatibility and Studio build. Local engine verification, not player or launch approval.'
```

Python exit 1. 당시 도구 출력의 핵심 호출 경로는 다음과 같다.

```text
development_cli.py:142 -> runtime.feedback(...)
adaptive_runtime.py:426 -> self._learn(...)
adaptive_runtime.py:390 -> self._new_specialization(route, examples)
adaptive_runtime.py:226 -> e["context"].items()
KeyError: 'context'
```

두 시도의 `source` 문구는 동일하지 않았다. 복구 작업자는 동일 피드백 재시도 정책과
실제 영속 상태를 확인해야 한다. 보고 시점에는 재시도하지 않았고, 정상 재시도라면
동일 payload를 재사용해야 한다. 이후 읽은 상태 기록에서는 해당 episode가 `SUCCEEDED`
상태로 `pending_feedback`에 남아 있었다. 피드백 완료나 기존 이력의 손상을 추정하지 않는다.

## 조사 요청과 확인되지 않은 원인

현재 코드의 [Python `_new_specialization`](../../src/hswm/cells/adaptive_runtime.py)은
예제마다 `context` 키가 있다고 가정한다. 기존 예제 중 다른 형식의 데이터가 있었다는
것이 직접적인 가설이다. 실제 예제 payload나 사고 당시 실행 바이너리의 정확한 바이트는
확보하지 않았으므로 레거시 데이터 문제·TS/Python 호환 문제로 확정하지 않는다.
TS의 일반적인 `feedback` 오류와 Python의 키 오류가 같은 원인인지도 미확인이다.

HSWM 작업자에게 요청하는 후속 확인:

1. 사설 상태의 격리 복사본에서 해당 episode·관계 revision·예제 스키마와 원래 실행본을
   확인한다. 원본 DB에 대한 임의 수정이나 실패 예제 삭제로 복구하지 않는다.
2. 네이티브 feedback의 원인 코드와 예외 경로가 비밀 데이터 없이 드러나게 확인한다.
   기존 데이터가 지원 범위 밖이면 명시적 검증/마이그레이션 오류를 제공한다.
3. 피드백 기록과 선택적인 학습/분화 단계의 실패 정책을 확인한다. 학습 오류가 판단
   기록까지 막는 현재 동작이 의도인지 명시하고, 실패 시 부분 쓰기와 재시도 충돌을 검사한다.
4. 수정 후 지원되는 native 경로에서 새·기존 형식 데이터, 동일 요청 재전달, 충돌 요청,
   실패 뒤 상태 보존, 프로세스 재시작을 격리 회귀로 확인한다.
5. 소비자 문서의 Python fallback을 현재 지원 정책과 맞춘다. 버엑시의 사용 재개는
   별도 사용자 지시가 있을 때만 진행한다.

## 출처와 범위

소비자 Git 증거는 `virtual-excel-simulator`의 다음 커밋에 있다.

- `00399f4236125f391abbe0cbdab9dd032daf957d`: `HANDOFF.md`에 검사 성공과 feedback 오류를 기록.
- `41eef5acfe0a5548c25a2b0ac7d06b44107b6848`: `AGENTS.md`, `HANDOFF.md`,
  `.claude/skills/hswm-dev/SKILL.md`에 사용자 지시의 HSWM 보류를 반영.

보고 작성 시 HSWM HEAD는 `b7721b4`였다. 사고 당시의 HSWM HEAD·실행 dist digest는
기록되지 않았으므로 이 커밋에서 같은 장애가 새로 재현됐다고 주장하지 않는다.

소비자 호스트의 로컬 기록 위치와 SHA-256은 아래와 같다. 임시 파일은 추후 사라질 수
있으며 다른 머신에 자동 제공되지 않는다. 전체 실행 출력·사설 DB는 보고에 복사하지 않았다.

| 로컬 기록 | SHA-256 |
| --- | --- |
| `/tmp/virtual-excel-training-match-hswm.json` | `6023e0fa4b6ae82eb36797cca46cec3ae28ef9257dd12e89a1f8a81050bedbc4` |
| `/tmp/virtual-excel-training-match-hswm-status.json` | `f7da1bd9a7777b9bf394ebf64f40456c0c5b79a39d872ebcfca03c58e90adbb8` |

오류 stderr는 당시 에이전트 도구 출력과 커밋된 소비자 인수인계에 근거한다. stdout용
feedback 임시 파일은 비어 있어 별도의 원본 stderr 파일 증거로 제시하지 않는다.
이 보고는 소비자 장애 인수인계이며, 런타임 feedback 제출·HSWM 학습·라이브 KG 반영이나
담당자의 확인 응답을 뜻하지 않는다. 보고 문서는 HSWM CLI를 호출하지 않고 직접 검사한다.
