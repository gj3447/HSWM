# HSWM 전체 범위 감사 — 2026-09-13

**판정: 활성 적응 실행기는 TS/Effect로 동작하지만, 저장소 전체 전환과 HSWM 연구 완성은 모두 미완료다.**
검토 기준은 Git `6b6c3fd51f496bdb43c3f1667e6d5bc62adbf7b8`이다. 이번 작업은 코드·실행 경로·기존 결과를 대조한 감사이며, 새 모델 실험이나 효능 판정이 아니다. 작업 중이던 relation-synthesis 변경 4개는 검토 기준에서 제외하고 보존했다.

목표는 [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 token-native macro-network다. evolving hypergraph가 harness·world model·continuous learner 역할을 함께 수행한다. 이번 개념적 변경은 **구현된 부품, 실제 연결된 실행 경로, 검증 범위, 과학적 완료 조건을 별도 속성으로 기록하는 것**이다. FCL-1..8, schema별 atom 책임 소유자 하나, typed reference, provenance와 outcome-bound revision 조건은 유지한다.

## 1. 전체 범위 대조

| 영역 | 확인한 구현·증거 | 남은 경계 |
|---|---|---|
| `hswm-live` / `hswm-dev` | TS/Effect 명령 실행, 관계 선택, SQLite revision, 명시적 피드백과 다음 선택 연결 | 국소 관측 기반 적응이다. 독립적 인과 credit·새 과제 우위의 증거는 별도다. |
| task / USL / KG / 개발 도구 | 네이티브 CLI와 bounded projection 구현 | Python wheel·sdist·문서 호출이 병존한다. 어댑터·조회 성공은 cognition이나 admission이 아니다. |
| S2S 모델 학습·보관 | 실제 native fit → optimization receipt → model archive → 파일 검증 | 원본 학습 궤적의 결정적 replay, Q 제거·복원, integrity, task evaluation, bootstrap, final candidate, pilot/CI가 연결되지 않았다. |
| F1 토큰·호출·HTTP | 고정 tokenizer 비교, QF→BF→AF 호출, 한 번의 HTTP 요청 어댑터, 기존 suite 판정 | 네이티브 `run` 없음. 원본 SQLite ledger·idempotent spool·원자적 item 수락·전체 suite 실행이 남았다. |
| F3 | cache key·hit/miss·한 호출의 budget 상태 전이 | 캐시/상태를 관리하는 실행기, provider retry, world·lesson·retrieval·evaluation·최종 receipt가 남았다. |
| CI·설치·컨테이너 | 네이티브 CI와 Python 호환/연구 CI 병존 | SWM-0W confirmatory register/confirm/adjudicate, S2S pilot, bootstrap의 Python 환경 설치를 개별 경로로 닫아야 한다. |
| 표준 그래프 도구 | 기존 RDF/N-Quads·SHACL·PROV·질의 projection과 잠금 파일 | native graph `qualify`도 Python runner profile에서는 `uv … python -I`를 실행한다. 표준 구현의 언어와 HSWM 소유 조정 코드의 언어를 분리해야 한다. |
| 함수형 경계 | 297개 TS 파일의 기존 5개 규칙 검사, 155개 선택 파일의 AST 검사 통과 | 예외 파일 38개가 남는다. 이 검사는 모든 오류 반환·부작용·자원 수명·실행 연결의 정합성을 증명하지 않는다. |
| 패키지 | 실제 npm pack 목록에서 30개 bin target 포함 여부 확인 | 파일 포함과 기능 완성은 다르다. Prom9/F3 내부 부품은 package root export 및 활성 `run`에 연결되지 않았다. |
| KG·지식 지도 | 최신 모델 checkpoint 34개 source pin 일치, 지식 지도 원래 commit의 246개 source pin 일치 | S-5의 오래된 상태가 지도에 남았다. 과거 snapshot을 현재 판정으로 그대로 사용하면 안 된다. |
| 구성적 증명 | 유한 선택 개선, 유한 무작위 배정 식별식, 합성 간섭 반례와 제한된 보완을 Lean으로 검사한 기록 | 실제 sampling premise, runtime refinement, multiscale credit·topology·world/self·합성의 동시 witness가 없다. |
| 연구 완료 | opaque v5의 state-readout·remove/restore·sham 관측, B0/B2 첫 비교 결과 존재 | D-4의 durable canonical revision과 진짜 held-out 행동 효과를 같은 run으로 보이는 단계가 남았다. 전체 FCL 실현은 미판정이다. |

기존 [inventory v8](../../_research/native_migration_2026-09-13/inventory.v8.json)의 22개 항목은 크기와 중복이 다른 묶음이다. `6 VERIFIED_NATIVE / 16 PARTIAL`을 전환율로 계산하지 않는다. `shell-watchdog`의 native 판정은 offline judge에 한정되며 upstream suite 생산까지 포함하지 않는다. 새 [진입점 목록](../../_research/native_migration_2026-09-13/scope-entrypoint-catalog.v1.json)은 검색으로 찾은 후보와 실제 호출 근거를 구분한다. 동적 호출·라이브 배포 전체를 확인한 목록은 아니다.

## 2. 이번에 추가로 확인한 문제

1. **F1 HTTP 구현이 활성 실행 명령까지 연결되지 않았다.** `hswm-prom9-f1 run`은 exit 2와 `judge` 사용법을 반환했다. [CLI](../../src/hswm/effect-runtime/src/native-prom9-f1-cli.ts), [호출 runtime](../../src/hswm/effect-runtime/src/native-prom9-network-runtime.ts), [원본 durable transport](../../prom_search_hswm/hswm_f1_durable_transport.py)를 대조했다. optional sink에 주입한 결과를 durable ledger가 만든 증거처럼 해석하면 안 된다.
2. **S2S 직접 호출용 설정 검증 함수에 오류 반환 결함이 있다.** [fit-domain](../../src/hswm/effect-runtime/src/native-s2s-fit-domain.ts)의 `validateNativeS2SFitConfig(unknown)`에 enumerable `seed` getter를 넣으면 getter를 한 번 실행하고 예외를 던진다. `Either.Left`를 반환하지 않는다. 일반 JSON CLI는 decode·config capture를 먼저 하므로 그 경로의 탈출 문제로 재현된 것은 아니다. package root export에도 이 함수는 없다. **좁은 API 경계 결함(P2), 미수정**으로 기록한다. [재현 프로그램](../../_research/native_migration_2026-09-13/scope-fit-getter-probe.mjs)은 현재 결함의 관측용이며 회귀 통과 검사가 아니다.
3. **기존 목록에 실행 경로가 너무 크게 묶여 있다.** [confirmatory workflow](../../.github/workflows/swm0w-confirmatory.yml)의 세 단계, [컨테이너 bootstrap](../../src/hswm/development/container/bootstrap.sh), AGENTS의 필수 Python math compiler를 구체적인 호출로 추가했다. P1v4 shell runner 7개도 실행 가능한 파일이지만 현재 재가동 중이라는 근거는 없어 `activation unknown`으로 구분한다.
4. **S-5 탐색 상태가 결과보다 뒤처져 있다.** [지식 지도](HSWM_KNOWLEDGE_MAP_2026-09-13.md)와 closure v5의 open/partial 표기는 이후의 [S-5 결과](../../results/HSWM_S5_B0_B2_COMPARISON_2026-09-06.md)를 반영하지 않는다. 첫 결과 파일 deliverable은 완료됐다. 두 arm은 각 12 episode를 완료했지만 descriptive valid_seen은 모두 0/4, cohort와 budget도 달라 효능·순위·matched causal effect를 산출할 수 없다. 과거 bundle을 바꾸지 않고 이 감사의 successor 판독으로 연결한다.

반박된 의심도 보존했다. npm의 `files` 배열에 `bin`이 없다는 이유만으로 bin 누락을 주장할 수 없으며 실제 pack에는 포함된다. S2S 결과 parameter가 원본 mutable 배열을 그대로 반환한다는 의심도 copy/freeze와 손실 검증 경계를 대조한 뒤 결함으로 채택하지 않았다. 지식 지도 README/INDEX hash 두 개의 현재 불일치는 원래 commit의 246/246 일치를 확인했으므로 과거 기록 훼손으로 분류하지 않는다.

## 3. “증명 방식으로 개발”은 어디까지인가

[구성적 증명 round 1](../research/HSWM_CONSTRUCTIVE_PROOF_ROUND_1_2026-09-10.md)은 실제 정의·정리·반례를 갖고 있다. 단순히 계획만 있는 상태는 아니다. 그러나 정리의 전제가 실제 HSWM에서 성립하는지와 전체 구성이 그 전이를 실행하는지는 열려 있다. 서로 다른 작은 모델의 정리를 합쳐 전체 HSWM의 존재·효능 증명으로 부를 수 없다.

후속 작업은 [CR-0..7](../research/HSWM_CONSTRUCTIVE_REALIZABILITY_PROGRAM_2026-09-10.md)의 **정리 전제 → 실행 관측량 → 독립 검증 자료 → 반례/실패 조건**을 같은 구성에 연결해야 한다. FCL-2/FCL-8의 두 scale에서는 typed nesting뿐 아니라 macro-state 개입 효과와 학습·계보 보존을 함께 확인해야 한다. 이번 감사는 Lean을 다시 실행하거나 외부 수학 연구를 독립 검증하지 않았다.

## 4. 완료에 필요한 개발 순서와 종료 조건

| 작업 | 구체적 다음 구현 | 완료를 확인할 자료 |
|---|---|---|
| S2S 경로 연결 | 현재 model archive를 replay·intervention·integrity·task/final receipt와 native pilot에 연결 | 원본 수락/거부 대조, 독립 replay 검증, native CLI로 생성·재검증한 전체 pilot artifact. 궤적이 다른 backend는 별도 profile로 qualification하며 원본과 같다고 표시하지 않는다. |
| F1 전체 실행 | 정확한 원본 SQLite per-call schema·audit·원자적 item binding, idempotent spool, 기존 HTTP/meter 연결 | 중단·복구·중복 호출에서 재추론/이중 수락이 없고 원본 receipt 의미를 보존하는 native `run`. 미수락 ledger 초안은 근거가 될 수 없다. |
| F3 lifecycle | cache와 budget을 관리하는 단일 실행 경계, world→experience→lesson→evaluation | 여러 호출·중단·cache hit/miss에 걸친 전체 trajectory·총비용·terminal receipt. 한 호출 테스트만으로 종료하지 않는다. |
| 나머지 소유 코드 | confirmatory·문서·유지보수·설치 경로의 호출자별 전환 | 각 실행 명령의 native 대체와 필요한 외부 도구 의존성 명시. Python wheel/과거 재현 계약을 깨뜨리거나 몰래 제거하지 않는다. |
| 함수형 검증 | 직접 호출 설정 경계의 descriptor-safe capture, 실제 I/O·state owner 연결 검토 | getter를 실행하지 않는 typed refusal, 기존 수치 oracle 보존, 예외 목록을 늘리지 않은 검사. |
| 연구 D-4 | 사전 고정된 train/held-out 관계와 study schema, 실제 Permit-bound canonical journal을 하나의 후보에 연결 | outcome→credit→durable revision→새 held-out 행동이 같은 run에 있고 remove/restore/sham/shuffled 대조와 all-run 비용·실패가 남는 자료. |
| 통합·프랙탈 | D-4의 범위 한정 결론 뒤 같은 구성의 CR/FCL 합성 검증 | 두 bounded scale에서 wrapper·fixed-router·pairwise·topology-fixed·lineage-copy null과 구별되는 결과. |

언어 전환과 연구 검증은 별도 완료 조건이다. 모든 Python 파일 삭제가 연구 완성을 뜻하지 않는다. 외부 Lean·SDK·표준 suite를 새로 구현할 필요도 없다. HSWM 소유의 활성 조정·상태·오류 경계는 TS/Effect로 닫고, 필요한 외부 도구는 정확한 pin·입출력·검증 범위를 가진 경계로 사용한다. D-3에 따라 B0/B2는 secondary comparator이며 이 감사가 primary G1 성공 기준을 바꾸지 않는다.

[기존 연구 도구 조사](../research/HSWM_SCIENTIFIC_RESEARCH_TOOLING_2026-09-13.md)의 Inspect·Lean·Effect·그래프 도구를 우선 재사용한다. 이번 범위 감사에서 새 도구 설치를 요구할 결손은 확인하지 않았다. 필요한 것은 이미 있는 부품과 검증 자료의 실행 연결이다.

## 5. 검증 범위와 기록

이번에 pinned Node 24.13.0/npm 11.6.2로 `hswm-dev` runtime profile **54개 검사**, TypeScript/Temporal type check, Effect/functional 규칙 검사를 실행했다. 모두 통과했다. 별도로 getter 예외, F1 `run` 부재와 package bin 포함을 확인했다. 직전 **1,426 passed / 8 skipped**는 [모델 checkpoint](../../_research/native_migration_2026-09-13/model-transport-verification.v1.json)의 격리 실행 기록을 인용한 것이며 이번 전체 재실행 수치가 아니다.

[통합 감사 기록](../../_research/native_migration_2026-09-13/overall-scope-audit.v1.json)에 source hash·발견·반박·검사·작업별 완료 조건을, [KG bundle](../../ontology/development/HSWM_OVERALL_SCOPE_AUDIT_2026-09-13.v1.json)에 typed source/범위/발견/후속 작업 관계를 둔다. [질의](../../ontology/queries/hswm_overall_scope_audit_2026-09-13/)로 미완료 범위·발견 근거·작업 의존성을 읽을 수 있다. 이 projection은 로컬 기록이며 live KG나 원격 배포 상태를 관측한 증거가 아니다.

에이전트 검토는 같은 작업 환경의 보조 검토다. 사용자 판정·외부 평가자·독립 과학적 재현과 구분한다. 현재 설치된 원격 service, private GPU/model, 모든 동적 import/호출의 실행 상태, 검토에서 제외한 사용자 변경은 확인하지 않았다. 새 과학 결과가 아니므로 F1_R8 연구 결과 행을 추가하지 않는다.
