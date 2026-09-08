# USL v2 구현 독립 검토 — 2026-09-08

판정: 의미 변경 검출·선택 조회·권한 전달은 이전 구현보다 실질적으로 개선됐고 재현됐다. 다만 라이브러리의 원문 결속 버그 1건, 관측 JSON 검증 누락 1건, HSWM 연결의 버전 불일치가 남았다. 제한된 CLI 개발 보조 실사용은 유용성을 측정할 다음 단계이며, 자동 판정·학습 입력으로 연결하기 전에는 아래 항목을 보완해야 한다.

HSWM의 목표 정체성은 진화하는 하이퍼그래프를 갖는 하나의 token-native LLM-function macro-neural network다. 이번 개념적 변화는 USL의 선언·참조 관측을 의미 계약과 원문에 결속하는 **외부 인터페이스 개선**이다. 관측 비교가 HSWM의 인지·인과 판정·학습을 대신하지 않으며, FCL 계약과 기존 G0/G1/D-4 판정은 변경하지 않는다. 이 문서는 구현 검토이며 과거 연구 결과나 USL 사용자 정의를 승격하지 않는다.

검토 대상은 로컬 `USL` 디렉터리의 package version `0.3.0`이며 Git 메타데이터가 없다. 검사 당시 파일 SHA-256과 실행 결과를 아래에 기록했다. USL 소스·의존성은 수정하거나 설치하지 않았다. 이전 v1 감사 기록은 그대로 보존한다.

## 먼저 수정할 항목

### 1. P2 — resolver 대기 중 sourceText 변경으로 서로 다른 원문과 plan이 결속됨

위치: USL `src/language/runtime.ts:38`, `:62`, `:86`.

`inputPlan`은 복사하지만 `options.sourceText`는 시작 시 검증하고 IO 후 다시 읽어 digest를 계산한다. 호출자가 같은 options 객체를 보유하고 resolver 실행 중 원문을 반대 의미의 유효한 USL 원문으로 변경하면, 실제 `observeProgram`이 **원래 planDigest + 변경된 원문의 sourceDigest**를 반환한다. 주입 resolver 두 번의 호출로 재현했다. CLI에서의 재현이나 권한 우회를 주장하지 않으며, 공유 options 객체를 쓰는 라이브러리 경로의 결속 결함이다.

수정: 첫 yield 전에 `const sourceText = options.sourceText`로 값을 고정하고 컴파일 검증과 digest에 동일한 값을 사용한다. 회귀 검사는 resolver 대기 중 options의 sourceText를 변경해도 관측 원문 식별자가 최초 값으로 유지되는지 확인하면 된다.

### 2. P2 — validateObservation이 모순된 v2 메타데이터를 승인함

위치: USL `src/language/comparison.ts:14`, `:31`, `:44`, `:48`.

정상 관측 JSON에서 `readScope.links`를 문자열로, metrics를 잘못된 타입으로 바꾸고, 전체 status·resourcesResolve를 개별 관측과 모순되게 설정했다. 실행되지 않은 check의 status도 `EXECUTED_AND_PASSED`로 변경한 뒤 바깥 observationDigest만 재계산했다. **validateObservation과 compareObservations 모두 통과**했다. 정상 runtime의 체크 자동 실행을 발견한 것이 아니라, 가져온 JSON을 `ProgramObservation`으로 반환하는 검증 경계의 누락이다.

수정: v2 필드의 정확한 타입·상태를 검사하고, 내부에서 재계산할 수 있는 전체 status, resourcesResolve, check 정의·역할·근거·NOT_EXECUTED 상태를 검증한다. readScope·metrics에는 타입·범위·선택 집합 일관성 검사를 추가한다. 호출 당시 실제 IO 횟수의 진위까지 JSON만으로 증명할 수는 없다.

임의의 유효한 plan/source digest도 통과하지만, 이를 암호학적 위조 방지 실패로 분류하지 않는다. 문서는 이미 digest가 작성자 증명이 아니라고 설명한다. 전체 plan은 보고서에 digest로만 기록되고, 의미 본문은 선택 범위만 포함하므로 전체 plan/source 식별자를 다시 계산하려면 호출자가 고정한 원본도 필요하다. 검증 가능한 내부 일관성과 외부 출처 신뢰를 구분해야 한다.

### 3. HSWM 통합 누락 — 현재 어댑터는 새 계약과 v2 관측을 거절함

위치: HSWM `src/hswm/infrastructure/usl_adapter.py:17`, `:124`, `:209`.

현재 USL에서 실제 생성한 관측을 기존 `preview_usl_request`에 전달했다. 기존 문법의 plan + v2 report는 `report shape`로 거절됐고, applies/check를 사용하는 plan은 `meaning shape`로 먼저 거절됐다. 기존 v1 fixture는 여전히 ACTION_PROPOSAL을 생성한다. 따라서 실패 시 차단은 유지되지만 **현재 USL을 HSWM이 직접 소비한다고 말할 수 없다**.

수정: 선택 범위, DENIED, 의미 계약, 원문·plan·관측 digest를 검증하는 명시적 v2 어댑터 경로를 추가한다. USL의 `sha256:<hex>` + JSON.stringify 순서 기반 식별자와 HSWM의 정렬 JSON digest도 구분해야 한다. schema 문자열만 v1으로 바꾸거나 새 필드를 버려 연결하면 이번 개선을 잃는다.

## 재현된 개선과 측정 범위

| 검증 | 실제 확인 | 해석 범위 |
| --- | --- | --- |
| 기존 테스트·타입 검사 | 90 passed, 0 failed, 0 skipped; tsc exit 0 | 기존 회귀 검사 통과. 위 추가 반례는 기존 검사에 없음 |
| 의미 반전 | plan·meaning·contract digest와 semanticContractChanged가 변경됨 | 동일 endpoint 결과여도 선언 의미의 변경을 분리 검출 |
| 역할·근거·검사 계약 | applies/check와 참여자 역할이 보존됨 | 검사 상태 NOT_EXECUTED, 의미 진실 NOT_EVALUATED 유지 |
| 선택 조회 | 선택 링크의 참여자와 grounding만 조회 | 미선택 자원은 읽지 않음 |
| 실제 resolver 권한 | 요청 정책이 Config 정책을 확대하지 못함; redirect 목적지와 symlink 실제 경로가 별도 허용 없으면 거절됨 | 주입 fetch·로컬 임시 파일로 확인. 호스트 파일시스템 격리 증명은 아님 |
| 관측 보존 CLI | baseline 저장·의미 변경 비교·입력 보존 테스트 통과 | 기존 관측 보존 경로의 회귀 확인 |
| 게임 dash fixture | 전체 선언 자원 5회 → 선택 링크 자원 3회; 내용 변경 1건 검출 | 격리 예제의 resolver 호출 계수 |

게임 예제의 `repository_scan`은 게임 저장소 전체를 탐색하는 구현이 아니라 **선언된 5개 fixture 자원 전체 조회**다. `unnecessaryRechecksAvoided=2`는 독립적인 개발자 재작업 측정이 아니라 `max(0, 5-3)`으로 계산된다. `staleEvidenceCaught=1`은 임시 controller 내용 수정이 RECHECK_EVIDENCE 제안으로 이어진 결과다. 테스트 파일을 읽었지만 실행하지 않았다. 주소만 이동한 경우와 의미 설명만 반전한 경우도 각각 분리 검출됐다.

개발자 시간, 실제 게임 품질, HSWM 학습 효과는 미측정이다. 먼저 실제 개발 작업에서 선택된 링크·조회 수·개발자가 받아들인 재검사 제안·수정 후 결과를 함께 기록하는 것이 적절하다. 유용성 피드백은 검사 성공과 별도로 받아야 한다. KG fingerprint는 문서대로 KG_METADATA 범위여서 외부 KG의 모든 의미·그래프 변경 검출을 보장하지 않는다.

## 재현물

- [USL 파일 해시 스냅샷](../../_research/usl_adapter/review_v2_source_snapshot_2026-09-08.json), [90개 테스트·타입 검사 출력](../../_research/usl_adapter/review_v2_baseline_verification_2026-09-08.json)
- [의미·원문 변경 및 검증 누락 재현 프로그램](../../_research/usl_adapter/review_v2_digest_probe_2026_09_08.ts), [결과](../../_research/usl_adapter/review_v2_digest_probe_2026-09-08.json)
- [권한 경계 재현 프로그램](../../_research/usl_adapter/review_v2_permissions_probe_2026_09_08.ts), [결과](../../_research/usl_adapter/review_v2_permissions_probe_2026_09_08.json)
- [게임 예제 독립 재현 결과](../../_research/usl_adapter/review_v2_game_result_2026-09-08.json)
- [HSWM 호환성 재현 프로그램](../../_research/usl_adapter/review_v2_hswm_compat_2026_09_08.py), [결과](../../_research/usl_adapter/review_v2_hswm_compat_2026-09-08.json)

저장소 루트에서 기존에 설치된 USL 도구만 사용해 다음과 같이 재현한다. 기존 결과를 보존하려면 `--out`에 새 경로를 지정한다. 권한 probe와 게임 예제는 stdout을 출력한다.

```sh
../USL/node_modules/.bin/tsx _research/usl_adapter/review_v2_digest_probe_2026_09_08.ts --usl-root ../USL --out /tmp/usl-v2-digest-review.json
../USL/node_modules/.bin/tsx _research/usl_adapter/review_v2_permissions_probe_2026_09_08.ts
../USL/node_modules/.bin/tsx ../USL/examples/game-workflow.ts
uv run --locked python _research/usl_adapter/review_v2_hswm_compat_2026_09_08.py --usl-root ../USL --out /tmp/usl-v2-hswm-review.json
```
