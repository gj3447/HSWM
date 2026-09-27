# CHU의 넓은 범위와 LLM 전용 HSWM — 소프트웨어 구조

2026-09-27 · `USER_PRIMARY_TARGET_DIRECTION`; 공학적 구체화는 `SECONDARY_AI`.

**CHU는 HSWM과 세계 모델들을 포함하는 더 넓은 계산가능 하이퍼우주의 개념이다.
HSWM은 그 안에서 LLM을 기본 계산 단위로 사용하는 하나의 하이퍼그래프 AI다.**
이것은 아래 사용자 발화의 재서술이며, 전체 CHU의 구현·물리적 실재·계산가능성 증명이 아니다.

## 사용자 원문

- [소프트웨어·ROM·메모리·프로그램 발화](sources/USER_PRIMARY_CHU_SOFTWARE_ARCHITECTURE_2026-09-27.txt)
- [CHU와 HSWM의 범위를 명시한 후속 발화](sources/USER_PRIMARY_CHU_HSWM_SCOPE_2026-09-27.txt)

두 발화를 별도 원문으로 보존한다. 후속 발화는 앞선 AI 답변에서 CHU를 HSWM의 메모리와
너무 가깝게 대응시킨 설명을 교정한다. 사용자 원문을 현재 코드에 맞게 축소하지 않는다.

| 사용자 진술 | 보존하는 의미 |
| --- | --- |
| “HSWM 은 llm 만을 위한 거고” | HSWM은 LLM을 기본 연산으로 사용하는 AI 구조다. 모든 계산·세계 모델의 일반 이름으로 확장하지 않는다. |
| “CHU 는 진짜 월즈모델도 포함이고 HSWM 도 포함” | CHU의 개념적 범위는 HSWM보다 넓으며, HSWM에 한정되지 않는 세계 모델도 포함한다. |
| “그런 추상적 개념적으로 거대한거야” | CHU 전체와 특정 유한 데이터베이스·메모리 인스턴스를 동일시하지 않는다. |
| “llm 은 그 하나의 실행단위 rom 같은거고” | LLM을 반복 사용 가능한 기본 처리 능력·실행 단위로 보는 컴퓨터 구조 비유를 보존한다. |
| “그 chu 에 있는 그 시멘틱 웨이트들이 프로그램” | 저장된 의미 관계가 실행을 조건화하고, 그 수정이 이후 동작을 바꾸는 소프트웨어 방향이다. |
| “코드실행도 하이퍼그래프 db 기반” / “llm 이 병렬적으로 동작” | 지속되는 그래프의 프로그램·상태를 국소 LLM 연산들이 읽고 실행하는 방향이다. |
| “문서라고는 없을거야” / “모든게 싹다 하이퍼그래프” | 코드·모델·인터넷·연결·문서를 그래프 중심으로 통합하는 AI-native 비전이다. 현재 달성됐다는 관측은 아니다. |

마지막 소프트웨어 축이 추가됐다는 것은 기록하지만, 앞선 두 범주를 새 범주표로 재정의하거나
비유의 세부를 사용자 직접 정의로 덧붙이지 않는다.

## 기존 HSWM에서 유지되는 것

[네 가지 기본 정체성](USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md)은 함께 유지된다.
하나의 AI, 하이퍼그래프 신경망 조직, LLM 기본 계산 단위, Semantic Weight 작동이다.
[큰 그래프가 상태이고 LLM은 국소 연산자](USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md)라는
정의와 [헌법](HSWM_CONSTITUTION_2026-08-20.md)의 world/self model·living harness·continuous learner
역할도 유지한다. **HSWM이 LLM 전용이라는 범위와 HSWM이 월드모델 역할을 한다는 정의는 양립한다.**
world model을 HSWM 밖의 배타적인 종류로 만들지 않는다.

LLM 전용의 공학적 해석은 **인지적 기본 연산이 LLM 함수라는 것**이다. 저장·인덱스·검증·
스케줄링·수치 도구까지 반드시 LLM으로 계산하라는 뜻으로 확대하지 않는다. 물리적 simulator를
호출·매핑할 수 있지만 그 simulator 자체가 자동으로 HSWM이 되지는 않는다.

## AI의 구체화와 경계

다음은 `SECONDARY_AI`다. 사용자 진술의 세부 구현을 이미 승인받았다고 소급하지 않는다.

1. CHU의 추상적 범위, 타입·실행 계약, 실제 유한 저장·실행 인스턴스를 구분한다.
2. ROM 비유에서 고정된 LLM parameter artifact와 이를 계산하는 실행을 분리한다.
   inference cache, 장기 그래프 상태, parameter 학습·교체도 다른 변경이다.
3. Semantic Weight의 저장 표현을 읽는 연산 의미가 있어야 프로그램으로 작동한다.
   모든 문장·근거·node가 실행 명령인 것은 아니다.
4. 문서는 그래프에서 생성하는 view로 다룰 수 있다. 기존 원문·역사 기록을 삭제하라는
   지시로 바꾸지 않는다. 모델 tensor와 binary artifact는 그래프에서 버전·digest로 참조할 수 있다.
5. CHU의 계산가능성에는 표현·step·관측·종료 범위가 필요하다. 이름이나 `axiom CHU : Type`
   선언만으로 이를 증명하지 않는다. 실제 우주 전체의 계산가능성도 따로 가정하지 않는다.

[원전 검토·계약·구현 연결](../research/CHU_HSWM_COMPUTATIONAL_ARCHITECTURE_2026-09-27.md)과
[출처 결속 KG](../../ontology/identity/hswm_core/CHU_HSWM_SOFTWARE_SCOPE_ONTOLOGY.v1.json)에
이 구분을 담는다. 과거 CHU·HSWM 기록과 실패 결과는 유지하고 새 해석의 출처를 덧붙인다.
기존 CR-0..7·FCL-1..8, 프랙탈 목표와 Hyperon 핵심 비교 의무는 그대로다.
