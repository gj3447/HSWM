# PROM 8 — "동적 HSWM" 두 차선 전방위 리서치 (2026-07-22)

> **질문 (USER)**: "①(최강경로 걷기) ②(場 생애 동적)로 어떻게 해결해야 할지 전방위적으로 + 관련 오픈소스"
> **방법**: 8축 병렬 web-research 에이전트, 전 출처 실재 검증 (repo 코드/PDF 직접 확인 포함). raw 결과 8건은 세션 산출.
> **전제 실측**: T1 RED (woven chain seed-미도달·T2 predicate 전멸) / B2 progressive (federated merge cross-field +0.214, L5 간섭 −0.065) / P6 RED (값 residual 흡수 전이 0).

---

## 0. 한 줄 종합

**①의 병목 셋(seed·predicate·재료)에는 각각 검증된 기성 처방이 존재하고, ②는 우리가 이미 업계 최전선이며(unseen 전이 통제실험은 업계에 전무 — P6가 앞서 실측), "exact-span 증거계약 + 걷기"의 조합은 세상에 아직 없다 = HSWM의 novelty 슬롯이 실재로 확인됨.**

---

## 1. Consensus (8축 교차 확증)

### C1. 걷기의 정본형 = "얕은 max 스텝 + 강한 경쟁" — 확산은 이론·문헌 양쪽에서 사망 [A7×A2]
- 5개 독립 이론이 수렴: ACT-R(1-hop 가중합+argmax retrieval, fan효과=희석 명시), 저온 modern Hopfield(=attention, 1-step sharp recall; 평균화는 저품질 영역), 해마 lateral inhibition(winner-take-all이 over-smoothing의 진화적 해답), **Tropical Attention(arXiv:2505.17190 — max-plus는 1-Lipschitz라 원리상 smoothing 없음)**, cognitive random walk(인간 탐색=얕은 1-hop 스텝의 *시퀀스*, 깊은 확산 아님).
- 문헌 추세도 동일: 2025-26 신작(PathRAG, HyperSU)은 전부 이산 경로+pruning, HyperSU는 PPR hub-drift를 명시 반증. HippoRAG조차 passage 가중 0.05로 확산을 묶은 "거의-이산".
- **판정: 우리 max-product K≤2 커널은 타협이 아니라 이론적 정본. USER "돌아다님"의 작동형 = 얕은 max 스텝의 궤적.**

### C2. T1 병목 3처방 — 전부 기성 검증 레시피 [A2×A3]
1. **seed**: NER/lexical → **query-to-triple 전체 임베딩 + 필터** (HippoRAG 1→2의 핵심 수정이 정확히 우리 증상이었음) + synonym edge.
2. **T2 predicate**: hard filter → **soft edge-weight 강등** (ToG ablation: lexical 강등 시 −8.4~−15.1% = hard lexical 게이트 사망의 정량 근거). 표현력은 **build-time Wikidata property alias-closure(CC0)** — 2Wiki 관계 어휘가 애초에 Wikidata산이라 직격. 선례=Falcon 2.0(MIT)·HippoRAG synonym-edge·EDC. cosine fallback은 **anisotropy 함정**(짧은 텍스트 cosine 0.8대 밀집 → raw threshold 무력화) 때문에 mean-centering+isotonic 보정 필수.
3. **dense 백오프 hybrid**: 걷기 단독은 single-hop서 평균을 깎는다는 게 비교벤치 전원일치 — walk 점수 임계 미달 시 flat 백오프가 기본값이어야.

### C3. 재료(identity) 파이프라인 확정 — 라이센스·결정론·span 전부 합격 조합 존재 [A1]
- **1순위: ReFinED(Apache-2.0, QID+char span) + fastcoref(MIT, 2026-05 활발, char span)** — 전부 argmax 결정론, receipt 계약에 그대로 꽂힘. GLiNER(Apache-2.0, 활발)를 span 보조로.
- 기술 1위급 ReLiK/maverick-coref는 CC BY-NC-SA → 공개 Apache repo와 충돌 소지(게이트 필요). Meta 계열(BLINK/GENRE) 전멸(아카이브).
- 함정: ReFinED 의존성 부패(2022 이후 방치 — 전용 venv+pin), GPU 비결정론(CPU 고정 권장), coref↔linking span 1-2자 어긋남(containment-match).

### C4. 걷기를 시험한 "판"이 틀렸었다 — 승리 regime 5조건 + 다음 판 확정 [A8×A2]
- graph 이득 실측: 2Wiki +20.9pt ≫ MuSiQue +2.7 ≫ HotpotQA 역전패. 이득 ∝ "명시적 entity-bridge로만 도달 가능한 정도".
- **5조건**: hop≥2 강제(DiRe 낮음) / bridge 희박·lexical disjoint / **pool 10⁴~10⁶ 단락** (fullwiki서 flat F1 25pt 붕괴 실증) / entity-유사 distractor / 문서내 co-occurrence sparse. 우리 실측 판(조밀·소규모)은 정확히 flat-우위 조건이었음.
- **다음 판**: (1) **2Wiki full-corpus pool 확장판** (걷기가 실제 이긴 유일 실판) (2) **PhantomWiki**(ICML'25 — universe 크기·hop 1-9 통제 생성기; **density/bridge-rate dial은 아무도 안 돌려봄 = 연구 빈칸**) (3) 서사축은 NovelHopQA(완전 공개, hop 통제 유일 장문판). NoCha는 gated.

### C5. 흡수(②)의 살길 = 구조+추상화 계보뿐 — P6는 업계를 앞서간 실측 [A5]
- 상용 메모리(Zep/Mem0/Letta/LangMem) **전부 seen-질의 회귀 벤치만** — unseen 전이 통제실험은 업계 전무. 정면 실험 셋(Procedural Memory Bench의 "generalization cliff" 84→59%, MemRL의 memorization 자백, 지식편집 gen/spec 프로토콜)이 전부 **"값 저장=전이 0, 구조+추상화만 전이"**로 수렴 — P6 기각과 정확히 정합.
- ACT-R base-level 수식 확보(B_i ≈ ln(n/(1−d)) − d·ln(t_n), 2스칼라) — 단 이론상 이것도 seen 강화 장치지 일반화 장치가 아님(전이는 spreading/partial-matching 몫).
- **후계 2안**: A="ACT-R soft prior"(값 주입→접근성 prior로 후퇴; 사전등록 예측 "전이 여전히 ~0" = P6 기각의 원인 분리 실험) / B="구조 흡수"(co-retrieval→assoc edge + Graphiti식 expired 마킹; 판정에 paraphrase/neighborhood 셋 이식). A/B 직교.

### C6. supersede 자동화 = 3층 사다리, 기존 CRDT 원장에 add-only로 얹힘 [A6]
- 검증 사다리: **1층 규칙**(Wikidata functional/single-value constraint — 12년·1억 아이템 검증, 위반노이즈 0.02~0.8%; "한때 참"은 deprecated 아니라 normal+end time — separator 규칙 필수) → **2층 ingest 1회 판정**(Graphiti 패턴: 후보는 결정론 검색, LLM은 모순 idx만, replay 무재호출) → **MiniCheck 770M**(Apache-2.0, GPT-4급 판정 400배 저렴, 로컬)로 2층 치환 가능.
- **핵심 통찰: invalid_at을 min-register로 정의하면 교환·결합·멱등 = CRDT lattice에 그대로**. SUPERSEDE 자체를 G-Set 원소로 add → bitemporal 4-timestamp가 공짜 완성. 반증 5종 설계 확보(합성모순 주입 100% / separator 오탐 0 / 커버리지 실측(공표 수치 없음 — 우리가 재면 novelty) / 셔플 replay 비트동일 / 2층 드리프트 측정).
- 외부 재현: Zep이 temporal reasoning +38.4% — "stale 침몰=검색 개선"(T4)의 독립 확인.

### C7. 게이트(L5 간섭) = federated IR "collection selection"의 재래 — conformal 보장까지 기성 존재 [A4]
- CORI/ReDDE/Taily(무학습, 수십 년 검증)가 정확히 "어느 場이 이 질의를 소유하나" 문제. **C3R(arXiv:2607.14157, 2026-07)** = label-free 멀티도메인 검색에 conformal risk control로 "타도메인 오염률≤예산" per-domain 보장 + abstain — 우리가 원하던 것의 직답. 도구: MAPIE/crepes(BSD-3, **Mondrian=場별 조건부 커버리지**).
- 경고: QPP 한계 감사(TOIS 2025) — selective processing 이득 ~4%에 그침, cross-collection 일반화 실패. → **oracle headroom 측정 선행이 관문** (oracle이 복구 못 하면 게이트가 아니라 merge 자체가 문제).
- unseen 전이 증명한 학습형 선례 3건 실재(RouterRetriever/LTRR/RouteLLM). P5가 죽인 건 *고정* lexical 라우팅 — 학습된 lexical(TF-IDF+SVM이 임베딩을 이김, RAGRouter-Bench)과는 별개.

### C8. HSWM의 novelty 슬롯 2개가 외부 조사로 실증 확인 [A2×A8]
1. **"evidence-bound exact-span 계약 + 걷기" 동시 만족 시스템은 존재하지 않음** (최근접 HyperSU·Ex-GraphRAG도 부분만).
2. **density/bridge-rate를 독립 dial로 통제한 걷기 실험은 전무** — PhantomWiki 확장으로 우리가 직접 메울 수 있는 빈칸.

---

## 2. Divergence (긴장 지점, 닫지 않음)

- **QPP 비관론(이득 ~4%) vs collection-selection 낙관론** — 우리 문제가 QPP보다 쉬운 "場 소유권" 문제라는 근거는 있으나 실측 전까지 열림.
- **기술 우위(ReLiK/maverick) vs 라이센스(NC)** — build-time 로컬 사용+산출물만 커밋 구조면 방어 가능하나 별도 판단 필요.
- **Graphiti의 ingest LLM 판정 vs 우리 결정론 요구** — MiniCheck 치환·판정의 이벤트 박제로 완화 가능하나 드리프트 측정(반증 5) 전까지 미결.
- **깊은 walk의 여지** — 인지과학 random walk는 "얕은 스텝의 긴 시퀀스"를 지지 (K를 키우는 것과 다름). 궤적형 walk(K≤2 반복)는 미시험.

## 3. Open Questions

- OQ1: alias-closure가 T2 전멸을 실제로 몇 % 회복하나 (어휘 문제 vs 구조 문제 판별).
- OQ2: 2Wiki full-pool(10⁴+ 단락)에서 우리 max-product가 flat을 이기는 첫 판이 나오나.
- OQ3: oracle gate 상한이 (in-field 복구 ∧ cross-field 유지)를 허용하나 — merge 자체 결함 여부.
- OQ4: 실데이터 모순 중 functional 규칙 1층이 잡는 비율 (공표 수치 전무 — 재면 그 자체가 기여).
- OQ5: ACT-R prior의 사전등록 예측("전이 여전히 0")이 맞나 — P6 기각의 원인 분리.

## 4. 권장 후속 (우선순위, 전부 반증가능 설계 확보됨)

| # | 작업 | 차선 | 근거 축 | 비용 |
|---|---|---|---|---|
| R1 | **T2 alias-closure(Wikidata CC0) + predicate soft-weight 강등 + HippoRAG2식 seed → T1 재판** | ① | C2 | 낮음 (frozen 자산 재사용) |
| R2 | ML lane 재료: ReFinED+fastcoref receipt weave (B1 후계) | ① | C3 | 중 (모델 셋업) |
| R3 | 판 교체: 2Wiki full-pool + PhantomWiki density-dial | ① | C4/C8 | 중 |
| R4 | 게이트: oracle headroom → 무학습 통계(A안) → conformal 학습형(B안) | ② L5 | C7 | 낮음→중 |
| R5 | supersede 3층 판정기 (add-only G-Set 원소, 반증 5종) | ② | C6 | 중 |
| R6 | 흡수 후계 A(ACT-R prior)·B(구조 흡수) 사전등록 | ② | C5 | 중 |

순서 논리: R1이 가장 싸고 T1 사인을 즉시 재판 → R1이 살면 R3(제대로 된 판)에서 걷기 본판 → R2는 R1 결과에 따라 규모 결정. R4는 독립 차선이라 병렬 가능. R5/R6는 ② 차선 — R5가 먼저(자동화가 T4 확증 메커니즘의 방아쇠만 자동화라 리스크 최소).

---

*8축 raw: A1(entity/coref OSS) · A2(걷기 시스템) · A3(predicate 매칭) · A4(게이트/conformal) · A5(continual 흡수) · A6(supersede/시간) · A7(이론 지반) · A8(벤치 regime). 전 출처 URL 실재 검증. KG: rf-prom8-dynamic-* 8건.*
