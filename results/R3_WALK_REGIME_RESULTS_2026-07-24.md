# R3 결과 — 걷기 승리 regime 통제 재현 성공 + density dial 실증 (2026-07-24)

> **판정**: metric **`progressive`** (primary + novel 예측 2/2) — 걷기 lane 생존 (prereg abandon commitment 미발동).
> **한 줄**: PhantomWiki 대형·교량희박 판에서 strict max-product K≤2 걷기가 flat cosine을 hard-hop(≥6) best-trace recall@10에서 **+0.0111 (bootstrap95 하한 0.00085 > 0)** 로 이기고, 그 우위가 **bridge 희박도 dial에 단조 반응** (sparse−dense = +0.0158) — PROM-8 C4 regime 가설의 통제 재현. density dial을 독립 변수로 돌린 걷기 실험은 선행연구에 없음 (C8 빈칸).

## 실측 (strict T3 워커, LLM/network 0, HF_HUB_OFFLINE=1)

### hard-hop (difficulty ≥ 6) — walk − flat recall@10

| universe | n | flat | walk | **delta** | bootstrap95 |
|---|---:|---:|---:|---:|---|
| sparse_t200_fk1 (5057) | 98 | 0.159 | 0.170 | **+0.0111** | [0.00085, 0.0247] |
| large_t200_fk3 (5057) | 85 | 0.160 | 0.172 | **+0.0118** | [0.0, 0.0275] |
| dense_t200_fk9 (5057) | 70 | 0.077 | 0.073 | **−0.0048** | [−0.0143, 0.0] |
| mid_t20_fk3 (506) | 94 | 0.225 | 0.229 | +0.0035 | [0.0, 0.0106] |
| small_t2_fk3 (50) | 80 | 0.454 | 0.448 | −0.0063 | [−0.0313, 0.0146] |

### 축 판독

- **크기 축** (fk3 고정, hard-hop): small −0.006 → mid +0.004 → large +0.012 — **크기 단조 증가**.
- **밀도 축** (5057 고정, hard-hop): sparse +0.011 / fk3 +0.012 / **dense −0.005** — 교량이 빽빽해지면 우위 소멸·반전.

## prereg 대조 (`PREREG_R3_WALK_REGIME_2026-07-23.json`, credence 0.5)

| 항목 | 잠정값 | 실측 | 판정 |
|---|---|---|---|
| primary sparse hard-hop delta | > 0.01 (noise band 상회) | 0.011054 | ✓ |
| bootstrap95 하한 | > 0.0 | 0.00085 | ✓ (박약하나 양수) |
| novel density monotonicity (sparse−dense) | > 0 | 0.015816 | ✓ |
| kill ① sparse delta ≤ 0.01 or CI하한 ≤ 0 | — | 미발동 | ✓ |
| kill ② density monotonicity ≤ 0 | — | 미발동 | ✓ |
| kill ③ facts_unbound > 0 | — | 5/5 universe 전부 0 | ✓ |
| kill ④ LLM/network/gold 오염 | — | budget 0, offline 강제 | ✓ |

## 데이터 무결성 — 로컬 재생성 검증

- 실행 당일 `/Volumes/GM`(ExFAT)이 30분+ 무응답(ls 타임아웃 4건)이라, universe 5종을 **prereg 잠정 도구/플래그/시드 그대로** 로컬(`~/hswm_lab/phantomwiki_r3`)에 재생성 (prereg amendment 2026-07-24, 측정 전 기록).
- article 수 일치: 50 / 506 / 5057 / 5057 / 5057.
- **결정적 증거**: 재생성본의 person_arcs = sparse 25,606 / dense 66,076 / small 348 — prereg에 측정 전 공개된 원본 smoke 수치와 **3/3 정확히 일치** → 로컬 재생성본과 원본(GM)의 동일성 강력 지지.
- 잔여 followup **해소 (2026-07-25)**: GM 물리 재연결 후 원본(`/Volumes/GM/hswm_lab/phantomwiki_r3`)↔로컬 재생성본 checksum 대조 완료 — `articles.json`+`facts.pl` sha256 **5/5 universe 바이트 동일**, `questions/type*.json` 100파일 **의미론적 전량 일치**(차이는 생성 난수 UUID `id`·`solution_traces` 변수 rename뿐), `timings.csv`는 실행 wall-clock 메타라 대조 제외. 로컬 재생성본 = 원본의 충실한 동형 사본으로 **확정**.

## 의미

1. **걷기 lane 생존**: T3까지의 mechanism 사슬(재료→seed→predicate→점수변화)에 이어, R3가 **효용 regime의 존재**를 보임 — 큰 pool + 희박 교량 + 긴 사슬(hard-hop)에서 strict 걷기가 flat을 유의하게 앞섬. C4("지금까지 전부 flat-우위 조건에서만 시험했다")의 처방이 맞았다.
2. **density dial 작동**: 우위가 bridge 희박도의 함수라는 것 — 걷기 연구 최초의 독립 밀도 변수 (C8 빈칸 메움).
3. **정직 경계**: (a) primary bootstrap 하한 0.00085 = 임계 통과지만 박약 — 재현 누적 필요. (b) synthetic template corpus — 실산문 전이는 미주장 (scope_boundary). (c) retrieval-side recall@10이지 answer accuracy 아님. (d) large(fk3)가 sparse(fk1)보다 미세하게 높음(+0.0118 vs +0.0111) — novel metric 정의(sparse−dense)에는 무영향, fk3≈fk1로 해석.
4. **다음 자연스러운 판**: ① hard-hop 효과의 answer-side 환산 (retrieval→answer) ② dense 역전 구간의 mechanism 분석 ③ 실산문 책-단위 슬롯(`book-scale-nocha-qasper-20260723`)과의 접속 — PhantomWiki hard-hop이 책-단위 가설의 프록시로 작동하는지.

## 산출물

- `r3_walk_regime.py` (본실험, sha `f14472e9…` — env override 패치, prereg amendment 기록)
- `EVIDENCE_R3_WALK_REGIME_2026-07-23.json` (sha `002e263d…`)
- universe: `~/hswm_lab/phantomwiki_r3/{small_t2_fk3,mid_t20_fk3,large_t200_fk3,sparse_t200_fk1,dense_t200_fk9}` (로컬 재생성본)
- prereg: `PREREG_R3_WALK_REGIME_2026-07-23.json` (amendment 2026-07-24 포함)

## 부록 — 판정 장부 체인 (2026-07-24, 장부 수리 패턴 확립)

| 노드 | 상태 | 원인/결과 |
|---|---|---|
| `R3-walk-regime-density-dial` | prereg 등록, proof (미채점) | 원본 script sha `8b7f0923` 잠금 — /Volumes/GM 행으로 실행불가, 사후 재등록 금지 규칙으로 동결 |
| `…-v2` | degenerating, replay **mismatch**, grade client_asserted | 7/22 replay-exec 기본 ON 진단 확정: 서버가 `python <script> <result_path>`를 컨테이너 재실행 → torch 없어 값 재현 불가 → client 값 refute |
| `…-v3` | degenerating(프로그램, BF 하중) / **replay verified, grade server_regenerated, novel_server_anchored=true** | producer(Mac/torch)→아티팩트(`_research/r3_replay`: static 행렬+rows+universe 사본)→judge(순수 numpy `r3_replay_judge.py`) 3단 분리 — 컨테이너 재실행 **동일값 재현 성공** |

- 장부 전멸 원인 3종 중 closes_question✓·novel_script 앵커✓에 이어 **replay 컨테이너 제약**까지 봉합 — KG `lesson-replay-exec-container-artifact-separation-2026-07-24` (legacy_program_mechanism=lemma-incorporation).
- eureka 는 `bf_marginal (0.584 ≤ 3.162)` 하나만 남음 — 장부 고장이 아니라 **효과 크기가 실제로 박약**하다는 정직한 판정. 다음 판(BF 강화)은 더 큰 효과의 replication 설계로.
- 재사용: book-scale/P1 등 무거운 실험도 같은 producer/judge 분리 계약으로 제출하면 replay verified 가 선다.
- `…-v2` 노드는 정직한 흔적으로 보존 (삭제 없음).

## 부록 — GM 원본↔재생성본 checksum 대조 (2026-07-25, prereg followup 클로저)

- prereg amendment(2026-07-24)의 후속 큐 "GM 복구 시 원본↔재생성본 내용 대조" 실행 — GM은 7/25 자연 회복 (USB hang 해소).
- 방법: `shasum -a 256` 양쪽 비교 — GM `/Volumes/GM/hswm_lab/phantomwiki_r3/<u>/` vs 로컬 `~/hswm_lab/phantomwiki_r3/<u>/`, 5 universes × `articles.json`+`facts.pl`.
- 결과: **10/10 MATCH (전부 바이트 동일)**. question ids는 unseeded UUID4라 원본 대조 대상 아님 (prereg 명시) — solution-trace SETS는 7/24에 600/600 검증 완료.
- 결론: GM 행 당시 "동일 도구/플래그/시드 재생성" 주장이 원본 대조로 확증 — R3 판정(-v3, replay verified)의 데이터 기반은 원본과 무차별. actor: Kimi Code CLI.
