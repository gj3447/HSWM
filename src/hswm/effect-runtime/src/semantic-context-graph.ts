/** Existing native KG-bundle v2 projection; this view is never a canonical graph write. */
import { type KgBundle } from "./native-kg-bundle-domain.js"
import { contextHash, contextJson, type ContextPlan, type ContextSelection } from "./semantic-context-domain.js"
import { type ContextAssembly } from "./semantic-context-runtime.js"

export const projectSemanticContext = (plan: ContextPlan, selection: ContextSelection, assembly: ContextAssembly | null, source: Readonly<{ path: string; sha256: string }>): KgBundle => {
  const nodes: KgBundle["nodes"][number][] = []
  const relations: KgBundle["relations"][number][] = []
  const root = `sym:AbstractNode:context-plan-${plan.planSha256}`
  const decision = `sym:Concept:context-selection-${contextHash(selection)}`
  const common = { authority_class: "SECONDARY_AI", claim_boundary: "ADVISORY_SELECTION_NOT_SUCCESS_OR_W", projection_nonclaim: "READ_ONLY_DERIVED_VIEW_NOT_CANONICAL_ADMISSION", source_path: source.path, source_sha256: source.sha256 }
  const node = (uid: string, role: string, name: string, properties: KgBundle["nodes"][number]["properties"]) => {
    if (!nodes.some(n => n.uid === uid)) nodes.push({ uid, labels: ["Concept", "SemanticContext"], properties: { ...common, name, description: name, standard_graph_role: role, ...properties } })
  }
  const edge = (from_uid: string, to_uid: string, type: string, scope: string) => relations.push({ from_uid, to_uid, type, authority_class: "SECONDARY_AI", scope, status: "OBSERVED_STRUCTURE_NOT_MODEL_EFFICACY" })
  node(root, "CONTEXT_PLAN", "Caller-scoped context plan", { plan_sha256: plan.planSha256, request_sha256: plan.requestSha256, state_revision: plan.stateRevision, task: plan.spec.event, maximum_context_bytes: plan.spec.maximumContextBytes, candidate_scope: plan.scope, mandatory_relation_uids: [...plan.spec.mandatoryRelationUids] })
  node(decision, "CONTEXT_SELECTION", "Advisory Jev context selection", { status: selection.status, reason: selection.reason, plan_sha256: plan.planSha256, request_sha256: selection.requestSha256, receipt_sha256: selection.receiptSha256, backend: selection.backend, model: selection.model, model_revision: selection.revision, receipt_authority: selection.authority, ...(selection.confidence === null ? {} : { confidence: selection.confidence }), ...(selection.margin === null ? {} : { margin: selection.margin }) })
  edge(root, decision, "HAS_CONCEPT", "PLAN_DECISION")
  for (const candidate of plan.spec.candidates) {
    const id = `sym:Concept:context-candidate-${contextHash({ plan: plan.planSha256, id: candidate.id })}`
    node(id, "CONTEXT_CANDIDATE", candidate.id, { candidate_id: candidate.id, summary: candidate.summary, relation_uids: [...candidate.relationUids], description_authority: "CALLER_AUTHORED_MAP_NOT_VERIFIED_SEMANTIC_SUFFICIENCY", plan_sha256: plan.planSha256 })
    edge(root, id, "HAS_CONCEPT", "SCOPED_CANDIDATE")
    if (candidate.id === selection.candidateId) edge(decision, id, "REFERENCES", "SELECTED_CANDIDATE")
  }
  if (assembly !== null) {
    const id = `sym:Concept:context-assembly-${assembly.assemblySha256}`
    node(id, "CONTEXT_ASSEMBLY", "Complete selected context", { assembly_sha256: assembly.assemblySha256, context_bytes: assembly.contextBytes, maximum_context_bytes: plan.spec.maximumContextBytes, truncation: "NONE", budget_unit: "UTF8_JSON_REQUEST_PAYLOAD_BYTES_NOT_TOKENS" })
    edge(decision, id, "HAS_CONCEPT", "ASSEMBLED_CONTEXT")
    assembly.payload.frames.forEach((frame, frameOrdinal) => {
      const frameUid = `sym:Concept:context-frame-${contextHash({ assembly: assembly.assemblySha256, ordinal: frameOrdinal })}`
      node(frameUid, "CONTEXT_FRAME", frame.relation.key.atomUid, { frame_sha256: frame.frameSha256, ordinal: frameOrdinal, relation_key_json: contextJson(frame.relation.key), relation_owner: frame.relation.owner, semantic_json: contextJson(frame.relation.semantic), prior_evidence_json: contextJson(frame.priorEvidence), mandatory: plan.spec.mandatoryRelationUids.includes(frame.relation.key.atomUid) })
      edge(id, frameUid, "HAS_CONCEPT", "ORDERED_FRAME")
      frame.roles.forEach((role, ordinal) => {
        const occurrence = `sym:Concept:context-role-${contextHash({ frameUid, ordinal })}`
        const participant = `sym:Concept:context-participant-${contextHash(role.key)}`
        node(occurrence, "CONTEXT_ROLE", role.role, { ordinal, role: role.role, reference_type: role.referenceType })
        node(participant, "CONTEXT_PARTICIPANT", role.key.atomUid, { participant_key_json: contextJson(role.key), participant_owner: role.owner, content_sha256: role.contentSha256, content_utf8: role.contentUtf8 })
        edge(frameUid, occurrence, "HAS_PARTICIPATION", "PINNED_ROLE_OCCURRENCE")
        edge(occurrence, participant, "REFERENCES", "EXACT_PARTICIPANT_VERSION")
      })
    })
  }
  return {
    schema_version: "hswm-semantic-context-graph/v1", bundle_uid: root,
    status: "SOURCE_BOUND_CONTEXT_OBSERVATION", nonclaim: "NOT_MODEL_CALIBRATION_NOT_SUCCESS_PROBABILITY_NOT_W_UPDATE_NOT_SUPERINTELLIGENCE",
    artifact_bindings: [source], expected_counts: { nodes: nodes.length, anchors: 0, relations: relations.length }, anchors: [], nodes, relations
  }
}
