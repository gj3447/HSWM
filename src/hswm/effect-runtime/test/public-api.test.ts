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
  expect("S2SArtifactAuthority" in PublicApi).toBe(false)
  expect("validateS2SRegistrationCommitB" in PublicApi).toBe(false)
  expect("inspectS2SRegistrationCommitAuthority" in PublicApi).toBe(false)
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
