/** Local-file DNRD adapter. This is not a Permit, HSWM admission, learning, or runner. */
import { createHash } from "node:crypto"

import { Effect, Either, Layer, Context, Data } from "effect"

import { canonicalJsonBytes, decodeCanonicalJsonBytes } from "./canonical-atom-v2-json.js"
import {
  CanonicalAtomV2DurableRuntime,
  commitCanonicalAtomV2DurableFromLocalDiagnosticInternal,
  makeCanonicalAtomV2DurableRuntimeFileLayer
} from "./canonical-atom-v2-durable-runtime.js"
import { decodeCanonicalAtomV2SchemaContent, describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "./canonical-atom-v2-content-bound.js"
import { type CanonicalAtomV2, type CanonicalAtomV2Key, type CommitCanonicalAtomsV2Command } from "./canonical-atom-v2-schema.js"
import {
  applyDnrdCreditUpdate,
  derangeDnrdRoutingBindings,
  dnrdRoutingPayloadSha256,
  makeDnrdCanonicalSchemaV2,
  makeDnrdEligibilityTrace,
  selectDnrdRoute,
  validateDnrdEligibilityTrace,
  validateDnrdOutcomeObservation,
  validateDnrdRoutingPayload,
  type DnrdEligibilityTrace,
  type DnrdOutcomeObservation,
  type DnrdRoutingPayload
} from "./canonical-atom-v2-routing-diagnostic.js"

export const DNRD_FILE_LINEAGE = "lineage:dnrd:local-experimental"
export const DNRD_FILE_AUTHORIZATION = "authorization:dnrd:local-experimental"
export const DNRD_FILE_SCOPE = "scope:dnrd:local-experimental"
export const DNRD_FILE_ACTOR = "actor:dnrd:local-experimental"
export const DNRD_FILE_STATUS = "LOCAL_EXPERIMENTAL_STRUCTURAL_ONLY_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING" as const
/** Immutable local preimage for the transition receipt's provenance digest. */
export const DNRD_FILE_TRANSITION_PROVENANCE_MEDIA_TYPE = "application/vnd.hswm.dnrd.local-transition-provenance+json" as const

export class DnrdRoutingDiagnosticFileError extends Data.TaggedError("DnrdRoutingDiagnosticFileError")<{
  readonly reason: "STATE" | "TRACE" | "OUTCOME" | "CONTENT"
  readonly detail: string
}> {}

const fail = (reason: DnrdRoutingDiagnosticFileError["reason"], detail: string) => new DnrdRoutingDiagnosticFileError({ reason, detail })
const utf8 = (value: unknown) => {
  const bytes = canonicalJsonBytes(value)
  return Either.isLeft(bytes) ? Either.left(fail("CONTENT", "DNRD value is not canonical JSON")) : Either.right(Uint8Array.from(bytes.right))
}
const sha256 = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex")
const sameKey = (left: CanonicalAtomV2Key, right: CanonicalAtomV2Key) =>
  left.schemaVersion === right.schemaVersion && left.lineageId === right.lineageId && left.atomUid === right.atomUid && left.revisionId === right.revisionId
const schemaBytes = () => utf8(makeDnrdCanonicalSchemaV2())
const key = (atomUid: string, revisionId: number): CanonicalAtomV2Key => ({ schemaVersion: "hswm:dnrd:v1", lineageId: DNRD_FILE_LINEAGE, atomUid, revisionId })
const routeKey = key("dnrd:routing", 0)
const atomUidForTrace = (traceId: string) => `dnrd:trace:${traceId}`
const atomUidForOutcome = (outcomeId: string) => `dnrd:outcome:${outcomeId}`
const atomUidForCredit = (outcomeId: string) => `dnrd:credit:${outcomeId}`

export class DnrdRoutingDiagnosticFile extends Context.Tag("hswm/DnrdRoutingDiagnosticFile")<
  DnrdRoutingDiagnosticFile,
  {
    /** Initialize one local mount. The process adapter alone assigns W0/control roles. */
    readonly initialize: (payload: DnrdRoutingPayload) => Effect.Effect<unknown, unknown>
    /** The payload is recovered from the durable routing chain; callers cannot substitute it. */
    readonly sealTrainingTrajectory: (input: { readonly episodeId: string; readonly contextSha256: string; readonly routeId: string; readonly requestSha256: string; readonly responseSha256: string }) => Effect.Effect<DnrdEligibilityTrace, unknown>
    readonly applyOutcome: (outcome: DnrdOutcomeObservation, learningRateMicros: number, scoreLimitMicros: number) => Effect.Effect<unknown, unknown>
    readonly project: (contextSha256: string, deranged?: boolean) => Effect.Effect<unknown, unknown>
    readonly recover: Effect.Effect<unknown, unknown>
    readonly creditedEpisodeIds: Effect.Effect<ReadonlyArray<string>, unknown>
    readonly snapshot: Effect.Effect<unknown, unknown>
  }
>() {}

/**
 * The adapter composes only local V2 durability with the frozen pure DNRD core.
 * A caller must create a fresh Layer to demonstrate process recovery.
 */
export const makeDnrdRoutingDiagnosticFileLayer = (rootPath: string) => {
  const rawSchema = schemaBytes()
  if (Either.isLeft(rawSchema)) return Layer.fail(rawSchema.left)
  const decodedSchema = decodeCanonicalAtomV2SchemaContent(rawSchema.right)
  if (Either.isLeft(decodedSchema)) return Layer.fail(decodedSchema.left)
  const rawGrants = [{ authorizationRef: DNRD_FILE_AUTHORIZATION, schemaVersion: "hswm:dnrd:v1", schemaContentSha256: decodedSchema.right.binding.content.sha256, scopes: [DNRD_FILE_SCOPE] }]
  return Layer.provide(
    Layer.effect(DnrdRoutingDiagnosticFile, Effect.gen(function* () {
      const runtime = yield* CanonicalAtomV2DurableRuntime
      const readPayload = (atom: CanonicalAtomV2) => Effect.gen(function* () {
        const bytes = yield* runtime.readContent(atom.content)
        const parsed = decodeCanonicalJsonBytes(bytes)
        if (Either.isLeft(parsed)) return yield* fail("CONTENT", "routing payload bytes are not canonical JSON")
        const checked = validateDnrdRoutingPayload(parsed.right)
        if (Either.isLeft(checked)) return yield* fail("CONTENT", checked.left.detail)
        return checked.right
      })
      const readTrace = (atom: CanonicalAtomV2) => Effect.gen(function* () {
        const bytes = yield* runtime.readContent(atom.content)
        const parsed = decodeCanonicalJsonBytes(bytes)
        if (Either.isLeft(parsed)) return yield* fail("TRACE", "durable trajectory bytes are not canonical JSON")
        const checked = validateDnrdEligibilityTrace(parsed.right)
        if (Either.isLeft(checked)) return yield* fail("TRACE", checked.left.detail)
        return checked.right
      })
      const creditedEpisodeIdsFromState = (state: { readonly canonical: { readonly atoms: ReadonlyArray<CanonicalAtomV2> } }) => Effect.gen(function* () {
        const episodeIds: string[] = []
        for (const credit of state.canonical.atoms.filter((candidate) => candidate.kind === "dnrd:credit")) {
          const references = credit.references.filter((candidate) => candidate.referenceType === "dnrd:reference" && candidate.role === "trajectory")
          const creditedTraceAtom = references.length === 1 ? state.canonical.atoms.find((candidate) => candidate.kind === "dnrd:trajectory" && sameKey(candidate.key, references[0]!.target)) : undefined
          if (creditedTraceAtom === undefined) return yield* fail("STATE", "durable credit has no exact typed trajectory reference")
          episodeIds.push((yield* readTrace(creditedTraceAtom)).episodeId)
        }
        const ordered = [...episodeIds].sort()
        if (new Set(ordered).size !== ordered.length) return yield* fail("STATE", "durable routing chain credits one training episode more than once")
        return Object.freeze(ordered)
      })
      const latestRouting = () => runtime.snapshot.pipe(Effect.flatMap((state) => {
        const atoms = state.canonical.atoms.filter((atom) => atom.kind === "dnrd:routing-disposition").sort((left, right) => left.key.revisionId - right.key.revisionId)
        if (atoms.length === 0) return Effect.fail(fail("STATE", "DNRD routing genesis atom is missing"))
        for (const [index, atom] of atoms.entries()) {
          if (atom.key.atomUid !== "dnrd:routing" || atom.key.revisionId !== index) {
            return Effect.fail(fail("STATE", "DNRD routing atoms are not one exact contiguous canonical chain"))
          }
          if (index === 0) {
            if (atom.references.length !== 0) return Effect.fail(fail("STATE", "DNRD routing genesis must not claim a causal predecessor"))
            continue
          }
          const credit = atom.references.filter((reference) => reference.referenceType === "dnrd:reference" && reference.role === "credit")
          const predecessor = atom.references.filter((reference) => reference.referenceType === "hswm:reference:supersedes" && reference.role === "hswm:role:predecessor")
          const targetCredit = credit[0] === undefined ? undefined : state.canonical.atoms.find((candidate) => candidate.kind === "dnrd:credit" && sameKey(candidate.key, credit[0]!.target))
          if (atom.references.length !== 2 || credit.length !== 1 || predecessor.length !== 1 || targetCredit === undefined || !sameKey(predecessor[0]!.target, atoms[index - 1]!.key)) {
            return Effect.fail(fail("STATE", "every DNRD routing successor must have one typed credit and its exact predecessor"))
          }
        }
        const atom = atoms[atoms.length - 1]!
        return readPayload(atom).pipe(Effect.map((payload) => ({ state, atom, payload })))
      }))
      const submitAtoms = (stateRevision: number, reads: ReadonlyArray<CanonicalAtomV2Key>, writes: ReadonlyArray<CanonicalAtomV2>, traceRef: CanonicalAtomV2Key | null) => Effect.gen(function* () {
        const bindings = []
        for (const atom of writes) {
          const envelope = describeCanonicalAtomV2Envelope(atom)
          if (Either.isLeft(envelope)) return yield* fail("CONTENT", envelope.left.detail)
          bindings.push({ key: atom.key, payload: atom.content, envelope: envelope.right })
        }
        const decidedAt = new Date().toISOString()
        const provenance = utf8({
          contract_version: "hswm-dnrd-local-transition-provenance/v1",
          clock_trust: "UNATTESTED_OS_CLOCK_ORDER_ESTABLISHED_BY_STATE_REVISION_ONLY",
          decided_at: decidedAt,
          expected_state_revision: stateRevision,
          read_set: reads,
          trace_ref: traceRef,
          writes: writes.map((atom) => ({ key: atom.key, kind: atom.kind, responsibility_owner: atom.responsibilityOwner, content: atom.content, atom_provenance: atom.provenance, lifecycle: atom.lifecycle, references: atom.references }))
        })
        if (Either.isLeft(provenance)) return yield* provenance.left
        const provenanceSha256 = sha256(provenance.right)
        const stagedProvenance = yield* runtime.stageContent(
          DNRD_FILE_TRANSITION_PROVENANCE_MEDIA_TYPE,
          provenance.right
        )
        if (stagedProvenance.sha256 !== provenanceSha256) {
          return yield* fail("CONTENT", "staged transition provenance descriptor does not match its canonical preimage")
        }
        const command: CommitCanonicalAtomsV2Command = {
          _tag: "CommitCanonicalAtomsV2", contractVersion: "hswm-canonical-transition/v2", transitionId: `dnrd:transition:${stateRevision}:${writes.map((atom) => atom.key.atomUid).join(":")}`,
          expectedStateRevision: stateRevision, schemaVersion: "hswm:dnrd:v1", actorClaim: DNRD_FILE_ACTOR, authorizationRef: DNRD_FILE_AUTHORIZATION, scope: DNRD_FILE_SCOPE,
          decidedAt, traceRef, readSet: [...reads], writes: [...writes], provenanceSha256: stagedProvenance.sha256
        }
        return yield* commitCanonicalAtomV2DurableFromLocalDiagnosticInternal(
          runtime,
          makeCanonicalAtomV2ContentBoundInput(
            runtime.schemaContent.content.sha256,
            command,
            bindings
          )
        )
      })
      const makeAtom = (atomKey: CanonicalAtomV2Key, kind: string, owner: string, payload: unknown, provenance: CanonicalAtomV2["provenance"], references: CanonicalAtomV2["references"]): Effect.Effect<CanonicalAtomV2, unknown> => Effect.gen(function* () {
        const bytes = utf8(payload)
        if (Either.isLeft(bytes)) return yield* bytes.left
        const content = yield* runtime.stageContent("application/vnd.hswm.dnrd+json", bytes.right)
        return { _tag: "CanonicalAtomV2", contractVersion: "hswm-canonical-atom/v2", key: atomKey, kind, responsibilityOwner: owner, content, provenance, lifecycle: "ADMITTED", references }
      })
      return DnrdRoutingDiagnosticFile.of({
        initialize: (payload) => runtime.snapshot.pipe(Effect.flatMap((state) => {
          const checked = validateDnrdRoutingPayload(payload)
          if (Either.isLeft(checked)) return Effect.fail(fail("STATE", checked.left.detail))
          if (state.canonical.atoms.some((atom) => atom.kind === "dnrd:routing-disposition")) return Effect.succeed(state)
          const payloadSha256 = dnrdRoutingPayloadSha256(checked.right)
          if (Either.isLeft(payloadSha256)) return Effect.fail(fail("CONTENT", payloadSha256.left.detail))
          return makeAtom(routeKey, "dnrd:routing-disposition", "owner:dnrd:routing", checked.right, { mode: "BOOTSTRAP", evidenceSha256: payloadSha256.right, sourceRef: null }, []).pipe(Effect.flatMap((atom) => submitAtoms(state.canonical.revision, [], [atom], null).pipe(Effect.as(state))))
        })),
        sealTrainingTrajectory: (input) => latestRouting().pipe(Effect.flatMap(({ state, atom: routing, payload }) => {
          const trace = makeDnrdEligibilityTrace({ ...input, payload })
          if (Either.isLeft(trace)) return Effect.fail(fail("TRACE", trace.left.detail))
          return makeAtom(key(atomUidForTrace(trace.right.traceId), 0), "dnrd:trajectory", "owner:dnrd:trajectory", trace.right, { mode: "OBSERVATION", evidenceSha256: trace.right.responseSha256, sourceRef: routing.key }, []).pipe(Effect.flatMap((atom) => submitAtoms(state.canonical.revision, [routing.key], [atom], null).pipe(Effect.as(trace.right))))
        })),
        applyOutcome: (outcome, learningRateMicros, scoreLimitMicros) => latestRouting().pipe(Effect.flatMap(({ state, atom: routing, payload }) => Effect.gen(function* () {
          const checkedOutcome = validateDnrdOutcomeObservation(outcome)
          if (Either.isLeft(checkedOutcome)) return yield* fail("OUTCOME", checkedOutcome.left.detail)
          const traceAtom = state.canonical.atoms.find((atom) => atom.key.atomUid === atomUidForTrace(checkedOutcome.right.traceId))
          if (traceAtom === undefined) return yield* fail("TRACE", "outcome names no durably sealed pre-outcome trace")
          if (state.canonical.atoms.some((candidate) => candidate.key.atomUid === atomUidForOutcome(checkedOutcome.right.outcomeId))) return yield* fail("OUTCOME", "one outcome id already has a local experimental successor")
          if (state.canonical.atoms.some((candidate) => candidate.kind === "dnrd:credit" && candidate.references.some((reference) => reference.referenceType === "dnrd:reference" && reference.role === "trajectory" && reference.target.atomUid === traceAtom.key.atomUid && reference.target.revisionId === traceAtom.key.revisionId))) return yield* fail("OUTCOME", "one sealed trace may produce at most one local experimental credit successor")
          const trace = yield* readTrace(traceAtom)
          const creditedEpisodeIds = yield* creditedEpisodeIdsFromState(state)
          if (creditedEpisodeIds.includes(trace.episodeId)) return yield* fail("OUTCOME", "one registered training episode may produce at most one local experimental credit successor")
          const consumedOutcomeIds = state.canonical.atoms.filter((candidate) => candidate.kind === "dnrd:outcome" && candidate.key.atomUid.startsWith("dnrd:outcome:")).map((candidate) => candidate.key.atomUid.slice("dnrd:outcome:".length)).sort()
          const update = applyDnrdCreditUpdate({ payload, trace, outcome: checkedOutcome.right, consumedOutcomeIds, learningRateMicros, scoreLimitMicros })
          if (Either.isLeft(update)) return yield* fail("OUTCOME", update.left.detail)
          const outcomeAtom = yield* makeAtom(key(atomUidForOutcome(outcome.outcomeId), 0), "dnrd:outcome", "owner:dnrd:outcome", checkedOutcome.right, { mode: "DERIVATION", evidenceSha256: checkedOutcome.right.scorerObservationSha256, sourceRef: traceAtom.key }, [{ referenceType: "dnrd:reference", role: "trajectory", target: traceAtom.key }])
          const creditAtom = yield* makeAtom(key(atomUidForCredit(outcome.outcomeId), 0), "dnrd:credit", "owner:dnrd:credit", update.right.receipt, { mode: "DERIVATION", evidenceSha256: update.right.receipt.afterPayloadSha256, sourceRef: outcomeAtom.key }, [{ referenceType: "dnrd:reference", role: "trajectory", target: traceAtom.key }, { referenceType: "dnrd:reference", role: "outcome", target: outcomeAtom.key }])
          const routingAtom = yield* makeAtom(key("dnrd:routing", routing.key.revisionId + 1), "dnrd:routing-disposition", "owner:dnrd:routing", update.right.payload, { mode: "DERIVATION", evidenceSha256: update.right.receipt.afterPayloadSha256, sourceRef: creditAtom.key }, [{ referenceType: "dnrd:reference", role: "credit", target: creditAtom.key }, { referenceType: "hswm:reference:supersedes", role: "hswm:role:predecessor", target: routing.key }])
          return yield* submitAtoms(state.canonical.revision, [traceAtom.key, routing.key], [outcomeAtom, creditAtom, routingAtom], null)
        }))),
        project: (contextSha256, deranged = false) => latestRouting().pipe(Effect.flatMap(({ state, payload }) => {
          const view = deranged ? derangeDnrdRoutingBindings(payload) : Either.right(payload)
          if (Either.isLeft(view)) return Effect.fail(fail("STATE", view.left.detail))
          const selected = selectDnrdRoute(view.right, contextSha256)
          const payloadSha256 = dnrdRoutingPayloadSha256(view.right)
          if (Either.isLeft(payloadSha256)) return Effect.fail(fail("CONTENT", payloadSha256.left.detail))
          return Either.isLeft(selected) ? Effect.fail(fail("STATE", selected.left.detail)) : Effect.succeed(Object.freeze({ selection: selected.right, payload: view.right, payloadSha256: payloadSha256.right, stateRevision: state.canonical.revision, journalHead: state.journalHead, status: DNRD_FILE_STATUS }))
        })),
        recover: latestRouting().pipe(Effect.flatMap(({ state, payload }) => {
          const payloadSha256 = dnrdRoutingPayloadSha256(payload)
          return Either.isLeft(payloadSha256)
            ? Effect.fail(fail("CONTENT", payloadSha256.left.detail))
            : Effect.succeed(Object.freeze({ payload, payloadSha256: payloadSha256.right, stateRevision: state.canonical.revision, journalHead: state.journalHead, status: DNRD_FILE_STATUS }))
        })),
        creditedEpisodeIds: runtime.snapshot.pipe(Effect.flatMap(creditedEpisodeIdsFromState)),
        snapshot: runtime.snapshot
      })
    })),
    makeCanonicalAtomV2DurableRuntimeFileLayer(rootPath, DNRD_FILE_LINEAGE, rawSchema.right, rawGrants)
  )
}
