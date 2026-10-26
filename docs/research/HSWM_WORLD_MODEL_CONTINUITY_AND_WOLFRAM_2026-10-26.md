# HSWM 월드모델의 연속적 발전과 Wolfram 기전 연결

2026-10-26 · 사용자 관점의 원문은 `USER_PRIMARY`, 대응·공학 해석은 `agent(codex) / SECONDARY_AI`.

**HSWM 자체를 월드모델로 놓고, 같은 지속 관계 상태의 표현·예측·행동·학습 능력을 발전시킨다.**
이것은 아래 사용자 관점을 기존 헌법과 연결한 AI 재서술이다. 개별 능력의 관측 범위와
확장 질문은 그 월드모델을 더 잘 이해하고 발전시키기 위한 정보다. 모든 연구 의무를 먼저
통과해야 월드모델이라는 이름을 허용하는 이분법적 분류로 사용하지 않는다.

## 사용자 관점과 기존 헌법

[이번 사용자 원문](../canon/sources/USER_PRIMARY_HSWM_WORLD_MODEL_CONTINUITY_2026-10-26.txt):

> 해당 내용 표준그래프 엔지니어링으로 구축해줘봐봐 그 너무 이분법적으로 그건 아니고 이건 맞다 이렇게 생각안해도되 ㅇㅇ; 나ㅡㄴㄴ HSWM 이 그자체로 충분히 월드모델이라고 생각함 ㅇㅇ

[통합 헌법](../canon/HSWM_CONSTITUTION.md)의 지속 Semantic Weight 하이퍼그래프는
세계·자기모델, 실행을 조직하는 하네스, 계속학습기의 역할을 함께 맡는다. 이번 관점은
그 연속성을 재확인한다. 기존의 단일 AI, 국소 LLM 연산, 결과 기반 관계 수정과 이어진다.
앞선 AI 답변의 여섯 조건은 기존 헌법에 대응하는 **발전 관점**으로 정리한다.

그래프에서 사용자 원문, AI의 연결 해석, 외부 저자의 설명, 구현 기록의 관측 범위를 각각
표현한다. 이 구분은 내용의 관계를 끊기 위한 것이 아니라 어떤 연결을 어떤 근거로
재사용할지 알려 주기 위한 것이다. 기존 실패·무개선 결과와 CR/FCL 의무도 함께 유지한다.

## 여섯 능력의 헌법·기전·근거·다음 사용

아래 C1–C6은 이번 조회를 위한 식별자이며 HSWM을 여섯 고정 subsystem으로 분해하지 않는다.

| 관점 | 헌법과 현재 연결 | Wolfram에서 이어 쓸 기전 | 발전 질문·관측 대상 |
| --- | --- | --- | --- |
| C1 지속 세계·자기 상태 | 1·2·7조. canonical atom의 UID·판본·owner, durable state, 선택된 관계의 읽기 | 국소 rewrite, 상태와 생성·소비 사건의 계보 | 외부 변화 뒤 관련 관계가 갱신되는가; 관측 시각·적용 조건·불확실성이 다음 사용까지 전달되는가 |
| C2 행동 조건부 예측 | 3·7·8조. 역할 있는 semantic frame, 실행 전 예측과 outcome 결속 | 주어진 규칙과 상태로 다음 상태를 생성하는 전이 | 관측 전에 고정한 예측의 오류가 관계/W 수정 후 새 사례에서 줄어드는가 |
| C3 미래 분기와 행동 선택 | 7조·FCL-6. 예측·관측·반사실 분기와 불확실성을 구별 | multiway 분기와 동형 상태 병합 | 제한된 예산에서 어떤 분기를 열고 실행할지; 다단계 과제 성공·비용·예측 불확실성 |
| C4 결과에 따른 관계·구조 학습 | 3·9조. 자동 활성화 학습, owner revision과 다음 사용; 제한된 구조 수정 | 사건 의존성, 규칙 적용 순서와 causal invariance의 조건 | 실행 계보를 바탕으로 수정 후보를 좁히고 제거·대체 비교로 기여를 확인; 새 경험 뒤 유지·회복 |
| C5 필요한 근거의 국소 획득 | 4·5·6조. 국소 선택·다단계 이동, 충분성·추가 획득 계약 | 정점 역인덱스와 영향받은 후보의 갱신 | 질문별 추가 읽기가 누락·오류를 얼마나 줄이는가; 원문·예외 보존과 총 비용 |
| C6 여러 해상도·프랙탈 합성 | 6·10조. Map, 하위 HSWM의 상위 cell 참여, 조건부 Step/Learn 보존 근거 | 관측자의 coarse graining, 관측량에 따른 상태 동치 | 요약·합성 후에도 역할·예외·허용 여부·다음 학습을 보존하는가; 새 조합·분리·재사용의 효용 |

헌법 원천: [1–3조](../canon/hswm/state.md), [4–6조](../canon/hswm/activation.md),
[7–9조](../canon/hswm/learning.md), [10–12조](../canon/hswm/composition.md),
[13–15조](../canon/hswm/assurance.md). 기존 연구의 구체적 관측은
[국소 학습 진단](../operations/HSWM_LOCAL_ACTIVATION_DIAGNOSIS_2026-10-18.md),
[다단계 활성화](../operations/HSWM_MULTIHOP_ACTIVATION_2026-10-24.md),
[workspace 실행](../operations/HSWM_WORKSPACE_ACTIVATION_2026-10-24.md),
[추상화의 실행·학습 보존](HSWM_OPERATIONAL_QUOTIENT_LEAN_2026-10-04.md)을 따른다.
이 기록들의 날짜·판본·실험 범위를 유지한다. 이번 구축은 내용의 표준 그래프 연결이다.

## Wolfram 기전의 구체적 접점

1. **국소 재작성과 계보.** 입력 패턴과 일치하는 관계를 소비하고 출력 관계를 생성하는 사건이
   세계의 변화를 구성한다. HSWM에서는 역할 있는 관계·그래프 프로그램·실제 실행을 연결하는
   기전으로 읽을 수 있다. 의미 연산의 결과를 다음 관측으로 교정하는 기존 학습 경로와 결합한다.
2. **Multiway 분기.** 가능한 규칙 적용을 경로로 펼치고 구조적으로 같은 상태를 병합한다.
   HSWM의 미래 분기에 응용할 때는 행동 조건·모델 판본·불확실성을 유지한다. 분기의 존재,
   확률, 과제 효용은 각각 표현하고, 탐색 예산 안에서 선택한다. 의미 상태 병합은 모양에 더해
   역할·조건·책임·이후 학습에서 관찰할 차이를 보존하는지 확인한다.
3. **사건 의존성과 인과 기여.** 생성된 관계를 다음 사건이 소비한 계보는 어떤 수정 후보를
   조사할지 알려 준다. 성공 기여를 판단할 때는 그 계보에 제거·대체·복원 관측을 덧붙인다.
   causal invariance는 적용 순서에 대한 특정 규칙계의 성질이다. HSWM에서는 독립 전이의
   순서 변경, 충돌하는 쓰기, 확률적 LLM 결과를 각각 검사하는 비교 질문으로 사용한다.
4. **관측자와 상태 축약.** Observer Theory는 유한한 관측자가 여러 미시 상태를 같은 인상으로
   묶는 과정을 다룬다. HSWM의 Map에는 어떤 질문·행동·학습을 위해 차이를 유지할지 명시한다.
   기존 operational quotient 연구는 제공된 가정 아래 실행과 학습의 허용 여부·출력·후속 상태를
   보존한다. 이 조건은 실제 요약을 선택하고 검사하는 기준으로 이어 쓸 수 있다.
5. **계산 예산과 예측 범위.** Wolfram은 계산적 비환원성과 함께 특정 관측량에서 계산을
   줄일 수 있는 부분을 논한다. HSWM에서는 국소 활성화·상위 요약·짧은 미래 전개·추가 관측을
   조합하는 근거로 사용한다. 항상 전체 미래를 펼쳐야 한다는 요구를 만들지 않는다.

Wolfram의 관계 세계와 HSWM의 의미 세계는 서로 연결할 수 있는 모델링 수준이다.
주어진 규칙의 전개, 관측으로부터 규칙을 수정하는 학습, 실제 과제의 효용을 이어서 연구한다.
울프람의 물리학적 해석과 HSWM의 의미 해석은 각 원천에 귀속시킨다.

### 확인한 원전과 코드

2026-10-26 이 대화에서 아래 공식 원전과 고정 커밋 소스를 읽었다. 웹 문헌은 URL·절·열람일로,
코드는 저장소·전체 commit으로 식별한다. 원격 응답 바이트를 보존하지 않은 웹 문헌에 콘텐츠
해시를 부여하지 않는다. 그래프의 로컬 source hash는 해당 해석·원문 파일의 실제 바이트다.

| ID | 원전 | 연결할 내용 |
| --- | --- | --- |
| W1 | [Wolfram Technical Introduction §6.1](https://www.wolframphysics.org/technical-introduction/the-updating-process-in-our-models/updating-events-and-causal-dependence/) | 국소 사건·생성 계보 |
| W2 | [§6.2 Multiway Systems](https://www.wolframphysics.org/technical-introduction/the-updating-process-in-our-models/multiway-systems-for-our-models/) | 분기·동형 상태 병합 |
| W3 | [§6.3 Causal Invariance](https://www.wolframphysics.org/technical-introduction/the-updating-process-in-our-models/causal-invariance/) · [§6.5](https://www.wolframphysics.org/technical-introduction/the-updating-process-in-our-models/causal-graphs-for-causal-invariant-rules/) | 규칙 조건과 순서 독립성 |
| W4 | [§7.3 Computational Capabilities](https://www.wolframphysics.org/technical-introduction/equivalence-and-computation-in-our-models/computational-capabilities-of-our-models/) · [§8.21](https://www.wolframphysics.org/technical-introduction/potential-relation-to-physics/specific-models-of-the-universe/) | 예측의 계산 부담·관측량·물리학 대응의 연구 범위 |
| W5 | [Stephen Wolfram, Observer Theory, 2023-12-11](https://writings.stephenwolfram.com/2023/12/observer-theory/) | 유한 관측자의 상태 축약 |
| W6 | [SetReplace `44c868bf4622e4542b306846ffdcc47c19d0bba8`, AtomsIndex.cpp](https://github.com/maxitg/SetReplace/blob/44c868bf4622e4542b306846ffdcc47c19d0bba8/libSetReplace/AtomsIndex.cpp) | Atom→TokenID 역인덱스 |
| W7 | [HypergraphRewritingEngine `c2728093fb170ccff4bfe5d4a83561920882b427`, rewriter.cpp](https://github.com/WolframInstitute/HypergraphRewritingEngine/blob/c2728093fb170ccff4bfe5d4a83561920882b427/hypergraph/src/rewriter.cpp) | 입력 검사·자식 상태·생성/소비 사건 |

기존 [엔진 소스 검토](CHU_OS_INDEXING_AND_WOLFRAM_ENGINE_2026-10-20.md)도 참조한다.
그 기록의 소스 관찰과 이번 연결 해석은 별도로 조회할 수 있다. Hyperon의 기존 핵심 비교
방향은 [상태·연산자 정전](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md)을 유지한다.

## 표준 그래프 계약과 실제 읽는 경로

독자는 `hswm-workspace` 사용자와 후속 연구자다. 새 번들 하나가 사용자 관점·여섯 능력·
일곱 외부 원전·네 기존 근거·다음 실험 제안을 연결한다. 기존 헌법과 identity·추상화·엔진
번들은 안정 UID의 anchor로 참조하며, `follow`는 정확한 목적지 번들 해시를 검사한다.
능력 노드는 문맥 있는 관계 묶음으로서 헌법·원전·관측·다음 질문을 함께 가진다.

기존 `AbstractNode`/`Concept`와 다음 관계를 재사용한다. 로컬 어휘이며 RDF 표준 자체의
새 predicate라고 주장하지 않는다. 각 edge는 출발·도착 1개이고, 아래 수는 주체별 관계 수다.

| 관계 | domain → range | cardinality·의미 |
| --- | --- | --- |
| `HAS_CONCEPT` | root → 능력·원전·근거·제안 | 0..n; 이 주제에서 탐색할 내용 |
| `HAS_SOURCE` | root/능력/제안 → 사용자 원문·외부 원전·기존 근거 | 1..n; 해석을 지지하거나 검토하게 하는 출처. 권위 자동 전파 없음 |
| `REFERENCES` | root/능력/제안 → 기존 anchor 또는 국소 노드 | 0..n; 적용 맥락·기존 연구로 이동, 동일성이나 인과성을 함의하지 않음 |
| `HAS_ENGINEERING_INTERPRETATION` | 사용자 원문 → root | 1; AI가 구성한 연결 해석을 원문과 함께 찾음 |

사용자 노드의 `exact_user_text`는 원문 파일과 같아야 한다. AI 노드는 `SECONDARY_AI`,
연결 edge는 AI의 문헌 대응으로 `PROPOSED`를 유지한다. 이는 사용자 관점을 보류하는 상태가
아니라 세부 대응의 작성 주체를 표시한다. `identity_position`과 각 능력의
`implementation_scope`, `evidence_scope`, `extension_question`을 별도 속성으로 조회한다.
SHACL은 이 속성·출처·관계 범위를 검사하고, SPARQL은 질문에 맞는 내용을 반환한다.
RDF 1.1/PROV-O projection은 기존 v2 도구가 생성한다. 생성 결과는 재생성 가능하므로 커밋하지 않는다.

```sh
src/hswm/effect-runtime/bin/hswm-workspace show world-model
src/hswm/effect-runtime/bin/hswm-workspace query world-model identity
src/hswm/effect-runtime/bin/hswm-workspace query world-model capabilities
src/hswm/effect-runtime/bin/hswm-workspace query world-model sources
src/hswm/effect-runtime/bin/hswm-workspace bindings world-model
src/hswm/effect-runtime/bin/hswm-workspace validate world-model
src/hswm/effect-runtime/bin/hswm-workspace navigate world-model
src/hswm/effect-runtime/bin/hswm-workspace follow world-model --uid sym:AbstractNode:hswm-constitution-learning
src/hswm/effect-runtime/bin/hswm-workspace read world-model --uid sym:Concept:hswm-world-model-2026-10-26-user
```

검증 질문은 원문을 정확히 찾는가, C1–C6이 헌법·원전·근거와 함께 반환되는가, 다음 질문과
기존 관측을 함께 읽을 수 있는가, 목적지와 출처의 바이트가 일치하는가다. 기존 표준 profile을
재사용하며 사용자 관점과 구현 관측을 섞는 변조도 거부하는지 확인한다.

구축 검증: v2 공통·주제 SHACL 적합, 원문 정확 대조, 능력 6개의 속성과 출처 연결 23건의
실제 SPARQL 반환값 대조, 로컬 출처 6개 해시 일치, anchor 9개의 목적지 이동을 확인했다.
AI 해석의 사용자 권위 승격·예측 근거 삭제·월드모델 관점의 완료 관문 치환은 각각 거부됐다.

## 다음 사용: 같은 월드모델을 더 잘 배우게 하는 실험

Wolfram 재작성 엔진을 통제 가능한 환경으로 연결하는 실험을 제안한다. 평가자는 규칙과
전체 상태를 보관하고, HSWM에는 정해진 부분 관측과 허용 행동을 제공한다. 현재 관계 상태에서
미래 결과를 예측하고 행동을 선택한 뒤 관측을 받아 같은 관계/W를 수정하고 다시 사용한다.

비교는 같은 모델·관측·예산에서 기억만 추가한 조건, W 동결 조건, 관계/W 학습 조건을 둔다.
새 초기 상태·규칙 변화·낡은 관측·역할 교환·요약에서 사라진 예외를 사용하고, 예측 오류·
행동 성과·회복·이전 능력 유지·비용을 함께 본다. 실제 모델 호출과 이 실험의 실행은 후속 범위다.
이번 그래프는 그 입력·근거·측정 질문을 기존 헌법과 실행 경로에 연결한다.
