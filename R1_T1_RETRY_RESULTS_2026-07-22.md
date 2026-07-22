# R1 T1 재판 결과 — PROM-8 처방 채택 실행 (2026-07-22)

> **채택**: `PROM_8_DYNAMIC_TWO_LANES_2026-07-22.md` §4 R1
> **코드**: [`r1_t1_retry.py`](r1_t1_retry.py) + [`r1_predicate_alias.py`](r1_predicate_alias.py)
> **prereg**: [`PREREG_R1_T1_RETRY_2026-07-22.json`](PREREG_R1_T1_RETRY_2026-07-22.json) (receipt `f52d881b…`)
> **evidence**: [`EVIDENCE_R1_T1_RETRY_2026-07-22.json`](EVIDENCE_R1_T1_RETRY_2026-07-22.json) (sha `154e906a…`)
> **LakatoTree**: `LakatosTree_PromSearchHSWM_20260721` / `R1-t1-retry-alias-soft-hipposeed`

## 한 줄

**T1 입구 도달(min)은 살렸다 (0→2). depth-2 법적 연속(min)은 못 살렸다 (0 유지, kill #2).**
2Wiki에서는 depth2가 0→4로 열렸고, MuSiQue depth2는 0 — **병목은 “어휘만”이 아니라 데이터셋 비대칭 구조**.

## 사전등록 대비 실측

| metric | baseline (A0 / 구 T1) | A4 R1 full | 판정 |
|---|---:|---:|---|
| `min_over_datasets t1_seed_reaches_entrance` | **0** | **2** | 개선 (예측 방향) |
| `min_over_datasets kernel_legal_depth2` | **0** | **0** | novel 미달 |
| kill2 (t1↑ & depth2_min=0) | — | **발동** | OQ1: 구조/재료 쪽 |

A0 재현 검증 (워커 포크 정상): 2Wiki t1=5 / MuSiQue t1=0 / depth2=0·0 — 구 T1 영수증과 일치.

## 암 분해 (n=200/dataset, frozen V5 emb, LLM·network 0)

| arm | 처방 | t1_min | d2_min | 2Wiki t1/d2 | MuSiQue t1/d2 |
|---|---|---:|---:|---|---|
| A0_baseline | hard gate + cosine seed | 0 | 0 | 5 / 0 | 0 / 0 |
| A1_alias | + offline alias | 0 | 0 | 5 / **2** | 0 / 0 |
| A2_soft | soft weight only | 0 | 0 | 5 / 0 | 0 / 0 |
| A3_alias_soft | alias+soft | 0 | 0 | 5 / **3** | 0 / 0 |
| **A4_r1_full** | **alias+soft+hippo seed** | **2** | **0** | **7 / 4** | **2 / 0** |

### 레버 해석

1. **Hippo-style seed (cosine ∪ title/entity lexical RRF)** 가 **t1_min 로드베어링**
   - MuSiQue 입구 0→2, 2Wiki 5→7
   - alias/soft만으로는 musique t1이 0 고정 → min 안 움직임
2. **Alias-closure** 가 **2Wiki continuation** 에 유효
   - A1만으로 2Wiki d2 0→2, A3→3, A4→4
   - MuSiQue d2에는 무효
3. **Soft alone (A2)** 이 판에서는 거의 무효 (2Wiki d2 그대로 0)
   - 품질 0 엣지를 열어 주지 않는 한 hard 게이트 대체 효과 약함
4. **kill #2 정확 발동**: 입구는 닿는데 양 데이터셋 공통 depth-2는 실패 → 다음 병목 = **구조/재료/판 (R2·R3)** 쪽

## 예산·규율

- LLM 0 / network 0 / new embedding 0
- gold 미소비
- `typed_composition.py` 미수정 (구 T1 sha 보존) — 연구용 워커 포크

## 한계 (정직)

- Alias = 로컬 family/morphology, live Wikidata SPARQL 아님
- Hippo seed = query-triple 임베딩이 아니라 lexical RRF 근사
- Soft = quality>0 필수 (완전 untyped walk 아님)
- answer F1 / retrieval quality 주장 없음

## 다음 수 (PROM-8 순서 유지)

| 우선 | 작업 | 이유 |
|---|---|---|
| R2 | ReFinED+fastcoref receipt weave (재료) | MuSiQue d2=0 → seed 옆 **chain이 seed 착지 문단에 없음** 가능 |
| R3 | 2Wiki full-pool + PhantomWiki density-dial | 걷기가 이기는 판으로 교체 (C4) |
| R4 | oracle headroom (B2 L5) | 독립 병렬 가능 |
| — | soft-only 재설계 | 이 substrate에선 우선순위 하향 |

## 총평

R1 채택 테스트 **부분 성공**:
- ✅ 처방 중 **seed 경로**는 T1 입구 문제를 숫자로 움직임
- ✅ **alias**는 2Wiki에서 걷기 연속을 부분 개방
- ❌ **양 데이터셋 min depth2** 는 여전히 0 → “T1/T2 완치” 아님
- 다음 판은 PROM-8 그대로 **재료(R2) + 판(R3)**
