# HSWM token-hypergraph Semantic Weight Map 선행연구 감사

> **상태:** `SECONDARY_AI_RESEARCH / PRIMARY_SOURCE_REVIEW`
> **기준일:** 2026-08-20
> **검색 범위:** hypergraph neural operators, role-aware n-ary representation,
> dynamic/temporal topology, external and test-time memory, LLM function graphs,
> LLM–hypergraph alignment, persistent cognitive metagraphs, 공식 구현 라이브러리
> **소스 규율:** 논문, 학회 게재본, 공식 문서·저장소만 비교했다.
> **관계:**
> [`USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md`](../canon/USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md)의
> 선행성·구현 선택·gap 판별을 담당한다.

## 0. 판정

**부품은 이미 많이 개발됐다. 넓게 정의한 “LLM + weighted hypergraph”는 새로운
주장이 아니다.** 특히 2026년 7월 Hyperon deep-dive는 weighted hyper/metagraph,
attention economics, LLM–AtomSpace read/write, token-position provenance, predictive-coding
학습, candidate validation·permission·promotion·rollback과 공유/individual AtomSpace까지
제안한다.

반면 검토한 소스 안에서 다음 **전체 인과 폐루프를 하나의 영속적
공개 시스템으로 구현·실증한 사례는 확인하지 못했다.**

```text
LLM token event
  → sparse role-aware n-ary hypergraph activation
  → typed LLM function cell
  → token/action outcome
  → pre-outcome trace에 대한 causal credit
  → versioned ΔW / ΔH commit
  → provenance를 보존한 다음 token 처리 변화
```

이는 **조사 범위 내 gap inference**다. 세계적 부재, 선취권, 절대 novelty를
주장하지 않는다. Hyperon 때문에 HSWM은 개념 유사성이 아니라 직접 구현,
matched-budget 비교, causal ablation, scale/stability로 자신을 증명해야 한다.

## 1. 가장 강한 직접 선행: OpenCog / Hyperon

| 시스템 | 이미 있는 것 | HSWM에 남은 문제 |
|---|---|---|
| [OpenCog AtomSpace](https://github.com/opencog/atomspace) | immutable, globally unique typed Atom에 mutable Value를 붙이는 generalized hyper/metagraph; query·program·rewrite rule을 그래프로 보존·실행; frame/change-set과 분기·rollback | 강한 persistent metagraph kernel이지만 HSWM의 token→LLM cell→external outcome→macro-W/H mediation 실증은 아님 |
| [ECAN](https://wiki.opencog.org/w/OpenCogPrime%3AEconomicAttentionAllocation) | Atom의 STI/LTI, attentional focus, HebbianLink 확산, resource allocation | 기존 ECAN은 공식 문서상 fossil/unmaintained; every-Atom micromanagement의 memory/compute 문제가 보고됨 |
| [MeTTa reflective metagraph rewriting](https://arxiv.org/abs/2112.08272) | 타입, 변수, pattern matching, program과 rewrite rule 자체를 metagraph로 표현하는 자기기술 구조 | 외부 outcome이 n-ary semantic macro-synapse를 학습시키는 계약은 별개 |
| [Hyperon Deep-Dive 2026](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf) | LLM을 external/bridge/native route로 통합; transformer token-position hidden state에서 AtomSpace read; neural state의 typed graph candidate write; source-token provenance, validation/promotion/permission; predictive-coding local learning; evaluator-minted attention fuel; individual/shared AtomSpace; rollback | HSWM의 가장 강한 competitor/conceptual prior. 문서의 상당 부분은 연구 program/hypothesis이므로 통합 구현·효능을 별도로 확인해야 함 |

백서의 page-level claim audit, 공식 공개 코드 범위, HSWM `H/W/A/F/Π` 대응과
직접 비교 실험은
[`HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md`](./HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)에
분리했다.

### 1.1 반드시 피할 token 용어 충돌

Hyperon의 `TECAN token`은 LLM subword token이 아니라 cognitive operation을 지급하는
자원/연산권 화폐다. HSWM의 token은 현재 LLM이 읽고 발생시키는 activation/
experience carrier다. 구현에서는 다음처럼 명칭을 분리해야 한다.

```text
LLMTokenEvent / TokenActivation     # 의미·활성 신호
ComputeCredit / AttentionBudget    # 연산 자원·권한
```

## 2. hypergraph neural operator 계통

| 1차 소스 | 핵심 메커니즘 | HSWM에 수입할 것 | 직접 쓸 수 없는 것 |
|---|---|---|---|
| [RAM](https://arxiv.org/abs/2104.09780), [code](https://github.com/liuyuaa/RAM) | n-ary fact를 role–entity map으로 두고 shared role basis + multilinear compatibility를 학습 | role-aware relation core `Θ_r` | KB completion decoder; message passing·계보·token activation이 없음 |
| [Hyper-SAGNN](https://arxiv.org/abs/1911.02613), [code](https://github.com/ma-compbio/Hyper-SAGNN) | variable-size homogeneous/heterogeneous hyperedge의 self-attention score와 outsider identification | query-conditioned heterogeneous member interaction | 일회성 tuple score이며 durable field가 아님 |
| [HNHN](https://arxiv.org/abs/2006.12278), [code](https://github.com/twistedcubic/HNHN) | node와 hyperedge 모두 neuron/state로 두고 `V→E→V` 비선형 update; degree/cardinality normalization | hyperedge를 first-class active state로 두는 근거 | unordered static incidence, offline task learning |
| [UniGNN](https://arxiv.org/abs/2105.00956), [code](https://github.com/OneForward/UniGNN) | `node multiset→edge`, `edge multiset→node` 두 단계로 GCN/GAT/GIN/SAGE를 hypergraph화 | 단순한 sparse baseline과 deep residual | role, time, provenance, online persistent update가 없음 |
| [AllSet](https://arxiv.org/abs/2106.13264), [code](https://github.com/jianhao2016/AllSet) | `V→E`와 `E→V`를 학습 가능한 multiset function으로 두고 Deep Sets/Set Transformer로 구현 | SWM-1의 가장 강한 기본 aggregator 후보 | role을 직접 표현하지 않으며 persistent cognition이 아님 |
| [ED-HNN](https://arxiv.org/abs/2207.06680), [code](https://github.com/Graph-COM/ED-HNN) | 각 member에 다른 message를 주는 continuous permutation-equivariant hypergraph diffusion; star expansion으로 효율 구현 | member-specific `E→V`, heterophily/depth 대응 | 모델 레이어 파라미터이지 시간에 걸친 durable edge memory가 아님 |
| [Sheaf Hypergraph Networks](https://proceedings.neurips.cc/paper_files/paper/2023/hash/27f243af2887d7f248f518d9b967a882-Abstract-Conference.html), [code](https://github.com/IuliaDuta/sheaf_HNN) | node/hyperedge local vector space와 incidence별 learned projection | role-conditioned transport `R_{r,ρ}`의 직접 근접 선행 | node classification용; semantic role 계약·출처·계보는 추가 필요 |
| [Heterogeneous Graph Transformer](https://arxiv.org/abs/2003.01332) | node/edge type-dependent attention·message parameter와 relative temporal encoding; web-scale sampling | type/relation-specific parameter sharing, heterogeneous mini-batch | pairwise graph이며 native n-ary relation이 아님 |

### 2.1 topology가 학습되는 선행

| 1차 소스 | 메커니즘 | HSWM gap |
|---|---|---|
| [Dynamic HGNN](https://www.ijcai.org/proceedings/2019/366), [code](https://github.com/iMoonLab/DHGNN) | 레이어의 현재 embedding으로 local kNN/global cluster hyperedge를 다시 생성 | 이전 topology를 폐기하므로 immutable history/supersession과 충돌 |
| [TDHNN](https://www.ijcai.org/proceedings/2023/275), [code](https://github.com/HHW-zhou/TDHNN) | hyperedge feature distribution에서 dynamic edge와 incidence를 sampling | 제안 근거·과거 epoch·rollback이 durable artifact가 아님 |
| [Neural Relational Inference](https://arxiv.org/abs/1802.04687) | observation으로 latent interaction graph와 dynamics를 동시 추론 | topology proposer의 선행; pairwise simulated dynamics와 HSWM 계보 사이 gap |
| [LDS](https://arxiv.org/abs/1903.11960), [IDGL](https://arxiv.org/abs/2006.13009) | downstream loss에 맞춰 adjacency와 representation을 공동 최적화 | label loss 중심; provenance, capability, multi-outcome, 비파괴 commit이 없음 |

선행연구의 `dynamic` topology는 대개 “모델 레이어마다 latent graph를 다시
계산한다”는 뜻이다. HSWM의 morphogenesis는 “제안·근거·outcome·검증·
supersession을 가진 새 topology epoch을 commit한다”는 뜻이므로 서로 다른 문제다.

## 3. token, external memory, test-time learning 계통

| 1차 소스 | 이미 증명/제안한 것 | HSWM에서 분리할 것 |
|---|---|---|
| [Transformer](https://arxiv.org/abs/1706.03762), [Modern Hopfield](https://arxiv.org/abs/2008.02217) | attention update와 modern Hopfield associative retrieval의 연결 | context 내 pairwise 순간 field ≠ persistent `H/W` |
| [Fast Weight Programmers](https://arxiv.org/abs/2102.11174) | token key/value가 fast-weight matrix를 recurrent하게 갱신 | 압축 matrix에 role-bearing n-ary 사실·출처·계보가 없음 |
| [Differentiable Neural Computer](https://www.nature.com/articles/nature20101) | controller가 external memory를 content/temporal addressing하고 구조를 조작하도록 end-to-end 학습 | finite vector slot 재사용·overwrite; typed history·black-box LLM credit이 없음 |
| [kNN-LM](https://arxiv.org/abs/1911.00172), [Memorizing Transformers](https://arxiv.org/abs/2203.08913) | 과거 token representation을 external key/value memory에 넣어 next-token distribution을 개선 | flat memory이며 relation/function/topology learning이 없음 |
| [RETRO](https://arxiv.org/abs/2112.04426) | 2 trillion token corpus의 retrieved chunk를 cross-attention에 연결하는 규모 선례 | corpus/index가 outcome에 따라 macro-synapse로 재배선되지 않음 |
| [Titans](https://arxiv.org/abs/2501.00663) | surprise gradient, momentum, decay로 test-time neural long-term memory를 갱신 | token-driven plasticity의 강한 선행이지만 MLP parameter에 출처·관계·rollback이 압축됨 |
| [ATLAS](https://arxiv.org/abs/2505.23735) | 현재·과거 token으로 high-capacity test-time memory를 최적화하고 긴 context로 확장 | sequence memory이며 persistent typed hypergraph·independent outcome credit이 아님 |
| [Temporal Graph Networks](https://arxiv.org/abs/2006.10637) | timed pairwise event stream, per-node memory, message/aggregate/update/temporal embedding | n-ary semantic event, immutable history, LLM function·outcome commit이 없음 |
| [HyperTPP/HGDHE](https://ojs.aaai.org/index.php/AAAI/article/view/25939) | temporal hyperedge event history로 다음 interaction·time을 예측 | 시간순 multi-way event의 근접 선행이지만 과거를 predictive state에 압축; evidence ledger·supersession은 없음 |

Titans의 surprise는 HSWM `θ_fast` 후보에 유용하지만 durable truth/slow-W 승격 신호로
쓰면 안 된다. 놀라운 거짓말은 surprise가 높아도 근거·진리·인과 효능이 높지
않기 때문이다.

## 4. LLM function graph·hypergraph alignment·graph memory 계통

| 1차 소스 | 핵심 | HSWM gap |
|---|---|---|
| [GPTSwarm](https://arxiv.org/abs/2402.16823) | LLM operation을 function node로, information flow를 edge로 두고 prompt/connectivity를 최적화 | `F/H` 직접 선행이지만 pairwise workflow; persistent semantic memory·n-ary evidence·outcome-bound W가 없음 |
| [DynamicGPTSwarm](https://arxiv.org/abs/2406.11555) | input-conditioned edge generator로 query별 agent graph를 구성 | 임시 workflow topology와 versioned world topology는 다름 |
| [Graphiti/Zep](https://arxiv.org/abs/2501.13956), [code](https://github.com/getzep/graphiti) | episode provenance, valid/invalid time, 비파괴 invalidation을 가진 incremental temporal KG memory | 계보 memory에 매우 가깝지만 property-graph retrieval이며 neural activation/causal credit field가 아님 |
| [HippoRAG](https://arxiv.org/abs/2405.14831), [HippoRAG 2](https://arxiv.org/abs/2502.14802) | LLM-built KG + associative PPR retrieval + non-parametric continual insertion | 지식을 추가/검색하지만 outcome이 graph synapse를 학습시키지 않음 |
| [HyperGraphRAG](https://arxiv.org/abs/2503.21322) | n-ary fact를 first-class hyperedge로 구축·검색·생성 | HSWM `H`의 직접 선행이지만 RAG pipeline |
| [Hyper-RAG](https://arxiv.org/abs/2504.08758), [HyperRAG 2026](https://arxiv.org/abs/2602.14470) | beyond-pairwise retrieval, n-ary path/reasoning chain을 query-conditioned하게 선택 | retrieval score/path이 durable causal macro-W/H로 commit되지 않음 |
| [Hypergraph as Language](https://arxiv.org/abs/2605.21858) | native incidence를 semantic/structure로 분리한 hypergraph token으로 compile해 frozen LLM에 입력 | 2026년의 가장 직접적인 LLM–hypergraph alignment; query-centered serialization이지 persistent recurrent learner가 아님 |
| [A-MEM](https://arxiv.org/abs/2502.12110) | LLM이 note의 tag/link를 생성하고 이전 memory metadata를 진화 | LLM judgment 기반 organization; independent outcome credit·topology ablation이 없음 |

`Hypergraph as Language`는 HSWM compiled neural plane에 중요한 선행이다. 다만 HSWM은
hypergraph를 LLM이 읽는 것에서 멈추지 않고, LLM이 발생시킨 token이 다시
activation을 만들고 결과가 `W/H`를 바꾸는 반복 회로를 만들어야 한다.

## 5. 구현 backend 감사

| 공식 구현 | 바로 쓸 수 있는 부분 | 그 자체로 해결되지 않는 부분 |
|---|---|---|
| [PyTorch Geometric HypergraphConv](https://pytorch-geometric.readthedocs.io/en/stable/generated/torch_geometric.nn.conv.HypergraphConv.html) | sparse incidence, hyperedge weight/attribute, node/edge attention | scalar diagonal edge weight 중심; role·history·operator-W runtime 없음 |
| [DeepHypergraph](https://github.com/iMoonLab/DeepHypergraph) | weighted `v2e/e2v`, graph/hypergraph construction, 다양한 HNN baseline | 계산 엔진이지 persistent cognitive runtime/ledger가 아님 |
| [DGL sparse HGNN](https://www.dgl.ai/dgl_docs/en/2.4.x/notebooks/sparse/hgnn.html) | sparse incidence algebra와 batching | canonical n-ary identity, role, provenance, online learning 계약은 별도 |

초기 구현은 PyG/DHG를 backend으로 사용할 수 있다. 하지만 canonical hypergraph와
compiled tensor graph를 분리해야 하며, backend 객체를 HSWM의 진실 원장으로 삼으면
안 된다.

### 5.1 graph engineering: projection, rewrite, incremental state

이 절의 소스는 **인지·학습 효능의 증거가 아니라**, canonical `H/W/A/F/Π`를 손실 없이
표현·갱신·검증하기 위한 import 가능한 graph-engineering mechanism이다. 특히 graph
expansion, sparse backend, CRDT는 HSWM의 cognition·routing·causal credit을 대신하지
않는다.

| 1차 소스 | 확인된 engineering mechanism | HSWM import 경계 |
|---|---|---|
| [From Graphs to Hypergraphs](https://arxiv.org/abs/2401.08519) | nested hyperedge와 uncovered-triangle 계열에서 pairwise projection이 higher-order grouping을 잃고, 추가 정보 없이 원 hypergraph 복원이 조합적으로 불가능해질 수 있음을 분석 | role-bearing native `H`를 canonical record/lineage 단위로 유지하고 clique/2-section을 명시적 lossy view로 제한한다 |
| [HENN: spectral similarity](https://proceedings.mlr.press/v231/hayhoe24a.html) | 하나의 hypergraph에 대한 여러 graph representation의 spectral similarity를 이용해 expansion 기반 operator의 transfer-error bound를 제시 | canonical incidence를 보존한 채 여러 compiled view를 교차 검증하는 근거. clique/star/line graph 어느 하나도 정본 `H`로 승격하지 않는다 |
| [WidthWall](https://arxiv.org/abs/2605.13690) **(2026-05 arXiv preprint; 미심사)** | hypertree-width 계층으로 HGNN expressivity를 분석하고 clique expansion이 잃는 pattern 정보를 주장 | native n-ary/role incidence와 projection-loss receipt를 유지해야 한다는 강한 설계 가설. 독립 재현 전에는 확정 이론·HSWM 효능 근거로 쓰지 않는다 |
| [Hypergraph energy functions](https://proceedings.mlr.press/v202/wang23d.html) | parameterized hypergraph energy와 여러 expansion의 관계를 하나의 bilevel factorization으로 해석 | compiled operator 선택을 명시적 energy/regularizer 계약으로 비교할 수 있음. energy 최소화가 truth, authority, outcome-bound learning을 정의하지는 않는다 |
| [Open Graphs and Monoidal Theories](https://arxiv.org/abs/1011.4114), [computational category-theoretic rewriting](https://arxiv.org/abs/2111.03784) | typed input/output을 보존하는 open-graph DPO rewrite와 DPO/SPO/SqPO의 executable categorical specification | `ΔH`를 free-form mutation이 아니라 typed match·precondition·postcondition을 가진 transaction으로 만든다. category formalism 자체는 HSWM ontology의 유일성을 주지 않는다 |
| [DPOI confluence](https://arxiv.org/abs/2109.06049), [SqPO rewriting](https://doi.org/10.1007/11841883_4) | interface를 보존하는 terminating DPOI system의 critical-pair confluence와, unknown context의 deletion·cloning을 다루는 SqPO semantics | `H` topology rewrite는 typed interface와 pre/postcondition을 가진 유한 rule로 제한한다. inverse가 정의되면 inverse receipt를, 아니면 이전 snapshot 또는 compensating restore transaction을 남긴다. 임의 LLM text/Python guard는 이 정리의 전제를 만족하지 않으므로 후보 생성만 맡는다 |
| [Locality-aware rewiring](https://proceedings.iclr.cc/paper_files/paper/2024/hash/7b7db41ea66d624587f211aa15c07e45-Abstract-Conference.html) | over-squashing 완화·locality·sparsity의 trade-off를 분리하고 locality-aware sequential rewiring을 제시 | `W/H` topology 후보의 locality/sparsity guard와 baseline으로 사용. 모델 성능용 temporary shortcut을 lineage 없는 world rewrite로 commit하지 않는다 |
| [Differential Dataflow](https://www.cidrdb.org/cidr2013/Papers/CIDR13_Paper111.pdf), [Naiad](https://www.microsoft.com/en-us/research/wp-content/uploads/2013/11/naiad_sosp2013.pdf), [GraphBLAS](https://graphblas.org/graphblas-api-cpp/) | nested iterative incremental computation, timestamp/frontier coordination, sparse matrix·incidence algebra | append/retract event에서 activation/readout/index를 증분 유지하는 execution backend 후보. dataflow timestamp와 matrix value는 `H` provenance·`W` semantic operator의 정본 의미가 아니다 |
| [W3C PROV-DM](https://www.w3.org/TR/2013/REC-prov-dm-20130430/), [Merkle-CRDTs](https://arxiv.org/abs/2004.00107) | entity/activity/agent/derivation provenance model과 hash-DAG 기반 convergent replication | `H` event·derivation·responsibility를 PROV-compatible로 export하고, content-addressed branch/merge를 transport에 사용. CRDT merge가 conflicting truth·authority·causal credit을 자동 판정하지는 않는다 |
| [EdgeBank / dynamic evaluation](https://proceedings.neurips.cc/paper_files/paper/2022/hash/d49042a5d49818711c401d34172f9900-Abstract-Datasets_and_Benchmarks.html) | 과거 edge 재발만으로 강한 동적-link 성능이 나올 수 있음을 보이고 harder negative sampling을 제안 | topology/weight learning 평가는 EdgeBank와 recurrence-matched baseline을 반드시 포함한다. 단순 edge recall을 morphogenesis·causal learning으로 오인하지 않는다 |

따라서 compiled projection은 다음처럼 일방향·명시적 손실 계약을 가져야 한다.

```text
canonical typed hypergraph (H + role-bearing incidence)
  → lossless incidence/star compiler + compiler receipt
  → one or more sparse graph/tensor views
  → backend execution / differential maintenance
  → proposed ΔW/ΔH
  → Π-governed validation and canonical rewrite commit
```

clique/2-section처럼 n-ary grouping·role·multiplicity를 버리는 view는 retrieval/analysis
cache일 수는 있어도 round-trip target이나 commit source가 될 수 없다. projection이
불가피할 때는 discarded fields, source root, compiler version, and reconstruction status를
receipt에 남긴다. 이 구분은 `H`의 계보·구조, `W`의 operator, `A`의 증분 활성,
`F`의 cell execution, `Π`의 commit 권한을 혼합하지 않기 위한 것이다.
`H`나 compiled view에 들어가는 authority·capability 값은 grant/revocation의
`authority_ref`, `capability_grant_ref`, `policy_version_ref`와 검증 당시 attestation이다.
현재 effective allow/deny, scope 해석과 transaction decision의 정본 소유자는 계속 `Π_t`다.

## 6. 구현에 대한 구체적 결론

```text
Canonical persistent hypergraph
  node + hyperedge + first-class incidence
  incidence = (node, hyperedge, role, direction, source,
               valid_time, observed_at, authority_ref, polarity,
               capability_grant_ref, policy_version_ref, attestation)

LLM token event
  → immutable artifact/span record
  → sparse seed activation
  → role-conditioned incidence transport          [RAM + Sheaf HNN]
  → learned V→E aggregation                       [AllSet]
  → member-specific E→V diffusion                 [ED-HNN]
  → selected typed LLM function cell               [GPTSwarm을 n-ary로 확장]
  → action/outcome + sealed eligibility
  → fast-W candidate                              [Titans/three-factor와 대조]
  → slow-W/topology validated commit              [Graphiti의 history보다 강한 계약]
  → next token processing change
```

중요한 결정은 다음 다섯 가지다.

1. **tokenizer 중립 원문 계보:** token ID를 semantic identity로 쓰지 않고 raw
   bytes/text, tokenizer/model digest, character/span map을 보존한다.
2. **first-class incidence:** role, direction, source, time, authority/grant reference와
   attestation은 node/edge의 자유로운 metadata 문자열이 아니라 propagation과 검증을
   바꾸는 typed input이다. 현재 effective permission은 `Π_t`가 판정한다.
3. **operator projections 분리:** `retrieve(W)`, `dispatch(W)`, `update(W)`는 같은 scalar를
   공유하지 않아도 된다. 진실, 효용, 활성, 권한을 혼합하지 않는다.
4. **canonical/compiled 분리:** GPU star expansion을 써도 n-ary relation과 role의 원장은
   보존한다.
5. **fast proposal / slow truth 분리:** attention·surprise·LLM proposal은 빠른 후보이지
   durable truth/weight/topology가 아니다.

## 7. 선행연구가 이미 가르친 실패

- ECAN처럼 모든 Atom을 매 cycle 갱신하면 world scale에서 memory/compute가 붕괴한다.
- 모든 raw token을 영구 node로 만들면 semantic graph가 transcript dump가 된다.
- attention matrix는 현재 context의 임시 soft adjacency이지 durable history가 아니다.
- surprise를 truth 신호로 쓰면 놀라운 hallucination을 강하게 학습한다.
- LLM proposal을 즉시 commit하면 자기 hallucination을 자기 학습하는 폐루프가 된다.
- 시간 계보만 잘 보존해도 cognition은 아니며, routing만 학습해도 world memory는 아니다.
- 진실·효용·권한·인기를 단일 scalar로 압축하면 기억–진리 분리와 인지주권이
  동시에 붕괴한다.
- layer-local dynamic graph를 매번 새로 만드는 것은 계보적 morphogenesis가 아니다.

## 8. 가장 먼저 결판할 다섯 실험

1. fixed `W` / learned `W` / shuffled `W`에서 learned arm이 held-out external outcome을
   개선하는가?
2. 활성 relation을 제거·shuffle·rollback했을 때 다음 route/action이 예측 가능하게
   변하는가?
3. learned topology가 fixed topology와 degree-matched random rewiring을 같은 연산으로
   이기는가?
4. Agent/LLM A가 만든 numeric `H/W` 변화가 transcript 없이 다른 tokenizer/model B에
   전이되는가?
5. hyperedge-native 구조가 pairwise marginal/clique가 동일한 n-ary task에서 실제로
   필요한가?

이 다섯 실험이 핵심이다. 더 큰 KG, 더 많은 규칙, 더 긴 prompt, 더 많은
agent는 이 결판을 대체하지 못한다.

## 9. 최종 연구 경계

HSWM이 방어할 수 있는 중심은 “hypergraph를 쓴다”가 아니다. 그 영역은 이미
성숙한 HNN, AtomSpace, Hyperon, hypergraph RAG와 많이 겹친다.

> **HSWM의 중심 연구 가설은 모델 중립적 token event가 역할·출처·시간을 가진
> 영속 hypergraph를 국소적으로 점화하고, LLM function cell과 세계 outcome을
> 거쳐, 인과적으로 검증된 macro-weight와 topology 변화로 돌아오는 역사 보존형
> 학습 폐루프다.**

이 가설은 아직 구현·실증되지 않았다. Hyperon 2026을 포함한 선행연구 때문에
개념적 최초를 주장하기보다, `SWM-0→SWM-5`의 인과·scale 증거를 쌓는 것이
정확한 연구 전략이다.
