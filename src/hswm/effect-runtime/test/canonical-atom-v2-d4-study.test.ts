import { createHash } from "node:crypto"
import { existsSync } from "node:fs"
import { join } from "node:path"

import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import { canonicalJsonBytes } from "../src/canonical-atom-v2-json.js"
import { canonicalAtomV2KeyId } from "../src/canonical-atom-v2-schema.js"
import { D4_STUDY_STATUS, validateD4StudyPostState } from "../src/canonical-atom-v2-d4-study.js"

const hex = (value: string) => value.repeat(64)
const hash = (value: Uint8Array) => createHash("sha256").update(value).digest("hex")
const leanCli = process.env["HSWM_D4_LEAN_EXECUTABLE"] ?? join(process.cwd(), "../../../formal/.lake/build/bin/HSWMAdmissionKernelCli")
const key = (atomUid: string) => ({ schemaVersion: "hswm:d4:declared-study-canonical:v1", lineageId: "lineage:d4:d4-fixture", atomUid, revisionId: 0 })
const ref = (referenceType: string, role: string, target: ReturnType<typeof key>) => ({ referenceType, role, target })
const bytes = (value: object) => { const encoded = canonicalJsonBytes(value); if (Either.isLeft(encoded)) throw encoded.left; return encoded.right }
const body = (value: object) => bytes(value)
const atom = (kind: string, owner: string, atomUid: string, payload: object, references: ReadonlyArray<object> = []) => {
  const content = body(payload)
  return { _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: key(atomUid), kind, responsibilityOwner: owner,
    content: { mediaType: "application/json", byteLength: content.byteLength, sha256: hash(content) }, provenance: { mode: "BOOTSTRAP", evidenceSha256: hex("b"), sourceRef: null }, lifecycle: "ADMITTED", references, _body: content }
}
const inline = (atoms: ReadonlyArray<ReturnType<typeof atom>>) => atoms.map((item) => ({ atomKey: canonicalAtomV2KeyId(item.key), mediaType: "application/json", byteLength: item._body.byteLength, sha256: hash(item._body), bytesBase64Url: Buffer.from(item._body).toString("base64url") }))
const closure = () => {
  const source = hex("c"), task = atom("d4-task-contract", "owner:d4:task", "task", { action_schema: "hswm-d4-opaque-action/v1", compiler_source_sha256: source, generator_source_sha256: source, opaque_id_bytes: 16, schema_version: "hswm-d4-opaque-binary-transform-task-contract/v1", selector_transform: "target_bit=selector_bit XOR latent_bit", task_family: "hswm-d4-opaque-binary-transform/v1" })
  const instance = atom("d4-training-instance", "owner:d4:instance", "instance", { action_codes: ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"], occurrence_uid: "d4-fixture", schema_version: "hswm-d4-opaque-binary-transform-instance/v1", selector_bit: 0, split: "TRAIN", table_bits: [0, 1], task_contract_sha256: task.content.sha256 }, [ref("d4:task", "task", task.key)])
  const trajectoryBody = { action_id: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", instance_sha256: instance.content.sha256, occurrence_uid: "d4-fixture", schema_version: "hswm-d4-opaque-binary-transform-trajectory/v1" }; const trajectorySeal = hash(bytes(trajectoryBody)); const trajectory = atom("d4-trajectory", "owner:d4:trajectory", "trajectory", { ...trajectoryBody, trajectory_sha256: trajectorySeal }, [ref("d4:task", "task", task.key), ref("d4:instance", "instance", instance.key)])
  const outcomeBody = { outcome: "FAILURE", occurrence_uid: "d4-fixture", schema_version: "hswm-d4-opaque-binary-transform-outcome/v1", trajectory_sha256: trajectorySeal }; const outcome = atom("d4-outcome", "owner:d4:outcome", "outcome", { ...outcomeBody, outcome_sha256: hash(bytes(outcomeBody)) }, [ref("d4:trajectory", "trajectory", trajectory.key)])
  const creditBody = { candidate_theta: 0, origin_occurrence_uid: "d4-fixture", outcome_sha256: hash(bytes(outcomeBody)), schema_version: "hswm-d4-opaque-binary-transform-credit/v1", selected_bit: 1, selector_bit: 0, task_contract_sha256: task.content.sha256, trajectory_sha256: trajectorySeal }; const credit = atom("d4-credit", "owner:d4:credit", "credit", { ...creditBody, credit_sha256: hash(bytes(creditBody)) }, [ref("d4:outcome", "outcome", outcome.key)])
  const disposition = atom("d4-disposition", "owner:d4:disposition", "disposition", { compiler_source_sha256: source, credit_sha256: hash(bytes(creditBody)), generator_source_sha256: source, latent_bit: 0, schema_version: "hswm-d4-latent-bit-disposition/v1", task_contract_sha256: task.content.sha256, task_family: "hswm-d4-opaque-binary-transform/v1", transform: "XOR" }, [ref("d4:credit", "credit", credit.key)])
  const atoms = [task, instance, trajectory, outcome, credit, disposition]; return { task, disposition, atoms, post: bytes({ status: D4_STUDY_STATUS, state: { schemaVersion: task.key.schemaVersion, revision: 1, bootstrapClosed: true, atoms: atoms.map(({ _body, ...rest }) => rest), acceptedTransitionIds: ["transition:d4:d4-fixture"] }, compiledDispositionKey: canonicalAtomV2KeyId(disposition.key), inlineContents: inline(atoms) }) }
}

it("accepts the immutable inline task-trajectory-outcome-credit-disposition closure", () => {
  const { post } = closure(); const result = validateD4StudyPostState(post); if (Either.isLeft(result)) throw result.left; expect(Either.isRight(result)).toBe(true); return
})

it("rejects tampered inline content even when the atom descriptor is unchanged", () => {
  const result = validateD4StudyPostState(bytes({ status: D4_STUDY_STATUS, state: { schemaVersion: "hswm:d4:declared-study-canonical:v1", revision: 0, bootstrapClosed: false, atoms: [], acceptedTransitionIds: [] }, compiledDispositionKey: "", inlineContents: [{ atomKey: "x", mediaType: "application/json", byteLength: 1, sha256: hex("a"), bytesBase64Url: "eA" }] }))
  expect(Either.isLeft(result)).toBe(true)
})

it.effect.skipIf(!existsSync(leanCli))("submits the D4 closure through the real Lean-protected V2 journal", () => Effect.gen(function* () {
  const { mkdtempSync, rmSync } = yield* Effect.promise(() => import("node:fs"))
  const { join } = yield* Effect.promise(() => import("node:path"))
  const { tmpdir } = yield* Effect.promise(() => import("node:os"))
  const { makeEphemeralLocalPermitIssuer } = yield* Effect.promise(() => import("../src/canonical-atom-v2-local-permit-commit.js"))
  const { makeD4StudyAdmissionGateway } = yield* Effect.promise(() => import("../src/canonical-atom-v2-d4-study.js"))
  const cli = leanCli
  const genesis = bytes({ status: D4_STUDY_STATUS, state: { schemaVersion: "hswm:d4:declared-study-canonical:v1", revision: 0, bootstrapClosed: false, atoms: [], acceptedTransitionIds: [] }, compiledDispositionKey: "", inlineContents: [] })
  // Reuse the separately tested semantic fixture by reconstructing its bytes.
  const { post } = closure()
  const fixed = () => new Date("2026-09-06T00:00:00.000Z")
  const issuer = makeEphemeralLocalPermitIssuer({ keyId: "key:d4", authorizer: "principal:d4", policyVersion: "policy:d4", revocationEpoch: 0, clock: fixed }); if (Either.isLeft(issuer)) throw issuer.left
  const nonce = issuer.right.mintNonce(); if (Either.isLeft(nonce)) throw nonce.left
  const priorHead = { lineageId: "lineage:d4:d4-fixture", sequence: 0, stateDigest: hash(genesis), recordDigest: hex("0") }; const expectedNextHead = { lineageId: "lineage:d4:d4-fixture", sequence: 1, stateDigest: hash(post), recordDigest: hex("1") }
  const issued = issuer.right.issue({ permitId: "permit:d4", executionId: "execution:d4", executionIntentDigest: hex("2"), permitDigest: hex("3"), proposalDigest: hex("4"), transitionInvariantDigest: hex("5"), priorHead, expectedNextHead, target: { schemaVersion: "hswm:d4:declared-study-canonical:v1", lineageId: "lineage:d4:d4-fixture", atomUid: "disposition" }, expectedRevision: "revision:absent", candidateRevision: "revision:0", authorizationRef: "authorization:d4", scope: "scope:d4", nonceDigest: nonce.right.nonceDigest, linearizationIndex: 1 }, 60_000); if (Either.isLeft(issued)) throw issued.left
  const root = mkdtempSync(join(tmpdir(), "hswm-d4-gateway-")); const gateway = makeD4StudyAdmissionGateway(root, issuer.right, { leanExecutable: cli }, fixed); if (Either.isLeft(gateway)) throw gateway.left
  const receipt = yield* gateway.right.submit({ ...issued.right, preStateBytes: genesis, postStateBytes: post }); expect(receipt.commit.expectedNextHead.sequence).toBe(1); expect((yield* gateway.right.recover()).commits).toHaveLength(1); rmSync(root, { recursive: true, force: true })
}))

it("rejects owner-bound atom mutation", () => {
  const { post } = closure()
  const parsed = JSON.parse(Buffer.from(post).toString("utf8")) as { state: { atoms: Array<{ kind: string; responsibilityOwner: string }> } }
  parsed.state.atoms.find((atom) => atom.kind === "d4-credit")!.responsibilityOwner = "owner:d4:task"
  expect(Either.isLeft(validateD4StudyPostState(bytes(parsed)))).toBe(true)
})

it("rejects an extra schema-valid atom outside the declared six-atom transition", () => {
  const { post } = closure()
  const parsed = JSON.parse(Buffer.from(post).toString("utf8"))
  const extra = structuredClone(parsed.state.atoms[0])
  extra.key.atomUid = "extra-task"
  parsed.state.atoms.push(extra)
  parsed.inlineContents.push({ ...parsed.inlineContents[0], atomKey: canonicalAtomV2KeyId(extra.key) })
  const result = validateD4StudyPostState(bytes(parsed))
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) expect(result.left.message).toContain("exactly the six")
})
