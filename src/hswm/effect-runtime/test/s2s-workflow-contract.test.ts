import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import { canonicalS2SControlSha256 } from "../src/s2s-canonical.js"
import {
  S2S_CONFIRMATORY_ARTIFACT_ROLES,
  S2S_CONFIRMATORY_JOB_IDS,
  S2S_CONFIRMATORY_JOB_STAGES,
  S2S_CONFIRMATORY_STAGE_CONTRACTS,
  S2S_CONFIRMATORY_WORKFLOW_CONTRACT,
  S2S_CONFIRMATORY_WORKFLOW_REF,
  s2sArtifactReadContract,
  s2sArtifactRoleMayBeConsumedByStage,
  s2sConfirmatoryWorkflowContractSha256,
  s2sStageForJobId
} from "../src/s2s-workflow-contract.js"

it("closes one exact three-stage workflow identity and role mapping", () => {
  expect(S2S_CONFIRMATORY_JOB_STAGES).toEqual([
    "REGISTER",
    "CONFIRM",
    "ADJUDICATE"
  ])
  expect(S2S_CONFIRMATORY_JOB_IDS).toEqual([
    "register",
    "confirm",
    "adjudicate"
  ])
  expect(S2S_CONFIRMATORY_ARTIFACT_ROLES).toEqual([
    "REGISTRATION",
    "CANDIDATE",
    "ADJUDICATION"
  ])
  expect(S2S_CONFIRMATORY_WORKFLOW_REF).toBe(
    "gj3447/HSWM/.github/workflows/swm0w-s2s-confirmatory.yml@refs/heads/main"
  )
  expect(
    S2S_CONFIRMATORY_JOB_STAGES.map(
      (stage) => S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].producesArtifactRole
    )
  ).toEqual(S2S_CONFIRMATORY_ARTIFACT_ROLES)
  expect(s2sStageForJobId("register")).toBe("REGISTER")
  expect(s2sStageForJobId("confirm")).toBe("CONFIRM")
  expect(s2sStageForJobId("adjudicate")).toBe("ADJUDICATE")
  expect(s2sStageForJobId("finalize")).toBeUndefined()
  expect(s2sStageForJobId(new String("confirm"))).toBeUndefined()
})

it("permits only predecessor artifact consumption inside workflow jobs", () => {
  expect(
    s2sArtifactRoleMayBeConsumedByStage("REGISTER", "REGISTRATION")
  ).toBe(false)
  expect(
    s2sArtifactRoleMayBeConsumedByStage("CONFIRM", "REGISTRATION")
  ).toBe(true)
  expect(s2sArtifactRoleMayBeConsumedByStage("CONFIRM", "CANDIDATE")).toBe(
    false
  )
  expect(s2sArtifactRoleMayBeConsumedByStage("ADJUDICATE", "CANDIDATE")).toBe(
    true
  )
  expect(
    s2sArtifactRoleMayBeConsumedByStage("ADJUDICATE", "ADJUDICATION")
  ).toBe(false)
  expect(
    S2S_CONFIRMATORY_STAGE_CONTRACTS.ADJUDICATE.consumesArtifactRoles
  ).toEqual(["REGISTRATION", "CANDIDATE"])
  expect(
    S2S_CONFIRMATORY_STAGE_CONTRACTS.ADJUDICATE.artifactReadOperations.map(
      (entry) => entry.operation
    )
  ).toEqual([
    "ADJUDICATE_READ_REGISTRATION",
    "ADJUDICATE_READ_CANDIDATE_FIRST",
    "ADJUDICATE_REREAD_CANDIDATE"
  ])
  expect(
    s2sArtifactReadContract("CONFIRM", "CONFIRM_READ_REGISTRATION")
  ).toMatchObject({ artifactRole: "REGISTRATION", maximumUses: 1 })
  expect(
    s2sArtifactReadContract("CONFIRM", "ADJUDICATE_READ_REGISTRATION")
  ).toBeUndefined()
})

it("has a stable canonical self-hash and deeply frozen contract", () => {
  const digest = s2sConfirmatoryWorkflowContractSha256()
  const independent = canonicalS2SControlSha256(
    S2S_CONFIRMATORY_WORKFLOW_CONTRACT
  )
  expect(Either.isRight(digest)).toBe(true)
  expect(digest).toEqual(independent)
  if (Either.isRight(digest)) {
    expect(digest.right).toBe(
      "45e14e0e3d2a0ca0b652c2d39741b264968d4ecdb2d0ff5b74eabd0aa8904050"
    )
  }
  expect(Object.isFrozen(S2S_CONFIRMATORY_WORKFLOW_CONTRACT)).toBe(true)
  expect(Object.isFrozen(S2S_CONFIRMATORY_WORKFLOW_CONTRACT.stages)).toBe(true)
  expect(
    S2S_CONFIRMATORY_WORKFLOW_CONTRACT.stages.every((stage) =>
      Object.isFrozen(stage.consumesArtifactRoles) &&
      Object.isFrozen(stage.artifactReadOperations) &&
      stage.artifactReadOperations.every(Object.isFrozen)
    )
  ).toBe(true)
  expect(S2S_CONFIRMATORY_WORKFLOW_CONTRACT.sourceManifestWorkflowEntry).toEqual(
    {
      path: ".github/workflows/swm0w-s2s-confirmatory.yml",
      mode: "100644",
      objectType: "blob",
      sha256Authority: "PINNED_REVIEWED_WORKFLOW_BYTES",
      sha256Status: "OPEN_UNTIL_WORKFLOW_BYTES_EXIST"
    }
  )
  expect(
    Object.isFrozen(
      S2S_CONFIRMATORY_WORKFLOW_CONTRACT.sourceManifestWorkflowEntry
    )
  ).toBe(true)
})
