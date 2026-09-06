import { createHash } from "node:crypto"
import { Effect, Either } from "effect"

import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import { validateCanonicalAtomV2State, validateHSWMCanonicalSchemaV2, type CanonicalAtomV2State } from "./canonical-atom-v2-domain.js"
import { canonicalAtomV2KeyId, type HSWMCanonicalSchemaV2 } from "./canonical-atom-v2-schema.js"
import { LocalPermitCommitError, type LocalPermitCommitRequest, type LocalPermitVerifierContext, type VerifiedAdmissionRecoveryV2 } from "./canonical-atom-v2-local-permit-commit.js"
import { makeVerifiedAdmissionGatewayV2, type VerifiedAdmissionGatewayConfig, type VerifiedAdmissionGatewayError, type VerifiedAdmissionGatewayV2Receipt } from "./canonical-atom-v2-verified-admission-gateway.js"

/** A study-local D4 schema, never a declaration of HSWM-wide admission. */
export const D4_STUDY_SCHEMA_V1 = "hswm:d4:declared-study-canonical:v1" as const
export const D4_STUDY_STATUS = "G0_LOCAL_DECLARED_STUDY_CANONICAL_ONLY_NOT_HSWM_WIDE_ADMISSION" as const
const sha256 = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex")
const isSha = (value: unknown): value is string => typeof value === "string" && /^[0-9a-f]{64}$/.test(value)
const exact = (value: Record<string, unknown>, keys: ReadonlyArray<string>): boolean => Object.keys(value).sort().join("|") === [...keys].sort().join("|")
const canonicalDigest = (value: unknown): string | undefined => { const encoded = canonicalJsonBytes(value); return Either.isRight(encoded) ? sha256(encoded.right) : undefined }
const genesisDigest = canonicalDigest({
  status: D4_STUDY_STATUS,
  state: { schemaVersion: D4_STUDY_SCHEMA_V1, revision: 0, bootstrapClosed: false, atoms: [], acceptedTransitionIds: [] },
  compiledDispositionKey: "", inlineContents: []
})

export const d4StudySchema = (): HSWMCanonicalSchemaV2 => ({
  _tag: "HSWMCanonicalSchemaV2", contractVersion: "hswm-canonical-schema-contract/v2",
  schemaVersion: D4_STUDY_SCHEMA_V1, scientificStatus: "UNJUDGED",
  bootstrapTrustStatement: "Secondary-AI declared-study schema; no HSWM-wide canonical admission.",
  owners: [
    { address: "owner:d4:task", obligation: "task-contract" }, { address: "owner:d4:instance", obligation: "training-instance" }, { address: "owner:d4:trajectory", obligation: "trajectory-seal" },
    { address: "owner:d4:outcome", obligation: "outcome-observation" }, { address: "owner:d4:credit", obligation: "credit-decision" },
    { address: "owner:d4:disposition", obligation: "disposition-revision" }
  ],
  kinds: [
    { kind: "d4-task-contract", form: "ENTITY", revisionPolicy: "SINGLETON", allowedOwners: ["owner:d4:task"], minimumArity: 0, referenceContracts: [] },
    { kind: "d4-training-instance", form: "RELATION", revisionPolicy: "SINGLETON", allowedOwners: ["owner:d4:instance"], minimumArity: 1, referenceContracts: [{ referenceType: "d4:task", roles: [{ role: "task", targetKinds: ["d4-task-contract"], minimum: 1, maximum: 1 }] }] },
    { kind: "d4-trajectory", form: "RELATION", revisionPolicy: "SINGLETON", allowedOwners: ["owner:d4:trajectory"], minimumArity: 2, referenceContracts: [{ referenceType: "d4:task", roles: [{ role: "task", targetKinds: ["d4-task-contract"], minimum: 1, maximum: 1 }] }, { referenceType: "d4:instance", roles: [{ role: "instance", targetKinds: ["d4-training-instance"], minimum: 1, maximum: 1 }] }] },
    { kind: "d4-outcome", form: "RELATION", revisionPolicy: "SINGLETON", allowedOwners: ["owner:d4:outcome"], minimumArity: 1, referenceContracts: [{ referenceType: "d4:trajectory", roles: [{ role: "trajectory", targetKinds: ["d4-trajectory"], minimum: 1, maximum: 1 }] }] },
    { kind: "d4-credit", form: "RELATION", revisionPolicy: "SINGLETON", allowedOwners: ["owner:d4:credit"], minimumArity: 1, referenceContracts: [{ referenceType: "d4:outcome", roles: [{ role: "outcome", targetKinds: ["d4-outcome"], minimum: 1, maximum: 1 }] }] },
    { kind: "d4-disposition", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: ["owner:d4:disposition"], minimumArity: 1, referenceContracts: [{ referenceType: "d4:credit", roles: [{ role: "credit", targetKinds: ["d4-credit"], minimum: 1, maximum: 1 }] }, { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["d4-disposition"], minimum: 0, maximum: 1 }] }] }
  ]
})

export interface D4InlineContent { readonly atomKey: string; readonly mediaType: string; readonly byteLength: number; readonly sha256: string; readonly bytesBase64Url: string }
export interface D4StudyPostState { readonly status: typeof D4_STUDY_STATUS; readonly state: CanonicalAtomV2State; readonly compiledDispositionKey: string; readonly inlineContents: ReadonlyArray<D4InlineContent> }
export type D4StudyValidation = Either.Either<D4StudyPostState, Error>
const fail = (message: string): D4StudyValidation => Either.left(new Error(message))

/** Semantic validator for gateway V2 post-state/recovery bytes. */
export const validateD4StudyPostState = (bytes: Uint8Array): D4StudyValidation => {
  const decoded = decodeCanonicalJsonBytes(bytes)
  if (Either.isLeft(decoded) || typeof decoded.right !== "object" || decoded.right === null) return fail("D4 post-state is not canonical JSON")
  const value = decoded.right as Record<string, unknown>
  if (Object.keys(value).sort().join("|") !== "compiledDispositionKey|inlineContents|state|status" || value["status"] !== D4_STUDY_STATUS || typeof value["compiledDispositionKey"] !== "string" || !Array.isArray(value["inlineContents"])) return fail("D4 post-state envelope is invalid")
  const schema = d4StudySchema(); const checkedSchema = validateHSWMCanonicalSchemaV2(schema)
  if (Either.isLeft(checkedSchema)) return fail("D4 schema is invalid")
  const state = validateCanonicalAtomV2State(checkedSchema.right, value["state"])
  if (Either.isLeft(state)) return fail(`D4 canonical state rejected: ${state.left.code}:${state.left.detail}`)
  if (state.right.revision > 0) {
    const kinds = ["d4-task-contract", "d4-training-instance", "d4-trajectory", "d4-outcome", "d4-credit", "d4-disposition"]
    if (!state.right.bootstrapClosed || state.right.atoms.length !== 6 || new Set(state.right.atoms.map((atom) => atom.kind)).size !== 6 || !kinds.every((kind) => state.right.atoms.filter((atom) => atom.kind === kind).length === 1)) return fail("D4 admitted state must contain exactly the six declared atoms")
    const lineage = state.right.atoms[0]?.key.lineageId
    if (!lineage || !state.right.atoms.every((atom) => atom.key.lineageId === lineage && atom.key.revisionId === 0) || !/^lineage:d4:[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/.test(lineage) || state.right.acceptedTransitionIds.length !== 1 || state.right.acceptedTransitionIds[0] !== `transition:d4:${lineage.slice("lineage:d4:".length)}`) return fail("D4 state lineage, atom revision, or transition binding is invalid")
  }
  const inline: D4InlineContent[] = []
  for (const item of value["inlineContents"]) {
    if (typeof item !== "object" || item === null) return fail("D4 inline content is invalid")
    const entry = item as Record<string, unknown>
    if (Object.keys(entry).sort().join("|") !== "atomKey|byteLength|bytesBase64Url|mediaType|sha256" || typeof entry["atomKey"] !== "string" || typeof entry["mediaType"] !== "string" || typeof entry["byteLength"] !== "number" || typeof entry["sha256"] !== "string" || typeof entry["bytesBase64Url"] !== "string") return fail("D4 inline content shape is invalid")
    let body: Uint8Array
    try { body = Uint8Array.from(Buffer.from(entry["bytesBase64Url"], "base64url")) } catch { return fail("D4 inline content encoding is invalid") }
    if (body.byteLength !== entry["byteLength"] || sha256(body) !== entry["sha256"] || Buffer.from(body).toString("base64url") !== entry["bytesBase64Url"]) return fail("D4 inline content digest is invalid")
    inline.push({ atomKey: entry["atomKey"], mediaType: entry["mediaType"], byteLength: entry["byteLength"], sha256: entry["sha256"], bytesBase64Url: entry["bytesBase64Url"] })
  }
  if (inline.length !== state.right.atoms.length || new Set(inline.map((entry) => entry.atomKey)).size !== inline.length) return fail("D4 needs exactly one immutable inline content body per atom")
  const contentByKey = new Map(inline.map((entry) => [entry.atomKey, entry] as const))
  for (const atom of state.right.atoms) {
    const entry = contentByKey.get(canonicalAtomV2KeyId(atom.key))
    if (!entry || entry.mediaType !== atom.content.mediaType || entry.byteLength !== atom.content.byteLength || entry.sha256 !== atom.content.sha256) return fail("D4 atom descriptor does not close over inline content")
  }
  const payload = (kind: string): Record<string, unknown> | undefined => {
    const atom = state.right.atoms.find((candidate) => candidate.kind === kind); if (!atom) return undefined
    const entry = contentByKey.get(canonicalAtomV2KeyId(atom.key)); if (!entry || entry.mediaType !== "application/json") return undefined
    const decodedPayload = decodeCanonicalJsonBytes(Uint8Array.from(Buffer.from(entry.bytesBase64Url, "base64url")))
    return Either.isRight(decodedPayload) && typeof decodedPayload.right === "object" && decodedPayload.right !== null ? decodedPayload.right as Record<string, unknown> : undefined
  }
  const task = payload("d4-task-contract"), instance = payload("d4-training-instance"), trajectory = payload("d4-trajectory"), outcome = payload("d4-outcome"), credit = payload("d4-credit"), dispositionPayload = payload("d4-disposition")
  const payloadHash = (kind: string): string | undefined => {
    const atom = state.right.atoms.find((candidate) => candidate.kind === kind)
    return atom ? contentByKey.get(canonicalAtomV2KeyId(atom.key))?.sha256 : undefined
  }
  const taskHash = payloadHash("d4-task-contract"), instanceHash = payloadHash("d4-training-instance"), trajectoryHash = payloadHash("d4-trajectory"), outcomeHash = payloadHash("d4-outcome"), creditHash = payloadHash("d4-credit")
  const selfDigest = (record: Record<string, unknown>, field: string): boolean => { const { [field]: claimed, ...body } = record; return isSha(claimed) && claimed === canonicalDigest(body) }
  const strictPayloads = !!task && !!instance && !!trajectory && !!outcome && !!credit && !!dispositionPayload && !!taskHash && !!instanceHash && !!trajectoryHash && !!outcomeHash && !!creditHash &&
    exact(task, ["action_schema", "compiler_source_sha256", "generator_source_sha256", "opaque_id_bytes", "schema_version", "selector_transform", "task_family"]) && task["action_schema"] === "hswm-d4-opaque-action/v1" && task["schema_version"] === "hswm-d4-opaque-binary-transform-task-contract/v1" && task["task_family"] === "hswm-d4-opaque-binary-transform/v1" && task["selector_transform"] === "target_bit=selector_bit XOR latent_bit" && task["opaque_id_bytes"] === 16 && isSha(task["generator_source_sha256"]) && isSha(task["compiler_source_sha256"]) &&
    exact(instance, ["action_codes", "occurrence_uid", "schema_version", "selector_bit", "split", "table_bits", "task_contract_sha256"]) && instance["schema_version"] === "hswm-d4-opaque-binary-transform-instance/v1" && instance["split"] === "TRAIN" && instance["task_contract_sha256"] === taskHash && typeof instance["occurrence_uid"] === "string" && /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/.test(instance["occurrence_uid"]) && (instance["selector_bit"] === 0 || instance["selector_bit"] === 1) && Array.isArray(instance["action_codes"]) && instance["action_codes"].length === 2 && new Set(instance["action_codes"]).size === 2 && (instance["action_codes"] as unknown[]).every((id) => typeof id === "string" && /^[a-f0-9]{32}$/.test(id)) && Array.isArray(instance["table_bits"]) && instance["table_bits"].length === 2 && (instance["table_bits"] as unknown[]).every((bit) => bit === 0 || bit === 1) && new Set(instance["table_bits"] as unknown[]).size === 2 &&
    exact(trajectory, ["action_id", "instance_sha256", "occurrence_uid", "schema_version", "trajectory_sha256"]) && trajectory["schema_version"] === "hswm-d4-opaque-binary-transform-trajectory/v1" && typeof trajectory["action_id"] === "string" && trajectory["instance_sha256"] === canonicalDigest(instance) && trajectory["occurrence_uid"] === instance["occurrence_uid"] && selfDigest(trajectory, "trajectory_sha256") &&
    exact(outcome, ["outcome", "occurrence_uid", "schema_version", "trajectory_sha256", "outcome_sha256"]) && outcome["schema_version"] === "hswm-d4-opaque-binary-transform-outcome/v1" && (outcome["outcome"] === "SUCCESS" || outcome["outcome"] === "FAILURE") && outcome["occurrence_uid"] === trajectory["occurrence_uid"] && outcome["trajectory_sha256"] === trajectory["trajectory_sha256"] && selfDigest(outcome, "outcome_sha256") &&
    exact(credit, ["candidate_theta", "origin_occurrence_uid", "outcome_sha256", "schema_version", "selected_bit", "selector_bit", "task_contract_sha256", "trajectory_sha256", "credit_sha256"]) && credit["schema_version"] === "hswm-d4-opaque-binary-transform-credit/v1" && credit["task_contract_sha256"] === taskHash && credit["trajectory_sha256"] === trajectory["trajectory_sha256"] && credit["outcome_sha256"] === outcome["outcome_sha256"] && credit["origin_occurrence_uid"] === trajectory["occurrence_uid"] && [credit["candidate_theta"], credit["selected_bit"], credit["selector_bit"]].every((bit) => bit === 0 || bit === 1) && selfDigest(credit, "credit_sha256") && credit["selector_bit"] === instance["selector_bit"] && credit["selected_bit"] === (instance["table_bits"] as unknown[])[(instance["action_codes"] as unknown[]).indexOf(trajectory["action_id"])] && credit["candidate_theta"] === ((credit["selected_bit"] as number) ^ (outcome["outcome"] === "SUCCESS" ? 0 : 1) ^ (credit["selector_bit"] as number)) &&
    exact(dispositionPayload, ["compiler_source_sha256", "credit_sha256", "generator_source_sha256", "latent_bit", "schema_version", "task_contract_sha256", "task_family", "transform"]) && dispositionPayload["schema_version"] === "hswm-d4-latent-bit-disposition/v1" && dispositionPayload["task_contract_sha256"] === taskHash && dispositionPayload["credit_sha256"] === credit["credit_sha256"] && dispositionPayload["generator_source_sha256"] === task["generator_source_sha256"] && dispositionPayload["compiler_source_sha256"] === task["compiler_source_sha256"] && dispositionPayload["task_family"] === "hswm-d4-opaque-binary-transform/v1" && dispositionPayload["transform"] === "XOR" && (dispositionPayload["latent_bit"] === 0 || dispositionPayload["latent_bit"] === 1) && dispositionPayload["latent_bit"] === credit["candidate_theta"]
  if (state.right.revision > 0 && !strictPayloads) return fail("D4 inline payload contract or lineage is invalid")
  const disposition = state.right.atoms.filter((atom) => atom.kind === "d4-disposition")
  if (state.right.revision === 0) {
    if (state.right.bootstrapClosed || state.right.atoms.length !== 0 || state.right.acceptedTransitionIds.length !== 0 || value["compiledDispositionKey"] !== "") return fail("D4 genesis must be the exact empty unclosed state")
  } else {
    // This declared study admits one immutable latent disposition per fresh
    // lineage. A later disposition needs a separately declared append schema.
    if (state.right.revision !== 1 || disposition.length !== 1) return fail("D4 admitted state requires the one-shot disposition state")
    if (canonicalAtomV2KeyId(disposition[0]!.key) !== value["compiledDispositionKey"]) return fail("D4 compiler key is not the admitted disposition")
  }
  return Either.right({ status: D4_STUDY_STATUS, state: state.right, compiledDispositionKey: value["compiledDispositionKey"], inlineContents: inline })
}

/**
 * The only D4 write surface: it snapshots caller bytes, validates the study
 * post-state before the Lean-gated V2 publication, and revalidates every
 * recovered post-state from that same immutable V2 journal.  It deliberately
 * exposes no generic canonical write operation.
 */
export interface D4StudyAdmissionGateway {
  readonly submit: (request: LocalPermitCommitRequest) => Effect.Effect<VerifiedAdmissionGatewayV2Receipt, LocalPermitCommitError | VerifiedAdmissionGatewayError>
  readonly recover: () => Effect.Effect<VerifiedAdmissionRecoveryV2, LocalPermitCommitError>
}

const invalidRequest = (detail: string): LocalPermitCommitError =>
  new LocalPermitCommitError({ code: "INPUT_INVALID", detail })

const validateD4Transition = (request: LocalPermitCommitRequest): Either.Either<void, LocalPermitCommitError> => {
  const pre = validateD4StudyPostState(request.preStateBytes)
  if (Either.isLeft(pre)) return Either.left(invalidRequest(`D4 pre-state rejected: ${pre.left.message}`))
  const post = validateD4StudyPostState(request.postStateBytes)
  if (Either.isLeft(post)) return Either.left(invalidRequest(post.left.message))
  if (pre.right.state.revision !== 0 || post.right.state.revision !== 1 || request.expectedBindings.priorHead.stateDigest !== createHash("sha256").update(request.preStateBytes).digest("hex") || request.expectedBindings.expectedNextHead.stateDigest !== createHash("sha256").update(request.postStateBytes).digest("hex")) return Either.left(invalidRequest("D4 requires the exact empty genesis to one-shot admitted-state transition"))
  const disposition = post.right.state.atoms.find((atom) => atom.kind === "d4-disposition")!
  if (request.expectedBindings.target.schemaVersion !== D4_STUDY_SCHEMA_V1 || request.expectedBindings.target.lineageId !== disposition.key.lineageId || request.expectedBindings.target.atomUid !== disposition.key.atomUid || request.expectedBindings.candidateRevision !== "revision:0" || request.expectedBindings.expectedRevision !== "revision:absent") return Either.left(invalidRequest("D4 Permit target and revision bindings must identify the admitted disposition"))
  return Either.right(undefined)
}

export const makeD4StudyAdmissionGateway = (
  rootPath: string,
  verifier: LocalPermitVerifierContext,
  config: VerifiedAdmissionGatewayConfig,
  clock: () => Date = () => new Date()
): Either.Either<D4StudyAdmissionGateway, VerifiedAdmissionGatewayError> => {
  const base = makeVerifiedAdmissionGatewayV2(rootPath, verifier, config, clock)
  if (Either.isLeft(base)) return base
  return Either.right(Object.freeze({
    submit: (request: LocalPermitCommitRequest) => {
      // Snapshot before an await/Effect boundary: caller mutation cannot alter
      // the bytes that semantic validation and the journal see.
      const frozen: LocalPermitCommitRequest = Object.freeze({
        envelopeBytes: Uint8Array.from(request.envelopeBytes), preStateBytes: Uint8Array.from(request.preStateBytes), postStateBytes: Uint8Array.from(request.postStateBytes),
        expectedBindings: Object.freeze({ ...request.expectedBindings, priorHead: Object.freeze({ ...request.expectedBindings.priorHead }), expectedNextHead: Object.freeze({ ...request.expectedBindings.expectedNextHead }), target: Object.freeze({ ...request.expectedBindings.target }) })
      })
      const checked = validateD4Transition(frozen)
      return Either.isLeft(checked) ? Effect.fail(checked.left) : base.right.submit(frozen)
    },
    recover: () => base.right.recover().pipe(Effect.flatMap((recovered) => {
      for (const item of recovered.commits) {
        const checked = validateD4StudyPostState(item.commit.postStateBytes)
        if (Either.isLeft(checked) || checked.right.state.revision !== 1
          || item.commit.priorHead.sequence !== 0 || item.commit.priorHead.stateDigest !== genesisDigest
          || item.commit.expectedNextHead.sequence !== 1
          || item.commit.expectedNextHead.lineageId !== checked.right.state.atoms[0]?.key.lineageId
          || item.commit.priorHead.lineageId !== item.commit.expectedNextHead.lineageId
          || item.commit.expectedNextHead.stateDigest !== sha256(item.commit.postStateBytes)) return Effect.fail(new LocalPermitCommitError({ code: "RECOVERY_INVALID", detail: "D4 recovered genesis, post-state or head binding rejected" }))
      }
      return Effect.succeed(recovered)
    }))
  }))
}
