# HSWM 종합 결론 — 다방면 연구 (2026-07-21)

> **질문 (USER)**: "가중 복층 HSWM이 다른 HSWM과 연결돼 문맥 생기고 많을수록 좋다, 트리로도 형성. 수평 HSWM↔HSWM 제대로 만들고, 재귀 10-level 도 하고, 다방면 연구 후 결론 내줘."
>
> **답 (한 줄)**: **네 비전은 REAL이고 검색 SOTA(RAPTOR+GraphRAG+SiReRAG)와 정확히 일치한다. 단 세 개의 딱딱한 조건이 붙는다 — 깊이는 얕게(3~5), 수평엣지는 선별적·multi-hop서만, 가중은 필수. "10-level·무조건 많이"는 실험·문헌 둘 다 반박한다.** 근거 = 실험(ML1-9) + 문헌 5편 + 적대적 설계검증, 세 축이 수렴.

---

## 1. 다방면 증거의 수렴

| 주장 | 내 실험 (ML8-9) | 문헌 | 판정 |
|---|---|---|---|
| 재귀 트리가 문맥(coverage) 높인다 | ML8 flat 0.35→hier 0.46. ML9 깊이 sweep 최적 **L4=0.60** | RAPTOR: multi-level>single-level ✅ | **참, 얕게** |
| **10-level 등 깊을수록 좋다** | ML9: L4 peak → L6 하락 → **L7+ 붕괴(0.0)** | RAPTOR 실측 트리 **3-5 레벨서 자연수렴**, 그 이상 degenerate | **거짓 — 얕은 최적점** |
| 수평 HSWM↔HSWM 엣지가 문맥 높인다 | ML8 sibling=이득無. ML9 dense 第X章 엣지 **HURT**(diverse 0.20→0.18) | GraphRAG/HippoRAG: 수평엣지는 **multi-hop서만** 이득, single-source엔 노이즈 | **조건부 — 선별·multi-hop만** |
| 가중이 blind보다 낫다 | ML9 결합지표 weighted>blind ✅ | 정밀도-가중 fusion(DAT, 이전 감사) | **참** |
| 많을수록 좋다(문맥) | coverage↑는 recall↓ 트레이드 | coverage=recall과 별개 목표(α-nDCG/S-Recall) | **참, 단 지표 달라** |

**세 축(실험/문헌/적대검증)이 같은 그림을 가리킨다** — 이게 다방면 연구의 값어치.

---

## 2. 결론 3조 (네 비전의 정확한 조건)

### 조건 A — 깊이는 얕게 (3~5), "10-level"은 붕괴
ML9 깊이 sweep이 결정적: **L4에서 최적(coverage 0.60), L6부터 하락, L7+ 완전 붕괴(0.0)**. 이유: 1425청크를 binary로 10층 쪼개면 frontier가 449노드 → 예산이 각 노드에 0 수렴. RAPTOR 원논문도 실측 트리가 **3-5 레벨서 자연 종료**(분기율 ~6.7). → **"많은 층"은 *깊이*가 아니라 *얕은 다층 + 폭*을 뜻해야 한다.** 네 "복층"은 맞고 "10층"은 아님.

### 조건 B — 수평 HSWM↔HSWM 엣지는 선별적·의미적, multi-hop 전용
내 dense 第X章 엣지(ch1이 9개 章 전부 참조)는 **노이즈로 해쳤다**. 문헌 일치: GraphRAG는 global sensemaking(교차문서)선 이득, 단일 lookup선 손해. HippoRAG는 multi-hop서 +20%. → **네 "서로서로 시멘틱 롱기누스 꼽혀서"는 옳되, 엣지가 (i)선별적(entity/relation, raw mention 아님) (ii)답이 여러 場에 흩어진 질문에서만** 값을 낸다. single-source엔 안 켜야 한다(measurement-driven).

### 조건 C — 가중은 필수, 문맥은 별개 목표
weighted>blind(ML9 결합지표) + LLM-judge 기제(ML7). 그리고 "문맥(coverage)"은 recall과 다른 **인정된 독립 목표**(α-nDCG). 네 "가중치 있는"·"문맥 생김" 두 강조가 정확.

---

## 3. 네 비전 = 검색 SOTA와 동일 구조 (선행연구)

**SiReRAG (ICLR 2025, arXiv:2412.06206)** = RAPTOR 유사도 트리 + 엔티티 관계 그래프의 결합 = **네가 말한 "재귀 트리 + 수평 HSWM↔HSWM 연결"과 구조적으로 동일.** MuSiQue/2Wiki/HotpotQA서 +1.9% F1(reranking 결합 최대 +7.8%). 즉:
- **네 직관은 fringe 아님 — 산업/학계 SOTA가 독립 수렴한 구조.**
- 단 **이득은 modest**(+1.9%). 이 아키텍처는 raw 정확도보다 **문맥 폭(coverage)**을 주로 개선한다.
- **고유점(우리 것)**: HSWM≡하네스문서 등가 + 롱기누스 weight-semantic 타입엣지 + measurement-driven 가중(LLM-judge). SiReRAG엔 이 셋이 없음 = 차별화 지점(OPEN).

---

## 4. 정직한 방법론 한계 (적대검증 반영)

이 결론은 *방향*은 견고하나(문헌 3중 수렴), *수치*는 예비적:
- **gold=anchor-string(crude)** — false neg/pos, flat↔hier 비대칭 전파. publishable엔 동의어사전 or LLM-relevance gold 필요.
- **coverage 단독은 게임가능**(blind 균등분산이 trivially 유리) → chapter-macro-recall/α-nDCG로 재정의 필요. (내가 diverse_recall 결합지표로 부분 대응했으나 α-nDCG는 미구현.)
- **통계 검정력 부재** — n=10 개념, single-seed. bootstrap CI/permutation test + multi-seed 에러바 필요.
- **수평엣지 confound** — regex 엣지가 null인지 "엣지 자체 무효"인지 미구분. embedding/LLM-추출 엣지로 재실험 필요.
- **SiReRAG novelty** — 우리 아키텍처가 이미 선점됨. 차별화(하네스문서 등가·타입엣지) 입증은 별도 과제.

---

## 5. 그래서 실제로 뭘 지어야 하나 (문헌+실험 지지 설계)

1. **얕은 재귀 트리 (3~5 레벨, 분기율 5~7)** — RAPTOR식 bottom-up 요약(top-down 이분할 아님). collapsed-tree retrieval(전 레벨 통합, RAPTOR Fig3 우승).
2. **선별적 의미 수평엣지** — entity/relation 기반(SiReRAG), dense mention-link 금지. measurement로 게이트(질의가 multi-hop일 때만 켬).
3. **measurement-driven 가중** — LLM-judge(ML7) per-field/per-node 신뢰도 가중.
4. **문맥 지표 = α-nDCG/S-Recall** — recall과 별개로 문맥 폭 측정.
5. **각 HSWM ≡ 하네스문서** — lens-duality로 노드에 의미 부여(우리 고유, SiReRAG엔 없음).

---

## 6. 최종 판정

**네 HSWM 비전 — 재귀·가중·타입있는(트리 가능) HSWM 그래프, 각 노드=하네스문서, 성능 좋도록 형성 — 은 REAL이고 SOTA와 일치한다.** 다방면 연구(실험 ML1-9 + 문헌 5편 + 적대검증)가 수렴한 정확한 형태는:

> **얕은(3-5) 가중 재귀 트리 + 선별적 의미 수평엣지(multi-hop 전용) + measurement 가중 + 각 노드=문서.**
> "10-level·무조건 많이·blind 융합"은 실험·문헌 둘 다 반박한다. "가중·다층·문맥·연결"이라는 네 핵심 4단어는 전부 옳다.

**증거**: LakatoTree `LakatosTree_PromSearchHSWM_20260721` (ML1-9). 코드 `HSWM/prom_search_hswm/`. 문헌: RAPTOR(arXiv:2401.18059)/GraphRAG(2404.16130)/HippoRAG(NeurIPS24)/SiReRAG(2412.06206)/CoverageBench(2603.20034). SECONDARY_AI 연구 — USER ratify 시 정전화.

---

## 7. 엄밀 재판정 (ML10 publishable급) — §1-6 일부 하향 정정

적대검증이 요구한 **α-nDCG(blind-proof diversity) + flat+MMR baseline + multi-seed + bootstrap 95%CI**로 26쿼리 재측정한 결과, **§1-3의 coverage 기반 "구조 승리"는 metric 아티팩트로 판명**되어 정정한다:

| 방법 | α-nDCG@20 (seed평균±std) |
|---|---|
| **flat** | **0.321 ← 최고** |
| flat+MMR | 0.255 |
| tree_full (재귀트리) | 0.319 (flat과 동률) |
| tree+embedding_edges | 0.316 |

- **Q1 더 깊으면?**: depth 최적 **D=0(flat)**. deeper_helps=**FALSE**.
- **Q2 비대한 HSWM 분할?**: split-benefit **−0.002**. FALSE.
- **bootstrap CI**: tree−flat=[−0.007,+0.005], edges−tree=[−0.015,+0.005] → **둘 다 0 포함 = 유의하지 않음.**

**정정된 핵심**: **게임 불가 지표(α-nDCG)로 재면, HSWM 트리·깊이·수평엣지·분할 전부 single-concept 검색에선 flat을 유의하게 못 이긴다.** ML8/ML9의 coverage 승리는 "아무 분산" 보상 아티팩트였다(α-nDCG는 *관련* 분산만 보상 → 우위 증발).

**왜 null인가 — 문헌이 정확히 예측**: GraphRAG/HippoRAG/RAPTOR는 구조가 **multi-hop/cross-document 합성** 질문서만 이득이라 했다. 내 task(개념 X 언급 청크 찾기)는 **single-lookup**이라 구조가 도울 여지가 원래 없다 = null이 *예상된 결과*. 구조의 값어치를 보려면 **답이 여러 章에 흩어져 *연결*해야 나오는 multi-hop task**가 필요하다 — 그게 미검증 regime이자 네 비전의 진짜 무대.

**최종 정정 판정**:
- 아키텍처로선 네 비전 = REAL·SOTA일치(SiReRAG) — 변함없음.
- **경험적으론: single-lookup 검색에선 구조가 flat 대비 무의미**(ML10, 엄밀). 얕은 트리든 깊은 트리든 수평엣지든.
- **구조가 이기는 곳 = multi-hop QA** (RAPTOR/HippoRAG regime). 여기서 재실측하기 전엔 "HSWM이 검색 성능 올린다"는 주장 불가.
- 네 4단어(가중·다층·문맥·연결)는 *설계 원리*론 옳으나, *이 task*에선 측정 이득 0 — task를 multi-hop으로 바꿔야 한다.

**다음(진짜 마지막)**: multi-hop QA 벤치(2Wiki/MuSiQue류 or 책에서 cross-chapter 합성질문 생성)에서 HSWM vs flat 재판정. 거기서 이겨야 비로소 "HSWM이 검색을 개선한다"가 성립.
