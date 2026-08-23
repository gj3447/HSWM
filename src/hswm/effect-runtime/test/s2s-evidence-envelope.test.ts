import { expect, it } from "@effect/vitest"
import { Either } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENTS,
  buildS2SEvidenceClaim,
  buildS2SEvidenceEnvelope,
  s2sEvidenceClaimFileName,
  validateS2SEvidenceClaim,
  validateS2SEvidenceClaimForEnvelope,
  validateS2SEvidenceEnvelope,
  type S2SEvidenceAttachmentInput,
  type S2SEvidenceEnvelopeError,
  type S2SEvidenceEnvelopeInput,
  type S2SEvidenceEnvelopeSnapshot,
  type S2SEvidenceStage
} from "../src/s2s-evidence-envelope.js"
import {
  S2S_CONFIRMATORY_BRANCH,
  S2S_CONFIRMATORY_WORKFLOW_PATH,
  s2sConfirmatoryWorkflowContractSha256
} from "../src/s2s-workflow-contract.js"

const UTF8_ENCODER = new TextEncoder()
const UTF8_DECODER = new TextDecoder("utf-8", { fatal: true })
const SOURCE_COMMIT_A = "a".repeat(40)
const REGISTRATION_COMMIT_B = "b".repeat(40)
const WORKFLOW_FILE_SHA256 = "c".repeat(64)
const WORKFLOW_CONTRACT_SHA256 = (() => {
  const outcome = s2sConfirmatoryWorkflowContractSha256()
  if (Either.isLeft(outcome)) throw outcome.left
  return outcome.right
})()
const WORKFLOW_RUN_ID = 123_456_789
const WORKFLOW_CREATED_AT_UNIX_SECONDS = 1_700_000_000
const WORKFLOW_API_PATH =
  `${S2S_CONFIRMATORY_WORKFLOW_PATH}@${S2S_CONFIRMATORY_BRANCH}`

const GOLDEN_MANIFEST =
  '{"attachment_count":2,"attachment_total_bytes":16,"attachments":[' +
  '{"byte_length":12,"logical_name":"evidence/control.json",' +
  '"media_type":"application/json","raw_sha256":' +
  '"e5f1eb4d806641698a35efe20e098efd20d7d57a9b90ee69079d5bb650920726",' +
  '"role":"CONTROL_RECEIPT","schema_version":"hswm.test/control/v1"},' +
  '{"byte_length":4,"logical_name":"numeric/output.bin",' +
  '"media_type":"application/octet-stream","raw_sha256":' +
  '"3d1f57c984978ef98a18378c8166c1cb8ede02c03eeb6aee7e2f121dfeee3e56",' +
  '"role":"NUMERIC_OUTPUT","schema_version":null}],' +
  '"claim_scope":"ONE_REGISTRATION_COMMIT_PER_STAGE",' +
  '"current_job_database_id":7001,' +
  '"experiment_id":"hswm-swm0w-s2s-confirmatory-v1",' +
  '"manifest_receipt_sha256":' +
  '"5fad7a779114e6aceb7b8b6e646ff3520336ea886bdabb7ac4c58635dfc70d47",' +
  '"predecessor":null,' +
  `"registration_commit_b":"${REGISTRATION_COMMIT_B}",` +
  '"schema_version":"hswm-swm0w-s2s-evidence-envelope/v1",' +
  `"source_commit_a":"${SOURCE_COMMIT_A}",` +
  '"stage":"REGISTER",' +
  `"workflow_api_path":"${WORKFLOW_API_PATH}",` +
  `"workflow_contract_sha256":"${WORKFLOW_CONTRACT_SHA256}",` +
  `"workflow_file_sha256":"${WORKFLOW_FILE_SHA256}",` +
  `"workflow_head_sha":"${REGISTRATION_COMMIT_B}",` +
  '"workflow_run_attempt":1,' +
  `"workflow_run_created_at_unix_seconds":${WORKFLOW_CREATED_AT_UNIX_SECONDS},` +
  `"workflow_run_id":${WORKFLOW_RUN_ID}}\n`

const GOLDEN_MANIFEST_RAW_SHA256 =
  "271687606fc6f933d6171c9988361543afe4fb7c9f74be1a9affa91ccfdebf1a"

const GOLDEN_CLAIM =
  '{"claim_receipt_sha256":' +
  '"b7035ba9c3688e1cfdb89ff1d22c1e9e7ca191811b85f7af6e7dde3794c2e1b3",' +
  '"claim_scope":"ONE_REGISTRATION_COMMIT_PER_STAGE",' +
  '"experiment_id":"hswm-swm0w-s2s-confirmatory-v1",' +
  `"manifest_raw_sha256":"${GOLDEN_MANIFEST_RAW_SHA256}",` +
  '"predecessor_claim_raw_sha256":null,' +
  `"registration_commit_b":"${REGISTRATION_COMMIT_B}",` +
  '"schema_version":"hswm-swm0w-s2s-evidence-claim/v1",' +
  `"source_commit_a":"${SOURCE_COMMIT_A}",` +
  '"stage":"REGISTER","workflow_run_attempt":1,' +
  `"workflow_run_id":${WORKFLOW_RUN_ID}}\n`

const GOLDEN_CLAIM_RAW_SHA256 =
  "13ba1f3e7071bab4fd55db3aec5e5ba2c981d7fc0d83c4d9acb073b744a189fc"

type JsonRecord = Record<string, unknown>
type ValidationAttachment = {
  readonly rawSha256: string
  readonly bytes: Uint8Array
}

const rightOrThrow = <A, E>(outcome: Either.Either<A, E>): A => {
  if (Either.isLeft(outcome)) throw outcome.left
  return outcome.right
}

const expectLeftReason = <A>(
  outcome: Either.Either<A, S2SEvidenceEnvelopeError>,
  expected: S2SEvidenceEnvelopeError["reason"]
): S2SEvidenceEnvelopeError => {
  expect(Either.isLeft(outcome)).toBe(true)
  if (Either.isRight(outcome)) {
    throw new Error(`expected ${expected}, received Right`)
  }
  expect(outcome.left.reason).toBe(expected)
  return outcome.left
}

const encodeCanonical = (value: unknown): Uint8Array =>
  rightOrThrow(canonicalS2SControlJsonBytes(value))

const canonicalSha256 = (value: unknown): string =>
  rightOrThrow(canonicalS2SControlSha256(value))

const parseRecord = (input: Uint8Array): JsonRecord => {
  const parsed: unknown = JSON.parse(UTF8_DECODER.decode(input))
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("expected a JSON object")
  }
  return parsed as JsonRecord
}

const requiredAttachments = (document: JsonRecord): Array<JsonRecord> => {
  const attachments = document["attachments"]
  if (!Array.isArray(attachments)) throw new Error("expected attachments array")
  for (const attachment of attachments) {
    if (
      attachment === null ||
      typeof attachment !== "object" ||
      Array.isArray(attachment)
    ) {
      throw new Error("expected attachment object")
    }
  }
  return attachments as Array<JsonRecord>
}

const withSelfHash = (
  document: JsonRecord,
  receiptField: "manifest_receipt_sha256" | "claim_receipt_sha256"
): Uint8Array => {
  const unsigned: JsonRecord = {}
  for (const [key, value] of Object.entries(document)) {
    if (key !== receiptField) unsigned[key] = value
  }
  document[receiptField] = canonicalSha256(unsigned)
  return encodeCanonical(document)
}

const makeAttachments = (): Array<S2SEvidenceAttachmentInput> => [
  {
    logicalName: "numeric/output.bin",
    role: "NUMERIC_OUTPUT",
    schemaVersion: null,
    mediaType: "application/octet-stream",
    bytes: Uint8Array.from([0, 1, 2, 255])
  },
  {
    logicalName: "evidence/control.json",
    role: "CONTROL_RECEIPT",
    schemaVersion: "hswm.test/control/v1",
    mediaType: "application/json",
    bytes: UTF8_ENCODER.encode('{"ok":true}\n')
  }
]

const makeInput = (
  overrides: Partial<S2SEvidenceEnvelopeInput> = {}
): S2SEvidenceEnvelopeInput => ({
  sourceCommitA: SOURCE_COMMIT_A,
  registrationCommitB: REGISTRATION_COMMIT_B,
  workflowRunId: WORKFLOW_RUN_ID,
  workflowRunCreatedAtUnixSeconds: WORKFLOW_CREATED_AT_UNIX_SECONDS,
  workflowApiPath: WORKFLOW_API_PATH,
  workflowFileSha256: WORKFLOW_FILE_SHA256,
  workflowContractSha256: WORKFLOW_CONTRACT_SHA256,
  stage: "REGISTER",
  currentJobDatabaseId: 7_001,
  predecessor: null,
  attachments: makeAttachments(),
  ...overrides
})

const buildEnvelope = (
  overrides: Partial<S2SEvidenceEnvelopeInput> = {}
): S2SEvidenceEnvelopeSnapshot =>
  rightOrThrow(buildS2SEvidenceEnvelope(makeInput(overrides)))

const validationAttachments = (
  envelope: S2SEvidenceEnvelopeSnapshot
): Array<ValidationAttachment> =>
  envelope.attachments.map((attachment) => ({
    rawSha256: attachment.descriptor.raw_sha256,
    bytes: attachment.readBytes()
  }))

const validateBuiltEnvelope = (envelope: S2SEvidenceEnvelopeSnapshot) =>
  validateS2SEvidenceEnvelope({
    manifestBytes: envelope.canonicalBytes,
    attachments: validationAttachments(envelope)
  })

it("emits and validates one literal deterministic manifest and claim vector", () => {
  const envelope = buildEnvelope()

  expect(UTF8_DECODER.decode(envelope.canonicalBytes)).toBe(GOLDEN_MANIFEST)
  expect(envelope.manifestRawSha256).toBe(GOLDEN_MANIFEST_RAW_SHA256)
  expect(envelope.document.manifest_receipt_sha256).toBe(
    "5fad7a779114e6aceb7b8b6e646ff3520336ea886bdabb7ac4c58635dfc70d47"
  )
  expect(
    envelope.attachments.map((attachment) => attachment.descriptor.logical_name)
  ).toEqual(["evidence/control.json", "numeric/output.bin"])
  expect(
    envelope.attachments.map((attachment) => attachment.descriptor.raw_sha256)
  ).toEqual([
    "e5f1eb4d806641698a35efe20e098efd20d7d57a9b90ee69079d5bb650920726",
    "3d1f57c984978ef98a18378c8166c1cb8ede02c03eeb6aee7e2f121dfeee3e56"
  ])

  const validated = rightOrThrow(validateBuiltEnvelope(envelope))
  expect(validated.document).toEqual(envelope.document)
  expect(validated.canonicalBytes).toEqual(envelope.canonicalBytes)

  const claim = rightOrThrow(buildS2SEvidenceClaim(envelope))
  expect(UTF8_DECODER.decode(claim.canonicalBytes)).toBe(GOLDEN_CLAIM)
  expect(claim.claimRawSha256).toBe(GOLDEN_CLAIM_RAW_SHA256)
  expect(rightOrThrow(validateS2SEvidenceClaim(claim.canonicalBytes))).toEqual(
    claim
  )
  expect(
    rightOrThrow(
      validateS2SEvidenceClaimForEnvelope(claim.canonicalBytes, envelope)
    )
  ).toEqual(claim)
  expect(
    s2sEvidenceClaimFileName(
      envelope.document.registration_commit_b,
      "REGISTER"
    )
  ).toBe(`${REGISTRATION_COMMIT_B}.register.json`)
})

it("forms the exact REGISTER to CONFIRM to ADJUDICATE predecessor chain", () => {
  const register = buildEnvelope()
  const registerClaim = rightOrThrow(buildS2SEvidenceClaim(register))
  const confirm = buildEnvelope({
    stage: "CONFIRM",
    currentJobDatabaseId: 7_002,
    predecessor: {
      stage: "REGISTER",
      manifestRawSha256: register.manifestRawSha256,
      claimRawSha256: registerClaim.claimRawSha256
    }
  })
  const confirmClaim = rightOrThrow(buildS2SEvidenceClaim(confirm))
  const adjudicate = buildEnvelope({
    stage: "ADJUDICATE",
    currentJobDatabaseId: 7_003,
    predecessor: {
      stage: "CONFIRM",
      manifestRawSha256: confirm.manifestRawSha256,
      claimRawSha256: confirmClaim.claimRawSha256
    }
  })
  const adjudicateClaim = rightOrThrow(buildS2SEvidenceClaim(adjudicate))

  expect(register.document.predecessor).toBeNull()
  expect(registerClaim.document.predecessor_claim_raw_sha256).toBeNull()
  expect(confirm.document.predecessor).toEqual({
    stage: "REGISTER",
    manifest_raw_sha256: register.manifestRawSha256,
    claim_raw_sha256: registerClaim.claimRawSha256
  })
  expect(confirmClaim.document.predecessor_claim_raw_sha256).toBe(
    registerClaim.claimRawSha256
  )
  expect(adjudicate.document.predecessor).toEqual({
    stage: "CONFIRM",
    manifest_raw_sha256: confirm.manifestRawSha256,
    claim_raw_sha256: confirmClaim.claimRawSha256
  })
  expect(adjudicateClaim.document.predecessor_claim_raw_sha256).toBe(
    confirmClaim.claimRawSha256
  )
  expect(rightOrThrow(validateBuiltEnvelope(confirm)).document.stage).toBe(
    "CONFIRM"
  )
  expect(rightOrThrow(validateBuiltEnvelope(adjudicate)).document.stage).toBe(
    "ADJUDICATE"
  )

  expectLeftReason(
    buildS2SEvidenceEnvelope(
      makeInput({
        predecessor: {
          stage: "REGISTER",
          manifestRawSha256: "1".repeat(64),
          claimRawSha256: "2".repeat(64)
        }
      })
    ),
    "PREDECESSOR_INVALID"
  )
  expectLeftReason(
    buildS2SEvidenceEnvelope(
      makeInput({ stage: "CONFIRM", predecessor: null })
    ),
    "PREDECESSOR_INVALID"
  )
  expectLeftReason(
    buildS2SEvidenceEnvelope(
      makeInput({
        stage: "ADJUDICATE",
        predecessor: {
          stage: "REGISTER",
          manifestRawSha256: "1".repeat(64),
          claimRawSha256: "2".repeat(64)
        }
      })
    ),
    "PREDECESSOR_INVALID"
  )
})

it("defensively snapshots builder, validator, envelope, attachment, and claim data", () => {
  const input = makeInput() as unknown as {
    attachments: Array<{
      logicalName: string
      bytes: Uint8Array
    }>
  }
  const envelope = rightOrThrow(
    buildS2SEvidenceEnvelope(input as unknown as S2SEvidenceEnvelopeInput)
  )
  input.attachments[0]!.logicalName = "counterfeit.bin"
  input.attachments[0]!.bytes.fill(0xaa)
  input.attachments.length = 0

  expect(UTF8_DECODER.decode(envelope.canonicalBytes)).toBe(GOLDEN_MANIFEST)
  expect(envelope.attachments).toHaveLength(2)
  expect(Object.isFrozen(envelope)).toBe(true)
  expect(Object.isFrozen(envelope.attachments)).toBe(true)
  expect(Object.isFrozen(envelope.attachments[0])).toBe(true)

  const leakedManifest = envelope.canonicalBytes
  const leakedDocument = envelope.document as unknown as {
    attachments: Array<{ logical_name: string }>
  }
  const leakedAttachments = envelope.attachments
  const leakedDescriptor = leakedAttachments[0]!.descriptor as unknown as {
    logical_name: string
  }
  const leakedPayload = leakedAttachments[0]!.readBytes()
  leakedManifest.fill(0)
  leakedDocument.attachments[0]!.logical_name = "forged.json"
  leakedDescriptor.logical_name = "forged-again.json"
  leakedPayload.fill(0)

  expect(UTF8_DECODER.decode(envelope.canonicalBytes)).toBe(GOLDEN_MANIFEST)
  expect(envelope.document.attachments[0]!.logical_name).toBe(
    "evidence/control.json"
  )
  expect(envelope.attachments[0]!.descriptor.logical_name).toBe(
    "evidence/control.json"
  )
  expect(envelope.attachments[0]!.readBytes()).toEqual(
    UTF8_ENCODER.encode('{"ok":true}\n')
  )

  const manifestInput = envelope.canonicalBytes
  const attachmentInputs = validationAttachments(envelope)
  const validated = rightOrThrow(
    validateS2SEvidenceEnvelope({
      manifestBytes: manifestInput,
      attachments: attachmentInputs
    })
  )
  manifestInput.fill(0)
  attachmentInputs[0]!.bytes.fill(0)
  attachmentInputs.length = 0
  expect(UTF8_DECODER.decode(validated.canonicalBytes)).toBe(GOLDEN_MANIFEST)
  expect(validated.attachments[0]!.readBytes()).toEqual(
    UTF8_ENCODER.encode('{"ok":true}\n')
  )

  const claim = rightOrThrow(buildS2SEvidenceClaim(envelope))
  const leakedClaim = claim.canonicalBytes
  const leakedClaimDocument = claim.document as unknown as { stage: string }
  leakedClaim.fill(0)
  leakedClaimDocument.stage = "CONFIRM"
  expect(UTF8_DECODER.decode(claim.canonicalBytes)).toBe(GOLDEN_CLAIM)
  expect(claim.document.stage).toBe("REGISTER")
  expect(Object.isFrozen(claim)).toBe(true)
})

it("rejects excess shape, duplicate names or roles, and an excessive roster", () => {
  const excessRoot = {
    ...makeInput(),
    untrusted: true
  } as unknown as S2SEvidenceEnvelopeInput
  expectLeftReason(
    buildS2SEvidenceEnvelope(excessRoot),
    "ENVELOPE_IDENTITY_INVALID"
  )

  const attachments = makeAttachments()
  const excessAttachment = {
    ...attachments[0]!,
    untrusted: true
  } as unknown as S2SEvidenceAttachmentInput
  expectLeftReason(
    buildS2SEvidenceEnvelope(
      makeInput({ attachments: [excessAttachment, attachments[1]!] })
    ),
    "ATTACHMENT_DESCRIPTOR_INVALID"
  )

  expectLeftReason(
    buildS2SEvidenceEnvelope(
      makeInput({
        attachments: [
          attachments[0]!,
          { ...attachments[1]!, logicalName: attachments[0]!.logicalName }
        ]
      })
    ),
    "ATTACHMENT_SET_INVALID"
  )
  expectLeftReason(
    buildS2SEvidenceEnvelope(
      makeInput({
        attachments: [
          attachments[0]!,
          { ...attachments[1]!, role: attachments[0]!.role }
        ]
      })
    ),
    "ATTACHMENT_SET_INVALID"
  )

  const excessive = Array.from(
    { length: S2S_EVIDENCE_ENVELOPE_MAX_ATTACHMENTS + 1 },
    (_, index): S2SEvidenceAttachmentInput => ({
      logicalName: `bulk/${String(index).padStart(3, "0")}.bin`,
      role: `ROLE_${index}`,
      schemaVersion: null,
      mediaType: "application/octet-stream",
      bytes: Uint8Array.of(index + 1)
    })
  )
  expectLeftReason(
    buildS2SEvidenceEnvelope(makeInput({ attachments: excessive })),
    "ENVELOPE_IDENTITY_INVALID"
  )
})

it("rejects rehashed manifest order, path, count, and declared-size counterfeits", () => {
  const envelope = buildEnvelope()
  const supplied = validationAttachments(envelope)

  const unordered = parseRecord(envelope.canonicalBytes)
  requiredAttachments(unordered).reverse()
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: withSelfHash(unordered, "manifest_receipt_sha256"),
      attachments: supplied
    }),
    "ATTACHMENT_ORDER_INVALID"
  )

  const unsafeName = parseRecord(envelope.canonicalBytes)
  requiredAttachments(unsafeName)[0]!["logical_name"] = "safe/../escape.json"
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: withSelfHash(unsafeName, "manifest_receipt_sha256"),
      attachments: supplied
    }),
    "ATTACHMENT_DESCRIPTOR_INVALID"
  )

  const wrongCount = parseRecord(envelope.canonicalBytes)
  wrongCount["attachment_count"] = 1
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: withSelfHash(wrongCount, "manifest_receipt_sha256"),
      attachments: supplied
    }),
    "ATTACHMENT_SET_INVALID"
  )

  const wrongTotal = parseRecord(envelope.canonicalBytes)
  wrongTotal["attachment_total_bytes"] = 15
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: withSelfHash(wrongTotal, "manifest_receipt_sha256"),
      attachments: supplied
    }),
    "ATTACHMENT_SIZE_INVALID"
  )

  const wrongDescriptorSize = parseRecord(envelope.canonicalBytes)
  requiredAttachments(wrongDescriptorSize)[0]!["byte_length"] = 13
  wrongDescriptorSize["attachment_total_bytes"] = 17
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: withSelfHash(
        wrongDescriptorSize,
        "manifest_receipt_sha256"
      ),
      attachments: supplied
    }),
    "ATTACHMENT_HASH_MISMATCH"
  )
})

it("rejects missing, extra, duplicate, hash-drifted, and size-drifted payloads", () => {
  const envelope = buildEnvelope()
  const supplied = validationAttachments(envelope)

  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: envelope.canonicalBytes,
      attachments: supplied.slice(1)
    }),
    "ATTACHMENT_SET_INVALID"
  )

  const extraBytes = UTF8_ENCODER.encode("unreferenced\n")
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: envelope.canonicalBytes,
      attachments: [
        ...supplied,
        { rawSha256: rawS2SFileSha256(extraBytes), bytes: extraBytes }
      ]
    }),
    "ATTACHMENT_SET_INVALID"
  )

  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: envelope.canonicalBytes,
      attachments: [...supplied, supplied[0]!]
    }),
    "ATTACHMENT_SET_INVALID"
  )

  const sameSizeDrift = validationAttachments(envelope)
  sameSizeDrift[0] = {
    rawSha256: sameSizeDrift[0]!.rawSha256,
    bytes: UTF8_ENCODER.encode('{"no":true}\n')
  }
  expect(sameSizeDrift[0]!.bytes.byteLength).toBe(supplied[0]!.bytes.byteLength)
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: envelope.canonicalBytes,
      attachments: sameSizeDrift
    }),
    "ATTACHMENT_HASH_MISMATCH"
  )

  const differentSizeDrift = validationAttachments(envelope)
  differentSizeDrift[0] = {
    rawSha256: differentSizeDrift[0]!.rawSha256,
    bytes: UTF8_ENCODER.encode("short\n")
  }
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: envelope.canonicalBytes,
      attachments: differentSizeDrift
    }),
    "ATTACHMENT_HASH_MISMATCH"
  )
})

it("distinguishes noncanonical, unparsable, schema-invalid, and self-hash drift", () => {
  const envelope = buildEnvelope()
  const supplied = validationAttachments(envelope)
  const document = parseRecord(envelope.canonicalBytes)

  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: UTF8_ENCODER.encode(`${JSON.stringify(document, null, 2)}\n`),
      attachments: supplied
    }),
    "CANONICAL_BYTES_DRIFT"
  )
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: envelope.canonicalBytes.subarray(
        0,
        envelope.canonicalBytes.byteLength - 1
      ),
      attachments: supplied
    }),
    "CANONICAL_BYTES_DRIFT"
  )
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: UTF8_ENCODER.encode("{not-json}\n"),
      attachments: supplied
    }),
    "DOCUMENT_PARSE_FAILED"
  )

  const excess = parseRecord(envelope.canonicalBytes)
  excess["counterfeit"] = true
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: encodeCanonical(excess),
      attachments: supplied
    }),
    "DOCUMENT_SCHEMA_REJECTED"
  )

  const receiptDrift = parseRecord(envelope.canonicalBytes)
  receiptDrift["manifest_receipt_sha256"] = "0".repeat(64)
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: encodeCanonical(receiptDrift),
      attachments: supplied
    }),
    "SELF_HASH_MISMATCH"
  )

  const coreDrift = parseRecord(envelope.canonicalBytes)
  coreDrift["current_job_database_id"] = 7_099
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: encodeCanonical(coreDrift),
      attachments: supplied
    }),
    "SELF_HASH_MISMATCH"
  )
})

it("rejects counterfeit envelope identity and workflow traversal", () => {
  expectLeftReason(
    buildS2SEvidenceEnvelope(
      makeInput({ registrationCommitB: SOURCE_COMMIT_A })
    ),
    "ENVELOPE_IDENTITY_INVALID"
  )
  expectLeftReason(
    buildS2SEvidenceEnvelope(
      makeInput({ workflowApiPath: ".github/workflows/../counterfeit.yml" })
    ),
    "DOCUMENT_SCHEMA_REJECTED"
  )

  const envelope = buildEnvelope()
  const supplied = validationAttachments(envelope)
  const wrongHead = parseRecord(envelope.canonicalBytes)
  wrongHead["workflow_head_sha"] = "e".repeat(40)
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: withSelfHash(wrongHead, "manifest_receipt_sha256"),
      attachments: supplied
    }),
    "ENVELOPE_IDENTITY_INVALID"
  )

  const pathTraversal = parseRecord(envelope.canonicalBytes)
  pathTraversal["workflow_api_path"] = ".github/workflows/../counterfeit.yml"
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: withSelfHash(pathTraversal, "manifest_receipt_sha256"),
      attachments: supplied
    }),
    "DOCUMENT_SCHEMA_REJECTED"
  )
})

it("rejects malformed claims, invalid predecessor shape, and forged envelopes", () => {
  const register = buildEnvelope()
  const registerClaim = rightOrThrow(buildS2SEvidenceClaim(register))

  const receiptDrift = parseRecord(registerClaim.canonicalBytes)
  receiptDrift["claim_receipt_sha256"] = "0".repeat(64)
  expectLeftReason(
    validateS2SEvidenceClaim(encodeCanonical(receiptDrift)),
    "SELF_HASH_MISMATCH"
  )
  expectLeftReason(
    validateS2SEvidenceClaim(
      UTF8_ENCODER.encode(
        `${JSON.stringify(parseRecord(registerClaim.canonicalBytes), null, 2)}\n`
      )
    ),
    "CANONICAL_BYTES_DRIFT"
  )

  const registerWithPredecessor = parseRecord(registerClaim.canonicalBytes)
  registerWithPredecessor["predecessor_claim_raw_sha256"] = "1".repeat(64)
  expectLeftReason(
    validateS2SEvidenceClaim(
      withSelfHash(registerWithPredecessor, "claim_receipt_sha256")
    ),
    "PREDECESSOR_INVALID"
  )

  const confirm = buildEnvelope({
    stage: "CONFIRM",
    currentJobDatabaseId: 7_002,
    predecessor: {
      stage: "REGISTER",
      manifestRawSha256: register.manifestRawSha256,
      claimRawSha256: registerClaim.claimRawSha256
    }
  })
  const confirmClaim = rightOrThrow(buildS2SEvidenceClaim(confirm))
  expectLeftReason(
    validateS2SEvidenceClaimForEnvelope(
      registerClaim.canonicalBytes,
      confirm
    ),
    "CLAIM_IDENTITY_MISMATCH"
  )
  const confirmWithoutPredecessor = parseRecord(confirmClaim.canonicalBytes)
  confirmWithoutPredecessor["predecessor_claim_raw_sha256"] = null
  expectLeftReason(
    validateS2SEvidenceClaim(
      withSelfHash(confirmWithoutPredecessor, "claim_receipt_sha256")
    ),
    "PREDECESSOR_INVALID"
  )

  const forged = {
    document: register.document,
    canonicalBytes: register.canonicalBytes,
    manifestRawSha256: "f".repeat(64),
    attachments: register.attachments
  } as unknown as S2SEvidenceEnvelopeSnapshot
  expectLeftReason(buildS2SEvidenceClaim(forged), "CLAIM_IDENTITY_MISMATCH")

  const hostile = new Proxy(register, {
    get: () => {
      throw new Error("hostile envelope getter")
    }
  })
  let hostileOutcome:
    | ReturnType<typeof buildS2SEvidenceClaim>
    | undefined
  expect(() => {
    hostileOutcome = buildS2SEvidenceClaim(hostile)
  }).not.toThrow()
  if (hostileOutcome === undefined) throw new Error("claim builder did not return")
  expectLeftReason(hostileOutcome, "CLAIM_IDENTITY_MISMATCH")
})

it("fails closed on exotic records, byte views, shared memory, and traps", () => {
  class CounterfeitRoot {
    sourceCommitA = SOURCE_COMMIT_A
    registrationCommitB = REGISTRATION_COMMIT_B
    workflowRunId = WORKFLOW_RUN_ID
    workflowRunCreatedAtUnixSeconds = WORKFLOW_CREATED_AT_UNIX_SECONDS
    workflowApiPath = WORKFLOW_API_PATH
    workflowFileSha256 = WORKFLOW_FILE_SHA256
    workflowContractSha256 = WORKFLOW_CONTRACT_SHA256
    stage: S2SEvidenceStage = "REGISTER"
    currentJobDatabaseId = 7_001
    predecessor = null
    attachments = makeAttachments()
  }
  expectLeftReason(
    buildS2SEvidenceEnvelope(
      new CounterfeitRoot() as unknown as S2SEvidenceEnvelopeInput
    ),
    "ENVELOPE_IDENTITY_INVALID"
  )

  const accessorRoot = makeInput()
  Object.defineProperty(accessorRoot, "stage", {
    enumerable: true,
    configurable: true,
    get: () => "REGISTER"
  })
  expectLeftReason(
    buildS2SEvidenceEnvelope(accessorRoot),
    "ENVELOPE_IDENTITY_INVALID"
  )

  const trappedRoot = new Proxy(makeInput(), {
    ownKeys: () => {
      throw new Error("hostile root ownKeys")
    }
  })
  expect(() => buildS2SEvidenceEnvelope(trappedRoot)).not.toThrow()
  expectLeftReason(
    buildS2SEvidenceEnvelope(trappedRoot),
    "ENVELOPE_IDENTITY_INVALID"
  )

  class CounterfeitAttachment {
    logicalName = "counterfeit.bin"
    role = "COUNTERFEIT"
    schemaVersion = null
    mediaType = "application/octet-stream" as const
    bytes = Uint8Array.of(1)
  }
  expectLeftReason(
    buildS2SEvidenceEnvelope(
      makeInput({
        attachments: [
          new CounterfeitAttachment() as unknown as S2SEvidenceAttachmentInput
        ]
      })
    ),
    "ATTACHMENT_DESCRIPTOR_INVALID"
  )

  const accessorAttachment = makeAttachments()[0]!
  Object.defineProperty(accessorAttachment, "role", {
    enumerable: true,
    configurable: true,
    get: () => "NUMERIC_OUTPUT"
  })
  expectLeftReason(
    buildS2SEvidenceEnvelope(
      makeInput({ attachments: [accessorAttachment] })
    ),
    "ATTACHMENT_DESCRIPTOR_INVALID"
  )

  for (const exoticBytes of [
    (() => {
      const value = Uint8Array.of(1)
      Object.defineProperty(value, Symbol.iterator, {
        value: Uint8Array.prototype[Symbol.iterator]
      })
      return value
    })(),
    (() => {
      const value = Uint8Array.of(1)
      Object.defineProperty(value, "buffer", { value: value.buffer })
      return value
    })(),
    new (class extends Uint8Array {})(1)
  ]) {
    expectLeftReason(
      buildS2SEvidenceEnvelope(
        makeInput({
          attachments: [
            {
              logicalName: "counterfeit.bin",
              role: "COUNTERFEIT",
              schemaVersion: null,
              mediaType: "application/octet-stream",
              bytes: exoticBytes
            }
          ]
        })
      ),
      "ATTACHMENT_BYTES_INVALID"
    )
  }

  if (typeof SharedArrayBuffer !== "undefined") {
    const shared = new Uint8Array(new SharedArrayBuffer(1))
    shared[0] = 1
    expectLeftReason(
      buildS2SEvidenceEnvelope(
        makeInput({
          attachments: [
            {
              logicalName: "shared.bin",
              role: "SHARED",
              schemaVersion: null,
              mediaType: "application/octet-stream",
              bytes: shared
            }
          ]
        })
      ),
      "ATTACHMENT_BYTES_INVALID"
    )
  }

  const envelope = buildEnvelope()
  const trappedManifest = new Proxy(envelope.canonicalBytes, {})
  expect(() =>
    validateS2SEvidenceEnvelope({
      manifestBytes: trappedManifest,
      attachments: validationAttachments(envelope)
    })
  ).not.toThrow()
  expectLeftReason(
    validateS2SEvidenceEnvelope({
      manifestBytes: trappedManifest,
      attachments: validationAttachments(envelope)
    }),
    "MANIFEST_SIZE_INVALID"
  )

  const trappedValidation = new Proxy(
    {
      manifestBytes: envelope.canonicalBytes,
      attachments: validationAttachments(envelope)
    },
    {
      ownKeys: () => {
        throw new Error("hostile validation ownKeys")
      }
    }
  )
  expect(() => validateS2SEvidenceEnvelope(trappedValidation)).not.toThrow()
  expectLeftReason(
    validateS2SEvidenceEnvelope(trappedValidation),
    "ATTACHMENT_SET_INVALID"
  )
})
