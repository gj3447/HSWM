# HSWM Sheaf 연구 온톨로지

> 상태: `SECONDARY_AI_RESEARCH_MAP`
>
> 기계 정본: `ontology/field/sheaf/HSWM_SHEAF_ONTOLOGY.v1.json`
> 범위: 수학적 정의·1차 출처와 HSWM 후보 대응을 분리한다. HSWM 효능 주장이 아니다.

## 1. Sheaf가 무엇인가

Sheaf는 한마디로 **서로 다른 장소의 국소 데이터를, 겹치는 부분에서 비교하고, 가능한
경우에만 하나의 전역 상태로 붙이는 구조**다.

일반 sheaf는 각 open set `U`에 데이터 공간 `F(U)`를 배정한다. `U⊆V`이면 큰 영역의
데이터를 작은 영역에서 보는 restriction `F(V)→F(U)`가 있고, 다음 두 조건을 만족한다.

1. locality: 두 후보가 cover의 모든 조각에서 같으면 전체에서도 같다.
2. gluing: local sections가 모든 overlap에서 호환되면 그것들을 restriction으로 갖는
   유일한 section이 합집합 위에 존재한다.

Presheaf는 데이터와 restriction만 있고 이 gluing 보장이 없다. 따라서
`sheaf = presheaf + locality/unique gluing`으로 기억하면 된다.

## 2. Cellular sheaf — HSWM에 필요한 계산 가능한 형태

Cellular sheaf는 cell complex 또는 graph/hypergraph의 incidence 위에서 계산한다.

- `F(v)`: vertex `v`의 stalk, 즉 `v`가 가질 수 있는 local state 공간
- `F(e)`: edge 또는 hyperedge `e`의 relation stalk
- `F_{v⊴e}:F(v)→F(e)`: endpoint의 state를 관계 공간으로 옮기는 restriction map

두 endpoint `u,v`가 edge `e`에서 호환된다는 뜻은

\[
F_{u\trianglelefteq e}x_u=F_{v\trianglelefteq e}x_v
\]

이다. 같은 값을 가져야 한다는 말이 아니다. **각자 다른 좌표계의 값을 관계에 맞는
번역기를 통과시킨 뒤 같아야 한다**는 뜻이다. 이것이 단순 consensus나 평균과 sheaf의
핵심 차이다. Hansen–Ghrist는 cellular sheaf를 face-poset functor
`F:P_X→Vect`로 정식화하고 stalk, restriction, global section, Laplacian을 연결한다.

### 작은 예

연구 함수 `A`의 state가 `(claim_strength, novelty)`이고 검증 함수 `B`의 state가
`(evidence_strength, reproducibility, cost)`라고 하자. 둘을 같은 3차원 embedding으로
강제할 필요가 없다.

```text
F(A) = R²        F(B) = R³
    \             /
     ρ_A         ρ_B
       \         /
        F(e) = R²       # relation-local: support, uncertainty
```

`ρ_A x_A`와 `ρ_B x_B`가 가까우면 해당 seam에서 호환된다. 다르면 둘 중 하나가 거짓이라고
즉시 판정하지 않고 translation loss, evidence conflict, 정당한 관점 차이 중 무엇인지 다음
LLM function이 판단할 수 있다.

## 3. 계산 사슬

Graph 위의 0-cochain `x`는 모든 vertex stalk에서 하나씩 값을 고른 것이다. Coboundary는
각 edge에서 restriction mismatch를 만든다.

\[
(\delta x)_e=F_{v\trianglelefteq e}x_v-F_{u\trianglelefteq e}x_u
\]

Degree-zero sheaf Laplacian과 consistency energy는

\[
L_F=\delta^*\delta,
\qquad
E_F(x)=\|\delta x\|^2=\langle x,L_Fx\rangle
\]

이다. `E_F=0`이면 모든 seam에서 호환되며

\[
\Gamma(X;F)=\ker\delta=\ker L_F=H^0(X;F)
\]

가 global section space다. Higher cohomology

\[
H^k(X;F)=\ker\delta^k/\operatorname{im}\delta^{k-1}
\]

는 local data가 globalize되지 못하는 obstruction이나 남는 자유도를 탐지한다. 단 이
대수적 obstruction을 곧바로 “의미 모순”이라고 부르면 안 된다. 어떤 cell/cochain이 실제
HSWM 의미를 보존하는지 먼저 입증해야 한다.

## 4. Neural sheaf가 추가하는 것

Ordinary GCN은 사실상 모든 node가 같은 공간에 있고 edge transport가 identity인 trivial
sheaf diffusion으로 볼 수 있다. Sheaf Neural Network는 edge마다 다른 transport를 허용한다.
그래서 signed·asymmetric·heterophilic 관계와 서로 다른 dimension을 표현할 수 있다.

Neural Sheaf Diffusion은 restriction maps와 diffusion parameter를 학습한다. NeurIPS 2022
논문은 non-trivial sheaf가 ordinary diffusion보다 asymptotic behavior를 더 세밀하게
제어하고 heterophily/oversmoothing benchmark에서 경쟁력 있는 결과를 냈다고 보고했다.
그러나 Connection Laplacian 연구는 full learned sheaf가 overfit과 계산비를 키울 수 있음을
명시한다. Sheaf Hypergraph Networks의 ablation에서도 이론적으로 더 expressive한 general
matrix보다 diagonal restriction이 종종 더 잘 최적화됐다.

따라서 HSWM에서는 `identity → scalar attention → diagonal → low-rank → general`을 같은
예산에서 순서대로 비교해야 한다. “더 일반적인 수학”을 자동 승격하지 않는다.

## 5. HSWM 후보 대응

| HSWM | Sheaf 대응 | 상태 | 핵심 경계 |
|---|---|---|---|
| typed LLM function의 local state | stalk | 후보 비유 | LLM 내부 상태는 명시적 encoder 없이 vector stalk가 아님 |
| n-ary connector | hyperedge relation stalk | 우선 probe | general hyperedge를 simplex로 바꾸지 않음 |
| typed port/adapter | restriction map | 우선 probe | static rule 대신 learned/measured transport |
| episode coherent macrostate | global section | 진단 전용 | global consistency ≠ truth/강제 consensus |
| port mismatch | consistency energy | 가장 먼저 관측 | 높은 energy는 오류 또는 유용한 이견 |
| locally valid/global conflict | cohomological obstruction | 후속 연구 | 정당한 cellular model이 먼저 필요 |
| relation-conditioned routing | learned restriction map | durable W 뒤 실험 | identity/attention/diagonal/low-rank 대조 |
| local outputs→coalition artifact | cosheaf aggregation | 개념 구분 | 방향과 colimit을 무시해 모두 sheaf라 부르지 않음 |

가장 작은 첫 구현은 `E_F`를 **결정 규칙이 아니라 observation feature**로 계산하는 것이다.

```text
typed local states
  -> learned/declared port transports
  -> seam residuals and E_F
  -> HSWM observation tokens
  -> outcome-bound W/routing/topology learning
```

이렇게 해야 sheaf가 또 하나의 정적 하네스가 아니라 HSWM이 자기 연결 상태를 느끼는
감각기관이 된다.

## 6. KG와 hypergraph에 직접 관련된 결과

`Knowledge Sheaves`는 entity embedding을 approximate global section으로, relation schema를
restriction compatibility로 본다. Composite relation inference를 한 framework에서 표현할 수
있지만, zero vector와 zero map이 consistency loss를 trivially 최소화할 수 있으므로 negative
sampling·non-collapse objective가 필요하다고 논문 자체가 경고한다.

`Sheaf Hypergraph Networks`는 각 node와 hyperedge에 stalk를 두고 incidence `v∈e`마다
`F(v)→F(e)` restriction을 둔다. 이것은 HSWM의 n-ary connector에 가장 직접적인 선행이다.
다만 실험은 hypergraph node classification이며 LLM function network나 persistent learning을
증명하지 않는다.

`Opinion Dynamics on Discourse Sheaves`는 agent가 가진 internal opinion과 edge에서 실제로
표현하는 내용을 분리한다. 선택적 표현이나 왜곡까지 restriction map으로 모델링하므로,
멀티에이전트가 무조건 평균 consensus로 붕괴하지 않게 하는 중요한 선행이다.

## 7. 하지 말아야 할 것

- `E_F`를 무조건 최소화해 모든 agent를 합의시키지 않는다.
- 모든 HSWM hyperedge를 simplicial complex로 바꾸지 않는다.
- sheaf consistency를 factual truth, reward, causal efficacy와 동일시하지 않는다.
- full matrix restriction부터 시작하지 않는다.
- graph/node-classification 결과를 HSWM 성능으로 전이 주장하지 않는다.
- 2026년 game-sheaf/KG-semantics preprint를 peer-reviewed foundation처럼 쓰지 않는다.

## 8. 1차 출처 지도

| 층 | 출처 | 이 온톨로지에서 쓰는 범위 |
|---|---|---|
| 기초·계산 | Curry, *Sheaves, Cosheaves and Applications* (2013), arXiv:1303.3255 | cellular (co)sheaf, 과학·공학 응용 |
| spectral | Hansen & Ghrist, *Toward a Spectral Theory of Cellular Sheaves* (JACT 2019) | stalk, restriction, global section, Laplacian |
| neural 시작 | Hansen & Gebhart, *Sheaf Neural Networks* (2020) | non-constant/asymmetric/signed relation diffusion |
| agent 통신 | Hansen & Ghrist, *Opinion Dynamics on Discourse Sheaves* (SIAM 2021) | internal state와 communicated state 분리 |
| KG | Gebhart–Hansen–Schrater, *Knowledge Sheaves* (2021 preprint) | approximate global section, relation composition, collapse caveat |
| learned diffusion | Bodnar et al., *Neural Sheaf Diffusion* (NeurIPS 2022) | learned maps, heterophily, oversmoothing |
| 비용 경계 | Barbero et al., *Connection Laplacians* (2022 workshop) | manual/learned tradeoff, overfit·계산비 |
| higher-order | Hajij et al., *Topological Deep Learning* (2022 preprint) | combinatorial-complex 통합 시야 |
| hypergraph | Duta et al., *Sheaf Hypergraph Networks* (NeurIPS 2023) | node/hyperedge stalk, linear/nonlinear Laplacian |
| 최신 방법 | Hernandez Caralt et al., *Joint Diffusion Processes* (PMLR workshop 2024) | parameter-reduced learned sheaf 후보 |
| frontier | Hernandez & Sanchez-Soto, *Strategic Multi-Agent Systems* (2026 preprint) | game/policy stalk 아이디어만 탐색 |
| frontier | Boudourides, *Sheaf Semantics for Knowledge Graphs* (2026 preprint) | context-dependent KG semantics 아이디어만 탐색 |

정확한 URL·저자·publication status와 KG UID는
[`HSWM_SHEAF_ONTOLOGY.v1.json`](HSWM_SHEAF_ONTOLOGY.v1.json)에 있다.
