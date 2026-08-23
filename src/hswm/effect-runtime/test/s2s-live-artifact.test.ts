import { expect, it } from "@effect/vitest"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import {
  Cause,
  Deferred,
  Effect,
  Either,
  Exit,
  Fiber
} from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  buildS2SEvidenceClaim,
  type S2SEvidenceEnvelopeInput,
  type S2SEvidenceEnvelopeSnapshot
} from "../src/s2s-evidence-envelope.js"
import {
  S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES,
  buildS2SSuccessStageEvidenceEnvelope
} from "../src/s2s-evidence-profile.js"
import {
  S2SDurableEvidenceFileStore,
  isAuthenticS2SDurableEvidenceRecovery,
  makeS2SDurableEvidenceFileStoreLayer
} from "../src/s2s-evidence-file.js"
import {
  S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_MAX_RAW_BYTES,
  S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_SCHEMA_VERSION,
  S2SStageArtifactReadError,
  probeS2SStageArtifactReadMechanicsForTest,
  type S2SAdjudicateStageArtifactReads,
  type S2SConfirmStageArtifactReads,
  type S2SStageArtifactReadsService
} from "../src/s2s-live-artifact.js"
import {
  S2S_GITHUB_API_VERSION,
  S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
  S2S_GITHUB_JSON_MAX_BYTES,
  S2S_GITHUB_REPOSITORY,
  S2SGitHubObservationError,
  S2SGitHubObserver,
  observeS2SGitHubArtifact,
  observeS2SGitHubRunArtifacts,
  observeS2SGitHubWorkflowAttemptJobs,
  observeS2SGitHubWorkflowRun,
  validateS2SGitHubRunArtifactsObservation,
  validateS2SGitHubWorkflowAttemptJobsObservation,
  validateS2SGitHubWorkflowRunObservation,
  type S2SGitHubArtifactDownload,
  type S2SGitHubArtifactDownloadReceipt,
  type S2SGitHubObservation
} from "../src/s2s-live-github.js"
import {
  S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION,
  type S2SCurrentRunStageEvidence
} from "../src/s2s-run-authority.js"
import {
  buildS2SStageArtifactReadReplay,
  buildS2SStageArtifactReadReplayEffect,
  validateS2SCurrentRunStageEvidenceForArtifactReplay,
  validateS2SCandidateReadReplayPair,
  validateS2SStageArtifactReadReplayEffect,
  validateS2SStageArtifactReadReplay,
  type S2SStageArtifactReadReplaySnapshot
} from "../src/s2s-stage-artifact-read-replay.js"
import {
  commitS2SStageReadReplayProfileAttachments,
  type S2SStageReadReplayDurablePublication
} from "../src/s2s-stage-read-replay-durable-profile.js"
import {
  S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MAX_BYTES,
  S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MEMBER_NAME,
  S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES,
  S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MAX_BYTES,
  S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MEMBER_NAME
} from "../src/s2s-stage-artifact-read-replay-contract.js"
import {
  appendS2SStageArtifactLedgerEntry,
  makeS2SStageArtifactPermitTestScope,
  useS2SStageArtifactPermit
} from "../src/s2s-stage-artifact-permits.js"
import {
  s2sConfirmatoryWorkflowContractSha256,
  type S2SConfirmatoryJobStage
} from "../src/s2s-workflow-contract.js"
import {
  buildS2SStoredZip,
  validateS2SArtifactZip
} from "../src/s2s-zip.js"

const RUN_ID = 32_442_437_970
const REGISTER_JOB_ID = 96_655_652_099
const CONFIRM_JOB_ID = 96_655_652_100
const ADJUDICATE_JOB_ID = 96_655_652_101
const REGISTRATION_ARTIFACT_ID = 9_433_344_546
const CANDIDATE_ARTIFACT_ID = 9_433_344_547
const HEAD_SHA = "75686549b1f6c65aea87ebd0f912a6e62909445a"
const SOURCE_COMMIT_A = "a".repeat(40)
const WORKFLOW_FILE_SHA256 = "b".repeat(64)
const WORKFLOW_PATH = ".github/workflows/swm0w-s2s-confirmatory.yml"
const CREATED_AT = "2026-08-21T03:10:32Z"
const CREATED_AT_UNIX_SECONDS = Date.parse(CREATED_AT) / 1_000
const OBSERVED_AT = CREATED_AT_UNIX_SECONDS + 2_000
const ENCODER = new TextEncoder()

type ArtifactRole = "REGISTRATION" | "CANDIDATE"

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
    const name = ENCODER.encode(member.name)
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
    const name = ENCODER.encode(member.name)
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
    const offset = offsets[index]
    if (offset === undefined) throw new Error("ZIP offset missing")
    header.writeUInt32LE(offset, 42)
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

const registrationArchive = () =>
  buildStoredArtifactZip([
    {
      name: "control_receipt.json",
      bytes: ENCODER.encode('{"control":"registration"}\n')
    }
  ])

const candidateArchive = (value = 1) =>
  buildStoredArtifactZip([
    {
      name: "control_receipt.json",
      bytes: ENCODER.encode('{"control":"candidate"}\n')
    },
    {
      name: "numeric_candidate.json",
      bytes: ENCODER.encode(`${JSON.stringify({ value })}\n`)
    }
  ])

const jsonBytes = (value: unknown): Uint8Array =>
  ENCODER.encode(`${JSON.stringify(value)}\n`)

const right = <A, E>(outcome: Either.Either<A, E>): A => {
  if (Either.isLeft(outcome)) throw outcome.left
  return outcome.right
}

const WORKFLOW_CONTRACT_SHA256 = right(
  s2sConfirmatoryWorkflowContractSha256()
)

const currentJobId = (stage: S2SConfirmatoryJobStage): number =>
  stage === "REGISTER"
    ? REGISTER_JOB_ID
    : stage === "CONFIRM"
      ? CONFIRM_JOB_ID
      : ADJUDICATE_JOB_ID

const predecessorJobIds = (
  stage: S2SConfirmatoryJobStage
): ReadonlyArray<number> =>
  stage === "REGISTER"
    ? []
    : stage === "CONFIRM"
      ? [REGISTER_JOB_ID]
      : [REGISTER_JOB_ID, CONFIRM_JOB_ID]

const makeSeed = (
  stage: S2SConfirmatoryJobStage,
  workflowApiPath = WORKFLOW_PATH
) =>
  Object.freeze({
    classification: "TEST_ONLY_NON_AUTHORIZING" as const,
    workflowRunId: RUN_ID,
    registrationCommitB: HEAD_SHA,
    workflowApiPath,
    workflowRunCreatedAt: CREATED_AT,
    workflowRunCreatedAtUnixSeconds: CREATED_AT_UNIX_SECONDS,
    stage,
    currentJobDatabaseId: currentJobId(stage),
    predecessorJobDatabaseIds: Object.freeze([...predecessorJobIds(stage)]),
    observations: Object.freeze({
      runStart: Object.freeze({
        receiptSha256: "1".repeat(64),
        githubRequestId: "SEED:RUN-START",
        observedAtUnixSeconds: OBSERVED_AT - 40
      }),
      jobs: Object.freeze({
        receiptSha256: "2".repeat(64),
        githubRequestId: "SEED:JOBS",
        observedAtUnixSeconds: OBSERVED_AT - 30
      }),
      runsForHead: Object.freeze({
        receiptSha256: "3".repeat(64),
        githubRequestId: "SEED:RUNS-FOR-HEAD",
        observedAtUnixSeconds: OBSERVED_AT - 20
      }),
      runEnd: Object.freeze({
        receiptSha256: "4".repeat(64),
        githubRequestId: "SEED:RUN-END",
        observedAtUnixSeconds: OBSERVED_AT - 10
      })
    })
  })

const makeCurrentRunEvidence = (
  stage: "CONFIRM" | "ADJUDICATE",
  trackedBytesManifestSha256 = "7".repeat(64)
): S2SCurrentRunStageEvidence => {
  const seed = makeSeed(stage)
  const core: Omit<S2SCurrentRunStageEvidence, "receiptSha256"> = {
    schemaVersion: S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION,
    authorityScope: "PROCESS_LOCAL_STAGE_ENTRY",
    uniquenessClaim: "ROSTER_OBSERVATION_INSTANT_ONLY",
    historicalUniquenessClaimed: false,
    crossExecutionReplayPreventionClaimed: false,
    durableCommitRequiresFreshTerminalObservation: true,
    sourceCommitA: SOURCE_COMMIT_A,
    registrationCommitB: seed.registrationCommitB,
    registrationAuthorityReceiptSha256: "5".repeat(64),
    currentInvocationReceiptSha256: "6".repeat(64),
    workflowContractSha256: WORKFLOW_CONTRACT_SHA256,
    workflowFileSha256: WORKFLOW_FILE_SHA256,
    trackedBytesManifestSha256,
    workflowApiPath: seed.workflowApiPath,
    workflowRunId: seed.workflowRunId,
    workflowRunAttempt: 1,
    stage,
    currentJobId: stage === "CONFIRM" ? "confirm" : "adjudicate",
    currentJobDatabaseId: seed.currentJobDatabaseId,
    predecessorJobDatabaseIds: seed.predecessorJobDatabaseIds,
    workflowRunCreatedAt: seed.workflowRunCreatedAt,
    workflowRunCreatedAtUnixSeconds: seed.workflowRunCreatedAtUnixSeconds,
    invocationCapturedAtUnixSeconds: OBSERVED_AT - 100,
    observations: seed.observations
  }
  return Object.freeze({
    ...core,
    receiptSha256: right(canonicalS2SControlSha256(core))
  })
}

const makeConsumerEnvelopeInput = (
  current: S2SCurrentRunStageEvidence,
  predecessor: NonNullable<S2SEvidenceEnvelopeInput["predecessor"]>,
  attachmentBytes: Readonly<Record<string, Uint8Array>>
): S2SEvidenceEnvelopeInput => ({
  sourceCommitA: current.sourceCommitA,
  registrationCommitB: current.registrationCommitB,
  workflowRunId: current.workflowRunId,
  workflowRunCreatedAtUnixSeconds: current.workflowRunCreatedAtUnixSeconds,
  workflowApiPath: current.workflowApiPath,
  workflowFileSha256: current.workflowFileSha256,
  workflowContractSha256: current.workflowContractSha256,
  stage: current.stage,
  currentJobDatabaseId: current.currentJobDatabaseId,
  predecessor,
  attachments: S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES[current.stage].map(
    (spec) => ({
      logicalName: spec.logicalName,
      role: spec.role,
      schemaVersion: spec.schemaVersion,
      mediaType: spec.mediaType,
      bytes: Uint8Array.from(
        attachmentBytes[spec.logicalName] ?? new Uint8Array([0x31])
      )
    })
  )
})

const issueDurableRecovery = (
  envelopes: ReadonlyArray<S2SEvidenceEnvelopeSnapshot>
) =>
  Effect.acquireUseRelease(
    Effect.sync(() => mkdtempSync(join(tmpdir(), "hswm-s2s-replay-source-"))),
    (root) =>
      Effect.gen(function* () {
        const [first, ...remaining] = envelopes
        if (first === undefined) {
          return yield* Effect.dieMessage(
            "durable recovery fixture requires a nonempty envelope chain"
          )
        }
        const store = yield* S2SDurableEvidenceFileStore
        let publication = yield* store.commit(first)
        for (const envelope of remaining) {
          publication = yield* store.commit(envelope)
        }
        return publication.recovery
      }).pipe(Effect.provide(makeS2SDurableEvidenceFileStoreLayer(root))),
    (root) => Effect.sync(() => rmSync(root, { force: true, recursive: true }))
  )

const makeRegistrationEnvelope = (
  archive: Uint8Array,
  current: S2SCurrentRunStageEvidence,
  overrides: Readonly<{
    workflowFileSha256?: string
    currentJobDatabaseId?: number
  }> = {}
): S2SEvidenceEnvelopeSnapshot =>
  right(
    buildS2SSuccessStageEvidenceEnvelope({
      sourceCommitA: current.sourceCommitA,
      registrationCommitB: current.registrationCommitB,
      workflowRunId: current.workflowRunId,
      workflowRunCreatedAtUnixSeconds: current.workflowRunCreatedAtUnixSeconds,
      workflowApiPath: current.workflowApiPath,
      workflowFileSha256:
        overrides.workflowFileSha256 ?? current.workflowFileSha256,
      workflowContractSha256: current.workflowContractSha256,
      stage: "REGISTER",
      currentJobDatabaseId:
        overrides.currentJobDatabaseId ?? REGISTER_JOB_ID,
      predecessor: null,
      attachments: S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES.REGISTER.map((spec) => ({
        logicalName: spec.logicalName,
        role: spec.role,
        schemaVersion: spec.schemaVersion,
        mediaType: spec.mediaType,
        bytes:
          spec.logicalName === "upload/registration_archive.zip"
            ? Uint8Array.from(archive)
            : new Uint8Array([0x31])
      }))
    })
  )

const makeRegistrationRecovery = (
  archive: Uint8Array,
  current: S2SCurrentRunStageEvidence,
  overrides: Readonly<{
    workflowFileSha256?: string
    currentJobDatabaseId?: number
  }> = {}
) =>
  issueDurableRecovery([
    makeRegistrationEnvelope(archive, current, overrides)
  ])

const makeAdjudicationRecovery = (
  registration: Uint8Array,
  candidate: Uint8Array,
  current: S2SCurrentRunStageEvidence
) => {
  const registrationEnvelope = makeRegistrationEnvelope(registration, current)
  const registrationClaim = right(buildS2SEvidenceClaim(registrationEnvelope))
  const confirmationEnvelope = right(
    buildS2SSuccessStageEvidenceEnvelope({
      sourceCommitA: current.sourceCommitA,
      registrationCommitB: current.registrationCommitB,
      workflowRunId: current.workflowRunId,
      workflowRunCreatedAtUnixSeconds: current.workflowRunCreatedAtUnixSeconds,
      workflowApiPath: current.workflowApiPath,
      workflowFileSha256: current.workflowFileSha256,
      workflowContractSha256: current.workflowContractSha256,
      stage: "CONFIRM",
      currentJobDatabaseId: CONFIRM_JOB_ID,
      predecessor: {
        stage: "REGISTER",
        manifestRawSha256: registrationEnvelope.manifestRawSha256,
        claimRawSha256: registrationClaim.claimRawSha256
      },
      attachments: S2S_SUCCESS_STAGE_ATTACHMENT_PROFILES.CONFIRM.map((spec) => ({
        logicalName: spec.logicalName,
        role: spec.role,
        schemaVersion: spec.schemaVersion,
        mediaType: spec.mediaType,
        bytes:
          spec.logicalName === "upload/candidate_archive.zip"
            ? Uint8Array.from(candidate)
            : new Uint8Array([0x31])
      }))
    })
  )
  return issueDurableRecovery([registrationEnvelope, confirmationEnvelope])
}

const responseProvenance = (githubRequestId: string) =>
  Object.freeze({
    githubRequestId,
    githubApiVersionSelected: S2S_GITHUB_API_VERSION,
    responseEtag: `W/"${"e".repeat(64)}"`
  })

const runJson = (
  workflowApiPath: string,
  overrides: Readonly<Record<string, unknown>> = {}
) => ({
  id: RUN_ID,
  run_attempt: 1,
  name: "SWM-0W-S2S confirmatory",
  path: workflowApiPath,
  event: "push",
  head_branch: "main",
  head_sha: HEAD_SHA,
  repository: { full_name: "gj3447/HSWM" },
  head_repository: { full_name: "gj3447/HSWM" },
  status: "in_progress",
  conclusion: null,
  created_at: CREATED_AT,
  ...overrides
})

const jobJson = (
  id: number,
  name: "register" | "confirm" | "adjudicate",
  status: "queued" | "in_progress" | "completed",
  startedAt: string,
  completedAt: string | null,
  overrides: Readonly<Record<string, unknown>> = {}
) => ({
  id,
  run_id: RUN_ID,
  run_attempt: 1,
  name,
  head_sha: HEAD_SHA,
  status,
  conclusion: status === "completed" ? "success" : null,
  started_at: startedAt,
  completed_at: completedAt,
  labels: ["ubuntu-24.04"],
  ...overrides
})

const jobsJson = (
  stage: S2SConfirmatoryJobStage,
  idOverrides: Readonly<Partial<Record<"register" | "confirm" | "adjudicate", number>>> = {}
) => {
  const register =
    stage === "REGISTER"
      ? jobJson(
          idOverrides.register ?? REGISTER_JOB_ID,
          "register",
          "in_progress",
          "2026-08-21T03:10:34Z",
          null
        )
      : jobJson(
          idOverrides.register ?? REGISTER_JOB_ID,
          "register",
          "completed",
          "2026-08-21T03:10:34Z",
          "2026-08-21T03:20:00Z"
        )
  const confirm =
    stage === "REGISTER"
      ? jobJson(
          idOverrides.confirm ?? CONFIRM_JOB_ID,
          "confirm",
          "queued",
          "2026-08-21T03:10:35Z",
          null
        )
      : stage === "CONFIRM"
        ? jobJson(
            idOverrides.confirm ?? CONFIRM_JOB_ID,
            "confirm",
            "in_progress",
            "2026-08-21T03:20:01Z",
            null
          )
        : jobJson(
            idOverrides.confirm ?? CONFIRM_JOB_ID,
            "confirm",
            "completed",
            "2026-08-21T03:20:01Z",
            "2026-08-21T03:30:00Z"
          )
  const adjudicate =
    stage === "ADJUDICATE"
      ? jobJson(
          idOverrides.adjudicate ?? ADJUDICATE_JOB_ID,
          "adjudicate",
          "in_progress",
          "2026-08-21T03:30:01Z",
          null
        )
      : jobJson(
          idOverrides.adjudicate ?? ADJUDICATE_JOB_ID,
          "adjudicate",
          "queued",
          stage === "REGISTER"
            ? "2026-08-21T03:10:36Z"
            : "2026-08-21T03:20:02Z",
          null
        )
  return { total_count: 3, jobs: [register, confirm, adjudicate] }
}

const artifactJson = (role: ArtifactRole, archive: Uint8Array) => ({
  id:
    role === "REGISTRATION"
      ? REGISTRATION_ARTIFACT_ID
      : CANDIDATE_ARTIFACT_ID,
  name: role === "REGISTRATION" ? "s2s-registration" : "s2s-candidate",
  size_in_bytes: archive.byteLength,
  digest: `sha256:${rawS2SFileSha256(archive)}`,
  expired: false,
  created_at:
    role === "REGISTRATION"
      ? "2026-08-21T03:19:59Z"
      : "2026-08-21T03:29:59Z",
  expires_at: "2026-11-19T03:10:32Z",
  workflow_run: { id: RUN_ID, head_sha: HEAD_SHA }
})

interface ArtifactPlan {
  readonly role: ArtifactRole
  readonly archive: Uint8Array
  readonly positivePoll: 1 | 2 | 3 | null
}

interface ScenarioOptions {
  readonly stage: S2SConfirmatoryJobStage
  readonly positivePoll?: 1 | 2 | 3 | null
  readonly candidateRereadArchive?: Uint8Array
  readonly requestIdOverrides?: Readonly<Record<number, string>>
  readonly jobIdOverrides?: Readonly<
    Partial<Record<"register" | "confirm" | "adjudicate", number>>
  >
  readonly workflowApiPath?: string
  readonly runOverrides?: Readonly<Record<string, unknown>>
}

const makeScenario = (options: ScenarioOptions) => {
  const registration = registrationArchive()
  const candidate = candidateArchive()
  const positivePoll =
    options.positivePoll === undefined ? 1 : options.positivePoll
  const plans: ReadonlyArray<ArtifactPlan> =
    options.stage === "REGISTER"
      ? []
      : options.stage === "CONFIRM"
        ? [{ role: "REGISTRATION", archive: registration, positivePoll }]
        : [
            { role: "REGISTRATION", archive: registration, positivePoll },
            { role: "CANDIDATE", archive: candidate, positivePoll },
            {
              role: "CANDIDATE",
              archive: options.candidateRereadArchive ?? candidate,
              positivePoll
            }
          ]
  const calls: Array<string> = []
  let requestIndex = 0
  let planIndex = -1
  let artifactPoll = 0
  let activePlan: ArtifactPlan | undefined
  const nextMetadata = (label: string) => {
    const index = requestIndex
    requestIndex += 1
    calls.push(label)
    return {
      observedAtUnixSeconds: OBSERVED_AT + index * 10,
      githubRequestId:
        options.requestIdOverrides?.[index] ?? `REQ:${index}:${label}`
    }
  }
  const observer = S2SGitHubObserver.of({
    observeWorkflowRun: () => {
      const metadata = nextMetadata("run")
      return Effect.succeed(
        right(
          observeS2SGitHubWorkflowRun(
            jsonBytes(
              runJson(
                options.workflowApiPath ?? WORKFLOW_PATH,
                options.runOverrides
              )
            ),
            RUN_ID,
            metadata.observedAtUnixSeconds,
            responseProvenance(metadata.githubRequestId)
          )
        )
      )
    },
    observeWorkflowAttemptJobs: () => {
      planIndex += 1
      activePlan = plans[planIndex]
      artifactPoll = 0
      const metadata = nextMetadata("jobs")
      return Effect.succeed(
        right(
          observeS2SGitHubWorkflowAttemptJobs(
            jsonBytes(jobsJson(options.stage, options.jobIdOverrides)),
            RUN_ID,
            1,
            metadata.observedAtUnixSeconds,
            responseProvenance(metadata.githubRequestId)
          )
        )
      )
    },
    observeWorkflowRunsForHead: () =>
      Effect.dieMessage("artifact mechanics must not query runs-for-head"),
    observeRunArtifacts: () => {
      const plan = activePlan
      if (plan === undefined) {
        return Effect.dieMessage("artifact plan was not selected by fresh jobs")
      }
      artifactPoll += 1
      const present =
        plan.positivePoll !== null && artifactPoll >= plan.positivePoll
      const rows = present ? [artifactJson(plan.role, plan.archive)] : []
      const metadata = nextMetadata("artifacts")
      return Effect.succeed(
        right(
          observeS2SGitHubRunArtifacts(
            jsonBytes({ total_count: rows.length, artifacts: rows }),
            RUN_ID,
            metadata.observedAtUnixSeconds,
            responseProvenance(metadata.githubRequestId)
          )
        )
      )
    },
    observeArtifact: (artifactId) => {
      const plan = activePlan
      if (plan === undefined) {
        return Effect.dieMessage("artifact requery has no active plan")
      }
      const metadata = nextMetadata("artifact")
      return Effect.succeed(
        right(
          observeS2SGitHubArtifact(
            jsonBytes(artifactJson(plan.role, plan.archive)),
            artifactId,
            metadata.observedAtUnixSeconds,
            responseProvenance(metadata.githubRequestId)
          )
        )
      )
    },
    downloadArtifactArchive: (artifactId) => {
      const plan = activePlan
      if (plan === undefined) {
        return Effect.dieMessage("artifact download has no active plan")
      }
      const metadata = nextMetadata("download")
      const core: Omit<S2SGitHubArtifactDownloadReceipt, "receiptSha256"> =
        Object.freeze({
          schemaVersion: S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
          apiVersion: S2S_GITHUB_API_VERSION,
          repository: S2S_GITHUB_REPOSITORY,
          artifactId,
          endpointPathAndQuery: `/repos/${S2S_GITHUB_REPOSITORY}/actions/artifacts/${artifactId}/zip`,
          downloadedAtUnixSeconds: metadata.observedAtUnixSeconds,
          redirectHttpStatus: 302,
          redirectGitHubRequestId: metadata.githubRequestId,
          redirectGitHubApiVersionSelected: S2S_GITHUB_API_VERSION,
          redirectResponseEtag: null,
          redirectUrlSha256: "a".repeat(64),
          redirectOrigin: "https://objects.example.invalid",
          archiveHttpStatus: 200,
          archiveMediaType: "application/zip",
          archiveResponseEtag: `"${"a".repeat(64)}"`,
          archiveByteLength: plan.archive.byteLength,
          downloadedArchiveSha256: rawS2SFileSha256(plan.archive)
        })
      const download: S2SGitHubArtifactDownload = Object.freeze({
        receipt: Object.freeze({
          ...core,
          receiptSha256: right(canonicalS2SControlSha256(core))
        }),
        readArchiveBytes: () => new Uint8Array(plan.archive)
      })
      return Effect.succeed(download)
    }
  })
  return { observer, calls, plans }
}

const confirmationReads = (
  reads: S2SStageArtifactReadsService
): S2SConfirmStageArtifactReads => {
  if (reads.stage !== "CONFIRM") {
    throw new Error("expected CONFIRM fixed read surface")
  }
  return reads
}

const adjudicationReads = (
  reads: S2SStageArtifactReadsService
): S2SAdjudicateStageArtifactReads => {
  if (reads.stage !== "ADJUDICATE") {
    throw new Error("expected ADJUDICATE fixed read surface")
  }
  return reads
}

it.effect("exposes only lazy fixed zero-identity stage Effects", () => {
  const confirm = makeScenario({ stage: "CONFIRM" })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM"),
    confirm.observer,
    (reads) =>
      Effect.gen(function* () {
        const fixed = confirmationReads(reads)
        expect(Object.keys(fixed).sort()).toEqual([
          "confirmReadRegistration",
          "stage"
        ])
        expect(typeof fixed.confirmReadRegistration).not.toBe("function")
        expect("observeRoleArtifact" in fixed).toBe(false)
        expect("readback" in fixed).toBe(false)
        expect(confirm.calls).toHaveLength(0)
        const result = yield* fixed.confirmReadRegistration
        expect(result._tag).toBe("ValidatedStageArtifactRead")
        expect(result.operation).toBe("CONFIRM_READ_REGISTRATION")
        expect(result.role).toBe("REGISTRATION")
        expect(result.permitEvidence.authorityScope).toBe(
          "TEST_ONLY_NON_AUTHORIZING"
        )
        expect(result.permitEvidence.authorizationClaimed).toBe(false)
        expect(result.permitEvidence.ledgerEntries).toHaveLength(12)
        const { receiptSha256, ...permitCore } = result.permitEvidence
        expect(right(canonicalS2SControlSha256(permitCore))).toBe(
          receiptSha256
        )
        expect(result.validatedArchive.archiveSha256).toBe(
          rawS2SFileSha256(result.readArchiveBytes())
        )
        if (false) {
          // @ts-expect-error fixed operation is an Effect property, not a method
          fixed.confirmReadRegistration(RUN_ID, HEAD_SHA, "REGISTRATION")
        }
      })
  )
})

it.effect("builds and independently replays the bounded poll-three registration read", () => {
  const scenario = makeScenario({ stage: "CONFIRM", positivePoll: 3 })
  const currentRunEvidence = makeCurrentRunEvidence("CONFIRM")
  const sourceArchive = scenario.plans[0]?.archive
  if (sourceArchive === undefined) {
    return Effect.dieMessage("registration source archive fixture is absent")
  }
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const predecessorRecovery = yield* makeRegistrationRecovery(
          sourceArchive,
          currentRunEvidence
        )
        expect(isAuthenticS2SDurableEvidenceRecovery(predecessorRecovery)).toBe(
          true
        )
        const validatedCurrent = right(
          validateS2SCurrentRunStageEvidenceForArtifactReplay(currentRunEvidence)
        )
        expect(validatedCurrent.receiptSha256).toBe(
          currentRunEvidence.receiptSha256
        )
        expect(
          validateS2SCurrentRunStageEvidenceForArtifactReplay(
            new Proxy(currentRunEvidence, {})
          )
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "CURRENT_RUN_BINDING_MISMATCH" }
        })
        const validatedRead = yield* confirmationReads(
          reads
        ).confirmReadRegistration
        const built = right(
          buildS2SStageArtifactReadReplay({
            validatedRead,
            currentRunEvidence,
            predecessorRecovery
          })
        )
        const carrierBytes = built.readCarrierBytes()
        const replayed = right(
          validateS2SStageArtifactReadReplay({
            carrierBytes,
            currentRunEvidence,
            predecessorRecovery
          })
        )
        const rebuilt = right(
          buildS2SStageArtifactReadReplay({
            validatedRead,
            currentRunEvidence,
            predecessorRecovery
          })
        )
        const wrongWorkflowRecovery = yield* makeRegistrationRecovery(
          sourceArchive,
          currentRunEvidence,
          { workflowFileSha256: "e".repeat(64) }
        )
        expect(
          buildS2SStageArtifactReadReplay({
            validatedRead,
            currentRunEvidence,
            predecessorRecovery: wrongWorkflowRecovery
          })
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "ARCHIVE_REFERENCE_INVALID" }
        })
        const wrongJobRecovery = yield* makeRegistrationRecovery(
          sourceArchive,
          currentRunEvidence,
          { currentJobDatabaseId: REGISTER_JOB_ID + 99 }
        )
        expect(
          buildS2SStageArtifactReadReplay({
            validatedRead,
            currentRunEvidence,
            predecessorRecovery: wrongJobRecovery
          })
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "ARCHIVE_REFERENCE_INVALID" }
        })
        expect(
          buildS2SStageArtifactReadReplay({
            validatedRead: Object.freeze({ ...validatedRead }),
            currentRunEvidence,
            predecessorRecovery
          })
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "INPUT_INVALID" }
        })
        let recoveryGetterCount = 0
        const counterfeitRecovery = Object.create(null, {
          chain: {
            enumerable: true,
            get: () => {
              recoveryGetterCount += 1
              throw new Error("counterfeit chain getter must remain inert")
            }
          },
          latest: {
            enumerable: true,
            get: () => {
              recoveryGetterCount += 1
              throw new Error("counterfeit latest getter must remain inert")
            }
          }
        })
        const lazyBuild = buildS2SStageArtifactReadReplayEffect({
          validatedRead,
          currentRunEvidence,
          predecessorRecovery: counterfeitRecovery
        })
        expect(recoveryGetterCount).toBe(0)
        const counterfeitOutcome = yield* lazyBuild.pipe(Effect.either)
        expect(counterfeitOutcome).toMatchObject({
          _tag: "Left",
          left: { reason: "ARCHIVE_REFERENCE_INVALID" }
        })
        expect(recoveryGetterCount).toBe(0)
        const effectBuilt = yield* buildS2SStageArtifactReadReplayEffect({
          validatedRead,
          currentRunEvidence,
          predecessorRecovery
        })
        expect(effectBuilt.carrierRawSha256).toBe(built.carrierRawSha256)
        const invalidEffect = yield* validateS2SStageArtifactReadReplayEffect(
          {}
        ).pipe(Effect.either)
        expect(invalidEffect).toMatchObject({
          _tag: "Left",
          left: { reason: "INPUT_INVALID" }
        })
        expect(replayed.manifest.operation).toBe(
          "CONFIRM_READ_REGISTRATION"
        )
        expect(replayed.manifest.successful_attempt_ordinal).toBe(3)
        expect(replayed.manifest.observation_count).toBe(11)
        expect(replayed.observations).toHaveLength(11)
        expect({
          carrierRawSha256: built.carrierRawSha256,
          manifestRawSha256: built.manifestRawSha256,
          carrierByteLength: built.carrierByteLength
        }).toEqual({
          carrierRawSha256:
            "92c7eafc1229f2e32bc9a91771278d53f329cb46970b6ee14eeb758677bd0c90",
          manifestRawSha256:
            "78d121dc38df0d61232f372dd9755f9e5c35c976c3c8d0280a15238299b257c0",
          carrierByteLength: 17_803
        })
        expect(replayed.manifest.archive_reference).toMatchObject({
          source_stage: "REGISTER",
          logical_name: "upload/registration_archive.zip",
          raw_sha256: rawS2SFileSha256(sourceArchive)
        })
        expect(rebuilt.carrierRawSha256).toBe(built.carrierRawSha256)
        expect(rebuilt.readCarrierBytes()).toEqual(carrierBytes)
        expect(replayed.readArchiveBytes()).toEqual(sourceArchive)

        const parsedCarrier = right(
          validateS2SArtifactZip(carrierBytes, {
            expectedArchiveSha256: built.carrierRawSha256,
            expectedArchiveByteLength: carrierBytes.byteLength,
            expectedMembers: [
              {
                name: S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MEMBER_NAME,
                maximumBytes:
                  S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MAX_BYTES
              },
              {
                name: S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MEMBER_NAME,
                maximumBytes:
                  S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MAX_BYTES
              }
            ],
            maximumArchiveBytes: S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES,
            maximumExpandedBytes:
              S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MAX_BYTES +
              S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MAX_BYTES
          })
        )
        expect(parsedCarrier.members.map(({ name }) => name)).toEqual([
          S2S_STAGE_ARTIFACT_READ_REPLAY_MANIFEST_MEMBER_NAME,
          S2S_STAGE_ARTIFACT_READ_REPLAY_OBSERVATIONS_MEMBER_NAME
        ])
        const manifestMember = parsedCarrier.members[0]
        const observationsMember = parsedCarrier.members[1]
        if (manifestMember === undefined || observationsMember === undefined) {
          throw new Error("fixed replay members are absent")
        }
        expect(manifestMember.readBytes()).toEqual(
          right(canonicalS2SControlJsonBytes(built.manifest))
        )
        expect(observationsMember.readBytes()).toEqual(
          built.readObservationBlob()
        )

        const mutatedObservationBytes = observationsMember.readBytes()
        mutatedObservationBytes[0] = (mutatedObservationBytes[0] ?? 0) ^ 1
        const observationMutation = right(
          buildS2SStoredZip([
            {
              name: manifestMember.name,
              bytes: manifestMember.readBytes()
            },
            {
              name: observationsMember.name,
              bytes: mutatedObservationBytes
            }
          ])
        )
        const observationRejected = validateS2SStageArtifactReadReplay({
          carrierBytes: observationMutation.readArchiveBytes(),
          currentRunEvidence,
          predecessorRecovery
        })
        expect(Either.isLeft(observationRejected)).toBe(true)
        if (Either.isLeft(observationRejected)) {
          expect(observationRejected.left.reason).toBe(
            "POLL_TOPOLOGY_INVALID"
          )
        }

        const coherentlyMutatedManifest = structuredClone(built.manifest)
        const [firstDescriptor, ...remainingDescriptors] =
          coherentlyMutatedManifest.observations
        if (firstDescriptor === undefined) {
          throw new Error("golden replay has no first observation")
        }
        const {
          replay_receipt_sha256: declaredCoherentReceipt,
          ...coherentlyMutatedCore
        } = {
          ...coherentlyMutatedManifest,
          observations: [
            {
              ...firstDescriptor,
              github_request_id: "REQ:COHERENT-MANIFEST-TAMPER"
            },
            ...remainingDescriptors
          ]
        }
        void declaredCoherentReceipt
        const coherentlyMutatedBytes = right(
          canonicalS2SControlJsonBytes({
            ...coherentlyMutatedCore,
            replay_receipt_sha256: right(
              canonicalS2SControlSha256(coherentlyMutatedCore)
            )
          })
        )
        const coherentMutationCarrier = right(
          buildS2SStoredZip([
            {
              name: manifestMember.name,
              bytes: coherentlyMutatedBytes
            },
            {
              name: observationsMember.name,
              bytes: observationsMember.readBytes()
            }
          ])
        )
        expect(
          validateS2SStageArtifactReadReplay({
            carrierBytes: coherentMutationCarrier.readArchiveBytes(),
            currentRunEvidence,
            predecessorRecovery
          })
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "OBSERVATION_REPLAY_INVALID" }
        })

        const manifestMutation = {
          ...structuredClone(built.manifest),
          source_commit_a: "c".repeat(40)
        }
        const manifestMutationBytes = right(
          canonicalS2SControlJsonBytes(manifestMutation)
        )
        const manifestMutationCarrier = right(
          buildS2SStoredZip([
            {
              name: manifestMember.name,
              bytes: manifestMutationBytes
            },
            {
              name: observationsMember.name,
              bytes: observationsMember.readBytes()
            }
          ])
        )
        const manifestRejected = validateS2SStageArtifactReadReplay({
          carrierBytes: manifestMutationCarrier.readArchiveBytes(),
          currentRunEvidence,
          predecessorRecovery
        })
        expect(Either.isLeft(manifestRejected)).toBe(true)
        if (Either.isLeft(manifestRejected)) {
          expect(manifestRejected.left.reason).toBe(
            "MANIFEST_SELF_HASH_MISMATCH"
          )
        }

        const missingSource = validateS2SStageArtifactReadReplay({
          carrierBytes,
          currentRunEvidence,
          predecessorRecovery: { chain: [], latest: null }
        })
        expect(Either.isLeft(missingSource)).toBe(true)
        if (Either.isLeft(missingSource)) {
          expect(missingSource.left.reason).toBe("ARCHIVE_REFERENCE_INVALID")
        }

        const sourceStage = predecessorRecovery.latest
        const corruptClaimBytes = sourceStage.claim.canonicalBytes
        corruptClaimBytes[0] = (corruptClaimBytes[0] ?? 0) ^ 1
        const wrongClaimStage = Object.freeze({
          envelope: sourceStage.envelope,
          claim: Object.freeze({
            document: sourceStage.claim.document,
            canonicalBytes: corruptClaimBytes,
            claimRawSha256: sourceStage.claim.claimRawSha256
          })
        })
        const wrongClaim = validateS2SStageArtifactReadReplay({
          carrierBytes,
          currentRunEvidence,
          predecessorRecovery: Object.freeze({
            chain: Object.freeze([wrongClaimStage]),
            latest: wrongClaimStage
          })
        })
        expect(wrongClaim).toMatchObject({
          _tag: "Left",
          left: { reason: "ARCHIVE_REFERENCE_INVALID" }
        })

        let counterfeitAttachmentReadCount = 0
        const unavailableAttachments = sourceStage.envelope.attachments.map(
          (attachment) =>
            attachment.descriptor.logical_name ===
            "upload/registration_archive.zip"
              ? Object.freeze({
                  descriptor: attachment.descriptor,
                  readBytes: (): Uint8Array => {
                    counterfeitAttachmentReadCount += 1
                    throw new Error("source bytes unavailable")
                  }
                })
              : attachment
        )
        const unavailableEnvelope = Object.freeze({
          document: sourceStage.envelope.document,
          canonicalBytes: sourceStage.envelope.canonicalBytes,
          manifestRawSha256: sourceStage.envelope.manifestRawSha256,
          attachments: Object.freeze(unavailableAttachments)
        })
        const unavailableStage = Object.freeze({
          envelope: unavailableEnvelope,
          claim: sourceStage.claim
        })
        expect(
          validateS2SStageArtifactReadReplay({
            carrierBytes,
            currentRunEvidence,
            predecessorRecovery: Object.freeze({
              chain: Object.freeze([unavailableStage]),
              latest: unavailableStage
            })
          })
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "ARCHIVE_REFERENCE_INVALID" }
        })
        expect(counterfeitAttachmentReadCount).toBe(0)

        const exposedCarrier = built.readCarrierBytes()
        exposedCarrier.fill(0)
        expect(rawS2SFileSha256(built.readCarrierBytes())).toBe(
          built.carrierRawSha256
        )
        const exposedObservations = built.readObservationBlob()
        exposedObservations.fill(0)
        expect(rawS2SFileSha256(built.readObservationBlob())).toBe(
          built.manifest.observation_blob_sha256
        )
        const exposedArchive = built.readArchiveBytes()
        exposedArchive.fill(0)
        expect(rawS2SFileSha256(built.readArchiveBytes())).toBe(
          built.manifest.artifact_sha256
        )
        const exposedManifest = built.manifest as {
          source_commit_a: string
        }
        exposedManifest.source_commit_a = "d".repeat(40)
        expect(built.manifest.source_commit_a).toBe(SOURCE_COMMIT_A)
        expect(
          validateS2SStageArtifactReadReplay({
            carrierBytes: Buffer.from(carrierBytes),
            currentRunEvidence,
            predecessorRecovery
          })
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "BYTE_BUDGET_EXCEEDED" }
        })
        expect(
          validateS2SStageArtifactReadReplay({
            carrierBytes: new Uint8Array(
              S2S_STAGE_ARTIFACT_READ_REPLAY_MAX_BYTES + 1
            ),
            currentRunEvidence,
            predecessorRecovery
          })
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "BYTE_BUDGET_EXCEEDED" }
        })
        if (typeof SharedArrayBuffer !== "undefined") {
          expect(
            validateS2SStageArtifactReadReplay({
              carrierBytes: new Uint8Array(new SharedArrayBuffer(1)),
              currentRunEvidence,
              predecessorRecovery
            })
          ).toMatchObject({
            _tag: "Left",
            left: { reason: "BYTE_BUDGET_EXCEEDED" }
          })
        }
        const accessorRoot = Object.create(null, {
          carrierBytes: {
            enumerable: true,
            get: () => carrierBytes
          },
          currentRunEvidence: {
            enumerable: true,
            value: currentRunEvidence
          },
          predecessorRecovery: {
            enumerable: true,
            value: predecessorRecovery
          }
        })
        expect(validateS2SStageArtifactReadReplay(accessorRoot)).toMatchObject({
          _tag: "Left",
          left: { reason: "INPUT_INVALID" }
        })
        expect(
          validateS2SStageArtifactReadReplay(
            new Proxy(
              { carrierBytes, currentRunEvidence, predecessorRecovery },
              {}
            )
          )
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "INPUT_INVALID" }
        })
        expect(
          validateS2SStageArtifactReadReplay({
            carrierBytes,
            currentRunEvidence: new Proxy(currentRunEvidence, {}),
            predecessorRecovery
          })
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "CURRENT_RUN_BINDING_MISMATCH" }
        })
        expect(
          validateS2SStageArtifactReadReplay({
            carrierBytes,
            currentRunEvidence,
            predecessorRecovery: new Proxy(predecessorRecovery, {})
          })
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "ARCHIVE_REFERENCE_INVALID" }
        })
        expect(
          validateS2SStageArtifactReadReplay({
            carrierBytes,
            currentRunEvidence,
            predecessorRecovery: Object.freeze({ ...predecessorRecovery })
          })
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "ARCHIVE_REFERENCE_INVALID" }
        })
      })
  )
})

it.effect("replays the adjudication chain and binds the two candidate reads", () => {
  const scenario = makeScenario({ stage: "ADJUDICATE", positivePoll: 3 })
  const currentRunEvidence = makeCurrentRunEvidence("ADJUDICATE")
  const registration = scenario.plans[0]?.archive
  const candidate = scenario.plans[1]?.archive
  if (registration === undefined || candidate === undefined) {
    return Effect.dieMessage("adjudication archive fixtures are absent")
  }
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("ADJUDICATE"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const predecessorRecovery = yield* makeAdjudicationRecovery(
          registration,
          candidate,
          currentRunEvidence
        )
        const fixed = adjudicationReads(reads)
        const registrationRead = yield* fixed.adjudicateReadRegistration
        const firstRead = yield* fixed.adjudicateReadCandidateFirst
        const reread = yield* fixed.adjudicateRereadCandidate
        const registrationReplay = right(
          buildS2SStageArtifactReadReplay({
            validatedRead: registrationRead,
            currentRunEvidence,
            predecessorRecovery
          })
        )
        const firstReplay = right(
          buildS2SStageArtifactReadReplay({
            validatedRead: firstRead,
            currentRunEvidence,
            predecessorRecovery
          })
        )
        const rereadReplay = right(
          buildS2SStageArtifactReadReplay({
            validatedRead: reread,
            currentRunEvidence,
            predecessorRecovery
          })
        )
        const pair = right(
          validateS2SCandidateReadReplayPair(firstReplay, rereadReplay)
        )
        expect(registrationReplay.manifest.archive_reference.source_stage).toBe(
          "REGISTER"
        )
        expect(firstReplay.manifest.archive_reference.source_stage).toBe(
          "CONFIRM"
        )
        expect(firstReplay.manifest.successful_attempt_ordinal).toBe(3)
        expect(firstReplay.manifest.observation_count).toBe(11)
        expect(firstReplay.manifest.candidate_fingerprint_sha256).not.toBeNull()
        expect(pair[0].manifest.candidate_fingerprint_sha256).toBe(
          pair[1].manifest.candidate_fingerprint_sha256
        )
        expect(pair[0].readArchiveBytes()).toEqual(candidate)
        expect(pair[1].readArchiveBytes()).toEqual(candidate)

        const otherCurrentRunEvidence = makeCurrentRunEvidence(
          "ADJUDICATE",
          "8".repeat(64)
        )
        const otherCurrentRereadReplay = right(
          buildS2SStageArtifactReadReplay({
            validatedRead: reread,
            currentRunEvidence: otherCurrentRunEvidence,
            predecessorRecovery
          })
        )
        expect(
          validateS2SCandidateReadReplayPair(
            firstReplay,
            otherCurrentRereadReplay
          )
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "LEDGER_BINDING_MISMATCH" }
        })

        const alternateScenario = makeScenario({
          stage: "ADJUDICATE",
          positivePoll: 3,
          requestIdOverrides: { 0: "REQ:ALTERNATE:0" }
        })
        let alternateRereadReplay:
          | S2SStageArtifactReadReplaySnapshot
          | undefined
        yield* probeS2SStageArtifactReadMechanicsForTest(
          makeSeed("ADJUDICATE"),
          alternateScenario.observer,
          (alternateReads) =>
            Effect.gen(function* () {
              const alternateFixed = adjudicationReads(alternateReads)
              yield* alternateFixed.adjudicateReadRegistration
              yield* alternateFixed.adjudicateReadCandidateFirst
              const alternateReread =
                yield* alternateFixed.adjudicateRereadCandidate
              alternateRereadReplay = right(
                buildS2SStageArtifactReadReplay({
                  validatedRead: alternateReread,
                  currentRunEvidence,
                  predecessorRecovery
                })
              )
            })
        )
        if (alternateRereadReplay === undefined) {
          return yield* Effect.dieMessage(
            "alternate candidate reread replay fixture was not produced"
          )
        }
        expect(
          validateS2SCandidateReadReplayPair(
            firstReplay,
            alternateRereadReplay
          )
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "LEDGER_BINDING_MISMATCH" }
        })

        const reversed = validateS2SCandidateReadReplayPair(
          rereadReplay,
          firstReplay
        )
        expect(Either.isLeft(reversed)).toBe(true)
        if (Either.isLeft(reversed)) {
          expect(reversed.left.reason).toBe(
            "CANDIDATE_FINGERPRINT_MISMATCH"
          )
        }
        expect(
          validateS2SCandidateReadReplayPair(
            structuredClone(firstReplay.manifest),
            rereadReplay
          )
        ).toMatchObject({
          _tag: "Left",
          left: { reason: "INPUT_INVALID" }
        })
      })
  )
})

it.effect("preserves fully validated replay carriers through one create-only three-stage chain", () => {
  const durableRoot = mkdtempSync(join(tmpdir(), "hswm-s2s-replay-profile-"))
  const confirmScenario = makeScenario({ stage: "CONFIRM", positivePoll: 3 })
  const adjudicateScenario = makeScenario({
    stage: "ADJUDICATE",
    positivePoll: 3
  })
  const registrationArchiveBytes = confirmScenario.plans[0]?.archive
  const adjudicateRegistrationBytes = adjudicateScenario.plans[0]?.archive
  const candidateArchiveBytes = adjudicateScenario.plans[1]?.archive
  if (
    registrationArchiveBytes === undefined ||
    adjudicateRegistrationBytes === undefined ||
    candidateArchiveBytes === undefined
  ) {
    rmSync(durableRoot, { force: true, recursive: true })
    return Effect.dieMessage("durable replay-profile fixtures are incomplete")
  }
  expect(adjudicateRegistrationBytes).toEqual(registrationArchiveBytes)

  const confirmCurrent = makeCurrentRunEvidence("CONFIRM")
  const adjudicateCurrent = makeCurrentRunEvidence("ADJUDICATE")
  const layer = makeS2SDurableEvidenceFileStoreLayer(durableRoot)
  const program = Effect.gen(function* () {
    const store = yield* S2SDurableEvidenceFileStore
    const registrationEnvelope = makeRegistrationEnvelope(
      registrationArchiveBytes,
      confirmCurrent
    )
    const registrationPublication = yield* store.commit(registrationEnvelope)

    const confirmationResult: {
      publication?: S2SStageReadReplayDurablePublication
      replay?: S2SStageArtifactReadReplaySnapshot
    } = {}
    yield* probeS2SStageArtifactReadMechanicsForTest(
      makeSeed("CONFIRM"),
      confirmScenario.observer,
      (reads) =>
        Effect.gen(function* () {
          const registrationRead = yield* confirmationReads(
            reads
          ).confirmReadRegistration
          const replay = right(
            buildS2SStageArtifactReadReplay({
              validatedRead: registrationRead,
              currentRunEvidence: confirmCurrent,
              predecessorRecovery: registrationPublication.recovery
            })
          )
          const predecessor = registrationPublication.recovery.latest
          const predecessorBinding = {
            stage: "REGISTER" as const,
            manifestRawSha256: predecessor.envelope.manifestRawSha256,
            claimRawSha256: predecessor.claim.claimRawSha256
          }
          const attachmentBytes = {
            "input/registration_read.zip": replay.readCarrierBytes(),
            "upload/candidate_archive.zip": candidateArchiveBytes
          }
          const envelopeInput = makeConsumerEnvelopeInput(
            confirmCurrent,
            predecessorBinding,
            attachmentBytes
          )
          const wrongPredecessor = makeConsumerEnvelopeInput(
            confirmCurrent,
            {
              ...predecessorBinding,
              claimRawSha256: "f".repeat(64)
            },
            attachmentBytes
          )
          const wrongPredecessorOutcome =
            yield* commitS2SStageReadReplayProfileAttachments({
              envelopeInput: wrongPredecessor,
              currentRunEvidence: confirmCurrent
            }).pipe(Effect.either)
          expect(wrongPredecessorOutcome).toMatchObject({
            _tag: "Left",
            left: { reason: "PREDECESSOR_ENVELOPE_MISMATCH" }
          })
          const publication =
            yield* commitS2SStageReadReplayProfileAttachments({
              envelopeInput,
              currentRunEvidence: confirmCurrent
            })
          confirmationResult.publication = publication
          confirmationResult.replay = replay
        })
    )
    const confirmationPublication = confirmationResult.publication
    const confirmationReplay = confirmationResult.replay
    if (
      confirmationPublication === undefined ||
      confirmationReplay === undefined
    ) {
      return yield* Effect.dieMessage(
        "confirmation replay-profile publication was not produced"
      )
    }
    expect(confirmationPublication._tag).toBe(
      "StageReadReplayProfileCommitted"
    )
    expect(confirmationPublication.replayAttachments).toMatchObject([
      {
        logicalName: "input/registration_read.zip",
        operation: "CONFIRM_READ_REGISTRATION",
        carrierRawSha256: confirmationReplay.carrierRawSha256
      }
    ])

    const adjudicationResult: {
      duplicate?: S2SStageReadReplayDurablePublication
      publication?: S2SStageReadReplayDurablePublication
    } = {}
    yield* probeS2SStageArtifactReadMechanicsForTest(
      makeSeed("ADJUDICATE"),
      adjudicateScenario.observer,
      (reads) =>
        Effect.gen(function* () {
          const fixed = adjudicationReads(reads)
          const registrationRead = yield* fixed.adjudicateReadRegistration
          const candidateFirst = yield* fixed.adjudicateReadCandidateFirst
          const candidateReread = yield* fixed.adjudicateRereadCandidate
          const predecessorRecovery = confirmationPublication.recovery
          const registrationReplay = right(
            buildS2SStageArtifactReadReplay({
              validatedRead: registrationRead,
              currentRunEvidence: adjudicateCurrent,
              predecessorRecovery
            })
          )
          const candidateFirstReplay = right(
            buildS2SStageArtifactReadReplay({
              validatedRead: candidateFirst,
              currentRunEvidence: adjudicateCurrent,
              predecessorRecovery
            })
          )
          const candidateRereadReplay = right(
            buildS2SStageArtifactReadReplay({
              validatedRead: candidateReread,
              currentRunEvidence: adjudicateCurrent,
              predecessorRecovery
            })
          )
          const predecessor = predecessorRecovery.latest
          const predecessorBinding = {
            stage: "CONFIRM" as const,
            manifestRawSha256: predecessor.envelope.manifestRawSha256,
            claimRawSha256: predecessor.claim.claimRawSha256
          }
          const envelopeInput = makeConsumerEnvelopeInput(
            adjudicateCurrent,
            predecessorBinding,
            {
              "input/registration_read.zip":
                registrationReplay.readCarrierBytes(),
              "input/candidate_first_read.zip":
                candidateFirstReplay.readCarrierBytes(),
              "input/candidate_reread.zip":
                candidateRereadReplay.readCarrierBytes()
            }
          )
          const swapped = makeConsumerEnvelopeInput(
            adjudicateCurrent,
            predecessorBinding,
            {
              "input/registration_read.zip":
                registrationReplay.readCarrierBytes(),
              "input/candidate_first_read.zip":
                candidateRereadReplay.readCarrierBytes(),
              "input/candidate_reread.zip":
                candidateFirstReplay.readCarrierBytes()
            }
          )
          const rejected =
            yield* commitS2SStageReadReplayProfileAttachments({
              envelopeInput: swapped,
              currentRunEvidence: adjudicateCurrent
            }).pipe(Effect.either)
          expect(rejected).toMatchObject({
            _tag: "Left",
            left: { reason: "REPLAY_OPERATION_MISMATCH" }
          })

          const publication =
            yield* commitS2SStageReadReplayProfileAttachments({
              envelopeInput,
              currentRunEvidence: adjudicateCurrent
            })
          const duplicate =
            yield* commitS2SStageReadReplayProfileAttachments({
              envelopeInput,
              currentRunEvidence: adjudicateCurrent
            })
          adjudicationResult.duplicate = duplicate
          adjudicationResult.publication = publication
        })
    )
    const adjudicationPublication = adjudicationResult.publication
    const adjudicationDuplicate = adjudicationResult.duplicate
    if (
      adjudicationPublication === undefined ||
      adjudicationDuplicate === undefined
    ) {
      return yield* Effect.dieMessage(
        "adjudication replay-profile publication was not produced"
      )
    }
    expect(adjudicationPublication._tag).toBe(
      "StageReadReplayProfileCommitted"
    )
    expect(adjudicationDuplicate._tag).toBe(
      "StageReadReplayProfileAlreadyCommitted"
    )
    expect(
      adjudicationPublication.replayAttachments.map(({ operation }) =>
        operation
      )
    ).toEqual([
      "ADJUDICATE_READ_CANDIDATE_FIRST",
      "ADJUDICATE_REREAD_CANDIDATE",
      "ADJUDICATE_READ_REGISTRATION"
    ])

    const restarted = yield* Effect.gen(function* () {
      const restartedStore = yield* S2SDurableEvidenceFileStore
      const identity = adjudicationPublication.recovery.latest.envelope.document
      return yield* restartedStore.recover({
        sourceCommitA: identity.source_commit_a,
        registrationCommitB: identity.registration_commit_b,
        workflowRunId: identity.workflow_run_id,
        stage: "ADJUDICATE"
      })
    }).pipe(Effect.provide(makeS2SDurableEvidenceFileStoreLayer(durableRoot)))
    expect(isAuthenticS2SDurableEvidenceRecovery(restarted)).toBe(true)
    expect(
      restarted.chain.map(({ envelope }) => envelope.document.stage)
    ).toEqual(["REGISTER", "CONFIRM", "ADJUDICATE"])
    expect(restarted.latest.envelope.manifestRawSha256).toBe(
      adjudicationPublication.manifestRawSha256
    )

    let accessorReads = 0
    const accessorInput = Object.create(Object.prototype, {
      envelopeInput: {
        enumerable: true,
        get: () => {
          accessorReads += 1
          throw new Error("accessor input must remain inert")
        }
      },
      currentRunEvidence: {
        enumerable: true,
        value: confirmCurrent
      }
    })
    const lazy = commitS2SStageReadReplayProfileAttachments(accessorInput)
    expect(accessorReads).toBe(0)
    const accessorOutcome = yield* lazy.pipe(Effect.either)
    expect(accessorOutcome).toMatchObject({
      _tag: "Left",
      left: { reason: "INPUT_INVALID" }
    })
    expect(accessorReads).toBe(0)
  })

  return program.pipe(
    Effect.provide(layer),
    Effect.ensuring(
      Effect.sync(() => rmSync(durableRoot, { force: true, recursive: true }))
    )
  )
})

it.effect("retains the complete bounded raw lookup trace on poll one, two, and three", () =>
  Effect.gen(function* () {
    expect(S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_MAX_RAW_BYTES).toBe(
      8 * S2S_GITHUB_JSON_MAX_BYTES
    )
    for (const positivePoll of [1, 2, 3] as const) {
      const scenario = makeScenario({ stage: "CONFIRM", positivePoll })
      yield* probeS2SStageArtifactReadMechanicsForTest(
        makeSeed("CONFIRM"),
        scenario.observer,
        (reads) =>
          Effect.gen(function* () {
            const result = yield* confirmationReads(
              reads
            ).confirmReadRegistration
            const trace = result.successfulLookupTrace
            expect(trace.schemaVersion).toBe(
              S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_SCHEMA_VERSION
            )
            expect(trace.successfulAttemptOrdinal).toBe(positivePoll)
            expect(trace.attempts).toHaveLength(positivePoll)
            expect(trace.attempts.map((attempt) => attempt.ordinal)).toEqual(
              Array.from({ length: positivePoll }, (_, index) => index + 1)
            )
            expect(
              trace.attempts.map((attempt) => attempt.classification)
            ).toEqual([
              ...Array.from(
                { length: positivePoll - 1 },
                () => "ARTIFACT_NOT_OBSERVED"
              ),
              "ARTIFACT_OBSERVED"
            ])
            for (const attempt of trace.attempts) {
              const targetArtifacts =
                attempt.artifactsObservation.receipt.projection.artifacts.filter(
                  (artifact) => artifact.name === "s2s-registration"
                )
              expect(targetArtifacts).toHaveLength(
                attempt.classification === "ARTIFACT_OBSERVED" ? 1 : 0
              )
            }
            const observations = [
              trace.initialWorkflowRunObservation,
              trace.workflowJobsObservation,
              ...trace.attempts.flatMap((attempt) => [
                attempt.artifactsObservation,
                attempt.workflowRunObservation
              ])
            ]
            expect(
              new Set(
                observations.map(
                  (observation) => observation.receipt.githubRequestId
                )
              ).size
            ).toBe(2 + 2 * positivePoll)
            expect(trace.totalRawBodyByteLength).toBe(
              observations.reduce(
                (total, observation) =>
                  total + observation.receipt.rawBodyByteLength,
                0
              )
            )
            expect(trace.totalRawBodyByteLength).toBeLessThanOrEqual(
              (2 + 2 * positivePoll) * S2S_GITHUB_JSON_MAX_BYTES
            )
            expect(trace.totalRawBodyByteLength).toBeLessThanOrEqual(
              S2S_ARTIFACT_SUCCESSFUL_LOOKUP_TRACE_MAX_RAW_BYTES
            )
            expect(result.permitEvidence.ledgerEntries).toHaveLength(
              10 + 2 * positivePoll
            )
            expect(result.permitEvidence.ledgerEntries.slice(4)).toHaveLength(
              6 + 2 * positivePoll
            )
            const ledgerEntry = (
              phase: string,
              observation: S2SGitHubObservation
            ) => ({
              operation: "CONFIRM_READ_REGISTRATION",
              phase,
              githubRequestId: observation.receipt.githubRequestId,
              receiptSha256: observation.receipt.receiptSha256,
              observedAtUnixSeconds: observation.receipt.observedAtUnixSeconds
            })
            expect(result.permitEvidence.ledgerEntries.slice(4)).toEqual([
              ledgerEntry("LOOKUP_RUN_START", trace.initialWorkflowRunObservation),
              ledgerEntry("LOOKUP_JOBS", trace.workflowJobsObservation),
              ...trace.attempts.flatMap((attempt) => [
                ledgerEntry(
                  `LOOKUP_ARTIFACTS_${attempt.ordinal}`,
                  attempt.artifactsObservation
                ),
                ledgerEntry(
                  `LOOKUP_RUN_END_${attempt.ordinal}`,
                  attempt.workflowRunObservation
                )
              ]),
              ledgerEntry(
                "READBACK_RUN_START",
                result.readbackStartRunObservation
              ),
              ledgerEntry(
                "READBACK_ARTIFACT",
                result.artifactRequeryObservation
              ),
              {
                operation: "CONFIRM_READ_REGISTRATION",
                phase: "READBACK_DOWNLOAD_REDIRECT",
                githubRequestId:
                  result.artifactDownload.receipt.redirectGitHubRequestId,
                receiptSha256: result.artifactDownload.receipt.receiptSha256,
                observedAtUnixSeconds:
                  result.artifactDownload.receipt.downloadedAtUnixSeconds
              },
              ledgerEntry(
                "READBACK_RUN_END",
                result.readbackFinalRunObservation
              )
            ])
            for (const observation of observations) {
              const original = observation.readRawBody()
              expect(rawS2SFileSha256(original)).toBe(
                observation.receipt.rawBodySha256
              )
              const callerCopy = observation.readRawBody()
              callerCopy[0] = (callerCopy[0] ?? 0) ^ 0xff
              expect(observation.readRawBody()).toEqual(original)
            }
            yield* validateS2SGitHubWorkflowRunObservation(
              trace.initialWorkflowRunObservation,
              RUN_ID
            )
            yield* validateS2SGitHubWorkflowAttemptJobsObservation(
              trace.workflowJobsObservation,
              RUN_ID
            )
            for (const attempt of trace.attempts) {
              yield* validateS2SGitHubRunArtifactsObservation(
                attempt.artifactsObservation,
                RUN_ID
              )
              yield* validateS2SGitHubWorkflowRunObservation(
                attempt.workflowRunObservation,
                RUN_ID
              )
            }
            const successfulAttempt = trace.attempts.find(
              (attempt) => attempt.classification === "ARTIFACT_OBSERVED"
            )
            expect(
              successfulAttempt?.artifactsObservation.receipt.receiptSha256
            ).toBe(result.artifactsObservation.receipt.receiptSha256)
            expect(successfulAttempt?.artifactsObservation).toBe(
              result.artifactsObservation
            )
            expect(
              successfulAttempt?.workflowRunObservation.receipt.receiptSha256
            ).toBe(result.workflowRunObservation.receipt.receiptSha256)
            expect(successfulAttempt?.workflowRunObservation).toBe(
              result.workflowRunObservation
            )
            expect(trace.initialWorkflowRunObservation).toBe(
              result.initialWorkflowRunObservation
            )
            expect(trace.workflowJobsObservation).toBe(
              result.workflowJobsObservation
            )
            const resultArchive = result.readArchiveBytes()
            const resultArchiveCopy = result.readArchiveBytes()
            resultArchiveCopy[0] = (resultArchiveCopy[0] ?? 0) ^ 0xff
            expect(result.readArchiveBytes()).toEqual(resultArchive)
            const downloadArchive = result.artifactDownload.readArchiveBytes()
            const downloadArchiveCopy = result.artifactDownload.readArchiveBytes()
            downloadArchiveCopy[0] = (downloadArchiveCopy[0] ?? 0) ^ 0xff
            expect(result.artifactDownload.readArchiveBytes()).toEqual(
              downloadArchive
            )
            for (const member of result.validatedArchive.members) {
              const memberBytes = member.readBytes()
              const memberCopy = member.readBytes()
              memberCopy[0] = (memberCopy[0] ?? 0) ^ 0xff
              expect(member.readBytes()).toEqual(memberBytes)
            }
            expect(Object.isFrozen(trace)).toBe(true)
            expect(Object.isFrozen(trace.attempts)).toBe(true)
            expect(trace.attempts.every(Object.isFrozen)).toBe(true)
            expect(
              Reflect.set(trace.attempts, 0, trace.attempts[0])
            ).toBe(false)
            expect(scenario.calls).toHaveLength(6 + 2 * positivePoll)
          })
      )
    }
  })
)

it.effect("REGISTER exposes no artifact operation", () => {
  const scenario = makeScenario({ stage: "REGISTER" })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("REGISTER"),
    scenario.observer,
    (reads) =>
      Effect.sync(() => {
        expect(reads).toEqual({ stage: "REGISTER" })
        expect(Object.keys(reads)).toEqual(["stage"])
        expect(scenario.calls).toHaveLength(0)
      })
  )
})

it.effect("spends a successful permit once without replenishment", () => {
  const scenario = makeScenario({ stage: "CONFIRM" })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const fixed = confirmationReads(reads)
        yield* fixed.confirmReadRegistration
        const callsAfterSuccess = scenario.calls.length
        const second = yield* fixed.confirmReadRegistration.pipe(Effect.either)
        expect(Either.isLeft(second)).toBe(true)
        if (Either.isLeft(second)) {
          expect(second.left).toMatchObject({
            _tag: "S2SStageArtifactPermitError",
            reason: "PERMIT_ALREADY_SPENT"
          })
        }
        expect(scenario.calls).toHaveLength(callsAfterSuccess)
      })
  )
})

it.effect("atomically admits only one parallel use", () => {
  const scenario = makeScenario({ stage: "CONFIRM" })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const effect = confirmationReads(reads).confirmReadRegistration
        const outcomes = yield* Effect.all(
          [effect.pipe(Effect.either), effect.pipe(Effect.either)],
          { concurrency: "unbounded" }
        )
        expect(outcomes.filter(Either.isRight)).toHaveLength(1)
        expect(outcomes.filter(Either.isLeft)).toHaveLength(1)
        expect(scenario.calls).toHaveLength(8)
      })
  )
})

it.effect("rejects wrong ordinal with zero I/O and leaves the next permit valid", () => {
  const scenario = makeScenario({ stage: "ADJUDICATE" })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("ADJUDICATE"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const fixed = adjudicationReads(reads)
        const wrong = yield* fixed.adjudicateReadCandidateFirst.pipe(
          Effect.either
        )
        expect(Either.isLeft(wrong)).toBe(true)
        if (Either.isLeft(wrong)) {
          expect(wrong.left).toMatchObject({ reason: "PERMIT_OUT_OF_ORDER" })
        }
        expect(scenario.calls).toHaveLength(0)
        const valid = yield* fixed.adjudicateReadRegistration
        expect(valid.operation).toBe("ADJUDICATE_READ_REGISTRATION")
        expect(scenario.calls).toHaveLength(8)
      })
  )
})

it.effect("burns a typed observer failure and performs no retry I/O", () => {
  const base = makeScenario({ stage: "CONFIRM" })
  let calls = 0
  const observer = S2SGitHubObserver.of({
    ...base.observer,
    observeWorkflowRun: () => {
      calls += 1
      return Effect.fail(
        new S2SGitHubObservationError({
          reason: "INVALID_ARGUMENT",
          path: "$fixture",
          detail: "typed failure"
        })
      )
    }
  })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM"),
    observer,
    (reads) =>
      Effect.gen(function* () {
        const effect = confirmationReads(reads).confirmReadRegistration
        const first = yield* effect.pipe(Effect.either)
        const second = yield* effect.pipe(Effect.either)
        expect(Either.isLeft(first)).toBe(true)
        expect(Either.isLeft(second)).toBe(true)
        if (Either.isLeft(second)) {
          expect(second.left).toMatchObject({ reason: "STAGE_VOID" })
        }
        expect(calls).toBe(1)
      })
  )
})

it.effect("preserves defects while burning the permit", () => {
  const base = makeScenario({ stage: "CONFIRM" })
  let calls = 0
  const observer = S2SGitHubObserver.of({
    ...base.observer,
    observeWorkflowRun: () => {
      calls += 1
      return Effect.dieMessage("observer defect")
    }
  })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM"),
    observer,
    (reads) =>
      Effect.gen(function* () {
        const effect = confirmationReads(reads).confirmReadRegistration
        const first = yield* Effect.exit(effect)
        expect(Exit.isFailure(first)).toBe(true)
        if (Exit.isFailure(first)) expect(Cause.isDieType(first.cause)).toBe(true)
        const retry = yield* effect.pipe(Effect.either)
        expect(Either.isLeft(retry)).toBe(true)
        if (Either.isLeft(retry)) {
          expect(retry.left).toMatchObject({ reason: "STAGE_VOID" })
        }
        expect(calls).toBe(1)
      })
  )
})

it.effect("preserves interruption while burning the permit", () =>
  Effect.gen(function* () {
    const base = makeScenario({ stage: "CONFIRM" })
    const started = yield* Deferred.make<void>()
    let calls = 0
    const observer = S2SGitHubObserver.of({
      ...base.observer,
      observeWorkflowRun: () => {
        calls += 1
        return Deferred.succeed(started, undefined).pipe(
          Effect.zipRight(Effect.never)
        )
      }
    })
    return yield* probeS2SStageArtifactReadMechanicsForTest(
      makeSeed("CONFIRM"),
      observer,
      (reads) =>
        Effect.gen(function* () {
          const effect = confirmationReads(reads).confirmReadRegistration
          const fiber = yield* effect.pipe(Effect.fork)
          yield* Deferred.await(started)
          const interrupted = yield* Fiber.interrupt(fiber)
          expect(Exit.isFailure(interrupted)).toBe(true)
          if (Exit.isFailure(interrupted)) {
            expect(Cause.isInterruptedOnly(interrupted.cause)).toBe(true)
          }
          const retry = yield* effect.pipe(Effect.either)
          expect(Either.isLeft(retry)).toBe(true)
          if (Either.isLeft(retry)) {
            expect(retry.left).toMatchObject({ reason: "STAGE_VOID" })
          }
          expect(calls).toBe(1)
        })
    )
  })
)

it.effect("rejects collisions with each current-run seed ID", () =>
  Effect.gen(function* () {
    const seedIds = [
      "SEED:RUN-START",
      "SEED:JOBS",
      "SEED:RUNS-FOR-HEAD",
      "SEED:RUN-END"
    ]
    for (const seedId of seedIds) {
      const scenario = makeScenario({
        stage: "CONFIRM",
        requestIdOverrides: { 0: seedId }
      })
      yield* probeS2SStageArtifactReadMechanicsForTest(
        makeSeed("CONFIRM"),
        scenario.observer,
        (reads) =>
          Effect.gen(function* () {
            const outcome = yield* confirmationReads(
              reads
            ).confirmReadRegistration.pipe(Effect.either)
            expect(Either.isLeft(outcome)).toBe(true)
            if (Either.isLeft(outcome)) {
              expect(outcome.left).toMatchObject({ reason: "REQUEST_ID_REUSED" })
            }
            expect(scenario.calls).toHaveLength(1)
          })
      )
    }
  })
)

it.effect("treats GitHub request IDs as case-sensitive", () => {
  const scenario = makeScenario({
    stage: "CONFIRM",
    requestIdOverrides: { 0: "seed:run-start" }
  })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM"),
    scenario.observer,
    (reads) =>
      Effect.asVoid(confirmationReads(reads).confirmReadRegistration)
  )
})

it.effect("carries request-ID reuse detection across adjudication operations", () => {
  const scenario = makeScenario({
    stage: "ADJUDICATE",
    requestIdOverrides: { 8: "REQ:0:run" }
  })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("ADJUDICATE"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const fixed = adjudicationReads(reads)
        yield* fixed.adjudicateReadRegistration
        const second = yield* fixed.adjudicateReadCandidateFirst.pipe(
          Effect.either
        )
        expect(Either.isLeft(second)).toBe(true)
        if (Either.isLeft(second)) {
          expect(second.left).toMatchObject({ reason: "REQUEST_ID_REUSED" })
        }
        expect(scenario.calls).toHaveLength(9)
      })
  )
})

it.effect("rejects an intermediate empty-poll collision before the paired run read", () => {
  const scenario = makeScenario({
    stage: "CONFIRM",
    positivePoll: 3,
    requestIdOverrides: { 4: "REQ:2:artifacts" }
  })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const outcome = yield* confirmationReads(
          reads
        ).confirmReadRegistration.pipe(Effect.either)
        expect(Either.isLeft(outcome)).toBe(true)
        if (Either.isLeft(outcome)) {
          expect(outcome.left).toMatchObject({ reason: "REQUEST_ID_REUSED" })
        }
        expect(scenario.calls).toEqual([
          "run",
          "jobs",
          "artifacts",
          "run",
          "artifacts"
        ])
      })
  )
})

it.effect("rejects a download redirect collision before the final run read", () => {
  const scenario = makeScenario({
    stage: "CONFIRM",
    requestIdOverrides: { 6: "REQ:2:artifacts" }
  })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const outcome = yield* confirmationReads(
          reads
        ).confirmReadRegistration.pipe(Effect.either)
        expect(Either.isLeft(outcome)).toBe(true)
        if (Either.isLeft(outcome)) {
          expect(outcome.left).toMatchObject({ reason: "REQUEST_ID_REUSED" })
        }
        expect(scenario.calls).toEqual([
          "run",
          "jobs",
          "artifacts",
          "run",
          "run",
          "artifact",
          "download"
        ])
      })
  )
})

it.effect("makes ledger phase topology a permit-core invariant", () => {
  const scope = right(
    makeS2SStageArtifactPermitTestScope(makeSeed("CONFIRM"))
  )
  const malformed = useS2SStageArtifactPermit(
    scope,
    "CONFIRM_READ_REGISTRATION",
    () =>
      appendS2SStageArtifactLedgerEntry(
        scope,
        "CONFIRM_READ_REGISTRATION",
        "LOOKUP_JOBS",
        "REQ:MALFORMED:PHASE",
        "5".repeat(64),
        OBSERVED_AT
      )
  )
  return Effect.gen(function* () {
    const outcome = yield* malformed.pipe(Effect.either)
    expect(Either.isLeft(outcome)).toBe(true)
    if (Either.isLeft(outcome)) {
      expect(outcome.left).toMatchObject({
        reason: "LEDGER_ENTRY_REJECTED"
      })
    }
  })
})

it.effect("fills the exact 16-entry CONFIRM ledger on a third-poll hit", () => {
  const scenario = makeScenario({ stage: "CONFIRM", positivePoll: 3 })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const result = yield* confirmationReads(reads).confirmReadRegistration
        expect(result.permitEvidence.ledgerCapacity).toBe(16)
        expect(result.permitEvidence.ledgerEntries).toHaveLength(16)
        expect(result.permitEvidence.ledgerEntries[0]?.githubRequestId).toBe(
          "SEED:RUN-START"
        )
        expect(scenario.calls).toHaveLength(12)
      })
  )
})

it.effect("fills the exact shared 40-entry ADJUDICATE ledger without eviction", () => {
  const scenario = makeScenario({ stage: "ADJUDICATE", positivePoll: 3 })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("ADJUDICATE"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const fixed = adjudicationReads(reads)
        yield* fixed.adjudicateReadRegistration
        yield* fixed.adjudicateReadCandidateFirst
        const result = yield* fixed.adjudicateRereadCandidate
        expect(result.permitEvidence.ledgerCapacity).toBe(40)
        expect(result.permitEvidence.ledgerEntries).toHaveLength(40)
        expect(result.permitEvidence.ledgerEntries.slice(0, 4).map(
          (entry) => entry.githubRequestId
        )).toEqual([
          "SEED:RUN-START",
          "SEED:JOBS",
          "SEED:RUNS-FOR-HEAD",
          "SEED:RUN-END"
        ])
        expect(scenario.calls).toHaveLength(36)
      })
  )
})

it.effect("rejects fresh current and predecessor numeric job-ID drift", () =>
  Effect.gen(function* () {
    for (const jobIdOverrides of [
      { confirm: CONFIRM_JOB_ID + 100 },
      { register: REGISTER_JOB_ID + 100 }
    ]) {
      const scenario = makeScenario({
        stage: "CONFIRM",
        jobIdOverrides
      })
      yield* probeS2SStageArtifactReadMechanicsForTest(
        makeSeed("CONFIRM"),
        scenario.observer,
        (reads) =>
          Effect.gen(function* () {
            const outcome = yield* confirmationReads(
              reads
            ).confirmReadRegistration.pipe(Effect.either)
            expect(Either.isLeft(outcome)).toBe(true)
            if (Either.isLeft(outcome)) {
              expect(outcome.left).toMatchObject({
                _tag: "S2SStageArtifactReadError",
                reason: "FRESH_JOB_BINDING_DRIFT"
              })
            }
            expect(scenario.calls).toHaveLength(2)
          })
      )
    }
  })
)

it.effect("rejects fresh run/head drift before jobs I/O", () => {
  const scenario = makeScenario({
    stage: "CONFIRM",
    runOverrides: { head_sha: "a".repeat(40) }
  })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const outcome = yield* confirmationReads(
          reads
        ).confirmReadRegistration.pipe(Effect.either)
        expect(Either.isLeft(outcome)).toBe(true)
        if (Either.isLeft(outcome)) {
          expect(outcome.left).toMatchObject({
            _tag: "S2SStageArtifactReadError",
            reason: "LOOKUP_REJECTED",
            phase: "LOOKUP_RUN_START"
          })
        }
        expect(scenario.calls).toEqual(["run"])
      })
  )
})

it.effect("performs an independent candidate reread and voids on byte drift", () => {
  const scenario = makeScenario({
    stage: "ADJUDICATE",
    candidateRereadArchive: candidateArchive(2)
  })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("ADJUDICATE"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const fixed = adjudicationReads(reads)
        yield* fixed.adjudicateReadRegistration
        yield* fixed.adjudicateReadCandidateFirst
        const reread = yield* fixed.adjudicateRereadCandidate.pipe(
          Effect.either
        )
        expect(Either.isLeft(reread)).toBe(true)
        if (Either.isLeft(reread)) {
          expect(reread.left).toMatchObject({
            _tag: "S2SStageArtifactPermitError",
            reason: "CANDIDATE_REREAD_MISMATCH"
          })
        }
        expect(scenario.calls).toHaveLength(24)
      })
  )
})

it.effect("retains all three artifact/run absence pairs in the typed rejection", () => {
  const scenario = makeScenario({ stage: "CONFIRM", positivePoll: null })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM"),
    scenario.observer,
    (reads) =>
      Effect.gen(function* () {
        const outcome = yield* confirmationReads(
          reads
        ).confirmReadRegistration.pipe(Effect.either)
        expect(Either.isLeft(outcome)).toBe(true)
        if (
          Either.isLeft(outcome) &&
          outcome.left instanceof S2SStageArtifactReadError
        ) {
          expect(outcome.left.reason).toBe("LOOKUP_REJECTED")
          expect(outcome.left.outcome?._tag).toBe(
            "ReconciledAbsentAfterProducerCompleted"
          )
          if (
            outcome.left.outcome?._tag ===
            "ReconciledAbsentAfterProducerCompleted"
          ) {
            expect(outcome.left.outcome.absenceObservationPairs).toHaveLength(3)
            expect(
              new Set(
                outcome.left.outcome.absenceObservationPairs.flatMap((pair) => [
                  pair.artifactsObservation.receipt.receiptSha256,
                  pair.workflowRunObservation.receipt.receiptSha256
                ])
              ).size
            ).toBe(6)
          }
        }
        expect(scenario.calls).toHaveLength(8)
      })
  )
})

it.effect("accepts the authority-bound @main workflow API representation", () => {
  const workflowApiPath = `${WORKFLOW_PATH}@main`
  const scenario = makeScenario({
    stage: "CONFIRM",
    workflowApiPath
  })
  return probeS2SStageArtifactReadMechanicsForTest(
    makeSeed("CONFIRM", workflowApiPath),
    scenario.observer,
    (reads) => Effect.asVoid(confirmationReads(reads).confirmReadRegistration)
  )
})

it.effect("closes captured test drivers and never replenishes the same fixture", () =>
  Effect.gen(function* () {
    const seed = makeSeed("CONFIRM")
    const scenario = makeScenario({ stage: "CONFIRM" })
    let captured: S2SConfirmStageArtifactReads | undefined
    yield* probeS2SStageArtifactReadMechanicsForTest(
      seed,
      scenario.observer,
      (reads) =>
        Effect.sync(() => {
          captured = confirmationReads(reads)
        })
    )
    if (captured === undefined) {
      return yield* Effect.dieMessage("test driver was not captured")
    }
    const closed = yield* captured.confirmReadRegistration.pipe(Effect.either)
    expect(Either.isLeft(closed)).toBe(true)
    if (Either.isLeft(closed)) {
      expect(closed.left).toMatchObject({ reason: "SCOPE_CLOSED" })
    }
    expect(scenario.calls).toHaveLength(0)
    yield* probeS2SStageArtifactReadMechanicsForTest(
      seed,
      scenario.observer,
      (reads) =>
        Effect.gen(function* () {
          const reused = yield* confirmationReads(
            reads
          ).confirmReadRegistration.pipe(Effect.either)
          expect(Either.isLeft(reused)).toBe(true)
          if (Either.isLeft(reused)) {
            expect(reused.left).toMatchObject({ reason: "SCOPE_CLOSED" })
          }
        })
    )
    expect(scenario.calls).toHaveLength(0)
  })
)
