<!-- PROVENANCE
Workflow: hswm-prior-art-tribunal (wf_b999f1ee-6fa), ultracode xhigh, 62 agents, 0 errors, 5.6M subagent tokens, ~33min.
6단계: Discover(16각도, round1=187편) → Critic-Expand(+8각도, round2 → 251편) → Curate(closest 14) → DeepRead(14편 정독) → Tribunal(청구항7 × skeptic3 다수결) → Synthesize.
코퍼스 251편(강한 overlap 199). Tribunal: 3 REFUTED(C2·C6·C7) / 4 SURVIVES(C1·C3·C4·C5).
검증(2026-07-19 parent WebFetch): critic이 "환각 의심"으로 플래그한 2025-26 arXiv ID 8건 전부 arxiv.org 실재 확인 —
  2601.02744(SYNAPSE)·2603.17244(Kumiho)·2604.15676(EvoRAG)·2604.18478(WorldDB)·2512.24722(PageRank≡SR)·
  2512.15922(Spreading Activation KG-RAG)·2506.06313(Beyond Chunking, ACL2026)·2503.21322(HyperGraphRAG, NeurIPS2025).
  → "붐비는 공간" 결론은 환각 아티팩트 아님, robust. 격추 3건은 전부 유명 실재논문(GA 2304.03442 / HyperGraphRAG / RAPTOR 2401.18059)에 근거.
관계: 이 문서는 PROM_6_EFFICACY_RESEARCH_2026-07-19.md(효능 갭)의 자매편(선행연구·신규성). canon=THEORY/재배맨/HSWM_STANDARD.md.
-->

# HSWM 선행연구·신규성 감사 보고서
### Hypergraph Semantic Weight Map — Prior-Art & Novelty Tribunal (PROM, 62-agent)

**대상**: W(e|c) = cosine(α) + λ_b·log(base_salience) + λ_j·judgment 를 단일 스칼라 場으로 삼아 **검색(retrieval)·계획/디스패치(planning)·비파괴적 대체(non-destructive supersession)** 를 모두 하나의 場의 readout으로 통합하는 KG 메모리 substrate.
**코퍼스**: dedup 251편(강한 overlap 199). **심층정독**: 14편. **Novelty Tribunal**: 청구항 7건 × 적대적 skeptic 3인 다수결. **arXiv 실재검증**: load-bearing 8건 전부 확인(위 PROVENANCE).

---

## 1. 한 줄 결론

**HSWM은 시스템 전체로는 신규가 아니다.** 개별 구성요소(스칼라 blend 공식, reified hypergraph + salience, spreading-activation-beats-cosine, LLM-judged supersession, one-field-many-readouts)는 하나도 빠짐없이 이미 선행연구에 존재하며, 이 공간은 **극도로 혼잡(highly crowded)** 하다 — 특히 2024–2026 LLM-agent-memory / KG-RAG 라인이 정면으로 겹친다. 7개 청구항 중 **3건 완전 격추(C2·C6·C7)**, 4건 생존(C1·C3·C4·C5)이나 **생존분은 전부 "얇은 재조합(thin recombinatory) 신규성"** 이며 그중 셋은 tribunal MEDIUM 이하 confidence다. 진짜로 아무도 소유하지 않은 지점은 단 하나: **비파괴적 supersession을 검색·계획과 *동일한* 스칼라 場의 threshold readout으로 접는 것**(C1의 3-way conjunction + C3) — 그러나 이것조차 (i) "아무도 안 함"이라는 부정적 근거에 불과하고 (ii) 인접 문헌(MemStrata AUROC 0.59)은 그 통합이 *나쁜 설계*일 수 있음을 시사한다.

---

## 2. 가장 가까운 선행연구 지도 (ranked)

| # | 선행연구 | 이미 함 (무엇을) | HSWM이 아직 소유 | 근접도 |
|---|---|---|---|---|
| 1 | **Kumiho — Graph-Native Cognitive Memory** [2603.17244] | substrate-not-reasoner 포지셔닝 + 비파괴 supersession(immutable revision + mutable pointer)에 **AGM K*2–K*6 형식증명** | 3-way scalar 통합; supersession을 *검색 score의 readout*으로 접는 것(Kumiho는 의도적 **분리**); log-salience 연속항; in-band judgment | **최근접 전체시스템 analog**. 단 supersession을 score에서 *떼는* 정반대 설계 |
| 2 | **Generative Agents** [2304.03442] | `score = α_rec·recency + α_imp·importance(LLM 1–10) + α_rel·cosine` — **W 공식 near-verbatim**, retrieval+planning 동일 場 | judgment의 *지속 업데이트*(GA=write-once); cosine-floor; supersession(GA=append-only); edge 가중치; IR 벤치 | 공식 자체 = **C2 사형집행자** |
| 3 | **ACT-R declarative activation** (Anderson 2004) | Aᵢ = Bᵢ(=ln Σtⱼ⁻ᵈ) + Sᵢ + noise — 하나의 스칼라가 **retrieval+latency+decay 망각** 동시 지배 (~50년) | retrieve=**plan** 통합(ACT-R은 dispatch를 별도 Uᵢ 場에 **의도적 분리**=반례); 이산 supersession; embedding cosine; LLM judgment | additive 형태 + one-field 주장의 **원조 조상** |
| 4 | **SYNAPSE — Spreading Activation** [2601.02744] | Eq.5 `S = λ₁·sim + λ₂·activation + λ₃·PageRank` — 3항 선형융합 memory substrate; activation scalar가 retrieval+archival gating 이중 사용 | judgment=진짜 LLM 평가(SYNAPSE=zero-LLM 결정론); cosine-floor; 진짜 supersession(SYNAPSE=destructive prune); planning 전무 | 3항 SHAPE + one-scalar-two-uses **존재증명** |
| 5 | **HippoRAG** [2405.14831] | LLM-KG를 PPR diffusion으로 검색, "artificial hippocampal index=substrate not reasoner", vector-RAG 격파 (~2년 선행) | additive W + validated cosine-floor; online judgment loop; supersession(add-only); planning readout | positioning + "cosine 이기고 hard multi-hop서 불연속" 시그니처 **동형** |
| 6 | **Zep / Graphiti** [2501.13956] | production bi-temporal KG; **LLM-judged 비파괴 invalidation**(t_invalid, 삭제 안 함) | 단일 fused scalar(Zep=무공식 파이프라인); supersession을 검색 threshold로 통합; cosine-floor; log-salience | supersession 메커니즘 **강한 부분 선행** |
| 7 | **WorldDB** [2604.18478] | content-addressed 비파괴 supersession(validity 닫기, 양쪽 보존, merge staging) 1급 write semantics | 단일 場(WorldDB=RRF 3-lane rank fusion); **judgment를 read-path서 의도적 배제** | supersession-as-readout 시스템화. judgment 배제는 HSWM 전제의 **반례** |
| 8 | **PageRank ≡ Successor Representation** [2512.24722] | **단일 스칼라 場(random-walk stationary dist)이 retrieval+planning+navigation 동시 subserve — 형식 isomorphism 증명** | 3번째 leg=navigation≠supersession; cosine/judgment/salience 분해 없음 | **C1(one-field-3-readout)의 최근접 형식선행** |
| 9 | **AriGraph** [2407.04363] | episodic+semantic 단일 KG가 retrieval+planning 겸용; MuSiQue/2wiki서 HSWM과 **동일 hard-multi-hop 열세 패턴** | 단일 scalar(AriGraph=2공식 분리); cosine-floor; 연속 judgment loop | 구조적 선행 + 동일 실패 시그니처 |
| 10 | **SR lineage** — Dayan 1993 / Stachenfeld 2017 / Gershman 2018 | V=M·R: 하나의 diffused 場이 similarity+plan 겸용, "substrate not reasoner", Momennejad 2017이 hard/easy dissociation preregister | 이산 비파괴 supersession(SR=destructive overwrite); additive 공식; cosine-floor; NL hypergraph 도메인 | one-field-2-readout **창립정리** (~30년 선행) |
| 11 | **DNC** [Graves 2016] | 단일 memory matrix가 content-lookup + temporal-link + usage-freeing **3-readout** | 단일 *scalar*(DNC=3 vector gate 보간); 비파괴(DNC=overwrite-on-free); judgment(DNC=BPTT) | 3-readout 최근접 고전선행. freeing=**정반대**(파괴적) |
| 12 | **PRoH** [2510.12434] | reified hypergraph 위 retrieval+planning loop; θ_emb cosine gate ≈ crude cosine-floor | 단일 캐시 scalar(PRoH=매쿼리 재계산·폐기); 지속 substrate; supersession; validated floor | 슬로건만 겹침, 메커니즘 DISTINCT |
| 13 | **HyperGraphRAG** [2503.21322] | reified n-ary hypergraph 검색 substrate + **per-hyperedge 고유 salience**(eᵢ=(text,score), sim ⊙ score) | additive+log 융합; validation cosine-floor; judgment loop; 3-way 통합 | C6 **사형집행자** |

---

## 3. Novelty 판정표 (C1–C7)

| 청구항 | 판정 | 명명된 anticipator | 정직한 한 줄 verdict |
|---|---|---|---|
| **C1** — retrieval·planning·supersession 모두 *하나의* 공유 스칼라 場의 readout | **SURVIVES** (0/3 refute, MEDIUM) | 최근접 [2512.24722] (3rd leg=navigation) | 개별 leg·2-way(retrieve+plan)는 전부 near-dup. 오직 **supersession을 동일 場에 접는 것**만 미선점. 얇음. |
| **C2** — W = cosine + λ_b·log(salience) + λ_j·judgment 가산 blend | **REFUTED** (3/3, HIGH) | **Generative Agents** [2304.03442] | recency+importance(LLM)+relevance(cosine) = 공식 near-verbatim, 2년 선행. 격추. |
| **C3** — supersession이 검색 場 자체서 파생(W-threshold), 분리 규칙 아님 | **SURVIVES** (0/3, MEDIUM) | 없음 (전 supersession 문헌이 *분리* 규칙) | 아무도 안 함이 근거. 단 MemStrata: cosine이 모순↔중복 구별 AUROC=0.59(≈chance) → 통합이 *의심스러운* 설계일 수. |
| **C4** — in-context LLM-judgment 루프(≠SGD)가 KG 검색 場 학습 메커니즘 | **SURVIVES** (0/3, MEDIUM) | **EvoRAG** [2604.15676] (but SGD 사용) | 아키텍처 전부 선점, 유일 차이 = "in-context vs gradient". 반드시 contested될 얇은 선. |
| **C5** — ReLU residual + validation-λ 로 구성보장 cosine-floor | **SURVIVES** (1/3 refute, LOW/MEDIUM) | **CLEAR** [2004.13969] (역방향: lexical floor) | floor는 사실상 자명(비음 ReLU·λ=0 = 표준 model selection). non-obvious성 취약. |
| **C6** — reified hypergraph substrate + per-hyperedge 고유 salience | **REFUTED** (3/3, HIGH) | **HyperGraphRAG** [2503.21322] | eᵢ=(text,score), 랭킹 sim ⊙ score = 정확 일치. 격추. |
| **C7** — 학습 weight 場 위 spreading-activation이 긴/책-길이 검색서 cosine 격파 | **REFUTED** (2/3, MEDIUM) | **Beyond Chunking** [2506.06313] + **Spreading Activation KG-RAG** [2512.15922] + **RAPTOR** [2401.18059] | 메커니즘도 regime도 각각 기출간. 사용자 자인 "untested" = 재발견. |

---

## 4. 유일하게 살아남은 방어선 (C1·C3·C4·C5)

> 생존 4건은 전부 "개별요소가 아니라 *조합*이 미선점"이라는 성질뿐. 방어 = 조합이 왜 자명하지 않은지를 **실증으로** 보여야 한다.

### C1 — 3-way scalar 통합 (retrieve = plan = supersede)
- **소유**: SR/PageRank[2512.24722]은 retrieval+planning+navigation을 증명(단 supersession 없음). GA[2304.03442]는 retrieve+plan을 공식화(단 supersession-as-readout 없음). ACT-R은 retrieve+decay를 하나에 넣되 **plan을 별도 場(Uᵢ)에 분리**. 즉 **supersession을 검색·계획과 동일 스칼라 threshold로 접은** 실물은 코퍼스에 없다.
- **방어 build**: (a) 동일 W 하나에서 세 readout이 나온다는 것을 **ablation으로 분리** — planning-only/supersession-only가 독립 場을 쓸 때 대비 통합 場이 *측정 이득*(파라미터 절약·일관성·transfer)을 내는지. (b) ACT-R 50년 반례(retrieve와 plan은 다른 dynamics)에 정면 응답.
- **counter-thesis**: "one-field-many-readouts" 메타아키텍처는 heavily 선점됐고 supersession leg만 남는데, 그게 가장 논쟁적(C3의 AUROC 0.59).

### C3 — supersession = W-threshold (분리 규칙 아님)
- **소유**: Zep·Kumiho·WorldDB·Memanto·MemStrata — 전부 비파괴 supersession을 **bi-temporal edge / AGM revision / 결정론 규칙**으로, 검색 scalar와 *분리* 구현.
- **방어 build**: supersession을 W-threshold로 뽑는 게 분리형보다 **낫다**는 실증. 핵심 — MemStrata "cosine으로 모순 vs 중복 구별 AUROC=0.59" → **judgment항 λ_j가 판별력을 chance 위로 끌어올린다**를 반드시 측정. 없으면 "왜 문헌 전체가 일부러 분리하는가"(신뢰 가능한 비파괴성 = 이산 tag여야 형식증명)에 진다.
- **counter-thesis (Kumiho)**: Kumiho[2603.17244]는 *정반대*로 — 연속 hybrid score와 belief-base를 **비상호작용 2층 분리** — AGM 형식증명을 얻음. 연속 場 위에선 "superseded"가 정도의 문제라 clean AGM proof가 안 산다. HSWM 통합은 parsimony가 아니라 *신뢰 가능한 비파괴성*을 포기하는 것일 수도.

### C4 — in-context LLM-judgment 루프 (≠SGD)
- **소유**: EvoRAG[2604.15676]=KG triplet 가중치를 LLM-judge 피드백으로 refine하는 near-identical 아키텍처지만 업데이트가 **진짜 gradient descent**. DAT[2503.23013]=in-context지만 per-query(지속 場 아님). Mem0=categorical ADD/UPDATE/DELETE. 4-술어 conjunction 만족 실물 없음.
- **방어 build**: EvoRAG를 명시 baseline으로, **in-context 업데이트가 gradient 대비 substantive**(데이터효율·냉시동·해석·비미분 신호 수용)임을 실증. 못 하면 "EvoRAG의 minor variant" 판정.
- **counter-thesis**: SYNAPSE[2601.02744]는 순수 결정론(zero-LLM)만으로 multi-hop lift(27.5→35.7 F1) — "cosine 위 2번째 신호"에서 이득에 **LLM judgment가 굳이 불필요**함을 증명. judgment 특정성이 통합에 불가결함을 못 보이면 값비싼 구현선택으로 강등.

### C5 — 구성보장 cosine-floor
- **소유**: CLEAR[2004.13969]=base 위 residual floor지만 base가 lexical(역방향). SPIBB[1712.06924]=baseline-in-candidate validation-select를 RL서 형식화. 정확 튜플 verbatim 논문은 없음.
- **정직 포지셔닝**: 이건 방어선이 아니라 **엔지니어링 안전장치**. floor는 selection set 위 자명(W≥cosine), OOD 보장 아님, 스칼라 floor가 검색성능 floor 함의도 안 함. "novelty"가 아니라 "reproducible safety property"로 청구. 1/3 skeptic 이미 REFUTE.

---

## 5. 죽은 주장 (refuted) — 집행자를 그대로 말한다

**C2 (공식) — killed by Generative Agents [2304.03442]**: `score = α_rec·recency(0.995^Δh) + α_imp·importance(LLM 1–10) + α_rel·cosine` = W = cosine + λ_b·log(salience) + λ_j·judgment 와 항 대 항 일치, 2년 선행. λ_b·log vs 지수감쇠 = monotone reparameterization. 3/3 HIGH.

**C6 (hypergraph+salience) — killed by HyperGraphRAG [2503.21322]**: eᵢ = (eᵢ^text, eᵢ^score), eᵢ^score = 쿼리-독립 고유 salience. 랭킹 sim(h_q,h_eH) ⊙ eH^score 가 cosine을 per-hyperedge 고유항으로 변조 = 정확 구현. 가산·log vs 곱셈 차이는 청구항 문언이 보호 못 함. 3/3 HIGH.

**C7 (긴문서 spreading-activation) — killed by Beyond Chunking [2506.06313] (+ Spreading Activation KG-RAG [2512.15922], RAPTOR [2401.18059])**: regime(구조 readout>flat-cosine on long-doc)은 RAPTOR(+20% QuALITY)·Beyond Chunking(RST discourse tree)이 이미 증명. 메커니즘(spreading>cosine)은 [2512.15922] (~39% over naive)·HippoRAG가 증명. 근원=Collins & Loftus 1975. 사용자 근거("긴 span에 논리/구조 가중치 vs word-embedding cosine")=그 고전 이분법의 near-verbatim 재진술. 2/3 MEDIUM.

---

## 6. 사용자 직관 (긴문서 spreading-activation)의 위치

**판정: C7은 신규가 아니다 — 이미 청구된 영역.** 그러나 *정확한 conjunction*(spreading-vs-cosine gap을 **unit 길이의 함수로** 측정해 book-length서 단조 확대)은 단일 논문이 verbatim 하지 않았다.
- **메커니즘 절반**(spreading>cosine): 완전 선점 — [2512.15922], HippoRAG, ACT-R, Collins & Loftus 1975.
- **regime 절반**(long-doc>flat cosine): 완전 선점 — RAPTOR, Beyond Chunking, DISRetrieval.
- **미측정 교집합**: "spreading-vs-cosine gap을 unit 길이에 대해 측정해 book-length서 단조 확대"는 없음. = 정확히 사용자의 자인된 untested 직관.

**그러나 HSWM 자신의 실측이 직관을 이미 반박할 위험**: MuSiQue −0.26 / 2wiki +0.04. SR lineage(Momennejad 2017)의 *경쟁 설명* = "span 길이"가 아니라 **iterated multi-hop 전파 부재**(정적 3항 가산은 진짜 graph diffusion을 안 하므로 깊은 관계변화서 지고 얕은 additive서 이김). 이 시그니처는 span 길이 가설과 **관측적으로 혼동(confounded)**.

### 구체적 다음 실험 (직관을 살리거나 죽이는 falsifier)
1. **길이-층화 ablation (핵심)**: 동일 reader·corpus, 검색 unit granularity sentence→paragraph→section→book. HSWM−cosine F1 delta를 unit 길이 함수로 플롯. **예측(직관 참)**: 단조 증가. **반증**: flat이거나 hop-depth에만 반응.
2. **혼동 분리 (직교화)**: hop-depth를 2번째 축으로 교차설계(short-unit-multi-hop vs long-unit-single-hop). span 길이 축과 multi-hop 축 분리 → 이득이 어느 축에 실리는지. SR반대가설(전파부재) vs 사용자가설(span길이) 판별.
3. **judgment 필요성 (C4 연동)**: judgment항을 SYNAPSE식 결정론 spreading recurrence로 대체한 arm 추가. long-span 이득이 judgment 특정적인지 임의 2번째 신호로 재현되는지.
4. **preregister**: delta 곡선의 방향·기울기·hop-축 대비를 사전등록. untested→*측정된 발견* 격상은 prereg된 길이-단조성 확인으로만.

---

## 7. 핵심 인용 (grouped)

**공식·one-field 통합 (C1·C2)**: Park *Generative Agents* 2304.03442(C2 killer) · Anderson *ACT-R* 2004(one-field 조상+plan분리 반례) · Millidge *PageRank≡SR* 2512.24722(C1 최근접 형식선행)
**Successor Representation lineage**: Dayan 1993 · Stachenfeld/Botvinick/Gershman *hippocampus as predictive map* 2017 · Gershman 2018 · Momennejad 2017(hard/easy preregister)
**KG/hypergraph RAG (C6·C7)**: Gutiérrez *HippoRAG* 2405.14831 · *HyperGraphRAG* 2503.21322(C6 killer) · *PRoH* 2510.12434 · Anokhin *AriGraph* 2407.04363
**Spreading activation / long-doc (C7)**: Jiang *SYNAPSE* 2601.02744 · Pavlović *Spreading Activation KG-RAG* 2512.15922(C7 co-killer) · Chen *Beyond Chunking* 2506.06313(C7 killer) · Sarthi *RAPTOR* 2401.18059 · Collins & Loftus 1975(근원 이분법)
**비파괴 supersession (C3)**: Park *Kumiho/AGM* 2603.17244(C3 최강 counter) · Rasmussen *Zep/Graphiti* 2501.13956 · Ganesan *WorldDB* 2604.18478 · Memanto 2604.22085 · MemStrata(cosine 모순판별 AUROC 0.59)
**judgment 루프 / floor (C4·C5)**: Fu *EvoRAG* 2604.15676(C4 최근접, SGD) · DAT 2503.23013 · Mem0 2504.19413 · *CLEAR* 2004.13969(C5 최근접, 역방향) · SPIBB 1712.06924
**고전 tri-readout**: Graves *DNC* 2016(Nature 538)

---

> **최종 정직선**: 이 공간은 붐빈다. HSWM 프레이밍은 GA(공식)·SR(one-field)·HyperGraphRAG(hypergraph+salience)·RAPTOR(long-doc)·Zep/Kumiho(supersession)가 각각 이미 소유한 조각들의 **재라벨링/일반화**로 읽힌다. 진짜 미선점은 "supersession을 검색·계획과 동일 스칼라에 접는 3-way conjunction"(C1+C3) 하나뿐이며, 그조차 (i) 부정적 근거뿐 (ii) Kumiho가 그 통합을 *일부러 피해* 더 강한 형식보장을 얻었고 (iii) MemStrata AUROC 0.59가 판별력 자체를 의심케 한다. **방어는 novelty 주장이 아니라 측정된 이득(통합 場이 분리 baseline 대비 무엇을 사는가)으로만 가능하다.**
