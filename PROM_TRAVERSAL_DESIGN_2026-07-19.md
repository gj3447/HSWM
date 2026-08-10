<!-- PROVENANCE
Workflow: hswm-traversal-design-prom (wf_e9e1d75f-d10), ultracode, 13 agents (8 research axes + design synthesis + 3-critic tribunal + final revision), 1.19M subagent tokens, ~23min.
Critic verdicts: SOUND_W_ADJ ×3 → 30 지적 전건 처리(§11).
8축 독립 수렴: cosine-seeded · b-감쇠(supersession-conductance) · restart(skip항, Dong rank-collapse 방어) · hop cap K≤2-3 · star-expansion PPR · certified μ floor(2×SE paired) + abstain trip-wires.
사용자 프레임 확인: "현대 AI가 이미 푼 해법의 이식" — restart=skip연결 / damping=LayerNorm·온도 / hop cap=고정깊이 / incidence mask=attention mask / cosine seed 보존=residual stream / 사전계산·seed 분리=KV cache(APPNP split). 유일 비기성 = 순회×supersession(novelty 코너).
관계: PROM_KQV_ATTENTION_BACKBONE(이론 등뼈) + PROM_PRIOR_ART_TRIBUNAL(novelty 경계) + expB v2(gj3447/HSWM@7678b4a, harness 확장 대상)의 종합 후속.
-->
# HSWM 場 순회(Field Traversal) 설계 SPEC v2 — 최종판 (3-critic 재판 반영)
## — 인증된 감쇠-재시작 초그래프 PPR (Certified Damped-Restart Hypergraph PPR)

- **대상 repo**: `/Users/lagyeongjun/CD/SYMPOSIUM/GIT/HSWM` (numpy-only — `pyproject.toml` deps = `numpy>=1.26` 단독, scipy 금지. dataclass, prereg 상수, certified selection, teeth test 관습 준수)
- **날짜**: 2026-07-19. v1(8축 리서치 합성) → 3-critic 적대재판(전원 SOUND_W_ADJ, **fatal 0건**) 전 지적 흡수판.
- **v2 핵심 변경**: ① T4.5 하이퍼엣지 월드 빌더 신설(BLOCKING 해소) ② z-정규화 support 제한 + raw-양수 마스크(BLOCKING 해소) ③ COO/bincount 커널(scipy 배제) ④ μ 인증 멀티플리시티 보정(SELECT_Z_ADJ=2.5) ⑤ depth 게이트 = bootstrap LCB ⑥ H-T3 6-arm 확장(bi-temporal Zep + Kumiho separated + 오-supersession 부수피해) ⑦ K=3 = canon-amendment 조건부 ⑧ §7 latency 수치 UNVERIFIED 강등 ⑨ §9 conjunctive 주장 → H-T5 prereg 가설 강등 ⑩ §4 주장문에 mechanism-genericity·measured-gain-only caveat 내장.

---

## 1. 한 줄 설계 결정

> **W(e|c)의 top-m softmax를 seed로, b(e)^κ를 전도도(conductance)로 하는 star-expansion 이분(bipartite) 감쇠-재시작 walk를 K=2 스텝 고정 실행하고, support-제한 z-정규화 + raw-양수 마스크를 통과한 ReLU 잔차를 μ·(멀티플리시티 보정 인증, μ=0 admissible)로 pointwise W에 더한다. μ=0 또는 γ=0이면 오늘의 pointwise readout과 비트 단위로 동일하다(early-return으로 구조적 보장).**

| 축 | 결정 | 기각한 대안 (이유 1줄) |
|---|---|---|
| **Operator** | Star/bipartite 확장 위 truncated 재시작 walk. `hypergraph.members`가 곧 incidence — **COO 인덱스 배열 + `np.bincount` segment-sum으로 구현** (scipy CSR 금지, `incidence()` dense materialize 금지) | Clique 확장(엣지 정체성·supersession 캐리어·receipt 파괴, O(Σr²) 폭발) / 비선형 초그래프 diffusion(receipt 불가) / DEQ 고정점 반복(수렴 목표 자체가 collapse) |
| **Seeding** | pointwise `W(e|c)`의 softmax_τ top-m (= `plan()` 분포의 절단). **HippoRAG-2 계보 명시** (dense-score-weighted PPR reset ≈ recognition-memory seeding, arXiv:2502.14802). 순수 구조 seed 절대 금지 | 순수구조 PPR seed — 실측 최약 arm (sup_recall@3 0.373 vs hswm 0.706, `substrate_bench_results.json`) |
| **Damping** | walk 질량 γ=0.5 고정(하드캡 ≤0.5 = 증폭 ≤2×), 재시작 = seed 재주입(skip 항), **K=2 고정. K=3은 canon-amendment 노드 기록 + hop-3 계층 인증 후에만** (KQV canon hop≤2 준수), hop별 top-m 절단 | 저재시작(restart 0.15) — repo 내 문서화된 anti-pattern / 적응적 halting — 선형 수축에선 고정 k의 변장 (단 §2.4의 renorm 비선형성 caveat 참조) |
| **Supersession** | b(e)^κ를 전이 **전도도**에 곱함 (κ=1 기본, κ∈{0,1} prereg arm). supersede() 코드 변경 0. **단 메커니즘 자체는 일반 edge-weighted PPR — 주장은 결합(conjunction)에만** (§4) | 하드 필터 — 비교 arm으로 유지하되 **bi-temporal Zep 충실 구현** (strawman 금지, §4·§8) |
| **Floor** | `W_trav = W + μ·R`, `R = 1[Δ>0]·ReLU(z_S(Δ))` (S = a_K/a_0 비영 union support), μ ∈ MU_GRID(support-제한 z 하 T1 재보정 후 lock), **SELECT_Z_ADJ=2.5 멀티플리시티 보정 paired 인증**, μ=0 admissible. 2단 floor: F1 대수적 + F2 인증 mean-nDCG | RRF 융합 — admissible zero 없음, one-field 정체성 파괴; falsifier 비교 arm으로 강등 |

---

## 2. 정확한 수식

### 2.1 기호
- `H ∈ {0,1}^{M×N}`: incidence — **표기 전용(notation-only)**. `hypergraph.incidence()`는 dense (M,N) bool을 materialize하므로(100k×100k = 10GB) **스케일에서 절대 호출 금지**. 실제 구현은 `members`에서 직접 COO 인덱스 배열 구축:
```python
edge_idx = np.repeat(np.arange(M), arity)      # nnz = Σ arity
node_idx = np.concatenate(hg.members)          # nnz
deg_node = np.maximum(np.bincount(node_idx, minlength=N), 1)   # 0-degree 노드 clip (0/0 NaN 방지)
```
- `r_e` = arity(e), `deg(v)` = 노드 v의 하이퍼엣지 차수 (실 KG 로드에서 엣지에 안 묶인 노드가 존재 가능 → clip ≥1 필수).
- `W(e|c) = α(e,c) + λ_b·log b(e)`: 기존 pointwise 場 (`weight_field.combine`). **순회는 이 場의 4번째 readout이다** — 새 場을 만들지 않는다.
- 활성 벡터 `a ∈ R^M`은 **엣지 공간**에 산다 (W와 같은 인덱스 공간, 가산 결합이 자연스러움).

### 2.2 Prereg 상수 (실행 전 고정, 재협상 금지 — expB 관습)
```python
GAMMA   = 0.5          # walk 질량. 하드캡 ≤0.5 → 최악 증폭 2γ/(1−γ) ≤ 2×
K_DEFAULT = 2          # hop 캡. K=3은 (a) KG canon-amendment 노드 기록 + (b) H-T1 hop-3 계층 인증
                       #   양쪽 충족 후에만 활성 (KQV backbone canon 'skip+hop≤2' 준수, §6)
TAU_SEED  = 1.0        # seed softmax 온도 (BP 수축영역 τ≥1, 미조정)
KAPPA_ARMS = (0, 1)    # b 전도도 지수. κ=1=novelty arm, κ=0=ablation. 기본 1
SEED_M  = 64           # seed 절단 (softmax 질량 상위 m 엣지)
PRUNE_M = 1024         # hop별 frontier 유지 수 (compute guard — 의미론 아님)
MU_GRID = (0.0, 0.1, 0.2, 0.4, 0.8)   # LAMBDA_GRID 거울; 0 admissible.
                       # ⚠ support-제한 z-norm 하에서 T1에서 재보정 후 prereg lock (v1 값은 잠정)
SELECT_Z     = 2.0     # per-arm 기본 (expB_longdoc._select_lambda 거울)
SELECT_Z_ADJ = 2.5     # μ 인증 실제 게이트: max-t/Bonferroni — 비영 4 arm 위 max-mean 선택의
                       # selection 멀티플리시티 보정 (one-sided α≈0.0057). H-T2 = empirical control 겸용
SEEDS   = (0, 1, 2, 3, 4)
# 질의시 trip-wire (고정, validation 조정 금지 — 조정하면 selection 채널 재개방)
ENTROPY_BLOWUP = log(4)      # H(a_K) − H(a_0) 초과 시 abstain
NEFF_MIN = 1.5               # 1-hop parent-contribution 근사 n_eff (§3 재정의) 미달 시 abstain
KEPT_MASS_ABSTAIN = 0.95     # 실월드: hop별 잔존질량 receipt 통계 → 미달 시 abstain
                             # (synthetic 테스트 월드에서만 ≥0.99 hard assert — §8)
# 비수축 판정(‖a_{k+1}−a_k‖ 증가)은 v2에서 abstain trigger가 **아니라 로그 전용 진단**
#   (per-hop L1 renorm의 비선형성 때문에 건강한 실행에서도 일시 증가 가능 — §2.4·§6.
#    비오염 validation에서 경험 보정 후에만 trigger 승격 가능, 승격 자체가 prereg 대상)
# depth 게이트 — point estimate 금지, per-corpus 라벨 샘플의 bootstrap 95% LCB로 판정:
#   LCB ≥ 0.90 → K=3 eligible / LCB ∈ [0.85, 0.90) → K=2 / LCB < 0.85 → 순회 OFF
JUDGE_SAMPLE_N = 200         # 도메인별 고정-n 라벨 샘플 (musique judge F1 seed 분산 실측:
                             # 0.8645(s7) vs 0.7773(s13), n=100, SE≈0.04 — 0.85 경계 걸침 → LCB 필수)
# stale-poisoning 주입 파라미터 (H-T3 — 설계자 자유도 제거, 상수 블록으로 고정)
STALE_PER_Q     = 1                          # 질문당 주입 stale bridge 수
STALE_COS_MATCH = "gold bridge cosine ±0.02" # 주입 fact의 cosine 배치 = gold 대응 bridge에 매칭
B_DOSE_GRID     = (0.5, 0.25, 0.1)           # supersede 반복 dose (dose-response arm 겸용)
```

### 2.3 Seed (질의는 seed와 재시작으로만 들어간다)
```
s = topm_sparsify( softmax( W(·|c) / TAU_SEED ), SEED_M );  s ← s / Σs
```
- 대수적 사실: `exp(W/τ) = exp(α/τ) · b^{λ_b/τ}` — **seed 자체가 이미 b^{λ_b/τ} 전도도를 품는다.** seed = `plan()` readout의 절단이므로, 순회의 진입점부터 같은 場이다.
- 노드로의 투영 시 `deg(v)`로 나눔 = HippoRAG의 node-specificity `|P_i|^{-1}` 유사물 (허브 독점 방지, arXiv:2405.14831).
- **계보 명시 (prior-art 정직성)**: 이 seed 설계는 HippoRAG-2의 dense-score-weighted PPR reset 계보다. 진짜 차별점은 4가지 — ① **0-LLM 질의 경로** (HippoRAG 2는 질의시 LLM triple-filter 사용), ② star-expansion 하이퍼그래프 incidence, ③ **O(0) supersession invalidation**, ④ μ=0-admissible 인증 floor. 이 4가지가 재구현 아닌 공학인 이유다 (§9).

### 2.4 One hop (edge → node → edge, bincount segment-sum 2회)
```python
w_in   = (a * g)[edge_idx]                                    # g_e = b(e)^κ  (supersession 전도도)
n      = np.bincount(node_idx, weights=w_in, minlength=N) / deg_node    # edge→node: 허브감쇠
ã      = np.bincount(edge_idx, weights=n[node_idx], minlength=M) / arity # node→edge: 멤버 평균
                                                              # (EDVW 슬롯 γ_e(v)는 uniform 1/r_e로 예약)
ã      ← ã / max(‖ã‖₁, ε)                                     # L1 재정규화
a_{k+1} = (1−γ)·s + γ·prune_topm(ã, PRUNE_M)                  # 재시작 = skip 항 (Dong rank-collapse 방어, arXiv:2103.03404)
```
- **전이 연산자는 slow 성분만** (COO 인덱스, deg, arity, b) — 질의-독립이라 bake 시 1회 구축·캐시, supersede write에 대한 invalidation이 구조적으로 0. 질의는 seed와 재시작 항으로만 들어온다.
- `b`는 COO 구조 **안이 아니라 별도 벡터** — supersede()가 float 1개만 쓰고 재빌드가 전혀 없다.
- hop별 top-m 절단은 **compute guard이지 의미론이 아니다**: 잘린 질량을 receipt에 기록 (실월드 처리 = §2.2 KEPT_MASS_ABSTAIN; scoring 의미론에 per-hop 하드 비선형 금지, 경로독립성 유지 arXiv:2211.09961).
- **명시적 비선형성 고지 (v2)**: per-hop L1 재정규화 + 절단으로 전이 연산자는 엄밀히는 **비선형**이다. 두 귀결을 명기한다 — (a) "선형 수축 ⇒ halting은 고정 k의 변장" 논증과 수축-단조 가정은 근사적으로만 성립 (→ 비수축 판정은 로그 전용, §2.2); (b) **재정규화는 균일한 b^κ 감쇠를 상쇄한다** — b의 *상대* 차이만 전파에 영향. stale-poisoning(bridge 하나만 감쇠)에는 문제없으나, **코퍼스 전역 균일 supersession은 구성상 순회 no-op**이다. 이 사실은 prereg 문서와 §4 주장문 범위에 명기.

### 2.5 종료조건과 최종 결합
- **종료 = K 스텝 도달 (고정), 수렴 판정 없음.** hop-k 기여는 γ^k = 0.5^k로 기하 감쇠 — 2 hop 밖 질량 ≤ 12.5%가 수식에서 자동으로 나온다.
- **최종 점수** (v2 — support 제한 + raw-양수 마스크):
```
Δ(e)        = a_K(e) − a_0(e)
S           = support(a_K) ∪ support(a_0)            # 비영 union support — 전체 M-차원 금지
R(e)        = 1[Δ(e) > 0] · ReLU( z_S(Δ)(e) ),  e ∈ S;  R(e)=0 otherwise
W_trav(e|c) = W(e|c) + μ · R(e)                       # μ=0 ⇒ 오늘의 pointwise와 비트 동일
```
- **z_S 제한 이유 (BLOCKING 해소)**: 전체 M-차원 z-norm은 ~99% 영-엔트리가 std를 지배 → frontier z-score O(10–500) → μ∈[0.1,0.8]이 W(cosine [−1,1] + λ·log b)를 삼키거나, seed-의존적으로 인증이 영원히 μ=0으로 붕괴. z는 S 위에서만. MU_GRID는 이 정규화 하에서 T1 재보정 후 lock.
- **raw-양수 마스크 이유**: z_S는 pool 중심화라 **순수-노이즈 순회에서도 후보 절반이 양수 부스트**를 받는다. `1[Δ>0]`는 "음수 방향 원시 이동엔 부스트 없음"을 추가로 강제하지만, **F1 floor를 "순회가 증거를 찾은 곳만 부스트"로 서술하는 것은 금지** — null-순회 오염의 유일한 방어선은 μ 인증(F2)이다. 이 문장은 prereg 문서에 그대로 들어간다.
- **γ=0 특례**: γ=0이면 Δ≡0 → z_S가 std=0으로 나눔. μ=0과 동일한 **early pointwise return**으로 처리 (ε-guard가 아니라 분기) — 그래야 "γ=0 ⇒ retrieve()와 비트 동일" 테스트가 성립한다.

---

## 3. readouts.py 통합 — traverse()는 SAME field의 4번째 readout

- 파일: 신규 `traversal.py` (연산자 + receipt dataclass) + `readouts.py`에 `traverse()` 추가. `retrieve()/plan()/dispatch()/supersede()`는 **한 글자도 안 바뀐다.** 모듈 docstring의 "one write, three effects"는 **"three effects (four where traversal is certified)"**로 갱신 — 배치 기본값이 μ=0(순회 OFF)이므로 무조건적 "four effects"는 과대주장 (§4·§5).
- 의사코드:

```python
@dataclass
class TraversalReceipt:
    seed_edges: np.ndarray; mu: float; gamma: float; K: int; kappa: int
    kept_mass: list[float]                # hop별 절단 후 잔존질량 (실월드: 통계+abstain feed)
    paths: list[tuple]                    # 탐욕 합성 argmax 사슬 (아래 명세) — 참 최대기여 경로 아님
    n_eff: float                          # 1-hop parent-contribution 근사 (아래 명세)
    contraction_log: list[float]          # ‖a_{k+1}−a_k‖ — 로그 전용 진단 (abstain trigger 아님)
    abstained: bool; abstain_reason: str | None

def traverse(field: WeightField, query_emb, k=10, mu=0.0, K=K_DEFAULT, kappa=1, gamma=GAMMA):
    """(iv) 순회 readout: 같은 場. mu=0 OR gamma=0 ⇒ retrieve()와 비트 동일 (early return)."""
    hg = field.hg
    W = field.value(query_emb)                             # 기존 pointwise 場
    if mu == 0.0 or gamma == 0.0:
        return _pointwise(W, k, reason=f"certified floor (mu={mu}, gamma={gamma})")
    s = _softmax_topm(W / TAU_SEED, SEED_M)                # seed = plan() 분포의 절단
    g = hg.base_salience ** kappa                          # supersession 전도도 (COO 밖 벡터)
    a, rc = s.copy(), TraversalReceipt(seed_edges=np.flatnonzero(s), mu=mu,
                                       gamma=gamma, K=K, kappa=kappa, ...)
    for step in range(K):
        n  = np.bincount(node_idx, weights=(a*g)[edge_idx], minlength=N) / deg_node
        at = np.bincount(edge_idx, weights=n[node_idx], minlength=M) / arity
        at /= max(at.sum(), 1e-12)
        a_new = (1-gamma)*s + gamma*_prune_topm(at, PRUNE_M, rc)   # kept_mass 기록
        _record_greedy_paths(rc, a, a_new, step)           # 탐욕 합성 argmax receipt
        rc.contraction_log.append(np.abs(a_new - a).sum())
        a = a_new
    if _tripwire(rc, s, a):                                # §5: entropy / n_eff / kept_mass
        return _pointwise(W, k, reason=rc.abstain_reason)  # abstain도 receipt에 남는 1급 출력
    S  = np.flatnonzero((a != 0) | (s != 0))               # support 제한 (§2.5)
    d  = a[S] - s[S]
    R  = np.zeros_like(W); R[S] = (d > 0) * np.maximum(_znorm(d), 0.0)
    Wt = W + mu * R
    order = np.argsort(-Wt, kind="stable")[:k]             # _ranks()와 같은 stable-tie 규율
    return order, Wt[order], rc
```

- **Path receipt 명세 (v2)**: 엄밀한 2-hop 경로 열거는 Σ_v deg(v)² triple — deg 5k 허브 하나가 25M triple을 낳으므로 불가. receipt는 **탐욕 합성 argmax**: hop마다 각 생존 엣지에 대해 (최대기여 parent_edge, via_node, contrib)를 O(nnz)로 기록. **이것은 참 최대-기여 경로가 아니라 탐욕 근사임을 receipt 자체에 문서화한다.**
- **n_eff 재정의 (v2)**: "top-k 기여 경로 유효수"는 receipt에서 계산 불가. 대신 **top-k 결과 엣지들의 1-hop parent-edge 기여** 위에서 정의: 각 top-k 엣지 e에 대해 node→edges 인접(gather, 저렴)으로 parent 기여 {c_p}를 모으고 `n_eff(e) = (Σc_p)²/Σc_p²`, 최종 `n_eff = min over top-k`. 1-hop 근사임을 문서화.
- 결정론: 순수 numpy 세그먼트-합 + stable argsort tie 규율 (`weight_field._ranks` 관습) → 동일 (COO 스냅샷, seed, γ, K, κ, μ)에서 비트 재현.

---

## 4. 순회 × supersession — 좁혀진 novelty 코너

**b가 전이에 들어가는 방식**: §2.4의 `g_e = b(e)^κ`가 edge→node 흡입 단계에 곱해진다. L-hop 경로 가중은 `Π_i b(e_i)^κ`로 복리 — superseded bridge 하나가 그 엣지를 지나는 모든 하류 경로를 가라앉힌다. 단 b>0 항상 (Eilu-va-Eilu) → 반흡수(semi-absorbing). `supersede(decay=0.5)` 한 번 = 전도도 절반. (재정규화로 인해 **상대** b 차이만 작동 — §2.4 고지.)

**Mechanism-genericity 고지 (주장문에 내장, v2)**: b^κ-전도도는 기계적으로 **일반 edge-weighted PPR**이다 (Neo4j GDS `relationshipWeightProperty` 수준; 가중 전이행렬은 교과서 재료). 이 메커니즘 자체로는 어떤 novelty도 주장하지 않는다 — 리뷰어는 weighted-PPR 한 방으로 죽일 수 있고, 그 전에 우리가 먼저 말한다.

**논문에 쓸 수 있는 문장 (v2 — 유일 허용, H-T3 전체 통과 조건부)**:
> "주장하는 것은 메커니즘이 아니라 **결합(conjunction)**이다: 한 번의 비파괴 supersession(b 한 번의 write)이 같은 하나의 場의 검색·plan 분포·다중홉 전파를 동시에 stale 지식 우회로 재라우팅하며, superseded 사실은 도달가능·감사가능·path-receipt 상태로 남는다. 이것은 readouts.py의 기존 honesty note와 동형인 **아키텍처 서술이자 measured-gain 주장이며, priority 주장이 아니다**. 검증 범위: AXIS 7 스윕은 예산-한정 표적 fetch였으므로 '검증한 범위 내 unclaimed'로 한정하며, 인접 문헌(Kumiho류 분리 설계의 의도적 supersession-점수 분리, MemStrata supersession 판정 AUROC 0.59)은 이 통합이 나쁜 설계일 수 있음을 적극 시사한다 — 본 주장은 H-T3의 5-arm 비교(bi-temporal 필터·separated-graded 태그 포함)와 H-T3b(오-supersession 부수피해 정량화)를 통과한 음성-증거 위에서만 성립한다."

**Stale-poisoning falsifier (§8 H-T3, v2 확장)**: T4.5가 지은 하이퍼엣지 월드에 질문당 STALE_PER_Q개의 고-cosine(STALE_COS_MATCH 배치) superseded 모순 bridge fact를 주입 후 B_DOSE_GRID로 supersede. **5 arm + 부수피해**:
- (a) pointwise W
- (b) **bi-temporal Zep/Graphiti 충실 구현** (arXiv:2501.13956): valid_at/invalid_at + point-in-time 질의. **arm (b)의 audit 의미론을 prereg로 정확히 고정**: current-mode = invalid_at 필터, audit-mode = 명시적 point-in-time 질의로 full store 접근 — audit-recall ≈ 1.0 by construction임을 **인정하고 시작한다** (약화된 상대 금지, strawman 하우스룰).
- (c) κ=0 순회 (ablation)
- (d) κ=1 순회 (본 설계)
- (e) **Kumiho식 separated-graded**: 점수와 분리된 불변 revision + pointer 태그, 단 graded 강도 보유 — 문헌이 supersession을 점수에서 *의도적으로* 분리하는 최강 대항설계.
- **H-T3b (부수피해 arm)**: **옳은** bridge를 supersede(B_DOSE_GRID)하고 하류 current-fact recall 손상을 dose 함수로 측정. "one write, four effects"의 dual = **"one wrong write, four corruptions"** — Π b^κ 복리는 오판 하나가 모든 하류 경로를 오염시키고, MemStrata AUROC 0.59는 supersession 판정이 noisy할 것임을 말한다. kill 조건은 아니나 **주장 문장과 반드시 병행 출판**.

**측정 지표**: stale-support rate@top-k / hop 2–3 current-fact recall / historical-audit recall / **dose-response 순서 정합** (B_DOSE_GRID dose vs stale fact의 rank 순위 Spearman ρ — graded 감쇠만 표현 가능하고 이진 필터·bi-temporal 스위치는 구조상 표현 불가능한 지표. kill (ii)의 "metric advantage" 질문에 대한 prereg 답).

**Kill 조건 (v2)**:
- (i) (d)가 (c)를 stale-support rate에서 >2×SE로 못 이기면 → supersession-in-traversal 기여 없음 → novelty 문장 사망.
- (ii) (b)가 (d)를 current-fact recall·historical-audit recall **그리고 dose-response 순서 정합** 3지표 전부에서 따라잡으면 → graded one-field 감쇠는 "필터+감사모드 분리"로 붕괴 → novelty 문장 철회, 아키텍처-결합 서술만 잔존.
- (iii) (d)가 (e)를 어떤 prereg 지표에서도 >2×SE로 못 이기면 → separated-but-graded 설계의 우위 = **기록되는 loss** (조용한 흡수 금지) — "왜 문헌은 전부 분리하는가"에 대한 우리 답이 틀렸다는 뜻.

---

## 5. Floor / Guard — certified μ와 abstain

**2단 floor** (`receipts/receipt_cosine_floor.py`의 정직-범위 언어 복제):
- **F1 (대수적, per-edge)**: `R ≥ 0` ⇒ `W_trav(e|c) ≥ W(e|c)` 모든 엣지에서 성립. **단** — (i) per-query nDCG ≥ W는 주장하지 않는다 (양수 부스트도 re-rank; cosine-floor에서 per-query min gap ≈ −0.22 실측 선례); (ii) **F1은 "증거 있는 곳만 부스트"가 아니다** — z_S 중심화 탓에 순수-노이즈 순회도 양수 부스트를 만든다 (raw-양수 마스크가 완화하되 제거 못 함). null-순회 오염의 방어선은 오직 F2. 두 문장 모두 prereg 문서 명기.
- **F2 (통계적, mean-nDCG)**: μ ∈ MU_GRID를 paired validation에서 선택하되 **멀티플리시티 보정**: 비영 4 arm 위 max-mean 선택 후 단일 z=2 검정은 명목 오인증률을 초과 (λ에서 라이브로 시연된 winner's-curse 채널과 동일) → 실제 게이트 = `SELECT_Z_ADJ = 2.5` (max-t/Bonferroni, one-sided α≈0.0057). 추가로 **H-T2(5-seed null world, 인증 0건 요구)를 empirical 멀티플리시티 컨트롤로 공식 지정**하고 시뮬레이션 오인증률을 결과 문서에 보고. 고정마진 게이트 금지 (`expB_longdoc.py:36-39` — null world가 λ=0.8을 순수 노이즈로 인증한 선례).
- **이식 quirk 문서화 (의도된 보수성)**: `_select_lambda`(expB_longdoc.py:118–144)는 인증된 작은 λ가 있어도 이후 더 좋은 평균의 λ가 인증 실패하면 0을 반환한다 — 보수적이며 **의도된 동작**으로 `_select_mu`에 그대로 이식·주석 명기.

**합성 규율**: 인증은 순차적 — λ_b(·λ_j) 동결 후 μ를 **배치된 pointwise W를 baseline으로** 인증. floor 전이 합성: `W_trav ≥ W ≥ cosine` (2단 의미). **도메인(corpus)별 인증** — 전역 도박 금지.

**언제 끄나 (abstain 3층, v2)**:
1. **bake-time**: 해당 도메인에서 μ 인증 실패 → μ=0, 순회 미배치 (기본값 OFF).
2. **depth 게이트 (LCB 기반, v2)**: point-estimate judge F1 판정 금지 — musique 실측이 seed-불안정(0.8645 s7 vs 0.7773 s13, n=100, SE≈0.04)하고 0.85 경계에 걸쳐 있어 v1 규칙은 seed 복권이었다. **판정 = 도메인별 고정-n(JUDGE_SAMPLE_N=200) 라벨 샘플의 bootstrap 95% LCB** (`stats_protocol.bootstrap_ci` 재사용): LCB≥0.90 → K=3 eligible / [0.85,0.90) → K=2 / <0.85 → OFF. **라이브-도메인 주석 프로토콜 명시**: gold-free 배치(실제 memory-substrate 사용처)에서는 judge F1이 측정 불가 → 도메인 온보딩 시 bake-time에 n=200 층화 샘플을 1회 라벨링(사람 또는 gold-지참 검증셋)하고 주기 갱신. **라벨 샘플 없는 도메인 = 순회 영구 OFF** (P^N 가드가 작동 불능이므로).
3. **질의시 trip-wire** (고정 상수, 미조정): (i) 엔트로피 폭발 `H(a_K)−H(a_0) > log 4`, (ii) `n_eff < 1.5` (§3의 1-hop 근사 정의), (iii) **kept_mass < KEPT_MASS_ABSTAIN** (실월드) — 하나라도 걸리면 pointwise W 반환 + refusal receipt. 비수축 판정은 로그 전용으로 강등 (§2.2). **trip-wire 상수는 유도가 아니라 prereg 단언**이며 abstain 방향으로만 실패한다 — 대신 **corpus별 trip 발화율을 EXPB_TRAVERSAL_RESULTS에 의무 보고** (가드가 질의 40%에서 발화해 처치효과를 조용히 먹는 상황을 가시화).

**Phase 2 (μ>0 인증 후에만)**: seed-margin 버킷별 계층화 인증 (버킷마다 자체 0-admissible 게이트, SELECT_Z_ADJ 적용). 게이트 임계 자체를 validation에서 조정 = selection 채널 재개방 = 금지.

---

## 6. 노이즈 복리 대책

judge-ceiling: 場은 judgment 신호로 갱신되는 시냅스 가중장(DPI) — 전파는 **noisy judge는 고칠 수 있어도 bad judge는 절대 못 고친다** (선형 확산은 분산만 죽이고 상관 bias는 통과시킴).

| 메커니즘 | 수단 | 정량 근거 |
|---|---|---|
| 직렬 복리 P^N | K=2 고정 (K=3 = canon-amendment + hop-3 인증 조건부) + LCB depth 게이트 | 0.97³=0.91 OK / 0.78³=0.47 사망. hop 이득 +0.014/+0.082/+0.064–0.072 (2/3/4hop)는 **동기 부여용 인용만** — §8 H-T1의 출처 정직성 참조 |
| 증폭 상한 | γ ≤ 0.5 하드캡 → 조건수 2γ/(1−γ) ≤ 2× | Bianchini-Gori-Scarselli TOIT 2005 `‖Δπ‖₁ ≤ (2α/(1−α))δ` |
| rank collapse | 재시작 = seed 재주입 (skip 항). **restart 형식** 채택 — lazy-walk의 무한극한은 seed-독립 정상분포 = collapse | Dong arXiv:2103.03404; APPNP arXiv:1810.05997 |
| hop별 오류 발산 | τ≥1 + argmax-사슬 금지 (per-hop 소프트 혼합, 날카로운 분리는 최종 readout 1회만) | Ihler-Fisher-Willsky JMLR 2005; Krotov-Hopfield arXiv:1606.01164 |
| 상관 bias | n_eff 진단 (1-hop 근사, §3) — n_eff≈1 = 단일사슬 = P^N 그대로 → abstain | von Neumann 1956 / Evans-Schulman 1999 |

**Empirical transfer 갭 명기 (v2)**: expB spread arm의 "3-step 생존" down payment는 **lazy-walk 연산자**(`expB_longdoc.py:113`, `act=(1−γ)act+γ(B@act)`) 하에서 측정된 것이고, 본 spec은 **restart 연산자 + top-m 절단**을 배치한다. restart 선택은 이론적으로 옳으나(APPNP), **T3에서 정확한 restart 커널로 spread arm을 재실행(저렴)하기 전까지 이 down payment 인용은 '연산자 상이, transfer 가정' 한정어를 달고만 쓴다.**

**KQV canon 준수 (v2)**: canon은 "skip 항 + forced hop≤2". K=3 prereg arm은 이를 초과하므로 — 묵시적 초과 금지. **K=3 활성 전 KG에 명시적 canon-amendment 노드를 기록**한다 (정당화 재료: 실측 3-hop 정점 +0.082 [동기용], restart-skip 항, LCB≥0.90 depth 게이트). H-T1 hop-3 계층 인증 실패 시 amendment 노드는 기록하지 않고 K=2 캡 유지.

**pointwise 후퇴 시점** = §5의 3층 그대로. 후퇴는 언제나 비트-동일 pointwise + 이유 receipt.

---

## 7. 스케일 아키텍처 (100k+)

**⚠ 상태 고지 (v2)**: v1의 "실측 9.5ms @ 100k (bench_axis5)" 및 그 분해(1.9/0.9/4.8/1.9ms)는 **repo에 아티팩트가 없다 → UNVERIFIED로 강등** (수치-claim spot-check·verify-async-results 하우스룰). T6에서 bench 스크립트+로그를 커밋하기 전까지 어떤 문서에도 measured로 인용 금지. 아래 수치는 재판 중 재실측된 참고치: fp32 `P@q` 2.6ms, COO hop 1.8ms/hop @ nnz=300k, argpartition 0.1ms @100k·384d (Apple Accelerate) — ≤10ms 예산 자체는 현실적.

**Precompute (bake/write 시)**:
- pooled 엣지 임베딩 P — **fp32 저장** (fp16 기각: matmul 2× 손해 + BLAS-less 플랫폼 ~100× 페널티; per-platform fp16 pin은 후순위 옵션). **실 임베딩 차원으로 재산정**: 768d(`neo4j_loader`) = 100k×768×4B ≈ **307MB**, 1024d(bge-m3) ≈ **410MB**, (384d였다면 153MB). 수용 가능.
- **`WeightField.__init__`에서 pooled 임베딩 1회 pre-normalize** (수치적으로 idempotent) — 현행 `attention_alpha`는 매 `field.value()` 호출마다 전체 재정규화하여 per-query 예산을 약 2배 잠식.
- COO 인덱스 배열 (edge_idx, node_idx; nnz = Σarity ≈ 300k) + deg_node(clip≥1), arity 벡터 / slow prior `λ_b·log b + λ_j·j` / **b는 COO 밖 별도 배열**. `incidence()` dense 호출 절대 금지 (§2.1).

**Per query (목표 ≤10ms @100k, T6에서 실측·커밋)**: dense cosine `P@q` → top-m seed 절단 → K=2 hop (bincount 4회) → 결합+top-k. ANN 인덱스·사전계산 PPR row 불필요 — ≥1M 엣지 전까지 도입 금지.

**Invalidation**: `supersede()` = b 배열 float 1개 write. b가 hop 시점 벡터곱으로만 들어가므로 **무효화할 사전계산물이 없다 — O(0) by construction**. Longinus incidence 변경(드묾)만 COO 재빌드 (100k members에서 sub-second). Neo4j = write-plane/정본, numpy = query-plane; supersession/judgment write는 `(edge_id, b, j)` delta 스트림만. per-query GDS PPR 금지.

**스케일 사다리**: Stage 1 (현행, ≤300k edges) query-time star push / Stage 2 (1M–10M) frontier-limited ACL local push (FOCS 2006; residual ledger = 세밀 receipt) / Stage 3 (>10M) PPRGo식 baked truncated PPR rows (arXiv:2007.01570) + dynamic-PPR repair (arXiv:1603.07796). 인증된 μ는 스테이지 간 이전.

**EDVW 예약 슬롯**: edge→node 단계의 멤버 가중 `γ_e(v)`는 현재 uniform 1/r_e. 역할 슬롯이 생기면 여기 주입 — Chitra-Raphael (arXiv:1905.08287) clique-동치 탈출의 정식 경로.

---

## 8. Prereg 실험 — expB harness 확장

모든 arm: SEEDS=(0..4), paired, `stats_protocol.paired_trend_p / bootstrap_ci / bh_adjust`, ALPHA=0.05. **추가 선행조건**: 현재 "보고만 되는" spread arm null offset(`numbers['spread_null_offset_note']`, expB_longdoc.py:256)을 순회가 scored arm이 되는 순간 **게이트로 격상** — null 분기에서 `numbers['null_spread_measured_bias']`(line 267)가 이미 계산되므로 격상은 실현 가능(재판 검증 완료).

**측정 월드에 대한 정직 고지 (v2, BLOCKING 해소)**: v1이 인용한 "기존 2wiki/musique 하이퍼엣지 월드"는 **repo에 존재하지 않는다**. `ab_p5_full.py`/`substrate_bench.py`는 per-query 문단 pool(10–20개)을 additive-j 場으로 채점할 뿐 `hypergraph.Hypergraph`를 통과하지 않으며, `doc_builder.py:20`이 QA 로더를 "the NEXT piece, not this one"으로 명시한다. 따라서 — (i) **T4.5(하이퍼엣지 월드 빌더)가 T5의 hard 선행조건**이다; (ii) 인용된 hop-계층 down payment(+0.014/+0.082/+0.064–0.072)는 **문단-pool additive-j delta이지 순회 월드에서의 측정이 아니다 — transfer는 가정**이며, 동기 부여로만 인용하고 증거로 인용하지 않는다.

- **H-T1 (효능 — 실데이터 hop 계층화)**: T4.5 월드에서 `Δ(W_trav − W)`를 hop 계층 위에서. 성공 = (i) paired_trend_p 기울기>0, p<0.05, (ii) hop≥3 계층 부트스트랩 CI가 0 배제, (iii) 데이터셋 간 BH 보정. 성공 기준은 계층화된 이득 성장이지 전체 평균 아님 — 1-hop 질의에서 no-op 허용. **검정력 게이트 (v2)**: 어떤 계층에서든 **음성 verdict를 내리기 전 `stats_protocol.required_n`(line 72) 검정력 확인 의무** — 기존 계층은 소표본(3hop n=57에서 +0.082가 겨우 ~2×SE, 4hop n=39)이므로 검정력 미달 null을 반증으로 읽는 것을 금지. 미달 시 verdict = UNDERPOWERED(OPEN 유지).
- **H-T2 (teeth — null world, v2 재정식화)**: 차수보존 membership-shuffle 월드. **게이트 = "5 seed 전부에서 인증 μ=0 ⇒ 배치 경로 W_trav − W가 항등적으로 0 (μ=0 early-return이 비트 단위로 보장)"**. v1의 "모든 순회 delta 정확히 0"은 raw-residual 조건으로는 충족 불가능 — 셔플 월드에도 구조가 있어 a_K≠a_0, R≠0이 generic. raw residual이 아니라 **인증에** 게이트를 건다. 하나라도 μ>0 인증 → verdict = **HARNESS_BROKEN**. 겸(§5): μ-selection 멀티플리시티의 empirical control — 시뮬레이션 오인증률 보고.
- **H-T3 (stale-poisoning, novelty의 이빨, v2 확장)**: §4의 5-arm (a)–(e) + H-T3b 부수피해 + dose-response arm(B_DOSE_GRID). 주입 파라미터는 §2.2 상수 블록에 고정(STALE_PER_Q/STALE_COS_MATCH/B_DOSE_GRID) — **주입 설계 자유도가 (c)vs(d) 효과크기를 결정하므로 설계자 재량 배제**. kill (i)(ii)(iii) 전부 통과 + H-T3b 병행 출판 시에만 §4 문장 허용.
- **H-T4 (judge-ceiling 스윕)**: `JUDGE_ACC ∈ {0.97, 0.78}`. **구현 예산 정정 (v2)**: JUDGE_ACC는 module-level 상수로 `_judge_bits` 내부에서 소비됨 — 스윕은 "1줄 변경"이 아니라 `run_expB/_eval_world/_judge_bits` 파라미터화 배관이 필요 (사소하나 T5 예산에 계상). 사전 잠금 예측: (i) 0.97에서 μ>0 인증 + hop≥2 delta CI lo>0; (ii) 0.78에서 guard 유지 (mean test delta가 −TOL 미만 절대 금지) + μ→0 수축. (ii) 실패 = guard 반증; (i) 실패 = 순회 무효(정직한 negative). 중간지대 없음.
- **H-T5 (conjunctive 계층화, v2 신설 — §9 주장 강등의 짝)**: gold가 **단일 hyperedge 내 공동멤버십**을 요구하는 질의 vs 분해가능 pair 질의로 계층화. 처치 = W_trav vs 분해-후-교집합 baseline. 이 검정 통과 전까지 §9의 conjunctive 우위는 가설 신분.
- **비교 arm**: `RRF(W, a_K)` (k=60, `rrf_scorer` 관습). hop≥3 계층에서 RRF가 인증-가산형을 이기면 **기록되는 finding**. (선택 stretch: HippoRAG-2 reference arm — 단 질의시 LLM 예산 차이로 **non-comparability를 기본 서술**로, §9.)
- **Receipt**: `receipts/receipt_traversal_floor.py` 신설 — F1 대수 floor 검증 + **negative oracle**: 부호 있는(no-ReLU·no-mask) 잔차는 F1을 반드시 위반해야 함, 아니면 receipt 자체가 공허(vacuous). **kept_mass ≥0.99 hard assert는 synthetic 테스트 월드 한정** — 실 KG에서는 64 seed가 허브를 지나면 1-hop frontier가 PRUNE_M=1024를 초과하는 heavy tail이 정상이므로, 실월드 kept_mass는 측정 receipt 통계로서 abstain 경로(§5)에 공급 (테스트 fail 아님).

---

## 9. 정직 한계 — 0-inference 순회가 못 닿는 것

**닿는 것**: bake 시점에 hyperedge로 물질화된 bridge를 지나는 entity-bridged chain/star 질의 ≤3 hop (HippoRAG 존재증명: ≈IRCoT, 10–30× 저렴).

**가설 신분으로 강등 (v2)**: "n-ary hyperedge 하나 안에 공존하는 conjunctive 제약" 우위 주장은 — (i) HyperGraphRAG(arXiv:2503.21322)의 retrieval이 이미 다중 질의-entity를 포함한 hyperedge를 채점하므로 점유 영토와 충돌하고, (ii) 지정된 falsifier가 없었다. **v2 처리**: 주장을 **"K-step 인증-floor 확산 하에서의 conjunction 보존"**으로 좁히고 HyperGraphRAG의 (확산 없는) retrieval scoring과의 차별점을 명시하되, **H-T5 통과 전까지는 표현-계승 능력 서술(capability inherited from representation)이지 novelty 주장이 아니다.**

**못 닿는 것 (이 표현 그대로 명기, 벤치마크 헤징 금지)**: ① 비단조 연산 — 비교/집계/부정/시간순서 (확산은 경로가중의 단조가산 함수); ② 물질화 안 된 관계 (커버리지 = bake 추출 recall이 상한 — 추출 갭은 1급 miss로 로깅); ③ 검색된 텍스트 내용에 다음 sub-query가 의존하는 분해 (IRCoT arXiv:2212.10509 — live inference 영토, 그마저 judge ceiling에 갇힘); ④ **코퍼스 전역 균일 supersession** — 재정규화가 균일 감쇠를 상쇄하므로 구성상 순회 no-op (§2.4).

**계보와 차별점 (v2)**: seed 설계 = HippoRAG-2 dense-score-weighted PPR reset 계보 (arXiv:2502.14802) — 명시적으로 인정. 진짜 차별점 4가지 = **0-LLM 질의 경로** (HippoRAG 2는 질의시 LLM triple-filter) / star-expansion 하이퍼그래프 incidence / **O(0) supersession invalidation** / **μ=0-admissible 인증 floor**. T5에서 HippoRAG-2와의 직접 비교는 질의시 LLM 예산 비대칭으로 **non-comparability 서술이 기본** (선택 reference arm은 stretch). 이 4가지 서술이 본 공학을 "재구현"에서 구분한다.

**Novelty 주장 금지 구역**: 순회 자체(HippoRAG/PPR) / n-ary RAG(HyperGraphRAG) / edge-weighted PPR 메커니즘(§4 고지) / GraphRAG식 global sensemaking(arXiv:2404.16130) / GNN·AllSet 학습 파라미터. **허용 주장은 §4의 문장뿐**, H-T3 전체(kill 3종 + H-T3b 병행) 통과 조건부, '검증한 범위 내 unclaimed' 한정.

**선택적 escalation hook (기본 OFF)**: 결정론적 난이도 게이트 → P5 'direct' listwise rerank (`ab_p5_full.py` arm 재사용)를 substrate의 **소비자**로 배치. 실측 |ΔF1|<0.03이므로 기본 비활성; 활성화 시 escalation rate 공개. 0-LLM 주장은 substrate 경계에 한정.

---

## 10. 구현 순서

- **T1 — `traversal.py` 연산자** (1–2일): COO 인덱스 빌드(edge_idx/node_idx/deg clip≥1/arity) + §2 커널(bincount) + `TraversalReceipt` + prereg 상수 블록. **support-제한 z-norm 하에서 MU_GRID 재보정 → 재보정값으로 prereg lock** (lock 이후 재협상 금지). 테스트: 결정론(비트 재현) / 질량 receipt(synthetic ≥0.99 hard) / **μ=0 그리고 γ=0 각각 ⇒ `retrieve()`와 비트 동일** (early-return 분기, `tests/test_readout_identity.py` 확장) / deg=0 노드 포함 월드 NaN-free.
- **T2 — readouts 통합 + floor receipt** (1일): `readouts.traverse()`, docstring **"three effects (four where traversal is certified)"**, `receipts/receipt_traversal_floor.py` (F1 + negative oracle). `supersede()` diff = 0 확인 테스트.
- **T3 — harness teeth** (1–2일): membership-shuffle null world + H-T2 게이트(v2 정식화) + spread null offset 게이트 격상 + **restart 커널로 spread arm 재실행** (§6 transfer 갭 해소, 저렴) + `_select_mu` 이식(SELECT_Z_ADJ + quirk 주석).
- **T4 — stale-poisoning falsifier** (2일): §4 월드 주입기(상수 블록 파라미터) + 5-arm 러너((b)는 bi-temporal 충실 구현, (e)는 separated-graded) + H-T3b + dose-response + kill 3종 판정.
- **T4.5 — corpus-level 하이퍼엣지 월드 빌더** (2–3일, **v2 신설 — T5 hard 선행조건**): 2wiki/musique를 `hypergraph.Hypergraph`로 — nodes=개념/entity, 문단당 1 hyperedge, per-query gold→edge-id 매핑, hop 라벨 = `row['hop']`. `doc_builder.py`가 "NEXT piece"로 지목한 그 조각의 착지. 산출 월드의 기술통계(arity 분포/허브 차수/계층별 n)를 결과 문서에 선행 보고.
- **T5 — 실데이터 인증** (2일): T4.5 월드에서 H-T1(검정력 게이트 포함) + per-corpus judge 라벨 샘플(n=JUDGE_SAMPLE_N, LCB depth 게이트) + per-corpus μ 인증 + H-T4 스윕(JUDGE_ACC 파라미터화 배관 포함) + H-T5 conjunctive 계층화 + RRF arm. 결과 = `EXPB_TRAVERSAL_RESULTS_*.md` (corpus별 trip 발화율 의무 포함).
- **T6 — 질의시 guard + 성능** (1일): trip-wire(entropy/n_eff/kept_mass) + refusal receipt + trip 빈도 통계 + **latency bench 스크립트와 로그를 repo에 커밋** (§7 UNVERIFIED 해소; fp32, pre-normalize, 768/1024d로 측정; 목표 ≤10ms @100k).
- **T7 (후순위, 선택)** — EDVW `γ_e(v)` 슬롯 배선 + `neo4j_loader.py` delta sync `(edge_id, b, j)` + 스케일 사다리 Stage 2 스텁.

**배치 기본값**: μ=0 (순회 OFF). T5의 per-corpus 인증(멀티플리시티 보정) + LCB depth 게이트 + 라벨 샘플 존재, 3조건이 모두 통과한 도메인에서만 μ>0. **K=3은 여기에 canon-amendment 노드까지 4조건.** 이것이 "순회는 거부 가능해야 한다"의 구조적 구현이다.

---

## 11. 재판 처리 내역

**Fatal: 3 critic 전원 0건.** 전 지적은 adjust 등급이며 아래와 같이 처리했다. (수용 = spec 본문에 반영 완료; 부분수용 = critic이 제시한 양자택일 중 한쪽을 채택하고 이유 명기.)

### Critic 0 (11건)
| # | 지적 | 처리 | 근거/위치 |
|---|---|---|---|
| 0-1 | [BLOCKING] 2wiki/musique 하이퍼엣지 월드 부재 — T4.5 빌더 필요 + down payment 출처 정직화 | **수용** | T4.5 신설(§10, T5 hard 선행조건) + §8 정직 고지("문단-pool additive-j delta, transfer 가정, 동기용 인용만"). `doc_builder.py:20` 실물 확인 |
| 0-2 | [BLOCKING] z_c 스케일 버그 — 전체 M-차원 z-norm은 영-엔트리가 std 지배 | **수용** | §2.5: z를 비영 union support S로 제한 + MU_GRID를 해당 정규화 하에서 T1 재보정 후 lock(§10 T1) |
| 0-3 | numpy-only에 scipy CSR 불가 | **수용** | 전 구현을 COO 인덱스 + `np.bincount` segment-sum으로 교체 (§2.1/§2.4/§3/§7). `pyproject.toml` deps=numpy 단독 확인 |
| 0-4 | `incidence()` dense materialize 금지 (10GB) | **수용** | §2.1: H는 표기 전용, COO는 `members`에서 직접 구축 |
| 0-5 | deg=0 NaN + γ=0 std=0 NaN | **수용** | §2.1 deg clip≥1 / §2.5·§3 γ=0 early pointwise return(μ=0 거울) + T1 NaN-free 테스트 |
| 0-6 | n_eff 원정의 계산 불가(허브 25M triple) + path receipt 1경로 한계 | **수용** | §3: n_eff = top-k 엣지의 1-hop parent-contribution 근사(min), path receipt = 탐욕 합성 argmax로 명세·한계 문서화 |
| 0-7 | latency: bench_axis5 아티팩트 부재 / fp16 함정 / attention_alpha 재정규화 / 실차원 768·1024 | **수용** | §7: UNVERIFIED 강등 + T6 커밋 의무 / fp32 채택(307–410MB) / `__init__` pre-normalize / 표 재산정 |
| 0-8 | H-T2 "모든 delta 정확히 0"은 raw-residual로 충족 불가 | **수용** | §8 H-T2 재정식화: 게이트 = 인증 μ=0 ⇒ 배치 경로 비트-0 (early-return 보장) |
| 0-9 | per-hop L1 renorm 비선형성 — 수축 가정 붕괴 + 균일 b 감쇠 상쇄 | **수용** | §2.4 명시 고지 2건 / 비수축 trip-wire → 로그 전용 강등(§2.2, 승격은 비오염 validation 보정 + prereg) / "전역 균일 supersession = no-op" §9 한계에 추가 |
| 0-10 | kept_mass ≥0.99 hard assert는 실 KG에서 prereg 리스크 | **수용** | §8: hard assert = synthetic 한정 / 실월드 = receipt 통계 + KEPT_MASS_ABSTAIN=0.95로 abstain 공급(§2.2·§5) |
| 0-11 | JUDGE_ACC 스윕은 1줄 아님 / _select_mu 이식 가능 / offset 게이트 격상 가능 | **수용** | §8 H-T4 배관 예산 계상 / §5 이식 유지 / §8 격상 명시(`null_spread_measured_bias` line 267 확인) |

### Critic 1 (10건)
| # | 지적 | 처리 | 근거/위치 |
|---|---|---|---|
| 1-1 | depth 게이트 point-estimate = seed 복권; LCB + 라이브 주석 프로토콜 필요 | **수용** | §2.2·§5: bootstrap 95% LCB(n=200 고정 샘플) 판정 + gold-free 도메인 주석 프로토콜 + 라벨 없으면 순회 영구 OFF |
| 1-2 | μ 인증 멀티플리시티 미보정 + _select_lambda quirk 문서화 | **수용** | §2.2 SELECT_Z_ADJ=2.5 (max-t/Bonferroni) + H-T2를 empirical control로 공식 지정·오인증률 보고(§5·§8) + quirk "의도된 보수성" 주석 명기(§5) |
| 1-3 | H-T3 kill(ii) 미결정·auto-fail 근접 — (b) audit 의미론 prereg or kill(ii) 폐기 | **부분수용 (유지 택)** | §4: (b)의 audit 의미론 정확 prereg(audit-recall≈1.0 by construction 인정) + graded 감쇠만 표현 가능한 **dose-response 순서 정합**을 3번째 지표로 추가하여 kill(ii)를 metric test로 존치. 아키텍처-only로의 후퇴는 3지표 전패 시의 결과로 규정 |
| 1-4 | 주입 파라미터가 효과크기를 결정 — 상수 블록 고정 + dose arm | **수용** | §2.2 STALE_PER_Q/STALE_COS_MATCH/B_DOSE_GRID + §8 dose-response arm |
| 1-5 | 9.5ms 수치 UNVERIFIED 처리 | **수용** | §7 (critic 0-7과 병합 처리) |
| 1-6 | ReLU(z_c)는 순수 노이즈에서도 절반 양수 부스트 — 서술 금지 + raw-양수 마스크 | **수용** | §2.5 `1[Δ>0]` 마스크 채택 + §5 F1에 "증거 있는 곳만 부스트 아님, 방어선은 F2뿐" 명기 |
| 1-7 | "one write, four effects"는 인증 도메인 한정 | **수용** | §3 docstring "three effects (four where traversal is certified)" + §4 문장도 조건부화 |
| 1-8 | §9 conjunctive 무falsifier 주장 — 가설 강등 or prereg 검정 | **수용 (양쪽 다)** | §9 가설 강등 + §8 H-T5 신설(공동멤버십 vs 분해가능 계층화), 통과 전 주장 금지 |
| 1-9 | H-T1 소표본 계층의 검정력 미확인 null을 반증으로 읽는 위험 | **수용** | §8 H-T1: 음성 verdict 전 `required_n` 의무 + UNDERPOWERED(OPEN) verdict 신설 + 기존 수치는 동기용 인용만(§6·§8) |
| 1-10 | trip-wire 상수는 단언 — corpus별 trip 발화율 의무 보고 | **수용** | §5: "유도 아닌 prereg 단언, abstain 방향 실패" 명기 + EXPB_TRAVERSAL_RESULTS에 발화율 의무(§10 T5) |

### Critic 2 (9건)
| # | 지적 | 처리 | 근거/위치 |
|---|---|---|---|
| 2-1 | b^κ = 일반 edge-weighted PPR — genericity 고지 inline | **수용** | §4 주장문 앞 mechanism-genericity 고지 단락 + 주장 대상을 conjunction으로 한정 |
| 2-2 | arm (b) strawman — Zep은 bi-temporal | **수용** | §4·§8: (b) = valid_at/invalid_at + point-in-time 충실 구현 prereg (strawman 하우스룰 준수) |
| 2-3 | arm (e) Kumiho식 separated-graded 추가 | **수용** | §4 arm (e) + kill (iii): (e)에 못 이기면 기록되는 loss |
| 2-4 | false-supersession 부수피해 arm 부재 — 주장이 일방향 | **수용** | §4 H-T3b: 옳은 bridge supersede → dose별 하류 손상 측정, 주장 문장과 병행 출판 의무 |
| 2-5 | K=3이 KQV canon(hop≤2) 묵시 초과 | **수용** | §2.2·§6: K=3 = canon-amendment KG 노드 기록 + hop-3 계층 인증의 이중 조건부. 인증 실패 시 amendment 미기록·K=2 유지 |
| 2-6 | spread arm 생존은 lazy-walk 측정 — restart 커널 재실행 or 한정 인용 | **수용 (양쪽 다)** | §6 transfer 갭 명기 + §10 T3에 restart 커널 재실행 편입(저렴) |
| 2-7 | §9 conjunctive vs HyperGraphRAG 충돌 | **수용** | §9: "K-step 인증-floor 확산 하 conjunction 보존"으로 축소 + H-T5 전 capability-inherited 서술 (1-8과 병합) |
| 2-8 | HippoRAG-2 계보 명시 + 차별점 명명 + reference arm or non-comparability | **부분수용 (non-comparability 택)** | §2.3·§9: 계보 명시 + 차별점 4종(0-LLM/star-expansion/O(0) invalidation/certified floor) + 질의시 LLM 예산 비대칭으로 non-comparability 기본 서술, reference arm은 T5 stretch |
| 2-9 | 재판 caveat을 §4 문장 안으로 — 음성증거 한정·예산한정 스윕·인접문헌 경고, measured-gain only | **수용** | §4 문장에 3-caveat 전부 내장 ("measured-gain 주장이며 priority 주장이 아니다" 포함) |

**요약**: 30건 중 28건 전면 수용, 2건 부분수용(1-3: kill(ii) 폐기 대신 dose-response 지표로 metric test 존치 — graded 감쇠의 측정 가능한 우위 질문에 prereg로 답하는 쪽이 정직 / 2-8: reference arm 대신 non-comparability 서술 — 질의시 LLM 예산이 다른 시스템과의 수치 비교는 그 자체가 오도이므로). 반박으로 기각한 지적 = 0건. Fatal = 0건 (3 critic 일치).
