# 7–9조: 월드모델·실행·학습

[통합 헌법](../HSWM_CONSTITUTION.md)의 선택 가능한 한 부분이다. 사용자 목표와 현재
공학적 실현·검증 범위를 구분한다. 아래 구성은 `SECONDARY_AI`다.

## 7. 세계·자기 상태에서 예측과 관측으로

HSWM의 지속 관계 상태는 세계와 자신의 구성·능력·도구·실패·계보를 함께 표현한다.
국소 연산은 선택한 상태에서 결과를 예측하고 행동을 제안·실행하며, 이후의 관측과 대조한다.
예측된 미래, 관측한 사실, 반사실 분기, 불확실성을 구별한다. 환경 결과를 미리 입력한 뒤
예측에 성공했다고 기록하지 않는다.

Wolfram형이라는 역할은 관계 상태·국소 rewrite·인과 계보에 있다. Wolfram 물리학,
causal invariance나 우주 전체의 재현이 증명됐다는 뜻이 아니다. 원문은
[8월 헌법 5조](../HSWM_CONSTITUTION_2026-08-20.md#5-wolframian-evolving-hypergraph-월드모델),
구현 질문은 [실현 가능한 구조](../../research/HSWM_IMPLEMENTABLE_ARCHITECTURE_2026-09-27.md)를 따른다.

## 8. 의미와 실제 실행을 결속한다

그래프에 저장된 프로그램은 입력·출력, 역할, 적용 조건·예외, 실제 tool/LLM,
오류·중단·복구와 owner를 연결해야 한다. 설명서를 조회한 것과 도구를 실행한 것은 다른 사건이다.
사용법·모델·프로그램 판본과 실제 전달된 문맥을 실행 결과에 연결한다.

현재 구현의 책임 분리는 다음과 같다.

| 경계 | 기존 구현·계약 |
| --- | --- |
| 원자·읽기/쓰기 집합·판본 | `canonical-atom-v2-schema.ts`, `canonical-atom-v2-durable-runtime.ts` |
| 역할 있는 LLM 의미 실행·outcome·수정 제안 | `canonical-atom-v2-llm-semantic-runtime.ts` |
| 선택된 문맥·실제 전송·응답 | `semantic-context-runtime.ts`, `semantic-context-presentation-domain.ts` |
| 정책 초기화·선택·결과 기반 제안 | `semantic-context-activation-runtime.ts` |
| admission·영속화·재개방 | 기존 owner writer와 durable state journal |

TS/Effect는 버전 관리되는 해석기와 I/O 경계다. 일상 학습은 그래프 프로그램·관계·정책
판본을 바꾸는 것이며 매번 TS 코드를 고치는 것으로 대체하지 않는다. 도구·규칙·실제 개발이
서로 피드백하는 요구는 [기존 tool-harness 계약](../../operations/HSWM_RESEARCH_WORKFLOW.md#tool-harness)을 잇는다.

## 9. 결과가 다음 활성화와 의미 구조를 바꾼다

필요한 연결은 다음과 같다. 정해진 여섯 프로세스를 만들라는 의미가 아니다.

```text
문맥과 선택 판본 → 실제 의미 전이 → 실행에 결속된 관측·실패·비용
→ 의미·관계·활성화 정책 수정 후보 → owner-valid 영속 revision
→ 별도 실행에서 해당 revision을 읽는 다음 선택·예측·행동
```

사용자 요구에는 연결의 강화·약화, 의미 기여가 적은 중복 정리, 의미에 맞는 배치,
노드·허브의 생성·제거가 포함된다. [자동 W·위상 수정 원문](../USER_PRIMARY_HSWM_SEMANTIC_TOPOLOGY_OPTIMIZATION_2026-10-12.md)을
보존한다. scalar 계수만 갱신한 실험을 이 요구 전체의 완성으로 세지 않는다.
국소 활성화 정책 자체도 경험으로 바뀌는 대상이다.

평가는 부모 상태, 같은 관측만 추가한 상태, 의미 수정 상태를 구별한다. 피드백의 작성자와
관측 범위를 남기며, 자기평가를 독립 환경 관측으로 바꾸지 않는다. 같은 피드백의 중복 적용,
낡은 read-set, 동시 수정 충돌, 소유자 변경, restore를 기존 계약에서 검사한다.
근거가 부족한 제안은 거부·보류할 수 있고 정당한 no-op을 가짜 revision으로 꾸미지 않는다.

완료 기준은 [실행→피드백→갱신→다음 사용 계약](../../operations/HSWM_RESEARCH_WORKFLOW.md#consumer-integration-completion)이다.
국소 실험은 [10월 18일 활성화 진단](../../operations/HSWM_LOCAL_ACTIVATION_DIAGNOSIS_2026-10-18.md)에
실제 개선과 제한이 함께 보고돼 있다. 이 헌법 통합 작업이 그 실험을 새로 실행했거나
운영 상태에 적용했다는 뜻은 아니다. 자연 과제의 장기 자기개선과 통합 효능은 별도 검증 대상이다.
