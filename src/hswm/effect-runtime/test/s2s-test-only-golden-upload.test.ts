import { Either } from "effect"
import { describe, expect, it } from "vitest"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS,
  S2S_TEST_ONLY_GOLDEN_POSTCONDITION_ARCHIVE_MAX_BYTES,
  S2S_TEST_ONLY_GOLDEN_POSTCONDITION_MEMBER_NAME,
  S2S_TEST_ONLY_GOLDEN_UPLOAD_POSTCONDITION_SCHEMA_VERSION,
  S2STestOnlyGoldenUploadError,
  buildS2STestOnlyGoldenArtifact,
  buildS2STestOnlyGoldenUploadPostcondition,
  reconstructS2STestOnlyGoldenUploadPostcondition,
  validateS2STestOnlyGoldenArtifactReadback,
  type S2STestOnlyGoldenUploadPostconditionDocument
} from "../src/s2s-test-only-golden-upload.js"
import { buildS2SStoredZip } from "../src/s2s-zip.js"

const encoder = new TextEncoder()

const right = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw value.left
  return value.right
}

const candidateBytes = (): Uint8Array =>
  encoder.encode(
    '{"schema_version":"hswm-swm0w-s2s-numeric-candidate/v1","value":1}\n'
  )

const adjudicationBytes = (): Uint8Array =>
  encoder.encode(
    '{"schema_version":"hswm-swm0w-s2s-numeric-adjudication/v1","value":1}\n'
  )

const candidateArtifact = () =>
  right(
    buildS2STestOnlyGoldenArtifact("GOLDEN_CANDIDATE", [
      { name: "numeric_candidate.json", bytes: candidateBytes() }
    ])
  )

const candidateBinding = (archiveBytes: Uint8Array) => ({
  role: "GOLDEN_CANDIDATE",
  publicationKey: "s2s-test-only-golden-candidate.zip",
  publicationDisposition: "CREATED",
  archiveBytes,
  readbackBytes: Uint8Array.from(archiveBytes)
})

const expectUploadReason = (
  value: Either.Either<unknown, unknown>,
  reason: S2STestOnlyGoldenUploadError["reason"]
): void => {
  expect(Either.isLeft(value)).toBe(true)
  if (Either.isRight(value)) throw new Error("expected a typed upload failure")
  expect(value.left).toBeInstanceOf(S2STestOnlyGoldenUploadError)
  if (!(value.left instanceof S2STestOnlyGoldenUploadError)) {
    throw value.left
  }
  expect(value.left.reason).toBe(reason)
}

const coreFromDocument = (
  document: S2STestOnlyGoldenUploadPostconditionDocument
): Readonly<Record<string, unknown>> => ({
  schema_version: document.schema_version,
  classification: document.classification,
  origin: document.origin,
  role: document.role,
  publication_key: document.publication_key,
  publication_disposition: document.publication_disposition,
  archive_raw_sha256: document.archive_raw_sha256,
  archive_byte_length: document.archive_byte_length,
  readback_raw_sha256: document.readback_raw_sha256,
  readback_byte_length: document.readback_byte_length,
  archive_readback_bytes_equal: document.archive_readback_bytes_equal,
  members: document.members.map((member) => ({ ...member }))
})

const withReceipt = (
  core: Readonly<Record<string, unknown>>
): Readonly<Record<string, unknown>> => ({
  ...core,
  receipt_sha256: right(canonicalS2SControlSha256(core))
})

const postconditionZip = (document: unknown): Uint8Array => {
  const bytes = right(canonicalS2SControlJsonBytes(document))
  return right(
    buildS2SStoredZip([
      { name: S2S_TEST_ONLY_GOLDEN_POSTCONDITION_MEMBER_NAME, bytes }
    ])
  ).readArchiveBytes()
}

describe("test-only golden upload pure contract", () => {
  it("freezes distinct fixed roles, keys, singleton rosters, and caps", () => {
    expect(S2S_TEST_ONLY_GOLDEN_ARTIFACT_SPECS).toEqual({
      GOLDEN_CANDIDATE: {
        publicationKey: "s2s-test-only-golden-candidate.zip",
        postconditionPublicationKey:
          "s2s-test-only-golden-candidate-upload-postcondition.zip",
        memberName: "numeric_candidate.json",
        memberMaximumBytes: 60 * 1_048_576,
        archiveMaximumBytes: 64 * 1_048_576,
        expandedMaximumBytes: 60 * 1_048_576
      },
      GOLDEN_ADJUDICATION: {
        publicationKey: "s2s-test-only-golden-adjudication.zip",
        postconditionPublicationKey:
          "s2s-test-only-golden-adjudication-upload-postcondition.zip",
        memberName: "numeric_adjudication.json",
        memberMaximumBytes: 3 * 1_048_576,
        archiveMaximumBytes: 4 * 1_048_576,
        expandedMaximumBytes: 3 * 1_048_576
      }
    })
  })

  it("builds deterministic singleton archives and returns defensive snapshots", () => {
    const candidateInput = candidateBytes()
    const first = right(
      buildS2STestOnlyGoldenArtifact("GOLDEN_CANDIDATE", [
        { name: "numeric_candidate.json", bytes: candidateInput }
      ])
    )
    const second = candidateArtifact()
    expect(first.readArchiveBytes()).toEqual(second.readArchiveBytes())
    expect(first.archiveRawSha256).toBe(
      rawS2SFileSha256(first.readArchiveBytes())
    )
    expect(first.members).toHaveLength(1)
    expect(first.members[0].name).toBe("numeric_candidate.json")
    expect(first.members[0].readBytes()).toEqual(candidateInput)

    const expectedArchive = first.readArchiveBytes()
    candidateInput.fill(0)
    const exposedArchive = first.readArchiveBytes()
    const exposedMember = first.members[0].readBytes()
    exposedArchive.fill(0)
    exposedMember.fill(0)
    expect(first.readArchiveBytes()).toEqual(expectedArchive)
    expect(first.members[0].readBytes()).toEqual(candidateBytes())

    const adjudication = right(
      buildS2STestOnlyGoldenArtifact("GOLDEN_ADJUDICATION", [
        { name: "numeric_adjudication.json", bytes: adjudicationBytes() }
      ])
    )
    expect(adjudication.members[0].name).toBe("numeric_adjudication.json")
  })

  it("rejects hostile, excess, cross-role, empty, and over-cap member input", () => {
    let accessorReads = 0
    const accessorMember: Record<string, unknown> = Object.create(null)
    Object.defineProperties(accessorMember, {
      name: { enumerable: true, value: "numeric_candidate.json" },
      bytes: {
        enumerable: true,
        get: () => {
          accessorReads += 1
          return candidateBytes()
        }
      }
    })
    const hostileArray = new Proxy(
      [{ name: "numeric_candidate.json", bytes: candidateBytes() }],
      {}
    )
    class ExoticBytes extends Uint8Array {}

    expectUploadReason(
      buildS2STestOnlyGoldenArtifact("CANDIDATE", []),
      "ROLE_INVALID"
    )
    expectUploadReason(
      buildS2STestOnlyGoldenArtifact("GOLDEN_CANDIDATE", []),
      "MEMBER_ROSTER_MISMATCH"
    )
    expectUploadReason(
      buildS2STestOnlyGoldenArtifact("GOLDEN_CANDIDATE", [
        { name: "numeric_adjudication.json", bytes: candidateBytes() }
      ]),
      "MEMBER_ROSTER_MISMATCH"
    )
    expectUploadReason(
      buildS2STestOnlyGoldenArtifact("GOLDEN_CANDIDATE", [
        {
          name: "numeric_candidate.json",
          bytes: candidateBytes(),
          extra: true
        }
      ]),
      "INPUT_INVALID"
    )
    expectUploadReason(
      buildS2STestOnlyGoldenArtifact("GOLDEN_CANDIDATE", hostileArray),
      "INPUT_INVALID"
    )
    expectUploadReason(
      buildS2STestOnlyGoldenArtifact("GOLDEN_CANDIDATE", [accessorMember]),
      "INPUT_INVALID"
    )
    expect(accessorReads).toBe(0)
    expectUploadReason(
      buildS2STestOnlyGoldenArtifact("GOLDEN_CANDIDATE", [
        {
          name: "numeric_candidate.json",
          bytes: new ExoticBytes(candidateBytes())
        }
      ]),
      "INPUT_INVALID"
    )
    expectUploadReason(
      buildS2STestOnlyGoldenArtifact("GOLDEN_ADJUDICATION", [
        {
          name: "numeric_adjudication.json",
          bytes: new Uint8Array(3 * 1_048_576 + 1)
        }
      ]),
      "INPUT_INVALID"
    )
  })

  it("revalidates independent archive and member bytes, not only metadata", () => {
    const artifact = candidateArtifact()
    const archiveBytes = artifact.readArchiveBytes()
    const validated = right(
      validateS2STestOnlyGoldenArtifactReadback(
        "GOLDEN_CANDIDATE",
        archiveBytes,
        Uint8Array.from(archiveBytes)
      )
    )
    expect(validated.archiveReadbackBytesEqual).toBe(true)
    expect(validated.members[0].readBytes()).toEqual(candidateBytes())

    const differentValidArchive = right(
      buildS2SStoredZip([
        {
          name: "numeric_candidate.json",
          bytes: encoder.encode(
            '{"schema_version":"hswm-swm0w-s2s-numeric-candidate/v1","value":2}\n'
          )
        }
      ])
    ).readArchiveBytes()
    expectUploadReason(
      validateS2STestOnlyGoldenArtifactReadback(
        "GOLDEN_CANDIDATE",
        archiveBytes,
        differentValidArchive
      ),
      "ARCHIVE_READBACK_MISMATCH"
    )
  })

  it("builds and reconstructs one canonical self-hashed postcondition ZIP", () => {
    const artifact = candidateArtifact()
    const archiveBytes = artifact.readArchiveBytes()
    const binding = candidateBinding(archiveBytes)
    const built = right(buildS2STestOnlyGoldenUploadPostcondition(binding))
    const document = built.document
    expect(document).toMatchObject({
      schema_version:
        S2S_TEST_ONLY_GOLDEN_UPLOAD_POSTCONDITION_SCHEMA_VERSION,
      classification: "TEST_ONLY_NON_AUTHORIZING",
      origin: "LOCAL_TEST_LAYER",
      role: "GOLDEN_CANDIDATE",
      publication_key: "s2s-test-only-golden-candidate.zip",
      publication_disposition: "CREATED",
      archive_raw_sha256: artifact.archiveRawSha256,
      archive_byte_length: artifact.archiveByteLength,
      readback_raw_sha256: artifact.archiveRawSha256,
      readback_byte_length: artifact.archiveByteLength,
      archive_readback_bytes_equal: true,
      members: [
        {
          name: "numeric_candidate.json",
          raw_bytes_sha256: artifact.members[0].rawBytesSha256,
          byte_length: artifact.members[0].byteLength
        }
      ]
    })
    expect(document.receipt_sha256).toBe(
      right(canonicalS2SControlSha256(coreFromDocument(document)))
    )
    expect(built.documentRawSha256).toBe(
      rawS2SFileSha256(built.readDocumentBytes())
    )
    expect(built.archiveRawSha256).toBe(
      rawS2SFileSha256(built.readArchiveBytes())
    )

    const reconstructed = right(
      reconstructS2STestOnlyGoldenUploadPostcondition(
        built.readArchiveBytes(),
        binding
      )
    )
    expect(reconstructed.document).toEqual(document)
    const exposed = reconstructed.readDocumentBytes()
    exposed.fill(0)
    expect(reconstructed.readDocumentBytes()).toEqual(built.readDocumentBytes())
  })

  it("rejects hostile, excess, wrong-key, and non-created bindings", () => {
    const archiveBytes = candidateArtifact().readArchiveBytes()
    const binding = candidateBinding(archiveBytes)
    let accessorReads = 0
    const accessorBinding: Record<string, unknown> = Object.create(null)
    Object.defineProperties(accessorBinding, {
      role: { enumerable: true, value: binding.role },
      publicationKey: { enumerable: true, value: binding.publicationKey },
      publicationDisposition: {
        enumerable: true,
        value: binding.publicationDisposition
      },
      archiveBytes: { enumerable: true, value: binding.archiveBytes },
      readbackBytes: {
        enumerable: true,
        get: () => {
          accessorReads += 1
          return binding.readbackBytes
        }
      }
    })

    expectUploadReason(
      buildS2STestOnlyGoldenUploadPostcondition({
        ...binding,
        publicationKey: "s2s-test-only-golden-adjudication.zip"
      }),
      "PUBLICATION_KEY_MISMATCH"
    )
    expectUploadReason(
      buildS2STestOnlyGoldenUploadPostcondition({
        ...binding,
        publicationDisposition: "ALREADY_PRESENT"
      }),
      "PUBLICATION_DISPOSITION_INVALID"
    )
    expectUploadReason(
      buildS2STestOnlyGoldenUploadPostcondition({ ...binding, extra: true }),
      "INPUT_INVALID"
    )
    expectUploadReason(
      buildS2STestOnlyGoldenUploadPostcondition(accessorBinding),
      "INPUT_INVALID"
    )
    expect(accessorReads).toBe(0)
  })

  it("rejects schema, canonical-byte, self-hash, and recomputed cross-binding mutations", () => {
    const artifact = candidateArtifact()
    const binding = candidateBinding(artifact.readArchiveBytes())
    const built = right(buildS2STestOnlyGoldenUploadPostcondition(binding))
    const document = built.document

    const extraProperty = postconditionZip({ ...document, extra: true })
    expectUploadReason(
      reconstructS2STestOnlyGoldenUploadPostcondition(extraProperty, binding),
      "POSTCONDITION_SCHEMA_REJECTED"
    )

    const prettyBytes = encoder.encode(`${JSON.stringify(document, null, 2)}\n`)
    const prettyZip = right(
      buildS2SStoredZip([
        {
          name: S2S_TEST_ONLY_GOLDEN_POSTCONDITION_MEMBER_NAME,
          bytes: prettyBytes
        }
      ])
    ).readArchiveBytes()
    expectUploadReason(
      reconstructS2STestOnlyGoldenUploadPostcondition(prettyZip, binding),
      "POSTCONDITION_NOT_CANONICAL"
    )

    const badReceipt = postconditionZip({
      ...document,
      receipt_sha256: "0".repeat(64)
    })
    expectUploadReason(
      reconstructS2STestOnlyGoldenUploadPostcondition(badReceipt, binding),
      "RECEIPT_HASH_MISMATCH"
    )

    const changedLengthsCore = {
      ...coreFromDocument(document),
      archive_byte_length: document.archive_byte_length + 1,
      readback_byte_length: document.readback_byte_length + 1
    }
    expectUploadReason(
      reconstructS2STestOnlyGoldenUploadPostcondition(
        postconditionZip(withReceipt(changedLengthsCore)),
        binding
      ),
      "CROSS_BINDING_MISMATCH"
    )

    const crossRoleCore = {
      ...coreFromDocument(document),
      role: "GOLDEN_ADJUDICATION",
      publication_key: "s2s-test-only-golden-adjudication.zip",
      members: [
        {
          ...document.members[0],
          name: "numeric_adjudication.json"
        }
      ]
    }
    expectUploadReason(
      reconstructS2STestOnlyGoldenUploadPostcondition(
        postconditionZip(withReceipt(crossRoleCore)),
        binding
      ),
      "CROSS_BINDING_MISMATCH"
    )

    const changedMemberCore = {
      ...coreFromDocument(document),
      members: [
        {
          ...document.members[0],
          raw_bytes_sha256: "f".repeat(64)
        }
      ]
    }
    expectUploadReason(
      reconstructS2STestOnlyGoldenUploadPostcondition(
        postconditionZip(withReceipt(changedMemberCore)),
        binding
      ),
      "CROSS_BINDING_MISMATCH"
    )
  })

  it("rejects valid but non-deterministic ZIP metadata and over-cap input", () => {
    const artifact = candidateArtifact()
    const binding = candidateBinding(artifact.readArchiveBytes())
    const built = right(buildS2STestOnlyGoldenUploadPostcondition(binding))
    const alternate = built.readArchiveBytes()
    const view = new DataView(
      alternate.buffer,
      alternate.byteOffset,
      alternate.byteLength
    )
    const endOffset = alternate.byteLength - 22
    const centralOffset = view.getUint32(endOffset + 16, true)
    view.setUint16(10, 1, true)
    view.setUint16(centralOffset + 12, 1, true)
    expectUploadReason(
      reconstructS2STestOnlyGoldenUploadPostcondition(alternate, binding),
      "ARCHIVE_NOT_DETERMINISTIC"
    )
    expectUploadReason(
      reconstructS2STestOnlyGoldenUploadPostcondition(
        new Uint8Array(
          S2S_TEST_ONLY_GOLDEN_POSTCONDITION_ARCHIVE_MAX_BYTES + 1
        ),
        binding
      ),
      "INPUT_INVALID"
    )
  })
})
