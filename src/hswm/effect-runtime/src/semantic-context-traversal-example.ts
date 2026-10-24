/** Authored five-vertex example, not production state or an independent efficacy dataset. */
import { Effect } from "effect"
import type { CanonicalAtomV2DurableRuntime } from "./canonical-atom-v2-durable-runtime.js"
import { describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "./canonical-atom-v2-content-bound.js"
import { HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION, type CanonicalAtomV2, type HSWMCanonicalSchemaV2 } from "./canonical-atom-v2-schema.js"
import { contextHash, contextJson } from "./semantic-context-domain.js"
import { prepareSemanticContext } from "./semantic-context-runtime.js"
import { prepareActivationInitialization } from "./semantic-context-activation-runtime.js"
import { ACTIVATION_STEP_MEDIA, type ActivationStep } from "./semantic-context-traversal-runtime.js"

export const traversalExampleOwner = "owner:traversal-example"
export const traversalExampleKey = (atomUid: string, revisionId = 0) => ({ schemaVersion: "traversal-example-v1", lineageId: "example", atomUid, revisionId })
export const traversalExampleConfig = { encoderRevision: "authored-signal/v1", featureNames: ["bias", "signal"], alpha: 1 }
export const traversalExampleTarget = (uid: string, revisionId: number) => ({ key: traversalExampleKey(uid, revisionId),
  owner: traversalExampleOwner, authorizationRef: "traversal-example", scope: "isolated-example", decidedAt: "2026-10-24T00:00:00.000Z" })
const roles = ["subject", "context", "evidence", "exception"]
export const traversalExampleSchema: HSWMCanonicalSchemaV2 = {
  _tag: "HSWMCanonicalSchemaV2", contractVersion: HSWM_CANONICAL_SCHEMA_V2_CONTRACT_VERSION,
  schemaVersion: "traversal-example-v1", scientificStatus: "UNJUDGED", bootstrapTrustStatement: "AUTHORED_INTEGRATION_EXAMPLE_NOT_PRODUCTION",
  owners: [{ address: traversalExampleOwner, obligation: "Isolated authored traversal example" }], kinds: [
    { kind: "semantic_participant", form: "ENTITY", revisionPolicy: "LINEAR", allowedOwners: [traversalExampleOwner], minimumArity: 0, referenceContracts: [
      { referenceType: "hswm:activation:next", roles: ["left", "right"].map(role => ({ role, targetKinds: ["semantic_participant"], minimum: 0, maximum: 1 })) },
      { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_participant"], minimum: 0, maximum: 1 }] }
    ] },
    { kind: "semantic_relation", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [traversalExampleOwner], minimumArity: 4, referenceContracts: [
      { referenceType: "hswm:semantic:role", roles: roles.map(role => ({ role, targetKinds: ["semantic_participant"], minimum: 1, maximum: 1 })) },
      { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_relation"], minimum: 0, maximum: 1 }] }
    ] },
    { kind: "semantic_context_policy", form: "RELATION", revisionPolicy: "LINEAR", allowedOwners: [traversalExampleOwner], minimumArity: 1, referenceContracts: [
      { referenceType: "hswm:context-policy:scope", roles: [{ role: "candidate-root", targetKinds: ["semantic_relation"], minimum: 1, maximum: 72 }] },
      { referenceType: "hswm:reference:supersedes", roles: [{ role: "hswm:role:predecessor", targetKinds: ["semantic_context_policy"], minimum: 0, maximum: 1 }] }
    ] }
  ]
}
const parents: Readonly<Record<string, ReadonlyArray<string>>> = {
  entry: [], left: ["entry"], right: ["entry"], "left-leaf": ["entry", "left"], "right-leaf": ["entry", "right"]
}
export const traversalExampleStep = (name: string): ActivationStep => ({
  contract: "hswm-activation-step/v1", policyUid: `policy:${name}`, spec: {
    contract: "hswm-semantic-context-spec/v1",
    mandatoryRelationUids: [...(parents[name] ?? []), name].map(n => `rule:${n}:required`),
    candidates: ["left", "right"].map(id => ({ id, summary: `${id} local operator`, relationUids: [`rule:${name}:${id}`] })),
    maximumContextBytes: 65536, minimumConfidence: 0, minimumMargin: 0
  },
  edges: ["left", "right"].map(candidateId => ({ candidateId,
    next: name.endsWith("-leaf") ? null : traversalExampleKey(`step:${name === "entry" ? candidateId : `${name}-leaf`}`) }))
})
export const seedTraversalExample = (runtime: CanonicalAtomV2DurableRuntime["Type"], transform: (name: string, step: ActivationStep) => ActivationStep = (_name, step) => step) => Effect.gen(function* () {
  const writes: CanonicalAtomV2[] = []
  const add = (uid: string, kind: string, media: string, payload: string, references: CanonicalAtomV2["references"]) => Effect.gen(function* () {
    const content = yield* runtime.stageContent(media, new TextEncoder().encode(payload))
    writes.push({ _tag: "CanonicalAtomV2", contractVersion: HSWM_CANONICAL_ATOM_V2_CONTRACT_VERSION, key: traversalExampleKey(uid), kind,
      responsibilityOwner: traversalExampleOwner, content, references, lifecycle: "ADMITTED",
      provenance: { mode: "BOOTSTRAP", evidenceSha256: content.sha256, sourceRef: null } })
  })
  for (const name of Object.keys(parents)) {
    const step = transform(name, traversalExampleStep(name))
    yield* add(`step:${name}`, "semantic_participant", ACTIVATION_STEP_MEDIA, contextJson(step), step.edges.flatMap(e => e.next === null ? [] : [
      { referenceType: "hswm:activation:next", role: e.candidateId, target: e.next }]))
    for (const role of roles.filter(r => r !== "context")) {
      yield* add(`${name}:${role}`, "semantic_participant", "text/plain",
        role === "exception" ? "At a leaf, blocked=true requires REFUSE. Preserve the original input and all required rules." : `Authored ${name} ${role}; not independent natural-task evidence.`, [])
    }
    for (const choice of ["required", "left", "right"]) {
      const semanticText = choice === "required"
        ? `/no_think Return JSON with prediction and uncertainty strings only. EVENT.input is a JSON string; decode it. ${name.endsWith("-leaf") ? 'If input.blocked is true, prediction must be "REFUSE", overriding the selected operator.' : 'Execute the selected local operator.'} No tools or extra text.`
        : `Unless a mandatory exception applies, prediction must be exactly "${choice === "left" ? "L" : "R"}". This literal is the selected operator result; signal is only a routing feature.`
      yield* add(`rule:${name}:${choice}`, "semantic_relation", "application/vnd.hswm.llm-semantic-relation-v1+json",
        contextJson({ semanticText, disposition: "predict", uncertainty: "authored", exceptionRefs: [`${name}:exception`], trace: null, outcome: null }),
        roles.map(role => ({ referenceType: "hswm:semantic:role", role, target: traversalExampleKey(role === "context" ? `step:${name}` : `${name}:${role}`) })))
    }
  }
  const envelopes = yield* Effect.forEach(writes, atom => describeCanonicalAtomV2Envelope(atom).pipe(Effect.map(envelope => ({ key: atom.key, payload: atom.content, envelope }))))
  yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
    _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
    transitionId: "seed-traversal-example", expectedStateRevision: 0, schemaVersion: traversalExampleSchema.schemaVersion,
    actorClaim: "traversal-example", authorizationRef: "traversal-example", scope: "isolated-example", decidedAt: traversalExampleTarget("unused", 0).decidedAt,
    traceRef: null, readSet: [], writes, provenanceSha256: contextHash(writes)
  }, envelopes))
  for (const name of Object.keys(parents)) {
    const step = transform(name, traversalExampleStep(name))
    const plan = yield* prepareSemanticContext(runtime, { ...step.spec, event: "initialize" })
    const proposal = yield* prepareActivationInitialization(runtime, plan, traversalExampleConfig, traversalExampleTarget(step.policyUid, 0))
    yield* runtime.submit(proposal.candidate)
  }
})
