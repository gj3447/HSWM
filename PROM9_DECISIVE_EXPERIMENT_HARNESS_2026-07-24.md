# PROM-9 결정 실험 하네스

> 날짜: 2026-07-24
> 상태: `IMPLEMENTED_DEVELOPMENT_READY`
> 과학 경계: 하네스 구현과 로컬 테스트 통과는 F1/P1v5/P2 효능 결과가 아니다.

## 1. 무엇을 만들었나

세 질문을 하나의 receipt 규약으로 검사한다.

| 질문 | 실행/판정 파일 | 통과할 때만 허용되는 주장 |
|---|---|---|
| typed LLM 함수망이 동일 예산 flat/vector보다 좋은가 | `prom_search_hswm/prom_f1_function_network.py` | `F1_SUPPORTED_NARROW` |
| outcome이 실제 used bond weight를 바꾸며 제거 시 이득이 사라지는가 | `prom_search_hswm/prom9_causal_harness.py judge-p1v5` | `P1V5_SUPPORTED_NARROW` |
| Agent A weight write만으로 frozen B가 unseen에서 좋아지는가 | `prom_search_hswm/prom9_causal_harness.py judge-p2` | `P2_SUPPORTED_NARROW` |

공통 하부는 다음 네 모듈이다.

- `hswm_typed_ports.py`: 여섯 input/output port를 exact-key JSON으로 검증한다.
- `hswm_function_registry.py`: role, model revision, prompt, port를 한 registry hash에 묶는다.
- `hswm_call_receipt.py`: 모든 physical call의 input/output port hash와 token/cost 정보를 남긴다.
- `hswm_function_network.py`: 모든 F1 arm을 정확히 `QF → BF → AF` 세 번 호출한다.

LLM 응답은 다음 함수의 instruction으로 직접 실행되지 않는다. 먼저 typed port를 통과한 JSON
data만 다음 함수 입력으로 들어간다.

## 2. F1 — 동일 호출·토큰 예산 함수망

### 입력 준비

[`f1_manifest.development.example.json`](_research/prom9_harness/f1_manifest.development.example.json)을
복사해 실제 개발 split과 candidate로 교체한다. `observable`에는 다음을 넣는다.

- typed arm용: base score, provenance, incidence/seam 등 등록된 observable component;
- flat arm용: `flat_position`, `flat_score`, `source_type`;
- vector arm용: `vector_score`, `source_type`.

각 arm의 candidate ID와 payload bytes는 같아야 한다. 하네스는 flat/vector arm에서 허용되지 않은
observable을 모델에게 보여주지 않는다.

### 개발 실행

```bash
export HSWM_LLM_ENDPOINT='http://127.0.0.1:8000/v1/chat/completions'

python3 -m prom_search_hswm.prom_f1_function_network run \
  --manifest _research/prom9_harness/f1_manifest.development.example.json \
  --endpoint "$HSWM_LLM_ENDPOINT" \
  --output /absolute/write-once/f1-development-suite.json
```

인증이 필요하면 key 값을 명령행에 쓰지 말고 환경변수 이름만 전달한다.

```bash
export HSWM_LLM_API_KEY='...'
python3 -m prom_search_hswm.prom_f1_function_network run \
  --manifest /absolute/f1-manifest.json \
  --endpoint "$HSWM_LLM_ENDPOINT" \
  --api-key-env HSWM_LLM_API_KEY \
  --output /absolute/write-once/f1-suite.json
```

### 독립 gold 판정

run 단계는 gold를 받지 않는다. 별도 evaluator가
[`f1_gold.development.example.json`](_research/prom9_harness/f1_gold.development.example.json) 형식으로
gold와 evaluator receipt를 만든 뒤 판정한다.

```bash
python3 -m prom_search_hswm.prom_f1_function_network judge \
  --suite /absolute/write-once/f1-development-suite.json \
  --gold /absolute/separate-evaluator/f1-gold.json \
  --output /absolute/write-once/f1-development-judgment.json
```

개발 manifest는 모든 수치 gate를 통과해도 `DEVELOPMENT_ONLY`만 반환한다. sealed manifest에는
사전등록 receipt hash를 넣고 split/model/prompt/token tolerance를 다시 동결해야 한다.

F1 support는 다음 conjunction이다.

```text
모든 item/arm = physical call 3회
AND model revision/candidate universe/허용 output budget 동일
AND 소비 token spread <= 사전등록 tolerance
AND typed-flat paired bootstrap LCB > 0
AND typed > vector
AND BF removal이 효과를 잃음
AND role shuffle이 효과를 잃음
```

마지막 두 조건이 실패하면 “function topology”가 아니라 “세 번 호출한 workflow” 결과다.

## 3. P1v5 — outcome → eligibility → 실제 weight → removal

P1v5 runner는 Gate-0 accepted learner view와 기존 모듈을 사용한다.

1. `p1_eligibility_tag.py`로 실제 readout에 쓰인 bond만 eligibility tag로 만든다.
2. 외부 evaluator outcome과 baseline으로 modulation을 만든다.
3. `p1_m_commit.py`로 immutable `WeightCandidateV1`을 제안한다.
4. validation/retention/canary를 통과한 candidate만 별도 승인·CAS 경로로 활성화한다.
5. fresh, cross-field, in-field, canary에서 등록된 10개 arm을 모두 측정한다.
6. base/candidate/promoted/removal snapshot과 측정 행을 P1v5 packet으로 묶는다.
7. 아래 judge에 전달한다.

```bash
python3 -m prom_search_hswm.prom9_causal_harness judge-p1v5 \
  --packet /absolute/write-once/p1v5-causal-packet.json \
  --output /absolute/write-once/p1v5-judgment.json
```

judge는 성능표만 보지 않는다.

- `promoted == apply_candidate(base, candidate)`인지 재계산;
- 모든 delta edge가 `used_edge_ids`와 eligibility tag에 결속됐는지 확인;
- removal weight map이 base와 같은지 확인;
- random credit, shuffled eligibility, no-promotion, static update를 함께 비교;
- fresh component-cluster bootstrap과 dataset별 최소 이득을 계산;
- cross/in-field/canary 손상이 `-0.02` 아래인지 확인;
- call/token/candidate/state 예산 audit을 검사한다.

fast만 통과하면 `FAST_ONLY`다. slow snapshot이 존재해도 removal에서 이득이 유지되면 durable
learning 주장은 기각한다.

### P1v5 packet 최소 필드

```text
base_snapshot / candidate / promoted_snapshot / removal_snapshot
training.used_edge_ids / training.eligibility_tags
independent evaluator receipt
split/gold/forbidden-feature/replay audit
10-arm equal-budget audit
fresh/cross_field/in_field/canary item rows
Gate-0 acceptance hash and, sealed일 때, preregistration hash
```

## 4. P2 — Agent A write → frozen Agent B transfer

P2는 F1과 P1v5가 둘 다 `SUPPORTED_NARROW`일 때만 판정 gate를 통과한다.

1. Agent A는 accepted mutation path로만 `WeightCandidateV1`을 write한다.
2. Agent B의 model parameters, prompt, tools, readout, budget manifest를 실행 전후 두 번 hash한다.
3. HSWM arm에서는 A transcript를 숨긴다.
4. training과 component-disjoint인 `fresh_unseen` 질문만 사용한다.
5. no-A, transcript-only, flat, vector, accepted-HSWM, HSWM-removal 여섯 arm을 동일 예산으로 측정한다.
6. packet을 판정한다.

```bash
python3 -m prom_search_hswm.prom9_causal_harness judge-p2 \
  --packet /absolute/write-once/p2-transfer-packet.json \
  --output /absolute/write-once/p2-transfer-judgment.json
```

P2 support는 다음을 동시에 요구한다.

```text
F1_SUPPORTED_NARROW + P1V5_SUPPORTED_NARROW
AND Agent A accepted snapshot이 base와 실제로 다름
AND Agent B before/after freeze manifest가 byte-equivalent
AND transcript visibility=false
AND exact-query cache hit=0
AND train/test component overlap=0
AND HSWM-noA component-bootstrap LCB > 0
AND 모든 dataset delta > +0.02
AND HSWM > flat/vector
AND removal이 no-A 수준으로 돌아가며 HSWM-removal LCB > 0
```

## 5. 개발과 sealed 실행을 섞지 않는 순서

```text
F1 development
  → prompts/ports/budget tolerance freeze
  → LakatoTree prediction registration
  → F1 sealed once

Gate-0 acceptance
  → P1v5 development
  → learner/promotion/rules freeze
  → LakatoTree prediction registration
  → P1v5 sealed once

F1 + P1v5 support
  → Agent B freeze + P2 development
  → transfer split/rules freeze
  → LakatoTree prediction registration
  → P2 sealed once
```

sealed 결과를 본 뒤 prompt, lambda, token tolerance, removal definition, split을 바꾸면 같은 실험의
재시도가 아니다. 새 prediction과 새 branch가 필요하다.

## 6. 현재 경계

- 구현됨: typed port, immutable registry, OpenAI-compatible model port, physical-call receipt,
  five-arm F1 executor, independent F1 judge, P1v5/P2 snapshot-bound causal judges, tests.
- 외부 자산 필요: 실제 F1 split/candidates, real Gate-0 packs, frozen learner, independent evaluator,
  LakatoTree preregistration, model deployment receipt.
- 아직 결과 아님: 현재 repository test PASS는 하네스가 거짓 결론을 fail-closed로 막는다는
  engineering evidence일 뿐이다.
