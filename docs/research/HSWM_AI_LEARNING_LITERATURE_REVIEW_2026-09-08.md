# AI는 무엇을 학습하며, HSWM은 무엇을 발명해야 하는가

> 검토일: **2026-09-08 UTC** · `SECONDARY_AI_LITERATURE_REVIEW`
>
> 외부 실험: `EXTERNAL_PRIMARY_SOURCE_REPORTED` · HSWM 연결 가설: `UNTESTED`
>
> 문헌의 방법·대조군을 검토한 기록이다. 논문 재현, 새 런타임 구현, HSWM 효능 또는 FCL 통과 결과가 아니다.

## 1. 결론과 정본 역할

최근 연구에서 HSWM에 가장 유용한 방향은 **경험을 재사용 가능한 계산으로 바꾸는 방법을 학습하고,
그 계산이 다음의 낯선 문제에서 실제로 도움이 되는지 검증하는 것**이다. 저장된 설명의 수,
한 과제의 최고 점수, 더 강한 기반 모델의 성능만으로는 이 변화를 식별할 수 없다.

이는 [HSWM Constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 목표를 축소하는 제안이 아니다.
HSWM은 하나의 token-native LLM-function macro-neural network이며, evolving canonical hypergraph가
living harness, world model, continuous learner의 역할을 함께 수행한다. 이 문서의 학습 상태 분류는
관측·개입을 위한 분류이고, HSWM을 별도 memory/actor/learner subsystem으로 나누는 설계가 아니다.

[프랙탈 scientific connections](HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md)의 FCL-1..8과
`SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`를 유지한다.
[adaptive research strategy](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)에 따라
실패한 기전은 그 범위와 계보를 보존하며 교체할 수 있지만, 외부 논문으로 이전 RED를 구제하지 않는다.

**이번 conceptual delta:** [9월 7일의 35편 이론 연결 지도](HSWM_FRONTIER_LEARNING_THEORY_KG_2026-09-07.md)에
이어, 가까운 후속 연구를 중심으로 **갱신되는 상태·새 정보의 출처·검증 분리·영속 전이·비용**을 조사했다.
그 결과를 아직 미검증인 관계/transition 합성 실험 가설로 좁혔다. 현재 코드의 완성도 판정을 갱신하지 않으며,
선행 문서의 G0 `NOT_PASSED`, G1 `NOT_EVALUATED`, D4 미완성, P1 `RED`도 이 검토로 승격되지 않는다.

## 2. 검색 범위와 읽은 깊이

2026년 7~9월 공개·개정 자료를 우선하고, 직접 비교에 필요한 6월 논문과 이전 연구를 포함했다.
검색어는 agent reinforcement learning, continual learning, test-time training, skill learning,
program synthesis, world-model rehearsal, causal learning이었다. 공개 Hugging Face papers 검색으로
후보를 찾고, 아래 인용의 **arXiv 원문·버전 이력**, 개발사 공식 보고서와 직접 평가 기관 자료를 확인했다.
검색 서비스의 추천·색인 날짜를 논문 제출일로 쓰지 않았다. 전체 분야를 망라한 systematic review는 아니다.

R01–R12는 협업 검토를 포함하여 방법·평가·관련 ablation 또는 한계를 읽었다. R13은 구조 ablation을
읽은 보조 논문이고, R14는 이번 조사에서 초록·메타데이터까지만 확인했다. 수치는 모두 저자 보고이며
코드 실행이나 독립 재현으로 확인한 값이 아니다. peer review 미확인은 논문의 거짓 또는 미게재 판정이 아니다.

| ID | 논문·고정 버전 | 최초 제출 / 검토한 개정 | 확인한 상태 |
|---|---|---|---|
| R01 | [Curriculum RL Can Incentivize Reasoning Capacity…](https://arxiv.org/abs/2606.22317v1) | 06-21 / v1 | preprint, peer review 미확인 |
| R02 | [SEED: Self-Evolving On-Policy Distillation](https://arxiv.org/abs/2607.14777v1) | 07-16 / v1 | preprint, peer review 미확인 |
| R03 | [Progressive Agent Skill Generation via RL](https://arxiv.org/abs/2608.01678v1) | 08-03 / v1 | preprint, peer review 미확인 |
| R04 | [Better, Faster, Stronger: Programmatic Skill Learning…](https://arxiv.org/abs/2608.11338v1) | 08-11 / v1 | preprint, peer review 미확인 |
| R05 | [No Time Like the Present: Agentic Test-Time Training](https://arxiv.org/abs/2607.03441v1) | 07-03 / v1 | preprint, peer review 미확인 |
| R06 | [Test-Time Training with Next-Token Prediction](https://arxiv.org/abs/2606.21803v2) | 06-19 / **08-30 v2** | arXiv comments상 Findings of EMNLP 2026 accepted; proceedings 별도 확인 안 함 |
| R07 | [The World Model Remembers, the Actor Forgets](https://arxiv.org/abs/2607.19749v1) | 07-22 / v1 | preprint, peer review 미확인 |
| R08 | [Do Agent Optimizers Compound?](https://arxiv.org/abs/2607.14004v1) | 07-15 / v1 | preprint, 평가 대상 RELAI 측 저자 포함 |
| R09 | [Causal Foundation Models](https://arxiv.org/abs/2609.03003v1) | **09-02 / v1** | 입문·비교 benchmark 논문, peer review 미확인 |
| R10 | [PRO-LONG](https://arxiv.org/abs/2607.20064v2) | 07-22 / 07-23 v2 | preprint, peer review 미확인 |
| R11 | [TOOD](https://arxiv.org/abs/2607.29592v1) | 07-31 / v1 | arXiv comments상 CoLLAs 2026 oral accepted; proceedings 별도 확인 안 함 |
| R12 | [Kimi K3: Open Frontier Intelligence](https://arxiv.org/abs/2607.24653v2) | 07-27 / 08-07 v2 | 기업 기술보고서, peer review 미확인 |
| R13 | [Attention Residuals](https://arxiv.org/abs/2603.15031v1) | 03-16 / v1 | 보조 구조 연구, peer review 미확인 |
| R14 | [Does RL Really Incentivize Reasoning Capacity…?](https://arxiv.org/abs/2504.13837v5) | 2025-04-18 / 2025-11-24 v5 | arXiv상 NeurIPS 2025 Oral; 이번에는 초록·메타데이터만 확인 |

## 3. 먼저 구분해야 할 다섯 종류의 변화

| 관측 대상 | 갱신 예 | 무엇을 더 확인해야 학습 주장을 할 수 있는가 |
|---|---|---|
| 한 요청의 작동 상태 | context, KV, prompt별 fast weight | context 초기화 뒤 효과가 남는지; 남지 않아도 유용한 추론 중 적응일 수 있음 |
| 세션 간 외부 상태 | raw log, 설명, skill, 실행 함수 | 저장된 내용을 실제로 읽고 사용하는지, 새 과제에서 이득인지 |
| 기반 모델 파라미터 | SFT, RL, distillation | 외부 교사·데이터·계산량을 포함한 대조군과 OOD·retention |
| 갱신을 만드는 정책 | skill editor, proposal policy | 같은 경험·예산에서 제안의 일반화·유효성·탐색 효율이 좋아지는지 |
| HSWM canonical revision | typed relation, executable transition, disposition | 정확한 revision의 remove/restore가 독립 outcome에 미치는 영향과 계보·책임 계약 |

이 분류는 서로 배타적인 제품 종류가 아니다. 한 시스템이 여러 종류를 함께 갱신할 수 있다.
HSWM의 macro-learning은 마지막 행을 포함해야 한다. 기반 LLM의 파라미터를 그대로 두는 것과
HSWM이 학습하지 않는 것은 동의어가 아니며, 반대로 LLM을 fine-tune해도 canonical 관계 학습이 자동 성립하지 않는다.

## 4. 학습 기전과 증거

### R01–R02. 성공을 재가중하는 것과 새 학습 신호를 공급하는 것

**Curriculum RL**은 pass@256으로 경험적 실패 경계를 찾고, 경계 부근·바깥 문제의 교사 trace를 SFT한 뒤
GRPO로 학습한다. 5개 base 설정의 수학 평가에서 평균 pass@256은 base 대비 9.8pp 높았고,
base가 256회 안에 못 푼 538문제 중 226개를 풀었다고 보고한다. 핵심 대조는 base와 vanilla RLVR다.
다만 유한 256회 실패는 능력의 수학적 상한이 아니고, 교사 trace가 외부 정보다. 총 FLOPs가 완전히
맞춰진 순수 RL 효과로 해석할 수 없다. 모두 같은 실패 보상을 받은 GRPO 그룹에서는 task advantage가
사라질 수 있지만 KL 등 다른 학습 항까지 없다는 뜻은 아니다. [R01 방법·평가](https://arxiv.org/html/2606.22317v1)

**SEED**는 수행 궤적을 hindsight skill로 기술하고, 같은 action을 그 skill과 함께/없이 평가한
차이로 token 수준 distillation 신호를 만든다. 이를 outcome RL과 결합해 **모델 weight에 내재화**하며,
배포 시 별도 skill bank는 사용하지 않는다. ALFWorld unseen에서 GRPO 70.9→86.2를 보고한다.
외부 GLM-5.2 analyzer를 쓰는 초기 SFT, static skill, hindsight 제거 등 ablation도 있다.
초기 교사·추가 분석 비용이 있고, 시뮬레이터·WebShop·검색 QA의 범위다. 자기 설명의 설득력만으로
그 설명이 실제 성공 원인이라고 판정하지는 못한다. [R02 §3–4, Appendix B.4](https://arxiv.org/html/2607.14777v1)

R14의 초록은 RLVR의 small-k 향상과 large-k coverage 감소를 구분한다. 이번에는 세부 실험을 재독하지
않았으므로 “RL은 새 능력을 만들 수 없다”는 보편 명제로 채택하지 않는다. R01 역시 외부 교사와 유한
샘플 경계라는 조건을 가진다. [R14 초록·상태](https://arxiv.org/abs/2504.13837v5)

**HSWM 유추:** outcome만 기록하는 것에 더해, 새 정보가 교사·실제 관찰·검증기·자기 재기술 중 어디에서
왔는지 남겨야 한다. 실패 설명은 제안의 입력이며, 그 설명 자체가 causal credit은 아니다.

### R03–R04. 재사용할 계산을 만들고, 만드는 방법까지 학습한다

**Skill-α**는 고정 worker를 보조할 skill editor를 Qwen3-8B 기반 SFT+GRPO로 학습한다.
editor는 SKILL.md의 생성·수정·병합·삭제·유지를 고른다. 같은 anchor query에서 편집 전후 결과를 비교하는
rollback reward를 사용하고, 별도의 target query로 평가한다. CL-Bench·tau2에서 strongest baseline 대비
각각 3.3pp·6.7pp 개선을 보고하며 SFT-only 등과 비교한다. benchmark에 따라 rubric judge 또는 환경
verifier를 쓴다. **editor policy의 weight를 학습하고, 산출 skill은 그 policy가 만드는 외부 artifact**다. 한 anchor의 이진 결과가 전체 task family의
기대 이득을 보증하지 않으며, 표현도 text skill에 한정된다. [R03 §4–5, Appendix E](https://arxiv.org/html/2608.01678v1)

**SpeedRunner**는 10회 rollout마다 궤적·call stack·이전 library를 보고 프로그램 함수를 추가·수정·삭제한다.
이는 inference-time library learning이며 parameter RL이 아니다. ScienceWorld·BabyAI·Crafter에서
200회 online rollout, 30개 고정 held-out episode, 3 seed로 평가한다. BabyAI에서 최종 token 비용이
ReAct의 약 1/8이면서 성공률도 개선됐다고 보고한다. interpreter 제거 ablation은 inducer의 코드 보조
궤적 분석이 효율에 기여함을 보여준다. 다만 ablation은 주로 BabyAI이고, family마다 library를 새로 시작한다.
inducer의 자체 코드 수정은 HSWM식 독립 admission과 같지 않다. [R04 §3–6, Appendix A](https://arxiv.org/html/2608.11338v1)

**HSWM 유추:** typed relation/transition을 “경험에서 합성한 실행 가능한 가설”로 취급하는 경로가 유망하다.
함수를 저장하는 것과 관계 자체를 학습하는 것의 차이는 산출물의 이름이 아니라 **어떤 실행 의미가
새로 생겼으며, 그 의미가 낯선 구성에서 어떤 outcome을 바꾸는지**에 있다.

### R05–R06. 추론 중 적응과 영속 학습은 수명이 다르다

**Agentic TTT**는 에피소드 중 5 step마다 LoRA를 next-token loss로 갱신하고 종료 시 초기화한다.
환경 관찰·자기 텍스트·별도 요약을 비교하며 반복 n-gram에 덜 학습하도록 한다. ALFWorld에서
Qwen3.5-9B ReAct 50.7→55.7, SWE-bench Lite에서 Qwen3.5-27B 57.8→62.7을 보고한다.
비용은 no-TTT의 약 1.9배다. context 및 반복 억제 대조가 있으나 저자도 기본 능력이 있는 과제에서
경로 이탈을 줄이는 범위로 해석한다. 새 과제 능력을 영속 획득했다는 증거가 아니다.
[R05 방법·대조·한계](https://arxiv.org/html/2607.03441v1)

**TTT-NTP v2**는 Transformer MLP down-projection에 prompt별 fast-weight 보정을 만든다.
관측 token의 다음 위치 표현을 이용하는 ridge-regression 갱신이며 요청 간 영속 학습을 시험하지 않는다.
같은 continual-pretraining token 예산 등으로 비교했고 Llama-3.1-8B의 RULER 평균은 55.8→59.7이다.
LongBench-v2 실제 QA도 평가한다. 따라서 합성 retrieval만의 결과로 축소해서도 안 되지만,
장기 retention·관계 발명까지 확장해서도 안 된다. 시험 정답을 loss로 쓰지 않는다는 기술과
모든 데이터 누수 가능성을 독립 감사했다는 주장은 다르다. [R06 방법·평가](https://arxiv.org/html/2606.21803v2)

**HSWM 유추:** 일시적 활성·적응을 자주 바꾸면서도, 영속 revision은 별도의 증거 수명을 가질 수 있다.
이는 하나의 canonical state model 안에서 lifecycle과 typed reference로 표현할 문제다.

### R07–R08·R11. 기억 보존, 행동 보존, 계속 개선은 별개다

**Dream Rehearsal**은 never-clear replay가 있는 17M DreamerV3형 모델·MiniGrid에서,
world-model probe가 보존돼도 actor가 이전 행동을 잊는 사례를 분리한다. frozen model과 같은 imagined
data·예산의 회복 실험에서 RL-in-imagination은 0/3 seed, graded self-imitation은 3/3이 회복했다.
강한 대조인 competent real-episode cloning도 네 과제 통과에는 성공한다. 꿈속 성공을 고르는 grader의
종료 후 점수 오염과 낙관적 value 문제, 구현 버그 수정도 공개했다. **3 seed·작은 환경·선별된 task chain**
결과로서, LLM 일반 법칙이나 상상 학습의 무조건적 우월성은 아니다. [R07 §4–9](https://arxiv.org/html/2607.19749v1)

**Do Agent Optimizers Compound?**는 같은 GPT-5.5 baseline에서 phase당 200 rollout으로 harness를
최적화한다. 12개 task 다음 10개가 추가되는 두 단계다. transfer 열은 **새 task만이 아니라 22개 합집합**이며,
마지막 재최적화도 이 합집합을 사용하므로 최종 값은 완전 미관측 test 성능이 아니다. GEPA의 transfer 54.5는
baseline 56.8보다 낮고, Meta Harness는 68.2로 높다. 표 caption의 “only positive transfer”는 이 값들과
맞지 않는다. RELAI 방식의 우위는 저자 측 평가·상이한 search space·두 단계 조건 안에서만 읽는다.
동일 rollout 수가 전체 token 비용까지 일치시킨 것도 아니다. [R08 §3–7, Table 1–3](https://arxiv.org/html/2607.14004v1)

**TOOD**는 continual vision classification에서 기존 accuracy가 유지돼도 OOD confidence 품질이
무너질 수 있음을 보인다. weight 대신 task별 calibration 통계를 저장하며, CIFAR-100의 한 설정에서
energy AUROC 60.9→68.3을 보고한다. 학습 때의 task/class partition이 필요하고, logit calibration이
표현의 모든 문제를 고치지는 않는다. LLM 연구로 직접 등치할 수 없는 **평가 누락의 반례**다.
[R11 방법·평가](https://arxiv.org/html/2607.29592v1)

**HSWM 유추:** relation이 저장돼 있는지, 실제 실행에서 읽혔는지, 행동이 유지되는지, 새 입력에서 잘못된
relation을 과신하지 않는지를 따로 측정해야 한다. memory의 존재만으로 behavior의 보존을 대리할 수 없다.

### R09. 최신 인과 모델도 가정과 질의를 필요로 한다

9월 2일 **Causal Foundation Models**는 새 모델 하나의 관계 발명 논문이 아니라 기존 CFM의 설명·비교다.
SCM prior에서 synthetic observational data와 intervention 정답을 생성해 pretrain하고, 새 dataset에서는
고정 weight로 causal effect를 in-context 추정한다. treatment·outcome·estimand가 주어진 **효과 추정**과
unknown graph의 discovery를 분리한다. RealCause-Lalonde의 semi-synthetic 평가에는 참값과 tuned
classical baseline이 있지만, benchmark가 보장하는 ignorability를 실제 미관측 confounding으로 확장할 수 없다.
CausalPFN 18.4초 대 tuned T-Learner 1,803초의 CPU median 비교는 pretraining을 제외한 amortized
deployment 비용이다. prior mismatch와 calibration은 여전히 한계다. [R09 §3–5](https://arxiv.org/html/2609.03003v1)

**HSWM 유추:** 인과 추정기를 사용하려면 먼저 intervention·outcome·관측 변수·가정·식별 상태를 명시해야 한다.
추정치가 생겼다는 이유로 relation의 causal credit이나 canonical admission이 자동 발생하지 않는다.

### R10·R12–R13. K3/Astra의 지능에서 실제로 가져올 수 있는 직관

**Kimi K3** 보고서는 효율적 혼합 attention/MoE·깊이 방향 정보 결합, 데이터, SFT, 장기 환경 RL,
여러 domain/effort teacher의 on-policy distillation을 함께 설명한다. 9개 RL expert는 **3 domain × 3 effort**다.
이를 “9개 domain”으로 읽으면 안 된다. 많은 sandbox·부분 rollout 유지가 긴 환경 경험을 가능하게 하지만,
각 요소를 제거한 동일 총 compute 대조가 충분히 공개되지는 않았다. 높은 점수의 원인을 단일 구조에
귀속할 수 없다. [R12 §4–6](https://arxiv.org/html/2607.24653v2)

**Attention Residuals**는 깊이 방향으로 이전 표현을 입력에 따라 선택·혼합하는 구조를 시험하며,
작은 모델의 matched-compute ablation이 있다. 이 결과는 정보 접근·최적화 경로에 관한 근거이며,
K3 전체 개선량의 인과 분해나 새로운 의미 관계의 발명 증거는 아니다. [R13 구조·ablation](https://arxiv.org/pdf/2603.15031v1)

**Astra**의 공개 시스템 문서는 reasoning RL을 설명하지만 parameter 수, recurrent depth,
latent loop, optimizer 및 학습 FLOPs를 충분히 공개하지 않는다. 특정 비공개 구조가 높은 지능의 원인이라는
설명은 여기서 채택하지 않는다. [OpenAI 공식 시스템 문서](https://deploymentsafety.openai.com/gpt-6-astra)

ARC Prize의 직접 평가에서 Astra max의 ARC-AGI-3 semi-private 점수는 standard 구성 62.71,
provider adapter 구성 98.55였다. opaque reasoning state·compaction 등을 포함한 **전체 구성 차이**다.
단일 memory 요소의 인과 실험도, 사람과의 순수 지능 비교도 아니다. 장기 상태를 유지하고 관측과 예측을
동기화하는 실행 조건을 강한 baseline에 넣어야 한다는 근거로 사용한다.
[ARC Prize 직접 평가](https://arcprize.org/blog/astra), [구성별 결과](https://arcprize.org/results/openai-gpt-6-astra)

**PRO-LONG**은 관측·행동·결과의 raw log를 프로그램으로 조회하게 한다. ARC-AGI-3 public 25게임에서
500-action 평가를 쓰며 **게임마다 새 workspace/session**을 시작한다. 따라서 게임 간 관계 학습의 증거가
아니다. 높은 장기 수행 점수가 단순하고 강한 기록 접근만으로도 개선될 수 있음을 보여주는 필수 대조다.
public/private, pass@1/best@k, 모델과 harness를 섞어 Astra adapter 점수와 비교하지 않는다.
[R10 방법·평가](https://arxiv.org/pdf/2607.20064v2)

## 5. “창조”에 대한 연구적 해석

다음은 위 논문들이 함께 증명한 정리가 아니라 **HSWM을 위한 종합 가설**이다.

1. **표현:** 과거 사례를 그대로 복사하지 않고 여러 문제에 쓰일 규칙·절차·함수로 표현한다.
2. **제안:** 그 표현 공간에서 변형·조합·새 실행 경로를 만든다. 제안기의 학습도 별도 가능하다.
3. **환경에 묻기:** 후보가 예측하는 차이를 실제 관찰·실행·검증 가능한 문제로 바꾼다.
4. **선택과 압축:** 유용한 경험을 이후 호출 가능한 계산으로 남긴다. 실패 조건도 함께 보존한다.
5. **새 구성에서 재사용:** context를 초기화하고 다른 task family에 적용해 전이·비용·망각을 확인한다.

Transformer의 패턴 표현·조건부 정보 결합은 이 과정의 제안 능력을 제공할 수 있다. RL은 검증 신호가
도달하는 후보들의 선택·수행을 바꿀 수 있고, distillation은 교사 또는 hindsight가 제공하는 정보를
내재화할 수 있다. 프로그램 합성은 반복 추론을 실행 구조로 압축할 수 있다. 어느 하나만으로 개방적인
발명·인과 이해·자기성의 충분조건이 되지는 않는다.

HSWM의 목표에서 “새 관계”는 새 이름이나 JSON edge 한 개가 아니다. 예를 들어 기존 후보가 모두
`조건 → 기존 route 선택`뿐이라면 이름을 바꾼 여러 후보도 그 표현 계열 안에 있다. successor hypothesis는
**누가 어떤 역할로 결합하고, 어떤 token/message를 변환하며, 무엇을 관찰·예측·실행하는가**를 바꾸는
schema-valid 실행 의미를 제안해야 한다. 이 예시는 현재 런타임이 구현했다는 진술이 아니다.

발명 범위도 미리 정해야 한다. “초기 library에 없는 실행 구성”, “학습 중 본 조합을 넘는 구성”,
“새 task family에 유용한 구조”는 서로 다른 주장이다. 문자열 신기함이나 graph 크기는 이를 대신하지 못한다.

## 6. HSWM 판별 실험 제안 — 아직 실행하지 않음

**가설 H1:** 경험에서 합성한 typed relation/transition이 강한 기반 모델·동일 실행 도구의 단순 기록/skill
대조보다 새로운 조합에서 낫고, 그 이득의 일부가 특정 canonical revision에 인과적으로 귀속된다.

**가설 H2:** 경험을 relation 후보로 바꾸는 proposal policy가 고정 제안기보다 같은 총 예산에서
유효한 후보를 더 효율적으로 찾아낸다. H1과 H2를 동시에 바꾸지 않고 각각 시험한다.

**가설 H3:** 새로운 revision으로 개선한 뒤에도 이전 능력과 불확실성 판단이 유지된다.
H1이 통과해도 H2·H3 또는 FCL-1..8이 자동 통과하지 않는다.

### 6.1 데이터와 outcome의 역할을 고정한다

| 구획 | 용도 | 금지되는 혼동 |
|---|---|---|
| A: 경험·학습 family | 관측 수집, 후보 생성, proposal 학습 | A 재성공만으로 전이 주장 |
| V: 개발·선택 family | 후보 비교·admission 판단, 개발 retention | 반복 조회한 V를 blind test라고 부르기 |
| B: 봉인한 최종 family | 처음 보는 구성·topology의 최종 비교 | B 점수로 후보를 고른 뒤 B를 최종 증거로 재사용 |
| A-retain: 봉인한 이전 능력 평가 | 새 학습 뒤 지연 retention·calibration | 학습에 다시 넣은 항목을 미관측 retention으로 보고 |

family 분할은 이름 교체를 넘어서 dependency·역할·관측 조건·구성 규칙으로 선언한다. 필요한 표본 수,
효과 크기 기준, seed, 비용 상한, 중단 규칙은 **결과를 보기 전에** 정한다. 여기서는 근거 없는 숫자를
success criterion으로 새로 만들지 않는다. B를 다시 탐색에 쓰면 다음 평가에는 새 봉인 집합이 필요하다.
B의 remove/restore 역시 사전 고정한 평가 arm으로 실행하며, 그 결과로 revision을 다시 선택하지 않는다.

### 6.2 같은 기반 모델·도구·예산에서 강한 대조를 둔다

| 대조 | 분리하려는 설명 |
|---|---|
| 고정 base + 기본 executor | 기반 모델이 이미 풀 수 있었음 |
| base + raw log + programmatic search | 기록 접근 개선만으로 충분함 |
| base + text skill / program library | 일반 skill 재사용만으로 충분함 |
| 기존 typed relation + 점수/guard 적응 | 고정 문법 안에서 선택만 개선됨 |
| relation 의미 제거·셔플, 비용·길이 대응 | 더 많은 context·호출·표현량 때문임 |
| 제안한 revision 제거 후 복원 | 그 exact revision의 행동 기여가 없음 |
| 교사·hindsight·proposal 학습 각각 제거 | 외부 교사 또는 더 큰 탐색 비용이 실제 원천임 |

같은 token 예산만으로 끝내지 않는다. LLM/교사 호출, rollout, simulator·verifier, editor, 학습,
retrieval, 재검증 비용을 포함한 총비용과 배포당 비용을 나누어 보고한다. 초기에 든 비용이 몇 번의 재사용으로
상쇄되는지도 측정한다. 모델·온도·도구·timeout·실패 재시도 조건과 평가 접근 권한도 맞춘다.

### 6.3 결과는 범위에 맞춰 판정한다

- A 또는 V만 좋아지면 local adaptation/selection 증거다. B 전이는 별도다.
- raw-log만 이기고 program-library와 분리되지 않으면 그 대비에서 관계 학습의 추가 효능은 지지되지 않는다.
- 독립 outcome 없는 LLM 자기평가 향상은 causal credit 증거가 아니다. 환경 verifier도 결함·누수 검사를 받는다.
- B 개선이 revision 제거에도 유지되면 그 revision에 대한 인과 귀속은 실패한다. 복원 실험도 같이 읽는다.
- B 개선과 A-retain 악화가 함께 있으면 retention 실패를 보존한다. 평균 점수로 감추지 않는다.
- semantic/topology 변화가 실제로 생성되지 않으면 관계 합성 가설을 검증한 실험이라고 이름 붙이지 않는다.
- 통과해도 해당 기전·family·모델·예산 안의 증거다. 상위 HSWM 합성은 이후의 별도 FCL 계약이다.

관계의 source·revision·실행 의미·관측·outcome을 같은 provenance 계보에 결속하고, canonical atom마다
schema-relative 책임 owner 하나를 둔다. 제안·검증·실행·책임은 typed reference로 연결하며,
기존 `Inv/Permit`과 권리·복구 계약을 유지한다. 이 문서는 새로운 개인 거버넌스 gate를 도입하지 않는다.

## 7. 함수형 TypeScript/Effect 방향과의 관계

이 연구 경로는 사용자의 함수형 TS/Effect 원칙과 양립한다. 향후 구현에서 후보 표현·정규화·동등성 판정·
학습 갱신은 immutable value를 입력받아 새 value를 반환하는 순수 함수로 두고, LLM·환경 실행·시간·저장 등
외부 효과는 Effect로 표현할 수 있다. 실행 가능한 후보도 typed AST와 명시적 해석 의미로 제한할 수 있다.

이는 **HSWM macro-learning을 어떻게 표현할지에 대한 설계안**이다. GPU gradient training 논문의 결과를
TypeScript 제어 루프로 옮겼다는 이유만으로 재현한 것이 되지는 않는다. 먼저 discrete relation 합성의
H1을 판별하고, 필요하면 별도 실험에서 H2의 editor 학습을 비교한다. 이번 변경에는 구현과 학습 실행이 없다.

## 8. 기록과 검증 경계

원문 식별자·읽은 범위·HSWM 가설은 새
[source-bound evidence projection](../../ontology/evidence/HSWM_AI_LEARNING_LITERATURE_REVIEW_2026-09-08.v1.json)에
연결한다. 이는 checked-in 문헌 인터페이스이며 live KG publish, HSWM cognition, causal admission이 아니다.
선행 canon·ontology·RED 기록은 재작성하지 않는다. 원문 PDF·본문·비공개 runtime trace를 저장소에 복제하지 않는다.

문서 렌더링·JSON·source hash 검사는 문서가 읽히고 출처가 연결되는지에 대한 공학적 검사다.
이를 논문 결과의 재현, HSWM 학습 효능 또는 새 material research result로 세지 않는다.
