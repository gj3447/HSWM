# HSWM-DNRD-5 Q0 qualification result: consumed, non-closeable

- Date: `2026-08-29`
- Machine: DGX `edgexpert-e229`
- Served model: `qwen3.6-35b-a3b` (`Qwen/Qwen3.6-35B-A3B-FP8`, vLLM `0.25.1`)
- Scientific status: `UNJUDGED`
- Q0 closure: not emitted
- Source-A eligibility/refusal disposition: `SOURCE_A_REFUSED_EXACTNESS_UNQUALIFIED`
- Source-A freeze or artifact created: no
- DNRD-5 causal occurrence calls: `0`
- Retry, resume, repair, replacement, or relabeling of this Q root: forbidden

## Result first

DGX에서 DNRD-5 인과 occurrence를 실행하지 않았다. 그 전에 요구되는 공개
synthetic Q0 response-reproducibility qualification을 시작했으나, 계획된 96회 중
첫 호출 하나만 소비한 뒤 계측 계약에서 멈췄다. 따라서 이 결과는 인과효과가
없다는 null 결과도, 인과효과가 있다는 양성 결과도 아니다. 인과효과는
`NOT_EVALUATED`다.

첫 호출 `DNRD5-Q-005-R004`은 HTTP `200`, `finish_reason=stop`, 올바른 served
model, token usage `166 + 41 = 207`, ordinary strict JSON 및 frozen response
schema 검증을 통과했다. 그러나 vLLM raw response envelope 778 bytes가
canonical-json/v1 바이트가 아니었다. gateway가 이 raw envelope에
`parse_canonical(observed.body)`를 적용하면서 `CANONICALJSONERROR`가 발생했고,
호출 ID는 zero-retry 규칙에 따라 영구 소비됐다. assistant content도 ordinary
JSON과 schema에는 맞지만 pretty JSON이라 canonical bytes가 아니었다. 이는
모델 정답 실패가 아니라 provider 직렬화와 gateway exactness 계약의 불일치다.

독립 verifier도 Q0 closure를 만들지 못했다. Q0 plan은 24개 exact request
hash를 precommit했고 independent verifier는 그에 대응하는 content blob 전부를
요구한다. 그러나 gateway는 first START 전에 instruction·model input·schema·RNG
blob만 저장하고 constructed request는 각 `execute_one` 시점에 저장했다. 첫 호출
뒤 중단됐기 때문에 durable root에는 실제 호출된 request 하나만 있고 나머지
23개가 없다. verifier는 불완전한 3-row ledger를 preregistered
`INCONCLUSIVE_QUALIFICATION_EVIDENCE`로 처리하는 지점보다 앞서 다음 오류로
fail-closed했다.

```text
corpus request_sha256 blob missing
```

따라서 `REPRODUCED_ON_FROZEN_QUALIFICATION_CORPUS_UNDER_DECLARED_BOUNDARY`,
`FALSIFIED_RESPONSE_REPRODUCIBILITY_ON_FROZEN_QUALIFICATION_CORPUS`,
`INCONCLUSIVE_QUALIFICATION_EVIDENCE` 중 어느 frozen terminal도 주장할 수 없다.
`q0.closure.json`은 생성되지 않았다. 사후에 23개 blob을 채우거나 root를
고쳐서 closure를 만드는 것도 금지된다.

## 측정·증거 품질 판정

| 항목 | 직접 확인 결과 | 판정 |
|---|---:|---|
| Frozen Q0 budget | 24 cases × 4 replicates = 96 calls | 계획만 고정 |
| Q ledger | marker 1 + START 1 + TERMINAL 1 = 3 rows | chain·ordinal·self-hash 유효 |
| Model dispatch / observed response | 1 / 1 | qualification-only |
| Gateway-accepted response | 0 | raw-envelope canonicalization에서 실패 |
| Unstarted Q slots | 95 | 재시작 금지 |
| Precommitted request blobs | 1 present / 23 missing | 독립 closure blocker |
| DNRD-5 causal blocks/calls | 0 / 0 | 인과효과 미측정 |
| Content-addressed store | 68 blobs, 81,667 bytes | filename/hash mismatch 0 |
| Whole Q root | 72 files, 117,261 bytes | 원본은 data-01에 보존 |

체크인한 exact ledger는
[`dnrd5_q0_attempt_ledger_2026-08-29.jsonl`](raw/dnrd5_q0_attempt_ledger_2026-08-29.jsonl),
실행 영수증은
[`dnrd5_q0_execution_receipt_2026-08-29.json`](raw/dnrd5_q0_execution_receipt_2026-08-29.json),
독립 verifier 영수증은
[`dnrd5_q0_independent_verifier_receipt_2026-08-29.json`](raw/dnrd5_q0_independent_verifier_receipt_2026-08-29.json)이다.
원시 provider envelope는 durable root의 content-addressed blob
`3b08a206d8852eacfa095b777161f41c6d328ce077acdee6ab2f9e61a58386d1`
로 보존했다.
단, data-01에 접근할 수 없는 제3자는 체크인된 exact ledger·wrapper
receipts·content hashes를 검증할 수 있을 뿐, 외부 root와 archived
stdout/stderr·artifact tar 전체를 독립 replay할 수는 없다.

## Frozen 경계와 추가 blocker

Q0 plan SHA-256은
`340306cd4e1d412576eacc9fdc312d72bf3bfdc0dedbce5be3ba9515a33db366`,
root UID는 `hswm:dnrd5:q0:dgx:2026-08-29:001`이다. Q0 source/build commit
`a4f3a21a5bdd603073ab88c26c3f176c5294cec5`의 첫 CI attempt
[`33231879117`](https://github.com/gj3447/HSWM/actions/runs/33231879117)와
Q0 publication commit `aab5085e7eb6ae461f2f599e25e486e383fc9397`의 CI
[`33232381857`](https://github.com/gj3447/HSWM/actions/runs/33232381857)는 각각
8개 job이 모두 성공했다. DGX run receipt는 publication commit을 기록하고,
Q0 plan은 source/build commit을 결속한다. 두 commit 사이에서 네 Q0 Python
source blob은 byte-identical하고 차이는 13개 frozen publication artifact의
추가뿐이다. 이 구분은 실행 출처를 숨기지 않기 위해 명시한다.

출력 전에 고정한 isolation identity 자체도 Source A를 허용하지 않는다:
prefix caching은 enabled, `max-num-seqs=6`, cross-process provider state는
closed가 아니고, no-interference는 성립하지 않았으며 다른 vLLM process가
관측됐다. 그러므로 Q0가 완주했더라도 이 identity만으로 production-shape
Source A를 승인할 수 없었다.

처음 두 `hswm-run` launcher는 각각 bare `python`과 bare `uv`가 DGX PATH에
없어 exit `127`로 pre-dispatch 종료됐다. 두 실행에는 evidence root, START,
model call이 없다. receipt SHA-256은 각각
`890d3a597c52a27bd41e0e54369ed0aa835fd464067e84321fbd8aff82bd1de7`,
`b7781f7c6105b8297a31ccc4d3def0cfc55624097ce49b25cbef59f9a0b66025`다.
실제 one-call run과 verifier run receipt SHA-256은 각각
`411bac08868375de1825dc265c08d4a7980c3bdd4e70295a76f4ec323dbf6ecc`,
`4d42f856f4245bc56b35a216f1427a1e19de44f97a69a82a3e60e9cbb9e1b729`다.

## HSWM 정체성 및 과학적 의미

HSWM의 target identity는 하나의 token-native LLM-function macro-neural
network이고, 진화하는 hypergraph가 living harness·world model·continuous
learner 역할을 함께 수행한다. Q0 gateway, ledger, repository ontology, KG 및
MCP는 그 정체성의 cognition이나 learning이 아니라 bounded evidence
projection과 interface다. 이번 결과는 HSWM-of-HSWMs의 same-rule recursive
composition, 여덟 FCL 법칙, outcome-bound causal learning, consciousness,
selfhood 또는 scale-invariant causal closure를 입증하거나 반증하지 않는다.
따라서 fractal research status도 기존
`SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`에서 변하지 않는다.

이번에 새로 확정된 것은 HSWM 효능이 아니라 두 개의 측정 도구 결함이다.

1. ordinary provider JSON을 raw canonical JSON으로 요구한 wire-contract는 현재
   vLLM endpoint와 호환되지 않는다.
2. plan의 24개 request hash precommit과 verifier의 24개 request blob 요구에
   비해 gateway가 dispatch 시점에만 request를 저장하여, 첫 호출 실패 뒤
   independent closure가 불가능하다.

이는 material negative instrument result다. harness가 더 길어진 것을 HSWM의
과학적 진전으로 세지 않는다.

## 다음 과학 단계

이 Q root와 attempt는 닫혔다. 수정, 재시도, 재개, 대체, 같은 결과의 재판정은
하지 않는다. DNRD-5 Source-A eligibility/refusal disposition은
`SOURCE_A_REFUSED_EXACTNESS_UNQUALIFIED`다. 이는 Source-A freeze나 artifact가
아니며 둘 다 생성되지 않았다. 따라서 Source B, future randomness, premarker,
300-block·2,700-call causal occurrence는 승인되지 않는다.

후속 연구가 필요하면 이 실행을 구제하거나 relabel하지 않는 별도 preregistered
successor여야 한다. 그 successor는 최소한 (1) 첫 START 전에 24개 exact request
blob 전부를 내구성 있게 물질화하고, (2) raw envelope를 그대로 보존하되 ordinary
JSON parse 후 canonicalized parsed value를 structured comparator에 쓰는 새 계약을
사전 고정하고, (3) provider cache·concurrency·cross-process interference를 닫거나
독립적으로 계량하며, (4) W0 materialization, 네 arm, 300-block runner와 independent
occurrence judge를 end-to-end rehearsal로 통과시켜야 한다. 그 뒤에만 새로운
Source A/B와 future-randomness chronology를 시작할 수 있다.
