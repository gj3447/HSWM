# B2.2 — query × semantic-bond weighting

> Status: engineering design plus exploratory headroom diagnosis; no new
> confirmatory efficacy claim.

## 결론

B2.1 이후 해야 할 일은 router의 abstention threshold를 낮추는 것이 아니다.
`A / B / MERGED`라는 큰 map 단위 선택을 버리고, **query가 현재 읽는 각 semantic bond의
상대 weight를 조절**해야 한다.

다만 두 종류의 weight를 섞으면 안 된다.

```text
slow:  ell(b)       이미 존재하는 bond의 durable salience
fast:  a_theta(q,b) 현재 query와 bond 사이의 volatile attention
```

B2의 간섭은 query마다 달라지므로 첫 학습 대상은 `a_theta(q,b)`다. 반복된 독립 결과가
누적되어 query와 무관한 효과가 확인될 때만 그것을 slow `Delta ell(b)` 후보로 증류한다.

## 권위와 해석 경계

USER_PRIMARY 방향:

- HSWM map은 여러 개이며 연결·분리·전문화할 수 있어야 한다.
- 고정된 1층이 아니라 어떤 HSWM도 같은 타입으로 다시 연결되어야 한다.
- agent가 HSWM의 weight를 학습하며 semantic neural network를 완성한다.

SECONDARY_AI 설계:

- 아래의 slow/fast 분리, 수식, API, 실험 단계와 threshold는 사용자 방향을 구현하기 위한
  공학적 가설이며 별도 승인·실측 전에는 canon이나 성능 사실이 아니다.

## 현재 빠진 실제 연결

`OpenHSWM`은 모든 atomic edge에 `SemanticWeight(edge_id, log_salience<=0)`를 저장하고
semantic digest에도 포함한다. 그러나 B2 readout은 현재 다음 값만 사용한다.

```text
S_B2(e,q) = edge_cosine
          + 0.10 * vertex_channel
          + 0.30 * seam_bridge
```

즉 manifest의 semantic weight는 지금까지 B2 점수에 들어가지 않았다. 따라서 learner보다
먼저 결정론적 weight-to-readout binding이 필요하다.

새 pure module `hswm_bond_readout.py`는 다음 좁은 계약만 소유한다.

```text
S(e|q) = S_base(e|q) + lambda_s * ell(e) + lambda_q * a_theta(q,e)

ell(e) <= 0
a_theta(q,e) = raw_logit(q,e) - max_e raw_logit(q,e) <= 0
```

logit에서 최대값을 빼는 것은 모든 bond에 같은 상수를 빼므로 ordering information을 잃지
않는다. 동시에 fast/slow weight가 같은 max-zero relative-potential domain을 사용한다.

이 모듈은 학습·저장·승격·판정을 소유하지 않는다. 그것들은 기존
`hswm_plasticity_loop.v1.json`이 소유한다. 따라서 새 엔진을 만들지 않고 pure module로
남긴다.

## 왜 slow `ell`부터 단독 학습하지 않는가

현재 neutral slow weight는 모두 `0`이며 canonical domain은 `ell<=0`이다. 따라서 첫
candidate가 할 수 있는 것은 edge suppression뿐이다. 더 중요한 문제는 slow `ell(e)`가
query-independent라는 점이다.

같은 paragraph가 어떤 query에서는 정답 근거이고 다른 query에서는 distractor일 수 있다.
그때 “train query에서 non-gold였다”는 이유로 paragraph 자체의 durable salience를 낮추면
relevance와 truth/provenance를 혼동한다. B2.1 test에서도 train top-20과 test top-20 edge가
많이 겹치므로 이 오류는 실제 retention 손해로 이어질 수 있다.

따라서 순서는 다음이어야 한다.

1. fast `a_theta(q,e)`가 query-dependent interference를 통제할 수 있는지 시험한다.
2. eligibility와 외부 outcome이 여러 query에서 같은 방향으로 반복된 bond만 slow
   `Delta ell(e)` 후보로 만든다.
3. slow candidate는 fresh retention/no-harm/replay를 통과해야만 CAS activate한다.

이 선택을 하기 전에 slow-first 반대안도 development로 직접 확인했다. train에서 최소 3개
독립 component에 non-gold로 등장하고 train gold는 아닌 edge만 대상으로, 최대 32개의
`log(.9)/log(.7)/log(.5)` attenuation을 greedy하게 골랐다. 결과는 다음과 같다.

| Dataset | Seeds | Train delta 범위 | Calibration delta | Test delta |
|---|---:|---:|---:|---:|
| 2Wiki | 3 | `0` ~ `+0.001678` | 3/3 `0.0` | 3/3 `0.0` |
| MuSiQue | 3 | `+0.006364` ~ `+0.006653` | 3/3 `0.0` | 3/3 `0.0` |

이것은 preregistered rejection이 아니라 한 edge-identity learner의 진단이다. 모든 slow
salience 학습을 죽이지는 않지만, 이 static patch를 큰 confirmatory 실험으로 승격할 근거는
없다. 반대로 query-conditioned action-space oracle에는 양 데이터 모두 충분한 room이 있다.

## 행동공간 상한 진단

B2.1의 gold oracle은 `A/B/MERGED` 중 하나만 고를 수 있었고 primary minimum headroom이
`+0.010870`이라 등록 목표 `>+0.02`가 불가능했다.

동일한 frozen MERGED top-20 안에서 edge 순서만 gold oracle로 다시 배열하면:

| Dataset | MERGED recall@10 | top-20 rerank oracle | Headroom | rank 11–20에 gold가 있던 query |
|---|---:|---:|---:|---:|
| 2Wiki primary development | `0.758152` | `0.807065` | `+0.048913` | 11 / 92 |
| MuSiQue primary development | `0.673810` | `0.757143` | `+0.083333` | 29 / 140 |

따라서 fine bond action space에는 양쪽 모두 `+0.02`보다 큰 room이 있다. 이것은 **가능성의
상한**일 뿐 observable feature를 가진 learner가 room을 회수한다는 증거가 아니다. 또한 이
cohort들은 B2.1에서 이미 열렸으므로 B2.2에서는 development 전용이다.

## 구현 단계

### B2.2a — neutral binding

1. `hswm_bond_readout.py`의 pure formula와 fail-closed coverage를 고정한다.
2. 모든 weight가 neutral일 때 frozen B2의 full ranking과 score를 `1e-9` 이내로 재현한다.
3. weight 변화가 embedding, incidence, seam, provenance, topology를 바꾸지 않음을 검사한다.

### B2.2b — full score-component pack

기존 B2.1 scorepack은 3,452/8,893개 edge 중 query별 top-20 최종 점수만 저장한다. 억제된
top edge 아래에서 21위 밖 edge가 올라올 수 있으므로 exact semantic-weight 실험에는
부족하다. Dell에서 frozen embedding을 한 번만 재사용해 다음을 저장한다.

```text
edge_ids, field_labels, query digests
full edge cosine matrix
full vertex-channel matrix
full merged/no-seam bridge matrix
full base score matrix
producer/input/model hashes
```

그 뒤 learner sweep은 embedding 없이 `base + weight`와 stable sort만 수행한다.

### B2.2c — fast bond learner

첫 learner는 작고 대칭이어야 한다.

```text
theta: shared low-capacity query-edge scorer
input: query features + edge score components + provenance/structural features
output: raw logits for the fixed candidate set
compile: subtract max -> a_theta(q,e)<=0
readout: S_base + lambda_q*a_theta
```

ML17에서는 generic semantic EDGE weighting이 recall을 `-0.0308`
(CI `[-0.0553,-0.0047]`) 해쳤다. 따라서 B2.2의 fast potential은 incidence나 seam bridge
생성을 바꾸지 않고 **완성된 frozen B2 score 뒤에만** 더한다. Calibration grid에는 반드시
`lambda_q=0`을 넣어 signal이 없으면 frozen MERGED로 정확히 돌아가게 한다.

금지 feature:

- query ID, edge ID embedding, test gold, hop label;
- answer 문자열 또는 private entity surface에만 의존하는 shortcut;
- learner가 만든 confidence를 learner 자신이 promotion verdict로 사용하는 것.

controls:

1. frozen MERGED;
2. rejected B2.1 whole-map router;
3. shuffled-target capacity match;
4. score-only linear model;
5. private-entity surface;
6. top-20 gold oracle diagnostic only.

### B2.2d — slow distillation

fast attention의 방향이 여러 component와 outcome window에서 반복된 bond만
`SparseSemanticDeltaV1`로 제안한다. sparse patch는 canonical state가 아니므로 compiler가
모든 edge를 덮는 dense `SemanticWeight[]` snapshot으로 바꾸고 새 semantic digest를 만든다.
P6의 immutable candidate, replay, retention, canary, approval, CAS 규율을 그대로 재사용한다.

## 실험 판정

기존 2Wiki/MuSiQue cohort는 development에만 쓴다. model, feature schema, lambda, sparsity,
abstention/no-change 규칙을 거기서 한 번 동결한 뒤, 아직 열지 않은 fresh PhantomWiki
universe를 크기 × friendship-k × hop으로 층화해 confirm한다.

confirmatory 최소 gate:

- fresh overall recall@10 delta의 component-bootstrap 95% lower bound `>0`;
- dataset/regime minimum delta `>+0.02`;
- cross-field B2 gain retention `>=-0.02`;
- in-field/no-bridge retention `>=-0.02`;
- shuffled learner joint pass `0`;
- private-entity 및 answer-surface control 통과;
- equal candidate/scorer budget;
- neutral exact replay와 candidate hash replay 통과.

kill conditions:

1. top-20 oracle room은 있지만 learned fast weight가 두 개발 데이터에서 positive CI를 만들지
   못한다 — observable bond features가 부족하다.
2. private surface를 없애면 이득이 사라진다 — semantic shortcut이다.
3. fast는 통과하지만 slow distillation이 retention을 해친다 — durable `ell`로 만들지 말고
   query attention으로만 유지한다.
4. full score pack에서 oracle room이 사라진다 — top-20 진단 artifact다.
5. flat/vector reranker가 equal compute에서 같거나 낫다 — HSWM-specific 구조 주장을 접는다.

## CONNECT / SEPARATE / SPECIALIZE로 이어지는 법

고정된 “1층”은 필요 없다. readout의 정의역을 bond 전체로 둔다.

```text
B = atomic hyperedges union HSWM connectors
```

현재 slice는 atomic hyperedge만 지원한다. 이후 connector도 동일한 weight/readout 계약을
소비하게 만들면:

- `CONNECT_soft`: connector attention/salience 증가;
- `SEPARATE_soft`: connector attention/salience 억제;
- `SPECIALIZE_soft`: 특정 sub-HSWM bond coalition의 반복 선택;
- structural verb: 검증된 반복 패턴만 typed topology edit로 compile.

즉 Transformer처럼 query-conditioned attention이 먼저 흐르고, agent가 검증된 반복 패턴만
durable weight와 topology로 결정화한다. **attention은 사용, slow weight는 기억, topology는
구조**라는 세 역할을 분리하는 것이 현재 가장 작고 우아한 HSWM 경로다.
