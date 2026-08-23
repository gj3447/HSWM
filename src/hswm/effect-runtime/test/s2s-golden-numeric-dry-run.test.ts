import { expect, it } from "@effect/vitest"
import { readFileSync } from "node:fs"

import { Effect, Either, Layer } from "effect"

import {
  canonicalS2SControlJsonBytes,
  canonicalS2SControlSha256,
  rawS2SFileSha256
} from "../src/s2s-canonical.js"
import {
  S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
  S2SSha256Schema
} from "../src/s2s-confirmatory.js"
import {
  runS2SGoldenNumericDryRun
} from "../src/s2s-golden-numeric-dry-run.js"
import {
  S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH,
  S2S_NUMERIC_GOLDEN_VECTOR_DOCUMENT_SHA256,
  S2S_NUMERIC_GOLDEN_VECTOR_RECEIPT_SHA256,
  S2S_NUMERIC_GOLDEN_VECTOR_SCHEMA_VERSION,
  S2S_NUMERIC_ORACLE_SOURCE_SHA256,
  S2S_PYTHON_RSS_TELEMETRY_SCHEMA_VERSION,
  S2S_PYTHON_RUNTIME_SOURCE_IDENTITY_SCHEMA_VERSION,
  S2SPythonGoldenVerifier,
  S2SPythonNumericExecutor,
  type S2SPythonGoldenVerification,
  type S2SPythonNumericOutput,
  type S2SPythonRuntimeSourceIdentityReceipt,
  type S2SPythonSourceIdentityEntry
} from "../src/s2s-live-python.js"
import {
  S2S_GOLDEN_CONFIRM_REQUEST_DOCUMENT_SHA256,
  S2S_GOLDEN_CONFIRM_REQUEST_SHA256
} from "../src/s2s-orchestration.js"
import {
  S2STestOnlyGoldenArtifactStore,
  S2STestOnlyGoldenArtifactStoreError,
  type S2STestOnlyGoldenArtifactPublicationReceipt,
  type S2STestOnlyGoldenArtifactReadback
} from "../src/s2s-test-only-golden-artifact-store.js"
import {
  buildS2STestOnlyGoldenArtifact,
  buildS2STestOnlyGoldenUploadPostcondition,
  type S2STestOnlyGoldenArtifactMemberInput,
  type S2STestOnlyGoldenRole
} from "../src/s2s-test-only-golden-upload.js"
import * as PublicApi from "../src/index.js"

const encoder = new TextEncoder()

const rightOrThrow = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw value.left
  return value.right
}

const canonicalBytes = (value: unknown): Uint8Array =>
  rightOrThrow(canonicalS2SControlJsonBytes(value))

const hash = (label: string) =>
  S2SSha256Schema.make(rawS2SFileSha256(encoder.encode(label)))

const sameBytes = (left: Uint8Array, right: Uint8Array): boolean =>
  left.byteLength === right.byteLength &&
  left.every((byte, index) => byte === right[index])

const rssBytes = (): Uint8Array =>
  canonicalBytes({
    api: "getrusage",
    oom_observed: false,
    peak_rss_kib: 42_000,
    schema_version: S2S_PYTHON_RSS_TELEMETRY_SCHEMA_VERSION,
    subject: "RUSAGE_SELF",
    unit: "KiB"
  })

const candidateBytes = (): Uint8Array =>
  canonicalBytes({
    canonical_encoding: "ASCII_CANONICAL_UTF8_JSON_PLUS_SINGLE_LF",
    receipt_sha256: hash("candidate-self"),
    schema_version: "hswm-swm0w-s2s-numeric-candidate/v1"
  })

const adjudicationBytes = (
  candidate: Uint8Array,
  outcome:
    | "CANDIDATE_PASS_AWAITING_BUNDLE"
    | "VOID"
): Uint8Array => {
  const replay = {
    candidate_reducer_canonical_equal: true,
    candidate_reducer_receipt_sha256: hash("candidate-reducer"),
    compact_competitive_phrase_allowed: false,
    compact_competitive_phrase_policy:
      "DS_SELECTED_CONFIGURATION_NEVER_BEAT_EPOCH_ZERO",
    numeric_candidate_outcome: outcome,
    numeric_candidate_reason_codes: [
      outcome === "VOID" ? "FAKE_VOID" : "ESSENTIAL_Q_B_R_PASS"
    ],
    optimizer_refit_performed: false,
    protocol_config_receipt_sha256: S2S_PROTOCOL_CONFIG_RECEIPT_SHA256,
    task_batch_sha256: hash("task-batch"),
    task_evaluation_receipt_sha256s: Array.from(
      { length: 20 },
      (_, index) => hash(`task-evaluation-${index}`)
    ),
    test_and_integrity_recomputed_count: 20
  }
  const unsigned = {
    candidate_document_sha256: rawS2SFileSha256(candidate),
    candidate_receipt_sha256: hash("candidate-self"),
    canonical_encoding: "ASCII_CANONICAL_UTF8_JSON_PLUS_SINGLE_LF",
    claim_boundary: "NUMERIC_ONLY_NO_EVIDENCE_VERDICT_OR_CHRONOLOGY_CLAIM",
    confirm_request_sha256: S2S_GOLDEN_CONFIRM_REQUEST_SHA256,
    numeric_replay: replay,
    schema_version: "hswm-swm0w-s2s-numeric-adjudication/v1",
    scientific_status: "NUMERIC_CANDIDATE_ONLY_UNJUDGED",
    status: "NUMERIC_REPLAY_VALIDATED_CANDIDATE_ONLY"
  }
  const receipt = rightOrThrow(canonicalS2SControlSha256(unsigned))
  return canonicalBytes({ ...unsigned, receipt_sha256: receipt })
}

interface RuntimeFixture {
  readonly identity: S2SPythonRuntimeSourceIdentityReceipt
  readonly mutableSourceClosure: Array<S2SPythonSourceIdentityEntry>
}

const runtimeFixture = (
  receiptLabel = "shared-runtime",
  documentLabel = "shared-runtime"
): RuntimeFixture => {
  const identityBytes = canonicalBytes({ runtime: documentLabel })
  const mutableSourceClosure: Array<S2SPythonSourceIdentityEntry> = [
    Object.freeze({
      path: "src/hswm/experiments/swm0w_s2s_numeric_oracle.py",
      byteLength: 1,
      rawBytesSha256: S2SSha256Schema.make(
        S2S_NUMERIC_ORACLE_SOURCE_SHA256
      )
    })
  ]
  return {
    mutableSourceClosure,
    identity: Object.freeze({
      schemaVersion: S2S_PYTHON_RUNTIME_SOURCE_IDENTITY_SCHEMA_VERSION,
      pythonExecutableSha256: hash("python-executable"),
      pythonVersion: "3.12.13",
      pythonImplementation: "CPython",
      pythonCacheTag: "cpython-312",
      byteorder: "little",
      numpyVersion: "2.5.2",
      numpyModulePath: "/pinned/numpy/__init__.py",
      modulePaths: Object.freeze({ oracle: "/repo/oracle.py" }),
      repositoryRoot: "/repo",
      pythonExecutableArgv0: "/pinned/python",
      processEnvironmentContract: Object.freeze({ LANG: "C" }),
      processEnvironmentContractSha256: hash("environment"),
      sourceClosure: mutableSourceClosure,
      sourceClosureSha256: hash("source-closure"),
      receiptSha256: hash(receiptLabel),
      readCanonicalBytes: () => Uint8Array.from(identityBytes)
    })
  }
}

const numericOutput = (input: {
  readonly operation: "CONFIRM" | "ADJUDICATE"
  readonly stdin: Uint8Array
  readonly stdout: Uint8Array
  readonly runtime: S2SPythonRuntimeSourceIdentityReceipt
  readonly inputHashOverride?: ReturnType<typeof hash>
  readonly onReadOutput?: () => void
  readonly onReadRss?: () => void
}): S2SPythonNumericOutput => {
  const telemetry = rssBytes()
  const outputBytes = Uint8Array.from(input.stdout)
  return Object.freeze({
    operation: input.operation,
    memberName:
      input.operation === "CONFIRM"
        ? "numeric_candidate.json"
        : "numeric_adjudication.json",
    inputRawBytesSha256:
      input.inputHashOverride ??
      S2SSha256Schema.make(rawS2SFileSha256(input.stdin)),
    rawBytesSha256: S2SSha256Schema.make(rawS2SFileSha256(outputBytes)),
    byteLength: outputBytes.byteLength,
    commandElapsedNanoseconds: 123_456,
    peakRssKiB: 42_000,
    rssTelemetryRawSha256: S2SSha256Schema.make(
      rawS2SFileSha256(telemetry)
    ),
    runtimeSourceIdentityReceiptSha256: input.runtime.receiptSha256,
    readCanonicalBytes: () => {
      input.onReadOutput?.()
      return Uint8Array.from(outputBytes)
    },
    readRssTelemetryCanonicalBytes: () => {
      input.onReadRss?.()
      return Uint8Array.from(telemetry)
    }
  })
}

interface NumericOptions {
  readonly outcome?: "CANDIDATE_PASS_AWAITING_BUNDLE" | "VOID"
  readonly verifierDocumentLabel?: string
  readonly confirmBindingMismatch?: boolean
  readonly corruptRuntimeBeforeAdjudicationBinding?: boolean
}

interface NumericServices {
  readonly trace: Array<string>
  readonly verifier: S2SPythonGoldenVerifier["Type"]
  readonly executor: S2SPythonNumericExecutor["Type"]
  readonly readConfirmInput: () => Uint8Array
  readonly readAdjudicationInput: () => Uint8Array
  readonly adjudicationOutputReadCounts: () => {
    readonly output: number
    readonly rss: number
  }
}

const makeNumericServices = (
  options: NumericOptions = {}
): NumericServices => {
  const trace: Array<string> = []
  const executorRuntime = runtimeFixture()
  const verifierRuntime = runtimeFixture(
    "shared-runtime",
    options.verifierDocumentLabel ?? "shared-runtime"
  )
  let confirmInput = new Uint8Array()
  let adjudicationInput = new Uint8Array()
  let adjudicationOutputReads = 0
  let adjudicationRssReads = 0
  const verification: S2SPythonGoldenVerification = Object.freeze({
    schemaVersion: S2S_NUMERIC_GOLDEN_VECTOR_SCHEMA_VERSION,
    documentByteLength: S2S_NUMERIC_GOLDEN_VECTOR_BYTE_LENGTH,
    rawBytesSha256: S2SSha256Schema.make(
      S2S_NUMERIC_GOLDEN_VECTOR_DOCUMENT_SHA256
    ),
    receiptSha256: S2SSha256Schema.make(
      S2S_NUMERIC_GOLDEN_VECTOR_RECEIPT_SHA256
    ),
    commandElapsedNanoseconds: 1,
    runtimeSourceIdentityReceiptSha256:
      verifierRuntime.identity.receiptSha256
  })
  const verifier = S2SPythonGoldenVerifier.of({
    runtimeSourceIdentity: verifierRuntime.identity,
    verify: Effect.sync(() => {
      trace.push("verify")
      return verification
    })
  })
  const executor = S2SPythonNumericExecutor.of({
    runtimeSourceIdentity: executorRuntime.identity,
    confirm: (stdin) =>
      Effect.sync(() => {
        trace.push("confirm")
        confirmInput = Uint8Array.from(stdin)
        return numericOutput({
          operation: "CONFIRM",
          stdin: confirmInput,
          stdout: candidateBytes(),
          runtime: executorRuntime.identity,
          ...(options.confirmBindingMismatch === true
            ? { inputHashOverride: hash("wrong-confirm-input") }
            : {})
        })
      }),
    adjudicate: (stdin) =>
      Effect.sync(() => {
        trace.push("adjudicate")
        adjudicationInput = Uint8Array.from(stdin)
        const output = numericOutput({
          operation: "ADJUDICATE",
          stdin: adjudicationInput,
          stdout: adjudicationBytes(
            adjudicationInput,
            options.outcome ?? "CANDIDATE_PASS_AWAITING_BUNDLE"
          ),
          runtime: executorRuntime.identity,
          onReadOutput: () => {
            adjudicationOutputReads += 1
          },
          onReadRss: () => {
            adjudicationRssReads += 1
          }
        })
        if (options.corruptRuntimeBeforeAdjudicationBinding === true) {
          executorRuntime.mutableSourceClosure[0] = Object.freeze({
            path: "src/hswm/experiments/swm0w_s2s_numeric_oracle.py",
            byteLength: 1,
            rawBytesSha256: hash("wrong-oracle-source")
          })
        }
        return output
      })
  })
  return {
    trace,
    verifier,
    executor,
    readConfirmInput: () => Uint8Array.from(confirmInput),
    readAdjudicationInput: () => Uint8Array.from(adjudicationInput),
    adjudicationOutputReadCounts: () => ({
      output: adjudicationOutputReads,
      rss: adjudicationRssReads
    })
  }
}

interface FakeStoreOptions {
  readonly mismatchSecondCandidateRead?: boolean
  readonly mismatchCandidateRecovery?: boolean
  readonly publicationOutcomeUnknown?: boolean
}

interface StoredArtifact {
  readonly receipt: S2STestOnlyGoldenArtifactPublicationReceipt
  readonly readback: S2STestOnlyGoldenArtifactReadback
}

const makeFakeStore = (
  trace: Array<string>,
  options: FakeStoreOptions = {}
): S2STestOnlyGoldenArtifactStore["Type"] => {
  const stored = new Map<S2STestOnlyGoldenRole, StoredArtifact>()
  const readCounts = new Map<S2STestOnlyGoldenRole, number>()
  return S2STestOnlyGoldenArtifactStore.of({
    publishGoldenArtifact: (
      role: S2STestOnlyGoldenRole,
      exactMembers: ReadonlyArray<S2STestOnlyGoldenArtifactMemberInput>
    ) =>
      Effect.suspend(() => {
        trace.push(`publish:${role}`)
        if (
          role === "GOLDEN_CANDIDATE" &&
          options.publicationOutcomeUnknown === true
        ) {
          return Effect.fail(
            new S2STestOnlyGoldenArtifactStoreError({
              operation: "PUBLISH",
              reason: "PUBLICATION_OUTCOME_UNKNOWN",
              role,
              detail: "intentional fake unknown publication outcome"
            })
          )
        }
        const artifact = rightOrThrow(
          buildS2STestOnlyGoldenArtifact(role, exactMembers)
        )
        const archive = artifact.readArchiveBytes()
        const postcondition = rightOrThrow(
          buildS2STestOnlyGoldenUploadPostcondition({
            role,
            publicationKey: artifact.publicationKey,
            publicationDisposition: "CREATED",
            archiveBytes: archive,
            readbackBytes: archive
          })
        )
        const postconditionArchive = postcondition.readArchiveBytes()
        const member = artifact.members[0]
        const receipt: S2STestOnlyGoldenArtifactPublicationReceipt =
          Object.freeze({
            _tag: "S2STestOnlyGoldenArtifactPublicationReceipt",
            classification: "TEST_ONLY_NON_AUTHORIZING",
            origin: "LOCAL_TEST_LAYER",
            role,
            publicationKey: artifact.publicationKey,
            disposition: "CREATED",
            archiveSha256: artifact.archiveRawSha256,
            archiveByteLength: artifact.archiveByteLength,
            postconditionPublicationKey:
              artifact.postconditionPublicationKey,
            postconditionSha256: postcondition.archiveRawSha256,
            postconditionByteLength: postcondition.archiveByteLength,
            readArchiveBytes: () => Uint8Array.from(archive)
          })
        const readback: S2STestOnlyGoldenArtifactReadback = Object.freeze({
          _tag: "S2STestOnlyGoldenArtifactReadback",
          classification: "TEST_ONLY_NON_AUTHORIZING",
          origin: "LOCAL_TEST_LAYER",
          role,
          publicationKey: artifact.publicationKey,
          archiveSha256: artifact.archiveRawSha256,
          archiveByteLength: artifact.archiveByteLength,
          postconditionPublicationKey: artifact.postconditionPublicationKey,
          postconditionSha256: postcondition.archiveRawSha256,
          postconditionByteLength: postcondition.archiveByteLength,
          member: Object.freeze({
            name: member.name,
            rawSha256: member.rawBytesSha256,
            byteLength: member.byteLength,
            readBytes: () => member.readBytes()
          }),
          readArchiveBytes: () => Uint8Array.from(archive),
          readPostconditionArchiveBytes: () =>
            Uint8Array.from(postconditionArchive),
          readPostconditionDocumentBytes: () =>
            postcondition.readDocumentBytes()
        })
        stored.set(role, { receipt, readback })
        return Effect.succeed(receipt)
      }),
    readBackGoldenArtifact: (receipt) =>
      Effect.suspend(() => {
        const count = (readCounts.get(receipt.role) ?? 0) + 1
        readCounts.set(receipt.role, count)
        trace.push(`read:${receipt.role}:${count}`)
        const value = stored.get(receipt.role)
        if (value === undefined) {
          return Effect.fail(
            new S2STestOnlyGoldenArtifactStoreError({
              operation: "READBACK",
              reason: "READBACK_FAILED",
              role: receipt.role,
              detail: "fake artifact is absent"
            })
          )
        }
        if (
          receipt.role === "GOLDEN_CANDIDATE" &&
          count === 2 &&
          options.mismatchSecondCandidateRead === true
        ) {
          const corruptMember = value.readback.member.readBytes()
          corruptMember[0] = corruptMember[0] === 0x20 ? 0x21 : 0x20
          return Effect.succeed(
            Object.freeze({
              ...value.readback,
              member: Object.freeze({
                ...value.readback.member,
                rawSha256: rawS2SFileSha256(corruptMember),
                readBytes: () => Uint8Array.from(corruptMember)
              })
            })
          )
        }
        return Effect.succeed(value.readback)
      }),
    recoverGoldenArtifactWithFreshLayer: (receipt) =>
      Effect.suspend(() => {
        trace.push(`recover:${receipt.role}`)
        const value = stored.get(receipt.role)
        if (value === undefined) {
          return Effect.fail(
            new S2STestOnlyGoldenArtifactStoreError({
              operation: "READBACK",
              reason: "RECOVERY_MISMATCH",
              role: receipt.role,
              detail: "fake recovery artifact is absent"
            })
          )
        }
        if (
          receipt.role === "GOLDEN_CANDIDATE" &&
          options.mismatchCandidateRecovery === true
        ) {
          const corruptMember = value.readback.member.readBytes()
          corruptMember[0] = corruptMember[0] === 0x20 ? 0x21 : 0x20
          return Effect.succeed(
            Object.freeze({
              ...value.readback,
              member: Object.freeze({
                ...value.readback.member,
                rawSha256: rawS2SFileSha256(corruptMember),
                readBytes: () => Uint8Array.from(corruptMember)
              })
            })
          )
        }
        return Effect.succeed(value.readback)
      })
  })
}

const testLayer = (
  numeric: NumericServices,
  storeOptions: FakeStoreOptions = {}
) =>
  Layer.mergeAll(
    Layer.succeed(S2SPythonGoldenVerifier, numeric.verifier),
    Layer.succeed(S2SPythonNumericExecutor, numeric.executor),
    Layer.succeed(
      S2STestOnlyGoldenArtifactStore,
      makeFakeStore(numeric.trace, storeOptions)
    )
  )

it.effect("lazily composes the exact fixed request, two candidate readbacks, evidence, and non-VOID uploads", () => {
  const numeric = makeNumericServices()
  const effect = runS2SGoldenNumericDryRun.pipe(
    Effect.provide(testLayer(numeric))
  )
  expect(numeric.trace).toEqual([])
  return Effect.gen(function* () {
    const result = yield* effect
    expect(numeric.trace).toEqual([
      "verify",
      "confirm",
      "publish:GOLDEN_CANDIDATE",
      "read:GOLDEN_CANDIDATE:1",
      "read:GOLDEN_CANDIDATE:2",
      "recover:GOLDEN_CANDIDATE",
      "adjudicate",
      "publish:GOLDEN_ADJUDICATION",
      "read:GOLDEN_ADJUDICATION:1",
      "recover:GOLDEN_ADJUDICATION"
    ])
    const confirmInput = numeric.readConfirmInput()
    expect(rawS2SFileSha256(confirmInput)).toBe(
      S2S_GOLDEN_CONFIRM_REQUEST_DOCUMENT_SHA256
    )
    const request: unknown = JSON.parse(
      new TextDecoder().decode(confirmInput)
    )
    expect(request).toMatchObject({
      external_seed_hex:
        "552e51d2ff75cb7c5df5b55a166aba12a277c2813bbdd69bc825286e7c26b6f0",
      request_sha256: S2S_GOLDEN_CONFIRM_REQUEST_SHA256
    })
    expect(sameBytes(numeric.readAdjudicationInput(), candidateBytes())).toBe(
      true
    )
    expect(result._tag).toBe("S2SGoldenNumericDryRunCompleted")
    if (result._tag === "S2SGoldenNumericDryRunCompleted") {
      expect(result.numericCandidateOutcome).toBe(
        "CANDIDATE_PASS_AWAITING_BUNDLE"
      )
      expect(result.candidateArtifact.role).toBe("GOLDEN_CANDIDATE")
      expect(result.adjudicationArtifact.role).toBe("GOLDEN_ADJUDICATION")
      expect(result.confirmEvidenceReceiptSha256).toMatch(/^[0-9a-f]{64}$/)
      expect(result.adjudicationEvidenceReceiptSha256).toMatch(
        /^[0-9a-f]{64}$/
      )
      expect(Object.isFrozen(result)).toBe(true)
      expect(Object.isFrozen(result.numericCandidateReasonCodes)).toBe(true)
      expect(Object.isFrozen(result.candidateArtifact)).toBe(true)
      expect("canonicalUtf8WithLf" in result).toBe(false)
    }
  })
})

it.effect("rejects verifier/executor canonical runtime mismatch before confirm", () => {
  const numeric = makeNumericServices({ verifierDocumentLabel: "other-runtime" })
  return Effect.gen(function* () {
    const result = yield* runS2SGoldenNumericDryRun.pipe(
      Effect.provide(testLayer(numeric)),
      Effect.either
    )
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({
        _tag: "S2SGoldenNumericDryRunError",
        reason: "RUNTIME_IDENTITY_MISMATCH"
      })
    }
    expect(numeric.trace).toEqual(["verify"])
  })
})

it.effect("binds confirm evidence before any candidate publication", () => {
  const numeric = makeNumericServices({ confirmBindingMismatch: true })
  return Effect.gen(function* () {
    const result = yield* runS2SGoldenNumericDryRun.pipe(
      Effect.provide(testLayer(numeric)),
      Effect.either
    )
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({
        _tag: "S2SPythonExecutionEvidenceError",
        reason: "REQUEST_BINDING_MISMATCH"
      })
    }
    expect(numeric.trace).toEqual(["verify", "confirm"])
  })
})

it.effect("rejects a differing second candidate readback before adjudication", () => {
  const numeric = makeNumericServices()
  return Effect.gen(function* () {
    const result = yield* runS2SGoldenNumericDryRun.pipe(
      Effect.provide(
        testLayer(numeric, { mismatchSecondCandidateRead: true })
      ),
      Effect.either
    )
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({ reason: "READBACK_MISMATCH" })
    }
    expect(numeric.trace).toEqual([
      "verify",
      "confirm",
      "publish:GOLDEN_CANDIDATE",
      "read:GOLDEN_CANDIDATE:1",
      "read:GOLDEN_CANDIDATE:2"
    ])
  })
})

it.effect("rejects fresh candidate recovery disagreement before adjudication", () => {
  const numeric = makeNumericServices()
  return Effect.gen(function* () {
    const result = yield* runS2SGoldenNumericDryRun.pipe(
      Effect.provide(
        testLayer(numeric, { mismatchCandidateRecovery: true })
      ),
      Effect.either
    )
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({
        _tag: "S2SGoldenNumericDryRunError",
        reason: "RECOVERY_MISMATCH"
      })
    }
    expect(numeric.trace).toEqual([
      "verify",
      "confirm",
      "publish:GOLDEN_CANDIDATE",
      "read:GOLDEN_CANDIDATE:1",
      "read:GOLDEN_CANDIDATE:2",
      "recover:GOLDEN_CANDIDATE"
    ])
  })
})

it.effect("returns an immediate independently validated VOID without adjudication evidence or upload", () => {
  const numeric = makeNumericServices({ outcome: "VOID" })
  return Effect.gen(function* () {
    const result = yield* runS2SGoldenNumericDryRun.pipe(
      Effect.provide(testLayer(numeric))
    )
    expect(result._tag).toBe("S2SGoldenNumericDryRunVoid")
    expect(numeric.trace).toEqual([
      "verify",
      "confirm",
      "publish:GOLDEN_CANDIDATE",
      "read:GOLDEN_CANDIDATE:1",
      "read:GOLDEN_CANDIDATE:2",
      "recover:GOLDEN_CANDIDATE",
      "adjudicate"
    ])
    expect(numeric.adjudicationOutputReadCounts()).toEqual({ output: 1, rss: 1 })
    if (result._tag === "S2SGoldenNumericDryRunVoid") {
      expect(result.status).toBe("NUMERIC_OUTCOME_VOID")
      expect(result.candidateArtifact.role).toBe("GOLDEN_CANDIDATE")
      expect("adjudicationEvidenceReceiptSha256" in result).toBe(false)
      expect("adjudicationArtifact" in result).toBe(false)
      expect(Object.isFrozen(result)).toBe(true)
      expect(Object.isFrozen(result.adjudicate)).toBe(true)
    }
  })
})

it.effect("projects non-VOID before adjudication evidence binding and never uploads invalid evidence", () => {
  const numeric = makeNumericServices({
    corruptRuntimeBeforeAdjudicationBinding: true
  })
  return Effect.gen(function* () {
    const result = yield* runS2SGoldenNumericDryRun.pipe(
      Effect.provide(testLayer(numeric)),
      Effect.either
    )
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({
        _tag: "S2SPythonExecutionEvidenceError",
        reason: "RUNTIME_IDENTITY_MISMATCH"
      })
    }
    // The independent pre-projection validator reads once. The later evidence
    // binder rejects the drifted runtime closure before trusting either reader.
    expect(numeric.adjudicationOutputReadCounts()).toEqual({ output: 1, rss: 1 })
    expect(numeric.trace).toEqual([
      "verify",
      "confirm",
      "publish:GOLDEN_CANDIDATE",
      "read:GOLDEN_CANDIDATE:1",
      "read:GOLDEN_CANDIDATE:2",
      "recover:GOLDEN_CANDIDATE",
      "adjudicate"
    ])
  })
})

it.effect("does not retry an unknown candidate publication outcome", () => {
  const numeric = makeNumericServices()
  return Effect.gen(function* () {
    const result = yield* runS2SGoldenNumericDryRun.pipe(
      Effect.provide(
        testLayer(numeric, { publicationOutcomeUnknown: true })
      ),
      Effect.either
    )
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) {
      expect(result.left).toMatchObject({
        _tag: "S2STestOnlyGoldenArtifactStoreError",
        reason: "PUBLICATION_OUTCOME_UNKNOWN"
      })
    }
    expect(numeric.trace).toEqual([
      "verify",
      "confirm",
      "publish:GOLDEN_CANDIDATE"
    ])
  })
})

it("keeps the composition root-private and free of production lifecycle imports", () => {
  expect("runS2SGoldenNumericDryRun" in PublicApi).toBe(false)
  const source = readFileSync(
    new URL("../src/s2s-golden-numeric-dry-run.ts", import.meta.url),
    "utf-8"
  )
  for (const forbidden of [
    "s2s-job-sequence",
    "s2s-evidence-profile",
    "s2s-evidence-file",
    "S2SConfirmatoryEvent",
    "S2SArtifactEvidence",
    "prepareS2SCandidateCarrier",
    "prepareS2SAdjudicationCarrier",
    "Effect.runPromise",
    "Effect.runSync"
  ]) {
    expect(source).not.toContain(forbidden)
  }
})
