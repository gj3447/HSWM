# PROM 9 — LLM 함수로 움직이는 HSWM 시멘틱 신경망

> 날짜: 2026-07-24
> 상태: `DESIGN_LOCKED_NOT_PREREGISTERED`
> 권위: `SECONDARY_AI_RESEARCH_AND_ENGINEERING_DESIGN`
> 기계 계약: [`prom9_semantic_neural_network.v1.json`](prom_search_hswm/prom9_semantic_neural_network.v1.json)
> 검증기: [`prom9_protocol.py`](prom_search_hswm/prom9_protocol.py)

## 0. 결론

HSWM을 사용자가 말한 **“LLM을 신경망 연산 함수로 쓰는 거대한 hypergraph semantic
neural network”**로 만드는 가장 작은 구현은 다음이다.

```text
QueryEnvelope
  -> QF: query compiler
  -> BF: query-conditioned bond proposer
  -> frozen HSWM readout
  -> AF: evidence-bound answer synthesizer
  -> external outcome
  -> used-bond eligibility
  -> fast bond candidate
  -> fresh / retention / canary / removal evaluation
  -> repeated effect only: slow semantic-weight candidate
  -> approval + CAS activation
```

여기서 LLM 하나는 뉴런 하나라기보다 **typed nonlinear function**이다. HSWM의 bond와 port가
함수의 입력·출력·연결 강도를 결정한다. 순간 route는 activation이고, 외부 결과를 거쳐 검증된
새 snapshot이 남아야 learning이다.

이 PROM은 위 설계와 실험 계약을 고정하지만 아직 예측을 등록하거나 결과를 만들지 않는다.

## 1. 계산 정의

각 LLM 함수 노드 (i)를 다음처럼 둔다.

\[
y_i=f_i\left(x_i,R_i(H_t,q);m_i,p_i\right)
\]

- (H_t): 현재 HSWM hypergraph snapshot;
- (R_i): query와 typed port에 따라 읽을 bond/payload를 결정하는 readout;
- (m_i): frozen model revision;
- (p_i): frozen role prompt;
- (x_i,y_i): schema로 제한된 typed input/output.

현재 query에서의 fast potential은:

\[
S_t(q,b)=S_{base}(q,b)+\lambda_q a_\theta(q,b),\qquad a_\theta(q,b)\le0
\]

외부 결과가 도착한 뒤 사용된 bond의 eligibility는:

\[
z_t(b)=\rho z_{t-1}(b)+use_t(b),\qquad
\delta_t=r_t-\hat r_t
\]

반복된 효과만 slow weight 후보로 만든다.

\[
\ell'(b)=clip\left(\ell(b)+\eta\delta_tz_t(b)-\lambda d_t(b),\ell_{min},0\right)
\]

이 식은 active state를 즉시 바꾸지 않는다. immutable candidate를 만들 뿐이고, 독립 평가와
사람 승인, CAS receipt까지 통과해야 새 epoch가 된다.

## 2. 최소 LLM 함수망 F1

### QF — Query Compiler

- 입력: `QueryEnvelopeV1`
- 출력: `QueryPlanV1`
- 책임: 질문을 evidence requirement로 변환
- 금지: 답변, 검색 결과 선택, outcome 접근, HSWM 변경

### BF — Bond Proposer

- 입력: `BondScoringEnvelopeV1`
- 출력: `BondProposalV1`
- 책임: 공급된 opaque candidate와 observable component만으로 fast potential 제안
- 금지: gold, answer surface, query/edge ID shortcut, slow weight 변경, promotion 판정

### AF — Answer Synthesizer

- 입력: `AnswerContextV1`
- 출력: `AnswerEnvelopeV1`
- 책임: 이미 선택된 evidence만으로 답변하고 evidence ID를 결속
- 금지: 추가 검색, reranking, HSWM 변경, 자기 실험 판정

세 역할의 실제 system prompt는 기계 계약의 `llm_functions`에 동결했다. 각 역할은 JSON
typed port만 사용한다. 모델의 자유 텍스트 rationale를 다른 함수의 control instruction으로
실행하지 않는다.

외부 evaluator는 네 번째 LLM 역할이 아니다. 그것은 function network 밖에서 outcome과
promotion evidence를 소유하는 독립 측정자다.

## 3. 왜 먼저 Gate 0인가

기존 B2.1 scorepack은 top-20만 남긴다. weight가 기존 상위 후보를 억제하면 21위 아래 후보가
올라올 수 있으므로, 이 pack으로 learner를 학습하면 관측되지 않은 후보를 잘못 채점한다.

따라서 다음 세 pack을 먼저 만들어야 한다.

1. 2Wiki `b2_reproduction400` — 400 queries × 2,753 candidates;
2. 2Wiki `full_closed_corpus` — 500 × 3,452;
3. MuSiQue `full_closed_corpus` — 800 × 8,893.

각 pack은 모든 `query × candidate` component, identity, provenance, model snapshot, producer hash,
neutral replay를 보존한다. 세 pack을 `compile → verify → lock → accept`한 영수증만 learner를
연다.

### guarded GPU 실행 골격

실제 경로를 채운 뒤 Dell guarded CUDA path에서 실행한다. pack 자체는 Git에 넣지 않는다.

```bash
export HSWM_DATA_ROOT=/absolute/pinned/data
export HSWM_MODEL_PATH=/absolute/pinned/all-MiniLM-L6-v2
export HSWM_GATE0_ROOT=/absolute/write-once/hswm-b22-gate0
export HSWM_B21_ROOT=/absolute/pinned/b21

python3 prom_search_hswm/hswm_b22_gate0_harness.py compile \
  --data "$HSWM_DATA_ROOT/2wiki.json" \
  --dataset 2wiki --cohort b2_reproduction400 --salt legacy \
  --model-path "$HSWM_MODEL_PATH" --device cuda --batch-size 128 \
  --b21-scorepack "$HSWM_B21_ROOT/2wiki.scorepack.json.gz" \
  --frozen-b2-reference "$HSWM_GATE0_ROOT/frozen-b2-reference.json.gz" \
  --output "$HSWM_GATE0_ROOT/reproduction400.pack" \
  --receipt "$HSWM_GATE0_ROOT/reproduction400.compile.json"

python3 prom_search_hswm/hswm_b22_gate0_harness.py compile \
  --data "$HSWM_DATA_ROOT/2wiki.json" \
  --dataset 2wiki --cohort full_closed_corpus --salt legacy \
  --model-path "$HSWM_MODEL_PATH" --device cuda --batch-size 128 \
  --b21-scorepack "$HSWM_B21_ROOT/2wiki.scorepack.json.gz" \
  --output "$HSWM_GATE0_ROOT/2wiki-full.pack" \
  --receipt "$HSWM_GATE0_ROOT/2wiki-full.compile.json"

python3 prom_search_hswm/hswm_b22_gate0_harness.py compile \
  --data "$HSWM_DATA_ROOT/musique.json" \
  --b21-history-2wiki-data "$HSWM_DATA_ROOT/2wiki.json" \
  --dataset musique --cohort full_closed_corpus --salt legacy \
  --model-path "$HSWM_MODEL_PATH" --device cuda --batch-size 128 \
  --b21-scorepack "$HSWM_B21_ROOT/musique.scorepack.json.gz" \
  --output "$HSWM_GATE0_ROOT/musique-full.pack" \
  --receipt "$HSWM_GATE0_ROOT/musique-full.compile.json"

python3 prom_search_hswm/hswm_b22_gate0_harness.py lock \
  --reproduction-pack "$HSWM_GATE0_ROOT/reproduction400.pack" \
  --reproduction-receipt "$HSWM_GATE0_ROOT/reproduction400.compile.json" \
  --two-wiki-pack "$HSWM_GATE0_ROOT/2wiki-full.pack" \
  --two-wiki-receipt "$HSWM_GATE0_ROOT/2wiki-full.compile.json" \
  --musique-pack "$HSWM_GATE0_ROOT/musique-full.pack" \
  --musique-receipt "$HSWM_GATE0_ROOT/musique-full.compile.json" \
  --output "$HSWM_GATE0_ROOT/gate0.lock.json"

python3 prom_search_hswm/hswm_b22_gate0_harness.py accept \
  --lock "$HSWM_GATE0_ROOT/gate0.lock.json" \
  --output "$HSWM_GATE0_ROOT/gate0.acceptance.json"
```

경로와 기존 scorepack 이름은 실행 직전 실제 자산 inventory로 확인해야 한다. 이름을 추정해서
돌리면 안 된다.

## 4. F1 구현 순서

Gate 0과 독립적으로 다음 다섯 모듈을 구현할 수 있다.

| 모듈 | 책임 |
|---|---|
| `hswm_typed_ports.py` | `QueryEnvelopeV1`, `QueryPlanV1`, `BondProposalV1`, `AnswerEnvelopeV1` 검증 |
| `hswm_function_registry.py` | role/model/prompt/input/output hash를 가진 immutable function registry |
| `hswm_function_network.py` | QF→BF→readout→AF deterministic orchestration |
| `hswm_call_receipt.py` | 매 physical call의 prompt/response/model/token/cache/latency receipt |
| `prom_f1_function_network.py` | typed/flat/vector/removal/shuffle matched-budget 실험 하네스 |

구현의 첫 vertical slice는 실제 성능 실험이 아니라 다음 invariant를 통과하는 것이다.

1. 잘못된 input/output schema는 함수 호출 전에 reject;
2. 같은 registry, input, recorded response로 replay하면 port hash가 동일;
3. 각 arm은 item당 정확히 physical call 3회;
4. 제거된 role도 schema-preserving null call로 대체하여 비용을 그대로 청구;
5. prompt/model/port 변경은 새 registry digest를 생성;
6. LLM output은 candidate이며 evaluator/verdict/activation 권한이 없음.

## 5. F1 대조군

| arm | 바뀌는 것 | 고정되는 것 |
|---|---|---|
| typed HSWM network | typed role과 HSWM port topology | model, calls, tokens, candidates |
| flat single-LLM workflow | global flat context, generic three-call workflow | 같은 model/calls/tokens |
| vector memory workflow | vector retrieval state | 같은 model/calls/tokens/candidates |
| role removal | 한 역할을 typed null로 치환 | 세 physical calls와 budget |
| role shuffle | port schema는 유지하고 역할 instruction을 섞음 | model/calls/tokens/topology |

typed arm이 이겨도 removal과 shuffle에서 효과가 유지되면 **function topology** 증거가 아니다.
그 경우 “세 번 호출한 workflow”로 좁혀 기록한다.

## 6. P1v5 fast-to-slow 실험

P1v5는 Gate-0 acceptance 뒤에만 연다.

### 개발 단계

1. accepted feature view만 로드한다.
2. 하나의 작은 A/B-renaming-invariant fast scorer를 학습한다.
3. `lambda_q=0`을 calibration grid에 넣어 neutral fallback을 보장한다.
4. 2Wiki/MuSiQue development에서 feature, lambda, sparsity, abstention을 한 번 동결한다.
5. sealed 결과를 열기 전에 fresh regime, 통계, promotion rule, prediction을 LakatoTree에 등록한다.

허용 feature는 observable score component, provenance, incidence/seam 통계다. query ID, edge-ID
embedding, hop label, answer 문자열, test gold는 금지한다.

### 인과 대조군

- frozen MERGED neutral;
- fast-only;
- fast → validated slow promotion;
- 기존 global static exact-answer update;
- random credit;
- shuffled eligibility;
- no promotion;
- promoted rewrite removal;
- equal-budget flat reranker;
- equal-budget vector memory.

slow learning 주장은 다음 conjunction 전체가 필요하다.

```text
fast effect exists
AND slow promoted snapshot changes later frozen behavior
AND fresh LCB > 0
AND minimum regime delta > +0.02
AND cross/in-field retention >= -0.02
AND random/shuffle controls fail
AND removal erases the gain
AND replay and activation receipts agree
```

fast만 통과하면 `FAST_ONLY`다. 이는 query-conditioned attention의 성공이지 durable memory의
성공이 아니다.

## 7. P2에서 비로소 “거대한 공유 신경망”을 시험한다

F1과 P1v5가 각각 통과한 다음 두 축을 합친다.

1. Agent A는 accepted HSWM mutation path로만 write;
2. Agent B의 model, prompt, tools, readout, budget은 frozen;
3. B는 A transcript를 보지 못함;
4. exact-query cache hit 금지;
5. fresh component-disjoint query에서 B를 측정;
6. HSWM rewrite를 제거하면 이득이 사라져야 함;
7. flat/vector/transcript-only와 equal-budget 비교.

이때 통과하면 “A가 남긴 shared semantic weight가 다른 frozen LLM 함수의 이후 계산을 바꿨다”는
좁고 강한 주장을 할 수 있다. 그래도 아직 topology learning이나 scale 증거는 아니다.

## 8. PROM-9 실행 packet 사용법

2026-07-24 현재 위 vertical slice와 세 결정 실험의 fail-closed 판정기가 구현됐다. 실제 endpoint
실행, manifest 형식, P1v5/P2 causal packet 작성법은
[`PROM9_DECISIVE_EXPERIMENT_HARNESS_2026-07-24.md`](PROM9_DECISIVE_EXPERIMENT_HARNESS_2026-07-24.md)에
고정한다. 구현 완료는 효능 결과가 아니며, development 출력은 성공 gate를 모두 통과해도
`DEVELOPMENT_ONLY`만 낸다.

프로토콜 자체 검사:

```bash
python3 -m prom_search_hswm.prom9_protocol validate
```

ordered status가 현재 여는 유일한 F1 repair packet 준비:

```bash
python3 -m prom_search_hswm.prom9_protocol prepare \
  --status receipts/HSWM_ORDERED_GATE_STATUS_20260724.json \
  --stage F1_TYPED_FUNCTION_NETWORK \
  --run-id f1-dev-001 \
  --output /new/write-once/F1_PROM9_STAGE_PACKET.json
```

현재 Gate-0, P1v5, P2를 준비하려 하면 F1 actual-compute gate부터 닫히지 않았으므로
거부되어야 정상이다. PROM-9 stage 순서도 `F1 → Gate-0 → P1v5 → P2`로 고정돼 있다.

stage packet은 `preparation_allowed=true`만 낸다. 다음 값은 언제나 false다.

- `sealed_measurement_allowed`;
- `activation_allowed`;
- `scientific_prediction_registered`;
- `scientific_result_submitted`.

즉 코드 생성과 개발을 열 뿐, sealed run이나 성공 판정을 몰래 열지 않는다.

## 9. 판정과 중단

- Gate-0 full pack에서 oracle room이 사라지면 B2.2 학습 가설을 중단한다.
- fast scorer가 두 개발 dataset 모두에서 positive CI를 만들지 못하면 observable feature 가설을
  중단한다.
- role ablation이 효과를 지우지 못하면 F1 “function network” 주장을 workflow로 좁힌다.
- slow promotion이 retention을 해치거나 removal이 효과를 지우지 못하면 slow memory 주장을
  중단하고 fast attention만 남긴다.
- flat/vector arm이 matched budget에서 같거나 낫다면 HSWM-specific 이득 주장을 접는다.
- 세 diversified candidate가 연속으로 vector gate를 못 넘으면 threshold를 완화하지 않고
  `SATURATED`로 닫는다.

## 10. 최종 피드백

개념 자체는 어렵지 않다. 어려운 부분은 LLM을 함수로 호출하는 코드가 아니라 다음 세 경계를
실험으로 분리하는 것이다.

1. **activation** — 이번 query에서 어느 bond와 함수가 사용됐는가;
2. **learning** — 외부 결과 때문에 이후에도 남는 weight가 바뀌었는가;
3. **structure** — function/bond topology 자체가 바뀌었는가.

이 순서를 지키면 HSWM은 단순 agent graph보다 훨씬 강한 연구 대상이 된다. 반대로 세 가지를
한꺼번에 최적화하면 무엇이 효과를 냈는지 판정할 수 없어 “거대한 시멘틱 신경망”이라는 말만
남는다.
