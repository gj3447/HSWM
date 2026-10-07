# Optimization evaluation reference

이 문서는 R1–R6의 평가 보강이며 일곱째 법칙이 아니다. `OPTIMIZATION.md`와
기존 owner·권한·출처 규칙을 대체하지 않는다. “CHU 병목 없이 완전히 최적화”는
사용자 지향이며, 달성 사실·효능·학습된 W의 주장으로 읽지 않는다.

## Context evaluation

R1/R4/R5/R6을 적용해 분할·병합·연결을 바꿀 때, 먼저 작업의 입력, 허용 effect,
관측·출력, 오류 예산, 출처·권한·예외와 다음 학습에 선언한 상태를 적는다. 고정 자원·작업
예산 안에서 개선을 비교하면 `hswm-optimization-evaluation` 작업으로 Comparison contract를
선택해 끝까지 읽는다. 표현 정리는 그 계약에서
admission, 출력, effect, provenance 및 선언한 미래 학습 조건을 보존한다는 목표와 근거가
있을 때만 후보가 된다. topology/연결 변경도 이 기준으로 분류하며, 보존 여부가 unknown이면
의미 변경·보존·개선을 단정하지 않는다. 실제 W는 outcome 전 선택 trace, 독립 outcome, 기존 변경
계약을 따른 revision, 다음 선택 변화가 있을 때만 논할 수 있다. 현재 task routing은 선언적
선택이지 learned dispatch가 아니다.

## CLI evaluation

R2/R3의 CLI는 기본 실행 인터페이스이며 HSWM 성립의 필요조건은 아니다. launcher·실제 버전,
입출력 계약·exit/failure/timeout과 전제를 해당 작업에 결속하되, CLI 경로나 그래프 참조만으로
실행 권한이나 성능을 추론하지 않는다. 비교 시 실행 단계별 queue waiting, 서비스 시간,
critical path와 end-to-end 결과를 함께 본다. p95들을 더해 전체 지연을 만들지 않으며, 병목이
다른 단계로 옮겨간 경우도 보고한다.

## Comparison contract

이 절은 상세 비교가 필요한 경우의 참조 계약이며 자동 활성화하지 않는다. 새 승인 게이트,
런타임 또는 의무 ledger를 만들지 않는다.

1. **비교 대상.** baseline과 후보에 task·입력 분포·동시성·오류 예산·허용 effect·평가
   시점·환경을 선언한다. 고정 자원 벡터와 측정 자원 벡터를 구분한다. 예: 전자는 상태/활성
   노드·관계 예산, 동시성 상한, 읽기·실행 예산이고, 후자는 실제 CPU/GPU·메모리·토큰·I/O,
   queue wait, 지연이다. 노드 수만 같다는 사실은 같은 크기의 CHU나 동등 비용을 뜻하지 않는다.
2. **보존 대 개선.** syntax/직렬화/문서 배치는 작업 계약을 보존하는지 확인한다. admission,
   출력, effect, provenance, declared future learning 중 하나라도 달라지면 의미 보존으로
   표시하지 않는다. 판단을 바꾸려는 W·관계·선택 정책 수정은 학습/의미 변경 후보로
   분리하고, 독립 outcome 없이 개선이라고 결론내리지 않는다. topology 수정도 표현 보존인지
   의미 변경인지 목적과 관측으로 분류하며, 구조가 달라졌다는 사실만으로 의미 변화를 단정하지 않는다.
3. **측정.** 각 단계의 도착·시작·종료를 가능한 범위에서 구분해 queue waiting, service,
   critical path, end-to-end 성공·오류·취소를 보고한다. 병목 순위와 이동을 함께 적고,
   missing data·unknown은 0으로 채우지 않는다. 합산 p95는 end-to-end p95의 대용물이 아니다.
4. **동치 범위.** task-relative 동치는 선언한 interface와 관측/개입 범위에 한정한다.
   [HSWMOperationalQuotient.lean](../../formal/HSWMOperationalQuotient.lean)의 205행과 216행은 출력만 같은 상태 또는 현재
   visible bit만으로는 exact learning abstraction이 안 될 수 있다는 조건부 형식 지원이다.
   실제 HSWM, 자연어 의미, scheduler 순서 또는 전역 최적화의 새 증명은 아니다.
5. **판정.** 결과는 `preserved`, `changed`, `unknown`을 구분한다. 병목 없음·완전/전역 최적화는
   목적함수, 제약, 허용 대안 집합과 그 범위의 증명이 있을 때만 말한다. 유한 표본의 전수 측정도
   측정하지 않은 분포·동시성·실패 경로에 대한 보편 결론은 만들지 않는다.
