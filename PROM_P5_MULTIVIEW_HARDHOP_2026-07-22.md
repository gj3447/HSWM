# HSWM P5 — 단일 場 대 역할분리 멀티뷰 hard-hop 재판

> 날짜: 2026-07-22
> 프로그램: `LakatosTree_PromSearchHSWM_20260721`
> 가지: `P5-onefield-vs-multiview-hardhop`
> 층위: 실측·서버 영수증은 EVIDENCE, 문헌 종합과 다음 설계는 `SECONDARY_AI`
> 결론: **고정 규칙 late fusion은 기각. HSWM hard core는 건드리지 않고 `cheap_query_routing` 보조가정만 폐기.**

## 1. 먼저 복구한 현재 상태

HSWM은 여기서 일반적인 world model이 아니라 **Hypergraph Semantic Weight Map**이며, 현재 방어 가능한 역할은 reasoner가 아니라 memory substrate다. 기존 연구의 살아 있는 핵은 다음 세 가지다.

1. n-ary 하이퍼엣지는 이진 분해보다 multi-hop에서 유리했다(ML16).
2. semantic은 `SEED`, 구조는 `EDGE`로 분리해야 했다(ML17).
3. 구조깊이는 solidity·이식성의 발판이지 전파를 깊게 쌓아 recall을 올리는 장치가 아니었다(ML18–19).

실험 당시 추적 정본은 private SYMPOSIUM의 `HSWM/prom_search_hswm/`이었고, 동시 작업 중이던 공개 저장소 변경은 그 write-set에서 제외했다. 이 공개본에서는 코드·증거를 [`prom_search_hswm/`](prom_search_hswm/) 아래로 통합했다. 라이브 LakatoTree는 로컬 `:55170` relay가 가리키는 서버이며 boot/disk SHA가 clean `PI/lakatotree@71915a52ee934e20943bfa33ad934711f0eceb4e`와 일치했다.

## 2. 문헌 충돌로 만든 P5

아래는 1차 출처에서 가져온 메커니즘이고, HSWM에 대한 연결은 `SECONDARY_AI` 해석이다.

| 1차 출처 | 메커니즘 | P5/P6 함의 |
|---|---|---|
| [HyperGraphRAG, NeurIPS 2025](https://arxiv.org/abs/2503.21322) | 사실의 n-ary 구조를 hyperedge로 보존해 entity·hyperedge·chunk를 함께 검색 | HSWM의 n-ary arm은 유지하되 표현 효과와 fusion 효과를 분리해야 한다. |
| [KG²RAG, NAACL 2025](https://aclanthology.org/2025.naacl-long.449/) | semantic seed 뒤 KG 확장과 context organization | ML17의 `semantic=SEED, structure=EDGE`와 정합한다. |
| [SiReRAG, ICLR 2025](https://arxiv.org/abs/2412.06206) | similarity와 relatedness 계층을 독립 구성한 뒤 retrieval 단계에서 합침 | 하나의 scalar로 너무 일찍 접는 것이 손실일 수 있다는 대안이다. |
| [HippoRAG 2, 2025](https://arxiv.org/abs/2502.14802) | passage·triple을 함께 두고 semantic seed와 graph propagation을 결합 | learning-while-using 비교기의 최소선이다. |
| [TagRAG, ACL Findings 2026](https://aclanthology.org/2026.findings-acl.321/) | 계층형 domain tag와 증분 insertion | 구조깊이의 효능을 recall 외 삽입비용·영향범위로 측정할 근거다. |
| [STEM, ACL 2026](https://aclanthology.org/2026.acl-long.329/) | semantic query를 schema graph에 투영하고 구조 계획을 수행 | semantic 값을 edge weight에 직접 바르는 대신 query-specific plan을 분리해야 한다. |
| [ParallaxRAG, ACL 2026](https://aclanthology.org/2026.acl-long.1226/) | hop/관계별 retrieval view와 query-aware specialization | P5의 핵심 경쟁가설. 다만 진짜 메커니즘은 단순 분리보다 학습형 specialist/gate일 수 있다. |
| [BRINK, EACL 2026](https://aclanthology.org/2026.eacl-long.114/) | 직접 답 triple이 있는 평가를 문제 삼고 incomplete-KG 조건에서 추론·암기를 분리 | 다음 실험은 private ID와 direct-edge deletion을 포함해야 한다. |

P5는 이 중 가장 싼 설명을 먼저 쳤다.

> 같은 title cosine, body cosine, n-ary entity APPNP 세 view와 같은 query-only 가중치를 쓰되, control은 정규화 점수를 먼저 한 scalar로 더하고 treatment는 세 순위를 late RRF로 합치면 hard-4에서 이긴다.

## 3. 사전등록과 동등비용 계약

- 데이터: `/Volumes/GM/bench/2wiki_dev.jsonl`, 12,576행, SHA-256 `c219e4…5d8e7`.
- 결정론 표본: 400문항, seed 7331, hard-4 80개와 2-support 320개.
- 두 arm 공통 view: title cosine, body cosine, n-ary entity APPNP.
- 두 arm 모두 3,295,200 query-document-view scores, reader call 0.
- 차이 하나: early normalized scalar sum 대 weighted reciprocal-rank late readout.
- 주지표: `hard4_recall10_multiview_minus_early`, baseline 0, noise 0.02.
- 사전 kill: hard-4 gain ≤ 0 또는 2-support gain < −0.01.
- prediction receipt `6d53bf5e…9dd67`가 `04:45:48Z`, 측정 시작이 `04:47:12Z`로 사전등록이 83.9초 앞섰다.

`register_prediction` 호출의 transport envelope는 500을 냈지만, 쓰기는 이미 커밋되어 authoritative GET에서 content-addressed prediction receipt와 `PREDICTED` 상태가 확인됐다. 측정은 이 readback 뒤에만 시작했다.

## 4. 결과

| 층 | early scalar | fixed late RRF | Δ late−early | 95% bootstrap CI |
|---|---:|---:|---:|---:|
| hard-4 recall@10, n=80 | 0.478125 | 0.478125 | **0.000000** | [−0.015625, 0.015625] |
| hard-4 full-chain@20 | 0.012500 | 0.000000 | **−0.012500** | — |
| 2-support recall@10, n=320 | 0.795312 | 0.779687 | **−0.015625** | [−0.029687, −0.003125] |

세부 hop label에서도 이득은 없었다: bridge-comparison 0, comparison −0.023810, compositional −0.014451, inference 0. preregistered check 네 개가 모두 실패했고, 공동 통과 margin은 `−0.0325`였다.

따라서 측정 커널의 판정은 `equivalent`다. 독립 judge가 반례를 `local_not_global`로, 대응을 `lemma_incorporation`으로 제출했다. 즉 HSWM 핵을 포기하거나 반례를 재정의하지 않고 **“고정 lexical routing + late RRF면 충분하다”는 보조정리를 조건화**했다.

라이브 서버 최종 상태:

- node state: `REJECTED`
- metric verdict: `equivalent`
- dialectical/Lakatos verdict: `degenerating`
- verdict receipt: `04085674…bfaed`
- previous prediction receipt: `6d53bf5e…9dd67`
- receipt fold: `ok=true`, rederived=`degenerating`
- 측정 등급: `client_asserted`; `script_sha_server_verified=false`, replay=`not_attempted`

마지막 두 항목 때문에 이 판정은 receipt chain이 유효하다는 뜻이지 서버가 데이터를 직접 재실행했다는 뜻은 아니다. 다음 승격 주장은 producer replay 또는 attestation을 별도 관문으로 둬야 한다.

## 5. 무엇이 죽었고 무엇이 남았나

죽은 것:

- role view를 나누기만 하면 이긴다는 주장.
- lexical cue로 고정한 query routing.
- late RRF 자체가 early scalar collapse의 충분한 치료라는 주장.

남은 것:

- n-ary hypergraph memory substrate.
- `semantic=SEED, structure=EDGE` 분리.
- 학습형 hop/role specialist와 query-aware gate.
- direct-edge deletion/private-ID 아래의 진짜 추론 효과.
- recall이 아닌 이식성·증분삽입·steerability 효능.

따라서 이 결과는 ParallaxRAG류의 학습형 멀티뷰를 반증하지 않는다. 오히려 **“멀티뷰라는 자료구조만으로는 부족하고 specialization/gating이 load-bearing일 수 있다”**로 다음 반증점을 좁힌다.

## 6. 다음 falsifier — P6

라이브 tree에 `Q-learned-gate-privateid-hardhop`를 frontier로 열었다. 아직 스크립트가 동결되지 않았으므로 prediction은 등록하지 않았다.

제안하는 다음 사전등록은 다음과 같다.

1. arm A: 현재 equal-compute early scalar.
2. arm B: 이번에 기각된 fixed late RRF를 음성 대조군으로 보존.
3. arm C: train-only learned hop/role gate + anchor/evidence/n-ary bridge specialist.
4. 데이터: 2Wiki + HotpotQA 또는 MuSiQue, 3 seeds, test label은 gate 학습에 금지.
5. 오염 차단: private entity IDs와 direct answer-edge deletion을 각각 독립 factor로 둔다.
6. 비용 통제: 동일 retrieval score budget, gate의 parameter/FLOP은 scalar-control calibration arm과 맞춘다.
7. 통과: 두 벤치 모두 hard-hop recall@10 +0.03 이상, paired CI lower > 0, deletion 조건 full-chain@20 +0.05, 2-support 회귀 ≥ −0.01.
8. kill: 한 벤치라도 부호 반전, private-ID에서 이득 소실, 또는 추가 scorer budget에서만 이득 발생.

## 7. 재현·감사 표면

- 측정 하네스: `prom_search_hswm/prom_p5_multiview_hardhop.py`
- 원 evidence: `prom_search_hswm/evidence/EVIDENCE_p5_multiview_hardhop_20260722.json`
- prereg: `prom_search_hswm/evidence/PREREG_p5_multiview_hardhop_20260722.json`
- 완전 판정 packet: `prom_search_hswm/judgments/P5_multiview_hardhop/judgment_packet.json`
- 최초 422와 교정 요청·응답·receipt·fold readback은 같은 judgment 디렉터리에 보존했다.

검증 완료:

- evidence schema: `errors=[]`, `grounded=true`, authored verdict 없음.
- local pure record judge: `equivalent`.
- `symposium-lakatotree-judgment/v1`: complete, linked artifact hashes verified.
- live receipt fold: `ok=true`, scripted source confirmed.

이 문서는 사용자 발화를 새 정전으로 만들지 않는다. 실측과 영수증을 제외한 해석·다음 설계는 사용자 ratification 전까지 `SECONDARY_AI`다.
