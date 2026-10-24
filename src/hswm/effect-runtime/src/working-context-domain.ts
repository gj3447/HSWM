/** Durable task-local hypergraph state. Prompt projection is derived, never the durable memory. */
import { Either, Schema } from "effect"
import { CanonicalAtomV2ContentSchema, CanonicalAtomV2KeySchema, canonicalAtomV2KeyId, type CanonicalAtomV2, type CanonicalAtomV2Key, type HSWMCanonicalSchemaV2 } from "./canonical-atom-v2-schema.js"
import { ContextSpecSchema, contextError, contextHash, contextJson, decodeContextSpec, type ContextPlan } from "./semantic-context-domain.js"
import { ActivationConfigSchema, NeuralActivationConfigSchema } from "./semantic-context-activation-domain.js"

export const WORKING_CONTEXT_KIND = "working_context"
export const WORKING_CONTEXT_MEDIA = "application/vnd.hswm.working-context-v1+json"
const text = (maximum: number) => Schema.NonEmptyString.pipe(Schema.maxLength(maximum), Schema.filter(s => s.trim().length > 0))
const digest = Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/))
export const WorkingMemorySchema = Schema.Struct({
  goal: text(1024), constraints: Schema.Array(text(512)).pipe(Schema.maxItems(8)),
  completionCriteria: Schema.Array(text(512)).pipe(Schema.minItems(1), Schema.maxItems(8)),
  progress: text(1024),
  gaps: Schema.Array(Schema.Struct({ id: text(128), question: text(512), status: Schema.Literal("OPEN", "RESOLVED"),
    evidence: Schema.Array(CanonicalAtomV2KeySchema).pipe(Schema.maxItems(16))
  })).pipe(Schema.maxItems(8), Schema.filter(xs => new Set(xs.map(x => x.id)).size === xs.length))
})
export type WorkingMemory = typeof WorkingMemorySchema.Type
export const WorkingContextInputSchema = Schema.Struct({
  agentId: text(256), taskId: text(256), memory: WorkingMemorySchema, spec: ContextSpecSchema,
  policyFamily: Schema.Struct({ lineageId: text(256), atomUid: text(256), config: Schema.Union(ActivationConfigSchema, NeuralActivationConfigSchema) })
})
export const WorkingDependencySchema = Schema.Struct({ key: CanonicalAtomV2KeySchema,
  owner: text(256), content: CanonicalAtomV2ContentSchema, kind: Schema.Literal("semantic_relation", "semantic_participant") })
export const WorkingRunSchema = Schema.Struct({
  id: text(256), requestSha256: digest, status: Schema.Literal("PENDING", "UPDATED", "AUDITED", "NO_UPDATE", "UNKNOWN"),
  traceContent: Schema.NullOr(CanonicalAtomV2ContentSchema), outcomeContent: Schema.NullOr(CanonicalAtomV2ContentSchema),
  policyKey: CanonicalAtomV2KeySchema
})
export const WorkingContextSchema = Schema.Struct({
  contract: Schema.Literal("hswm-working-context/v1"), ...WorkingContextInputSchema.fields,
  dependencies: Schema.Array(WorkingDependencySchema).pipe(Schema.minItems(1), Schema.maxItems(250)),
  policyKey: CanonicalAtomV2KeySchema, lastRun: Schema.NullOr(WorkingRunSchema)
})
export type WorkingContext = typeof WorkingContextSchema.Type
export type WorkingRun = typeof WorkingRunSchema.Type
export const workingError = (code: string, detail: string) => contextError(`WORKING_CONTEXT_${code}`, detail)
export const decodeWorking = <A, I>(schema: Schema.Schema<A, I>, raw: unknown) =>
  Schema.decodeUnknownEither(schema)(raw, { onExcessProperty: "error" }).pipe(Either.mapLeft(() => workingError("INVALID", "Malformed bounded working-context contract")))
export const sameWorkingKey = (a: CanonicalAtomV2Key, b: CanonicalAtomV2Key) => canonicalAtomV2KeyId(a) === canonicalAtomV2KeyId(b)
export const sameWorkingLineage = (a: CanonicalAtomV2Key, b: CanonicalAtomV2Key) =>
  a.schemaVersion === b.schemaVersion && a.lineageId === b.lineageId && a.atomUid === b.atomUid
export const latestWorkingAtom = (atoms: ReadonlyArray<CanonicalAtomV2>, key: CanonicalAtomV2Key) =>
  atoms.filter(a => sameWorkingLineage(a.key, key)).reduce<CanonicalAtomV2 | undefined>((latest, a) => !latest || a.key.revisionId > latest.key.revisionId ? a : latest, undefined)

/** Explicit schema extension for a new/local journal; never mutate a pinned schema in place. */
export const workingContextKind = (owners: ReadonlyArray<string>): HSWMCanonicalSchemaV2["kinds"][number] => ({
  kind: WORKING_CONTEXT_KIND, form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: owners, minimumArity: 2,
  referenceContracts: [
    { referenceType: "hswm:working-context:dependency", roles: [{ role: "source", targetKinds: ["semantic_relation", "semantic_participant"], minimum: 1, maximum: 250 }] },
    { referenceType: "hswm:working-context:policy", roles: [{ role: "activation", targetKinds: ["semantic_context_policy"], minimum: 1, maximum: 1 }] },
    { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: [WORKING_CONTEXT_KIND], minimum: 0, maximum: 1 }] }
  ]
})

export const workingSpec = (context: typeof WorkingContextInputSchema.Type) => decodeContextSpec({ ...context.spec,
  event: contextJson({ event: context.spec.event, agentId: context.agentId, taskId: context.taskId, memory: context.memory }) })
export const workingDependencies = (plan: ContextPlan): WorkingContext["dependencies"] => {
  const pins = plan.bindings.flatMap(b => [
    { key: b.key, owner: b.owner, content: b.content, kind: "semantic_relation" as const },
    ...b.participants.map(p => ({ key: p.key, owner: p.owner, content: p.content, kind: "semantic_participant" as const }))
  ])
  return [...new Map(pins.map(p => [canonicalAtomV2KeyId(p.key), p])).values()]
}
export const workingReferences = (context: WorkingContext, prior: CanonicalAtomV2Key | null): CanonicalAtomV2["references"] => [
  ...(prior === null ? [] : [{ referenceType: "hswm:reference:supersedes", role: "hswm:role:predecessor", target: prior }]),
  ...context.dependencies.map(d => ({ referenceType: "hswm:working-context:dependency", role: "source", target: d.key })),
  { referenceType: "hswm:working-context:policy", role: "activation", target: context.policyKey }
]
/** Superseding a participant requires its source owner to rebind the relation before refresh. */
export const workingChanges = (dependencies: WorkingContext["dependencies"], atoms: ReadonlyArray<CanonicalAtomV2>) =>
  dependencies.flatMap<{ readonly before: CanonicalAtomV2Key; readonly after: CanonicalAtomV2Key | null; readonly reason: "MISSING_OR_CHANGED" | "SUPERSEDED" }>(pin => {
    const exact = atoms.find(a => sameWorkingKey(a.key, pin.key))
    const latest = latestWorkingAtom(atoms, pin.key)
    if (!exact || exact.lifecycle !== "ADMITTED" || exact.responsibilityOwner !== pin.owner || contextHash(exact.content) !== contextHash(pin.content) || exact.kind !== pin.kind)
      return [{ before: pin.key, after: latest?.key ?? null, reason: "MISSING_OR_CHANGED" as const }]
    return latest && !sameWorkingKey(latest.key, pin.key)
      ? [{ before: pin.key, after: latest.key, reason: "SUPERSEDED" as const }] : []
  })
export const reopenWorkingGaps = (memory: WorkingMemory, changed: ReadonlyArray<CanonicalAtomV2Key>): WorkingMemory => ({ ...memory,
  gaps: memory.gaps.map(gap => gap.evidence.some(key => changed.some(c => sameWorkingLineage(key, c)))
    ? { ...gap, status: "OPEN", evidence: [] } : gap)
})
