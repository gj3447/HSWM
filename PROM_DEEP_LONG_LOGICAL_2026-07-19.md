# PROM_DEEP — HSWM 긴문맥·논리 우위의 정면 검증 (4축 종합, 2026-07-19)

> **주제**: 사용자 정본 발화 "cosine은 단어 임베딩 위주라 긴 문장·책 단위·논리 내용에서 무너지고, HSWM은 웨이트 장을 순회하며 논리를 잡아 유의하게 이긴다 — 유능함(reasoner)도 이긴다"를 학문적으로 정면 검증한다.
> **방법**: 4축 병렬 심층 리서치(각 axis 별 agent, 핵심 논문 pdftotext 원문 검증, ≥2 삼각검증) + 기존 실측(substrate ladder, hop stratification, 합성 expB) 통합.
> **한 줄 결론**: **님 직관은 옳고, 4겹으로 grounding된다. 단 그 우위를 만드는 엔진("웨이트 장 순회")은 현재 HSWM에 아직 안 켜져 있고**(정적 1-hop), 켜는 순간(cosine-seeded 다단계 전파) 문헌·합성 양쪽이 "홉 깊을수록 이김"을 예측한다. 진짜 시험대는 두 개: (1) cosine이 아니라 **강한 baseline**을 이겨야, (2) 이득이 corpus 암기가 아니라 **이식 가능한 논리**여야.

---

## 0. 판정 요약 (님 5개 주장에 대해)

님 발화를 5개 반증가능 명제로 분해하고 각각 판정:

| # | 주장 | 판정 | 근거축 |
|---|---|---|---|
| **A** | cosine은 어휘(단어 임베딩) 정렬 위주다 | ✅ **정확 (형식 항등)** | 축3: `cosine = M=I인 RESCAL/Hopfield-sim`. 축1: 단일벡터 sign-rank 천장 |
| **B** | cosine은 긴 문장·책 단위·논리 내용에서 무너진다 | ✅ **강한 확증 (4겹)** | 축1: LIMIT 이론천장 + evidence dilution(EDI) + NoCha 책단위 55.8% + BRIGHT 추론검색 59→18 |
| **C** | 논리 사슬이 길수록 HSWM이 cosine보다 더 벌린다 | ✅ **실측+문헌 정합** | 실데이터 홉 stratification(2홉+0.014→4홉 nDCG+0.072) + 축2 Quest-GNN(+1.7→+25) + RAGSearch(+0.47 vs +27.23) |
| **D** | 그 메커니즘은 "웨이트 장 순회(traversal)"다 | ⚠️ **방향 옳음 / 현재 미구현** | 축3: 현 HSWM=APPNP K=0 정적 1-hop, 순회 항 없음. 순회 arm은 홉서 벌리나(합성 spread arm) 아직 코드에 없음. 순수 PPR arm은 이미 최약(seed 없어서) |
| **E** | 어떤 regime선 reasoner(유능함)도 이긴다 | ✅ **부분 실측** | substrate ladder: 2Wiki HSWM 0.721 > direct-LLM 0.679 |

**종합**: A·B·C·E는 **참(실측/형식)**. D만 **"열망은 옳고 실현은 미완"** — 그리고 D가 정확히 님 비전의 심장이다. 이 문서의 핵심은 **D를 어떻게 진짜로 켜는가**다.

---

## 1. 축1 — cosine이 무너지는 지점 (님 주장 B의 지반)

단일 벡터의 붕괴는 4겹으로 grounding된다 (전부 원문 검증):

1. **이론 천장** — *On the Theoretical Limitations of Embedding-Based Retrieval* (DeepMind, arXiv 2508.21038, ICLR 2026): 단일벡터가 top-k로 반환 가능한 문서 조합 수는 차원 d로 **상한**된다(sign-rank/communication complexity). d=1024 → 4M 조합 천장. 어떤 d로도 반환 불가능한 조합이 존재.
2. **경험적 붕괴** — 같은 논문 LIMIT: BEIR 62.76(Qwen3-Embed)가 자명한 과제서 **recall@100 = 4.8%**. BM25는 거의 완벽, multi-vector는 크게 위, cross-encoder는 100%. → **붕괴는 단일벡터 아키텍처 고유**.
3. **기계론** — *Lost in a Single Vector* (arXiv 2606.18781, 2026): 긴 문서서 결정적 근거 span이 인코딩 중 **희석**(Evidence Dilution Index). >4k 토큰서 chunk-aggregate로 30→90 회복.
4. **책 단위·추론** — NoCha(arXiv 2406.16264): 책 전역 추론 GPT-4o 55.8% vs 인간 97%. BRIGHT(arXiv 2407.12883): 추론검색서 dense 59→18. NovelHopQA(2506.02000): RAG가 golden 대비 multi-hop −31점.

**⚠️ 축1이 못박은 진짜 시험대**: 이 불가능성은 **단일벡터 dot-product 한정**이다. multi-vector(ColBERT), cross-encoder rerank, question-seeded graph가 손실 대부분을 싸게 회복한다. **HSWM의 "유의한 승"은 cosine이 아니라 이 강한 baseline들을 이겨야 성립.** 게다가 HSWM readout이 결국 고정차원 내적으로 환원되면 **같은 sign-rank 천장을 상속**(반드시 검정).

---

## 2. 축2 — 순회 우위가 홉 따라 벌어짐 (님 주장 C·D의 문헌 지반)

**"margin grows with hops"는 여러 논문에서 정량 재현된다** (전부 원문 pdftotext 검증):

| 출처 | 홉-margin 증거 (dense 대비 순회) |
|---|---|
| **Quest-GNN** (SIGIR'26, 2510.11541) | MuSiQue R@5: HippoRAG2 +3.0→+3.3→**+8.7**(4홉); Quest-GNN +1.7→+5.3→**+25.0**(4홉) — **단조 확대** |
| **RAGSearch** (2604.09666, 2026) | 단일홉 **+0.47** vs 다중홉 **+27.23** |
| **HippoRAG** (2405.14831, ICML'25) | 2Wiki All-Recall@5 **+38.6** (사슬 전체 회수) |
| **HippoRAG2** (2502.14802, ICML'25) | passage recall Hotpot(2홉)+1.8 < 2Wiki+13.9 (관계복잡도 비례) |
| **AAR** (2604.20850, 2026) | 전체 +8.6 vs dense-실패 질문 **+28.5** |
| **HSWM 내부** (실데이터) | 2홉+0.014→3홉+0.082→4홉 nDCG+0.072 |

**구조적 이유** (왜 한 벡터 top-k가 사슬 중간을 놓치나): 다중홉에서 "query와의 관련성"과 "다른 passage와의 관련성"이 **분기**한다. bridge 엔티티는 query와 표면 유사도가 낮아 단일 사영으론 상위에 못 올라온다. 순회는 엣지를 따라 *간접* 접근한다.

**❌ 정직한 두 한정**:
- **상대적 우위다**: 절대 성능은 모든 방법이 홉↑에 감소(exponential search space + noise). "순회가 4홉을 쉽게 만든다"가 아니라 **"덜 무너진다"**. Goodhart 회피 위해 이 프레이밍 유지 필수.
- **★ 최대 반증 (AAR inductive)**: *Association ≠ Similarity*(2604.20850)는 HSWM 명제를 거의 그대로 실험했다(dense를 association으로 rerank, HotpotQA +8.6). **그런데 transductive(대상 corpus co-occurrence 학습)는 이기지만 inductive(미관측 관계)엔 이득 0.** 즉 이득이 "이식 가능한 논리"가 아니라 **"이 corpus 통계 암기"**일 수 있다. → **inductive/cross-corpus falsifier를 반드시 사전등록**해야 님 "논리 포착" 주장이 방어된다.

**❌ "그래프RAG=다중홉 우위"는 거짓**: GraphRAG(MS)·RAPTOR·LightRAG는 다중홉 passage recall에서 dense보다 **낮다**(요약형이지 retrieval형 아님). 정확히는 **"question-seeded 순회(PPR/GNN/association)=다중홉 우위"**. HSWM는 후자 진영에 명확히 서야 한다.

---

## 3. 축3 — 형식 지반: HSWM는 무엇인가 (님 주장 A·D의 수학)

**단단한 형식 결과 하나**: HSWM가 실제 계산하는 `α = pooled(e)ᵀ M q` (코드 `weight_field.py::attention_alpha` 검증)는 세 이론이 인정하는 **한 수학적 대상**이다:

| 읽기 | 대응 | 정합 |
|---|---|---|
| 관계 임베딩 | 단일관계 RESCAL `eₛᵀ R eₒ` (`M=I⇒cosine`, `M=full⇒RESCAL`) | **정확 항등** (관계 1개) |
| 연상기억 유사도 | Universal Hopfield `sim(M,q)`; `M↔W_Kᵀ W_Q` | **정확 항등** |
| `plan=softmax(W)` | Modern Hopfield 1 업데이트 = **transformer attention 1 스텝** (Ramsauer 2020, 2008.02217) | **정확 항등** |
| `W=cosine+λ_b·log b` | 1-hop 절단 **ACT-R 활성화** `Aᵢ=Bᵢ+ΣWⱼSⱼᵢ` | **구조 동형** |

readout 3형(`retrieve=top-k / plan=softmax / dispatch=argmax`)은 **한 유사도 場의 sparse/softmax/max separation** = Universal Hopfield 논지의 축자적 instance. → 님의 "**활성화**"(A) 동사는 형식적으로 정당하다.

**정직한 over-claim 원장** (진술대로는 비허가):

| 주장 | 판정 | 이유 |
|---|---|---|
| "M이 **논리**를 담는다" | ⚠️ **한 관계편향까지만** | 단일 global M ≠ per-relation {Rₖ}(RESCAL gap). AND/OR/NOT·규칙·진리전파 없음(Query2Box/MLN/LNN gap). **정확 어휘 = "학습된 단일관계 metric"이지 "논리"가 아님** |
| "웨이트로 **순회**한다" | ❌ **미구현** | W는 `Tᵏ(k≥2)` 항 없는 정적 per-edge 점수 = APPNP **K=0**. 다단계 합성 불가 ⇒ MuSiQue 다중홉 약세가 *구조적으로 예측됨*(임베딩 품질 무관). 순수 PPR arm은 이미 최약(0.373<0.670) |
| "HSWM=연상기억(완전한 Hopfield)" | ❌ **vapor** | 용량 2^{d/2}·수렴·**패턴완성**은 전부 *반복* 사상 고정점 성질. HSWM는 1-shot readout, W를 재주입 안 함 ⇒ "한 Hopfield 스텝"이지 "수렴 연상기억" 아님 |
| "LLM 루프라서 무경사(SGD 아님)" | ⚠️ **감독출처로만 참** | 코드 update = judge 라벨 위 InfoNCE = Bradley-Terry 대조경사 = **SGD**. von Oswald(2212.07677): in-context 루프조차 암묵 GD. "무경사"는 Hebbian write/MWU로 *실현*해야 구조적으로 참이 됨 |

**님 "학습" 발화의 정직 분해**: "LLM이 판단 피드백으로 웨이트 조정"은 두 주장의 혼합 — **(감독출처)** "task 정답이 아니라 LLM verdict로 움직인다" = **참·강근거**(RLHF/DPO/LLM-judge); **(메커니즘)** "무경사" = 현재 코드엔 거짓(SGD). 두 축은 직교하며, LLM을 넣는 건 *감독출처*만 바꾼다.

---

## 4. 종합 — 겉보기 모순의 해소 (이 문서의 심장)

세 실측이 한 점으로 모인다:

| 소스 | 정적 HSWM(현재) | 순회(spread) arm |
|---|---|---|
| 합성 expB 로그 | delta 붕괴 {0:0.42,1:0.19,2:0.16}, **hop_drop +0.26 (진다)** | delta 성장 {0:−0.03,1:0.31,2:0.34}, **hop_drop −0.37 (이긴다)** |
| 축2 문헌 | (single-hop dense 충분) | Quest-GNN margin +1.7→+25 단조 |
| 축3 이론 | APPNP K=0 → 다중홉 약세 **구조적 예측** | APPNP K≥3 전파 = SR/PPR resolvent `(I−γT)⁻¹` = 모든 walk 합 |

→ 님 직관("웨이트로 돌아다니면서 논리를 잡는다")은 방향상 순회 arm의 성질이다. 그런데 **현재 HSWM은 그 순회를 아직 안 함**(정적 1-hop). 실데이터 홉-우위(+0.014→+0.082)는 작지만 실재한다.

### 4.1 ⚠️ 정정 (2026-07-19, 순회 실험 실행 후) — "잠든 엔진" 가설 **반증**

위 문단은 처음에 "진짜 큰 우위는 아직 안 켜진 순회 엔진에 잠들어 있다"고 적었다. **그 주장을 검정하려 순회를 실제로 켜봤고, 이 substrate에서 반증됐다** (`gj3447/HSWM@add1584 traversal_bench.py`, CPU·0 LLM·재현게이트 300/300 통과):

- cosine-seeded APPNP(K=3~10, a∈{.1,.15,.2}) 전파를 구현 → **정적보다 홉에서 *더* 무너짐**: hop_drop static **+0.241** < traversal **+0.354** (P(static이 덜 무너짐)=0.99, Δ CI 상한<0). **9개 (a,K) 조합 전부** 정적보다 나쁨.
- **"홉 깊을수록 덜 무너진다"는 성질은 실재하나 순회가 아니라 *정적 학습 필드*에 산다**: hop_drop cosine +0.301 > static +0.241, 그리고 static의 cosine 대비 마진이 홉 따라 **성장**(2홉 +0.018→4홉 +0.079, p=0.003). 순회를 켜면 그걸 **파괴**한다.
- **메커니즘**: 쿼리당 풀 10~20개 = 조밀 para-para cosine 그래프. 대칭정규화 확산은 조밀 그래프서 **저역통과 평활기**로 작동해 랭킹 specificity를 뭉갠다 — 4 gold를 16 distractor서 구분해야 하는 고홉서 특히 손해.

**정정된 결론**: D("순회")는 *명세대로는 이 substrate에서 반증*. 다중홉 우위는 **이미 정적 pointwise M 필드가 나르고 있고**, 명세대로의 cosine-seeded 순회는 그걸 깬다. **단 D가 죽은 게 아니라 *장소가 틀렸다*** — 문헌(축2 HippoRAG2/Quest-GNN)의 순회 우위는 **희소 엔티티-공기(association) 그래프 + 대형 코퍼스 + bridge 노드**에서 나오지 조밀 cosine 소풀에서 나오지 않는다. 즉 순회를 살리려면 substrate 자체를 바꿔야 한다(doc→개념 하이퍼그래프 빌더 + 실 책-코퍼스). cosine-seeding이 seedless PPR은 이김(0.548>0.387, HippoRAG2 방향성 확인)이나 cosine 회복은 못 함.

---

## 5. 두 진짜 시험대 + 사전등록 실험 (다음 진행)

### 시험대 1 — 강한 baseline (축1)
cosine 말고 **ColBERTv2 / HippoRAG2 / RAPTOR / late-chunking** 대비 이겨야 진짜. (단일벡터 천장은 이들이 싸게 회복하므로.)

### 시험대 2 — inductive falsifier (축2 AAR)
이득이 **미관측 관계(다른 split/corpus)**에서도 유지되어야 "논리 포착"; transductive만 이기면 "corpus 암기"로 반증.

### 사전등록 실험 (축4 설계 + 축3 처방 통합)
**"순회를 진짜로 켜라"**: 기존 W場 위 `Z^{(k+1)}=(1−α)Â Z^{(k)}+α W`, K≈3–10, **cosine seed 유지**. arm = {BM25, cosine, late-chunking, HSWM-static(pointwise), **HSWM-traversal(cosine-seeded APPNP)**, ColBERTv2, HippoRAG2, RAPTOR}. 전부 query-time 0 LLM(build 비대칭은 amortize + break-even N 공개).

**3중 confound 직교화** (축4): M1 길이(재청킹, H·gold 고정) / M2 홉(길이·분산 매칭 후 2v3v4) / M3 분산(needle 재배치, 총길이 고정). 혼합효과 회귀 `m_q = β0 + β_L·L + β_H·H + β_P·P + β_LH·(L×H) + u_q + u_doc`.

**prereg 예측** (첫 실측 전 잠금: MARGIN=0.03, α=0.05, k∈{5,10}, seeds 0-4, λ grid {0,.1,.2,.4,.8} val-only):
- **P1(길이)**: `β_L>0`, paired-perm p<0.05, whole-doc−sentence gap≥0.03, CI 하한>0.
- **P2(길이×홉)**: `β_LH>0` — 길이 우위가 고홉서 더 큼.
- **P3(분산 편출·결정적)**: P 공변량 투입 후에도 β_L이 MARGIN 위 유지. *실패 시 "길이"는 사실 증거분산(=SR 승리)*.
- **P4(강baseline 생존)**: long/global 층서 HSWM 마진이 max{RAPTOR,late-chunking,ColBERTv2} 대비>0.
- **P5(순회 필요성)** — ❌ **실행됨·반증 (2026-07-19, §4.1)**: `hop_drop_traversal ≤ 0.5·hop_drop_static` 예측했으나 실측은 정반대(traversal +0.354 > static +0.241). 이 조밀-소풀 substrate에선 순회가 오히려 해로움. **재검정 조건 = 희소 개념-하이퍼그래프 + 대형 책-코퍼스**(substrate 교체 후 재실행해야 유효한 P5).
- **P6(inductive)**: traversal 이득이 미관측 관계 split서 CI 하한>0. *실패 시 corpus 암기로 반증*.
- **null 이빨**: 스크램블 regime서 전 arm |마진|<0.02.

**오늘 착수 가능한 최소** (CPU, 0 LLM): MuSiQue-dev(2417 Q, ≫678 powered) granularity pilot에 **cosine-seeded APPNP traversal arm 추가** → 첫 실제 β_L·β_P·hop_drop 점추정 + σ 확보.

---

## 6. 흡수 core (USER line 6) — 무엇을 흡수하나

> "CHU·라카토트리·비행기맨 툴이 하네스표준을 흡수했듯 HSWM을 완전히 흡수해버려야 한다."

이 4축이 **흡수 가능한 core를 정확히 확정**했다 — vapor 말고 solid만 흡수한다:

- **흡수할 solid core** = ① readout 인터페이스(`retrieve/plan/dispatch = 한 유사도 場의 top-k/softmax/argmax`, Universal Hopfield 항등) + ② `α=pooledᵀMq`(RESCAL/attention 항등) + ③ base-rate 사전분포(`log b`, ACT-R 동형) + ④ supersession을 場 write로. 이건 형식적으로 방어된다.
- **흡수 전 켜야 할 엔진** = cosine-seeded 순회(§5 P5). 이게 님 비전의 심장이자 흡수의 진짜 가치. 순회 없이 흡수하면 "cosine + 얇은 잔여"만 흡수하는 것.
- **흡수하면 안 되는 vapor** = "완전한 연상기억"/"논리 계산기"/"무경사" 라벨. 흡수 시 정확 어휘로: *단일관계 metric + 1-hop(→K-hop) 場 + 선호신호 학습*.
- **3면 흡수 경로**: bhgman(롱기누스=bind/재배맨=plan/오캄=supersede가 場 위 operator로 readout 호출, engineboy와 substrate 공유) / LakatoTree(검색·계획 readout을 판정 substrate로) / CHU(場을 계산가능 하이퍼우주 타입 한 층으로).
- **선결 조건**: §5 P4·P5·P6 통과 = "solid core가 강baseline을 이기고, 순회가 필요하고, 이식 가능"임을 실측한 뒤에만 흡수 착수. (좋은 substrate가 실측 유효임을 전제로만 — INDEX §5.)

---

## 7. 검증된 핵심 인용 (load-bearing, 원문/삼각 확인)

**단일벡터 붕괴**: 2508.21038(LIMIT, ICLR'26) · 2606.18781(EDI) · 2407.12883(BRIGHT) · 2406.16264(NoCha) · 2506.02000(NovelHopQA)
**순회>flat**: 2405.14831(HippoRAG) · 2502.14802(HippoRAG2) · 2510.11541(Quest-GNN, SIGIR'26) · 2604.09666(RAGSearch) · 2604.20850(AAR, inductive 반증) · 2502.12442(HopRAG) · 2601.02744(SYNAPSE)
**형식 지반**: 2008.02217(Ramsauer, Hopfield=attention) · 2202.04557(Universal Hopfield) · 2302.07253(Energy Transformer) · 2411.08590(sparse Hopfield-FY) · RESCAL(Nickel 2011) · 1901.09590(TuckER) · 1810.05997(APPNP) · 1911.05485(GDC) · Collins-Loftus 1975(DOI 10.1037/0033-295X.82.6.407) · ACT-R(Anderson 2004) · SR(Stachenfeld 2017, DOI 10.1038/nn.4650)
**학습=선호신호**: 2305.18290(DPO) · 1706.03741(Christiano) · 2212.07677(von Oswald, ICL≡GD) · 1807.03748(InfoNCE)
**⚠️ vapor 플래그**: "RAG=Hopfield 검색(용량/수렴 정리 포함)" = peer-reviewed 부재, 유추로만. 2025-26 diffusion-RAG preprint군 = landscape only.

---

### 한 줄
님 직관은 4겹으로 옳다 — **cosine은 긴 논리서 무너지고, 場을 순회하면 홉 깊을수록 이긴다.** 단 그 순회는 아직 안 켜졌고(정적 1-hop), 켜는 실험(cosine-seeded K-step 전파, inductive falsifier 포함)이 D 동사와 흡수의 전제다. `α=pooledᵀMq = RESCAL = attention`이 단단한 지반, "논리 계산기·완전 연상기억·무경사"는 정직하게 내려놓는다.
