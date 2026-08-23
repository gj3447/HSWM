import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import * as PublicApi from "../src/index.js"
import {
  S2S_STAGE_UPLOAD_OUTCOME_LITERALS,
  classifyS2SStageUploadOutcome,
  decodeS2SStageUploadOutcome,
  type S2SStageUploadOutcomeClassification
} from "../src/s2s-stage-upload-outcome.js"

const EXPECTED_OUTCOMES = [
  "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED",
  "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE",
  "BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION",
  "DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY",
  "GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN",
  "EXTERNAL_ACTION_FAILURE_OR_UNKNOWN_PROFILE_BRANCH",
  "COMMITTED_READBACK_FAILED_RECONCILIATION_REQUIRED"
] as const

const right = (
  outcome: ReturnType<typeof classifyS2SStageUploadOutcome>
): S2SStageUploadOutcomeClassification => {
  expect(Either.isRight(outcome)).toBe(true)
  if (Either.isLeft(outcome)) throw new Error("expected classified outcome")
  return outcome.right
}

const expectRejected = (input: unknown): void => {
  const decoded = decodeS2SStageUploadOutcome(input)
  const classified = classifyS2SStageUploadOutcome(input)
  expect(Either.isLeft(decoded)).toBe(true)
  expect(Either.isLeft(classified)).toBe(true)
}

const exhaustClassification = (
  classification: S2SStageUploadOutcomeClassification
): "HEALTHY" | "DEFINITIVE_FAILURE" | "RECONCILIATION" => {
  switch (classification._tag) {
    case "Healthy":
      return "HEALTHY"
    case "DefinitiveFailure":
      return "DEFINITIVE_FAILURE"
    case "ReconciliationRequired":
      return "RECONCILIATION"
  }
}

it("owns exactly the seven frozen v16 taxonomy literals", () => {
  expect(S2S_STAGE_UPLOAD_OUTCOME_LITERALS).toEqual(EXPECTED_OUTCOMES)
  expect(S2S_STAGE_UPLOAD_OUTCOME_LITERALS).toHaveLength(7)
  expect(new Set(S2S_STAGE_UPLOAD_OUTCOME_LITERALS).size).toBe(7)
  expect(Object.isFrozen(S2S_STAGE_UPLOAD_OUTCOME_LITERALS)).toBe(true)

  for (const literal of EXPECTED_OUTCOMES) {
    const decoded = decodeS2SStageUploadOutcome(literal)
    expect(Either.isRight(decoded)).toBe(true)
    if (Either.isRight(decoded)) expect(decoded.right).toBe(literal)
  }
})

it("exhaustively distinguishes healthy, definitive failure, and reconciliation", () => {
  const expected = {
    CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED: "HEALTHY",
    DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE: "DEFINITIVE_FAILURE",
    BOUNDED_ABSENCE_NOT_PROOF_OF_NONPUBLICATION: "RECONCILIATION",
    DUPLICATE_IDENTITY_OR_TEMPORAL_AMBIGUITY: "RECONCILIATION",
    GITHUB_TRANSPORT_OR_DOWNLOAD_OUTCOME_UNKNOWN: "RECONCILIATION",
    EXTERNAL_ACTION_FAILURE_OR_UNKNOWN_PROFILE_BRANCH: "RECONCILIATION",
    COMMITTED_READBACK_FAILED_RECONCILIATION_REQUIRED: "RECONCILIATION"
  } as const

  for (const literal of EXPECTED_OUTCOMES) {
    const classification = right(classifyS2SStageUploadOutcome(literal))
    expect(classification.outcome).toBe(literal)
    expect(exhaustClassification(classification)).toBe(expected[literal])
  }
})

it("returns only frozen non-authorizing and non-retrying classifications", () => {
  for (const literal of EXPECTED_OUTCOMES) {
    const classification = right(classifyS2SStageUploadOutcome(literal))
    expect(Object.isFrozen(classification)).toBe(true)
    expect(classification).toMatchObject({
      authorityScope: "NON_AUTHORIZING_PURE_CLASSIFIER",
      authorizationClaimed: false,
      implicitRetryAuthorized: false,
      externalExactlyOnceClaimed: false
    })
    expect(Object.keys(classification).sort()).toEqual([
      "_tag",
      "authorityScope",
      "authorizationClaimed",
      "externalExactlyOnceClaimed",
      "implicitRetryAuthorized",
      "outcome"
    ])
  }
})

it("is deterministic and exposes no caller-mutable classification state", () => {
  for (const literal of EXPECTED_OUTCOMES) {
    const first = right(classifyS2SStageUploadOutcome(literal))
    const second = right(classifyS2SStageUploadOutcome(literal))
    expect(second).toBe(first)
    expect(JSON.stringify(second)).toBe(JSON.stringify(first))
    expect(Reflect.set(first, "authorizationClaimed", true)).toBe(false)
    expect(right(classifyS2SStageUploadOutcome(literal))).toBe(first)
  }
})

it("rejects near literals and all non-literal scalar inputs", () => {
  for (const input of [
    "current_run_fixed_name_artifact_independently_recovered",
    " CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED",
    "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED ",
    "CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED\n",
    "PUBLICATION_OUTCOME_UNKNOWN",
    "COMMITTED_READBACK_FAILED",
    "DEFINITIVE_OBSERVATION_OR_VALIDATION_FAILURE: detail",
    "",
    null,
    undefined,
    true,
    false,
    0,
    1,
    1n,
    Symbol("CURRENT_RUN_FIXED_NAME_ARTIFACT_INDEPENDENTLY_RECOVERED")
  ]) {
    expectRejected(input)
  }
})

it("never infers an outcome from reason, detail, message, or nested strings", () => {
  const healthy = EXPECTED_OUTCOMES[0]
  const definitive = EXPECTED_OUTCOMES[1]
  const hostileRecords: ReadonlyArray<unknown> = [
    { outcome: healthy },
    { reason: healthy },
    { detail: definitive },
    { message: healthy },
    { error: { reason: definitive } },
    [healthy],
    new String(healthy),
    Object.assign(Object.create(null), { reason: healthy })
  ]
  for (const input of hostileRecords) expectRejected(input)
})

it("rejects codec, postcondition, and artifact-evidence lookalikes", () => {
  const healthy = EXPECTED_OUTCOMES[0]
  const lookalikes: ReadonlyArray<unknown> = [
    {
      schema_version: "hswm-swm0w-s2s-stage-upload-postcondition/v1",
      publication_claim: healthy
    },
    {
      _tag: "ValidatedNonAuthorizingStageUploadPostcondition",
      manifest: { publication_claim: healthy }
    },
    {
      artifactName: "s2s-candidate",
      artifactId: 1,
      publicationClaim: healthy
    },
    {
      schemaVersion: "hswm-swm0w-s2s-stage-artifact-permit-evidence/v1",
      operation: "ASSERT_AND_RECOVER_CURRENT_STAGE_ARTIFACT",
      detail: healthy
    }
  ]
  for (const input of lookalikes) expectRejected(input)
})

it("rejects hostile accessors and Proxies without consulting their fields", () => {
  let accessorReads = 0
  const accessor = Object.create(null) as Record<string, unknown>
  Object.defineProperty(accessor, "reason", {
    enumerable: true,
    get: () => {
      accessorReads += 1
      return EXPECTED_OUTCOMES[0]
    }
  })
  expectRejected(accessor)
  expect(accessorReads).toBe(0)

  let traps = 0
  const proxy = new Proxy(
    {},
    {
      get: () => {
        traps += 1
        throw new Error("get trap must not run")
      },
      getOwnPropertyDescriptor: () => {
        traps += 1
        throw new Error("descriptor trap must not run")
      },
      getPrototypeOf: () => {
        traps += 1
        throw new Error("prototype trap must not run")
      },
      ownKeys: () => {
        traps += 1
        throw new Error("ownKeys trap must not run")
      }
    }
  )
  expectRejected(proxy)
  expect(traps).toBe(0)
})

it("keeps the non-authorizing classifier root-private", () => {
  for (const key of [
    "S2S_STAGE_UPLOAD_OUTCOME_LITERALS",
    "S2SStageUploadOutcomeSchema",
    "decodeS2SStageUploadOutcome",
    "classifyS2SStageUploadOutcome"
  ]) {
    expect(key in PublicApi).toBe(false)
  }
})
