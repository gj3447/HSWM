import { execFile, spawn } from "node:child_process"
import { createHash } from "node:crypto"
import { chmod, mkdir, mkdtemp, readFile, rm, symlink } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { promisify } from "node:util"

import { afterEach, expect, it } from "vitest"

import { executeDnrdRoutingDiagnosticProcess } from "../src/canonical-atom-v2-routing-diagnostic-process.js"

const roots: string[] = []
const hash = (value: string | Uint8Array): string => createHash("sha256").update(value).digest("hex")
const scorerSha = "s".replace("s", "a").repeat(64)
const implementationPath = resolve(import.meta.dirname, "../src/canonical-atom-v2-routing-diagnostic-process.ts")

const episode = (phase: "training" | "heldout", index: number, context: string, route: string | null) => {
  const canary = `dnrd-training-provenance:${index.toString(16).padStart(32, "0")}`
  return ({
  episode_id: `episode:${phase}:${index}`,
  stream_id: "stream-0",
  phase,
  context_key: context,
  candidate_route_ids: ["route:a", "route:b"],
  entity: `entity:${index}`,
  aliases: [`entity:${index}`, `entity:${index}:alias`],
  surface_template: `template:${index}`,
  prompt: phase === "training" ? `prompt:${index}\nTraining provenance marker: ${canary}` : `prompt:${index}`,
  route_evidence: [
    { route_id: "route:a", evidence_text: "a", response_token: "a" },
    { route_id: "route:b", evidence_text: "b", response_token: "b" }
  ],
  ...(phase === "training" ? { forced_route_id: route, provenance_canary: canary } : { arm_order: ["FULL", "NO_MEMORY_ROLLBACK", "BINDING_DERANGED_NUMERIC_PLACEBO"] })
  })
}

const stream = () => {
  const contexts = ["context:a", "context:b", "context:c", "context:d"]
  const coreOrder = [...contexts].sort((left, right) => hash(left).localeCompare(hash(right)))
  const matchedDerangement = Object.fromEntries(coreOrder.map((context, index) => [context, coreOrder[(index + 1) % coreOrder.length]!]))
  const training = contexts.flatMap((context, index) => [
    episode("training", index * 2, context, "route:a"),
    episode("training", index * 2 + 1, context, "route:b")
  ])
  return {
    stream_id: "stream-0",
    route_ids: ["route:a", "route:b"],
    context_keys: contexts,
    matched_derangement: matchedDerangement,
    training,
    heldout: contexts.flatMap((context, index) => [episode("heldout", index * 2, context, null), episode("heldout", index * 2 + 1, context, null)])
  }
}

const streamWithId = (streamId: string) => {
  const source = stream()
  return {
    ...source,
    stream_id: streamId,
    training: source.training.map((entry) => ({ ...entry, stream_id: streamId })),
    heldout: source.heldout.map((entry) => ({ ...entry, stream_id: streamId }))
  }
}

const stateKeys = ["state_sha256", "revision_id", "lineage_id", "owner_id", "mount_id", "mount_role", "immutable", "scores"] as const
type Wire = Record<string, unknown>
const state = (value: unknown): Wire => value as Wire
const execFileAsync = promisify(execFile)
const configFor = (root: string, frozenScorerSourceSha256 = scorerSha) => ({ frozen_scorer_source_sha256: frozenScorerSourceSha256, root_path: root })
const request = async (root: string, operation: string, payload: Wire, frozenScorerSourceSha256 = scorerSha): Promise<Wire> => {
  const config = configFor(root, frozenScorerSourceSha256)
  const implementationSha = hash(await readFile(implementationPath))
  return executeDnrdRoutingDiagnosticProcess({
    operation,
    implementation_path: implementationPath,
    implementation_sha256: implementationSha,
    config,
    config_sha256: hash(JSON.stringify(config)),
    payload
  })
}

const childRequest = async (childPath: string, config: Wire, operation: string, payload: Wire): Promise<Wire> => {
  const body = JSON.stringify({
    operation,
    implementation_path: childPath,
    implementation_sha256: hash(await readFile(childPath)),
    config,
    config_sha256: hash(JSON.stringify(config)),
    payload
  })
  const response = await new Promise<{ readonly code: number | null; readonly stdout: string; readonly stderr: string }>((resolveChild, rejectChild) => {
    const child = spawn(process.execPath, [childPath], { cwd: resolve(import.meta.dirname, ".."), stdio: ["pipe", "pipe", "pipe"] })
    let stdout = ""
    let stderr = ""
    const timer = setTimeout(() => {
      child.kill("SIGKILL")
      rejectChild(new Error("DNRD child request timed out"))
    }, 10_000)
    child.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString("utf8") })
    child.stderr.on("data", (chunk: Buffer) => { stderr += chunk.toString("utf8") })
    child.once("error", (error) => { clearTimeout(timer); rejectChild(error) })
    child.once("close", (code) => { clearTimeout(timer); resolveChild({ code, stdout, stderr }) })
    child.stdin.end(body)
  })
  if (response.code !== 0 || response.stderr !== "") throw new Error(`DNRD child refused: ${response.stderr}`)
  return JSON.parse(response.stdout) as Wire
}

const outcome = (trace: Wire, reward: -1_000_000 | 0 | 1_000_000 = 1_000_000): Wire => ({
  episode_id: trace["episode_id"],
  selected_route_id: trace["selected_route_id"],
  reward,
  outcome_digest: hash(`outcome:${trace["trace_id"]}:${reward}`),
  scorer_source_identity: scorerSha,
  scorer_address: "_research/dnrd/scorer.py",
  role_separation: "DECLARED_ROLE_SEPARATION_NOT_PROVEN"
})

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })))
})

it("initializes copied W0/W1, seals before outcome, and freshly recovers the exact routing state", async () => {
  const root = await mkdtemp(join(tmpdir(), "hswm-dnrd-process-"))
  roots.push(root)
  await chmod(root, 0o700)
  const initialized = await request(root, "INIT_STREAM", { stream: stream() })
  const w0 = state(initialized["w0"])
  const w1 = state(initialized["w1"])
  expect(Object.keys(w0).sort()).toEqual([...stateKeys].sort())
  expect(w0["state_sha256"]).toBe(w1["state_sha256"])
  expect(w0["mount_id"]).not.toBe(w1["mount_id"])
  expect(w0["mount_role"]).toBe("W0_ROLLBACK")
  expect(w1["mount_role"]).toBe("FULL_TRAINABLE")
  expect(initialized["equal_genesis_content"]).toBe(true)
  expect(String(initialized["common_prefix_sha256"])).toHaveLength(64)
  expect(Object.values(w0["scores"] as Record<string, Record<string, number>>).flatMap(Object.values).every((score) => score === 0)).toBe(true)
  await expect(request(root, "RECOVER", {
    state: { ...w0, mount_id: `dnrd-mount-v1-${"a".repeat(36)}` }
  })).rejects.toThrow(/mount_id is invalid/)

  const trace = await request(root, "SEAL_TRACE", {
    state: w1,
    episode_id: "episode:training:0",
    context_key: "context:a",
    selected_route_id: "route:a",
    request_sha256: hash("request"),
    response_sha256: hash("response")
  })
  expect(trace["routing_payload_sha256"]).toBe(w1["state_sha256"])
  const applied = await request(root, "APPLY_OUTCOME", { state: w1, trace, outcome: outcome(trace) })
  const w1After = state(applied["state"])
  expect(w1After["state_sha256"]).not.toBe(w1["state_sha256"])
  expect((w1After["scores"] as Record<string, Record<string, number>>)["context:a"]?.["route:a"]).toBe(100_000)
  expect((applied["receipt"] as Wire)["scorer_provenance"]).toEqual({ scorer_address: "_research/dnrd/scorer.py", scorer_source_identity: scorerSha, role_separation: "DECLARED_ROLE_SEPARATION_NOT_PROVEN" })
  expect(((applied["receipt"] as Wire)["credit_receipt"] as Wire)["updatedRouteCount"]).toBe(1)
  const recovered = await request(root, "RECOVER", { state: w1After })
  expect(recovered["state"]).toEqual(w1After)
  expect(recovered["fresh_process"]).toBe(true)
  expect(String(recovered["journal_sha256"])).toHaveLength(64)
})

it("materializes independently replayed RAW and exact DERANGED controls and refuses forged state/outcome", async () => {
  const root = await mkdtemp(join(tmpdir(), "hswm-dnrd-process-control-"))
  roots.push(root)
  await chmod(root, 0o700)
  const source = stream()
  const initialized = await request(root, "INIT_STREAM", { stream: source })
  const w0 = state(initialized["w0"])
  let full = state(initialized["w1"])
  const records: Wire[] = []
  await expect(request(root, "MATERIALIZE_CONTROL", {
    state: full,
    stream_id: "stream-0",
    arm: "RAW_EQUAL_BUDGET",
    raw_delta_rule: "signed_reward_times_100000_div_1000000/v1",
    training_update_records: [],
    required_training_outcome_count: 8
  })).rejects.toThrow(/RAW must materialize only from the immutable recovered W0/)
  await expect(request(root, "MATERIALIZE_CONTROL", {
    state: w0,
    stream_id: "stream-0",
    arm: "BINDING_DERANGED_NUMERIC_PLACEBO",
    matched_derangement: source.matched_derangement
  })).rejects.toThrow(/DERANGED must materialize only from the recovered trained FULL/)
  for (const training of source.training as Array<{ readonly episode_id: string; readonly context_key: string; readonly forced_route_id: string }>) {
    const trace = await request(root, "SEAL_TRACE", {
      state: full,
      episode_id: training.episode_id,
      context_key: training.context_key,
      selected_route_id: training.forced_route_id,
      request_sha256: hash(`request:${training.episode_id}`),
      response_sha256: hash(`response:${training.episode_id}`)
    })
    const scored = outcome(trace, training.forced_route_id === "route:a" ? 1_000_000 : -1_000_000)
    if (records.length === 0) {
      await expect(request(root, "APPLY_OUTCOME", { state: full, trace, outcome: { ...scored, scorer_source_identity: "f".repeat(64) } })).rejects.toThrow(/scorer source differs/)
      await expect(request(root, "APPLY_OUTCOME", { state: full, trace, outcome: { ...scored, scorer_address: "forged:scorer" } })).rejects.toThrow(/scorer address differs/)
    }
    const applied = await request(root, "APPLY_OUTCOME", { state: full, trace, outcome: scored })
    full = state(applied["state"])
    records.push({ episode_id: training.episode_id, context_key: training.context_key, selected_route_id: training.forced_route_id, reward: scored["reward"], trace_id: trace["trace_id"], outcome_digest: scored["outcome_digest"] })
    if (records.length === 1) {
      await expect(request(root, "MATERIALIZE_CONTROL", {
        state: full,
        stream_id: "stream-0",
        arm: "BINDING_DERANGED_NUMERIC_PLACEBO",
        matched_derangement: source.matched_derangement
      })).rejects.toThrow(/requires exactly all eight once-credited/)
    }
  }
  const rawRequest = {
    state: w0,
    stream_id: "stream-0",
    arm: "RAW_EQUAL_BUDGET",
    raw_delta_rule: "signed_reward_times_100000_div_1000000/v1",
    training_update_records: records,
    required_training_outcome_count: 8
  }
  const raw = await request(root, "MATERIALIZE_CONTROL", rawRequest)
  const rawState = state(raw["state"])
  expect((rawState["scores"] as Record<string, Record<string, number>>)["context:a"]).toEqual({ "route:a": 100_000, "route:b": -100_000 })
  expect(rawState["scores"]).toEqual(full["scores"])
  await expect(request(root, "MATERIALIZE_CONTROL", rawRequest)).rejects.toThrow(/control reservation already exists/)
  const derangedRequest = {
    state: full,
    stream_id: "stream-0",
    arm: "BINDING_DERANGED_NUMERIC_PLACEBO",
    matched_derangement: source.matched_derangement
  }
  const deranged = await request(root, "MATERIALIZE_CONTROL", derangedRequest)
  const derangedState = state(deranged["state"])
  const derangedScores = derangedState["scores"] as Record<string, Record<string, number>>
  const fullScores = full["scores"] as Record<string, Record<string, number>>
  expect(derangedScores["context:a"]).toEqual(fullScores[source.matched_derangement["context:a"]!])
  await expect(request(root, "MATERIALIZE_CONTROL", derangedRequest)).rejects.toThrow(/control reservation already exists/)
  await expect(request(root, "MATERIALIZE_CONTROL", { ...derangedRequest, state: rawState })).rejects.toThrow(/DERANGED must materialize only from the recovered trained FULL/)

  for (const [mounted, role] of [[w0, "W0_ROLLBACK"], [full, "FULL_TRAINABLE"], [rawState, "RAW_CONTROL"], [derangedState, "DERANGED_CONTROL"]] as const) {
    const recovered = await request(root, "RECOVER", { state: mounted })
    const payloadUtf8 = String(recovered["routing_payload_utf8"])
    expect(recovered["mount_role"]).toBe(role)
    expect(hash(payloadUtf8)).toBe(recovered["routing_payload_sha256"])
    expect(Buffer.byteLength(payloadUtf8, "utf8")).toBe(recovered["routing_payload_bytes"])
    expect(recovered["routing_payload_sha256"]).toBe(mounted["state_sha256"])
    expect(String(recovered["process_instance_id"])).toMatch(/^[0-9a-f-]{36}$/)
  }

  await expect(request(root, "RECOVER", { state: { ...full, state_sha256: "f".repeat(64) } })).rejects.toThrow(/does not exactly match/)
  await expect(request(root, "RECOVER", { state: { ...full, mount_role: "W0_ROLLBACK" } })).rejects.toThrow(/does not exactly match/)
  const heldoutTrace = await request(root, "SEAL_TRACE", {
    state: full,
    episode_id: "episode:heldout:0",
    context_key: "context:a",
    selected_route_id: "route:a",
    request_sha256: hash("forged-request"),
    response_sha256: hash("forged-response")
  })
  await expect(request(root, "APPLY_OUTCOME", { state: full, trace: heldoutTrace, outcome: outcome(heldoutTrace) })).rejects.toThrow(/heldout traces remain read-only/)
  await expect(request(root, "SEAL_TRACE", {
    state: w0,
    episode_id: "episode:training:0",
    context_key: "context:a",
    selected_route_id: "route:a",
    request_sha256: hash("pinned-request"),
    response_sha256: hash("pinned-response")
  })).rejects.toThrow(/only the FULL trainable mount may seal/)
  const trainingTrace = await request(root, "SEAL_TRACE", {
    state: full,
    episode_id: "episode:training:0",
    context_key: "context:a",
    selected_route_id: "route:a",
    request_sha256: hash("pinned-full-request"),
    response_sha256: hash("pinned-full-response")
  })
  await expect(request(root, "APPLY_OUTCOME", { state: w0, trace: trainingTrace, outcome: outcome(trainingTrace) })).rejects.toThrow(/only the immutable FULL trainable mount role/)
  await expect(request(root, "APPLY_OUTCOME", { state: rawState, trace: trainingTrace, outcome: outcome(trainingTrace) })).rejects.toThrow(/only the immutable FULL trainable mount role/)
  await expect(request(root, "APPLY_OUTCOME", { state: derangedState, trace: trainingTrace, outcome: outcome(trainingTrace) })).rejects.toThrow(/only the immutable FULL trainable mount role/)
  await expect(request(root, "APPLY_OUTCOME", { state: full, trace: trainingTrace, outcome: outcome(trainingTrace) })).rejects.toThrow(/one registered training episode may produce at most one/)
}, 60_000)

it("freezes one scorer configuration and one occurrence per frozen stream identity", async () => {
  const root = await mkdtemp(join(tmpdir(), "hswm-dnrd-process-reservation-"))
  roots.push(root)
  await chmod(root, 0o700)
  const initialized = await request(root, "INIT_STREAM", { stream: stream() })
  await expect(request(root, "INIT_STREAM", { stream: stream() })).rejects.toThrow(/stream reservation already exists/)
  await expect(request(root, "RECOVER", { state: state(initialized["w0"]) }, "f".repeat(64))).rejects.toThrow(/already frozen to a different scorer/)

  const anotherRoot = await mkdtemp(join(tmpdir(), "hswm-dnrd-process-stream-id-"))
  roots.push(anotherRoot)
  await chmod(anotherRoot, 0o700)
  await expect(request(anotherRoot, "INIT_STREAM", { stream: streamWithId("stream-4") })).rejects.toThrow(/only the four frozen DNRD stream identities/)
})

it("requires a prompt-bound provenance canary only on training episodes", async () => {
  const missingRoot = await mkdtemp(join(tmpdir(), "hswm-dnrd-process-canary-missing-"))
  roots.push(missingRoot)
  await chmod(missingRoot, 0o700)
  const missing = stream() as unknown as { readonly training: Wire[] }
  delete missing.training[0]!["provenance_canary"]
  await expect(request(missingRoot, "INIT_STREAM", { stream: missing })).rejects.toThrow(/missing or excess fields/)

  const promptRoot = await mkdtemp(join(tmpdir(), "hswm-dnrd-process-canary-prompt-"))
  roots.push(promptRoot)
  await chmod(promptRoot, 0o700)
  const absentFromPrompt = stream() as unknown as { readonly training: Wire[] }
  absentFromPrompt.training[0]!["prompt"] = "prompt without marker"
  await expect(request(promptRoot, "INIT_STREAM", { stream: absentFromPrompt })).rejects.toThrow(/malformed or absent from its prompt/)

  const heldoutRoot = await mkdtemp(join(tmpdir(), "hswm-dnrd-process-canary-heldout-"))
  roots.push(heldoutRoot)
  await chmod(heldoutRoot, 0o700)
  const heldout = stream() as unknown as { readonly heldout: Wire[] }
  heldout.heldout[0]!["provenance_canary"] = `dnrd-training-provenance:${"f".repeat(32)}`
  await expect(request(heldoutRoot, "INIT_STREAM", { stream: heldout })).rejects.toThrow(/missing or excess fields/)
})

it("accepts only the three DNRD-3 scientific arms in heldout order", async () => {
  const root = await mkdtemp(join(tmpdir(), "hswm-dnrd-process-arm-order-"))
  roots.push(root)
  await chmod(root, 0o700)
  const source = stream() as unknown as { readonly heldout: Wire[] }
  source.heldout[0]!["arm_order"] = [
    "FULL",
    "NO_MEMORY_ROLLBACK",
    "RAW_EQUAL_BUDGET",
    "BINDING_DERANGED_NUMERIC_PLACEBO"
  ]
  await expect(request(root, "INIT_STREAM", { stream: source })).rejects.toThrow(
    /heldout arm order differs from frozen arm set/
  )
})

it("accepts the exact public stream emitted by the Python fixture generator", async () => {
  const root = await mkdtemp(join(tmpdir(), "hswm-dnrd-process-python-contract-"))
  roots.push(root)
  await chmod(root, 0o700)
  const repository = resolve(import.meta.dirname, "../../../..")
  const generated = await execFileAsync(
    "python3",
    [
      "-c",
      "from _research.dnrd.task_family import canonical_json,generate_manifests; public,_=generate_manifests(bytes(range(32))); print(canonical_json(public).decode('ascii'))"
    ],
    { cwd: repository, encoding: "utf8" }
  )
  const publicManifest = JSON.parse(generated.stdout) as { readonly streams: ReadonlyArray<Wire> }
  const initialized = await request(root, "INIT_STREAM", { stream: publicManifest.streams[0]! })
  expect(Object.keys(state(initialized["w0"])).sort()).toEqual([...stateKeys].sort())
})

it("rejects a non-core derangement even when zero or repeated score vectors hide the wrong binding", async () => {
  const root = await mkdtemp(join(tmpdir(), "hswm-dnrd-process-derangement-"))
  roots.push(root)
  await chmod(root, 0o700)
  const source = stream()
  const wrongButFixedPointFree = {
    "context:a": "context:b",
    "context:b": "context:c",
    "context:c": "context:d",
    "context:d": "context:a"
  }
  expect(wrongButFixedPointFree).not.toEqual(source.matched_derangement)
  await expect(request(root, "INIT_STREAM", {
    stream: { ...source, matched_derangement: wrongButFixedPointFree }
  })).rejects.toThrow(/differs structurally from the exact TS-core SHA-ordered binding/)
})

it("fails closed for a nonprivate or symlinked dedicated root", async () => {
  const parent = await mkdtemp(join(tmpdir(), "hswm-dnrd-process-root-"))
  roots.push(parent)
  const unsafe = join(parent, "unsafe")
  await chmod(parent, 0o700)
  await mkdir(unsafe, { mode: 0o755 })
  await chmod(unsafe, 0o755)
  await expect(request(unsafe, "INIT_STREAM", { stream: stream() })).rejects.toThrow(/private 0700/)
  const safe = join(parent, "safe")
  await mkdir(safe, { mode: 0o700 })
  await chmod(safe, 0o700)
  const linked = join(parent, "linked")
  await symlink(safe, linked)
  await expect(request(linked, "INIT_STREAM", { stream: stream() })).rejects.toThrow(/plain private 0700/)
})

it("runs INIT, seal, declared scorer envelope, apply, and two recoveries in actual fresh child processes", async () => {
  const root = await mkdtemp(join(tmpdir(), "hswm-dnrd-process-child-"))
  roots.push(root)
  await chmod(root, 0o700)
  const packageRoot = resolve(import.meta.dirname, "..")
  const childPath = join(packageRoot, "dist", "canonical-atom-v2-routing-diagnostic-process.js")
  await execFileAsync(process.execPath, [join(packageRoot, "node_modules", "typescript", "bin", "tsc"), "-p", "tsconfig.build.json"], { cwd: packageRoot })
  const config = configFor(root)
  const initialized = await childRequest(childPath, config, "INIT_STREAM", { stream: stream() })
  const w1 = state(initialized["w1"])
  const trace = await childRequest(childPath, config, "SEAL_TRACE", {
    state: w1,
    episode_id: "episode:training:0",
    context_key: "context:a",
    selected_route_id: "route:a",
    request_sha256: hash("child-request"),
    response_sha256: hash("child-response")
  })
  const applied = await childRequest(childPath, config, "APPLY_OUTCOME", { state: w1, trace, outcome: outcome(trace) })
  const after = state(applied["state"])
  const firstRecovery = await childRequest(childPath, config, "RECOVER", { state: after })
  const secondRecovery = await childRequest(childPath, config, "RECOVER", { state: after })
  expect(initialized["equal_genesis_content"]).toBe(true)
  expect(firstRecovery["state"]).toEqual(after)
  expect(firstRecovery["mount_role"]).toBe("FULL_TRAINABLE")
  expect(firstRecovery["routing_payload_sha256"]).toBe(after["state_sha256"])
  expect(firstRecovery["process_instance_id"]).not.toBe(secondRecovery["process_instance_id"])
}, 45_000)
