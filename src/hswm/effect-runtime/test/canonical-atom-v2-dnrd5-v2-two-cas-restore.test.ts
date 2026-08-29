import { expect, it } from "@effect/vitest"
import { Effect, Either } from "effect"

import {
  CanonicalAtomV2DurableRuntime,
  recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal
} from "../src/canonical-atom-v2-durable-runtime.js"
import {
  resumeDnrd5V2AdmitTwoCas,
  resumeDnrd5V2RestoreTwoCas,
  submitDnrd5V2AdmitTwoCas,
  submitDnrd5V2RestoreTwoCas
} from "../src/canonical-atom-v2-dnrd5-durable-permit.js"
import {
  canonicalJsonBytes,
  decodeCanonicalJsonBytes
} from "../src/canonical-atom-v2-json.js"
import { canonicalAtomV2KeyId } from "../src/canonical-atom-v2-schema.js"
import type { Dnrd5V2RestorePreparedFixture } from "./fixtures/canonical-atom-v2-dnrd5-v2-two-cas.js"
import {
  makeDnrd5V2TwoCasLayer,
  prepareDnrd5V2RestoreFixture,
  prepareDnrd5V2TwoCasFixture,
  verifyDnrd5V2RestoreFixtureGenericDurability
} from "./fixtures/canonical-atom-v2-dnrd5-v2-two-cas.js"

const assertRaw = (
  fixture: Dnrd5V2RestorePreparedFixture,
  expected: "S0" | "R1" | "R2"
) => Effect.gen(function* () {
  const runtime = yield* CanonicalAtomV2DurableRuntime
  const witness = yield* recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal(runtime)
  const revision = fixture.s0Revision + (expected === "S0" ? 0 : expected === "R1" ? 1 : 2)
  expect(witness.state.canonical.revision).toBe(revision)
  // The raw journal includes its genesis slot, while history does not.
  expect(witness.journal).toHaveLength(revision + 1)
  expect(witness.history).toHaveLength(revision)
  if (expected !== "S0") {
    expect(witness.journal[fixture.s0Revision + 1]?.descriptor).toEqual(fixture.expectedR1)
  }
  if (expected === "R2") {
    expect(witness.journal[fixture.s0Revision + 2]?.descriptor).toEqual(fixture.expectedR2)
    expect(witness.state.journalHead).toEqual(fixture.expectedR2)
  }
  return witness
}).pipe(Effect.orDie)

const makeExactR1 = () => Effect.gen(function* () {
  const fixture = yield* prepareDnrd5V2RestoreFixture()
  const receiptPayload = fixture.input.receipt.writePayloads.find(
    ({ atomKeyId }) => atomKeyId !== canonicalAtomV2KeyId(fixture.input.receipt.consumption.atom.key)
  )
  if (receiptPayload === undefined) throw new Error("RESTORE fixture lacks rollback receipt payload")
  const result = yield* submitDnrd5V2RestoreTwoCas({
    ...fixture.input,
    receipt: {
      ...fixture.input.receipt,
      writePayloads: fixture.input.receipt.writePayloads.map((payload) =>
        payload.atomKeyId === receiptPayload.atomKeyId
          ? { ...payload, bytes: Uint8Array.from([...payload.bytes, 0]) }
          : payload
      )
    }
  }).pipe(Effect.either)
  expect(Either.isLeft(result)).toBe(true)
  if (Either.isLeft(result)) expect(result.left).toMatchObject({ milestone: "CAS1_EXACT_R1_RECEIPT_PENDING" })
  yield* assertRaw(fixture, "R1")
  return fixture
}).pipe(Effect.orDie)

it.effect("generic RESTORE fixture self-check commits its deterministic R1 then R2", () =>
  verifyDnrd5V2RestoreFixtureGenericDurability().pipe(
    Effect.provide(makeDnrd5V2TwoCasLayer())
  ), 15_000
)

it.effect("submits RESTORE as exact raw R1/R2 with restore and rollback atoms", () =>
  Effect.gen(function* () {
    const fixture = yield* prepareDnrd5V2RestoreFixture()
    const confirmed = yield* submitDnrd5V2RestoreTwoCas(fixture.input)
    expect(confirmed).toMatchObject({
      milestone: "CAS2_EXACT_R2_CONFIRMED",
      mainRecord: fixture.expectedR1,
      receiptRecord: fixture.expectedR2
    })
    const raw = yield* assertRaw(fixture, "R2")
    const kinds = raw.state.canonical.atoms.map((atom) => atom.kind)
    expect(kinds).toContain("hswm:dnrd5:v2:restore_transaction")
    expect(kinds).toContain("hswm:dnrd5:v2:rollback_transition_receipt")
    expect(kinds).toContain("hswm:dnrd5:v2:capability_consumption")
    expect(kinds).toContain("hswm:dnrd5:v2:evidence_seal_consumption")
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer())), 15_000
)

it.effect("rejects ADMIT and RESTORE root contracts at the opposite entrypoints without writes", () =>
  Effect.gen(function* () {
    const restore = yield* prepareDnrd5V2RestoreFixture()
    const beforeRestore = yield* assertRaw(restore, "S0")
    expect(Either.isLeft(yield* submitDnrd5V2AdmitTwoCas(restore.input).pipe(Effect.either))).toBe(true)
    expect(Either.isLeft(yield* resumeDnrd5V2AdmitTwoCas(restore.input).pipe(Effect.either))).toBe(true)
    const afterRestore = yield* assertRaw(restore, "S0")
    expect(afterRestore.journal).toEqual(beforeRestore.journal)

  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer())), 15_000
)

it("keeps RESTORE and exact-W0 evidence entrypoints out of the package root", async () => {
  const publicApi: Record<string, unknown> = await import("../src/index.js")
  for (const entrypoint of [
    "submitDnrd5V2RestoreTwoCas",
    "resumeDnrd5V2RestoreTwoCas",
    "validateDnrd5V2ExactW0RestoreProjection"
  ]) {
    expect(entrypoint in publicApi).toBe(false)
  }
})

it.effect("rejects the ADMIT root at RESTORE entrypoints without journal mutation", () =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const admit = yield* prepareDnrd5V2TwoCasFixture()
    const before = yield* runtime.snapshot
    expect(Either.isLeft(yield* submitDnrd5V2RestoreTwoCas(admit.input).pipe(Effect.either))).toBe(true)
    expect(Either.isLeft(yield* resumeDnrd5V2RestoreTwoCas(admit.input).pipe(Effect.either))).toBe(true)
    const after = yield* runtime.snapshot
    expect(after).toEqual(before)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer())), 15_000
)

it.effect("RESTORE resume is CAS2-only at exact R1, idempotent at R2, and refuses S0", () =>
  Effect.gen(function* () {
    const fixture = yield* makeExactR1()
    const confirmed = yield* resumeDnrd5V2RestoreTwoCas(fixture.input)
    expect(confirmed).toMatchObject({ milestone: "CAS2_EXACT_R2_CONFIRMED", mainRecord: fixture.expectedR1, receiptRecord: fixture.expectedR2 })
    const beforeRepeat = yield* assertRaw(fixture, "R2")
    yield* resumeDnrd5V2RestoreTwoCas(fixture.input)
    const afterRepeat = yield* assertRaw(fixture, "R2")
    expect(afterRepeat.journal).toEqual(beforeRepeat.journal)
    expect(afterRepeat.history).toEqual(beforeRepeat.history)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer())), 15_000
)

it.effect("RESTORE S0 resume and receipt grammar crosswire leave respectively S0 and exact R1", () =>
  Effect.gen(function* () {
    const fixture = yield* prepareDnrd5V2RestoreFixture()
    const before = yield* assertRaw(fixture, "S0")
    expect(Either.isLeft(yield* resumeDnrd5V2RestoreTwoCas(fixture.input).pipe(Effect.either))).toBe(true)
    expect((yield* assertRaw(fixture, "S0")).journal).toEqual(before.journal)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer())), 15_000
)

it.effect("RESTORE receipt grammar crosswire publishes only R1", () =>
  Effect.gen(function* () {
    const fixture = yield* prepareDnrd5V2RestoreFixture({ receiptGrammarCrosswire: true })
    const result = yield* submitDnrd5V2RestoreTwoCas(fixture.input).pipe(Effect.either)
    expect(Either.isLeft(result)).toBe(true)
    if (Either.isLeft(result)) expect(result.left).toMatchObject({ milestone: "CAS1_EXACT_R1_RECEIPT_PENDING" })
    const raw = yield* assertRaw(fixture, "R1")
    expect(raw.journal.some((entry) => entry.descriptor.sha256 === fixture.expectedR2.sha256)).toBe(false)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer())), 15_000
)

it.effect("rejects a legal-shape RESTORE phase mutation before CAS1 and a ROLLBACK-to-REVISION receipt mutation after only R1", () =>
  Effect.gen(function* () {
    const fixture = yield* prepareDnrd5V2RestoreFixture()
    const decodedMain = decodeCanonicalJsonBytes(fixture.input.main.consumption.payloadBytes)
    if (Either.isLeft(decodedMain)) throw new Error("RESTORE main consumption was not canonical JSON")
    const wrongPhase = canonicalJsonBytes({
      ...(decodedMain.right as Record<string, unknown>),
      phase: "MAIN_ADMIT"
    })
    if (Either.isLeft(wrongPhase)) throw new Error("cannot encode phase mutation")
    const before = yield* assertRaw(fixture, "S0")
    expect(Either.isLeft(yield* submitDnrd5V2RestoreTwoCas({
      ...fixture.input,
      main: { ...fixture.input.main, consumption: { ...fixture.input.main.consumption, payloadBytes: wrongPhase.right } }
    }).pipe(Effect.either))).toBe(true)
    expect((yield* assertRaw(fixture, "S0")).journal).toEqual(before.journal)

    const receiptPayload = fixture.input.receipt.writePayloads.find(
      ({ atomKeyId }) => atomKeyId !== canonicalAtomV2KeyId(fixture.input.receipt.consumption.atom.key)
    )
    if (receiptPayload === undefined) throw new Error("RESTORE fixture lacks rollback receipt payload")
    const decodedReceipt = decodeCanonicalJsonBytes(receiptPayload.bytes)
    if (Either.isLeft(decodedReceipt)) throw new Error("rollback receipt was not canonical JSON")
    const revisionPayload = canonicalJsonBytes({
      ...(decodedReceipt.right as Record<string, unknown>),
      receiptKind: "REVISION"
    })
    if (Either.isLeft(revisionPayload)) throw new Error("cannot encode receipt-kind mutation")
    const mutated = yield* submitDnrd5V2RestoreTwoCas({
      ...fixture.input,
      receipt: {
        ...fixture.input.receipt,
        writePayloads: fixture.input.receipt.writePayloads.map((payload) =>
          payload.atomKeyId === receiptPayload.atomKeyId
            ? { ...payload, bytes: revisionPayload.right }
            : payload
        )
      }
    }).pipe(Effect.either)
    expect(Either.isLeft(mutated)).toBe(true)
    if (Either.isLeft(mutated)) expect(mutated.left).toMatchObject({ milestone: "CAS1_EXACT_R1_RECEIPT_PENDING" })
    yield* assertRaw(fixture, "R1")
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer())), 15_000
)

it.effect("keeps all four staging/RESTORE nonces distinct and rejects staged nonce substitution before CAS1", () =>
  Effect.gen(function* () {
    const runtime = yield* CanonicalAtomV2DurableRuntime
    const fixture = yield* prepareDnrd5V2RestoreFixture()
    const staged = yield* Effect.all(
      (yield* assertRaw(fixture, "S0")).state.canonical.atoms
        .filter((atom) => atom.kind === "hswm:dnrd5:v2:capability_consumption" || atom.kind === "hswm:dnrd5:v2:evidence_seal_consumption")
        .map((atom) => runtime.readContent(atom.content))
    )
    const stagedNonces = staged.map((bytes) => {
      const decoded = decodeCanonicalJsonBytes(bytes)
      if (Either.isLeft(decoded)) throw new Error("staged consumption payload was not canonical JSON")
      return (decoded.right as Record<string, unknown>)["capabilityNonceSha256"]
    })
    const mainDecoded = decodeCanonicalJsonBytes(fixture.input.main.consumption.payloadBytes)
    const receiptDecoded = decodeCanonicalJsonBytes(fixture.input.receipt.consumption.payloadBytes)
    if (Either.isLeft(mainDecoded) || Either.isLeft(receiptDecoded)) throw new Error("RESTORE consumption payload was not canonical JSON")
    const allNonces = [...stagedNonces, (mainDecoded.right as Record<string, unknown>)["capabilityNonceSha256"], (receiptDecoded.right as Record<string, unknown>)["capabilityNonceSha256"]]
    expect(allNonces).toHaveLength(4)
    expect(new Set(allNonces).size).toBe(4)
    const collision = canonicalJsonBytes({ ...(mainDecoded.right as Record<string, unknown>), capabilityNonceSha256: stagedNonces[0] })
    if (Either.isLeft(collision)) throw new Error("cannot encode staged nonce collision")
    const before = yield* assertRaw(fixture, "S0")
    expect(Either.isLeft(yield* submitDnrd5V2RestoreTwoCas({
      ...fixture.input,
      main: { ...fixture.input.main, consumption: { ...fixture.input.main.consumption, payloadBytes: collision.right } }
    }).pipe(Effect.either))).toBe(true)
    const after = yield* assertRaw(fixture, "S0")
    expect(after.journal).toEqual(before.journal)
  }).pipe(Effect.provide(makeDnrd5V2TwoCasLayer())), 15_000
)
