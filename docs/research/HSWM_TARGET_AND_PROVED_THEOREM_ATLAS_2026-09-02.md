# HSWM target and proved-theorem atlas

> **Date:** `2026-09-02`
>
> **Status:** `CANONICAL_TARGET_EXPLAINED / FORMAL_MODEL_PROOF_ATLAS / REAL_RUNTIME_AND_SCIENTIFIC_EFFICACY_UNPROVED`
>
> **Scientific status:** `UNJUDGED / INTEGRATED_CLAIM_UNJUDGED`
>
> **Target authority:**
> [`HSWM Constitution`](../canon/HSWM_CONSTITUTION_2026-08-20.md),
> [`fractal cognitive composition canon`](../canon/USER_PRIMARY_HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.md)
>
> **Current status parent:**
> [`HSWM proof-status graph`](HSWM_PROOF_STATUS_GRAPH_2026-09-02.md) and its
> [`v5 machine projection`](../../ontology/identity/hswm_core/HSWM_GRAPH_AND_LOOP_ENGINEERING_ONTOLOGY.v5.json)

## 1. Answer first

HSWM의 목표를 알고 있다. HSWM은 memory, KG, RAG, agent workflow 또는 외부 harness를
붙인 시스템의 이름이 아니다. 목표는 **하나의 token-native LLM-function macro-neural
network**다. Schema가 승인한 canonical atom과 typed relation의 evolving hypergraph가
동시에 다음 네 역할을 수행해야 한다.

1. token event로 점화되고 LLM-executed transition을 만드는 신경망;
2. 다음 실행의 memory, function, tool, verifier, suppression과 stop을 조건화하는 living harness;
3. 관계 상태와 provenance-bound rewrite 안에서 인지·행동하는 world/self model;
4. outcome-bound canonical revision이 이후 traversal과 행동을 바꾸는 continuous learner.

목표 폐루프는 다음이다.

```text
LLM token event
  -> schema-admissible sparse n-ary traversal/transition
  -> outcome 전에 봉인된 typed trajectory
  -> 외부에서 귀속 가능한 outcome
  -> independently identified causal credit
  -> owner + Permit + invariant-valid canonical revision
  -> durable successor and changed fresh behavior
```

Lean으로 **증명된 것은 이 목표를 안전하게 말하기 위한 model-level grammar와 조건부
합성의 상당 부분**이다. Lean으로 **증명되지 않은 것은 이 grammar가 실제
TypeScript/Effect, 암호·시간·저장소, 외부 세계의 진실, 인과 식별과 real LLM에서 실제로
inhabit됐다는 사실**이다.

따라서 두 문장이 동시에 정확하다.

> HSWM의 형식 모델에는 이미 많은 기계 증명이 있다.

> 현실에서 작동하고 학습하는 완성된 HSWM은 아직 증명되지 않았다.

## 2. Target identity graph

```text
T0  one token-native LLM-function macro-neural HSWM
 |
 +--T1  schema-approved canonical atoms + typed n-ary relations
 +--T2  evolving hypergraph = neural state = harness = world/self model
 +--T3  sealed trajectory -> external outcome -> causal credit
 +--T4  single-owner + current Permit + invariant-valid revision
 +--T5  durable successor changes later traversal/action and remains restorable
 +--T6  cognition-bearing HSWMs compose into a larger HSWM under the same grammar
 |
 +--Tmax  difference-preserving HSWM-of-HSWMs, ultimately the human-universal-body target

P1..P8  Lean proof families --CONSTRAIN--> T0..T6
E-real  runtime/world/experiment evidence --REQUIRED_FOR--> inhabiting T0..T6
```

`T1..T6`는 subsystem 목록이 아니다. 하나의 HSWM을 서로 다른 correctness와 observation
질문으로 본 target obligation이다. Fixed `H/W/A/F/Pi` 분해는 현행 정본이 아니다. 각
schema-approved atom version은 정확히 하나의 schema-relative responsibility owner를
가지고, 다른 의미·역할·권한은 typed reference와 provenance-bound transition으로
연결한다.

### Fractal maximum target

HSWM의 fractal 목표는 graph를 nested하게 저장하는 것이 아니다. Cognition-bearing HSWM
전체가 하나의 scale-relative cognitive cell이 되고, 여러 HSWM이 합성된 상위 전체에도
같은 `Step / Learn / Inv / Permit / lineage` 전이 문법이 다시 적용되어야 한다. 상위
HSWM은 구성원의 주소성, 차이, provenance, consent, exit와 restore 가능성을 지우면 안
된다.

최대 목표 합성은 인류·LLM·인지능력체·센서·인터넷·공개 정보와 기억이 차이와 권리 경계를
보존한 채 하나의 공개 HSWM 구조에서 작동하는 **인류보편체**다. 이것은 target identity의
최대 방향이지 현재 구현, scale invariance, consciousness, personhood 또는 사회적 정당성의
증명이 아니다.

## 3. What “proved” means here

현재 `formal/`에는 Lean module 20개가 있고, 그중 19개가 총 274개의
`theorem / lemma / example` 선언을 가진다. Pinned Lean `4.32.1`에서 `lake build` 35 jobs가
통과했다. `sorry` 또는 `axiom` 선언은 발견되지 않았다. Source에 보이는 `.admit`은
proof-hole tactic이 아니라 `Learn.admit`, `AtomicAdmission.admit` 같은 inductive relation의
명명된 data constructor다.

이 숫자는 HSWM 과학 진척률이 아니다. 하나의 큰 theorem을 여러 보조 lemma로 나눌 수
있으므로 theorem 수로 목표 달성률을 계산하지 않는다. 여기서 `PROVED`는 정확히 다음을
뜻한다.

```text
declared Lean types + relations + explicit premises
  -> Lean kernel이 해당 conclusion을 허용
```

다음을 뜻하지 않는다.

```text
TypeScript가 그 relation을 실제로 구현함
외부 premise가 현실에서 참임
실제 LLM behavior가 개선됨
HSWM 전체나 fractal composition이 실현됨
```

## 4. Machine-proved theorem families

### P1 — canonical outcome-bound learning safety

주요 파일:
[`HSWMCanonicalLearning.lean`](../../formal/HSWMCanonicalLearning.lean)

대표 정리:

- `learnRequiresIndependentEvaluator`
- `learnRequiresIndependentOutcomeOwner`
- `learnRequiresTraceBinding`
- `learnRequiresSupportedOutcome`
- `learnRequiresCurrentPermit`
- `learnRequiresInvariant`
- `learnRequiresExactCurrentRevision`
- `learnPreservesTargetOwner`
- `learnChangesOnlyTarget`
- `learnArchivesPreviousVersion`

Lean model 안에서 `Learn` witness가 존재하려면 exact trajectory/outcome/proposal binding,
독립 역할, supporting outcome, current active Permit, invariant와 current revision이 필요함을
증명한다. Self-evaluation, proposer evaluation, actor/proposer-owned outcome, unsealed 또는
mismatched trajectory, unsupported outcome, denied/inactive Permit, stale/reused revision에는
`Learn` witness가 없다는 보호 정리도 있다.

**증명하지 않는 것:** evaluator가 현실에서 독립인지, outcome이 참인지, credit이 인과적인지,
실제 저장소가 바뀌었는지 또는 revision이 유용한지.

### P2 — owner-bound observation and revision-support judgment

주요 파일:
[`HSWMOutcomeJudgment.lean`](../../formal/HSWMOutcomeJudgment.lean)

대표 정리:

- `observationHasUniqueOwner`
- `judgmentHasUniqueOwner`
- `learnFromEvidenceRequiresExactJudgment`
- `observationAloneCannotLearn`
- `nonSupportingJudgmentCannotLearn`
- `collapsedOwnerRolesCannotLearn`
- `collapsedEvaluatorAdjudicatorCannotLearn`

Outcome observation과 “이 outcome이 이 revision을 지지한다”는 judgment를 다른 lifecycle과
owner를 가진 record로 분리하고, exact supporting judgment가 admission에 실제 소비되어야
함을 증명한다. Observation을 저장했거나 역할 이름이 다르다는 사실만으로 learning이
생기지 않는다.

**증명하지 않는 것:** observation truth, principal authentication, operational independence와
causal support.

### P3 — head-bound atomic admission, consistency, and non-entailment

주요 파일:
[`HSWMAtomicAdmission.lean`](../../formal/HSWMAtomicAdmission.lean),
[`HSWMAtomicAdmissionConsistency.lean`](../../formal/HSWMAtomicAdmissionConsistency.lean),
[`HSWMAtomicAdmissionNonEntailment.lean`](../../formal/HSWMAtomicAdmissionNonEntailment.lean)

대표 정리:

- `atomicAdmissionRequiresSharedHead`
- `atomicAdmissionRequiresExactProposalBinding`
- `atomicAdmissionRequiresExactCertificateConsumption`
- `atomicAdmissionRequiresLinearSuccessor`
- `atomicAdmissionNextStateUnique`
- `stalePermitHeadCannotAdmit`
- `deniedPermitCannotAtomicAdmit`
- `atomicAdmissionRelationIsNonempty`
- `atomicAdmissionCanExistWithoutBehaviorChange`
- `atomicAdmissionDoesNotEntailIntegratedEfficacy`

Permit, invariant certificate, proposal, state digest와 commit이 같은 head와 exact candidate를
가리켜야 하고, modeled stale/mismatch/denial은 admission될 수 없음을 증명한다. Target owner,
non-target frame과 previous revision archive가 보존되고, 고정 input의 successor가 유일함도
증명한다. 별도 consistency witness는 relation이 공허하지 않음을 보인다.

동시에 exact atomic admission이 있어도 constant behavior, external truth 부재 또는 causal
support 부재와 양립할 수 있다는 countermodel을 증명한다. 즉 **구조적 admission 자체가
효능을 함의하지 않는다는 것까지 증명됐다.**

**증명하지 않는 것:** trusted head/hash, real atomic storage, authenticated principal,
outcome truth, causal credit 또는 LLM gain.

### P4 — abstract local Permit, nonce, commit, wire, and persisted decision

주요 파일:
[`HSWMLocalPermitCommit.lean`](../../formal/HSWMLocalPermitCommit.lean),
[`HSWMVerifiedAdmissionKernel.lean`](../../formal/HSWMVerifiedAdmissionKernel.lean),
[`HSWMVerifiedAdmissionWire.lean`](../../formal/HSWMVerifiedAdmissionWire.lean),
[`HSWMPersistedVerifiedAdmission.lean`](../../formal/HSWMPersistedVerifiedAdmission.lean)

대표 정리:

- `issueLocalNonceAcceptedIff`
- `acceptedLocalCommitRequiresForeignChecks`
- `advancedLocalCommitRejectsSameNonceReplay`
- `verifiedAdmissionKernelAcceptedIff`
- `verifiedAdmissionKernelSound`
- `verifiedAdmissionKernelComplete`
- `wireAcceptedHasExactKernelSuccessor`
- `acceptedPersistedEntrySimulatesFullLocalCommit`
- `wrongStoredResponseCannotBeAccepted`

순수 state machine과 checker 안에서 acceptance가 exact successor publication과 nonce
consumption을 요구하고, 같은 nonce replay를 거부함을 증명한다. Verified admission kernel은
선언된 abstract transition에 대해 sound하고 complete하며, decoded wire와 persisted entry가
같은 recovered head/nonce view의 exact transition을 투영함을 증명한다.

**증명하지 않는 것:** Effect/Node semantics, Ed25519, SHA-256, canonical JSON, clock truth,
nonce randomness, filesystem durability, crash recovery 또는 TypeScript source refinement.

### P5 — Permit envelope and execution-certificate decoded structure

주요 파일:
[`HSWMCanonicalPermitEnvelope.lean`](../../formal/HSWMCanonicalPermitEnvelope.lean),
[`HSWMExecutionCertificateWire.lean`](../../formal/HSWMExecutionCertificateWire.lean)

대표 정리:

- `acceptedEnvelopeProjectsEveryCheckedBinding`
- `acceptedEnvelopeAndSoundVerifierYieldAuthenticatedDocument`
- `changedNonceCannotBeAccepted`
- `acceptedWireProjectsStructuralConditions`
- `acceptedWireProjectsLinearSuccessor`
- `acceptedWireYieldsClaimedConcreteExecutionEvidence`
- `changedIntentDigestRejected`
- `invalidSuccessorRejected`

Accepted decoded field가 expected execution/head/proposal/nonce/key-policy/time context와 exact
successor chronology를 투영하고, modeled field substitution을 거부함을 증명한다. Signature의
의미는 supplied verifier-soundness premise 아래에서만 나온다.

**증명하지 않는 것:** raw parser와 canonical bytes, hash/signature cryptography, real issuer
custody, authoritative time 또는 actual certificate occurrence.

### P6 — conditional end-to-end composition and current-runtime obstruction

주요 파일:
[`HSWMEndToEndRuntimeRefinement.lean`](../../formal/HSWMEndToEndRuntimeRefinement.lean),
[`HSWMTypeScriptV1Refinement.lean`](../../formal/HSWMTypeScriptV1Refinement.lean)

대표 정리:

- `claimedCertificateConditionsYieldAtomicAdmission`
- `soundVerifierAndKeyPolicyYieldPermitAuthentication`
- `externalOutcomeWitnessProjectsTruthAndCausalCredit`
- `matchingSuiteMeasurementYieldsBoundedScoreGain`
- `boundedImprovementImpliesBehaviorChange`
- `conditionalEvidenceBundleYieldsBoundedClaim`
- `checkedInTypeScriptPublishesOnlyObstruction`
- `checkedInTypeScriptNotReadyForEndToEndRefinement`
- `booleanReadinessDoesNotEntailAtomicAdmission`
- `currentV1CannotRefineLearn`

Concrete runtime abstraction, exact certificate/Permit/commit occurrence, sound verifier and active
key, external truth/credit witness, sealed behavior measurement, strict score gain과 independent
revision attribution을 **전제로 받으면** atomic admission과 bounded behavior claim을 합성할
수 있음을 증명한다. Strict aggregate gain이면 declared suite 안에서 적어도 한 modeled
response가 달라짐도 증명한다.

동시에 checked-in current profile과 단순 Boolean readiness metadata로는 이 positive witness를
만들 수 없다는 obstruction을 증명한다.

**증명하지 않는 것:** 위 현실 premise가 실제로 존재함, 모든 TS/Effect execution의 Lean
refinement, real provider call completeness 또는 real-world causal efficacy.

### P7 — DNRD-5 exact gate and typed causal-occurrence bridge

주요 파일:
[`HSWMDnrd5ExactSignGate.lean`](../../formal/HSWMDnrd5ExactSignGate.lean),
[`HSWMDnrd5EfficacyBoundary.lean`](../../formal/HSWMDnrd5EfficacyBoundary.lean),
[`HSWMCausalEfficacyBridge.lean`](../../formal/HSWMCausalEfficacyBridge.lean)

대표 정리:

- `exactBonferroniPassTrueIff`
- `goRequiresIntegrityCompletenessAndAllContrasts`
- `checkedInEvidenceCannotIssueScientificTerminal`
- `ledgerHasExactlyOneTrajectoryFourProposalsAndFourProbes`
- `witnessHasTwoThousandSevenHundredUniqueTypedCalls`
- `typedOccurrenceAndDerivedGoYieldBoundedCausalEfficacy`
- `derivedGoWithMissingRuntimeAdapterCannotYieldCausalClaim`
- `atomicAdmissionAloneDoesNotEntailBehaviorChange`

Exact sign/Bonferroni count arithmetic, integrity-first classifier와 declared four-arm 300-block,
2,700-call typed occurrence structure를 증명한다. Row mismatch, premature delayed release,
rollback snapshot mismatch와 extra/replaced generation call은 modeled checker에서 fail closed한다.
모든 real-world semantic premise와 derived `GO`가 함께 있을 때만 bounded causal claim이
나온다.

**증명하지 않는 것:** actual 300-block run, future randomness, complete provider ledger,
placebo/isolation, score truth, independent judge, actual rollback, causal identification 또는
LLM efficacy. 현재 checked-in evidence는 scientific terminal을 발행할 수 없다는 것이
증명된 상태다.

### P8 — runtime, durable-outbox, and cellular pure contracts

주요 파일:
[`HSWMRuntime.lean`](../../formal/HSWMRuntime.lean),
[`HSWMDurableRuntime.lean`](../../formal/HSWMDurableRuntime.lean),
[`HSWMCellular.lean`](../../formal/HSWMCellular.lean)

대표 정리:

- `duplicateRequestRejects`
- `validRequestProducesOneEvent`
- `replayAppend`
- `succeededIsTerminal`
- `thenCell_preserves_output_type`
- `candidate_is_reversible`
- `rejected_proposal_is_noop`
- `connection_alone_is_not_larger_ai`

Typed pure-kernel event/outbox transition, terminal-state와 reversible cell-proposal 성질을
증명한다. Cell이 연결됐다는 사실만으로 larger cognition-bearing HSWM이 되지 않는다는
구조적 경계도 명시한다.

**증명하지 않는 것:** real filesystem/SQLite/effect execution, real LLM, cognition,
composition efficacy 또는 FCL closure.

[`HSWMAdmissionKernelCli.lean`](../../formal/HSWMAdmissionKernelCli.lean)은 theorem module이
아니라 native stdin/stdout adapter다. Key, clock, nonce issuer나 storage authority를 소유하지
않는다.

## 5. Target-to-evidence matrix

| Target obligation | Formal status | Runtime/scientific status |
|---|---|---|
| schema-relative owner, typed binding and revision frame | extensive model theorems | bounded local engineering only |
| current Permit, invariant and exact atomic admission | model theorems and nonempty witness | one local slice; production authority/storage unproved |
| every in-scope TS/Effect execution refines Lean | necessary conditions and current-profile obstruction | `UNPROVED` |
| external outcome is true | conditional witness interface only | `NOT_ESTABLISHED` |
| exact revision receives independent causal credit | conditional witness and non-entailment theorems | `NOT_ESTABLISHED` |
| revision causes fresh real-LLM improvement | conditional suite/occurrence theorem only | `G0_NOT_PASSED / G1_NOT_EVALUATED` |
| durable learned relation/disposition/topology | safety scaffolds only | `UNJUDGED` |
| FCL-1..8 and HSWM-of-HSWMs cognitive closure | target contracts and scientific connections only | `UNJUDGED` |
| consciousness, personhood, scale invariance, human-universal-body realization | no such theorem | not claimed |

이 표에서 가장 중요한 구분은 **relation이 안전하게 정의됐다는 것**과 **현실 witness가 그
relation을 inhabit했다는 것**이다. Lean은 전자를 강하게 만들고 후자의 가짜 승격을
차단한다. 현실 witness는 암호·저장소 checker, external outcome provenance, independent
causal design과 real LLM occurrence로 별도 제출되어야 한다.

## 6. Current exact conclusion

기존 여섯 end-to-end proof-status obligation을 기준으로 한 현재 판정은 다음과 같다.

```text
FORMAL_MODEL_PROVED          1
LOCAL_ENGINEERING_SUPPORTED  2
CORE_UNPROVED                3
```

엄격한 형식 증명 여부로만 이분하면 `1 formal proof group / 5 not universal or scientific
proof groups`다. 후자 중 둘은 “아무것도 없음”이 아니라 제한된 local execution evidence다.
그러나 HSWM target 전체를 묻는다면 보편 runtime bridge와 scientific causal loop가 닫히지
않았으므로 **미증명이 우세하고 전체 상태는 `UNJUDGED`**다.

## 7. What must be proved next

1. 증명 대상을 “모든 임의의 TypeScript”가 아니라 exact protected TS/Effect surface와
   observable trace semantics로 자른다.
2. 그 surface의 actual v2 receipt와 complete execution certificate를 pinned checker에
   연결하고 Lean transition simulation을 증명한다.
3. Production key custody, authoritative time, cross-store atomic nonce, power-loss,
   anti-rollback과 target storage semantics를 각각 qualification한다.
4. G0를 닫은 외부 occurrence에서 outcome truth, evaluator/judge independence와 causal
   credit을 판정한다.
5. 그 뒤에만 fresh real-LLM probe의 gain, remove-loss, restore-return과 independent
   reproduction으로 revision efficacy를 판정한다.
6. Local causal rung이 통과한 뒤에만 topology learning과 FCL composition으로 올라간다.

Downstream scale, 더 큰 model 또는 더 많은 agent는 upstream failure를 구제하지 않는다.
실패한 mechanism은 evidence lineage를 보존한 채 교체하되 target identity를 작은 memory,
KG, harness나 workflow로 축소하지 않는다.

## 8. Document boundary

이 문서는 Constitution과 checked-in Lean source를 사람이 읽기 쉽게 연결한 derived proof
atlas다. 새 theorem, runtime occurrence, experimental result, KG cognition 또는 scientific
terminal을 만들지 않는다. Exact status node와 source hash는 parent proof-status v5를
따르며, 동시 진행 중인 graph-loop successor projection을 수정하거나 선점하지 않는다.
