# PROM 16 — HSWM 현재 문제점 전수 감사 (2026-07-25)

> **2026-08-15 운영 정정:** 이 문서는 당시 상태의 역사 snapshot이다. 아래 LOCAL_WORKFLOW 세마포어
> 처방은 현재 규약에서 superseded되었으며 LOCAL_WORKFLOW는 RETIRED·역사 읽기 전용이다.

> 질문: **"지금 HSWM에서 문제점이 뭐냐?"** — 16 subagent (4축 × 4렌즈), read-only 감사.
> 축: A 과학적 미증명 게이트 / B 장부·재현성 / C 인프라·운영 / D 방향·가치. 렌즈: ①낶부 증거 ②외부 기준 ③함정·오탐 ④처방.
> Raw: [`_findings/prom16-hswm-current-problems-20260725/swarm_raw_16.txt`](../../_findings/prom16-hswm-current-problems-20260725/swarm_raw_16.txt) (16/16 완주, 충돌 0).
> 관련 장부: `HSWM_LOCAL_RECORD` (52노드), `HSWM_LOCAL_RECORD` (38노드), `hswm-ordered-research-harness-20260724`.

---

## 0. 사전 지식 (감사 시점 상태)

- 측정 판정: memory-substrate 사다리 1위 CONFIRMED / reasoner 대체로 REFUTED / C1 book-scale: hswm−clique −2.00pp novel kill / R3 walk lane +0.0111 생존(bf 0.584 박약).
- 게이트: ORDERED v2 정본, F1 active(패리티 수리 완료, sealed는 vLLM 윈도 대기), F2 sealed 실행 중(15:23 KST~), PREREG F2~F5 REGISTERED, foundation 2건 OPEN.
- 장부 알림: eureka hallucination 1.0, self-report 11+25건, Laudan 폐기후보 5+7가지.

---

## 1. Consensus

### C1. 장부 알림 3종은 "연구 부실"이 아니라 영수증·tier·집계 플러밍 문제 — 단 그 아래 효과 박약은 진짜다 (B①③④ 수렴)

- eureka hallucination 1.0은 **notebook tier 아티팩트**: 양 트리 모두 FF1 파일앵커 미적용 → server_anchored 0.211/0.077 → client float novel은 구조적으로 "확증 불가"로 집계. 게다가 집계≠개별: `B2-crossfield-merge-payoff`는 개별 eureka **true (BF 6.0)**인데 트리 집계는 true 0/hallucinated 31.
- 폐기후보 12 중 **최소 3건 오탐** — `hswm-ordered-causal-gates-20260724`(현재 활성 정본), `prom9-f1-actual-development-r4-20260724`(활성 F1 수리선), `R3-walk-regime-density-dial-v3`(유일 replay-verified 생존 가지). 원인: 예측적중 집계가 영수증 의존이라 client-asserted 노드는 구조적으로 0적중.
- "영수증 없는 self-report 36건"도 실제는 "영수증은 있으나 client_asserted 등급" — 디스크 영수증(GIT/HSWM/receipts/ 73파일)은 실재.
- **그러나**: substantial(BF≥3.162) 확증 novel 예측이 **0건**, fertility 3/15·1/31 — 효과 박약은 영수증에 명시된 실측 (R3 bf 0.584, r2-repair 4건 bf 0.167).

### C2. 방향 핵심 리스크: "hyper"graph의 n-ary 고유 기여가 측정값 0 — 프로그램 존립 증거가 F2 하나로 수렴 (D①②, A①② 수렴)

- C1 PRELUDE: clique(pairwise 축약, 동일 walk) 0.447 > hswm 0.427 — dense 대비 이득의 성분은 "n-ary 구조"가 아니라 "확산 재료" (`C1_PRELUDE_BOOKSCALE_RESULTS:4,17,23`). hswm−dense +3.16pp도 low-power라 우위 주장 보류.
- substrate 사다리 1위의 분해(`result-substrate-ladder-hswm-rank1-embeddings-carry`): 리프트 본체 임베딩 ~95% + 순수 구조 PPR **전 arm 최악**(0.373) + CRDT 원장(구조 무관). **현 상태에서 하이퍼그래프를 제거핮와 측정값이 변하지 않는다.**
- R3 걷기 승리는 pairwise 그래프 증거(n-ary 아님) + 박약(하한 0.00085) + retrieval-side만. 홉 층화 마진(3홉 +0.082)은 **clique 대조 미실시** — C1을 죽인 강한 null에 한 번도 대조된 적 없음.
- tribunal 생존 슬롯 4개 전원 = 미증명 claim(F2~F5 prereg 대상). **F2(ΔW credit ρ≥0.2)가 사실상 프로그램 존립 증거**인데 외부에서 HAGE(RL 엣지 크레딧, 2605.09942)·MERIT·Memento 등 outcome-기반 선행 등장 — F2 arm(Shapley/random/verbal-gradient 3종)에 outcome-기반 외부 대조 부재.

### C3. 측정 묵력: 현 설계대로면 F2~F5 판정이 ~coin-flip (A③④ 수렴)

- **파워**: n=100/arm, δ=0.08 기준 McNemar 근사 파워 ~40~60% (추정). "δ̂>0이지만 LCB≤0" 미정의 구간 — C1 +3.16pp low-power 판정이 동일 실패 모드 선례. noise_band 0.02는 실제 SE(~0.05)의 1/3.
- **ρ 게이트 이중 묵력**: ①입력 레슨 6개 고정 — n=6 Spearman 해상도 없음(임계 ~0.83) ②dev-φ vs dev-LOO(공유 V_cache) **자기데이터 일관성 검사**라 예측력 0이어도 통과 가능. dev-φ vs **fresh** LOO 여야 함.
- **run_verdict 미집행**: F2 dev는 VOID leakage split(t200 3형제, leakage=102) 위에서 "통과" 보고 — VOID가 기록만 되고 run을 멈추지 않음(`run_verdict` 정의만 있고 미배선). headroom **바닥(floor) kill 조건 부재** — dedup 수리 후 smoke `dev_base_accuracy=0.0`인데 run 계속. 현재 실행 중인 sealed가 이 함정에 해당할 수 있음(미확인).
- **F4 락 모순**: 머신락 n=30 vs 마스터 문서 n≥100. F4는 F2 통과(학습된 W*) 전제인데 의존 미선언.

### C4. F3/F5는 실행 수단이 없고, 최신 선행이 prereg을 갉아먹었다 (A①②, D② 수렴)

- foundation 2건(`multi-agent-transfer-harness`, `semantic-weight-metric-contract`) = KG `needed`, 하네스/metric 미존재 — PREREG만 잠금.
- **F3**: MemTransplants(ICLR 2026 WS)가 사전등록 6-gate + placebo 4종 + freeze-sha + 2×2 factorial **이미 실행** — PREREG F3 설계와 거의 1:1. 결과는 **부정 prior**: frozen-receiver(static) 이득 제한적, negative transfer 흔함, 이득은 약한 solver에 집중. 잔여 novelty = 교차**모델**×placebo-RCT 교집합 + S 서명 + ΔW 성분분해.
- **F5**: 2607.17545(budget 고정 시 consolidation 이득은 조건적)·2605.08538(sleep-phase 6메커니즘)·MemTier(LoCoMo가 아키텍처 무관) 미인용 — kill 조건 발동 확률이 작성 시점보다 높음. 외부 SOTA 앵커(Mem0/Zep급) arm 부재.
- **F2**: SEDM(메모리 아이템별 marginal utility→admission→가중치 갱신) 존재 — "레슨 단위 인과 신용" 잔여 novelty는 **추정기 검증 게이트** 하나로 축소. 대조군에 KNN-Shapley/Data-OOB 저비용 추정기·GEPA급 휴리스틱 부재.

### C5. 인프라: 단일 공유 vLLM 윈도 = 전 서열 critical path 병목 + sealed 재현성 기반 미확보 (C①②③④ 수렴)

- F1 sealed(1500콜)이 F2 뒤에 직렬 대기 — 게이트 JSON상 하위 5게이트 전부 BLOCKED. 무인증·무큐·무예약, dev-4 60콜조차 900s×2 재시도.
- **배치 불변성 미확보**: 공유 vLLM 동적 배칭은 temp0+seed에서도 수치 변동(외부 실측 다수) — vLLM batch invariance 미적용 증거. "replay verified" 주장의 기반이 흔들릴 수 있음.
- **frozen answerer 미핀**: F2는 p1v4의 Qwen3.6-35B-A3B-FP8이 dgx에 없어 qwen3.6-27b로 대체("closest available") — PREREG에 모델/revision 필드 자체 부재(p1v2는 `model_revision` 핀 관례 있음).
- **`.f2_cache` dev↔sealed 공유 + purge 없음** — 키에 모델 revision 미포함; 캐시 히트는 클라이언트 재생인데 prereg은 `replay: server-regenerated` 등록 — 정면충돌. `cached` 플래그는 기록되나 verdict 산출에서 미제외.
- C1 novel kill 판정의 judge = 생성 arm과 동일 서빙 모델(자기채점) + 캐시 39M이 git 제외 — 스냅샷 소실 시 프로그램급 판정이 재생 불가.

### C6. 이중 정본 서열: ORDERED v2 vs PREREG F2~F5 — 같은 claim 4개에 두 개의 "정본 순서" (A①④)

- ORDERED: F1 선행·sequence_locked·P1v5~P4 BLOCKED. PREREG: F2 선행 없음. **F2 sealed가 F1 미충족 상태로 이미 실행 중** — 어느 체계의 영수증이 claim을 여는지 무규정 → 사후 cherry-pick 통로.

---

## 2. Divergence

- **D1. R3 판정 이중성**: 디스크 문서 "progressive·걷기 lane 생존"(prereg 포인트룰: 0.011054>0.01, 하한>0) vs 트리 영수증 "degenerating·bf 0.584"(엔진 BF룰) — 같은 값·같은 script_sha, 미reconcile. 어느 룰이 정본인지 결정 필요.
- **D2. 처방 최우선의 렌즈 차이**: 영수증 배치 수리(B④) vs run_verdict 배선(A③) vs 서열+파워 addendum(A④) vs clique 재분석(D①) — 각 셀의 "최대 레버리지"가 다름. 모순이 아니라 의존 순서 문제로 §4에서 통합.
- **D3. GM 디스크**: 데이터는 전량 구출(15/15 tarball + 사진)되어 HSWM 관점 교체 근거 소멸(C④) vs dd 이미지·물리 재연결은 사용자 보류(7/27) 유지.

---

## 3. Open Questions

- **Q1. clique arm이 홉 마진도 재현하는가?** — 방향 결정 실험. 재현되면 "graph not hypergraph" 양 스케일 확정 → 흡수 단위를 n-ary에서 분리. hswm만 생존하면 n-ary 최초 검출 기여 → F4 credence 상향. (D①)
- **Q2. 실행 중인 F2 sealed의 dev_base ≥0.3 인가?** — floor confound 여부, 완료 후 첫 검사 항목. (A③)
- **Q3. `semantic-weight-metric-contract` foundation을 ratify하는가?** — (a)성분분석 (b)metric-감도 게이트 (c)F5 hard dep (d)인터페이스 계약 — 4개 옵션 전부가 이 한 건에 블록. (D④)
- **Q4. 흡수 전제 실험(F0-absorption-precondition: 통합 場 vs 분리 場 ablation)을 서열에 넣는가?** — tribunal이 C1 방어 조건으로 명시했으나 F2~F5 어디에도 없음. 없으면 흡수 find条件이 영구 공회전. (D③)
- **Q5. 양 트리 notebook→receipted 격상 + client_asserted 36건 run-the-receipt 배치를 실행하는가?** — r2-ledger-repair가 패턴 증명(4건 정직 rejected → 장부 신뢰도 상승). (B①④)

---

## 4. 권장 후속 작업 (의존 순서 통합)

**P0 — F2 sealed 완료 전, 비용 ≈ 0 (판정 무결성)**:
1. `run_verdict` fail-closed 배선 + headroom floor(base<0.3) void 조건 — `f2_delta_w_credit.py` (A③). 진행 중 run의 dev_base 확인 포함(Q2).
2. F2 sealed 완료 시 **producer/judge 아티팩트 분리 패턴**으로 제출(레슨 `lesson-replay-exec-container-artifact-separation-2026-07-24`) — replay_refuted 재발 방지 (A①).
3. LOCAL_WORKFLOW 세마포어 `dgx-vllm-window`(max 1, F1 우선) + sync EXCLUDES에 `.f2_cache/`·`data/prelude/cache/` 2줄 (C④).

**P1 — F2 완료 직후 (서열·방향 확정)**:
4. **통합 서열+파워 addendum 수정등록** (C6+C3 통합): F1 sealed를 전 claim 전제로 확정(다음 윈도 최우선, 03:47 회피) / 판정 2단계 sequential(interim n=100 미결 시 n=250 확장) / ρ 게이트 재설계(레슨 ≥20, dev-φ vs fresh-LOO) / F4 n=100·F2-조걶로 재등록.
5. **clique arm 재분석** (Q1) — substrate 사다리+홉 층화에 clique 추가. 기존 frozen 코퍼스 재사용, sealed F4보다 훨씬 저렴. 방향 결정.
6. model_revision 핀 공통 계약화 + 캐시 키 revision + sealed 개시 시 purge/run_id 네임스페이스 (C③).
7. **최신 선행 tribunal 재판** — HAGE·MERIT·MemTransplants·2607.17545 4편 (D②). F2/F5 kill 조건 사후 정합성 + 슬롯 C3/C6 갱신. (※ 정전상 나생문은 사용자 명시 시)

**P2 — 문서·장부 정리 (사용자 승인 항목 포함)**:
8. 영수증 배치 수리 + 폐기후보 재분류안: **KEEP 3**(ordered-gates, prom9-f1, R3-v3) / **CLOSE 7**(판결 완료 가지, 폐기 아닌 종결) / **ABANDON 2**(novelty-supersession 가지, ML1) — 승인 필요 (B④).
9. F3 prereg 재기술(novelty=교차모델×placebo-RCT 교집합, receiver capability 층화 추가, MemTransplants 1차 대조) + F5 kill 조건 재평가 (A②).
10. verdict 문자열에서 판결 축/보증 축 분리(partial@L0 혼합 라벨 폐기) + client_asserted 음성 면제 비대칭(B21) 규칙 정정 (B③).
11. F0-absorption-precondition 게이트 삽입 + INDEX §5 `PENDING`→`BLOCKED-BY` (Q4) — 사용자 결정.
12. sealed 결과 착지 시 Zenodo DOI 번들(코드 태그+universe+replay 아티팩트+prereg+env manifest) — ACM Available/외부 독립 재현 진입점 (B②).

---

## 5. 한 줄 답 (질문에 대한)

**겉으로 울리는 문제(장부 알림 3종)는 플러밍 — 진짜 문제 3개는: ① n-ary 고유 기여 측정값 0(존립 증거가 F2 하나) ② F2~F5 판정 설계의 통계 묵력(파워 ~50% + ρ 묵력 + run_verdict 미집행) ③ 단일 vLLM 윈도 병목과 이중 정본 서열. 셋 다 수리 경로가 있고 P0 3건은 비용이 거의 0이다.**

# KG: prom16-hswm-current-problems-20260725
