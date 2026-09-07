# HSWM 적대적 검토와 최신 이론의 선택적 채택

기준 revision: `6e2e49f`. 권위: `SECONDARY_AI_REVIEW_AND_RECOMMENDATION`.
범위: 현재 조건부 preview/후보 합성의 실행 반례, checked-in 효능 기록, 최신 이론의 적용 조건.
전체 저장소·환경·논문 증명의 완전한 감사 또는 새 HSWM 연구 실험이 아니다.

현재 가장 중요한 개선은 **후보가 더 유용한 구분을 만들고, 독립적으로 얻은 경험에서
그 구분이 새 과제에도 유효한지 확인하는 연결**이다. 학습 이론의 장점도 성립 조건·비용과
함께 가져와야 한다. 이론 이름, KG 크기, 통과한 소프트웨어 검사 수는 효능의 대용물이 아니다.

[헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 token-native LLM-function
macro-neural HSWM, schema-relative single owner·typed reference·outcome-bound revision을
유지한다. [적응적 연구 전략](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)에
따라 현재 방법은 바꿀 수 있다. FCL-1..8과 `INTEGRATED_CLAIM_UNJUDGED`도 유지한다.
이번 conceptual delta는 정체성 변경이 아니라 **후보 탐색의 편향, 의미 중복, 관찰 선택과
이후 행동의 평가를 구체적 반례에 결속하는 것**이다.

## 1. 성능 주장에 대한 적대적 판정

| 주장 | 판정 | 근거 |
|---|---|---|
| 관계·상태가 다음 선택을 조건화한다 | 제한된 관측이 살아 있음 | opaque v5와 preview의 관계 교체/복원 |
| 공개 예시에서 AST 후보를 생성한다 | 제한된 공학 동작 확인 | 연구자가 준 완전 관측·유한 문법 안의 conjunction 열거 |
| 새로운 과제의 성능이 좋아졌다 | 아직 입증되지 않음 | 현재 preview에는 held-out 환경 결과가 없고 G1 미평가 |
| 일반 LLM/RAG/경험 재사용보다 유리하다 | 비교 근거 부족 | S-5는 HSWM arm이 없고 B0/B2도 unpaired·budget 불일치 |
| 더 큰 프랙탈 합성이 하위 학습의 미입증을 해결한다 | 허용되지 않음 | FCL과 기존 upstream/downstream 증거 경계 |

[v5 결과](../../results/HSWM_G1_OPAQUE_IDENTIFIABILITY_V5_RESULTS_2026-09-06.md)의
96/96 합계는 v3/v4/v5 기술 통계이며 새 단일 확증 실험이 아니다. v3/v4의 원래 실패 판정과
[EFFICACY](../../EFFICACY.md)의 과거 P1 RED는 유지한다. 정적 retrieval의 양성과
SWM-0W의 좁은 양성도 각각의 범위에서 보존하며, 전체 프로그램을 전부 실패로 부르지 않는다.
[S-5 비교](../../results/HSWM_S5_B0_B2_COMPARISON_2026-09-06.md)는 HSWM의 상대 성능을
추정할 수 없다. G0 NOT_PASSED, G1 NOT_EVALUATED, D-4 미완료 상태는 그대로다.

## 2. 실행해서 확인한 네 적대적 사례

소스: [`conditional.py`](../../src/hswm/cells/conditional.py).
소스 SHA-256: `0a56063a8cd68f6475f9ac9654f82e980d82026a4923912d67c485ffe318ddc5`.
[재현 프로그램](../../_research/causal_composition/audits/conditional_preview_adversarial_2026_09_07.py)과
[실행 결과](../../_research/causal_composition/audits/conditional_preview_adversarial_2026_09_07.json)를 함께 남긴다.

| ID·우선순위 | 반례·관측 | 정확한 의미와 수정 방향 |
|---|---|---|
| A1·최적화 시 주의 | 세 binary field의 모든 8개 완전 관측 입력에서 outcome=False를 제공하면 후보 8개가 모두 FALSE다. 예: `a=0 AND a=1`. 그러나 missing을 포함한 27개 관측에서는 **서로 다른 진리표 8개**다. | 완전 관측에서의 구분력은 같지만 UNKNOWN 동작은 다르다. 이는 현재 합성의 오류가 아니라 단순 진리표 기반 중복 제거안의 반례다. 읽기·UNKNOWN·권한·비용까지 동등한 후보만 합쳐야 한다. 후보 수를 독립적인 성공 능력 수로 세지 않는다. |
| A2·높음 | 10개 field가 모두 0일 때 False, 모두 1일 때 True인 두 예시에서 a0~a7만 남고 똑같이 일관된 a8·z는 cap 때문에 빠진다. `examined=16`, 일반 PROPOSED 상태다. | 이름 정렬·상한에 따른 탐색 편향이다. 현 문서가 유한 탐색을 공개하므로 문법 완전성 위반은 아니다. cap/budget/space-exhausted 종료 이유와 아직 검토하지 않은 후보 범위를 내보내야 한다. 새 입력에서 첫 후보를 진실로 취급하면 안 된다. |
| A3·실행 연결 전 높음 | 같은 relation·입력 revision과 관측 source에서 관측값만 0→1 바꾸면 static preview UID와 read trace가 같지만 WITHHOLD→ACTION_PROPOSAL로 바뀐다. | UID는 의도적으로 정적이므로 자체 결함은 아니다. 그러나 실제 step receipt로 쓰기에 정보가 부족하다. 별도 step input digest, 관측 record/digest, 시각·budget·current-check 참조와 선택 rule을 기록한다. 거대한 새 장부는 필요 없다. |
| A4·낮음 | malformed AST JSON은 `Reject`가 아닌 `JSONDecodeError`로 나온다. | 입력은 실패하며 effect/admission 우회는 없다. 호출자가 Reject만 처리하면 복구 경로가 깨지는 API 오류 형태의 불일치다. 경계에서 구조 검증과 일관된 Reject로 정규화한다. |

A1에서 “긍정 예시가 없으면 가설 제안 금지”를 새 규칙으로 만들면 안 된다. 원 계약은
명시된 prior만으로도 제안을 허용한다. 항상 실패하는 가설 자체도 환경에 따라 유효할 수 있다.
문제는 이를 성공 능력처럼 쓰거나 동일한 의미를 여러 개의 구분으로 세는 것이다.

현재 provenance의 caller assertion, preview-only, 최대 3개 equality conjunction,
미구현 admission은 [reference 문서](HSWM_CONDITIONAL_CAPABILITY_REFERENCE_2026-09-07.md)에
이미 공개된 한계다. 적대적 검토가 그 한계를 새 보안 취약점이나 과학적 RED로 바꾸지 않는다.

## 3. 최신 이론에서 가져올 정확한 부분

아래 연결은 본 검토의 HSWM 적용 제안이다. 논문의 보고 결과가 HSWM에 이전됐다는 뜻이 아니다.

| 순서 | 가져올 부분 | 지금 적용할 범위·비용·실패 조건 |
|---|---|---|
| 1 | 명시적 탐색 종료 이유, 관측 digest와 일관된 오류; 제한된 후보 동등성 검사 | A1~A4에 대응하는 작은 공학 보완이다. 고급 이론의 효능으로 포장할 필요가 없다. 동등성 검사는 완전 관측의 값뿐 아니라 missing/stale·읽기·권한·비용을 보존해야 한다. 열거 비용을 측정하고 확인하지 못한 동등성은 UNJUDGED로 남긴다. |
| 2 | Narcissus의 AST 문맥을 이용한 탐색 순위와 제안에 없는 문법 규칙의 탐색 유지 | 현재 conjunction 열거와 비교하는 별도 후보 생성 정책으로 시험한다. 제안·parse·탐색의 총비용을 맞춘다. 작은 양의 점수만으로 유한 beam의 완전성이 보장되지는 않으므로, unguided 탐색 예산·재개 상태를 별도로 보존한다. |
| 3 | 인과 발견 연구의 ‘LLM prior는 틀릴 수 있음’과 ‘현재 개입으로 구별 불가능함’ | 경쟁 AST가 다른 예측을 하는 허용 관찰/행동을 다음 probe로 제안한다. 목적·예상 결과·대조 조건은 outcome 전에 기록한다. 판별 관찰이 없으면 보류하며, 관찰상 구분만으로 causal credit을 주지 않는다. |
| 4 | TheoryCoder-2의 전제조건·효과를 가진 재사용 가능한 추상화 | 먼저 하위 관계의 fresh/retention 결과를 얻고, 반복되는 AST·disposition의 재사용 후보만 제안한다. read/compile/유지 비용까지 줄지 않으면 압축을 채택하지 않는다. object-state scaffold와 predicate 표현 취약성을 함께 가져와 시험한다. |
| 5 | ExpeL·GEPA의 경험 반성으로 후보를 수정하고 성능·비용을 비교하는 방식 | 반성문은 후보 생성 입력으로만 쓰고, 직접 relation admission을 만들지 못하게 한다. 처음에는 동일 이력의 단순 lesson/retrieval과 재추론 baseline으로 비교한다. 다목적 Pareto 유지가 필요한지는 metric을 확보한 뒤 판단한다. |
| 뒤로 | Nested Learning·Meta-TTL의 서로 다른 시간척도/적응 정책 학습 | 평가 단위를 episode 내 적응과 episode 간 지속 변화로 구분하는 아이디어는 참고한다. 전체 backend 교체, 진화적 outer loop, 여러 단계 학습기 도입은 단순 경로의 효용·유지비를 측정한 뒤 검토한다. |

**Narcissus:** AST 문맥·재사용·regularization이 제안 기반 탐색을 유도한다.
본문의 bounded beam 설명은 잘못된 heuristic이 후보를 잘라 정답을 잃을 수 있다고 명시한다.
따라서 ‘모든 문법 규칙에 양의 점수 → 정답 탐색 보장’으로 읽으면 안 된다.
[원문 방법·탐색·ablation](https://arxiv.org/html/2608.25657v1).

**인과 식별:** Causal ABA는 LLM의 의미 prior와 관측 제약을 결합하고, intervention-only
연구는 특정 개입·faithfulness 가정 아래 식별과 남는 동등류를 다룬다. 어느 방법도 허용되지
않은 관측을 만들거나 prior만으로 HSWM credit을 확정해주지 않는다.
[Causal ABA](https://arxiv.org/abs/2602.16481v2),
[Intervention-only discovery](https://arxiv.org/abs/2607.11816v1).

**TheoryCoder-2:** 경험 기반 추상화와 계층 계획을 연결하지만, 본문은 object-oriented
text state를 전제하고 predicate classifier가 상태 표현에 취약한 사례를 공개한다.
‘문법·관측 자체를 자율 발견’하는 증거로 확대하면 안 된다.
[원문 Discussion·Limitations](https://arxiv.org/html/2602.00929v1).

**경험 재사용·메타학습:** ExpeL의 경험 추출과 GEPA의 반성 기반 후보 탐색은 강한
대조/후보 생성 경로다. Meta-TTL은 적응 정책에 대한 outer-loop search가 추가된다.
실행 과제와 outcome 경계가 없는 현재 preview 위에 이를 올리면 비교할 개선 신호가 없다.
[ExpeL](https://arxiv.org/abs/2308.10144v3),
[GEPA](https://arxiv.org/abs/2507.19457v2),
[Meta-TTL](https://arxiv.org/html/2604.00830v3),
[Nested Learning](https://arxiv.org/abs/2512.24695v1).

## 4. 다음 실험이 답해야 할 질문

다음 순서는 새 gate나 성공 기준 완화가 아닌 적용 우선순위다.

1. A2~A4를 보완하고 후보의 의미 차이·truncation·step provenance를 검사한다.
   중복 제거를 도입한다면 A1의 부분 관측 차이를 보존하는지 먼저 확인한다.
2. 현재 enumerator, 동일 정보의 재추론/lesson baseline, guided AST 후보 경로를 같은 task/seed,
   backbone, 이력, 허용 관측과 총비용 기회에서 비교한다. 아직 얻지 않은 결과를 proposer가
   보지 못하게 한다. outcome source와 제안자는 역할·프로세스 경계를 가진다.
3. 새로운 instance와 선언된 task-family shift를 구별하고, 성공·보류·실패·관찰 수·토큰·지연·
   proposal/compile/유지비를 모두 남긴다. retention, exact REMOVE/RESTORE와 SHAM도 유지한다.
4. 기존 G1 계약의 성공 기준을 별도 사전 명세에 그대로 결속한다. 임의 숫자 문턱을 이
   검토에서 새로 발명하지 않는다. 효과가 없으면 그 후보 경로만 폐기하고 음성 계보를 보존한다.

KG는 현재 **찾아볼 연구 색인**으로 적합하다. 35개 항목 대부분은 초록·metadata 검토이므로
설계 채택의 충분 근거가 아니다. 우선 채택할 논문에 한해 방법, 가정, task/split, 정보 접근,
비용, 실패 사례를 확인해야 한다. 이번에는 Narcissus·TheoryCoder-2·Meta-TTL의 본문을 열어
관련 절을 검토했다. 전체 35개 논문을 재현하거나 정리 증명을 감사한 것은 아니다.
기존 게시된 literature bundle bytes는 그대로 보존한다.

## 5. 재현과 산출물 경계

```sh
uv run python _research/causal_composition/audits/conditional_preview_adversarial_2026_09_07.py
uv run pytest -q tests/test_conditional_capability.py tests/test_hswm_cellular_runtime.py
```

네 적대적 소프트웨어 사례를 실행해 확인했고 기존 검사 31개는 통과했다. A1은 제안한
최적화에 대한 반례, A2·A3은 알려진 범위의 구체적 한계, A4는 오류 형태의 불일치다.
기존 검사는 그 검사가 대상으로 삼은 동작을 확인하며 이번 사례까지 검증한 것은 아니다.
이번 산출물은 감사·추천 문서와 재현 프로그램이며 알고리즘 변경·새 환경 run·성능 개선은
발생하지 않았다. routine software audit이므로 연구 결과 장부나 gate를 승격하지 않는다.
