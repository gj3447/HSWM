# PROM 검색 → HSWM 레이어 빌더 연구 (2026-07-21)

> ⚠️ **정직 한 줄 (Wave 1 판정, 2026-07-22)**: semantic weave 이득은 equal-compute control을 이기지 못함(LakatoTree partial) — 전체 프로그램 degenerating, 이후 모든 semantic weave 주장은 이 한계 하에서만 유효. (P4 verdict 원문 = §1 판정 블록. P1 binding density 자체는 progressive — lexical CONTAINS 0.0 대비 gap 0.2121, MC-null z 6.56. 단 P4에서 1패스 Jaccard 0.4242가 semantic 0.2121을 이김.)

> **한 줄**: 프로메테우스(PROM)의 검색을 "맹목 웹검색"에서 "인터넷+내부KG를 가중 시멘틱 하이퍼엣지로 엮어 HSWM 레이어를 적층하는 것"으로 승격시키려는 연구. **자가비판 우선** — 순진한 해법은 실측으로 반증하고, 살아남은 구조만 남긴다.
>
> - **LakatoTree**: `LakatosTree_PromSearchHSWM_20260721` (예측 사전등록 + Dung 자기공격)
> - **USER 정전 (2026-07-21)**: "prom 이 인터넷과 내부 kg 의 hswm 레이어를 쌓는 연구인거야."
> - **코드/영수증**: 이 폴더 (`prom_consensus_bench.py` / `prom_consensus_real.py` / `prom_legend_recall.py` + `EVIDENCE_*.json`)

---

## 0. "HSWM 이 그렇게 위대하냐?" — 정직한 답

**아니다. "위대"는 과장이다. 그러나 "정직하게 검증된 substrate"는 맞다.** 근거는 과장이 아니라 실측이다 (상세 = `../INDEX.md` §1–4, `gj3447/HSWM` repo).

| 주장 | 판정 | 근거 |
|---|---|---|
| **메모리 substrate로서 다른 검색구조보다 낫다** | ✅ **CONFIRMED** | 5-substrate 사다리 1위. F1 0.541 vs cosine 0.469 (+0.073, p<0.0001, n=300, 추론 LLM콜 0). bm25/ppr/rrf 전부 이김 |
| **긴 논리 사슬일수록 우위 확대** | 🟡 down payment | 2홉 무승부 → 4홉 +0.064~0.072 (홉↑ monotone). 단 **문서-길이(책 단위) 차원은 미검증** |
| **reasoner로서 direct-LLM보다 낫다** | ❌ **REFUTED** | 2Wiki만 이김. "substrate에 IQ 묻기 = 범주오류" |
| **"웨이트로 돌아다닌다"(query-time 순회/spreading activation)** | ❌ 거의 OFF | T4/T5/traversal_bench 인증 전부 **TRAVERSAL_OFF** — 정적 학습 필드가 이기고, query-time 전파는 specificity 파괴 |
| **novelty (선점 안 된 새 아이디어)** | 🟡 얇음 | prior-art 재판 251편: 청구항 7건 중 3 격추 / 4 생존(얇은 재조합). 산업(GraphRAG/HippoRAG) 독립 수렴. 유일 미선점 = supersession을 검색·계획과 같은 場에 접기 |

**결론**: HSWM의 위대함은 **딱 하나 — "가중 시멘틱 substrate가 flat 검색보다 유의하게 낫다"가 실측으로 참**이라는 점이다. 그 위의 큰 꿈들(순수 하이퍼그래프 구조가 부하를 진다 / 순회로 돌아다닌다 / 책 단위서 압승 / 근본적으로 새롭다)은 **아직 미증명이거나 반증됐다.** 그리고 리프트의 몸통(~95%)은 임베딩 정렬이지 하이퍼그래프 구조 자체가 아니다. **정직하게: HSWM = 검증된 substrate + 열린 큰 가설들. "위대한 발명"이 아니라 "정직한 엔지니어링."**

> 왜 그래도 계속 파나: 검증된 그 한 조각(substrate 우위)이 실제고, 우리 생태계(비행기맨/CHU/라카토트리)가 흡수할 수 있는 실 인터페이스이기 때문. 과장 없이 그 한 조각을 넓히는 게 이 연구다.

---

## 1. 이 연구가 새로 얹은 것 (2026-07-21)

기존 HSWM 연구는 **QA 검색(retrieval)** 축에서 substrate를 검증했다. 이 연구는 **다른 모서리** — PROM의 **합의탐지(consensus)와 레전드 발견(discovery)** — 에서 같은 substrate 주장을 시험한다. 그리고 독립적으로 **HSWM의 "형태(shape)" 주장에 새 증거**를 얹었다.

### 진단 (D1): 현 PROM 검색은 lexical-shallow

`SKILLS/prometheus/SKILL.md` v6.3 실측 — 검색층 6대 결함:
1. Step 2.5 하계 pre-fetch = `CONTAINS` 부분문자열 (의미검색 아님)
2. Step 4 합의탐지 = recommendation **문자열 동일성** 그룹핑 (line 558)
3. cross-encoder 재랭킹 전무
4. 하이브리드 dense+sparse RRF 융합 전무
5. contextual anchoring 전무
6. citation-graph / agentic-RAG 반복탐색 전무

→ haiku N개가 각 axis 셀 1회 맹목 웹검색만. **인용 그래프를 타고 레전드repo(예: `bojieli/ai-agent-book`)로 엮여 들어갈 경로 자체가 구조적으로 없다.** 우리 인식론층(LakatoTree/나생문/placebo A/B)은 깊은데 **object-level 검색만 얕은 비대칭.**

### 판정 (Wave 1, 2026-07-22) — P1/P4 LakatoTree 원문

> 실험: `prom_p1_binding_density.py` → `evidence/EVIDENCE_p1_binding_density_2026-07-22.json` / `prom_p4_equalcompute_ab.py` → `evidence/EVIDENCE_p4_equalcompute_2026-07-22.json`. gold = `data/binding_gold_p1.json` (n=66, calibration 33 / eval 33, 후보풀 113 = 35 target + 78 distractor), τ = 0.592758 (calibration-only MC-null). 사전등록 metric 무변경.

**P1-binding-density → verdict `progressive`** (judged_at `2026-07-22T01:33:10.052334+00:00`)

- value = held_out_binding_density(semantic) = **0.2121** (7/33; baseline 0.05 + noise 0.03 초과, delta 0.1621) / novel_measured = semantic_minus_lexical_binding_gap = **0.2121 ≥ 0.2** / **MC-null z = 6.56** (perms 2000, null_mean 0.0279, null_std 0.0281)
- lexical(현 Step 2.5 정규화 CONTAINS 재현) binding_density = **0.0** (0/33, any_contains_match 0) — **D1 lexical-shallow 진단 실측 재확인**
- Goodhart 가드 precision = 0.4667 (fires 15 / correct 7 — τ-fire의 절반가량이 비gold top-1, 한계 투명 기록)
- 서버 verdict 원문:

```json
{"ok": true, "freshen": false, "verdict": "progressive", "delta": 0.1621, "novel": true, "lakatos": "progressive", "metric_verdict": "progressive", "requires_human": false, "script_sha_server_verified": false, "judge_script_sha": "ec0d3bf03985406f5aefcb3d3594de6db3f02808263f73ee191fcf0fd2870e57", "attested_by": null, "eureka": {"felt": true, "true": true, "hallucinated": false, "reasons": [], "bf": 6.0}, "rule": "improved=True, novel=True, noise_band=0.03, novelty_sense=zahar_use_novelty", "replay": "python /Users/lagyeongjun/CD/SYMPOSIUM/HSWM/prom_search_hswm/prom_p1_binding_density.py /Users/lagyeongjun/CD/SYMPOSIUM/HSWM/prom_search_hswm/evidence/EVIDENCE_p1_binding_density_2026-07-22.json"}
```

**P4-equal-compute-control → verdict `partial` / lakatos `degenerating`** (judged_at `2026-07-22T01:47:20.063251+00:00`) — **프로그램 존폐 게이트(tree hard core 불변식 iii)가 null**

- value = semantic_minus_equalcompute_binding_gain = 0.2121 − 0.1818 = **0.0303** (baseline 0.0 + noise 0.03을 0.0003 차로 초과 → improved=True) / novel_measured = semantic_layer_over_more_blind_search_gap = **0.0303 < 0.1 → novel 미달** / **MC-null z = 1.0** (perms 2000, null_mean −0.009, null_std 0.0393 — gap이 null과 통계적으로 구분 안 됨)
- 3-arm (동일 gold·pool·τ; equal-compute 토큰예산 13438976 vs semantic 3090702 = 4.35×, equal_compute_verified=true): semantic_weave **0.2121** / equalcompute_lexical(변형 429개 blind-RRF control) **0.1818** / lexical_1x(Jaccard 1패스) **0.4242**
- 추가 정직 anomaly (판정 불사용): 단순 1패스 Jaccard(0.4242)가 τ-게이트 semantic(0.2121)과 equal-compute RRF control(0.1818) **양쪽을 이김** — D1 "lexical-shallow" 진단은 CONTAINS(0.0)에 한정 유효하며, Jaccard 수준의 lexical만으로도 semantic 초과. 변형다발+RRF는 오히려 1패스 Jaccard보다 나쁨(변형 희석).
- 서버 verdict 원문:

```json
{"ok": true, "freshen": false, "verdict": "partial", "delta": 0.0303, "novel": false, "lakatos": "degenerating", "metric_verdict": "partial", "requires_human": false, "script_sha_server_verified": false, "judge_script_sha": "29e797e881b65ef0ed40ffca0be12ee7e15d726f8595f657ad0846b7dba46045", "attested_by": null, "eureka": {"felt": true, "true": false, "hallucinated": true, "reasons": ["novel_unconfirmed", "bf_marginal:1.000<=3.162"], "bf": 1.0}, "rule": "improved=True, novel=False, noise_band=0.03, novelty_sense=zahar_use_novelty", "replay": "python /Users/lagyeongjun/CD/SYMPOSIUM/HSWM/prom_search_hswm/prom_p4_equalcompute_ab.py /Users/lagyeongjun/CD/SYMPOSIUM/HSWM/prom_search_hswm/evidence/EVIDENCE_p4_equalcompute_2026-07-22.json"}
```

**축소 (사전 고정 해석 그대로, 재해석 없음)**: 예측 "semantic weave가 equal-compute control을 이긴다"는 novel 수준 확증 실패 — tree hard_core 불변식 (iii)이 이 노드 자체이므로 **전체 프로그램 degenerating**. semantic weave 이득은 equal-compute control을 이기지 못함(LakatoTree partial) — 전체 프로그램 degenerating, 이후 모든 semantic weave 주장은 이 한계 하에서만 유효. 아래 ML5–ML19·T5 서술은 그대로 보존하되 이 조건 하에서 읽어야 한다 (축소는 삭제가 아님 — Eilu va-Eilu).

---

## 2. 영수증 3건 — 전부 정직한 RED

모든 실험: 결정론 스크립트 + 로컬 다중언어 임베딩(`paraphrase-multilingual-MiniLM-L12-v2`) + 사전등록 예측 + MC-null 통제 + precision 동반. LakatoTree가 판정(자기채점 아님).

### P2 (toy) — `prom_consensus_bench.py` → verdict **degenerating**
| 방법 | recall | precision |
|---|---|---|
| **현 PROM (lexical 문자열동일)** | **0.0** | **0.0** |
| semantic (임베딩 τ=0.5) | 0.667 | 0.216 |

- gap 0.667 ≥ 0.15 임계 통과처럼 보이나 **MC-null z=1.51 < 3.0** (우연 대비 무의) + precision 0.216 (과병합).
- **eureka hallucinated=true.** → D1 진단은 실증(lexical 0), naive semantic은 미검증.

### P2b (실 KG data) — `prom_consensus_real.py` → verdict **equivalent / degenerating**
gold = Neo4j 홈canon `prom16-gfs-2026-05-21`, RF 13개 / consensus 8개.

- **핵심 발견**: 실 PROM consensus는 **overlapping hypergraph** — 한 RF(예 C2)가 8개 consensus 중 4개에 **동시 소속**. 현 PROM의 partition(disjoint 그룹) 모델은 이걸 **구조적으로 표현 불가**.
- lexical recall **0.0** 재확인. semantic recall 0.44 / precision 0.88이나 **MC-null z=0.19 (랜덤과 무구별)** + **cosine separation −0.038 (음수: 같은-클러스터가 오히려 덜 유사)**.
- → **recommendation 텍스트 유사도 = consensus의 잘못된 계측기.** naive semantic-on-recommendation **REFUTED.**
- **부산물 = HSWM 형태 주장의 새 증거**: 실 consensus가 overlapping hypergraph라는 건 "지식은 가중 하이퍼그래프"라는 HSWM 형태 가설을 **QA 검색이 아닌 KG consensus 구조라는 독립 모서리에서** 지지한다.

### P3 (레전드 recall, cross-lingual) — `prom_legend_recall.py` → verdict **partial / degenerating**
corpus = `ai-agent-book`(중국어) 1425 청크 + distractor 15. 질의 = 한/영 (SYMPOSIUM 어휘).

| anchor 언어 | lexical recall@5 | semantic recall@5 |
|---|---|---|
| 라틴 (harness/RAG/KV/Coding) | 0.75 | **1.0** |
| 중국어 (评估/上下文/多Agent) | 0.667 | 0.667 |
| **전체** | 0.71 | 0.86 |

- gap 0.14 < 0.3 임계 → **novel 미확정.**
- **내 실험 설계 결함까지 노출**: 고빈도 중국어 anchor(评估 327회)는 lexical 점수 0이어도 tie-break로 top-5에 우연히 걸려 baseline을 부풀림. → 이 retrieval-proxy는 cross-lingual 갭을 깨끗이 못 보여준다.

---

## 3. 세 영수증이 함께 말하는 것

1. **진단(D1)은 참** — 현 PROM 검색은 toy에서도 실 KG에서도 의미상 같은 것을 **recall 0.0**으로 못 묶는다.
2. **순진한 lexical→semantic 치환은 전부 degenerating** — 우리가 심어둔 self-critical 게이트(null 통제 / precision / eureka-hallucination)가 순진한 승리를 **매번** 기각했다. 지표만 봤으면 세 번 다 속았다.
3. **HSWM 형태(overlapping hypergraph)는 새 증거를 얻었다** — 단, 이는 *형태(shape)* 확증이지 *작동 메커니즘(embedding-on-recommendation)* 확증이 아니다. 둘을 혼동하면 안 된다.

**→ 이게 정확히 §0의 답을 재확인한다: HSWM은 형태로선 옳은 방향(또 한 번 지지받음), 작동 해법으로선 순진한 버전이 반증됨. "위대"가 아니라 "정직하게 좁혀지는 중."**

---

## 4. multi-layer 조사 (ML1–ML4) — USER "여러 층" 가설의 정직한 해소

USER 정정(2026-07-21): "HSWM 연구는 계속 이어진다. 레이어가 여러 층이 아니어서 그랬던 것 같다." → 4단계 판정:

| # | 실험 | 층 성격 | gold | 결과 |
|---|---|---|---|---|
| ML1 | co-activation | 같은 텍스트→8 thesis 재투영 | GFS(degenerate) | 미확인 (계측기 부적합) |
| ML2 | binary co-activation | 재투영 (blind/구조화) | badiou(balanced) | **REFUTED** (과활성) |
| ML3 | profile cosine (threshold-free AUC) | 재투영 (blind/구조화) | badiou | **REFUTED** (단일층 0.643 > 다층 0.595/0.555) |
| **ML4** | **field-of-fields 융합** | **독립 모달리티** (semantic 텍스트場 + lexical 인용-엔티티場) | badiou | **✅ VINDICATED** |

**해소 (핵심)**: "여러 층"은 **재투영(같은 텍스트를 여러 각도로)일 땐 무익**(ML1–3, dense 임베딩이 이미 다차원이라 투영=정보손실) — **독립 모달리티/소스일 땐 유익**(ML4).

- **ML4**: entity場(인용학자 Jaccard, lexical) AUC **0.708** > text場(semantic) 0.643. RRF 융합 0.697. **+0.065**. hypothesis_test 전부 TRUE. entity場이 semantic이 놓친 role축(secondary→Hallward/Bosteels, critique→Laruelle/Meillassoux)을 잡음.
- **왜 이게 맞나**: PROM 정의("**인터넷場 + 내부KG場**의 hswm 레이어를 쌓는")와 HSWM 정전(field-of-fields, 場 간 weight-semantic 롱기누스 바인딩)이 정확히 **독립 소스 場**을 말한다. USER 직관은 옳은 operationalization(독립場)에서 참.

**정직 경계 (caveat)**: (a) 이 KG는 RF 비-consensus 이웃이 균일 → **진짜 KG-구조場은 부재**, entity場은 텍스트서 lexical 추출한 **하한 프록시**(진짜 internet場+KG場 아님). (b) n=24 단일 gold, toy급. (c) ML4는 "독립場이 도움된다"는 *방향*을 지지할 뿐, 실제 internet+KG 場 융합은 미구현. → 다음 = 진짜 독립 소스(웹검색 결과場 + KG-임베딩場)로 재현.

**기존 HSWM 정전과의 정합**: `../INDEX.md` §1 "리프트 본체=임베딩, 순수 하이퍼그래프 구조 부하 못 짐"을 ML3가 독립 재현(재투영 무익). ML4는 그 위에 "**독립 소스場은 다르다**"를 얹음 — substrate 우위의 새 미개척 축.

### ML5 — 진짜 판정: REAL 인터넷場 + KG場 (`prom_realfields_ab.py`)

ML4는 lexical 프록시. ML5는 **실제 소스**: web=WebSearch(2026-07-21), kg=Neo4j 홈canon. task=ai-agent-book legend recall(6개념), 4場(raw/web/kg/fused RRF), metric=MRR.

| 場 | mean MRR | 판정 |
|---|---|---|
| raw (질의만) | **0.917** | 이미 천장 근처 |
| web (실 인터넷) | 0.867 | — |
| kg (실 내부KG) | 0.639 | — |
| fused (RRF) | 0.917 | = raw (net gain 0) |

**집계는 net-zero지만 per-concept가 진실**:
- **multi-agent**: raw 0.5 → **web 1.0** → fused 1.0 — **실 인터넷場이 질의 실패를 구조** (진짜 도움 실증)
- **coding-agent**: web **0.2** → fused 0.5 — off-domain 英 웹요약이 中 책서 멀어져 **해침**
- **rag / evaluation**: kg **0.25** — 우리 KG 그 개념 커버 빈약 = **노이즈로 해침**
- harness / kv-cache: raw 이미 1.0 (여지 無)

**최종 해소 (조건부)**: field-of-fields는 **REAL이나 UNCONDITIONAL 아님**. 독립場은 (a)base 질의가 실패하고 (b)場이 관련 신호를 가질 때만 도움 — **노이즈場/off-domain場은 오히려 해친다**. → **blind RRF는 틀렸고, field-quality 가중 融合 = 우리 정전 `7cmd-measurement-driven-conditional-dispatch`(각 場의 신호를 측정 후 threshold 넘을 때만 dispatch)가 정답.** 이게 PROM을 실제로 고칠 설계: 인터넷場+KG場을 무조건 섞지 말고, 場별 관련도를 측정해 가중.

**정직 경계**: legend-recall이 raw에 너무 쉬워(천장) 순 이득 관측 여지가 작았다. 다음 = base가 실패하는 어려운 task + 場별 관련도 gate 구현.

### ML6 — PROM→HSWM 엔진 구현 + 실검증 (`hswm_fusion.py` / `test_hswm_fusion.py`)

THEORY_GROUNDING이 도출한 fix("blind 융합 말고 場-품질 가중")를 실 엔진으로. `hswm_fusion.py` = PROM Step3/4 프리미티브(pluggable weighting: blind/confidence/agreement/gated). ML5 실데이터서 4전략 A/B:

| 전략 | mean MRR |
|---|---|
| raw_only / **blind(=ML5)** | **0.917** |
| agreement | 0.889 |
| confidence / gated_agreement | 0.833 |

**→ 내 값싼 가중 휴리스틱 전부 blind를 못 이김 (best=blind).** 근본원인(깊은 발견): helpful web場(multi-agent, raw와 agreement 0.2)이 harmful web場(coding-agent, agreement 0.29)보다 **agreement가 낮다** — 도움되는 場은 raw와 *달라서*(새 정보) 돕고, 해로운 場은 off-domain이어도 topically 겹쳐 agreement 높음. **agreement/confidence는 helpful/harmful을 구분 못하는 신호. 단일 임계 불가.**

**함의**: Cormack 2009("무가중 RRF 이기기 어려움") + DAT(arXiv:2503.23013, **LLM judge로 per-query weight**)를 실증. **값싼 통계 QPP로는 PROM→HSWM fix 불가 — LLM 기반 場-관련도 판정이 필요.** 엔진(인터페이스·게이트·가중 배선)은 準비 완료, weighting 함수만 LLM-judge로 교체하면 됨(dgx vLLM qwen3.6-27b 사용 가능).

### ML7 — 완성: LLM-judge 場-품질 가중 (`test_hswm_llm_judge.py`, DAT식)

ML6이 요구한 LLM-judge를 실구현. dgx vLLM(qwen3.6-27b, thinking off)이 각 場의 top-1 검색청크를 "질의에 답하나 0-10" 판정 → weight=score/10 → external-weighted RRF. 18 vLLM콜 캐시.

mean MRR: raw 0.917 = blind 0.917 > **llm_judge 0.889**. **집계론 여전히 blind 못 이김** — 하지만 **기제는 정성적으로 정확**:

| concept | raw | blind | llm | LLM 판정 |
|---|---|---|---|---|
| rag | 1.0 | 1.0 | 1.0 | raw top-1=**0**(RAG아님), web=**8**(정답)→web가중 ✅ |
| multi-agent | 0.5 | 1.0 | 1.0 | web=**10**(정확)→유지, raw실패 구조 ✅ |
| evaluation | 1.0 | 1.0 | 1.0 | 세 場 top-1 전부 0→aux 배제→raw ✅ |
| coding-agent | 1.0 | 0.5 | **0.333** | web=**8**(진짜 코딩에이전트 청크, 옳음) but 리터럴 anchor 無 → **gold artifact** |

**결정적 해석**: 유일 하락(coding-agent)은 LLM이 틀려서가 아니라 **anchor-string gold가 crude**해서다 — LLM은 web場의 관련 청크를 정확히 8점 줬는데, 그 청크에 리터럴 "Coding Agent"가 없어 gold가 non-gold 처리. **LLM-judge 기제는 옳고(rag/eval/multi-agent 전부 올바른 per-field 결정, 값싼 휴리스틱ML6이 못한 것), 지표가 틀렸다.**

## 구현 최종 상태 (PROM→HSWM)

- ✅ **엔진 + LLM-judge weighting: 구현 완료, 기제 정성 검증** — 場별 신뢰도를 LLM이 측정해 per-query 가중(rag의 나쁜 raw 버리고 좋은 web 채택 등). measurement-driven conditional dispatch의 실동작.
- ⚠️ **집계-지표 승리: 미실증** — anchor-string gold(crude) + ceiling task(5/6이 raw=1.0)가 점수화를 막음. coding-agent "실패"는 gold artifact로 규명됨.
- **다음(진짜 마지막)**: proper relevance-gold(리터럴 아닌 판정 기반) + non-ceiling task로 재측정 → 여기서 llm_judge>blind 나오면 PROM SKILL 배선. 지금은 **기제 검증 완료, 클린 벤치마크만 남음.**

---

## 6. V∪E 하이퍼엣지 readout (T5, "V 실채널") — P0 빌더 닫음 (2026-07-21)

> USER verdict 2026-07-21: **"HSWM에 V 실채널 이식"** → (b) T5 하이퍼엣지 V∪E readout 선택. 기존 ML1–7은 **場-가중 융합(K 채널)**만 살았고, KQV 등뼈(`../PROM_KQV_ATTENTION_BACKBONE`)의 attention 출력 = `Σ w·V`의 **V(값/내용 readout) 채널**은 없었다. 이 절이 그 V를 실는다.

**⛔ P0 blocker CLOSED**: KQV T5는 "문서→하이퍼그래프 빌더가 없다(실증 기반은 curated KG뿐)"에 막혀 있었다. 이번에 raw findings에서 하이퍼그래프를 자동 구성하는 빌더를 지어 그 전제를 닫았다.

| 산출 | 내용 |
|---|---|
| `hswm_hypergraph.py` (빌더) | raw findings → 정점 V(entity 40 + topic 7) ∪ 하이퍼엣지 E(24 findings). **edge.value = finding 원문 = 읽어낼 V값**. 임베딩 주입식(구조검증 torch-free). gold_badiou24 실측: **V∪E 71 units**, hub=hallward deg 11(KQV T2 4-fold hub 예측 정합), A1 dangling(정직) |
| `test_hswm_hypergraph.py` | 구조 불변식 **11/11 PASS** + 부정 오라클(손상 incidence 검출) |
| `hswm_hypergraph_readout.py` | V∪E readout 프리미티브 3 arm: `node_only`/`edge_only`/`v_union_e`. 실 임베딩 smoke: query "Cohen forcing+event"에 edge **B1**(정확한 finding) top, v_union_e가 엣지+topic정점 상보 합류 확인 |

**정직 경계 (프로그램 hard-core iii)**: 여기까지는 **구조/프리미티브만 건설**. "v_union_e > node_only/edge_only"라는 성능 주장은 **아직 안 한다** — LakatoTree 노드 `T5-vunione-firstclass-readout`에 예측 **사전등록 완료**(metric=`vunione_minus_edgeonly_recall_gap`, baseline 0, MC-null z>3, credence 0.4). smoke상 엣지가 지배해 정점이 더할지 불확실 → 정직한 낮은 credence.

### 실험 B (step 3) — T5 판정: `prom_vunione_ab.py` → **degenerating** (정직한 RED)

entity-only 그래프(gold==topic이라 topic 정점화하면 leakage → 차단), gold=topic 공동멤버십 held-out, leave-one-out(n=18), finding-level 집계(세 arm 같은 23 findings 랭킹 → candidate inflation 중화).

| arm | recall@5 | MRR |
|---|---|---|
| node_only (entity 정점만) | 0.343 | 0.414 |
| **edge_only** (findings-as-hyperedge) | **0.644** | 0.648 |
| v_union_e (V∪E) | 0.616 | 0.646 |

- **사전등록 metric `vunione_minus_edgeonly_recall_gap` = −0.028 → 예측(higher) REFUTED**. raw entity 정점을 blind union하니 오히려 살짝 해침 — `max(edge,entity)` 집계가 **비변별 hub**(hallward deg 11, topic 횡단)를 엉뚱한 finding으로 승격. KQV T2가 경고한 hub 문제 실증.
- 단 **하이퍼엣지(E) 채널은 신호 지배**: `v_union_e − node_only = +0.273`, **MC-null z = 5.318 ≥ 3**(우연 아님). E를 빼면(node_only) recall 붕괴 = **HyperGraphRAG ablation(−9.0 F1) 방향 재현**.

### 실험 B-2 (변주) — measurement-driven entity gating: `prom_vunione_gated_ab.py` → **rejected**

T5b(blind) 반증 후속 문제이동: entity를 blind union 말고 **idf hub-suppression + edge-dominant 가산**(`score = edge_cos + 0.3·max idf_norm·ent_cos`, 7cmd conditional dispatch 동형). λ=0.3 사전고정(스윕 없음, DoF 통제).

| arm | recall@5 |
|---|---|
| **edge_only** | **0.644** |
| v_union_e_blind | 0.616 (gap −0.028) |
| v_union_e_gated | 0.602 (**gap −0.042, 더 악화**) |

- **사전등록 gap = −0.042 → REJECTED** (LakatoTree 정식 판정 degenerating, eureka hallucinated bf 0.394). MC-null z=5.27로 above chance이나 방향 실패.
- 메커니즘: 가산항이 *모든* finding을 재정렬(정답 포함) → blind max(엔티티가 edge 이길 때만 변경)보다 **더 많은 랭킹 손상**. idf hub 억제로도 못 살림.

### 이 서브라인 종결 결론 (two REDs)

**"V 실채널"(값 readout 채널)은 실현됐고 작동한다 — 단 findings-as-hyperedge로.** edge_only(recall 0.644, z=5.3)가 V값 payload를 최적으로 읽는다. **"raw entity 정점을 V∪E 1급 단위로 추가"는 blind·gated 양쪽에서 반증** — 이 single-hop topic-retrieval task에서 entity 정점은 무익(hub는 비변별, 미세 정점은 노이즈). **기존 HSWM 정전과 정합**: "구조는 multi-hop 전용, single-lookup선 flat과 무의미"(§7). V∪E entity 이득(HyperGraphRAG −9.0 F1)은 **entity가 답을 bridge하는 multi-hop 데이터**서만 재현될 것 — 그 검증은 별도 벤치(이 badiou n=18 아님). LakatoTree: `T5b`(degenerating) → `T5c-vunione-gated`(rejected).

---

## 5. 파일

| 파일 | 내용 |
|---|---|
| `prom_consensus_bench.py` + `EVIDENCE_prom_consensus_toy_2026-07-21.json` | P2 toy — lexical vs semantic 합의탐지 |
| `prom_consensus_real.py` + `real_gold_gfs.json` + `EVIDENCE_prom_consensus_real_gfs_2026-07-21.json` | P2b 실 KG — overlapping hypergraph 발견 + naive semantic 반증 |
| `prom_legend_recall.py` + `EVIDENCE_prom_legend_recall_2026-07-21.json` | P3 레전드 recall cross-lingual |
| `hswm_hypergraph.py` + `test_hswm_hypergraph.py` | **T5 P0 빌더** — 문서→하이퍼그래프(V∪E). 구조 11/11 PASS |
| `hswm_hypergraph_readout.py` | **V∪E readout 프리미티브** — node_only/edge_only/v_union_e 3 arm ("V 실채널") |

**재현**: `uv run --with sentence-transformers --with torch --with numpy python <script>.py`

**provenance**: LakatoTree `LakatosTree_PromSearchHSWM_20260721` (receipt 체인 durable) · commits `961310d`/`701ee09`/`ebbd92f` · ai-agent-book 흡수분석 = `/Volumes/GM/oss-clones/ai-agent-book/` (GM ExFAT 콜드). 상위 HSWM 연구체 = `../INDEX.md`.
