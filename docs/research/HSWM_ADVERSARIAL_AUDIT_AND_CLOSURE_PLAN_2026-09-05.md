# HSWM 적대적 감사와 폐쇄 계획

> **Date:** `2026-09-05`
>
> **Status:** `ADVERSARIAL_AUDIT_VERIFIED / CLOSURE_PLAN_PROPOSED / USER_PRIMARY_PENDING / G0_NOT_PASSED / G1_LOCKED`
>
> **Scientific status:** `UNJUDGED / INTEGRATED_CLAIM_UNJUDGED`
>
> **Audited commit:** `4dcba752a661de23066b3b33381bfdfc34879a57`
>
> **Target authority:** [`HSWM Constitution`](../canon/HSWM_CONSTITUTION_2026-08-20.md),
> [`adaptive research strategy`](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)
>
> **Machine projection:**
> [`HSWM_CLOSURE_PLAN_ONTOLOGY.v1.json`](../../ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v1.json)
> (bundle UID `sym:AbstractNode:hswm-closure-plan-ontology-2026-09-05`)
>
> **Bound evidence:**
> [`HSWM_ADVERSARIAL_AUDIT_FINDINGS_2026-09-05.json`](../../_research/causal_composition/audits/HSWM_ADVERSARIAL_AUDIT_FINDINGS_2026-09-05.json)

## 1. Answer first

HSWM이 완성되지 않는 이유는 기술 블로커가 아니라 자기부과 조건 세 개의 결합이다.

1. 첫 관문 G0가 한 사람이 채울 수 없는 외부 공증 체인이 됐다. 2026-08-29의 G0 원문은
   "outcome 생산을 actor와 proposer로부터 독립시켜라, 더 정교한 judge나 ontology를 대체물로
   추가하지 마라"였다. 2026-08-30 실행은 evaluator가 같은 프로세스라는 하나의 고칠 수 있는
   이유로 미통과였다. 2026-09-03 이후 그 "독립"이 9개 역할과 13개 외부 서비스로 코드화됐고,
   `hswm-g0-occurrence preflight`는 `BLOCKED_EXTERNAL`과 누락 바인딩 22개를 돌려준다. 그 역할을
   맡을 사람, 계정, 날짜는 어디에도 없다.
2. 규칙집은 기준을 강화만 할 수 있고 정지 규칙은 선언뿐이다. `AGENTS.md`의 "Never weaken a
   success criterion"은 집행되고, 유일한 정지 장치인 burden cap은 숫자도 검사도 없이 쓴 지
   4일 만에 위반됐다.
3. 실제 학습 루프는 2026-08-30 이후 한 줄도 안 바뀐 1비트 레지스터이고 그 위에 Lean, Effect,
   RDF, Neo4j, Temporal 층만 쌓였다. 2026-08-31 이후 35 커밋 중 `results/`, `evidence/`,
   `preregistrations/`, `F1_R8_RESULTS_LOG.md`를 건드린 커밋은 0개다.

"아이디어는 충분하다"는 절반만 맞다. 목표 정체성과 G0..G6 반증 설계는 충분하다. 실행에
필요한 두 문장이 비어 있다. 첫째, G1에서 HSWM revision이 정보량이 같은 text lesson보다 왜
나아야 하는지의 기전 문단이 없다. 둘째, "무엇이 나오면 v1은 끝났다"의 유한한 정의가 canon에
없다.

이 문서와 그 KG 투영은 v3 결과가 나오기 전까지 G0 상태를 다시 진술하는 새 profile, authority,
boundary 문서를 대체한다. 상태 변화는 이 번들의 event version(ratification, v3 receipt)과
`F1_R8_RESULTS_LOG.md`에만 기록한다.

## 2. Canonical role, evidence boundary, and conceptual delta

| Layer | Statement |
|---|---|
| Target identity | HSWM은 하나의 token-native LLM-function macro-neural network이며, evolving canonical hypergraph가 living harness, world model, continuous learner를 동시에 수행한다. 이 문서는 목표를 축소하지 않는다. |
| Current evidence | 2026-08-30 opaque v2는 탐색적 state-readout 식별성만 관측했고 G0 `NOT_PASSED`, G1 `LOCKED`다. 감사 결과는 프로그램 거버넌스에 대한 self-attested AI 판정이지 HSWM 인지, 학습, 효능에 대한 증거가 아니다. |
| Conceptual delta | 새 HSWM 부품을 추가하지 않는다. 감사 발견, 간극, 결정 요청, 순서 있는 6단계, 정지 규칙, 숫자 있는 burden cap을 기존 Claim, Evidence, Decision, Gap 문법으로 한 번들에 고정하고, 완료 상태를 유한하게 정의한다. |

감사 방법은 8개 적대적 finder lens, 1회 병합, 발견마다 독립 반박자 2명(evidence-skeptic,
steelman-maintainer), 1회 합성이었다. 38개 AI agent가 1,421회 도구 호출을 수행했다.
`CONFIRMED`는 두 반박자 모두 반박 실패, `CONTESTED`는 한 명 반박, `REFUTED`는 둘 다 반박이다.
모든 인용은 audited commit 기준이며 발견 원문과 반박 투표는 bound JSON에 있다.

## 3. Verified findings

| # | key | reported → revised | verdict | 살아남은 핵심 |
|---|---|---|---|---|
| 1 | `g0-requires-nine-independent-roles-with-no-plan` | FATAL → FATAL | CONFIRMED | `occurrence_integrity.py`의 `_separate`는 9역할 쌍마다 issuer, subject, account, admin_domain, key_ref가 전부 달라야 한다. 외부 운영자는 어디에도 지정되지 않았다. |
| 2 | `hswm-delta-is-governance-not-behavior` | FATAL → MAJOR | CONTESTED | `project.v1.json`의 G1 pass_rule은 mediation만 요구하므로 "구조적 통과 불가"는 반박됐다. 남는 것은 문서 간 estimand 모순과 H1이 B2를 이겨야 할 기전 문단 부재다. |
| 3 | `core-loop-starved-by-substrate-engineering` | FATAL → MAJOR | CONFIRMED | 2026-08-20 이후 LLM-in-loop 커밋은 극소수이고 `g1_micro*.py`는 2026-08-30 이후 미변경이다. DGX 없이 가능한 Python과 Atom v2 브리지도 안 됐다. |
| 4 | `loop-degenerates-to-one-bit-copy-register` | FATAL → MAJOR | CONFIRMED | 상태는 disposition 최대 1개(`g1_micro.py:1012`), propose 프롬프트가 갱신 규칙을 알려주고 probe 프롬프트는 compiled action_code만 읽으라 한다. ACTIVE 8/8은 지시 따르기 증명이다. |
| 5 | `target-closed-as-civilizational-horizon-no-done-state` | FATAL → MAJOR | CONFIRMED | methodology는 "완성하는 프로젝트가 아니라 탐색 프로그램"이라 적고, 유일한 유한 positive도 독립 재현 뒤에만 후보다. |
| 6 | `g0-requirement-accretion-and-circular-qualification` | MAJOR → MAJOR | CONFIRMED | G0 전제가 실행 없이 약 7항목에서 8항목, 17단계와 9역할로 늘었다. Temporal live 조건은 qualified deployment의 rehearsal을 요구하는데 runtime은 loopback만 허용한다. |
| 7 | `monotone-ratchet-no-termination-rule` | MAJOR → MAJOR | CONFIRMED | 강화 규칙은 집행되고 burden cap은 숫자, 검사, receipt가 없다. 2026-08-23 sprawl 정리 뒤 1주 안에 같은 모양이 재발했다. |
| 8 | `void-driven-instrument-fanout-without-closure` | MAJOR → MAJOR | CONFIRMED | v2의 실질 결함은 position bias 하나인데 `do_not_rerun_this_occurrence`가 true다. ALFWorld B0는 NOT_RUN, ExpeL B2는 parity manifest만 있다. |
| 9 | `handoff-projection-ceremony-as-unit-of-work` | MAJOR → MINOR | CONFIRMED | 25개 NEXT_SESSION 문서와 10k줄의 무시된 handoff 테스트가 남아 있다. 2026-08-23 이후 NEXT_SESSION은 0개다. |
| 10 | `semantic-weight-has-no-executable-definition` | MAJOR → MINOR | CONTESTED | README의 set-to-set operator는 `swm0w_s2s_operator.py`와 training 코드에 구현돼 있고 2026-08-26 canon이 W를 재정의했다. 남는 것은 S2S lane과 LLM loop의 접점 부재다. |
| 11 | `bridge-theorems-satisfied-by-trivial-interpretation` | MAJOR → MINOR | REFUTED | all-True 해석 만족은 repo가 스스로 선언한 claim boundary다. Lean은 병목이 아니다. |
| 12 | `proof-burst-formalizes-unrun-dnrd5-off-critical-path` | MAJOR → MINOR | CONFIRMED | proof burst 16커밋 중 DNRD-5 전용 1,516줄은 실행된 적 없는 300-block 프로토콜의 형식화다. |
| 13 | `no-bridge-between-llm-instrument-and-atom-v2-permit` | MAJOR → MAJOR | CONFIRMED | experiments 쪽에서 effect-runtime 참조 0, TS 쪽에서 LLM 호출 0이다. |
| 14 | `ts-lean-link-is-caller-asserted-booleans` | MINOR → MINOR | CONFIRMED | TS와 Lean 링크는 호출자가 상수 true로 넣는 Bool 세 개이고 CI에 lake build가 없다. |

## 4. Open gaps

| Gap | Statement | Closed by |
|---|---|---|
| GAP-1 | G0-external 역할을 채울 제2자 미지정 | S-1 (deferral), 제2자 지정 |
| GAP-2 | Python LLM instrument와 Atom v2 Permit 사이 브리지 없음 | S-2 |
| GAP-3 | 랜덤 위치, sham, 별 프로세스 evaluator를 갖춘 G0-local 재실행 미수행 | S-3 |
| GAP-4 | G1 estimand 불일치와 H1 over B2 기전 문단 부재 | S-4 |
| GAP-5 | 유한한 v1 완료 상태 미정의 | S-1 (D-4) |
| GAP-6 | burden cap 미집행 | S-6 |
| GAP-7 | reuse-first comparator B0, B2 미실행 | S-5 |

## 5. Closure plan

목표는 하나다. `outcome → credit → durable canonical revision → changed held-out behavior`가
remove/restore와 sham 대조와 함께 `results/`에 체크인된 run 한 번이다.

| Step | Kind | Run by | Needs | Deliverables | Stop rule |
|---|---|---|---|---|---|
| S-1 | RULE_RELAXATION | 2026-09-08 | user | D-1, D-2, D-4 원문을 `docs/canon/sources/USER_PRIMARY_HSWM_CLOSURE_DECISIONS_<date>.txt`로 결속, `AGENTS.md` 33-34행 한정, G0 profile 상태줄에 DEFERRED_PUBLICATION_GATE, 번들 v2 | D-1 거부 시 S-3 미개시, 거부를 결정으로 기록 |
| S-2 | TECHNICAL_WORK | 2026-09-10 | none | effect-runtime에 stdin envelope, stdout receipt 방식의 local-permit-commit 프로세스, `g1_micro.py`의 `_admit_branch`가 subprocess 호출, receipt digest를 compile_disposition readset에 결속, GPU UUID와 이미지 pin을 protocol 필드로 | LLM payload 없는 effect-runtime 모듈 금지, 2일 내 미폐쇄 시 blocker 기록 후 중단 |
| S-3 | TECHNICAL_WORK | 2026-09-15 | DGX | opaque v3 preregistration(v2 + 랜덤 위치 + sham arm + 별 프로세스 evaluator + S-2 Permit path, n ≥ 30), results, evidence, F1_R8 row | occurrence 1회, VOID는 24시간 내 repair-rerun, 새 instrument family 금지 |
| S-4 | RULE_RELAXATION | 2026-09-08 | user | D-3 원문 결속, option B 선택 시 H1 over B2 기전 문단 1개 | 기전 문단을 못 쓰면 option A가 binding |
| S-5 | TECHNICAL_WORK | 2026-09-22 | DGX | sealed ALFWorld B0와 ExpeL B2의 첫 result 파일, F1_R8 rows | comparator는 secondary ceiling, 실패해도 estimand 재개봉 금지 |
| S-6 | RESOURCE | 2026-09-08 | user | F1_R8 규칙 문단과 검사 명령, 제2자 recruiting 날짜 또는 명시적 미개시 한 줄 | 위반 시 INSTRUMENT_RED 행 기록, 범위 확대 금지 |

순서 제약은 S-1 → S-3, S-2 → S-3, S-4 → S-5, S-3 → S-5, S-1 → S-6이다. S-2는 지금 시작할 수 있다.

### 5.1 G1 estimand

`_research/causal_composition/project.v1.json`의 G1 pass_rule은 fresh-task gain, remove
eliminates, restore recovers, sham과 shuffled credit 실패, compiled traversal mediation을 요구한다.
"B2를 이겨라" 조항은 없다. 반면 viability 문서 115행은 text lesson보다 큰 held-out gain을
요구하고, v2 결과 문서 165행은 "strongest inherited baseline보다 낫다"가 아직 실행 가능한 결정
규칙이 아니라고 적는다. D-3는 이 모순을 닫는다. Option A는 pass_rule을 binding estimand로 두고
B2, B0를 secondary ceiling comparator로 강등한다. Option B는 H1이 B2를 이겨야 하는 기전 문단을
쓴다. 후보 문장은 "cue-indexed compiled projection은 global rule-list interference 없이 정확히 한
disposition만 readset에 넣으므로, 규칙 수가 늘수록 text lesson의 retrieval 오류율보다 낮은
오적용률을 가진다"이다. 이 문단이 prospective hypothesis로 쓰이지 않으면 option A가 답이다.

### 5.2 Proposed G0 split

| Sub-gate | Ceiling | Pass criteria |
|---|---|---|
| G0-local | `MEASUREMENT_READY_SINGLE_OWNER` | 별 프로세스, 별 OS 사용자, 별 키의 evaluator; 사전 커밋된 reveal; episode마다 랜덤 후보 위치와 층화 분석; outcome-independent sham arm; outcome 전 trajectory seal; exact remove/restore; VOID 포함 all-run manifest |
| G0-external | `DEFERRED_PUBLICATION_GATE` | 제2자가 이름과 날짜로 지정; 기존 preflight가 누락 바인딩 0; 제2자의 independent replay 일치 |

## 6. Stop rules and burden cap

| Rule | Statement |
|---|---|
| SR-1 | v3 결과 전까지 G0_NOT_PASSED를 다시 진술하는 profile, authority, boundary, NEXT_SESSION 문서를 만들지 않는다. 상태 변화는 이 번들의 event version과 F1_R8에만 기록한다. |
| SR-2 | 제2자가 지정되기 전까지 OSF, Sigstore, WORM, Temporal serve infra를 확장하지 않는다. |
| SR-3 | VOID는 24시간 내 같은 protocol family로 repair-rerun한다. 새 instrument family를 열지 않는다. |
| SR-4 | G1 판정 전까지 ICE 물리 episode와 새 ontology JSON 버전(graph-and-loop v7 포함)을 만들지 않는다. 예외는 이 번들의 event version뿐이다. |
| SR-5 | 살아 있는 파일을 exact-byte hash로 pin하지 않는다. 무시된 handoff 테스트 10k줄은 별도 정리 커밋으로 제거한다. |

Burden cap 제안: audited commit 이후 100 커밋 중 50% 이상이 core path
(`src/hswm/experiments/g1_micro*`, `src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit*`,
`_research/causal_composition/preregistrations/`, `results/`, `evidence/`, `F1_R8_RESULTS_LOG.md`)를
건드려야 한다. v3 run-by는 2026-09-15다. 위반 시 F1_R8에 `INSTRUMENT_RED` 행을 기록하고 범위를
확대하지 않는다. 검사 명령은 다음이다.

```bash
uv run python scripts/check_hswm_closure_burden_cap.py
```

이 스크립트는 보고만 하며 CI gate가 아니다.

## 7. Decisions requested from the user

아래 네 문장은 `SECONDARY_AI` 제안이다. 사용자가 각 문장을 그대로 확정하거나, 고치거나,
거부한 원문을 `docs/canon/sources/USER_PRIMARY_HSWM_CLOSURE_DECISIONS_<date>.txt`에 보존해야
`USER_PRIMARY`가 된다. 그 전까지 KG의 결정 노드는 `PROPOSED`다.

- **D-1** G0를 G0-local과 G0-external로 나눈다. G0-local은 별도 프로세스, 별도 OS 사용자, 별도
  키의 evaluator, 사전 커밋된 reveal, 후보 위치 랜덤화, outcome-independent sham으로 통과할 수
  있고 claim ceiling은 MEASUREMENT_READY_SINGLE_OWNER다. OSF, Sigstore, WORM, 9역할 등 외부 공증은
  G0-external로 옮기고, 제2자가 이름과 날짜로 지정되기 전까지 미개시한다.
- **D-2** `AGENTS.md`의 "Never weaken a success criterion"은 "outcome을 관측한 뒤 preregistered
  contract를 수정하지 않는다"로 한정한다. outcome을 보기 전의 gate 분할과 요구사항 정리는
  약화가 아니다.
- **D-3** G1의 binding estimand는 `project.v1.json`의 pass_rule이다. ExpeL B2와 ALFWorld B0 비교는
  secondary ceiling comparator로 두고, H1이 B2보다 나아야 하는 기전 문단이 쓰여지기 전까지
  primary estimand에 포함하지 않는다.
- **D-4** v1 완료 상태는 G0-local 아래에서 outcome, credit, 실제 Atom v2 Permit 경로의 durable
  canonical revision, changed held-out behavior가 remove/restore와 sham 대조와 함께 `results/`에
  체크인된 한 번의 run이다. burden cap은 4dcba75 이후 100 커밋 중 50% 이상이 core path를 건드리는
  것이고 v3 run-by는 2026-09-15다. 위반 시 F1_R8에 INSTRUMENT_RED 행을 기록하고 범위를 확대하지
  않는다.

제2자 recruiting은 D-4와 함께 답해야 한다. 날짜를 적거나 "G0-external은 recruit 전까지
미개시"를 한 줄로 적는다.

## 8. Build, validate, and publish

```bash
uv run python scripts/build_hswm_closure_plan_ontology.py --check
uv run --locked --extra dev pytest -q tests/test_hswm_closure_plan.py tests/test_repository_ontology.py
uv run --extra kg python scripts/upsert_hswm_closure_plan.py
uv run --extra kg python scripts/upsert_hswm_closure_plan.py \
  --apply --source-config ~/.config/symposium-ontology/source.yaml
uv run python scripts/check_hswm_closure_burden_cap.py
```

같은 번들 바이트는 표준 그래프 읽기 전용 뷰로도 검사한다.
[`kg_bundle_graph_view.py`](../../src/hswm/infrastructure/kg_bundle_graph_view.py)는 exact
SHA-256으로 결속된 번들을 blank-node-free RDF 1.1 N-Quads로 투영하고, 각 relation을 authority,
scope, status를 보존하는 reified resource와 typed direct edge로 표현하며, PROV-O derivation을
붙인다. [`HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0.ttl`](../../schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0.ttl)은
Claim, Decision, Gap, closure step, USER_PRIMARY decision, burden cap의 구조 불변식을 SHACL 1.0으로
검사하고, 로컬 SPARQL 1.1 ASK가 "모든 claim에 대응 decision이 있다", "user step은 user decision에
의존한다", "아직 RATIFIED가 없다", "모든 gap을 어떤 step이 닫는다"를 확인한다. 이 뷰는
write-back이 금지된 교환 경계이며 live KG 상태나 게시 여부를 말하지 않는다.

```bash
uv run --project _research/graph_standards/runtime --locked --extra graph \
  pytest -q tests/test_kg_bundle_graph_view.py
```

퍼블리셔는 live schema registry의 label과 relation type, 10개 anchor의 정확한 이름을 단언한 뒤
한 트랜잭션으로 생성하고 exact readback한다. KG 게시는 `PROPOSED` 계획의 공개이지 사용자
확정, gate 통과, 과학적 결과가 아니다. 이 번들의 새 버전은 ratification과 v3 receipt에서만
만든다.

## 9. Evidence status

이 문서는 material research result가 아니다. 새 실험 outcome, causal terminal, claim promotion을
만들지 않았으므로 research receipt나 `F1_R8_RESULTS_LOG.md` entry를 추가하지 않는다. G0는
`NOT_PASSED`, G1은 `LOCKED`, 통합 과학 상태는 `INTEGRATED_CLAIM_UNJUDGED`로 유지된다.
