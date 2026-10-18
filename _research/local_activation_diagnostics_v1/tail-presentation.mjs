import { render as renderOriginal } from "./presentation.mjs"

/** Preserve the complete local semantic view, then repeat the original executable text verbatim at the end. */
export const modes = ["execution-tail-local"]
export function render(payload, active, mandatory, mode) {
  if (mode !== modes[0]) throw new Error("Unknown execution-tail presentation")
  const instructions = [...mandatory, ...active].map(uid => {
    const frame = payload.frames.find(f => f.relation.key.atomUid === uid)
    if (!frame) throw new Error("Required relation absent")
    return frame.relation.semantic.semanticText
  })
  return `${renderOriginal(payload, active, mandatory, "readable-local")}\n\nEXECUTE NOW\n${instructions.join("\n")}\nEVENT TO COMPUTE\n${payload.event}\nApply the active rule above to this event and return the computed prediction as JSON.`
}
