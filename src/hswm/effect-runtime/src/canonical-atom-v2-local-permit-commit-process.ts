#!/usr/bin/env node
/**
 * One-request CLI bridge for the v1 local Permit commit.
 *
 * A Python research instrument (g1_micro) hands one exact state transition to
 * this process: pre-state bytes, post-state bytes, and the Permit claims that
 * bind them.  The process mints one ephemeral Ed25519 issuer, issues one
 * signed Permit envelope, and commits it through the fsync'd no-replace local
 * journal slot.  The ephemeral private key never leaves this process; the
 * public trust snapshot is written beside the journal so a later process can
 * recover and re-verify every committed record.
 *
 * This is the real local owner/Permit admission path for one transition.  It
 * is not an authoritative, distributed, or trusted-time Permit, not canonical
 * HSWM admission, not outcome truth, causal credit, learning, or efficacy.
 */
import { open, readFile } from "node:fs/promises"
import { constants } from "node:fs"
import { createHash } from "node:crypto"
import { isAbsolute } from "node:path"
import { pathToFileURL } from "node:url"

import { Effect, Either } from "effect"

import { canonicalJsonBytes, decodeCanonicalJsonBytes, type CanonicalJson } from "./canonical-atom-v2-json.js"
import {
  HSWM_LOCAL_PERMIT_COMMIT_STATUS,
  makeEphemeralLocalPermitIssuer,
  makeLocalPermitCommitStore,
  makeLocalPermitVerifierContext,
  type LocalPermitCommitReceipt
} from "./canonical-atom-v2-local-permit-commit.js"
import type { CanonicalPermitHeadBinding, CanonicalPermitTargetBinding } from "./canonical-atom-v2-permit-envelope.js"

export const HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION =
  "hswm-local-permit-commit-process/v1" as const
export const HSWM_LOCAL_PERMIT_COMMIT_PROCESS_CLAIM_BOUNDARY =
  "ONE_SHOT_LOCAL_EPHEMERAL_KEY_PERMIT_COMMIT_OF_ONE_EXACT_STATE_TRANSITION_NOT_AUTHORITATIVE_NOT_DISTRIBUTED_NOT_TRUSTED_TIME_NOT_CANONICAL_HSWM_ADMISSION_NOT_OUTCOME_TRUTH_NOT_CAUSAL_CREDIT_NOT_LEARNING_NOT_EFFICACY" as const

const MAX_INPUT_BYTES = 1_048_576
const MAX_STATE_BYTES = 262_144
const Identifier = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/
const Digest = /^[0-9a-f]{64}$/

type JsonObject = Readonly<Record<string, CanonicalJson>>

class ProcessRefusal extends Error {
  constructor(readonly detail: string) {
    super(detail)
    this.name = "LocalPermitCommitProcessRefusal"
  }
}

const digest = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")

const asObject = (value: CanonicalJson | undefined, label: string): JsonObject => {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ProcessRefusal(`${label} must be an object`)
  }
  return value as JsonObject
}

const exactKeys = (value: JsonObject, expected: ReadonlyArray<string>, label: string): void => {
  const actual = Object.keys(value).sort()
  const sorted = [...expected].sort()
  if (actual.length !== sorted.length || actual.some((key, index) => key !== sorted[index])) {
    throw new ProcessRefusal(`${label} has missing or excess fields`)
  }
}

const identifier = (value: CanonicalJson | undefined, label: string): string => {
  if (typeof value !== "string" || !Identifier.test(value)) {
    throw new ProcessRefusal(`${label} must be a bounded identifier`)
  }
  return value
}

const sha256Hex = (value: CanonicalJson | undefined, label: string): string => {
  if (typeof value !== "string" || !Digest.test(value)) {
    throw new ProcessRefusal(`${label} must be a lowercase SHA-256 hex digest`)
  }
  return value
}

const safeInteger = (value: CanonicalJson | undefined, label: string, minimum = 0): number => {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < minimum) {
    throw new ProcessRefusal(`${label} must be a safe integer >= ${minimum}`)
  }
  return value
}

const absolutePath = (value: CanonicalJson | undefined, label: string): string => {
  if (typeof value !== "string" || value.length < 1 || value.length > 4096 || value.includes("\0")) {
    throw new ProcessRefusal(`${label} must be a bounded path`)
  }
  if (!isAbsolute(value)) throw new ProcessRefusal(`${label} must be absolute`)
  return value
}

const stateBytes = (value: CanonicalJson | undefined, label: string): Uint8Array => {
  if (typeof value !== "string" || value.length < 1) throw new ProcessRefusal(`${label} must be base64url text`)
  const decoded = Uint8Array.from(Buffer.from(value, "base64url"))
  if (decoded.byteLength < 1 || decoded.byteLength > MAX_STATE_BYTES || Buffer.from(decoded).toString("base64url") !== value) {
    throw new ProcessRefusal(`${label} must be nonempty, bounded, canonical base64url`)
  }
  return decoded
}

const parseHead = (value: CanonicalJson | undefined, label: string): CanonicalPermitHeadBinding => {
  const input = asObject(value, label)
  exactKeys(input, ["lineageId", "recordDigest", "sequence", "stateDigest"], label)
  return Object.freeze({
    lineageId: identifier(input["lineageId"], `${label}.lineageId`),
    sequence: safeInteger(input["sequence"], `${label}.sequence`),
    stateDigest: sha256Hex(input["stateDigest"], `${label}.stateDigest`),
    recordDigest: sha256Hex(input["recordDigest"], `${label}.recordDigest`)
  })
}

const parseTarget = (value: CanonicalJson | undefined): CanonicalPermitTargetBinding => {
  const input = asObject(value, "claims.target")
  exactKeys(input, ["atomUid", "lineageId", "schemaVersion"], "claims.target")
  return Object.freeze({
    schemaVersion: identifier(input["schemaVersion"], "claims.target.schemaVersion"),
    lineageId: identifier(input["lineageId"], "claims.target.lineageId"),
    atomUid: identifier(input["atomUid"], "claims.target.atomUid")
  })
}

interface ParsedClaims {
  readonly permitId: string
  readonly executionId: string
  readonly executionIntentDigest: string
  readonly permitDigest: string
  readonly proposalDigest: string
  readonly transitionInvariantDigest: string
  readonly priorHead: CanonicalPermitHeadBinding
  readonly expectedNextHead: CanonicalPermitHeadBinding
  readonly target: CanonicalPermitTargetBinding
  readonly expectedRevision: string
  readonly candidateRevision: string
  readonly authorizationRef: string
  readonly scope: string
  readonly linearizationIndex: number
}

const parseClaims = (value: CanonicalJson | undefined): ParsedClaims => {
  const input = asObject(value, "claims")
  exactKeys(input, [
    "authorizationRef", "candidateRevision", "executionId", "executionIntentDigest", "expectedNextHead",
    "expectedRevision", "linearizationIndex", "permitDigest", "permitId", "priorHead", "proposalDigest",
    "scope", "target", "transitionInvariantDigest"
  ], "claims")
  return Object.freeze({
    permitId: identifier(input["permitId"], "claims.permitId"),
    executionId: identifier(input["executionId"], "claims.executionId"),
    executionIntentDigest: sha256Hex(input["executionIntentDigest"], "claims.executionIntentDigest"),
    permitDigest: sha256Hex(input["permitDigest"], "claims.permitDigest"),
    proposalDigest: sha256Hex(input["proposalDigest"], "claims.proposalDigest"),
    transitionInvariantDigest: sha256Hex(input["transitionInvariantDigest"], "claims.transitionInvariantDigest"),
    priorHead: parseHead(input["priorHead"], "claims.priorHead"),
    expectedNextHead: parseHead(input["expectedNextHead"], "claims.expectedNextHead"),
    target: parseTarget(input["target"]),
    expectedRevision: identifier(input["expectedRevision"], "claims.expectedRevision"),
    candidateRevision: identifier(input["candidateRevision"], "claims.candidateRevision"),
    authorizationRef: identifier(input["authorizationRef"], "claims.authorizationRef"),
    scope: identifier(input["scope"], "claims.scope"),
    linearizationIndex: safeInteger(input["linearizationIndex"], "claims.linearizationIndex")
  })
}

const headJson = (head: CanonicalPermitHeadBinding): JsonObject => Object.freeze({
  lineageId: head.lineageId, sequence: head.sequence, stateDigest: head.stateDigest, recordDigest: head.recordDigest
})

const receiptJson = (receipt: LocalPermitCommitReceipt): JsonObject => Object.freeze({
  recordSha256: receipt.recordSha256,
  slotPath: receipt.slotPath,
  nonceDigest: receipt.nonceDigest,
  executionIntentDigest: receipt.executionIntentDigest,
  priorHead: headJson(receipt.priorHead),
  expectedNextHead: headJson(receipt.expectedNextHead),
  verificationTime: receipt.verificationTime,
  postStateSha256: digest(receipt.postStateBytes),
  status: receipt.status
})

const writeExclusive = async (path: string, bytes: Uint8Array): Promise<void> => {
  const handle = await open(path, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600)
  try {
    await handle.writeFile(bytes)
    await handle.sync()
  } finally {
    await handle.close()
  }
}

const runEffect = async <A, E extends { readonly code: string; readonly detail: string }>(effect: Effect.Effect<A, E>): Promise<A> => {
  const exit = await Effect.runPromiseExit(effect)
  if (exit._tag === "Success") return exit.value
  const cause = exit.cause
  if (cause._tag === "Fail") throw new ProcessRefusal(`${cause.error.code}: ${cause.error.detail}`)
  throw new ProcessRefusal("local Permit commit effect died")
}

const executeCommit = async (input: JsonObject): Promise<JsonObject> => {
  exactKeys(input, [
    "claims", "contractVersion", "issuer", "lifetimeMs", "operation", "postStateBase64Url",
    "preStateBase64Url", "rootPath", "trustSnapshotPath"
  ], "request")
  const rootPath = absolutePath(input["rootPath"], "rootPath")
  const trustSnapshotPath = absolutePath(input["trustSnapshotPath"], "trustSnapshotPath")
  const issuerInput = asObject(input["issuer"], "issuer")
  exactKeys(issuerInput, ["authorizer", "keyId", "policyVersion", "revocationEpoch"], "issuer")
  const lifetimeMs = safeInteger(input["lifetimeMs"], "lifetimeMs", 1)
  const claims = parseClaims(input["claims"])
  const preState = stateBytes(input["preStateBase64Url"], "preStateBase64Url")
  const postState = stateBytes(input["postStateBase64Url"], "postStateBase64Url")
  if (digest(preState) !== claims.priorHead.stateDigest) {
    throw new ProcessRefusal("pre-state bytes do not match claims.priorHead.stateDigest")
  }
  if (digest(postState) !== claims.expectedNextHead.stateDigest) {
    throw new ProcessRefusal("post-state bytes do not match claims.expectedNextHead.stateDigest")
  }
  if (claims.priorHead.sequence !== 0 || claims.expectedNextHead.sequence !== 1) {
    throw new ProcessRefusal("this one-shot bridge commits exactly the sequence-zero to sequence-one transition")
  }
  const issuer = makeEphemeralLocalPermitIssuer({
    keyId: identifier(issuerInput["keyId"], "issuer.keyId"),
    authorizer: identifier(issuerInput["authorizer"], "issuer.authorizer"),
    policyVersion: identifier(issuerInput["policyVersion"], "issuer.policyVersion"),
    revocationEpoch: safeInteger(issuerInput["revocationEpoch"], "issuer.revocationEpoch")
  })
  if (Either.isLeft(issuer)) throw new ProcessRefusal(`${issuer.left.code}: ${issuer.left.detail}`)
  const minted = issuer.right.mintNonce()
  if (Either.isLeft(minted)) throw new ProcessRefusal(`${minted.left.code}: ${minted.left.detail}`)
  const issued = issuer.right.issue({ ...claims, nonceDigest: minted.right.nonceDigest }, lifetimeMs)
  if (Either.isLeft(issued)) throw new ProcessRefusal(`${issued.left.code}: ${issued.left.detail}`)
  try {
    await writeExclusive(trustSnapshotPath, issuer.right.trustSnapshotBytes)
  } catch (cause) {
    const code = typeof cause === "object" && cause !== null && "code" in cause ? String(cause.code) : ""
    throw new ProcessRefusal(code === "EEXIST"
      ? "trust snapshot path already exists; one bridge process owns one fresh root"
      : "cannot write the public trust snapshot beside the local journal")
  }
  const store = makeLocalPermitCommitStore(rootPath, issuer.right)
  const receipt = await runEffect(store.commit({
    envelopeBytes: issued.right.envelopeBytes,
    expectedBindings: issued.right.expectedBindings,
    preStateBytes: preState,
    postStateBytes: postState
  }))
  return Object.freeze({
    _tag: "LocalPermitCommitProcessResult",
    contractVersion: HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION,
    operation: "commit",
    receipt: receiptJson(receipt),
    envelopeSha256: digest(issued.right.envelopeBytes),
    envelopeBytesBase64Url: Buffer.from(issued.right.envelopeBytes).toString("base64url"),
    trustSnapshotPath,
    trustSnapshotSha256: digest(issuer.right.trustSnapshotBytes),
    preStateSha256: digest(preState),
    postStateSha256: digest(postState),
    commitStatus: HSWM_LOCAL_PERMIT_COMMIT_STATUS,
    claimBoundary: HSWM_LOCAL_PERMIT_COMMIT_PROCESS_CLAIM_BOUNDARY
  })
}

const executeRecover = async (input: JsonObject): Promise<JsonObject> => {
  exactKeys(input, ["contractVersion", "operation", "rootPath", "trustSnapshotPath"], "request")
  const rootPath = absolutePath(input["rootPath"], "rootPath")
  const trustSnapshotPath = absolutePath(input["trustSnapshotPath"], "trustSnapshotPath")
  let trustBytes: Uint8Array
  try {
    trustBytes = Uint8Array.from(await readFile(trustSnapshotPath))
  } catch {
    throw new ProcessRefusal("cannot read the public trust snapshot")
  }
  const verifier = makeLocalPermitVerifierContext(trustBytes)
  if (Either.isLeft(verifier)) throw new ProcessRefusal(`${verifier.left.code}: ${verifier.left.detail}`)
  const recovered = await runEffect(makeLocalPermitCommitStore(rootPath, verifier.right).recover())
  return Object.freeze({
    _tag: "LocalPermitCommitProcessResult",
    contractVersion: HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION,
    operation: "recover",
    commits: recovered.commits.map(receiptJson),
    head: recovered.head === null ? null : headJson(recovered.head),
    trustSnapshotPath,
    trustSnapshotSha256: digest(trustBytes),
    commitStatus: recovered.status,
    claimBoundary: HSWM_LOCAL_PERMIT_COMMIT_PROCESS_CLAIM_BOUNDARY
  })
}

export const executeLocalPermitCommitProcess = async (request: CanonicalJson): Promise<JsonObject> => {
  const input = asObject(request, "request")
  if (input["contractVersion"] !== HSWM_LOCAL_PERMIT_COMMIT_PROCESS_V1_CONTRACT_VERSION) {
    throw new ProcessRefusal("request contract version is not supported")
  }
  const operation = input["operation"]
  if (operation === "commit") return executeCommit(input)
  if (operation === "recover") return executeRecover(input)
  throw new ProcessRefusal("operation must be commit or recover")
}

const output = (value: unknown): string => {
  const encoded = canonicalJsonBytes(value as CanonicalJson)
  if (Either.isLeft(encoded)) throw new ProcessRefusal("process output cannot form canonical JSON")
  return `${new TextDecoder().decode(encoded.right)}\n`
}

export const runLocalPermitCommitProcess = async (stdin: string): Promise<number> => {
  try {
    if (Buffer.byteLength(stdin, "utf8") > MAX_INPUT_BYTES) {
      throw new ProcessRefusal("stdin exceeds the bounded canonical JSON limit")
    }
    const decoded = decodeCanonicalJsonBytes(new TextEncoder().encode(stdin))
    if (Either.isLeft(decoded)) throw new ProcessRefusal("stdin must be canonical JSON")
    process.stdout.write(output(await executeLocalPermitCommitProcess(decoded.right)))
    return 0
  } catch (error) {
    const detail = error instanceof Error ? error.message : "unknown local Permit commit refusal"
    process.stderr.write(`HSWM_LOCAL_PERMIT_COMMIT_REFUSED: ${detail}\n`)
    return 2
  }
}

const invokedPath = process.argv[1]
if (invokedPath !== undefined && import.meta.url === pathToFileURL(invokedPath).href) {
  let source = ""
  process.stdin.setEncoding("utf8")
  process.stdin.on("data", (chunk: string) => {
    source += chunk
    if (Buffer.byteLength(source, "utf8") > MAX_INPUT_BYTES) process.stdin.pause()
  })
  process.stdin.once("end", () => {
    void runLocalPermitCommitProcess(source).then((exitCode) => {
      process.exitCode = exitCode
    })
  })
  process.stdin.once("error", () => {
    process.stderr.write("HSWM_LOCAL_PERMIT_COMMIT_REFUSED: stdin read failure\n")
    process.exitCode = 2
  })
}
