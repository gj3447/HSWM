# SWM-0W-S2S — recipient-specific set-to-set semantic transport gate

> **상태:** `SECONDARY_AI_PROPOSED`
> **과학적 상태:** `UNJUDGED`
> **기준일:** 2026-08-20
> **권위 경계:** canonical set-to-set `W` 방향은 `USER_PRIMARY`; 이 target family,
> operator, control, threshold와 판정 규칙은 비준 전 `SECONDARY_AI_PROPOSED`
> **범위:** 하나의 hyperedge, 세 semantic role, role마다 정확히 두 member,
> 한 번의 비재귀 numeric sweep
> **비범위:** SWM-1 recurrent depth, LLM function cell, outcome-bound `ΔW`,
> `ΔH`, 실제 세계 효능
> **현재 구현:** [finite world](../../src/hswm/experiments/swm0w_s2s_worlds.py) ·
> [seed-varying V2 family](../../src/hswm/experiments/swm0w_s2s_family.py) ·
> [one-sweep operator](../../src/hswm/experiments/swm0w_s2s_operator.py) ·
> [deterministic training](../../src/hswm/experiments/swm0w_s2s_training.py) ·
> [world tests](../../tests/test_hswm_swm0w_s2s_worlds.py) ·
> [family tests](../../tests/test_hswm_swm0w_s2s_family.py) ·
> [operator tests](../../tests/test_hswm_swm0w_s2s_operator.py) ·
> [training tests](../../tests/test_hswm_swm0w_s2s_training.py), 모두 engineering-only;
> 동결 optimizer configuration·protocol·효능 판정 없음
> **상위 문서:** [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md) ·
> [token-hypergraph core](../canon/USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md) ·
> [철학층](../canon/HSWM_PHILOSOPHICAL_FOUNDATIONS_2026-08-20.md) ·
> [Occam core](HSWM_OCCAM_CORE_2026-08-20.md)

## 0. 철학적 판별선부터

현재의 [SWM-0W scalar confirmatory PASS](../../results/SWM0W_SCALAR_GATE_RESULTS_2026-08-20.md)는
세 singleton role의 learned scalar compatibility만 `SUPPORTED_NARROW`로 지지한다.
그 결과는 여러 member를 가진 relation이 각 member에게 서로 다른 다음 상태를
전달할 수 있음을 보이지 않았다.

> **하나의 role-bearing relation은 같은 set 안의 차이를 지우지 않으면서,
> relation 전체에 조건화된 서로 다른 2-vector를 각 incidence에 전달할 수 있는가?**

이는 다음 세 원리를 코드 전에 시험 가능한 의무로 내린다.

- **관계적 존재론:** 의미 단위는 여섯 payload의 flat tuple이 아니라 세 role-set을
  가진 하나의 n-ary relation이다.
- **차이 보존적 통일:** 한 edge의 통합은 모든 member에게 같은 pooled vector를
  방송하는 것이 아니다. recipient가 달라지면 message도 달라질 수 있어야 한다.
- **Occam/CCA:** scalar gate에 multiplicity와 recipient conditioning만 더한다.
  이 차이를 제거해도 결과가 유지되면 canonical set-to-set `W` 가설은 필요하지 않다.

따라서 이 gate는 **SWM-1이 아니다.** SWM-1은 여러 sweep가 필요한 locality와
recurrent depth를 시험하도록 남겨 둔다. 여기서는 immutable presweep state에서
정확히 한 번만 `V → E → V`를 계산한다.

### `H/W/A/F/Π` 대응

| 객체 | 이 gate에서의 정확한 역할 | 아직 하지 않는 것 |
|---|---|---|
| `H` | 하나의 immutable typed hyperedge와 `3 roles × 2 members`의 first-class incidence | edge 추가·삭제·학습 |
| `W` | 동일 role 안에서 equivariant하고 recipient마다 다른 2-vector를 내는 learned set-to-set operator | causal efficacy, fast/slow plasticity |
| `A` | presweep의 여섯 categorical activation과 동시에 산출되는 `6 × 2` postsweep activation | recurrent trajectory |
| `F` | centered contrast, bias-free linear encoder, Hadamard interaction, linear readout | LLM 호출 또는 token generation |
| `Π` | explicit evaluator-field exclusion, symmetry, budget, intervention, exact restore와 artifact contract | reward로 학습되는 경계 |

개념적 delta는 `3 singleton roles → one scalar`에서
`3 two-member role-sets → one 2-vector per recipient incidence`로 가는 것뿐이다.

## 1. 유한 세계와 명시적 split 경계

role 집합은 `R={0,1,2}`이고 각 role의 incidence 집합은
`I_r={i_(r,0),i_(r,1)}`이다. 각 incidence 값은 `a_i ∈ Z_5`이며 한 world는
`x ∈ Z_5^6`이다. 한 world의 여섯 recipient와 두 channel, 즉 **12개 scalar
output은 항상 같은 split과 같은 minibatch unit**으로 이동한다. output을 펼쳐
서로 다른 split이나 batch로 보내면 protocol violation이다.

integrity fixture v1은 syndrome `s(x)=Σ_i a_i mod 5`의 residue `{0,1}`을
train, `{2}`를 dev, `{3,4}`를 test에 고정 배정한다. 따라서
world 수는 각각 `6,250 / 3,125 / 6,250`이고 full six-coordinate world는 겹치지
않는다. raw split 크기는 `2:1:2`이지만, 각 split 안의 **정규화된** 모든
`1..5`차 coordinate marginal은 정확히 uniform이고 split 사이에 동일하다.
이는 integer histogram으로 전수 감사한다.

fixture v1에서 external seed는 manifest identity만 바꾸며 factor family와 split
support는 바꾸지 않는다. 따라서 v1 seed를 여러 task처럼 세는 것은 금지한다. 별도의
V2 family는 이 역사적 fixture를 변경하지 않고, seed와 draw index로 rank gain과
held-out split law를 domain-separated하게 생성한다. V2의 syndrome은
`s_q(x)=Σ_r q_r(a_(r,0)+a_(r,1)) mod 5`, `q=(1,q1,q2)`,
`q1,q2∈{1,2,3,4}`이고, 30개의 labeled `2/1/2` residue allocation 중 하나를
사용한다. 이로써 정확히 480개의 서로 다른 split law가 생기며 어느 law에서도
`1..5`차 normalized marginal은 동일하다.

V2 draw는 한 고정 feature frame 위의 **indexed pseudorandom sampling with
replacement**다. 구조적으로 같은 target이나 task가 다시 나오면 버리거나 재추첨하지
않고 draw index와 함께 기록한다. 서로 다른 coefficient/split law이지 서로 독립인
mechanism 또는 임의 relabeling 아래 non-isomorphic family라는 주장은 하지 않는다.

모든 arm의 고정 입력 basis는 centered contrast
`χ_q(a)=1[a=q]−1[a=4] (q=0,1,2,3)`다. `χ: Z_5 → R^4`는 injective이고, 어떤 centered lookup
`f(a)`도 `f(a)=λ^Tχ(a)`로 표현한다. syndrome, split residue, task coefficient,
world UID와 target 공식은 **명시적 evaluator field**로 model input에 넣지 않는다.
다만 여섯 raw value를 함께 보면 `Σ_i a_i mod 5`와 split membership은 계산 가능하다.
이는 secrecy가 아니라 의도된 six-way distribution shift이며 receipt에 그대로 밝힌다.

## 2. target은 set-factorized rank이며 six-way CP가 아니다

이 gate의 target rank는 **`K=2`로 고정**한다. `p=2` output channel이므로
`pK=4 ≤ h`여야 하고 T16의 `h=16`은 이를 만족한다.

recipient `i ∈ I_r`, 같은 role의 유일한 co-member를 `\bar i`라 하자. 각 hidden
factor는 `(c,k)`로만 색인한다. integrity fixture v1의 target은 다음과 같다.

```math
y_{i,c}=
\sum_{k=0}^{1}
P_{rck}(a_i)T_{rck}(a_{\bar i})
\prod_{s\ne r}
\left(\sum_{j\in I_s}T_{sck}(a_j)\right),
\qquad c\in\{0,1\}.
```

target을 future score로 선별하지 않기 위해 factor frame 자체를 고정한다.

```text
h0 = (-2, -1,  0,  1,  2)
h1 = ( 0,  3, -4, -1,  2)
h2 = ( 7, -7, -6,  5,  1)
h3 = ( 3, -3,  2, -7,  5)
```

네 row는 centered이고 Gram diagonal이 `(10,30,160,96)`인 exact orthogonal frame이다.
`o=(r+c) mod 4`에 대해 `T_rck=h_(o+k)`, `P_rck=h_(o+k+2)`로 둔다(index mod 4).
고정 family의 analytic numerator bound는 `19,208 < 2^15`, 실제 전수 최대는 `5,560`이므로
target scale은 outcome을 보지 않고 `2^-15`로 고정한다. external seed는 현재
**task identity만 결속**하며 factor나 split을 바꾸지 않는다.

V2는 같은 `P/T` frame을 유지하면서 각 rank 항에 `g_(r,c,k)`를 곱한다.
`g_(0,0,0)=8`을 고정하고 나머지 11개 gain은 각각 `{8,...,15}`에서 뽑으므로
구조 target 공간은 `8^11=2^33`이다. scale은 `2^-19`이고 outcome과 무관한
느슨한 정수 numerator bound는 `15×19,208=288,120<2^19`다. 과제의
constructive T16 witness는 이 gain을
`Q_r[c,2c+k]=g_(r,c,k)2^-19`에만 결속한다. seed commitment, draw index,
split, manifest는 operator state에 넣지 않는다. 같은 구조 target은 같은 operator를
가져야 하기 때문이다.

곱을 전개한 각 항은 recipient, co-member, 다른 두 role에서 하나씩 고른 member,
즉 **네 coordinate**에만 의존한다. 이것은 role-set을 factorize한 rank `K` target이지
여섯 incidence를 모두 곱한 six-way synergy나 일반 CP-rank 주장으로 읽지 않는다.

`1..5`차 marginal uniformity와 factor centering 때문에 각 role/channel/split에서
target mean은 정확히 `0`이고, target은 아래 recipient-star pair span과 정확히
직교한다. 이 직교성은 **unrestricted pair-additive span에는 주장하지 않는다.**
두 non-recipient coordinate만 잇는 임의 pair까지 넓히면 보장은 깨진다.

## 3. T16 한 번의 set-to-set sweep

`R=3`, input dimension `d=4`, hidden width `h=16`, output width `p=2`로 둔다.
각 role의 두 member는 같은 encoder를 공유한다. encoder에는 bias가 없다.

```math
u_i=\phi_r\!\left(\chi(a_i)\right),
\qquad
v_s^{(-i)}=
\sum_{j\in I_s,\;j\ne i\;\mathrm{if}\;s=r}
\psi_s\!\left(\chi(a_j)\right),
```

```math
\widehat y_i=b_r+U_ru_i
+\sum_{s=0}^{2}P_{rs}\!\left(u_i\odot v_s^{(-i)}\right)
+Q_r\!\left[
u_i\odot v_r^{(-i)}\odot\prod_{s\ne r}v_s
\right].
```

여기서 모든 곱은 hidden-coordinate별 Hadamard product다. 모든 `u`와 `v`는
동일한 immutable presweep snapshot에서 계산한다. 한 recipient의 새 output을
다른 recipient 계산에 읽히게 하는 순차 update는 금지한다.

trainable block과 exact parameter census는 다음과 같다.

| block | shape/count at `h=16` |
|---|---:|
| bias-free `φ_r,ψ_r: R^4→R^h` | `2R·4h = 384` |
| `U_r,Q_r ∈ R^(p×h)` | `2Rph = 192` |
| recipient-star `P_rs ∈ R^(p×h)` | `R²ph = 288` |
| `b_r ∈ R^p` | `Rp = 6` |
| **T16 total** | **`870`** |

### 동일 role 안의 대칭

group은 세 role 안에서 두 member를 독립적으로 바꾸는
`G=S_2^3`이다. output도 대응하는 physical recipient와 함께 움직여야 한다:
`W(gx)=gW(x)` for every `g∈S_2^3`. role 자체의 교환은 symmetry가 아니다.

## 4. 최소 세 train arm

confirmatory protocol에는 다음 세 arm만 둔다.

1. **T16:** 위의 full operator, 정확히 `870` parameters.
2. **P_CAP18:** `Q_r` block을 완전히 제거한 recipient-star-only control.
   `h=18`에서
   `2R·4h + Rph + R²ph + Rp = 48h+6 = 870`이다. 이 arm은 unrestricted
   pair model이 아니며 그런 모델에 대한 직교성도 주장하지 않는다.
3. **DS870:** role마다 tied member encoder와 sum aggregation을 쓰고,
   recipient feature와 세 role summary를 하나의 shared decoder에 주는
   information-complete `S_2^3`-equivariant control. `x=χ(a)`에 대해

```math
\eta_s(x)=[x;\tanh(xE_s+d_s)]\in\mathbb R^8,
\qquad z_s=\sum_{j\in I_s}\eta_s(x_j).
```

fixed `x` 절반이 `Z_5`의 two-member multiset을 lossless하게 보존하고 learned 절반도
decoder에 연결된다. role code는 고정
`κ_0=(1,0), κ_1=(0,1), κ_2=(-1,-1)`이고 recipient decoder input은
`[x_i;z_0;z_1;z_2;κ_r]∈R^30`이다. 모든 role/member가 같은
`30→14→22→2` tanh MLP를 사용한다.

| DS870 block | parameters |
|---|---:|
| `E_s∈R^(4×4), d_s∈R^4`, three roles | `60` |
| shared `30→14` affine | `434` |
| shared `14→22` affine | `330` |
| shared `22→2` affine | `46` |
| **total** | **`870`** |

이는 input representation이 information-complete라는 뜻이지 finite `14/22` decoder의
universal approximation 주장이 아니다. 모든 parameter가 forward path에 연결된다.
DS870은 T16보다 MAC/tanh 비용이 더 크므로 exact parameter와 update budget은 맞지만
equal-compute control은 아니다. 그 차이를 receipt에 기록하고 `C`는 보수적인
matched-parameter 비교로만 읽는다.

### 구현된 학습 경로의 경계

세 arm은 별도 training module에서 complete train `6,250` worlds와 dev `3,125`
worlds만 받는다. 입력 순서는 lexicographic raw-value order로 정규화하고, world의
12개 output은 한 full-batch unit에 남는다. test case는 fit API가 받지 않는다.

role/channel별 train target population variance를 `V_(r,c)`라 할 때 목적함수는

```math
L=\frac{1}{6}\sum_{r,c}\frac{\operatorname{MSE}_{r,c}}{V_{r,c}}.
```

`V_(r,c)`는 integer target numerator의 exact sum과 sum-of-squares에서 계산하며,
dev checkpoint 선택에도 같은 train-derived weight만 쓴다. 초기화는 task와 무관하다.
T16/P_CAP18의 `phi/psi`, DS870의 internal feature tensors만 seeded Xavier로 시작하고
모든 output head와 output bias는 exact positive zero다. 학습은 float64 full-batch
Adam, global norm clipping, epoch-0 eligibility, strict `min_delta`, earliest tie와
exact best-state restore를 구현한다.

`fitted`는 optimizer artifact가 만들어졌다는 뜻이고, `learned`는 선택된 best update가
0보다 크며 parameter bytes가 initializer와 다를 때만 참이다. receipt는 complete
train/dev hashes, exact loss, architecture, typed full history와 best state를 묶지만
self-hash 자체는 실행 provenance가 아니다. 별도 deterministic replay가 같은 task와
configuration에서 history·receipt·모든 parameter byte를 다시 만들어야 증거 계층이
이를 받아들일 수 있다. 현재 configuration은 protocol로 동결되지 않았고 이 경로를
통과한 admissible efficacy artifact도 없다.

## 5. frozen T16에 대한 세 intervention

학습을 다시 하지 않고 같은 frozen checkpoint에 다음을 적용한다.

- **remove `Q`:** 모든 `Q_r`를 exact zero로 바꾸고 평가한 뒤 원래 bytes를 복원한다.
- **within-role broadcast:** 각 semantic role의 두 prediction만 평균내어 그 role의
  두 member에 방송한다. role conditioning은 보존하고 recipient 차이만 제거한다.
- **both role cycles:** `(0 1 2)`와 `(0 2 1)`로 physical incidence의 role label/input
  slot을 바꾸되 label-indexed model parameter는 고정한다. 그 뒤 `g^{-1}`로 output을
  원래 physical recipient에 되돌려 평가한다. 두 cycle을 모두 통과해야 한다.

`Q` restore 뒤 model-state bytes, prediction bytes와 score receipt는 원본과 같아야 한다.

## 6. deterministic integrity gates

다음 중 하나라도 깨지면 성능과 무관하게 run은 `VOID`다.

1. `Z_5^6` 전수 domain, split cardinality, full-world disjointness와 모든
   `1..5`차 normalized marginal의 exact integer audit.
2. world의 12 output이 같은 split/batch unit에 남고 UID, syndrome, coefficient와
   target이 explicit feature에 없다는 schema audit. joint raw input에서 syndrome을
   계산할 수 있다는 의도된 경계도 receipt에 명시한다.
3. 모든 task/split/role/channel target의 exact zero mean, strictly positive variance,
   rank/coefficients/scale digest. task를 test statistic으로 rescale하거나 고르지 않는다.
4. target과 세 arm의 모든 `g∈S_2^3` equivariance. target은 exact arithmetic,
   float model은 사전 결속된 tolerance로 전수 검사한다.
5. target과 **recipient-star-only** constant/unary/pair span의 exact inner product `0`.
6. exact recipient-star projection과 P_CAP18의 test `R² ≤ ε`.
7. frozen T16에서 `Q`를 뺀 모든 role/channel의 test `R² ≤ ε`.
8. T16/P_CAP18/DeepSets의 exact parameter census와 T16 `Q`의 byte-exact restore.

`ε`와 float reduction order는 구현 오차분석으로 정하고 confirmatory target을 보기
전에 preregistration에 동결한다. pair 또는 `T16−Q`가 `ε`를 넘으면 target이 Q를
격리했다는 전제가 무너진 것이므로 negative efficacy가 아니라 `VOID`다.

## 7. statistic과 제안 threshold

task `t`, role `r`, channel `c`별 test `R²_(t,r,c)`를 계산한다. role/channel을
global score로 숨기지 않고 primary task statistic은 여섯 stratum 중 최악이다.

```math
Q_t=\min_{r,c}R^2_{t,r,c}(T16).
```

broadcast와 role-cycle damage도 task 안에서 최악의 stratum/cycle을 취한다.

```math
B_t=\min_{r,c}\left[R^2_{t,r,c}(T16)-R^2_{t,r,c}(within\text{-}role\ broadcast)\right],
```

```math
R_t=\min_{g\in\{(012),(021)\}}\min_{r,c}
\left[R^2_{t,r,c}(T16)-R^2_{t,r,c}(g^{-1}T16(gx))\right].
```

world나 12개 output을 독립 표본으로 bootstrap하지 않는다. **task만** 복원추출하고,
모든 metric에 같은 bootstrap index를 사용한다. 제안 essential threshold는 task mean의
one-sided 95% lower bound에 대해 다음과 같다.

| claim | proposed gate |
|---|---:|
| worst role/channel predictive transport | `LCB(mean Q_t) ≥ 0.80` |
| member-specificity beyond within-role broadcast | `LCB(mean B_t) ≥ 0.10` |
| semantic-role dependence, both cycles | `LCB(mean R_t) ≥ 0.10` |

DeepSets 차이 `C_t=Q_t(T16)−Q_t(DeepSets)`에서
`LCB(mean C_t) ≥ -0.02`일 때만 **“matched-budget compact competitive”**라는
선택적 문구를 허용한다. 이는 essential PASS gate가 아니며 T16의 보편적 우월성,
novelty 또는 architecture-independence를 허용하지 않는다.

V2 family의 exact universal floor는 모든 허용 gain/split/role/channel에서
within-role broadcast damage가 최소
`2027528/4509001 ≈ 0.449662`이다. 두 role cycle의 최소도 각각
`420960389/416884981 ≈ 1.009776`,
`17109007/16617375 ≈ 1.029585`다. 4,320개의 관련 정수 행렬에 대해
`5N−4D ≻ 0`을 exact Sylvester/Bareiss 검사하여 더 보수적인
`broadcast>2/5`, `cycle>4/5`를 증명한다. 따라서 제안된 `B,R ≥ 0.10`은
target construction 자체가 불가능하게 만드는 threshold가 아니다.

V2 family, task-bound constructive witness와 deterministic train/dev optimizer는 이제
**engineering implemented**다. 남은 `PRE_FREEZE_BLOCKER`는 disclosed timing/convergence
pilot로 정할 arm별 learning rate와 공통 update·patience·시간 budget,
conditional task-bootstrap rule, future-public seed 결속과
candidate-only→adjudication protocol이다. V2 draw들은 한 고정 feature frame에서 나온
coefficient/split law이므로 bootstrap 해석도 이 명시된 generator에 조건부이며,
독립 mechanism 표본으로 승격하지 않는다.

## 8. pilot, freeze, confirmatory 순서

confirmatory seed를 열기 전에 별도 disclosed pilot에서 integrity와 wall-time을 잰다.
특히 세 arm의 task당 update time, peak memory와 workflow p95를 먼저 측정한 뒤에만
현실적인 max updates와 timeout을 동결한다. timing pilot의 test score로 task 수,
target scale, acceptance threshold나 task acceptance를 정하면 안 된다.

그 다음 하나의 preregistration에 다음을 모두 고정한다.

- V2 with-replacement task generator, task 수와 duplicate 처리, 고정 `K=2`,
  coefficient/split/scale generator, conditional bootstrap 단위, analytic
  member-specificity floor와 future-public randomness binding;
- 세 arm의 exact architecture, initialization, optimizer, learning rate, world-batch size,
  loss, gradient clipping, max updates와 dev-only early-stop/tie-break;
- `ε`, summation order, checkpoint selection, parameter/FLOP/update receipts;
- bootstrap resample 수·seed·interval, shared indices, 모든 threshold와 reducer;
- remove/broadcast/cycle/restore 순서, artifact schema, workflow image와 timeout.

confirmatory task를 일부 본 뒤 task 수나 update budget을 연장하지 않는다. 변경이
필요하면 기존 run을 닫고 새 preregistration과 새 future randomness로 시작한다.

## 9. 판정 경계

- **PASS / `SUPPORTED_NARROW`:** 모든 integrity gate가 유효하고 세 essential LCB가
  모두 threshold 이상이다. 허용 문장은 이 고정 synthetic family에서 한-sweep
  recipient-specific set-to-set transport가 매개됐다는 것뿐이다.
- **KILL / negative:** protocol은 유효하지만 essential metric 하나 이상의 95% upper
  bound가 threshold보다 낮다. canonical S2S bridge를 더 큰 graph로 덮지 말고
  operator 또는 target 가정을 축소한다. SWM-1을 열지 않는다.
- **INCONCLUSIVE:** 완전하고 유효한 사전등록·task·adjudication bundle에서 LCB는
  PASS에 못 미치지만 UCB가 threshold를 가로지른다. PASS로 올리지 않고 optional
  continuation도 하지 않는다.
- **VOID / no admissible evidence:** bundle이 불완전하거나 split, leakage, symmetry,
  orthogonality, parameter, restore, freeze 계약이 깨졌다. efficacy 해석을 금지하고
  수정된 protocol을 새로 preregister한다.

## 10. 명시적 비주장과 다음 문

이 gate는 deep neural HSWM, recurrent reasoning, LLM token cognition, semantic truth,
outcome-bound causal learning, operator durability, topology morphogenesis, real-world
utility, federation, 의식 또는 인류보편체를 증명하지 않는다. 하나의 synthetic
hyperedge와 categorical finite domain 밖으로 일반화하지 않는다.

PASS가 나더라도 다음에 열리는 것은 **SWM-1 설계**뿐이다. 그때 처음으로 같은
operator를 weight-tied multiple sweep로 반복하고, one-sweep로 풀 수 없는 locality
task에서 depth의 counterfactual necessity를 시험한다.

> **SWM-0W-S2S의 전부: set을 보존하고, recipient를 보존하고, 둘 중 하나를
> 지웠을 때 예측 가능한 차이가 사라지는지 확인한다.**
