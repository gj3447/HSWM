import { expect, it } from "@effect/vitest"

import * as PublicApi from "../src/index.js"

it("exports the bounded core ontology contract without a mutation capability", () => {
  expect(typeof PublicApi.decodeHSWMCoreResponsibilityOntologyBytes).toBe(
    "function"
  )
  expect(typeof PublicApi.decodeHSWMCoreResponsibilityOntology).toBe("function")
  expect("validateHSWMCoreResponsibilityOntology" in PublicApi).toBe(false)
  expect("publishHSWMCoreResponsibilityOntology" in PublicApi).toBe(false)
})

it("exports the bounded v2 reference kernel but not its receipt internals", () => {
  expect(typeof PublicApi.decodeHSWMCanonicalSchemaV2).toBe("function")
  expect(typeof PublicApi.decodeCommitCanonicalAtomsV2Command).toBe(
    "function"
  )
  expect(typeof PublicApi.decodeCanonicalAtomV2AuthorizationGrants).toBe(
    "function"
  )
  expect(typeof PublicApi.validateHSWMCanonicalSchemaV2).toBe("function")
  expect(typeof PublicApi.evolveCanonicalAtomsV2).toBe("function")
  expect(typeof PublicApi.makeCanonicalAtomV2ReferenceLayer).toBe("function")
  expect("makeCanonicalAtomV2AcceptedReceipt" in PublicApi).toBe(false)
  expect("snapshotCanonicalAtomV2" in PublicApi).toBe(false)
  expect("snapshotCanonicalAtomV2Receipt" in PublicApi).toBe(false)
  expect("snapshotCanonicalAtomV2State" in PublicApi).toBe(false)
  expect("snapshotCommitCanonicalAtomsV2Command" in PublicApi).toBe(false)
  expect("snapshotHSWMCanonicalSchemaV2" in PublicApi).toBe(false)
})

it("exports the content-bound v2 facade without raw store mutation ports", () => {
  expect(typeof PublicApi.decodeCanonicalJsonBytes).toBe("function")
  expect(typeof PublicApi.canonicalJsonBytes).toBe("function")
  expect(typeof PublicApi.decodeCanonicalAtomV2SchemaContent).toBe(
    "function"
  )
  expect(typeof PublicApi.describeCanonicalAtomV2Envelope).toBe("function")
  expect(typeof PublicApi.makeCanonicalAtomV2ContentBoundInput).toBe(
    "function"
  )
  expect(typeof PublicApi.makeCanonicalAtomV2ContentRuntimeMemoryLayer).toBe(
    "function"
  )
  expect(typeof PublicApi.makeCanonicalAtomV2ContentRuntimeFileLayer).toBe(
    "function"
  )
  expect("CanonicalAtomV2ContentStore" in PublicApi).toBe(false)
  expect("makeCanonicalAtomV2ContentRuntimeLayer" in PublicApi).toBe(false)
  expect("makeCanonicalAtomV2ContentFileStoreLayer" in PublicApi).toBe(false)
  expect("makeCanonicalAtomV2ContentStoreMemoryLayer" in PublicApi).toBe(
    false
  )
  expect("snapshotCanonicalAtomV2WriteContentBinding" in PublicApi).toBe(
    false
  )
  expect("snapshotCanonicalAtomV2ContentState" in PublicApi).toBe(false)
  expect("makeCanonicalAtomV2ContentAuthorizer" in PublicApi).toBe(false)
  expect("decodeCanonicalAtomV2ContentBoundInput" in PublicApi).toBe(false)
  expect("decodeCanonicalAtomV2ContentGrants" in PublicApi).toBe(false)
  expect(
    "validateCanonicalAtomV2ContentGrantConfiguration" in PublicApi
  ).toBe(false)
  expect("prepareCanonicalAtomV2WriteContent" in PublicApi).toBe(false)
})

it("exports a read-only durable graph view and GE-2 composition without a raw mutation port", () => {
  expect(typeof PublicApi.decodeCanonicalAtomV2StateJournalRecordBytes).toBe(
    "function"
  )
  expect(typeof PublicApi.CanonicalAtomV2DurableGraphView).toBe("function")
  expect(
    typeof PublicApi.makeGraphLoopEngineeringFileLayer
  ).toBe("function")
  expect(PublicApi.HSWM_CANONICAL_ATOM_V2_LOCAL_DURABLE_STATE).toBe(
    "LOCAL_PREDECESSOR_BOUND_STATE_AND_RECEIPT_JOURNAL_V1"
  )
  expect("CanonicalAtomV2StateJournalStore" in PublicApi).toBe(false)
  expect("CanonicalAtomV2DurableRuntime" in PublicApi).toBe(false)
  expect("CanonicalAtomV2DurableRuntimeError" in PublicApi).toBe(false)
  expect("makeCanonicalAtomV2DurableRuntimeFileLayer" in PublicApi).toBe(
    false
  )
  expect("makeGraphLoopControlJournalFileLayer" in PublicApi).toBe(false)
  expect("makeGraphLoopEngineeringControllerLayer" in PublicApi).toBe(false)
  expect(
    "makeCanonicalAtomV2StateJournalFileStoreLayer" in PublicApi
  ).toBe(false)
  expect(
    "makeCanonicalAtomV2StateJournalStoreMemoryLayer" in PublicApi
  ).toBe(false)
  expect(
    "CANONICAL_ATOM_V2_STATE_JOURNAL_FILE_PUBLICATION_CHECKPOINTS_FOR_TEST" in
      PublicApi
  ).toBe(false)
  expect(
    "makeCanonicalAtomV2StateJournalFileStoreLayerWithInterruptionForTest" in
      PublicApi
  ).toBe(false)
  expect(
    "CANONICAL_ATOM_V2_STATE_JOURNAL_FILE_IO_FAULT_POINTS_FOR_TEST" in
      PublicApi
  ).toBe(false)
  expect(
    "makeCanonicalAtomV2StateJournalFileStoreLayerWithIoFaultsForTest" in
      PublicApi
  ).toBe(false)
  expect(
    "makeCanonicalAtomV2StateJournalFileStoreLayerWithBeforeSlotLinkForTest" in
      PublicApi
  ).toBe(false)
  expect(
    "makeCanonicalAtomV2DurableRuntimeFileLayerWithInterruptionForTest" in
      PublicApi
  ).toBe(false)
  expect(
    "makeCanonicalAtomV2DurableRuntimeFileLayerWithIoFaultsForTest" in
      PublicApi
  ).toBe(false)
  expect(
    "makeCanonicalAtomV2DurableRuntimeFileLayerWithBeforeSlotLinkForTest" in
      PublicApi
  ).toBe(false)
  expect("makeCanonicalAtomV2DurableRuntimeLayer" in PublicApi).toBe(false)
  expect(
    "makeCanonicalAtomV2DurableRuntimeMemoryLayerForTest" in PublicApi
  ).toBe(false)
  expect("makeCanonicalAtomV2StateJournalGenesis" in PublicApi).toBe(false)
  expect("makeCanonicalAtomV2StateJournalCommit" in PublicApi).toBe(false)
  expect("applyCanonicalAtomV2StateJournalGenesis" in PublicApi).toBe(false)
  expect("applyCanonicalAtomV2StateJournalCommit" in PublicApi).toBe(false)
  expect("canonicalAtomV2StateJournalRecordBytes" in PublicApi).toBe(false)
  expect("describeCanonicalAtomV2StateJournalRecord" in PublicApi).toBe(
    false
  )
  expect("canonicalAtomV2StateSha256" in PublicApi).toBe(false)
  expect("snapshotCanonicalAtomV2StateJournalRecord" in PublicApi).toBe(
    false
  )
  expect(
    typeof PublicApi.compileCanonicalAtomV2DurableRdfProjection
  ).toBe("function")
  expect(
    typeof PublicApi.verifyCanonicalAtomV2DurableRdfProjection
  ).toBe("function")
  expect(
    typeof PublicApi.decodeCanonicalAtomV2DurableRdfProjectionBytes
  ).toBe("function")
  expect(
    "recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal" in PublicApi
  ).toBe(false)
  expect(
    "recoverCanonicalAtomV2DurableForReadOnlyProjectionInternal" in PublicApi
  ).toBe(false)
})

it("exports the blocked G0 phase kernel without test or live-execution authority", () => {
  expect(PublicApi.HSWM_G0_OCCURRENCE_PHASE_KERNEL_V1_CONTRACT_VERSION).toBe(
    "hswm-g0-occurrence-phase-kernel/v1"
  )
  expect(typeof PublicApi.G0OccurrencePhaseKernel).toBe("function")
  expect(typeof PublicApi.G0OccurrencePhaseKernelLayer).toBe("object")
  expect("makeG0OccurrencePhaseKernelLayer" in PublicApi).toBe(false)
  expect(typeof PublicApi.g0OneShotWorkflowPolicy).toBe("function")
  expect("registeredG0Occurrence" in PublicApi).toBe(false)
  expect("advanceG0Occurrence" in PublicApi).toBe(false)
  expect("makeG0TestOnlyMemoryPortsLayer" in PublicApi).toBe(false)
  expect("executeG0Occurrence" in PublicApi).toBe(false)
  expect("signalG0Occurrence" in PublicApi).toBe(false)
  expect("publishG0Occurrence" in PublicApi).toBe(false)
  expect("startG0TemporalOneShot" in PublicApi).toBe(false)
  expect("runG0TemporalWorker" in PublicApi).toBe(false)
  expect("runG0TemporalLocalRehearsalWorker" in PublicApi).toBe(false)
  expect("simulateG0TestOnlyOperator" in PublicApi).toBe(false)
})

it("exports read-safe typed transition evidence without an issuer or admission bypass", () => {
  expect(
    PublicApi.HSWM_CANONICAL_TRANSITION_EVIDENCE_V1_CONTRACT_VERSION
  ).toBe("hswm-canonical-transition-evidence/v1")
  expect(
    typeof PublicApi.validateCanonicalAtomV2TransitionEvidenceRecord
  ).toBe("function")
  expect(
    typeof PublicApi.decodeCanonicalAtomV2TransitionEvidenceRecordBytes
  ).toBe("function")
  expect(
    typeof PublicApi.validateCanonicalAtomV2TransitionEvidenceBundle
  ).toBe("function")
  expect(
    typeof PublicApi.decodeCanonicalAtomV2TransitionEvidenceBundleBytes
  ).toBe("function")
  expect(
    typeof PublicApi.classifyCanonicalAtomV2AuthorizationEvidence
  ).toBe("function")
  expect("snapshotCanonicalAtomV2TransitionEvidenceRecord" in PublicApi).toBe(
    false
  )
  expect("snapshotCanonicalAtomV2TransitionEvidenceBundle" in PublicApi).toBe(
    false
  )
  expect("CanonicalAtomV2CurrentPermitResolver" in PublicApi).toBe(false)
  expect("CanonicalAtomV2TransitionEvidenceStore" in PublicApi).toBe(false)
  expect("issueCanonicalAtomV2AuthorizationDecision" in PublicApi).toBe(false)
  expect("makeCanonicalAtomV2TransitionEvidenceBundle" in PublicApi).toBe(false)
  expect("createCanonicalAtomV2TransitionEvidence" in PublicApi).toBe(false)
  expect("publishCanonicalAtomV2TransitionEvidence" in PublicApi).toBe(false)
  expect("storeCanonicalAtomV2TransitionEvidence" in PublicApi).toBe(false)
  expect("applyCanonicalAtomV2TransitionEvidence" in PublicApi).toBe(false)
  expect("commitCanonicalAtomV2TransitionEvidence" in PublicApi).toBe(false)
  expect("admitCanonicalAtomV2TransitionEvidence" in PublicApi).toBe(false)
  expect("learnCanonicalAtomV2Outcome" in PublicApi).toBe(false)
})

it("exports exact local-head Permit eligibility without a canonical Permit or commit capability", () => {
  expect(
    PublicApi.HSWM_CANONICAL_CURRENT_STATE_PERMIT_V1_CONTRACT_VERSION
  ).toBe("hswm-canonical-current-state-permit/v1")
  expect(
    typeof PublicApi.validateCanonicalAtomV2CurrentStatePermitRecord
  ).toBe("function")
  expect(
    typeof PublicApi.decodeCanonicalAtomV2CurrentStatePermitInputBytes
  ).toBe("function")
  expect(
    typeof PublicApi.resolveCanonicalAtomV2CurrentStatePermitEligibilityAtDurableRuntime
  ).toBe("function")
  expect(
    "resolveCanonicalAtomV2CurrentStatePermitEligibility" in PublicApi
  ).toBe(false)
  expect("CanonicalAtomV2CurrentPermitResolver" in PublicApi).toBe(false)
  expect("CanonicalAtomV2CanonicalPermit" in PublicApi).toBe(false)
  expect("issueCanonicalAtomV2Permit" in PublicApi).toBe(false)
  expect("commitCanonicalAtomV2WithPermit" in PublicApi).toBe(false)
  expect("submitCanonicalAtomV2WithPermit" in PublicApi).toBe(false)
  expect("makeCanonicalAtomV2MonotonicHeadWitness" in PublicApi).toBe(false)
  expect("verifyCanonicalAtomV2MonotonicHeadWitness" in PublicApi).toBe(false)
  expect("admitCanonicalAtomV2PermitResolution" in PublicApi).toBe(false)
  expect("learnCanonicalAtomV2PermitResolution" in PublicApi).toBe(false)
})

it("exports the fail-closed Lean refinement obstruction without a learning capability", () => {
  expect(
    PublicApi.HSWM_CANONICAL_LEARNING_REFINEMENT_V1_CONTRACT_VERSION
  ).toBe("hswm-canonical-learning-refinement/v1")
  expect(
    PublicApi.canonicalAtomV2LearningRefinementProfile().verdict
  ).toBe("BLOCKED_NOT_REFINED_TO_LEAN_LEARN")
  expect(
    typeof PublicApi.canonicalAtomV2LearningRefinementProfileBytes
  ).toBe("function")
  expect(
    typeof PublicApi.decodeCanonicalAtomV2LearningRefinementProfileBytes
  ).toBe("function")
  expect("refineCanonicalAtomV2ToLeanLearn" in PublicApi).toBe(false)
  expect("admitCanonicalAtomV2Learning" in PublicApi).toBe(false)
  expect("issueCanonicalAtomV2CanonicalPermit" in PublicApi).toBe(false)
})

it("exports owner-bound outcome codecs without evaluator, adjudicator, or learning authority", () => {
  expect(
    PublicApi.HSWM_CANONICAL_OWNER_BOUND_OUTCOME_V1_CONTRACT_VERSION
  ).toBe("hswm-canonical-owner-bound-outcome/v1")
  expect(
    typeof PublicApi.validateCanonicalAtomV2OwnerBoundOutcomeRecord
  ).toBe("function")
  expect(
    typeof PublicApi.decodeCanonicalAtomV2OwnerBoundOutcomeJudgmentBundleBytes
  ).toBe("function")
  expect("issueCanonicalAtomV2OutcomeObservation" in PublicApi).toBe(false)
  expect("issueCanonicalAtomV2RevisionSupport" in PublicApi).toBe(false)
  expect("makeCanonicalAtomV2OutcomeEvaluator" in PublicApi).toBe(false)
  expect("makeCanonicalAtomV2CreditAdjudicator" in PublicApi).toBe(false)
  expect("learnCanonicalAtomV2OutcomeJudgment" in PublicApi).toBe(false)
})

it("exports the atomic-admission obstruction without composition or mutation authority", () => {
  expect(
    PublicApi.HSWM_CANONICAL_ATOMIC_ADMISSION_REFINEMENT_V1_CONTRACT_VERSION
  ).toBe("hswm-canonical-atomic-admission-refinement/v1")
  expect(
    PublicApi.canonicalAtomV2AtomicAdmissionRefinementProfile().verdict
  ).toBe("BLOCKED_NOT_REFINED_TO_LEAN_ATOMIC_ADMISSION")
  expect(
    typeof PublicApi.decodeCanonicalAtomV2AtomicAdmissionRefinementProfileBytes
  ).toBe("function")
  expect("composeCanonicalAtomV2AtomicAdmission" in PublicApi).toBe(false)
  expect("issueCanonicalAtomV2HeadBoundPermit" in PublicApi).toBe(false)
  expect("validateCanonicalAtomV2TransitionInvariant" in PublicApi).toBe(false)
  expect("admitCanonicalAtomV2AtomicLearning" in PublicApi).toBe(false)
})

it("does not export privileged store or authorizer capabilities", () => {
  expect("CommitStore" in PublicApi).toBe(false)
  expect("CreditAuthorizer" in PublicApi).toBe(false)
  expect("makeCommitStoreMemory" in PublicApi).toBe(false)
  expect("makeHSWMRuntimeLive" in PublicApi).toBe(false)
  expect("makeStaticCreditAuthorizer" in PublicApi).toBe(false)
  expect("S2SConfirmatoryControlPlane" in PublicApi).toBe(false)
  expect("advanceS2SConfirmatory" in PublicApi).toBe(false)
  expect("S2SConfirmatoryEventSchema" in PublicApi).toBe(false)
  expect("PythonNumericOracle" in PublicApi).toBe(false)
  expect("ConfirmatoryArtifactStore" in PublicApi).toBe(false)
  expect("RunEvidenceStore" in PublicApi).toBe(false)
  expect("runS2SBoundedProcess" in PublicApi).toBe(false)
  expect("S2SPythonGoldenVerifier" in PublicApi).toBe(false)
  expect("S2SDurableJournalFileStore" in PublicApi).toBe(false)
  expect("S2SDurableEvidenceFileStore" in PublicApi).toBe(false)
  expect("isAuthenticS2SDurableEvidenceRecovery" in PublicApi).toBe(false)
  expect("buildS2SEvidenceEnvelope" in PublicApi).toBe(false)
  expect("validateS2SEvidenceEnvelope" in PublicApi).toBe(false)
  expect("validateS2SEvidenceEnvelopeSnapshot" in PublicApi).toBe(false)
  expect("buildS2SEvidenceClaim" in PublicApi).toBe(false)
  expect("validateS2SArtifactZip" in PublicApi).toBe(false)
  expect("prepareS2SRegistrationCarrier" in PublicApi).toBe(false)
  expect("prepareS2SCandidateCarrier" in PublicApi).toBe(false)
  expect("prepareS2SAdjudicationCarrier" in PublicApi).toBe(false)
  expect("finalizeS2SEvidenceReadback" in PublicApi).toBe(false)
  expect("S2SGitHubHttpTransport" in PublicApi).toBe(false)
  expect("S2SGitHubObserver" in PublicApi).toBe(false)
  expect("S2SGitHubObserverLive" in PublicApi).toBe(false)
  expect("S2SGitHubObservationValidationError" in PublicApi).toBe(false)
  expect("makeS2SGitHubHttpTransportLiveLayer" in PublicApi).toBe(false)
  expect("observeS2SGitHubWorkflowRunsForHead" in PublicApi).toBe(false)
  expect("validateS2SGitHubWorkflowRunObservation" in PublicApi).toBe(false)
  expect(
    "validateS2SGitHubWorkflowAttemptJobsObservation" in PublicApi
  ).toBe(false)
  expect(
    "validateS2SGitHubWorkflowRunsForHeadObservation" in PublicApi
  ).toBe(false)
  expect("validateS2SGitHubRunArtifactsObservation" in PublicApi).toBe(false)
  expect("validateS2SGitHubArtifactObservation" in PublicApi).toBe(false)
  expect("S2SArtifactAuthority" in PublicApi).toBe(false)
  expect("S2SStageArtifactReads" in PublicApi).toBe(false)
  expect("S2SStageArtifactPermitError" in PublicApi).toBe(false)
  expect("S2SStageArtifactReadError" in PublicApi).toBe(false)
  expect("S2SArtifactReadbackError" in PublicApi).toBe(false)
  expect(
    "S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_SCHEMA_VERSION" in PublicApi
  ).toBe(false)
  expect(
    "S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_MAX_RAW_BYTES" in PublicApi
  ).toBe(false)
  expect(
    "makeS2SCurrentRunAndStageArtifactReadsLiveLayer" in PublicApi
  ).toBe(false)
  expect("makeS2SStageArtifactReadsLiveLayer" in PublicApi).toBe(false)
  expect("probeS2SStageArtifactReadMechanicsForTest" in PublicApi).toBe(false)
  expect("claimS2SStageArtifactPermitScope" in PublicApi).toBe(false)
  expect("makeS2SStageArtifactPermitTestScope" in PublicApi).toBe(false)
  expect("appendS2SStageArtifactLedgerEntry" in PublicApi).toBe(false)
  expect("useS2SStageArtifactPermit" in PublicApi).toBe(false)
  expect("snapshotS2SStageArtifactPermitEvidence" in PublicApi).toBe(false)
  expect("validateS2SStageArtifactPermitEvidence" in PublicApi).toBe(false)
  expect("closeS2SStageArtifactPermitScope" in PublicApi).toBe(false)
  expect("isAuthenticS2SValidatedStageArtifactRead" in PublicApi).toBe(false)
  expect("buildS2SStageArtifactReadReplay" in PublicApi).toBe(false)
  expect("buildS2SStageArtifactReadReplayEffect" in PublicApi).toBe(false)
  expect("validateS2SStageArtifactReadReplay" in PublicApi).toBe(false)
  expect("validateS2SStageArtifactReadReplayEffect" in PublicApi).toBe(false)
  expect("inspectS2SStageArtifactReadReplaySnapshot" in PublicApi).toBe(false)
  expect(
    "validateS2SCurrentRunStageEvidenceForArtifactReplay" in PublicApi
  ).toBe(false)
  expect("validateS2SCurrentRunStageEvidence" in PublicApi).toBe(false)
  expect("buildS2SStageUploadPostcondition" in PublicApi).toBe(false)
  expect("buildS2SStageUploadPostconditionEffect" in PublicApi).toBe(false)
  expect("reconstructS2SStageUploadPostcondition" in PublicApi).toBe(false)
  expect("validateS2SStageUploadPostcondition" in PublicApi).toBe(false)
  expect("validateS2SStageUploadPostconditionEffect" in PublicApi).toBe(false)
  expect("S2S_PREPARED_STAGE_CARRIER_SCHEMA_VERSION" in PublicApi).toBe(
    false
  )
  expect("S2SPreparedStageCarrierError" in PublicApi).toBe(false)
  expect("prepareS2SCurrentStageCarrier" in PublicApi).toBe(false)
  expect("inspectS2SPreparedStageCarrierCapability" in PublicApi).toBe(false)
  expect("makeS2SPreparedStageCarrierTestCapability" in PublicApi).toBe(
    false
  )
  expect("inspectS2SPreparedStageCarrierTestCapability" in PublicApi).toBe(
    false
  )
  expect("S2S_STAGE_UPLOAD_OUTCOME_LITERALS" in PublicApi).toBe(false)
  expect("S2SStageUploadOutcomeSchema" in PublicApi).toBe(false)
  expect("decodeS2SStageUploadOutcome" in PublicApi).toBe(false)
  expect("classifyS2SStageUploadOutcome" in PublicApi).toBe(false)
  expect("S2SStageUploadAssertionPermitError" in PublicApi).toBe(false)
  expect("claimS2SStageUploadAssertionPermitScope" in PublicApi).toBe(false)
  expect("makeS2SStageUploadAssertionPermitTestScope" in PublicApi).toBe(
    false
  )
  expect(
    "appendS2SStageUploadAssertionLedgerEntryForTest" in PublicApi
  ).toBe(false)
  expect("useS2SStageUploadAssertionPermitForTest" in PublicApi).toBe(false)
  expect(
    "snapshotS2SStageUploadAssertionPermitEvidenceForTest" in PublicApi
  ).toBe(false)
  expect("closeS2SStageUploadAssertionPermitScope" in PublicApi).toBe(false)
  expect("probeS2SStageUploadAssertionMechanicsForTest" in PublicApi).toBe(
    false
  )
  expect("validateS2SCandidateReadReplayPair" in PublicApi).toBe(false)
  expect("validateS2SCandidateReadReplayPairEffect" in PublicApi).toBe(false)
  expect(
    "commitS2SStageReadReplayProfileAttachments" in PublicApi
  ).toBe(false)
  expect("S2SStageReadReplayDurableProfileError" in PublicApi).toBe(false)
  expect("S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES" in PublicApi).toBe(false)
  expect("validateS2SRegistrationCommitB" in PublicApi).toBe(false)
  expect("inspectS2SRegistrationCommitAuthority" in PublicApi).toBe(false)
  expect("inspectS2SRegistrationReplaySnapshot" in PublicApi).toBe(false)
  expect("inspectS2SRegistrationWorkflowManifestBinding" in PublicApi).toBe(
    false
  )
  expect("S2S_CONFIRMATORY_WORKFLOW_CONTRACT" in PublicApi).toBe(false)
  expect("S2S_CONFIRMATORY_WORKFLOW_ID" in PublicApi).toBe(false)
  expect("S2SCurrentInvocation" in PublicApi).toBe(false)
  expect("S2SCurrentInvocationLive" in PublicApi).toBe(false)
  expect("inspectS2SCurrentInvocationAuthority" in PublicApi).toBe(false)
  expect("readS2SCurrentInvocationEventBytes" in PublicApi).toBe(false)
  expect("makeS2SCurrentInvocationTestLayer" in PublicApi).toBe(false)
  expect("validateS2SCurrentInvocation" in PublicApi).toBe(false)
  expect("makeS2SConfirmatoryControlPlaneMemoryForTest" in PublicApi).toBe(
    false
  )
  expect("SWM0RoleAwareT16ParameterArchiveSchema" in PublicApi).toBe(false)
  expect("makeSWM0RoleAwareT16Operator" in PublicApi).toBe(false)
  expect("evaluateSWM0RoleAwareT16" in PublicApi).toBe(false)
  expect("removeSWM0RoleAwareT16Q" in PublicApi).toBe(false)
  expect("restoreSWM0RoleAwareT16Q" in PublicApi).toBe(false)
  expect("broadcastSWM0RoleAwareT16Result" in PublicApi).toBe(false)
  expect("evaluateSWM0RoleAwareT16RoleCycles" in PublicApi).toBe(false)
})

it("keeps stage artifact capability and permit types root-private", () => {
  // @ts-expect-error stage read service types are deliberately root-private
  type ForbiddenReads = import("../src/index.js").S2SStageArtifactReadsService
  // @ts-expect-error permit evidence types are deliberately root-private
  type ForbiddenPermit = import("../src/index.js").S2SStageArtifactPermitEvidence
  // @ts-expect-error validated stage read types are deliberately root-private
  type ForbiddenValidatedRead = import("../src/index.js").S2SValidatedStageArtifactRead
  // @ts-expect-error raw lookup trace types are deliberately root-private
  type ForbiddenLookupTrace = import("../src/index.js").S2SArtifactSuccessfulLookupTrace
  // @ts-expect-error replay snapshot types are deliberately root-private
  type ForbiddenReplay = import("../src/index.js").S2SStageArtifactReadReplaySnapshot
  // @ts-expect-error upload postcondition types are deliberately root-private
  type ForbiddenUploadPostcondition = import("../src/index.js").S2SStageUploadPostconditionSnapshot
  // @ts-expect-error prepared carrier bearers are deliberately root-private
  type ForbiddenPreparedCarrier = import("../src/index.js").S2SPreparedStageCarrierCapability
  // @ts-expect-error assertion permit bearers are deliberately root-private
  type ForbiddenUploadAssertion = import("../src/index.js").S2SStageUploadAssertionPermitScope
  // @ts-expect-error upload outcome classifications are deliberately root-private
  type ForbiddenUploadOutcome = import("../src/index.js").S2SStageUploadOutcomeClassification
  // @ts-expect-error durable recovery types are deliberately root-private
  type ForbiddenRecovery = import("../src/index.js").S2SDurableEvidenceRecovery
  // @ts-expect-error durable replay-profile types are deliberately root-private
  type ForbiddenReplayPublication = import("../src/index.js").S2SStageReadReplayDurablePublication
  const absent: readonly [
    ForbiddenReads | undefined,
    ForbiddenPermit | undefined,
    ForbiddenValidatedRead | undefined,
    ForbiddenLookupTrace | undefined,
    ForbiddenReplay | undefined,
    ForbiddenUploadPostcondition | undefined,
    ForbiddenPreparedCarrier | undefined,
    ForbiddenUploadAssertion | undefined,
    ForbiddenUploadOutcome | undefined,
    ForbiddenRecovery | undefined,
    ForbiddenReplayPublication | undefined
  ] = [
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined
  ]
  expect(absent).toEqual([
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined
  ])
})

it("keeps the first T16 parity capsule package-root private", () => {
  // @ts-expect-error package publication is deferred until a separate review
  type ForbiddenOperator = import("../src/index.js").SWM0RoleAwareT16Operator
  // @ts-expect-error package publication is deferred until a separate review
  type ForbiddenResult = import("../src/index.js").SWM0RoleAwareT16Result
  const absent: readonly [
    ForbiddenOperator | undefined,
    ForbiddenResult | undefined
  ] = [undefined, undefined]
  expect(absent).toEqual([undefined, undefined])
})
