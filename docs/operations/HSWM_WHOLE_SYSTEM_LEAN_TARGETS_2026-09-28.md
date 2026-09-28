# HSWM 전체 구현을 위한 Lean 공략점

2026-09-28 · `SECONDARY_AI_IMPLEMENTATION_PLAN` · 조사 기준 Git `6d2d85f1dfc1ec4e5ed516ee153bc92a7fac480c`.

**다음 공략점은 실제 의미 실행·학습 루프를 기존 증명의 구체적인 인스턴스로 만드는 것이다.**
그다음 국소 읽기, 반복 학습, 구조 변경, 두 규모 합성을 연결한다. 아래 P1–P5는 후속 작업이며,
이번 문서는 새 Lean 증명이나 모델 효능 결과를 보고하지 않는다. 기존 정리·구현의 소스를 대조하고
논문 본문을 확인한 구현 계획이다. CR-0..7/FCL-1..8의 목표·판정과 과거 음성 결과를 유지한다.

## 전체를 보는 기준

[사용자 정의](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md)에 따라
큰 Semantic Weight 하이퍼그래프가 하나의 AI 상태이며 LLM은 국소 연산자다.
실행·월드모델·자기모델·학습은 이 상태의 역할이다.
[CHU](../research/CHU_HSWM_COMPUTATIONAL_ARCHITECTURE_2026-09-27.md)는 더 넓은 계산 우주의 개념이고,
HSWM은 LLM 계산을 사용하는 구체적인 대상이다.

| 사용자 직관 | 구현에 사용할 수 있는 증명 질문 |
| --- | --- |
| Agent는 바깥 추상화 수준의 시뮬레이터이며 M은 층간 Map이다 | 구체 상태를 추상 상태로 옮겨도 실행과 학습이 보존되는가? 근사라면 어떤 관측·오차·시간 범위인가? |
| 하이퍼그래프는 관계를 표현하는 경제적인 체계다 | 관계 ID·역할·순서·문맥을 보존하는가? 특정 작업·표현·비용 모형에서 손실과 비용은 얼마인가? 보편적 최소 비용이라는 결론은 별도다. |
| LLM과 실행 가능한 그래프 메모리는 소프트웨어다 | 저장된 상태·연산·outcome으로 다음 상태를 구성하고, 재개방한 실행이 실제 그 상태를 읽는가? |

현재 실행 연결은 [선택된 의미 상태의 실행](HSWM_SEMANTIC_SELECTED_EXECUTION.md)에 있다.
호출자가 relation UID를 지정하고, LLM 의미 실행 뒤 outcome에 결속한 revision을 만들며,
`--allowance`와 `--debit`를 함께 준 실행에서는 dev 선택 결과를 저장한 다음
선택한 durable branch를 재개방해 heldout 실행에 사용한다.
새 검증 계층을 추가하기보다 이 경로를 기준으로 증명과 구현을 맞춘다.

## 이미 있는 기반: 재증명 대신 재사용

| 기반 | 실제 범위 | 후속 연결 |
| --- | --- | --- |
| [실행 가능한 incidence encoding](../../formal/HSWMExecutableGraphEncoding.lean) | 유한 typed n-ary family의 왕복, Step/Learn과 혼합 실행열 보존 | 실제 버전형 관계 schema에 인스턴스화 |
| [Operational abstraction](../../formal/HSWMOperationalAbstraction.lean) | `FibreCriterion`과 정확한 refinement 존재의 동치, 실행열 보존 | 실제 read-set·역할·예외·학습 guard의 충분성 |
| [Frozen-round 통계 학습](../../formal/statistical-learning/HSWMStatisticalLearning/CanonicalBridge.lean) | 고정 후보군, 독립 bounded 평가 행에서 선택 오류 경계와 canonical Learn/다음 Step 연결 | 과거 이력에 따라 바뀌는 후보·여러 평가 라운드 |
| [Verified admission](../../formal/HSWMVerifiedAdmissionKernel.lean), [wire](../../formal/HSWMVerifiedAdmissionWire.lean), [persisted state](../../formal/HSWMPersistedVerifiedAdmission.lean) | 실행 가능한 Lean checker와 조건부 정확한 successor; TS gateway에서 사용 | 실제 semantic lifecycle의 대응과 adapter 가정 명시 |
| [합성 간섭](../../formal/HSWMCompositionInterference.lean), [재귀 합성](../../formal/HSWMRecursiveLearningComposition.lean) | 쓰기가 교환 가능해도 공동 효용은 하락할 수 있음; XOR 주변분포 손실 반례 | 공동 상태·관측과 학습을 보존하는 합성 |

Frozen-round 정리는 후보끼리 독립일 것을 요구하지 않는다. 평가 행의 독립성과 범위가 중요하다.
최대 b개 행 교체의 평균 오차 보정은 Huber 분포 오염과 다른 가정이다.
현재 TS의 정수 `allowance`·`debit`가 통계적 반경·비용을 자동으로 구현한다는 증명은 없다.
Admission 증명도 JSON parser, SHA, 파일시스템 crash, TS 전체 실행의 정확성을 포괄하지 않는다.

## P1 — 실제 의미 루프와 Lean 상태 전이를 연결

**첫 구현 묶음.** [LLM semantic runtime](../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.ts)의
`SemanticReadFrame`, trace, outcome, revision과
[selected execution](../../src/hswm/effect-runtime/src/semantic-lifecycle-selected-execution.ts)의
선택·재개방·다음 읽기를 하나의 대응 관계로 정의한다.
수학적 Learn successor와 다음 Step의 연결은 이미 있다. 여기서 추가할 것은
실제 TS artifact가 그 수학적 상태에 대응한다는 runtime refinement다.

- Lean 목표: 실제 artifact의 추상화가 같은 관계 버전의 Step/Learn을 나타내고, 선택된 successor가
  다음 읽기의 상태가 됨을 보인다. 기존 GraphState는 단일 relation 읽기 모형이므로 multi-atom
  frame을 이미 표현한다고 가정하지 않고 필요한 추상화 함수를 명시한다.
- TS/Effect 작업: 순수한 frame/trace/outcome projection과 기존 admission adapter 연결.
  runtime source·model·설정·입력 버전의 결속과 canonical encode/decode 적합성을 확인한다.
  기존 Lean CLI와 journal을 재사용한다.
- 완료 기준: 실제 lifecycle artifact로 전이 대응을 검사하고, 역할·버전·outcome을 바꾼 입력은
  잘못된 동일 전이로 인정되지 않는다. 선택 이후 기존 관계를 읽는 오류도 검출한다.
  provider의 출력 의미와 외부 outcome의 진실은 이 구조 정리의 결론으로 넣지 않는다.

같은 frame이면 실제 LLM 응답이 항상 같다고 가정하지 않는다. 우선 지정된 interpreter 호출의
일치를 다루고, 확률적 출력까지 다루려면 상태·설정을 포함한 확률 kernel 또는 명시적 randomness를
모형화한다. 역할 교환과 의미 보존 paraphrase를 구별하는 W1 평가를 이 경로에 연결한다.

## P2 — 큰 그래프에서 필요한 부분만 읽는 조건

P1의 전이 대응에 쓰이는 **국소성 법칙**을 공략한다. task에서 관계 후보와 bounded read plan을
만들고, 필요한 역할·예외·근거가 부족하면 추가 읽기 또는 `UNKNOWN`을 반환한다.

- Lean 목표: 실제 schema에 `FibreCriterion`을 적용해 같은 추상 읽기가 Step뿐 아니라 Learn의
  guard와 결과도 보존함을 증명한다. read/write frame 바깥의 변경이 무관하다는 조건도 명시한다.
- TS/Effect 작업: immutable read planner와 저장소 조회 service. relation identity, participant
  role/order, context, exception, revision을 보존하고, 누락·projection loss를 결과에 담는다.
- 완료 기준: 역할이나 예외를 지운 투영의 반례를 포함한다. 단순 token 절약을 충분성으로 판정하지 않는다.
  정확한 조건이 너무 강하면 [근사 simulation](https://www.cs.ox.ac.uk/people/alessandro.abate/publications/HSA17.pdf)의
  출력 오차·transition coupling·실제 interface를 지정한 제한된 모형부터 사용한다.

## P3 — 한 번의 선택에서 지속적인 학습으로

기존 [평가 정리](../research/HSWM_FRESH_EVALUATION_LEAN_PROOF_2026-09-28.md)를
과거 transcript에 조건부인 라운드로 확장한다. 후보 생성은 이전 이력으로 결정할 수 있지만,
이번 라운드의 후보·평가 규칙은 이번 평가 결과를 보기 전에 고정해야 한다.

- Lean 목표: 조건부 fresh/독립 표본, 라운드별 오류 예산, 전체 예산 상계 아래 반복 선택의 오류를 제어한다.
  먼저 고정 라운드 길이와 오류 예산 합으로 구성하고, 데이터에 따른 중단이 필요할 때 confidence sequence로 확장한다.
  유용한 후보를 생성하는 문제와 후보를 안전하게 선택하는 문제를 구별하며, 충분한 이득이 있으면 선택되는 조건도 유지한다.
- TS/Effect 작업: transcript·split·평가 규칙·model/config를 결속하고 heldout 재사용을 막는다.
  정리의 평균·비용 단위에 맞는 계산과 보수적 반올림을 구현해 현재 bigint guard와의 대응을 증명한다.
- 문헌: [Learn then Test](https://arxiv.org/abs/2110.01052v5)는 독립 calibration과 다중 위험 제약,
  [Huber-Robust Confidence Sequences](https://proceedings.mlr.press/v206/wang23p.html)는 명시한 오염·moment 조건에서
  시간 전체의 신뢰 보장에 참고한다. 후자가 임의 drift나 적응적 데이터 재사용을 허용하지는 않는다.
  [GEPA](https://arxiv.org/abs/2507.19457v2)는 실행 trace로 수정 후보를 만드는 방법이며 개선 보장의 전제가 아니다.
- 완료 기준: 과거 이력 의존성·중단 규칙·평가 오염을 구분한 정리와 반례; frozen/evidence-only/sham/learned
  비교에서 같은 출발 상태·비용·독립 outcome을 사용한다. no-op과 거절도 표본에서 지우지 않는다.

## P4 — 관계 내용에서 구조 학습으로

현재 semantic revision의 의미 텍스트·disposition·uncertainty 변경을 넘어서려면,
**구조 변경이 다음 읽기와 dispatch를 바꾸는 consumer semantics**가 필요하다.

- Lean 목표: ADD/SPLIT/MERGE/SUPERSEDE 중 필요한 연산부터 버전형 delta로 정의하고,
  적용 전후의 실제 실행 의미와 owner·lineage·역할·순서·중복 참여·예외의 불변식을 연결한다.
- TS/Effect 작업: 기존 canonical revision 모델을 확장하는 순수 delta 함수와 실제 read/dispatch consumer.
  malformed·stale·conflicting 변경은 거절하고 과거 버전으로 재현할 수 있게 한다.
- 완료 기준: 저장 성공만 검사하지 않고 구조 수정이 다음 실행을 변화시키는 예제와 충돌 반례를 제공한다.
  고정 arity encoding 정리를 동적 topology 전체의 증명으로 재명명하지 않는다.

## P5 — 두 개의 국소 계산을 하나의 학습계로 합성

P1·P2의 실제 전이를 두 cell에 적용해 공유 원인·read/write 충돌·공동 outcome을 먼저 다룬다.
정확한 Map은 기존 refinement composition을 사용한다. 근사 Map은
[Rischel–Weichwald](https://proceedings.mlr.press/v161/rischel21a.html)의 해당 인과 모형·거리 조건이나
근사 simulation의 coupling 조건을 실제 대상에 맞게 인스턴스화한다.

- Lean 목표: Step/Learn 모두의 합성, 실행 순서·serializability 또는 명시적 거절, 공동 관측 보존.
  credit assignment에는 별도의 인과 가정이나 식별 설계가 필요하며, local gain의 합으로 대체하지 않는다.
- [Small-gain 계약](https://people.eecs.berkeley.edu/~sseshia/pubdir/hscc17-gain.pdf)은 각 부분의 계약과
  feedback 호환성·초기 조건이 있을 때 전체 계약을 구성하는 참고다. 해당 정리가 학습 이득을 보장하지는 않는다.
- 완료 기준: 기존 교환 가능한 쓰기의 효용 하락과 XOR 반례를 보존하고,
  두 규모의 공동 실행·학습 및 오차/비용을 검사한 뒤 재귀 깊이를 늘린다.

## 순서·비교·출처

**P1을 첫 구현으로, P2와 P3를 병렬로, 이후 P4와 두 규모 P5로 진행한다.**
국소 수정이 공동 결과에 해로운지는 P5 완성 전에도 기존 간섭 반례로 계속 검사한다.
순수 TS domain과 Effect I/O를 유지하고 RDF/SHACL/SPARQL/PROV 도구는 기존 교환·조회·출처 용도로 재사용한다.
이 계획 때문에 새 DB·검증 승인 절차·고정 H/W/A/F/Π 분해를 도입하지 않는다.

Hyperon은 [기존 직접 비교 조사](../research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)를 재사용한다.
고정 comparator는 `hyperon-experimental v0.2.10`, commit `3f76dc460da6961f57f69f6c3e550c59c74ada83`이다.
2026 whitepaper의 MeTTa/AtomSpace 관련 구현과 neural bridge 연구·설계를 구분하고,
같은 모델·과제·예산에서 비교한다. 이는 최신 버전 주장이나 HSWM 증명의 전제가 아니다.

[9월 20일 실제 학습 결과](../../results/HSWM_DGX_SEMANTIC_LEARNING_2026-09-20.md)의
frozen/learned 155/320, evidence-only 156/320과
[9월 21일 semantic no-op](../../results/HSWM_JEV_PRINCIPLES_2026-09-21.md)을 출발점으로 유지한다.
scripted 연결 검사를 실제 모델 학습 효과로 승격하지 않는다.

[출처 연결 JSON](artifacts/hswm_whole_system_lean_targets_2026-09-28/source-map.v1.json)은
P1–P5를 기존 소스·논문·전제·적용 한계에 연결한다. 선택한 원문 7개는 이미 수집한
[아카이브](../../_research/source_archive_2026-09-28/README.md)의 receipt ID와 파일 SHA-256을 재사용한다.
이 JSON은 작업 계획의 출처 지도이며 새로운 canonical AI 상태나 live KG 게시 결과가 아니다.
