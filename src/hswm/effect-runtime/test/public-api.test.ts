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
  expect("makeS2SConfirmatoryControlPlaneMemoryForTest" in PublicApi).toBe(
    false
  )
})
