import { readFileSync, writeFileSync, chmodSync, mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { initializeNeuralGate, neuralGateForward, neuralGateGradient, trainNeuralGate } from "../../src/hswm/effect-runtime/src/semantic-context-neural-domain.js"
import { decodeActivationPolicy, initializeActivation, chooseActivation, updateActivation } from "../../src/hswm/effect-runtime/src/semantic-context-activation-domain.js"
import { CanonicalAtomV2DurableRuntime, makeCanonicalAtomV2DurableRuntimeFileLayer } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.js"
import { canonicalAtomV2SchemaContentBytes, decodeCanonicalAtomV2SchemaContent, describeCanonicalAtomV2Envelope, makeCanonicalAtomV2ContentBoundInput } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.js"
import { HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION } from "../../src/hswm/effect-runtime/src/canonical-atom-v2-schema.js"
import { NodePosixServicesLive } from "../../src/hswm/effect-runtime/src/effect-posix-services.js"
import { NodePosixFileSystem } from "../../src/hswm/effect-runtime/src/effect-posix-filesystem.js"
import { withLocalActivationSession } from "../../src/hswm/effect-runtime/src/semantic-context-read-session.js"
import { decodeWorkspaceManifest } from "../../src/hswm/effect-runtime/src/workspace-manifest-domain.js"
import { readWorkspaceActivationSource, selectWorkspaceSourceUnit, seedWorkspaceActivation, executeWorkspaceActivation, workspaceActivationSchema, workspaceActivationConfig,
  workspaceActivationSpec, type WorkspaceActivationSource } from "../../src/hswm/effect-runtime/src/workspace-activation-runtime.js"
import { contextHash } from "../../src/hswm/effect-runtime/src/semantic-context-domain.js"
import { workspaceSourceUnits } from "../../src/hswm/effect-runtime/src/workspace-source-units-domain.js"
import { kgSha256 } from "../../src/hswm/effect-runtime/src/native-kg-bundle-domain.js"
import { prepareSemanticContext } from "../../src/hswm/effect-runtime/src/semantic-context-runtime.js"
import { unwrap } from "./semantic-context-fixture.js"

const neural = { hiddenUnits: 8, learningRate: 0.3, gradientNormLimit: 1, seed: 37 }
it("splits complete Markdown units without treating fenced headings as routes or losing UTF-8 bytes", () => {
  const document = "서문\r\n# 실제 제목\r\n본문\n```md\n# 가짜 제목\n```\n## 예외\nUNKNOWN이면 중단.\n"
  const units = workspaceSourceUnits(document)
  expect(units.map(u => u.heading?.text ?? null)).toEqual([null, "실제 제목", "예외"])
  expect(units.map(u => u.text).join("")).toBe(document)
  const encoded = new TextEncoder().encode(document)
  for (const unit of units) expect(new TextDecoder().decode(encoded.slice(unit.startByte, unit.endByte))).toBe(unit.text)
  expect(units.at(-1)?.endByte).toBe(encoded.byteLength)
})
it("matches independent finite differences for both hidden and expert weights", () => {
  const gate = initializeNeuralGate(2, 2, neural), x = [0.3, -0.7], epsilon = 1e-5
  const gradient = neuralGateGradient(gate, x, 1, 0.8)
  const loss = (g: typeof gate) => 0.5 * ((neuralGateForward(g, x).means[1] ?? NaN) - 0.8) ** 2
  for (const part of ["hidden", "outputs"] as const) for (let i = 0; i < gate[part].length; i++) for (let j = 0; j < (gate[part][i]?.length ?? 0); j++) {
    const change = (d: number) => ({ ...gate, [part]: gate[part].map((row, a) => row.map((v, b) => v + (a === i && b === j ? d : 0))) })
    expect((loss(change(epsilon)) - loss(change(-epsilon))) / (2 * epsilon)).toBeCloseTo(gradient[part][i]?.[j] ?? NaN, 7)
  }
})
it("learns a nonlinear operator boundary without labels for unexecuted alternatives", () => {
  let gate = initializeNeuralGate(2, 2, neural)
  const cases = [[-1, -1], [-1, 1], [1, -1], [1, 1]]
  for (let epoch = 0; epoch < 1600; epoch++) for (const [i, x] of cases.entries()) {
    const selected = epoch % 2, reward = Number(selected === (i === 0 || i === 3 ? 0 : 1))
    gate = unwrap(trainNeuralGate(gate, x, selected, reward, neural))
  }
  for (const [i, x] of cases.entries()) {
    const scores = neuralGateForward(gate, x).means
    expect((scores[0] ?? NaN) > (scores[1] ?? NaN) ? 0 : 1).toBe(i === 0 || i === 3 ? 0 : 1)
  }
  expect(Either.isLeft(trainNeuralGate(gate, [1], 99, 1, neural))).toBe(true)
})

const source = (): WorkspaceActivationSource => {
  const sourceText = "# Source title\n\nThis is a bounded source. Exception: unknown means UNKNOWN.\n"
  const binding = { contract: "hswm-workspace-source-consumer/v1", entryId: "test", title: "test", document: "docs/test.md",
    activationSha256: kgSha256(sourceText), activationBytes: new TextEncoder().encode(sourceText).byteLength,
    selection: { kind: "COMPLETE_DOCUMENT" as const, unitId: null, startByte: 0, endByte: new TextEncoder().encode(sourceText).byteLength },
    documentSha256: kgSha256(sourceText), documentBytes: new TextEncoder().encode(sourceText).byteLength, bundle: "ontology/test.json", bundleSha256: "0".repeat(64),
    historicalSourceOnly: false, route: [], authority: "SECONDARY_AI_CURRENT_CHECKOUT_OBSERVATION_NOT_HISTORICAL_REPIN" }
  return { binding, sourceText, documentText: sourceText, units: workspaceSourceUnits(sourceText), observations: [], sourceId: contextHash(binding) }
}
const schemaBytes = unwrap(canonicalAtomV2SchemaContentBytes(workspaceActivationSchema))
const schemaHash = unwrap(decodeCanonicalAtomV2SchemaContent(schemaBytes)).binding.content.sha256
const layer = (root: string) => makeCanonicalAtomV2DurableRuntimeFileLayer(root, "workspace-source", schemaBytes, [{
  authorizationRef: "workspace-source-operator", schemaVersion: workspaceActivationSchema.schemaVersion, schemaContentSha256: schemaHash, scopes: ["read-reason-source"] }])
const fixture = async (work: (root: string) => Promise<void>) => { const root = mkdtempSync(join(tmpdir(), "neural-workspace-")); try { await work(root) } finally { rmSync(root, { recursive: true, force: true }) } }
const request = { question: "Return the first heading exactly.", intent: "EXACT" as const, mode: "TRAIN" as const,
  cell: { base_url: "https://fixture.invalid/v1", model: "SCRIPTED_NOT_PROVIDER", max_tokens: 64 } }
const ports = (runtime: CanonicalAtomV2DurableRuntime["Type"]) => ({
  http: { postJson: () => Effect.succeed(new TextEncoder().encode(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ prediction: "Source title", uncertainty: "fixture" }) } }] }))) },
  admit: (p: { candidate: unknown }) => runtime.submit(p.candidate),
  evaluate: () => Effect.succeed({ reward: 1, observed: "Source title", source: "AUTHORED_SOURCE_HEADING_ORACLE", continue: true })
})

it("persists neural parameters through the native owner and reopens the exact policy", () => fixture(async root => {
  const beforeAfter = await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    yield* seedWorkspaceActivation(runtime, source())
    const result = yield* withLocalActivationSession(root, runtime, local => executeWorkspaceActivation(local, source(), request, ports(local)))
    expect(result.result.status).toBe("UPDATED")
    expect(result.reads.fullSnapshots).toBe(2)
    expect(result.reads.nativeSubmissions).toBe(1)
    expect(result.reads.snapshotRequests).toBeGreaterThan(15)
    expect(result.result.proposal?.policy.contract).toBe("hswm-context-activation-policy/v2")
    if (result.result.proposal) expect(Either.isLeft(yield* Effect.either(runtime.submit(result.result.proposal.candidate)))).toBe(true)
    expect((yield* runtime.snapshot).canonical.revision).toBe(3)
    return result.result.proposal?.policy
  }).pipe(Effect.provide(layer(root)), Effect.provide(NodePosixServicesLive)))
  await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const result = yield* withLocalActivationSession(root, runtime, local => executeWorkspaceActivation(local, source(), { ...request, mode: "AUDIT" }, ports(local)))
    expect(result.result.execution.selection.policyKey.revisionId).toBe(1)
    expect(result.reads.nativeSubmissions).toBe(0)
    expect(result.result.execution.selection.policySha256).toBe(contextHash(beforeAfter))
  }).pipe(Effect.provide(layer(root)), Effect.provide(NodePosixServicesLive)))
}), 60000)

it("keeps v1 bytes/semantics and rejects neural dimension, scope and feedback drift", () => fixture(async root => {
  await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    yield* seedWorkspaceActivation(runtime, source())
    const plan = yield* prepareSemanticContext(runtime, workspaceActivationSpec("question"))
    const legacy = unwrap(initializeActivation(plan, { encoderRevision: "legacy", featureNames: ["x"], alpha: 1 }))
    expect(legacy.contract).toBe("hswm-context-activation-policy/v1")
    expect("network" in legacy).toBe(false)
    const policy = unwrap(initializeActivation(plan, workspaceActivationConfig))
    const features = { encoderRevision: workspaceActivationConfig.encoderRevision, eventSha256: contextHash(plan.spec.event), values: [1, 0, 0.1] }
    expect(unwrap(chooseActivation(plan, policy, features, "EXPLOIT")).source).toBe("NEURAL_TOP1_OPERATOR_GATE_NOT_LLM_WEIGHT_TRAINING")
    expect(Either.isLeft(decodeActivationPolicy({ ...policy, network: { hidden: [[1]], outputs: [[1]] } }))).toBe(true)
    expect(Either.isLeft(chooseActivation(plan, policy, { ...features, eventSha256: "0".repeat(64) }, "EXPLOIT"))).toBe(true)
    expect(Either.isLeft(updateActivation(policy, "missing", features, 1, "0".repeat(64)))).toBe(true)
  }).pipe(Effect.provide(layer(root)), Effect.provide(NodePosixServicesLive)))
}), 60000)

it("binds explicit sections to their parent and refuses fabricated ranges before native mutation", () => fixture(async root => {
  await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const selected = yield* selectWorkspaceSourceUnit(source(), "section:0")
    const forgedBinding = { ...selected.binding, selection: { ...selected.binding.selection, startByte: 1 } }
    const bad = yield* Effect.either(seedWorkspaceActivation(runtime, { ...selected, binding: forgedBinding, sourceId: contextHash(forgedBinding) }))
    expect(Either.isLeft(bad)).toBe(true)
    expect((yield* runtime.snapshot).canonical.revision).toBe(0)
    expect(Either.isLeft(yield* Effect.either(selectWorkspaceSourceUnit(source(), "section:missing")))).toBe(true)
    yield* seedWorkspaceActivation(runtime, selected)
    const state = yield* runtime.snapshot
    expect(state.canonical.atoms.find(a => a.key.atomUid === "source:catalog")?.references.map(r => r.target.atomUid)).toEqual(["source:section:0"])
    let leaked: CanonicalAtomV2DurableRuntime["Type"] | undefined
    yield* withLocalActivationSession(root, runtime, local => Effect.sync(() => { leaked = local }))
    if (!leaked) return yield* Effect.fail("missing fixture")
    expect(Either.isLeft(yield* Effect.either(leaked.snapshot))).toBe(true)
    const closedWrite = yield* Effect.either(leaked.stageContent("text/plain", new TextEncoder().encode("closed")))
    expect(Either.isLeft(closedWrite)).toBe(true)
  }).pipe(Effect.provide(layer(root)), Effect.provide(NodePosixServicesLive)))
}), 60000)

it("rejects outside-owner head advancement inside a read session", () => fixture(async root => {
  await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    yield* seedWorkspaceActivation(runtime, source())
    const result = yield* Effect.either(withLocalActivationSession(root, runtime, local => Effect.gen(function* () {
      const snapshot = yield* local.snapshot
      const first = snapshot.canonical.atoms.find(a => a.kind === "semantic_participant")
      if (!first) return yield* Effect.fail("missing fixture")
      const atom = { ...first, key: { ...first.key, atomUid: "source:outside" },
        provenance: { mode: "DERIVATION" as const, sourceRef: first.key, evidenceSha256: first.content.sha256 } }
      const envelope = yield* describeCanonicalAtomV2Envelope(atom)
      yield* runtime.submit(makeCanonicalAtomV2ContentBoundInput(runtime.schemaContent.content.sha256, {
        _tag: "CommitCanonicalAtomsV2", contractVersion: HSWM_CANONICAL_TRANSITION_V2_CONTRACT_VERSION,
        transitionId: "outside-writer", expectedStateRevision: snapshot.canonical.revision, schemaVersion: runtime.schema.schemaVersion,
        actorClaim: "test", authorizationRef: "workspace-source-operator", scope: "read-reason-source", decidedAt: "2026-10-24T00:00:00.000Z",
        traceRef: null, readSet: [first.key], writes: [atom], provenanceSha256: atom.content.sha256
      }, [{ key: atom.key, payload: atom.content, envelope }]))
      return yield* local.snapshot
    })))
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) expect(result.left).toMatchObject({ detail: expect.stringContaining("advanced") })
  }).pipe(Effect.provide(layer(root)), Effect.provide(NodePosixServicesLive)))
}), 60000)

it("connects every current workspace topic with exact declared hops and complete source bytes", async () => {
  const checkout = resolve(import.meta.dirname, "../..")
  const manifest = unwrap(decodeWorkspaceManifest(JSON.parse(readFileSync(join(checkout, "ontology/workspace/HSWM_WORKSPACE.v1.json"), "utf8"))))
  const covered: string[] = []
  for (const entry of manifest.entries) {
    const reads: string[] = []
    const observed = await Effect.runPromise(readWorkspaceActivationSource(manifest, entry.id, (path, maximumBytes = 16777216) => {
      reads.push(path)
      return NodePosixFileSystem.readRegularBounded(join(checkout, path), { maximumBytes, operation: "workspace-activation-test" }).pipe(Effect.map(r => r.bytes))
    }))
    expect(observed.binding.documentSha256).toBe(kgSha256(readFileSync(join(checkout, entry.document))))
    expect(observed.sourceText).toBe(readFileSync(join(checkout, entry.document), "utf8"))
    expect(new Set(reads.filter(p => manifest.entries.some(e => e.document === p)))).toEqual(new Set([entry.document]))
    expect(observed.binding.historicalSourceOnly).toBe(entry.projection_profile === "SOURCE_ONLY")
    covered.push(entry.id)
  }
  expect(covered).toHaveLength(49)
}, 60000)


it("admits all 49 actual source catalogs within native batch bounds before any provider call", () => fixture(async root => {
  const checkout = resolve(import.meta.dirname, "../..")
  const manifest = unwrap(decodeWorkspaceManifest(JSON.parse(readFileSync(join(checkout, "ontology/workspace/HSWM_WORKSPACE.v1.json"), "utf8"))))
  for (const entry of manifest.entries) {
    await Effect.runPromise(Effect.gen(function* () {
      const whole = yield* readWorkspaceActivationSource(manifest, entry.id, (path, maximumBytes = 16777216) =>
        NodePosixFileSystem.readRegularBounded(join(checkout, path), { maximumBytes, operation: "source-admission-test" }).pipe(Effect.map(r => r.bytes)))
      const first = whole.units.find(u => u.heading?.level === 1)
      if (!first) return yield* Effect.fail("No first heading")
      const selected = yield* selectWorkspaceSourceUnit(whole, first.id)
      const runtime = yield* CanonicalAtomV2DurableRuntime
      yield* seedWorkspaceActivation(runtime, selected)
      const state = yield* runtime.snapshot
      expect(state.canonical.revision).toBe(Math.ceil((whole.units.length + 9) / 64) + 1)
      expect(state.canonical.atoms.filter(a => a.key.atomUid.startsWith("source:section:"))).toHaveLength(whole.units.length)
      expect(state.canonical.atoms.find(a => a.key.atomUid === "source:catalog")?.references).toHaveLength(whole.units.length)
      expect(state.canonical.atoms.filter(a => a.provenance.mode === "BOOTSTRAP").length).toBeLessThanOrEqual(64)
    }).pipe(Effect.provide(layer(join(root, entry.id))), Effect.provide(NodePosixServicesLive)))
  }
}), 180000)


it.each(["selected-content", "head", "unrelated-final"] as const)("detects %s corruption at the declared session boundary", target => fixture(async root => {
  await Effect.runPromise(Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    yield* seedWorkspaceActivation(runtime, source())
    let reachedFinal = false
    const result = yield* Effect.either(withLocalActivationSession(root, runtime, local => Effect.gen(function* () {
      const snapshot = yield* local.snapshot
      const selected = snapshot.canonical.atoms.find(a => a.key.atomUid === (target === "unrelated-final" ? "source:catalog" : "source:evidence"))
      if (!selected) return yield* Effect.fail("missing fixture")
      const path = target === "head" ? join(root, "journal-objects", snapshot.journalHead.sha256) : join(root, "objects", selected.content.sha256)
      yield* Effect.sync(() => {
        const bytes = readFileSync(path)
        bytes[0] = (bytes[0] ?? 0) ^ 1
        chmodSync(path, 0o600); writeFileSync(path, bytes); chmodSync(path, 0o400)
      })
      if (target === "selected-content") yield* local.readContent(selected.content)
      else yield* local.snapshot
      reachedFinal = true
    })))
    expect(Either.isLeft(result)).toBe(true)
    expect(reachedFinal).toBe(target === "unrelated-final")
  }).pipe(Effect.provide(layer(root)), Effect.provide(NodePosixServicesLive)))
}), 60000)
