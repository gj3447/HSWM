# PREREG F5v2 v2 — B′ QUERY-AGNOSTIC DURABLE CONSOLIDATION (claim ④ 재시험)

> 상태: **RATIFIED v2 (사용자 C4 verdict 2026-07-28) — NOT MACHINE-LOCKED / NO MEASUREMENT AUTHORIZED**.
> 2026-07-26 사용자 발화 "F5v2 진행좀 해줘봐"는 작업 진행 권한으로 보존한다.
> **2026-07-28 사용자 ratification (Claude Code 세션, 명시 선택지 응답): C4 = B′
> query-agnostic durable cache 확정 + PROM 16 amend 10종 전부 수용.** 이로써 아래 C4의
> B′ 선택은 CODEX ENGINEERING DECISION에서 사용자 확정 설계로 격상된다.
> machine-lock과 sealed는 여전히 ORDERED v2(`F1 -> B22 -> P1v5 -> P2 -> P3 -> P4`)를
> 따르며 P4 active 전에는 측정 권한이 없다.
> 기존 파일명은 reference continuity를 위해 보존했지만, query-conditioned read-time 연산은
> 더 이상 consolidation arm으로 부르지 않는다.

## 0. 선행 판정과 실행 경계

- 구 F5 sealed: wake+sleep(age-downscale) slope `-0.158` vs append-only `-0.097`,
  차이 CI `[-0.098,-0.024]`. write-side lossy decay는 detail을 파괴했다.
- PROM 16 판정: `ratify-with-amend` 16/16. 이는 연구 합의이지 사용자 ratification이 아니다.
- KG 정전 ORDERED v2: `F1 -> B22 Gate-0 -> P1v5 -> P2 -> P3 -> P4`.
  F5v2는 P4(sleep/consolidation)이며 앞 단계를 추월하지 않는다.
- 현재 live active gate는 F1 r3 하나다. 따라서 지금 허용되는 작업은 DRAFT amend와
  오프라인 코드/fixture 검증뿐이다. live dev, machine-lock, sealed prep/run은 금지한다.
- F5v2 unlock은 CPL1의 real numeric packet + provenance, donor-specific transfer,
  rollback/removal evidence가 모두 존재하고 ORDERED harness가 P4를 active로 열 때만 가능하다.

## 1. 목적과 좁힌 가설

F5 K1의 교훈("raw provenance를 손상시키는 write-side lossy 연산은 detail을 파괴")을
보존하면서, query 도착 전에 numeric `W/H` 경험을 durable slow state로 합치는 B′가
append-only numeric state를 이길 수 있는지 시험한다.

- **H1 detail non-inferiority**: `slope(B′)-slope(A)`의 cluster-bootstrap 95% CI
  하한이 `>-delta`, `delta=0.10`.
- **H2 causal utility**: B′의 downstream accuracy가 A와 가장 강한 retrieval control보다
  높고 paired 95% CI 하한이 `>0`.
- **H3 consolidation signature**: B′ 산출물이 (a) durable, (b) query-agnostic,
  (c) 입력 단일 packet에 없던 결합 numeric rule/exception state를 포함한다.
- **H4 removal**: B′ slow state를 제거/rollback하면 B′ 이득의 70% 이상이 사라진다.
- **보존 조건**: episodic detail 손실 `<=5pp`, donor DSI 보존 `>=80%`.

## 2. Arm 정의

| arm | 정의 | persistent write | 분류 |
|---|---|---|---|
| A append-only | CPL1 numeric packet을 원형 그대로 유지하고 strong retrieval/readout | raw append만 | 기준선 |
| R QFR | query-conditioned verbatim span/packet 선택과 재배열; 결과는 일회성 | 없음 | strong retrieval control, consolidation 아님 |
| B0 extractive cache | query 공개 전 frozen topic key로 packet을 묶은 content-addressed durable cache; 파생 rule 없음 | derived cache만, raw 불변 | caching control |
| **B′ durable slow-W/H** | query 공개 전 성공/실패 trajectory를 대조해 numeric semantic rule + exception ledger를 생성, CAS로 slow `W/H`에 승격 | content-addressed derived state | 유일한 consolidation treatment |
| C bitemporal-lite | 동일 referent의 구버전에 `invalid_at`을 추가하되 본문·provenance 보존 | append + 비파괴 마킹 | gated supersession |
| D age-downscale | 구 F5의 `confidence *= 0.8` 및 gist 압축 | lossy derived state | 기살해군/negative control |
| N no-op/sham | 동일 sleep 비용을 쓰되 random/no-op replay | raw 불변 | process control |
| X exact replay | raw episodic record를 그대로 재생 | raw 불변 | upper bound |

### B′ 입력 allowlist

- CPL1 numeric packet payload는 기존 전이 계약과 동일한 정확히 5필드만 허용한다:
  `shared_schema_sha256`, `edge_or_hyperedge_id`, `numeric_delta`, `confidence`,
  `provenance_sha256`.
- episode/topic 정보는 packet을 변조하지 않는 별도 machine-locked envelope로만 받는다:
  `episode_id`, `pre_outcome_receipt_sha256`, `outcome`,
  `donor_specificity_stratum`, frozen topic key.
- packet SHA는 5필드 canonical projection에서 계산한다. envelope가 packet SHA를 바꾸거나
  query 정보를 topic key에 운반하면 VOID다.

금지 입력은 donor transcript, training answer, verdict/rationale text, natural-language lesson,
query text/hash, hidden cache, 새 prompt instruction이다. 금지 필드가 있으면 run을 VOID한다.

### B′ durable cache 불변식

1. source cut와 topic partition을 query 공개 전에 SHA-256으로 고정한다.
2. 같은 source cut은 입력 순서와 무관하게 bit-identical manifest/block을 만든다.
3. block 주소는 canonical content SHA-256이며 후속 복수 query가 같은 block을 재사용한다.
4. raw append log의 byte hash는 build 전후 동일해야 한다.
5. 각 derived rule은 모든 source packet/provenance hash와 exception ledger를 보존한다.
6. cache manifest나 block에 query text/hash가 한 바이트라도 있으면 VOID한다.
7. rollback은 삭제가 아니라 이전 immutable epoch를 active로 되돌리고 receipt를 append한다.

## 3. Cohort와 실행 단위

- 기본 testbed: CPL1/F3v2 procedural foundry의 machine-locked 후속 cohort.
- 독립 seed 최소 5; episode `E=8` 이상; cluster key는 world/run이다.
- sealed split은 development, sealed_train, sealed_fresh, sealed_retention,
  sealed_donor_exclusive, sealed_common으로 분리하고 content SHA 교집합을 거부한다.
- B′ build 구간에는 새 관측과 query 공개를 금지한다.
- C arm이 no-op이 되지 않도록 반복 referent/version conflict가 최소 1건 이상 존재해야 한다.

## 4. Metrics와 비용 계약

### 1차

- detail preservation slope와 `B′-A` 비열등성 CI.
- downstream accuracy의 `B′-max(A,R,B0,C)` paired CI.
- removal/rollback removed-gain fraction.

### 2차

- gist slope는 detail과 DRM lure를 함께 보고하며 단독 상승을 개선으로 해석하지 않는다.
- donor DSI, supersession QA, provenance entailment, exception recall.
- consolidation signature 3축(durable/derived/query-agnostic).

### 비용

- build latency, query latency p50/p95, prompt/completion token, context chars,
  derived bytes, active bytes, amortized cost/query를 arm별로 기록한다.
- B′ amortized token 또는 latency가 A의 `1.5x`를 넘으면 정확도 이득이 있어도
  Pareto 우위로 부르지 않는다.

## 5. 통계 잠금

- cluster/run-level paired bootstrap `>=1000`; sealed 기본 10,000.
- `delta=0.10`은 구 F5 canon과 동일하며 결과 열람 후 바꾸지 않는다.
- MDE는 구 F5 잔차 sigma와 pilot variance로 산정하고 power `<0.80`이면 sealed cohort를
  늘린 뒤 새 machine lock을 만든다.
- query predictability 상호작용은 rho 점추정으로 kill하지 않는다. 95% CI 전체가 `0.3`
  미만이고 power가 충분할 때만 claim을 좁힌다. 아니면 exploratory로 남긴다.
- belt-halt 전 conditional power `<0.20`인지 계산한다. 두 번째 kill은 검정된 operator
  class에만 적용하며 모든 consolidation을 일반 폐기하지 않는다.

## 6. Judge와 provenance gate

- sealed 전 adversarial wrong-answer/citation canary catch-rate `>=90%`.
- 모든 B0/B′ 출력은 source ID, byte/range 또는 packet ID, source SHA, provenance SHA가
  일치해야 한다. 범위 밖/위조 citation 하나면 해당 output을 0점 처리한다.
- DRM related-but-unstated lure를 별도 계수한다. lure 채택률 상승은 gist 개선을 무효화한다.
- entailment와 schema validator는 judge와 독립적으로 deterministic fail-closed한다.
- 동일 response cache replay는 network를 hard-forbid하고 bit-equal receipt를 요구한다.

## 7. Kill/VOID 조건

- **K1 detail kill**: B′ 또는 C의 slope 비열등성 CI 하한 `<=-delta`.
- **K2 no unique contribution**: B′ accuracy가 `max(A,R,B0,C)`를 이기지 못함.
- **K3 retrieval-only**: R 또는 B0가 B′와 ROPE `+/-2pp` 안이고 removal이 효과를
  지우지 못함. claim을 retrieval/caching으로 강등한다.
- **K4 signature kill**: durability, derived novelty, query-agnostic 중 하나라도 실패.
- **K5 provenance kill**: raw hash 변화, query leakage, source/packet tamper, forbidden field.
- **K6 preservation kill**: detail 손실 `>5pp` 또는 donor DSI 보존 `<80%`.
- judge catch-rate `<90%`, split overlap, model/deployment/code hash drift, out-of-order gate,
  live F1과 endpoint 동시 점유는 run VOID다.

## 8. 실행 순서

1. 이 amended DRAFT와 machine-readable draft를 오프라인 검증한다.
2. 사용자 C4 ratification 전에는 state를 `DRAFT`에서 올리지 않는다. — **충족
   (2026-07-28 사용자 verdict: B′ + amend 10/10 수용, state → RATIFIED v2).**
3. ORDERED F1 -> B22 -> P1v5 -> P2 -> P3 결과를 각각 등록하고 P4 active를 확인한다.
4. CPL1 real numeric packet/provenance + removal/transfer receipt를 바인딩한다.
5. power/judge/deployment/code/data hashes를 포함한 dev manifest를 write-once 생성한다.
6. deterministic fixture와 injected-negative를 통과한 뒤에만 live dev smoke를 수행한다.
7. dev가 설계를 바꾸면 amend -> ratify -> 새 lock을 반복한다.
8. sealed manifest mode flip 후 단 한 번 실행하고 cache-only replay judge로 재생한다.
9. 결과 제출과 HSWM_LOCAL_RECORD 판정은 별도 독립 단계이며 이 문서는 progress verdict를 내지 않는다.

## 9. 이번 amend가 반영한 PROM 16 10종

1. Infini-Memory를 read-time 선례에서 제거하고 write/manage + agentic read 결합으로 정정.
2. latency/token/build/amortized 비용 상한 추가.
3. B0 extractive query-agnostic cache 추가.
4. C4를 B′로 선택하고 QFR을 retrieval control로 분리.
5. K1을 cluster-bootstrap 비열등성으로 재기술.
6. K3를 CI + power 조건으로 경화.
7. judge canary, entailment, 출처 스키마 검증 추가.
8. C를 observer-safe bitemporal-lite로 명시.
9. belt-halt 전 conditional-power와 operator-class 범위 제한 추가.
10. gist/detail 이중렌즈와 DRM lure probe 추가.

## 10. 기존 증거 보존

`f5_consolidation.py`, `f5_replay_judge.py`, 구 F5 receipt는 byte-immutable historical
evidence다. F5v2는 새 `f5v2_*` 파일과 새 schema/manifest를 사용하며 구 receipt의 SHA 결박을
깨지 않는다.

오프라인 substrate는 HSWM branch `codex/f5v2-bprime`, commit `ea28ca3`에 있다.
F5v2+packaging 테스트 `35/35`를 통과했지만, synthetic chain도
`OFFLINE_SEALED_NOT_AUTHORIZED`와 `measurement_authorized=false`로만 끝난다.
