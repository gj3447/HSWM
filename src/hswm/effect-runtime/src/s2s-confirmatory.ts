import { Data, Either, Schema } from "effect"

import { canonicalS2SControlSha256 } from "./s2s-canonical.js"
import { deriveS2SExternalSeed, S2S_EXTERNAL_SEED_DOMAIN } from "./s2s-seed.js"

/**
 * The adopted train/dev pilot is an input to this control boundary, not a
 * scientific verdict. Changing this value requires a new, independently
 * replayed adoption receipt.
 */
export const S2S_PILOT_ADOPTION_RECEIPT_SHA256 =
  "97a752fea5ae45a311a2e8cf2376b391d76a8269dbab20f60688f543bcc5dea1" as const

export const S2S_CONFIRMATORY_POLICY_SCHEMA_VERSION =
  "hswm-swm0w-s2s-confirmatory-operational-policy/v1" as const

export const S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION =
  "hswm-swm0w-s2s-confirmatory-control-event/v1" as const

export const S2S_CONFIRMATORY_EXPERIMENT_ID =
  "hswm-swm0w-s2s-confirmatory-v1" as const

export const S2S_PROTOCOL_CONFIG_RECEIPT_SHA256 =
  "a8f62d3811e42fbf3bc0dc82a52a17f3fa27b4dfa1d43aa9e7ea302a142c40bb" as const

export const S2S_PROTOCOL_CONFIG_DOCUMENT_SHA256 =
  "315dad65a8882c4b7c5fb73d295df28b58b0696e25b1b790a342b40ced8d10c4" as const

/** SHA-256 of canonical float-free JSON for S2S_CONFIRMATORY_POLICY. */
export const S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256 =
  "d6a0c679f9ff9c72773f8a3713bffe1f3ac5d2b6f5e53e653603b30204d9c7eb" as const

export const S2S_NUMERIC_CONTINUITY_PATHS = Object.freeze([
  "pyproject.toml",
  "src/hswm/experiments/swm0w_s2s_worlds.py",
  "src/hswm/experiments/swm0w_s2s_family.py",
  "src/hswm/experiments/swm0w_s2s_operator.py",
  "src/hswm/experiments/swm0w_s2s_training.py",
  "src/hswm/experiments/swm0w_s2s_protocol.py",
  "src/hswm/experiments/swm0w_s2s_pilot.py",
  "uv.lock"
] as const)

const MEBIBYTE = 1_048_576

/**
 * Frozen operational policy. All durations and byte sizes are integers so the
 * control plane never depends on binary floating-point policy comparisons.
 */
export const S2S_CONFIRMATORY_POLICY = Object.freeze({
  schemaVersion: S2S_CONFIRMATORY_POLICY_SCHEMA_VERSION,
  experimentId: S2S_CONFIRMATORY_EXPERIMENT_ID,
  adoptionReceiptSha256: S2S_PILOT_ADOPTION_RECEIPT_SHA256,
  protocolConfigReceiptSha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
  resourceBasis: Object.freeze({
    selectedFitReplayBaselineNanoseconds: 424_904_259_742,
    selectedArmMaxNanoseconds: Object.freeze({
      T16: 117_431_761_697,
      P_CAP18: 16_843_724_419,
      DS870: 18_412_821_404
    }),
    projectedTwentyTaskFitReplayNanoseconds: 3_053_766_150_400,
    projectedTaskPreparationNanoseconds: 15_622_204_200,
    projectedPreEvaluationNanoseconds: 3_069_388_354_600,
    postSeedWorkCapNanoseconds: 7_200_000_000_000,
    postSeedReserveNanoseconds: 4_130_611_645_400
  }),
  deadlines: Object.freeze({
    maximumDeclaredPulseLeadSeconds: 3_900,
    registerJobTimeoutSeconds: 1_200,
    confirmWaitBudgetSeconds: 3_900,
    confirmPostSeedWorkBudgetSeconds: 7_200,
    confirmCommandSlackSeconds: 300,
    confirmCommandTimeoutSeconds: 11_400,
    confirmJobTimeoutSeconds: 12_600,
    adjudicationCommandTimeoutSeconds: 1_200,
    adjudicationJobTimeoutSeconds: 1_800,
    githubHostedJobHardCapSeconds: 21_600
  }),
  archive: Object.freeze({
    compressionLevel: 0,
    retentionDays: 90,
    overwrite: false,
    artifactCountPerJob: 1,
    registrationArchiveMaximumBytes: 4 * MEBIBYTE,
    candidateMemberMaximumBytes: 60 * MEBIBYTE,
    candidateArchiveMaximumBytes: 64 * MEBIBYTE,
    adjudicationArchiveMaximumBytes: 4 * MEBIBYTE,
    apiDigestRequired: true,
    downloadedReadbackRequired: true
  }),
  candidateArchive: Object.freeze({
    exactMembers: Object.freeze([
      "control_receipt.json",
      "numeric_candidate.json"
    ] as const),
    numericMemberOwnership: "PYTHON_OPAQUE_CANONICAL_UTF8_LF" as const,
    controlMemberOwnership: "TYPESCRIPT_CONTROL_ENVELOPE" as const
  }),
  rssTelemetry: Object.freeze({
    api: "getrusage" as const,
    subject: "RUSAGE_SELF" as const,
    unit: "KiB" as const,
    pilotObservedPeakRssKiB: 171_108,
    required: true,
    hardLimitKiB: null,
    admissionCriterion: false,
    scientificVerdictCriterion: false,
    actualOomDisposition: "VOID" as const
  }),
  attempt: Object.freeze({
    workflowRunAttempt: 1,
    resume: false,
    checkpointResume: false,
    rerun: false,
    reroll: false,
    cellRetry: false,
    taskRetry: false,
    taskSkip: false,
    partialCandidate: false
  }),
  workload: Object.freeze({
    taskCount: 20,
    armOrder: Object.freeze(["T16", "P_CAP18", "DS870"] as const),
    cellCount: 60,
    optimizerExecutionsPerCell: 2,
    optimizerExecutionCount: 120,
    testWorldsPerTask: 6_250,
    scoreVariantCount: 8,
    domainWorldCount: 15_625,
    allFitReplayBeforeAnyTestMaterialization: true,
    adjudicationOptimizerExecutionCount: 0,
    adjudicationRerunsBls: true,
    adjudicationRerunsBatch: true,
    adjudicationRerunsTestEvaluation: true,
    adjudicationRerunsIntegrityReducer: true
  }),
  claims: Object.freeze({
    compactCompetitivePhraseAllowed: false,
    compactCompetitivePhraseDisabledReason:
      "DS_SELECTED_CONFIGURATION_NEVER_BEAT_EPOCH_ZERO" as const
  }),
  externalSeed: Object.freeze({
    domain: S2S_EXTERNAL_SEED_DOMAIN,
    componentCount: 5,
    separator: "NUL" as const,
    separatorCount: 4,
    roundEncoding: "UNSIGNED_U64_BIG_ENDIAN" as const,
    materialByteLength: 139,
    digest: "SHA256" as const
  }),
  numericBoundary: Object.freeze({
    confirmRequestSchemaVersion:
      "hswm-swm0w-s2s-numeric-confirm-request/v1" as const,
    candidateSchemaVersion: "hswm-swm0w-s2s-numeric-candidate/v1" as const,
    adjudicationSchemaVersion:
      "hswm-swm0w-s2s-numeric-adjudication/v1" as const,
    candidateLabel: "NUMERIC_REPLAY_VALIDATED_CANDIDATE_ONLY" as const,
    typescriptNeverReserializesNumericFiles: true
  }),
  operationalVoidReasons: Object.freeze([
    "REGISTER_JOB_DID_NOT_COMPLETE_SUCCESSFULLY",
    "CONFIRM_JOB_DID_NOT_COMPLETE_SUCCESSFULLY",
    "CANDIDATE_ARTIFACT_UNAVAILABLE",
    "ADJUDICATION_INTEGRITY_FAILURE",
    "ADJUDICATION_ARTIFACT_UNAVAILABLE"
  ] as const),
  numericContinuityPaths: S2S_NUMERIC_CONTINUITY_PATHS
})

const Sha256TextSchema = Schema.String.pipe(
  Schema.pattern(/^[0-9a-f]{64}$/),
  Schema.brand("S2SSha256")
)

const GitCommitShaSchema = Schema.String.pipe(
  Schema.pattern(/^[0-9a-f]{40}$/),
  Schema.brand("S2SGitCommitSha")
)

const SafeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(0, Number.MAX_SAFE_INTEGER)
)

const PositiveSafeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(1, Number.MAX_SAFE_INTEGER)
)

const ByteCountSchema = SafeIntegerSchema.pipe(Schema.brand("S2SByteCount"))
const SecondsSchema = SafeIntegerSchema.pipe(Schema.brand("S2SSeconds"))
const NanosecondsSchema = SafeIntegerSchema.pipe(
  Schema.brand("S2SNanoseconds")
)
const UnixSecondsSchema = SafeIntegerSchema.pipe(
  Schema.brand("S2SUnixSeconds")
)
const WorkflowRunIdSchema = PositiveSafeIntegerSchema.pipe(
  Schema.brand("S2SWorkflowRunId")
)
const ArtifactIdSchema = PositiveSafeIntegerSchema.pipe(
  Schema.brand("S2SArtifactId")
)
const WorkflowJobIdSchema = PositiveSafeIntegerSchema.pipe(
  Schema.brand("S2SWorkflowJobId")
)
const BeaconRoundSchema = PositiveSafeIntegerSchema.pipe(
  Schema.brand("S2SBeaconRound")
)
const GitHubArtifactNameSchema = Schema.String.pipe(
  Schema.pattern(/^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$/),
  Schema.brand("S2SGitHubArtifactName")
)

export type S2SSha256 = Schema.Schema.Type<typeof Sha256TextSchema>
export type S2SGitCommitSha = Schema.Schema.Type<typeof GitCommitShaSchema>
export type S2SByteCount = Schema.Schema.Type<typeof ByteCountSchema>
export type S2SSeconds = Schema.Schema.Type<typeof SecondsSchema>
export type S2SNanoseconds = Schema.Schema.Type<typeof NanosecondsSchema>
export type S2SUnixSeconds = Schema.Schema.Type<typeof UnixSecondsSchema>
export type S2SWorkflowRunId = Schema.Schema.Type<typeof WorkflowRunIdSchema>
export type S2SArtifactId = Schema.Schema.Type<typeof ArtifactIdSchema>
export type S2SWorkflowJobId = Schema.Schema.Type<typeof WorkflowJobIdSchema>
export type S2SBeaconRound = Schema.Schema.Type<typeof BeaconRoundSchema>

export const S2SSha256Schema = Sha256TextSchema
export const S2SGitCommitShaSchema = GitCommitShaSchema
export const S2SByteCountSchema = ByteCountSchema
export const S2SSecondsSchema = SecondsSchema
export const S2SNanosecondsSchema = NanosecondsSchema

const LifecycleBindingSchema = Schema.Struct({
  experimentId: Schema.Literal(S2S_CONFIRMATORY_EXPERIMENT_ID),
  sourceCommitA: GitCommitShaSchema,
  registrationCommitB: GitCommitShaSchema,
  workflowRunId: WorkflowRunIdSchema,
  workflowRunAttempt: Schema.Literal(1),
  workflowHeadSha: GitCommitShaSchema,
  workflowSha256: Sha256TextSchema,
  preregistrationSha256: Sha256TextSchema,
  resourcePolicySha256: Schema.Literal(
    S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256
  ),
  protocolConfigSha256: Schema.Literal(S2S_PROTOCOL_CONFIG_RECEIPT_SHA256),
  predecessorControlReceiptSha256: Sha256TextSchema
})

export type S2SLifecycleBinding = Schema.Schema.Type<
  typeof LifecycleBindingSchema
>

const AttemptEvidenceSchema = Schema.Struct({
  workflowRunAttempt: Schema.Literal(1),
  resume: Schema.Literal(false),
  checkpointResume: Schema.Literal(false),
  rerun: Schema.Literal(false),
  reroll: Schema.Literal(false),
  cellRetry: Schema.Literal(false),
  taskRetry: Schema.Literal(false),
  taskSkip: Schema.Literal(false),
  partialCandidate: Schema.Literal(false)
})

export type S2SAttemptEvidence = Schema.Schema.Type<
  typeof AttemptEvidenceSchema
>

const ArtifactEvidenceSchema = Schema.Struct({
  artifactName: GitHubArtifactNameSchema,
  artifactId: ArtifactIdSchema,
  artifactCount: PositiveSafeIntegerSchema,
  archiveSizeBytes: ByteCountSchema,
  largestMemberSizeBytes: ByteCountSchema,
  compressionLevel: SafeIntegerSchema,
  retentionDays: PositiveSafeIntegerSchema,
  overwrite: Schema.Boolean,
  apiDigestSha256: Sha256TextSchema,
  downloadedArchiveSha256: Sha256TextSchema
})

export type S2SArtifactEvidence = Schema.Schema.Type<
  typeof ArtifactEvidenceSchema
>

const RssEvidenceSchema = Schema.Struct({
  api: Schema.Literal("getrusage"),
  subject: Schema.Literal("RUSAGE_SELF"),
  unit: Schema.Literal("KiB"),
  peakRssKiB: PositiveSafeIntegerSchema,
  oomObserved: Schema.Literal(false)
})

export type S2SRssEvidence = Schema.Schema.Type<typeof RssEvidenceSchema>

const ArmOrderSchema = Schema.Tuple(
  Schema.Literal("T16"),
  Schema.Literal("P_CAP18"),
  Schema.Literal("DS870")
)

const BeginRegistrationSchema = Schema.Struct({
  schemaVersion: Schema.Literal(S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION),
  _tag: Schema.Literal("BeginRegistration"),
  binding: LifecycleBindingSchema,
  adoptionReceiptSha256: Sha256TextSchema,
  workflowRunId: WorkflowRunIdSchema,
  registrationJobId: WorkflowJobIdSchema,
  workflowRunAttempt: Schema.Literal(1),
  workflowHeadSha: GitCommitShaSchema,
  workflowCreatedAtUnixSeconds: UnixSecondsSchema,
  registrationJobStartedAtUnixSeconds: UnixSecondsSchema,
  sourceCommitSha: GitCommitShaSchema,
  preregistrationCommitSha: GitCommitShaSchema,
  beaconId: Schema.Literal("quicknet"),
  beaconChainHashHex: Sha256TextSchema,
  futureBeaconRound: BeaconRoundSchema,
  futureRoundCommitmentSelfHashSha256: Sha256TextSchema,
  declaredPulseLeadSeconds: SecondsSchema
})

const VerifyRegistrationSchema = Schema.Struct({
  schemaVersion: Schema.Literal(S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION),
  _tag: Schema.Literal("VerifyRegistration"),
  binding: LifecycleBindingSchema,
  workflowRunId: WorkflowRunIdSchema,
  registrationJobId: WorkflowJobIdSchema,
  workflowRunAttempt: Schema.Literal(1),
  workflowHeadSha: GitCommitShaSchema,
  registrationJobCompletedAtUnixSeconds: UnixSecondsSchema,
  sourceIsAncestorOfPreregistration: Schema.Literal(true),
  preregistrationIsDirectChildOfSource: Schema.Literal(true),
  numericContinuityManifestSha256AtSource: Sha256TextSchema,
  numericContinuityManifestSha256AtPreregistration: Sha256TextSchema,
  numericContinuityPathsByteEqual: Schema.Literal(true),
  jobElapsedSeconds: SecondsSchema,
  artifact: ArtifactEvidenceSchema
})

const BeginConfirmSchema = Schema.Struct({
  schemaVersion: Schema.Literal(S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION),
  _tag: Schema.Literal("BeginConfirm"),
  binding: LifecycleBindingSchema,
  workflowRunId: WorkflowRunIdSchema,
  confirmJobId: WorkflowJobIdSchema,
  workflowRunAttempt: Schema.Literal(1),
  workflowHeadSha: GitCommitShaSchema,
  confirmJobStartedAtUnixSeconds: UnixSecondsSchema,
  attempt: AttemptEvidenceSchema
})

const AcceptVerifiedPulseSchema = Schema.Struct({
  schemaVersion: Schema.Literal(S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION),
  _tag: Schema.Literal("AcceptVerifiedPulse"),
  binding: LifecycleBindingSchema,
  workflowRunId: WorkflowRunIdSchema,
  confirmJobId: WorkflowJobIdSchema,
  beaconId: Schema.Literal("quicknet"),
  beaconChainHashHex: Sha256TextSchema,
  beaconRound: BeaconRoundSchema,
  roundTimeUnixSeconds: UnixSecondsSchema,
  verifiedAtUnixSeconds: UnixSecondsSchema,
  pulseWaitElapsedSeconds: SecondsSchema,
  verifiedRandomnessHex: Sha256TextSchema,
  externalSeedHex: Sha256TextSchema,
  verifierReceiptSha256: Sha256TextSchema,
  verificationAccepted: Schema.Literal(true)
})

const BeginNumericConfirmSchema = Schema.Struct({
  schemaVersion: Schema.Literal(S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION),
  _tag: Schema.Literal("BeginNumericConfirm"),
  binding: LifecycleBindingSchema,
  workflowRunId: WorkflowRunIdSchema,
  confirmJobId: WorkflowJobIdSchema
})

const RecordCandidateProducedSchema = Schema.Struct({
  schemaVersion: Schema.Literal(S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION),
  _tag: Schema.Literal("RecordCandidateProduced"),
  binding: LifecycleBindingSchema,
  adoptionReceiptSha256: Sha256TextSchema,
  workflowRunId: WorkflowRunIdSchema,
  confirmJobId: WorkflowJobIdSchema,
  attempt: AttemptEvidenceSchema,
  externalSeedHex: Sha256TextSchema,
  taskCount: PositiveSafeIntegerSchema,
  armOrder: ArmOrderSchema,
  cellCount: PositiveSafeIntegerSchema,
  optimizerExecutionsPerCell: PositiveSafeIntegerSchema,
  optimizerExecutionCount: PositiveSafeIntegerSchema,
  completedFitReplayCellCount: SafeIntegerSchema,
  testWorldsPerTask: PositiveSafeIntegerSchema,
  scoreVariantCount: PositiveSafeIntegerSchema,
  domainWorldCount: PositiveSafeIntegerSchema,
  allFitReplayCompletedBeforeAnyTestMaterialization: Schema.Literal(true),
  postSeedWorkElapsedNanoseconds: NanosecondsSchema,
  commandElapsedSeconds: SecondsSchema,
  jobElapsedSeconds: SecondsSchema,
  rss: RssEvidenceSchema,
  numericCandidateBytesSha256: Sha256TextSchema,
  numericConfirmRequestSha256: Sha256TextSchema,
  numericCandidateLabel: Schema.Literal(
    "NUMERIC_REPLAY_VALIDATED_CANDIDATE_ONLY"
  ),
  candidateOnly: Schema.Literal(true)
})

const VerifyCandidateArtifactSchema = Schema.Struct({
  schemaVersion: Schema.Literal(S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION),
  _tag: Schema.Literal("VerifyCandidateArtifact"),
  binding: LifecycleBindingSchema,
  workflowRunId: WorkflowRunIdSchema,
  confirmJobId: WorkflowJobIdSchema,
  confirmJobCompletedAtUnixSeconds: UnixSecondsSchema,
  numericCandidateBytesSha256: Sha256TextSchema,
  artifact: ArtifactEvidenceSchema,
  archiveMembers: Schema.Tuple(
    Schema.Literal("control_receipt.json"),
    Schema.Literal("numeric_candidate.json")
  ),
  readbackContainsCanonicalCandidate: Schema.Literal(true)
})

const BeginAdjudicationSchema = Schema.Struct({
  schemaVersion: Schema.Literal(S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION),
  _tag: Schema.Literal("BeginAdjudication"),
  binding: LifecycleBindingSchema,
  workflowRunId: WorkflowRunIdSchema,
  adjudicationJobId: WorkflowJobIdSchema,
  workflowRunAttempt: Schema.Literal(1),
  workflowHeadSha: GitCommitShaSchema,
  adjudicationJobStartedAtUnixSeconds: UnixSecondsSchema,
  attempt: AttemptEvidenceSchema,
  candidateArtifactId: ArtifactIdSchema,
  expectedCandidateArchiveSha256: Sha256TextSchema,
  requeriedApiDigestSha256: Sha256TextSchema,
  redownloadedCandidateArchiveSha256: Sha256TextSchema
})

const RecordAdjudicationProducedSchema = Schema.Struct({
  schemaVersion: Schema.Literal(S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION),
  _tag: Schema.Literal("RecordAdjudicationProduced"),
  binding: LifecycleBindingSchema,
  adoptionReceiptSha256: Sha256TextSchema,
  workflowRunId: WorkflowRunIdSchema,
  adjudicationJobId: WorkflowJobIdSchema,
  attempt: AttemptEvidenceSchema,
  candidateArtifactId: ArtifactIdSchema,
  externalSeedHex: Sha256TextSchema,
  taskCount: PositiveSafeIntegerSchema,
  testWorldsPerTask: PositiveSafeIntegerSchema,
  scoreVariantCount: PositiveSafeIntegerSchema,
  domainWorldCount: PositiveSafeIntegerSchema,
  optimizerExecutionCount: SafeIntegerSchema,
  blsVerificationRerun: Schema.Literal(true),
  taskBatchRerun: Schema.Literal(true),
  testEvaluationRerun: Schema.Literal(true),
  integrityReducerRerun: Schema.Literal(true),
  compactCompetitivePhraseAllowed: Schema.Literal(false),
  numericCandidateDocumentSha256: Sha256TextSchema,
  numericCandidateReceiptSha256: Sha256TextSchema,
  numericConfirmRequestSha256: Sha256TextSchema,
  numericAdjudicationReceiptSha256: Sha256TextSchema,
  numericCandidateOutcome: Schema.Literal(
    "CANDIDATE_PASS_AWAITING_BUNDLE",
    "CANDIDATE_KILL_AWAITING_BUNDLE",
    "CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE"
  ),
  commandElapsedSeconds: SecondsSchema,
  jobElapsedSeconds: SecondsSchema,
  rss: RssEvidenceSchema,
  numericAdjudicationBytesSha256: Sha256TextSchema,
  candidateOnly: Schema.Literal(true)
})

const VerifyEvidenceArtifactSchema = Schema.Struct({
  schemaVersion: Schema.Literal(S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION),
  _tag: Schema.Literal("VerifyEvidenceArtifact"),
  binding: LifecycleBindingSchema,
  workflowRunId: WorkflowRunIdSchema,
  adjudicationJobId: WorkflowJobIdSchema,
  adjudicationJobCompletedAtUnixSeconds: UnixSecondsSchema,
  numericAdjudicationBytesSha256: Sha256TextSchema,
  artifact: ArtifactEvidenceSchema,
  readbackContainsCanonicalAdjudication: Schema.Literal(true),
  compactCompetitivePhraseAllowed: Schema.Literal(false)
})

export const S2SOperationalVoidReasonSchema = Schema.Literal(
  "REGISTER_JOB_DID_NOT_COMPLETE_SUCCESSFULLY",
  "CONFIRM_JOB_DID_NOT_COMPLETE_SUCCESSFULLY",
  "CANDIDATE_ARTIFACT_UNAVAILABLE",
  "ADJUDICATION_INTEGRITY_FAILURE",
  "ADJUDICATION_ARTIFACT_UNAVAILABLE"
)

export type S2SOperationalVoidReason = Schema.Schema.Type<
  typeof S2SOperationalVoidReasonSchema
>

const RecordOperationalVoidSchema = Schema.Struct({
  schemaVersion: Schema.Literal(S2S_CONFIRMATORY_EVENT_SCHEMA_VERSION),
  _tag: Schema.Literal("RecordOperationalVoid"),
  binding: LifecycleBindingSchema,
  workflowRunId: WorkflowRunIdSchema,
  workflowJobId: WorkflowJobIdSchema,
  workflowRunAttempt: Schema.Literal(1),
  reason: S2SOperationalVoidReasonSchema,
  evidenceSha256: Sha256TextSchema
})

export const S2SConfirmatoryEventSchema = Schema.Union(
  BeginRegistrationSchema,
  VerifyRegistrationSchema,
  BeginConfirmSchema,
  AcceptVerifiedPulseSchema,
  BeginNumericConfirmSchema,
  RecordCandidateProducedSchema,
  VerifyCandidateArtifactSchema,
  BeginAdjudicationSchema,
  RecordAdjudicationProducedSchema,
  VerifyEvidenceArtifactSchema,
  RecordOperationalVoidSchema
)

export type S2SConfirmatoryEvent = Schema.Schema.Type<
  typeof S2SConfirmatoryEventSchema
>

export const decodeS2SConfirmatoryEvent = Schema.decodeUnknown(
  S2SConfirmatoryEventSchema,
  { onExcessProperty: "error" }
)

type BeginRegistration = Schema.Schema.Type<typeof BeginRegistrationSchema>
type VerifyRegistration = Schema.Schema.Type<typeof VerifyRegistrationSchema>
type BeginConfirm = Schema.Schema.Type<typeof BeginConfirmSchema>
type AcceptVerifiedPulse = Schema.Schema.Type<typeof AcceptVerifiedPulseSchema>
type RecordCandidateProduced = Schema.Schema.Type<
  typeof RecordCandidateProducedSchema
>
type VerifyCandidateArtifact = Schema.Schema.Type<
  typeof VerifyCandidateArtifactSchema
>
type BeginAdjudication = Schema.Schema.Type<typeof BeginAdjudicationSchema>
type RecordAdjudicationProduced = Schema.Schema.Type<
  typeof RecordAdjudicationProducedSchema
>
type VerifyEvidenceArtifact = Schema.Schema.Type<
  typeof VerifyEvidenceArtifactSchema
>
type RecordOperationalVoid = Schema.Schema.Type<
  typeof RecordOperationalVoidSchema
>

export interface S2SNumericCandidatePlan {
  readonly schemaVersion: "hswm-swm0w-s2s-numeric-confirm-plan/v1"
  readonly protocolConfigReceiptSha256: typeof S2S_PROTOCOL_CONFIG_RECEIPT_SHA256
  readonly externalSeedHex: S2SSha256
  readonly taskCount: 20
  readonly armOrder: readonly ["T16", "P_CAP18", "DS870"]
  readonly cellCount: 60
  readonly optimizerExecutionsPerCell: 2
  readonly optimizerExecutionCount: 120
  readonly testWorldsPerTask: 6_250
  readonly scoreVariantCount: 8
  readonly domainWorldCount: 15_625
  readonly allFitReplayBeforeAnyTestMaterialization: true
}

export interface S2SNumericAdjudicationPlan {
  readonly schemaVersion: "hswm-swm0w-s2s-numeric-adjudication-plan/v1"
  readonly protocolConfigReceiptSha256: typeof S2S_PROTOCOL_CONFIG_RECEIPT_SHA256
  readonly externalSeedHex: S2SSha256
  readonly numericCandidateBytesSha256: S2SSha256
  readonly candidateArtifactId: S2SArtifactId
  readonly taskCount: 20
  readonly testWorldsPerTask: 6_250
  readonly scoreVariantCount: 8
  readonly domainWorldCount: 15_625
  readonly optimizerExecutionCount: 0
  readonly rerunTaskBatch: true
  readonly rerunTestEvaluation: true
  readonly rerunIntegrityReducer: true
  readonly compactCompetitivePhraseAllowed: false
}

interface PreparedState {
  readonly _tag: "Prepared"
  readonly experimentId: typeof S2S_CONFIRMATORY_EXPERIMENT_ID
  readonly policySchemaVersion: typeof S2S_CONFIRMATORY_POLICY_SCHEMA_VERSION
  readonly adoptionReceiptSha256: typeof S2S_PILOT_ADOPTION_RECEIPT_SHA256
  readonly resourcePolicySha256: typeof S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256
  readonly protocolConfigSha256: typeof S2S_PROTOCOL_CONFIG_RECEIPT_SHA256
  readonly latestControlReceiptSha256: S2SSha256
  readonly compactCompetitivePhraseAllowed: false
}

interface RegisteringState extends Omit<PreparedState, "_tag"> {
  readonly _tag: "Registering"
  readonly registration: BeginRegistration
}

interface RegistrationVerifiedState extends Omit<RegisteringState, "_tag"> {
  readonly _tag: "RegistrationVerified"
  readonly registrationEvidence: VerifyRegistration
}

interface ConfirmWaitingState
  extends Omit<RegistrationVerifiedState, "_tag"> {
  readonly _tag: "ConfirmWaiting"
  readonly confirm: BeginConfirm
}

interface PulseEligibleState extends Omit<ConfirmWaitingState, "_tag"> {
  readonly _tag: "PulseEligible"
  readonly pulse: AcceptVerifiedPulse
}

interface ConfirmRunningState extends Omit<PulseEligibleState, "_tag"> {
  readonly _tag: "ConfirmRunning"
  readonly numericPlan: S2SNumericCandidatePlan
}

interface CandidateProducedState extends Omit<ConfirmRunningState, "_tag"> {
  readonly _tag: "CandidateProduced"
  readonly candidate: RecordCandidateProduced
}

interface CandidateArtifactVerifiedState
  extends Omit<CandidateProducedState, "_tag"> {
  readonly _tag: "CandidateArtifactVerified"
  readonly candidateArtifact: VerifyCandidateArtifact
}

interface AdjudicatingState
  extends Omit<CandidateArtifactVerifiedState, "_tag" | "numericPlan"> {
  readonly _tag: "Adjudicating"
  readonly adjudication: BeginAdjudication
  readonly numericPlan: S2SNumericAdjudicationPlan
}

interface AdjudicationProducedState
  extends Omit<AdjudicatingState, "_tag"> {
  readonly _tag: "AdjudicationProduced"
  readonly adjudicationCandidate: RecordAdjudicationProduced
}

interface EvidenceArtifactVerifiedState
  extends Omit<AdjudicationProducedState, "_tag"> {
  readonly _tag: "EvidenceArtifactVerified"
  readonly evidenceArtifact: VerifyEvidenceArtifact
  readonly verdict: "PASS" | "KILL" | "INCONCLUSIVE"
}

interface VoidedState {
  readonly _tag: "Voided"
  readonly experimentId: typeof S2S_CONFIRMATORY_EXPERIMENT_ID
  readonly policySchemaVersion: typeof S2S_CONFIRMATORY_POLICY_SCHEMA_VERSION
  readonly adoptionReceiptSha256: typeof S2S_PILOT_ADOPTION_RECEIPT_SHA256
  readonly resourcePolicySha256: typeof S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256
  readonly protocolConfigSha256: typeof S2S_PROTOCOL_CONFIG_RECEIPT_SHA256
  readonly latestControlReceiptSha256: S2SSha256
  readonly compactCompetitivePhraseAllowed: false
  readonly binding: S2SLifecycleBinding
  readonly failedPhase: Exclude<S2SConfirmatoryPhase, "Voided">
  readonly workflowRunId: S2SWorkflowRunId
  readonly workflowRunAttempt: 1
  readonly reason: S2SOperationalVoidReason
  readonly evidenceSha256: S2SSha256
  readonly retryAllowed: false
  readonly candidateConsumable: false
}

export type S2SConfirmatoryState =
  | PreparedState
  | RegisteringState
  | RegistrationVerifiedState
  | ConfirmWaitingState
  | PulseEligibleState
  | ConfirmRunningState
  | CandidateProducedState
  | CandidateArtifactVerifiedState
  | AdjudicatingState
  | AdjudicationProducedState
  | EvidenceArtifactVerifiedState
  | VoidedState

export type S2SConfirmatoryPhase = S2SConfirmatoryState["_tag"]

export class S2SInvalidTransition extends Data.TaggedError(
  "S2SInvalidTransition"
)<{
  readonly phase: S2SConfirmatoryPhase
  readonly event: S2SConfirmatoryEvent["_tag"]
}> {}

export class S2SOperationalPolicyViolation extends Data.TaggedError(
  "S2SOperationalPolicyViolation"
)<{
  readonly reason:
    | "ADOPTION_RECEIPT_MISMATCH"
    | "ARCHIVE_POLICY_MISMATCH"
    | "ARTIFACT_READBACK_MISMATCH"
    | "ATTEMPT_POLICY_MISMATCH"
    | "CANDIDATE_BINDING_MISMATCH"
    | "CONFIRM_ORDERING_VIOLATION"
    | "CONTROL_RECEIPT_CHAIN_MISMATCH"
    | "CONTROL_RECEIPT_NONCANONICAL"
    | "DEADLINE_EXCEEDED"
    | "OPTIONAL_CLAIM_DISABLED"
    | "PROTOCOL_CONTINUITY_UNPROVEN"
    | "PULSE_BINDING_MISMATCH"
    | "RESOURCE_LIMIT_EXCEEDED"
    | "RUN_BINDING_MISMATCH"
    | "VOID_REASON_MISMATCH"
    | "WORKLOAD_MISMATCH"
}> {}

export type S2SConfirmatoryTransitionError =
  | S2SInvalidTransition
  | S2SOperationalPolicyViolation

export const initialS2SConfirmatoryState = (): S2SConfirmatoryState =>
  Object.freeze({
    _tag: "Prepared",
    experimentId: S2S_CONFIRMATORY_EXPERIMENT_ID,
    policySchemaVersion: S2S_CONFIRMATORY_POLICY_SCHEMA_VERSION,
    adoptionReceiptSha256: S2S_PILOT_ADOPTION_RECEIPT_SHA256,
    resourcePolicySha256: S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256,
    protocolConfigSha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
    latestControlReceiptSha256: S2SSha256Schema.make(
      S2S_PILOT_ADOPTION_RECEIPT_SHA256
    ),
    compactCompetitivePhraseAllowed: false
  })

const policyViolation = (
  reason: S2SOperationalPolicyViolation["reason"]
): Either.Either<never, S2SOperationalPolicyViolation> =>
  Either.left(new S2SOperationalPolicyViolation({ reason }))

const invalidTransition = (
  state: S2SConfirmatoryState,
  event: S2SConfirmatoryEvent
): Either.Either<never, S2SInvalidTransition> =>
  Either.left(
    new S2SInvalidTransition({ phase: state._tag, event: event._tag })
  )

const sameAttemptPolicy = (attempt: S2SAttemptEvidence): boolean =>
  attempt.workflowRunAttempt === S2S_CONFIRMATORY_POLICY.attempt.workflowRunAttempt &&
  attempt.resume === S2S_CONFIRMATORY_POLICY.attempt.resume &&
  attempt.checkpointResume === S2S_CONFIRMATORY_POLICY.attempt.checkpointResume &&
  attempt.rerun === S2S_CONFIRMATORY_POLICY.attempt.rerun &&
  attempt.reroll === S2S_CONFIRMATORY_POLICY.attempt.reroll &&
  attempt.cellRetry === S2S_CONFIRMATORY_POLICY.attempt.cellRetry &&
  attempt.taskRetry === S2S_CONFIRMATORY_POLICY.attempt.taskRetry &&
  attempt.taskSkip === S2S_CONFIRMATORY_POLICY.attempt.taskSkip &&
  attempt.partialCandidate === S2S_CONFIRMATORY_POLICY.attempt.partialCandidate

const artifactMatchesPolicy = (
  artifact: S2SArtifactEvidence,
  archiveMaximumBytes: number,
  memberMaximumBytes: number
): boolean =>
  artifact.artifactCount === S2S_CONFIRMATORY_POLICY.archive.artifactCountPerJob &&
  artifact.archiveSizeBytes <= archiveMaximumBytes &&
  artifact.largestMemberSizeBytes <= memberMaximumBytes &&
  artifact.largestMemberSizeBytes <= artifact.archiveSizeBytes &&
  artifact.compressionLevel === S2S_CONFIRMATORY_POLICY.archive.compressionLevel &&
  artifact.retentionDays === S2S_CONFIRMATORY_POLICY.archive.retentionDays &&
  artifact.overwrite === S2S_CONFIRMATORY_POLICY.archive.overwrite

const artifactReadbackMatches = (artifact: S2SArtifactEvidence): boolean =>
  artifact.apiDigestSha256 === artifact.downloadedArchiveSha256

const makeNumericCandidatePlan = (
  pulse: AcceptVerifiedPulse
): S2SNumericCandidatePlan =>
  Object.freeze({
    schemaVersion: "hswm-swm0w-s2s-numeric-confirm-plan/v1",
    protocolConfigReceiptSha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
    externalSeedHex: pulse.externalSeedHex,
    taskCount: 20,
    armOrder: Object.freeze(["T16", "P_CAP18", "DS870"] as const),
    cellCount: 60,
    optimizerExecutionsPerCell: 2,
    optimizerExecutionCount: 120,
    testWorldsPerTask: 6_250,
    scoreVariantCount: 8,
    domainWorldCount: 15_625,
    allFitReplayBeforeAnyTestMaterialization: true
  })

const makeNumericAdjudicationPlan = (
  state: CandidateArtifactVerifiedState
): S2SNumericAdjudicationPlan =>
  Object.freeze({
    schemaVersion: "hswm-swm0w-s2s-numeric-adjudication-plan/v1",
    protocolConfigReceiptSha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
    externalSeedHex: state.pulse.externalSeedHex,
    numericCandidateBytesSha256: state.candidate.numericCandidateBytesSha256,
    candidateArtifactId: state.candidateArtifact.artifact.artifactId,
    taskCount: 20,
    testWorldsPerTask: 6_250,
    scoreVariantCount: 8,
    domainWorldCount: 15_625,
    optimizerExecutionCount: 0,
    rerunTaskBatch: true,
    rerunTestEvaluation: true,
    rerunIntegrityReducer: true,
    compactCompetitivePhraseAllowed: false
  })

const sameLifecycleIdentity = (
  left: S2SLifecycleBinding,
  right: S2SLifecycleBinding
): boolean =>
  left.experimentId === right.experimentId &&
  left.sourceCommitA === right.sourceCommitA &&
  left.registrationCommitB === right.registrationCommitB &&
  left.workflowRunId === right.workflowRunId &&
  left.workflowRunAttempt === right.workflowRunAttempt &&
  left.workflowHeadSha === right.workflowHeadSha &&
  left.workflowSha256 === right.workflowSha256 &&
  left.preregistrationSha256 === right.preregistrationSha256 &&
  left.resourcePolicySha256 === right.resourcePolicySha256 &&
  left.protocolConfigSha256 === right.protocolConfigSha256

const validateLifecycleBinding = (
  state: S2SConfirmatoryState,
  event: S2SConfirmatoryEvent
): Either.Either<S2SSha256, S2SOperationalPolicyViolation> => {
  const binding = event.binding
  if (
    binding.experimentId !== S2S_CONFIRMATORY_EXPERIMENT_ID ||
    binding.workflowRunAttempt !== 1 ||
    binding.workflowHeadSha !== binding.registrationCommitB ||
    binding.sourceCommitA === binding.registrationCommitB ||
    binding.resourcePolicySha256 !==
      S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256 ||
    binding.protocolConfigSha256 !== S2S_PROTOCOL_CONFIG_RECEIPT_SHA256
  ) {
    return policyViolation("RUN_BINDING_MISMATCH")
  }
  if (
    binding.predecessorControlReceiptSha256 !==
    state.latestControlReceiptSha256
  ) {
    return policyViolation("CONTROL_RECEIPT_CHAIN_MISMATCH")
  }
  if (
    state._tag !== "Prepared" &&
    state._tag !== "Voided" &&
    !sameLifecycleIdentity(state.registration.binding, binding)
  ) {
    return policyViolation("RUN_BINDING_MISMATCH")
  }
  const receipt = canonicalS2SControlSha256(event)
  if (Either.isLeft(receipt) || receipt.right === state.latestControlReceiptSha256) {
    return policyViolation("CONTROL_RECEIPT_NONCANONICAL")
  }
  return Either.right(S2SSha256Schema.make(receipt.right))
}

const validateBeginRegistration = (
  event: BeginRegistration
): Either.Either<void, S2SOperationalPolicyViolation> => {
  if (event.adoptionReceiptSha256 !== S2S_PILOT_ADOPTION_RECEIPT_SHA256) {
    return policyViolation("ADOPTION_RECEIPT_MISMATCH")
  }
  if (
    event.workflowRunAttempt !== 1 ||
    event.workflowRunId !== event.binding.workflowRunId ||
    event.workflowHeadSha !== event.binding.workflowHeadSha ||
    event.sourceCommitSha !== event.binding.sourceCommitA ||
    event.preregistrationCommitSha !== event.binding.registrationCommitB ||
    event.workflowHeadSha !== event.preregistrationCommitSha ||
    event.sourceCommitSha === event.preregistrationCommitSha ||
    event.registrationJobStartedAtUnixSeconds <
      event.workflowCreatedAtUnixSeconds
  ) {
    return policyViolation("RUN_BINDING_MISMATCH")
  }
  if (
    event.declaredPulseLeadSeconds >
    S2S_CONFIRMATORY_POLICY.deadlines.maximumDeclaredPulseLeadSeconds
  ) {
    return policyViolation("DEADLINE_EXCEEDED")
  }
  return Either.right(undefined)
}

const validateRegistrationEvidence = (
  state: RegisteringState,
  event: VerifyRegistration
): Either.Either<void, S2SOperationalPolicyViolation> => {
  if (
    event.workflowRunId !== state.registration.workflowRunId ||
    event.registrationJobId !== state.registration.registrationJobId ||
    event.workflowRunAttempt !== state.registration.workflowRunAttempt ||
    event.workflowHeadSha !== state.registration.workflowHeadSha ||
    event.registrationJobCompletedAtUnixSeconds <
      state.registration.registrationJobStartedAtUnixSeconds
  ) {
    return policyViolation("RUN_BINDING_MISMATCH")
  }
  if (
    !event.sourceIsAncestorOfPreregistration ||
    !event.preregistrationIsDirectChildOfSource ||
    !event.numericContinuityPathsByteEqual ||
    event.numericContinuityManifestSha256AtSource !==
      event.numericContinuityManifestSha256AtPreregistration
  ) {
    return policyViolation("PROTOCOL_CONTINUITY_UNPROVEN")
  }
  if (
    event.jobElapsedSeconds >
      S2S_CONFIRMATORY_POLICY.deadlines.registerJobTimeoutSeconds ||
    event.jobElapsedSeconds !==
      event.registrationJobCompletedAtUnixSeconds -
        state.registration.registrationJobStartedAtUnixSeconds
  ) {
    return policyViolation("DEADLINE_EXCEEDED")
  }
  if (
    !artifactMatchesPolicy(
      event.artifact,
      S2S_CONFIRMATORY_POLICY.archive.registrationArchiveMaximumBytes,
      S2S_CONFIRMATORY_POLICY.archive.registrationArchiveMaximumBytes
    )
  ) {
    return policyViolation("ARCHIVE_POLICY_MISMATCH")
  }
  if (!artifactReadbackMatches(event.artifact)) {
    return policyViolation("ARTIFACT_READBACK_MISMATCH")
  }
  return Either.right(undefined)
}

const validateBeginConfirm = (
  state: RegistrationVerifiedState,
  event: BeginConfirm
): Either.Either<void, S2SOperationalPolicyViolation> => {
  if (
    event.workflowHeadSha !== state.registration.workflowHeadSha ||
    event.workflowRunId !== state.registration.workflowRunId ||
    event.confirmJobId === state.registration.registrationJobId ||
    event.confirmJobStartedAtUnixSeconds <
      state.registrationEvidence.registrationJobCompletedAtUnixSeconds
  ) {
    return policyViolation("RUN_BINDING_MISMATCH")
  }
  if (!sameAttemptPolicy(event.attempt)) {
    return policyViolation("ATTEMPT_POLICY_MISMATCH")
  }
  return Either.right(undefined)
}

const validatePulse = (
  state: ConfirmWaitingState,
  event: AcceptVerifiedPulse
): Either.Either<void, S2SOperationalPolicyViolation> => {
  if (event.workflowRunId !== state.confirm.workflowRunId) {
    return policyViolation("RUN_BINDING_MISMATCH")
  }
  if (event.confirmJobId !== state.confirm.confirmJobId) {
    return policyViolation("RUN_BINDING_MISMATCH")
  }
  if (
    event.beaconId !== state.registration.beaconId ||
    event.beaconChainHashHex !== state.registration.beaconChainHashHex ||
    event.beaconRound !== state.registration.futureBeaconRound ||
    event.verifiedAtUnixSeconds < event.roundTimeUnixSeconds
  ) {
    return policyViolation("PULSE_BINDING_MISMATCH")
  }
  const derivedSeed = deriveS2SExternalSeed({
    beaconChainHashHex: event.beaconChainHashHex,
    round: event.beaconRound,
    verifiedRandomnessHex: event.verifiedRandomnessHex,
    futureRoundCommitmentSelfHashHex:
      state.registration.futureRoundCommitmentSelfHashSha256
  })
  if (
    Either.isLeft(derivedSeed) ||
    derivedSeed.right.externalSeedHex !== event.externalSeedHex
  ) {
    return policyViolation("PULSE_BINDING_MISMATCH")
  }
  if (
    event.pulseWaitElapsedSeconds >
    S2S_CONFIRMATORY_POLICY.deadlines.confirmWaitBudgetSeconds
  ) {
    return policyViolation("DEADLINE_EXCEEDED")
  }
  return Either.right(undefined)
}

const validateCandidate = (
  state: ConfirmRunningState,
  event: RecordCandidateProduced
): Either.Either<void, S2SOperationalPolicyViolation> => {
  if (
    event.workflowRunId !== state.confirm.workflowRunId ||
    event.confirmJobId !== state.confirm.confirmJobId ||
    event.externalSeedHex !== state.pulse.externalSeedHex
  ) {
    return policyViolation("RUN_BINDING_MISMATCH")
  }
  if (event.adoptionReceiptSha256 !== S2S_PILOT_ADOPTION_RECEIPT_SHA256) {
    return policyViolation("ADOPTION_RECEIPT_MISMATCH")
  }
  if (!sameAttemptPolicy(event.attempt)) {
    return policyViolation("ATTEMPT_POLICY_MISMATCH")
  }
  const workload = S2S_CONFIRMATORY_POLICY.workload
  if (
    event.taskCount !== workload.taskCount ||
    event.armOrder[0] !== workload.armOrder[0] ||
    event.armOrder[1] !== workload.armOrder[1] ||
    event.armOrder[2] !== workload.armOrder[2] ||
    event.cellCount !== workload.cellCount ||
    event.optimizerExecutionsPerCell !== workload.optimizerExecutionsPerCell ||
    event.optimizerExecutionCount !== workload.optimizerExecutionCount ||
    event.completedFitReplayCellCount !== workload.cellCount ||
    event.testWorldsPerTask !== workload.testWorldsPerTask ||
    event.scoreVariantCount !== workload.scoreVariantCount ||
    event.domainWorldCount !== workload.domainWorldCount ||
    !event.allFitReplayCompletedBeforeAnyTestMaterialization
  ) {
    return policyViolation("WORKLOAD_MISMATCH")
  }
  if (
    event.postSeedWorkElapsedNanoseconds >
    S2S_CONFIRMATORY_POLICY.resourceBasis.postSeedWorkCapNanoseconds
  ) {
    return policyViolation("RESOURCE_LIMIT_EXCEEDED")
  }
  if (
    event.commandElapsedSeconds >
      S2S_CONFIRMATORY_POLICY.deadlines.confirmCommandTimeoutSeconds ||
    event.jobElapsedSeconds >
      S2S_CONFIRMATORY_POLICY.deadlines.confirmJobTimeoutSeconds ||
    event.commandElapsedSeconds > event.jobElapsedSeconds ||
    state.pulse.pulseWaitElapsedSeconds * 1_000_000_000 +
        event.postSeedWorkElapsedNanoseconds >
      event.commandElapsedSeconds * 1_000_000_000
  ) {
    return policyViolation("DEADLINE_EXCEEDED")
  }
  return Either.right(undefined)
}

const validateCandidateArtifact = (
  state: CandidateProducedState,
  event: VerifyCandidateArtifact
): Either.Either<void, S2SOperationalPolicyViolation> => {
  if (
    event.workflowRunId !== state.confirm.workflowRunId ||
    event.confirmJobId !== state.confirm.confirmJobId ||
    event.numericCandidateBytesSha256 !==
      state.candidate.numericCandidateBytesSha256
  ) {
    return policyViolation("CANDIDATE_BINDING_MISMATCH")
  }
  if (
    !artifactMatchesPolicy(
      event.artifact,
      S2S_CONFIRMATORY_POLICY.archive.candidateArchiveMaximumBytes,
      S2S_CONFIRMATORY_POLICY.archive.candidateMemberMaximumBytes
    )
  ) {
    return policyViolation("ARCHIVE_POLICY_MISMATCH")
  }
  if (!artifactReadbackMatches(event.artifact)) {
    return policyViolation("ARTIFACT_READBACK_MISMATCH")
  }
  if (
    event.archiveMembers[0] !==
      S2S_CONFIRMATORY_POLICY.candidateArchive.exactMembers[0] ||
    event.archiveMembers[1] !==
      S2S_CONFIRMATORY_POLICY.candidateArchive.exactMembers[1] ||
    event.confirmJobCompletedAtUnixSeconds <
      state.confirm.confirmJobStartedAtUnixSeconds ||
    state.candidate.jobElapsedSeconds !==
      event.confirmJobCompletedAtUnixSeconds -
        state.confirm.confirmJobStartedAtUnixSeconds
  ) {
    return policyViolation("CONFIRM_ORDERING_VIOLATION")
  }
  return Either.right(undefined)
}

const validateBeginAdjudication = (
  state: CandidateArtifactVerifiedState,
  event: BeginAdjudication
): Either.Either<void, S2SOperationalPolicyViolation> => {
  const candidateArtifact = state.candidateArtifact.artifact
  if (
    event.workflowHeadSha !== state.registration.workflowHeadSha ||
    event.workflowRunId !== state.registration.workflowRunId ||
    event.adjudicationJobId === state.registration.registrationJobId ||
    event.adjudicationJobId === state.confirm.confirmJobId ||
    event.adjudicationJobStartedAtUnixSeconds <
      state.candidateArtifact.confirmJobCompletedAtUnixSeconds
  ) {
    return policyViolation("RUN_BINDING_MISMATCH")
  }
  if (!sameAttemptPolicy(event.attempt)) {
    return policyViolation("ATTEMPT_POLICY_MISMATCH")
  }
  if (
    event.candidateArtifactId !== candidateArtifact.artifactId ||
    event.expectedCandidateArchiveSha256 !==
      candidateArtifact.downloadedArchiveSha256 ||
    event.requeriedApiDigestSha256 !== candidateArtifact.apiDigestSha256 ||
    event.redownloadedCandidateArchiveSha256 !==
      candidateArtifact.downloadedArchiveSha256
  ) {
    return policyViolation("CANDIDATE_BINDING_MISMATCH")
  }
  return Either.right(undefined)
}

const validateAdjudication = (
  state: AdjudicatingState,
  event: RecordAdjudicationProduced
): Either.Either<void, S2SOperationalPolicyViolation> => {
  if (
    event.workflowRunId !== state.adjudication.workflowRunId ||
    event.adjudicationJobId !== state.adjudication.adjudicationJobId ||
    event.candidateArtifactId !==
      state.candidateArtifact.artifact.artifactId ||
    event.externalSeedHex !== state.pulse.externalSeedHex ||
    event.numericCandidateDocumentSha256 !==
      state.candidate.numericCandidateBytesSha256 ||
    event.numericConfirmRequestSha256 !==
      state.candidate.numericConfirmRequestSha256
  ) {
    return policyViolation("RUN_BINDING_MISMATCH")
  }
  if (event.adoptionReceiptSha256 !== S2S_PILOT_ADOPTION_RECEIPT_SHA256) {
    return policyViolation("ADOPTION_RECEIPT_MISMATCH")
  }
  if (!sameAttemptPolicy(event.attempt)) {
    return policyViolation("ATTEMPT_POLICY_MISMATCH")
  }
  const workload = S2S_CONFIRMATORY_POLICY.workload
  if (
    event.taskCount !== workload.taskCount ||
    event.testWorldsPerTask !== workload.testWorldsPerTask ||
    event.scoreVariantCount !== workload.scoreVariantCount ||
    event.domainWorldCount !== workload.domainWorldCount ||
    event.optimizerExecutionCount !==
      workload.adjudicationOptimizerExecutionCount ||
    !event.blsVerificationRerun ||
    !event.taskBatchRerun ||
    !event.testEvaluationRerun ||
    !event.integrityReducerRerun
  ) {
    return policyViolation("WORKLOAD_MISMATCH")
  }
  if (event.compactCompetitivePhraseAllowed) {
    return policyViolation("OPTIONAL_CLAIM_DISABLED")
  }
  if (
    event.commandElapsedSeconds >
      S2S_CONFIRMATORY_POLICY.deadlines.adjudicationCommandTimeoutSeconds ||
    event.jobElapsedSeconds >
      S2S_CONFIRMATORY_POLICY.deadlines.adjudicationJobTimeoutSeconds ||
    event.commandElapsedSeconds > event.jobElapsedSeconds
  ) {
    return policyViolation("DEADLINE_EXCEEDED")
  }
  return Either.right(undefined)
}

const candidateOutcomeToVerdict = (
  outcome:
    | "CANDIDATE_PASS_AWAITING_BUNDLE"
    | "CANDIDATE_KILL_AWAITING_BUNDLE"
    | "CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE"
): "PASS" | "KILL" | "INCONCLUSIVE" => {
  switch (outcome) {
    case "CANDIDATE_PASS_AWAITING_BUNDLE":
      return "PASS"
    case "CANDIDATE_KILL_AWAITING_BUNDLE":
      return "KILL"
    case "CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE":
      return "INCONCLUSIVE"
  }
}

const validateEvidenceArtifact = (
  state: AdjudicationProducedState,
  event: VerifyEvidenceArtifact
): Either.Either<void, S2SOperationalPolicyViolation> => {
  if (
    event.workflowRunId !== state.adjudication.workflowRunId ||
    event.adjudicationJobId !== state.adjudication.adjudicationJobId ||
    event.numericAdjudicationBytesSha256 !==
      state.adjudicationCandidate.numericAdjudicationBytesSha256
  ) {
    return policyViolation("RUN_BINDING_MISMATCH")
  }
  if (event.compactCompetitivePhraseAllowed) {
    return policyViolation("OPTIONAL_CLAIM_DISABLED")
  }
  if (
    !artifactMatchesPolicy(
      event.artifact,
      S2S_CONFIRMATORY_POLICY.archive.adjudicationArchiveMaximumBytes,
      S2S_CONFIRMATORY_POLICY.archive.adjudicationArchiveMaximumBytes
    )
  ) {
    return policyViolation("ARCHIVE_POLICY_MISMATCH")
  }
  if (!artifactReadbackMatches(event.artifact)) {
    return policyViolation("ARTIFACT_READBACK_MISMATCH")
  }
  if (
    event.adjudicationJobCompletedAtUnixSeconds <
      state.adjudication.adjudicationJobStartedAtUnixSeconds ||
    state.adjudicationCandidate.jobElapsedSeconds !==
      event.adjudicationJobCompletedAtUnixSeconds -
        state.adjudication.adjudicationJobStartedAtUnixSeconds
  ) {
    return policyViolation("DEADLINE_EXCEEDED")
  }
  return Either.right(undefined)
}

const activeRunId = (
  state: Exclude<
    S2SConfirmatoryState,
    PreparedState | RegistrationVerifiedState | EvidenceArtifactVerifiedState | VoidedState
  >
): S2SWorkflowRunId => {
  switch (state._tag) {
    case "Registering":
      return state.registration.workflowRunId
    case "ConfirmWaiting":
    case "PulseEligible":
    case "ConfirmRunning":
    case "CandidateProduced":
      return state.confirm.workflowRunId
    case "CandidateArtifactVerified":
      return state.confirm.workflowRunId
    case "Adjudicating":
    case "AdjudicationProduced":
      return state.adjudication.workflowRunId
  }
}

const activeJobId = (
  state: Exclude<
    S2SConfirmatoryState,
    PreparedState | RegistrationVerifiedState | CandidateArtifactVerifiedState | EvidenceArtifactVerifiedState | VoidedState
  >
): S2SWorkflowJobId => {
  switch (state._tag) {
    case "Registering":
      return state.registration.registrationJobId
    case "ConfirmWaiting":
    case "PulseEligible":
    case "ConfirmRunning":
    case "CandidateProduced":
      return state.confirm.confirmJobId
    case "Adjudicating":
    case "AdjudicationProduced":
      return state.adjudication.adjudicationJobId
  }
}

const expectedVoidReasons = (
  phase: S2SConfirmatoryPhase
): ReadonlyArray<S2SOperationalVoidReason> => {
  switch (phase) {
    case "Registering":
      return ["REGISTER_JOB_DID_NOT_COMPLETE_SUCCESSFULLY"]
    case "ConfirmWaiting":
    case "PulseEligible":
    case "ConfirmRunning":
      return ["CONFIRM_JOB_DID_NOT_COMPLETE_SUCCESSFULLY"]
    case "CandidateProduced":
      return ["CANDIDATE_ARTIFACT_UNAVAILABLE"]
    case "Adjudicating":
      return [
        "ADJUDICATION_INTEGRITY_FAILURE",
        "ADJUDICATION_ARTIFACT_UNAVAILABLE"
      ]
    case "AdjudicationProduced":
      return ["ADJUDICATION_ARTIFACT_UNAVAILABLE"]
    case "Prepared":
    case "RegistrationVerified":
    case "CandidateArtifactVerified":
    case "EvidenceArtifactVerified":
    case "Voided":
      return []
  }
}

const recordVoid = (
  state: S2SConfirmatoryState,
  event: RecordOperationalVoid,
  latestControlReceiptSha256: S2SSha256
): Either.Either<VoidedState, S2SConfirmatoryTransitionError> => {
  if (
    state._tag === "Prepared" ||
    state._tag === "RegistrationVerified" ||
    state._tag === "CandidateArtifactVerified" ||
    state._tag === "EvidenceArtifactVerified" ||
    state._tag === "Voided"
  ) {
    return invalidTransition(state, event)
  }
  if (
    event.workflowRunId !== activeRunId(state) ||
    event.workflowJobId !== activeJobId(state) ||
    event.workflowRunAttempt !== 1
  ) {
    return policyViolation("RUN_BINDING_MISMATCH")
  }
  if (!expectedVoidReasons(state._tag).includes(event.reason)) {
    return policyViolation("VOID_REASON_MISMATCH")
  }
  return Either.right(
    Object.freeze({
      _tag: "Voided",
      experimentId: S2S_CONFIRMATORY_EXPERIMENT_ID,
      policySchemaVersion: S2S_CONFIRMATORY_POLICY_SCHEMA_VERSION,
      adoptionReceiptSha256: S2S_PILOT_ADOPTION_RECEIPT_SHA256,
      resourcePolicySha256: S2S_CONFIRMATORY_RESOURCE_POLICY_SHA256,
      protocolConfigSha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
      latestControlReceiptSha256,
      compactCompetitivePhraseAllowed: false,
      binding: event.binding,
      failedPhase: state._tag,
      workflowRunId: event.workflowRunId,
      workflowRunAttempt: 1,
      reason: event.reason,
      evidenceSha256: event.evidenceSha256,
      retryAllowed: false,
      candidateConsumable: false
    })
  )
}

export const advanceS2SConfirmatory = (
  state: S2SConfirmatoryState,
  event: S2SConfirmatoryEvent
): Either.Either<S2SConfirmatoryState, S2SConfirmatoryTransitionError> => {
  const lifecycle = validateLifecycleBinding(state, event)
  if (Either.isLeft(lifecycle)) return Either.left(lifecycle.left)
  const latestControlReceiptSha256 = lifecycle.right
  if (event._tag === "RecordOperationalVoid") {
    return recordVoid(state, event, latestControlReceiptSha256)
  }
  switch (state._tag) {
    case "Prepared": {
      if (event._tag !== "BeginRegistration") {
        return invalidTransition(state, event)
      }
      const validation = validateBeginRegistration(event)
      if (Either.isLeft(validation)) return Either.left(validation.left)
      return Either.right(
        Object.freeze({
          ...state,
          _tag: "Registering",
          latestControlReceiptSha256,
          registration: event
        })
      )
    }
    case "Registering": {
      if (event._tag !== "VerifyRegistration") {
        return invalidTransition(state, event)
      }
      const validation = validateRegistrationEvidence(state, event)
      if (Either.isLeft(validation)) return Either.left(validation.left)
      return Either.right(
        Object.freeze({
          ...state,
          _tag: "RegistrationVerified",
          latestControlReceiptSha256,
          registrationEvidence: event
        })
      )
    }
    case "RegistrationVerified": {
      if (event._tag !== "BeginConfirm") {
        return invalidTransition(state, event)
      }
      const validation = validateBeginConfirm(state, event)
      if (Either.isLeft(validation)) return Either.left(validation.left)
      return Either.right(
        Object.freeze({
          ...state,
          _tag: "ConfirmWaiting",
          latestControlReceiptSha256,
          confirm: event
        })
      )
    }
    case "ConfirmWaiting": {
      if (event._tag !== "AcceptVerifiedPulse") {
        return invalidTransition(state, event)
      }
      const validation = validatePulse(state, event)
      if (Either.isLeft(validation)) return Either.left(validation.left)
      return Either.right(
        Object.freeze({
          ...state,
          _tag: "PulseEligible",
          latestControlReceiptSha256,
          pulse: event
        })
      )
    }
    case "PulseEligible": {
      if (event._tag !== "BeginNumericConfirm") {
        return invalidTransition(state, event)
      }
      if (
        event.workflowRunId !== state.confirm.workflowRunId ||
        event.confirmJobId !== state.confirm.confirmJobId
      ) {
        return policyViolation("RUN_BINDING_MISMATCH")
      }
      return Either.right(
        Object.freeze({
          ...state,
          _tag: "ConfirmRunning",
          latestControlReceiptSha256,
          numericPlan: makeNumericCandidatePlan(state.pulse)
        })
      )
    }
    case "ConfirmRunning": {
      if (event._tag !== "RecordCandidateProduced") {
        return invalidTransition(state, event)
      }
      const validation = validateCandidate(state, event)
      if (Either.isLeft(validation)) return Either.left(validation.left)
      return Either.right(
        Object.freeze({
          ...state,
          _tag: "CandidateProduced",
          latestControlReceiptSha256,
          candidate: event
        })
      )
    }
    case "CandidateProduced": {
      if (event._tag !== "VerifyCandidateArtifact") {
        return invalidTransition(state, event)
      }
      const validation = validateCandidateArtifact(state, event)
      if (Either.isLeft(validation)) return Either.left(validation.left)
      return Either.right(
        Object.freeze({
          ...state,
          _tag: "CandidateArtifactVerified",
          latestControlReceiptSha256,
          candidateArtifact: event
        })
      )
    }
    case "CandidateArtifactVerified": {
      if (event._tag !== "BeginAdjudication") {
        return invalidTransition(state, event)
      }
      const validation = validateBeginAdjudication(state, event)
      if (Either.isLeft(validation)) return Either.left(validation.left)
      return Either.right(
        Object.freeze({
          ...state,
          _tag: "Adjudicating",
          latestControlReceiptSha256,
          adjudication: event,
          numericPlan: makeNumericAdjudicationPlan(state)
        })
      )
    }
    case "Adjudicating": {
      if (event._tag !== "RecordAdjudicationProduced") {
        return invalidTransition(state, event)
      }
      const validation = validateAdjudication(state, event)
      if (Either.isLeft(validation)) return Either.left(validation.left)
      return Either.right(
        Object.freeze({
          ...state,
          _tag: "AdjudicationProduced",
          latestControlReceiptSha256,
          adjudicationCandidate: event
        })
      )
    }
    case "AdjudicationProduced": {
      if (event._tag !== "VerifyEvidenceArtifact") {
        return invalidTransition(state, event)
      }
      const validation = validateEvidenceArtifact(state, event)
      if (Either.isLeft(validation)) return Either.left(validation.left)
      return Either.right(
        Object.freeze({
          ...state,
          _tag: "EvidenceArtifactVerified",
          latestControlReceiptSha256,
          evidenceArtifact: event,
          verdict: candidateOutcomeToVerdict(
            state.adjudicationCandidate.numericCandidateOutcome
          )
        })
      )
    }
    case "EvidenceArtifactVerified":
    case "Voided":
      return invalidTransition(state, event)
  }
}
