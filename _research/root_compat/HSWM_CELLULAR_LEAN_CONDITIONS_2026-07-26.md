# HSWM cellular metaneural Lean conditions

> **status**: `USER_PRIMARY_DIRECTION + SECONDARY_AI_FORMALIZATION`
> **date**: 2026-07-26
> **lane**: `BRIDGE + ENGINEERING`
> **formal module**: `formal/HSWMCellular.lean`
> **claim boundary**: Lean은 타입·합성·rollback 계약을 검사한다. HSWM이 실제로 더 큰 AI라는
> 과학적 효능은 증명하지 않는다.

## 0. USER_PRIMARY

> “cell 같은 존재인거야 하나의 llm 이 그 신경망 하나의 함수처럼 동작하는거지 신경망 웨이트 함수처럼 뭔말인지 아냐 ㅇㅇ? hswm 를 좀 전체적 추상적으로 접근좀 해줘봐 ㅇㅇ”

이 발화와 기존 정전을 합치면 HSWM의 방향은 다음과 같다.

> **논리적 LLM 인스턴스는 typed stateful semantic cell이고, hyperedge의 Semantic Weight는
> 여러 cell 출력을 수신 cell의 입력으로 옮기는 operator-valued macro-synapse이며, 실현된
> HSWM 전체도 다시 하나의 stateful cell 인터페이스로 노출될 수 있다.**

위 한 줄 아래의 구체 Lean 타입과 정리는 `SECONDARY_AI` 형식화다.

## 1. 세 스케일

| scale | object | 의미 |
|---|---|---|
| micro | `Cell.modelKey`가 가리키는 LLM parameter | cell 내부 neural weight; 여러 논리 cell이 공유 가능 |
| meso | `SemanticSynapse.transform/gate/efficacy/uncertainty` | cell 사이 operator-valued semantic weight |
| macro | `MorphogenesisClock` | cell·synapse·topology·interface의 구조 가소성 |

일반 신경망의 scalar activation 대신 HSWM packet은 typed semantic object다. 따라서 synapse도
`Real` 하나가 아니라 다음 함수다.

\[
\mathcal W_e:\operatorname{List}(Packet)\times Context\to Packet
\]

`CellularHSWM.typedSynapse`는 tail cell들이 emit한 packet들을 이 함수가 head cell이 accept하는
packet으로 옮긴다는 조건이다.

## 2. Lean이 직접 검사하는 조건

| id | Lean symbol | 조건 |
|---|---|---|
| L1 | `HSWM.Cell.step_typed` | accepted input을 실행하면 declared output type을 보존 |
| L2 | `HSWM.Cell.thenCell` | 두 cell은 명시적 compatibility proof가 있을 때만 합성 |
| L3 | `HSWM.CellularHSWM.tail_nonempty` | 모든 semantic synapse는 빈 tail이 아님 |
| L4 | `HSWM.CellularHSWM.typedSynapse` | n-ary tail output이 head input contract를 만족 |
| L5 | `HSWM.CellularHSWM.route_disabled` | gate=false인 synapse는 `none`으로 fail-closed |
| L6 | `HSWM.CellularHSWM.route_enabled_is_head_typed` | 열린 route가 반환한 packet은 head-typed |
| L7 | `HSWM.Realization.asCell` | 내부 상태를 감추면 전체망도 `Cell Packet` 인터페이스 |
| L8 | `HSWM.PlasticityClock.sealTrace` | trace seal 타입에는 `Outcome` 입력이 없음 |
| L9 | `HSWM.PlasticityClock.rollback_apply` | candidate weight update는 delta로 rollback 가능 |
| L10 | `HSWM.MutationProposal.kind` | structural proposal 하나는 mutation class 하나만 소유 |
| L11 | `HSWM.MorphogenesisClock.rejected_proposal_is_noop` | reject된 topology/cell proposal은 원상태 유지 |
| L12 | `HSWM.connection_alone_is_not_larger_ai` | cell 연결만으로 larger-AI 조건이 성립하지 않음 |

## 3. Lean 정의에 넣되 아직 구현과 동일하다고 주장하지 않는 조건

1. `SemanticSynapse`는 operator-valued지만 현재 Python `SemanticWeight`는 slow scalar
   `log_salience`가 중심이다. 따라서 runtime binding은 `PARTIAL_MATERIALIZATION`이다.
2. `Realization.run`은 scheduler·budget·stop rule을 추상화한다. 현재 Lean 모듈은 termination이나
   fairness를 증명하지 않는다.
3. `PlasticityClock`은 올바른 순서와 rollback을 형식화하지만 credit의 통계적 정당성은 증명하지
   않는다.
4. `MorphogenesisClock`은 evidence를 입력받고 한 mutation class만 제안하지만 evidence가 충분한지,
   candidate가 성능을 높이는지는 실험 대상이다.
5. 같은 `modelKey`를 공유하는 두 cell은 같은 micro-weight를 쓸 수 있지만 role·state·port가
   다르다는 사실만으로 specialization 효과가 자동 발생하지 않는다.

## 4. 반드시 실험으로 충족해야 하는 larger-AI 조건

`HSWM.LargerAIConditions`는 다음 일곱 조건의 conjunction이다.

1. **persistent macro state**: episode를 넘어 HSWM 자체의 상태가 남음;
2. **closed outcome credit**: outcome이 사용된 synapse trace에 credit을 돌려줌;
3. **semantic-weight mediation**: learned `W`를 제거·shuffle하면 해당 이득이 사라짐;
4. **topology mediation**: learned `H` rewrite 제거 시 structural adaptation이 사라짐;
5. **transfer beyond transcript**: transcript/answer 없이 A의 학습이 frozen B에 전달됨;
6. **strongest-cell control 초과**: 전체망이 가장 강한 단일 LLM과 equal-budget full-context를 초과;
7. **retention and rollback**: 새 학습 후 old regime과 exception을 보존하고 실패 update를 복구.

Lean theorem이 아니라 sealed receipt가 각 명제를 채워야 한다. 현재 HSWM은 이 conjunction을
충족했다고 주장할 수 없다.

## 5. 다음 최소 falsifier

`HSWM-CELL-0`:

- frozen LLM-cell 3개;
- 역할이 있는 irreducible ternary semantic synapse 1개;
- bounded recurrent realization 1개;
- outcome-before/after가 분리된 eligibility/credit update;
- controls: scalar synapse, shuffled synapse, removed cell, full-context, strongest single cell;
- positive requirement: learned semantic operator 제거가 gain의 최소 70%를 선택적으로 제거;
- composition requirement: 세-cell motif를 `Realization.asCell`로 감싼 뒤 다른 motif와 연결해도
  공개 interface behavior가 보존됨.

이 falsifier를 통과하기 전 `causal emergence`, `organism`, `larger AI`는 연구 가설이다.

## 6. 권위와 바인딩 경계

- 사용자 발화: 본 문서 §0에 literal 보존;
- 기존 정전: `HSWM_CANONICAL_RESEARCH_DIRECTION_20260724.md`;
- 수학 protective belt: `PROM_16_HSWM_SEMANTIC_WEIGHT_FIELD_MATHEMATICS_2026-07-26.md`;
- Lean: `formal/HSWMCellular.lean`;
- 부분 runtime: `prom_search_hswm/hswm_open_composition.py`;
- Longinus: `LONGINUS_HSWM_CELLULAR_LEAN_BINDING_2026-07-26.json`;
- KG: write 권한이 이번 요청에 없으므로 proposed anchors만 기록하고 write하지 않는다.
