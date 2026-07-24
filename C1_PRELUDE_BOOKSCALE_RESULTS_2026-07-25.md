# C1 PRELUDE book-scale 결과 — 하네스 첫 완주 + novel kill 발동 (2026-07-25)

> **판정**: novel(하이퍼그래프 네이티브 > 쌍 축약) **REFUTED — kill condition 발동**. primary(hswm−dense ≥ +3.0pp)는 점추정 +3.16pp로 임계 통과하나 CI가 임계·0 양쪽으로 걸침 = prereg 규정상 **low_power**. LakatoTree 노드 `exp-c1-prelude-bookscale-20260723`: metric `equivalent`(noise 1.0 내) / 프로그램 `degenerating`.
> **한 줄**: book-scale 첫 실측에서 dense 대비 이득의 **전부가 pairwise clique 축약으로 재현**된다 — 하이퍼그래프 "네이티브 구조"의 고유 기여는 PRELUDE 공개 split에서 검출되지 않았다. "리프트 몸통=임베딩 정렬" 진단(§1)과 일치.

## 실측 (n=262, 4권, 3 arms, judge=qwen3.6-27b temp0, bge-m3)

| arm | macro-F1 |
|---|---:|
| dense (bge-m3 cosine top-20) | 0.3955 |
| **hswm** (traversal walk, μ=0.4 K=2 γ=0.5) | 0.4273 |
| **clique** (동일 하이퍼그래프의 쌍 축약, 동일 walk) | **0.4472** |

| delta (pp) | mean | CI95 | p(≤0) | prereg 대조 |
|---|---:|---:|---:|---|
| hswm − dense | **+3.16** | [−1.50, +7.89] | 0.091 | ≥+3.0 점추정 통과, **low_power** (CI가 임계+0 양쪽 걸침) |
| hswm − clique | **−2.00** | [−5.64, +1.52] | 0.879 | novel >0 **실패 → kill 발동** |

## prereg 대조 (`prom_search_hswm/evidence/PREREG_c1_prelude_bookscale_20260723.json`)

- primary `macroF1(HSWM)−macroF1(dense) ≥ +3.0pp`: 점추정 +3.16pp — **low_power 판정 의무** (prereg power note: CI가 +3.0을 걸치면 low_power 표기).
- novel `HSWM > clique`: **미달** (−2.00pp). kill `HSWM ≤ clique` **발동**.
- 정직 해석: ① novel 반증은 clique가 *같은 하이퍼그래프*의 pairwise 축약이라는 점에서 강하다 — 이득이 있다면 그건 "n-ary 구조"가 아니라 "용어-공유 확산" 자체에서 나온다. ② primary의 +3.16pp는 n=262로는 구분력 부족 — dense 대비 우위 주장은 보류 (저전력). ③ zh 2권 포함 혼합 말뭉치 — 언어별 분해는 evidence의 per_book 참조.

## 하네스 상태 — 미완주 → 완주 (버그 4건 수리)

하네스는 7/23에 만들어졌으나 한 번도 완주되지 않았다. 이번 세션에서 수리:

1. **pandas 3.0 회귀**: `groupby.apply`가 그룹 컬럼 드롭 (`--limit` 경로) → cumcount 마스크로 교체.
2. **WeightField 계약 위반**: node_emb 2차원 placeholder vs bge-m3 1024차원 target_emb 불일치 → 노드 차원을 임베딩 차원에 정합 (노드는 무의미 zeros 유지, 계약 충족).
3. **ollama 16-way 병렬 500 에러**: 임베딩 병렬도 env화 (`EMB_PARALLEL`, 기본 8).
4. **bge-m3 NaN 임베딩 병리**: 262건 중 정확히 1건 (idx146 封神 질의 `…（…）`) — 모델이 NaN 벡터 반환해 ollama가 500. 괄호(전/반각) 제거 후 결정론 1회 재시도 fallback, `cost.embedding_fallbacks` 공시 (본 run=1).

## 측정주권 (R3 패턴 재사용)

- **producer** `c1_prelude_bookscale.py` (dgx ollama/vLLM, 전 응답 디스크 캐시) → **아티팩트** `data/prelude/c1_replay_records.json` (24K, 262×3 golds/preds) → **judge** `c1_replay_judge.py` (순수 numpy).
- judge가 컨테이너에서 `metric=3.158733` **비트 재현** — replay 계약 검증됨. 장부 노드는 첫 제출 시 sync 경합으로 records 미동기화 상태라 replay_refuted로 봉인됐고(재채점 금지), 이후 파일 수동 보정+컨테이너 재실행으로 재현 확인. lineage 7건(source 5 + final + intermediate) 기록으로 계보 게이트 통과 (claim-standing 0.97, 잔여 block=foundation 2건=ratify 대기 영역).
- 교훈: sync 전체확장(24 매핑) 하에서 GIT/ 의 hot append-only 로그(타 세션 receipts)가 rsync↔검증 사이에 바뀌어 **MANIFEST MISMATCH 반복** — 하네스 오너에게 quiet-window 스케줄 또는 hot-log exclude 제안 (CONTINUATION 로그 기록).

## 산출물

- `c1_prelude_bookscale.py` (수리 4건), `c1_replay_judge.py` (신규, sha `8d8ca5a6…`)
- `EVIDENCE_C1_PRELUDE_BOOKSCALE_2026-07-23.json` (sha `42e6bf78…`), `data/prelude/c1_replay_records.json`
- 장부: `LakatosTree_HSWM_20260719/exp-c1-prelude-bookscale-20260723` (equivalent/degenerating, novel_unconfirmed) + lineage 7건
- 잔여: `data/prelude/cache/` (39M, 임베딩+judge 캐시) — git 제외, Proxmox 스냅샷 보존
