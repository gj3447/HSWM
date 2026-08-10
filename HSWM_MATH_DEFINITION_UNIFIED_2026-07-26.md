# HSWM 수학적 통합 정의 + 정의 파편화 감사 (2026-07-26)

> **성격**: SECONDARY_AI 형식화 제안 — 사용자 정의 문서들(USER_PRIMARY)의 *통합 좌표계*. 새 정전을 만들지 않고, 흩어진 정의를 한 수식 체계에 걸고 파편을 명시한다.
> **범위**: 정의(무엇인가)만. 효능 판정(얼마나 좋은가)은 각 sealed receipt의 것을 바꾸지 않는다.
> **답부터**: **네, 정의는 파편화돼 있다.** 정의문 11종이 문서 11개+와 KG 노드에 걸쳐 있고(오늘 codex의 cellular 형식화 D11 포함), (a) 정체 3층, (b) W 공식 3종, (c) fold 수 2종, (d) supersession 기구 4종, (e) 시간척도 2종, (f) H 정의 2벌이 한 기호 체계로 통합된 적이 없다. §1에 전수 대조표, §2에 통합 정의(+§2.A 코드 인용), §3에 파편 레지스터와 처리 판정.

---

## 1. 파편화 감사 — 정의문 전수 대조

| # | 정의문 (정본 경로) | 핵심 정의 구문 | 무엇이 다른가 |
|---|---|---|---|
| D1 | `THEORY/재배맨/HSWM_STANDARD.md` v0.2 (2026-07-19, 자기강등 DESIGN DRAFT) | "H와 W 위에서 f_i 자체가 LLM으로 실행되는 거대 시맨틱 신경망(지향 정체성) — 검색·계획을 동일 readout으로, cosine⊕judgment 합성 binding-first 하이퍼그래프" | W 코드 공식 = `α + λ_b·log b` (**j 부재**), 설계 공식 = `+λ_j·j`, j=λ·ReLU(·)≥0. 3-fold readout으로 정정됨 |
| D2 | KG `commander-hswm-omc-2026-07-19` (CANONICAL) | "HSWM 표준(cosine⊕judgment 場, **4-fold** readout, additive-j floor)" | D1이 이미 4-fold→3-fold로 정정했는데 KG 노드 미갱신 + "표준" 표기 잔류 (doc_status_drift 플래그 있음) |
| D3 | `GIT/HSWM/CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md` (CANONICAL_USER_DIRECTION) | HSWM = LLM-executed functions + H + W + recurrent plastic state; W = fast θ + slow ℓ,b; ΔW=(r−r̂)z (three-factor, **부호 있음**) | W의 **fast/slow 이중척도** 도입 — D1의 단일 W와 기호 충돌. ΔW 부호 있음 vs D1의 j≥0 규율 |
| D4 | `GIT/HSWM/HSWM_CANONICAL_RESEARCH_DIRECTION_20260724.md` | HSWM_t=(H_t,W_t,A_t,F_t), a^{t+1}_i=f_i^t(x_i^t,a^t_{N(i)};W_t), f=LLM(ρ,τ,·) | 상태 4-tuple 명시. hard core vs protective belt 분리 — **통합 시 기본 골격으로 채택** |
| D5 | KG `user-canon-hswm-is-the-larger-ai-containing-consensus-2026-07-23` (CANONICAL) | "HSWM 자체가 더 큰 범위의 AI이며 합의를 포함" — 좁은 메모리/검색 기질 프레이밍 supersede | **스코프 격상**: substrate < neural net < AI. 수학적 내용은 없음 (방향 층) |
| D6 | `HSWM/SPEC_SHARED_HYPERGRAPH_NN_SEMANTIC_WEIGHT_2026-07-22.md` (SECONDARY_AI) | Semantic = emb(좌표) + hypergraph(결합) + W(강도) + a(활성) **삼중+활성 표현**; W = Canonical Semantic Weight | semantic의 구성요소 정의. D1~D4에 없던 "semantic의 분해" |
| D7 | `HSWM/SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md` + `AMENDMENT_..._V2` | HSWM = typed ports + scalar weight field의 **open hypergraph**; H=NF(M,P,C,X,ℓ,Π); compose_β(H_1..H_n)=NF(∪H_i∪Connectors(β)) | **합성 대수**: 계층 객체가 아니라 동일 타입으로 닫히는 open 객체. D1~D4의 단일 場과 스케일이 다름 |
| D8 | `HSWM/HARNESS_7COMMANDER_HSWM_SUBSTRATE_2026-07-21.md` | 흡수 단위 = "검색·계획·supersession을 하나의 가중장 readout으로 두는 substrate 인터페이스"; Field{field_id, current_locator, weight, supersede_state, sha256_baseline} | Field에 **안정 정체성(field_id)/위치자(locator)/낡음(supersede_state) 분리** — D1~D7에 없는 식별자 계층 |
| D9 | `GIT/HSWM/README.md` + 코드 (`weight_field.py`, `readouts.py`, `supersede_ledger.py`, `hswm_field_algebra.py`, `hswm_open_kernel.py`) | 코드가 실제로 강제하는 것: W(e‖c)=cosine⊕base-salience / retrieve·selection·dispatch·supersede / G-Set CRDT 원장 / field 대수 L1–L4 / compose kernel v2r3 | **실재 정의의 하한**. j·traversal(μ=0)·bind 미구현 |
| D10 | `HSWM/DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md` | "한 대수 두 스케일": fact-level ADD/SPLIT/MERGE/SUPERSEDE ≡ field-level 망 연산 | D7의 compose와 B0 field 대수를 같은 대수로 주장 — **미증명 가설**(C1) |
| D11 | `GIT/HSWM/DEFINITION_HSWM_CELLULAR_METANEURAL_SYSTEM_2026-07-26.md` (2026-07-26, codex — **본 문서와 같은 날 병렬 작성**) | Ω_t=(F,H,𝒲,α,A,S,Z,M,G,P) 10-tuple — operator-valued 시냅스(관계·수송·게이트·효능·불확실), stateful LLM-cell, eligibility Z, fast/slow 시냅스. Lean 9정리 witness + Longinus 32바인딩 | **가장 풍부한 target-층 형식화**. 본 통합안과 대조: ①fast/slow W 층별화가 **독립 수렴**(consilience 신호) ②𝒲는 operator-valued(더 풍부) vs 본 문서의 score는 그 **스칼라 그림자**(측정 레일) ③Π≈P∪G, A≈A — 본 문서는 D11의 구현-층 투사로 읽힘 (§2.8) |

### 파편 축 (10)

- **F1 정체 3층**: 측정된 메모리 substrate(D9 실측) / LLM-함수 신경망(D3·D4 지향 정체) / 합의 포함 더 큰 AI(D5 스코프 격상). 모순이 아니라 층인데, 문서들이 층을 섞어 인용.
- **F2 W 공식 3종**: ①코드 `W=α+λ_b·log b` (j 부재) ②설계 `+λ_j·ReLU(j)`, j≥0 (D1-canonical) ③CANON fast θ + slow ℓ,b 이중척도. 같은 W 기호에 다른 객체.
- **F3 fold 수**: "4-fold readout"(D2 KG) vs "3-fold readout + write 2종"(D1 정정). KG 노드가 stale.
- **F4 supersession 기구 3+1종**: b 감쇠(dose-graded, 코드) / CRDT G-Set canonical fold(내구 층) / invalid_at 비파괴 마킹(F5v2 방향) + **코드 안에도 3개**(legacy in-place 비멱등 — T2 음의 오라클이 제곱 부패를 *증명* / G-Set CRDT / shadow-gate 토폴로지 원장). 같은 철학(삭제 0)이나 형식이 4개.
- **F5 ΔW 부호**: D3의 ΔW=(r−r̂)z는 부호 있음 vs D1의 "모든 음성 신호는 오직 b로" 규율. 층을 안 나누면 직접 충돌.
- **F6 traversal**: 사용자 비전("웨이트로 돌아다님") vs 실측 μ=0 OFF 2계열. 정의에선 순회가 살아있고 배치 정의에선 죽어 있음 — 현재는 "OFF-until-certified"로 봉인됨(그대로 유지).
- **F7 스케일 대수**: field 대수(B0) ≡ compose 대수(D7) "한 대수 두 스케일"(D10) — 미증명.
- **F8 명칭/지위**: "표준"(D2) vs "DESIGN DRAFT (NOT a standard)"(D1 자기강등) vs "target identity, not efficacy"(D3·D4).
- **F9 H 정의 2벌 (코드)**: `hypergraph.py` 프로토타입(int 인덱스 노드, base_salience 벡터) vs `hswm_hypergraph.py` field 대수(문자열 vid `kind:name`, payload=원문 문자열, gold cluster). 호환 없이 공존.
- **F10 고립 정점 운영 (코드)**: field 대수 `_rebuild`는 고립 정점을 **조용히 삭제**(`hswm_field_algebra.py:106-114`, 주석으로만 문서화) vs open kernel v2는 고립 정점 소실을 **falsifier #7로 금지**(AMENDMENT §3). "삭제 0" ethos의 두 예외/비예외가 층마다 다름.

---

## 2. 통합 수학 정의 (제안)

> 기호는 D4(최신 hard-core 정본)를 골격으로, D3의 시간척도와 D1의 D1-규율을 W 층으로 삽입하고, D7의 합성을 스케일 축으로 붙인다. **어느 단일 문서도 아직 이 형태를 갖지 않는다** — 이것이 통합 제안.

### 2.0 한 줄

**HSWM := 의미 상태 노드와 LLM-실행 함수 노드를 n-ary 결합으로 묶는 open 가중 하이퍼그래프 (H, W, A, F, Π) 로서, W는 지속층(W_slow)과 휘발층(W_fast)으로 층별화된 시맨틱 가중치 맵이고, 읽기는 단일 가중장의 순수 readout, 쓰기는 비파괴 대수 연산, 학습(미폐쇄)은 검증된 verdict의 W_slow 갱신이다.**

### 2.1 객체

```
HSWM_t := (H_t, W_t, A_t, F_t, Π_t)

H_t := (V_t, E_t, I_t, Π^H_t)        가변 하이퍼그래프
  V_t   : 의미 상태 노드. 임베딩 X : V → R^d (d=768, bge-m3, frozen — 리프트 본체)
  E_t   : reified n-ary 하이퍼엣지 (사실·관계·lesson·bond·함수 노드 참조)
  I_t   : E → 2^V incidence (n-ary 결합; "무엇이 공동 주장되는가")
  Π^H_t : provenance (evidence id, source digest, event id — 삭제 0, append-only)

W_t := (W_slow, W_fast)               시맨틱 가중치 맵 — 층별화 (F2·F5 파편의 통합)
  W_slow : E → (ℓ, b)                 지속층 — macro-synapse
    ℓ(e) ∈ R_{≤0}  : base log-salience (학습으로 갱신되는 유일한 지속 가중)
    b(e) ∈ (0,1]   : 유효도 — supersession dose 누적, b=1 현행 → 0에 수렴
  W_fast : E × C → R_{≥0}             휘발층 — query 조걶 잠재
    j(e,c) ≥ 0     : additive 잔여 (D1 규율: boost-only; 음성 신호는 오직 b로)

A_t : V → R                           활성 — 휘발, run마다 초기화 (지속 상태 아님)

F_t : typed port 함수 노드 집합
  f_i := LLM(ρ_i, τ_i, ·)             ρ=역할 타입, τ=프롬프트 계약. micro-weight(LLM 파라미터)는
                                       함수 구현 난부, HSWM의 W가 아님 (macro/micro 분리 정전)

Π_t := Π^H ∪ ledger ∪ receipts       결정론 제어평면 (CAS·CRDT·replay·gates)
                                       — 신경이 아님. safety/control plane 정전
```

### 2.2 읽기 대수 (3-fold — F3 파편은 이 형태로 봉인)

```
score(e | c) := α(e,c) + λ_b · log b(e) + λ_j · ReLU( j(e,c) )
  α(e,c) := cos( X(pooled(e)), q_c )   (frozen — M-학습은 v0.1 반증으로 폐기)
  λ_b ≥ 0, λ_j ≥ 0 (val에서 선택, 0 포함)

retrieve(c) := top-k score(·|c)         검색 readout
plan(c)     := softmax score(·|c)       계획 분포
dispatch(c) := argmax plan(c)           실행
```

- 세 연산은 **같은 score의 순수 readout** — 상태를 바꾸지 않는다 (I3′).
- traverse(seed, K)는 이 대수 **밖**의 선택 연산: **OFF-until-certified** (μ=0, 실측 2계열 봉인). 정의에서 삭제하지 않고 봉인 조항으로 유지.

### 2.3 쓰기 대수 (비파괴 — F4 파편의 통합: 하나의 연산, 세 투사)

```
SUPERSEDE(e, dose d ∈ [0,1]) :  b(e) ← b(e) · (1 − d)         [場 투사: dose-graded]
  기록: ledger ← ledger ∪ {(event_id, e, d)}                   [내구 투사: G-Set CRDT]
  표현: invalid_at(e, t) := t_commit                           [시간 투사: bitemporal 표기]
    b(e) := ∏_{(id,e,d)∈ledger} (1−d)  — canonical event-id 순 fold (곱은 가환·비결합
    → 순서 고정으로 비트 수렴; 동일 id 재적용 = no-op 멱등)
```

- V·E 단조 비감소, 삭제 연산 없음 (I2). supersede는 b만 바꾸고 노드/엣지는 남는다.
- 나머지 field 연산: `ADD(e)`, `SPLIT(e→e₁,e₂)`, `MERGE(e₁,e₂→e)` — provenance 보존 조건.
- `BIND(e, members)`: incidence 확장 — **미구현**(pooled 캐시 무효화 필요), TARGET.

### 2.4 전진 동역학 (지향 정체 — CANON)

```
a_i^{t+1} := f_i^t( x_i^t, a^t_{𝒩(i)} ; W_t )     함수 노드의 국소 전이
(H_{t+1}, W_{t+1}) := Plasticity(H_t, W_t, a^t, M_t)
  Δℓ(e) := η · (r − r̂) · z(e)                     three-factor (TARGET — 루프 미폐쇄)
    z(e) : eligibility trace (episode-ID 태그, wall-clock decay 금지)
    r    : 외부 verdict (neuromodulator M)          r̂ : 예측
    η    : 학습률·homeostasis 게이트
```

- **F5 파편 봉인**: Δℓ는 부호가 있다(음성 verdict가 ℓ를 깎음). D1의 "음성은 b로만" 규율은 **W_fast/readout 층**의 규율 — 층이 다륯므로 충돌이 아니다. 둘을 한 W에 쓰면 충돌; 이 문서의 W_slow/W_fast 분리가 그 파편의 핵소.
- topology 가소성: ADD/SPLIT/MERGE/SUPERSEDE 수용은 verdict-gated 확률 × prior (TARGET, shadow-gate만 존재).

### 2.5 합성 (open self-similar — D7)

```
compose_β(H_1,…,H_n) := NF( ⋃_i H_i ∪ Connectors(β) ) ∈ HSWM
  mount/port/connector 모두 동일 타입 — 고정 층 없음, 연결첻도 HSWM
materialize : compose 결과 → legacy quotient 場 (명시적, 비공짜)
separate / specialize : 역연산 계열 — digest 일치 검증 fail-closed
```

- D10의 "한 대수 두 스케일"(fact 대수 ≡ 망 대수)은 이 정의에서 **미증명 가설 C1**로 표기한다.

### 2.6 불변식 (ENFORCED vs TARGET — D1 정본 그대로)

| # | 내용 | 지위 |
|---|---|---|
| I1 | score는 실재 E 위에만 정의 — off-support는 −∞ (0 아님) | ENFORCED(명세 정정됨), mask 테스트 보강 필요 |
| I2 | 비파괴 — SUPERSEDE는 b만, V·E 단조 비감소 | ENFORCED |
| I3′ | retrieve/plan/dispatch = 동일 score의 순수 readout | ENFORCED |
| I4 | cosine 바닥: j≥0이면 score ≥ α pointwise + val-선택 mean floor. **per-query floor는 아님(min gap −0.22 실측)** | ENFORCED under D1 (과장 금지 문구 포함) |
| I5 | binding-first: j는 bound edge에만 | UNENFORCEABLE (j 미구현) |
| I6 | verdict-gated 고-W | TARGET |
| I7 | provenance(WeightAdjusted PROV) | TARGET |

### 2.7 정체 층 (F1 파편 봉인 — 어느 층의 문인가)

| 층 | 정체 | 증거 상태 | 이 층의 문서 |
|---|---|---|---|
| **L0 substrate** | 가중장 위 검색 readout | **CONFIRMED** (5-substrate 사다리 1위, cosine +0.073 p<1e-4) | D1 §0.4–0.5, D9 |
| **L1 neural function net** | LLM-실행 함수망 + plasticity | **TARGET** — Gate A(F1) 진행 중, plasticity loop 미폐쇄 | D3, D4 |
| **L2 composition/federation** | open self-similar compose | **공학 closure** (v2r3 78 tests) — 성능 미측정 | D7, D10 |
| **L3 더 큰 AI (⊇합의)** | 스코프 격상 방향 | **OPEN** — 수학적 내용 아직 없음 | D5 |

규율: 상위 층의 문으로 하위 층의 증거를 인용하지 않는다 (D5가 명시한 대로 측정은 유효하되 대상 범주가 다름). 역도 금지 — L0 CONFIRMED를 L1 증거로 쓰는 것이 과거 category error의 반복.

### 2.8 병렬 형식화와의 관계 (D11 cellular metaneural, 2026-07-26 codex)

본 문서 작성과 같은 날 codex 세션이 target-층 형식화(D11, Ω 10-tuple + Lean 9정리)를 등록했다. 파편이 아니라 **층이 다른 두 좌표계**:

| | 본 문서 (통합 정의) | D11 (cellular metaneural) |
|---|---|---|
| 초점 | **구현·측정 레일의 통합 좌표** — 실재 코드/정의문 10종의 파편 봉인 | **target 정체의 풍부한 형식화** — operator-valued 시냅스, stateful cell, Lean witness |
| W | 스칼라 score (α+λ_b·log b+λ_j·ReLU(j)) + W_slow/W_fast | operator-valued 𝒲 (관계·수송·게이트·효능·불확실) + fast/slow |
| 관계 | D11의 **스칼라 그림자/구현-층 투사** (Π≈P∪G, A≈A, z≈Z) | 본 문서의 **target-층 확장** |

- **consilience 신호**: fast/slow W 층별화가 두 세션에서 독립 수렴 — F2/F5 파편의 층별화 핵소가 한 세션의 임의 선택이 아님.
- 미해소 매핑 질문: D11의 operator-valued 𝒲를 본 문서의 스칼라 score로 환원하는 사영이 정보를 얼마나 버리는가 — `Q-hswm-operator-synapse-scalar-shadow` 후보.

---

## 2.A 코드 층 인용 (정의의 하한 — `GIT/HSWM` 실측)

> 문서가 아니라 **테스트가 강제하는** 수학. 통합 정의 §2.1~2.6과의 대응을 괄호로 표시.

### 2.A.1 객체 (§2.1 대응)

- **프로토타입 場** `hypergraph.py:23-52`: `Hypergraph{node_emb (N,d) float64, members: list[int array], edge_freq, edge_recency, base_salience (M,)}` — incidence = bool (M,N) (`:88-93`), 풀링 = permutation-invariant mean(DeepSets, `:95-114`). (H, X)
- **field 대수 場** `hswm_hypergraph.py:44-103`: `Vertex{vid="kind:name", kind ∈ {entity,topic}}` + `Hyperedge{eid, value=원문 payload, members 정렬, clusters}` + 양방향 incidence 불변식 `check_incidence()`. (H — F9의 두 번째 벌)
- **Field 값객체** `hswm_field_algebra.py:51-68`: `Field{hg, provenance: eid→정렬 source digest (엣지마다 ≥1, 누락 ValueError), ledger: frozenset[event-id G-Set], seam}` — `field_id = sha256(canonical JSON)`, **임베딩은 해시에서 명시적 제외**(파생물, `:18-19,73-90`). (Π^H)

### 2.A.2 가중치 (§2.1 W 대응)

- 프로토타입: `W(e|c) = α(e,c) + λ·log(clip(b,1e-6,·))`, 기본 λ=0.15, α=`pooledᵀ·M·q` (`weight_field.py:34-54`).
- additive-j (D1): `W = cos + λ_j·ReLU(peᵀMq)`, λ_j ∈ {0, 0.5, 1, 2, 4, 8} val 선택 — **음수 신호는 b로만** (`learned_v3_additive.py:14-15,33,116-117`).
- **bond readout = W_slow/W_fast 2평면이 이미 코드에 존재**: `rank_bonds(base, ℓ, a) = base + λ_s·ℓ + λ_q·a` (`hswm_bond_readout.py:126-183`) — ℓ,a 모두 **R_{≤0} 상대 잠재 공간**이 계약(`hswm_open_composition.py:63-73`, `hswm_weight_snapshot.py:65-71`, `-0.0`→`0.0` 정규화). 두 평면 모두 후보집합 exact coverage 강제(`:107-123`). — 본 문서 §2.1의 W_slow/W_fast 층별화는 창안이 아니라 **bond 층 기존 코드의 일반화**.
- weight snapshot: CAS delta 적용(before 불일치 거부, `hswm_weight_snapshot.py:284-299`) + SQLite single-writer WAL (`hswm_weight_store.py:100-116`) — §7.1 동시성 파편의 코드 측 대응물.

### 2.A.3 대수 법칙 (테스트 강제)

| 법칙 | 내용 | 테스트 |
|---|---|---|
| L1 가환 / L2 결합 / L3 멱등 | `field_id(merge)` 기준 | `test_hswm_field_algebra.py:46-58,75-81` |
| L4 왕복 | `field_id(reassemble(split(f))) == field_id(f)` 비트동일 | `:61-72` |
| R4 | `compose = merge_all` 얇은 별칭 | `:112-115` |
| CRDT semilattice | ledger 멱등·가환·결합 (digest 동등) | `test_supersede_confluence.py:93-105` |
| T1 순열 불변 | 임의 셔플 배달에 base_salience `np.array_equal` + top-k rank 불변 | `:65-90` |
| T2 중복 no-op | + **음의 오라클: legacy 비멱등 supersede는 정확히 제곱 부패** | `:110-148` |
| T3 admission | 교환 op 통과, 상태 읽는 op `AdmissionError` | `:159-175` |
| T4 epoch fence | consistent cut 접두, fence 초과 시 인증값 변경 | `:180-204` |
| additive floor | `W ≥ cos` 점별, λ=0이면 정확히 cosine, λ<0 fail-closed | `test_additive_floor.py:15-58` |
| bond 중립성 | 중립 가중은 순서·점수 보존, slow weight는 점수를 올리지 못함 | `test_hswm_bond_readout.py:21-44` |

### 2.A.4 supersession 세 경로 (F4 코드 증거)

1. **legacy in-place** `readouts.py:74-83`: `b[e] *= decay` — 비멱등, T2가 부패 증명. → **CRDT로 supersede 권장** (§3 등록).
2. **G-Set CRDT** `supersede_ledger.py:95-173`: `b(e)=b0(e)·Πδ_i`, canonical event-id 순 fold로 비트 수렴(`:140-153`), `at_epoch(n)` = Chandy-Lamport cut, `apply_ledger`는 `base_salience`를 b0에서 **재계산해 덮어씀**(`:176-187`).
3. **shadow-gate 토폴로지 원장** `hswm_shadow_gate.py:126-262`: `invalid_at_round: None ⇒ active`, SUPERSEDE는 교체 레코드(삭제 아님), SPLIT/MERGE는 멤버 합집합 강제, 게이트 = canary≥98% ∧ fresh≥−0.01 ∧ target≥+0.03.

### 2.A.5 봉인/미구현 (§2.2·§2.6 대응)

- **traversal**: `mu==0 or gamma==0`이면 pointwise readout과 **비트동일 early return** (`traversal.py:159-160`) — OFF-until-certified가 코드 수준에서 정확히 구현됨. 상수 prereg lock: GAMMA=0.5, K_DEFAULT=2, MU_GRID=(0,.1,.2,.4,.8), trip-wire 시 abstain (`:34-48,180-194`).
- **hash 임베딩 = STAND-IN**: 256d md5 bucket (`doc_builder.py:64-81`) — 실측 bge-m3 768d와 다른 stand-in임이 코드에 명시.
- **Lean 층 존재**: `formal/HSWMCellular.lean:106-121` `route_disabled` (gate=false 시냅스 fail-closed).
- **S2(judgment) 스트림은 CRDT 모델링 안 함** — order-essential이라 admission이 배제 (`supersede_ledger.py:41-45`) → 판정 쓰기는 직렬화 필요 (§7.1 과 연결).
- compose의 lazy overlay 미승격 (`hswm_field_algebra.py:177-178`), α-nDCG 미구현, seam 자동 후보 생성 유예.

---

## 3. 파편 레지스터 — 처리 판정

| 파편 | 내용 | 판정 |
|---|---|---|
| F2 W 공식 3종 | §2.1 W_slow/W_fast 층별화로 통합 — **코드 선례 있음** (bond readout 2평면, §2.A.2) | **본 문서가 통합안** — 사용자 verdict 시 각 문서 기호 정정 |
| F3 4-fold KG stale | D2 KG 노드 role 속성 갱신 필요 ("3-fold readout + additive-j floor, DESIGN DRAFT") | **KG amend 제안** (아래 §4) |
| F5 ΔW 부호 | slow 층 부호 있음 / fast 층 boost-only — 층 분리로 해소 | 본 문서 §2.4에 봉인 |
| F4 supersession 4형 | 하나의 SUPERSEDE, 3 투사(場·내구·시간) — 코드 legacy in-place 경로는 T2가 부패를 증명했으므로 **CRDT 경로로 supersede** | 본 문서 §2.3에 통합 + legacy 폐기 제안 (§4-4) |
| F6 traversal | OFF-until-certified 유지 — 코드가 μ=0 비트동일 early return으로 정확히 구현 | 변경 없음 |
| F7 두 스케일 대수 | 미증명 가설 C1로 표기 | open question 등록 제안 |
| F8 "표준" 표기 | D2 KG role 속성 정정 | KG amend 제안 (§4) |
| F9 H 정의 2벌 | 프로토타입(측정 하네스 전용) vs field 대수(대수·합성 전용) — **용도 분리 명시로 봉인**, 하나로 합치는 리팩터는 측정 재현성 비용 때문에 비추 | 본 문서 §1에 등록, 현상 유지 |
| F10 고립 정점 | field 대수 GC(주석 문서화) vs open kernel v2 보존 법칙 — **층별 명시**: field 대수 남부의 GC는 "고립 정점은 어떤 사실도 운지 않는다"는 GC 규칙, 합성 층의 보존은 "타 場 재참조 가능성" 때문. 단일 규칙 아님을 문서화 | 본 문서에 등록, open question 후보 |
| — j 미구현 | I5/코드 부재 — 정의에는 넣되 TARGET 표기 | §2.1에 명시됨 |

### §4 KG/코드 amend 제안 (사용자 승인 대기 — 아직 실행 안 함)

1. `commander-hswm-omc-2026-07-19`.role: "…표준(cosine⊕judgment 場, 4-fold readout, additive-j floor)" → "…설계 초안(DESIGN DRAFT, 3-fold readout + additive-j floor; 정본=HSWM_STANDARD.md v0.2 + 본 통합 정의)".
2. 새 open question: `Q-hswm-field-compose-algebra-isomorphism` (F7, "한 대수 두 스케일"의 증명/반증) + `Q-hswm-isolated-vertex-law` (F10, 고립 정점의 통일 규칙).
3. 본 문서를 `SemanticAnchor` 계열 노드로 등록 (정의 통합 좌표, SECONDARY_AI 표기).
4. 코드: `readouts.py:74-83` legacy in-place supersede 경로에 DEPRECATED 표기 (CRDT ledger가 정본) — 단 실험 재현성 레일이라 삭제는 금지, 표지만.

---

## 5. provenance

- 입력 정본: §1 표의 D1~D10 (각 파일 경로 그대로).
- 코드 층 대조: explore 에이전트 전수 추출 (2026-07-26) — §2.A에 파일:라인 인용으로 반영 완료. F9(H 정의 2벌)·F10(고립 정점)·legacy supersede 부패(T2 증명)는 이 추출에서 발견.
- 작성: Kimi Code CLI, 2026-07-26. 사용자 발화 "일단 수학적으로 정의필봐 hswm을 그 정의 자체가 좀 파편화되있지않냐"에 대한 응답.
