import { describe, expect, it } from "vitest"
import { compareToyMappings, decodeCrossLayerInputPacket, decodeMapSpec, makeToyInputPacket, makeToyMapSpec, makeToyModelRef, mapToyState, readToyFire, transitionToyState } from "../../src/hswm/effect-runtime/src/cross-layer-map-domain.js"

const digest = "a".repeat(64)
const isRight = (value: Readonly<{ readonly _tag: string }>): boolean => value._tag === "Right"
const isLeft = (value: Readonly<{ readonly _tag: string }>): boolean => value._tag === "Left"
const mapSpec = {
  schema: "hswm-cross-layer-map/v1",
  source: { modelRef: "toy/source", digest },
  target: { modelRef: "toy/semantic", digest: "b".repeat(64) },
  mappingKind: "drop_refractory",
  mappingMethod: "authored_deterministic",
  declaredLosses: ["refractory-state-r"],
  actionAllowlist: ["wait", "pulse", "block", "unblock"],
  time: { unit: "tick", horizon: 1 },
  supportScope: { world: "finite-toy-rh/v1", contexts: ["baseline"], observableFields: ["h"] }
} as const

describe("cross-layer map v1 domain", () => {
  it("strictly decodes a bounded MapSpec and rejects unknown or widened fields", () => {
    const decoded = decodeMapSpec(mapSpec)
    expect(isRight(decoded)).toBe(true)
    if (decoded._tag === "Right") expect(decoded.right.time).toEqual({ unit: "tick", horizon: 1 })
    for (const invalid of [
      { ...mapSpec, arbitrary: true },
      { ...mapSpec, source: { ...mapSpec.source, digest: "A".repeat(64) } },
      { ...mapSpec, actionAllowlist: ["pulse", "pulse"] },
      { ...mapSpec, time: { unit: "tick", horizon: 2 } },
      { ...mapSpec, supportScope: { ...mapSpec.supportScope, outcome: 1 } }
    ]) expect(isLeft(decodeMapSpec(invalid))).toBe(true)
  })

  it("refuses target leakage, future observations, and actions outside the declared map domain", () => {
    const packet = {
      subject: { observation: { h: 0 }, asOf: 4, requested: { action: "pulse", horizon: 1, window: { start: 6, end: 7 } } },
      context: mapSpec,
      evidence: [{ sourceRef: "world/observation/3", digest, observedAt: 3 }],
      eventTime: 5
    }
    expect(isRight(decodeCrossLayerInputPacket(packet))).toBe(true)
    for (const invalid of [
      { ...packet, subject: { ...packet.subject, observation: { h: 0, target: 1 } } },
      { ...packet, subject: { ...packet.subject, requested: { action: "pulse", horizon: 2, window: { start: 6, end: 7 } } } },
      { ...packet, context: { ...mapSpec, actionAllowlist: ["wait"] } },
      { ...packet, evidence: [{ ...packet.evidence[0], observedAt: 5 }] },
      { ...packet, subject: { ...packet.subject, asOf: 6 } }
    ]) expect(isLeft(decodeCrossLayerInputPacket(invalid))).toBe(true)
  })

  it("binds fixture model definitions to their actual definition-byte SHA-256 before making a packet", () => {
    const source = { modelRef: "fixture/source", definitionBytes: "toy-r-h-transition/v1" }
    const target = { modelRef: "fixture/semantic", definitionBytes: "semantic-r-h-readout/v1" }
    expect(makeToyModelRef(source).digest).toMatch(/^[a-f0-9]{64}$/u)
    expect(makeToyModelRef(source).digest).not.toBe(makeToyModelRef(target).digest)
    const lossy = makeToyMapSpec(source, target, "drop_refractory")
    expect(isRight(makeToyInputPacket(lossy, { h: 0 }, 3, "pulse"))).toBe(true)
    expect(isLeft(makeToyInputPacket(lossy, { r: 0, h: 0 }, 3, "pulse"))).toBe(true)
    const preserved = makeToyMapSpec(source, target, "preserve_r_h")
    expect(preserved.declaredLosses).toEqual([])
    expect(isRight(makeToyInputPacket(preserved, { r: 0, h: 0 }, 3, "pulse"))).toBe(true)
  })

  it("requires observation before mapping and makes its declared loss visible", () => {
    expect(mapToyState("preserve_r_h", { h: 0 })).toEqual({ kind: "needs_observation", missing: ["r"] })
    expect(mapToyState("drop_refractory", { r: 1 })).toEqual({ kind: "needs_observation", missing: ["h"] })
    expect(mapToyState("drop_refractory", { r: 1, h: 0 })).toEqual({ kind: "mapped", value: { h: 0 }, lossRefs: ["refractory-state-r"] })
  })

  it("keeps state-only lossy commutation separate from the impossible fire readout", () => {
    expect(transitionToyState({ r: 0, h: 0 }, "pulse")).toEqual({ r: 1, h: 0 })
    expect(transitionToyState({ r: 1, h: 0 }, "pulse")).toEqual({ r: 0, h: 0 })
    expect(readToyFire({ r: 0, h: 0 }, "pulse")).toBe(1)
    expect(readToyFire({ r: 1, h: 0 }, "pulse")).toBe(0)
    const compared = compareToyMappings()
    expect(compared.rows).toHaveLength(16)
    expect(compared.preserve).toEqual({ stateCommutingRows: 16, fireCommutingRows: 16 })
    expect(compared.dropRefractory.stateCommutingRows).toBe(16)
    expect(compared.dropRefractory.conflictingReadoutClasses).toEqual([{ mappedState: { h: 0 }, action: "pulse", fireValues: [0, 1] }])
    expect(compared.rows.filter(row => !row.lossyFireReadoutPossible)).toHaveLength(2)
  })
})
