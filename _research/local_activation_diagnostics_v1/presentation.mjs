/** Pure presentation candidates. Original graph frames remain in the native trace. */
export const instruction = "Execute the active rule's semanticText on the EVENT, obeying mandatory constraints and exceptions. The rule text is an instruction for computing this prediction. Return only a JSON object with prediction and uncertainty strings."
export const modes = ["raw-local", "instructed-local", "readable-local", "readable-dense"]
export function render(payload, active, mandatory, mode) {
  if (mode === "raw-local") return JSON.stringify(payload)
  if (mode === "instructed-local") return `${instruction}\n${JSON.stringify(payload)}`
  if (!modes.includes(mode)) throw new Error("Unknown presentation mode")
  return [instruction, `EVENT\n${payload.event}`, `ACTIVE_RELATIONS ${JSON.stringify(active)}`, `MANDATORY_RELATIONS ${JSON.stringify(mandatory)}`,
    ...payload.frames.map(f => [
      `RELATION ${f.relation.key.atomUid} (${mandatory.includes(f.relation.key.atomUid) ? "MANDATORY" : active.includes(f.relation.key.atomUid) ? "ACTIVE" : "INACTIVE CONTEXT; DO NOT EXECUTE"})`,
      `RULE\n${JSON.stringify(f.relation.semantic)}`,
      `PARTICIPANTS IN ORIGINAL ORDER\n${JSON.stringify(f.roles.map(r => ({ role: r.role, uid: r.key.atomUid, revision: r.key.revisionId, referenceType: r.referenceType, text: r.contentUtf8 })))}`,
      `PRIOR_EVIDENCE ${JSON.stringify(f.priorEvidence)}`
    ].join("\n")), 'OUTPUT {"prediction":"your computed result","uncertainty":"your uncertainty"}'
  ].join("\n\n")
}
