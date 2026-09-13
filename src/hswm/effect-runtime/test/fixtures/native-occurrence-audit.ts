import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { Effect, Either, Layer } from "effect"

import { BoundedSubprocess, type BoundedSubprocessShape, type SubprocessObservation } from "../../src/effect-bounded-subprocess.js"
import { PosixFileSystem, type PosixFileSystemShape } from "../../src/effect-posix-filesystem.js"
import { NativePinnedVerifier, NativePinnedVerifierError, type NativePinnedVerifierShape } from "../../src/native-pinned-verifier-runtime.js"
import { NATIVE_OCCURRENCE_QUALIFICATION_PATH, NATIVE_OCCURRENCE_TOOLCHAIN_PATH } from "../../src/native-occurrence-audit-runtime.js"
import { completeNativeOccurrence, type NativeIssuedCompletionReceipt, type NativeOccurrenceCompletionInput } from "../../src/native-occurrence-completion-domain.js"
import { nativeAssessDualEvaluation } from "../../src/native-occurrence-dual-evaluator-domain.js"
import { nativeAssessOccurrenceIntegrity } from "../../src/native-occurrence-integrity-domain.js"
import { advanceNativeOccurrence, registeredNativeOccurrence } from "../../src/native-occurrence-workflow-domain.js"
import type { TaskJson } from "../../src/native-task-json-domain.js"

const checkout = resolve(import.meta.dirname, "../../../../..")
const fixturePath = resolve(checkout, "tests/fixtures/native_migration/occurrence_completion_v1/qualified-audit-original.v2.json")
const integrityPath = resolve(checkout, "tests/fixtures/native_migration/occurrence_integrity_v1/original_python.json")
const candidatePath = resolve(checkout, "tests/fixtures/native_migration/occurrence_completion_v1/original_python_candidate.json")

const object = (value: unknown): Readonly<Record<string, unknown>> => {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("fixture object required")
  return value as Readonly<Record<string, unknown>>
}
const string = (value: Readonly<Record<string, unknown>>, key: string): string => {
  const found = value[key]
  if (typeof found !== "string") throw new Error(`fixture string ${key} required`)
  return found
}
const taskMap = (value: unknown): Readonly<Record<string, TaskJson>> => {
  const record = object(value)
  return record as Readonly<Record<string, TaskJson>>
}
const unwrap = <A, E>(value: Either.Either<A, E>): A => {
  if (Either.isLeft(value)) throw new Error("fixture domain construction failed")
  return value.right
}
const rawJudgment = (value: Readonly<Record<string, TaskJson>>): TaskJson => {
  const { schema: _schema, ...raw } = value
  return raw
}

export const qualifiedAuditFixture = object(JSON.parse(readFileSync(fixturePath, "utf8")))
const virtualFiles = object(qualifiedAuditFixture["virtual_files"])
const qualification = object(JSON.parse(string(virtualFiles, "qualification.json")))
const cosign = object(qualification["cosign"])
const trustedRoot = object(qualification["trusted_root"])
const fixtureRoot = string(qualifiedAuditFixture, "root")
export const originalSealedReceipt = object(qualifiedAuditFixture["sealed"])
export const originalAuditPayload = object(qualifiedAuditFixture["expected"])
export const originalAuditMaterial = Object.freeze({
  auditManifest: `${fixtureRoot}/audit-manifest.json`,
  cosignBundle: `${fixtureRoot}/bundle.json`,
  temporalTerminalReceipt: `${fixtureRoot}/temporal-terminal.json`,
  temporalHistoryExport: `${fixtureRoot}/temporal-history-export.json`
})

const virtual = (name: string): Uint8Array => new TextEncoder().encode(string(virtualFiles, name))
const successful = (stdout: string, stderr = ""): SubprocessObservation => Object.freeze({
  exitCode: 0, signal: null, timedOut: false, outputTruncated: false, launchError: null,
  stdout: new TextEncoder().encode(stdout), stderr: new TextEncoder().encode(stderr)
})
export interface QualifiedAuditMockOptions {
  readonly bytesForRead?: (path: string, readCount: number, original: Uint8Array | undefined) => Uint8Array | undefined
  readonly observation?: (argv: ReadonlyArray<string>) => SubprocessObservation
  readonly pinnedVerifier?: NativePinnedVerifierShape
}
const noIo = (fixtureFiles: ReadonlyMap<string, Uint8Array>, bytesForRead: QualifiedAuditMockOptions["bytesForRead"]): PosixFileSystemShape => {
  let readCount = 0
  return ({
  identity: () => Effect.die("unexpected identity"), listDirectory: () => Effect.die("unexpected list"), realpath: () => Effect.die("unexpected realpath"), makeDirectory: () => Effect.die("unexpected mkdir"), syncDirectory: () => Effect.die("unexpected sync directory"), syncRegular: () => Effect.die("unexpected sync file"), writeExclusive: () => Effect.die("unexpected write"), linkNoReplace: () => Effect.die("unexpected link"), chmod: () => Effect.die("unexpected chmod"), unlinkIfPresent: () => Effect.die("unexpected unlink"),
  readRegularBounded: (path) => {
    readCount += 1
    const value = bytesForRead === undefined ? fixtureFiles.get(path) : bytesForRead(path, readCount, fixtureFiles.get(path))
    return value === undefined ? Effect.die(`unexpected read ${path}`) : Effect.succeed({ bytes: value, device: 1, inode: 1 })
  }
  })
}
const auditSubprocess = (observation: QualifiedAuditMockOptions["observation"]): BoundedSubprocessShape => ({
  observe: (command) => Effect.succeed(observation === undefined ? (command.argv.at(1) === "version"
    ? successful(string(cosign, "exact_version_output"))
    : successful(string(qualifiedAuditFixture, "verifier_stdout"), string(qualifiedAuditFixture, "verifier_stderr"))) : observation(command.argv))
})
const auditPinnedVerifier = (observation: QualifiedAuditMockOptions["observation"]): NativePinnedVerifierShape => ({
  verify: (request) => {
    const version = observation === undefined ? successful(request.expectedVersionOutput) : observation([request.executablePath, "version"])
    const verification = observation === undefined ? successful(string(qualifiedAuditFixture, "verifier_stdout"), string(qualifiedAuditFixture, "verifier_stderr")) : observation(request.argv)
    if (version.launchError !== null || version.timedOut || version.outputTruncated || version.exitCode !== 0 || version.signal !== null || new TextDecoder().decode(version.stdout) + new TextDecoder().decode(version.stderr) !== request.expectedVersionOutput) return Effect.fail(new NativePinnedVerifierError({ code: "PIN_MISMATCH", detail: "mocked pinned verifier version mismatch" }))
    return Effect.succeed(Object.freeze({ version, verification }))
  }
})
const files = new Map<string, Uint8Array>([
  [NATIVE_OCCURRENCE_QUALIFICATION_PATH, virtual("qualification.json")],
  [NATIVE_OCCURRENCE_TOOLCHAIN_PATH, virtual("candidates.json")],
  [string(cosign, "path"), virtual("cosign")],
  [string(cosign, "license_path"), virtual("LICENSE")],
  [string(trustedRoot, "path"), virtual("root.json")],
  [originalAuditMaterial.auditManifest, virtual("audit-manifest.json")],
  [originalAuditMaterial.cosignBundle, virtual("bundle.json")],
  [originalAuditMaterial.temporalTerminalReceipt, virtual("temporal-terminal.json")],
  [originalAuditMaterial.temporalHistoryExport, virtual("temporal-history-export.json")]
])
export const qualifiedAuditServicesWith = (options: QualifiedAuditMockOptions = {}) => Layer.merge(Layer.merge(Layer.succeed(PosixFileSystem, noIo(files, options.bytesForRead)), Layer.succeed(BoundedSubprocess, auditSubprocess(options.observation))), Layer.succeed(NativePinnedVerifier, options.pinnedVerifier ?? auditPinnedVerifier(options.observation)))
export const qualifiedAuditServices = qualifiedAuditServicesWith()

const integrityFixture = object(JSON.parse(readFileSync(integrityPath, "utf8")))
const candidateFixture = object(JSON.parse(readFileSync(candidatePath, "utf8")))
const candidateInput = object(candidateFixture["input"])
export const completionTestBase = (): NativeOccurrenceCompletionInput => {
  const positive = object(integrityFixture["positive"])
  const assessment = unwrap(nativeAssessOccurrenceIntegrity(taskMap(positive["input"])))
  const judgmentA = rawJudgment(taskMap(object(candidateInput["judgment_a"])))
  const judgmentB = rawJudgment(taskMap(object(candidateInput["judgment_b"])))
  const dualEvaluation = unwrap(nativeAssessDualEvaluation(judgmentA, judgmentB))
  let workflow = unwrap(registeredNativeOccurrence("g0-occurrence-1", assessment.workflowEvidenceSha256s[0]!))
  for (const [phase, index] of [["CLAIMED", 1], ["SCHEDULED", 2], ["PRE_PULSE_SEALED", 3], ["PULSE_VERIFIED", 4], ["REVEALED", 5], ["DUAL_EVALUATED", 6]] as const) {
    workflow = unwrap(advanceNativeOccurrence(workflow, phase, assessment.workflowEvidenceSha256s[index]!, index <= 3 ? "PRE_PULSE" : "POST_PULSE"))
  }
  return Object.freeze({ assessment, workflow, dualEvaluation, judgmentA, judgmentB, startedAt: string(candidateInput, "started_at"), terminalAt: "2026-09-03T00:02:00Z" })
}
export const sealedCompletionInput = (): NativeOccurrenceCompletionInput => {
  const base = completionTestBase()
  const candidate = unwrap(completeNativeOccurrence({ ...base, terminalAt: "2026-09-03T00:01:00Z" }))
  const workflow = unwrap(advanceNativeOccurrence(base.workflow, "SEALED", candidate.receiptSha256, "POST_PULSE"))
  return Object.freeze({ ...base, workflow, candidateReceipt: candidate, externalAuditMaterial: originalAuditMaterial })
}
export const freshCandidateReceipt = (): NativeIssuedCompletionReceipt => {
  const base = completionTestBase()
  return unwrap(completeNativeOccurrence({ ...base, terminalAt: "2026-09-03T00:01:00Z" }))
}
