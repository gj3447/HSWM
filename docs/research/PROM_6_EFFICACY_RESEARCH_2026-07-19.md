# HSWM 효능 갭 — PROM 6축 리서치 (2026-07-19)

> **트리거**: 사용자 질문 — "cosine보다 효능이 낮은 거냐? 내 생각엔 cosine은 단어임베딩 위주인데 HSWM은 논리적 내용도 웨이트 활성화하면서 긴 문장·책 단위에서 cosine보다 유의미하게 좋다. 유능함도 이긴다. 아직 개념적으로만 있고 다듬어야 할 게 많다. 여기 저장하고 prom 깊게 돌려서 정리해라 — 이건 깊은 학문이다." (`HSWM/내가 주는 말.txt`)
> **방법**: 6축 병렬 리서치 subagent (각 4 sub-question, 웹/arXiv grounding). 진단은 `gj3447/HSWM` repo의 A/B 실측(`ab_p5_full_*.json`)에서 출발.
> **관계**: 기존 canon `THEORY/재배맨/HSWM_STANDARD.md` §0.3/§0.4 + `WHY_NO_COGNITIVE_UPLIFT_2026-07-19.md`를 **반증 아닌 문헌 grounding으로 보강**. 충돌 없음. 열린 갭 3개(긴문서 미측정 / 약한 baseline / 통계 엄밀화)를 채우는 게 목적.

---

## 0. 한 줄 결론

**HSWM의 현재 *측정된 범주*는 "reasoner"가 아니라 judgment 신호로 갱신되는 시멘틱 가중장(memory substrate)이며, 그 효능은 판사(judge) 품질을 신호 상한으로 갖는다. 데이터에서 관측된 2wiki 승리 / MuSiQue 패배는 결함이 아니라 bias-variance + 벤치 난이도 이론이 정확히 예측하는 crossover다. 사용자 직관("긴 문장·책 단위에서 cosine을 이긴다")은 아직 *검증된 적 없는* 유일한 살아있는 가설이며, local-vs-global 축 위에서 falsifiable하게 설계 가능하다.**

---

## 1. 진단 — 왜 2wiki 이기고 MuSiQue 지나 (실측)

`gj3447/HSWM` full P5, 3 runs n=100, judge/reader = qwen3-27b, matched budget 100==100:

| run | judge F1 | cosine F1 | **HSWM F1** | direct F1 | HSWM−direct | sup_recall@k (h/d) |
|---|---|---|---|---|---|---|
| 2wiki s7 | **0.969** | 0.657 | **0.721** | 0.679 | **+0.041** | 0.88 / 0.945 |
| MuSiQue s7 | 0.865 | 0.410 | 0.444 | **0.701** | **−0.257** | 0.608 / 0.837 |
| MuSiQue s13 | **0.777** | 0.339 | 0.459 | **0.691** | **−0.232** | 0.631 / 0.857 |

**핵심 변수 = 판사 품질. HSWM 성적이 judge F1을 그대로 따라간다.** 모든 run에서 HSWM > cosine(+0.035~+0.12), 그러나 판사가 강할 때만 direct까지 넘는다.

**단일 근본원인**: HSWM의 weight field는 LLM 판단의 함수. 판사가 좋으면(2wiki) 그 좋은 판단을 안정적으로 캐시해 라이브 단일추론(direct)의 노이즈를 이기고, 판사가 능력 밖이면(MuSiQue 4-hop) 틀린 판단을 그대로 캐시해 밀린다.

---

## 2. Consensus — 6축이 수렴한 것 (문헌 grounding)

### C1 — "판사 = 천장"은 *신호(정보) 상한*으로 엄밀히 참, 단 metric 상한은 아님 (축1)
- **DPI**: `truth → judge → HSWM-weights` 마르코프 사슬 → `I(truth; HSWM) ≤ I(truth; judge)`. 후처리는 판사가 안 나른 ground-truth 신호를 만들 수 없다. (Cover & Thomas; Gao et al. 2023 *Scaling Laws for Reward Model Overoptimization* arXiv:2210.10760)
- **단 상한은 *상호정보*이지 F1 같은 단일 metric의 pointwise 상한이 아니다.** "HSWM_F1 ≤ judge_F1"은 틀린 진술. 옳은 진술 = "HSWM는 극한에서 판사의 정보를 체계적으로 초과 못 한다."
- **캐시가 라이브를 이기는 유일한 합법 경로 = 분산 감소(variance reduction)**, 신호 증폭 아님. Born-Again Nets(1805.04770), batched self-consistency(2505.12570)가 학생>교사를 만드는 메커니즘과 동일.
- **정확한 선행연구 analog = Rank-DistiLLM(2405.07920)**: "LLM 순위에서 증류한 cross-encoder는 teacher까지만 도달, 173배 빠를 뿐, teacher를 못 넘는다." **HSWM = amortization이지 signal amplification이 아니다.**

### C2 — novelty 판정 = INCREMENTAL, 방어가능한 novel corner는 딱 하나 (축2)
- HSWM의 `W = cosine + λ_b·log(salience) + λ_j·judgment`는 **Park et al. 2023 Generative Agents 검색점수의 near-duplicate** (cosine relevance + 내재 importance + 제3항). Park는 이미 검색+계획을 같은 점수로 통합함.
- 하이퍼그래프 substrate = HyperGraphRAG(2503.21322), 비파괴 supersession = Zep/Graphiti(2501.13956)·MemStrata. 전부 선행.
- **유일하게 안 뚫린 코너 = "supersession을 별도 시간규칙이 아니라 *검색/dispatch와 똑같은 W 場의 readout*으로 접기"** — 사용자의 **검색=계획=supersession 4중 동일시** 직관 그대로. 어떤 선행연구도 이 3-way collapse는 안 했다.
- ⚠️ **정면 counter-thesis**: MemStrata는 "결정론적 supersession이 점수기반보다 by construction 낫다"고 주장. 이걸 falsifiable하게 이겨야 NOVEL 성립.

### C3 — 2wiki win / MuSiQue loss = bias-variance × 난이도 crossover (축3·축5)
- **캐시 = 분산↓, 편향은 고정.** LLM 판정은 항목당 최대 ~50% 뒤집히는 고분산(2412.12509). 2wiki는 판사 평균이 좋아 분산감소가 순이익. MuSiQue는 판사가 능력 밖 → bias 지배 → 캐시가 "confidently-wrong"을 저장.
- **MuSiQue는 일부러 "지름길 불가"로 설계됨.** DiRe cheatable: HotpotQA 27.6% / 2wiki 35.3% / **MuSiQue 8.3%** (Trivedi et al. TACL 2022, 2108.00573).
- **2wiki win의 정체 = 구조적 지름길 의존 의심.** HippoRAG 실측: 구조retrieval의 all-recall 우위가 2wiki +20~38pt인데 MuSiQue +3~6pt로 증발(2405.14831). → 2wiki의 +0.04는 substrate 우수성이 아니라 template artifact exploit일 수 있음.
- recall 0.88→0.63 = **홉수 기하급수 감쇠 P^N**의 예측치와 일치. judge F1 0.97→0.78 = pointwise 판사가 "조합해야 relevant"한 패시지를 못 봄(context에 3-5× 덜 주목, 2606.28050).
- **결론: MuSiQue 패배는 HSWM 결함이 아니라 judge-ceiling + non-decomposability의 예상 결과.**

### C4 — 난이도 의존 = difficulty-gated hybrid이 정석 처방 (축3·축5)
- Snell 2024(2408.03314): 라이브 추론의 가치는 난이도 의존. 쉬운 문제엔 낭비, 어려운 문제엔 필수.
- Ma 2023(2303.08559): 쉬운 샘플은 싼 모델, 어려운 샘플만 LLM escalate. → **HSWM 설계 함의: 저홉/쉬운 쿼리는 캐시, 고홉/어려운 쿼리는 라이브 rerank로 escalate** → win은 취하고 loss는 피함.

### C5 — cosine-floor는 selection set에서만 확정적 (축6)
- `W = cosine + λ·ReLU(residual)`, λ=0 허용 = **단일스텝 boosting on frozen base learner** (Friedman 2001) = **ResNet residual**(1512.03385)의 동형. λ→0이 base 복원.
- **그러나 floor는 λ를 고른 검증셋에서만 deterministic.** held-out에선 winner's-curse로 확률적 보장(선택 optimism만큼 test gain이 깎임).
- **λ→0(실KG) vs +0.116(synthetic)은 버그 아님** — Bruch 2023(2210.11934): 검증튜닝 fusion 가중치는 분포이동 시 under-transfer. synthetic은 val=test라 optimism이 안 갚아짐. **정상 행동.**
- 처방: "provably never worse" 문구 금지 → "held-out에서 검증 gain의 표본오차 한도 내 high-probability로 no-worse, 유의하지 않으면 λ=0=cosine." + **RRF를 tuning-free baseline으로** 추가(못 이기면 학습residual이 복잡도값 못 함).

---

## 3. Divergence / 정직한 반증 위험 (닫지 않고 남김)

- **D1 (프레임 이중성)**: reasoner 기준 → cognitive uplift **REFUTED**(§0.3 HSWM_LOCAL_RECORD `rejected`, MuSiQue −0.26). substrate 기준(같은 reader, cosine=vector-RAG) → §0.4 **POOLED +0.073 p<0.0001 유효**. 둘 다 참. 어떤 질문을 하느냐가 답을 정한다. HSWM은 #8 입체운행구름 substrate 군단장이라 substrate 기준이 본령(인프라에 IQ 묻기=범주오류).
- **D2 (2wiki win 귀속)**: +0.04가 (a)진짜 구조weight 우수성인지 (b)variance-reduction인지 (c)template artifact exploit인지 **미분리**. 축3·축5 둘 다 (b)(c) 가능성 경고. → matched-budget 2×2 통제 없이는 귀속 불가.
- **D3 (novelty 방어선)**: 공식·하이퍼그래프·supersession 데이터모델·"학습된 場" 각각은 전부 반증가능. NOVEL 주장은 오직 "supersession-as-field-readout" 코너로 좁혀야 생존.
- **D4 (통계 미충족)**: §0.4 POOLED는 n=300으로 축6 few-query 우려를 일부 넘지만, **seed variance 미보고 + prereg 미등록 + RRF/강baseline 미비교**는 여전히 열림.

---

## 4. Open Questions = 사용자 3갭 (a/b/c)

- **(a) cosine은 약한 baseline** — BM25/PPR-확산활성화(HippoRAG)/RAPTOR/late-chunking/Dense-X/discourse-retrieval 같은 **센 substrate**를 이겨야 진짜 substrate 우위. cosine만 이기면 null-strength.
- **(b) 긴 문서/책 단위 미측정** — 사용자 핵심 직관. 현재 실험은 전부 짧은 멀티홉 QA. **벤치 자체가 없다.** ← 최우선.
- **(c) matched-budget A/B 통계 엄밀화** — +0.04류가 진짜냐 노이즈냐. prereg + power분석 + paired permutation + seed variance.

---

## 5. 권장 후속 — 실험 설계 3개 (착수순)

### 실험 B (최우선) — 긴문서 local-vs-global 벤치 (사용자 직관 검증)
- **가설을 상호작용 효과로 재정식화**: `advantage(HSWM−baseline)`가 (문서길이 × global질문)에서 **커지고** local/짧은건 ≈0.
- **데이터**: 1차 **NoCha**(소설 67권, local/global 라벨 native) → 2차 NarrativeQA(full-book) + QASPER(gold evidence span) → **DeepMind LIMIT**(2508.21038)를 tool-fitness prefilter(cosine이 set-structured에서 실패하는지 먼저 확인).
- **baseline ladder(전부 필수, strawman 금지)**: naive cosine / late-chunking(2409.04701) / Dense-X proposition(2312.06648) / **RAPTOR(2401.18059)** / discourse-aware(2506.06313) / full-context stuffing.
- **headline = 평균 아님 → 상호작용항**: `score ~ method × question_type × length`의 `HSWM:GLOBAL`·`HSWM:GLOBAL:length` 계수 + CI.
- **CONFIRM**: GLOBAL 층에서 HSWM이 RAPTOR 포함 전 baseline 유의 초과 **AND** 격차가 길이에 단조 증가, LOCAL에선 ≈. **REFUTE**: GLOBAL 무격차 / 길이로만 설명 / RAPTOR·late-chunk 못 넘음 / proposition baseline으로 바꾸니 소멸(=청킹 artifact).

### 실험 A — matched-budget A/B 귀속 분리 (2wiki win 정체 규명)
- **2×2**: {캐시=1샘플, 캐시=k샘플} × {direct=1샘플, direct=k샘플 self-consistency}. **direct도 k샘플 주면 HSWM win이 사라지면 → win=variance reduction이지 amortization 아님**(더 약한 주장).
- matched budget에 **offline precompute 비용 접기**: `amortized = cache_build_calls/N + query_cost`, break-even N 공개.
- **홉수/난이도 stratify + per-stratum F1 + bootstrap CI**. 판사 accuracy·variance를 데이터셋별 직접 측정(가설 직접 검증).

### 실험 C — 통계 프로토콜 (전 실험 공통 게이트, prereg 후 unblind)
- 3분할: **λ-selection / locked-test / (필요시 nested inner CV)**. 헤드라인은 locked-test에서만.
- 1차 검정 = **paired 2-sided permutation**(per-query Δ sign-flip ≥10k), 보조 = paired bootstrap CI. Wilcoxon/sign/unpaired 금지.
- **power**: σ_Δ 실측 → `n ≈ 8·(σ_Δ/minD)²`. minD=0.03이면 σ_Δ=0.2일 때 ~200쿼리, 0.1일 때 ~50. **<30쿼리는 underpowered 선언.**
- **≥5 seed, 전 seed 점수 + mean±std**. seed std ≳ gain이면 "seed noise 내".
- 다중데이터셋 주장 시 Benjamini-Hochberg. synthetic-dev는 mechanism sanity-check이지 성능결과 아님.
- **prereg falsifier**: primary에서 p>0.05 OR bootstrap CI가 0 포함 → no-gain 선언(사전확정).

### 실험 D (선택, novelty용) — supersession-as-field-readout vs 결정론적 supersession
- MemStrata류 결정론 supersession layer 대비, W-threshold 유도 supersession이 **더 낫거나 더 단순함**을 falsifiable 시연. 이게 유일한 NOVEL 방어선.

---

## 6. 핵심 인용 (검증됨)

**Ceiling/DPI/증류**: Gao 2210.10760 · Hinton 1503.02531 · Furlanello Born-Again 1805.04770 · Rank-DistiLLM 2405.07920 · RankZephyr 2312.02724
**선행/novelty**: Park Generative Agents 2304.03442 · HyperGraphRAG 2503.21322 · HippoRAG 2405.14831 · Zep 2501.13956 · GNN-RAG 2405.20139
**cache/variance/난이도**: Snell 2408.03314 · batched self-consistency 2505.12570 · permutation self-consistency 2310.07712 · ColBERT 2004.12832 · Ma-reranker 2303.08559
**MuSiQue/멀티홉**: MuSiQue 2108.00573 · 2wiki 2011.01060 · judge task-asymmetry 2606.28050 · Baleen 2101.00436
**긴문서 벤치**: NoCha 2406.16264 · NarrativeQA(TACL 2018) · QASPER · ∞Bench 2402.13718 · NovelQA 2403.12766 · RAPTOR 2401.18059 · late-chunking 2409.04701 · Dense-X 2312.06648 · LIMIT 2508.21038 · Dolce 2409.06338
**floor/통계**: Friedman 2001(GBM) · ResNet 1512.03385 · Bruch fusion 2210.11934 · RRF(SIGIR 2009) · Smucker 2007 · Sakai topic-set-size 2016 · Card *Little Power* 2010.06595 · Demšar JMLR 2006

> ⚠️ 2602~2607.* arXiv id 일부는 2026 preprint 스탬프로 검색됨 — load-bearing 정량 주장은 각각 2020~2024 확정 소스로 교차확인됨. 출판 전 id 재확인 필요.

---

## 7. 다음 액션

1. 이 문서 = HSWM 폴더 첫 결정화. 실험 B(긴문서)가 사용자 직관의 유일 미검증 가설 → **최우선 착수**.
2. 실험 C 통계 프로토콜을 `gj3447/HSWM` repo `falsifier.py`에 prereg로 배선(paired permutation + power + seed).
3. KG 결정화는 홈 KG MCP 복구(P3 이관 컷오버) 후 replay. 현재는 이 md가 정본.
4. 최종 흡수(사용자 txt): CHU/폐기된 외부 판정기/비행기맨이 하네스표준 흡수했듯 HSWM 흡수 = 실험 B/A가 substrate 우위를 확증한 *후*의 작업.
