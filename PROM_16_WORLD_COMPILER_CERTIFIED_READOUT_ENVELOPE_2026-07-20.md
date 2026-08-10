<!-- PROVENANCE
Status: SECONDARY_AI_PROPOSAL / USER_RATIFICATION_REQUIRED
Research lane: ENGINEERING
Cycle: PROM 16, 2026-07-20
Question: How should HSWM become an evidence-preserving World Compiler with a certified field/readout safety boundary?
Authority order used: live KG canon -> user-primary HSWM utterance -> local HSWM design/research canon -> current code/results -> primary external specifications and papers.
Live KG: read-only, connector healthy, 2026-07-20 session. No KG write.
Methods: symposium-research + engine-design + harness category audit. Naesengmoon was NOT invoked; adversarial verdict remains UNVALIDATED.
Parallel axes: current boundary/IR; certified readout envelope; primary prior art/standards; parent synthesis.
Write scope: this report and the companion module decision JSON only. Existing code, results, canon, and KG were not modified.
-->

# PROM 16 — HSWM Evidence-Preserving World Compiler + Certified Readout Envelope

> **Status:** 기술 설계 제안. 사용자가 이번 대화에서 방향을 요청했지만, 아래 세부 구조와 명칭은 아직 `SECONDARY_AI`이며 사용자 ratification 전 정전이 아니다.
>
> **Companion decision:** `HSWM_WORLD_COMPILER_MODULE_DECISION_2026-07-20.json`

## 0. 최상위 판정

HSWM의 재정의는 다음 한 문장이어야 한다.

> **HSWM은 source evidence를 잃지 않는 결정론적 World Compiler가 immutable field snapshot을 만들고, 모든 retrieval·selection·optional traversal·temporal readout을 동일 snapshot에서 수행하며, 인증되지 않거나 위험한 처치는 정확한 이전 readout으로 후퇴시키는 substrate다.**

이 재정의는 기존 사용자 정전을 바꾸지 않는다.

- HSWM은 계속 **입체운행구름(OM #8)의 군단장**이다.
- 사용자-primary `binding-first-then-weight`를 구현 경계로 구체화한다.
- 재배맨·오캄·나생문·롱기누스는 HSWM의 소유자가 아니라 조건부 외부 operator/consumer다.
- HSWM을 비행기맨 계보의 `Harness`라고 재분류하지 않는다.
- reasoner나 truth engine을 자칭하지 않는다.

권장 구현명은 세 층이다.

```text
HSWM
├── Evidence-Preserving World Compiler (EPWC)   source/observation -> immutable world
├── Field Snapshot Kernel (FSK)                 immutable snapshot -> score components
└── Certified Readout Envelope (CRE)            certify/fallback/receipt/update boundary
```

`EPWC`와 `FSK`는 우선 순수 모듈이다. `CRE`도 에이전트 Harness가 아니라 **L_RT 안에 들어갈 수 있는 domain safety component**다. 세 층을 합친 runtime engine은 실제 다중 소비자·incremental ingest·concurrent writer·durable recovery가 생길 때만 승격한다.

## 1. 연구 계약과 authority

### 1.1 질문

현재 분리된 네 경로를 어떻게 한 증거 보존 substrate로 합칠 것인가?

1. closed-pool additive-j 성능 경로
2. corpus world-builder 경로
3. traversal certification 경로
4. supersession/stale-poisoning 경로

### 1.2 사용자/KG hard core

이번 설계가 보존해야 할 정전은 다음이다.

- KG `verdict-hswm-belongs-to-omc-8-legion-2026-07-19` (`UserPrimaryCanon`): HSWM은 입체운행구름 #8 군단장이고 engineboy sibling이다.
- KG `verdict-jaebaeman-v3-longinus-based-substrate-2026-07-19` (`UserPrimaryCanon`): **binding-first-then-weight**, 가중치는 바인딩된 관계에만 올라간다.
- KG `principle-binding-first-then-weight-grounded-2026-07-19`: source binding이 weight보다 선행한다.
- KG `oq-jaebaeman-v3-weightfield-common-substrate-2026-07-19`: 場이 전 군단의 공용 좌표계인지는 여전히 `OPEN`이다.
- 사용자 원 발화: 긴 문서·논리 단위에서 cosine을 넘어서는 `웨이트로 돌아다님`, 그리고 최종 생태계 흡수 요구. `내가 주는 말.txt:1-6`.

따라서 이 보고서는 HSWM을 다른 사도에게 넘기지 않고, **#8 substrate 내부의 컴파일·스냅샷·안전 경계**만 명세한다.

### 1.3 현재 정본이 이미 인정한 결손

- Map/Mapper 분리 없음: `THEORY/재배맨/HSWM_STANDARD.md:4,191`.
- binding-first provenance 없음: 같은 문서 `:84-86,151-153`.
- retrieve/plan은 readout, supersede/bind는 write라는 재타이핑: `:103-107`.
- 동시성·영속·복구 미정: `:194-200`.
- supersede fold는 가환이지만 idempotent가 아님: `PROM_WOLFRAM_IMPORT_2026-07-19.md:48-68`.

이번 재정의는 새 철학의 수입이 아니라 이 미구현 축을 하나의 좁은 허리로 닫는 작업이다.

## 2. PROM 16 축 판정

| 축 | 질문 | 판정 |
|---|---|---|
| A1 Identity | HSWM은 무엇을 소유하는가 | #8 substrate + world/field artifact. 다른 commander의 판단 자체는 소유하지 않음 |
| A2 Category | Harness인가 engine인가 module인가 | 현재 `NON_HARNESS`, `MODULE`; CRE는 domain certification envelope |
| A3 Current paths | 하나의 시스템인가 | 아직 아님. additive-j·world·traversal·T4가 분리됨 |
| A4 Narrow waist | 가장 작은 공용 계약은 | frozen source+observation -> immutable `WorldArtifactV1` |
| B1 Evidence | 최소 provenance는 | source digest + exact quote/span + observation/build lineage |
| B2 Identity | stable ID는 | content/policy-addressed ID; dense array index와 분리 |
| B3 Fact shape | paragraph인가 triple인가 | source-specific role-aware n-ary assertion + 별도 EvidenceUnit |
| B4 Time | stale/supersession 시간은 | valid/effective time와 recorded/transaction time 분리 |
| C1 Field | 하나의 場이란 | 한 객체에 저장됨이 아니라 같은 immutable snapshot의 component vector |
| C2 Readouts | plan/retrieve/traverse 관계 | retrieve와 selection distribution은 같은 score view; 실제 agent planning은 미증명 |
| C3 Certification | 무엇을 인증하는가 | artifact+policy+metric+domain에 결박된 deploy/refuse 결정 |
| C4 Correction | 위험 시 어떻게 돌아가는가 | traversal -> current static -> temporal cosine -> hard refuse |
| D1 Builder | HippoRAG/ontology를 어떻게 쓰나 | extractor/linker/ontology를 독립 관측 arm으로 분리; full ontology는 core 금지 |
| D2 Supersession | b는 어디에 저장되나 | append-only decision ledger에서 unique-event fold로 파생 |
| D3 Experiment | 무엇이 다음 falsifier인가 | arm(e) 정정 후 lossless builder factorial + full-corpus 재인증 |
| D4 Promotion | 언제 engine인가 | 실제 소비자 2+, incremental/concurrent/durable 요구가 관측될 때 |

## 3. 현재 구현의 실제 단절

```text
ab_p5_full.Field
  closed per-query paragraph pool
  cosine + learned additive residual
  ───────────────────────────────────┐
                                     │  아직 미통합
world_builder -> Hypergraph -> WeightField -> readouts/traversal/T4
  corpus paragraphs    cosine + log(b)
```

### 3.1 측정된 additive-j 경로

`GIT/HSWM/ab_p5_full.py:454-550`의 `Field`가 bge-m3 paragraph cosine에 PCA-space bilinear residual의 ReLU를 더한다. 이 경로가 stored F1 lift를 만들었다.

그러나:

- 질문별 10–20 paragraph pool의 reranking이다.
- world-builder·Hypergraph·supersession과 연결되지 않았다.
- run당 100 offline LLM judgment를 사용한다.
- `substrate_bench.py`의 PPR은 실제 HippoRAG가 아니라 per-query token graph다.

### 3.2 corpus world와 readout 경로

- `world_builder.py:124-166`: paragraph 하나가 unordered entity-set hyperedge 하나다.
- `hypergraph.py:23-52`: predicate·argument role·source span·valid time이 없다.
- `traversal_cert.py:52-56`: `WeightField._pooled`를 paragraph embedding으로 private overwrite한다.
- `weight_field.py:101-118`: core에는 별도 additive `j`가 없다.
- `readouts.py:78-88`: supersession은 stable decision이 아니라 positional edge ID의 in-place `*= decay`다.
- `stale_poisoning.py:117-124`: T4는 실제 supersede path를 호출하지 않고 b vector를 직접 대입한다.
- `traversal_cert.py:245-258`: embedding cache key가 entity labels와 unit 수만 보며 source/query text·model revision·prompt/config를 보지 않는다.

### 3.3 측정/배포 표면의 부채

- `pyproject.toml:18-33`은 최근 world/traversal/stale modules를 package하지 않는다.
- `substrate_bench.py:537`은 현재 return되지 않는 key를 읽으므로 stored benchmark를 HEAD에서 그대로 재실행할 수 없다.
- pooled n=300에는 MuSiQue query ID 12개가 겹친다. grouped paired 통계로 다시 계산해야 한다.
- T4 arm (e), T4 trip rate, actual write receipt가 없다.
- 2Wiki T5에는 25 hash embedding fallback이 있는데 결과문서의 0 fallback 서술과 충돌한다.

이 부채를 닫지 않고 builder만 무겁게 만들면 더 정교한 입력이 더 불명확한 시스템으로 들어간다.

## 4. 재정의된 hard core

### 4.1 `binding-first-then-weight`의 실행 의미

```text
Source bytes
  -> exact evidence selectors
  -> mentions and source-specific assertions
  -> entity hypotheses and typed bindings
  -> field targets/projections
  -> score components
  -> certified readouts
```

가중치는 source evidence로 역추적되지 않는 target에 올라갈 수 없다. extractor confidence는 truth가 아니며, entity merge는 source assertion을 지우지 않는다.

### 4.2 “one shared field”의 새 정의

폐기할 정의:

> `b`가 `WeightField` 객체 내부에 물리적으로 있으므로 하나의 場이다.

채택할 정의:

> **동일한 `FieldSnapshot` ID, candidate-set digest, scorer/policy hash에서 계산된 score-component vector를 여러 readout이 소비한다.**

이 정의에서는 graded metadata가 field 외부에 저장되어도 점수 대수는 동일할 수 있음을 인정한다. HSWM의 방어점은 저장 위치가 아니라 snapshot consistency·evidence chain·atomic decision fanout·fallback이다.

### 4.3 score layer를 세 층으로 분리

```text
S_sem(e,q)  = cosine(e,q) + lambda_j * ReLU(j(e,q))
S_cur(e,q)  = S_sem(e,q)  + lambda_b * log(b(e, ledger_cut))
S_trav(e,q) = S_cur(e,q)  + mu * R(e,q),  R >= 0
```

정확한 floor 언어:

- `S_sem >= cosine`은 per-edge 대수적 사실이다.
- `b < 1`인 stale target은 `S_cur < cosine`일 수 있고 그것이 의도다.
- `S_trav >= S_cur` per-edge라도 ranking/nDCG floor는 아니다.
- 양수 잔여를 더해도 개별 query nDCG가 악화될 수 있다. 현 receipt가 약 `-0.22` 사례를 기록한다.
- 그러므로 metric 안전은 대수식이 아니라 held-out deployment gate와 exact fallback으로 보장한다.

### 4.4 selection은 planning이 아니다

현재 `plan()`은 `softmax(W)`이고 테스트는 retrieve top-1과 argmax가 같음을 보일 뿐이다. 실제 downstream task·cost·risk를 최적화하는 agent plan은 검증하지 않았다.

권장 core 명칭:

- `selection_distribution()` — 정확한 구현명
- `dispatch()` — argmax/sample consumer
- `plan()` — compatibility alias, downstream 계획 효능 전까지 과대해석 금지

## 5. EPWC — module contract

### 5.1 판정

`MODULE / DEFER_ENGINE`.

```text
compile_world(
    sources: SourceBundleV1,
    observations: ObservationBundleV1,
    policy: CompilePolicyV1,
) -> WorldArtifactV1 | CompileRejectionV1
```

컴파일러 안에는 filesystem·network·clock·randomness·model call·credential이 없다. 외부 extractor/linker/embedder가 반환한 값을 raw output hash와 함께 먼저 기록하고, compiler는 그 frozen observation만 받는다.

### 5.2 Compiler 소유

- source/evidence/mention/entity/assertion topology
- stable ID와 dense-index projection
- schema·span·hash validation
- lossless dedup와 quarantine
- deterministic canonical serialization/build ID
- paragraph/binary/n-ary projection
- 기술통계와 BuildReceipt

### 5.3 외부 policy/port

- splitter·extractor·prompt·model·decoding
- entity linker와 merge threshold
- ontology snapshot과 mapping threshold
- contradiction/cardinality policy
- supersession 승인과 dose
- field parameter·readout·certification
- DB·scheduler·retry·auth·deployment

### 5.4 Non-goals v1

- live BIND mutation: topology 변경은 v1에서 recompile만 허용
- automatic truth 또는 automatic supersede
- full OWL inference
- query-time LLM reasoning
- durable runtime engine
- multi-field weave 자체: leaf artifact가 future weave에 필요한 namespace/reference만 제공

## 6. World IR v1

### 6.1 최소 record

| Record | 필수 내용 | 핵심 이유 |
|---|---|---|
| `SourceSnapshotV1` | source ID, locator, media type, raw digest, recorded captured-at | 원문 정체성 |
| `EvidenceUnitV1` | source ID, unit kind, ordinal, exact selector, text digest | paragraph/sentence/span 증거 |
| `ObservationV1` | producer, version/model, prompt/config hash, input/output hash, raw output ref | stochastic 단계 동결 |
| `MentionV1` | evidence unit, exact selector, surface, normalized surface, observation ID | alias 전 원형 보존 |
| `EntityV1` | local stable ID, mention IDs, label, aliases, external mapping evidence | hard merge의 손실 방지 |
| `ArgumentV1` | role, ordinal, entity/literal ref, evidence IDs | 방향·역할·순서 보존 |
| `AssertionV1` | local predicate, arguments, polarity, modality, qualifiers, valid time, provenance | paragraph와 fact 분리 |
| `ClaimKeyV1` | assertion grouping key와 policy hash | source assertion을 지우지 않는 비교 |
| `FieldTargetV1` | target kind, embedding observation, incidence, evidence IDs | IR과 retrieval view 분리 |
| `BuildManifestV1` | schema/compiler/policy/source/observation/projection hashes, quarantine, stats | 재현·감사 |
| `EvaluationSuiteV1` | query, answer, gold/support labels | compiler leakage 차단을 위한 별도 객체 |

### 6.2 Evidence selector

position만 저장하면 source가 조금만 변해도 깨진다. 최소한 다음을 함께 가진다.

- raw source content SHA-256
- exact quote
- prefix/suffix context
- start/end position
- normalization policy hash

이는 [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)의 `TextQuoteSelector`와 `TextPositionSelector`를 core-native 형태로 취한다. 코드 source에는 가능하면 Longinus의 symbol/file/line/hash binding을 추가하고, 일반 prose에는 코드 전용 7-layer를 억지로 강제하지 않는다.

### 6.3 Assertion과 evidence를 분리

```text
EvidenceUnit 1 ──contains──> Assertion N
Assertion N   ──supported-by──> EvidenceUnit 1..N
Assertion     ──projects-to──> FieldTarget
```

retrieval target은 paragraph일 수 있지만 supersession target은 atomic assertion이어야 한다. claim score를 evidence unit으로 투영하는 방식은 policy다. 그래야 한 사실의 supersession이 문단의 다른 사실까지 가라앉히지 않는다.

### 6.4 n-ary role 보존

unordered members set만으로는 다음을 구분하지 못한다.

```text
Alice sold Book to Bob for $10
Bob sold Book to Alice for $10
```

`AssertionV1`은 relation instance와 `seller/buyer/object/amount` 역할을 보존한다. 외부 export는 [W3C n-ary relation pattern](https://www.w3.org/TR/swbp-n-aryRelations/)을 참고하되, core role schema는 HSWM이 versioning한다.

### 6.5 provenance와 reproducibility

- native IR이 source of truth다.
- [W3C PROV-DM/O](https://www.w3.org/TR/prov-o/)의 Entity/Activity/Agent, used/generated/derived/revision/invalidation은 export profile이다.
- JSON artifact는 명시적 Unicode/number policy 후 [RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785.html)로 canonicalize하고 SHA-256을 낸다.
- BuildReceipt는 [SLSA build provenance](https://slsa.dev/spec/v1.2/build-provenance)의 subject digest, external parameters, resolved dependencies, builder/run/byproducts 구조를 얇게 차용한다.
- [OpenLineage](https://openlineage.io/docs/spec/facets/)는 operation-level export adapter일 뿐 claim-span provenance를 대체하지 않는다.

### 6.6 IR 불변식

1. 모든 accepted evidence selector는 bound source digest에서 exact quote를 복원한다.
2. 모든 mention/assertion/field target은 최소 하나의 evidence ID로 역추적된다.
3. source order가 바뀌어도 stable IDs와 build ID가 동일하다.
4. dense array ID는 artifact 내부 projection일 뿐 durable identity가 아니다.
5. entity resolution은 raw mention·source assertion을 삭제하지 않는다.
6. role·ordinal·polarity·modality·qualifier·time은 unordered incidence로 환원되어 사라지지 않는다.
7. 동일 source+observation+policy는 bit-identical artifact를 낸다.
8. question/answer/gold/support flag 변경은 WorldArtifact build ID를 바꾸지 않는다.
9. missing observation·hash mismatch·dangling ref·nonfinite vector는 typed rejection이다.
10. external QID/PID가 없어도 local entity/assertion은 완전해야 한다.

## 7. Supersession Decision Ledger

### 7.1 b는 mutable truth가 아니라 derived view

```text
SupersessionDecisionV1
  event_id
  target_assertion_id
  replacement_assertion_id?
  decay
  effective_at          # valid-time side
  recorded_at           # transaction-time side
  actor_ref
  justification_evidence_ids[]
  expected_revision
  epoch
```

```text
b(assertion, ledger_cut) = product(decay of UNIQUE accepted events)
```

- 동일 event ID 재생은 `NOOP_DUPLICATE`.
- 동일 ID·다른 payload는 conflict.
- event order와 무관한 canonical fold를 사용한다.
- target은 stable assertion ID다.
- rollback은 history 삭제나 역곱이 아니라 compensating event다.
- current/as-of/audit view는 같은 ledger cut에서 재현된다.

### 7.2 자동 supersede 금지

동일 `(subject, predicate)`의 다른 object는 자동 모순이 아니다. multi-valued relation, 다른 시점·장소·modality일 수 있다. Compiler/ontology layer는 `SupersessionCandidate`와 증거만 낸다. 실제 decision은 별도 authority가 승인한다.

### 7.3 atomic snapshot publish는 미래 runtime 책임

v1 compiler는 ledger snapshot을 입력으로 받아 새 immutable `FieldSnapshot`을 만든다. 실제 concurrent write service가 필요해질 때 다음 요구가 engine 승격 근거가 된다.

- expected-revision CAS
- append + snapshot publish atomicity
- old readers의 snapshot pinning
- crash recovery와 dedup
- concurrent current/as-of consistency

## 8. Field Snapshot Kernel

```text
WorldSnapshotV1
  world_id
  source_manifest_sha
  evidence_manifest_sha
  topology_sha
  embedding_manifest_sha

FieldSnapshotV1
  world_id
  ledger_cut
  kernel_sha
  parameter_sha
  policy_sha
  field_vector_digest
  certified_policy_ids[]
```

모든 readout은 한 request 동안 같은 `FieldSnapshotV1`과 candidate-set digest를 pin한다.

### 8.1 componentized result

각 target은 최소 다음을 반환 가능해야 한다.

```text
target stable ID
cosine alpha
lambda_j * j_positive
lambda_b * log b
traversal residual, if applied
final score
evidence IDs
decision event IDs
```

score를 한 숫자로만 materialize하면 감사와 arm ablation이 다시 불가능해진다.

### 8.2 legacy seam

첫 착지에서 현재 API를 깨지 않는다.

```text
compile_legacy_rows(rows)
  ├── compile_corpus(rows without evaluation labels) -> WorldArtifactV1
  ├── compile_eval_suite(question/answer/support)     -> EvaluationSuiteV1
  └── to_legacy_built_world(artifact, suite, projection="paragraph-v1")
        -> BuiltWorld + StableIdMap
```

golden parity 범위:

- entity order와 stable-ID map
- paragraph first-seen dedup
- members/unit texts/node+unit embeddings
- query→gold mapping과 stats
- field values, retrieve order, selection probabilities
- `mu=0` traversal output

`WeightField`는 explicit `target_emb`를 받아야 하며 `_pooled` monkeypatch를 금지한다.

## 9. CRE — Certified Readout Envelope

### 9.1 category guard

`CRE`는 비행기맨의 Harness family instance가 아니다. LLM-tool-session orchestration을 소유하지 않으며, HSWM domain component의 admission·verification·fallback만 소유한다.

Inform/Constrain/Verify/Correct는 CRE 내부 누락을 보는 진단 렌즈로만 쓴다.

| 축 | 현재 | 목표 |
|---|---:|---|
| Inform | 1/3 | 모든 결과에 evidence/snapshot/cert scope/component/known limit 동봉 |
| Constrain | 2/3 | typed request, immutable snapshot, certified policy만, raw knob 금지 |
| Verify | 2/3 | null/negative oracle 유지 + arm(e), cert binding, replay/transaction 검증 |
| Correct | 1/3 | fallback 외 quarantine, compensation, rollback, drift recert 추가 |

### 9.2 fallback ladder

```text
certified traversal S_trav
    ↓ trip/cert mismatch
current static field S_cur
    ↓ j certificate mismatch
cosine + SAME temporal policy
    ↓ snapshot/ledger/evidence integrity failure
hard refusal
```

raw cosine으로 바로 돌아가면 superseded fact가 부활하므로 안전 fallback이 아니다.

### 9.3 certification scope

`CertificationReceiptV1`은 다음에 정확히 결박한다.

- WorldArtifact/world family
- source/compiler/extractor/linker/embedder revision
- field kernel/parameter/policy
- candidate policy와 metric
- calibration/test split hashes와 unique grouping key
- allowed config (`lambda_j`, `mu`, `gamma`, `K`)
- validity/expiration/drift triggers

새 builder·embedding·policy·ledger semantics는 기존 certificate를 자동 만료시킨다.

### 9.4 raw knobs 차단

현 production-facing `readouts.traverse(..., mu=...)`는 certification을 우회한다. 권장 API:

```text
read(snapshot, query, CertifiedPolicyV1) -> ReadoutResultV1
research_probe(snapshot, query, UnsafeProbePolicyV1) -> ProbeResultV1
```

production path는 raw `mu/gamma/K`를 받지 않는다. 연구 probe는 결과에 `UNSAFE_PROBE / NOT_DEPLOYABLE`을 강제한다.

## 10. Gate hierarchy

### 10.1 Compile/field admission

| Gate | 조건 | 실패 |
|---|---|---|
| G0 SourceBinding | source SHA + exact quote/span 100%, evaluation leakage 0 | `COMPILE_REJECT` |
| G1 SnapshotIntegrity | schema/topology/embedding/ledger/kernel hash 정합, stable ID resolve, nonfinite 0 | `HARD_REFUSE` |
| G2 KernelInvariant | 동일 입력 bit reproduction, stable ties, off-support score 금지 | `BROKEN` |
| G3 LayerContract | `S_sem>=cos`, temporal 하강은 target만, `S_trav>=S_cur`; negative oracle 포함 | `BROKEN` |

### 10.2 Empirical certification

| Gate | 조건 | 실패 |
|---|---|---|
| G4 ScopeBinding | certificate와 artifact/model/policy/config 정확 일치 | `OFF` |
| G5 SplitIntegrity | selection/test 분리, duplicate qid/source/entity family grouped | `BROKEN` |
| G6 Controls | cosine/current/strong baseline + shuffled/degree-null + negative oracle | `INCONCLUSIVE` |
| G7 Statistics | paired permutation, bootstrap CI, power, multiplicity; point estimate와 CI 병행 | `UNDERPOWERED/OFF` |
| G8 OptionalReadout | `mu=0` admissible, null 5 seeds 모두 0, label 없는 domain OFF | `OFF` |

현재 방식은 `empirical deployment gate` 또는 `empirical certificate`라고 부른다. 독립 calibration과 bounded-risk upper confidence receipt가 들어간 뒤에만 `statistically certified`라고 부른다. Conformal risk control과 learn-then-test 계보가 이 명명 한계를 이미 점유한다. [Conformal Risk Control](https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html), [ranked retrieval CRC](https://www.ijcai.org/proceedings/2025/1012)

### 10.3 Query-time trip

현재 상수는 유지 가능한 출발점이다.

- entropy delta <= `log 4`
- `n_eff >= 1.5`
- `kept_mass >= 0.95`
- finite output
- latency/resource budget

개선점:

- 첫 reason만이 아니라 모든 관측값과 fired reason을 기록한다.
- ITT, eligible-only effect, coverage/trip/refusal을 함께 보고한다.
- trip은 동일 snapshot의 current static field로 bit-identical fallback한다.

### 10.4 Supersession admission

| Gate | 조건 | 실패 |
|---|---|---|
| G9 DecisionAdmission | stable assertion, actor, evidence, justification, times, decay | `QUARANTINE_WRITE` |
| G10 ShadowImpact | expected stale suppression/current collateral/audit reachability 사전 계산 | `QUARANTINE_WRITE` |
| G11 Commit | unique event, expected revision, append+publish | `NOOP/CONFLICT` |
| G12 ReplayAudit | same digest, as-of reconstruction, compensation | `AUDIT_BROKEN` |

## 11. Receipt family

### `BuildReceiptV1`

- source/compiler/extractor/linker/embedder/prompt/config hashes
- counts, quarantine/fallbacks, span/provenance completeness
- topology statistics와 world manifest SHA

### `FieldSnapshotReceiptV1`

- world ID, ledger cut, kernel/parameter/policy hashes
- score layer별 digest와 분포
- invariant/negative-oracle 결과

### `CertificationReceiptV1`

- prereg ID와 exact arm definitions
- split/group hashes, n/power
- baseline/CI/p/multiplicity/null/negative oracle
- trip coverage, stale collateral, audit reachability
- `CERTIFIED | OFF | REFUTED | INCONCLUSIVE | UNDERPOWERED | BROKEN`

### `ReadoutReceiptV1`

- query/request hash, current/as-of/audit view
- snapshot/certificate/candidate digest
- score-component digest와 output digest
- `APPLY | FALLBACK_CURRENT_STATIC | FALLBACK_TEMPORAL_COSINE | REFUSE`
- 모든 gate 관측값/reason, latency, approximation label

### `SupersessionReceiptV1`

- event/stable assertion ID
- previous/new b와 dose
- actor/evidence/valid+recorded time
- expected/committed snapshot version
- shadow impact, commit digest, compensation pointer

## 12. World Builder v2 — ontology보다 먼저 할 것

### 12.1 먼저 IR + deterministic title-anchor

MuSiQue/2Wiki paragraph title은 이미 강한 corpus-local anchor다. 현재 capitalization heuristic보다 먼저 title dictionary의 exact/normalized mention을 exact span으로 잡는 값싼 arm을 둔다.

이 arm이 NER/coref/LLM extractor와 동률이면 무거운 builder는 채택하지 않는다.

### 12.2 extractor/linker/arity/ontology를 독립 가설로

누적 tier는 무엇이 성능을 만들었는지 알 수 없다. 다음 네 축을 가능한 한 frozen observation과 projection으로 분리한다.

1. mention/extraction: caps / title-anchor / NER / local coref / LLM OpenIE
2. resolution: none / embedding soft / QID+SKOS soft / hard union
3. fact shape: paragraph union / binary / role-aware n-ary
4. semantic profile: none / local types-relations / QID-PID / temporal-cardinality policy

LLM extractor는 question·answer·gold·support flag를 볼 수 없다. strict output와 exact evidence selectors를 만족하지 못한 assertion은 quarantine한다.

### 12.3 ontology profile

Core에 full RDF/OWL을 넣지 않는다.

- local stable ID가 정본이다.
- Wikidata Q/P는 optional external reference다.
- SKOS `altLabel/closeMatch`는 soft alias evidence다.
- hard `sameAs/exactMatch`는 높은 precision gate 후에만 projection에서 허용한다.
- type은 기본적으로 attribute이며 traversal hub node가 아니다.
- SHACL은 RDF export의 structural validation adapter일 뿐 semantic truth gate가 아니다. [SHACL](https://www.w3.org/TR/shacl/)

Wikidata statement의 qualifier/rank와 SKOS mapping semantics는 유용하지만 identity와 contradiction을 자동 보장하지 않는다. [Wikidata data model](https://www.wikidata.org/wiki/Help%3AData_model), [SKOS](https://www.w3.org/TR/skos-reference/)

### 12.4 선행 시스템에서 훔칠 것

| 계보 | 가져올 것 | 가져오지 않을 것 |
|---|---|---|
| HippoRAG | bake-time NER/OpenIE, soft synonym edge, passage incidence | 무조건 PPR, query-time LLM filter |
| HippoRAG 2 | passage context와 dense/sparse seed 통합 관찰 | 0-query-LLM 정체성을 깨는 online filter |
| GraphRAG | source provenance, temporal/status claim schema | community-summary 전체를 core에 이식 |
| HyperGraphRAG | natural-language n-ary fact record와 entity/fact confidence | n-ary 자체가 traversal 이득이라는 가정 |
| Web Annotation/PROV | evidence selector와 lineage vocabulary | truth 판정 |
| JCS/SLSA | content-addressed artifact/build receipt | source claim의 진실성 보증 |

### 12.5 novelty 금지와 방어 가능한 후보

이미 점유된 것:

- provenance-preserving KG/RAG: [HierarchRAG](https://papers.ssrn.com/sol3/Delivery.cfm/ce098f9a-b76b-4900-9493-078dfefeb057-MECA.pdf?abstractid=7042057&mirid=1)
- evidence ledger + temporal governance: [LedgerRAG](https://www.mdpi.com/2079-9292/15/7/1376)
- temporal graph updates: [TG-RAG](https://arxiv.org/abs/2510.13590)
- certified RAG/retrieval 일반론: CRC·C-RAG 계보

따라서 다음은 **검증 전 novelty가 아니라 contribution candidate**다.

1. stochastic observation과 deterministic compilation 사이의 compiler wall
2. 한 IR에서 paragraph/binary/n-ary/legacy view를 만드는 lossless multi-projection
3. source span -> observation -> assertion -> decision -> score terms -> rank의 snapshot-consistent replay chain
4. utility·false bridge·overmerge·hub/percolation·stale collateral·coverage를 동시에 보는 certified artifact change deployment
5. 좋은 graph material에서도 traversal이 계속 인증 거부되는 음성 결과

## 13. T6-EPWC prereg 실험

### 13.1 질문

> evidence-preserving builder가 full-corpus retrieval을 실제 개선하는가, 무엇이 그 이득을 만들며, 개선된 world에서 traversal `mu>0`이 살아나는가?

### 13.2 고정

- source snapshot과 split
- query-unique/grouped evaluation unit
- embedding model revision과 raw observation cache
- extractor inputs에서 QA labels 완전 제거
- same reader와 field policy
- primary/secondary metrics, multiplicity family
- builder마다 certificate 재발급; 이전 certificate 재사용 금지

### 13.3 단계형 factorial

전 조합을 한꺼번에 돌리지 않는다.

1. **Extraction phase:** caps vs title-anchor vs NER/coref vs LLM extraction, paragraph projection 고정
2. **Resolution phase:** best cheap extractor 위 none vs soft synonym vs QID/SKOS soft vs hard merge
3. **Arity phase:** 같은 frozen assertions를 paragraph/binary/n-ary projection으로 비교
4. **Temporal phase:** typed time/cardinality가 real stale candidate detection에 주는 이득 측정

### 13.4 결과 전 의무통계

- source/unit/mention/entity/assertion 수
- exact-span·provenance·role·temporal coverage
- extraction/link fallback와 quarantine
- alias soft/hard merge 수, sampled overmerge precision
- arity·degree p50/p90/max·Gini·components·giant-component
- gold-gold vs gold-noise bridge separation과 false bridge
- component score 분포, tie/margin/top-k churn
- eligible/trip/fallback/refusal을 reason별로
- current/as-of/audit coverage
- build/query LLM calls, tokens, time, cost
- source/model/prompt/config/cache/code hashes

`mention_misses_df_gate`는 mention recall이 아니다. 별도 annotated sample 없이는 recall이라고 부르지 않는다.

### 13.5 metrics

Primary:

- full-corpus all-support recall@10
- nDCG@10
- paired downstream answer F1

Safety co-primary:

- false bridge/overmerge
- hub/percolation budget
- stale-current collateral
- audit reachability
- CRE coverage/trip/refusal

Secondary:

- bridge coverage
- role/temporal completeness
- build/query cost와 latency

### 13.6 kill conditions

1. title-anchor가 NER/LLM arm과 동률이면 무거운 extractor를 채택하지 않는다.
2. exact-span gate 후 LLM gain이 사라지면 외부지식/누수 이득으로 기록한다.
3. n-ary가 같은 frozen fact의 binary projection을 못 이기면 성능 주장은 죽고 audit representation으로만 남긴다.
4. ontology gain이 alias-only control 후 사라지면 ontology theater다.
5. hard merge가 false bridge·hub·component collapse를 늘리면 retrieval gain과 무관하게 배포 거부한다.
6. builder 통계가 좋아져도 full-corpus metric이 안 오르면 구조 미학일 뿐이다.
7. 좋은 builder에서도 `mu=0`이면 “재료만 좋으면 순회가 산다”가 죽는다.
8. 동일 snapshot readout이 다른 evidence/score digest를 내면 one-field claim이 죽는다.
9. supersession detector의 precision-cost가 wrong-write collateral을 감당하지 못하면 자동화는 영구 금지한다.

## 14. 선결 falsifier — T4 arm (e)

사전등록은 separated-graded arm (e)와 kill(iii)을 요구했지만 구현은 deferred했다.

현재 정의대로 외부 revision metadata의 graded strength를 readout에서 `cosine + lambda_b log b`로 적용하면:

```text
MuSiQue x dose 0.5/0.25/0.1: arm(a) == arm(e), max_abs = 0.0
2Wiki   x dose 0.5/0.25/0.1: arm(a) == arm(e), max_abs = 0.0
```

따라서 retrieval capability의 “one-field only” novelty는 kill(iii)이 발동하는 방향이다.

구현 착지 순서:

1. 공식 arm (e)와 equivalence receipt 추가
2. actual stable-ID supersession write path 사용
3. current/audit/dose/trip 세 지표를 contract대로 판정
4. b=0.5 current recall이 완전 무손상이 아니었던 문구 정정
5. 차별화 가설을 atomic snapshot·replay·as-of·fanout·latency로 이동

이 정정은 EPWC 설계보다 논리적으로 먼저며, 구현은 EPWC S0에서 수행한다.

## 15. 수직 구현 순서

### S0 — claim/measurement repair

- T4 arm (e), kill(iii), actual write, trip receipt
- current-recall 문구 정정
- `substrate_bench.py` 재실행 오류 수리
- duplicate query grouped statistics 재계산
- embedding fallback artifact 정합

Gate: 기존 숫자의 변경 여부를 숨기지 않는 corrected baseline.

### S1 — module contract + IR skeleton

신규 후보:

- `world_ir.py`
- `world_compiler.py`
- `legacy_adapter.py`

Tests:

- source/span tamper rejection
- dangling evidence rejection
- input-order invariance
- QA/gold leakage negative oracle
- canonical build ID

### S2 — lossless paragraph compatibility

현 `world_builder.build()`를 parity oracle로 두고 새 compiler projection과 bit/stable-ID parity를 만든다.

Gate: 기존 59 tests + golden world/field/readout outputs 전부 유지.

### S3 — FieldSnapshot + CRE skeleton

- explicit target embeddings
- immutable snapshot IDs
- componentized score/readout receipts
- typed fallback/refusal
- raw production `mu` 차단

Gate: retrieve/selection/traverse same-snapshot digest + cert mismatch fail-closed.

### S4 — event-folded supersession

- stable assertion target
- unique event fold
- duplicate no-op / same-ID conflict
- current/as-of/audit reconstruction
- compensating event

Gate: replay/order/race simulation과 wrong-write shadow impact.

### S5 — additive-j core 통합

`ab_p5_full.Field`의 frozen cosine + positive residual을 core FSK로 옮긴다.

Gate:

- 기존 ab-p5 score/rank parity
- `lambda_j=0` exact temporal-cosine fallback
- negative judgment는 j가 아니라 decision/b route
- scorer/model/prompt hash receipt

### S6 — builder observation adapters

순서:

1. title-anchor exact span
2. NER
3. local coref
4. soft entity linking
5. recorded LLM n-ary extraction
6. optional QID/PID/SKOS adapter

Gate: 각 추가 기능이 독립 arm으로 원인 귀속 가능.

### S7 — T6 full-corpus + traversal 재인증

Gate: utility와 safety co-primary 동시 통과. `mu=0`은 정상적인 합격 결과이며 순회 OFF를 유지한다.

### S8 — ecosystem adapters

- LakatoTree: artifact/evidence/certificate read adapter
- bhgman_tool: stable-ID selection/readout adapter
- CHU: leaf-world reference adapter
- Longinus: source-specific evidence binding adapter

이 단계 전에는 planned consumer를 current consumer라고 부르지 않는다.

## 16. Module -> Engine 승격 조건

현 결정서는 `HSWM_WORLD_COMPILER_MODULE_DECISION_2026-07-20.json`이다.

다음이 모두 관측되기 전에는 engine을 만들지 않는다.

1. 독립 current consumer 2개 이상이 동일 IR을 실제 사용
2. full rebuild가 비현실적이라 incremental ingest 필요
3. concurrent writer와 single authoritative state owner 필요
4. crash-resume·durable dedup·atomic publish/outbox 필요
5. bounded queue·backpressure·cancellation·timeout 필요
6. IR이 2 dataset/2 release 이상 안정
7. Neo4j와 artifact store 중 authoritative writer 결정

승격 후에도 `compile_world()`는 pure kernel로 남고 orchestration engine이 바깥을 감싼다.

## 17. 허용/금지 주장

### 지금 허용

- HSWM은 evidence-preserving World Compiler와 snapshot-consistent certified readout substrate를 목표로 한다.
- 현 traversal refusal/fallback discipline은 가치 있는 안전 공학이다.
- graded temporal decay는 hard deletion 없이 dose-response를 표현한다.
- World builder 품질은 retrieval과 traversal의 열린 인과 가설이다.

### 구현 후에만 허용

- source-to-rank chain이 replay 가능하다.
- 한 supersession decision이 동일 snapshot의 모든 readout에 atomic하게 반영된다.
- builder change가 multi-metric deployment certificate를 통과한다.
- 통합 field가 full-corpus retrieval에서 baseline을 이긴다.

### 금지

- evidence-preserving RAG 자체가 HSWM 고유다.
- graded score는 HSWM만 표현할 수 있다.
- positive score residual이 ranking floor를 보장한다.
- n-ary/ontology가 traversal을 자동으로 살린다.
- 현재 softmax distribution이 실제 agent planning 효능을 증명한다.
- 현재 mean comparison이 formal/statistical certificate다.

## 18. 즉시 다음 수

가장 작은 실제 implementation packet은 다음 세 개다.

```text
P0-A  stale_poisoning arm(e) + claim repair
P0-B  world_ir.py + module decision + tamper/leakage tests
P0-C  legacy_adapter parity before any new extractor
```

그 다음에만 `FieldSnapshot + CRE`를 만들고, 그 위에서 title-anchor부터 builder factorial을 시작한다.

이 순서를 지키면 “새 builder가 좋아 보인다”가 아니라 다음을 분리해 알 수 있다.

```text
좋은 증거를 만들었나?
좋은 binding을 만들었나?
좋은 field를 만들었나?
좋은 readout을 만들었나?
해로운 처치를 정확히 거부했나?
```

그 다섯 질문에 artifact와 receipt로 답하는 것이 재정의된 HSWM의 본체다.

## 19. Source ledger

### Local/user/KG

- `HSWM/내가 주는 말.txt:1-6`
- `THEORY/재배맨/HSWM_STANDARD.md:74-215`
- `HSWM/PROM_TRAVERSAL_DESIGN_2026-07-19.md`
- `HSWM/PROM_WOLFRAM_IMPORT_2026-07-19.md`
- `GIT/HSWM/hypergraph.py`
- `GIT/HSWM/weight_field.py`
- `GIT/HSWM/readouts.py`
- `GIT/HSWM/world_builder.py`
- `GIT/HSWM/traversal.py`
- `GIT/HSWM/traversal_cert.py`
- `GIT/HSWM/stale_poisoning.py`
- live KG refs listed in §1.2, read-only on 2026-07-20

### Primary standards/papers

- [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
- [W3C PROV-O](https://www.w3.org/TR/prov-o/)
- [W3C n-ary relation pattern](https://www.w3.org/TR/swbp-n-aryRelations/)
- [W3C SHACL](https://www.w3.org/TR/shacl/)
- [RFC 8785 JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html)
- [SLSA Build Provenance](https://slsa.dev/spec/v1.2/build-provenance)
- [OpenLineage facets](https://openlineage.io/docs/spec/facets/)
- [Wikidata data model](https://www.wikidata.org/wiki/Help%3AData_model)
- [SKOS Recommendation](https://www.w3.org/TR/skos-reference/)
- [HippoRAG](https://arxiv.org/html/2405.14831)
- [HippoRAG 2](https://arxiv.org/html/2502.14802)
- [Microsoft GraphRAG dataflow](https://microsoft.github.io/graphrag/index/default_dataflow/)
- [HyperGraphRAG](https://arxiv.org/html/2503.21322)
- [Conformal Risk Control for RAG](https://proceedings.mlr.press/v235/kang24a.html)

## 20. Unresolved / ratification required

1. `EPWC / FSK / CRE` 명칭을 사용자 정전으로 채택할지.
2. core API의 `plan()`을 `selection_distribution()`으로 정직화할지.
3. v1 supersession authority를 누구/어떤 operator가 승인할지.
4. statistical certificate로 승격할 risk target과 loss를 무엇으로 할지.
5. leaf HSWM들의 multi-field weave를 Longinus가 어떤 stable reference로 묶을지.
6. 구현 P0-A/B/C를 바로 시작할지.

이 여섯 항목은 AI가 임의 정전화하지 않는다.
