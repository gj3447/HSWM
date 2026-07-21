# field-of-fields 이론 지반 — 정직한 감사 (2026-07-21)

> **목적**: PROM 검색 실험(ML1–ML5, `README.md`)이 발견한 "field-of-fields는 REAL이나 CONDITIONAL"을 확립된 이론에 바인딩. 5개 후보 이론을 1차 문헌으로 긁어오되 **내 매핑을 적대적으로 검증**함(자가비판 유지).
>
> **메타-결론 (중요)**: 5개 이론 **전부 STRETCH** 판정. 방향은 다 맞지만 나(claude)는 각 이론의 *직접성/엄밀성*을 과장했다. 방어가능한 핵은 좁고 단단하다. 이 문서는 SECONDARY_AI 연구 grounding(정전 아님) — source=claude.

---

## 0. 유일하게 robust하게 VALID한 것

**"재투영(같은 데이터를 결정론적 함수로 변환)은 정보를 *더할 수 없다*."** 두 독립 이론이 같은 것을 말한다:

- **데이터 처리 부등식 (DPI)** — Cover & Thomas, *Elements of Information Theory* 2nd ed. (Wiley 2006) §2.8 Thm 2.8.1, Cor. p.35: $Z=g(X)$ ⟹ $I(Y;X)\ge I(Y;g(X))$. "functions of the data cannot increase information."
- **앙상블 ambiguity 항등식** — Krogh & Vedelsby 1995 (via Wood et al., *"A Unified Theory of Diversity in Ensemble Learning"*, JMLR 24, 2023): 모든 멤버가 동일(재투영)이면 ambiguity항 $\frac1m\sum(q_i-\bar q)^2=0$ → 앙상블 이득 0.

→ **ML1–ML3(재투영 다층)이 단일층을 못 이긴 것의 정보이론적 하한**. 이게 이 조사에서 유일하게 "증명"이라 부를 수 있는 조각.

**단, 즉시 정정**: DPI는 *정보 상한*만 보장하지, AUC가 반드시 떨어진다고는 안 한다. AUC는 코사인 유사도(≠베이즈 최적)의 경험적 분리력이고, **손실 사영이 downstream metric을 오히려 돕는 표준 반례가 존재**(LDA/Fisher, PCA denoising — nuisance 차원 제거로 성능↑). ML3에서 실제로 AUC가 떨어진 실원인 = "DPI"가 아니라 **10개 anchor축이 gold 신호와 정렬 안 됨(신호는 버려진 374차원에)**이라는 별도 경험적 사실.

---

## 5개 이론 감사표

| 이론 | 1차 출처 | 판정 | 정정된 정확한 진술 |
|---|---|---|---|
| **DPI** | Cover & Thomas 2006 §2.8 Thm 2.8.1 | **STRETCH** | 형식(정보 못 늘림) VALID. "DPI가 AUC 하락을 설명" WRONG — AUC≠MI, 코사인≠베이즈최적, LDA/PCA 반례. 하락 실원인=anchor 신호 미정렬 |
| **앙상블/Condorcet** | Condorcet 1785; Krogh-Vedelsby 1995 (Wood JMLR24 2023); Ueda-Nakano 1996; Jain arXiv:1604.07711 | **STRETCH** | "entity>text=앙상블"은 **WRONG**(단일 feature 비교). "재투영 무익"=VALID(ambiguity=0). "탈상관→이득"=미측정 가정. **fusion(0.697)<entity단독(0.708)은 이론이 정확히 예측**(≤평균만 보장, ≤최강 아님). Jain: 다양성 무조건 이득 아님(약멤버가 강멤버 희석) |
| **Co-training** | Blum & Mitchell 1998 COLT; Balcan-Blum-Yang 2004 NeurIPS; Abney 2002; Nigam-Ghani 2000; Krogel-Scheffer 2004; Kumar-Daumé 2011 ICML | **STRETCH** | 알고리즘 오귀속(준지도 분류≠우리 비지도). ML4서 조건부독립 **위반**(entity가 text서 추출=공통원인). 단 *다중뷰 원리*는 전이 — 관건은 확률적 독립 아니라 **오류 비-중복성**(Krogel-Scheffer: 의존도 임계 이하면 이득) |
| **하이브리드검색/RRF** | Cormack-Clarke-Büttcher 2009 SIGIR (RRF k=60); Thakur 2021 BEIR arXiv:2104.08663; "Balancing the Blend" arXiv:2508.01405; RAG-Fusion arXiv:2603.02153 | **STRETCH** | RRF 방법 VALID. **ML5는 "fusion 이긴다"의 확증이 아니라 weakest-link 실패모드 사례**. RRF는 rank-noise엔 강건, **확신 있는 계통적 오답 승격엔 안 강건**(=ML5 web場). entity-Jaccard는 BM25 아니라 sparse의 좁은 특수사례(entity-exactness만) |
| **Gated/weighted fusion** | inverse-variance weighting(BLUE); Jacobs-Jordan-Nowlan-Hinton 1991 MoE; Shazeer 2017 arXiv:1701.06538; Markovits-Shtok-Kurland-Carmel CIKM 2012; DAT arXiv:2503.23013 | **STRETCH** | IVW는 "동일모수 unbiased 기지분산" 요구(우리 세팅 없음). MoE 게이트는 **학습됨**(우리 dispatch는 hand-tuned rule). "정밀도 가중>균일"의 *형태(shape)*만 VALID. 진짜 근거=retrieval-native 문헌(Markovits, DAT) |

---

## 진짜 지반은 검색-융합 문헌 (거대이론 아님)

거대 이론(정보/학습이론)은 **교육용 유비(analogy)**로만 유효. field-of-fields 발견의 **직접적·같은-도메인 근거**는 IR fusion 문헌:

1. **Cormack, Clarke & Büttcher 2009 (SIGIR)** — 무가중 RRF가 여러 *합리적* 시스템 융합 시 우수. 단 "관련 없는 도메인 섞어도 안전"은 아님.
2. **"Balancing the Blend" arXiv:2508.01405 (2025)** — **weakest-link effect** 실증: 약한 path 하나가 전체 정확도 크게 저하 → 융합 전 path-wise quality assessment 필요. = ML5 정확히 그 현상.
3. **RAG-Fusion 산업배포 arXiv:2603.02153** — noisy/off-topic query 확장이 RRF 융합 "오염" → 필터링+variant별 가중 권고. "raw expansion+blind fusion은 프로덕션 불충분" 명시.
4. **Markovits et al. CIKM 2012** — query performance prediction으로 per-query 차등가중 fusion이 uniform 능가.
5. **DAT (Dynamic Alpha Tuning) arXiv:2503.23013 (2025)** — LLM이 쿼리별 소스 신뢰도 측정→hybrid weight α(q) 동적조정 → +2~7.5pp. **= 우리가 원한 "소스별 신뢰도 측정 후 가중"의 실측 사례.**

**단 정정**: "가중이 항상 무가중보다 낫다"도 STRETCH — Cormack 원논문은 성분이 비슷한 수준일 땐 무가중이 학습형도 이겼다. 정확한 조건부 명제 = **"성분 품질이 비대칭적이거나 한 성분이 도메인 이탈일 때만 가중/필터가 blind RRF를 이긴다."**

---

## 실험 ↔ 문헌이 예측한 것 (수렴)

우리 자가비판 영수증은 성숙한 문헌이 문서화한 것을 **독립 재현**했다:

| 영수증 | 문헌 예측 | 정합 |
|---|---|---|
| ML1–3 재투영 null | DPI/ambiguity: 재투영 정보 0 | ✅ |
| ML4 독립場 이득이나 fusion<entity단독 | 앙상블: ≤평균만 보장, 다양성 무조건 이득 아님(Jain) | ✅ 이론 정확히 예측 |
| ML5 aggregate net-zero + off-domain場 해침 | RRF weakest-link(Balancing the Blend), noisy expansion 오염(RAG-Fusion) | ✅ 교과서적 실패모드 |
| "field-quality 가중이 fix" | per-query adaptive weighting(Markovits, DAT) | ✅ 직접 근거 |

---

## HSWM 정전과의 바인딩

- **HSWM "weight-semantic map"의 weight = 場-품질/관련도 가중** — DAT/weighted-RRF가 실측 지지. 균일 융합(현 PROM 암묵)은 weakest-link에 취약.
- **정전 `7cmd-measurement-driven-conditional-dispatch`** = per-source measurement→threshold gate. **구조적으로 per-query adaptive fusion과 동형**. 단 MoE의 *학습된* 게이트와 구별: 우리 것은 "MoE-inspired hand-tuned reliability gate."
- **롱기누스 weight-semantic 바인딩** = 場 간 엣지에 관련도 가중을 싣는 것 — 이 문헌들이 "그 가중이 measured여야 한다"를 요구.

## PROM 실제 fix (이 조사의 공학 산출)

현 PROM Step 3/4를 고치는 문헌-지지 설계:
1. 인터넷場 + KG場을 **무조건 RRF 섞지 말 것**(weakest-link).
2. **場별 관련도를 측정**(query performance prediction류)해 **가중/필터** 융합(DAT식 α(q)).
3. 場이 관련 신호 없으면(off-domain/sparse-coverage) **그 場을 배제** — measurement-driven conditional dispatch.

---

## 정직 경계

- 5 이론 전부 STRETCH — 이 문서의 가치는 "5 정리로 증명"이 아니라 **"어느 조각이 rigorous(재투영 무익)이고 어느 게 analogy(거대이론)이며 진짜 근거가 어디(IR fusion 문헌)인지" 정직하게 가른 것.**
- arXiv 2508.01405 / 2603.02153 / 2503.23013은 최신(2025~)이라 에이전트 web 확인분 — 핵심 논지는 고전(Cover-Thomas, Blum-Mitchell, Cormack 2009, Krogh-Vedelsby, Jacobs 1991)이 받침.
- n=24 toy gold + 6개념 legend-recall은 소규모. 문헌 정합은 강하나 우리 실측 자체는 예비적.

**한 줄**: 사용자 "여러 場을 엮으면 낫다" 직관은 **IR fusion 문헌이 직접 확증**하되 *상보적·비대칭품질일 때 가중해서*라는 단서가 붙는다. 거대이론(DPI/앙상블/co-training/MoE)은 그 직관의 여러 측면을 비추는 유비이지 증명이 아니며, 내가 그 직접성을 과장했다 — 이 감사가 그걸 바로잡는다.
