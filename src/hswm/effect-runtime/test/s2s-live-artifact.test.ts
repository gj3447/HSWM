import { expect, it } from "@effect/vitest"
import { Effect, Either, Layer } from "effect"

import {
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  S2SArtifactAuthority,
  makeS2SArtifactAuthorityTestLayer,
  type S2SObservedArtifactAuthority
} from "../src/s2s-live-artifact.js"
import {
  S2S_GITHUB_API_VERSION,
  S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
  S2S_GITHUB_REPOSITORY,
  S2SGitHubObservationError,
  S2SGitHubObserver,
  observeS2SGitHubArtifact,
  observeS2SGitHubRunArtifacts,
  observeS2SGitHubWorkflowAttemptJobs,
  observeS2SGitHubWorkflowRun,
  type S2SGitHubArtifactDownload,
  type S2SGitHubArtifactDownloadReceipt,
  type S2SGitHubArtifactProjection,
  type S2SGitHubArtifactsProjection,
  type S2SGitHubObservation,
  type S2SGitHubWorkflowJobsProjection,
  type S2SGitHubWorkflowRunProjection
} from "../src/s2s-live-github.js"

const RUN_ID = 32_442_437_970
const JOB_ID = 96_655_652_099
const ARTIFACT_ID = 9_433_344_546
const HEAD_SHA = "75686549b1f6c65aea87ebd0f912a6e62909445a"
const OBSERVED_AT = 1_787_283_300
const encoder = new TextEncoder()

const responseProvenance = (suffix: number | string) => Object.freeze({
  githubRequestId: `A1B2:C3D4:E5F6:${suffix}`,
  githubApiVersionSelected: S2S_GITHUB_API_VERSION,
  responseEtag: `W/"${"e".repeat(64)}"`
})

interface ZipMember {
  readonly name: string
  readonly bytes: Uint8Array
}

const crcTable = (): Uint32Array => {
  const table = new Uint32Array(256)
  for (let index = 0; index < table.length; index += 1) {
    let value = index
    for (let bit = 0; bit < 8; bit += 1) {
      value = (value & 1) === 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1
    }
    table[index] = value >>> 0
  }
  return table
}

const CRC_TABLE = crcTable()

const crc32 = (bytes: Uint8Array): number => {
  let value = 0xffffffff
  for (const byte of bytes) {
    const next = CRC_TABLE[(value ^ byte) & 0xff]
    if (next === undefined) throw new Error("CRC table entry missing")
    value = next ^ (value >>> 8)
  }
  return (value ^ 0xffffffff) >>> 0
}

const buildStoredArtifactZip = (
  members: ReadonlyArray<ZipMember>
): Uint8Array => {
  const localChunks: Array<Uint8Array> = []
  const offsets: Array<number> = []
  let cursor = 0
  for (const member of members) {
    const name = encoder.encode(member.name)
    const checksum = crc32(member.bytes)
    const header = Buffer.alloc(30)
    header.writeUInt32LE(0x04034b50, 0)
    header.writeUInt16LE(20, 4)
    header.writeUInt16LE(0x0008, 6)
    header.writeUInt16LE(0, 8)
    header.writeUInt16LE(0x1c25, 10)
    header.writeUInt16LE(0x5d15, 12)
    header.writeUInt16LE(name.byteLength, 26)
    const descriptor = Buffer.alloc(16)
    descriptor.writeUInt32LE(0x08074b50, 0)
    descriptor.writeUInt32LE(checksum, 4)
    descriptor.writeUInt32LE(member.bytes.byteLength, 8)
    descriptor.writeUInt32LE(member.bytes.byteLength, 12)
    offsets.push(cursor)
    localChunks.push(header, name, member.bytes, descriptor)
    cursor += header.byteLength + name.byteLength + member.bytes.byteLength + 16
  }

  const centralOffset = cursor
  const centralChunks: Array<Uint8Array> = []
  members.forEach((member, index) => {
    const name = encoder.encode(member.name)
    const header = Buffer.alloc(46)
    header.writeUInt32LE(0x02014b50, 0)
    header.writeUInt16LE(0x032d, 4)
    header.writeUInt16LE(20, 6)
    header.writeUInt16LE(0x0008, 8)
    header.writeUInt16LE(0, 10)
    header.writeUInt16LE(0x1c25, 12)
    header.writeUInt16LE(0x5d15, 14)
    header.writeUInt32LE(crc32(member.bytes), 16)
    header.writeUInt32LE(member.bytes.byteLength, 20)
    header.writeUInt32LE(member.bytes.byteLength, 24)
    header.writeUInt16LE(name.byteLength, 28)
    header.writeUInt32LE((((0o100000 | 0o644) << 16) | 0x20) >>> 0, 38)
    const localOffset = offsets[index]
    if (localOffset === undefined) throw new Error("ZIP offset missing")
    header.writeUInt32LE(localOffset, 42)
    centralChunks.push(header, name)
    cursor += header.byteLength + name.byteLength
  })

  const end = Buffer.alloc(22)
  end.writeUInt32LE(0x06054b50, 0)
  end.writeUInt16LE(members.length, 8)
  end.writeUInt16LE(members.length, 10)
  end.writeUInt32LE(cursor - centralOffset, 12)
  end.writeUInt32LE(centralOffset, 16)
  return Uint8Array.from(
    Buffer.concat([...localChunks, ...centralChunks, end])
  )
}

const jsonBytes = (value: unknown): Uint8Array =>
  encoder.encode(`${JSON.stringify(value)}\n`)

const right = <A, E>(outcome: Either.Either<A, E>): A => {
  if (Either.isLeft(outcome)) throw outcome.left
  return outcome.right
}

const jobJson = (overrides: Record<string, unknown> = {}) => ({
  id: JOB_ID,
  run_id: RUN_ID,
  run_attempt: 1,
  name: "register",
  head_sha: HEAD_SHA,
  status: "completed",
  conclusion: "success",
  started_at: "2026-08-21T03:10:34Z",
  completed_at: "2026-08-21T03:33:15Z",
  labels: ["ubuntu-24.04"],
  ...overrides
})

const runJson = (overrides: Record<string, unknown> = {}) => ({
  id: RUN_ID,
  run_attempt: 1,
  name: "SWM-0W-S2S confirmatory",
  path: ".github/workflows/swm0w-s2s-confirmatory.yml",
  event: "push",
  head_branch: "main",
  head_sha: HEAD_SHA,
  repository: { full_name: "gj3447/HSWM" },
  head_repository: { full_name: "gj3447/HSWM" },
  status: "in_progress",
  conclusion: null,
  created_at: "2026-08-21T03:10:32Z",
  ...overrides
})

const artifactJson = (
  archive: Uint8Array,
  overrides: Record<string, unknown> = {}
) => ({
  id: ARTIFACT_ID,
  name: "s2s-registration",
  size_in_bytes: archive.byteLength,
  digest: `sha256:${rawS2SFileSha256(archive)}`,
  expired: false,
  created_at: "2026-08-21T03:33:12Z",
  expires_at: "2026-11-19T03:10:32Z",
  workflow_run: { id: RUN_ID, head_sha: HEAD_SHA },
  ...overrides
})

interface FixtureOptions {
  readonly runOverrides?: Record<string, unknown>
  readonly jobOverrides?: Record<string, unknown>
  readonly artifactRows?: ReadonlyArray<Record<string, unknown>>
  readonly requeryOverrides?: Record<string, unknown>
  readonly downloadHashOverride?: string
}

const makeFixture = (options: FixtureOptions = {}) => {
  const controlBytes = encoder.encode('{"control":"receipt"}\n')
  const archive = buildStoredArtifactZip([
    { name: "control_receipt.json", bytes: controlBytes }
  ])
  const canonicalArtifact = artifactJson(archive)
  const artifactRows = options.artifactRows ?? [canonicalArtifact]
  const runOffsets = artifactRows.length === 0 ? [-1, 2, 12, 22] : [-1, 2, 3, 6]
  const runObservations = runOffsets.map((offset) =>
    right(
      observeS2SGitHubWorkflowRun(
        jsonBytes(runJson(options.runOverrides)),
        RUN_ID,
        OBSERVED_AT + offset,
        responseProvenance(`run-${offset}`)
      )
    )
  )
  const run = runObservations[0]
  if (run === undefined) throw new Error("workflow run observation missing")
  const jobs = right(
    observeS2SGitHubWorkflowAttemptJobs(
      jsonBytes({
        total_count: 1,
        jobs: [jobJson(options.jobOverrides)]
      }),
      RUN_ID,
      1,
      OBSERVED_AT,
      responseProvenance("jobs")
    )
  )
  const artifactObservations = [1, 11, 21].map((offset) =>
    right(
      observeS2SGitHubRunArtifacts(
        jsonBytes({ total_count: artifactRows.length, artifacts: artifactRows }),
        RUN_ID,
        OBSERVED_AT + offset,
        responseProvenance(`artifacts-${offset}`)
      )
    )
  )
  const artifacts = artifactObservations[0]
  if (artifacts === undefined) throw new Error("artifact observation missing")
  const requery = right(
    observeS2SGitHubArtifact(
      jsonBytes({ ...canonicalArtifact, ...options.requeryOverrides }),
      ARTIFACT_ID,
      OBSERVED_AT + 4,
      responseProvenance("artifact-requery")
    )
  )
  const receiptCore: Omit<
    S2SGitHubArtifactDownloadReceipt,
    "receiptSha256"
  > = Object.freeze({
    schemaVersion: S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
    apiVersion: S2S_GITHUB_API_VERSION,
    repository: S2S_GITHUB_REPOSITORY,
    artifactId: ARTIFACT_ID,
    endpointPathAndQuery: `/repos/${S2S_GITHUB_REPOSITORY}/actions/artifacts/${ARTIFACT_ID}/zip`,
    downloadedAtUnixSeconds: OBSERVED_AT + 5,
    redirectHttpStatus: 302,
    redirectGitHubRequestId: "A1B2:C3D4:E5F6:DOWNLOAD",
    redirectGitHubApiVersionSelected: S2S_GITHUB_API_VERSION,
    redirectResponseEtag: null,
    redirectUrlSha256: "a".repeat(64),
    redirectOrigin: "https://objects.example.invalid",
    archiveHttpStatus: 200,
    archiveMediaType: "application/zip",
    archiveResponseEtag: `"${"a".repeat(64)}"`,
    archiveByteLength: archive.byteLength,
    downloadedArchiveSha256:
      options.downloadHashOverride ?? rawS2SFileSha256(archive)
  })
  const receiptSha256 = right(canonicalS2SControlSha256(receiptCore))
  const download: S2SGitHubArtifactDownload = Object.freeze({
    receipt: Object.freeze({ ...receiptCore, receiptSha256 }),
    readArchiveBytes: () => new Uint8Array(archive)
  })
  return {
    archive,
    controlBytes,
    run,
    runObservations,
    jobs,
    artifacts,
    artifactObservations,
    requery,
    download
  }
}

const makeAuthorityLayer = (fixture: ReturnType<typeof makeFixture>) => {
  let runObservationIndex = 0
  let artifactObservationIndex = 0
  const github = Layer.succeed(
    S2SGitHubObserver,
    S2SGitHubObserver.of({
      observeWorkflowRun: () => {
        const observation =
          fixture.runObservations[
            Math.min(
              runObservationIndex,
              fixture.runObservations.length - 1
            )
          ] ?? fixture.run
        runObservationIndex += 1
        return Effect.succeed(observation)
      },
      observeWorkflowAttemptJobs: () => Effect.succeed(fixture.jobs),
      observeRunArtifacts: () => {
        const observation =
          fixture.artifactObservations[
            Math.min(
              artifactObservationIndex,
              fixture.artifactObservations.length - 1
            )
          ] ?? fixture.artifacts
        artifactObservationIndex += 1
        return Effect.succeed(observation)
      },
      observeArtifact: () => Effect.succeed(fixture.requery),
      downloadArtifactArchive: () => Effect.succeed(fixture.download)
    })
  )
  return makeS2SArtifactAuthorityTestLayer().pipe(Layer.provide(github))
}

it.effect("issues nominal authority and validates a distinct exact ZIP readback", () => {
  const fixture = makeFixture()
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup._tag).toBe("Observed")
    if (lookup._tag !== "Observed") return
    const readback = yield* service.readback(lookup)
    expect(readback.validatedArchive.archiveSha256).toBe(
      rawS2SFileSha256(fixture.archive)
    )
    expect(readback.validatedArchive.members).toHaveLength(1)
    expect(readback.validatedArchive.members[0]?.readBytes()).toEqual(
      fixture.controlBytes
    )
    expect(readback.requeryObservationReceiptSha256).not.toBe(
      lookup.artifactsObservation.receipt.receiptSha256
    )
    expect(readback.artifactRequeryObservation.receipt.receiptSha256).toBe(
      readback.requeryObservationReceiptSha256
    )
    expect(readback.artifactDownload.receipt.receiptSha256).toBe(
      readback.downloadObservationReceiptSha256
    )
    expect(readback.readbackStartRunObservation.receipt.receiptSha256).toBe(
      readback.readbackStartRunObservationReceiptSha256
    )
    expect(readback.readbackFinalRunObservation.receipt.receiptSha256).toBe(
      readback.readbackFinalRunObservationReceiptSha256
    )
    expect(Object.isFrozen(readback.artifactEvidence)).toBe(true)
    const mutableEvidence = readback.artifactEvidence as unknown as {
      artifactId: number
    }
    expect(() => {
      mutableEvidence.artifactId = 1
    }).toThrow()
    expect(readback.artifactEvidence.artifactId).toBe(ARTIFACT_ID)
    const mutableDownload = readback.artifactDownload.readArchiveBytes()
    mutableDownload.fill(0)
    expect(
      rawS2SFileSha256(readback.artifactDownload.readArchiveBytes())
    ).toBe(rawS2SFileSha256(fixture.archive))
    const mutableRead = readback.readArchiveBytes()
    mutableRead.fill(0)
    expect(rawS2SFileSha256(readback.readArchiveBytes())).toBe(
      rawS2SFileSha256(fixture.archive)
    )
  }).pipe(Effect.provide(makeAuthorityLayer(fixture)))
})

it.effect("reconciles bounded absence only after a successful completed producer", () => {
  const fixture = makeFixture({ artifactRows: [] })
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup).toMatchObject({
      _tag: "ReconciledAbsentAfterProducerCompleted",
      role: "REGISTRATION",
      producerJobId: JOB_ID,
      expectedArtifactName: "s2s-registration"
    })
    if (lookup._tag === "ReconciledAbsentAfterProducerCompleted") {
      expect(new Set(lookup.absenceObservationReceiptSha256s).size).toBe(3)
      expect(lookup.reconciliationReceiptSha256).toMatch(/^[0-9a-f]{64}$/)
      const { receiptSha256, ...receiptCore } = lookup.reconciliationReceipt
      expect(right(canonicalS2SControlSha256(receiptCore))).toBe(receiptSha256)
      expect(
        lookup.absenceObservations.map(
          (observation) => observation.receipt.receiptSha256
        )
      ).toEqual(lookup.absenceObservationReceiptSha256s)
      expect(
        lookup.initialWorkflowRunObservation.receipt.receiptSha256
      ).toBe(lookup.initialWorkflowRunObservationReceiptSha256)
      expect(lookup.workflowRunObservation.receipt.receiptSha256).toBe(
        lookup.workflowRunObservationReceiptSha256
      )
      expect(lookup.workflowJobsObservation.receipt.receiptSha256).toBe(
        lookup.workflowJobsObservationReceiptSha256
      )
      expect(() =>
        (
          lookup.absenceObservationReceiptSha256s as unknown as Array<string>
        ).fill("0".repeat(64))
      ).toThrow()
      expect(
        right(
          canonicalS2SControlSha256({
            ...receiptCore,
            expectedHeadSha: "f".repeat(40)
          })
        )
      ).not.toBe(receiptSha256)
    }
  }).pipe(Effect.provide(makeAuthorityLayer(fixture)))
})

it.effect("separates failed producers and ambiguous duplicate artifacts", () => {
  const failed = makeFixture({
    runOverrides: { status: "completed", conclusion: "failure" },
    jobOverrides: { conclusion: "failure" },
    artifactRows: []
  })
  const downstreamFailed = makeFixture({
    runOverrides: { status: "completed", conclusion: "failure" }
  })
  const duplicateArchive = failed.archive
  const duplicate = makeFixture({
    artifactRows: [
      artifactJson(duplicateArchive),
      artifactJson(duplicateArchive, { id: ARTIFACT_ID + 1 })
    ]
  })
  const inspect = (layer: ReturnType<typeof makeAuthorityLayer>) =>
    Effect.gen(function* () {
      const service = yield* S2SArtifactAuthority
      return yield* service.observeRoleArtifact(
        RUN_ID,
        HEAD_SHA,
        "REGISTRATION"
      )
    }).pipe(Effect.provide(layer))
  return Effect.gen(function* () {
    const failedOutcome = yield* inspect(makeAuthorityLayer(failed))
    const duplicateOutcome = yield* inspect(makeAuthorityLayer(duplicate))
    const downstreamFailedOutcome = yield* inspect(
      makeAuthorityLayer(downstreamFailed)
    )
    expect(failedOutcome._tag).toBe("ProducerDidNotCompleteSuccessfully")
    expect(duplicateOutcome).toMatchObject({
      _tag: "Ambiguous",
      reason: "DUPLICATE_ARTIFACT_NAME"
    })
    expect(downstreamFailedOutcome).toMatchObject({
      _tag: "Ambiguous",
      reason: "WORKFLOW_RUN_DID_NOT_SUCCEED"
    })
  })
})

it.effect("rejects counterfeit authority and download identity drift", () => {
  const fixture = makeFixture({ downloadHashOverride: "c".repeat(64) })
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup._tag).toBe("Observed")
    if (lookup._tag !== "Observed") return
    const counterfeit = Object.freeze({ ...lookup }) as S2SObservedArtifactAuthority
    const counterfeitResult = yield* service.readback(counterfeit).pipe(Effect.either)
    const driftResult = yield* service.readback(lookup).pipe(Effect.either)
    expect(Either.isLeft(counterfeitResult)).toBe(true)
    expect(Either.isLeft(driftResult)).toBe(true)
    if (Either.isLeft(counterfeitResult)) {
      expect(counterfeitResult.left.reason).toBe("INVALID_AUTHORITY")
    }
    if (Either.isLeft(driftResult)) {
      expect(driftResult.left.reason).toBe("DOWNLOAD_MISMATCH")
    }
  }).pipe(Effect.provide(makeAuthorityLayer(fixture)))
})

it.effect("rejects an artifact download with a counterfeit receipt self-hash", () => {
  const fixture = makeFixture()
  const counterfeitFixture = {
    ...fixture,
    download: Object.freeze({
      ...fixture.download,
      receipt: Object.freeze({
        ...fixture.download.receipt,
        receiptSha256: "b".repeat(64)
      })
    })
  }
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup._tag).toBe("Observed")
    if (lookup._tag !== "Observed") return
    const outcome = yield* service.readback(lookup).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left).toMatchObject({
        reason: "DOWNLOAD_MISMATCH",
        causeReason: "RECEIPT_SELF_HASH_MISMATCH"
      })
    }
  }).pipe(Effect.provide(makeAuthorityLayer(counterfeitFixture)))
})

it.effect("scopes nominal authority to one Layer instance", () => {
  const fixture = makeFixture()
  const issue = Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    if (lookup._tag !== "Observed") {
      return yield* Effect.dieMessage("fixture did not issue authority")
    }
    return lookup
  }).pipe(Effect.provide(makeAuthorityLayer(fixture)))
  return Effect.gen(function* () {
    const foreignAuthority = yield* issue
    const outcome = yield* Effect.gen(function* () {
      const service = yield* S2SArtifactAuthority
      return yield* service.readback(foreignAuthority).pipe(Effect.either)
    }).pipe(Effect.provide(makeAuthorityLayer(makeFixture())))
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("INVALID_AUTHORITY")
    }
  })
})

it.effect("rejects rerun-attempt metadata before issuing authority", () => {
  const fixture = makeFixture()
  const rerunObservation = Object.freeze({
    ...fixture.run,
    receipt: Object.freeze({
      ...fixture.run.receipt,
      observedAtUnixSeconds: OBSERVED_AT + 2,
      githubRequestId: "A1B2:C3D4:E5F6:RERUN",
      projection: Object.freeze({
        ...fixture.run.receipt.projection,
        runAttempt: 2
      })
    })
  })
  const rerunFixture = {
    ...fixture,
    runObservations: [fixture.run, rerunObservation]
  }
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup).toMatchObject({
      _tag: "Ambiguous",
      reason: "HEAD_SHA_MISMATCH"
    })
  }).pipe(Effect.provide(makeAuthorityLayer(rerunFixture)))
})

it.effect("rejects unknown and inherited role names before observation", () => {
  const fixture = makeFixture()
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    for (const hostileRole of ["UNKNOWN", "__proto__", "toString"]) {
      const lookup = yield* service.observeRoleArtifact(
        RUN_ID,
        HEAD_SHA,
        hostileRole as "REGISTRATION"
      )
      expect(lookup).toEqual({
        _tag: "InvalidRequest",
        reason: "INVALID_ROLE"
      })
    }
    const hostileCall = service.observeRoleArtifact as unknown as (
      workflowRunId: number,
      expectedHeadSha: unknown,
      role: "REGISTRATION"
    ) => Effect.Effect<unknown>
    const hostileHead = yield* hostileCall(
      RUN_ID,
      Symbol("head-sha"),
      "REGISTRATION"
    )
    expect(hostileHead).toEqual({
      _tag: "InvalidRequest",
      reason: "INVALID_HEAD_SHA"
    })
  }).pipe(Effect.provide(makeAuthorityLayer(fixture)))
})

it.effect("rechecks rerun identity when spending artifact authority", () => {
  const fixture = makeFixture()
  const rerunObservation = Object.freeze({
    ...fixture.run,
    receipt: Object.freeze({
      ...fixture.run.receipt,
      observedAtUnixSeconds: OBSERVED_AT + 6,
      projection: Object.freeze({
        ...fixture.run.receipt.projection,
        runAttempt: 2
      })
    })
  })
  const rerunFixture = {
    ...fixture,
    runObservations: [
      fixture.run,
      fixture.runObservations[1] ?? fixture.run,
      rerunObservation
    ]
  }
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup._tag).toBe("Observed")
    if (lookup._tag !== "Observed") return
    const outcome = yield* service.readback(lookup).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("RUN_REQUERY_MISMATCH")
    }
  }).pipe(Effect.provide(makeAuthorityLayer(rerunFixture)))
})

it.effect("rejects a readback run query that reuses an issuance request id", () => {
  const fixture = makeFixture()
  const issuedRun = fixture.runObservations[1] ?? fixture.run
  const reusedReadbackRun = right(
    observeS2SGitHubWorkflowRun(
      jsonBytes(runJson()),
      RUN_ID,
      OBSERVED_AT + 3,
      Object.freeze({
        githubRequestId: issuedRun.receipt.githubRequestId,
        githubApiVersionSelected: S2S_GITHUB_API_VERSION,
        responseEtag: `W/"${"e".repeat(64)}"`
      })
    )
  )
  expect(reusedReadbackRun.receipt.receiptSha256).not.toBe(
    issuedRun.receipt.receiptSha256
  )
  const reusedFixture = {
    ...fixture,
    runObservations: [
      fixture.run,
      issuedRun,
      reusedReadbackRun,
      fixture.runObservations[3] ?? fixture.run
    ]
  }
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup._tag).toBe("Observed")
    if (lookup._tag !== "Observed") return
    const outcome = yield* service.readback(lookup).pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left.reason).toBe("OBSERVATION_ORDER_INVALID")
      expect(outcome.left.causeReason).toBe(
        "GITHUB_REQUEST_ID_REUSED_BEFORE_READBACK"
      )
    }
  }).pipe(Effect.provide(makeAuthorityLayer(reusedFixture)))
})

it.effect("does not call repeated identical empty lists reconciled absence", () => {
  const fixture = makeFixture({ artifactRows: [] })
  const repeatedFixture = {
    ...fixture,
    artifactObservations: [
      fixture.artifacts,
      fixture.artifacts,
      fixture.artifacts
    ]
  }
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup).toMatchObject({
      _tag: "Ambiguous",
      reason: "OBSERVATION_REQUEST_IDS_NOT_DISTINCT"
    })
  }).pipe(Effect.provide(makeAuthorityLayer(repeatedFixture)))
})

it.effect("rejects timestamp-distinct absence receipts that reuse a request id", () => {
  const fixture = makeFixture({ artifactRows: [] })
  const reusedRequestArtifacts = [1, 11, 21].map((offset) =>
    right(
      observeS2SGitHubRunArtifacts(
        jsonBytes({ total_count: 0, artifacts: [] }),
        RUN_ID,
        OBSERVED_AT + offset,
        responseProvenance("REUSED-ABSENCE-REQUEST")
      )
    )
  )
  expect(
    new Set(
      reusedRequestArtifacts.map(
        (observation) => observation.receipt.receiptSha256
      )
    ).size
  ).toBe(3)
  const reusedFixture = {
    ...fixture,
    artifacts: reusedRequestArtifacts[0] ?? fixture.artifacts,
    artifactObservations: reusedRequestArtifacts
  }
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup).toMatchObject({
      _tag: "Ambiguous",
      reason: "OBSERVATION_REQUEST_IDS_NOT_DISTINCT"
    })
  }).pipe(Effect.provide(makeAuthorityLayer(reusedFixture)))
})

it.effect("rejects absence polling when successive run brackets reuse a request id", () => {
  const fixture = makeFixture({ artifactRows: [] })
  const runObservations = [-1, 2, 12, 22].map((offset, index) =>
    right(
      observeS2SGitHubWorkflowRun(
        jsonBytes(runJson()),
        RUN_ID,
        OBSERVED_AT + offset,
        responseProvenance(
          index === 0 ? "INITIAL-RUN" : "REUSED-RUN-BRACKET"
        )
      )
    )
  )
  expect(
    new Set(
      runObservations.map((observation) => observation.receipt.receiptSha256)
    ).size
  ).toBe(4)
  const reusedFixture = {
    ...fixture,
    run: runObservations[0] ?? fixture.run,
    runObservations
  }
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup).toMatchObject({
      _tag: "Ambiguous",
      reason: "OBSERVATION_REQUEST_IDS_NOT_DISTINCT"
    })
  }).pipe(Effect.provide(makeAuthorityLayer(reusedFixture)))
})

it.effect("requires the frozen minimum gaps for absence reconciliation", () => {
  const fixture = makeFixture({ artifactRows: [] })
  const closeArtifacts = [1, 2, 3].map((offset) =>
    right(
      observeS2SGitHubRunArtifacts(
        jsonBytes({ total_count: 0, artifacts: [] }),
        RUN_ID,
        OBSERVED_AT + offset,
        responseProvenance(`close-artifacts-${offset}`)
      )
    )
  )
  const closeRuns = [-1, 2, 3, 4].map((offset) =>
    right(
      observeS2SGitHubWorkflowRun(
        jsonBytes(runJson()),
        RUN_ID,
        OBSERVED_AT + offset,
        responseProvenance(`close-run-${offset}`)
      )
    )
  )
  const closeFixture = {
    ...fixture,
    artifactObservations: closeArtifacts,
    artifacts: closeArtifacts[0] ?? fixture.artifacts,
    run: closeRuns[0] ?? fixture.run,
    runObservations: closeRuns
  }
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup).toMatchObject({
      _tag: "Ambiguous",
      reason: "ABSENCE_OBSERVATIONS_TOO_CLOSE"
    })
  }).pipe(Effect.provide(makeAuthorityLayer(closeFixture)))
})

it.effect("requires run observations to bracket job and artifact observations", () => {
  const fixture = makeFixture()
  const staleFinalRun = right(
    observeS2SGitHubWorkflowRun(
      jsonBytes(runJson()),
      RUN_ID,
      OBSERVED_AT,
      responseProvenance("stale-final-run")
    )
  )
  const staleFixture = {
    ...fixture,
    runObservations: [fixture.run, staleFinalRun]
  }
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup).toMatchObject({
      _tag: "Ambiguous",
      reason: "OBSERVATION_ORDER_INVALID"
    })
  }).pipe(Effect.provide(makeAuthorityLayer(staleFixture)))
})

it.effect("surfaces observer failure as unavailable without retrying", () => {
  let attempts = 0
  const github = Layer.succeed(
    S2SGitHubObserver,
    S2SGitHubObserver.of({
      observeWorkflowRun: () => Effect.succeed(makeFixture().run),
      observeWorkflowAttemptJobs: () => {
        attempts += 1
        return Effect.fail(new S2SGitHubObservationError({
          reason: "JSON_REJECTED",
          path: "$",
          detail: "fixture"
        }))
      },
      observeRunArtifacts: () => Effect.dieMessage("must not run"),
      observeArtifact: () => Effect.dieMessage("not used"),
      downloadArtifactArchive: () => Effect.dieMessage("not used")
    })
  )
  const layer = makeS2SArtifactAuthorityTestLayer().pipe(Layer.provide(github))
  return Effect.gen(function* () {
    const service = yield* S2SArtifactAuthority
    const lookup = yield* service.observeRoleArtifact(
      RUN_ID,
      HEAD_SHA,
      "REGISTRATION"
    )
    expect(lookup).toMatchObject({
      _tag: "ObservationUnavailable",
      operation: "OBSERVE_JOBS",
      errorReason: "JSON_REJECTED"
    })
    expect(attempts).toBe(1)
  }).pipe(Effect.provide(layer))
})

// Compile-time anchors for the generic observation shapes used by the fake
// port. They prevent accidental widening to unknown in this authority test.
const _observationTypeAnchors: readonly [
  S2SGitHubObservation<S2SGitHubWorkflowRunProjection> | null,
  S2SGitHubObservation<S2SGitHubWorkflowJobsProjection> | null,
  S2SGitHubObservation<S2SGitHubArtifactsProjection> | null,
  S2SGitHubObservation<S2SGitHubArtifactProjection> | null
] = [null, null, null, null]
void _observationTypeAnchors
