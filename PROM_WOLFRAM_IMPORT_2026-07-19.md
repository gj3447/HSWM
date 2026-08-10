<!-- PROVENANCE
Workflow: wolfram-import-assessment (wf_16225251-b87), ultracode, 6 agents (5축 리서치 + 종합), 512k tokens.
판정 집계(14행): IMPORT_MECHANISM 1(causal invariance→write confluence) / FORMALISM_ONLY 3 / ANALOGY 격리 3 / NUMEROLOGY_REJECT 7.
핵심 실측: S1 supersede 스트림 = 가환(순열 3.3e-16 동일) 그러나 idempotent 아님 → replay pack 이중적용 시 b 조용히 제곱부패 — P3 사고 replay pack 운영과 직결.
CHU 관계: 리라이팅-온톨로지 층은 CHU 소유(기존 흡수), HSWM은 참조만. 수비학 가드 7건 발동(우주론·양자·branchial·ruliad·창발차원·창발시간·THE-rule 전량 기각).
-->
# HSWM × Wolfram 물리 — 이식 판정 최종 문서

> 판정일 2026-07-19. 대상: `github.com/gj3447/HSWM` (로컬 `/Users/lagyeongjun/CD/SYMPOSIUM/GIT/HSWM`, 문서둥지 `/Users/lagyeongjun/CD/SYMPOSIUM/HSWM/`). 규율: 수비학 가드 (교차도메인 구조 유사 = 기본 NUMEROLOGY, 메커니즘 + 반증가능 payoff가 있어야만 이식). 코드 인용은 본 세션에서 로컬 실측 검증함.

---

## 1. 한 줄 판정

**Wolfram 물리에서 HSWM이 가져올 것은 우주론이 아니라 이산-이벤트 진화의 부기(bookkeeping) 규율 단 하나다: "필드 진화 = 쓰기-이벤트의 동시성 시스템"으로 취급하여, (A) 쓰기 순서 무관성(confluence)을 CRDT 대수로 강제·검증하고 (B) 쓰기-이벤트 인과 DAG를 PROV 어휘로 구체화한다 — 물리 해석(시공간·양자·branchial·ruliad·창발차원·창발시간)은 전량 기각하고, 리라이팅-온톨로지 층은 CHU 소유이므로 참조만 한다.**

집계: 6개 후보 매핑 계열에서 **메커니즘 이식 1건** (causal invariance → 쓰기-순서 confluence), **형식-어휘만 이식 3건** (causal graph→쓰기 DAG, DPO 타이핑 seam, foliation→consistent cut), **비유 격리 3건** (rewrite event, multiway, observer theory), **수비학 기각 7건**. 유일한 메커니즘 이식조차 수학의 출처는 Wolfram이 아니라 Newman/Huet/Church–Rosser + CRDT다 — Wolfram/Gorard가 기여하는 것은 *질문의 인스턴스*("필드 진화는 업데이트-순서 불변인가?")뿐이며, 정직한 attribution은 그렇게 기록한다.

---

## 2. 이식 판정표

| # | Wolfram 개념 | HSWM 대응 | Verdict | Payoff 한 줄 |
|---|---|---|---|---|
| 1 | Set substitution rule (DPO span L←K→R, adhesive category) | HSWM 쓰기 op를 "구조 불변·속성만 변경"인 퇴화 DPO 규칙으로 타이핑 | **FORMALISM_ONLY** | 쓰기 op의 read/write-set 명시 + DPO parallel-independence가 동시쓰기 정적 체크가 됨; CHU와의 유일한 타입 seam |
| 2 | Update event (파괴적 국소 치환) | supersede()/judgment 쓰기 | **ANALOGY_ONLY** | 없음(Wolfram 경유로는). 노출된 실제 갭 — supersede가 *무엇이 대체했는지*를 안 기록함 — 은 PROV/event-sourcing으로 고침 (superseding_edge_id 추가) |
| 3 | Causal graph (이벤트 의존 DAG) | 쓰기-이벤트 provenance DAG (= PROV used/wasGeneratedBy = Winskel event structure) | **FORMALISM_ONLY** | causal-cone 감사("이 edge가 왜 가라앉았나"), 인과순서-복원 replay 정리, causal-depth 기반 b-damping A/B 후보 |
| 4 | **Causal invariance** (모든 갱신 순서 → 동형 causal graph) | **필드 쓰기의 순서-무관성 (confluence of writes)** | **IMPORT_MECHANISM** | S1(supersede=가환 monoid)/S2(judgment=순서필수) 스트림 분리 + permute-replay teeth test + CRDT refactor → 동시세션 treadmill 실패계급 은퇴. §3-A 상세 |
| 5 | Multiway system (전 분기 실체화) | 동시세션 분기 / plan readout 탐색 | **ANALOGY_ONLY** | 없음 — 올바른 공학은 multiway를 *표현*하는 게 아니라 confluence로 *자명하게 만드는 것*; multiway 층은 CHU 소유 |
| 6 | Branchial space / branchial distance | "메모리 상태 간 의미 유사도" | **NUMEROLOGY_REJECT** | 없음 — foliation-의존(불변 아님), HSWM엔 분기 모집단 자체가 없음, 유일 잔여(충돌관계)는 #3-4가 이미 전달 |
| 7 | Foliation / 기준계 | 필드 스냅샷 | **FORMALISM_ONLY** (얇음) | receipt는 wall-clock이 아니라 쓰기-DAG의 consistent cut-id를 고정해야 함 (Chandy–Lamport); 단일-writer 현재엔 시퀀스 번호로 퇴화 |
| 8 | "우주=하이퍼그래프 ⇒ 물리 결과 전이" (창발기하·곡률) | W(e\|c) 필드 관측량 | **NUMEROLOGY_REJECT** | 없음 — 공유되는 건 컨테이너 타입뿐 |
| 9 | 양자 독법 (superposition/entanglement/measurement collapse) | judgment 분기 / 검색 readout | **NUMEROLOGY_REJECT** | 없음 — readout은 비파괴·결정론·반복가능, 매핑이 자기모순 |
| 10 | 창발 차원 V(r)~r^d | "의미 차원" 지표 | **NUMEROLOGY_REJECT** | 없음 — 조밀-소풀 substrate서 2–3홉에 포화(INDEX.md §3 실측), 추정기가 정의불능 |
| 11 | Ruliad | "모든 가능한 judgment 위의 필드" | **NUMEROLOGY_REJECT** | 없음 — CHU가 더 강한 버전을 3축 반증 완료(LakatoTree `rejected`), a fortiori 상속 |
| 12 | 창발 시간 (리라이팅=시간) | 필드 진화=시간 | **NUMEROLOGY_REJECT** | 없음 — HSWM엔 자율적 규칙 적용이 없음(외생 LLM-judgment가 예약 발화), 창발할 것이 없음 |
| 13 | Observer theory (계산적으로 유계인 관찰자) | LLM reader = 필드의 유계 coarse-graining | **ANALOGY_ONLY** | 문서에 태그된 프레이밍 한 문장까지만; 설계 결정의 근거로 인용 금지 (근거는 prereg 실측만) |
| 14 | 보존법칙/열역학 전이 + "THE rule 탐색" | weight flux 보존 / update-rule 학습 | **NUMEROLOGY_REJECT** | 없음 — 후자는 사내에서 이미 실측 반증됨 (cosine 0.956 ≫ learned 0.649, jaebaeman v3 2026-07-19); 재제안은 회귀 |

---

## 3. 최상위 이식 상세 (2건)

### 3-A. Causal invariance → 쓰기-순서 confluence — 유일한 메커니즘 이식

**근거 다리 (검증된 인용)**: Gorard는 causal invariance를 "all causal graphs isomorphic irrespective of updating order"로 정의하고, 비-confluence일 때 "causal invariance is explicitly violated, as a consequence of non-confluence of the underlying rewriting system" (Complex Systems 29(2):537–598, 2020)이라 명시한다. Wolfram 자신도 이것이 "essentially the confluence property discussed in the theory of term-rewriting systems"라 인정한다(wolframphysics.org technical introduction). 즉 수입되는 수학은 Church–Rosser(1936)/Newman(1942)/Huet(1980)이고, 산업형 후예는 CRDT(Shapiro et al. 2011)다. 일반공변성 독법은 버린다.

**HSWM 현재 코드에 대한 즉각 판정: HSWM은 causally invariant하지 않다 — 그리고 그 경계선이 코드 구조에 이미 그어져 있다.**

- **S1 스트림 (supersede) — 이미 confluent, 단 idempotent 아님**. `readouts.py:88` (`field.hg.base_salience[edge_id] *= decay`, decay ∈ (0,1], 실측 확인): 양의 실수 곱은 가환 monoid 작용이므로 supersede 멀티셋이 순서와 무관하게 b를 결정한다. log 영역에서 `log b(e) = Σ_i log δ_i` — 음의 증분 G-Counter. 실측(400-이벤트 로그, 50 edge): 순열 후 max rel diff 3.3e-16, allclose PASS. **그러나 중복 적용 시 0.5-decay 2회 = 0.25** — op-based CRDT라서 exactly-once 전달이 전제다. 프로젝트는 실제로 replay pack을 굴린다(P3 사고, `PI/kg_replay_session_20260719.cypher`) — 이중 적용된 pack은 b를 *조용히* 제곱-부패시킨다.
- **S2 스트림 (judgment) — confluent 아니고, 만들 수도 없다**. `llm_judgment_loop.py:84–105` (실측): `probe = pool[np.argsort(-s_pool)[:topk_probe]]` — 어떤 edge가 판정을 *받는지 자체*가 현재 M의 함수이고, `M = M - lr*(grad/n)`은 자기가 읽는 상태를 쓴다. 라운드 내부는 frozen-M 누적이라 순서무관(≤ulp), 라운드 간은 본질적으로 순차. SGD류 갱신은 가환화가 불가능 — 정직한 처방은 "순서를 보존하고 그 사실을 문서화"다.

**처방 (코드 변경 3건 + 테스트 1파일)**:

1. **이벤트-id dedup으로 S1을 state-based CRDT로 격상**: 적용된 event-id의 G-Set을 semilattice로 삼고 `b(e) = ∏_{i∈S} δ_i` — 복리(compounding) 의미론을 유지하면서 중복 내성 획득. (대안 `b := min(b, x)`는 공짜 idempotent지만 N회 독립 supersession의 복리를 죽임 — Eilu-va-Eilu 의미론상 기본값은 dedup-곱셈, min은 at-least-once 채널용 config.)
2. **replay pack 포맷을 2-스트림으로 분리**: S1 = 무순서·병합가능·id-dedup / S2 = 시퀀스 번호 + **judge에게 실제 보여준 probe set을 로그** (Fowler의 logged-external-query 수법 — 스코어링 코드가 tie를 바꿔도 replay가 동일 M을 재유도).
3. **λ/μ 인증 = epoch fence**: 인증은 순차·스냅샷 의존(PROM_TRAVERSAL_DESIGN §5)이므로 로그에 epoch 번호를 달고 순열은 epoch 내부에서만 합법.

**Teeth test 스펙 — `tests/test_field_confluence.py` (~150 LOC, numpy-only, 기존 `test_falsifier_teeth.py` 관습 준수)**:

| 테스트 | 조작 | 오라클 | 기대 |
|---|---|---|---|
| T1 | S1 supersede 로그를 R회 무작위 순열 | `np.allclose(rtol=1e-9)` + retrieve() top-k edge-id 열 동일 + 인접쌍 \|ΔW\|<1e-12 fragile-tie 플래그 | **PASS 필수** |
| T2 | 동일 replay pack 2회 적용 | dedup 있으면 필드 불변 / **dedup 제거 시 반드시 FAIL** | 음성 오라클 (테스트에 이빨이 있음을 증명) |
| T3 | S2 judgment 라운드 순열 | 필드가 **달라져야** 함 | 음성 오라클 — 비-invariance가 우발이 아니라 문서화된 설계임을 인증 |
| T4 | λ/μ 인증 이벤트를 가로지르는 cross-epoch 순열 | 인증값이 달라짐 | fence의 음성 오라클 |

**부동소수점 계약**: IEEE-754 곱/합은 가환이지만 결합적이지 않고, 모든 readout이 argsort/argmax로 이산화하므로 1e-16 섭동이 near-tie를 뒤집어 루프에서 증폭될 수 있다. confluence 계약은 **rank 수준**으로 서술한다(위 T1 오라클). 비트 수준을 원하면 event-id 정렬 fold로 canonical화 — 그러면 어떤 전달 순서에서도 비트 재현.

**이론이 강제하는 설계 규칙 (Plump 가지치기)**: 하이퍼그래프 리라이팅의 confluence는 종료 조건下에서도 **결정불능**(Plump 1993)이고, graph rewriting에선 critical-pair joinability가 국소 confluence를 함의하지 않는다(Plump 2005). 또한 HSWM 필드는 종료하지 않으므로 Newman's lemma가 아예 적용 불가 — confluence는 사후 검증이 아니라 **대수적 화이트리스트로 설계 시점에 강제**해야 한다. → `HSWM_STANDARD`에 1페이지 admission rule: *새 필드-쓰기 op는 기존 모든 S1 op와의 pairwise-commutation pytest를 동봉하거나(현재 1개, 유한·저렴) S2/ordered로 선언해야 한다.* 결정불능인 전역 성질을 결정가능한 유한 체크리스트로 바꾸는 것 — 이것이 결정불능성 결과가 강제하는 정확한 공학적 수다.

### 3-B. Causal graph → 쓰기-이벤트 DAG + blame attribution — 형식 이식 + 비-Wolfram 메커니즘 3종

**어휘는 PROV로 명명한다** (Wolfram-풍 신조어 금지): Activity = 쓰기 이벤트, Entity = 필드-성분 버전, 인과 edge = used/wasGeneratedBy 합성 wasInformedBy. Wolfram causal graph는 이 객체와 구조적으로 동일하며(본 세션 검증), 이미 프로젝트 정전에 있는 W3C PROV가 정본 어휘다.

**이벤트 레코드**: `(event_id, rule_type ∈ {judgment, supersede, bind, create}, read_set, write_set, causal_parents, epoch, payload)`. 인과 메타데이터는 **비가환 조각(S2)에만 의무** — 가환 S1은 인과 부기가 아예 불필요하다는 것이 이 이식의 핵심 절약이다.

**따라오는 정리와 반증기 (replay 정리)**: 인과 순서와 일관인 *임의의* 선형화가 동일 필드를 재생해야 한다. 반증 테스트: 기존 delta-replay pack의 추론된 이벤트 DAG를 20개 무작위 인과-일관 선형화로 재생 → 필드 rank-동일 assert. 발산하면 로그된 cause-set 또는 쓰기 가환성 중 하나가 틀린 것이고 버그가 국소화된다. 두 번째 반증기: judgment 쓰기에서 인과 메타데이터를 일부러 제거 → replay 발산을 보임으로써 메타데이터가 의례가 아니라 하중을 받음을 증명.

**Blame attribution (메커니즘, 출처 = provenance semiring)**: K≤3 절단 감쇠-보행 점수는 경로별 b(e)^κ 곱들의 합 — 문자 그대로 가환 semiring 위 provenance 다항식이며(Green–Karvounarakis–Tannen, PODS 2007), monomial = HSWM의 path receipt다. 파이프라인: ① path receipt가 답변별 기여 edge를 나열(이미 설계됨) → ② (edge, 성분)→최근 write_id 인덱스로 후보 blame set → ③ 용의 write를 되돌리고 K≤3 traversal 재실행(저렴) — 뒤집히는 write가 poisoning write, 상관이 아닌 **정확한 counterfactual**. 지상진실은 이미 repo에 preregister되어 있다: H-T3 stale-poisoning 실험(STALE_PER_Q/B_DOSE_GRID)의 주입 poison이 정답이므로 **blame@1**과 후보셋 크기가 즉시 측정가능.

**Invalidation은 DAG로 풀지 않는다 (기각된 세부-변형)**: Adapton/salsa식 값-단위 인과 DAG는 기각 — K≤3 PPR의 의존 cone은 도달 가능한 ball 전체로 퇴화(조밀)하고, v2 스펙이 이미 supersede에 대해 **구조적으로 invalidation 0**을 달성했다("b는 COO 구조 안이 아니라 별도 벡터", §2.4 실측 인용). 대신 **salsa durability의 조악한 변형**만 수입: 3개 revision counter (`topology_rev`/`b_rev`/`j_rev`), 캐시된 slow 성분은 자기가 읽는 rev에만 키잉. 반증기: 혼합 워크로드(supersede 1000 + judgment 100 + topology 10) → slow-component rebuild 횟수가 **정확히 10**이어야 하며, b/judgment 쓰기가 유발한 rebuild는 카운터가 탐지 가능한 버그다.

**보너스 A/B (저렴, prereg 가능)**: 인과 DAG의 hop-깊이를 wall-clock 대신 b-damping의 "의존-깊이 나이" 신호로 — 기존 substrate_bench(n=300) 하네스로 현행 time-decay 대비 A/B.

---

## 4. 기각 목록 (수비학 가드 발동 사유)

가드 규율: 교차도메인 구조 유사 = 기본 NUMEROLOGY. 각 항목은 메커니즘 테스트의 실패 지점을 명시한다.

1. **"우주=하이퍼그래프, HSWM=하이퍼그래프, 고로 물리 상속" (마스터 유혹)** — 공유물은 컨테이너 타입뿐. Wolfram 하이퍼엣지는 익명 튜플이 고정 국소 규칙에 의해 자율·파괴적으로 치환됨; HSWM 하이퍼엣지는 학습 가중장을 지닌 reified 의미 단위로 LLM-judgment가 발화할 때만 진화. 규칙도, 치환도, 자율성도 없음 = 메커니즘 공유 0. F1/recall에 대한 예측 0. "HSWM은 작은 Wolfram 우주다" 류 문장은 정전 금지, AI-comment 태그만 허용.
2. **Branchial space → 의미 유사도** — 이중 실패: (a) branchial 구조는 foliation 선택에 불변이 아님(Wolfram 문헌 스스로 인정 — causal graph와 결정적 비대칭); (b) HSWM엔 시점당 필드가 하나뿐, branchial graph가 될 분기 모집단이 존재하지 않음. HSWM 유사도=콘텐츠 임베딩 기하 / branchial 인접=반사실 상태 간 공유 리라이트 조상 — 생성 메커니즘 무공유, 상호 예측 0. 접지된 잔여(Winskel conflict relation)는 §3이 이미 전달.
3. **양자 비유 전반 (공유 hyperedge=entanglement, 검색=측정/붕괴)** — 자기 항에서부터 모순: HSWM readout은 비파괴·결정론(필드 given)·반복가능; 양자 측정은 파괴·확률·비반복. Gorard의 QM 유도는 causal invariance + 물리 해석 둘 다 필요하며 둘 다 contested (Aaronson "infinitely flexible", Harlow "at best qualitative" — Becker, SciAm 2020). 양자 어휘는 명시 태그된 rejected-correspondences 부록 밖에서 금지.
4. **창발 차원 V(r)~r^d → "의미 차원"** — 추정기가 정의불능: 대형·희소·근사균질 그래프의 manifold 극한을 전제하는데, HSWM substrate는 실측상 조밀-소풀로 ball 성장이 2–3홉에 포화 (traversal 반증과 같은 원인: hop_drop 정적 +0.241 < 순회 +0.354, 9/9 config, INDEX.md §3). d를 소비하는 readout도, d↔F1 prereg 예측도 없음. 기하 진단이 필요하면 이미 반증가능·이미 측정된 hop stratification(`_research/hop_stratification.json`)을 확장할 것.
5. **Ruliad → "모든 judgment 위의 메모리 ruliad"** — 사내 판례로 기각: CHU=Ruliad는 3개 독립 축(범주 오류 / limit-computable 비폐쇄 Limit Lemma witness / CUH-plenitude vs 유일-총체 존재양화 충돌)으로 반증 완료, LakatoTree 결정론 엔진 `rejected` (prereg 1.0 → 실측 0.0, `prom16-chu-ruliad-grounding-2026-07-15`). HSWM 버전(유한·코퍼스-조건 가중장)은 엄격히 더 약하므로 a fortiori 상속. 재개는 정전 drift.
6. **창발 시간 → "필드 진화 = 창발 시간"** — 자율성 전제 불일치: Wolfram에서 시간은 자율 규칙 적용의 진행 그 자체; HSWM에서 시간은 decay/log(b)로 들어오는 외생 wall-clock이고 진화는 외부 루프가 예약·판정. 전체 내용이 "둘 다 시간에 따라 변한다"인 대응 = 예측 0, 코드 변경 0. supersession 타임스탬프 부분순서는 평범한 PROV 부기이며 물리 광택이 필요 없음.
7. **보존법칙/열역학 + "THE rule 탐색"** — W(e|c)는 보존량이 아님(judgment가 비국소로 가중을 임의 주입·제거); Noether-풍 주장은 Gorard 유도의 모든 가설(자율성·파괴성·causal invariance)을 위반하는 시스템 위의 장식. rule-탐색 변형("HSWM도 자기 갱신규칙을 학습해야")은 **이미 실측 반증** — learned-weight 축은 실KG 측정(cosine 0.956 ≫ learned 0.649)으로 철회됨(jaebaeman v3, 2026-07-19). 재제안 = 연구가 아니라 회귀.

**절차 규정**: 위 개념이 재부상하면 science-feedback-loop 프로토콜대로 **NUMEROLOGY_HOLD Possibility 노드**로만 진입하며, 설계 입력이 될 수 없다. 해제 조건 = Wolfram측 정량 + HSWM측 관측량 + 예측된 단조 관계 + MC null의 4종 prereg (feedback_numerology_mc_discrimination).

---

## 5. CHU와의 관계 — 중복 흡수 금지

**소유권 판정: 리라이팅 형식론은 CHU가 이미 완전 소유. HSWM의 올바른 수는 재흡수가 아니라 참조이며, 승인된 흡수 화살표는 반대 방향이다.**

| 층 | 소유자 | 근거 아티팩트 |
|---|---|---|
| 리라이팅-온톨로지 (set substitution, rule 공간, multiway, rulial limit, HoTT 다리) | **CHU** | `prom16-wolfram-chu-ruliad-hott-2026-07-13` (16 RF); Arsiwalla & Gorard arXiv:2111.03460 Props 4.2–4.4 (pdftotext 검증); Lean `CHU_WolframRewrite.lean` (Trunc.collapse, exit 0, Mathlib-free); Rust `chu_core.rs` (실제 multiway explorer 34 states/33 edges + UnivalentStateStore) |
| CHU의 미해결 프론티어 | **CHU** | level≥2 higher rules → level≥3 / n→∞ colimit / HITs — HSWM 소관 아님 |
| Ruliad 반증 판례 | **CHU** | `lesson-chu-ruliad-identity-refuted-truncation-reframe-2026-07-15`; HSWM측 ruliad 주장은 이 판례를 경유해야 함 (§4-5) |
| **진화-부기 층** (이벤트, confluence, 인과 provenance — 구조적으로 준정적인 reified 하이퍼그래프의 *속성-쓰기*에 적용) | **HSWM** (본 문서 §3) | Wolfram과의 중복 0 — CHU는 구조-리라이팅 우주를, HSWM은 가중-속성 쓰기의 동시성 규율만 취함 |
| 양측 인터페이스 | seam 1개 | §2 행1의 퇴화-DPO 타이핑: HSWM 쓰기 = CHU가 흡수한 리라이팅 타입 내부의 attribute-layer 규칙 (K=L 구조, 속성만 변경) — 2차 흡수 없이 접속 |

**결정적 사실 (INDEX.md §5, USER 발화 2026-07-19)**: 승인된 방향은 *CHU가 HSWM의 가중장을 계산가능 하이퍼우주 타입의 한 층으로 흡수*하는 것이다. HSWM은 수입자가 아니라 **수입되는 쪽**이다. 따라서 HSWM이 Wolfram 리라이팅을 직수입하면 (a) CHU 정전과의 중복 drift (`feedback_canon_propagation_simultaneous` 위반), (b) 흡수 방향의 역행 — 이중으로 금지된다.

**실행 항목 (저렴)**: `HSWM_STANDARD.md`에 포인터 블록 1개 — "리라이팅 형식론: CHU dynamics 층 참조 (Lean/Rust 아티팩트). HSWM은 Wolfram에서 직접 수입하는 것이 없음; 수입물은 §3의 진화-부기(이벤트/confluence/provenance)이며 수학적 출처는 Newman/Huet/CRDT/PROV." 미래의 리라이팅-형식 수요는 전부 CHU의 기존 Lean/Rust 증명으로 라우팅.

---

## 6. 인용

**본 세션 fetch·검증 (venue 주의: Complex Systems는 Wolfram 창간·발행 저널, Gorard 논문 다수는 사실상 self-published 계열 — 물리 주장의 contested 지위와 일관)**

- S. Wolfram, "A Class of Models with the Potential to Represent Fundamental Physics", *Complex Systems* 29(2):107–536, 2020. doi:10.25088/ComplexSystems.29.2.107
- J. Gorard, "Some Relativistic and Gravitational Properties of the Wolfram Model", *Complex Systems* 29(2):599–654, 2020. arXiv:2004.14810 — causal invariance 정의; covariance 독법은 물리측으로 표기
- J. Gorard, "Some Quantum Mechanical Properties of the Wolfram Model", *Complex Systems* 29(2):537–598, 2020 — "causal invariance is explicitly violated, as a consequence of non-confluence of the underlying rewriting system" (인용 검증)
- J. Gorard, "Algorithmic Causal Sets and the Wolfram Model", arXiv:2011.12174 — 물리측 전량 기각 표기
- J. Gorard, M. Namuduri, X.D. Arsiwalla, "ZX-Calculus and Extended Hypergraph Rewriting Systems I", arXiv:2010.02752 — adhesive+DPO 정식화; multiway/branchial monoidal 구조
- X.D. Arsiwalla, J. Gorard, "Pregeometric Spaces from Wolfram Model Rewriting Systems as Homotopy Types", *Int. J. Theor. Phys.* 63 (2024), arXiv:2111.03460 — **CHU측 다리 객체, HSWM 비수입**
- Wolfram Physics Project, Technical Introduction, "The Phenomenon of Causal Invariance", wolframphysics.org — "essentially the confluence property…" (인용 검증)
- S. Wolfram, "The Concept of the Ruliad", writings.stephenwolfram.com, 2021-11-10; "Observer Theory", 2023-12
- A. Becker, "Physicists Criticize Stephen Wolfram's Theory of Everything", *Scientific American*, 2020-05-06 (Aaronson/Harlow 비판)
- Zhang, Lofgren, Goel, "Approximate Personalized PageRank on Dynamic Graphs", KDD 2016, arXiv:1603.07796 (invariant-restoring dynamic push, O(1) amortized — §3-B 조건부)
- Hammer et al., Nominal Adapton, OOPSLA 2015, arXiv:1503.07792 (기각된 세부-변형의 근거)
- Hellerstein, Alvaro, "Keeping CALM", arXiv:1901.01930 / CACM 63(9), 2020
- M. Fowler, "Event Sourcing", martinfowler.com (logged-external-query 규율)
- W3C PROV-DM, W3C Recommendation, 2013-04-30

**표준 문헌 (canonical, 본 세션 재-fetch 없음 — WebSearch 예산 소진 전 기존 검증분)**

- Church, Rosser, "Some Properties of Conversion", *Trans. AMS* 39, 1936
- M.H.A. Newman, "On Theories with a Combinatorial Definition of Equivalence", *Annals of Mathematics* 43(2):223–243, 1942
- G. Huet, "Confluent Reductions: Abstract Properties and Applications to Term Rewriting Systems", *JACM* 27(4):797–821, 1980
- Baader, Nipkow, *Term Rewriting and All That*, CUP 1998; Terese, *Term Rewriting Systems*, CUP 2003
- D. Plump, "Hypergraph Rewriting: Critical Pairs and Undecidability of Confluence", in *Term Graph Rewriting*, Wiley 1993; "Confluence of Graph Transformation Revisited", LNCS 3838, 2005 (OpenAlex 검증)
- Ehrig, Ehrig, Prange, Taentzer, *Fundamentals of Algebraic Graph Transformation*, Springer 2006; Lack, Sobociński, "Adhesive Categories", FoSSaCS 2004 / RAIRO-ITA 39(3), 2005
- Nielsen, Plotkin, Winskel, "Petri Nets, Event Structures and Domains, Part I", *TCS* 13(1):85–108, 1981; G. Winskel, "Event Structures", LNCS 255, 1986
- L. Lamport, "Time, Clocks, and the Ordering of Events in a Distributed System", *CACM* 21(7), 1978; Chandy, Lamport, "Distributed Snapshots", *ACM TOCS* 3(1), 1985
- Shapiro, Preguiça, Baquero, Zawirski, "Conflict-free Replicated Data Types", SSS 2011, LNCS 6976:386–400
- Lloyd, Freedman, Kaminsky, Andersen, "Don't Settle for Eventual" (COPS), SOSP 2011
- Green, Karvounarakis, Tannen, "Provenance Semirings", PODS 2007; Cheney, Chiticariu, Tan, "Provenance in Databases", *FnT Databases* 1(4), 2009
- D. Goldberg, "What Every Computer Scientist Should Know About Floating-Point Arithmetic", *ACM Computing Surveys*, 1991
- salsa-rs/salsa book (durability, red-green); rustc dev guide, Incremental compilation

**로컬 정전·실측 (본 세션 검증)**

- `/Users/lagyeongjun/CD/SYMPOSIUM/GIT/HSWM/readouts.py:78–88` (supersede 곱셈 감쇠); `llm_judgment_loop.py:84–105` (argsort probe + per-round M 갱신)
- `/Users/lagyeongjun/CD/SYMPOSIUM/HSWM/PROM_TRAVERSAL_DESIGN_2026-07-19.md` §2.4 (O(0) invalidation, b=별도 벡터), §4 (비트 재현은 고정-순서 한정), §5 (순차 인증 fence), H-T3 prereg 상수
- `/Users/lagyeongjun/CD/SYMPOSIUM/HSWM/INDEX.md` §1–3 (리프트 분해: 임베딩 정렬 ~95%; 순회 반증 hop_drop 정적 +0.241 < 순회 +0.354, 9/9), §5 (흡수 방향: CHU가 HSWM을 흡수)
- `/Users/lagyeongjun/CD/SYMPOSIUM/THEORY/CHU/PROM_16_RULIAD_GROUNDING_REPORT_2026-07-15.md`; `project_chu_wolfram_absorption_2026_07_13`; `lesson-chu-ruliad-identity-refuted-truncation-reframe-2026-07-15`; `project_jaebaeman_v3_semantic_weight_mapper_2026_07_19`; `PI/kg_replay_session_20260719.cypher` (P3 replay pack)

---

*판정 요약 재확인: 가져오는 것 = confluence-of-writes 메커니즘 1건(§3-A, teeth test 4종 동봉) + 형식-어휘 3건(쓰기 DAG·DPO seam·consistent cut, §3-B). 버리는 것 = 물리 독법 전부(§4, 7건 수비학 기각 + 비유 3건 격리). CHU 것은 CHU에(§5). 이 문서의 기각 목록은 향후 "메모리 필드의 창발 기하" 류 주장 전체에 대한 기본 판정(default verdict)으로 선다.*
