# HSWM 심층 연구 — 의미 실행, 반례 기반 갱신, 국소 상태와 합성

2026-09-22 · `SECONDARY_AI_RESEARCH_SYNTHESIS_AND_EXPERIMENT_DESIGN`
새 모델 실험: 0. 문헌의 성과, 기존 실험의 관측, 아래의 설계 추론을 구분한다. CR-0..7 및 FCL-1..8은 승격하지 않는다.

**현재 가장 정보 가치가 높은 순서는 올바른 관계의 국소 실행 → outcome을 통한 관계 교정 → 능동 국소 읽기 → 결합 출력과 재귀 합성이다.** 먼저 한 관계가 정확하게 작동하고 실제 경험으로 교정되는 조건을 찾아야 한다. 현재 기록은 revision이 commit됐어도 네 semantic field와 평가 projection이 그대로인 경우다. 이를 더 큰 그래프로 확대해서 의미 학습의 근거를 얻을 수는 없다.

이번 연구는 [9월 22일 Jev 그래프 정리](HSWM_JEV_GRAPH_ENGINEERING_2026-09-22.md)의 W1–W5를 구체적인 실패 원인, 대안 알고리즘, 대조군과 중단 조건으로 전개한다. 단순 문헌 유사성이 아니라 **어느 가정이 HSWM에서 새로 검증되어야 하는가**를 채택 기준으로 쓴다.

## 1. 그대로 유지하는 대상과 이번 변화

[헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md), [기본 정체성](../canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md), [상태·국소 연산자 정의](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md)를 함께 유지한다. HSWM은 **하나의 큰 AI**, **하이퍼그래프 신경망 조직**, **LLM을 기본 계산 단위로 사용**, **하이퍼그래프 Semantic Weight를 통해 작동**하는 대상이다. 큰 그래프가 AI 상태이고 작은 국소 입력을 받은 LLM이 내부 신경 연산을 수행한다. API 호출 수는 이 정체성의 정의가 아니다.

living harness, world/self model, continuous learner는 같은 evolving graph와 동역학의 관점이다. 아래의 읽기·실행·후보 생성·평가·revision은 그 상태에 대한 연산 역할이다. 새 고정 subsystem 분해를 제안하지 않는다. 각 canonical atom은 schema-relative responsibility owner 하나와 typed reference, provenance, revision 계보를 가진다. owner나 구조 검증은 참, 실행 허가, 인과적 credit을 대신하지 않는다.

**개념적 변화:** Semantic Weight를 저장하는 것, 그 의미를 LLM이 실행하는 것, outcome으로 수정하는 것, 수정이 미래에 유용한 것을 각각 식별한다. 이는 [기존 정의](HSWM_SEMANTIC_WEIGHT_DEFINITION_AND_HYPERGRAPH_2026-09-14.md)와 [이론의 전이·학습 보존 구분](HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md)을 실제 연구 순서에 적용한 것이다. 새로운 실현 증명은 아니다. [목표 유지·방법 교체 원칙](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)에 따라 실패는 해당 기전의 기록으로 남긴다.

## 2. 현재 관측이 실제로 식별하는 것

[코드·근거 감사](artifacts/hswm_deep_research_2026-09-22/mechanism-audit.md)는 source hash와 코드 위치를 함께 기록한다. 아래 숫자는 새 실험이 아니라 [9월 21일 결과](../../results/HSWM_JEV_PRINCIPLES_2026-09-21.md)의 재검토다.

| 관측 | 식별할 수 있는 결론 | 아직 구분되지 않은 원인 |
|---|---|---|
| 네 번의 commit에서 semanticText/disposition/uncertainty/exceptionRefs 변화 없음 | 이 실행은 의미 교정 효과를 측정하지 못함 | 피드백 형식, 한 번의 갱신, 추론 능력, 프롬프트·serving 제약 중 무엇이 no-op을 만들었는가 |
| learned와 evidence-only의 모델 입력/request가 동일 | 두 arm의 수치 차이를 의미 갱신에 귀속할 수 없음 | 동일 요청의 출력 변동 원인 |
| 정답 관계를 넣은 direct oracle도 27/48 | 이 frozen 모델·프롬프트·단일 토큰 readout의 실행 충실도 부족 | 역할 해석, 조합 연산, 출력 제한, tokenizer/서버 설정 각각의 기여 |
| direct 480/480 형식 유효, JSON 389/480 유효 | 형식과 의미 정확도를 따로 측정해야 함 | 자기보고 확률과 답의 불일치가 얼마나 의미 오류와 겹치는가 |
| 0 temperature/seed에서도 동일 요청의 예측 변동 | 한 번의 호출 차이로 mediation을 판정할 수 없음 | scheduling, kernel, batch, 기타 serving 상태 |

여기서 oracle은 **정답 관계 문장을 제공한 조건**이다. 정답 실행기나 학습된 decision head가 아니다. `max_tokens=1`은 확인된 제한이고, 그것이 낮은 정확도의 원인이라는 명제는 아직 가설이다. 이 구분 없이 “LLM은 의미 관계를 실행하지 못한다” 또는 “그래프 구조가 잘못됐다”고 일반화하면 다음 실험을 잘못 고른다.

또한 여섯 arm은 같은 48개 test 사례를 공유한다. 288개의 독립 문제로 계산하지 않는다. 이 작은 authored bit 과제의 성공도 자연언어 세계모델 학습으로 확대하지 않는다.

## 3. 원문에서 채택할 부분

학습 문헌 7편, 상태·읽기 문헌 6편, 아래 추가 문헌 4편과 Hyperon 공식 자료를 조사했다. 핵심 기전은 원문의 방법·가정·제한까지 확인했고, 출처마다 실제 읽은 범위를 기록했다. 선정은 현재 실패 기전 중심이며, 모든 관련 연구를 망라한 systematic review는 아니다. 상세 출처·판·읽은 범위는 [학습 카탈로그](artifacts/hswm_deep_research_2026-09-22/learning-sources.v1.json), [상태 카탈로그](artifacts/hswm_deep_research_2026-09-22/state-composition-sources.v1.json), [추가 카탈로그](artifacts/hswm_deep_research_2026-09-22/synthesis-sources.v1.json)에 있다.

| 원문 기전 | HSWM에 대한 설계 추론 | 이식하지 않는 결론 |
|---|---|---|
| [VML](https://arxiv.org/abs/2406.04344), [TextGrad](https://www.nature.com/articles/s41586-025-08661-4), [MIPRO](https://aclanthology.org/2024.emnlp-main.525/), [GEPA](https://arxiv.org/abs/2507.19457): 자연어 변수의 후보 생성과 평가 | relation version을 교정 후보로 만들고 외부 outcome과 선택용 검증 집합으로 비교 | text gradient가 수학적 미분·인과 credit이라는 해석 |
| [WorldCoder v3](https://arxiv.org/html/2402.12275v3): 관측 전이와 모순되는 프로그램을 교정 | 실패 사례와 유지해야 할 성공 사례를 같은 revision packet에 제공 | deterministic symbolic-state 결과를 현실 LLM 실행 성능으로 이전 |
| [Pinductor](https://arxiv.org/abs/2605.13740): 관측 궤적에 대한 모델 후보·점수·진단·선택 | 관계 가설과 관측, 점수, 불확실성, 선택을 별도로 기록 | 모델 순위 점수를 참이나 Semantic Weight로 동일시 |
| [PoE-World v4](https://arxiv.org/html/2505.10819v4): 작은 전문가의 가중 결합 | 예외·국소 기전별 revision과 간섭을 실험 | feature conditional independence를 일반 n항 joint law에 가정 |
| [MSA v2](https://arxiv.org/html/2507.12547v2): 문제별 변수·의존성·확률모형 생성 | 빠진 변수와 추가 read를 후보로 제안 | 사람 판단과의 일치를 세계의 참·새 원시 개념 발견으로 확대 |
| [자기수정 음성 결과](https://arxiv.org/abs/2310.01798) | 같은 LLM의 비평은 후보 생성 신호로 두고 관측과 평가 규칙을 따로 고정 | 스스로 더 그럴듯하다고 말하면 개선되었다는 판정 |

WorldCoder의 code execution, Pinductor의 POMDP program, iVML의 PDDL은 유용한 비교군이다. HSWM의 관계 의미를 사람이 만든 routing DSL로 치환해 성공시키면 사용자 가정을 시험한 것이 아니다. LLM의 pretrained 의미 지식은 사용할 수 있는 prior이며, 관측에 맞는지 시험한다. 코드 실행기는 task fixture의 기준이나 별도 대조군으로 명시한다.

MSA는 새 temporal primitive를 예시 없이 발명하는 데 한계를 보고한다. 이는 “LLM이 필요한 관계를 알아서 찾아줄 것”을 전제로 삼지 말아야 할 직접적인 이유다. HSWM의 구조 발견은 후보 안에서 잘 고르는 능력과 후보 자체를 만들어 내는 능력을 나누어 측정한다. [MSA의 제한](https://arxiv.org/html/2507.12547v2)

## 4. 첫째 연구: LLM을 국소 의미 연산자로 성립시키기

**질문:** relation text, ordered typed roles, context, exceptions, evidence가 모두 정확할 때, 고정 LLM이 의도한 전이를 얼마나 충실하게 실현하는가?

기존 네 bit family의 모든 32개 입력 조합을 각각 검사하는 128-case census를 첫 진단으로 쓴다. 이미 알려진 fixture이므로 generalization test로 부르지 않는다. tokenizer, chat template, model revision, precision, serving version/config, request bytes를 고정하고 반복 호출한다. 반복은 동일 사례의 독립 문제 수를 늘리지 않는다.

| 조건 | 바꾸는 것 | 알아내는 것 |
|---|---|---|
| E0 | 기존 한 토큰 conditional-logprob readout | 기존 실패 재현 |
| E1 | 답 bit만 평가하고 자기보고 확률 일치 조건 제거 | 형식 계약 오류와 의미 오류 분리 |
| E2 | typed intermediate record에 base/context/exception 결과를 출력한 뒤 최종 bit 제출 | 중간 연산을 허용하면 실행이 개선되는가 |
| E3 | fixture의 독립 참조 실행기 | label/serialization 오류 진단; HSWM 성과로 제외 |

E0–E2는 같은 정보와 관계를 읽는다. E2의 계산 증가를 숨기지 않는다. 먼저 능력 진단을 하고, 이후 총 입력·출력 token, latency, 추가 호출 비용을 맞춘 frontier에서 비교한다. E2의 intermediate record는 검증 가능한 출력 형식이며 모델의 내부 사고를 관찰했다는 뜻이 아니다. 이 구조화가 효과가 있다면 자연어 관계 실행을 돕는 국소 realization 후보가 된다.

문장 paraphrase, 일관된 identifier 재명명, JSON 열거 순서 변경, 의미를 바꾸는 role 교환을 구별한다. role 자체를 교환하면 정답이 달라질 수 있다. 조건불변 변환에는 불변성, 의미변경 변환에는 정해진 대응을 요구한다. 익숙한 이름과 opaque 이름을 paired condition으로 두어 pretrained prior의 도움과 지름길을 분리한다.

제안된 범위는 원본·paraphrase 2개·재명명·열거 재배치·role 교환의 6종이다. E0–E2 각각 128×6 사례와 사전 선택한 sentinel 8개의 20회 반복을 합쳐 2,784회 모델 요청이며 E2를 한 번의 structured-output 호출로 계산한 값이다. exact prompt/변환 bytes는 실행 전에 동결해야 한다. E1/E2는 고정 JSON parser로 채점하고 잘못된 출력은 분모에서 빼지 않는다. 현재 case의 gold label이나 참조 실행기 출력은 모델에 전달하지 않는다. 이것은 실행 예산 제안이며 이미 실행한 횟수가 아니다.

**다음 연구 진입 조건:** 이 작은 결정론적 fixture에서는 사전에 고정한 census와 의미 보존 변환에 대해 오류·거절 0인 실행 조건을 요구한다. 이는 외부 세계 전반의 완벽성 요구가 아니라 실험 기구의 준비 기준이다. 우연 수준을 넘기는 것만으로 관계 교정 효과를 깨끗하게 측정할 수 없다. 반복성 실패가 남으면 출력 분포를 보고하고 이 기준은 미충족으로 둔다. 모델이나 연산 방식을 바꿀 수 있으나 원래 실패는 보존한다.

## 5. 둘째 연구: outcome이 의미를 교정하도록 만들기

**선택할 방법은 반례를 받은 후보 생성과 별도 선택 절차다.** GEPA의 후보 비교, WorldCoder의 실패 전이, Pinductor의 진단 구분을 참고한 HSWM 설계 추론이며 논문의 알고리즘을 그대로 재현했다는 뜻은 아니다.

1. 현재 relation version과 실제 ReadFrame, joint prediction, 모델·요청 식별자를 outcome 전에 봉인한다.
2. 독립 환경이 관측 outcome을 제공한다. 예측/관측 차이와 관측 불확실성, 이미 맞던 사례를 같은 feedback packet에 넣는다. 여기서 독립은 다른 LLM 이름이 아니라 답 후보에 의해 정답이 바뀌지 않는 측정 절차를 뜻한다.
3. 고정 예산 안에서 국소 LLM이 여러 revision 후보를 제안한다. 초기 진단에서는 parent를 포함한 최대 4개 후보, 최대 3회 제안을 제안값으로 둔다. 숫자는 최적값이나 검정력 계산 결과가 아니며 실행 전 manifest에서 고정한다.
4. `NO_CHANGE`, `EVIDENCE_ONLY`, `SEMANTIC_PARAMETER`, `RELATION_TEXT`, `ROLE_OR_EXCEPTION`, `TOPOLOGY`로 변경을 분류한다. 이번 W2는 topology를 고정하고 관계 의미 교정만 시험한다. no-op은 적절한 선택일 수 있고, 문장 변경만으로 의미 개선을 판정하지 않는다.
5. search/train과 별도의 selection set으로 후보를 비교한다. 유효한 proposal을 해당 schema/owner/transition 규칙에 따라 admit하고, 새 프로세스가 canonical revision을 다시 읽게 한다. 점수가 admission이나 권한을 직접 부여하지 않는다.
6. 그 후의 봉인된 fresh cases에서 parent, evidence-only, sham paraphrase, revision과 비교한다. 평가용 라벨을 후보 생성에 되돌리지 않는다. [적응적 holdout 재사용 문제](https://proceedings.neurips.cc/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html)를 피하기 위한 설계이며 reusable-holdout 보장을 구현한 것은 아니다.

학습의 첫 유의미한 단위는 “commit 하나”가 아니라 **관측 오차 → 전이 성향의 교정 → 새 canonical read → fresh behavior의 개선**이다. 필요 없던 semantic edit를 억지로 만들지 않는다. 잘못된 초기 관계를 심은 조건에서조차 개선이 없다면 해당 updater는 실패한 것이다.

개입 효과는 동일 초기 state의 격리된 branch들에 revision arm을 무작위 배정하고 같은 task cases를 paired 평가하여 측정한다. 관측이 stochastic하면 공통 환경 난수를 사용할 수 있지만 branch 간 mutable cache와 state는 공유하지 않는다. serving 반복은 technical replicate로 둔다. 관계 의미와 evidence를 교차한 대조가 차이를 분리할 때에만 그 제한된 semantic intervention의 효과라고 부른다. 여러 field가 함께 바뀌면 field별 효과는 식별되지 않는다.

remove/restore는 관계 version과 read-frame bytes의 복원을 확인한다. 복원 후 모든 모델 출력이 bitwise 같아야 한다고 가정하지 않는다. 복원 전후의 분포와 불확실성을 비교한다. 저장 복원과 행동 복원을 같은 항목으로 보고하지 않는다.

## 6. 셋째 연구: 작은 읽기는 검색 문제가 아니라 정보 문제다

[국소 상태 검토](artifacts/hswm_deep_research_2026-09-22/state-composition-review.md)의 POMDP·PSR 연결을 적용하면, 충분성은 전체 과거를 요약했다는 인상보다 **어떤 미래 질문과 허용 행동에 필요한 구분을 남겼는가**로 정의해야 한다. 생성 모형이나 predictive test set이 맞는다는 가정을 HSWM에 자동으로 줄 수는 없다.

다음은 새 경험적 결과가 아닌 elementary counterexample이다. 두 동일 확률 상태가 같은 frame `r`로 읽히지만, 읽히지 않은 exception bit 때문에 정답이 각각 0과 1이라고 하자. frame만 보는 어떤 무작위 연산자도 평균 오류를 1/2보다 낮출 수 없다. 출력 1의 확률을 `q`라 하면 오류는 다음과 같다.

```math
\frac{1}{2}q+\frac{1}{2}(1-q)=\frac{1}{2}.
```

이 조건에서 LLM 크기나 optimizer를 바꿔도 잃은 정보는 복구되지 않는다. 해결 후보는 exception을 읽거나, 관측 가능한 추가 정보를 요청하거나, 모른다는 상태를 유지하는 것이다. 허용된 어떤 관측에도 차이가 없다면 불확실성을 유지해야 하며 숨은 정답을 맞히도록 요구하지 않는다.

세 가지 충분성을 별도로 시험한다.

| 충분성 | 같은 frame으로 보존해야 할 것 | 반증 방법 |
|---|---|---|
| 현재 출력 | 현재 요구된 joint prediction | 같은 frame인데 정답 law가 다른 두 상태 |
| 제어 | 허용 read/action 뒤 outcome law와 task loss | 현재 답은 같지만 다음 action의 효과가 다른 상태 |
| 학습 | 같은 outcome 이후 필요한 revision 및 미래 출력 law | 현재 답이 같아도 누락된 과거 예외 때문에 올바른 후속 상태가 다른 경우 |

W3에서는 full admissible read, fixed local read, active local read를 비교한다. full read도 숨은 환경 정답은 읽지 않는다. 세 arm의 도달 가능한 관측을 고정하고, active read의 추가 토큰·시간을 전체 비용에 포함한다. relevance 점수, candidate recall, decision accuracy, abstention coverage, stale evidence, revision retention을 분리한다.

`other/expand`는 후보가 빠졌다는 것을 표현할 수 있는 실제 action이어야 한다. committee가 모두 같은 잘못된 후보를 갖고 있을 수 있으므로 낮은 disagreement를 충분성 증명으로 쓰지 않는다. 의도적으로 같은 frame이 되는 상태 쌍에서 필요한 구분을 되찾는지를 직접 시험한다. 이를 통과한 “국소”는 선언한 예산·horizon·task 분포 안의 국소이지 임의의 세계에 대한 상수 크기 충분성을 뜻하지 않는다.

## 7. 넷째·다섯째 연구: 결합 법칙을 보존하며 합성하기

Jev의 typed readout과 독립 scheduling은 측정·효율 아이디어다. n항 출력의 결합 의미나 HSWM-of-HSWMs의 증거가 아니다. 독립 readout 여러 개를 곱하는 방식은 공유 사건의 상관을 잃을 수 있다.

예를 들어 `P(00)=P(11)=1/2`와 `Q(01)=Q(10)=1/2`는 각 bit의 marginal이 모두 1/2이지만 공동 사건은 정반대다. 독립 marginal의 곱은 네 경우에 1/4씩 할당하여 두 law를 구별하지 못한다. 이 finite construction은 [기존 Semantic Weight의 joint-law 의무](HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md)를 실험 사례로 옮긴 것이며 새 형식 검증이 아니다.

W4는 shared cause/context와 role-bearing incidence를 가진 joint output을 실제로 읽고 예측하는지 시험한다. joint log loss, 불가능 조합 발생률, 부분 intervention 효과를 측정한다. 태그 있는 factor/incidence graph는 binary RDF에서도 n항 구조를 보존할 수 있다. pair-only clique나 additive pairwise와 tagged incidence를 같은 대조군으로 묶지 않는다.

W5는 두 scale만 선언해 시작한다. child의 state·uncertainty·outcome revision을 감춘 parent 요약이 current output뿐 아니라 이후 revision과 회복까지 보존하는지 본다. child에 공통 규칙을 실행시키는 것만으로 parent가 cognition-bearing HSWM이 되지는 않는다. 같은 자원에서 flat system, static wrapper, 학습 가능한 parent를 비교하고, 하위 손상·model 교체·예외 추가 뒤 world/self prediction과 lineage 연속성을 시험한다. [FCL-1..8](HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md)의 의무는 그대로 남는다.

이 단계들의 수학적 설계와 데이터 구조 검토는 병행할 수 있다. 다만 W1–W3의 실패를 W4–W5의 성능으로 구제하거나 현재 증거로 상위 효능을 홍보하지 않는다.

## 8. bit fixture 이후의 실험 대상과 강한 비교군

다음 testbed 후보는 token-native 작업장 시뮬레이터다. entity, tool, material, context, exception과 관측 가능한 action outcome을 가진다. 같은 물체도 역할과 문맥에 따라 다른 전이를 보이도록 구성하고, 일부 상태는 추가 read로만 알 수 있게 한다. 규칙을 그대로 답으로 노출하지 않고 outcome으로 교정할 수 있어야 한다. 이는 real-world grounding의 완료가 아닌 통제 가능한 다음 실험이다.

과제군을 익숙한 어휘/재명명 어휘, 새 객체 조합, 새 예외, observation noise, 변화한 dynamics로 나눈다. 고정 문법의 새로운 조합은 새 primitive 발견과 구분한다. 문법 밖 primitive를 요구하는 과제에서 실패하면 후보 언어의 한계를 그대로 기록한다. 첫 연구에서는 deterministic complete observation으로 실행을 분리하고, 이후 부분 관측과 stochasticity를 하나씩 추가한다.

| 비교군 | 반드시 맞출 조건 | 이 비교가 답하는 질문 |
|---|---|---|
| frozen relation | 같은 model/read/task | 경험에 따른 변화 자체가 유용한가 |
| append-only evidence memory | 같은 관측과 총 예산 | 관계 수정이 기록 추가보다 나은가 |
| plain natural-language hypothesis revision | 같은 proposer/evaluator/후보 예산 | hypergraph 구조가 단순 text learner보다 기여하는가 |
| full-history LLM | 같은 이용 가능 정보, 비용 frontier | bounded graph read의 이득과 손실은 무엇인가 |
| Panini/GSW 등 memory 방식 | 같은 retrieval 가능 정보와 outcome test | QA/retrieval 향상을 동역학 학습과 구별할 수 있는가 |
| code world model | 같은 관측·변수·검색 비용 | 의미 실행 비용과 code-execution 비용의 차이는 무엇인가 |
| Hyperon의 pin된 구현 + 명시적 adapter | 같은 model, relation, read/action, feedback | persistent metagraph와 국소 neural bridge의 실제 차이는 무엇인가 |

Hyperon은 필수 비교 대상이다. [July 2026 공식 백서](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf)와 [MeTTa v0.2.10](https://github.com/trueagi-io/hyperon-experimental/releases/tag/v0.2.10), commit `3f76dc460da6961f57f69f6c3e550c59c74ada83`을 [직접 prior audit](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)의 성숙도 구분으로 다룬다. persistent metagraph, neural bridge, selective read/write는 이미 직접 겹치는 선행 방향이다. 새로 붙인 adapter의 성과를 upstream Hyperon 기능이라고 부르지 않으며 미구현 설계를 실행 baseline으로 쓰지 않는다. 이 조사에서 동등 조건 benchmark는 실행하지 않았다.

따라서 HSWM의 잠재적 차별점은 “LLM+graph”라는 조합 자체에 둘 수 없다. **동일한 role-bearing state의 경험 기반 전이 교정이 국소 실행과 상위 합성에서도 보존되는 구체적 구성**에서 입증해야 한다. 이것도 현재는 연구 질문이다.

## 9. 실패 판정과 실행 순서

[기계 판독 protocol](../../_research/hswm_deep_research_v1/protocol.v1.json)은 아래 단계와 평가 분리를 담는다. `PROPOSED_NOT_RUN`이며 사후 등록이나 실험 성공 기록이 아니다.

| 순서 | 완료해야 할 관측 | 실패 시 바꿀 대상 |
|---|---|---|
| W1 국소 실행 | oracle fixture와 고정 의미 변환의 오류·거절 0, serving 반복성 보고 | readout, typed realization, prompt binding, 필요 시 model/operator training |
| W2 의미 교정 | 봉인된 fresh population에서 frozen/evidence/sham보다 유용한 개선, retention 손실 제한 | feedback packet, 후보 언어, 제안·선택 알고리즘 |
| W3 능동 읽기 | 비용을 맞춘 local baseline보다 의미 있는 개선, 누락된 구분의 회복 | read policy, 예외·불확실성 표현, 정보 예산 |
| W4 공동 실행 | joint law·불가능 조합·개입 반응 보존 | 독립성 가정, shared context, joint factor realization |
| W5 두 scale 합성 | parent의 지속 state와 학습 효과, child 변화 뒤 연속성 | composition operator와 요약 계약 |

W2의 제안된 confirmatory 기준은 **각각의** frozen/evidence/sham 대조군 대비 task-world 단위 평균 paired 차이의 하한이 절대 +5 percentage points를 넘고, 각각의 보존 과제 악화 상한이 절대 2 points 미만인 것이다. world 안의 사례·serving 반복을 먼저 평균하며 거절은 실패로 센다. 3개 개선 하한과 3개 retention 상한에 one-sided paired-world t bound, Bonferroni `alpha=0.05/6`을 적용하는 nominal familywise 95% 설계를 제안한다. 독립 world와 world 평균의 근사 정규성/충분한 표본 가정이 필요하며 분포 무관 유한표본 보장은 아니다.

이는 이번에 제안한 practical margin과 분석법이며 기존 결과에 소급 적용하지 않는다. 필요한 world 수와 분석 가정의 타당성은 test를 열기 전 별도 pilot으로 판단한다. 표본이 부족하면 `UNDERDETERMINED`; 정해진 비용·효과 범위가 배제되면 해당 기전의 `RED_WITHIN_SCOPE`다. no-op과 실패한 revision을 포함한 전체 world 분석이 주 분석이고, 바뀐 사례만 고른 결과로 대체하지 않는다. 후보 개수·최적화 반복·test population·고정 표본 수는 사전에 동결하고 test 피드백을 본 뒤 바꾸지 않는다.

W3–W5는 아직 수치 confirmatory 기준이 완결되지 않았다. 위 표는 반증 질문과 의존성이다. 해당 protocol을 실행 가능한 수준으로 고정하기 전에는 탐색 관측을 확증으로 부르지 않는다. 이전 RED path는 이 단계 이동으로 삭제되지 않는다.

CR 대응은 [원래 정의](HSWM_CONSTRUCTIVE_REALIZABILITY_PROGRAM_2026-09-10.md)의 범위를 따른다. W1은 CR-0의 일부 실행 기구 조건, W2는 CR-1/2, W3는 CR-4/5 관련 표현·선택 문제, W4는 CR-3/4/6의 일부 조건, W5는 CR-5/6을 조사한다. CR-7은 이들을 **같은 구성에서** 함께 보이는 의무여서 각각의 좋은 사례를 합쳐 충족했다고 할 수 없다. world/self 및 다중 scale credit의 남은 의무도 독립적으로 보존한다.

## 10. 이번 산출물의 역할

코드·기존 관측 감사, 17편의 primary literature 검토, Hyperon 성숙도 비교, 반례와 실행 protocol을 [source-bound KG snapshot](../../ontology/development/HSWM_DEEP_RESEARCH_2026-09-22.v1.json)에 연결한다. [SPARQL 조회](../../ontology/queries/hswm_deep_research_2026-09-22/README.md)는 출처, 실패, 아직 실행하지 않은 연구와 과장된 승격 여부를 확인한다. 표준 RDF/PROV-O/SHACL 경로를 재사용하며 새 canonical-write 경로나 backend를 만들지 않는다.

이번 새 근거는 문헌 검토와 기존 실행의 기전 분석이다. 논문 구현을 설치·재현하거나 모델을 추가 실행하지 않았고, private runtime trace를 public KG에 넣지 않았다. 구조 검증 결과는 [검증 기록](artifacts/hswm_deep_research_2026-09-22/validation.v1.json)에 별도로 남긴다. 다음 실증의 가장 작은 목표는 **정답 관계를 정확하게 실행하는 국소 LLM 조건을 확보한 뒤, 틀린 관계 하나가 실제 outcome으로 교정되어 새 사례에서 유용해짐을 보이는 것**이다.
