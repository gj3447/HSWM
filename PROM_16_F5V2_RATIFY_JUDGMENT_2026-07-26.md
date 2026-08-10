# PROM 16 — F5v2 retrieval-time consolidation prereg ratify 판단 (2026-07-26)

> cycle_id: `prom16-hswm-f5v2-ratify-20260726` · N=16 (4축×4렌즈, 16/16 수확, 충돌 0) · 도구: Kimi Code CLI
> 대상: `PREREG_F5V2_RETRIEVAL_TIME_CONSOLIDATION_2026-07-26.md` (DRAFT, USER ratify 대기)
> raw: `_findings/prom16-hswm-f5v2-ratify-20260726/` (16 JSON) · KG: Lesson `lesson-prom16-hswm-f5v2-ratify-20260726` + RF 16 verified + seed 9 + plan 3

## 0. 사전 지식 (하계 pre-fetch)

- F5 sealed(07-25): write-side downscale K1 kill (slope −0.158 vs append-only −0.097, CI [−0.098,−0.024]) — "downscale 역설", 연산자 폐기 확정.
- 외부 재현 3종 인용값: CogCanvas 2601.00821 (+15.9pp) / ARC-AGI 계열 2605.12978 (54% 회귀) / Neuromem 2602.13967 (F1 −50%).
- **이번 사이클 원문 대조 결과: 인용 arXiv ID 6종(위 3 + Infini-Memory 2606.10677 / sleep-time 2504.13171 / Auto-Dreamer 2605.20616) 전부 실재 + 핵심 수치 일치** (implementation-benchmarks 셀이 1차 대조).

## 1. Consensus (6)

- **C1 = ratify-with-amend (16/16, shelve 의견 0)** — write-side lossy consolidation의 detail 파괴는 LLM메모리·DB·모니터링·인지과학 전 분야에서 동일 메커니즘으로 재현되는 보편 법칙. A(append-only)/B(RT)/C(dedup+gated) 비파괴 arm 구성 + D 적대 대조는 역사적 실패 모드와 정확히 정렬. 방향 자체에 이견 없음.
- **C2 = arm B에 latency/token-cost 의무 2차 metric + 비용 상한 사전 고정** — DB 선례에서 append-only가 지는 지점은 항상 read 측(read amplification). 현 prereg은 detail slope + QA acc만 있음. LLMLingua 20×/1.5pt를 비용 레퍼런스로.
- **C3 = Infini-Memory 인용 정정** — 2606.10677은 buffer→topic document로 주기적 쓰기하는 **write-side consolidation** 논문. arm B의 read-time 선례로 인용 부정확. 정확한 참조 = CogCanvas "defer the decision to query time" + sleep-time compute(2504.13171). (참고: sleep-time 원문이 "query predictability와 효능 상관"을 직접 보고 — K3의 직접 선례 확인.)
- **C4 = arm B 정체성 결정 필요 (유일한 설계 tension)** — 형식문헌(RECOMP/QFS/late-interaction)상 query-conditioned read-time 재조립은 **retrieval reorganization/QFS**로 분류됨. 두 갈래: (i) 선제적으로 "query-focused reassembly(QFR)"로 rename + 기존 명명정정 규칙 유지, vs (ii) arm B를 **B'**(query-agnostic 사전 주제블록 재조립 + durable cache, 후속 쿼리 재사용)로 재정의 — sleep-time amortization(2.5×/쿼리)과 정합, 진짜 consolidation signature(지속성·파생신규성·쿼리비조건성 3축) 충족. **사용자 결정 사항.**
- **C5 = 통계 판정층 경화** — K1을 "CI 0 제외"에서 **비열등성**(B/C−A slope CI 하한 > −δ, δ=F5 캐논과 일치, cluster bootstrap ≥1000, MDE=F5 잔차 σ로 사전 산정)으로 재기술. K3의 ρ<0.3 점추정 hard kill → **CI 전체가 0.3 미만일 때만** claim 축소 + 상호작용 검정 파워 산정(16× 규칙상 불가하면 K3를 exploratory scope-note로 강등). judge catch-rate는 adversarial canary 주입으로 사전 측정.
- **C6 = arm C = Graphiti식 bitemporal-lite 명시** — invalid_at 마킹은 Graphiti/Mem0 v3 ADD-only의 산업 선례 존재(신규성 주장 과장 금지). observer-gate 불변식(향후 물리 삭제는 reader 보호 창 후에만) + mutation-time 발화 고정. CRDT supersession은 단일-writer 근거 부재로 Phase B federated 전용 유보.

## 2. Divergence / 미해소 tension

- C4(arm B 명명/설계)가 유일한 분기 — 사실 충돌이 아니라 설계 선택. 나머지 15셀은 방향 일치. open conflict = 0.

## 3. Singleton (VERIFY, 저신뢰 플래그)

- S1: gist 강화는 false memory를 키움(FTT phantom recollection) — K4 judge에 DRM식 related-but-unstated lure probe 포함, gist 단독 상승은 detail 개선 근거 사용 금지.
- S2: belt-halt(2연속 kill) 전 conditional-power < 0.15~0.20 확인 의무화(Lan-Simon-Halperin) + shelve 범위는 검정된 연산자 클래스로 한정.
- S3: arm B에 B0(extractive-only reassembly: MaxSim 문장선택+출처, abstractive 없음) 대조군 — 이득의 귀속(재조립 vs re-ranking) 분리.

## 4. 권장 후속 작업 (ActionPlan)

1. `plan-hswm-f5v2-prereg-amend-v2-20260726` (ACTION/HIGH): amend 10종 반영 — ①인용 정정 ②비용 metric ③B0 대조군 ④arm B 명명(사용자 결정) ⑤K1 비열등성 ⑥K3 CI화 ⑦judge canary+entailment+출처검증 ⑧arm C bitemporal 명시 ⑨belt-halt 조걶 ⑩gist 이중렌즈+DRM lure.
2. `plan-hswm-f5v2-user-ratify-decision-20260726` (ACTION/HIGH): 사용자 ratify 판단 — **분기 = C4만**, 나머지는 amend 수용 여부.
3. `plan-hswm-f5v2-dev-smoke-after-ratify` (FUTURE): ratify 후 dev 스모크(D arm 역설 재현 확인) → 머신락 → sealed (F1 sealed 완료 후 직렬).

## 5. 정직 경계

- arXiv 6종 실재·수치 일치는 이번 사이클이 원문 대조한 것. 단 subagent 4셀은 MEDIUM confidence(implementation-alternatives/pitfalls, limitations-benchmarks) — 해당 권고는 amend 수준 참고.
- "ratify-with-amend"는 리서치 합의일 뿐 **ratify 자체가 아님** — prereg은 사용자 verdict 전까지 DRAFT 유지.
- Infini-Memory를 read-time 선례로 인용한 현 DRAFT §2 표기는 부정확이 확인됨 — amend ①의 근거.

## 6. 후속 공학 disposition (2026-07-26, Codex)

- 사용자 발화 "F5v2 진행좀 해줘봐"에 따라 amend와 오프라인 구현을 진행한다. 이 발화를
  C4의 특정 설계에 대한 사용자 정전으로 소급 해석하지 않는다.
- C4 공학 선택은 **B′ query-agnostic durable slow-W/H consolidation**이다. CPL1의 real
  numeric packet+provenance를 query 공개 전에 rule/exception state로 합치고 raw episodic
  provenance는 byte-immutable하게 보존한다.
- QFR은 폐기하지 않고 `R_QFR_EPHEMERAL` strong retrieval control로 분리한다. B0는 같은
  source cut의 query-agnostic extractive durable cache라서 caching과 derived synthesis의
  기여를 분해한다.
- KG ORDERED v2의 `F1→B22→P1v5→P2→P3→P4`가 우선한다. 현재 F1 r3가 active이므로
  F5v2 live dev, machine-lock, sealed prep/run은 out-of-order다. 지금 생성하는 코드는
  offline-only이며 P4가 유일 active gate가 될 때까지 측정 권한을 갖지 않는다.
- amend 10종의 구체 잠금은
  `PREREG_F5V2_RETRIEVAL_TIME_CONSOLIDATION_2026-07-26.md` v2에 있다.
