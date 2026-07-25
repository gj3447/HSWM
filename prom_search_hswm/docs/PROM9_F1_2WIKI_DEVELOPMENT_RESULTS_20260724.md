# PROM-9 F1 실제 LLM 함수망 개발 실측 — 2026-07-24

## 판정

**`DEVELOPMENT_ONLY / HSWM 고유 우위 미확증`**

실제 2WikiMultiHopQA validation 4문항과 DGX의 `Qwen/Qwen3.6-27B`를 사용해
5개 arm을 각각 정확히 3회 호출했다. 최종 공정성 수정 런 `f1-2wiki-dev-r4-20260724`에서
typed HSWM은 flat보다 1문항 높았지만 vector와 동률이었다. 표본이 4개뿐이고, paired
bootstrap 하한이 0이며, 실제 소비 토큰 동등성도 실패했으므로 efficacy 또는 HSWM 고유
효과를 주장할 수 없다.

## 실측 조건

- 데이터: `framolfese/2WikiMultihopQA`, config `default`, split `validation`, offset 0,
  length 4. Dataset Viewer에서 받은 원문 바이트의 hash를 source receipt에 고정했다.
- gold 분리: retrieval feature와 실행 manifest를 만든 뒤 정답은 별도 파일에 기록했으며,
  run 단계는 gold를 열지 않았다. judge 단계에서만 gold를 열었다.
- 모델: DGX vLLM의 `qwen3.6-27b` (`Qwen/Qwen3.6-27B`), temperature 0,
  `enable_thinking=false`, JSON-object 응답.
- arm: typed HSWM, flat 3-call, vector-memory 3-call, typed role removal,
  typed role-instruction shuffle.
- 공통 상한: 문항/arm당 3 physical calls, 호출당 최대 출력 512 tokens,
  합계 최대 출력 1,536 tokens, 동일 후보 universe, 동일 모델, 동일 4,096-byte
  persistent-state capacity.
- 평가지표: normalize 후 exact answer match. bootstrap 10,000회, seed 20260724.

## 결과

| arm | exact match | 정답률 | 실제 총 토큰 | 선택 bond 수/문항 |
|---|---:|---:|---:|---:|
| typed HSWM 3-function network | 2/4 | 0.50 | 13,722 | 3, 3, 3, 3 |
| flat 3-call workflow | 1/4 | 0.25 | 10,495 | 3, 3, 3, 3 |
| vector-memory 3-call workflow | 2/4 | 0.50 | 10,848 | 3, 3, 3, 3 |
| role removed, schema-preserving null | 0/4 | 0.00 | 10,114 | 0, 0, 0, 0 |
| role instructions shuffled, ports preserved | 1/4 | 0.25 | 12,472 | 3, 3, 3, 3 |

Paired 차이는 다음과 같다.

| 비교 | 평균 차이 | bootstrap 95% |
|---|---:|---:|
| typed − flat | +0.25 | [0.00, 0.75] |
| typed − vector | 0.00 | [0.00, 0.00] |
| typed − role removed | +0.50 | [0.00, 1.00] |
| typed − role shuffled | +0.25 | [0.00, 0.75] |

판정기 gate:

- `exact_three_calls_each=true`
- `typed_beats_vector=false`
- `typed_beats_flat_lcb_gt_0=false`
- `removal_loses_effect=true`
- `shuffle_loses_effect=true`
- `equal_budget=false`

모든 문항에서 arm 간 실제 입력+출력 소비량 차이가 등록 허용치 512를 넘었다. 문항별
spread는 813, 1,008, 935, 928 tokens였다. 동일 call 수와 동일 최대 출력 예산은 지켰지만,
typed arm의 구조 feature와 프롬프트가 더 길어 실제 소비 compute는 같지 않았다. 따라서
"동일 호출·토큰 예산에서 typed가 이겼다"는 첫 질문의 답은 현재 **아니다**.

## 세 가설에 대한 현재 답

1. **typed LLM function network가 flat/vector를 이기는가?**
   flat에는 방향성 `+0.25`가 있었지만 유의한 하한이 없고 vector와 동률이다. 소비 토큰
   parity도 깨졌다. **미확증**이다.
2. **결과 신호가 실제 bond weight를 바꾸고, 제거하면 개선도 사라지는가?**
   이 F1 런에서 BF 제거 시 선택 bond가 매 문항 3개에서 0개로 바뀌고 점수가 0.50에서
   0으로 떨어졌다. 그러나 이것은 **함수 역할/선택 경로 제거** 효과이지,
   outcome→credit→persistent `Delta W` 학습과 그 learned weight 제거 실험이 아니다.
   후자는 아직 실측하지 않았다.
3. **Agent A의 weight 변화만으로 동결 Agent B가 unseen에서 좋아지는가?**
   이 런에는 training Agent A, frozen Agent B, sealed unseen split이 없다. **미실측**이다.

따라서 이번에 나온 고유한 결과는 "typed port와 BF 경로가 실제 27B 모델 호출을 거쳐
끝까지 실행되고, role 제거가 bond 선택과 downstream answer를 인과적으로 끊는다"는
engineering observation이다. vector baseline을 넘어서는 HSWM 고유 efficacy 결과는 아직 없다.

## 개발 중 발견해 수정한 두 문제

- 긴 human-readable `request_id`를 모델이 변형해 run이 fail-closed 되었다. 실행 정체성은
  call receipt가 이미 별도로 결박하므로, 모델에는 receipt-bound 20-hex digest만 복사하도록
  바꿨다. 관련 테스트는 통과했다.
- 초기 r3에서는 typed AF만 shortest-span 출력을 강제해 exact-match에 유리했다. r3의
  `2/4 vs 0/4 vs 1/4` 결과는 유효 비교에서 제외하고, 모든 arm에 같은 shortest-span
  계약을 적용한 r4만 위 표에 사용했다.

## 다음 실험 gate

1. arm별 prompt/input token을 사전 투영하고, 의미 없는 padding 없이 허용 feature plane을
   더 압축해 문항별 실제 token spread를 등록 허용치 안으로 줄인다.
2. 수정된 protocol을 freeze한 뒤 더 큰 sealed cohort와 독립 evaluator로 F1을 재실행한다.
3. P1v5에서는 outcome receipt가 used-bond eligibility tag를 통해 persistent slow-weight
   snapshot을 실제 변경하는지, learned delta만 제거했을 때 이득이 사라지는지 검사한다.
4. P2에서는 Agent A update packet 이외의 transcript/state 전달을 금지하고, frozen Agent B의
   sealed unseen 성능과 no-transfer/shuffled-transfer를 비교한다.

## 재현·영수증

- manifest SHA-256: `0b77af0eb16fe524c85efa7f05d8b7d1bff0a447700759a22e85aa23093d6871`
- source receipt embedded SHA-256: `99dbae543b256333aefe81b76f7e74f68edfdfa79d5c27b8c726c38aa1066a67`
- suite receipt SHA-256: `97fd2d317471f25a0f620976c0e90092cff69eff567d497d37a1f34aaf61b9dd`
- judgment SHA-256: `055e25a69e65db9d8f673e8f86627c1562470cac4384bcb5338891e686a4d31d`
- protocol file SHA-256: `2caf7011214557fffde0b60c13c5a394343a0a1f3097ccab0618cfd6a2b2a2bc`

Raw artifacts are under `_research/prom9_runs/f1-2wiki-dev-r4/`. This is a local
development receipt chain, not a preregistered or LakatoTree-judged result.
