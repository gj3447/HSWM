# HSWM 자체 개발에 HSWM 사용하기

2026-09-08의 [사용자 원문](../canon/sources/USER_PRIMARY_HSWM_SELF_DEVELOPMENT_AND_DAILY_KG_2026-09-08.txt)은
HSWM 자체도 HSWM을 기반으로 개발하고 오늘 작업을 온톨로지로 기록하라는 지침이다.
지침 자체는 `USER_PRIMARY`이며 아래 검사 구성과 피드백 방식은 `SECONDARY_AI` 구현이다.

[Constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 지속 학습 HSWM 목표를
유지한다. 이번 개념적 변화는 HSWM 자체 개발 과제를 기존 적응 런타임의 입력으로 사용한다는
것이다. 검사 선택·실행·관측·명시적 피드백을 같은 경로로 연결한다. 자기 수정 알고리즘,
자율 코딩 전체 경로, 자기 판정의 신뢰성이나 인지 합성이 완성됐다는 뜻은 아니다.

## 개발 흐름

HSWM checkout에서 실행한다. 다른 workspace를 지정하려면 해당 경로도 `hswm` 프로젝트여야
하며 `pyproject.toml`, `src/hswm`, `tests`, `scripts` 표식이 필요하다.

```bash
uv run --locked hswm-dev hswm plan --focus runtime
uv run --locked hswm-dev hswm run --focus runtime \
  --task '적응 런타임 변경사항 확인'
uv run --locked hswm-dev hswm status
```

[프로필](../../_research/causal_composition/examples/adaptive_hswm_development.v1.json)의
각 focus에는 집중 검사와 관련 검사를 이어 실행하는 확장 관계가 있다.
초기 선택에는 비용과 탐색도 작용한다. 받은 피드백은 해당 관계의 문맥 계수에 반영된다.
상태는 `.hswm-local/projects/hswm-<workspace 해시>.sqlite3`에 별도로 보존된다.

| focus | 집중 검사 | 확장 검사 |
| --- | --- | --- |
| `runtime` | 적응 상태 저장·런타임·개발 CLI | USL 어댑터 |
| `usl` | USL v1·v2 어댑터 | 적응 상태 저장·런타임 |
| `ontology` | 기존 개발 작업·문헌·오늘 작업 KG projection | Markdown 계약·수식 컴파일러 |
| `docs` | Markdown 계약·수식 컴파일러 | 기존 개발 작업·문헌 KG projection |

명령은 설치된 환경에서 `uv run --no-sync pytest -q`로 실행한다. profile은 패키지를
설치하거나 원격 서비스를 실행하지 않는다. 변경에 필요한 추가 검사는 별도로 실행하며,
선택된 검사에 맞추어 요구되는 검증 범위를 줄이지 않는다.

유용성을 판단한 뒤 `feedback --episode <ID> --success true|false --source <출처>`를
입력한다. 에이전트 판단은 `agent(codex):...`처럼 표시하며 사용자 의견으로 대체하지 않는다.
검사 exit code는 자동 보상이 아니다. 동일 피드백을 재전달해도 중복 학습하지 않으며 다른
판정으로 덮어쓰려는 충돌은 거절한다.
자기 개발 데이터도 외부 과제와 마찬가지로 관측적 국소 적응이며 인과적 credit은 미식별이다.

이 흐름은 [AGENTS.md](../../AGENTS.md)에 지속 지침으로 반영했다. wrapper 자체가 고장 나면
직접 집중 검사를 통해 수리하고 그 한계를 기록한다. 별도 승인이나 개발 중단 조건을 추가하지 않는다.

## 처음 사용한 결과

2026-09-08에 실제 `hswm-dev hswm` 실행 4건을 기록했다. 서로 다른 검사 범위이므로 수를
합산해 성능 지표로 만들지 않는다.

| focus | 실행 결과 | 명시적 피드백 |
| --- | --- | --- |
| runtime | 20개 통과, exit 0 | 대기 |
| ontology | 9개 통과, exit 0; RDFLib deprecation 경고 3건 | 에이전트의 유용성 판단 1건 |
| docs | 325개 통과, exit 0 | 대기 |
| usl | 19개 통과, exit 0 | 대기 |

검사 종료만으로는 네 결과 모두 `success=null`이며 학습 label을 만들지 않았다.
그 뒤 온톨로지의 source·사용자 인용 변조 검사가 이번 게시기 개발에 유용했다고 판단하여
`agent(codex):...` 출처의 명시적 feedback을 한 번 입력했다. 사용자 피드백은 받지 않았다.
`ontology-focused` 관계의 관측 수는 0→1, revision은 1→2가 됐다. 다음 프로세스의 plan에서
예측값은 0.5→약 0.690, 선택 점수는 약 0.267→0.727로 바뀌었다. 선택한 관계는 동일하다.
이 값은 학습 모델의 내부 점수이며 실제 성공 확률의 보정이나 더 나은 행동을 입증하지 않는다.

[기계 보고서](../../docs/operations/artifacts/development_day_2026-09-08/self_development_run.json)는
profile SHA-256, episode ID, 검사 범위별 출력 digest, 피드백 출처, 전후 plan과 상태 요약을
담는다. 작성 중 초기 프로필의 bootstrap 실행은 ignored 로컬 보관본으로 남겼다. 공개 보고는
최종 프로필의 4건과 피드백 1건을 기록하며 이후 실행의 현재 상태를 대신하지 않는다.
