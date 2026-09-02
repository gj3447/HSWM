# HSWM proof-status graph

> **Date:** `2026-09-02`
>
> **Status:** `FORMAL_MODEL_PROVED_1 / LOCAL_ENGINEERING_SUPPORTED_2 / CORE_UNPROVED_3`
>
> **Scientific status:** `UNJUDGED / INTEGRATED_CLAIM_UNJUDGED`
>
> **Machine projection:**
> [`HSWM_GRAPH_AND_LOOP_ENGINEERING_ONTOLOGY.v5.json`](../../ontology/identity/hswm_core/HSWM_GRAPH_AND_LOOP_ENGINEERING_ONTOLOGY.v5.json)

## 1. Answer first

엄격히 말하면 **증명되지 않은 쪽이 더 많다**. 다만 “아무것도 안 됐다”는
뜻은 아니다. 서로 다른 크기의 정리나 테스트 개수를 세면 결론을 쉽게 왜곡할 수
있으므로, 이 기록은 end-to-end HSWM에 필요한 여섯 개의 고정된 횡단 의무를 판정
단위로 사용한다.

| 판정 묶음 | 수 | 뜻 |
|---|---:|---|
| `FORMAL_MODEL_PROVED` | 1 | 선언된 Lean 모델 안에서 전제와 결론이 기계 검증됐다. |
| `LOCAL_ENGINEERING_SUPPORTED` | 2 | 제한된 로컬 경로가 구현·시험됐지만 보편 정리나 과학적 효능 증명은 아니다. |
| `CORE_UNPROVED` | 3 | 보편 런타임 정제, 현실 outcome/credit, 실제 LLM 인과 효능이 아직 확립되지 않았다. |

따라서 이 여섯 묶음을 엄격한 `proof / not proof`로만 이분하면 **형식 증명 1,
형식 증명이 아닌 것 5**다. 그 5개 중 2개는 강한 제한 범위 공학 근거이고 3개는
핵심 미증명이다. 목표 수준 결론은 다음과 같다.

> Lean 내부 안전조건과 조건부 합성은 상당히 닫혔다. 그러나 실제
> TypeScript/Effect 실행, 현실의 진실·인과, revision이 만드는 실제 LLM 개선까지
> 포함한 HSWM 전체는 아직 증명되지 않았다.

이 수는 저장소 전체의 모든 정리나 연구 질문을 백분율로 환산한 값이 아니다. 서로
다른 세부도를 가진 명제를 임의로 잘게 쪼개 “증명이 많아 보이게” 하지 않기 위한
고정된 상태 대시보드다.

## 2. Canonical role, evidence boundary, and conceptual delta

목표 정체성은
[`HSWM Constitution`](../canon/HSWM_CONSTITUTION_2026-08-20.md)에 고정된 그대로다.
HSWM은 token-native LLM-function macro-neural network 하나이며, 살아 있는 harness,
world model, continuous learner는 분리된 하위 시스템이 아니라 같은 evolving
hypergraph의 기능적 얼굴이다. KG와 이 문서는 그 상태를 **관측·감사하는 bounded
projection**일 뿐 HSWM의 cognition, routing, permission 또는 learning이 아니다.

현재 증거는 세 층으로 분리한다.

1. Lean 정리는 선언된 타입, 관계, 전제 아래의 형식 명제를 증명한다.
2. TypeScript/Effect 테스트와 로컬 실행은 특정 구현 경로의 공학 근거를 제공한다.
3. outcome truth, causal credit와 LLM efficacy는 외부 세계에서 독립적으로 운영된
   실험과 판정이 있어야 하는 과학 명제다.

이번 conceptual delta는 새 알고리즘이나 새 HSWM 부품이 아니다. 기존 기록을
`Claim -> Evidence -> Decision -> Gap/Gate`로 분리하고, 모든 현재 판정에 같은 세
축을 적용해 한 층의 성공이 다른 층의 증명으로 승격되는 것을 막는 것이다.

## 3. Standard graph-engineering status model

```text
Claim --HAS_SOURCE--> source-bound EvidenceArtifact
  |
  +--HAS_CONCEPT--> current Decision
  |                    |
  |                    +--CONSTRAINS--> exact Claim scope and ceiling
  |
  +--TARGETS--> open Gap
  +--CONSTRAINS--> HSWM public-claim boundary

Program --TESTS--> prospective Gate
QualificationRun --TESTS--> Claim       # 실행 scope와 한계를 별도 기록
```

현재 KG registry와 호환되도록 등록된 관계 어휘를 유지하고, 각 edge의 `scope`와
`status`가 표준 역할을 구체화한다. 또한 Claim의 `current_decision_uid`, `open_gap_uid`,
Decision의 `assesses_claim_uid`, source의 `standard_graph_role`을 first-class property로
중복 고정해 generic registry relation만으로 의미가 흐려지지 않게 한다. Source node의
hash binding은 판정에 사용한 bytes를 고정할 뿐 그 내용의 진실이나 실행을 스스로
증명하지 않는다.

이번 기록 시점에 실제 재실행한 Lean build, targeted TypeScript test/typecheck와 KG
reproducibility check는 각각 `QR-1..3` local `QualificationRun` record로 분리했다. 그러나
raw command log를 영구 보존하지 않았으므로 status는 모두
`SELF_ATTESTED_LOCAL_REPORTED_PASS / NOT_INDEPENDENTLY_QUALIFIED`다. Command, tool version,
input source UIDs, 보고된 결과와 한계는 재현용 metadata이지 독립 qualification receipt나
과학 실험, scientific terminal이 아니다. `QR-1`과 `QR-2`의 source list는 인용된 direct source와 tool/package config를
결속하며 전체 transitive dependency closure를 attest하지 않는다. `QR-3`는 builder가
선언한 v5 source binding 전체를 결정적으로 재검사한다.

각 Decision은 다음 세 축을 반드시 따로 가진다.

| 축 | 허용 상태 | 질문 |
|---|---|---|
| `implementation_status` | `NOT_STARTED`, `PARTIAL`, `IMPLEMENTED`, `QUALIFIED` | 필요한 표면이 어느 정도 만들어졌는가? |
| `evidence_disposition` | `NOT_EVALUATED`, `SUPPORTED_IN_SCOPE`, `RED`, `UNDERDETERMINED` | 선언된 범위의 근거는 무엇을 판정하는가? |
| `claim_ceiling` | 명시적 scope ceiling | 이 근거로 공개적으로 어디까지 말할 수 있는가? |

`SUPPORTED_IN_SCOPE`는 scope 밖으로 전파되지 않는다. `RED`는 정확히 시험한 mechanism
family만 퇴역·우회시키며 HSWM 목표를 축소하지 않는다. `NOT_EVALUATED`는 성공도 실패도
아니다. 그래프의 Claim과 Decision을 분리했으므로 다음 evidence snapshot은 과거 판정을
덮어쓰지 않고 새 version으로 이어갈 수 있다.

v5 JSON은 저장소 schema registry에 맞춘 bounded property-graph projection이지 RDF
표준 적합성 인증서가 아니다. 이후 별도 운영 경계에서 official N-Quads/RDFC suite,
HSWM-used SHACL profile, JSON-LD FromRDF profile, narrowed read-only SPARQL profile이
exact source/package/runtime/receipt로 qualification되었고 constrained PROV-O view도
구현됐다. 그 최신 범위는
[`HSWM full-stack graph engineering boundary`](../operations/HSWM_FULL_STACK_GRAPH_ENGINEERING_2026-09-02.md)가
관리한다. 이 추가 공학 근거는 이 문서의 여섯 end-to-end proof obligation 판정 수를
바꾸지 않으며 cognition, causal learning, efficacy 또는 universal standards
conformance 증명으로 승격되지 않는다.

## 4. Six fixed proof obligations

| ID | Claim | implementation_status | evidence_disposition | claim_ceiling | Current decision | Next gate |
|---|---|---|---|---|---|---|
| `PS-1` | Cited Lean model safety and conditional composition | `QUALIFIED` | `SUPPORTED_IN_SCOPE` | `FORMAL_MODEL_ONLY` | 인용·결속된 모델과 전제 안에서 증명됨 | Lean build를 보존하고 runtime/과학 bridge는 별도 의무로 유지 |
| `PS-2` | Tested TS-to-Lean wire and persisted local decision | `IMPLEMENTED` | `SUPPORTED_IN_SCOPE` | `LOCAL_RUNTIME_ONLY` | 고정·적대 벡터와 v2 local gateway 경로의 공학 근거 있음 | executable identity 고정, 실제 recovered receipt의 full-certificate audit, 독립 cross-language qualification |
| `PS-3` | Every in-scope TS/Effect execution refines Lean | `PARTIAL` | `UNDERDETERMINED` | `NO_UNIVERSAL_REFINEMENT_CLAIM` | 미증명; 현재 profile에는 명시적 blocker가 있음 | 검증 가능한 source semantics, extraction 또는 bounded simulation theorem |
| `PS-4` | Real local key/time/nonce Permit and atomic recovery occurrence | `IMPLEMENTED` | `SUPPORTED_IN_SCOPE` | `LOCAL_RUNTIME_ONLY` | v1 local Permit-commit의 Node/POSIX process-crash 범위에서 지지됨; v2 crash qualification은 아님 | v2 SIGKILL checkpoint, durable key custody, trusted time, global nonce, power-loss, anti-rollback, deployment storage qualification |
| `PS-5` | Externally true outcome and independent causal credit | `PARTIAL` | `NOT_EVALUATED` | `CAUSAL_CLAIM_PENDING` | 현실 premise를 만족한 occurrence가 없어 `NOT_ESTABLISHED` | sealed external outcome, separate evaluator/judge, controls, custody와 independent replay |
| `PS-6` | Exact revision causes real-LLM improvement | `PARTIAL` | `NOT_EVALUATED` | `INTEGRATED_CLAIM_UNJUDGED` | confirmatory G0/G1 occurrence가 없어 `NOT_ESTABLISHED` | G0를 먼저 닫고 fresh probe, remove/restore, sham/delayed-credit와 재현성을 갖춘 G1 또는 frozen DNRD-5 실행 |

### PS-1 — what Lean really proves

대표 source-bound 형식 증거는
[`HSWMCanonicalLearning.lean`](../../formal/HSWMCanonicalLearning.lean),
[`HSWMVerifiedAdmissionKernel.lean`](../../formal/HSWMVerifiedAdmissionKernel.lean),
[`HSWMEndToEndRuntimeRefinement.lean`](../../formal/HSWMEndToEndRuntimeRefinement.lean),
[`HSWMCausalEfficacyBridge.lean`](../../formal/HSWMCausalEfficacyBridge.lean)다.
이들은 outcome-bound learning의 필요조건, Permit/admission의 구조와 순수 kernel,
조건부 end-to-end evidence 합성, typed causal-occurrence bridge를 기계 검증한다.

여기서 “조건부”는 약점 은폐가 아니다. 외부 truth, verifier soundness, storage
occurrence, causal identification과 provider semantics처럼 Lean 구조만으로 만들 수 없는
사실을 premise로 남겨 놓은 정확한 claim boundary다. 이 premise가 현실에서 채워졌다는
결론은 PS-1에서 나오지 않는다.

### PS-2 and PS-4 — what actually runs locally

[`TypeScript/Effect–Lean evidence status`](HSWM_TYPESCRIPT_EFFECT_LEAN_AND_CAUSAL_EVIDENCE_STATUS_2026-08-31.md)는
strict wire/adversarial vectors, configured Lean CLI의 exact response, v2 immutable record와
recovery revalidation을 기록한다. 별도의
[`local Permit commit`](../../src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit.ts)은
ephemeral Ed25519 key, random nonce, caller-relative clock, signed envelope, no-replace hard-link,
`fsync`, concurrent winner와 independent-process `SIGKILL` recovery 경로를 갖는다.

이는 실제로 실행되는 제한 경로이므로 단순 설계 문서보다 강하다. 그러나 v2 gateway의
persisted Lean-decision test와 v1 local Permit-commit의 independent-process `SIGKILL` test는
서로 다른 namespace와 qualification이다. 현재 v2-specific crash checkpoint는 없다.
또한 unpinned CLI, process-local capability, ephemeral key, caller-relative time, local
namespace와 특정 POSIX failure model을 벗어난 보편 증명은 아니다. 특히 power loss,
device flush, global anti-rollback과 distributed linearizability를 주장하지 않는다.

### PS-3, PS-5, and PS-6 — what remains unproved

[`end-to-end refinement boundary`](HSWM_END_TO_END_RUNTIME_REFINEMENT_LEAN_BOUNDARY_2026-08-31.md)는
모든 현실 premise가 주어질 때 무엇이 합성되는지를 증명하지만 TypeScript source나 Node
semantics를 Lean이 실행하지 않는다. 따라서 모든 TS/Effect execution의 보편 정제는
미증명이다.

[`causal-efficacy occurrence bridge`](HSWM_CAUSAL_EFFICACY_OCCURRENCE_LEAN_BRIDGE_2026-09-01.md)는
300 block, 2,700 typed call ID, four-arm chronology와 exact-sign decision의 구조를
조건부로 묶지만 실제 300-block occurrence를 만들지 않았다. 현재 exploratory evidence는
baseline saturation 또는 position/evaluator confounding을 남겼다. 기록된 판정은
`G0_NOT_PASSED / G1_NOT_EVALUATED`; 전체 과학 상태는 `INTEGRATED_CLAIM_UNJUDGED`다.

## 5. Negative results and route discipline

현재 source profile이 positive refinement witness를 만들 수 없다는 obstruction이나 특정
mechanism의 `RED`는 실패 은폐가 아니라 유효한 결과다. 다만 그 결과는 그 exact route의
다음 사용을 막거나 재설계를 요구할 뿐 다음을 뜻하지 않는다.

- HSWM 최종 정체성이 반증됐다는 뜻이 아니다.
- 미통과 G0를 downstream scale이나 더 큰 모델로 구제할 수 있다는 뜻도 아니다.
- 조건부 Lean 정리를 현실 효능으로 이름 바꿀 수 있다는 뜻도 아니다.
- 테스트 수를 progress 또는 cognition으로 환산할 수 있다는 뜻도 아니다.

이 원칙은
[`adaptive research strategy`](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)의
target-preserving route replacement와 failure lineage를 그대로 따른다.

## 6. Ordered closure path

1. **PS-3를 bounded theorem으로 자른다.** 먼저 증명할 TypeScript/Effect surface와
   observable trace를 고정하고 verified semantics, proof-producing extraction 또는
   simulation 중 하나를 선택한다. “모든 임의의 TS” 같은 무제한 주장은 피한다.
2. **한 실제 transition을 끝까지 연결한다.** 실제 v2 recovered receipt에서 full execution
   certificate를 만들고 pinned Lean checker와 독립 cross-language audit를 통과시킨다.
3. **PS-4의 ceiling을 올릴 배포 근거를 만든다.** key custody, trusted time, globally atomic
   nonce, power-loss/anti-rollback과 대상 storage semantics를 각각 qualification한다.
4. **PS-5를 외부 occurrence로 평가한다.** G0 전제, sealed truth source, evaluator/judge
   independence, sham/delayed/shuffled credit와 complete custody를 먼저 닫는다.
5. **그 뒤 PS-6를 평가한다.** fresh held-out real-LLM probes에서 gain, remove-loss,
   restore-return, uncertainty와 independent reproduction을 함께 요구한다.

상류 실패는 하류 규모로 구제하지 않는다. 각 단계가 닫힐 때 새 source-bound Decision과
QualificationRun을 후속 KG version에 추가하며, 기존 v5 bytes와 실패 lineage는 보존한다.

## 7. Qualification runs and reproducibility

| Run | Scope | Result | Exact boundary |
|---|---|---|---|
| `QR-1` | Lean 4.32.1 project build and four cited module compiles | `SELF_ATTESTED_REPORTED_PASS`; `lake build` 35 jobs | raw log absent; formal source/build status only, foreign semantics and real-world premises excluded |
| `QR-2` | Effect-runtime typecheck plus v2 gateway, v1 Permit and v1 SIGKILL tests | `SELF_ATTESTED_REPORTED_PASS`; 3 files, 12 tests | raw log absent; v2 persisted-decision test and v1 crash test remain distinct, with no v2 crash/power-loss/universal claim |
| `QR-3` | deterministic v5, ontology shape, portable Markdown and whitespace | `SELF_ATTESTED_REPORTED_PASS` | raw log absent; projection reproducibility status only, no HSWM or scientific efficacy result |

기계 투영은 기존 graph-and-loop ontology를 덮어쓰지 않고 v5로 이어진다. builder는 모든
local source path와 SHA-256, 6 Claim, 6 current Decision, 3 QualificationRun, open Gap/Gate,
predecessor v4를 결정적으로 묶는다.

```bash
uv run python scripts/build_hswm_graph_and_loop_engineering_ontology.py --check
uv run pytest -q tests/test_hswm_graph_and_loop_engineering_ontology.py
(
  cd formal
  lake build
)
(
  cd src/hswm/effect-runtime
  npm run check
  npm test -- canonical-atom-v2-verified-admission-gateway-v2.test.ts \
    canonical-atom-v2-local-permit-commit.test.ts \
    canonical-atom-v2-local-permit-commit-process-crash.test.ts
)
uv run python scripts/compile_portable_markdown_math.py \
  README.md INDEX.md docs/canon docs/research ontology
git diff --check
```

이 정리는 새 material research result가 아니다. 새 실험 outcome, causal terminal 또는
claim promotion을 만들지 않았으므로 content-addressed research receipt나
`F1_R8_RESULTS_LOG.md` entry를 추가하지 않는다.
