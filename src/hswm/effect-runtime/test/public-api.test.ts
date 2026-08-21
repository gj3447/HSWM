import { expect, it } from "@effect/vitest"

import * as PublicApi from "../src/index.js"

it("does not export privileged store or authorizer capabilities", () => {
  expect("CommitStore" in PublicApi).toBe(false)
  expect("CreditAuthorizer" in PublicApi).toBe(false)
  expect("makeCommitStoreMemory" in PublicApi).toBe(false)
  expect("makeHSWMRuntimeLive" in PublicApi).toBe(false)
  expect("makeStaticCreditAuthorizer" in PublicApi).toBe(false)
})
