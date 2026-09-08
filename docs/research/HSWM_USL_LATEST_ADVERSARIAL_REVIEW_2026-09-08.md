# 최신 USL 적대적 검증 — 관측 수정 이후

2026-09-08 로컬 USL `0.3.0`을 다시 검사했다. 관측 포맷은 `usl-program-observation/v2`,
새 compact 전달 포맷은 `usl-agent-context-compact/v1`이다. Git 메타데이터가 없어 파일 SHA-256으로
검토 대상을 고정했다. HSWM의 대상 정체성과 기존 연구 판정은 변경하지 않는다.
USL과 compact 출력은 참조·전달 인터페이스이며 인지나 학습 판정이 아니다.

판정: **기존 두 수정은 유지됐고, 별도의 KG 투영 API에서 출처 결속 결함 1건을 새로 재현했다.**
전체 테스트 105개와 TypeScript 타입 검사는 통과했다. 이 결과가 모든 경계의 완전성을 증명하지는 않는다.
검토 중 구형 레코드 투영의 `src/project.ts`와 `test/project.test.ts`가 다른 작업에서 변경됐다.
해당 변경 뒤 투영 검사 4개와 타입 검사를 추가 실행했다. 아래 P2의 대상은 별도 파일인
`src/language/project.ts`이며 검사 동안 그 파일의 hash는 유지됐다.

## P2 — KG 투영 API가 다른 원문을 plan의 출처로 기록함

위치: USL `src/language/project.ts:20`의 `toSemanticBundle` 및 `:30`의 source hash 계산.

원문 A를 compile한 plan에 반대 의미의 원문 B를 `options.source.text`로 전달하면,
API가 성공하며 **KG 노드 설명은 A, source_sha256은 B**인 bundle을 만든다.
예제의 설명 `code implements the target`은 그대로인데 반대 원문의 hash가 출처로 기록됐다.
같은 plan A / source B를 `observeProgram`에 전달한 대조 호출은 불일치를 거절한다.

이는 임의 JSON의 서명 부재를 다시 지적한 것이 아니다. 공개 투영 함수가 자신이 받는 plan과
출처 원문 사이의 일관성을 검사하지 않아, 실제 생성한 산출물 안에서 출처를 잘못 결속하는 문제다.
CLI의 source 파일 경로는 같은 원문을 compile하고 project에 넘기므로 이 반례가 그 경로에서
발생한 것은 아니다. bundle의 외부 게시나 실제 KG 오염도 실행하지 않았다.

수정 기준:

1. source를 받으면 그 원문을 compile하고 입력 plan과 USL plan digest가 같은지 투영 전에 검사한다.
2. 투영에 사용할 plan과 원문 값을 고정해 출처 식별자를 같은 입력에 결속한다.
3. 직접 API에서 plan A / source B는 거절하고, plan A / source A는 기존 결과를 보존하는 회귀 검사를 추가한다.

[재현 프로그램](../../_research/usl_adapter/latest_projection_audit_2026_09_08.ts) ·
[결과](../../_research/usl_adapter/latest_projection_audit_2026_09_08.json).

## 유지된 수정과 새 경계 검사

| 경로 | 실제 확인 | 판정 범위 |
| --- | --- | --- |
| sourceText 관측 | 최초 원문 값 고정과 옵션 변경 회귀 검사 통과 | 기존 원문 혼합 버그 수정 유지 |
| v2 관측 검증 | 바깥 digest를 재계산한 실행 상태·resolver 호출 수 조작을 USL·HSWM 모두 거절 | 기존 검증 누락 수정 유지 |
| compact 맥락 | 다자 역할·의미·경로 복원 정보 보존, 정확한 기존 digest만 UNCHANGED, 의미 반전은 FULL | 맥락 전송 최적화. 실제 토큰 청구나 모델 성능 결과는 아님 |
| compact 예산 | callback이 옵션을 바꿔도 고정한 예산 유지, 잘못된 입력은 typed error | 검사한 입력에서 경계 유지 |
| resolver | 파일/Git 라인 범위 hash, commit pin, redirect byte 제한, timeout 확인 | 로컬 임시 파일·저장소와 주입 fetch 검사 |
| 관측 저장 | stale baseline 쓰기 거절과 기존 파일 바이트 보존 | 협력적 CAS 경로 검사 |

compact와 resolver 검사에서 새 중대 결함은 재현하지 못했다. 호스트 파일시스템에 대한
기존 trust_host 한계나 알려진 TOCTOU를 새 결함으로 다시 세지 않는다.

## 통합 계약 차이 — contentHash

USL의 v2 스키마는 contentHash에 비어 있지 않은 문자열을 허용하지만, HSWM은 raw 64자리
SHA-256 hex pin을 요구한다. `contentHash: "content"`인 내부적으로 일관된 보고서는 USL에서는
유효하지만 HSWM에서는 거절된다. 현재 실제 resolver와 표본은 hex를 사용하므로 정상 연결에는
문제가 없었다. 이 차이는 권한 우회가 아니라 **지원하는 입력 범위의 차이**다.

USL에서 hash 알고리즘·표현을 계약으로 좁히거나, HSWM의 제한된 입력 범위를 명시해야 한다.
임의 문자열을 새로 hash해서 기존 원문 hash인 것처럼 연결해서는 안 된다. 미래 timestamp의
경우 USL은 형식을 검사하고 HSWM은 freshness 정책에 따라 UNRESOLVED로 처리했으며,
이는 의도된 책임 분리다.

## 근거

- [소스 스냅샷](../../_research/usl_adapter/latest_source_snapshot_2026-09-08.json)
- [전체 테스트·타입 검사 기록](../../_research/usl_adapter/latest_baseline_verification_2026-09-08.json)
- [관측·HSWM 통합 재현](../../_research/usl_adapter/latest_observation_audit_2026_09_08.json)
- [compact 재현](../../_research/usl_adapter/latest_compact_audit_2026-09-08.json)
- [resolver·저장 재현](../../_research/usl_adapter/latest_resolver_audit_2026_09_08.json)

검사에서 USL 소스를 수정하거나 의존성을 설치하지 않았다. 기존 감사 기록은 당시 상태로
보존하고, 이번 결과를 새 문서와 재현물로 추가했다.
