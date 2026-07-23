# Phase B — Shadow-Gated n-ary Topology Absorption 결과 (2026-07-23)

> **사전등록**: `prom_search_hswm/evidence/PREREG_shadow_gated_absorption_20260723.json` (예측: rounds_passed ≥ 1, novel: canary_preservation ≥ 98%, kill: 3라운드 연속 acceptance 0 — user-declared, 서버 영수증 sha 미기록)
> **실측**: `prom_search_hswm/evidence/EVIDENCE_shadow_gated_absorption_20260723.json` (sha `13d6de32…`, 재실행 결정론 일치)
> **한 줄**: n-ary topology 흡수(ADD/SPLIT/MERGE/SUPERSEDE)는 **무해하지만 무득** — 게이트가 3라운드 전부 `no_target_gain`으로 기각(kill 조건 발동), canary는 100% 보존. **Phase A의 "해로움"과 구분되는 "무득" 판정 = shadow 게이트의 진단 능력 실증.**

## 1. 설계 (prereg B-1)

- P6 규율 재사용: 2Wiki n=900, seed 8217, train 3×120 / validation 3×120 / sealed holdout 180, exact-질의-disjoint, ID feature 금지, replay 검증.
- **환경 대체(정직 기록)**: 원본 `2wiki_dev.jsonl`(외장볼륨) 미마운트 + 다운로드 금지 → SiReRAG 2Wiki dev 1000행 무손실 변환(`convert_sirerag_2wiki.py`) + all-MiniLM-L6-v2 대신 결정론 lexical 임베딩(hashed TF-IDF + seeded random projection, stdlib+numpy). 절대 recall은 P6와 비교 불가, paired 비교만 유효.
- 후보(라운드당, 결정론): train gold 문서 간 공유 entity 기반 n-ary ADD(≤100, 크기 3–65), 고차수 비응집 엣지 SPLIT(≤20), Jaccard≥0.6 MERGE(≤20), 부모는 SUPERSEDE(valid_at/invalid_at, in-place 금지).
- 게이트: shadow 적용 → canary(후보 무접촉 지식, ε=0.01) ≥98% AND fresh Δ ≥ −0.01 AND target Δ ≥ +0.03. 대조 arm: absorb-all(무게이트), frozen.

## 2. 라운드 결과 (gated arm)

| round | ops (ADD/SPLIT/MERGE) | canary_pres | fresh Δ | target Δ | verdict | 기각 사유 |
|---|---|---|---|---|---|---|
| 1 | 100/20/20 | 100.00 | +0.000 | +0.000 | FAIL | no_target_gain |
| 2 | 100/20/20 | 100.00 | +0.000 | +0.000 | FAIL | no_target_gain |
| 3 | 100/20/20 | 100.00 | −0.002 | −0.021 | FAIL | no_target_gain |

- **rounds_passed = 0** → 예측(rounds_passed ≥ 1) 기각, **kill 조건(3라운드 연속 acceptance 0) 발동**.
- **novel (min canary_preservation) = 100.0 ≥ 98** → novel cross-metric은 확증. topology 편집이 무관 지식을 전혀 해치지 않음(theta 변경 엔트리 6만+, max 0.345에도).
- absorb-all arm도 전 라운드 같은 사유(no_target_gain)로 게이트 기준 미달 — 게이트가 과민하게 막은 게 아니라 통과시킬 후보가 없었음.

## 3. Sealed holdout (n=180, frozen recall@10 = 0.6986)

| arm | recall@10 | Δ vs frozen | bootstrap95 |
|---|---|---|---|
| gated | 0.6986 | 0.000 | [0.000, 0.000] |
| absorb_all | 0.6972 | −0.0014 | [−0.0042, 0.000] |

- 게이트 arm = frozen과 동일(아무것도 commit 안 함) — Phase A와 달리 손해 0.
- 무게이트 흡수는 sealed에서 −0.0014 (중립~미세 음수): 전부 받았어도 득이 없었음 → **게이트의 효과 분리 확인**(걸러낸 것 = 손해가 아니라 공회전).

## 4. Phase A 원인 진단 (이 실험의 핵심 산출)

- Phase A(의미 KV residual): fresh Δ −0.06~−0.02, **해로움(harm)** → FSM 기각.
- Phase B(n-ary topology): canary 100%, fresh ≈ 0, target ≈ 0, **무득(no gain)** → shadow 게이트가 `canary_harm`이 아니라 `no_target_gain`으로 정확히 분류.
- 결론: 흡수 실패의 원인은 게이트/FSM이 아니라 **후보 생성기** — 공유 entity 기반 n-ary 링크는 unseen 질의의 recall을 움직이지 못함. 다음 문제이동은 후보의 표현력(target probe를 움직일 topology)이지 게이트 완화가 아님.

## 5. Caveat

- 데이터셋/인코더 대체로 절대 수치는 P6와 비교 불가. 외장볼륨 복귀 후 MiniLM + 원본 2Wiki로 재현 필요(prereg deferred에 명시).
- target 슬라이스 = 후보에 gold 문서가 접촉된 validation 질의(n=11–17) — "train 분포"의 구조적 근사.
- 단일 벤치마크/단일 시드. LakatoTree 예측은 user 선언(2026-07-23), 서버 영수증 sha 미기록.
- train 흡수는 gold 지도 기반(supervised learning-while-using).

## 6. 산출물

- 러너: `prom_search_hswm/prom_shadow_gated_absorption.py` (sha `5558e61b…`)
- 게이트 reducer: `prom_search_hswm/hswm_shadow_gate.py` + 테스트 `test_hswm_shadow_gate.py` (22/22)
- 사전등록/실측: `prom_search_hswm/evidence/PREREG_shadow_gated_absorption_20260723.json`, `EVIDENCE_shadow_gated_absorption_20260723.json`
- 데이터 변환기: `prom_search_hswm/convert_sirerag_2wiki.py` → `data/2wiki_sirerag_1000.jsonl`
