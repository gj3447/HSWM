/** Typed decisions over an owner-admitted local map; citation integrity is not entailment. */
import { Either, Schema } from "effect"
import { CanonicalAtomV2KeySchema } from "./canonical-atom-v2-schema.js"
import { ContextSpecSchema, contextError } from "./semantic-context-domain.js"

const text = (maximum: number) => Schema.NonEmptyString.pipe(Schema.maxLength(maximum))
const digest = Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/))
export const EvidenceStepSchema = Schema.Struct({
  contract: Schema.Literal("hswm-evidence-step/v1"),
  resource: text(512),
  policyUid: text(512),
  spec: ContextSpecSchema.omit("event"),
  /** Exact USL context bytes are a participant of a mandatory relation. No resolver authority. */
  navigation: CanonicalAtomV2KeySchema,
  edges: Schema.Array(Schema.Struct({ id: text(128), link: text(512), resource: text(512), enteredRole: text(128), exitedRole: text(128),
    next: CanonicalAtomV2KeySchema })).pipe(Schema.maxItems(8), Schema.filter(xs => new Set(xs.map(x => x.id)).size === xs.length)),
  evidence: Schema.Array(Schema.Struct({ sourceId: text(128), key: CanonicalAtomV2KeySchema, sha256: digest }))
    .pipe(Schema.maxItems(8), Schema.filter(xs => new Set(xs.map(x => x.sourceId)).size === xs.length))
})
export type EvidenceStep = typeof EvidenceStepSchema.Type
// A narrow consumer view; the original full USL packet remains in native content, unmodified.
// USL owns compilation. This only checks that executable edges agree with its local witnesses.
const NavigationView = Schema.Struct({
  schema: Schema.Literal("usl-agent-context/v1"), focus: text(512), planDigest: text(80),
  links: Schema.Array(Schema.Struct({ name: text(512), meaning: text(512),
    participants: Schema.Array(Schema.Struct({ role: text(128), resource: text(512) })) })),
  meanings: Schema.Array(Schema.Struct({ name: text(512), roles: Schema.Array(Schema.Struct({ name: text(128) })) })),
  paths: Schema.Array(Schema.Struct({ resource: text(512), steps: Schema.Array(Schema.Struct({
    link: text(512), meaning: text(512), from: text(512), to: text(512), enteredRole: text(128), exitedRole: text(128) })) })),
  interpretation: Schema.Struct({ semanticTruth: Schema.Literal("NOT_EVALUATED"), reachability: Schema.Literal("NOT_OBSERVED"), execution: Schema.Literal("NOT_PLANNED") })
})
export const validateEvidenceNavigation = (raw: unknown, step: EvidenceStep) => Either.gen(function* () {
  const nav = yield* Schema.decodeUnknownEither(NavigationView)(raw).pipe(Either.mapLeft(() => contextError("USL_BINDING_INVALID", "Expected an unpromoted full USL agent context")))
  if (nav.focus !== step.resource || new Set(nav.links.map(l => l.name)).size !== nav.links.length || new Set(nav.meanings.map(m => m.name)).size !== nav.meanings.length)
    return yield* Either.left(contextError("USL_BINDING_INVALID", "Ambiguous local declaration identity"))
  for (const edge of step.edges) {
    const link = nav.links.find(l => l.name === edge.link), meaning = nav.meanings.find(m => m.name === link?.meaning)
    if (!link || !meaning || new Set(link.participants.map(p => p.role)).size !== link.participants.length ||
      contextRoleSet(link.participants.map(p => p.role)) !== contextRoleSet(meaning.roles.map(r => r.name)) ||
      !link.participants.some(p => p.role === edge.enteredRole && p.resource === nav.focus) ||
      !link.participants.some(p => p.role === edge.exitedRole && p.resource === edge.resource) ||
      !nav.paths.some(p => p.resource === edge.resource && p.steps.length === 1 && p.steps.some(s => s.link === edge.link &&
        s.meaning === link.meaning && s.from === nav.focus && s.to === edge.resource && s.enteredRole === edge.enteredRole && s.exitedRole === edge.exitedRole)))
      return yield* Either.left(contextError("USL_BINDING_INVALID", "Executable edge must preserve the complete named roles and a one-hop USL witness"))
  }
  return nav
})
const contextRoleSet = (xs: ReadonlyArray<string>) => JSON.stringify([...xs].sort())
const citation = Schema.Struct({ sourceId: text(128), quote: text(2048) })
export const EvidenceActionSchema = Schema.Union(
  Schema.Struct({ action: Schema.Literal("FOLLOW"), edgeId: text(128) }),
  Schema.Struct({ action: Schema.Literal("ANSWER"), answer: text(2048),
    citations: Schema.Array(citation).pipe(Schema.minItems(1), Schema.maxItems(8)) }),
  Schema.Struct({ action: Schema.Literal("ABSTAIN"), reason: text(2048) })
)
export type EvidenceAction = typeof EvidenceActionSchema.Type
export interface VisitedEvidence {
  readonly sourceId: string
  readonly sha256: string
  readonly text: string
}
export const inspectEvidenceAction = (prediction: string, step: EvidenceStep, visited: ReadonlyArray<VisitedEvidence>) => Either.gen(function* () {
  if (prediction.length > 16384) return yield* Either.left(contextError("ACTION_INVALID", "Bounded action JSON required"))
  const raw = yield* Either.try({ try: () => JSON.parse(prediction) as unknown,
    catch: () => contextError("ACTION_INVALID", "Prediction must contain one typed JSON action") })
  const action = yield* Schema.decodeUnknownEither(EvidenceActionSchema)(raw, { onExcessProperty: "error" })
    .pipe(Either.mapLeft(() => contextError("ACTION_INVALID", "Unknown action, extra fields or invalid citation shape")))
  if (action.action === "FOLLOW" && !step.edges.some(e => e.id === action.edgeId))
    return yield* Either.left(contextError("EDGE_NOT_LOCAL", "Only an exact outgoing edge of the visited step may be followed"))
  if (action.action === "ANSWER") {
    for (const c of action.citations) {
      const matches = visited.filter(v => v.sourceId === c.sourceId)
      if (matches.length !== 1 || !c.quote.trim() || !matches[0]?.text.includes(c.quote))
        return yield* Either.left(contextError("CITATION_UNBOUND", "Citations must quote actually activated, pinned source text"))
    }
  }
  return { action, grounding: action.action === "ANSWER" ? "EXACT_QUOTE_INTEGRITY_ONLY" as const : "NOT_APPLICABLE" as const }
})
