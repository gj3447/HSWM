# HSWM 헌법 — 현재 통합본

2026-10-24 · 대상 정체성 `USER_PRIMARY`, 이 문서의 구성·연결·공학 계약
`agent(codex) / SECONDARY_AI_SYNTHESIS`. 새로운 과학적 성공 판정은 없다.

**HSWM은 지속적인 Semantic Weight 하이퍼그래프를 AI 상태로 삼고, LLM이 필요한
국소 입력에서 의미 연산을 수행하며, 경험에 따른 관계·프로그램 수정이 다음 활성화와
예측·행동을 바꾸는 하나의 AI 구조다.** 같은 상태가 세계·자기모델, living harness,
계속학습기의 역할을 한다. 이 문장은 연결된 사용자 원문의 통합 재서술이다.

이 통합본은 [8월 헌법](HSWM_CONSTITUTION_2026-08-20.md)의 정체성·책임·권리·계보와
이후의 상태/국소 연산, CHU 범위, 분산 Map, 의미 위상 학습 요구를 함께 읽는 현재 진입점이다.
과거 헌법·원문·해시·실험 판정은 보존한다. ‘현재 진입점’은 AI가 추가한 세부 계약까지
사용자가 모두 비준했다는 뜻이 아니다.

## 필요한 조항으로 들어가기

| 질문 | 조항 | 그래프 진입점 |
| --- | --- | --- |
| 무엇이 AI이며 무엇이 지속되는가? | [1–3: 정체성·상태·관계](hswm/state.md) | `constitution-state` |
| 필요한 내용은 어떻게 여러 곳을 거쳐 찾는가? | [4–6: 국소 활성화·Map·원문](hswm/activation.md) | `constitution-activation` |
| 어떻게 예측·실행·학습하고 다음 행동을 바꾸는가? | [7–9: 월드모델·실행·학습](hswm/learning.md) | `constitution-learning` |
| CHU·프랙탈 합성·인류보편체는 어떻게 연결되는가? | [10–12: 합성·범위·철학](hswm/composition.md) | `constitution-composition` |
| 무엇이 구현됐고 어떤 증거가 더 필요한가? | [13–15: 평가·실현·개정](hswm/assurance.md) | `constitution-assurance` |

위 분할은 독자가 선택하는 문서 단위다. HSWM을 다섯 고정 subsystem으로 분해하지 않는다.
세부 지도는 각각의 파일과 기존 번들로 분산되어 있고, 주제 사이의 연결도 따라갈 수 있다.
목차 전체나 모든 번들을 매번 LLM에 넣을 필요는 없다.

## 조항별 이유와 구현 설계

2026-10-24 보강은 각 조항의 **해결할 문제 → 외부 원전과 적용 한계 → 구현 경로 → 현재
기능·후속 과제·확인 사례**를 해당 모듈에 둔다. 논문·표준 20종의 지정 판본을 확인했다.
외부 근거는 설계의 참고이고, HSWM의 사용자 정체성이나 실측 결과를 대신하지 않는다.

| 조항 | 해결할 문제 | 구현의 중심 |
| --- | --- | --- |
| [1. 지속 상태](hswm/state.md#1조의-이유문제구현) | 대화마다 경험 소실·서로 다른 상태 복사본 | 지속 graph와 국소 연산, 다음 사용의 판본 연결 |
| [2. 책임·계보](hswm/state.md#2조의-이유문제구현) | 동일 이름 혼동·동시 수정·책임 소실 | 원자 식별·owner·read-set·선행 revision |
| [3. 관계·W](hswm/state.md#3조의-이유문제구현) | 역할·조건 손실, 유사성과 인과의 혼동 | n항 관계·역할·순서·예외와 수정 대상 구분 |
| [4. 국소 활성화](hswm/activation.md#4조의-이유문제구현) | 무관 규칙 경쟁·필수 조건 누락 | 상황별 선택과 필수 역할·예외의 완전한 조립 |
| [5. 다단계 탐색](hswm/activation.md#5조의-이유문제구현) | 처음에는 이름도 모르는 후속 근거 누락 | 방문 결과에 따른 다음 선택·이동·중단 |
| [6. Map](hswm/activation.md#6조의-이유문제구현) | 요약의 조건 손실·원천 위치 상실 | 여러 해상도와 원문·판본·변환 조건 연결 |
| [7. 세계·자기모델](hswm/learning.md#7조의-이유문제구현) | 기억만 있고 예측 없음·추측의 사실화 | 예측·행동·관측·반사실의 구분과 시간 순서 |
| [8. 실제 실행](hswm/learning.md#8조의-이유문제구현) | 설명과 호출·결과의 단절 | 의미 역할·도구 판본·실제 I/O·실패 결속 |
| [9. 지속 학습](hswm/learning.md#9조의-이유문제구현) | 기록만 축적·잘못된 피드백 강화 | 연결된 사용의 자동 학습·owner 반영·다음 선택 |
| [10. 프랙탈 합성](hswm/composition.md#10조의-이유문제구현) | 재사용 곤란·합성 시 조건과 권리 손실 | 하위 계약·상위 전이·분리·계보 보존 |
| [11. CHU 범위](hswm/composition.md#11조의-이유문제구현) | 특정 모델·검색 방식과 개념의 혼동 | 이질적 모델의 역할·단위·좌표·시간 경계 |
| [12. 참여자 경계](hswm/composition.md#12조의-이유문제구현) | 연결을 권한으로 오인·철회 뒤 재사용 | 행위별 정책·집행·파생 자료의 출처 의존성 |
| [13. 평가](hswm/assurance.md#13조의-이유문제구현) | 구조 통과를 지능·효능으로 오인 | 주장별 근거·비교 조건·평가기 검토 |
| [14. 통합](hswm/assurance.md#14조의-이유문제구현) | 개별 성공이 한 경험으로 연결되지 않음 | 실제 read-set·실행·결과·다음 판본의 연결 |
| [15. 개정](hswm/assurance.md#15조의-이유문제구현) | 원문 drift·과거 근거 및 권위 혼합 | 새 source binding·이전 판본·이동 pin 보존 |

확인 사례는 해당 구현을 만들거나 바꿀 때 사용할 검사 설계다. 일상 사용마다 15개 조항의
검사·보고서를 새로 만들라는 절차가 아니다. 연결된 TRAIN 경로의 W 갱신은 기존 runtime이
자동 처리한다. 현재 기능과 아직 풀어야 할 문제의 상세 경계는 [14조](hswm/assurance.md#14-현재-실행-경로와-남은-통합-의무)에 둔다.

## 이번에 명시한 국소성

[이번 대화의 사용자 원문](sources/USER_PRIMARY_HSWM_MULTIHOP_RECONSTRUCTION_2026-10-24.md)은
필요한 것만 활성화하려면 여러 곳을 타고 가야 한다는 점과 전체 내용·헌법 보강 요청을 담는다.
**국소성은 홉 수가 작다는 뜻이 아니다. 각 단계의 선택·읽기·연산 범위가 과제에 맞게
제한되고, 경로를 따라 얻은 정보로 다음 선택을 바꾸는 성질이다.** 이 굵은 문장은 AI 해석이다.

[발표 11·17·34·36쪽 원문](sources/HSWM_SEMINAR_LOCAL_ACTIVATION_2026-10-21.json)도 연결한다.
MoE·국소 활성화의 사용자 주장, 헌법 조항, 현재 구현, 반례와 실측의 대응은
[검사 문서](../operations/HSWM_MULTIHOP_ACTIVATION_2026-10-24.md)에 명시한다.

탐색한 후보, 실제 읽은 원문, 실행에 유지한 문맥, 수정한 지속 상태를 구분한다.
짧은 경로·작은 문맥만을 목표로 필수 역할·조건·예외를 누락하지 않는다. 충분성·최소성은
과제·관측·허용 오차에 상대적인 평가 대상이며, 검색기가 처음부터 알고 있다고 가정하지 않는다.

## 내용에서 원문까지 실제로 이동하기

기존 `hswm-workspace`를 사용한다. 자세한 옵션·예외는
[CLI 사용법](../agent-rules/CLI.md#workspace-usage)에 있다.

```sh
src/hswm/effect-runtime/bin/hswm-workspace navigate constitution
src/hswm/effect-runtime/bin/hswm-workspace follow constitution --uid sym:AbstractNode:hswm-constitution-activation
src/hswm/effect-runtime/bin/hswm-workspace navigate constitution-activation
src/hswm/effect-runtime/bin/hswm-workspace read constitution-activation --uid sym:AbstractNode:hswm-constitution-activation
```

`follow`는 해당 지도에 명시된 목적지 하나의 바이트·UID·타입을 확인한다. `navigate`는
한 노드의 관계를 페이지 단위로 돌려주고, `read`는 선택한 출처의 완전한 본문과 해시를 반환한다.
반환 예산이 부족하면 잘린 원문을 완전한 문맥으로 표시하지 않는다. 이 읽기 도구는
내용을 찾는 실제 구현이며, native 의미 실행·W 갱신은 [별도 기존 경로](hswm/learning.md)를 따른다.

## 권위와 개정

사용자 원문, AI의 해석, 구현 관측, 형식 증명, 독립 효능은 각각의 지위를 유지한다.
정체성의 의미를 바꾸는 새 사용자 결정은 원문과 선행 결정의 관계로 추가하고, 공학적 수정은
해당 코드·문서·검사와 Git 이력으로 남긴다. 목표·판정 기준이나 실패 결과를 현재 구현에
맞춰 축소하지 않는다. 세부 규약은 [15조](hswm/assurance.md#15-개정과-다음-사용)에서 읽는다.

문헌·구현 설명을 보강한 현재 연결은 `ontology/workspace/constitution/*.v2.json`을 사용한다.
최초 통합본과 v1 번들의 원래 바이트는 Git `b7ac03c302749f5519b7387fd6b5c9364e71a673`에
보존돼 있다. v2의 모듈 노드는 그 선행 Git 판본·번들 경로·hash를 기록한다. 현재 문서를
과거 hash에 맞춘 것으로 가장하지 않고, 과거 문서가 필요하면 그 Git 판본에서 함께 읽는다.
