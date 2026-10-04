# 동굴 비유에서 실행·학습을 보존하는 표현으로

2026-10-04 · `SECONDARY_AI_CONDITIONAL_FORMAL_RESULT`

**HSWM에는 실제 Lean4 증명이 있고, 이번에는 허용·거절을 포함하는 상태 추상화 증명을
추가했다. 전체 HSWM의 정확성·성능이나 metahumotonic의 완전성·유일성은 증명하지 않았다.**
이 결과는 [직전 동굴·metahumotonic 연구](HSWM_CAVE_METAHUMOTONIC_RESEARCH_2026-10-04.md)의
“추상화가 개입과 학습을 보존하는가”라는 질문을 기존 결정적 Step/Learn 모형에서 구체화한다.

## 이미 있던 증명과 이번에 닫은 공백

[기존 검증 감사](HSWM_LEAN_VALIDATION_REVIEW_2026-09-28.md)는 decoded 의미 수정의 구조적
일관성, 선택한 역할의 국소 읽기, 조건부 통계 보장을 다룬다. 이번에 lifecycle 두 모듈과
통계 감사기의 여섯 소스를 다시 컴파일하고 정리별 공리를 검사했다. 실제 TS 전체의 의미,
LLM 응답의 진실성, 학습으로 좋은 후보를 발견한다는 주장은 여전히 그 결론 밖이다.

[기존 출력 행동 최소성](../../formal/HSWMBehavioralMinimality.lean)은 모든 유한 Step/Learn
기록의 **출력**이 같으면 상태를 같은 부류로 묶는다. 그런데 Learn이 허용돼도, 거절돼도
출력이 `none`일 수 있다. 기존 파일 자체에 이 차이를 놓치는 반례가 있었다.
[기존 연산적 추상화](../../formal/HSWMOperationalAbstraction.lean)의 `FibreCriterion`은
허용 여부까지 보존해야 하므로 두 증명 사이에는 실제로 공백이 있었다.

[새 모듈](../../formal/HSWMOperationalQuotient.lean)은 각 이벤트의 관측을
`(허용 여부, 출력)`으로 확장한다. 같은 이벤트 열을 두 상태에서 실행했을 때 이러한 관측
기록이 모든 유한 길이에서 같으면 `OperationallyEquivalent`로 정의한다. 여기서 “모든”은
몇 개의 샘플을 검사했다는 뜻이 아니라 임의의 이벤트 리스트에 대한 전칭 명제다.

| 증명 | 정확한 내용과 전제 |
| --- | --- |
| `operational_quotient_fibre_criterion` | 위 동치류로 상태를 묶으면 Step/Learn의 허용 여부, 허용된 Step 출력과 다음 동치류, 허용된 Learn의 다음 동치류가 보존된다. |
| `operational_quotient_refines`, `operational_quotient_preserves_run` | 각 동치류의 대표 상태를 돌려주는 함수와 그 올바름을 **제공하면**, 기존 대표 상태 구성으로 정확한 추상 실행기를 얻고 모든 유한 혼합 실행을 보존한다. |
| `exact_refinement_preserves_observedTrace` | 기존 `ExactRefinement`가 성립하는 임의의 상태 매핑은 허용·거절을 포함한 새 기록도 보존한다. |
| `distinguishing_trace_refutes_exact_abstraction` | 같은 요약으로 합쳐진 두 상태에 서로 다른 관측 기록을 만드는 유한 이벤트 열이 있으면, 그 매핑으로는 정확한 추상 실행기를 만들 수 없다. |
| 두 구체적 반례 | 출력은 항상 같아도 Learn 허용 여부가 다르면 새 동치가 아니다. 현재 보이는 비트만 같아도 숨은 비트가 Learn 뒤 출력에 영향을 주면 그 요약은 정확한 학습 추상화가 될 수 없다. |

`refinementFactor_on_source`는 대표를 제공한 정확한 추상화의 코드를 다시 이 동치류로
연결한다. 이는 선언된 관측 정보의 보존에 관한 성질이며, 하이퍼그래프의 byte/token 최소성이나
세계의 유일한 표현을 뜻하지 않는다. 거절된 이벤트의 사용되지 않는 원시 전이는 보존을
요구하지 않는다. 실행 모형은 거절 시 상태를 유지한다.

## 문헌과의 연결 및 HSWM 적용 범위

[Rubenstein 외, Causal Consistency v1 §4.3–4.4](https://arxiv.org/html/1707.00819v1#S4.SS3)는
상태뿐 아니라 허용 개입과 개입 후 분포의 대응을 요구한다. 이는 출력 정렬만으로 충분하다고
가정하지 않는 연구 방향의 근거다. **이번 Lean 모듈은 그 논문의 확률적 SEM 정리를
형식화한 것이 아니다.** 공통 Action/Evidence를 사용하는 결정적 전이계이며 개입의 부분순서,
개입 번역 함수, 확률분포, 실제 환경의 인과적 식별을 구현하지 않았다.

HSWM의 MapSpec/read planner에는 “같은 frame으로 합치는 상태가 이후 허용·거절과 수정에서
갈리는가”를 검토할 의무로 연결한다. 실제 graph schema에 `Dynamics`를 인스턴스화하고,
허용한 이벤트·관측과 runtime의 대응을 보인 뒤에야 이 정리를 실제 planner에 적용할 수 있다.
현재는 그러한 planner를 자동으로 찾거나 실행 경로에서 admission을 바꾸는 기능이 없다.

모든 유한 기록에 대한 동치는 일반적으로 유한 실험만으로 판정되지 않는다. 대표 상태를
선택하는 실행 가능한 알고리즘도 이번 정리에 포함하지 않는다. 실제 LLM의 확률성,
미선언 provenance·owner·권한·비용, 열린 환경의 관측 충분성은 별도 의무다. 필요하다면 그
관측을 모형에 먼저 포함해야 한다. 사용자 이데아 명명은 [기존 정전](../canon/USER_PRIMARY_HSWM_METAHUMOTONIC_IDEA_2026-10-04.md)으로 유지한다.

Hyperon 필수 비교와 CR/FCL 기준, 기존 음성 결과도 유지한다. 이번에는 새 아키텍처의
우월성이나 독창성을 판정하지 않았고 Hyperon backend 및 실모델 실험을 실행하지 않았다.
직전 연구의 버전이 고정된 비교 자료와 네 `NOT_RUN` 평가 계획을 변경하지 않는다.

## 실제 검사와 재현

Lean 4.32.1을 고정했다. 새 정리·보조정리 14개와 관련 기존 추상화 정리 19개를 새 OLean
디렉터리에서 다시 컴파일하고 공리를 검사했다. 새 모듈이 쓰는 공리는 `propext`,
`Quot.sound`이며 `sorryAx`, 사용자 axiom, `native_decide`는 없다. 숫자 14는 보조정리까지
포함한 선언 수이지 독립적인 HSWM 성능 보장 14개라는 뜻이 아니다.

원본 소스는 컴파일되고, 관측에서 허용 정보를 지우거나 후속 상태 전이를 무시하는 두
변형은 컴파일에 실패한다. 이는 증명 전제와 정의의 민감도 확인이며 실모델 평가가 아니다.
기존 lifecycle 19개·통계 44개 선언의 공리 재검사도 통과했다. 새 모듈의 import closure를
빈 환경에서 검사하는 `leanchecker --fresh`는 처음 120초 제한에 도달했고, 새 300초 한도에서
143.452초에 통과했다. 같은 커널을 사용하는 검사다. 범위·시간 제한과 소스 hash는
[검증 기록](../../_research/operational_quotient_2026-10-04/verification.v1.json)에 보존한다.

[Lean 공식 검증 안내](https://lean-lang.org/doc/reference/latest/ValidatingProofs/)에 따라
컴파일·공리 검사·OLean replay와 정리 문장의 의미 검토를 구별한다. 설치된 4.32.1에서
replay 명령은 `leanchecker`다. 같은 Lean 커널의 재검사이며 독립 구현의 checker 검증은 아니다.

```sh
# 저장소 루트
npm --prefix src/hswm/effect-runtime run build
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile operational-quotient --output .hswm-local/NEW_QUOTIENT_AUDIT
node src/hswm/effect-runtime/dist/semantic-philosophy-proof-process.js --profile semantic-lifecycle --output .hswm-local/NEW_LIFECYCLE_AUDIT
node src/hswm/effect-runtime/dist/statistical-learning-proof-process.js --output .hswm-local/NEW_STATISTICAL_AUDIT

# formal 디렉터리에서 실행해야 해당 lean-toolchain이 선택된다.
cd formal
lake build
lake env leanchecker --fresh --verbose HSWMOperationalQuotient
```

`lake --dir formal`만 저장소 루트에서 사용하면 elan이 먼저 루트의 다른 toolchain을
선택할 수 있다. 이번 초기 개발 호출에서도 4.34.1이 선택돼 기존 파일 컴파일이 실패했고,
`formal/`에서 고정 4.32.1로 실행해 해결했다. 기존 증명 소스를 그 다른 버전에 맞춰 바꾸지 않았다.

## 표준 그래프 연결

새 읽기용 bundle과 `operational-quotient` workspace entry에 정리, 소스 hash, 검증 기록,
미해결 경계를 연결했다. 기존 metahumotonic bundle은 바이트를 보존하고 그 추상화 가설의
UID를 새 bundle에서 참조한다. 해당 가설 전체나 경험적 평가를 `PROVED`/`PASS`로 바꾸지 않는다.

RDF/PROV-O projection, SHACL, SPARQL은 기존 도구를 재사용한다.
`proofs`는 네 결과의 정확한 UID·Lean 정리·소스 hash를, `gaps`는 runtime 연결과 효능의
미완료 상태를 보여준다. 로컬 어휘의 방향·역할 계약과 예상 결과는
[그래프 계약](../../_research/operational_quotient_2026-10-04/graph-contract.v1.json)에 있다.

```sh
src/hswm/effect-runtime/bin/hswm-workspace validate operational-quotient
src/hswm/effect-runtime/bin/hswm-workspace query operational-quotient proofs
src/hswm/effect-runtime/bin/hswm-workspace query operational-quotient gaps
```

공유 live KG와 실행 중인 HSWM canonical state에 쓰지 않는다. 이 결과는 출처가 결속된
조건부 형식 연구이며 성능 측정이나 완전한 metahumotonic의 인증이 아니다.
