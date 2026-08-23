import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  S2SGitCommitShaSchema,
  S2SSha256Schema
} from "../src/s2s-confirmatory.js"
import {
  S2S_GITHUB_API_VERSION,
  S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
  S2S_GITHUB_REPOSITORY,
  observeS2SGitHubArtifact,
  observeS2SGitHubRunArtifacts,
  observeS2SGitHubWorkflowAttemptJobs,
  observeS2SGitHubWorkflowRun,
  type S2SGitHubArtifactDownload,
  type S2SGitHubArtifactDownloadReceipt,
  type S2SGitHubObservation
} from "../src/s2s-live-github.js"
import {
  S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION,
  type S2SCurrentRunStageEvidence
} from "../src/s2s-run-authority.js"
import {
  validateS2SCurrentRunStageEvidence,
  validateS2SCurrentRunStageEvidenceForArtifactReplay
} from "../src/s2s-stage-artifact-read-replay.js"
import { S2S_STAGE_ARTIFACT_SPECS } from "../src/s2s-stage-artifact-spec.js"
import {
  S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES,
  S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MEMBER_NAME,
  S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES,
  S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES,
  S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MEMBER_NAME
} from "../src/s2s-stage-upload-postcondition-contract.js"
import {
  S2S_STAGE_UPLOAD_ASSERTION_OPERATION,
  S2S_STAGE_UPLOAD_ASSERTION_PERMIT_EVIDENCE_SCHEMA_VERSION,
  S2SStageUploadPostconditionError,
  buildS2SStageUploadPostcondition,
  buildS2SStageUploadPostconditionEffect,
  buildS2SStageUploadPostconditionFromProductionShell,
  reconstructS2SStageUploadPostcondition,
  validateS2SStageUploadPostcondition,
  validateS2SStageUploadPostconditionEffect,
  type S2SStageUploadAssertionPermitEvidence,
  type S2SStageUploadBuildObservation,
  type S2SStageUploadPreparedMember
} from "../src/s2s-stage-upload-postcondition.js"
import { S2S_TEST_ONLY_GOLDEN_UPLOAD_POSTCONDITION_SCHEMA_VERSION } from "../src/s2s-test-only-golden-upload.js"
import {
  S2S_CONFIRMATORY_JOB_STAGES,
  S2S_CONFIRMATORY_STAGE_CONTRACTS,
  S2S_CONFIRMATORY_WORKFLOW_PATH,
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
const ARTIFACT_IDS = Object.freeze({
  REGISTER: 9_433_344_546,
  CONFIRM: 9_433_344_547,
  ADJUDICATE: 9_433_344_548
} as const)
const HEAD_SHA = "75686549b1f6c65aea87ebd0f912a6e62909445a"
const SOURCE_COMMIT_A = "a".repeat(40)
const WORKFLOW_FILE_SHA256 = "b".repeat(64)
const CREATED_AT = "2026-08-21T03:10:32Z"
const CREATED_AT_UNIX_SECONDS = Date.parse(CREATED_AT) / 1_000
const OBSERVED_AT = CREATED_AT_UNIX_SECONDS + 2_000
const ENCODER = new TextEncoder()
const DECODER = new TextDecoder()
const MANIFEST_TOP_LEVEL_KEYS = Object.freeze(
  [
    "archive_members_equal_prepared_members",
    "archive_reference",
    "archive_validation",
    "artifact_byte_length",
    "artifact_evidence",
    "artifact_id",
    "artifact_name",
    "artifact_sha256",
    "assertion_permit_evidence",
    "authority_scope",
    "classification",
    "cross_module_copy_replay_prevention_claimed",
    "cross_process_replay_prevention_claimed",
    "cross_worker_replay_prevention_claimed",
    "current_run_evidence_receipt_sha256",
    "download_receipt",
    "durable_replay_prevention_claimed",
    "experiment_id",
    "external_exactly_once_claimed",
    "historical_uniqueness_claimed",
    "identity",
    "observation_blob_byte_length",
    "observation_blob_sha256",
    "observation_count",
    "observations",
    "postcondition_receipt_sha256",
    "prepared_members",
    "producer_job_id",
    "producer_job_name",
    "publication_claim",
    "publisher_return_used_as_evidence",
    "representation",
    "role",
    "schema_version",
    "source_commit_a",
    "stage",
    "successful_attempt_ordinal"
  ].sort()
)

type Attempt = 1 | 2 | 3
type PermitLedgerEntry =
  S2SStageUploadAssertionPermitEvidence["ledgerEntries"][number]

interface ZipMember {
  readonly name: string
  readonly bytes: Uint8Array
}

const right = <A, E>(outcome: Either.Either<A, E>): A => {
  if (Either.isLeft(outcome)) throw outcome.left
  return outcome.right
}

const expectReason = (
  outcome: Either.Either<unknown, unknown>,
  reason: S2SStageUploadPostconditionError["reason"]
): S2SStageUploadPostconditionError => {
  expect(Either.isLeft(outcome)).toBe(true)
  if (Either.isRight(outcome)) throw new Error("expected a typed failure")
  expect(outcome.left).toBeInstanceOf(S2SStageUploadPostconditionError)
  if (!(outcome.left instanceof S2SStageUploadPostconditionError)) {
    throw outcome.left
  }
  expect(outcome.left.reason).toBe(reason)
  return outcome.left
}

const jsonBytes = (value: unknown): Uint8Array =>
  ENCODER.encode(`${JSON.stringify(value)}\n`)

const WORKFLOW_CONTRACT_SHA256 = right(
  s2sConfirmatoryWorkflowContractSha256()
)

const jobDatabaseId = (stage: S2SConfirmatoryJobStage): number =>
  stage === "REGISTER"
    ? REGISTER_JOB_ID
    : stage === "CONFIRM"
      ? CONFIRM_JOB_ID
      : ADJUDICATE_JOB_ID

const predecessorJobDatabaseIds = (
  stage: S2SConfirmatoryJobStage
): ReadonlyArray<number> =>
  stage === "REGISTER"
    ? []
    : stage === "CONFIRM"
      ? [REGISTER_JOB_ID]
      : [REGISTER_JOB_ID, CONFIRM_JOB_ID]

const makeCurrentRunEvidence = (
  stage: S2SConfirmatoryJobStage
): S2SCurrentRunStageEvidence => {
  const observations = Object.freeze({
    runStart: Object.freeze({
      receiptSha256: "1".repeat(64),
      githubRequestId: `SEED:${stage}:RUN-START`,
      observedAtUnixSeconds: OBSERVED_AT - 40
    }),
    jobs: Object.freeze({
      receiptSha256: "2".repeat(64),
      githubRequestId: `SEED:${stage}:JOBS`,
      observedAtUnixSeconds: OBSERVED_AT - 30
    }),
    runsForHead: Object.freeze({
      receiptSha256: "3".repeat(64),
      githubRequestId: `SEED:${stage}:RUNS-FOR-HEAD`,
      observedAtUnixSeconds: OBSERVED_AT - 20
    }),
    runEnd: Object.freeze({
      receiptSha256: "4".repeat(64),
      githubRequestId: `SEED:${stage}:RUN-END`,
      observedAtUnixSeconds: OBSERVED_AT - 10
    })
  })
  const core: Omit<S2SCurrentRunStageEvidence, "receiptSha256"> = {
    schemaVersion: S2S_CURRENT_RUN_STAGE_EVIDENCE_SCHEMA_VERSION,
    authorityScope: "PROCESS_LOCAL_STAGE_ENTRY",
    uniquenessClaim: "ROSTER_OBSERVATION_INSTANT_ONLY",
    historicalUniquenessClaimed: false,
    crossExecutionReplayPreventionClaimed: false,
    durableCommitRequiresFreshTerminalObservation: true,
    sourceCommitA: SOURCE_COMMIT_A,
    registrationCommitB: HEAD_SHA,
    registrationAuthorityReceiptSha256: "5".repeat(64),
    currentInvocationReceiptSha256: "6".repeat(64),
    workflowContractSha256: WORKFLOW_CONTRACT_SHA256,
    workflowFileSha256: WORKFLOW_FILE_SHA256,
    trackedBytesManifestSha256: "7".repeat(64),
    workflowApiPath: S2S_CONFIRMATORY_WORKFLOW_PATH,
    workflowRunId: RUN_ID,
    workflowRunAttempt: 1,
    stage,
    currentJobId: S2S_CONFIRMATORY_STAGE_CONTRACTS[stage].jobId,
    currentJobDatabaseId: jobDatabaseId(stage),
    predecessorJobDatabaseIds: Object.freeze([
      ...predecessorJobDatabaseIds(stage)
    ]),
    workflowRunCreatedAt: CREATED_AT,
    workflowRunCreatedAtUnixSeconds: CREATED_AT_UNIX_SECONDS,
    invocationCapturedAtUnixSeconds: OBSERVED_AT - 100,
    observations
  }
  return Object.freeze({
    ...core,
    receiptSha256: right(canonicalS2SControlSha256(core))
  })
}

const responseProvenance = (githubRequestId: string) =>
  Object.freeze({
    githubRequestId,
    githubApiVersionSelected: S2S_GITHUB_API_VERSION,
    responseEtag: `W/"${"e".repeat(64)}"`
  })

const runJson = () => ({
  id: RUN_ID,
  run_attempt: 1,
  name: "SWM-0W-S2S confirmatory",
  path: S2S_CONFIRMATORY_WORKFLOW_PATH,
  event: "push",
  head_branch: "main",
  head_sha: HEAD_SHA,
  repository: { full_name: "gj3447/HSWM" },
  head_repository: { full_name: "gj3447/HSWM" },
  status: "in_progress",
  conclusion: null,
  created_at: CREATED_AT
})

const jobJson = (
  id: number,
  name: "register" | "confirm" | "adjudicate",
  status: "queued" | "in_progress" | "completed",
  startedAt: string,
  completedAt: string | null
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
  labels: ["ubuntu-24.04"]
})

const jobsJson = (stage: S2SConfirmatoryJobStage) => {
  const register =
    stage === "REGISTER"
      ? jobJson(
          REGISTER_JOB_ID,
          "register",
          "in_progress",
          "2026-08-21T03:10:34Z",
          null
        )
      : jobJson(
          REGISTER_JOB_ID,
          "register",
          "completed",
          "2026-08-21T03:10:34Z",
          "2026-08-21T03:20:00Z"
        )
  const confirm =
    stage === "REGISTER"
      ? jobJson(
          CONFIRM_JOB_ID,
          "confirm",
          "queued",
          "2026-08-21T03:10:35Z",
          null
        )
      : stage === "CONFIRM"
        ? jobJson(
            CONFIRM_JOB_ID,
            "confirm",
            "in_progress",
            "2026-08-21T03:20:01Z",
            null
          )
        : jobJson(
            CONFIRM_JOB_ID,
            "confirm",
            "completed",
            "2026-08-21T03:20:01Z",
            "2026-08-21T03:30:00Z"
          )
  const adjudicate =
    stage === "ADJUDICATE"
      ? jobJson(
          ADJUDICATE_JOB_ID,
          "adjudicate",
          "in_progress",
          "2026-08-21T03:30:01Z",
          null
        )
      : jobJson(
          ADJUDICATE_JOB_ID,
          "adjudicate",
          "queued",
          stage === "REGISTER"
            ? "2026-08-21T03:10:36Z"
            : "2026-08-21T03:20:02Z",
          null
        )
  return { total_count: 3, jobs: [register, confirm, adjudicate] }
}

const archiveMembers = (
  stage: S2SConfirmatoryJobStage,
  value = 1
): ReadonlyArray<ZipMember> => {
  const control =
    stage === "REGISTER"
      ? `registration-${value}`
      : stage === "CONFIRM"
        ? `candidate-${value}`
        : `adjudication-${value}`
  const members: Array<ZipMember> = [
    {
      name: "control_receipt.json",
      bytes: ENCODER.encode(`${JSON.stringify({ control })}\n`)
    }
  ]
  if (stage === "CONFIRM") {
    members.push({
      name: "numeric_candidate.json",
      bytes: ENCODER.encode(`${JSON.stringify({ value })}\n`)
    })
  } else if (stage === "ADJUDICATE") {
    members.push({
      name: "numeric_adjudication.json",
      bytes: ENCODER.encode(`${JSON.stringify({ value })}\n`)
    })
  }
  return Object.freeze(members)
}

const makeArchive = (
  stage: S2SConfirmatoryJobStage,
  value = 1
): Uint8Array =>
  right(buildS2SStoredZip(archiveMembers(stage, value))).readArchiveBytes()

const makePreparedMembers = (
  stage: S2SConfirmatoryJobStage,
  value = 1
): ReadonlyArray<S2SStageUploadPreparedMember> =>
  Object.freeze(
    archiveMembers(stage, value).map((member) => {
      const bytes = Uint8Array.from(member.bytes)
      return Object.freeze({
        name: member.name as S2SStageUploadPreparedMember["name"],
        byteLength: bytes.byteLength,
        rawBytesSha256: rawS2SFileSha256(bytes),
        readBytes: (): Uint8Array => Uint8Array.from(bytes)
      })
    })
  )

const artifactJson = (
  stage: S2SConfirmatoryJobStage,
  archive: Uint8Array
) => ({
  id: ARTIFACT_IDS[stage],
  name: S2S_STAGE_ARTIFACT_SPECS[stage].artifactName,
  size_in_bytes: archive.byteLength,
  digest: `sha256:${rawS2SFileSha256(archive)}`,
  expired: false,
  created_at:
    stage === "REGISTER"
      ? "2026-08-21T03:19:59Z"
      : stage === "CONFIRM"
        ? "2026-08-21T03:29:59Z"
        : "2026-08-21T03:39:59Z",
  expires_at: "2026-11-19T03:10:32Z",
  workflow_run: { id: RUN_ID, head_sha: HEAD_SHA }
})

const makeObservations = (
  stage: S2SConfirmatoryJobStage,
  attempt: Attempt,
  archive: Uint8Array
): ReadonlyArray<S2SStageUploadBuildObservation> => {
  const output: Array<S2SStageUploadBuildObservation> = []
  let index = 0
  const metadata = (phase: string) => {
    const observedAtUnixSeconds = OBSERVED_AT + index * 10
    const githubRequestId = `POST:${stage}:${attempt}:${index}:${phase}`
    index += 1
    return {
      observedAtUnixSeconds,
      provenance: responseProvenance(githubRequestId)
    }
  }
  const run = (phase: S2SStageUploadBuildObservation["phase"]): void => {
    const next = metadata(phase)
    output.push(
      Object.freeze({
        phase,
        observation: right(
          observeS2SGitHubWorkflowRun(
            jsonBytes(runJson()),
            RUN_ID,
            next.observedAtUnixSeconds,
            next.provenance
          )
        )
      })
    )
  }

  run("LOOKUP_RUN_START")
  const jobMetadata = metadata("LOOKUP_JOBS")
  output.push(
    Object.freeze({
      phase: "LOOKUP_JOBS",
      observation: right(
        observeS2SGitHubWorkflowAttemptJobs(
          jsonBytes(jobsJson(stage)),
          RUN_ID,
          1,
          jobMetadata.observedAtUnixSeconds,
          jobMetadata.provenance
        )
      )
    })
  )
  for (let ordinal = 1; ordinal <= attempt; ordinal += 1) {
    const artifactsPhase =
      `LOOKUP_ARTIFACTS_${ordinal}` as S2SStageUploadBuildObservation["phase"]
    const artifactsMetadata = metadata(artifactsPhase)
    const artifacts =
      ordinal === attempt ? [artifactJson(stage, archive)] : []
    output.push(
      Object.freeze({
        phase: artifactsPhase,
        observation: right(
          observeS2SGitHubRunArtifacts(
            jsonBytes({ total_count: artifacts.length, artifacts }),
            RUN_ID,
            artifactsMetadata.observedAtUnixSeconds,
            artifactsMetadata.provenance
          )
        )
      })
    )
    run(
      `LOOKUP_RUN_END_${ordinal}` as S2SStageUploadBuildObservation["phase"]
    )
  }
  run("READBACK_RUN_START")
  const artifactMetadata = metadata("READBACK_ARTIFACT")
  output.push(
    Object.freeze({
      phase: "READBACK_ARTIFACT",
      observation: right(
        observeS2SGitHubArtifact(
          jsonBytes(artifactJson(stage, archive)),
          ARTIFACT_IDS[stage],
          artifactMetadata.observedAtUnixSeconds,
          artifactMetadata.provenance
        )
      )
    })
  )
  run("READBACK_RUN_END")
  return Object.freeze(output)
}

const makeDownload = (
  stage: S2SConfirmatoryJobStage,
  attempt: Attempt,
  archive: Uint8Array,
  downloadedAtUnixSeconds: number
): S2SGitHubArtifactDownload => {
  const artifactId = ARTIFACT_IDS[stage]
  const core: Omit<S2SGitHubArtifactDownloadReceipt, "receiptSha256"> =
    Object.freeze({
      schemaVersion: S2S_GITHUB_ARTIFACT_DOWNLOAD_SCHEMA_VERSION,
      apiVersion: S2S_GITHUB_API_VERSION,
      repository: S2S_GITHUB_REPOSITORY,
      artifactId,
      endpointPathAndQuery: `/repos/${S2S_GITHUB_REPOSITORY}/actions/artifacts/${artifactId}/zip`,
      downloadedAtUnixSeconds,
      redirectHttpStatus: 302,
      redirectGitHubRequestId: `POST:${stage}:${attempt}:DOWNLOAD`,
      redirectGitHubApiVersionSelected: S2S_GITHUB_API_VERSION,
      redirectResponseEtag: null,
      redirectUrlSha256: "8".repeat(64),
      redirectOrigin: "https://objects.example.invalid",
      archiveHttpStatus: 200,
      archiveMediaType: "application/zip",
      archiveResponseEtag: `"${"9".repeat(64)}"`,
      archiveByteLength: archive.byteLength,
      downloadedArchiveSha256: rawS2SFileSha256(archive)
    })
  const bytes = Uint8Array.from(archive)
  return Object.freeze({
    receipt: Object.freeze({
      ...core,
      receiptSha256: right(canonicalS2SControlSha256(core))
    }),
    readArchiveBytes: (): Uint8Array => Uint8Array.from(bytes)
  })
}

const makePermit = (
  current: S2SCurrentRunStageEvidence,
  observations: ReadonlyArray<S2SStageUploadBuildObservation>,
  download: S2SGitHubArtifactDownloadReceipt
): S2SStageUploadAssertionPermitEvidence => {
  const ledgerEntries: Array<PermitLedgerEntry> = [
    {
      operation: "CURRENT_RUN_AUTHORITY",
      phase: "CURRENT_RUN_RUN_START",
      githubRequestId: current.observations.runStart.githubRequestId,
      receiptSha256: S2SSha256Schema.make(
        current.observations.runStart.receiptSha256
      ),
      observedAtUnixSeconds:
        current.observations.runStart.observedAtUnixSeconds
    },
    {
      operation: "CURRENT_RUN_AUTHORITY",
      phase: "CURRENT_RUN_JOBS",
      githubRequestId: current.observations.jobs.githubRequestId,
      receiptSha256: S2SSha256Schema.make(
        current.observations.jobs.receiptSha256
      ),
      observedAtUnixSeconds: current.observations.jobs.observedAtUnixSeconds
    },
    {
      operation: "CURRENT_RUN_AUTHORITY",
      phase: "CURRENT_RUN_RUNS_FOR_HEAD",
      githubRequestId: current.observations.runsForHead.githubRequestId,
      receiptSha256: S2SSha256Schema.make(
        current.observations.runsForHead.receiptSha256
      ),
      observedAtUnixSeconds:
        current.observations.runsForHead.observedAtUnixSeconds
    },
    {
      operation: "CURRENT_RUN_AUTHORITY",
      phase: "CURRENT_RUN_RUN_END",
      githubRequestId: current.observations.runEnd.githubRequestId,
      receiptSha256: S2SSha256Schema.make(
        current.observations.runEnd.receiptSha256
      ),
      observedAtUnixSeconds: current.observations.runEnd.observedAtUnixSeconds
    }
  ]
  for (const entry of observations) {
    if (entry.phase === "READBACK_RUN_END") {
      ledgerEntries.push({
        operation: S2S_STAGE_UPLOAD_ASSERTION_OPERATION,
        phase: "READBACK_DOWNLOAD_REDIRECT",
        githubRequestId: download.redirectGitHubRequestId,
        receiptSha256: S2SSha256Schema.make(download.receiptSha256),
        observedAtUnixSeconds: download.downloadedAtUnixSeconds
      })
    }
    ledgerEntries.push({
      operation: S2S_STAGE_UPLOAD_ASSERTION_OPERATION,
      phase: entry.phase,
      githubRequestId: entry.observation.receipt.githubRequestId,
      receiptSha256: S2SSha256Schema.make(
        entry.observation.receipt.receiptSha256
      ),
      observedAtUnixSeconds:
        entry.observation.receipt.observedAtUnixSeconds
    })
  }
  const core: Omit<
    S2SStageUploadAssertionPermitEvidence,
    "receiptSha256"
  > = {
    schemaVersion:
      S2S_STAGE_UPLOAD_ASSERTION_PERMIT_EVIDENCE_SCHEMA_VERSION,
    authorityScope: "TEST_ONLY_NON_AUTHORIZING",
    authorizationClaimed: false,
    oneUseClaim: "MECHANICS_ONLY_EPHEMERAL_TEST_SCOPE",
    crossWorkerReplayPreventionClaimed: false,
    crossModuleCopyReplayPreventionClaimed: false,
    crossProcessReplayPreventionClaimed: false,
    durableReplayPreventionClaimed: false,
    identity: {
      workflowRunId: current.workflowRunId,
      workflowRunAttempt: 1,
      registrationCommitB: S2SGitCommitShaSchema.make(
        current.registrationCommitB
      ),
      workflowApiPath: S2S_CONFIRMATORY_WORKFLOW_PATH,
      workflowRunCreatedAt: current.workflowRunCreatedAt,
      workflowRunCreatedAtUnixSeconds:
        current.workflowRunCreatedAtUnixSeconds,
      stage: current.stage,
      currentJobDatabaseId: current.currentJobDatabaseId,
      predecessorJobDatabaseIds: [...current.predecessorJobDatabaseIds]
    },
    operation: S2S_STAGE_UPLOAD_ASSERTION_OPERATION,
    ledgerCapacity: 16,
    ledgerEntries
  }
  return Object.freeze({
    ...core,
    receiptSha256: S2SSha256Schema.make(
      right(canonicalS2SControlSha256(core))
    )
  })
}

const makeFixture = (stage: S2SConfirmatoryJobStage, attempt: Attempt) => {
  const currentRunEvidence = makeCurrentRunEvidence(stage)
  const archive = makeArchive(stage)
  const preparedMembers = makePreparedMembers(stage)
  const observations = makeObservations(stage, attempt, archive)
  const artifactObservation = observations.at(-2)
  if (artifactObservation?.phase !== "READBACK_ARTIFACT") {
    throw new Error("fixture readback observation disappeared")
  }
  const artifactDownload = makeDownload(
    stage,
    attempt,
    archive,
    artifactObservation.observation.receipt.observedAtUnixSeconds + 5
  )
  const assertionPermitEvidence = makePermit(
    currentRunEvidence,
    observations,
    artifactDownload.receipt
  )
  const buildInput = {
    artifactDownload,
    assertionPermitEvidence,
    currentRunEvidence,
    observations,
    preparedMembers,
    successfulAttemptOrdinal: attempt
  }
  return {
    stage,
    attempt,
    archive,
    preparedMembers,
    observations,
    artifactDownload,
    currentRunEvidence,
    assertionPermitEvidence,
    buildInput
  }
}

const parseManifest = (bytes: Uint8Array): Record<string, unknown> =>
  JSON.parse(DECODER.decode(bytes)) as Record<string, unknown>

const sealManifest = (
  document: Readonly<Record<string, unknown>>
): Readonly<Record<string, unknown>> => {
  const { postcondition_receipt_sha256: _discarded, ...core } = document
  return {
    ...core,
    postcondition_receipt_sha256: right(canonicalS2SControlSha256(core))
  }
}

const carrierFromParts = (
  manifestBytes: Uint8Array,
  observationBytes: Uint8Array
): Uint8Array =>
  right(
    buildS2SStoredZip([
      {
        name: S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MEMBER_NAME,
        bytes: manifestBytes
      },
      {
        name: S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MEMBER_NAME,
        bytes: observationBytes
      }
    ])
  ).readArchiveBytes()

const carrierFromDocument = (
  document: Readonly<Record<string, unknown>>,
  observationBytes: Uint8Array
): Uint8Array =>
  carrierFromParts(
    right(canonicalS2SControlJsonBytes(document)),
    observationBytes
  )

const validateFixtureCarrier = (
  fixture: ReturnType<typeof makeFixture>,
  carrierBytes: Uint8Array
) =>
  validateS2SStageUploadPostcondition({
    carrierBytes,
    currentRunEvidence: fixture.currentRunEvidence,
    currentStageArchiveBytes: fixture.archive,
    preparedMembers: fixture.preparedMembers
  })

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
  let value = 0xffff_ffff
  for (const byte of bytes) {
    const next = CRC_TABLE[(value ^ byte) & 0xff]
    if (next === undefined) throw new Error("CRC table entry missing")
    value = next ^ (value >>> 8)
  }
  return (value ^ 0xffff_ffff) >>> 0
}

/** Builds a validator-compatible ZIP while preserving caller member order. */
const buildCompatibleStoredZip = (
  members: ReadonlyArray<ZipMember>,
  dosTime: number
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
    header.writeUInt16LE(dosTime, 10)
    header.writeUInt16LE(0x0021, 12)
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
    header.writeUInt16LE(dosTime, 12)
    header.writeUInt16LE(0x0021, 14)
    header.writeUInt32LE(crc32(member.bytes), 16)
    header.writeUInt32LE(member.bytes.byteLength, 20)
    header.writeUInt32LE(member.bytes.byteLength, 24)
    header.writeUInt16LE(name.byteLength, 28)
    header.writeUInt32LE(((0o100644 << 16) | 0x20) >>> 0, 38)
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

const assertGenericCarrierZip = (carrier: Uint8Array): void => {
  const validation = validateS2SArtifactZip(carrier, {
    expectedArchiveSha256: S2SSha256Schema.make(
      rawS2SFileSha256(carrier)
    ),
    expectedArchiveByteLength: carrier.byteLength,
    expectedMembers: [
      {
        name: S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MEMBER_NAME,
        maximumBytes: S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES
      },
      {
        name: S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MEMBER_NAME,
        maximumBytes: S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES
      }
    ],
    maximumArchiveBytes: S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES,
    maximumExpandedBytes:
      S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MAX_BYTES +
      S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MAX_BYTES
  })
  expect(Either.isRight(validation)).toBe(true)
}

const replaceAsciiOnce = (
  bytes: Uint8Array,
  before: string,
  after: string
): Uint8Array => {
  if (before.length !== after.length) {
    throw new Error("replacement fixture must preserve byte length")
  }
  const output = Uint8Array.from(bytes)
  const needle = ENCODER.encode(before)
  const replacement = ENCODER.encode(after)
  let found = -1
  for (let index = 0; index <= output.byteLength - needle.byteLength; index += 1) {
    if (needle.every((byte, offset) => output[index + offset] === byte)) {
      found = index
      break
    }
  }
  if (found < 0) throw new Error("observation mutation target missing")
  output.set(replacement, found)
  return output
}

const permitCore = (
  permit: S2SStageUploadAssertionPermitEvidence
): Omit<S2SStageUploadAssertionPermitEvidence, "receiptSha256"> => {
  const { receiptSha256: _discarded, ...core } = permit
  return core
}

const sealPermit = (
  core: Omit<S2SStageUploadAssertionPermitEvidence, "receiptSha256">
): S2SStageUploadAssertionPermitEvidence =>
  Object.freeze({
    ...core,
    receiptSha256: S2SSha256Schema.make(
      right(canonicalS2SControlSha256(core))
    )
  })

const observationProvenance = (observation: S2SGitHubObservation) =>
  Object.freeze({
    githubRequestId: observation.receipt.githubRequestId,
    githubApiVersionSelected: S2S_GITHUB_API_VERSION,
    responseEtag: observation.receipt.responseEtag
  })

const observationAtPhase = (
  observations: ReadonlyArray<S2SStageUploadBuildObservation>,
  phase: S2SStageUploadBuildObservation["phase"]
): S2SStageUploadBuildObservation => {
  const entry = observations.find((candidate) => candidate.phase === phase)
  if (entry === undefined) throw new Error(`fixture phase ${phase} missing`)
  return entry
}

const replaceObservationAtPhase = (
  observations: ReadonlyArray<S2SStageUploadBuildObservation>,
  phase: S2SStageUploadBuildObservation["phase"],
  observation: S2SGitHubObservation
): ReadonlyArray<S2SStageUploadBuildObservation> =>
  Object.freeze(
    observations.map((entry) =>
      entry.phase === phase
        ? Object.freeze({ phase, observation })
        : entry
    )
  )

const replaceSuccessfulArtifactListing = (
  fixture: ReturnType<typeof makeFixture>,
  artifacts: ReadonlyArray<unknown>
): ReadonlyArray<S2SStageUploadBuildObservation> => {
  const phase =
    `LOOKUP_ARTIFACTS_${fixture.attempt}` as S2SStageUploadBuildObservation["phase"]
  const original = observationAtPhase(fixture.observations, phase).observation
  const replacement = right(
    observeS2SGitHubRunArtifacts(
      jsonBytes({ total_count: artifacts.length, artifacts }),
      RUN_ID,
      original.receipt.observedAtUnixSeconds,
      observationProvenance(original)
    )
  )
  return replaceObservationAtPhase(fixture.observations, phase, replacement)
}

const replaceJobsObservation = (
  fixture: ReturnType<typeof makeFixture>,
  body: unknown
): ReadonlyArray<S2SStageUploadBuildObservation> => {
  const phase = "LOOKUP_JOBS" as const
  const original = observationAtPhase(fixture.observations, phase).observation
  const replacement = right(
    observeS2SGitHubWorkflowAttemptJobs(
      jsonBytes(body),
      RUN_ID,
      1,
      original.receipt.observedAtUnixSeconds,
      observationProvenance(original)
    )
  )
  return replaceObservationAtPhase(fixture.observations, phase, replacement)
}

const replaceArtifactRequery = (
  fixture: ReturnType<typeof makeFixture>,
  body: unknown
): ReadonlyArray<S2SStageUploadBuildObservation> => {
  const phase = "READBACK_ARTIFACT" as const
  const original = observationAtPhase(fixture.observations, phase).observation
  const replacement = right(
    observeS2SGitHubArtifact(
      jsonBytes(body),
      ARTIFACT_IDS[fixture.stage],
      original.receipt.observedAtUnixSeconds,
      observationProvenance(original)
    )
  )
  return replaceObservationAtPhase(fixture.observations, phase, replacement)
}

const buildInputWithObservations = (
  fixture: ReturnType<typeof makeFixture>,
  observations: ReadonlyArray<S2SStageUploadBuildObservation>,
  artifactDownload: S2SGitHubArtifactDownload = fixture.artifactDownload
) => ({
  ...fixture.buildInput,
  artifactDownload,
  observations,
  assertionPermitEvidence: makePermit(
    fixture.currentRunEvidence,
    observations,
    artifactDownload.receipt
  )
})

it("round-trips every stage and successful attempt deterministically", () => {
  for (const stage of S2S_CONFIRMATORY_JOB_STAGES) {
    for (const attempt of [1, 2, 3] as const) {
      const fixture = makeFixture(stage, attempt)
      const first = right(buildS2SStageUploadPostcondition(fixture.buildInput))
      const second = right(buildS2SStageUploadPostcondition(fixture.buildInput))
      expect(first._tag).toBe(
        "ValidatedNonAuthorizingStageUploadPostcondition"
      )
      expect(first.manifest.stage).toBe(stage)
      expect(Object.isFrozen(first.manifest)).toBe(true)
      expect(Object.keys(first.manifest).sort()).toEqual(
        MANIFEST_TOP_LEVEL_KEYS
      )
      expect(MANIFEST_TOP_LEVEL_KEYS).toHaveLength(37)
      expect(first.manifest.successful_attempt_ordinal).toBe(attempt)
      expect(first.manifest.observation_count).toBe(5 + attempt * 2)
      expect(first.manifest.publisher_return_used_as_evidence).toBe(false)
      expect(first.manifest.external_exactly_once_claimed).toBe(false)
      expect(first.manifest.durable_replay_prevention_claimed).toBe(false)
      expect(first.assertionPermitEvidence.ledgerEntries).toHaveLength(
        10 + attempt * 2
      )
      expect(first.readCarrierBytes()).toEqual(second.readCarrierBytes())
      expect(first.carrierRawSha256).toBe(second.carrierRawSha256)

      const validated = right(
        validateS2SStageUploadPostcondition({
          carrierBytes: first.readCarrierBytes(),
          currentRunEvidence: fixture.currentRunEvidence,
          currentStageArchiveBytes: fixture.archive,
          preparedMembers: fixture.preparedMembers
        })
      )
      const reconstructed = right(
        reconstructS2SStageUploadPostcondition({
          manifestBytes: first.readManifestBytes(),
          observationBytes: first.readObservationBlob(),
          currentRunEvidence: fixture.currentRunEvidence,
          currentStageArchiveBytes: fixture.archive,
          preparedMembers: fixture.preparedMembers
        })
      )
      expect(validated.manifest).toEqual(first.manifest)
      expect(reconstructed.manifest).toEqual(first.manifest)
      expect(reconstructed.readArchiveBytes()).toEqual(fixture.archive)
      expect(reconstructed.observations).toHaveLength(5 + attempt * 2)
    }
  }
})

it("keeps the production-shell assembler fixed to trusted permit evidence", () => {
  const fixture = makeFixture("REGISTER", 1)
  expectReason(
    buildS2SStageUploadPostconditionFromProductionShell(fixture.buildInput),
    "PERMIT_BINDING_MISMATCH"
  )
})

it("returns deep-frozen evidence and fresh defensive byte copies", () => {
  const fixture = makeFixture("ADJUDICATE", 3)
  const snapshot = right(buildS2SStageUploadPostcondition(fixture.buildInput))
  expect(Object.isFrozen(snapshot)).toBe(true)
  expect(Object.isFrozen(snapshot.manifest)).toBe(true)
  expect(Object.isFrozen(snapshot.manifest.identity)).toBe(true)
  expect(Object.isFrozen(snapshot.manifest.observations)).toBe(true)
  expect(Object.isFrozen(snapshot.manifest.observations[0])).toBe(true)
  expect(Object.isFrozen(snapshot.assertionPermitEvidence)).toBe(true)
  expect(Object.isFrozen(snapshot.assertionPermitEvidence.ledgerEntries)).toBe(
    true
  )

  const readers = [
    snapshot.readCarrierBytes,
    snapshot.readManifestBytes,
    snapshot.readObservationBlob,
    snapshot.readArchiveBytes
  ]
  for (const read of readers) {
    const first = read()
    const expected = read()
    first[0] = (first[0] ?? 0) ^ 0xff
    expect(read()).toEqual(expected)
    expect(read()).not.toBe(first)
  }
})

it.effect("keeps build and validation byte inspection lazy", () =>
  Effect.gen(function* () {
    const fixture = makeFixture("CONFIRM", 2)
    let buildReads = 0
    const lazyBuildInput = {
      ...fixture.buildInput,
      artifactDownload: {
        receipt: fixture.artifactDownload.receipt,
        readArchiveBytes: (): Uint8Array => {
          buildReads += 1
          return Uint8Array.from(fixture.archive)
        }
      },
      preparedMembers: fixture.preparedMembers.map((member) => ({
        name: member.name,
        byteLength: member.byteLength,
        rawBytesSha256: member.rawBytesSha256,
        readBytes: (): Uint8Array => {
          buildReads += 1
          return member.readBytes()
        }
      }))
    }
    const build = buildS2SStageUploadPostconditionEffect(lazyBuildInput)
    expect(buildReads).toBe(0)
    const snapshot = yield* build
    expect(buildReads).toBeGreaterThan(0)

    let validationReads = 0
    const validation = validateS2SStageUploadPostconditionEffect({
      carrierBytes: snapshot.readCarrierBytes(),
      currentRunEvidence: fixture.currentRunEvidence,
      currentStageArchiveBytes: fixture.archive,
      preparedMembers: fixture.preparedMembers.map((member) => ({
        name: member.name,
        byteLength: member.byteLength,
        rawBytesSha256: member.rawBytesSha256,
        readBytes: (): Uint8Array => {
          validationReads += 1
          return member.readBytes()
        }
      }))
    })
    expect(validationReads).toBe(0)
    yield* validation
    expect(validationReads).toBeGreaterThan(0)
  })
)

it("rejects proxies, excess keys, accessors, and exotic byte surfaces", () => {
  const fixture = makeFixture("REGISTER", 1)
  expectReason(
    buildS2SStageUploadPostcondition(
      new Proxy(fixture.buildInput, Object.create(null))
    ),
    "INPUT_INVALID"
  )
  expectReason(
    buildS2SStageUploadPostcondition({
      ...fixture.buildInput,
      publisherReturn: "success"
    }),
    "INPUT_INVALID"
  )

  let getterCalls = 0
  const accessorInput: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(fixture.buildInput)) {
    if (key === "artifactDownload") {
      Object.defineProperty(accessorInput, key, {
        enumerable: true,
        get: () => {
          getterCalls += 1
          return value
        }
      })
    } else {
      Object.defineProperty(accessorInput, key, {
        enumerable: true,
        value
      })
    }
  }
  expectReason(
    buildS2SStageUploadPostcondition(accessorInput),
    "INPUT_INVALID"
  )
  expect(getterCalls).toBe(0)

  const snapshot = right(buildS2SStageUploadPostcondition(fixture.buildInput))
  expectReason(
    validateS2SStageUploadPostcondition({
      carrierBytes: Buffer.from(snapshot.readCarrierBytes()),
      currentRunEvidence: fixture.currentRunEvidence,
      currentStageArchiveBytes: fixture.archive,
      preparedMembers: fixture.preparedMembers
    }),
    "BYTE_BUDGET_EXCEEDED"
  )
  if (typeof SharedArrayBuffer !== "undefined") {
    const sharedCarrier = new Uint8Array(
      new SharedArrayBuffer(snapshot.carrierByteLength)
    )
    sharedCarrier.set(snapshot.readCarrierBytes())
    expectReason(
      validateS2SStageUploadPostcondition({
        carrierBytes: sharedCarrier,
        currentRunEvidence: fixture.currentRunEvidence,
        currentStageArchiveBytes: fixture.archive,
        preparedMembers: fixture.preparedMembers
      }),
      "BYTE_BUDGET_EXCEEDED"
    )
  }

  expectReason(
    buildS2SStageUploadPostcondition({
      ...fixture.buildInput,
      preparedMembers: [
        {
          ...fixture.preparedMembers[0],
          publisherReturn: true
        }
      ]
    }),
    "PREPARED_MEMBER_MISMATCH"
  )
})

it("requires canonical manifest JSON and its exact self-hash", () => {
  const fixture = makeFixture("CONFIRM", 2)
  const snapshot = right(buildS2SStageUploadPostcondition(fixture.buildInput))
  const manifestBytes = snapshot.readManifestBytes()
  const observationBytes = snapshot.readObservationBlob()
  const document = parseManifest(manifestBytes)
  expect(manifestBytes).toEqual(
    right(canonicalS2SControlJsonBytes(snapshot.manifest))
  )
  const {
    postcondition_receipt_sha256: declaredReceipt,
    ...manifestCore
  } = snapshot.manifest
  expect(right(canonicalS2SControlSha256(manifestCore))).toBe(declaredReceipt)

  const pretty = ENCODER.encode(`${JSON.stringify(document, null, 2)}\n`)
  expectReason(
    validateFixtureCarrier(
      fixture,
      carrierFromParts(pretty, observationBytes)
    ),
    "MANIFEST_INVALID"
  )

  const stale = structuredClone(document)
  stale["artifact_byte_length"] =
    (stale["artifact_byte_length"] as number) + 1
  expectReason(
    validateFixtureCarrier(
      fixture,
      carrierFromDocument(stale, observationBytes)
    ),
    "MANIFEST_SELF_HASH_MISMATCH"
  )

  const excess = sealManifest({ ...document, publisher_return: "ignored" })
  expectReason(
    validateFixtureCarrier(
      fixture,
      carrierFromDocument(excess, observationBytes)
    ),
    "MANIFEST_INVALID"
  )
})

it("rejects observation topology drift and coherent raw-body mutation", () => {
  const fixture = makeFixture("CONFIRM", 3)
  const snapshot = right(buildS2SStageUploadPostcondition(fixture.buildInput))
  const document = parseManifest(snapshot.readManifestBytes())
  const observationBytes = snapshot.readObservationBlob()

  const rawDrift = Uint8Array.from(observationBytes)
  rawDrift[0] = (rawDrift[0] ?? 0) ^ 0x01
  expectReason(
    validateFixtureCarrier(
      fixture,
      carrierFromDocument(document, rawDrift)
    ),
    "OBSERVATION_TOPOLOGY_INVALID"
  )

  const topology = structuredClone(document)
  const topologyDescriptors = topology["observations"] as Array<
    Record<string, unknown>
  >
  const firstTopology = topologyDescriptors[0]
  if (firstTopology === undefined) throw new Error("descriptor missing")
  firstTopology["offset"] = 1
  expectReason(
    validateFixtureCarrier(
      fixture,
      carrierFromDocument(sealManifest(topology), observationBytes)
    ),
    "OBSERVATION_TOPOLOGY_INVALID"
  )

  const coherentRawDrift = replaceAsciiOnce(
    observationBytes,
    '"head_branch":"main"',
    '"head_branch":"maim"'
  )
  const coherent = structuredClone(document)
  const descriptors = coherent["observations"] as Array<
    Record<string, unknown>
  >
  const first = descriptors[0]
  if (first === undefined) throw new Error("descriptor missing")
  const firstLength = first["byte_length"] as number
  first["raw_body_sha256"] = rawS2SFileSha256(
    coherentRawDrift.subarray(0, firstLength)
  )
  coherent["observation_blob_sha256"] = rawS2SFileSha256(coherentRawDrift)
  expectReason(
    validateFixtureCarrier(
      fixture,
      carrierFromDocument(sealManifest(coherent), coherentRawDrift)
    ),
    "OBSERVATION_REPLAY_INVALID"
  )
})

it("rejects cross-stage, recovered-archive, and prepared-byte mismatches", () => {
  const register = makeFixture("REGISTER", 1)
  const confirm = makeFixture("CONFIRM", 1)
  const registerSnapshot = right(
    buildS2SStageUploadPostcondition(register.buildInput)
  )
  expectReason(
    validateS2SStageUploadPostcondition({
      carrierBytes: registerSnapshot.readCarrierBytes(),
      currentRunEvidence: confirm.currentRunEvidence,
      currentStageArchiveBytes: confirm.archive,
      preparedMembers: confirm.preparedMembers
    }),
    "STAGE_IDENTITY_MISMATCH"
  )

  const confirmSnapshot = right(
    buildS2SStageUploadPostcondition(confirm.buildInput)
  )
  const alternateArchive = makeArchive("CONFIRM", 2)
  expectReason(
    validateS2SStageUploadPostcondition({
      carrierBytes: confirmSnapshot.readCarrierBytes(),
      currentRunEvidence: confirm.currentRunEvidence,
      currentStageArchiveBytes: alternateArchive,
      preparedMembers: makePreparedMembers("CONFIRM", 2)
    }),
    "DOWNLOAD_REPLAY_INVALID"
  )

  const changedPrepared = confirm.preparedMembers.map((member, index) => {
    if (index !== 0) return member
    const bytes = member.readBytes()
    bytes[0] = (bytes[0] ?? 0) ^ 0x01
    return {
      name: member.name,
      byteLength: bytes.byteLength,
      rawBytesSha256: rawS2SFileSha256(bytes),
      readBytes: (): Uint8Array => Uint8Array.from(bytes)
    }
  })
  expectReason(
    validateS2SStageUploadPostcondition({
      carrierBytes: confirmSnapshot.readCarrierBytes(),
      currentRunEvidence: confirm.currentRunEvidence,
      currentStageArchiveBytes: confirm.archive,
      preparedMembers: changedPrepared
    }),
    "PREPARED_MEMBER_MISMATCH"
  )
})

it("rejects reversed rosters and alternate valid ZIP dialects", () => {
  const fixture = makeFixture("ADJUDICATE", 2)
  const snapshot = right(buildS2SStageUploadPostcondition(fixture.buildInput))
  const members = [
    {
      name: S2S_STAGE_UPLOAD_POSTCONDITION_MANIFEST_MEMBER_NAME,
      bytes: snapshot.readManifestBytes()
    },
    {
      name: S2S_STAGE_UPLOAD_POSTCONDITION_OBSERVATIONS_MEMBER_NAME,
      bytes: snapshot.readObservationBlob()
    }
  ] as const

  const reversed = buildCompatibleStoredZip([...members].reverse(), 0)
  assertGenericCarrierZip(reversed)
  expectReason(validateFixtureCarrier(fixture, reversed), "CARRIER_INVALID")

  const alternateDialect = buildCompatibleStoredZip(members, 1)
  assertGenericCarrierZip(alternateDialect)
  expectReason(
    validateFixtureCarrier(fixture, alternateDialect),
    "CARRIER_INVALID"
  )
})

it("never adapts a test-only golden postcondition into production evidence", () => {
  const fixture = makeFixture("REGISTER", 1)
  const goldenManifest = right(
    canonicalS2SControlJsonBytes({
      schema_version:
        S2S_TEST_ONLY_GOLDEN_UPLOAD_POSTCONDITION_SCHEMA_VERSION
    })
  )
  const carrier = carrierFromParts(goldenManifest, new Uint8Array([0x31]))
  expectReason(
    validateFixtureCarrier(fixture, carrier),
    "TEST_ONLY_GOLDEN_REJECTED"
  )
})

it("rejects forged trusted build authority while recovery stays non-authorizing", () => {
  const fixture = makeFixture("ADJUDICATE", 3)
  const baseline = right(
    buildS2SStageUploadPostcondition(fixture.buildInput)
  )
  const trustedCore: Omit<
    S2SStageUploadAssertionPermitEvidence,
    "receiptSha256"
  > = {
    ...permitCore(fixture.assertionPermitEvidence),
    authorityScope: "TRUSTED_SINGLE_MODULE_CURRENT_JOB",
    authorizationClaimed: true,
    oneUseClaim: "ONE_USE_PER_GENUINE_AUTHORITY_AND_PROCESS_IDENTITY_SLOT"
  }
  const trustedPermit = sealPermit(trustedCore)
  expectReason(
    buildS2SStageUploadPostcondition({
      ...fixture.buildInput,
      assertionPermitEvidence: trustedPermit
    }),
    "PERMIT_BINDING_MISMATCH"
  )

  const trustedDocument = parseManifest(baseline.readManifestBytes())
  trustedDocument["assertion_permit_evidence"] = structuredClone(trustedPermit)
  const sealedDocument = sealManifest(trustedDocument)
  const manifestBytes = right(canonicalS2SControlJsonBytes(sealedDocument))
  const carrierBytes = carrierFromParts(
    manifestBytes,
    baseline.readObservationBlob()
  )
  const recovered = right(validateFixtureCarrier(fixture, carrierBytes))
  expect(recovered._tag).toBe(
    "ValidatedNonAuthorizingStageUploadPostcondition"
  )
  expect(recovered.assertionPermitEvidence.authorityScope).toBe(
    "TRUSTED_SINGLE_MODULE_CURRENT_JOB"
  )
  const reconstructed = right(
    reconstructS2SStageUploadPostcondition({
      manifestBytes,
      observationBytes: baseline.readObservationBlob(),
      currentRunEvidence: fixture.currentRunEvidence,
      currentStageArchiveBytes: fixture.archive,
      preparedMembers: fixture.preparedMembers
    })
  )
  expect(reconstructed._tag).toBe(
    "ValidatedNonAuthorizingStageUploadPostcondition"
  )
})

it("rejects wrong and proxied supplied projections without invoking traps", () => {
  const fixture = makeFixture("CONFIRM", 1)
  const entry = observationAtPhase(
    fixture.observations,
    "LOOKUP_RUN_START"
  )
  const run = right(
    observeS2SGitHubWorkflowRun(
      entry.observation.readRawBody(),
      RUN_ID,
      entry.observation.receipt.observedAtUnixSeconds,
      observationProvenance(entry.observation)
    )
  )
  const wrongObservation = Object.freeze({
    receipt: Object.freeze({
      ...run.receipt,
      projection: Object.freeze({
        ...run.receipt.projection,
        headBranch: "maim"
      })
    }),
    readRawBody: run.readRawBody
  })
  const wrongObservations = replaceObservationAtPhase(
    fixture.observations,
    "LOOKUP_RUN_START",
    wrongObservation
  )
  expectReason(
    buildS2SStageUploadPostcondition(
      buildInputWithObservations(fixture, wrongObservations)
    ),
    "OBSERVATION_REPLAY_INVALID"
  )

  let trapCalls = 0
  const projectionProxy = new Proxy(run.receipt.projection, {
    get: () => {
      trapCalls += 1
      throw new Error("projection get trap must not run")
    },
    getOwnPropertyDescriptor: () => {
      trapCalls += 1
      throw new Error("projection descriptor trap must not run")
    },
    getPrototypeOf: () => {
      trapCalls += 1
      throw new Error("projection prototype trap must not run")
    },
    ownKeys: () => {
      trapCalls += 1
      throw new Error("projection ownKeys trap must not run")
    }
  })
  const proxyObservation = Object.freeze({
    receipt: Object.freeze({
      ...run.receipt,
      projection: projectionProxy
    }),
    readRawBody: run.readRawBody
  })
  const proxyObservations = replaceObservationAtPhase(
    fixture.observations,
    "LOOKUP_RUN_START",
    proxyObservation
  )
  expectReason(
    buildS2SStageUploadPostcondition(
      buildInputWithObservations(fixture, proxyObservations)
    ),
    "OBSERVATION_REPLAY_INVALID"
  )
  expect(trapCalls).toBe(0)
})

it("round-trips 65 artifacts and a 65-label job without truncation", () => {
  const fixture = makeFixture("ADJUDICATE", 1)
  const jobsBody = structuredClone(jobsJson("ADJUDICATE"))
  const currentJob = jobsBody.jobs.find(
    (job) => job.name === "adjudicate"
  )
  if (currentJob === undefined) throw new Error("current job fixture missing")
  currentJob.labels = Array.from(
    { length: 65 },
    (_, index) => `runner-label-${index.toString().padStart(2, "0")}`
  )
  const originalJobs = observationAtPhase(
    fixture.observations,
    "LOOKUP_JOBS"
  ).observation
  const largeJobsObservation = right(
    observeS2SGitHubWorkflowAttemptJobs(
      jsonBytes(jobsBody),
      RUN_ID,
      1,
      originalJobs.receipt.observedAtUnixSeconds,
      observationProvenance(originalJobs)
    )
  )
  expect(
    largeJobsObservation.receipt.projection.jobs.find(
      (job) => job.name === "adjudicate"
    )?.labels
  ).toHaveLength(65)

  const fixedArtifact = artifactJson("ADJUDICATE", fixture.archive)
  const artifacts = [
    fixedArtifact,
    ...Array.from({ length: 64 }, (_, index) => ({
      ...fixedArtifact,
      id: 10_000_000_000 + index,
      name: `unrelated-${index.toString().padStart(2, "0")}`
    }))
  ]
  const listingPhase = "LOOKUP_ARTIFACTS_1" as const
  const originalListing = observationAtPhase(
    fixture.observations,
    listingPhase
  ).observation
  const largeArtifactObservation = right(
    observeS2SGitHubRunArtifacts(
      jsonBytes({ total_count: artifacts.length, artifacts }),
      RUN_ID,
      originalListing.receipt.observedAtUnixSeconds,
      observationProvenance(originalListing)
    )
  )
  expect(largeArtifactObservation.receipt.projection.totalCount).toBe(65)
  expect(
    largeArtifactObservation.receipt.projection.artifacts.filter(
      (artifact) =>
        artifact.name ===
        S2S_STAGE_ARTIFACT_SPECS.ADJUDICATE.artifactName
    )
  ).toHaveLength(1)

  let observations = replaceObservationAtPhase(
    fixture.observations,
    "LOOKUP_JOBS",
    largeJobsObservation
  )
  observations = replaceObservationAtPhase(
    observations,
    listingPhase,
    largeArtifactObservation
  )
  const snapshot = right(
    buildS2SStageUploadPostcondition(
      buildInputWithObservations(fixture, observations)
    )
  )
  expect(
    Either.isRight(
      validateS2SStageUploadPostcondition({
        carrierBytes: snapshot.readCarrierBytes(),
        currentRunEvidence: fixture.currentRunEvidence,
        currentStageArchiveBytes: fixture.archive,
        preparedMembers: fixture.preparedMembers
      })
    )
  ).toBe(true)
})

it("rejects duplicate, expired, cross-head, and impossible-time artifacts", () => {
  const fixture = makeFixture("REGISTER", 2)
  const fixed = artifactJson("REGISTER", fixture.archive)
  const cases: ReadonlyArray<{
    readonly name: string
    readonly artifacts: ReadonlyArray<unknown>
    readonly reason: S2SStageUploadPostconditionError["reason"]
  }> = [
    {
      name: "duplicate fixed name",
      artifacts: [fixed, { ...fixed, id: fixed.id + 100 }],
      reason: "OBSERVATION_REPLAY_INVALID"
    },
    {
      name: "expired fixed artifact",
      artifacts: [{ ...fixed, expired: true }],
      reason: "ARTIFACT_BINDING_MISMATCH"
    },
    {
      name: "expired-by-time fixed artifact with a false boolean",
      artifacts: [
        {
          ...fixed,
          expired: false,
          expires_at: "2026-08-21T03:20:00Z"
        }
      ],
      reason: "ARTIFACT_BINDING_MISMATCH"
    },
    {
      name: "cross-head artifact",
      artifacts: [
        {
          ...fixed,
          workflow_run: { id: RUN_ID, head_sha: "c".repeat(40) }
        }
      ],
      reason: "OBSERVATION_TOPOLOGY_INVALID"
    },
    {
      name: "artifact before producer start",
      artifacts: [{ ...fixed, created_at: "2026-08-21T03:10:33Z" }],
      reason: "ARTIFACT_BINDING_MISMATCH"
    }
  ]
  for (const scenario of cases) {
    const observations = replaceSuccessfulArtifactListing(
      fixture,
      scenario.artifacts
    )
    const result = buildS2SStageUploadPostcondition(
      buildInputWithObservations(fixture, observations)
    )
    expectReason(result, scenario.reason)
  }
})

it("rejects wrong current, predecessor, and later job state", () => {
  const fixture = makeFixture("CONFIRM", 1)
  type MutableJobsBody = {
    readonly total_count: number
    readonly jobs: Array<Record<string, unknown>>
  }
  const mutableJobs = (): MutableJobsBody =>
    structuredClone(jobsJson("CONFIRM")) as MutableJobsBody
  const cases: ReadonlyArray<{
    readonly name: string
    readonly mutate: (body: MutableJobsBody) => void
  }> = [
    {
      name: "wrong current job",
      mutate: (body) => {
        const job = body.jobs.find((candidate) => candidate["name"] === "confirm")
        if (job === undefined) throw new Error("confirm job fixture missing")
        job["id"] = CONFIRM_JOB_ID + 500
      }
    },
    {
      name: "failed predecessor",
      mutate: (body) => {
        const job = body.jobs.find((candidate) => candidate["name"] === "register")
        if (job === undefined) throw new Error("register job fixture missing")
        job["conclusion"] = "failure"
      }
    },
    {
      name: "started later job",
      mutate: (body) => {
        const job = body.jobs.find(
          (candidate) => candidate["name"] === "adjudicate"
        )
        if (job === undefined) throw new Error("adjudicate job fixture missing")
        job["status"] = "in_progress"
      }
    }
  ]
  for (const scenario of cases) {
    const body = mutableJobs()
    scenario.mutate(body)
    const observations = replaceJobsObservation(fixture, body)
    expectReason(
      buildS2SStageUploadPostcondition(
        buildInputWithObservations(fixture, observations)
      ),
      "STAGE_IDENTITY_MISMATCH"
    )
  }
})

it("rejects coherently regenerated reused IDs and nonmonotonic observations", () => {
  const fixture = makeFixture("CONFIRM", 2)
  const runStart = observationAtPhase(
    fixture.observations,
    "LOOKUP_RUN_START"
  ).observation
  const jobs = observationAtPhase(
    fixture.observations,
    "LOOKUP_JOBS"
  ).observation

  const reusedJobs = right(
    observeS2SGitHubWorkflowAttemptJobs(
      jobs.readRawBody(),
      RUN_ID,
      1,
      jobs.receipt.observedAtUnixSeconds,
      {
        ...observationProvenance(jobs),
        githubRequestId: runStart.receipt.githubRequestId
      }
    )
  )
  const reusedObservations = replaceObservationAtPhase(
    fixture.observations,
    "LOOKUP_JOBS",
    reusedJobs
  )
  const reusedInput = buildInputWithObservations(
    fixture,
    reusedObservations
  )
  const reusedLedgerEntry =
    reusedInput.assertionPermitEvidence.ledgerEntries.find(
      (entry) => entry.phase === "LOOKUP_JOBS"
    )
  expect(reusedLedgerEntry?.githubRequestId).toBe(
    reusedJobs.receipt.githubRequestId
  )
  expect(reusedLedgerEntry?.receiptSha256).toBe(
    reusedJobs.receipt.receiptSha256
  )
  const reusedFailure = expectReason(
    buildS2SStageUploadPostcondition(reusedInput),
    "PERMIT_BINDING_MISMATCH"
  )
  expect(reusedFailure.phase).toBe("ASSERTION_PERMIT_EVIDENCE")
  expect(reusedFailure.detail).toContain("exact non-evicting ledger diverged")

  const earlierJobsTime = OBSERVED_AT - 5
  expect(earlierJobsTime).toBeGreaterThan(
    fixture.currentRunEvidence.observations.runEnd.observedAtUnixSeconds
  )
  expect(earlierJobsTime).toBeLessThan(
    runStart.receipt.observedAtUnixSeconds
  )
  const earlierJobs = right(
    observeS2SGitHubWorkflowAttemptJobs(
      jobs.readRawBody(),
      RUN_ID,
      1,
      earlierJobsTime,
      observationProvenance(jobs)
    )
  )
  const nonmonotonicObservations = replaceObservationAtPhase(
    fixture.observations,
    "LOOKUP_JOBS",
    earlierJobs
  )
  const nonmonotonicInput = buildInputWithObservations(
    fixture,
    nonmonotonicObservations
  )
  const nonmonotonicLedgerEntry =
    nonmonotonicInput.assertionPermitEvidence.ledgerEntries.find(
      (entry) => entry.phase === "LOOKUP_JOBS"
    )
  expect(nonmonotonicLedgerEntry?.observedAtUnixSeconds).toBe(
    earlierJobs.receipt.observedAtUnixSeconds
  )
  expect(nonmonotonicLedgerEntry?.receiptSha256).toBe(
    earlierJobs.receipt.receiptSha256
  )
  const nonmonotonicFailure = expectReason(
    buildS2SStageUploadPostcondition(nonmonotonicInput),
    "PERMIT_BINDING_MISMATCH"
  )
  expect(nonmonotonicFailure.phase).toBe("ASSERTION_PERMIT_EVIDENCE")
  expect(nonmonotonicFailure.detail).toContain(
    "exact non-evicting ledger diverged"
  )
})

it("rejects artifact requery and independent download drift", () => {
  const fixture = makeFixture("CONFIRM", 1)
  const requeryDrift = replaceArtifactRequery(fixture, {
    ...artifactJson("CONFIRM", fixture.archive),
    name: "s2s-candidate-drift"
  })
  expectReason(
    buildS2SStageUploadPostcondition(
      buildInputWithObservations(fixture, requeryDrift)
    ),
    "ARTIFACT_BINDING_MISMATCH"
  )

  const alternateArchive = buildCompatibleStoredZip(
    archiveMembers("CONFIRM"),
    1
  )
  expect(alternateArchive).not.toEqual(fixture.archive)
  const alternateDownload = makeDownload(
    "CONFIRM",
    1,
    alternateArchive,
    fixture.artifactDownload.receipt.downloadedAtUnixSeconds
  )
  expectReason(
    buildS2SStageUploadPostcondition(
      buildInputWithObservations(
        fixture,
        fixture.observations,
        alternateDownload
      )
    ),
    "DOWNLOAD_REPLAY_INVALID"
  )
})

it("rejects a carrier directly above the fixed byte cap", () => {
  const fixture = makeFixture("REGISTER", 1)
  const oversizedCarrier = new Uint8Array(
    S2S_STAGE_UPLOAD_POSTCONDITION_MAX_BYTES + 1
  )
  expectReason(
    validateS2SStageUploadPostcondition({
      carrierBytes: oversizedCarrier,
      currentRunEvidence: fixture.currentRunEvidence,
      currentStageArchiveBytes: fixture.archive,
      preparedMembers: fixture.preparedMembers
    }),
    "BYTE_BUDGET_EXCEEDED"
  )
})

it("rejects a coherently resealed archive-reference mutation", () => {
  const fixture = makeFixture("ADJUDICATE", 2)
  const snapshot = right(buildS2SStageUploadPostcondition(fixture.buildInput))
  const document = parseManifest(snapshot.readManifestBytes())
  const archiveReference = document["archive_reference"] as Record<
    string,
    unknown
  >
  const originalHash = archiveReference["raw_sha256"]
  archiveReference["raw_sha256"] =
    originalHash === "0".repeat(64) ? "1".repeat(64) : "0".repeat(64)
  const carrierBytes = carrierFromDocument(
    sealManifest(document),
    snapshot.readObservationBlob()
  )
  expectReason(
    validateFixtureCarrier(fixture, carrierBytes),
    "ARCHIVE_REFERENCE_INVALID"
  )
})

it("keeps REGISTER generic validation separate from predecessor replay", () => {
  const register = makeCurrentRunEvidence("REGISTER")
  const generic = validateS2SCurrentRunStageEvidence(register)
  expect(Either.isRight(generic)).toBe(true)
  if (Either.isLeft(generic)) throw generic.left
  expect(generic.right.stage).toBe("REGISTER")
  expect(generic.right.predecessorJobDatabaseIds).toEqual([])

  const predecessorCompatibility =
    validateS2SCurrentRunStageEvidenceForArtifactReplay(register)
  expect(Either.isLeft(predecessorCompatibility)).toBe(true)
  if (Either.isRight(predecessorCompatibility)) {
    throw new Error("REGISTER must not enter predecessor-read compatibility")
  }
  expect(predecessorCompatibility.left.reason).toBe(
    "CURRENT_RUN_BINDING_MISMATCH"
  )
  expect(predecessorCompatibility.left.detail).toContain(
    "no REGISTER consumer surface"
  )
})
