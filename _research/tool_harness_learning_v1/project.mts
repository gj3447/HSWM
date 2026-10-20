/** Bounded USL view over verified native before/outcome/after identities; no resolver I/O. */
import { readFileSync } from "node:fs"
import { resolve, join } from "node:path"
import { createHash } from "node:crypto"
import assert from "node:assert/strict"
import { adaptResourceGraph } from "../../../USL/dist/src/integrations/resource-graph.js"
import { agentContext } from "../../../USL/dist/src/language/navigation.js"

const directory = resolve(process.argv[2] ?? "")
assert.ok(process.argv[2], "Explicit run directory required")
const read = (path: string) => JSON.parse(readFileSync(path, "utf8")) as Record<string, unknown>
const sha = (data: Uint8Array) => createHash("sha256").update(data).digest("hex")
const summary = read(join(directory, "summary.json"))
assert.equal(summary["accepted"], true, "A failed/partial study is not a learned-policy view")
const before = read(join(directory, "observations-only-worker.json"))
const after = read(join(directory, "learned-worker.json"))
const outcome = read(join(directory, `learn-${summary["policyRevision"]}.json`))
const source = "sym:AbstractNode:hswm-tool-harness-2026-10-20-root"
const resources = [
  { id: source, types: ["urn:hswm:ToolHarnessDesign"], locator: "file://localhost" + new URL("../../ontology/development/HSWM_TOOL_HARNESS_2026-10-20.v1.json", import.meta.url).pathname,
    metadata: { status: "DESIGN_SOURCE_NOT_EXECUTED_BY_ITSELF" } },
  { id: "hswm:tool-harness-learning:policy:0", types: ["urn:hswm:NativePolicyRevision"], locator: `file://localhost${join(directory, "observations-only-worker.json")}`,
    metadata: { nativeKey: before["policyKey"], content: before["policyContent"], phase: "observations-only" } },
  { id: "hswm:tool-harness-learning:outcome:18", types: ["urn:hswm:ObservedOutcome"], locator: `file://localhost${join(directory, "learn-18.json")}`,
    metadata: { outcome: outcome["outcomeContent"], authority: "AGENT_AUTHORED_EVALUATOR_OF_ACTUAL_CLI_BYTES" } },
  { id: "hswm:tool-harness-learning:policy:18", types: ["urn:hswm:NativePolicyRevision"], locator: `file://localhost${join(directory, "learned-worker.json")}`,
    metadata: { nativeKey: after["policyKey"], content: after["policyContent"], phase: "learned" } },
  { id: "hswm:tool-harness-learning:comparison", types: ["urn:hswm:PairedComparison"], locator: `file://localhost${join(directory, "summary.json")}`,
    metadata: { sha256: sha(readFileSync(join(directory, "summary.json"))), claimCeiling: summary["claimCeiling"] } }
]
const graph = { schema: "usl-resource-graph/v1", resources,
  meanings: [{ id: "urn:hswm:source-outcome-policy-comparison", description: "Source design, initial native policy, exact observed feedback, admitted successor and controlled comparison. Mapping is not authority or an efficacy claim beyond the recorded scope." }],
  links: [{ id: "hswm:tool-harness-learning:controlled-update", meaning: "urn:hswm:source-outcome-policy-comparison",
    participants: [
      { role: "source", resource: source }, { role: "before", resource: "hswm:tool-harness-learning:policy:0" },
      { role: "feedback", resource: "hswm:tool-harness-learning:outcome:18" }, { role: "after", resource: "hswm:tool-harness-learning:policy:18" },
      { role: "comparison", resource: "hswm:tool-harness-learning:comparison" }
    ] }]
}
const adapted = adaptResourceGraph(JSON.stringify(graph), { namespace: "hswm.tool-harness.learning.evidence.v1" })
if (adapted._tag === "Left") throw adapted.left
const focus = adapted.right.identities.resources[source]
const target = adapted.right.identities.resources["hswm:tool-harness-learning:policy:18"]
assert.ok(focus && target)
const navigation = agentContext(adapted.right.plan, {
  focus, target,
  maxHops: 1, maxResources: 8, maxLinks: 4, maxVisits: 32
})
if (navigation._tag === "Left") throw navigation.left
assert.equal(navigation.right.target?.status, "FOUND")
assert.equal(navigation.right.resources.length, 5)
console.log(JSON.stringify({ status: "USL_SOURCE_TO_NATIVE_SUCCESSOR_FOUND", resolverReads: 0, graph,
  context: navigation.right, sourceProtocolSha256: summary["protocolSha256"] }, null, 2))
