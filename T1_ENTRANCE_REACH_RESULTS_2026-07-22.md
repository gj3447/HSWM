# T1 entrance-reach 결과 — RED (2026-07-22)

> **판정**: metric `equivalent`(0=baseline) / Lakatos `degenerating`. 노드 `T1-entrance-reach-c3` (예측 receipt `e3cc80aa…`), receipt fold `ok=true`.
> **한 줄**: B1이 해금한 결정론 weave chain은 **frozen seed에서 도달·계속 불가** — MuSiQue는 top-3 seed가 입구에 한 번도 안 닿고(0/200), 2Wiki는 5/200 질의가 입구에 닿지만 **typed kernel의 predicate 게이트(T2)에서 전멸**(legal depth-2 = 0/200 양쪽). 사전등록 kill #1(도달불가)·#2(T2 병목 이동) 정확히 발동.

## 실측 (n=200/dataset, frozen V5 dev 임베딩 재사용, 신규 spend 0)

| | entrance 문단 | T1 seed 도달 질의 | kernel legal depth-2 질의 |
|---|---:|---:|---:|
| MuSiQue C3 | 5 | **0** | 0 |
| 2Wiki C3 | 10 | **5** | **0** |
| C0 양쪽 | 0 | 0 | 0 (공표 waterfall 재확인) |

## 해석 (exception-barring)

1. **B1 unlock의 지위 격하**: T0 구조 해금은 실재하나 **결정론 lane 한정으로는 공회전** — chain이 있어도 (a) MuSiQue에선 seed가 그 근처에 안 가고 (b) 2Wiki에선 가도 predicate 어휘가 질의와 안 맞아 kernel이 정당하게 거부. B1 결과 문서의 정직 경계 3("다음 rung이 죽으면 공회전')이 그대로 현실화.
2. **병목의 정확한 이동**: material 유무(T0, 해결) → **seed 정렬 + predicate 어휘 호환(T1/T2, 미해결)**. 남은 활로: (a) ML lane(ReFinED/fastcoref)으로 chain을 seed가 실제 내려앉는 문단들 위에 짜기, (b) T2 predicate 매칭 어휘 확장(단 min_typed_match 완화는 안전계약 위반 — 금지), (c) 여기서 멈추고 identity lane 폐기.
3. 프로그램 차원: progressive(B1) 직후 즉시 반증(T1) — 자기비판 루프가 설계대로 동작. eureka seam도 B1을 hallucinated로 미리 경고했었음(BF 0.167).

## 산출물

- `t1_entrance_reach.py` (prereg guard + 무수정 kernel 재실행) · `PREREG_T1_ENTRANCE_REACH_2026-07-22.json` (실행 전 동결) · `EVIDENCE_T1_ENTRANCE_REACH_2026-07-22.json` (sha `92905c18…`)
- gold 라벨 무소비, LLM/network/신규 embedding 0.
