# HSWM 직접 측정 결과 로그

> 체크인 코드와 직접 측정으로 재현 가능한 현재 결과만 요약한다.
> 삭제된 개인 판정·감사·오케스트레이션 계층의 기록은 현재 권위가 없으며 복원하지 않는다.

| 날짜 | 결과 | 경계 |
|---|---|---|
| 2026-08-15 | 폐기 도구 전용 원격 브랜치를 삭제했다. 현재 HSWM 작업 트리의 파일명·본문에서 폐기 대상 세 계열의 이름은 0건이며 `main`과 `origin/main`은 일치한다. | 현재 트리와 원격 ref 직접 검사 |
| 2026-08-15 | 개인 거버넌스 계층과 결합된 코드·문서·테스트·영수증을 제거하고 기본 경로를 `실행 → 직접 측정 → 중요 결과 기록 → commit/push`로 단순화했다. 전체 회귀는 **1148 passed, 3 skipped**다. | [`minimal governance`](research/HSWM_MINIMAL_GOVERNANCE.v1.json) · [`user canon`](USER_PRIMARY_HSWM_MINIMAL_GOVERNANCE_RAGNAROK_2026-08-15.md) |
| 2026-08-15 | 실제 KG에서 폐기 계보 노드 **3,234개**와 잔여 관계를 제거했다. 전용 라벨·관계 타입과 모든 속성을 다시 스캔한 결과 노드 0, 관계 0이다. | Neo4j 속성·라벨·관계 전수 검사와 삭제 후 재조회 |
| 2026-08-15 | Dell tower의 사용자 서비스·코드·credential 디렉터리를 격리했고 Mac mini의 재생성 원인이던 SERVER installer/watchdog 항목을 제거했다. Mac은 watchdog 여러 주기 뒤에도 LaunchAgent·plist·55170 listener가 모두 0이며 Dell도 서비스·listener가 0이다. | 운영 readback · SERVER `7940743` · 한 주기 초과 재검사 |
| 2026-08-15 | Dell의 3D 제품 저장소에서 외부 판정기·고정 manifest·mutation gate 3,077줄을 제거하고 실제 카메라·PLC·DB 통합 실행만 남겼다. 사용자 dirty diff는 별도 백업 뒤 그대로 보존했다. 정리 관련 회귀는 **88 passed**이며, 전체 e2e의 기존 artifact-path 실패 5건은 전후 동일하다. | Dell `776712bf` · clean HEAD 기준 전 7 fail/후 5 fail(폐기 테스트 2건 제거) |
| 2026-08-15 | 333에서 외부 정적 gate와 별도 CLI wrapper를 제거하고 native Rust trace/test 경로로 통합했다. substrate 직렬 전체 회귀는 통과했고 transfer의 TCP round-trip 1건은 정리 전후 동일한 기존 실패다. | 333 `1095d93` · local/Mac 동기화 |
| 2026-08-15 | bhgman에서 전용 adapter·gate·seed·judge 계층을 제거했다. canonical branch와 Mac의 진행 중인 16개 수정 파일을 분리해 각각 반영했고 생성 캐시도 격리했다. 전체 회귀는 **2189 passed, 32 skipped**, 기존 AMIE Java 환경 실패 1건은 동일하다. | canonical `1363385` · Mac `925a9bc` |
| 2026-08-15 | Mac의 오래된 HSWM checkout을 현재 `main`으로 fast-forward하고, 전역 Claude/Codex skill·MCP 설정·플러그인 캐시·세션 메모에서 폐기 계보를 격리했다. 갱신 플러그인은 46개 skill을 포팅하며 **75 passed** 및 공식 구조 검증을 통과했다. | HSWM `25e7661` · plugin `0.1.0+codex.20260815082829` · 활성 경로 문자열 재검사 0 |
| 2026-08-15 | 현재 호스트의 Orca runtime-home에 숨어 있던 폐기 MCP block과 skew pair를 제거하고 관련 telemetry/cache/backups를 휴지통에 격리했다. 실시간 status telemetry는 현재 대화 텍스트이므로 실행 설정과 분리했다. | 활성 Orca config 재검사 0 |
| 2026-08-15 | Dell canonical checkout과 전용 이름의 별도 worktree는 정리했다. 다만 별개의 Claude 작업 worktree 19개에는 서로 다른 미완료 변경이 있어 역사 복사본을 강제로 덮어쓰지 않았다. 해당 경로를 cwd로 쓰는 프로세스는 0이다. | dirty worktree 보존 경계 · 프로세스 cwd 전수 검사 |
| 2026-08-15 | 현재 머신의 root 소유 55170 relay만 sudo 권한 부재로 unit 제거가 막혀 있다. upstream은 제거되어 기능하지 않지만 unit과 로컬 listener 자체는 남아 있다. | `systemctl show`와 `ss` 직접 검사 |
| 2026-08-15 | Sheaf의 local-to-global 수학, cellular/Hodge 연산자와 HSWM 후보 대응을 분리해 정리했다. 효능 주장은 하지 않는다. | [`research note`](HSWM_SHEAF_RESEARCH_ONTOLOGY_2026-08-15.md) · [`ontology`](research/HSWM_SHEAF_ONTOLOGY.v1.json) |
| 2026-08-04 | selective utility 개발 측정에서 typed arm이 네 대조군보다 높았지만 탐색 결과이며 sealed 과학 판정이 아니다. | [`EFFICACY.md`](EFFICACY.md) |
| 2026-07-23 | scalar slow-weight P1은 12개 candidate 중 fresh pass·activation 0, A1−A2 0, 456개 rank replay에서 top-10 변화 0으로 과학적 RED다. | [`EFFICACY.md`](EFFICACY.md) · [`evidence`](EVIDENCE_P1_CLOSED_LEARNING_LOOP_2026-07-23.json) |

프로그램 전체의 과학적 상태는 `UNJUDGED`다. 로컬 테스트 통과는 구조·불변식의 공학적
closure일 뿐, 효능 승격으로 해석하지 않는다.
