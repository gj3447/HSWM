# HSWM-DNRD-5 DGX live Q1 v3 result: finite exactness falsified

- Date: `2026-08-29`
- Machine: DGX `edgexpert-e229`
- Served model: `qwen3.6-35b-a3b`
  (`Qwen/Qwen3.6-35B-A3B-FP8`, revision
  `95a723d08a9490559dae23d0cff1d9466213d989`)
- Runtime: vLLM `0.25.1`, NVIDIA GB10, compute capability `12.1`
- Frozen Q1 terminal:
  `LIVE_FALSIFIED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FROZEN_Q1`
- Source-A disposition: `SOURCE_A_REFUSED_EXACTNESS_UNQUALIFIED`
- DNRD-5 causal effect: `NOT_EVALUATED`
- Source-A freeze or artifact created: no
- Retry, resume, repair, replacement, relabeling, or rerun of this Q1 plan:
  forbidden

## Result first

사전등록된 24개 public-synthetic case에 같은 exact request를 네 번씩 보내는
DGX live Q1 v3를 96/96회 완료했다. HTTP response 96개가 모두 성공했고 retry는
0이었으며, hash-chained ledger와 frozen independent verifier도 완결성을
재검증했다. 그러나 `QCASE-024`의 네 assistant-content UTF-8 값 중 하나가 다른
의미의 rationale을 생성했다. 사전 고정 comparator는 assistant content 전체의
byte equality였으므로 primary terminal은 명확한 `FALSIFIED`다.

이것은 모델이 틀렸다는 결과가 아니다. corpus에는 correctness evaluator가 없고,
이번 측정은 정확성·효능·인과효과를 평가하지 않았다. 또한 24개 prompt를 어떤
모집단에서 IID 표집한 것이 아니므로 `23/24` 또는 `95/96`을 일반 반복률로
추정하지 않는다. 직접 반증된 것은 오직 아래에 고정된 한 model/runtime/request/
RNG/isolation 구성에서의 finite exact assistant-content repeatability다.

## 직접 측정

| 항목 | 결과 | 해석 |
|---|---:|---|
| Frozen budget | 24 cases × 4 replicas = 96 POST | 전량 소비, 재실행 금지 |
| START / successful TERMINAL | 96 / 96 | HTTP success, retry 0 |
| Exact four-replica cases | 23 / 24 | finite corpus 기술값 |
| Varying cases | `QCASE-024` 1개 | primary exactness 반증 |
| Outputs equal to each case's modal bytes | 95 / 96 | post-hoc 기술값, population estimate 아님 |
| Ledger | 195 rows, 210,683 bytes | chain·ordinal·self-hash 유효 |
| Content store | 432 blobs, 1,556,791 bytes | filename/hash mismatch 0 |
| DNRD-5 causal blocks/calls | 0 / 0 | causal effect 미평가 |

Ledger는 `PLAN_CONSUMPTION` 1행, `LIVE_MARKER` 1행, 96개의 START와 96개의
successful TERMINAL, `RUN_SEAL` 1행으로 끝난다. 마지막 record SHA-256은
`14e9bd0a7867939045f8817b716ec0734036c5bee0a8e4bfdf15072b22b32092`,
ledger SHA-256은
`f3cdfff46e1ee4ff0973531296863970f7bc9fa21eff1ea60ddc4da7a6e13f00`다.
정확한 원장은
[`dnrd5_dgx_live_q1_attempt_ledger_2026-08-29.jsonl`](raw/dnrd5_dgx_live_q1_attempt_ledger_2026-08-29.jsonl)에
보존했다.

## 관측된 단일 분기

`QCASE-024` request SHA-256은 네 replica 모두
`c24c74241bbf670b3e2c640f3acd18cb449d3172659bde5fcb08262950a53a19`였다.
request는 `temperature=0`, `top_p=1`, `n=1`, `stream=false`, seed
`116212972334048`, strict JSON schema, `max_tokens=256`을 고정했다. frozen
순서에서 R3, R4, R2, R1은 각각 3, 10, 19, 46번째 호출이었다.

R1·R2·R4의 exact assistant content는 다음 234 bytes였다.

```json
{
  "answer": "VISTA",
  "rationale": "The first cue explicitly starts with the letter V, which matches the beginning of VISTA. The second cue describes the word WATER, which is a different label and does not fit the initial letter"
}
```

SHA-256은
`14bc62d62791f445e539a4c4e1f212c0d7e5d818095ae87608fcc8eabf262a31`이고,
exact bytes는
[`modal assistant content`](raw/dnrd5_dgx_live_q1_qcase024_modal_assistant_content_2026-08-29.json)에
보존했다. R3의 exact assistant content는 다음 231 bytes였다.

```json
{
  "answer": "VISTA",
  "rationale": "The first cue highlights the letter V which is the starting letter of VISTA. The second cue provides a word length that does not match VISTA but helps distinguish it from the other options."
}
```

SHA-256은
`b8dba1c6c5d591e9460923c93bc3b129686ff97e1fef1d33a99f261df02d6d23`이고,
exact bytes는
[`variant assistant content`](raw/dnrd5_dgx_live_q1_qcase024_variant_assistant_content_2026-08-29.json)에
보존했다. completion token 수 역시 modal 59와 variant 58로 달랐다. 따라서
공백·key order 차이만이 아니라 rationale 의미가 달라진 출력 분기다.

네 `answer` 필드가 모두 `VISTA`였다는 것은 결과를 본 뒤 분리한 field-level
기술값일 뿐이다. Q1의 primary endpoint를 구제하지 않으며 정답성, semantic
stability 또는 HSWM 효능으로 승격하지 않는다.

## Frozen 실행 경계와 독립 재검증

Q1 plan SHA-256은
`b054396e68620c2bcc97a9da9c429edda3182c93d41a573e6eef6fe30c997c22`,
closure-manifest SHA-256은
`04f16434ebea65f6a0551313c6686ab6dbe5668e8566cc7a5aa38bef71bae661`이다.
publication commit은 `fddfe6eecdc508b1ad7fada114374fdc2dda265c`, tree는
`6c6d3a2ad26a20e85e2db478d83d2f49c607a057`이며, exact-head GitHub CI
run [`33255350582`](https://github.com/gj3447/HSWM/actions/runs/33255350582)는
첫 attempt의 8개 job이 모두 성공했다.

실행 `dgx-q1-v3-live-fddfe6e-001`은 `2026-08-29T13:45:35Z`부터
`13:55:22Z`까지 진행됐다. run receipt SHA-256은
`a10d107463823218ada992945d7b72167669e0948b3019dd680607a530c30978`,
archive SHA-256은
`b01c034b32e44953a1d4c3882c01acd5ffaa7f71a6f8eb51b6d1a78c36b40afc`
(2,129,920 bytes)다. durable path는
`/mnt/hswm/runs/dgx-q1-v3-live-fddfe6e-001`이다.

plan-consumption marker는 첫 live START 전에 node-local durable registry에
기록됐고 SHA-256은
`7196b27a29b61087413c756a0823105258063ff06903f48c0e6f8518c9ed655a`다.
따라서 이 plan은 소모됐으며 어떤 수정·재시도·재개도 하지 않는다.

별도 run `dgx-q1-v3-independent-reverify-fddfe6e-003`은 frozen verifier source
SHA-256
`124e91dba89952ac8a72824810f89be0085de3ab5fe3bd0ac6229801966963dc`로
동일한 195-row ledger와 동일한 `FALSIFIED` terminal을 다시 산출했다. receipt
SHA-256은
`8b7e4096f3ab2635f272ba81aacd15246acdbe147ce63c3df7772e49d00e3406`다.
체크인한 execution receipt, independent result, independent re-verification과
content-addressed summary는 각각
[`raw results`](raw/)와
[`evidence receipt`](../evidence/EVIDENCE_HSWM_DNRD5_DGX_LIVE_Q1_2026-08-29.json)에
있다. 2.13 MB archive 전체는 durable data-01 path와 digest로 보존했다.

## 무엇이 반증됐고 무엇이 미판정인가

vLLM 공식 문서는 기본 설정의 재현성을 보장하지 않으며 online serving의
scheduling-independent 재현성 수단으로 batch invariance를 설명한다.
[`VLLM_ENABLE_V1_MULTIPROCESSING=0`](https://docs.vllm.ai/en/stable/usage/reproducibility/)만으로
online 전역 결정성이 성립하는 것은 아니다. Qwen3.6은 Gated DeltaNet과 full
attention을 섞은 hybrid MoE이고, pinned vLLM `0.25.1`의 GDN path는 batch
invariance를 지원하지 않아 v2가 POST 0건으로 거절된 사실도 별도로 보존돼 있다.
이는 [Qwen3.6 model card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8/blob/main/README.md)와
[vLLM의 GDN 지원 이슈](https://github.com/vllm-project/vllm/issues/48613)에
부합한다.

이번 v3는 batch invariance를 켜거나 주장하지 않았다. eager execution,
`max_num_seqs=1`, prefix-cache off, V1 multiprocessing off, engine seed 0,
`CUBLAS_WORKSPACE_CONFIG=:4096:8`, dedicated container/GPU, sequential calls를
고정한 finite serialized observation이다. 따라서 다음의 원인은 모두
`UNJUDGED`다.

- greedy decoding 중 근접한 token score가 작은 수치 차이로 갈렸는지
- asynchronous scheduling 또는 worker history가 영향을 줬는지
- GDN, FP8, kernel 또는 reduction path의 수치 차이가 영향을 줬는지

eager mode는 torch.compile과 CUDA Graph를 끄므로 이를 이번 원인으로 바로
지목할 수 없다. FP8 rounding이 가능한 수치 민감성이라는 일반 근거도 원인
증거가 아니다. 첫 divergence token과 그 지점의 competing-token log probability를
Q1이 기록하지 않았으므로 이번 자료로 causal attribution은 불가능하다.

반증된 강한 명제는 더 좁다. 이 frozen 구성에서 request seed와 greedy 설정을
고정하는 것만으로 assistant-content byte identity가 보장된다는 명제는 finite
counterexample을 얻었다. 반대로 provider-wide nondeterminism, 모든 Qwen3.6
configuration의 변이, 모델 품질 저하 또는 특정 kernel의 결함을 입증한 것은
아니다.

## DNRD-5와 HSWM에 대한 결과 경계

[`exactness policy`](../docs/research/HSWM_DNRD_5_EXACTNESS_POLICY_AMENDMENT_2026-08-28.md)는
frozen boundary 안의 deterministic response generation을 exact-test assumption
profile의 강한 충분조건으로 요구하고, finite replay가 그 profile을 반증할 수
있다고 정한다. falsifying result가 있으므로 Source-A disposition은
`SOURCE_A_REFUSED_EXACTNESS_UNQUALIFIED`다. 이는 Source-A freeze나 artifact가
아니며 둘 다 만들지 않았다. Source B, future beacon, 300-block occurrence 또는
DNRD-5 causal model call도 승인되지 않는다. 따라서 causal effect는 0·null·음수가
아니라 `NOT_EVALUATED`다.

HSWM의 target identity는 하나의 token-native LLM-function macro-neural
network이고, evolving hypergraph가 living harness·world model·continuous
learner의 역할을 함께 수행한다. 이 DGX qualification, repository ontology,
live KG, launcher 및 receipt는 cognition이나 learning이 아니라 bounded
projection/interface다. 이번 결과는 outcome-bound causal learning,
HSWM-of-HSWMs의 same-rule recursive composition, 여덟 FCL 법칙, consciousness,
selfhood 또는 scale-invariant causal closure를 입증하거나 반증하지 않는다.
fractal status는 계속
`SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`다. 따라서 live KG는
갱신하지 않는다.

## 다음 과학 단계

이 Q1을 v4로 반복하거나 통과시키려 하지 않는다. 다음 실험은 결과를 본 뒤
선택했다는 사실을 명시한 별도 `QCASE-024 mechanism-isolation diagnostic`이어야
한다. 같은 model/revision/image/GPU/request를 고정하되 async scheduling on/off를
각각 두 fresh server block에서 네 번씩 직렬 관측하는 2×2 blocked design, 총
16 POST를 사전등록한다. 두 arm 모두 `logprobs=true`, `top_logprobs=20`과
processed-logprob 기록을 사용해 첫 divergence token과 selected-versus-competing
token gap을 보존한다.

그 결과는 scheduler-sensitive path 또는 near-tie amplification과의 일치 여부만
판단할 수 있고 원인을 확정하지 못한다. GDN과 FP8을 분리하려면 checkpoint,
precision 또는 backend를 바꾸는 별도 factor experiment가 필요하다. 이 후속
diagnostic 역시 Q1 재시도, Source-A qualification, DNRD-5 causal occurrence 또는
HSWM 효능 시험이 아니다.
