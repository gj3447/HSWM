<!-- PROVENANCE
Status: SECONDARY_AI (자료집 — 1차 소스 수집·검증 기록. 사용자 창작 아님)
Date: 2026-07-20. Method: 4 병렬 리서치 에이전트 (차선별 1), 전 URL WebFetch 실재검증,
페이월 PDF는 로컬 pdftotext/pypdf 추출로 verbatim 인용 확보. 요약기-경유 인용은 개별 표기.
Scope guard: `PROM_WOLFRAM_IMPORT_2026-07-19.md` 판정표 준수 — 채택 4차선만 수집.
기각 7건(우주론·양자·branchial·ruliad·창발차원·창발시간·THE-rule)은 수집 금지 이행됨.
OSS 클론 실물: dgx `~/symposium-restore/` (GIT/CATALOG.md §WOLFRAM_HSWM_EPWC, 9 repo shallow).
-->

# HSWM × Wolfram — 이식 4차선 1차소스 자료집 (검증된 인용 + OSS)

> 자매편: `PROM_WOLFRAM_IMPORT_2026-07-19.md`(이식 재판 — 무엇을 왜 가져오는지) ·
> `PROM_16_WORLD_COMPILER_CERTIFIED_READOUT_ENVELOPE_2026-07-20.md`(EPWC/FSK/CRE — 어디에 꽂히는지).
> 이 문서 = **그 판정을 집행할 때 인용할 1차 소스의 검증된 재고**.

## 0. 차선 지도 (판정표 → 소스 묶음)

| 차선 | 판정 | 이 문서 섹션 | EPWC 배선 |
|---|---|---|---|
| A. causal invariance → 쓰기 confluence | IMPORT_MECHANISM (유일) | §1–§3 | S1 CRDT 격상 · teeth tests · admission rule |
| B. causal graph → PROV 쓰기-이벤트 DAG + blame | FORMALISM_ONLY | §4 | 이벤트 레코드 · blame semiring · rev counter |
| C. foliation → consistent cut | FORMALISM_ONLY (얇음) | §5 | snapshot id = 인과 폐쇄 cut |
| D. DPO 타이핑 seam (CHU 공유) | FORMALISM_ONLY | §6 | 쓰기-op 정적 충돌검사 · CHU 타입 seam |

**Attribution 규율 (재판 §1 그대로)**: 차선 A의 수학 출처는 Wolfram이 아니라
Church–Rosser/Newman/Huet + CRDT(Shapiro)다. Wolfram/Gorard의 기여 = *질문의 인스턴스*
("필드 진화는 업데이트-순서 불변인가?") + 실행 가능한 판정 도구. 인용 시 이 순서 유지.

---

## 1. 차선 A-1 — Wolfram/Gorard 원문 (질문의 인스턴스)

- **Gorard, "Some Relativistic and Gravitational Properties of the Wolfram Model"** — Complex Systems 29(2):599–654, 2020. DOI 10.25088/ComplexSystems.29.2.599 · arXiv:2004.14810 [VERIFIED, PDF 추출]
  > "First, we prove that causal invariance (namely, the requirement that all causal graphs be isomorphic, irrespective of the choice of hypergraph updating order) is equivalent to a discrete version of general covariance…" (Abstract)
  > "Definition 9. A multiway system is 'causal invariant' if the causal graphs that it generates … are all, eventually, isomorphic as directed, acyclic graphs." (§2.2)
  - §2.2가 confluence를 causal invariance의 **필요조건**으로 명시. feeds: A(정의 앵커), B(Def.9 DAG-동형), C(foliation=Cauchy surface 구절).
- **Gorard, "Some Quantum Mechanical Properties of the Wolfram Model"** — Complex Systems 29(2):537–598, 2020. DOI 10.25088/ComplexSystems.29.2.537. **arXiv 없음 — 저널 DOI로만 인용** [VERIFIED, PDF 추출]
  > "…in order to study classes of such models in which causal invariance is explicitly violated, as a consequence of non-confluence of the underlying rewriting system." (Abstract)
  > "observers may then impose 'effective' causal invariance by performing a Knuth–Bendix completion operation…" (Abstract)
  - 수집 범위 = §2.1–2.2(abstract rewriting 정리 요약)만. 논문 본론(양자 해석)은 기각 차선 — 인용 금지. feeds: A(비-confluence 방향 + Knuth–Bendix 수리 기제).
- **Wolfram, "A Class of Models with the Potential to Represent Fundamental Physics"** — Complex Systems 29(2):107–536, 2020. arXiv:2004.08210 [VERIFIED — 출판사 PDF는 403, arXiv 경로 사용]
  > "When a system is causal invariant for all possible initial conditions, we will say that it is totally causally invariant. **(This is essentially the confluence property discussed in the theory of term-rewriting systems.)**" (§5 — confluence 자백 문장)
  > "This causal graph is dual to our original evolution graph in the sense that edges in the original evolution graph correspond to events—which now become nodes in the causal graph." (§5)
  > "Each choice of how to assign updates to steps in effect defines a foliation of the evolution. We will call foliations in which the updates at each step are causally independent 'causal foliations'." (§5)
  - feeds: A + B + C. 웹판 동일 문장: wolframphysics.org/technical-introduction/ → "The Phenomenon of Causal Invariance" [VERIFIED].
- **정밀도 주의 (뭉뚱그리면 drift)**: Gorard(Rel. §2.2)는 confluence = causal invariance의 **필요조건**, CausalInvariantQ 문서는 causal invariance가 confluence의 **충분조건** — 두 성질은 밀접 결합이되 동일 정의가 아님. Wolfram의 "essentially"는 비공식 다리. HSWM 산문에서 이 방향성 보존할 것.

### OSS (실행 가능한 기계)

| repo | 검증 | license | HSWM 재사용 포인트 |
|---|---|---|---|
| `maxitg/SetReplace` | VERIFIED | MIT | evolution→`"CausalGraph"`/`"EventsGraph"` 속성 = 이벤트-DAG 생성 기계; `libSetReplace/` C++ 코어는 CMake 단독 빌드 가능. 최종 릴리스 2021-03 (개발 둔화) |
| `phcerdan/wolfram_model` | VERIFIED | MIT | libSetReplace의 **Mathematica-free 파이썬 래퍼** (dormant이나 코어 독립 구동 증명) |
| WFR `MultiwaySystem` (Gorard/Wolfram/Piskunov) | VERIFIED | WFR 약관 (OSS 아님) | CausalGraph/BranchialGraph/StatesGraph 속성 일습 |
| WFR `CausalInvariantQ` (Gorard) | VERIFIED | WFR 약관 | **causal invariance 기계판정 함수** — "all branches … isomorphic as acyclic graphs" |

### 정직 부록 (계약 지위)

- Becker, "Physicists Criticize Stephen Wolfram's 'Theory of Everything'", *Scientific American* 2020-05-06 [VERIFIED]:
  > "It's this sort of infinitely flexible philosophy…" (Aaronson) · "The successes he claims are, at best, qualitative." (Harlow)
- Complex Systems는 Wolfram 자신의 저널 — 세 논문 모두 통상적 독립 피어리뷰 밖. 인용 시 이 사실 병기.

---

## 2. 차선 A-2 — 진짜 수학 계보 (Church–Rosser / Newman / Huet / Plump)

- **Church & Rosser 1936** — "Some properties of conversion", Trans. AMS 39(3):472–482. DOI 10.1090/S0002-9947-1936-1501858-0 [메타데이터 VERIFIED, 전문 403 — **verbatim 인용 없음, Huet/Baader-Nipkow 경유 인용**]
- **Newman 1942** — "On Theories with a Combinatorial Definition of 'Equivalence'", Ann. Math. 43(2):223–243. DOI 10.2307/1968867 [메타데이터 VERIFIED, JSTOR 페이월 — verbatim 없음]. diamond lemma: 종료+국소 confluence ⇒ confluence. **S1에 적용가능 근거 = 이벤트당 유한 감쇠라 종료 가설 충족.**
- **Huet 1980** — "Confluent Reductions: Abstract Properties and Applications to Term Rewriting Systems", JACM 27(4):797–821. DOI 10.1145/322217.322230 [VERIFIED via dblp/S2, ACM DL 403]. critical pair 판정의 정본 + 무종료 하 strong-confluence 기준.
- **Plump 1993** — "Hypergraph Rewriting: Critical Pairs and Undecidability of Confluence", in *Term Graph Rewriting*, Wiley, pp.201–213 [서지 VERIFIED, York PURE 500×3 — 인용은 2005판 경유]
- **Plump 2005** — "Confluence of Graph Transformation Revisited", LNCS 3838:280–308. DOI 10.1007/11601548_16 [VERIFIED, abstract 추출]:
  > "It is shown that it is undecidable in general whether a terminating graph rewriting system is confluent or not—in contrast to the situation for term and string rewriting systems. … the mere existence of common reducts for all critical pairs of a graph rewriting system does not imply local confluence."
  - **하중 인용**: 그래프 리라이팅에선 critical-pair joinability가 (i) 결정불능이고 (ii) 충분하지도 않음 → HSWM admission rule은 joinability가 아니라 **결정가능한 pairwise commutation**(RR-7506 Def 2.6)을 요구해야 함. RTA Open Problem #75 [VERIFIED]도 동일 진술.
- 교과서 앵커: **Baader & Nipkow 1998** (DOI 10.1017/CBO9781139172752 — Newman §2.7.2, critical pair, Knuth–Bendix) · **Terese 2003** (ISBN 9780521391153 — ARS·commutation·term graph 장) [둘 다 VERIFIED].

---

## 3. 차선 A-3 — CRDT 정본 + 도구 (처방의 집행부)

- **Shapiro/Preguiça/Baquero/Zawirski, INRIA RR-7506 (2011)** — "A comprehensive study of Convergent and Commutative Replicated Data Types", HAL inria-00555588 [HAL Anubis-차단 — DePaul 미러 PDF 로컬 추출, **인용 전부 verbatim**]:
  > "Since merge is idempotent and commutative (by the properties of ⊔v), messages may be lost, received out of order, or multiple times…" (§2.3.1 state-based)
  > "we assume an underlying system reliable broadcast that delivers every update to every replica in an order <d" (§2.4 op-based)
  > "Definition 2.6 (Commutativity). Operations f and g commute, iff … S·f·g and S·g·f are equivalent abstract states." (§2.4)
  > G-Set §3.3.1: "merge(S, T) = S ∪ T … states form a monotonic semilattice and merge is a LUB operation; G-Set is a CvRDT."
  - **처방의 이론 잠금**: 중복 내성은 **idempotent merge(state-based)에서만** 나옴 — op-based는 reliable broadcast(무중복) 전제. S1의 `b(e)=∏δᵢ`는 가환이나 비-idempotent → **적용된 event-id의 G-Set(그 자체 CvRDT)으로 곱 누산기를 감싸는 격상**이 정확한 수리. (= PROM_WOLFRAM §3-A 처방 1의 원문 근거.)
- **Shapiro et al., SSS 2011** — "Conflict-Free Replicated Data Types", LNCS 6976:386–400. DOI 10.1007/978-3-642-24550-3_29 [VERIFIED]. SEC(Strong Eventual Consistency) = 형식 목표 성질.

### OSS

| repo | 검증 | license | HSWM 재사용 포인트 |
|---|---|---|---|
| `automerge/automerge` | VERIFIED | MIT | 코드 아닌 **op-identity 설계**: (actor-id, seq) 전역 유일 id + 기적용-id dedup 게이트 = S1 처방의 산업 선례; "immutable change DAG + 결정론 replay" 모델 |
| `yjs/yjs` | VERIFIED | MIT | (clientID, clock) id + idempotent update 적용(재적용=no-op) — 중복-안전 op 스트림의 최소 메타데이터 |
| `y-crdt/pycrdt` | VERIFIED | MIT | 파이썬 API 표면 참조 (Doc/transaction/update). 곱-감쇠 타입은 없음 — HSWM CRDT는 순수 파이썬 자작 (G-Set dedup + product monoid) |
| CSI (Innsbruck) | 신규 페이지 VERIFIED | **미확인** (논문상 LGPL, 페이지 침묵 — 코드 재사용 전 확인 필수) | 1차 confluence 자동증명기 (CoCo 우승). OCaml, 설치 무거움 — CI 오프라인 오라클용 |
| **ACP** (Aoto/Toyama, Niigata) | VERIFIED — tarball 검수 | BSD-류 (COPYING) | **1급 commutation 모드**: "For the commutation problem, specify two TRSs" (README verbatim) — admission rule의 "두 op가 가환인가"를 그대로 묻는 도구. SML/NJ+MiniSAT. 단 하이퍼그래프 op의 1차 항 인코딩 타당성은 우리 몫 (Plump 결정불능이라 일반 커버 도구는 없음) |
| AGCP | VERIFIED — tarball 검수 | BSD-류 | **ground confluence** (구체 이벤트 스트림 = HSWM 실황에 맞는 약한 성질) + many-sorted 입력 (NodeId/Weight/EventId sort) |
| `HypothesisWorks/hypothesis` | VERIFIED | MPL-2.0 | teeth test 직결: `@given(lists(op), randoms())` 순열+중복주입 → 필드 rank-동일 assert / `RuleBasedStateMachine`+`@invariant` 수렴 검사. shrinking이 최소 비가환 op쌍을 뱉음 — ACP 정적 체크의 런타임 보완 |
| CoCo/COPS (경연·문제 DB) | 호스트 다운 (2026-07-20) | — | TACAS 2019 보고 논문 (DOI 10.1007/978-3-030-17502-3_2, VERIFIED)으로 앵커. **COM = commutation 카테고리** 존재 = 문제 클래스가 tool-supported임의 증거 |

---

## 4. 차선 B — PROV 쓰기-이벤트 DAG + blame semiring

- **W3C PROV-DM** (Recommendation 2013-04-30) — w3.org/TR/prov-dm/ [VERIFIED]:
  > "Activity: Something that occurs over a period of time and acts upon or with entities…"
  > "wasInformedBy: … activity a2 is dependent on another a1, by way of some unspecified entity that is generated by a1 and used by a2."
  - = HSWM 이벤트 레코드의 정본 어휘 (Activity=쓰기 이벤트 / Entity=필드-성분 버전 / wasInformedBy=쓰기→쓰기 인과 edge). PROV-O [VERIFIED]는 직렬화 필요 시만.
- **`trungdong/prov`** (MIT, v2.5.1, 활발) [VERIFIED] — 인메모리 PROV 문서 구축 + PROV-JSON/RDF/graphviz/NetworkX. **경량 대안 없음(NOT_FOUND)** — rdflib 체인이 무거우면 PROV-JSON dict 직접 방출이 최경량 경로.
- **Green/Karvounarakis/Tannen, "Provenance Semirings"** — PODS 2007. DOI 10.1145/1265530.1265535 [UC Davis PDF 추출 — ACM 403]:
  > "Definition 4.1 … The positive algebra provenance semiring for I is the semiring of polynomials … (N[X], +, ·, 0, 1)."
  > "Proposition 4.2 … there exists a unique homomorphism of semirings Evalv : N[X] → K…"
  - **하중 사실 = Prop 4.2 (자유 가환 semiring의 보편성)**: 다항식 annotation 하나 기록하면 평가만 바꿔 bag/trust/boolean-why 등 모든 semiring으로 특수화됨. HSWM path receipt(경로별 b^κ 곱의 합)가 문자 그대로 이 다항식 — blame 계산은 같은 기록의 재평가.
- **ProvSQL** (Senellart, MIT) [VERIFIED] — provenance **circuit** + 플러그형 semiring 평가기(+Shapley) 아키텍처가 numpy 구현의 설계도. 코드 자체는 PostgreSQL 내부 결합이라 이식 불가. **파이썬 provenance-semiring 라이브러리는 부재(NOT_FOUND) — blame 구현은 신규 작업.**
- **Kappa "stories"** — KappaTools (LGPL-3.0) [VERIFIED] + Danos/Feret/Fontana/Harmer/Krivine, CONCUR 2007, LNCS 4703:17–41, DOI 10.1007/978-3-540-74407-8_3 [ENS PDF VERIFIED]. 인과 trace를 관측가능값 기준 **최소 인과 DAG로 압축** — 오염-쓰기 blame(= poison observable에 도달하는 최소 쓰기 sub-DAG 가지치기)의 정확한 선례. weak/strong compression 구분 = blame 가지치기 강도 축.
- **Winskel, "Event Structures"** — LNCS 255:325–392, 1987. DOI 10.1007/3-540-17906-2_31 [서지 VERIFIED, 페이월 — verbatim 없음]. configuration(하향폐쇄·무충돌 이벤트 집합) ≈ 쓰기-DAG의 consistent cut.
- **rev counter 선례** (전체 의존 DAG는 기각 유지): **salsa** (Apache/MIT) [VERIFIED] — > "If a revision changes only lower-durability inputs, Salsa can skip validating queries that depend exclusively on higher-durability inputs." = 전역 revision 정수 + durability 계층으로 O(1) 무효화 판정. **Adapton** (MPL-2.0, PLDI 2014, DOI 10.1145/2594291.2594324) [repo VERIFIED, adapton.org DNS 死] — versioned cell + lazy dirty 전파 개념만.
- **Fowler, "Event Sourcing"** (2005) — martinfowler.com/eaaDev/EventSourcing.html [VERIFIED] — External Queries 게이트웨이: 외부 질의 결과를 최초 실행 시 기록, replay 땐 기록본 서빙 → 비결정 read의 결정론 replay. = S2 "judge에게 보여준 probe set 로깅" 처방의 정본. (요약기-경유 인용 — 출판 인용 시 원문 재추출 플래그.)

---

## 5. 차선 C — consistent cut (Chandy–Lamport)

- **Chandy & Lamport 1985** — "Distributed Snapshots: Determining Global States of Distributed Systems", ACM TOCS 3(1):63–75. DOI 10.1145/214451.214456 [Lamport 저자 PDF 추출 — verbatim]:
  > "We shall show that: (1) S* is reachable from S₀, and (2) S₄ is reachable from S*."
  - 기록된 전역 상태 S*는 실제 순간 상태와 다를 수 있으나 **일어날 수 있었던 일관 상태**로 보증됨 (S₀→S*→S₄ 도달성 샌드위치). = HSWM snapshot id가 "replay 가능한 인과-폐쇄 cut의 이름"이기 위해 필요한 정확한 보증. 단일-writer 현재엔 시퀀스 번호로 퇴화 (재판 #7 그대로).

---

## 6. 차선 D — DPO 타이핑 seam (CHU 공유 인터페이스)

- **Ehrig/Ehrig/Prange/Taentzer 2006** — *Fundamentals of Algebraic Graph Transformation* (EATCS). DOI 10.1007/3-540-31188-2 [VERIFIED] — 분야 표준 인용 [EEPT06]. Part III = typed **attributed** graph transformation: 속성이 대수-값 노드로 그래프에 삶 → "속성만 변경" 규칙 = 구조상 K≅L인 퇴화 span의 형식적 정의.
- **Lack & Sobociński, "Adhesive Categories"** — FoSSaCS 2004, LNCS 2987:273–288. DOI 10.1007/978-3-540-24727-2_20 [BRICS RS-03-31 PDF 추출]:
  > "Definition 3.1 (Adhesive category). … (i) C has pushouts along monomorphisms; (ii) C has pullbacks; (iii) pushouts along monomorphisms are VK-squares."
  - CHU 소유 층이 보증해야 할 공리 = 이 3줄. HSWM은 블랙박스로 소비.
- **Söldner & Plump 2024** — "Formalising the Double-Pushout Approach to Graph Transformation", LMCS 20(4:3). DOI 10.46298/LMCS-20(4:3)2024, arXiv:2312.15641 [PDF 추출] — **Isabelle/HOL 기계검증판**:
  > "Definition 4.1 (Parallel independence [EEPT06]). … parallel independent if there exists morphisms L1 → D2 and L2 → D1 such that L1 → D2 → G = L1 → G and L2 → D1 → G = L2 → G."
  > "Theorem 4.3 (Church-Rosser Theorem [EK76])…"
  - Isabelle 아티팩트: github.com/UoYCS-plasma/DPO-Formalisation. **도출 (합성, 인용 아님)**: 속성-전용 퇴화 규칙에선 pushout complement가 항상 존재하고 parallel independence가 **속성 read/write footprint의 집합 교차 검사로 퇴화** → 동시쓰기 정적 충돌검사.
- **NAC 정본**: Habel/Heckel/Taentzer 1996, "Graph Grammars with Negative Application Conditions", Fund. Inform. 26(3–4):287–313. DOI 10.3233/FI-1996-263404 [VERIFIED] — NAC 하에서도 Parallelism Theorem 성립 = 조건 달린 규칙에서도 independence 체크 유효.

### OSS (설계 참조 서열)

| repo | 검증 | license | 판정 |
|---|---|---|---|
| `jakobandersen/mod` (MØD) | VERIFIED, active (v1.0.0 2025, push 2026-07) | GPL-3.0 | **1순위 설계 참조** — 진짜 DPO(모닉 매치) + PyMØD + GML `left[]/context[]/right[]` 직렬화 = span 그대로. 화학 부분 무시 |
| `Kappa-Dev/ReGraph` | VERIFIED, 저활동 | MIT | **파이썬 최근접 조상** — `Rule(p,lhs,rhs,p_lhs,p_rhs)` span 자료구조 + `added/removed_*_attrs` 메서드. ⚠ **SqPO ≠ DPO**: `cloned_nodes()/merged_nodes()` 비어있음 강제로 배제. independence 체커 없음(이론에서 가져옴). **hierarchy(그래프가 그래프로 타이핑) = HSWM↔CHU seam의 기성 패턴** |
| `UoYCS-plasma/GP2` | VERIFIED (2024-04) | GPL-3.0 | interface(=K) 명시 텍스트 규칙 문법 — "interface = LHS 전체" 가 퇴화 규칙 표기법. 같은 그룹의 DPO-Formalisation과 짝 |
| GROOVE (`nl-utwente-groove/code`) | VERIFIED, active (7.5.3 2026-07) | 미확인 (역사적 Apache-2.0) | **SPO+NAC이지 DPO 아님** — 단일그래프+역할주석 규칙 인코딩만 참고 |
| AGG | 홈페이지 404 (2026) | 미확인 | 문헌-전용 (EEPT06 Ch.15). critical-pair 분석 = 정적 체크의 고전 동적 대응물 |

### 하이퍼그래프 DPO 재고 (정직 헤드라인)

**유지보수되는 하이퍼그래프-DPO 파이썬 라이브러리는 세상에 없음 (NOT_FOUND).**
- `pnnl/HyperNetX` (BSD-3, v2.4.3 2026-04) · `HGX-Team/hypergraphx` (BSD-3, v1.8.0 2026-05): **분석 전용, 리라이팅 없음** — host 자료구조로만.
- `smimram/hyper`: 자유 하이퍼그래프 범주의 string-diagram 리라이팅 (소규모 연구코드, DPO 여부 불명). 이론 히트: arXiv:2406.15882 "Equivalence Hypergraphs: DPO Rewriting for Monoidal E-Graphs" (검색-검증만).
- `opencog/atomspace`(비-DPO 질의 리라이트, 부적합) · `met4citizen/Hypergraph`(울프람-스타일 JS 시각화 — 존재 기록만, scope guard상 해석 수입 없음).
- **함의**: 하이퍼그래프-DPO 커널 = 인하우스 (MØD 규칙모델 + ReGraph span 자료구조 + Söldner-Plump Def 4.1 스펙, HyperNetX-또는-dict host 위).

---

## 7. 통합 정직 갭 ledger

1. verbatim 실패 (페이월/403): Church–Rosser 1936, Newman 1942, Winskel 1987 — 서지만 확정, 인용은 Huet/Baader-Nipkow 경유.
2. 파이썬 부재 2건: provenance-semiring 라이브러리 / 하이퍼그래프-DPO 라이브러리 — **둘 다 신규 구현 대상** (설계도는 각각 GKT+ProvSQL / MØD+ReGraph+기계검증 정의).
3. license 미확인 2건: CSI (논문상 LGPL, 페이지 침묵) · GROOVE (LICENSE.md 존재, 명칭 미확인) — 코드-수준 재사용 전 확인.
4. 호스트 다운 (2026-07-20 기준): CoCo/COPS · AGG 홈 · adapton.org · HAL(Anubis) · York PURE — 전부 대체 검증 경로 기록됨.
5. 요약기-경유 인용 (byte-exact 필요 시 재추출): Huet abstract, SSS 2011, salsa docs, Fowler, CoCo 2019.
6. Gorard QM 논문 arXiv 부재 — 저널 DOI 인용.
7. 방향성 정밀도: confluence ↔ causal invariance는 필요/충분이 비대칭 (§1 주의 박스) — 동일시 서술 금지.

## 8. 다음 배선 (EPWC 처방 ↔ 이 재고)

| PROM_WOLFRAM 처방 | 집행 시 인용/도구 |
|---|---|
| S1 event-id dedup CRDT 격상 | RR-7506 §2.3.1+§3.3.1 (G-Set CvRDT) + automerge op-identity |
| 2-스트림 replay pack (S2 probe 로깅) | Fowler External Queries + RR-7506 §2.4 (op-based 전제) |
| teeth test 4종 | Hypothesis stateful (`RuleBasedStateMachine`) — shrinking으로 최소 반례 |
| admission rule (pairwise commutation) | Plump 2005 (joinability 불충분·결정불능) → RR-7506 Def 2.6 + ACP commutation 모드 (오프라인) |
| 쓰기-이벤트 레코드 | PROV-DM 어휘 + `prov` (MIT) 또는 PROV-JSON 직접 방출 |
| blame attribution | GKT Prop 4.2 (보편성) + ProvSQL circuit 설계 + Kappa stories 압축 |
| snapshot id = consistent cut | Chandy–Lamport 도달성 샌드위치 (epoch fence의 형식 근거) |
| 쓰기-op DPO 타이핑 (CHU seam) | Söldner-Plump Def 4.1 (기계검증) + MØD GML + ReGraph hierarchy 패턴 |
