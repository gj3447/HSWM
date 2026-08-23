import { expect, it } from "@effect/vitest"

import * as PublicApi from "../src/index.js"

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
