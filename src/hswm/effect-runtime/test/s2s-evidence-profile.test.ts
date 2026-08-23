import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import * as PublicApi from "../src/index.js"
import { s2sConfirmatoryWorkflowContractSha256 } from "../src/s2s-workflow-contract.js"
import {
  S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES,
  buildS2SSuccessStageEvidenceEnvelope,
  validateS2SSuccessStageEvidenceEnvelope
} from "../src/s2s-evidence-profile.js"
import type {
  S2SEvidenceEnvelopeInput,
  S2SEvidenceStage
} from "../src/s2s-evidence-envelope.js"

const SOURCE_A = "1".repeat(40)
const REGISTRATION_B = "2".repeat(40)
const WORKFLOW_SHA = "3".repeat(64)
const CONTRACT_SHA = (() => {
  const value = s2sConfirmatoryWorkflowContractSha256()
  if (Either.isLeft(value)) throw value.left
  return value.right
})()

const inputFor = (stage: S2SEvidenceStage): S2SEvidenceEnvelopeInput => ({
  sourceCommitA: SOURCE_A,
  registrationCommitB: REGISTRATION_B,
  workflowRunId: 123,
  workflowRunCreatedAtUnixSeconds: 1_700_000_000,
  workflowApiPath: ".github/workflows/swm0w-s2s-confirmatory.yml",
  workflowFileSha256: WORKFLOW_SHA,
  workflowContractSha256: CONTRACT_SHA,
  stage,
  currentJobDatabaseId: 456,
  predecessor:
    stage === "REGISTER"
      ? null
      : {
          stage: stage === "CONFIRM" ? "REGISTER" : "CONFIRM",
          manifestRawSha256: "4".repeat(64),
          claimRawSha256: "5".repeat(64)
        },
  attachments: S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES[stage].map((spec) => ({
    logicalName: spec.logicalName,
    role: spec.role,
    schemaVersion: spec.schemaVersion,
    mediaType: spec.mediaType,
    bytes: new Uint8Array([0x31])
  }))
})

it("freezes the exact incremental success rosters within substrate bounds", () => {
  expect(S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES.REGISTER).toHaveLength(13)
  expect(S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES.CONFIRM).toHaveLength(17)
  expect(S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES.ADJUDICATE).toHaveLength(18)
  for (const stage of ["REGISTER", "CONFIRM", "ADJUDICATE"] as const) {
    const profile = S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES[stage]
    expect(Object.isFrozen(profile)).toBe(true)
    expect(profile.map((entry) => entry.logicalName)).toEqual(
      [...profile.map((entry) => entry.logicalName)].sort()
    )
    expect(new Set(profile.map((entry) => entry.logicalName)).size).toBe(
      profile.length
    )
    expect(new Set(profile.map((entry) => entry.role)).size).toBe(profile.length)
    const built = buildS2SSuccessStageEvidenceEnvelope(inputFor(stage))
    expect(Either.isRight(built)).toBe(true)
  }
})

it("rejects missing, relabeled, and profile-oversized attachments", () => {
  const base = inputFor("CONFIRM")
  const missing = buildS2SSuccessStageEvidenceEnvelope({
    ...base,
    attachments: base.attachments.slice(1)
  })
  const relabeledAttachments = [...base.attachments]
  const first = relabeledAttachments[0]
  if (first === undefined) throw new Error("profile fixture is empty")
  relabeledAttachments[0] = { ...first, role: "RELABELLED" }
  const relabeled = buildS2SSuccessStageEvidenceEnvelope({
    ...base,
    attachments: relabeledAttachments
  })
  const rssIndex = base.attachments.findIndex(
    (attachment) => attachment.logicalName === "numeric/python_rss.json"
  )
  const oversizedAttachments = [...base.attachments]
  const rss = oversizedAttachments[rssIndex]
  if (rss === undefined) throw new Error("RSS profile fixture is absent")
  oversizedAttachments[rssIndex] = {
    ...rss,
    bytes: new Uint8Array(8 * 1_024 + 1)
  }
  const oversized = buildS2SSuccessStageEvidenceEnvelope({
    ...base,
    attachments: oversizedAttachments
  })

  expect(Either.isLeft(missing)).toBe(true)
  expect(Either.isLeft(relabeled)).toBe(true)
  expect(Either.isLeft(oversized)).toBe(true)
  if (Either.isLeft(missing)) {
    expect(missing.left).toMatchObject({ reason: "ATTACHMENT_COUNT_MISMATCH" })
  }
  if (Either.isLeft(relabeled)) {
    expect(relabeled.left).toMatchObject({
      reason: "ATTACHMENT_DESCRIPTOR_MISMATCH"
    })
  }
  if (Either.isLeft(oversized)) {
    expect(oversized.left).toMatchObject({
      reason: "ATTACHMENT_PROFILE_LIMIT_EXCEEDED",
      logicalName: "numeric/python_rss.json"
    })
  }
})

it("keeps success-profile builders out of the package root", () => {
  expect("S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES" in PublicApi).toBe(false)
  expect("buildS2SSuccessStageEvidenceEnvelope" in PublicApi).toBe(false)
  expect("validateS2SSuccessStageEvidenceEnvelope" in PublicApi).toBe(false)
})

it("does not misreport a structurally invalid envelope as REGISTER", () => {
  const rejected = validateS2SSuccessStageEvidenceEnvelope({})
  expect(Either.isLeft(rejected)).toBe(true)
  if (Either.isLeft(rejected)) {
    expect(rejected.left).toMatchObject({
      stage: "UNKNOWN",
      reason: "STRUCTURAL_ENVELOPE_REJECTED"
    })
  }
})
