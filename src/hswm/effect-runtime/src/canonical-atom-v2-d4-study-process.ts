#!/usr/bin/env node
/**
 * Narrow one-request bridge for the declared D4 study only.
 *
 * The caller supplies the five sealed study payloads, never atom/state or
 * Permit material.  This bridge constructs the sole admitted D4 closure and
 * sends it through the Lean-validated V2 gateway.  It is an internal research
 * interface, not a generic canonical writer or an HSWM-wide admission path.
 */
import { createHash } from "node:crypto"
import { dirname, isAbsolute, join } from "node:path"
import { pathToFileURL } from "node:url"

import { Effect, Either } from "effect"

import { D4_STUDY_SCHEMA_V1, D4_STUDY_STATUS, makeD4StudyAdmissionGateway, validateD4StudyPostState } from "./canonical-atom-v2-d4-study.js"
import { canonicalJsonBytes, decodeCanonicalJsonBytes, type CanonicalJson } from "./canonical-atom-v2-json.js"
import { makeEphemeralLocalPermitIssuer, makeLocalPermitVerifierContext, type LocalPermitCommitError } from "./canonical-atom-v2-local-permit-commit.js"
import { PosixFileSystem } from "./effect-posix-services.js"
import { ProcessRefusal, refuse, runProcessMain } from "./effect-process-main.js"
import type { VerifiedAdmissionGatewayError } from "./canonical-atom-v2-verified-admission-gateway.js"

export const HSWM_D4_STUDY_PROCESS_V1 = "hswm-d4-study-process/v1" as const
export const HSWM_D4_STUDY_PROCESS_CLAIM_BOUNDARY =
  "D4_ACTIVE_DECLARED_STUDY_ONLY_LEAN_VALIDATED_LOCAL_V2_ADMISSION_NOT_HSWM_WIDE_ADMISSION_NOT_CONTROL_RESULT_NOT_FREEZE_NOT_MODEL_CALL_NOT_PROGRESS_OR_EFFICACY_CLAIM" as const

const MAX_PAYLOAD_BYTES = 65_536
const MAX_TRUST_SNAPSHOT_BYTES = 65_536
const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/
const sha256 = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const exactKeys = (value: Record<string, unknown>, keys: ReadonlyArray<string>): boolean =>
  Object.keys(value).sort().join("\0") === [...keys].sort().join("\0")
const object = (value: unknown): Record<string, unknown> | null =>
  typeof value === "object" && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : null
const identifier = (value: unknown): value is string => typeof value === "string" && IDENTIFIER.test(value)
const absolutePath = (value: unknown): value is string => typeof value === "string" && value.length > 0 && value.length <= 4096 && !value.includes("\0") && isAbsolute(value)

interface D4Payloads {
  readonly task: CanonicalJson
  readonly instance: CanonicalJson
  readonly trajectory: CanonicalJson
  readonly outcome: CanonicalJson
  readonly credit: CanonicalJson
  readonly disposition: CanonicalJson
}
interface CommitRequest {
  readonly operation: "commit"
  readonly rootPath: string
  readonly trustSnapshotPath: string
  readonly leanExecutable: string
  readonly occurrenceUid: string
  readonly lifetimeMs: number
  readonly payloads: D4Payloads
}
interface RecoverRequest {
  readonly operation: "recover"
  readonly rootPath: string
  readonly trustSnapshotPath: string
  readonly leanExecutable: string
  readonly occurrenceUid: string
}
type D4ProcessRequest = CommitRequest | RecoverRequest

const payloads = (value: unknown): D4Payloads | null => {
  const candidate = object(value)
  if (candidate === null || !exactKeys(candidate, ["task", "instance", "trajectory", "outcome", "credit", "disposition"])) return null
  const values = [candidate["task"], candidate["instance"], candidate["trajectory"], candidate["outcome"], candidate["credit"], candidate["disposition"]]
  if (values.some((item) => !isCanonicalJson(item))) return null
  return Object.freeze({ task: candidate["task"] as CanonicalJson, instance: candidate["instance"] as CanonicalJson, trajectory: candidate["trajectory"] as CanonicalJson, outcome: candidate["outcome"] as CanonicalJson, credit: candidate["credit"] as CanonicalJson, disposition: candidate["disposition"] as CanonicalJson })
}

const isCanonicalJson = (value: unknown): value is CanonicalJson => Either.isRight(canonicalJsonBytes(value))

const decodeRequest = (value: CanonicalJson): Effect.Effect<D4ProcessRequest, ProcessRefusal> => {
  const candidate = object(value)
  if (candidate === null || candidate["contractVersion"] !== HSWM_D4_STUDY_PROCESS_V1) return Effect.fail(refuse("request contract version is not supported"))
  if (candidate["operation"] === "commit") {
    const bodies = payloads(candidate["payloads"])
    if (!exactKeys(candidate, ["contractVersion", "operation", "rootPath", "trustSnapshotPath", "leanExecutable", "occurrenceUid", "lifetimeMs", "mode", "payloads"]) ||
      !absolutePath(candidate["rootPath"]) || !absolutePath(candidate["trustSnapshotPath"]) || !absolutePath(candidate["leanExecutable"]) || !identifier(candidate["occurrenceUid"]) ||
      candidate["mode"] !== "ACTIVE" || !Number.isSafeInteger(candidate["lifetimeMs"]) || (candidate["lifetimeMs"] as number) < 1 || (candidate["lifetimeMs"] as number) > 60_000 || bodies === null) {
      return Effect.fail(refuse("request is not a valid bounded ACTIVE D4 commit"))
    }
    return Effect.succeed(Object.freeze({ operation: "commit", rootPath: candidate["rootPath"], trustSnapshotPath: candidate["trustSnapshotPath"], leanExecutable: candidate["leanExecutable"], occurrenceUid: candidate["occurrenceUid"], lifetimeMs: candidate["lifetimeMs"] as number, payloads: bodies }))
  }
  if (candidate["operation"] === "recover") {
    if (!exactKeys(candidate, ["contractVersion", "operation", "rootPath", "trustSnapshotPath", "leanExecutable", "occurrenceUid"]) || !absolutePath(candidate["rootPath"]) || !absolutePath(candidate["trustSnapshotPath"]) || !absolutePath(candidate["leanExecutable"]) || !identifier(candidate["occurrenceUid"])) {
      return Effect.fail(refuse("request is not a valid bounded D4 recovery"))
    }
    return Effect.succeed(Object.freeze({ operation: "recover", rootPath: candidate["rootPath"], trustSnapshotPath: candidate["trustSnapshotPath"], leanExecutable: candidate["leanExecutable"], occurrenceUid: candidate["occurrenceUid"] }))
  }
  return Effect.fail(refuse("operation must be commit or recover"))
}

const boundedBytes = (value: CanonicalJson, label: string): Effect.Effect<Uint8Array, ProcessRefusal> => {
  const encoded = canonicalJsonBytes(value)
  return Either.isLeft(encoded) || encoded.right.byteLength < 1 || encoded.right.byteLength > MAX_PAYLOAD_BYTES
    ? Effect.fail(refuse(`${label} must be nonempty canonical JSON within the byte bound`))
    : Effect.succeed(encoded.right)
}

const canonicalDigest = (value: CanonicalJson, label: string): Effect.Effect<string, ProcessRefusal> => {
  const encoded = canonicalJsonBytes(value)
  return Either.isLeft(encoded) ? Effect.fail(refuse(`${label} cannot form canonical JSON`)) : Effect.succeed(sha256(encoded.right))
}

const occurrenceBoundPayloads = (payloads: D4Payloads, occurrenceUid: string): boolean => {
  const instance = object(payloads.instance)
  const trajectory = object(payloads.trajectory)
  const outcome = object(payloads.outcome)
  const credit = object(payloads.credit)
  return instance?.["occurrence_uid"] === occurrenceUid && trajectory?.["occurrence_uid"] === occurrenceUid &&
    outcome?.["occurrence_uid"] === occurrenceUid && credit?.["origin_occurrence_uid"] === occurrenceUid
}

const atomKey = (lineageId: string, atomUid: string) => Object.freeze({ schemaVersion: D4_STUDY_SCHEMA_V1, lineageId, atomUid, revisionId: 0 })
const keyId = (key: ReturnType<typeof atomKey>): string => `${key.schemaVersion}|${key.lineageId}|${key.atomUid}|${key.revisionId}`
const reference = (referenceType: string, role: string, target: ReturnType<typeof atomKey>) => Object.freeze({ referenceType, role, target })

const atom = (lineageId: string, kind: string, owner: string, atomUid: string, content: Uint8Array, references: ReadonlyArray<ReturnType<typeof reference>>) => Object.freeze({
  _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: atomKey(lineageId, atomUid), kind, responsibilityOwner: owner,
  content: Object.freeze({ mediaType: "application/json", byteLength: content.byteLength, sha256: sha256(content) }),
  provenance: Object.freeze({ mode: "BOOTSTRAP", evidenceSha256: sha256(content), sourceRef: null }), lifecycle: "ADMITTED", references
})

interface D4States { readonly pre: Uint8Array; readonly post: Uint8Array; readonly dispositionKey: string }
const constructStates = (occurrenceUid: string, input: D4Payloads): Effect.Effect<D4States, ProcessRefusal> => Effect.gen(function* () {
  if (!occurrenceBoundPayloads(input, occurrenceUid)) return yield* Effect.fail(refuse("D4 instance, trajectory, outcome, and credit must bind the requested occurrence UID"))
  const taskBody = yield* boundedBytes(input.task, "task payload")
  const instanceBody = yield* boundedBytes(input.instance, "training instance payload")
  const trajectoryBody = yield* boundedBytes(input.trajectory, "trajectory payload")
  const outcomeBody = yield* boundedBytes(input.outcome, "outcome payload")
  const creditBody = yield* boundedBytes(input.credit, "credit payload")
  const dispositionBody = yield* boundedBytes(input.disposition, "disposition payload")
  const lineage = `lineage:d4:${occurrenceUid}`
  const task = atom(lineage, "d4-task-contract", "owner:d4:task", "task", taskBody, [])
  const instance = atom(lineage, "d4-training-instance", "owner:d4:instance", "instance", instanceBody, [reference("d4:task", "task", task.key)])
  const trajectory = atom(lineage, "d4-trajectory", "owner:d4:trajectory", "trajectory", trajectoryBody, [reference("d4:task", "task", task.key), reference("d4:instance", "instance", instance.key)])
  const outcome = atom(lineage, "d4-outcome", "owner:d4:outcome", "outcome", outcomeBody, [reference("d4:trajectory", "trajectory", trajectory.key)])
  const credit = atom(lineage, "d4-credit", "owner:d4:credit", "credit", creditBody, [reference("d4:outcome", "outcome", outcome.key)])
  const disposition = atom(lineage, "d4-disposition", "owner:d4:disposition", "disposition", dispositionBody, [reference("d4:credit", "credit", credit.key)])
  const atoms = [task, instance, trajectory, outcome, credit, disposition]
  const bodies = [taskBody, instanceBody, trajectoryBody, outcomeBody, creditBody, dispositionBody]
  const inlineContents = atoms.map((entry, index) => Object.freeze({ atomKey: keyId(entry.key), mediaType: "application/json", byteLength: bodies[index]!.byteLength, sha256: entry.content.sha256, bytesBase64Url: Buffer.from(bodies[index]!).toString("base64url") }))
  const pre = yield* boundedBytes({ status: D4_STUDY_STATUS, state: { schemaVersion: D4_STUDY_SCHEMA_V1, revision: 0, bootstrapClosed: false, atoms: [], acceptedTransitionIds: [] }, compiledDispositionKey: "", inlineContents: [] }, "D4 genesis")
  const post = yield* boundedBytes({ status: D4_STUDY_STATUS, state: { schemaVersion: D4_STUDY_SCHEMA_V1, revision: 1, bootstrapClosed: true, atoms, acceptedTransitionIds: [`transition:d4:${occurrenceUid}`] }, compiledDispositionKey: keyId(disposition.key), inlineContents }, "D4 post-state")
  const validated = validateD4StudyPostState(post)
  if (Either.isLeft(validated)) return yield* Effect.fail(refuse(`D4 payload closure is invalid: ${validated.left.message}`))
  return Object.freeze({ pre, post, dispositionKey: keyId(disposition.key) })
})

const freshRoot = (rootPath: string, trustSnapshotPath: string): Effect.Effect<void, ProcessRefusal, PosixFileSystem> => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  if (trustSnapshotPath !== join(rootPath, "trust-snapshot.json") || dirname(trustSnapshotPath) !== rootPath) return yield* Effect.fail(refuse("trust snapshot must be the fixed file inside the declared root"))
  const root = yield* fs.identity(rootPath, "d4-root").pipe(Effect.mapError(() => refuse("D4 root must already exist and be no-follow inspectable")))
  if (root.kind !== "DIRECTORY") return yield* Effect.fail(refuse("D4 root must be a non-symlink directory"))
  const resolved = yield* fs.realpath(rootPath, "d4-root").pipe(Effect.mapError(() => refuse("D4 root must be realpath-resolvable")))
  if (resolved !== rootPath) return yield* Effect.fail(refuse("D4 root must be supplied as its real no-follow path"))
  const entries = yield* fs.listDirectory(rootPath, "d4-root").pipe(Effect.mapError(() => refuse("cannot inspect D4 root")))
  if (entries.length !== 0) return yield* Effect.fail(refuse("D4 root must be fresh and empty"))
})

const commit = (request: CommitRequest): Effect.Effect<CanonicalJson, ProcessRefusal | LocalPermitCommitError | VerifiedAdmissionGatewayError, PosixFileSystem> => Effect.gen(function* () {
  yield* freshRoot(request.rootPath, request.trustSnapshotPath)
  const states = yield* constructStates(request.occurrenceUid, request.payloads)
  const issuer = makeEphemeralLocalPermitIssuer({ keyId: `key:d4:${request.occurrenceUid}`, authorizer: "principal:d4-study", policyVersion: HSWM_D4_STUDY_PROCESS_V1, revocationEpoch: 0 })
  if (Either.isLeft(issuer)) return yield* Effect.fail(refuse(`cannot mint D4 ephemeral issuer: ${issuer.left.detail}`))
  const nonce = issuer.right.mintNonce()
  if (Either.isLeft(nonce)) return yield* Effect.fail(refuse(`cannot mint D4 nonce: ${nonce.left.detail}`))
  const priorHead = Object.freeze({ lineageId: `lineage:d4:${request.occurrenceUid}`, sequence: 0, stateDigest: sha256(states.pre), recordDigest: "0".repeat(64) })
  const expectedNextHead = Object.freeze({ lineageId: priorHead.lineageId, sequence: 1, stateDigest: sha256(states.post), recordDigest: sha256(new TextEncoder().encode(`d4:${request.occurrenceUid}:${sha256(states.post)}`)) })
  const proposalDigest = yield* canonicalDigest({
    contractVersion: HSWM_D4_STUDY_PROCESS_V1, occurrenceUid: request.occurrenceUid, mode: "ACTIVE",
    payloads: { task: request.payloads.task, instance: request.payloads.instance, trajectory: request.payloads.trajectory, outcome: request.payloads.outcome, credit: request.payloads.credit, disposition: request.payloads.disposition }
  }, "D4 proposal")
  const transitionInvariantDigest = yield* canonicalDigest({
    studySchemaVersion: D4_STUDY_SCHEMA_V1, studyStatus: D4_STUDY_STATUS,
    stateTransition: { fromStateRevision: 0, toStateRevision: 1, targetAtomInitialRevision: 0, targetMustBeAbsentBeforeCommit: true },
    postStateSha256: sha256(states.post)
  }, "D4 transition invariant")
  const issued = issuer.right.issue({
    permitId: `permit:d4:${request.occurrenceUid}`, executionId: `execution:d4:${request.occurrenceUid}`,
    executionIntentDigest: sha256(states.post), permitDigest: sha256(new TextEncoder().encode(`permit:${request.occurrenceUid}:${proposalDigest}`)), proposalDigest, transitionInvariantDigest,
    priorHead, expectedNextHead, target: { schemaVersion: D4_STUDY_SCHEMA_V1, lineageId: priorHead.lineageId, atomUid: "disposition" }, expectedRevision: "revision:absent", candidateRevision: "revision:0", authorizationRef: "authorization:d4-study", scope: "scope:d4-active", nonceDigest: nonce.right.nonceDigest, linearizationIndex: 1
  }, request.lifetimeMs)
  if (Either.isLeft(issued)) return yield* Effect.fail(refuse(`cannot issue D4 Permit: ${issued.left.detail}`))
  const fs = yield* PosixFileSystem
  yield* fs.writeExclusive(request.trustSnapshotPath, issuer.right.trustSnapshotBytes, { mode: 0o600, sync: true, operation: "d4-trust-snapshot" }).pipe(Effect.mapError(() => refuse("cannot write exclusive D4 public trust snapshot")))
  yield* fs.syncDirectory(request.rootPath, "d4-root").pipe(Effect.mapError(() => refuse("cannot fsync D4 root after trust snapshot")))
  const gateway = makeD4StudyAdmissionGateway(request.rootPath, issuer.right, { leanExecutable: request.leanExecutable })
  if (Either.isLeft(gateway)) return yield* Effect.fail(gateway.left)
  const receipt = yield* gateway.right.submit({ envelopeBytes: issued.right.envelopeBytes, expectedBindings: issued.right.expectedBindings, preStateBytes: states.pre, postStateBytes: states.post })
  return Object.freeze({ contractVersion: HSWM_D4_STUDY_PROCESS_V1, operation: "commit", occurrenceUid: request.occurrenceUid, mode: "ACTIVE", postStateBase64Url: Buffer.from(states.post).toString("base64url"), postStateSha256: sha256(states.post), head: receipt.commit.expectedNextHead, leanRequestSha256: receipt.decision.requestSha256, leanDecisionSha256: receipt.decision.decisionSha256, trustSnapshotSha256: sha256(issuer.right.trustSnapshotBytes), commitRecordSha256: receipt.commit.recordSha256, claimBoundary: HSWM_D4_STUDY_PROCESS_CLAIM_BOUNDARY }) as unknown as CanonicalJson
})

const recover = (request: RecoverRequest): Effect.Effect<CanonicalJson, ProcessRefusal | LocalPermitCommitError | VerifiedAdmissionGatewayError, PosixFileSystem> => Effect.gen(function* () {
  const fs = yield* PosixFileSystem
  const root = yield* fs.identity(request.rootPath, "d4-root").pipe(Effect.mapError(() => refuse("D4 recovery root must be no-follow inspectable")))
  if (root.kind !== "DIRECTORY") return yield* Effect.fail(refuse("D4 recovery root must be a non-symlink directory"))
  if (request.trustSnapshotPath !== join(request.rootPath, "trust-snapshot.json")) return yield* Effect.fail(refuse("trust snapshot must be the fixed file inside the declared root"))
  const trust = yield* fs.readRegularBounded(request.trustSnapshotPath, { maximumBytes: MAX_TRUST_SNAPSHOT_BYTES, minimumBytes: 1, requiredMode: 0o600, operation: "d4-trust-snapshot" }).pipe(Effect.mapError(() => refuse("cannot read bounded D4 public trust snapshot")))
  const verifier = makeLocalPermitVerifierContext(trust.bytes)
  if (Either.isLeft(verifier)) return yield* Effect.fail(refuse("D4 public trust snapshot is invalid"))
  const gateway = makeD4StudyAdmissionGateway(request.rootPath, verifier.right, { leanExecutable: request.leanExecutable })
  if (Either.isLeft(gateway)) return yield* Effect.fail(gateway.left)
  const recovered = yield* gateway.right.recover()
  if (recovered.commits.length !== 1 || recovered.head === null || recovered.head.sequence !== 1) return yield* Effect.fail(refuse("D4 recovery requires exactly one admitted V2 commit"))
  const expectedLineage = `lineage:d4:${request.occurrenceUid}`
  if (recovered.head.lineageId !== expectedLineage) return yield* Effect.fail(refuse("D4 recovery occurrence UID does not bind the recovered head lineage"))
  const post = recovered.commits[0]!.commit.postStateBytes
  const validated = validateD4StudyPostState(post)
  if (Either.isLeft(validated) || validated.right.state.revision !== 1) return yield* Effect.fail(refuse("D4 recovered post-state is invalid"))
  const recoveredPayload = (kind: string): Record<string, unknown> | null => {
    const atom = validated.right.state.atoms.find((entry) => entry.kind === kind)
    if (atom === undefined) return null
    const entry = validated.right.inlineContents.find((item) => item.atomKey === `${atom.key.schemaVersion}|${atom.key.lineageId}|${atom.key.atomUid}|${atom.key.revisionId}`)
    if (entry === undefined) return null
    const decoded = decodeCanonicalJsonBytes(Uint8Array.from(Buffer.from(entry.bytesBase64Url, "base64url")))
    return Either.isRight(decoded) ? object(decoded.right) : null
  }
  const instance = recoveredPayload("d4-training-instance")
  const trajectory = recoveredPayload("d4-trajectory")
  const outcome = recoveredPayload("d4-outcome")
  const credit = recoveredPayload("d4-credit")
  if (instance?.["occurrence_uid"] !== request.occurrenceUid || trajectory?.["occurrence_uid"] !== request.occurrenceUid || outcome?.["occurrence_uid"] !== request.occurrenceUid || credit?.["origin_occurrence_uid"] !== request.occurrenceUid) return yield* Effect.fail(refuse("D4 recovery occurrence UID does not bind recovered payload lineage"))
  const entry = validated.right.inlineContents.find((item) => item.atomKey === validated.right.compiledDispositionKey)
  if (entry === undefined) return yield* Effect.fail(refuse("D4 recovered disposition content is absent"))
  return Object.freeze({ contractVersion: HSWM_D4_STUDY_PROCESS_V1, operation: "recover", occurrenceUid: request.occurrenceUid, postStateBase64Url: Buffer.from(post).toString("base64url"), postStateSha256: sha256(post), head: recovered.head, compiledDispositionKey: validated.right.compiledDispositionKey, compiledDispositionBase64Url: entry.bytesBase64Url, compiledDispositionSha256: entry.sha256, trustSnapshotSha256: sha256(trust.bytes), claimBoundary: HSWM_D4_STUDY_PROCESS_CLAIM_BOUNDARY }) as unknown as CanonicalJson
})

export type D4StudyProcessError = ProcessRefusal | LocalPermitCommitError | VerifiedAdmissionGatewayError
export const executeD4StudyProcess = (request: CanonicalJson): Effect.Effect<CanonicalJson, D4StudyProcessError, PosixFileSystem> => Effect.gen(function* () {
  const decoded = yield* decodeRequest(request)
  return yield* (decoded.operation === "commit" ? commit(decoded) : recover(decoded))
})
export const describeD4StudyProcessFailure = (error: D4StudyProcessError): string => error._tag === "ProcessRefusal" ? error.detail : `${error.code}: ${error.detail}`
export const runD4StudyProcess = (): Promise<number> => runProcessMain({ refusalPrefix: "HSWM_D4_STUDY_REFUSED", program: executeD4StudyProcess, describeFailure: describeD4StudyProcessFailure })

const invokedPath = process.argv[1]
if (invokedPath !== undefined && import.meta.url === pathToFileURL(invokedPath).href) void runD4StudyProcess().then((exitCode) => { process.exitCode = exitCode })
