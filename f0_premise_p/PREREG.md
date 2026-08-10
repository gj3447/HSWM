# F0 — 전제 P falsifier (prereg, toy prototype)

> **status**: PREREG (예측을 결과 보기 *전에* 잠금). SECONDARY_AI, toy prototype.
> **design**: [`../DESIGN_HARNESS_DOC_HSWM_LENS_DUALITY_2026-07-21.md`](../DESIGN_HARNESS_DOC_HSWM_LENS_DUALITY_2026-07-21.md) §1.3 전제 P + §9 F0.
> **date**: 2026-07-21

## 무엇을 재는가

**전제 P** (설계 §1.3): 하네스 문서의 world-common 산문은 "irreducibly 私有(priv_A)"가 아니라 *아직 바인딩 안 된 binding-TODO*다 — HSWM 노드 콘텐츠에 담기면 `get`(serialize)이 그것을 렌더할 수 있다. P가 참이면 **비대칭 delta lens로 충분**(HSWM이 문서를 master). P가 거짓(산문이 노드 밖에서만 삼)이면 그 축만 **symmetric 격상 후보** → 새 USER verdict.

**측정**: 각 (field node content → doc prose) 쌍에 대해, LLM에게 *노드 콘텐츠만* 주고 doc 산문을 **재생성**시킨 뒤, 재생성본 vs 실제 doc 산문의 겹침(F1)을 측정.

- **높은 F1** = 산문이 노드에서 파생됨 = priv_A ≈ ∅ = **P 지지(asymmetric OK)**.
- **낮은 F1** = 산문이 노드에 없는 정보를 담음 = priv_A ≠ ∅ = **P 반증(symmetric 후보)**.

## 잠금된 예측 (결과 보기 전)

- **1차 지표**: char-bigram token-F1 (한/영 혼합에 robust). 쌍별 F1의 **평균**.
- **2차 지표**: word-level token-F1 + (가용 시) 임베딩 cosine.
- **판정 밴드** (mean 1차 F1):
  - `≥ 0.80` → **P_SUPPORTED** (강한 재생성, 비대칭 충분)
  - `≤ 0.50` → **P_REFUTED** (큰 gap, 그 축 symmetric 후보)
  - `(0.50, 0.80)` → **INCONCLUSIVE** (toy로는 미결, 실데이터 필요)
- **표본**: toy 6쌍 (7군단장 canon 중 6). 프로토타입 규모.

## 정직 caveat (미리 명시)

1. **toy = harness 검증 + 첫 신호**이지 최종 verdict 아님. field content가 canon 산문의 lossy 요약이라 내가 만든 gap이 섞임. **실 verdict = 실 HSWM 노드 ↔ 실 하네스-doc 스팬** (다음 단계).
2. **F1 지표 자체가 paraphrase에 불리** — 같은 뜻 다른 표현이면 F1↓. 그래서 임베딩 cosine 2차 지표 병행. mean F1이 낮아도 cosine이 높으면 "뜻은 파생되나 표현이 priv_A"로 분해.
3. **재생성 LLM = 실측 오라클** — LLM이 canon을 이미 알면(암기) F1 부풀려짐. toy가 유명 canon이라 이 confound 존재 → 실데이터는 LLM 미학습 노드로.
4. harness 코어(F1 scorer + 집계)는 LLM 무관하게 결정론 테스트됨. LLM 런은 첫 데이터 포인트.

## 파일

- `f1_score.py` — token-F1 scorer (char-bigram 1차 / word 2차). 순수함수.
- `toy_pairs.json` — 6 (field_id, node_content, doc_prose) 쌍.
- `regenerate.py` — pluggable 재생성 (dgx vLLM HTTP / stub). stdlib only.
- `run_f0.py` — harness: 재생성 → 채점 → 집계 → 판정.
- `test_f0.py` — 결정론 테스트 (scorer + harness w/ stub, LLM 불요).
- `RESULTS_*.md` — 런 결과 (런 후 생성).
