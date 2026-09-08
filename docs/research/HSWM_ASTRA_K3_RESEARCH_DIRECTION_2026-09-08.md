# Astra·K3 이후 HSWM의 연구 방향

2026-09-08 · `SECONDARY_AI / RESEARCH_DIRECTION_PROPOSAL`.
검토 기준: HSWM `87e381c`, GPT-6 Astra 공식 자료, Kimi K3 기술보고서 v1.
새로운 성능 실험이나 사용자에 의한 상세 설계 확정이 아니다.

**판단:** 최고 모델의 성능을 온전히 사용하는 기능 cell 위에서, 실제 경험이 다음 과제의
관찰·실행·검증·구성을 바꾸는 지속 학습을 만들어야 한다. 모델 교체 뒤에도 유효한 지식과
조건부 행동이 남는지 확인한다. KG·메모리·다중 에이전트의 존재만으로 차별성을 주장하지 않는다.

[Constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 token-native LLM-function
macro-neural HSWM을 유지한다. evolving hypergraph가 living harness·world/self model·learner의
역할을 함께 하는 목표다. [적응 연구 전략](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)에
따라 그 목표를 실현하는 현재 알고리즘과 모델·도구는 교체할 수 있다.
개념적 변화는 **일반적인 agent 기능의 유무보다 경험에 의한 지속 상태의 추가 효과에
개발과 판별을 집중한다**는 것이다. FCL-1..8과 기존 실패·미판정 상태는 유지한다.

## 공식 자료에서 확인한 흐름

### Astra: 추론뿐 아니라 장기 실행과 문맥 복구가 발전한다

OpenAI의 발표 표에서 GPT-5.6 Sol→GPT-6 Astra는 Terminal-Bench 4.0의
37.3→57.9, Terminal-Bench Science 0.1의 22.4→64.6을 보고한다. 모든 항목에서 일률적인
상승이나 다른 모델 대비 전면 우위가 있는 것은 아니다. 표는 reasoning effort별 최대치이며
연구/API 환경의 system prompt와 도구가 제품 환경과 다를 수 있다.
[공식 발표와 평가 주석](https://openai.com/index/gpt-6-astra/).

같은 발표는 Codex에서 context window 사이 노트를 남기고 이전 메시지·도구 결과를 검색하는
실험 기능을 설명한다. 따라서 ‘긴 작업의 실패를 기억한다’도 독점적인 HSWM 기능이 아니다.
[공식 발표의 Coding 절](https://openai.com/index/gpt-6-astra/).

Astra는 약 105만 token context와 reasoning effort 제어를 제공한다.
[모델 명세](https://developers.openai.com/api/docs/models/gpt-6-astra).
비동기 tool calling·실행 중 steering·대화 중 effort 변경을 지원하지만, 도구 실행과
진행 중 작업 관리는 application의 책임이다.
[공식 모델 가이드](https://developers.openai.com/api/docs/guides/latest-model).

### K3: KG·다중 harness·지속 환경·검증까지 훈련 대상이다

Kimi K3는 공개 가중치의 native multimodal MoE이며 약 100만 token context를 제공한다.
공식 표의 agent 평가는 서로 다른 harness와 일부 다른 환경을 사용하므로 Astra 발표표와
숫자를 단순 대조하지 않는다. K3의 Terminal-Bench 2.1과 Astra의 4.0은 같은 시험이 아니다.
[공식 저장소와 평가 주석](https://github.com/MoonshotAI/Kimi-K3).

기술보고서에서 HSWM과 직접 겹치는 내용은 다음이다.

- §4.2.1: 도구·prompt·context 관리·skills·memory·subagents를 조합한 여러 harness로 RL한다.
- §4.2.2: 재귀적으로 확장한 개념 KG에서 자료를 찾아 학습 과제를 합성한다.
- §4.2.5–6: 여러 날에 걸친 모의 환경과 상태 변화를 다루고, 독립 verifier와 숨겨진 시나리오로
  산출물·최종 환경 상태를 평가한다.
- §4.1.2: 과제별 token budget과 effort 수준을 훈련에 반영한다.

이는 K3 훈련 방법에 대한 저자 보고다. 배포된 모델이 사용자별로 같은 KG를 계속 학습한다는
증거도, HSWM의 학습 효능 증거도 아니다.
[Kimi K3 기술보고서 v1](https://arxiv.org/html/2607.24653v1).

**추론:** foundation model과 그 실행 환경이 함께 발전한다. 단순 분해·검색·반성·기억을
수작업으로 많이 붙이는 HSWM은 그 실행 비용 때문에 오히려 뒤처질 수 있다. 지속성이나
회사 데이터 접근도 다른 도구가 구현할 수 있으므로, 그것만으로 지속적인 경쟁 우위는 아니다.

## 현재 코드가 실제로 하는 것

활성 기준은 `src/hswm/effect-runtime/src/`다. 과거 Python 문서를 현재 기능 근거로 대체하지 않는다.

| 현재 경로 | 확인한 범위 | 부족한 부분 |
| --- | --- | --- |
| `adaptive-domain.ts` | 최대 8개 scalar 문맥, 64개 feature의 성공 성향·비용 기반 선택과 유한 guard 합성 | 행동 뒤 외부 상태나 자신의 능력 변화를 예측하는 world/self model은 아님 |
| `adaptive-runtime.ts` | versioned atom·trajectory·outcome 저장, 관계 갱신, 조건에 따른 read-set 추가 | 국소 분화는 기존 member를 재사용. 자유로운 구성 발명이나 독립 credit의 증거가 아님 |
| `adaptive-runtime.ts`의 사후 feedback | root 선택 관계에 Boolean 평가 반영 | 실제 내부 단계·출력과 결속한 명시적 평가 API 미완성 |
| `adaptive-executor.ts`의 직접 LLM 호출 | 한 user message를 Chat Completions로 보내고 content 문자열을 취함 | provider의 멀티턴 tool loop·reasoning state·steering·usage를 보존하는 session 경로가 없음 |

command cell을 통해 외부 agent를 실행할 수 있다는 사실과 직접 LLM 경로의 한계는 구분한다.
모델 이름만 Astra/K3로 바꿔도 native agent의 모든 능력이 연결된다고 말하지 않는다.
K3의 공식 사용법은 멀티턴 도구 호출에서 반환된 assistant message의 reasoning/tool 내용을
보존하도록 요구한다. provider 세션 상태를 임의의 텍스트 요약으로 평탄화하면 손실될 수 있다.
[K3 Model Usage](https://github.com/MoonshotAI/Kimi-K3#6-model-usage).

## 개발 우선순위

**1. 유능한 기능 cell의 범위를 먼저 확보한다.** 모델이 코드·도구·관측을 함께 다루는
의미 있는 작업을 수행하게 한다. 근거 없이 한 추론을 여러 약한 호출로 잘게 나누지 않는다.
cell 분할은 별도 입력·산출물·검증이 있을 때 선택한다. 기존 공식 SDK/agent 실행 표면을
우선하며 HSWM 연결부는 task·권한·세션·진행·산출물 참조·비용·취소의 얇은 typed 계약으로 둔다.
새 session 계약은 아직 설계 제안이며 이번 검토에서 구현·호출하지 않았다.

**2. 관계가 ‘무엇을 예상하며 무엇을 더 읽을지’를 학습하게 한다.** 같은 schema 안의
관계·조건·parameter·trajectory·outcome atom에 다음을 결속한다: 어떤 상태에서, 어떤 근거를
읽고, 어떤 행동을 하면, 어떤 외부 변화가 예상되며, 어떤 관찰로 틀렸음을 알 수 있는가.
예상 결과와 실제 결과의 차이로 조건·근거의 유효성·다음 관측·행동을 수정한다.
언어 설명을 추가하는 것만으로 예측 모델이 생겼다고 하지 않는다.

현재 guard와 read-set 학습을 발판으로 삼되, 새 관측 항목을 발견하는 것과 이미 선언된 enum
field를 추가로 선택하는 것을 구분한다. 관측의 수치·불확실성·버전이 필요한 Reluvator 과제는
Boolean 몇 개로 정보를 잃는지 먼저 확인한다. 최신 모델 자체에도 학습된 세계 지식이 있으므로
동일 모델에 이력을 직접 제공한 대조와 비교한다.

**3. 근거와 전술을 모델 버전에 맞춰 유지·수정·폐기한다.** 확인한 API 계약이나 calibration
버전은 외부 사실로 관리하고, ‘이 모델·도구·문맥에서 이 접근이 유용했다’는 조건부 전술로
관리한다. 모델을 바꿀 때 사실이 모두 사라지거나 옛 성공 점수가 무조건 승계되지 않게 한다.
현재 모델·harness에서 적은 실제 사례로 다시 보정하고 오래된 관계는 비활성화할 수 있어야 한다.
이는 별도 subsystem 목록이 아니라 같은 graph의 atom 역할과 갱신 시간척도에 대한 제안이다.

**4. KG를 판별할 질문을 만드는 데 쓴다.** 실패한 관계, 충돌하는 근거, 검증되지 않은 전제에서
다음 확인 과제를 제안한다. 제안자가 만든 정답을 그대로 독립 outcome으로 쓰지 않는다.
실제 외부 관찰이나 분리된 평가용 사례가 이 제안을 반박할 수 있어야 한다. K3의 task synthesis와
verifier 분리에서 채택할 실용적인 방향이다. 기존 문헌 KG의 node 수 증가는 학습 결과가 아니다.

추론·코딩 담당을 Astra/K3 이름만으로 고정하지 않는다. 같은 과제에서 필요한 정확도·지연·
실제 총비용을 보고 model/effort를 선택한다. 추가 검토나 병렬 agent도 기대되는 이득과 비용을
측정한다. 단일 모델의 self-review나 서로 다른 모델의 동의만으로 독립성을 주장하지 않는다.

## 실사용 장면과 가벼운 비교

Reluvator의 예시 가설은 ‘센서·calibration·schema 버전 조합이 바뀌었을 때 어떤 검사와
원본 관측이 먼저 필요한가’다. 계약 검사를 통과한 경험을 3D 추론 정확도로 보상하지 않는다.
read-only replay 가능한 실제 실패 하나에서 근거 선택→원인 가설→관측→관계 수정이 이어지고,
다음 비슷한 변경에서 누락 검사를 줄이는지 본다. 현장 장치 조작을 요구하는 예시는 아니다.

ICE에서는 지난 반례가 실패한 정확한 정의역·경계조건을 새 질문의 어떤 가정에 적용할지,
게임에서는 재현되는 버그의 플랫폼·상태 조건에 따라 어떤 검사를 앞당길지 비교할 수 있다.
모두 **앞으로 수행할 예시**이며 관측된 효능이 아니다. 현재 ICE의 배타적 root guard에서는
후보 간 선택 개선을 식별하기 어렵다는 [소비자 평가](../operations/HSWM_ICE_CONSUMER_FEEDBACK_2026-09-08.md)를
출발점으로 삼는다.

실사용을 계속하면서 일부 동일 snapshot 과제만 별도로 비교한다. 각 모델 안에서 먼저
① 그 모델의 native agent + 동일 원문·이력, ② 갱신을 끈 HSWM, ③ 학습하는 HSWM을
같은 예산으로 비교한다. native agent가 가진 memory·context·skills를 억지로 제거하지 않는다.
모델별 제품 조건 차이가 크면 공통 API 조건의 비교와 native 제품 전체의 비교를 따로 보고한다.

특히 **새 모델 단독과 이전 모델+HSWM**도 같은 자원 한도에서 비교한다. HSWM 개선보다
모델 업그레이드가 저렴하고 효과적인지 보되, 이것은 모델과 HSWM 효과가 섞인 투자 대안 비교다.
학습의 인과적 효과는 앞의 같은 모델 내 비교로만 판단한다.

처음에는 종료한 과제의 재현·평가 가능성을 확인하는 소수 사례로 충분하다. 이후에만 held-out
품질·유효한 반례·조건 누락·총 token/시간·검토/통합 비용을 반복 측정한다. 이력 제공량·학습
비용도 맞춘다. 차이가 생긴 관계를 지우거나 복원하고, 같은 이력을 평문으로 주었을 때와
비교하여 typed relation 구조 자체의 기여를 좁혀 본다.

평가가 충분히 민감한데도 이득이 없으면 해당 scoring·분화·구성 기전을 교체한다. 소수 사례나
과제 포화·측정 불능은 `UNDERDETERMINED`로 남긴다. 규모나 KG 크기를 늘려 실패를 구제하지 않는다.
상위 HSWM 구성도 [FCL의 wrapper 대조](HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md)가 필요하다.
하위 기능의 실사용을 막는 새 승인 절차나 과학적 gate를 추가하는 제안은 아니다.

이 검토는 실제 모델 호출·학습·가중치 다운로드·배포를 수행하지 않았다. 모델별 API의 사용
가능 여부와 정확한 snapshot·요금은 실행을 시작할 때 다시 확인해야 한다. 여기의 결정은
최신 모델을 사용한 경험 기반 관계 학습에 집중하자는 연구 제안이며 효과는 계속 미판정이다.
